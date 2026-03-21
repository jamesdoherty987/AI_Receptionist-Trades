"""
Tests for simplified speech_final handling in ASR.

The simplified ASR trusts Deepgram directly:
1. speech_final transcript is used as-is (no manual accumulation)
2. No duplicate detection (Deepgram handles this)
3. interim_text tracks latest segment/interim for barge-in only
4. clear() resets state for next utterance
"""
import pytest
import json


class MockDeepgramASR:
    """
    Mock ASR that mirrors the simplified DeepgramASR._recv logic.
    Trusts Deepgram's speech_final transcript directly.
    Has fallback for when speech_final never arrives.
    """
    
    def __init__(self):
        self.text = ""
        self.interim_text = ""
        self.speech_final = False
        self.last_segment_text = ""
        self.last_segment_time = 0.0
        self._mock_time = 0.0  # For testing time-based fallback

    def process_message(self, data: dict, current_time: float = None):
        """Process a Deepgram message - mirrors simplified _recv logic"""
        if current_time is not None:
            self._mock_time = current_time
        
        # Handle UtteranceEnd message type
        msg_type = data.get("type", "")
        if msg_type == "UtteranceEnd":
            if self.last_segment_text and not self.speech_final:
                self.text = self.last_segment_text
                self.speech_final = True
                self.last_segment_text = ""
                self.last_segment_time = 0.0
                self.interim_text = ""
            return
            
        is_speech_final = data.get("speech_final", False)
        is_final = data.get("is_final", False)
        
        alt = data.get("channel", {}).get("alternatives", [])
        transcript = alt[0].get("transcript", "") if alt else ""
        
        if is_speech_final:
            final_text = transcript.strip()
            if final_text:
                self.text = final_text
                self.speech_final = True
            elif self.last_segment_text:
                # Empty speech_final but we have accumulated segments — promote them
                self.text = self.last_segment_text
                self.speech_final = True
            self.interim_text = ""
            self.last_segment_text = ""
            self.last_segment_time = 0.0
            
        elif is_final:
            if transcript.strip():
                self.interim_text = transcript.strip()
                # Only set fallback segment if we don't already have one pending.
                # This preserves the FIRST meaningful segment even if the caller
                # later says "Hello?" out of frustration. New segments are appended.
                if not self.last_segment_text:
                    self.last_segment_text = transcript.strip()
                else:
                    self.last_segment_text += " " + transcript.strip()
                # Always update time to the latest segment — measures
                # silence since caller last spoke (matches production code)
                self.last_segment_time = self._mock_time
                
        else:
            if transcript.strip():
                self.interim_text = transcript.strip()
    
    def get_text(self) -> str:
        return self.text.strip()
    
    def get_interim(self) -> str:
        return self.interim_text.strip()
    
    def is_speech_finished(self) -> bool:
        return self.speech_final
    
    def has_pending_segment(self, timeout: float = 3.0) -> bool:
        if self.speech_final or not self.last_segment_text or self.last_segment_time == 0.0:
            return False
        return (self._mock_time - self.last_segment_time) >= timeout
    
    def promote_segment(self):
        if self.last_segment_text:
            self.text = self.last_segment_text
            self.speech_final = True
            self.last_segment_text = ""
            self.last_segment_time = 0.0
            self.interim_text = ""
    
    def clear(self):
        self.text = ""
        self.interim_text = ""
        self.speech_final = False
        self.last_segment_text = ""
        self.last_segment_time = 0.0


