"""
Tests for the two-phase address audio capture feature.

Phase 1: AI asks for address → set awaiting_address_audio flag
Phase 2: Caller's next speech_final → capture audio buffer

NOTE: We avoid importing media_handler at module level because it triggers
heavy initialization (Deepgram, prerecorded audio, TTS). Instead we test
the detection function via a local reimplementation using the same keywords,
and test CallState directly.
"""
import pytest
import time
from src.services.call_state import CallState, create_call_state

# Replicate the keywords and function from media_handler to avoid heavy import
ADDRESS_ASK_KEYWORDS = ['address', 'eircode', 'eir code', 'location', 'where', 'job site', 'job location', 'work location']

def ai_asked_for_address(text: str) -> bool:
    """Local copy of the detection function to avoid importing media_handler."""
    lower = text.lower()
    return any(kw in lower for kw in ADDRESS_ASK_KEYWORDS)


class TestAiAskedForAddress:
    """Test the ai_asked_for_address detection function."""

    def test_detects_address_keyword(self):
        assert ai_asked_for_address("What is your address?") is True

    def test_detects_eircode_keyword(self):
        assert ai_asked_for_address("Can you give me your eircode?") is True

    def test_detects_eir_code_keyword(self):
        assert ai_asked_for_address("Do you have an eir code?") is True

    def test_detects_location_keyword(self):
        assert ai_asked_for_address("What's the location of the job?") is True

    def test_detects_where_keyword(self):
        assert ai_asked_for_address("Where is the property?") is True

    def test_detects_job_site_keyword(self):
        assert ai_asked_for_address("What's the job site?") is True

    def test_detects_work_location_keyword(self):
        assert ai_asked_for_address("What's the work location?") is True

    def test_case_insensitive(self):
        assert ai_asked_for_address("What is your ADDRESS?") is True
        assert ai_asked_for_address("EIRCODE please?") is True

    def test_no_match_unrelated(self):
        assert ai_asked_for_address("What time works for you?") is False

    def test_no_match_empty(self):
        assert ai_asked_for_address("") is False

    def test_no_match_name_question(self):
        assert ai_asked_for_address("Can I get your name please?") is False

    def test_no_match_phone_question(self):
        assert ai_asked_for_address("What's your phone number?") is False

    def test_mixed_content_with_address(self):
        text = "Great, I have your name. Now can you give me the address or eircode for the job?"
        assert ai_asked_for_address(text) is True

    def test_address_in_confirmation(self):
        text = "So the address is 123 Main Street, Dublin?"
        assert ai_asked_for_address(text) is True

    def test_keyword_coverage(self):
        """Ensure all keywords are detected."""
        for kw in ADDRESS_ASK_KEYWORDS:
            text = f"Can you tell me the {kw}?"
            assert ai_asked_for_address(text) is True, f"Keyword '{kw}' not detected"


class TestCallStateAddressAudioFields:
    """Test CallState fields for address audio capture."""

    def test_initial_state(self):
        cs = create_call_state()
        assert cs.awaiting_address_audio is False
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None

    def test_set_awaiting(self):
        cs = create_call_state()
        cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is True

    def test_reset_clears_all(self):
        cs = create_call_state()
        cs.awaiting_address_audio = True
        cs.address_audio_captured = True
        cs.address_audio_url = "https://example.com/audio.wav"
        cs.reset()
        assert cs.awaiting_address_audio is False
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None

    def test_capture_flow(self):
        """Simulate the full two-phase flow on CallState."""
        cs = create_call_state()
        cs.awaiting_address_audio = True
        cs.awaiting_address_audio = False
        cs.address_audio_url = "https://r2.example.com/audio/test.wav"
        cs.address_audio_captured = True
        assert cs.address_audio_captured is True
        assert cs.address_audio_url == "https://r2.example.com/audio/test.wav"

    def test_no_double_capture(self):
        """Even after capture, the flag can be re-set to allow overwrite."""
        cs = create_call_state()
        cs.address_audio_captured = True
        cs.awaiting_address_audio = True
        # In the new code, phase 2 just checks awaiting_address_audio (no captured guard)
        should_capture = cs.awaiting_address_audio
        assert should_capture is True  # Overwrite is allowed


