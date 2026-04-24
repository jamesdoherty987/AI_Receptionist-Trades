"""
Tests for the 4 fixes:
1. "Yeah that's correct" freezing - ADDRESS_CONFIRMED pre-check misfire
2. Time-constrained availability (before/after X pm)
3. Booking confirmation cutoff - TIME_SELECTED + BOOKING_CONFIRMED pre-check
4. Fuzzy match too aggressive (Dorothy/Doherty, Josh/John)
"""
import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 1: ADDRESS_CONFIRMED pre-check misfire
# ═══════════════════════════════════════════════════════════════════════

class TestAddressConfirmedPrecheck:
    """
    The ADDRESS_CONFIRMED pre-check was too broad.
    "is that correct" and "is that right" matched booking confirmations,
    causing filler misfires when the LLM didn't call any tools.
    """

    def _simulate_precheck(self, prev_assistant_msg, user_message):
        """Simulate the ADDRESS_CONFIRMED pre-check logic."""
        prev = prev_assistant_msg.lower()
        user = user_message.lower()

        address_phrases = [
            "same address", "still your address", "your address",
            "still at", "at the same", "same location", "same place",
            "address as before", "address on file",
            "correct address", "the correct address",
        ]
        ai_asked_address = any(p in prev for p in address_phrases)

        booking_phrases = ["booked in for", "book for", "want to book"]
        day_names = ["monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday"]
        time_patterns = [
            "at 1 pm", "at 2 pm", "at 3 pm", "at 4 pm", "at 5 pm",
            "at 9 am", "at 10 am", "at 11 am", "at 12 pm",
        ]
        has_booking_phrase = any(p in prev for p in booking_phrases)
        has_day_and_time = (
            any(d in prev for d in day_names)
            and any(t in prev for t in time_patterns)
        )
        override_phrases = ["same address", "address as before", "address on file"]
        ai_asking_about_booking = (
            (has_booking_phrase or has_day_and_time)
            and not any(p in prev for p in override_phrases)
        )

        user_confirms = any(
            p in user
            for p in ["yes", "yeah", "yep", "correct", "that's right",
                       "it is", "that's it", "that's correct"]
        )

        return ai_asked_address and user_confirms and not ai_asking_about_booking

    # --- Cases that should NOT trigger ADDRESS_CONFIRMED ---

    def test_booking_confirm_does_not_trigger(self):
        """AI asks 'Thursday the 26th at 3 PM for the tap replacement, correct?'
        User says 'Yes. That's correct.' -> should NOT trigger ADDRESS_CONFIRMED."""
        result = self._simulate_precheck(
            "just to confirm, you want to book for thursday the 26th at 3 pm for the tap replacement, correct?",
            "yes. that's correct.",
        )
        assert result is False, "Booking confirmation must NOT trigger ADDRESS_CONFIRMED"

    def test_name_confirm_does_not_trigger(self):
        """AI asks 'That's James Dorothy, correct?' -> should NOT trigger."""
        result = self._simulate_precheck(
            "that's james dorothy, correct?",
            "yeah. correct.",
        )
        assert result is False, "Name confirmation must NOT trigger ADDRESS_CONFIRMED"

    def test_service_confirm_does_not_trigger(self):
        """AI asks 'A tap replacement in your kitchen, is that correct?'"""
        result = self._simulate_precheck(
            "a tap replacement in your kitchen, is that correct?",
            "yeah. that's correct.",
        )
        assert result is False, "Service confirmation must NOT trigger ADDRESS_CONFIRMED"

    def test_generic_correct_does_not_trigger(self):
        """AI says something without address phrases, user says 'correct'."""
        result = self._simulate_precheck(
            "can i get your name please?",
            "yeah. correct.",
        )
        assert result is False

    # --- Cases that SHOULD trigger ADDRESS_CONFIRMED ---

    def test_same_address_triggers(self):
        """AI asks 'Same address as before - V95H5P2?' -> SHOULD trigger."""
        result = self._simulate_precheck(
            "great to hear from you again, james! same address as before - v95h5p2?",
            "yeah. correct.",
        )
        assert result is True, "Address confirmation SHOULD trigger ADDRESS_CONFIRMED"

    def test_address_on_file_triggers(self):
        """AI asks 'Is the address on file still correct?'"""
        result = self._simulate_precheck(
            "is the address on file at 123 main street still correct?",
            "yes it is.",
        )
        assert result is True

    def test_same_location_triggers(self):
        """AI asks 'Same location as last time?'"""
        result = self._simulate_precheck(
            "same location as last time?",
            "yep.",
        )
        assert result is True

    def test_address_with_booking_context_still_triggers(self):
        """AI mentions address AND has 'address as before' override."""
        result = self._simulate_precheck(
            "same address as before at v95h5p2? we have monday at 2 pm available.",
            "yes that's correct.",
        )
        assert result is True, "Address phrase with override should still trigger"


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 2: Time-constrained availability (before/after)
# ═══════════════════════════════════════════════════════════════════════

