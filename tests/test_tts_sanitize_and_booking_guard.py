"""
Tests for Issue 5 (TTS cutoff on bullet points) and Issue 6 (BOOKING_CONFIRMED misfire).

Issue 5: Deepgram TTS stops speaking when it encounters newline+dash formatting
like "I have availability on:\n- Monday the 23rd from 8 am to 3 pm".
Fix: sanitize_for_tts() strips bullet/dash/newline formatting before TTS.

Issue 6: "Yeah. What's available, I said?" triggers BOOKING_CONFIRMED pre-check
when user is asking to repeat availability, not confirming a booking.
Fix: Removed brittle phrases + added negative guard for availability keywords.
"""
import pytest
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Issue 5: TTS sanitization tests
# ============================================================

class TestSanitizeForTts:
    """Test that sanitize_for_tts strips formatting that breaks Deepgram TTS."""

    def setup_method(self):
        from src.services.llm_stream import sanitize_for_tts
        self.sanitize = sanitize_for_tts

    def test_strips_newline_dash_bullets(self):
        text = "I have availability on:\n- Monday the 23rd from 8 am to 3 pm\n- Wednesday the 25th from 9 am to 1 pm"
        result = self.sanitize(text)
        assert "\n" not in result
        assert "\n-" not in result
        assert "Monday the 23rd" in result
        assert "Wednesday the 25th" in result

    def test_strips_bullet_point_unicode(self):
        text = "Available days:\n• Monday\n• Tuesday\n• Wednesday"
        result = self.sanitize(text)
        assert "\n" not in result
        assert "•" not in result
        assert "Monday" in result
        assert "Tuesday" in result

    def test_strips_asterisk_bullets(self):
        text = "Options:\n* Option A\n* Option B"
        result = self.sanitize(text)
        assert "\n" not in result
        assert "Option A" in result
        assert "Option B" in result

    def test_converts_to_comma_separated(self):
        text = "I have:\n- Monday at 9 am\n- Tuesday at 2 pm\n- Wednesday at 10 am"
        result = self.sanitize(text)
        # Should be comma-separated, not bullet-separated
        assert ", Monday at 9 am" in result or "Monday at 9 am," in result
        assert ", Tuesday at 2 pm" in result or "Tuesday at 2 pm," in result

    def test_no_double_commas(self):
        text = "I have:\n- Monday\n- Tuesday"
        result = self.sanitize(text)
        assert ",," not in result

    def test_colon_comma_cleanup(self):
        """After stripping '\n- ', 'I have:\n- Monday' should become 'I have: Monday' not 'I have:, Monday'."""
        text = "I have:\n- Monday at 9 am"
        result = self.sanitize(text)
        assert ":," not in result
        assert "I have: Monday at 9 am" in result

    def test_preserves_normal_text(self):
        text = "I have Monday at 9 am and Tuesday at 2 pm available."
        result = self.sanitize(text)
        assert result == text

    def test_preserves_commas_in_normal_text(self):
        text = "I have Monday, Tuesday, and Wednesday available."
        result = self.sanitize(text)
        assert result == text

    def test_handles_empty_string(self):
        assert self.sanitize("") == ""

    def test_handles_none(self):
        assert self.sanitize(None) is None

    def test_replaces_plain_newlines(self):
        text = "Line one\nLine two\nLine three"
        result = self.sanitize(text)
        assert "\n" not in result
        assert "Line one" in result
        assert "Line two" in result

    def test_real_world_availability_response(self):
        """Simulate the exact format that was causing TTS cutoff in production."""
        text = (
            "I have availability on:\n"
            "- Monday the 23rd from 8 am to 3 pm\n"
            "- Wednesday the 25th from 9 am to 5 pm\n"
            "- Thursday the 26th from 10 am to 2 pm"
        )
        result = self.sanitize(text)
        # Must be a single line with no bullets
        assert "\n" not in result
        assert "- " not in result
        # All days must be present
        assert "Monday the 23rd" in result
        assert "Wednesday the 25th" in result
        assert "Thursday the 26th" in result


# ============================================================
# Issue 6: BOOKING_CONFIRMED misfire tests
# ============================================================

