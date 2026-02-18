"""
Tests for the continuation window feature.
This feature allows callers to continue speaking after a response starts,
cancelling the response and restarting with combined text.
"""
import pytest
import asyncio


class MockASR:
    """Mock ASR for testing"""
    def __init__(self):
        self.interim = ""
        self.text = ""
        
    def get_interim(self):
        return self.interim
    
    def get_text(self):
        return self.text
    
    def clear_all(self):
        self.interim = ""
        self.text = ""
        
    async def feed(self, audio):
        pass


def norm_text(s: str) -> str:
    """Normalize text for comparison"""
    return " ".join((s or "").lower().split())


class TestContinuationWindowLogic:
    """Test the continuation window detection logic"""
    
    def test_new_speech_detection(self):
        """Test that new speech is correctly identified as different from original"""
        original = "I need to book"
        new_speech = "an appointment for tomorrow"
        
        # New speech should be detected as different
        is_new = (
            len(new_speech.split()) >= 1 and
            len(new_speech.strip()) >= 3 and
            norm_text(new_speech) != norm_text(original)
        )
        assert is_new is True
        
    def test_same_speech_not_detected(self):
        """Test that same speech is not detected as new"""
        original = "I need to book"
        same_speech = "I need to book"
        
        is_new = (
            len(same_speech.split()) >= 1 and
            len(same_speech.strip()) >= 3 and
            norm_text(same_speech) != norm_text(original)
        )
        assert is_new is False
        
    def test_continuation_combines_text(self):
        """Test that continuation correctly combines original and new text"""
        original = "I need to book"
        new_speech = "an appointment"
        
        # If new speech doesn't start with original, combine them
        if norm_text(new_speech).startswith(norm_text(original)):
            combined = new_speech
        else:
            combined = original + " " + new_speech
            
        assert combined == "I need to book an appointment"
        
    def test_continuation_avoids_duplication(self):
        """Test that continuation doesn't duplicate when ASR already combined"""
        original = "I need"
        # ASR might return the full phrase if it caught up
        new_speech = "I need to book an appointment"
        
        if norm_text(new_speech).startswith(norm_text(original)):
            combined = new_speech
        else:
            combined = original + " " + new_speech
            
        # Should use new_speech directly since it already contains original
        assert combined == "I need to book an appointment"
        
    def test_noise_not_detected(self):
        """Test that noise/short sounds are not detected as speech"""
        original = "I need to book"
        noise = "um"  # Only 2 chars
        
        is_new = (
            len(noise.split()) >= 1 and
            len(noise.strip()) >= 3 and  # Requires 3+ chars
            norm_text(noise) != norm_text(original)
        )
        assert is_new is False
        
    def test_empty_not_detected(self):
        """Test that empty string is not detected as speech"""
        original = "I need to book"
        empty = ""
        
        is_new = (
            len(empty.split()) >= 1 and
            len(empty.strip()) >= 3 and
            norm_text(empty) != norm_text(original)
        )
        assert is_new is False


