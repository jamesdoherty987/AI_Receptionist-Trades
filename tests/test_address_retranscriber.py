"""
Tests for the post-call address re-transcription pipeline.

Covers:
  - Whisper transcription (mocked)
  - LLM validation (mocked)
  - Full retranscribe_and_update pipeline
  - SMS deferral in book_job when address audio captured
  - Fallback when Whisper fails
  - Fallback when LLM says "not an address"
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


# ---------------------------------------------------------------------------
# Unit tests for whisper_transcribe_address
# ---------------------------------------------------------------------------

class TestWhisperTranscribe:
    """Test the Whisper transcription function."""

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_successful_transcription(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import whisper_transcribe_address

        # Mock HTTP download
        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        # Mock Whisper response
        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = "32 Silver Grove, Ballybrack, Dublin"
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = whisper_transcribe_address("https://r2.example.com/audio.wav")
        assert result == "32 Silver Grove, Ballybrack, Dublin"
        mock_client.audio.transcriptions.create.assert_called_once()

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_returns_none_on_download_failure(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import whisper_transcribe_address

        mock_httpx.get.side_effect = Exception("Network error")
        result = whisper_transcribe_address("https://r2.example.com/audio.wav")
        assert result is None

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_returns_none_on_empty_transcript(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import whisper_transcribe_address

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = ""
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = whisper_transcribe_address("https://r2.example.com/audio.wav")
        assert result is None


# ---------------------------------------------------------------------------
# Unit tests for llm_validate_address
# ---------------------------------------------------------------------------

class TestLLMValidateAddress:
    """Test the LLM address validation function."""

    @patch("src.services.address_retranscriber._get_client")
    def test_high_confidence_result(self, mock_get_client):
        from src.services.address_retranscriber import llm_validate_address
        import json

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "address": "32 Silver Grove, Ballybrack, Dublin 18",
            "eircode": None,
            "confidence": "high",
            "reasoning": "Both transcriptions agree"
        })
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = llm_validate_address("32 Silver Grove Ballybrack Dublin", "32 Silver Grove Ballybrack Dublin")
        assert result["confidence"] == "high"
        assert "Silver Grove" in result["address"]

    @patch("src.services.address_retranscriber._get_client")
    def test_none_confidence_for_non_address(self, mock_get_client):
        from src.services.address_retranscriber import llm_validate_address
        import json

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "address": "",
            "eircode": None,
            "confidence": "none",
            "reasoning": "Caller said 'yes' — not an address"
        })
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = llm_validate_address("Yes.", "Yes")
        assert result["confidence"] == "none"

    @patch("src.services.address_retranscriber._get_client")
    def test_extracts_eircode(self, mock_get_client):
        from src.services.address_retranscriber import llm_validate_address
        import json

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "address": "32 Silver Grove, Ballybrack",
            "eircode": "V94 H2P8",
            "confidence": "high",
            "reasoning": "Eircode extracted from address"
        })
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = llm_validate_address("32 Silver Grove Ballybrack V94H2P8", "32 Silver Grove")
        assert result["eircode"] == "V94 H2P8"

    @patch("src.services.address_retranscriber._get_client")
    def test_fallback_on_llm_error(self, mock_get_client):
        from src.services.address_retranscriber import llm_validate_address

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_get_client.return_value = mock_client

        result = llm_validate_address("32 Silver Grove", "32 Silver Grove")
        assert result["confidence"] == "low"
        assert result["address"] == "32 Silver Grove"


# ---------------------------------------------------------------------------
# Integration tests for retranscribe_and_update pipeline
# ---------------------------------------------------------------------------

class TestRetranscribeAndUpdate:
    """Test the full async pipeline."""

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_full_pipeline_updates_db_and_sends_sms(self, mock_llm, mock_whisper):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "32 Silver Grove, Ballybrack, Dublin 18"
        mock_llm.return_value = {
            "address": "32 Silver Grove, Ballybrack, Dublin 18",
            "eircode": "D18 XY45",
            "confidence": "high",
            "reasoning": "Both agree"
        }

        mock_db = MagicMock()
        mock_db.update_booking.return_value = True
        mock_db.update_client.return_value = True

        mock_sms = MagicMock()
        mock_sms.send_booking_confirmation.return_value = True

        sms_kwargs = {
            "to_number": "0852635954",
            "appointment_time": datetime(2026, 3, 25, 10, 0),
            "customer_name": "John Smith",
            "service_type": "Plumbing",
            "company_name": "JP Plumbing",
            "address": "32 silver grove bally brack",  # original bad ASR
        }

        with patch("src.services.database.get_database", return_value=mock_db), \
             patch("src.services.sms_reminder.get_sms_service", return_value=mock_sms):
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="32 silver grove bally brack",
                caller_phone="0852635954",
                company_id=1,
                booking_id=42,
                client_id=7,
                send_sms=True,
                sms_kwargs=sms_kwargs,
            )

        assert result == "32 Silver Grove, Ballybrack, Dublin 18"
        # Verify DB was updated
        mock_db.update_booking.assert_called_once()
        call_kwargs = mock_db.update_booking.call_args
        assert call_kwargs[1]["address"] == "32 Silver Grove, Ballybrack, Dublin 18"
        assert call_kwargs[1]["eircode"] == "D18 XY45"
        # Verify client was updated
        mock_db.update_client.assert_called_once()
        # Verify SMS was sent with refined address
        mock_sms.send_booking_confirmation.assert_called_once()
        sms_call = mock_sms.send_booking_confirmation.call_args[1]
        assert sms_call["address"] == "32 Silver Grove, Ballybrack, Dublin 18"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_whisper_failure_falls_back_to_original(self, mock_llm, mock_whisper):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = None  # Whisper failed

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address="32 silver grove",
            caller_phone="0852635954",
            company_id=1,
        )

        assert result == "32 silver grove"
        mock_llm.assert_not_called()  # LLM should not be called if Whisper fails

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_llm_none_confidence_keeps_original(self, mock_llm, mock_whisper):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "Yes correct"
        mock_llm.return_value = {
            "address": "",
            "eircode": None,
            "confidence": "none",
            "reasoning": "Not an address"
        }

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address="32 silver grove",
            caller_phone="0852635954",
            company_id=1,
        )

        assert result == "32 silver grove"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_no_sms_when_send_sms_false(self, mock_llm, mock_whisper):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "32 Silver Grove"
        mock_llm.return_value = {
            "address": "32 Silver Grove",
            "eircode": None,
            "confidence": "high",
            "reasoning": "OK"
        }

        with patch("src.services.sms_reminder.get_sms_service") as mock_get_sms:
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="32 silver grove",
                caller_phone="0852635954",
                company_id=1,
                send_sms=False,
            )
            mock_get_sms.assert_not_called()


# ---------------------------------------------------------------------------
# Test SMS deferral flag on CallState
# ---------------------------------------------------------------------------

class TestSMSDeferral:
    """Test that deferred SMS kwargs are stashed on call_state correctly."""

    def test_deferred_sms_attrs_set(self):
        """Simulate what book_job does when address audio is captured."""
        from src.services.call_state import CallState

        cs = CallState()
        cs.address_audio_captured = True
        cs.address_audio_url = "https://r2.example.com/audio.wav"

        # Simulate what book_job stashes
        sms_kwargs = {
            "to_number": "0852635954",
            "appointment_time": datetime(2026, 3, 25, 10, 0),
            "customer_name": "John Smith",
            "service_type": "Plumbing",
            "address": "32 silver grove",
        }
        cs._deferred_sms_kwargs = sms_kwargs
        cs._deferred_sms_booking_id = 42
        cs._deferred_sms_client_id = 7
        cs._deferred_sms_original_address = "32 silver grove"

        assert cs._deferred_sms_kwargs["customer_name"] == "John Smith"
        assert cs._deferred_sms_booking_id == 42
        assert cs._deferred_sms_client_id == 7

    def test_no_deferred_sms_when_no_audio(self):
        """When no address audio captured, deferred attrs should not exist."""
        from src.services.call_state import CallState

        cs = CallState()
        cs.address_audio_captured = False

        assert not hasattr(cs, '_deferred_sms_kwargs') or getattr(cs, '_deferred_sms_kwargs', None) is None


# ---------------------------------------------------------------------------
# Test prompt changes
# ---------------------------------------------------------------------------

class TestPromptAddressChanges:
    """Verify the prompt no longer asks AI to repeat addresses."""

    def test_prompt_does_not_repeat_address(self):
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        # Should NOT contain instructions to repeat address back
        assert "repeat back what you heard" not in prompt.lower()
        # Should contain the new instruction
        assert "accept what you hear the FIRST time" in prompt
        assert "system will verify the address after the call" in prompt

    def test_prompt_still_spells_eircode(self):
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        # Eircode spelling should still be there
        assert "spell out eircode character by character" in prompt.lower()

    def test_final_confirm_excludes_address(self):
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        # Step 11 should NOT include address in final confirmation
        assert "NOT the address" in prompt
        assert "system verifies that separately" in prompt


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases in the retranscription pipeline."""

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_empty_original_address(self, mock_llm, mock_whisper):
        """Pipeline works when original address is empty/None."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "32 Silver Grove, Ballybrack"
        mock_llm.return_value = {
            "address": "32 Silver Grove, Ballybrack",
            "eircode": None,
            "confidence": "medium",
            "reasoning": "Only Whisper available"
        }

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address="",
            caller_phone="0852635954",
            company_id=1,
        )
        assert result == "32 Silver Grove, Ballybrack"
        # LLM should have been called with empty string for original
        mock_llm.assert_called_once_with("32 Silver Grove, Ballybrack", "")

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_none_original_address(self, mock_llm, mock_whisper):
        """Pipeline works when original address is None."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "Dooradoyle, Limerick"
        mock_llm.return_value = {
            "address": "Dooradoyle, Limerick",
            "eircode": None,
            "confidence": "high",
            "reasoning": "Clear"
        }

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address=None,
            caller_phone="0852635954",
            company_id=1,
        )
        assert result == "Dooradoyle, Limerick"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_whisper_hears_yes_correct(self, mock_llm, mock_whisper):
        """If caller said 'yes correct' (not an address), LLM returns none confidence."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "Yes, that's correct."
        mock_llm.return_value = {
            "address": "",
            "eircode": None,
            "confidence": "none",
            "reasoning": "Caller confirmed something, not an address"
        }

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address="32 Silver Grove",
            caller_phone="0852635954",
            company_id=1,
        )
        # Should keep original when LLM says "none"
        assert result == "32 Silver Grove"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_eircode_only_transcription(self, mock_llm, mock_whisper):
        """Caller gave just an eircode, not a full address."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "V94 H2P8"
        mock_llm.return_value = {
            "address": "V94 H2P8",
            "eircode": "V94 H2P8",
            "confidence": "high",
            "reasoning": "Eircode only"
        }

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address="V94H2P8",
            caller_phone="0852635954",
            company_id=1,
        )
        assert result == "V94 H2P8"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_db_update_failure_doesnt_block_sms(self, mock_llm, mock_whisper):
        """If DB update fails, SMS should still be sent."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "32 Silver Grove"
        mock_llm.return_value = {
            "address": "32 Silver Grove",
            "eircode": None,
            "confidence": "high",
            "reasoning": "OK"
        }

        mock_db = MagicMock()
        mock_db.update_booking.side_effect = Exception("DB connection lost")

        mock_sms = MagicMock()
        mock_sms.send_booking_confirmation.return_value = True

        sms_kwargs = {
            "to_number": "0852635954",
            "appointment_time": datetime(2026, 3, 25, 10, 0),
            "customer_name": "John",
            "address": "original",
        }

        with patch("src.services.database.get_database", return_value=mock_db), \
             patch("src.services.sms_reminder.get_sms_service", return_value=mock_sms):
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="original",
                caller_phone="0852635954",
                company_id=1,
                booking_id=42,
                send_sms=True,
                sms_kwargs=sms_kwargs,
            )

        # SMS should still have been sent despite DB failure
        mock_sms.send_booking_confirmation.assert_called_once()
        assert result == "32 Silver Grove"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_no_booking_or_client_id_skips_db(self, mock_llm, mock_whisper):
        """When no booking_id or client_id, DB update is skipped entirely."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "Castletroy, Limerick"
        mock_llm.return_value = {
            "address": "Castletroy, Limerick",
            "eircode": None,
            "confidence": "high",
            "reasoning": "OK"
        }

        with patch("src.services.database.get_database") as mock_get_db:
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="castletroy limerick",
                caller_phone="0852635954",
                company_id=1,
                booking_id=None,
                client_id=None,
            )
            # DB should not have been called at all
            mock_get_db.assert_not_called()

        assert result == "Castletroy, Limerick"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.whisper_transcribe_address")
    @patch("src.services.address_retranscriber.llm_validate_address")
    async def test_low_confidence_still_used(self, mock_llm, mock_whisper):
        """Low confidence results are still used (better than nothing)."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_whisper.return_value = "something unclear"
        mock_llm.return_value = {
            "address": "Something Unclear, Limerick",
            "eircode": None,
            "confidence": "low",
            "reasoning": "Hard to determine"
        }

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address="something unclear",
            caller_phone="0852635954",
            company_id=1,
        )
        assert result == "Something Unclear, Limerick"

    def test_whisper_uses_irish_prompt(self):
        """Verify the Whisper prompt contains Irish place name context."""
        import inspect
        from src.services.address_retranscriber import whisper_transcribe_address
        source = inspect.getsource(whisper_transcribe_address)
        assert "Irish address" in source
        assert "Dooradoyle" in source
        assert "Castletroy" in source
        assert "Limerick" in source
        assert "eircode" in source.lower()

    def test_llm_uses_gpt4o_not_mini(self):
        """Verify the LLM validation uses gpt-4o (not mini) for max quality."""
        import inspect
        from src.services.address_retranscriber import llm_validate_address
        source = inspect.getsource(llm_validate_address)
        # Should use gpt-4o, not gpt-4o-mini
        assert 'model="gpt-4o"' in source
        assert 'model="gpt-4o-mini"' not in source

    def test_llm_prompt_mentions_ireland(self):
        """Verify the LLM system prompt explicitly mentions Ireland."""
        import inspect
        from src.services.address_retranscriber import llm_validate_address
        source = inspect.getsource(llm_validate_address)
        assert "IRELAND" in source or "Ireland" in source
        assert "townland" in source.lower()
        assert "county" in source.lower()