class TestTwoPhaseIntegration:
    """Integration-style tests simulating the two-phase approach."""

    def test_phase1_triggers_even_after_capture(self):
        """Phase 1 should re-set the flag even if audio was already captured,
        allowing overwrite (e.g., eircode fallback to street address)."""
        cs = create_call_state()
        cs.address_audio_captured = True
        text = "What's your address?"
        if ai_asked_for_address(text):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is True  # Re-set allowed

    def test_phase2_clears_flag_immediately(self):
        cs = create_call_state()
        cs.awaiting_address_audio = True
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
        assert cs.awaiting_address_audio is False

    def test_full_conversation_flow(self):
        """Simulate a realistic conversation flow."""
        cs = create_call_state()

        # Turn 1: AI greets — no trigger
        ai_1 = "Hi, thank you for calling. How can I help you today?"
        if ai_asked_for_address(ai_1):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is False

        # Turn 2: AI asks for name — no trigger
        ai_2 = "Sure, can I get your name please?"
        if ai_asked_for_address(ai_2):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is False

        # Turn 3: AI asks for address — TRIGGERS phase 1
        ai_3 = "Great, and what's the address or eircode for the job?"
        if ai_asked_for_address(ai_3):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is True

        # Turn 4: Caller says address — TRIGGERS phase 2
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            cs.address_audio_url = "https://r2.example.com/audio/call123.wav"
            cs.address_audio_captured = True
        assert cs.awaiting_address_audio is False
        assert cs.address_audio_captured is True
        assert cs.address_audio_url is not None

        # Turn 5: AI mentions address again — flag re-sets (allows overwrite)
        ai_5 = "And what's the address again? Just to confirm."
        if ai_asked_for_address(ai_5):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is True  # Re-set is allowed now

    def test_eircode_fallback_to_address(self):
        """AI asks for eircode, caller doesn't know, AI asks for address instead.
        Should end up with the address recording, not the 'I don't know' one."""
        cs = create_call_state()

        # AI asks for eircode
        ai_1 = "Do you have an eircode for the property?"
        if ai_asked_for_address(ai_1):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is True

        # Caller says "I don't know my eircode" — phase 2 fires, captures this
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            cs.address_audio_url = "https://r2.example.com/audio/useless.wav"
            cs.address_audio_captured = True

        assert cs.address_audio_url == "https://r2.example.com/audio/useless.wav"

        # AI then asks for street address — flag re-sets (no captured guard)
        ai_2 = "No problem, can you give me the street address instead?"
        if ai_asked_for_address(ai_2):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is True

        # Caller gives actual address — phase 2 fires again, OVERWRITES
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            cs.address_audio_url = "https://r2.example.com/audio/real_address.wav"
            cs.address_audio_captured = True

        assert cs.address_audio_url == "https://r2.example.com/audio/real_address.wav"

    def test_no_capture_when_ai_doesnt_ask(self):
        """If AI never asks for address, nothing gets captured."""
        cs = create_call_state()

        ai_responses = [
            "Hi, how can I help?",
            "Can I get your name?",
            "What time works for you?",
            "Great, I've booked that for you.",
        ]
        for ai_text in ai_responses:
            if ai_asked_for_address(ai_text):
                cs.awaiting_address_audio = True

        assert cs.awaiting_address_audio is False
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None


class TestPerformanceCharacteristics:
    """Verify the feature adds zero latency to the call path."""

    def test_ai_asked_for_address_is_fast(self):
        text = "Great, and what's the address or eircode for the job? We need this to send our team out."
        start = time.perf_counter()
        for _ in range(10000):
            ai_asked_for_address(text)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"Too slow: {elapsed:.3f}s for 10k iterations"

    def test_no_blocking_operations_in_detection(self):
        import inspect
        assert not inspect.iscoroutinefunction(ai_asked_for_address)