class TestSpeechFinalDirect:
    """Test that ASR trusts Deepgram's speech_final transcript directly"""
    
    def test_single_segment_with_speech_final(self):
        """Simple case: one segment with speech_final=true"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Hello, how are you?'}]}
        })
        
        assert asr.get_text() == "Hello, how are you?"
        assert asr.is_speech_finished() is True
    
    def test_speech_final_uses_deepgram_transcript_directly(self):
        """
        Key change: We no longer accumulate segments manually.
        Deepgram's speech_final transcript is the authoritative text.
        """
        asr = MockDeepgramASR()
        
        # First segment: is_final but not speech_final
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment'}]}
        })
        
        assert asr.is_speech_finished() is False
        # interim_text should have the latest segment for barge-in
        assert asr.get_interim() == "Hi. Can I book an appointment"
        
        # speech_final arrives — Deepgram gives us the FULL utterance
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment, please, for a leak pipe in my bathroom?'}]}
        })
        
        assert asr.is_speech_finished() is True
        # We trust Deepgram's transcript directly
        assert asr.get_text() == "Hi. Can I book an appointment, please, for a leak pipe in my bathroom?"
        # interim cleared after speech_final
        assert asr.get_interim() == ""
    
    def test_interim_updates_for_bargein(self):
        """interim_text should track latest text for barge-in detection"""
        asr = MockDeepgramASR()
        
        # Interim result
        asr.process_message({
            'is_final': False,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'my name'}]}
        })
        assert asr.get_interim() == "my name"
        
        # Updated interim
        asr.process_message({
            'is_final': False,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'my name is John'}]}
        })
        assert asr.get_interim() == "my name is John"
        
        # is_final segment also updates interim
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'my name is John Smith'}]}
        })
        assert asr.get_interim() == "my name is John Smith"
        assert asr.is_speech_finished() is False
    
    def test_speech_final_without_transcript(self):
        """speech_final with empty transcript but accumulated segments should promote them.
        
        This is the key fix for the freeze bug: Deepgram sends is_final segments
        with text, then speech_final with EMPTY transcript. Previously, the empty
        speech_final would silently wipe last_segment_text without promoting it,
        causing the caller's response to be lost.
        """
        asr = MockDeepgramASR()
        
        # Segment with text (is_final, not speech_final)
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Yes, that is correct'}]}
        }, current_time=10.0)
        
        assert asr.last_segment_text == "Yes, that is correct"
        
        # speech_final with empty transcript — should promote accumulated text
        asr.process_message({
            'is_final': False,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': ''}]}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Yes, that is correct"
    
    def test_speech_final_empty_no_accumulated(self):
        """speech_final with empty transcript and NO accumulated segments should be a no-op."""
        asr = MockDeepgramASR()
        
        # speech_final with empty transcript, nothing accumulated
        asr.process_message({
            'is_final': False,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': ''}]}
        })
        
        assert asr.is_speech_finished() is False
        assert asr.get_text() == ""
    
    def test_speech_final_clears_interim(self):
        """speech_final should always clear interim_text"""
        asr = MockDeepgramASR()
        
        # Build up interim
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hello world'}]}
        })
        assert asr.get_interim() == "Hello world"
        
        # speech_final clears interim
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Hello world, how are you?'}]}
        })
        assert asr.get_interim() == ""
        assert asr.get_text() == "Hello world, how are you?"


class TestClearAndReset:
    """Test clear() behavior"""
    
    def test_clear_resets_all_state(self):
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Hello'}]}
        })
        
        assert asr.get_text() == "Hello"
        assert asr.is_speech_finished() is True
        
        asr.clear()
        
        assert asr.get_text() == ""
        assert asr.get_interim() == ""
        assert asr.is_speech_finished() is False
    
    def test_clear_allows_next_utterance(self):
        """After clear, next speech_final should work normally"""
        asr = MockDeepgramASR()
        
        # First utterance
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Yes'}]}
        })
        assert asr.get_text() == "Yes"
        
        asr.clear()
        
        # Second utterance
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'My name is John'}]}
        })
        assert asr.get_text() == "My name is John"
        assert asr.is_speech_finished() is True


class TestEdgeCases:
    """Test edge cases"""
    
    def test_empty_transcript_ignored(self):
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': ''}]}
        })
        assert asr.get_interim() == ""
        
    def test_whitespace_only_transcript(self):
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': '   '}]}
        })
        assert asr.get_interim() == ""
    
    def test_no_alternatives(self):
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {}
        })
        assert asr.get_text() == ""
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': []}
        })
        assert asr.get_text() == ""
    
    def test_confirmation_response(self):
        """Simple yes/no should work immediately"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Yes, that is correct.'}]}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Yes, that is correct."