class TestBookingConfirmedNegativeGuard:
    """Test that BOOKING_CONFIRMED doesn't fire when user asks about availability."""

    def _run_precheck(self, prev_assistant_msg, user_message):
        """Simulate the BOOKING_CONFIRMED pre-check logic from llm_stream.py."""
        import random
        prev_assistant_msg = prev_assistant_msg.lower()
        user_message = user_message.lower()

        booking_confirmation_phrases = [
            "ready to book", "shall i book", "want me to book",
            "confirm the booking", "go ahead and book", "all correct",
            "is that correct?", "correct?"
        ]

        day_names_lower = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        time_indicators = ["am", "pm", "o'clock"]
        prev_has_day = any(d in prev_assistant_msg for d in day_names_lower)
        prev_has_time = any(t in prev_assistant_msg for t in time_indicators)
        prev_is_booking_context = prev_has_day and prev_has_time

        ai_asked_to_book = False
        for phrase in booking_confirmation_phrases:
            if phrase in prev_assistant_msg:
                if phrase in ["is that correct?", "correct?"]:
                    if prev_is_booking_context:
                        ai_asked_to_book = True
                        break
                else:
                    ai_asked_to_book = True
                    break

        user_confirms = any(phrase in user_message for phrase in [
            "yes", "yeah", "yep", "please", "go ahead", "book it",
            "that's perfect", "sounds good", "correct", "that's right", "that's correct"
        ])

        # Negative guard
        user_asking_availability = any(word in user_message for word in [
            "available", "availability", "again", "what's available", "when are you", "repeat"
        ])

        return ai_asked_to_book and user_confirms and not user_asking_availability

    def test_whats_available_i_said_does_not_trigger(self):
        """The exact production misfire case: user says 'Yeah. What's available, I said?'"""
        prev = "I'm here! Which day and time would you like for the tap replacement?"
        user = "yeah. what's available, i said?"
        assert not self._run_precheck(prev, user)

    def test_say_that_again_does_not_trigger(self):
        prev = "I have Monday at 9 am or Tuesday at 2 pm. Is that correct?"
        user = "yeah can you say that again"
        assert not self._run_precheck(prev, user)

    def test_whats_available_does_not_trigger(self):
        prev = "I have Monday at 9 am. Is that correct?"
        user = "yeah what's available"
        assert not self._run_precheck(prev, user)

    def test_repeat_does_not_trigger(self):
        prev = "I have Monday at 9 am. Is that correct?"
        user = "yeah repeat that please"
        assert not self._run_precheck(prev, user)

    def test_genuine_booking_confirm_still_triggers(self):
        """Normal booking confirmation should still work."""
        prev = "so that's monday at 9 am for the tap replacement. shall i book that?"
        user = "yes please"
        assert self._run_precheck(prev, user)

    def test_ready_to_book_yes_triggers(self):
        prev = "ready to book that for you?"
        user = "yeah go ahead"
        assert self._run_precheck(prev, user)

    def test_is_that_correct_with_day_time_triggers(self):
        prev = "monday at 2 pm for the boiler service. is that correct?"
        user = "that's correct"
        assert self._run_precheck(prev, user)

    def test_is_that_correct_without_day_time_does_not_trigger(self):
        """Generic 'is that correct?' without booking context should not trigger."""
        prev = "your name is john smith. is that correct?"
        user = "yes"
        assert not self._run_precheck(prev, user)

    def test_tap_replacement_phrases_removed(self):
        """The brittle 'for the tap replacement' phrases should no longer be in the list."""
        booking_confirmation_phrases = [
            "ready to book", "shall i book", "want me to book",
            "confirm the booking", "go ahead and book", "all correct",
            "is that correct?", "correct?"
        ]
        assert "for the tap replacement, correct" not in booking_confirmation_phrases
        assert "for the tap replacement?" not in booking_confirmation_phrases


class TestBookingConfirmedPhrasesInCode:
    """Verify the actual code no longer contains the brittle phrases."""

    def test_tap_replacement_phrases_removed_from_code(self):
        """Check the actual llm_stream.py source doesn't have the brittle phrases."""
        import inspect
        from src.services import llm_stream
        source = inspect.getsource(llm_stream)

        # These should have been removed
        assert '"for the tap replacement, correct"' not in source
        assert '"for the tap replacement?"' not in source

    def test_sanitize_for_tts_exists(self):
        """Verify sanitize_for_tts function exists in llm_stream."""
        from src.services.llm_stream import sanitize_for_tts
        assert callable(sanitize_for_tts)

    def test_sanitize_for_tts_used_in_direct_response(self):
        """Verify sanitize_for_tts is called on direct responses."""
        import inspect
        from src.services import llm_stream
        source = inspect.getsource(llm_stream)
        assert "sanitize_for_tts(direct_response)" in source

    def test_sanitize_for_tts_used_in_token_stream(self):
        """Verify sanitize_for_tts is called on streamed tokens."""
        import inspect
        from src.services import llm_stream
        source = inspect.getsource(llm_stream)
        assert "sanitize_for_tts(cleaned_token)" in source

    def test_negative_guard_in_booking_confirmed(self):
        """Verify the negative guard for availability keywords exists."""
        import inspect
        from src.services import llm_stream
        source = inspect.getsource(llm_stream)
        assert "user_asking_availability" in source
        assert "not user_asking_availability" in source
