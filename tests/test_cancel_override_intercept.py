"""
Tests for the cancel override in the reschedule intercept logic.

When a user says "cancel" after previously rescheduling in the same call,
the system should NOT redirect cancel_job → reschedule_job.
"""
import json
import pytest


def compute_user_wants_reschedule(detected_intent, user_text, messages):
    """
    Extracted logic from llm_stream.py stream_llm() — the reschedule intercept
    decision. Returns (user_wants_reschedule, user_explicitly_cancelling).
    """
    reschedule_words = ["reschedule", "move my", "move the", "change the date", "change the day", "move it"]
    cancel_words = ["cancel", "cancel my", "need to cancel", "want to cancel", "cancel that", "cancel the"]

    user_explicitly_cancelling = (
        detected_intent == "CANCEL_REQUEST"
        or any(w in user_text.lower() for w in cancel_words)
    )

    # Multi-turn cancel detection: check if cancel_job was already called earlier
    if not user_explicitly_cancelling:
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("function", {}).get("name") in ("cancel_job", "cancel_appointment"):
                        user_explicitly_cancelling = True
                        break
            if user_explicitly_cancelling:
                break
    if not user_explicitly_cancelling:
        # Check if a recent user message mentioned cancel
        # Look back up to 5 user messages
        # But stop if we hit a reschedule word first — means user changed their mind
        user_msg_count = 0
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_msg_count += 1
                msg_text = msg.get("content", "").lower()
                if any(w in msg_text for w in cancel_words):
                    user_explicitly_cancelling = True
                    break
                if any(w in msg_text for w in reschedule_words):
                    break
                if user_msg_count >= 5:
                    break

    user_wants_reschedule = detected_intent == "RESCHEDULE" or any(w in user_text.lower() for w in reschedule_words)

    if not user_wants_reschedule and not user_explicitly_cancelling:
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("function", {}).get("name") in ("reschedule_job", "reschedule_appointment"):
                        user_wants_reschedule = True
                        break
            if user_wants_reschedule:
                break

    if not user_wants_reschedule and not user_explicitly_cancelling:
        for msg in messages:
            if msg.get("role") == "user":
                msg_text = msg.get("content", "").lower()
                if any(w in msg_text for w in reschedule_words):
                    user_wants_reschedule = True
                    break

    if user_explicitly_cancelling and user_wants_reschedule:
        user_wants_reschedule = False

    return user_wants_reschedule, user_explicitly_cancelling


def _make_reschedule_history():
    """Messages list with prior reschedule_job tool calls (simulates a completed reschedule)."""
    return [
        {"role": "user", "content": "I'd like to reschedule my appointment"},
        {"role": "assistant", "tool_calls": [
            {"function": {"name": "reschedule_job", "arguments": json.dumps({"current_date": "Monday", "customer_name": "James"})}}
        ]},
        {"role": "tool", "content": json.dumps({"success": True})},
        {"role": "assistant", "content": "Your appointment has been moved to Thursday."},
    ]


class TestCancelOverrideAfterReschedule:
    """The bug: user says 'cancel' but history has reschedule_job calls, so cancel_job gets redirected."""

    def test_cancel_request_not_intercepted_after_prior_reschedule(self):
        """Core bug fix: 'cancel that job' should NOT be treated as reschedule."""
        messages = _make_reschedule_history()
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent="CANCEL_REQUEST",
            user_text="Actually, can you please cancel that job?",
            messages=messages,
        )
        assert explicitly_cancelling is True
        assert wants_reschedule is False

    def test_explicit_cancel_words_override_history(self):
        """Even without CANCEL_REQUEST intent, cancel words in user text should override."""
        messages = _make_reschedule_history()
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="No. I said I want to cancel, please.",
            messages=messages,
        )
        assert explicitly_cancelling is True
        assert wants_reschedule is False

    def test_cancel_my_booking_after_reschedule(self):
        messages = _make_reschedule_history()
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent="CANCEL_REQUEST",
            user_text="I need to cancel my booking",
            messages=messages,
        )
        assert explicitly_cancelling is True
        assert wants_reschedule is False

    def test_cancel_followup_date_after_cancel_request(self):
        """Key bug: user said 'cancel' in previous turn, now gives date — should stay in cancel flow."""
        messages = _make_reschedule_history() + [
            {"role": "user", "content": "Actually, can I cancel a job, please?"},
            {"role": "assistant", "content": "What day is your booking for?"},
        ]
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="It's for the April 2",
            messages=messages,
        )
        assert explicitly_cancelling is True
        assert wants_reschedule is False

    def test_cancel_followup_after_cancel_tool_called(self):
        """If cancel_job was already called (e.g. to list bookings), follow-up should stay in cancel."""
        messages = _make_reschedule_history() + [
            {"role": "user", "content": "Can I cancel a job?"},
            {"role": "assistant", "tool_calls": [
                {"function": {"name": "cancel_job", "arguments": json.dumps({"appointment_date": "April 2", "customer_name": ""})}}
            ]},
            {"role": "tool", "content": json.dumps({"success": False, "message": "Which booking?"})},
            {"role": "assistant", "content": "I have 3 bookings. Which name is yours?"},
        ]
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="John Smith",
            messages=messages,
        )
        assert explicitly_cancelling is True
        assert wants_reschedule is False

    def test_cancel_two_messages_back_after_reschedule(self):
        """Exact production bug: cancel request is 2 user messages back, with a neutral date reply in between."""
        messages = _make_reschedule_history() + [
            # Reschedule completed successfully
            {"role": "assistant", "content": "Successfully rescheduled to Saturday, April 04."},
            # User now wants to cancel
            {"role": "user", "content": "Perfect. Actually, would I be able to cancel that booking?"},
            {"role": "assistant", "content": "What day is your booking for?"},
            # User gives the date — no cancel words
            {"role": "user", "content": "It's for Saturday, April 4."},
            {"role": "assistant", "content": "What day is your booking for?"},
        ]
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="It's for Saturday, April 4",
            messages=messages,
        )
        assert explicitly_cancelling is True
        assert wants_reschedule is False