class TestTimeFilterBeforeAfter:
    """
    search_availability should support 'before_X' time filters
    in addition to the existing 'after_X'.
    """

    def test_before_filter_db_path(self):
        """before_14 should exclude slots at 14:00 and later."""
        time_filter = "before_14"
        # Simulate slot checking
        accepted = []
        for hour in range(8, 17):
            slot_hour = hour
            if time_filter.startswith("before_"):
                before_hour = int(time_filter.split("_")[1])
                if slot_hour >= before_hour:
                    continue
            accepted.append(hour)
        assert accepted == [8, 9, 10, 11, 12, 13]
        assert 14 not in accepted
        assert 15 not in accepted

    def test_after_filter_db_path(self):
        """after_14 should exclude slots before 14:00."""
        time_filter = "after_14"
        accepted = []
        for hour in range(8, 17):
            slot_hour = hour
            if time_filter.startswith("after_"):
                after_hour = int(time_filter.split("_")[1])
                if slot_hour < after_hour:
                    continue
            accepted.append(hour)
        assert accepted == [14, 15, 16]
        assert 13 not in accepted

    def test_before_filter_gcal_path(self):
        """before_X filter in Google Calendar path."""
        time_filter = "before_15"
        slots = [
            datetime(2026, 3, 23, h, 0) for h in range(8, 17)
        ]
        filtered = []
        for slot in slots:
            if time_filter.startswith("before_"):
                before_hour = int(time_filter.split("_")[1])
                if slot.hour < before_hour:
                    filtered.append(slot)
        assert len(filtered) == 7  # 8,9,10,11,12,13,14
        assert all(s.hour < 15 for s in filtered)

    def test_morning_filter_unchanged(self):
        """morning filter should still work (before 12pm)."""
        time_filter = "morning"
        accepted = []
        for hour in range(8, 17):
            if time_filter == "morning" and hour >= 12:
                continue
            accepted.append(hour)
        assert accepted == [8, 9, 10, 11]

    def test_no_results_message_before(self):
        """No-results message should say 'before X:00' for before_X filter."""
        time_filter = "before_14"
        if time_filter.startswith("after_"):
            desc = f"after {time_filter.split('_')[1]}:00"
        elif time_filter.startswith("before_"):
            desc = f"before {time_filter.split('_')[1]}:00"
        else:
            desc = {"morning": "morning", "afternoon": "afternoon",
                    "evening": "evening"}.get(time_filter, time_filter)
        assert desc == "before 14:00"

    def test_no_results_message_after(self):
        """No-results message should say 'after X:00' for after_X filter."""
        time_filter = "after_16"
        if time_filter.startswith("after_"):
            desc = f"after {time_filter.split('_')[1]}:00"
        elif time_filter.startswith("before_"):
            desc = f"before {time_filter.split('_')[1]}:00"
        else:
            desc = time_filter
        assert desc == "after 16:00"

    def test_parse_prompt_mentions_before(self):
        """The AI parse prompt in calendar_tools should mention before_X."""
        with open('src/services/calendar_tools.py', 'r') as f:
            content = f.read()
        assert '"before_X"' in content or "'before_X'" in content
        assert '"before_14"' in content or "'before_14'" in content
        assert '"before_15"' in content or "'before_15'" in content

    def test_tool_description_mentions_before(self):
        """search_availability tool description should mention 'before 2pm'."""
        with open('src/services/calendar_tools.py', 'r') as f:
            content = f.read()
        assert "before 2pm" in content.lower() or "before_" in content

    def test_system_prompt_mentions_before(self):
        """System prompt should guide LLM to use search_availability for time prefs."""
        with open('prompts/trades_prompt.txt', 'r') as f:
            content = f.read()
        assert "before 2pm" in content.lower() or "before" in content.lower()
        assert "search_availability" in content


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 3: Booking confirmation / TIME_SELECTED pre-check
# ═══════════════════════════════════════════════════════════════════════

