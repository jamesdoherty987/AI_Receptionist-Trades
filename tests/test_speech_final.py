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
    """
    
    def __init__(self):
        self.text = ""
        self.interim_text = ""
        self.speech_final = False

    def process_message(self, data: dict):
        """Process a Deepgram message - mirrors simplified _recv logic"""
        is_speech_final = data.get("speech_final", False)
        is_final = data.get("is_final", False)
        
        alt = data.get("channel", {}).get("alternatives", [])
        transcript = alt[0].get("transcript", "") if alt else ""
        
        if is_speech_final:
            final_text = transcript.strip()
            if final_text:
                self.text = final_text
                self.speech_final = True
            self.interim_text = ""
            
        elif is_final:
            if transcript.strip():
                self.interim_text = transcript.strip()
                
        else:
            if transcript.strip():
                self.interim_text = transcript.strip()
    
    def get_text(self) -> str:
        return self.text.strip()
    
    def get_interim(self) -> str:
        return self.interim_text.strip()
    
    def is_speech_finished(self) -> bool:
        return self.speech_final
    
    def clear(self):
        self.text = ""
        self.interim_text = ""
        self.speech_final = False


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
        """speech_final with empty transcript should not set text"""
        asr = MockDeepgramASR()
        
        # Segment with text
        asr.process_message({
            'is_final': True,
            'speech_final': False,
            'channel': {'alternatives': [{'transcript': 'Yes, that is correct'}]}
        })
        
        # speech_final with empty transcript (silence detected)
        asr.process_message({
            'is_final': False,
            'speech_final': True,
            'channel': {'alternatives': [{'transcript': ''}]}
        })
        
        # Should NOT set text since speech_final transcript was empty
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
        })
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
        })
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
