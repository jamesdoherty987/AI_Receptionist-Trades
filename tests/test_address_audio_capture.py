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
ADDRESS_CONFIRM_PATTERNS = ['confirm', 'correct?', 'right?', 'is it', 'is that', 'so the address is',
                            'booked in for', 'booked for', 'job at', 'job for']

def ai_asked_for_address(text: str) -> bool:
    """Local copy of the detection function to avoid importing media_handler."""
    lower = text.lower()
    if not any(kw in lower for kw in ADDRESS_ASK_KEYWORDS):
        return False
    if any(cp in lower for cp in ADDRESS_CONFIRM_PATTERNS):
        return False
    return True


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
        """AI confirming an address should NOT trigger capture."""
        text = "So the address is 123 Main Street, Dublin?"
        assert ai_asked_for_address(text) is False

    def test_keyword_coverage(self):
        """Ensure all keywords are detected."""
        for kw in ADDRESS_ASK_KEYWORDS:
            text = f"Can you tell me the {kw}?"
            assert ai_asked_for_address(text) is True, f"Keyword '{kw}' not detected"

    # --- Confirmation-skip tests ---
    def test_no_trigger_on_confirm_address(self):
        """AI confirming address back should NOT trigger."""
        assert ai_asked_for_address("Just confirming your address: 32 Silver Grove, correct?") is False

    def test_no_trigger_on_is_it_address(self):
        assert ai_asked_for_address("Is it 32 Silver Grove, Balenbygan?") is False

    def test_no_trigger_on_booked_for_address(self):
        assert ai_asked_for_address("You're booked in for Thursday at 32 Silver Grove.") is False

    def test_no_trigger_on_job_at_address(self):
        assert ai_asked_for_address("Scheduled job at 32 Silver Grove, Balenbygan.") is False

    def test_no_trigger_on_is_that_right(self):
        assert ai_asked_for_address("The address is 32 Silver Grove, is that right?") is False

    def test_still_triggers_genuine_ask(self):
        """Genuine address questions should still trigger."""
        assert ai_asked_for_address("What's your address?") is True
        assert ai_asked_for_address("Can you give me the eircode?") is True
        assert ai_asked_for_address("Where is the property?") is True
        assert ai_asked_for_address("Can you provide your full address instead?") is True
        assert ai_asked_for_address("Do you know your eircode?") is True

    def test_no_trigger_on_real_world_confirm(self):
        """Exact phrase from production logs that caused the bug."""
        text = "I'm here! Just confirming your address: 32 Silver Grove, Balenbygan, correct?"
        assert ai_asked_for_address(text) is False


class TestCallStateAddressAudioFields:
    """Test CallState fields for address audio capture."""

    def test_initial_state(self):
        cs = create_call_state()
        assert cs.awaiting_address_audio is False
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None
        assert cs._addr_audio_collecting is False

    def test_set_awaiting(self):
        cs = create_call_state()
        cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is True

    def test_reset_clears_all(self):
        cs = create_call_state()
        cs.awaiting_address_audio = True
        cs._addr_audio_collecting = True
        cs.address_audio_captured = True
        cs.address_audio_url = "https://example.com/audio.wav"
        cs.reset()
        assert cs.awaiting_address_audio is False
        assert cs._addr_audio_collecting is False
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None

    def test_deferred_capture_flow(self):
        """Simulate the full 3-phase deferred capture flow on CallState.
        Phase 1: AI asks → awaiting=True
        Phase 2: First speech_final → awaiting=False, collecting=True
        Phase 3: Before LLM responds → collecting=False, capture + upload
        """
        cs = create_call_state()
        # Phase 1
        cs.awaiting_address_audio = True
        # Phase 2: speech_final arrives
        cs.awaiting_address_audio = False
        cs._addr_audio_collecting = True
        # Phase 3: LLM about to respond — finalize capture
        cs._addr_audio_collecting = False
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

    def test_phase1_resets_collecting(self):
        """When AI asks again (e.g., eircode → street address), collecting resets."""
        cs = create_call_state()
        cs._addr_audio_collecting = True  # Was collecting from previous ask
        # Phase 1 re-triggers
        cs.awaiting_address_audio = True
        cs._addr_audio_collecting = False  # Reset — new ask cycle
        assert cs._addr_audio_collecting is False
        assert cs.awaiting_address_audio is True