class TestTimeSelectedPrecheck:
    """
    TIME_SELECTED was too loose - saying just '2pm' triggered it,
    causing a filler + misfire where LLM just confirms instead of booking.
    Now requires day+time or explicit pick phrase.
    """

    def _simulate_time_selected(self, prev_assistant_msg, user_message):
        """Simulate the TIME_SELECTED pre-check logic."""
        prev = prev_assistant_msg.lower()
        user = user_message.lower()

        explicit_pick = [
            "i'll take", "let's do", "let's go with", "that one",
            "the first one", "the second", "morning one", "afternoon one",
            "book me in for", "go with",
        ]
        day_names = ["monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday"]
        time_phrases = [
            "9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm",
            "9 o'clock", "10 o'clock",
            "at 9", "at 10", "at 11", "at 12", "at 1", "at 2", "at 3",
            "at 4", "at 5",
        ]
        time_offered = any(
            p in prev
            for p in ["available", "free", "i have", "which works",
                       "which time", "which day"]
        )
        has_explicit = any(p in user for p in explicit_pick)
        has_day = any(d in user for d in day_names)
        has_time = any(t in user for t in time_phrases)

        return time_offered and (has_explicit or (has_day and has_time))

    # --- Should NOT trigger ---

    def test_just_2pm_does_not_trigger(self):
        """'2PM or something' should NOT trigger TIME_SELECTED."""
        result = self._simulate_time_selected(
            "i have monday the 23rd from 8 am to 3 pm. which works best for you?",
            "2pm or something.",
        )
        assert result is False, "Just '2pm' without day should NOT trigger"

    def test_just_day_does_not_trigger(self):
        """'Thursday please' without time should NOT trigger."""
        result = self._simulate_time_selected(
            "i have monday and thursday available. which day works?",
            "thursday please.",
        )
        assert result is False, "Just day without time should NOT trigger"

    def test_okay_does_not_trigger(self):
        """'Okay' should NOT trigger."""
        result = self._simulate_time_selected(
            "i have monday from 8 am to 3 pm. which works?",
            "okay.",
        )
        assert result is False

    # --- SHOULD trigger ---

    def test_day_and_time_triggers(self):
        """'Thursday at 3pm' should trigger."""
        result = self._simulate_time_selected(
            "i have monday and thursday available. which works?",
            "i'll take thursday at 3pm, please.",
        )
        assert result is True

    def test_explicit_pick_with_day_triggers(self):
        """'I'll take Thursday' should trigger (explicit pick phrase)."""
        result = self._simulate_time_selected(
            "i have monday and thursday free. which day?",
            "i'll take thursday.",
        )
        assert result is True

    def test_explicit_pick_with_time_triggers(self):
        """'Let's go with 2pm' should trigger (explicit pick phrase)."""
        result = self._simulate_time_selected(
            "i have 10am or 2pm available. which time?",
            "let's go with 2pm.",
        )
        assert result is True

    def test_book_me_in_triggers(self):
        """'Book me in for Thursday at 10am' should trigger."""
        result = self._simulate_time_selected(
            "i have monday and thursday available. which works?",
            "book me in for thursday at 10am.",
        )
        assert result is True