class TestMediaHandlerTriggerLogic:
    """
    Test the simplified trigger logic in media_handler.
    Now we only trigger on speech_final — no fallback timeout.
    """
    
    def test_speech_final_triggers_response(self):
        """Response should trigger when speech_final=true"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'I need to book an appointment'}]}
        })
        
        assert asr.is_speech_finished() is True
    
    def test_is_final_without_speech_final_does_not_trigger(self):
        """is_final alone should NOT trigger a response"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment, please, for a leak'}]}
        })
        
        assert asr.is_speech_finished() is False
    
    def test_interim_does_not_trigger(self):
        """Interim results should never trigger a response"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': False,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi can I book'}]}
        })
        
        assert asr.is_speech_finished() is False
        assert asr.get_interim() == "Hi can I book"


class TestRealWorldScenarios:
    """Test scenarios based on real call patterns"""
    
    def test_booking_request_deepgram_handles_accumulation(self):
        """
        Real scenario: Caller pauses mid-sentence.
        Deepgram accumulates and sends full text on speech_final.
        We just trust it.
        """
        asr = MockDeepgramASR()
        
        # Interim results as caller speaks
        asr.process_message({
            'is_final': False, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi'}]}
        })
        asr.process_message({
            'is_final': False, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. Can I book'}]}
        })
        
        # First segment finalized (caller paused)
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment, please, for a leak'}]}
        }, current_time=10.0)
        assert asr.is_speech_finished() is False
        
        # More interim as caller continues
        asr.process_message({
            'is_final': False, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'pipe in my bathroom'}]}
        })
        
        # Deepgram sends speech_final with the FULL utterance
        asr.process_message({
            'is_final': True, 'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'pipe in my bathroom?'}]}
        })
        
        assert asr.is_speech_finished() is True
        # We trust whatever Deepgram gives us on speech_final
        assert asr.get_text() == "pipe in my bathroom?"
    
    def test_eircode_with_pause(self):
        """Caller pauses while looking up eircode — Deepgram handles it"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': "It's"}]}
        }, current_time=10.0)
        assert asr.is_speech_finished() is False
        
        # Long pause while looking at letter... Deepgram waits (endpointing=1200ms)
        # Then caller says the eircode
        asr.process_message({
            'is_final': True, 'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'D02 WR97'}]}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "D02 WR97"
    
    def test_multiple_utterances_in_sequence(self):
        """Multiple back-to-back utterances with clear() between"""
        asr = MockDeepgramASR()
        
        # First utterance
        asr.process_message({
            'is_final': True, 'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Yes'}]}
        })
        assert asr.get_text() == "Yes"
        asr.clear()
        
        # Second utterance
        asr.process_message({
            'is_final': True, 'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Tuesday morning please'}]}
        })
        assert asr.get_text() == "Tuesday morning please"
        asr.clear()
        
        # Third utterance
        asr.process_message({
            'is_final': True, 'speech_final': True,
            'channel': {'alternatives': [{'transcript': "That's correct, thanks"}]}
        })
        assert asr.get_text() == "That's correct, thanks"