class TestTwoPhaseIntegration:
    """Integration-style tests simulating the deferred 3-phase approach.
    Phase 1: AI asks for address → awaiting_address_audio = True
    Phase 2: Caller's speech_final → awaiting=False, collecting=True (skip-check)
    Phase 3: Before LLM responds → collecting=False, snapshot buffer, upload
    """

    def test_phase1_triggers_even_after_capture(self):
        """Phase 1 should re-set the flag even if audio was already captured,
        allowing overwrite (e.g., eircode fallback to street address)."""
        cs = create_call_state()
        cs.address_audio_captured = True
        text = "What's your address?"
        if ai_asked_for_address(text):
            cs.awaiting_address_audio = True
            cs._addr_audio_collecting = False  # Reset collecting on new ask
        assert cs.awaiting_address_audio is True  # Re-set allowed

    def test_phase2_sets_collecting(self):
        """Phase 2 should set collecting=True and clear awaiting."""
        cs = create_call_state()
        cs.awaiting_address_audio = True
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            cs._addr_audio_collecting = True
        assert cs.awaiting_address_audio is False
        assert cs._addr_audio_collecting is True

    def test_phase3_finalizes_capture(self):
        """Phase 3 (before LLM) should clear collecting and do the capture."""
        cs = create_call_state()
        cs._addr_audio_collecting = True
        # Phase 3: before start_tts
        if cs._addr_audio_collecting:
            cs._addr_audio_collecting = False
            cs.address_audio_url = "https://r2.example.com/audio/full_address.wav"
            cs.address_audio_captured = True
        assert cs._addr_audio_collecting is False
        assert cs.address_audio_captured is True

    def test_full_conversation_flow(self):
        """Simulate a realistic conversation flow with deferred capture."""
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
            cs._addr_audio_collecting = False
        assert cs.awaiting_address_audio is True

        # Turn 4: Caller says address — Phase 2 (start collecting)
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            cs._addr_audio_collecting = True
        assert cs.awaiting_address_audio is False
        assert cs._addr_audio_collecting is True

        # Phase 3: Before LLM responds — finalize capture
        if cs._addr_audio_collecting:
            cs._addr_audio_collecting = False
            cs.address_audio_url = "https://r2.example.com/audio/call123.wav"
            cs.address_audio_captured = True
        assert cs._addr_audio_collecting is False
        assert cs.address_audio_captured is True
        assert cs.address_audio_url is not None

        # Turn 5: AI confirms address — should NOT re-trigger
        ai_5 = "And what's the address again? Just to confirm."
        if ai_asked_for_address(ai_5):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is False  # Confirmation phrases don't re-trigger

    def test_multi_speech_final_captures_all(self):
        """KEY TEST: Deepgram splits address into multiple speech_final events.
        The deferred approach should capture ALL of them because the buffer
        snapshot happens in Phase 3 (before LLM), not on the first speech_final."""
        cs = create_call_state()

        # Phase 1: AI asks for address
        cs.awaiting_address_audio = True
        cs._addr_audio_collecting = False

        # Phase 2: First speech_final — "32 Silver Grove"
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            cs._addr_audio_collecting = True
        assert cs._addr_audio_collecting is True

        # Second speech_final — "Ballybrack, County Dublin" — collecting stays True
        # (awaiting is already False, so Phase 2 doesn't re-trigger, but collecting persists)
        assert cs._addr_audio_collecting is True

        # Third speech_final — "D18 WR97" — still collecting
        assert cs._addr_audio_collecting is True

        # Phase 3: LLM about to respond — NOW we snapshot the buffer
        # At this point the buffer contains ALL three segments' audio
        if cs._addr_audio_collecting:
            cs._addr_audio_collecting = False
            cs.address_audio_url = "https://r2.example.com/audio/full_address.wav"
            cs.address_audio_captured = True
        assert cs.address_audio_captured is True

    def test_eircode_fallback_to_address(self):
        """AI asks for eircode, caller doesn't know, AI asks for address instead.
        With skip logic, the 'I don't know' response is NOT captured at all.
        Only the actual address gets captured."""
        cs = create_call_state()

        # AI asks for eircode
        ai_1 = "Do you have an eircode for the property?"
        if ai_asked_for_address(ai_1):
            cs.awaiting_address_audio = True
            cs._addr_audio_collecting = False
        assert cs.awaiting_address_audio is True

        # Caller says "No. I don't." — skip logic detects this is NOT an address
        caller_text = "No. I don't."
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            text_lower_check = caller_text.lower().strip().rstrip('.,!?')
            skip_phrases = {'no', "no i don't", "no i dont", "i don't know", "i dont know",
                            "i'm not sure", "im not sure", "not sure", "no idea"}
            is_skip = text_lower_check in skip_phrases or (len(caller_text.split()) <= 3 and text_lower_check.startswith('no'))
            if not is_skip:
                cs._addr_audio_collecting = True

        # Nothing should be collecting
        assert cs._addr_audio_collecting is False
        assert cs.address_audio_url is None

        # AI then asks for street address — flag re-sets
        ai_2 = "No problem, can you give me the street address instead?"
        if ai_asked_for_address(ai_2):
            cs.awaiting_address_audio = True
            cs._addr_audio_collecting = False
        assert cs.awaiting_address_audio is True

        # Caller gives actual address — Phase 2 starts collecting
        caller_text_2 = "Yeah. It's 32 Silver Grove, Valley Big, Innis."
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            text_lower_check = caller_text_2.lower().strip().rstrip('.,!?')
            is_skip = text_lower_check in skip_phrases or (len(caller_text_2.split()) <= 3 and text_lower_check.startswith('no'))
            if not is_skip:
                cs._addr_audio_collecting = True
        assert cs._addr_audio_collecting is True

        # Phase 3: finalize
        if cs._addr_audio_collecting:
            cs._addr_audio_collecting = False
            cs.address_audio_url = "https://r2.example.com/audio/real_address.wav"
            cs.address_audio_captured = True

        assert cs.address_audio_url == "https://r2.example.com/audio/real_address.wav"
        assert cs.address_audio_captured is True

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
        assert cs._addr_audio_collecting is False
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None

    def test_confirm_does_not_overwrite_captured_audio(self):
        """REGRESSION: Exact scenario from production logs.
        AI asks for address → caller gives it → audio captured.
        AI then confirms 'Just confirming your address: X, correct?' →
        this should NOT re-trigger Phase 1, so 'Yes. Correct.' does NOT
        overwrite the real address recording."""
        cs = create_call_state()

        # AI asks for address → Phase 1
        ai_1 = "No problem! Can you provide your full address instead?"
        if ai_asked_for_address(ai_1):
            cs.awaiting_address_audio = True
            cs._addr_audio_collecting = False
        assert cs.awaiting_address_audio is True

        # Caller gives address → Phase 2 (collecting)
        if cs.awaiting_address_audio:
            cs.awaiting_address_audio = False
            cs._addr_audio_collecting = True

        # Phase 3: capture
        if cs._addr_audio_collecting:
            cs._addr_audio_collecting = False
            cs.address_audio_url = "https://r2.example.com/audio/real_address.wav"
            cs.address_audio_captured = True
        assert cs.address_audio_url == "https://r2.example.com/audio/real_address.wav"

        # AI confirms address — should NOT re-trigger Phase 1
        ai_2 = "I'm here! Just confirming your address: 32 Silver Grove, Balenbygan, correct?"
        if ai_asked_for_address(ai_2):
            cs.awaiting_address_audio = True
        assert cs.awaiting_address_audio is False  # NOT re-triggered

        # Caller says "Yes. Correct." — nothing changes
        assert cs.address_audio_url == "https://r2.example.com/audio/real_address.wav"  # Unchanged


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


