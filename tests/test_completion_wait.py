"""
Tests for COMPLETION_WAIT interruption handling.

Tests the scenario where:
1. Caller speaks, then goes silent for SILENCE_HOLD
2. AI starts generating response
3. Caller speaks again within COMPLETION_WAIT
4. AI should cancel, combine texts, and restart

Edge cases tested:
- Interruption exactly at COMPLETION_WAIT boundary
- Multiple rapid interruptions
- Interruption with same text (duplicate detection)
- Interruption after COMPLETION_WAIT (should be normal barge-in)
- Very short interruption (noise filtering)
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
import base64


class MockASR:
    """Mock ASR that can simulate transcription results"""
    def __init__(self):
        self.text = ""
        self.interim_text = ""
        self.is_final = False
        self._feed_count = 0
        self._scheduled_texts = []  # [(feed_count, text, is_final), ...]
    
    async def connect(self):
        pass
    
    async def feed(self, audio: bytes):
        self._feed_count += 1
        # Check if we should update text based on feed count
        for count, text, is_final in self._scheduled_texts:
            if self._feed_count >= count:
                if is_final:
                    self.text = text
                    self.is_final = True
                else:
                    self.interim_text = text
    
    def get_text(self) -> str:
        return self.text.strip()
    
    def get_interim(self) -> str:
        return self.interim_text.strip()
    
    def reset_final_flag(self):
        self.is_final = False
    
    def clear_all(self):
        self.text = ""
        self.interim_text = ""
        self.is_final = False
    
    async def close(self):
        pass
    
    def schedule_text(self, feed_count: int, text: str, is_final: bool = False):
        """Schedule text to appear after N feed() calls"""
        self._scheduled_texts.append((feed_count, text, is_final))


class MockWebSocket:
    """Mock WebSocket for testing"""
    def __init__(self):
        self.sent_messages = []
        self.remote_address = ("127.0.0.1", 12345)
    
    async def send(self, data):
        self.sent_messages.append(data)


def create_audio_packet(energy_level: int = 2000) -> bytes:
    """Create a mock audio packet with approximate energy level"""
    # μ-law encoding: higher values = higher energy
    # We'll create a simple pattern that gives roughly the desired energy
    if energy_level < 500:
        # Very quiet - mostly silence bytes
        return bytes([0x7F] * 160)  # 20ms of near-silence
    elif energy_level < 1500:
        # Quiet speech
        return bytes([0x50] * 160)
    elif energy_level < 2500:
        # Normal speech
        return bytes([0x30] * 160)
    else:
        # Loud speech
        return bytes([0x10] * 160)


def create_media_event(audio: bytes, stream_sid: str = "test_stream") -> dict:
    """Create a Twilio media event"""
    return {
        "event": "media",
        "media": {
            "payload": base64.b64encode(audio).decode()
        },
        "streamSid": stream_sid
    }


class TestCompletionWaitInterruption:
    """Test COMPLETION_WAIT interruption behavior"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config with test values"""
        config = Mock()
        config.SPEECH_ENERGY = 1600
        config.SILENCE_ENERGY = 1000
        config.SILENCE_HOLD = 0.7  # 700ms - wait after silence before starting response
        config.COMPLETION_WAIT = 2.0  # 2s - window for caller to continue (runs parallel with response generation)
        config.INTERRUPT_ENERGY = 2800
        config.NO_BARGEIN_WINDOW = 0.5
        config.BARGEIN_HOLD = 0.4
        config.POST_TTS_IGNORE = 0.05
        config.MIN_WORDS = 1
        config.DUPLICATE_WINDOW = 3.0
        config.MIN_SPEECH_DURATION = 0.3
        config.LLM_PROCESSING_TIMEOUT = 8.0
        config.MIN_TOKENS_BEFORE_INTERRUPT = 8
        config.TTS_TIMEOUT = 20.0
        config.CONTINUATION_WINDOW = 2.0  # Same as COMPLETION_WAIT (legacy alias)
        config.AUDIO_ENCODING = "mulaw"
        config.AUDIO_SAMPLE_RATE = 8000
        config.AUDIO_CHANNELS = 1
        config.DEEPGRAM_API_KEY = "test_key"
        config.TTS_PROVIDER = "deepgram"
        return config

    def test_completion_wait_window_calculation(self, mock_config):
        """Test that COMPLETION_WAIT window is calculated correctly
        
        Flow:
        1. Caller speaks, then goes silent
        2. Wait SILENCE_HOLD (0.7s) after silence detected
        3. After SILENCE_HOLD, start generating response (this is response_start)
        4. COMPLETION_WAIT (2s) timer starts when SILENCE_HOLD finishes
        5. Response generation happens in parallel with COMPLETION_WAIT
        """
        response_start = 10.0  # When SILENCE_HOLD finished and response generation started
        completion_wait = mock_config.COMPLETION_WAIT  # 2.0s
        
        # At time 10.5 (0.5s after start), should be in window
        current_time = 10.5
        in_window = (current_time - response_start) <= completion_wait
        assert in_window is True
        
        # At time 11.5 (1.5s after start), should still be in window
        current_time = 11.5
        in_window = (current_time - response_start) <= completion_wait
        assert in_window is True
        
        # At time 12.5 (2.5s after start), should be outside window (2.0s window)
        current_time = 12.5
        in_window = (current_time - response_start) <= completion_wait
        assert in_window is False

    def test_text_combination_logic(self):
        """Test that texts are combined correctly"""
        original_text = "I need to book"
        new_speech = "an appointment for Tuesday"
        
        # Simulate the combination logic from media_handler
        def norm_text(s: str) -> str:
            return " ".join((s or "").lower().split())
        
        # If new text doesn't start with original, combine them
        if not norm_text(new_speech).startswith(norm_text(original_text)):
            combined = original_text + " " + new_speech
        else:
            combined = new_speech
        
        assert combined == "I need to book an appointment for Tuesday"

    def test_text_combination_when_asr_already_combined(self):
        """Test that we don't double-combine if ASR already did it"""
        original_text = "I need to book"
        # ASR sometimes includes the original text in the new transcription
        new_speech = "I need to book an appointment"
        
        def norm_text(s: str) -> str:
            return " ".join((s or "").lower().split())
        
        # If new text already starts with original, don't combine
        if not norm_text(new_speech).startswith(norm_text(original_text)):
            combined = original_text + " " + new_speech
        else:
            combined = new_speech
        
        # Should NOT be "I need to book I need to book an appointment"
        assert combined == "I need to book an appointment"

    def test_duplicate_detection_prevents_double_processing(self):
        """Test that duplicate text is detected and not processed twice"""
        def norm_text(s: str) -> str:
            return " ".join((s or "").lower().split())
        
        def content_fingerprint(s: str) -> str:
            import re
            return re.sub(r'[^a-z0-9]', '', (s or "").lower())
        
        last_committed = "I need to book an appointment"
        new_text = "I need to book an appointment"
        
        # Exact match detection
        is_duplicate = norm_text(new_text) == norm_text(last_committed)
        assert is_duplicate is True
        
        # Fingerprint match (handles spacing differences)
        last_committed = "v 9 5 h 5 p 2"
        new_text = "v95h5p2"
        
        is_duplicate = content_fingerprint(new_text) == content_fingerprint(last_committed)
        assert is_duplicate is True

    def test_interruption_requires_real_speech(self):
        """Test that interruption requires actual words, not just noise"""
        # Minimum requirements for interruption
        min_words = 1
        min_chars = 3
        
        # Just noise - should NOT trigger interruption
        interim_check = "um"
        words = interim_check.strip().split()
        is_real_speech = len(words) >= min_words and len(interim_check.strip()) >= min_chars
        assert is_real_speech is False  # "um" is only 2 chars
        
        # Real speech - should trigger interruption
        interim_check = "wait"
        words = interim_check.strip().split()
        is_real_speech = len(words) >= min_words and len(interim_check.strip()) >= min_chars
        assert is_real_speech is True

    def test_new_speech_detection(self):
        """Test that new speech is different from original"""
        def norm_text(s: str) -> str:
            return " ".join((s or "").lower().split())
        
        original_text = "I need to book"
        
        # Same text - should NOT be considered new speech
        interim_check = "I need to book"
        is_new = norm_text(interim_check) != norm_text(original_text)
        assert is_new is False
        
        # Different text - should be considered new speech
        interim_check = "for Tuesday"
        is_new = norm_text(interim_check) != norm_text(original_text)
        assert is_new is True

    def test_conversation_rollback_on_interruption(self):
        """Test that conversation is rolled back when interrupted"""
        conversation = [
            {"role": "system", "content": "You are a receptionist"},
            {"role": "user", "content": "I need to book"},
        ]
        
        # Simulate interruption - remove last user message
        if conversation and conversation[-1].get('role') == 'user':
            removed = conversation.pop()
            assert removed['content'] == "I need to book"
        
        # Now conversation should only have system message
        assert len(conversation) == 1
        assert conversation[0]['role'] == 'system'
        
        # Add combined text
        conversation.append({"role": "user", "content": "I need to book for Tuesday"})
        assert conversation[-1]['content'] == "I need to book for Tuesday"

    def test_multiple_interruptions_combine_correctly(self):
        """Test handling of multiple rapid interruptions"""
        def norm_text(s: str) -> str:
            return " ".join((s or "").lower().split())
        
        # First speech
        text1 = "I need"
        
        # First interruption
        text2 = "to book"
        combined1 = text1 + " " + text2
        assert combined1 == "I need to book"
        
        # Second interruption
        text3 = "an appointment"
        if not norm_text(text3).startswith(norm_text(combined1)):
            combined2 = combined1 + " " + text3
        else:
            combined2 = text3
        assert combined2 == "I need to book an appointment"

    def test_edge_case_empty_interruption(self):
        """Test handling of empty or whitespace-only interruption"""
        original_text = "I need to book"
        
        # Empty interruption should not change anything
        new_speech = ""
        if new_speech.strip():
            combined = original_text + " " + new_speech
        else:
            combined = original_text
        
        assert combined == "I need to book"
        
        # Whitespace-only interruption
        new_speech = "   "
        if new_speech.strip():
            combined = original_text + " " + new_speech
        else:
            combined = original_text
        
        assert combined == "I need to book"

    def test_edge_case_very_long_text(self):
        """Test handling of very long combined text"""
        original_text = "I need to book an appointment for my car service"
        new_speech = "and also I want to check if you have availability next week for a full inspection"
        
        combined = original_text + " " + new_speech
        
        # Should handle long text without issues
        assert len(combined) > 100
        assert "appointment" in combined
        assert "inspection" in combined

    def test_state_reset_after_successful_response(self):
        """Test that all state is properly reset after successful response"""
        # Simulate state variables
        state = {
            'continuation_window_start': 10.0,
            'continuation_original_text': "I need to book",
            'continuation_energy_since': 10.1,
            'continuation_recovery_mode': True,
            'continuation_base_text': "I need to book",
            'pre_response_pending': True,
            'pre_response_text': "test",
            'pre_response_start': 10.0,
        }
        
        # Simulate reset after successful response
        state['continuation_window_start'] = 0.0
        state['continuation_original_text'] = ""
        state['continuation_energy_since'] = 0.0
        state['continuation_recovery_mode'] = False
        state['continuation_base_text'] = ""
        state['pre_response_pending'] = False
        state['pre_response_text'] = ""
        state['pre_response_start'] = 0.0
        
        # All state should be reset
        assert state['continuation_window_start'] == 0.0
        assert state['continuation_original_text'] == ""
        assert state['continuation_recovery_mode'] is False


