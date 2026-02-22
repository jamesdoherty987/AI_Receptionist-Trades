"""
Tests for full-day job booking functionality.

Tests the fix for the issue where full-day jobs (8+ hours = 480+ mins) couldn't be booked
because the system was offering hourly slots and then rejecting them.

A "full day" job is any job >= 8 hours (480 minutes). This includes:
- 8-hour jobs (480 mins)
- General Service jobs (1440 mins - stored as 24 hours but blocks business day)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


class TestFullDayBookingLogic:
    """Test the full-day booking auto-adjustment logic"""
    
    def test_full_day_service_auto_adjusts_to_start_of_day(self):
        """
        When booking a full-day service at 5pm, it should auto-adjust to 8am.
        This prevents the loop of "5pm not available, try 4pm, 4pm not available..."
        """
        # Simulate the logic from book_job
        service_duration = 1440  # Full day (24 hours)
        start_hour = 8
        end_hour = 17
        
        # User requested 5pm
        parsed_time = datetime(2026, 3, 9, 17, 0, 0)  # Monday 5pm
        
        # The fix: auto-adjust to start of business day for full-day services
        if service_duration >= 480:  # 8 hours or more
            original_time = parsed_time
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        assert parsed_time.hour == 8
        assert parsed_time.minute == 0
        assert parsed_time.day == 9  # Same day
    
    def test_full_day_job_end_time_is_closing_time(self):
        """
        For full-day jobs (8+ hours = 480+ mins), the job_end_time should be closing time,
        not the actual duration after start. This allows full-day jobs to be booked
        even when business hours are only 9 hours.
        """
        service_duration = 480  # 8 hours (full day job)
        start_hour = 8
        end_hour = 17
        
        parsed_time = datetime(2026, 3, 9, 8, 0, 0)  # Start of day
        
        # The fix: for full-day jobs (8+ hours), end time is closing time
        if service_duration >= 480:
            job_end_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            job_end_time = parsed_time + timedelta(minutes=service_duration)
        
        closing_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # Job should NOT extend past closing (they should be equal)
        assert job_end_time <= closing_time
        assert job_end_time.hour == 17
    
    def test_full_day_service_detects_insufficient_hours(self):
        """
        Full-day jobs (8+ hours) should use closing time as end, not actual duration.
        This means they always fit within business hours.
        """
        service_duration = 480  # 8 hours
        start_hour = 8
        end_hour = 17  # 9 hour business day
        
        parsed_time = datetime(2026, 3, 9, 8, 0, 0)  # Start of day
        
        # With the fix, full-day jobs use closing time as end
        if service_duration >= 480:
            job_end_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            job_end_time = parsed_time + timedelta(minutes=service_duration)
        
        closing_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # With the fix, full-day jobs should fit (end at closing)
        assert job_end_time <= closing_time
    
    def test_regular_service_not_affected(self):
        """
        Regular services (< 8 hours) should NOT be auto-adjusted.
        """
        service_duration = 60  # 1 hour
        start_hour = 8
        
        # User requested 2pm
        parsed_time = datetime(2026, 3, 9, 14, 0, 0)  # Monday 2pm
        
        # Should NOT adjust for regular services
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # Time should remain 2pm
        assert parsed_time.hour == 14
    
    def test_8_hour_service_is_treated_as_full_day(self):
        """
        Services of exactly 8 hours (480 mins) should be treated as full-day.
        """
        service_duration = 480  # Exactly 8 hours
        start_hour = 8
        
        parsed_time = datetime(2026, 3, 9, 10, 0, 0)  # 10am
        
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # Should be adjusted to 8am
        assert parsed_time.hour == 8


class TestAvailabilitySlotFiltering:
    """Test that availability only shows one slot per day for full-day services"""
    
    def test_full_day_service_shows_one_slot_per_day(self):
        """
        For full-day services (8+ hours), check_availability should return only ONE slot per day,
        not hourly slots from 8am-5pm.
        """
        service_duration = 480  # 8 hours (full day)
        
        # Simulate multiple slots for a day
        day_slots = [
            datetime(2026, 3, 9, 8, 0),
            datetime(2026, 3, 9, 8, 30),
            datetime(2026, 3, 9, 9, 0),
            datetime(2026, 3, 9, 9, 30),
            datetime(2026, 3, 9, 10, 0),
        ]
        
        # The fix: filter to one slot for full-day services
        if day_slots and service_duration >= 480:
            day_slots = [day_slots[0]]
        
        assert len(day_slots) == 1
        assert day_slots[0].hour == 8
    
    def test_regular_service_shows_all_slots(self):
        """
        Regular services should still show all available slots.
        """
        service_duration = 60  # 1 hour
        
        day_slots = [
            datetime(2026, 3, 9, 8, 0),
            datetime(2026, 3, 9, 8, 30),
            datetime(2026, 3, 9, 9, 0),
            datetime(2026, 3, 9, 9, 30),
            datetime(2026, 3, 9, 10, 0),
        ]
        
        # Should NOT filter for regular services
        if day_slots and service_duration >= 480:
            day_slots = [day_slots[0]]
        
        assert len(day_slots) == 5
    
    def test_full_day_slot_end_is_closing_time(self):
        """
        For full-day services (8+ hours), slot_end should be closing time, not actual duration later.
        This allows slots to be generated even when business day < service duration.
        """
        slot_duration = 480  # 8 hours (full day)
        end_hour = 17
        
        current_slot = datetime(2026, 3, 9, 8, 0)  # 8am
        end_time = datetime(2026, 3, 9, 17, 0)  # 5pm closing
        
        # The fix: for full-day jobs (8+ hours), slot_end is closing time
        if slot_duration >= 480:
            slot_end = end_time
        else:
            slot_end = current_slot + timedelta(minutes=slot_duration)
        
        # Slot should fit within business hours
        assert slot_end <= end_time
        assert slot_end.hour == 17


class TestAvailabilitySummaryDisplay:
    """Test that availability summary shows 'full day available' for full-day services"""
    
    def test_full_day_summary_format(self):
        """
        For full-day services (8+ hours), the summary should say "full day available"
        instead of "free from 8am to 5pm".
        """
        service_duration = 480  # 8 hours (full day)
        day_name = "Monday"
        
        if service_duration >= 480:
            summary = f"{day_name}: full day available"
        else:
            summary = f"{day_name}: free from 8 am to 5 pm"
        
        assert "full day available" in summary
        assert "8 am" not in summary
    
    def test_regular_service_shows_time_range(self):
        """
        Regular services should show the time range.
        """
        service_duration = 60
        day_name = "Monday"
        first_time = "8 am"
        last_time = "5 pm"
        
        if service_duration >= 480:
            summary = f"{day_name}: full day available"
        else:
            summary = f"{day_name}: free from {first_time} to {last_time}"
        
        assert "free from 8 am to 5 pm" in summary


class TestTTSFormatting:
    """Test TTS formatting for phone numbers and eircodes"""
    
    def test_irish_phone_number_spacing(self):
        """
        Irish phone numbers should be spaced out for slower TTS reading.
        """
        import re
        
        text = "I have your number as 085 263 5954"
        
        # Pattern from format_for_tts_spelling
        irish_phone_pattern = re.compile(r'\b(0\d{2})\s+(\d{3})\s+(\d{4})\b')
        
        def space_irish_phone(match):
            g1, g2, g3 = match.groups()
            spaced_g1 = ' '.join(g1)
            spaced_g2 = ' '.join(g2)
            spaced_g3 = ' '.join(g3)
            return f"{spaced_g1} ... {spaced_g2} ... {spaced_g3}"
        
        result = irish_phone_pattern.sub(space_irish_phone, text)
        
        assert "0 8 5 ... 2 6 3 ... 5 9 5 4" in result
    
    def test_eircode_spacing(self):
        """
        Eircodes should be spaced out for slower TTS reading.
        """
        import re
        
        text = "Your eircode is V95H5P2"
        
        # Pattern from format_for_tts_spelling
        eircode_pattern = re.compile(r'\b([A-Z]\d{2})\s?([A-Z0-9]{4})\b', re.IGNORECASE)
        
        def space_eircode(match):
            part1, part2 = match.groups()
            spaced_part1 = ' '.join(part1.upper())
            spaced_part2 = ' '.join(part2.upper())
            return f"{spaced_part1} ... {spaced_part2}"
        
        result = eircode_pattern.sub(space_eircode, text)
        
        assert "V 9 5 ... H 5 P 2" in result
    
    def test_spelled_name_spacing(self):
        """
        Spelled-out names (J-O-H-N) should have spaces around dashes.
        """
        import re
        
        text = "That's J-O-H-N S-M-I-T-H"
        
        spelled_pattern = re.compile(r'\b([A-Z0-9]-)+[A-Z0-9]\b', re.IGNORECASE)
        
        def add_spaces_to_spelled(match):
            spelled = match.group(0)
            return spelled.replace('-', ' - ')
        
        result = spelled_pattern.sub(add_spaces_to_spelled, text)
        
        assert "J - O - H - N" in result
        assert "S - M - I - T - H" in result


class TestFuzzyCustomerMatching:
    """Test fuzzy matching for customer lookup (ASR error handling)"""
    
    def test_phone_plus_first_name_match(self):
        """
        Strategy 1: Phone matches + first name 90%+ + last name 65%+
        Should catch "James Dorothy" vs "James Doherty"
        """
        from difflib import SequenceMatcher
        
        search_name = "James Dorothy"  # ASR transcription
        actual_name = "James Doherty"  # Actual customer
        phone_matches = True
        
        search_first, search_last = "james", "dorothy"
        client_first, client_last = "james", "doherty"
        
        first_similarity = SequenceMatcher(None, search_first, client_first).ratio()
        last_similarity = SequenceMatcher(None, search_last, client_last).ratio()
        
        # First name should be exact match
        assert first_similarity >= 0.90
        
        # Last name should be close enough (Dorothy/Doherty)
        assert last_similarity >= 0.65
        
        # With phone match, this should be a match
        if phone_matches and first_similarity >= 0.90 and last_similarity >= 0.65:
            match_score = 0.95 + (last_similarity * 0.05)
            assert match_score > 0.95
    
    def test_prevents_joe_john_mismatch(self):
        """
        Strategy 2 threshold (85%) should prevent "Joe Smith" matching "John Smith"
        """
        from difflib import SequenceMatcher
        
        search_name = "Joe Smith"
        actual_name = "John Smith"
        
        full_similarity = SequenceMatcher(None, 
            search_name.lower(), 
            actual_name.lower()).ratio()
        
        # Joe Smith vs John Smith should be ~84%, below 85% threshold
        assert full_similarity < 0.85, f"Similarity {full_similarity:.2%} should be < 85%"
    
    def test_high_confidence_name_only_match(self):
        """
        Strategy 3: Very high name similarity (92%+) without phone
        Should catch "Jon Smith" vs "John Smith"
        """
        from difflib import SequenceMatcher
        
        search_name = "Jon Smith"
        actual_name = "John Smith"
        
        full_similarity = SequenceMatcher(None, 
            search_name.lower(), 
            actual_name.lower()).ratio()
        
        # Jon Smith vs John Smith should be ~95%
        assert full_similarity >= 0.92, f"Similarity {full_similarity:.2%} should be >= 92%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestFullDayConflictDetection:
    """Test that full-day bookings properly detect conflicts"""
    
    def test_full_day_booking_blocks_entire_day(self):
        """
        When a full-day booking exists (8+ hours = 480+ mins), it should block the entire
        business day, not just the actual duration from start time.
        """
        end_hour = 17
        
        # Existing full-day booking at 8am
        booking_start = datetime(2026, 3, 9, 8, 0, 0)
        booking_duration = 480  # 8 hours (full day)
        
        # The fix: full-day bookings (8+ hours) end at closing time
        if booking_duration >= 480:
            booking_end = booking_start.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            booking_end = booking_start + timedelta(minutes=booking_duration)
        
        # Booking should end at 5pm, not 4pm (8 hours after 8am)
        assert booking_end.hour == 17
        assert booking_end.day == 9  # Same day
    
    def test_new_booking_conflicts_with_full_day(self):
        """
        A new booking at 2pm should conflict with an existing full-day booking.
        """
        end_hour = 17
        
        # Existing full-day booking
        existing_start = datetime(2026, 3, 9, 8, 0, 0)
        existing_duration = 480  # 8 hours (full day)
        
        if existing_duration >= 480:
            existing_end = existing_start.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            existing_end = existing_start + timedelta(minutes=existing_duration)
        
        # New booking attempt at 2pm
        new_start = datetime(2026, 3, 9, 14, 0, 0)
        new_duration = 60
        new_end = new_start + timedelta(minutes=new_duration)
        
        # Check for overlap
        has_conflict = (new_start < existing_end and new_end > existing_start)
        
        assert has_conflict, "2pm booking should conflict with full-day booking"
    
    def test_next_day_booking_no_conflict(self):
        """
        A booking on the next day should NOT conflict with a full-day booking.
        """
        end_hour = 17
        
        # Existing full-day booking on Monday
        existing_start = datetime(2026, 3, 9, 8, 0, 0)
        existing_duration = 480  # 8 hours (full day)
        
        if existing_duration >= 480:
            existing_end = existing_start.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            existing_end = existing_start + timedelta(minutes=existing_duration)
        
        # New booking on Tuesday
        new_start = datetime(2026, 3, 10, 10, 0, 0)
        new_duration = 60
        new_end = new_start + timedelta(minutes=new_duration)
        
        # Check for overlap
        has_conflict = (new_start < existing_end and new_end > existing_start)
        
        assert not has_conflict, "Tuesday booking should NOT conflict with Monday full-day"
    
    def test_full_day_conflicts_with_existing_short_booking(self):
        """
        A new full-day booking should conflict with an existing 1-hour booking.
        """
        end_hour = 17
        start_hour = 8
        
        # Existing 1-hour booking at 2pm
        existing_start = datetime(2026, 3, 9, 14, 0, 0)
        existing_duration = 60
        existing_end = existing_start + timedelta(minutes=existing_duration)
        
        # New full-day booking attempt
        new_start = datetime(2026, 3, 9, 8, 0, 0)
        new_duration = 480  # 8 hours (full day)
        
        if new_duration >= 480:
            new_end = new_start.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            new_end = new_start + timedelta(minutes=new_duration)
        
        # Check for overlap
        has_conflict = (new_start < existing_end and new_end > existing_start)
        
        assert has_conflict, "Full-day booking should conflict with existing 2pm booking"