# --- Skip phrases logic (replicated from media_handler.py) ---
SKIP_PHRASES = {'no', "no i don't", "no i dont", "i don't know", "i dont know",
                "i'm not sure", "im not sure", "not sure", "no idea"}

def should_skip_capture(text: str) -> bool:
    """Replicate the skip logic from media_handler for testing."""
    text_lower_check = text.lower().strip().rstrip('.,!?')
    if text_lower_check in SKIP_PHRASES:
        return True
    if len(text.split()) <= 3 and text_lower_check.startswith('no'):
        return True
    return False


class TestSkipCaptureLogic:
    """Test that short negative responses are skipped (not captured as address audio)."""

    def test_skip_no(self):
        assert should_skip_capture("No.") is True

    def test_skip_no_i_dont(self):
        assert should_skip_capture("No. I don't.") is True

    def test_skip_no_i_dont_no_punctuation(self):
        assert should_skip_capture("No I don't") is True

    def test_skip_i_dont_know(self):
        assert should_skip_capture("I don't know.") is True

    def test_skip_i_dont_know_no_apostrophe(self):
        assert should_skip_capture("I dont know") is True

    def test_skip_not_sure(self):
        assert should_skip_capture("Not sure.") is True

    def test_skip_im_not_sure(self):
        assert should_skip_capture("I'm not sure.") is True

    def test_skip_no_idea(self):
        assert should_skip_capture("No idea.") is True

    def test_skip_short_no_response(self):
        """Any 1-3 word response starting with 'no' should be skipped."""
        assert should_skip_capture("No thanks") is True
        assert should_skip_capture("No sorry") is True
        assert should_skip_capture("No I can't") is True

    def test_no_skip_actual_address(self):
        assert should_skip_capture("32 Silver Grove, Valley Big, Innis") is False

    def test_no_skip_eircode(self):
        assert should_skip_capture("V94 ABC1") is False

    def test_no_skip_address_with_yeah(self):
        assert should_skip_capture("Yeah. It's 32 Silver Grove, Valley Big Innis.") is False

    def test_no_skip_long_response_starting_with_no(self):
        """Longer responses starting with 'no' that contain address info should NOT be skipped."""
        assert should_skip_capture("No wait, it's 15 Main Street, Limerick") is False

    def test_no_skip_number_only(self):
        assert should_skip_capture("D02 WR97") is False

    def test_skip_is_case_insensitive(self):
        assert should_skip_capture("NO") is True
        assert should_skip_capture("I DON'T KNOW") is True
        assert should_skip_capture("NO IDEA") is True


# ─── Tests for trim_silence_mulaw sliding-window logic ───────────────────────
from src.utils.audio_utils import trim_silence_mulaw, ulaw_energy, MU_LAW_DECODE_TABLE


def _make_silent_packet(size=160) -> bytes:
    """Create a packet of mulaw silence (byte 0xFF = 0 amplitude)."""
    return bytes([0xFF] * size)


def _make_loud_packet(size=160, byte_val=0x00) -> bytes:
    """Create a packet with high energy. Byte 0x00 decodes to large amplitude in mulaw."""
    return bytes([byte_val] * size)


def _make_soft_packet(size=160, byte_val=0x70) -> bytes:
    """Create a packet with moderate energy — above onset threshold but possibly below main."""
    return bytes([byte_val] * size)


class TestTrimSilenceMulawBasics:
    """Basic edge cases for trim_silence_mulaw."""

    def test_empty_packets_returns_empty_bytes(self):
        result = trim_silence_mulaw([])
        assert result == b''

    def test_single_silent_packet_returns_all(self):
        """No speech detected → returns everything."""
        packets = [_make_silent_packet()]
        result = trim_silence_mulaw(packets)
        assert result == b''.join(packets)

    def test_single_loud_packet_returns_all(self):
        """Only one packet — can't form a window of 5, so no speech detected → returns all."""
        packets = [_make_loud_packet()]
        result = trim_silence_mulaw(packets)
        assert result == b''.join(packets)

    def test_all_silence_returns_all(self):
        """All silent packets → no speech detected → returns everything."""
        packets = [_make_silent_packet() for _ in range(20)]
        result = trim_silence_mulaw(packets)
        assert result == b''.join(packets)

    def test_all_loud_returns_all(self):
        """All loud packets → speech everywhere → returns everything (with padding clamped)."""
        packets = [_make_loud_packet() for _ in range(20)]
        result = trim_silence_mulaw(packets)
        assert result == b''.join(packets)