class TestRescheduleStillWorks:
    """Make sure the cancel override doesn't break legitimate reschedule interception."""

    def test_reschedule_intent_still_detected(self):
        messages = [{"role": "user", "content": "I want to reschedule"}]
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent="RESCHEDULE",
            user_text="I want to reschedule my appointment",
            messages=messages,
        )
        assert wants_reschedule is True
        assert explicitly_cancelling is False

    def test_reschedule_from_history_when_no_cancel(self):
        """Neutral follow-up after reschedule should still be treated as reschedule."""
        messages = _make_reschedule_history()
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="This Thursday please",
            messages=messages,
        )
        assert wants_reschedule is True
        assert explicitly_cancelling is False

    def test_reschedule_from_earlier_user_message(self):
        """If an earlier user message said 'reschedule' and current is neutral, still intercept."""
        messages = [
            {"role": "user", "content": "I want to reschedule my appointment"},
            {"role": "assistant", "content": "What day is your booking for?"},
        ]
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="This Thursday",
            messages=messages,
        )
        assert wants_reschedule is True
        assert explicitly_cancelling is False

    def test_move_my_appointment_detected(self):
        messages = []
        wants_reschedule, _ = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="Can you move my appointment to next week?",
            messages=messages,
        )
        assert wants_reschedule is True


class TestEdgeCases:

    def test_cancel_the_reschedule(self):
        """User says 'cancel the reschedule' — cancel should win."""
        messages = _make_reschedule_history()
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="cancel the reschedule",
            messages=messages,
        )
        # Both words present, but cancel override should win
        assert explicitly_cancelling is True
        assert wants_reschedule is False

    def test_no_intent_no_history(self):
        """Neutral message with no history — neither flag set."""
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="Hello, I have a question",
            messages=[],
        )
        assert wants_reschedule is False
        assert explicitly_cancelling is False

    def test_cancel_with_no_prior_reschedule(self):
        """Cancel with clean history — should just work normally."""
        messages = [
            {"role": "user", "content": "I booked something last week"},
            {"role": "assistant", "content": "How can I help?"},
        ]
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent="CANCEL_REQUEST",
            user_text="I want to cancel that",
            messages=messages,
        )
        assert explicitly_cancelling is True
        assert wants_reschedule is False

    def test_cancel_then_change_mind_to_reschedule(self):
        """User said 'cancel' earlier but then said 'reschedule' — reschedule should win."""
        messages = _make_reschedule_history() + [
            {"role": "user", "content": "I want to cancel that booking"},
            {"role": "assistant", "content": "Are you sure you want to cancel?"},
            {"role": "user", "content": "Actually, can you reschedule it instead?"},
            {"role": "assistant", "content": "What day would you like to move it to?"},
        ]
        wants_reschedule, explicitly_cancelling = compute_user_wants_reschedule(
            detected_intent=None,
            user_text="Next Thursday",
            messages=messages,
        )
        # The reschedule message is more recent than the cancel — reschedule should win
        assert explicitly_cancelling is False
        assert wants_reschedule is True
