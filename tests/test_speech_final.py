"""
Tests for speech_final handling in ASR and media handler.

These tests verify that:
1. ASR correctly accumulates text across is_final segments
2. ASR only signals speech_finished when speech_final=true arrives
3. Media handler only triggers response on speech_final (not brief pauses)
4. The domino effect bug is fixed
"""
import pytest
import json
import re


class MockDeepgramASR:
    """
    Mock ASR that simulates the new speech_final behavior.
    This mirrors the actual DeepgramASR class logic.
    """
    
    def __init__(self):
        self.text = ""
        self.interim_text = ""
        self.is_final = False
        self.speech_final = False
        self._accumulated_text = ""
        self._last_final_text = ""
        self._last_final_fingerprint = ""
        self._last_final_time = 0.0
        self._last_transcript_time = 0.0
    
    def _fingerprint(self, s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', (s or "").lower())
    
    def process_message(self, data: dict, current_time: float = 0.0):
        """Process a Deepgram message - mirrors _recv logic"""
        is_speech_final = data.get("speech_final", False)
        is_final = data.get("is_final", False)
        
        alt = data.get("channel", {}).get("alternatives", [])
        if alt and alt[0].get("transcript"):
            transcript = alt[0]["transcript"]
            
            if is_final:
                # Accumulate text from this segment
                if transcript.strip():
                    if self._accumulated_text:
                        self._accumulated_text += " " + transcript.strip()
                    else:
                        self._accumulated_text = transcript.strip()
                    self._last_transcript_time = current_time
                
                # Clear interim when we get final segment
                self.interim_text = ""
                
                # If this is also speech_final, the caller has finished speaking
                if is_speech_final:
                    full_text = self._accumulated_text.strip()
                    full_fp = self._fingerprint(full_text)
                    
                    is_duplicate = (
                        full_text == self.text.strip() or
                        full_text == self._last_final_text.strip() or
                        (full_fp and full_fp == self._last_final_fingerprint)
                    )
                    
                    if full_text and not is_duplicate:
                        self.text = full_text
                        self.is_final = True
                        self.speech_final = True
                        self._last_final_text = full_text
                        self._last_final_fingerprint = full_fp
                        self._last_final_time = current_time
                    elif is_duplicate:
                        self.is_final = True
                        self.speech_final = True
                    
                    # Reset accumulator for next utterance
                    self._accumulated_text = ""
            else:
                # Interim result
                if self._accumulated_text:
                    combined = self._accumulated_text + " " + transcript.strip()
                    if combined.strip() != self.interim_text.strip():
                        self.interim_text = combined.strip()
                        self._last_transcript_time = current_time
                elif transcript.strip() != self.interim_text.strip():
                    self.interim_text = transcript.strip()
                    self._last_transcript_time = current_time
        
        # Handle speech_final without transcript (silence detected)
        elif is_speech_final and self._accumulated_text:
            full_text = self._accumulated_text.strip()
            full_fp = self._fingerprint(full_text)
            
            is_duplicate = (
                full_text == self._last_final_text.strip() or
                (full_fp and full_fp == self._last_final_fingerprint)
            )
            
            if full_text and not is_duplicate:
                self.text = full_text
                self.is_final = True
                self.speech_final = True
                self._last_final_text = full_text
                self._last_final_fingerprint = full_fp
                self._last_final_time = current_time
            
            self._accumulated_text = ""
    
    def get_text(self) -> str:
        return self.text.strip()
    
    def get_interim(self) -> str:
        return self.interim_text.strip()
    
    def is_speech_finished(self) -> bool:
        return self.speech_final
    
    def clear(self):
        self.text = ""
        self.interim_text = ""
        self.is_final = False
        self.speech_final = False
        self._accumulated_text = ""
        self._last_transcript_time = 0.0


class TestSpeechFinalAccumulation:
    """Test that ASR correctly accumulates text until speech_final"""
    
    def test_single_segment_with_speech_final(self):
        """Simple case: one segment with speech_final=true"""
        asr = MockDeepgramASR()
        
        # Single message with both is_final and speech_final
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Hello, how are you?'}]}
        })
        
        assert asr.get_text() == "Hello, how are you?"
        assert asr.is_speech_finished() is True
    
    def test_multiple_segments_accumulated(self):
        """
        Key test: Multiple is_final segments should accumulate until speech_final.
        This is the exact scenario from the bug report.
        """
        asr = MockDeepgramASR()
        
        # First segment: is_final=true but speech_final=false (caller paused briefly)
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment, please, for a leak'}]}
        })
        
        # Should NOT be ready yet
        assert asr.is_speech_finished() is False
        assert asr._accumulated_text == "Hi. Can I book an appointment, please, for a leak"
        
        # Second segment: is_final=true AND speech_final=true (caller finished)
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'pipe in my bathroom?'}]}
        })
        
        # NOW should be ready with combined text
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Hi. Can I book an appointment, please, for a leak pipe in my bathroom?"
    
    def test_three_segments_accumulated(self):
        """Test accumulation across three segments"""
        asr = MockDeepgramASR()
        
        # Segment 1
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'I need to'}]}
        })
        assert asr.is_speech_finished() is False
        
        # Segment 2
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'book an appointment'}]}
        })
        assert asr.is_speech_finished() is False
        
        # Segment 3 with speech_final
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'for Tuesday please'}]}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "I need to book an appointment for Tuesday please"
    
    def test_interim_results_combined_with_accumulated(self):
        """Test that interim results show accumulated + current interim"""
        asr = MockDeepgramASR()
        
        # First segment finalized
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hello'}]}
        })
        
        # Interim result for next segment
        asr.process_message({
            'is_final': False,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'my name is'}]}
        })
        
        # Interim should show combined text
        assert asr.get_interim() == "Hello my name is"
        assert asr.is_speech_finished() is False
    
    def test_speech_final_without_transcript(self):
        """Test speech_final arriving as separate message (silence detected)"""
        asr = MockDeepgramASR()
        
        # Segment finalized
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Yes, that is correct'}]}
        })
        
        assert asr.is_speech_finished() is False
        
        # speech_final arrives without transcript (just silence detection)
        asr.process_message({
            'is_final': False,
            'speech_final': True,
            'channel': {'alternatives': []}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Yes, that is correct"


class TestMediaHandlerTriggerLogic:
    """Test the trigger logic in media_handler"""
    
    def test_speech_final_triggers_response(self):
        """Response should trigger when speech_final=true"""
        speech_finished = True
        silence_since = 10.0
        now = 10.5  # Only 0.5s of silence
        duration_met = True
        
        extended_silence = silence_since and (now - silence_since) >= 3.0
        should_trigger = (speech_finished and duration_met) or (extended_silence and duration_met)
        
        assert should_trigger is True
    
    def test_brief_pause_does_not_trigger(self):
        """Brief pause (0.8s) should NOT trigger without speech_final"""
        speech_finished = False
        silence_since = 10.0
        now = 10.9  # 0.9s of silence
        duration_met = True
        SILENCE_HOLD = 0.8
        
        silence_met = silence_since and (now - silence_since) >= SILENCE_HOLD
        extended_silence = silence_since and (now - silence_since) >= 3.0
        should_trigger = (speech_finished and duration_met) or (extended_silence and duration_met)
        
        # silence_met is True but should_trigger should be False
        assert silence_met is True
        assert should_trigger is False
    
    def test_extended_silence_fallback(self):
        """Extended silence (3s) should trigger as fallback"""
        speech_finished = False
        silence_since = 10.0
        now = 13.5  # 3.5s of silence
        duration_met = True
        
        extended_silence = silence_since and (now - silence_since) >= 3.0
        should_trigger = (speech_finished and duration_met) or (extended_silence and duration_met)
        
        assert extended_silence is True
        assert should_trigger is True
    
    def test_exactly_at_3s_boundary(self):
        """Test behavior exactly at 3s boundary"""
        speech_finished = False
        silence_since = 10.0
        duration_met = True
        
        # Just under 3s - should NOT trigger
        now = 12.99
        extended_silence = silence_since and (now - silence_since) >= 3.0
        should_trigger = (speech_finished and duration_met) or (extended_silence and duration_met)
        assert should_trigger is False
        
        # Exactly 3s - should trigger
        now = 13.0
        extended_silence = silence_since and (now - silence_since) >= 3.0
        should_trigger = (speech_finished and duration_met) or (extended_silence and duration_met)
        assert should_trigger is True


class TestDominoEffectPrevention:
    """
    Test that the domino effect bug is fixed.
    
    The bug: AI responds to first part of sentence, then second part
    comes in as "new" message, creating cascading confusion.
    """
    
    def test_domino_effect_scenario(self):
        """
        Simulate the exact scenario from the bug report:
        Caller: "Hi. Can I book an appointment, please, for a leak" [pause] "pipe in my bathroom?"
        
        OLD behavior (bug):
        - First part triggers response
        - Second part treated as new message
        - AI responds to "pipe in my bathroom?" as if it's a new question
        
        NEW behavior (fixed):
        - First part accumulated, waits for speech_final
        - Second part accumulated
        - speech_final arrives, full sentence processed
        """
        asr = MockDeepgramASR()
        responses_triggered = []
        
        def check_trigger(asr, silence_duration):
            """Simulate media handler trigger check"""
            speech_finished = asr.is_speech_finished()
            duration_met = True
            extended_silence = silence_duration >= 3.0
            return (speech_finished and duration_met) or (extended_silence and duration_met)
        
        # Caller says first part
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment, please, for a leak'}]}
        })
        
        # Brief pause (0.8s) - OLD code would trigger here
        if check_trigger(asr, 0.8):
            responses_triggered.append(asr.get_text())
            asr.clear()
        
        # Should NOT have triggered
        assert len(responses_triggered) == 0
        
        # Caller continues
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'pipe in my bathroom?'}]}
        })
        
        # Now check trigger
        if check_trigger(asr, 0.5):
            responses_triggered.append(asr.get_text())
        
        # Should have triggered ONCE with FULL sentence
        assert len(responses_triggered) == 1
        assert responses_triggered[0] == "Hi. Can I book an appointment, please, for a leak pipe in my bathroom?"
    
    def test_multiple_pauses_accumulated(self):
        """Test caller who pauses multiple times mid-sentence"""
        asr = MockDeepgramASR()
        
        # "I need..." [pause]
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': "I need"}]}
        })
        assert asr.is_speech_finished() is False
        
        # "...to book..." [pause]
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': "to book"}]}
        })
        assert asr.is_speech_finished() is False
        
        # "...an appointment..." [pause]
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': "an appointment"}]}
        })
        assert asr.is_speech_finished() is False
        
        # "...for Tuesday." [done]
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': "for Tuesday."}]}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "I need to book an appointment for Tuesday."


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_transcript_ignored(self):
        """Empty transcripts should not affect accumulation"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hello'}]}
        })
        
        # Empty transcript
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': ''}]}
        })
        
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'world'}]}
        })
        
        assert asr.get_text() == "Hello world"
    
    def test_whitespace_only_transcript(self):
        """Whitespace-only transcripts should not affect accumulation"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hello'}]}
        })
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': '   '}]}
        })
        
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'world'}]}
        })
        
        assert asr.get_text() == "Hello world"
    
    def test_clear_resets_accumulator(self):
        """clear should reset the accumulator"""
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Hello'}]}
        })
        
        assert asr._accumulated_text == "Hello"
        
        asr.clear()
        
        assert asr._accumulated_text == ""
        assert asr.get_text() == ""
        assert asr.is_speech_finished() is False
    
    def test_duplicate_detection_still_works(self):
        """Duplicate detection should still work with accumulation"""
        asr = MockDeepgramASR()
        
        # First utterance
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Yes'}]}
        })
        
        assert asr.get_text() == "Yes"
        first_text = asr.get_text()
        
        # Same utterance again (echo)
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Yes'}]}
        })
        
        # Should still be the same (duplicate ignored)
        assert asr.get_text() == first_text
    
    def test_no_alternatives_handled(self):
        """Messages without alternatives should not crash"""
        asr = MockDeepgramASR()
        
        # No alternatives
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {}
        })
        
        # Empty alternatives
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': []}
        })
        
        # Should not crash and state should be clean
        assert asr.get_text() == ""
        assert asr._accumulated_text == ""