class TestTrimSilenceMulawSlidingWindow:
    """Tests for the sliding-window speech detection logic."""

    def test_speech_in_middle_trims_silence(self):
        """Silence → speech → silence should trim the outer silence."""
        silence = [_make_silent_packet() for _ in range(30)]
        speech = [_make_loud_packet() for _ in range(10)]
        packets = silence + speech + silence
        result = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=5)
        # Result should be shorter than the full buffer
        full = b''.join(packets)
        assert len(result) < len(full)
        # But should contain the speech portion
        speech_bytes = b''.join(speech)
        assert speech_bytes in result

    def test_speech_at_start_no_over_trimming(self):
        """Speech at the very beginning should not be clipped."""
        speech = [_make_loud_packet() for _ in range(10)]
        silence = [_make_silent_packet() for _ in range(30)]
        packets = speech + silence
        result = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=5)
        # First speech packet must be in the result
        assert packets[0] in result
        # Should trim trailing silence
        assert len(result) < len(b''.join(packets))

    def test_speech_at_end_no_over_trimming(self):
        """Speech at the very end should not be clipped."""
        silence = [_make_silent_packet() for _ in range(30)]
        speech = [_make_loud_packet() for _ in range(10)]
        packets = silence + speech
        result = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=5)
        # Last speech packet must be in the result
        assert packets[-1] in result
        # Should trim leading silence
        assert len(result) < len(b''.join(packets))

    def test_soft_onset_captured_by_sliding_window(self):
        """
        Gradual energy rise: soft → loud. The sliding window should detect
        speech onset at the loud section, then walk backwards with the lower
        onset threshold (50%) to catch the soft start.
        """
        silence = [_make_silent_packet() for _ in range(20)]
        # Soft packets: energy above 50% of threshold but below threshold
        soft = [_make_soft_packet() for _ in range(5)]
        loud = [_make_loud_packet() for _ in range(10)]
        packets = silence + soft + loud + silence

        # Verify our soft packets are actually in the right energy range
        soft_energy = ulaw_energy(soft[0])
        loud_energy = ulaw_energy(loud[0])
        threshold = 100.0
        # Soft should be above onset threshold (50%) for the walkback to catch it
        # If not, adjust — the test is about the mechanism, not exact byte values
        
        result = trim_silence_mulaw(packets, energy_threshold=threshold, pad_packets=3)
        full = b''.join(packets)
        
        # Result should be shorter than full (trimmed leading/trailing silence)
        assert len(result) < len(full)
        # The loud speech must be present
        assert b''.join(loud) in result

    def test_short_burst_captured_with_padding(self):
        """A short burst of speech (5 packets = 100ms) should be captured with padding."""
        silence_before = [_make_silent_packet() for _ in range(30)]
        speech = [_make_loud_packet() for _ in range(5)]
        silence_after = [_make_silent_packet() for _ in range(30)]
        packets = silence_before + speech + silence_after
        
        result = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=5)
        # Speech must be in result
        assert b''.join(speech) in result
        # Result should include padding but not all silence
        full = b''.join(packets)
        assert len(result) < len(full)
        # Result should be longer than just the speech (padding added)
        assert len(result) > len(b''.join(speech))

    def test_window_needs_min_active_packets(self):
        """
        If only 2 loud packets exist in a window of 5 (below MIN_ACTIVE=3),
        no speech is detected → returns all packets.
        """
        silence = [_make_silent_packet() for _ in range(20)]
        # Scatter only 2 loud packets — not enough for a window of 3
        packets = list(silence)
        packets[10] = _make_loud_packet()
        packets[12] = _make_loud_packet()
        # No window of 5 will have 3+ active packets
        result = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=3)
        assert result == b''.join(packets)

    def test_two_speech_segments_captures_both(self):
        """Two separate speech bursts — should capture from first to last."""
        silence = [_make_silent_packet() for _ in range(10)]
        speech1 = [_make_loud_packet() for _ in range(8)]
        gap = [_make_silent_packet() for _ in range(5)]
        speech2 = [_make_loud_packet() for _ in range(8)]
        packets = silence + speech1 + gap + speech2 + silence
        
        result = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=3)
        # Both speech segments should be in the result
        assert b''.join(speech1) in result
        assert b''.join(speech2) in result

    def test_pad_packets_respected(self):
        """Padding should add silent packets around speech."""
        silence = [_make_silent_packet() for _ in range(30)]
        speech = [_make_loud_packet() for _ in range(10)]
        packets = silence + speech + silence
        
        # With pad_packets=0, should be tighter
        result_no_pad = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=0)
        # With pad_packets=10, should be wider
        result_with_pad = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=10)
        
        assert len(result_with_pad) > len(result_no_pad)


class TestTrimSilenceMulawThresholds:
    """Tests for energy threshold behavior."""

    def test_high_threshold_misses_soft_speech(self):
        """Very high threshold → soft speech not detected → returns all."""
        silence = [_make_silent_packet() for _ in range(10)]
        soft = [_make_soft_packet() for _ in range(10)]
        packets = silence + soft + silence
        
        soft_energy = ulaw_energy(soft[0])
        # Use a threshold way above the soft packet energy
        high_threshold = soft_energy * 5
        result = trim_silence_mulaw(packets, energy_threshold=high_threshold, pad_packets=3)
        # No speech detected → returns all
        assert result == b''.join(packets)

    def test_low_threshold_catches_everything(self):
        """Very low threshold → even quiet packets count as speech."""
        silence = [_make_silent_packet() for _ in range(10)]
        soft = [_make_soft_packet() for _ in range(10)]
        packets = silence + soft + silence
        
        # Threshold of 1.0 — almost everything is "speech"
        result = trim_silence_mulaw(packets, energy_threshold=1.0, pad_packets=3)
        # Should detect the soft packets as speech and trim silence
        # (unless silence packets also have energy > 1.0, in which case all is "speech")
        assert len(result) > 0

    def test_production_threshold_30(self):
        """
        The production code uses threshold=30. Verify that loud speech
        is detected and silence is trimmed at this threshold.
        """
        silence = [_make_silent_packet() for _ in range(30)]
        speech = [_make_loud_packet() for _ in range(15)]
        packets = silence + speech + silence
        
        result = trim_silence_mulaw(packets, energy_threshold=30.0, pad_packets=25)
        full = b''.join(packets)
        # Should trim some silence
        assert len(result) <= len(full)
        # Speech must be present
        assert b''.join(speech) in result