class TestContinuationWindowTiming:
    """Test the timing aspects of continuation window"""
    
    def test_window_active_within_threshold(self):
        """Test that window is active within the threshold"""
        continuation_window_start = 100.0
        CONTINUATION_WINDOW = 2.0  # Default is now 2 seconds
        continuation_original_text = "hello"
        
        now = 101.5  # 1.5 seconds after start (within 2s window)
        
        in_continuation_window = (
            continuation_window_start > 0 and
            (now - continuation_window_start) <= CONTINUATION_WINDOW and
            bool(continuation_original_text)
        )
        assert in_continuation_window is True
        
    def test_window_inactive_after_threshold(self):
        """Test that window is inactive after the threshold"""
        continuation_window_start = 100.0
        CONTINUATION_WINDOW = 2.0
        continuation_original_text = "hello"
        
        now = 102.5  # 2.5 seconds after start (past 2s threshold)
        
        in_continuation_window = (
            continuation_window_start > 0 and
            (now - continuation_window_start) <= CONTINUATION_WINDOW and
            bool(continuation_original_text)
        )
        assert in_continuation_window is False
        
    def test_window_inactive_without_original_text(self):
        """Test that window is inactive without original text"""
        continuation_window_start = 100.0
        CONTINUATION_WINDOW = 2.0
        continuation_original_text = ""  # No original text
        
        now = 101.0
        
        in_continuation_window = (
            continuation_window_start > 0 and
            (now - continuation_window_start) <= CONTINUATION_WINDOW and
            bool(continuation_original_text)
        )
        assert in_continuation_window is False
        
    def test_window_inactive_when_not_started(self):
        """Test that window is inactive when not started"""
        continuation_window_start = 0.0  # Not started
        CONTINUATION_WINDOW = 2.0
        continuation_original_text = "hello"
        
        now = 101.0
        
        in_continuation_window = (
            continuation_window_start > 0 and
            (now - continuation_window_start) <= CONTINUATION_WINDOW and
            bool(continuation_original_text)
        )
        assert in_continuation_window is False


class TestConversationManagement:
    """Test conversation list management during continuation"""
    
    def test_removes_last_user_message(self):
        """Test that last user message is removed when continuation detected"""
        conversation = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "I need to book"},
        ]
        
        # Simulate continuation detection - remove last user message
        if conversation and conversation[-1].get('role') == 'user':
            conversation.pop()
            
        assert len(conversation) == 1
        assert conversation[0]['role'] == 'system'
        
    def test_does_not_remove_non_user_message(self):
        """Test that non-user messages are not removed"""
        conversation = [
            {"role": "system", "content": "You are helpful"},
            {"role": "assistant", "content": "How can I help?"},
        ]
        
        original_len = len(conversation)
        
        # Should not remove assistant message
        if conversation and conversation[-1].get('role') == 'user':
            conversation.pop()
            
        assert len(conversation) == original_len


class TestRecoveryMode:
    """Test the recovery mode text combination logic"""
    
    def test_recovery_mode_combines_base_with_new_text(self):
        """Test that recovery mode correctly combines base text with new speech"""
        continuation_recovery_mode = True
        continuation_base_text = "I need to book"
        text = "an appointment for tomorrow"
        
        # Simulate the combination logic
        if continuation_recovery_mode and continuation_base_text:
            if not norm_text(text).startswith(norm_text(continuation_base_text)):
                text = continuation_base_text + " " + text
        
        assert text == "I need to book an appointment for tomorrow"
        
    def test_recovery_mode_avoids_duplication_when_asr_includes_base(self):
        """Test that recovery mode doesn't duplicate when ASR already has base text"""
        continuation_recovery_mode = True
        continuation_base_text = "I need"
        # ASR sometimes catches up and includes the original
        text = "I need to book an appointment"
        
        if continuation_recovery_mode and continuation_base_text:
            if not norm_text(text).startswith(norm_text(continuation_base_text)):
                text = continuation_base_text + " " + text
        
        # Should NOT duplicate since text already starts with base
        assert text == "I need to book an appointment"
        
    def test_recovery_mode_inactive_when_no_base_text(self):
        """Test that recovery mode does nothing without base text"""
        continuation_recovery_mode = True
        continuation_base_text = ""  # Empty base
        text = "an appointment"
        original_text = text
        
        if continuation_recovery_mode and continuation_base_text:
            if not norm_text(text).startswith(norm_text(continuation_base_text)):
                text = continuation_base_text + " " + text
        
        # Should remain unchanged
        assert text == original_text
        
    def test_recovery_mode_inactive_when_flag_false(self):
        """Test that recovery mode does nothing when flag is false"""
        continuation_recovery_mode = False
        continuation_base_text = "I need to book"
        text = "an appointment"
        original_text = text
        
        if continuation_recovery_mode and continuation_base_text:
            if not norm_text(text).startswith(norm_text(continuation_base_text)):
                text = continuation_base_text + " " + text
        
        # Should remain unchanged
        assert text == original_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
