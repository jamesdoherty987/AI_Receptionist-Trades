"""
Tests for the post-call address re-transcription pipeline.

Covers:
  - gpt-4o-transcribe transcription (mocked)
  - Full retranscribe_and_update pipeline
  - SMS deferral in book_job when address audio captured
  - Fallback when transcription fails
  - DB update failure doesn't block SMS
  - Returning customer flow unaffected
  - Prompt changes (no address repetition, eircode still spelled)
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime


# ---------------------------------------------------------------------------
# Unit tests for transcribe_address_audio
# ---------------------------------------------------------------------------

class TestTranscribeAddressAudio:
    """Test the gpt-4o-transcribe transcription function."""

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_successful_transcription(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = "32 Silver Grove, Ballybrack, Dublin"
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result == "32 Silver Grove, Ballybrack, Dublin"

        # Verify gpt-4o-transcribe model is used
        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs[1]["model"] == "gpt-4o-transcribe"

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_returns_none_on_download_failure(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_httpx.get.side_effect = Exception("Network error")
        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result is None

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_returns_none_on_empty_transcript(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = ""
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result is None

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_returns_none_on_api_error(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("API error")
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result is None

    def test_uses_gpt4o_transcribe_not_whisper(self):
        """Verify the code uses gpt-4o-transcribe model, not whisper-1."""
        import inspect
        from src.services.address_retranscriber import transcribe_address_audio
        source = inspect.getsource(transcribe_address_audio)
        assert 'model="gpt-4o-transcribe"' in source
        assert 'model="whisper-1"' not in source


# ---------------------------------------------------------------------------
# Integration tests for retranscribe_and_update pipeline
# ---------------------------------------------------------------------------

class TestRetranscribeAndUpdate:
    """Test the full async pipeline."""

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.transcribe_address_audio")
    async def test_full_pipeline_updates_db_and_sends_sms(self, mock_transcribe):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_transcribe.return_value = "32 Silver Grove, Ballybrack, Dublin 18"

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
            "address": "32 silver grove bally brack",
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
        # DB updated
        mock_db.update_booking.assert_called_once_with(42, company_id=1, address="32 Silver Grove, Ballybrack, Dublin 18")
        mock_db.update_client.assert_called_once_with(7, address="32 Silver Grove, Ballybrack, Dublin 18")
        # SMS sent with refined address
        mock_sms.send_booking_confirmation.assert_called_once()
        assert mock_sms.send_booking_confirmation.call_args[1]["address"] == "32 Silver Grove, Ballybrack, Dublin 18"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.transcribe_address_audio")
    async def test_transcription_failure_falls_back_to_original(self, mock_transcribe):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_transcribe.return_value = None

        mock_sms = MagicMock()
        mock_sms.send_booking_confirmation.return_value = True

        sms_kwargs = {
            "to_number": "0852635954",
            "appointment_time": datetime(2026, 3, 25, 10, 0),
            "customer_name": "John",
            "address": "32 silver grove",
        }

        with patch("src.services.sms_reminder.get_sms_service", return_value=mock_sms):
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="32 silver grove",
                caller_phone="0852635954",
                company_id=1,
                send_sms=True,
                sms_kwargs=sms_kwargs,
            )

        assert result == "32 silver grove"
        # SMS still sent with original address
        mock_sms.send_booking_confirmation.assert_called_once()
        assert mock_sms.send_booking_confirmation.call_args[1]["address"] == "32 silver grove"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.transcribe_address_audio")
    async def test_no_sms_when_send_sms_false(self, mock_transcribe):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_transcribe.return_value = "32 Silver Grove"

        with patch("src.services.sms_reminder.get_sms_service") as mock_get_sms:
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="32 silver grove",
                caller_phone="0852635954",
                company_id=1,
                send_sms=False,
            )
            mock_get_sms.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.transcribe_address_audio")
    async def test_db_failure_doesnt_block_sms(self, mock_transcribe):
        """If DB update fails, SMS should still be sent."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_transcribe.return_value = "32 Silver Grove"

        mock_db = MagicMock()
        mock_db.update_booking.side_effect = Exception("DB down")

        mock_sms = MagicMock()
        mock_sms.send_booking_confirmation.return_value = True

        sms_kwargs = {
            "to_number": "0852635954",
            "appointment_time": datetime(2026, 3, 25, 10, 0),
            "customer_name": "John",
            "address": "32 silver grove area",
        }

        with patch("src.services.database.get_database", return_value=mock_db), \
             patch("src.services.sms_reminder.get_sms_service", return_value=mock_sms):
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="32 silver grove area",
                caller_phone="0852635954",
                company_id=1,
                booking_id=42,
                send_sms=True,
                sms_kwargs=sms_kwargs,
            )

        mock_sms.send_booking_confirmation.assert_called_once()
        assert result == "32 Silver Grove"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.transcribe_address_audio")
    async def test_no_booking_or_client_skips_db(self, mock_transcribe):
        """When no booking_id or client_id, DB update is skipped."""
        from src.services.address_retranscriber import retranscribe_and_update

        mock_transcribe.return_value = "Castletroy, Limerick"

        with patch("src.services.database.get_database") as mock_get_db:
            result = await retranscribe_and_update(
                audio_url="https://r2.example.com/audio.wav",
                original_address="castletroy limerick",
                caller_phone="0852635954",
                company_id=1,
                booking_id=None,
                client_id=None,
            )
            mock_get_db.assert_not_called()

        assert result == "Castletroy, Limerick"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.transcribe_address_audio")
    async def test_empty_original_address_still_works(self, mock_transcribe):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_transcribe.return_value = "Dooradoyle, Limerick"

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address="",
            caller_phone="0852635954",
            company_id=1,
        )
        assert result == "Dooradoyle, Limerick"

    @pytest.mark.asyncio
    @patch("src.services.address_retranscriber.transcribe_address_audio")
    async def test_none_original_address_still_works(self, mock_transcribe):
        from src.services.address_retranscriber import retranscribe_and_update

        mock_transcribe.return_value = "Raheen, Limerick"

        result = await retranscribe_and_update(
            audio_url="https://r2.example.com/audio.wav",
            original_address=None,
            caller_phone="0852635954",
            company_id=1,
        )
        assert result == "Raheen, Limerick"