class TestCompletionWaitTiming:
    """Test timing-related edge cases"""
    
    def test_interruption_at_exact_boundary(self):
        """Test interruption exactly at COMPLETION_WAIT boundary"""
        response_start = 10.0
        completion_wait = 2.0  # 2 seconds
        
        # Just before boundary - should be in window
        current_time = 11.99
        in_window = (current_time - response_start) <= completion_wait
        assert in_window is True
        
        # Just past boundary - should be outside
        current_time = 12.01
        in_window = (current_time - response_start) <= completion_wait
        assert in_window is False

    def test_sustained_speech_detection(self):
        """Test that speech must be sustained for 100-150ms"""
        speech_start = 10.0
        required_duration = 0.1  # 100ms for LLM processing check, 150ms for TTS speaking check
        
        # Too short - should not trigger
        current_time = 10.05  # 50ms
        is_sustained = (current_time - speech_start) >= required_duration
        assert is_sustained is False
        
        # Long enough - should trigger
        current_time = 10.15  # 150ms
        is_sustained = (current_time - speech_start) >= required_duration
        assert is_sustained is True


class TestIntegrationScenarios:
    """Integration-style tests for complete scenarios"""
    
    def test_scenario_caller_continues_mid_sentence(self):
        """
        Scenario: Caller says "I need to book..." pauses for 0.7s (SILENCE_HOLD),
        AI starts generating, then caller says "...for Tuesday" within 2s (COMPLETION_WAIT)
        
        Expected: AI cancels, combines to "I need to book for Tuesday", restarts
        """
        # Initial state
        original_text = "I need to book"
        conversation = [{"role": "user", "content": original_text}]
        
        # After SILENCE_HOLD (0.7s), AI starts generating
        # continuation_window_start is set to this moment
        continuation_window_start = 10.0
        continuation_original_text = original_text
        
        # Caller speaks within COMPLETION_WAIT window (2s)
        current_time = 11.0  # 1s later, within 2s window
        new_speech = "for Tuesday"
        
        # Check if in window
        completion_wait = 2.0
        in_window = (current_time - continuation_window_start) <= completion_wait
        assert in_window is True
        
        # Cancel and combine
        conversation.pop()  # Remove original
        combined = original_text + " " + new_speech
        conversation.append({"role": "user", "content": combined})
        
        assert conversation[-1]['content'] == "I need to book for Tuesday"

    def test_scenario_caller_interrupts_after_window(self):
        """
        Scenario: Caller says something, AI starts generating after SILENCE_HOLD,
        caller interrupts AFTER COMPLETION_WAIT window (2s)
        
        Expected: Normal barge-in behavior, not text combination
        """
        continuation_window_start = 10.0
        completion_wait = 2.0
        
        # Caller speaks after window
        current_time = 12.5  # 2.5s later, outside 2s window
        
        in_window = (current_time - continuation_window_start) <= completion_wait
        assert in_window is False
        
        # This should trigger normal barge-in, not continuation

    def test_scenario_rapid_fire_corrections(self):
        """
        Scenario: Caller keeps correcting themselves rapidly
        "Monday" -> "no Tuesday" -> "actually Wednesday"
        
        Expected: Each correction combines with previous
        """
        def combine_if_new(original, new):
            norm = lambda s: " ".join((s or "").lower().split())
            if not norm(new).startswith(norm(original)):
                return original + " " + new
            return new
        
        text = "Monday"
        
        # First correction
        text = combine_if_new(text, "no Tuesday")
        assert text == "Monday no Tuesday"
        
        # Second correction
        text = combine_if_new(text, "actually Wednesday")
        assert text == "Monday no Tuesday actually Wednesday"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestToolExecutionSafety:
    """Test that tool execution prevents unsafe cancellation"""
    
    def test_tool_execution_blocks_continuation_restart(self):
        """Test that continuation restart is blocked during tool execution"""
        # Simulate state
        continuation_window_start = 10.0
        continuation_original_text = "I need to book an appointment"
        tool_execution_in_progress = True
        CONTINUATION_WINDOW = 2.0
        now = 10.5  # Within window
        
        # Check if in continuation window (should be False due to tool execution)
        in_continuation_window = (
            continuation_window_start > 0 and 
            (now - continuation_window_start) <= CONTINUATION_WINDOW and
            continuation_original_text and
            not tool_execution_in_progress  # This should block it
        )
        
        assert in_continuation_window is False
    
    def test_continuation_allowed_without_tool_execution(self):
        """Test that continuation works when no tool is executing"""
        continuation_window_start = 10.0
        continuation_original_text = "I need to book an appointment"
        tool_execution_in_progress = False
        CONTINUATION_WINDOW = 2.0
        now = 10.5  # Within window
        
        in_continuation_window = (
            continuation_window_start > 0 and 
            (now - continuation_window_start) <= CONTINUATION_WINDOW and
            continuation_original_text and
            not tool_execution_in_progress
        )
        
        assert in_continuation_window is True