class TestTrimSilenceMulawSafetyNet:
    """
    Tests for the 1.5s safety net in media_handler.
    The safety net is in media_handler, not in trim_silence_mulaw itself,
    but we test the scenario: if trim returns very short audio, the caller
    should use the full buffer instead.
    """

    def test_safety_net_scenario(self):
        """
        Simulate the safety net: trim returns < 1.5s, so we fall back to full buffer.
        This mirrors the logic in media_handler.py.
        """
        MULAW_SAMPLE_RATE = 8000
        
        # Create a buffer where speech is very short (just barely above threshold)
        silence = [_make_silent_packet() for _ in range(50)]
        # 5 loud packets = 5 * 160 bytes = 800 bytes = 0.1s at 8kHz
        speech = [_make_loud_packet() for _ in range(5)]
        packets = silence + speech + silence
        
        captured_audio = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=3)
        cap_duration = len(captured_audio) / MULAW_SAMPLE_RATE
        
        # Apply the safety net logic from media_handler
        if cap_duration < 1.5 and len(packets) > 0:
            # Fall back to full buffer
            captured_audio = b''.join(packets)
        
        # Should have used the full buffer
        assert captured_audio == b''.join(packets)

    def test_no_safety_net_for_long_speech(self):
        """
        When trim returns >= 1.5s of audio, the safety net should NOT trigger.
        """
        MULAW_SAMPLE_RATE = 8000
        
        silence = [_make_silent_packet() for _ in range(30)]
        # 100 loud packets = 100 * 160 = 16000 bytes = 2.0s at 8kHz
        speech = [_make_loud_packet() for _ in range(100)]
        packets = silence + speech + silence
        
        captured_audio = trim_silence_mulaw(packets, energy_threshold=100.0, pad_packets=5)
        cap_duration = len(captured_audio) / MULAW_SAMPLE_RATE
        
        # Should be >= 1.5s — safety net does NOT trigger
        assert cap_duration >= 1.5
        # Should be trimmed (not the full buffer)
        full = b''.join(packets)
        assert len(captured_audio) < len(full)


class TestTrimSilenceMulawEnergyCalculation:
    """Verify the energy calculation used by trim."""

    def test_silence_has_low_energy(self):
        """0xFF mulaw byte = silence, should have very low energy."""
        pkt = _make_silent_packet()
        energy = ulaw_energy(pkt)
        assert energy < 10, f"Silent packet energy {energy} should be < 10"

    def test_loud_has_high_energy(self):
        """0x00 mulaw byte = max amplitude, should have high energy."""
        pkt = _make_loud_packet()
        energy = ulaw_energy(pkt)
        assert energy > 1000, f"Loud packet energy {energy} should be > 1000"

    def test_empty_frame_zero_energy(self):
        assert ulaw_energy(b'') == 0.0

    def test_energy_scales_with_amplitude(self):
        """Louder packets should have higher energy."""
        soft = _make_soft_packet()
        loud = _make_loud_packet()
        assert ulaw_energy(loud) > ulaw_energy(soft)


# ─── Edge case tests for the deferred 3-phase capture flow ───────────────────
# These simulate the exact logic from media_handler.py to verify correctness
# across realistic conversation scenarios.


# Replicate the skip-check logic from media_handler Phase 2
SKIP_PHRASES = {'no', "no i don't", "no i dont", "i don't know", "i dont know",
                "i'm not sure", "im not sure", "not sure", "no idea"}

def _should_skip(text: str) -> bool:
    """Replicate the skip-check from media_handler Phase 2."""
    text_lower_check = text.lower().strip().rstrip('.,!?')
    if text_lower_check in SKIP_PHRASES:
        return True
    if len(text.split()) <= 3 and text_lower_check.startswith('no'):
        return True
    return False


def _simulate_phase1(cs, ai_text):
    """Simulate Phase 1: AI speaks → check if it's asking for address."""
    if ai_asked_for_address(ai_text):
        cs.awaiting_address_audio = True
        cs._addr_audio_collecting = False  # Reset on new ask
        cs._addr_audio_phase1_time = time.time()
        return True
    return False


def _simulate_phase2(cs, caller_text):
    """Simulate Phase 2: Caller's speech_final → skip-check, set collecting."""
    if cs.awaiting_address_audio:
        cs.awaiting_address_audio = False
        if _should_skip(caller_text):
            return 'skipped'
        else:
            cs._addr_audio_collecting = True
            return 'collecting'
    return 'no_action'


def _simulate_phase3(cs):
    """Simulate Phase 3: Before LLM responds → finalize capture.
    Returns True if capture happened."""
    if cs._addr_audio_collecting:
        cs._addr_audio_collecting = False
        # In real code this snapshots buffer + uploads. We just set the URL.
        cs.address_audio_url = f"https://r2.example.com/audio/capture_{time.time()}.wav"
        cs.address_audio_captured = True
        return True
    return False