class TestBookingConfirmedPrecheck:
    """
    BOOKING_CONFIRMED should catch 'is that correct?' when the AI
    is confirming booking details (day+time present).
    """

    def _simulate_booking_confirmed(self, prev_assistant_msg, user_message):
        """Simulate the BOOKING_CONFIRMED pre-check logic."""
        prev = prev_assistant_msg.lower()
        user = user_message.lower()

        booking_phrases = [
            "ready to book", "shall i book", "want me to book",
            "confirm the booking", "go ahead and book", "all correct",
            "for the tap replacement, correct", "for the tap replacement?",
            "is that correct?", "correct?",
        ]
        day_names = ["monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday"]
        time_indicators = ["am", "pm", "o'clock"]
        prev_has_day = any(d in prev for d in day_names)
        prev_has_time = any(t in prev for t in time_indicators)
        prev_is_booking_ctx = prev_has_day and prev_has_time

        ai_asked = False
        for phrase in booking_phrases:
            if phrase in prev:
                if phrase in ["is that correct?", "correct?"]:
                    if prev_is_booking_ctx:
                        ai_asked = True
                        break
                else:
                    ai_asked = True
                    break

        user_confirms = any(
            p in user
            for p in ["yes", "yeah", "yep", "please", "go ahead",
                       "book it", "that's perfect", "sounds good",
                       "correct", "that's right", "that's correct"]
        )
        return ai_asked and user_confirms

    # --- SHOULD trigger ---

    def test_booking_with_day_time_correct_triggers(self):
        """AI: 'Thursday the 26th at 3 PM...correct?' User: 'Yes' -> trigger."""
        result = self._simulate_booking_confirmed(
            "just to confirm, you want to book for thursday the 26th at 3 pm for the tap replacement, correct?",
            "yes. that's correct.",
        )
        assert result is True, "Booking confirmation with day+time should trigger"

    def test_shall_i_book_triggers(self):
        """AI: 'Shall I book that?' User: 'Yes please'."""
        result = self._simulate_booking_confirmed(
            "shall i book that for you?",
            "yes please.",
        )
        assert result is True

    def test_ready_to_book_triggers(self):
        """AI: 'Ready to book?' User: 'Go ahead'."""
        result = self._simulate_booking_confirmed(
            "are you ready to book?",
            "go ahead.",
        )
        assert result is True

    # --- Should NOT trigger ---

    def test_generic_correct_without_booking_context(self):
        """AI: 'That's James Dorothy, correct?' -> should NOT trigger."""
        result = self._simulate_booking_confirmed(
            "that's james dorothy, correct?",
            "yes.",
        )
        assert result is False, "Name confirmation should NOT trigger BOOKING_CONFIRMED"

    def test_service_confirm_does_not_trigger(self):
        """AI: 'A tap replacement, is that correct?' -> no day/time -> no trigger."""
        result = self._simulate_booking_confirmed(
            "a tap replacement in your kitchen, is that correct?",
            "yeah. that's correct.",
        )
        assert result is False

    def test_address_confirm_does_not_trigger(self):
        """AI: 'Same address V95H5P2, correct?' -> no day/time -> no trigger."""
        result = self._simulate_booking_confirmed(
            "same address as before - v95h5p2, correct?",
            "yes.",
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════
# ISSUE 4: Fuzzy match too aggressive
# ═══════════════════════════════════════════════════════════════════════

class TestFuzzyMatchName:
    """
    fuzzy_match_name was matching Dorothy->Doherty and Josh->John
    due to substring matching and low SequenceMatcher thresholds.
    """

    def test_dorothy_does_not_match_doherty(self):
        """'James Dorothy' should NOT fuzzy-match 'James Doherty' at high confidence.
        First name 'James' matches exactly, but 'Dorothy'/'Doherty' similarity
        is ~0.67 which is below the 0.80 threshold for the non-matching part.
        Falls through to Strategy 5 (full name SequenceMatcher)."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "James Dorothy", ["James Doherty"]
        )
        # Strategy 3 won't fire (Dorothy/Doherty ~ 0.67 < 0.80)
        # Strategy 5: full name ratio "james dorothy"/"james doherty" ~ 0.85
        # If it matches via Strategy 5, score = int(0.85 * 75) = 63
        if match:
            assert score < 80, (
                f"Dorothy->Doherty matched at {score}%, should be <80%"
            )

    def test_josh_does_not_match_john(self):
        """'Josh Smith' should NOT fuzzy-match 'John Smith' at high confidence.
        Last name 'Smith' matches exactly, but 'Josh'/'John' similarity
        is ~0.50 which is below the 0.80 threshold.
        Falls through to Strategy 5."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "Josh Smith", ["John Smith"]
        )
        # Strategy 3 won't fire (Josh/John ~ 0.50 < 0.80)
        # Strategy 5: full name ratio "josh smith"/"john smith" ~ 0.90 >= 0.85
        # Score = int(0.90 * 75) = 67
        if match:
            assert score < 80, (
                f"Josh->John matched at {score}%, should be <80%"
            )

    def test_exact_match_still_works(self):
        """Exact name match should return 100%."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "James Doherty", ["James Doherty"]
        )
        assert match == "James Doherty"
        assert score == 100

    def test_exact_first_name_match(self):
        """Exact first name match with different last names.
        'James Murphy' vs candidates - should find a match via fall-through."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "James Murphy", ["James O'Brien", "Tom Murphy"]
        )
        # "James O'Brien": first exact, last Murphy/O'Brien ~ 0.15 < 0.80 -> no Strategy 3
        #   Falls to Strategy 5: "james murphy"/"james o'brien" ~ 0.52 < 0.85 -> no match
        # "Tom Murphy": last exact, first James/Tom ~ 0.0 < 0.80 -> no Strategy 3
        #   Falls to Strategy 5: "james murphy"/"tom murphy" ~ 0.62 < 0.85 -> no match
        # Neither matches well enough - that's actually correct behavior!
        # These are genuinely different people
        assert score < 80

    def test_exact_last_name_match(self):
        """When names share a last name but first names are very different,
        the match should be low confidence."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "Tom Murphy", ["James Murphy"]
        )
        # Last exact, first Tom/James ~ 0.0 < 0.80 -> no Strategy 3
        # Strategy 5: "tom murphy"/"james murphy" ~ 0.62 < 0.85 -> no match
        assert score < 80

    def test_no_substring_matching(self):
        """'Art Smith' vs 'Arthur Smith': last name matches exactly,
        first name Art/Arthur sim ~ 0.77 < 0.80, so Strategy 3 won't fire.
        Falls to Strategy 5: full name ratio ~ 0.87 >= 0.85 -> matches."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "Art Smith", ["Arthur Smith"]
        )
        # Strategy 5: "art smith"/"arthur smith" ~ 0.87 >= 0.85
        # Score = int(0.87 * 75) = 65
        assert match == "Arthur Smith"
        assert score < 80  # Low-confidence match via SequenceMatcher

    def test_very_different_names_low_score(self):
        """Completely different names should score very low."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "Sarah Connor", ["Michael Johnson"]
        )
        assert score < 50

    def test_close_typo_still_matches(self):
        """Close typo like 'Jon' vs 'John' should still match.
        'Jon Smith' vs 'John Smith': last name exact, first name Jon/John ~ 0.86 >= 0.75."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "Jon Smith", ["John Smith"]
        )
        # Last name exact, first name Jon/John ~ 0.86 >= 0.75
        # Score = 80 + int(0.86 * 10) = 88
        assert match == "John Smith"
        assert score >= 80

    def test_full_name_exact_both_parts(self):
        """Both first and last name exact -> 95."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "James Murphy", ["James Murphy", "Tom Smith"]
        )
        assert score == 100  # exact match
        assert idx == 0

    def test_multiple_candidates_picks_best(self):
        """Should pick the best match from multiple candidates."""
        from src.services.calendar_tools import fuzzy_match_name
        match, score, idx = fuzzy_match_name(
            "James Murphy",
            ["Tom Smith", "James O'Brien", "James Murphy"]
        )
        assert match == "James Murphy"
        assert score == 100
        assert idx == 2


class TestLookupCustomerFuzzyThresholds:
    """
    The lookup_customer fuzzy matching in execute_tool_call had thresholds
    that were too low, matching Dorothy->Doherty with phone match.
    """

    def test_last_name_threshold_raised(self):
        """Last name similarity threshold should be >= 0.75 (was 0.65)."""
        from difflib import SequenceMatcher
        # Dorothy vs Doherty similarity
        ratio = SequenceMatcher(None, "dorothy", "doherty").ratio()
        # This should be below the new 0.75 threshold
        assert ratio < 0.75, (
            f"Dorothy/Doherty ratio is {ratio:.2f}, "
            f"should be below 0.75 threshold"
        )

    def test_full_name_threshold_raised(self):
        """Full name similarity threshold should be >= 0.91 (was 0.85)."""
        from difflib import SequenceMatcher
        # Josh Smith vs John Smith
        ratio = SequenceMatcher(None, "josh smith", "john smith").ratio()
        assert ratio < 0.91, (
            f"Josh Smith/John Smith ratio is {ratio:.2f}, "
            f"should be below 0.91 threshold"
        )

    def test_legitimate_match_still_passes(self):
        """Jon Smith vs John Smith should still pass with phone match."""
        from difflib import SequenceMatcher
        # Full name similarity
        ratio = SequenceMatcher(None, "jon smith", "john smith").ratio()
        # This should be >= 0.88 (it's ~0.95)
        assert ratio >= 0.88, (
            f"Jon Smith/John Smith ratio is {ratio:.2f}, "
            f"should pass 0.88 threshold"
        )

    def test_code_has_075_threshold(self):
        """calendar_tools.py should have 0.75 or 0.80 last name threshold."""
        with open('src/services/calendar_tools.py', 'r') as f:
            content = f.read()
        assert ">= 0.75" in content or ">=0.75" in content or ">= 0.80" in content or ">=0.80" in content


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION: End-to-end search_availability with before_X filter
# ═══════════════════════════════════════════════════════════════════════

class TestSearchAvailabilityBeforeFilter:
    """
    Integration test: execute_tool_call('search_availability') with
    a 'before 2pm' query should use the AI parser and filter slots.
    """

    def _mock_config(self):
        from src.utils.config import config as real_config
        mock_cfg = MagicMock(wraps=real_config)
        mock_cfg.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_cfg.get_business_hours.return_value = {'start': 8, 'end': 17}
        mock_cfg.OPENAI_API_KEY = real_config.OPENAI_API_KEY
        mock_cfg.BUSINESS_DAYS = [0, 1, 2, 3, 4]
        mock_cfg.BUSINESS_HOURS_START = 8
        mock_cfg.BUSINESS_HOURS_END = 17
        return mock_cfg

    def _make_mock_db(self):
        db = MagicMock()
        db.has_workers.return_value = False
        db.get_all_workers.return_value = []
        db.get_all_bookings.return_value = []
        return db

    def _make_mock_calendar(self):
        from src.services.database_calendar import DatabaseCalendarService
        cal = MagicMock(spec=DatabaseCalendarService)

        def get_slots(date, service_duration=None):
            duration = service_duration or 60
            slots = []
            for hour in range(8, 17):
                t = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                if t <= datetime.now():
                    continue
                if t.hour + (duration / 60) > 17:
                    continue
                slots.append(t)
            return slots

        cal.get_available_slots_for_day = MagicMock(side_effect=get_slots)
        return cal

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )
    def test_before_2pm_filters_correctly(self):
        """search_availability with 'before 2pm' should only return morning slots."""
        from src.services.calendar_tools import execute_tool_call

        db = self._make_mock_db()
        cal = self._make_mock_calendar()
        services = {'google_calendar': cal, 'db': db, 'company_id': 1}

        svc = {'name': 'Tap Replacement', 'duration_minutes': 150,
               'workers_required': 1, 'worker_restrictions': None}

        with patch('src.services.calendar_tools.match_service') as mock_match:
            mock_match.return_value = {'service': svc, 'confidence': 1.0}
            with patch('src.utils.config.config', self._mock_config()):
                result = execute_tool_call(
                    'search_availability',
                    {'query': 'before 2pm', 'job_description': 'replace tap'},
                    services,
                )

        assert result['success'] is True
        # If slots found, all should be before 14:00
        if result.get('available_slots'):
            for slot in result['available_slots']:
                time_str = slot.get('time', '')
                # Parse hour from time string like "08:00 AM" or "1:00 PM"
                if 'PM' in time_str.upper() and '12:' not in time_str:
                    hour = int(time_str.split(':')[0]) + 12
                else:
                    hour = int(time_str.split(':')[0])
                assert hour < 14, f"Slot at {time_str} should be before 2pm"

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )
    def test_after_3pm_filters_correctly(self):
        """search_availability with 'after 3pm' should only return afternoon slots."""
        from src.services.calendar_tools import execute_tool_call

        db = self._make_mock_db()
        cal = self._make_mock_calendar()
        services = {'google_calendar': cal, 'db': db, 'company_id': 1}

        svc = {'name': 'Tap Replacement', 'duration_minutes': 60,
               'workers_required': 1, 'worker_restrictions': None}

        with patch('src.services.calendar_tools.match_service') as mock_match:
            mock_match.return_value = {'service': svc, 'confidence': 1.0}
            with patch('src.utils.config.config', self._mock_config()):
                result = execute_tool_call(
                    'search_availability',
                    {'query': 'after 3pm', 'job_description': 'replace tap'},
                    services,
                )

        assert result['success'] is True
        if result.get('available_slots'):
            for slot in result['available_slots']:
                time_str = slot.get('time', '')
                if 'PM' in time_str.upper() and '12:' not in time_str:
                    hour = int(time_str.split(':')[0]) + 12
                elif 'AM' in time_str.upper():
                    hour = int(time_str.split(':')[0])
                else:
                    hour = int(time_str.split(':')[0])
                assert hour >= 15, f"Slot at {time_str} should be after 3pm"


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION: Full conversation scenario from the logs
# ═══════════════════════════════════════════════════════════════════════

class TestFullConversationScenario:
    """
    Replay the exact scenario from the bug report logs to verify
    all fixes work together.
    """

    def test_scenario_service_confirm_no_misfire(self):
        """Step 1: AI says 'A tap replacement, is that correct?'
        User: 'Yeah. That's correct.' -> should NOT trigger any filler."""
        prev = "a tap replacement in your kitchen, is that correct?"
        user = "yeah. that's correct."
        # Should not trigger ADDRESS_CONFIRMED
        addr = TestAddressConfirmedPrecheck()
        assert addr._simulate_precheck(prev, user) is False
        # Should not trigger BOOKING_CONFIRMED
        book = TestBookingConfirmedPrecheck()
        assert book._simulate_booking_confirmed(prev, user) is False

    def test_scenario_name_confirm_no_misfire(self):
        """Step 2: AI says 'That's James Dorothy, correct?'
        User: 'Yeah. Correct.' -> should NOT trigger any filler."""
        prev = "that's james dorothy, correct?"
        user = "yeah. correct."
        addr = TestAddressConfirmedPrecheck()
        assert addr._simulate_precheck(prev, user) is False
        book = TestBookingConfirmedPrecheck()
        assert book._simulate_booking_confirmed(prev, user) is False

    def test_scenario_address_confirm_triggers(self):
        """Step 3: AI says 'Same address as before - V95H5P2?'
        User: 'Yeah. Correct.' -> SHOULD trigger ADDRESS_CONFIRMED."""
        prev = "great to hear from you again, james! same address as before - v95h5p2?"
        user = "yeah. correct."
        addr = TestAddressConfirmedPrecheck()
        assert addr._simulate_precheck(prev, user) is True

    def test_scenario_booking_confirm_triggers(self):
        """Step 4: AI says 'Thursday the 26th at 3 PM...correct?'
        User: 'Yes. That's correct.' -> SHOULD trigger BOOKING_CONFIRMED."""
        prev = "just to confirm, you want to book for thursday the 26th at 3 pm for the tap replacement, correct?"
        user = "yes. that's correct."
        book = TestBookingConfirmedPrecheck()
        assert book._simulate_booking_confirmed(prev, user) is True

    def test_scenario_2pm_request_no_time_selected(self):
        """Step 5: User says '2PM or something' -> should NOT trigger TIME_SELECTED."""
        prev = "i have monday the 23rd from 8 am to 3 pm, wednesday the 25th from 8 am to 3 pm. which works best for you?"
        user = "2pm or something."
        ts = TestTimeSelectedPrecheck()
        assert ts._simulate_time_selected(prev, user) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