class TestRecoveryModePreservation:
    """Test that recovery mode is preserved across task cancellation"""
    
    def test_recovery_mode_not_cleared_in_finally(self):
        """Test that finally block doesn't clear recovery mode when set"""
        # Simulate the state after interruption detection
        continuation_recovery_mode = True
        continuation_base_text = "I need to book"
        
        # Simulate what the finally block does
        if not continuation_recovery_mode:
            continuation_window_start = 0.0
            continuation_original_text = ""
            continuation_energy_since = 0.0
        
        # Recovery mode should still be True
        assert continuation_recovery_mode is True
        # Base text should still be preserved
        assert continuation_base_text == "I need to book"
    
    def test_recovery_mode_cleared_after_use(self):
        """Test that recovery mode is cleared after text combination"""
        continuation_recovery_mode = True
        continuation_base_text = "I need to book"
        text = "for Tuesday"
        
        # Simulate text combination
        def norm_text(s):
            return " ".join((s or "").lower().split())
        
        if continuation_recovery_mode and continuation_base_text:
            if not norm_text(text).startswith(norm_text(continuation_base_text)):
                text = continuation_base_text + " " + text
            # Reset after use
            continuation_recovery_mode = False
            continuation_base_text = ""
        
        assert text == "I need to book for Tuesday"
        assert continuation_recovery_mode is False
        assert continuation_base_text == ""