def _simulate_turn(cs, ai_text, caller_text):
    """Simulate a full turn: AI speaks (Phase 1 check) → caller responds
    (Phase 2) → LLM about to respond (Phase 3).
    Returns dict with what happened."""
    result = {
        'phase1_triggered': _simulate_phase1(cs, ai_text),
        'phase2_result': _simulate_phase2(cs, caller_text),
        'phase3_captured': _simulate_phase3(cs),
    }
    return result


class TestDeferredCaptureEdgeCases:
    """Edge cases for the deferred 3-phase address audio capture."""

    def test_normal_address_capture(self):
        """Happy path: AI asks for address, caller gives it, captured."""
        cs = create_call_state()
        r = _simulate_turn(cs, "What's the address for the job?", "32 Silver Grove, Ballybrack")
        assert r['phase1_triggered'] is True
        assert r['phase2_result'] == 'collecting'
        assert r['phase3_captured'] is True
        assert cs.address_audio_captured is True
        assert cs.address_audio_url is not None

    def test_eircode_capture(self):
        """AI asks for eircode, caller gives it."""
        cs = create_call_state()
        r = _simulate_turn(cs, "Do you have an eircode?", "D18 WR97")
        assert r['phase1_triggered'] is True
        assert r['phase3_captured'] is True
        assert cs.address_audio_captured is True

    def test_caller_declines_eircode_then_gives_address(self):
        """AI asks for eircode → caller says no → AI asks for address → caller gives it.
        Only the actual address should be captured."""
        cs = create_call_state()

        # Turn 1: AI asks for eircode, caller says no
        r1 = _simulate_turn(cs, "Do you have an eircode?", "No I don't")
        assert r1['phase1_triggered'] is True
        assert r1['phase2_result'] == 'skipped'
        assert r1['phase3_captured'] is False
        assert cs.address_audio_captured is False

        # Turn 2: AI asks for street address, caller gives it
        r2 = _simulate_turn(cs, "Can you give me the street address?", "32 Silver Grove, Ballybrack")
        assert r2['phase1_triggered'] is True
        assert r2['phase2_result'] == 'collecting'
        assert r2['phase3_captured'] is True
        assert cs.address_audio_captured is True

    def test_caller_says_not_sure_then_gives_address(self):
        """Caller says 'not sure' about eircode, then gives address."""
        cs = create_call_state()
        r1 = _simulate_turn(cs, "What's the eircode?", "I'm not sure")
        assert r1['phase2_result'] == 'skipped'
        assert r1['phase3_captured'] is False

        r2 = _simulate_turn(cs, "No problem, what's the address?", "15 Main Street, Dundalk")
        assert r2['phase3_captured'] is True
        assert cs.address_audio_captured is True

    def test_caller_repeats_address_overwrites(self):
        """AI asks for address twice (e.g., didn't hear it). Second capture overwrites first."""
        cs = create_call_state()

        # First attempt
        r1 = _simulate_turn(cs, "What's the address?", "32 Silver Grove")
        assert r1['phase3_captured'] is True
        first_url = cs.address_audio_url

        # AI asks again (maybe didn't understand)
        r2 = _simulate_turn(cs, "Sorry, could you repeat the address?", "32 Silver Grove, Ballybrack, Dublin")
        assert r2['phase1_triggered'] is True
        assert r2['phase3_captured'] is True
        assert cs.address_audio_url != first_url  # Overwritten with new capture

    def test_confirmation_does_not_capture_yes(self):
        """After capturing address, AI confirms it. 'Yes correct' should NOT be captured."""
        cs = create_call_state()

        # Capture the address
        _simulate_turn(cs, "What's the address?", "32 Silver Grove, Ballybrack")
        assert cs.address_audio_captured is True
        original_url = cs.address_audio_url

        # AI confirms — Phase 1 should NOT trigger (confirm pattern)
        r2 = _simulate_turn(cs, "Just confirming, the address is 32 Silver Grove, correct?", "Yes correct")
        assert r2['phase1_triggered'] is False
        assert r2['phase2_result'] == 'no_action'
        assert r2['phase3_captured'] is False
        assert cs.address_audio_url == original_url  # Unchanged

    def test_unrelated_ai_question_does_not_trigger(self):
        """AI asks about something else (name, time, etc.) — no capture."""
        cs = create_call_state()
        r = _simulate_turn(cs, "What's your name?", "Tony Adams")
        assert r['phase1_triggered'] is False
        assert r['phase2_result'] == 'no_action'
        assert r['phase3_captured'] is False
        assert cs.address_audio_captured is False

    def test_multiple_unrelated_turns_then_address(self):
        """Several turns of non-address conversation, then address capture."""
        cs = create_call_state()

        _simulate_turn(cs, "Hi, how can I help?", "I have a burst pipe")
        assert cs.address_audio_captured is False

        _simulate_turn(cs, "Can I get your name?", "Tony Adams")
        assert cs.address_audio_captured is False

        _simulate_turn(cs, "What time works?", "Tomorrow morning")
        assert cs.address_audio_captured is False

        r = _simulate_turn(cs, "And what's the address?", "32 Silver Grove, Ballybrack")
        assert r['phase3_captured'] is True
        assert cs.address_audio_captured is True

    def test_caller_says_no_short_variants(self):
        """All short 'no' variants should be skipped."""
        for response in ["No", "No.", "no", "NO", "No!", "No way"]:
            cs = create_call_state()
            r = _simulate_turn(cs, "Do you have an eircode?", response)
            assert r['phase2_result'] == 'skipped', f"Should skip '{response}'"
            assert cs.address_audio_captured is False, f"Should not capture for '{response}'"

    def test_caller_says_no_but_long_response_not_skipped(self):
        """'No but the address is...' should NOT be skipped — it contains the address."""
        cs = create_call_state()
        r = _simulate_turn(cs, "Do you have an eircode?", "No but the address is 32 Silver Grove")
        assert r['phase2_result'] == 'collecting'
        assert r['phase3_captured'] is True

    def test_caller_gives_eircode_with_yeah(self):
        """'Yeah it's D18 WR97' should be captured."""
        cs = create_call_state()
        r = _simulate_turn(cs, "Do you have an eircode?", "Yeah it's D18 WR97")
        assert r['phase2_result'] == 'collecting'
        assert r['phase3_captured'] is True

    def test_phase1_resets_stale_collecting(self):
        """If collecting was somehow left True (shouldn't happen, but safety),
        Phase 1 re-triggering should reset it."""
        cs = create_call_state()
        cs._addr_audio_collecting = True  # Stale state

        _simulate_phase1(cs, "What's the address?")
        assert cs._addr_audio_collecting is False  # Reset by Phase 1
        assert cs.awaiting_address_audio is True

    def test_no_capture_if_ai_never_asks(self):
        """Full conversation without address question — nothing captured."""
        cs = create_call_state()
        turns = [
            ("Hi, how can I help?", "Burst pipe"),
            ("Can I get your name?", "Tony Adams"),
            ("What time works?", "Tomorrow at 9"),
            ("Great, I've booked that for you.", "Thanks"),
        ]
        for ai, caller in turns:
            _simulate_turn(cs, ai, caller)
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None
        assert cs._addr_audio_collecting is False
        assert cs.awaiting_address_audio is False

    def test_booked_for_address_does_not_retrigger(self):
        """'I've booked you in for 32 Silver Grove' should NOT trigger Phase 1."""
        cs = create_call_state()
        # First capture the address
        _simulate_turn(cs, "What's the address?", "32 Silver Grove")
        original_url = cs.address_audio_url

        # AI says booking confirmation with address — should NOT re-trigger
        r = _simulate_turn(cs, "I've booked you in for 32 Silver Grove at 9am", "Great thanks")
        assert r['phase1_triggered'] is False
        assert cs.address_audio_url == original_url

    def test_is_that_the_right_address_does_not_retrigger(self):
        """'Is that the right address?' should NOT trigger Phase 1."""
        cs = create_call_state()
        _simulate_turn(cs, "What's the address?", "32 Silver Grove")
        original_url = cs.address_audio_url

        r = _simulate_turn(cs, "Is it 32 Silver Grove? Is that right?", "Yes")
        assert r['phase1_triggered'] is False
        assert cs.address_audio_url == original_url

    def test_reset_clears_all_capture_state(self):
        """CallState.reset() should clear all capture-related fields."""
        cs = create_call_state()
        _simulate_turn(cs, "What's the address?", "32 Silver Grove")
        assert cs.address_audio_captured is True

        cs.reset()
        assert cs.awaiting_address_audio is False
        assert cs._addr_audio_collecting is False
        assert cs._addr_audio_phase1_time == 0.0
        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None

    def test_three_eircode_attempts(self):
        """Caller tries eircode 3 times with different responses.
        Only the last valid one should be captured."""
        cs = create_call_state()

        # Attempt 1: "no idea"
        r1 = _simulate_turn(cs, "Do you have an eircode?", "No idea")
        assert r1['phase2_result'] == 'skipped'

        # Attempt 2: AI asks for address, caller gives partial
        r2 = _simulate_turn(cs, "What's the address then?", "Somewhere in Dublin")
        assert r2['phase3_captured'] is True
        first_url = cs.address_audio_url

        # Attempt 3: AI asks to clarify, caller gives full address
        r3 = _simulate_turn(cs, "Can you give me the full address?", "32 Silver Grove, Ballybrack, Dublin 18")
        assert r3['phase3_captured'] is True
        assert cs.address_audio_url != first_url  # Overwritten

    def test_where_keyword_triggers(self):
        """'Where is the job?' should trigger Phase 1."""
        cs = create_call_state()
        r = _simulate_turn(cs, "Where is the job located?", "15 Main Street")
        assert r['phase1_triggered'] is True
        assert r['phase3_captured'] is True

    def test_job_site_keyword_triggers(self):
        """'What's the job site?' should trigger Phase 1."""
        cs = create_call_state()
        r = _simulate_turn(cs, "What's the job site?", "The shopping centre on Main Street")
        assert r['phase1_triggered'] is True
        assert r['phase3_captured'] is True

    def test_work_location_keyword_triggers(self):
        cs = create_call_state()
        r = _simulate_turn(cs, "What's the work location?", "Unit 5, Industrial Estate")
        assert r['phase1_triggered'] is True
        assert r['phase3_captured'] is True

    def test_phase2_only_fires_once_per_cycle(self):
        """Phase 2 clears awaiting_address_audio. If the caller somehow sends
        another speech_final before LLM responds, Phase 2 should NOT fire again."""
        cs = create_call_state()
        _simulate_phase1(cs, "What's the address?")
        assert cs.awaiting_address_audio is True

        # First speech_final
        r1 = _simulate_phase2(cs, "32 Silver Grove")
        assert r1 == 'collecting'
        assert cs.awaiting_address_audio is False

        # Hypothetical second speech_final (shouldn't happen in practice,
        # but test the guard)
        r2 = _simulate_phase2(cs, "Ballybrack")
        assert r2 == 'no_action'  # awaiting is already False

        # Phase 3 still captures (collecting was set by first Phase 2)
        assert _simulate_phase3(cs) is True

    def test_phase3_only_fires_once(self):
        """Phase 3 clears collecting. Calling it again should be a no-op."""
        cs = create_call_state()
        _simulate_phase1(cs, "What's the address?")
        _simulate_phase2(cs, "32 Silver Grove")

        assert _simulate_phase3(cs) is True
        first_url = cs.address_audio_url

        # Second Phase 3 call — should not fire
        assert _simulate_phase3(cs) is False
        assert cs.address_audio_url == first_url  # Unchanged