class TestFallbackWhenSpeechFinalMissing:
    """
    Test the fallback for when Deepgram sends is_final segments
    but never sends speech_final or UtteranceEnd. This is a last-resort
    safety net — with utterance_end_ms enabled, it should rarely fire.
    """
    
    def test_fallback_triggers_after_timeout(self):
        """
        Segment arrives at t=10, no speech_final by t=13 → fallback fires.
        """
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'I have a burst pipe and I need help'}]}
        }, current_time=10.0)
        
        assert asr.is_speech_finished() is False
        assert asr.last_segment_text == "I have a burst pipe and I need help"
        
        # At t=12 (2s later) — not yet
        asr._mock_time = 12.0
        assert asr.has_pending_segment(timeout=3.0) is False
        
        # At t=13 (3s later) — fallback should fire
        asr._mock_time = 13.0
        assert asr.has_pending_segment(timeout=3.0) is True
        
        # Promote it
        asr.promote_segment()
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "I have a burst pipe and I need help"
        assert asr.last_segment_text == ""
    
    def test_fallback_does_not_trigger_if_speech_final_arrives(self):
        """If speech_final arrives normally, fallback should not be needed."""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hello there'}]}
        }, current_time=10.0)
        
        # speech_final arrives before timeout
        asr.process_message({
            'is_final': True, 'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Hello there, I need a plumber'}]}
        }, current_time=11.0)
        
        # speech_final already arrived, so has_pending_segment should be False
        asr._mock_time = 14.0
        assert asr.has_pending_segment(timeout=3.0) is False
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Hello there, I need a plumber"
    
    def test_fallback_does_not_trigger_without_segment(self):
        """No segment text → no fallback."""
        asr = MockDeepgramASR()
        asr._mock_time = 100.0
        assert asr.has_pending_segment(timeout=3.0) is False
    
    def test_fallback_clears_after_promote(self):
        """After promote, state should be clean for next utterance."""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Test message'}]}
        }, current_time=10.0)
        
        asr._mock_time = 14.0
        asr.promote_segment()
        
        assert asr.get_text() == "Test message"
        assert asr.last_segment_text == ""
        assert asr.last_segment_time == 0.0
        assert asr.get_interim() == ""
        
        # Clear and verify clean state
        asr.clear()
        assert asr.get_text() == ""
        assert asr.is_speech_finished() is False
    
    def test_real_scenario_burst_pipe_no_speech_final(self):
        """
        Exact scenario from production logs:
        1. Caller says "I have a burst pipe..." → is_final segment
        2. Deepgram never sends speech_final
        3. Caller waits, then says "Hello?" → that gets appended to pending segment
        4. Without fallback, LLM only sees "Hello?" and ignores the burst pipe
        
        With fallback + accumulation: after 5s, the full accumulated text gets promoted.
        The timer starts from the FIRST segment, so "Hello?" doesn't reset it.
        """
        asr = MockDeepgramASR()
        
        # Caller describes issue
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. I just have a burst pipe. Can you help with that?'}]}
        }, current_time=10.0)
        
        assert asr.is_speech_finished() is False
        
        # 3 seconds pass, no speech_final or UtteranceEnd
        asr._mock_time = 13.0
        assert asr.has_pending_segment(timeout=3.0) is True
        
        # Promote before the caller says "Hello?"
        asr.promote_segment()
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Hi. I just have a burst pipe. Can you help with that?"
    
    def test_new_segments_reset_timer(self):
        """
        Timer resets on each new segment — measures silence since caller last spoke.
        This prevents premature promotion during long multi-segment utterances.
        New segments are still appended to preserve the full text.
        """
        asr = MockDeepgramASR()
        
        # Caller spells name
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': "It's p e t e r r o n a n."}]}
        }, current_time=10.0)
        
        assert asr.last_segment_text == "It's p e t e r r o n a n."
        assert asr.last_segment_time == 10.0
        
        # Caller says "Hello?" at t=20 — timer resets to t=20
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hello?'}]}
        }, current_time=20.0)
        
        # Timer should be from latest segment (t=20)
        assert asr.last_segment_time == 20.0
        # Text should be accumulated
        assert asr.last_segment_text == "It's p e t e r r o n a n. Hello?"
        
        # At t=22 (2s after last segment) — not yet
        asr._mock_time = 22.0
        assert asr.has_pending_segment(timeout=3.0) is False
        
        # At t=23 (3s after last segment) — should trigger
        asr._mock_time = 23.0
        assert asr.has_pending_segment(timeout=3.0) is True
        
        # Promote — should get the full accumulated text
        asr.promote_segment()
        assert asr.get_text() == "It's p e t e r r o n a n. Hello?"
    
    def test_accumulation_preserves_full_utterance(self):
        """
        When Deepgram sends multiple is_final segments without speech_final,
        all segments should be accumulated so the full utterance is preserved.
        """
        asr = MockDeepgramASR()
        
        # First part of sentence
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. I, have a burst'}]}
        }, current_time=10.0)
        
        # Second part arrives
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'pipe in my room, and I need help'}]}
        }, current_time=12.0)
        
        # Timer resets to latest segment
        assert asr.last_segment_time == 12.0
        assert asr.last_segment_text == "Hi. I, have a burst pipe in my room, and I need help"
        
        # After 3s from last segment (t=12)
        asr._mock_time = 15.0
        assert asr.has_pending_segment(timeout=3.0) is True
        
        asr.promote_segment()
        assert asr.get_text() == "Hi. I, have a burst pipe in my room, and I need help"