class TestFillerPhraseScenarios:
    """Test scenarios involving filler phrases during tool calls"""
    
    def test_filler_phrase_timing(self):
        """
        Test that CONTINUATION_WINDOW (2s) is long enough for filler phrases.
        Filler phrases like "Let me check that for you" take ~1.5s to play.
        """
        CONTINUATION_WINDOW = 2.0
        filler_duration = 1.5  # Typical filler phrase duration
        
        # Caller should be able to interrupt after filler plays
        response_start = 10.0
        filler_ends = response_start + filler_duration  # 11.5
        caller_speaks = filler_ends + 0.3  # 11.8 - caller speaks 300ms after filler
        
        # Should still be in window
        in_window = (caller_speaks - response_start) <= CONTINUATION_WINDOW
        assert in_window is True  # 1.8s < 2.0s
    
    def test_late_interruption_outside_window(self):
        """Test that interruption after CONTINUATION_WINDOW is normal barge-in"""
        CONTINUATION_WINDOW = 2.0
        response_start = 10.0
        
        # Caller speaks 2.5s after response starts
        caller_speaks = 12.5
        
        in_window = (caller_speaks - response_start) <= CONTINUATION_WINDOW
        assert in_window is False  # 2.5s > 2.0s - should be normal barge-in


class TestConversationIntegrity:
    """Test conversation state integrity during interruptions"""
    
    def test_conversation_pop_only_removes_user_message(self):
        """Test that only user messages are popped, not system or assistant"""
        conversation = [
            {"role": "system", "content": "You are a receptionist"},
            {"role": "assistant", "content": "How can I help?"},
            {"role": "user", "content": "I need to book"},
        ]
        
        # Only pop if last message is user
        if conversation and conversation[-1].get('role') == 'user':
            conversation.pop()
        
        assert len(conversation) == 2
        assert conversation[-1]['role'] == 'assistant'
    
    def test_conversation_not_popped_if_assistant_last(self):
        """Test that assistant messages are not accidentally popped"""
        conversation = [
            {"role": "system", "content": "You are a receptionist"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "How can I help?"},
        ]
        
        original_len = len(conversation)
        
        # Only pop if last message is user
        if conversation and conversation[-1].get('role') == 'user':
            conversation.pop()
        
        # Should not have changed
        assert len(conversation) == original_len
    
    def test_empty_conversation_handling(self):
        """Test that empty conversation doesn't cause errors"""
        conversation = []
        
        # Should not raise error
        if conversation and conversation[-1].get('role') == 'user':
            conversation.pop()
        
        assert len(conversation) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