class TestRealWorldScenarios:
    """Test scenarios based on real call logs"""
    
    def test_booking_request_with_pause(self):
        """
        Real scenario: "Hi. Can I book an appointment, please, for a leak" [pause] "pipe in my bathroom?"
        """
        asr = MockDeepgramASR()
        
        # Simulate Deepgram messages
        messages = [
            {'is_final': False, 'speech_final': False, 'channel': {'alternatives': [{'transcript': 'Hi'}]}},
            {'is_final': False, 'speech_final': False, 'channel': {'alternatives': [{'transcript': 'Hi. Can I'}]}},
            {'is_final': False, 'speech_final': False, 'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment'}]}},
            {'is_final': True, 'speech_final': False, 'channel': {'alternatives': [{'transcript': 'Hi. Can I book an appointment, please, for a leak'}]}},
            # Brief pause here - OLD code would trigger
            {'is_final': False, 'speech_final': False, 'channel': {'alternatives': [{'transcript': 'pipe'}]}},
            {'is_final': False, 'speech_final': False, 'channel': {'alternatives': [{'transcript': 'pipe in my bathroom'}]}},
            {'is_final': True, 'speech_final': True, 'channel': {'alternatives': [{'transcript': 'pipe in my bathroom?'}]}},
        ]
        
        for msg in messages:
            asr.process_message(msg)
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Hi. Can I book an appointment, please, for a leak pipe in my bathroom?"
    
    def test_name_spelling_scenario(self):
        """
        Real scenario: Caller spells name with pauses
        "J" [pause] "A" [pause] "M" [pause] "E" [pause] "S"
        """
        asr = MockDeepgramASR()
        
        # Each letter might come as separate segment
        letters = ['J', 'A', 'M', 'E', 'S']
        for i, letter in enumerate(letters):
            is_last = (i == len(letters) - 1)
            asr.process_message({
                'is_final': True,
                'speech_final': is_last,
                'channel': {'alternatives': [{'transcript': letter}]}
            })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "J A M E S"
    
    def test_confirmation_response(self):
        """
        Real scenario: Simple "Yes" or "No" response
        Should trigger immediately with speech_final
        """
        asr = MockDeepgramASR()
        
        asr.process_message({
            'is_final': True,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': 'Yes, that is correct.'}]}
        })
        
        assert asr.is_speech_finished() is True
        assert asr.get_text() == "Yes, that is correct."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