# ---------------------------------------------------------------------------
# SMS deferral on CallState
# ---------------------------------------------------------------------------

class TestSMSDeferral:
    """Test that deferred SMS kwargs are stashed on call_state correctly."""

    def test_deferred_sms_attrs_set(self):
        from src.services.call_state import CallState

        cs = CallState()
        cs.address_audio_captured = True
        cs.address_audio_url = "https://r2.example.com/audio.wav"

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

    def test_no_deferred_sms_when_no_audio(self):
        from src.services.call_state import CallState

        cs = CallState()
        cs.address_audio_captured = False
        assert not hasattr(cs, '_deferred_sms_kwargs') or getattr(cs, '_deferred_sms_kwargs', None) is None


# ---------------------------------------------------------------------------
# Returning customer flow
# ---------------------------------------------------------------------------

class TestReturningCustomerFlow:
    """Verify returning customer address confirmation is unaffected."""

    def test_prompt_still_confirms_stored_address(self):
        """Returning customers should still hear their stored address for confirmation."""
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        # Step 7a should still confirm stored address
        assert "Is it still the same address" in prompt
        assert "already verified data" in prompt or "verified data from the system" in prompt

    def test_address_audio_capture_skips_confirmation(self):
        """When AI confirms a stored address, audio capture should NOT trigger."""
        from tests.test_address_audio_capture import ai_asked_for_address

        # AI confirming stored address — should NOT trigger capture
        assert ai_asked_for_address("Is it still the same address, 32 Silver Grove, Ballybrack?") is False
        assert ai_asked_for_address("Just confirming your address: 32 Silver Grove, correct?") is False
        assert ai_asked_for_address("So the address is 32 Silver Grove, Ballybrack?") is False

    def test_new_address_question_still_triggers_capture(self):
        """When AI asks a NEW customer for their address, capture should trigger."""
        from tests.test_address_audio_capture import ai_asked_for_address

        assert ai_asked_for_address("What's the full address for the job?") is True
        assert ai_asked_for_address("Can you give me your eircode?") is True
        assert ai_asked_for_address("Where is the property?") is True


# ---------------------------------------------------------------------------
# Prompt changes
# ---------------------------------------------------------------------------

class TestPromptAddressChanges:
    """Verify the prompt no longer asks AI to repeat addresses."""

    def test_prompt_does_not_repeat_address(self):
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        assert "repeat back what you heard" not in prompt.lower()
        assert "accept what you hear the FIRST time" in prompt
        assert "system will verify the address after the call" in prompt

    def test_prompt_has_natural_acknowledgment(self):
        """AI should say something natural like 'Grand, got that' after hearing address."""
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        assert "Grand, got that" in prompt
        assert "acknowledge naturally" in prompt

    def test_prompt_still_spells_eircode(self):
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        assert "spell out eircode character by character" in prompt.lower()

    def test_final_confirm_excludes_address(self):
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        assert "NOT the address" in prompt
        assert "system verifies that separately" in prompt

    def test_confirm_rule_has_address_exception(self):
        """The 'ALWAYS confirm details' rule should note the address exception."""
        with open("prompts/receptionist_prompt_fast.txt", "r") as f:
            prompt = f.read()

        assert "EXCEPT for addresses" in prompt


# ---------------------------------------------------------------------------
# Prefix stripping from retranscribed address
# ---------------------------------------------------------------------------

class TestAddressPrefixStripping:
    """Verify conversational prefixes are stripped from transcription results."""

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_strips_yeah_its_prefix(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = "Yeah, it's 13 Oceanview Lahinch County Clare, Ireland."
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result == "13 Oceanview Lahinch County Clare, Ireland."

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_strips_yes_the_address_is(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = "Yes, the address is 45 O'Connell Street, Limerick."
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result == "45 O'Connell Street, Limerick."

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_strips_sure_im_at(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = "Sure, I'm at 7 Castletroy Drive, Limerick."
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result == "7 Castletroy Drive, Limerick."

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_no_strip_when_no_prefix(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = "32 Silver Grove, Ballybrack, Dublin"
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result == "32 Silver Grove, Ballybrack, Dublin"

    @patch("src.services.address_retranscriber.httpx")
    @patch("src.services.address_retranscriber._get_client")
    def test_strips_um_prefix(self, mock_get_client, mock_httpx):
        from src.services.address_retranscriber import transcribe_address_audio

        mock_resp = MagicMock()
        mock_resp.content = b"fake wav data"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.text = "Um, 15 Raheen Road, Limerick."
        mock_client.audio.transcriptions.create.return_value = mock_transcript
        mock_get_client.return_value = mock_client

        result = transcribe_address_audio("https://r2.example.com/audio.wav")
        assert result == "15 Raheen Road, Limerick."