class TestUtteranceEnd:
    """
    Test UtteranceEnd handling — Deepgram's word-timing-based end-of-speech
    detection that works even in noisy environments where speech_final (VAD)
    fails.
    """
    
    def test_utterance_end_promotes_accumulated_segments(self):
        """UtteranceEnd should promote accumulated is_final segments to final text."""
        asr = MockDeepgramASR()
        
        # Caller speaks, gets is_final but no speech_final
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Yeah. That is correct.'}]}
        }, current_time=10.0)
        
        assert asr.is_speech_finished() is False
        assert asr.last_segment_text == "Yeah. That is correct."
        
        # UtteranceEnd arrives — word timing gap detected
        asr.process_message({'type': 'UtteranceEnd'}, current_time=11.5)
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Yeah. That is correct."
        assert asr.last_segment_text == ""
        assert asr.get_interim() == ""
    
    def test_utterance_end_with_multiple_segments(self):
        """UtteranceEnd should promote ALL accumulated segments."""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. I have a burst pipe.'}]}
        }, current_time=10.0)
        
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Can you help with that?'}]}
        }, current_time=12.0)
        
        asr.process_message({'type': 'UtteranceEnd'}, current_time=13.5)
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Hi. I have a burst pipe. Can you help with that?"
    
    def test_utterance_end_ignored_if_no_segments(self):
        """UtteranceEnd with no pending segments should be a no-op."""
        asr = MockDeepgramASR()
        
        asr.process_message({'type': 'UtteranceEnd'}, current_time=10.0)
        
        assert asr.is_speech_finished() is False
        assert asr.get_text() == ""
    
    def test_utterance_end_ignored_if_speech_final_already_set(self):
        """If speech_final already fired, UtteranceEnd should be ignored."""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True, 'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Hello there'}]}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Hello there"
        
        # UtteranceEnd arrives after speech_final — should not change anything
        asr.process_message({'type': 'UtteranceEnd'})
        
        assert asr.get_text() == "Hello there"
    
    def test_utterance_end_beats_fallback(self):
        """UtteranceEnd should fire well before the 3s fallback timer."""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True, 'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Yes. Correct.'}]}
        }, current_time=10.0)
        
        # At t=11.2 — UtteranceEnd fires (1.2s after speech, matching utterance_end_ms)
        # This is well before the 3s fallback would fire at t=13
        asr._mock_time = 11.2
        assert asr.has_pending_segment(timeout=3.0) is False  # Fallback hasn't fired yet
        
        asr.process_message({'type': 'UtteranceEnd'}, current_time=11.2)
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Yes. Correct."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