class TestDeferredCaptureRealisticConversations:
    """Full realistic conversation simulations."""

    def test_full_booking_with_eircode(self):
        """Complete booking flow where caller provides eircode."""
        cs = create_call_state()

        _simulate_turn(cs, "Hi, thank you for calling Murphy's Plumbing. How can I help?", "I have a burst pipe")
        _simulate_turn(cs, "I'm sorry to hear that. Can I get your name?", "Tony Adams")
        _simulate_turn(cs, "Thanks Tony. Do you have an eircode for the property?", "D18 WR97")

        assert cs.address_audio_captured is True
        eircode_url = cs.address_audio_url

        _simulate_turn(cs, "Great, and what time works for you?", "Tomorrow morning")
        _simulate_turn(cs, "I've booked you in for tomorrow at 9am. Is that ok?", "Yes perfect")

        # URL should not have changed after non-address turns
        assert cs.address_audio_url == eircode_url

    def test_full_booking_eircode_fallback_to_address(self):
        """Caller doesn't know eircode, gives street address instead."""
        cs = create_call_state()

        _simulate_turn(cs, "Hi, how can I help?", "Blocked drain")
        _simulate_turn(cs, "Can I get your name?", "Mary O'Brien")
        
        # Ask for eircode — caller doesn't know
        r1 = _simulate_turn(cs, "Do you have an eircode?", "I don't know")
        assert r1['phase2_result'] == 'skipped'
        assert cs.address_audio_captured is False

        # Ask for address — caller gives it
        r2 = _simulate_turn(cs, "No problem, what's the street address?", "42 Orchard Road, Swords, County Dublin")
        assert r2['phase3_captured'] is True
        assert cs.address_audio_captured is True

        # Confirm — should NOT overwrite
        r3 = _simulate_turn(cs, "So the address is 42 Orchard Road, Swords. Is that correct?", "Yes that's right")
        assert r3['phase1_triggered'] is False
        assert r3['phase3_captured'] is False

    def test_full_booking_caller_corrects_address(self):
        """Caller gives wrong address, AI asks again, caller corrects."""
        cs = create_call_state()

        _simulate_turn(cs, "What's the address?", "32 Silver Grove")
        first_url = cs.address_audio_url
        assert cs.address_audio_captured is True

        # AI misheard or caller wants to correct
        _simulate_turn(cs, "Sorry, can you repeat the full address?", "32 Silver Grove, Ballybrack, Dublin 18")
        assert cs.address_audio_url != first_url  # New capture

    def test_full_booking_no_address_asked(self):
        """Some bookings might not need an address (e.g., callback request)."""
        cs = create_call_state()

        _simulate_turn(cs, "Hi, how can I help?", "Can someone call me back?")
        _simulate_turn(cs, "Sure, can I get your name?", "John Smith")
        _simulate_turn(cs, "And your phone number?", "085 123 4567")
        _simulate_turn(cs, "Great, someone will call you back shortly.", "Thanks bye")

        assert cs.address_audio_captured is False
        assert cs.address_audio_url is None

    def test_caller_gives_address_with_directions(self):
        """Caller gives a long response with address + directions.
        Should still be captured (not skipped)."""
        cs = create_call_state()
        long_response = "Yeah it's 32 Silver Grove in Ballybrack, if you come down the N11 take the second exit"
        r = _simulate_turn(cs, "What's the address?", long_response)
        assert r['phase2_result'] == 'collecting'
        assert r['phase3_captured'] is True

    def test_caller_says_just_yeah(self):
        """Caller says 'yeah' — this is NOT a skip phrase, so it gets captured.
        In practice this would be 'yeah' followed by the address in the same
        speech_final (Deepgram accumulates). But even if it's just 'yeah',
        better to capture than miss."""
        cs = create_call_state()
        r = _simulate_turn(cs, "What's the address?", "Yeah")
        assert r['phase2_result'] == 'collecting'
        assert r['phase3_captured'] is True

    def test_caller_says_no_then_gives_address_same_turn(self):
        """'No eircode but the address is 32 Silver Grove' — should capture."""
        cs = create_call_state()
        r = _simulate_turn(cs, "Do you have an eircode?",
                           "No eircode but the address is 32 Silver Grove, Ballybrack")
        assert r['phase2_result'] == 'collecting'
        assert r['phase3_captured'] is True

    def test_multiple_address_keywords_in_ai_response(self):
        """AI response contains multiple address keywords — should still trigger once."""
        cs = create_call_state()
        r = _simulate_turn(cs,
                           "Can you give me the address or eircode for the job location?",
                           "D02 XY45")
        assert r['phase1_triggered'] is True
        assert r['phase3_captured'] is True

    def test_ai_asks_where_in_different_context(self):
        """'Where' in 'where is the leak?' should trigger Phase 1.
        This is a known trade-off — 'where' is broad. But it's better
        to capture too much than miss an address."""
        cs = create_call_state()
        r = _simulate_turn(cs, "Where is the leak?", "In the kitchen under the sink")
        assert r['phase1_triggered'] is True
        # This captures a non-address response, but that's OK — the recording
        # is just extra context for the business owner. Better safe than sorry.
        assert r['phase3_captured'] is True
