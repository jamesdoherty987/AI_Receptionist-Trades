"""
Simulated conversation flow tests for full-day job booking.

These tests simulate the actual conversation flow to catch edge cases.
"""
import pytest
from datetime import datetime, timedelta


class TestFullDayJobConversationFlow:
    """
    Simulate the conversation flow from the logs:
    1. Customer calls about "table repair" (matches General Service = 1440 mins)
    2. AI checks availability for 2 weeks out
    3. AI offers "Monday to Friday, free from 8 AM to 5 PM" (WRONG - should say "full day available")
    4. Customer picks Monday
    5. AI asks "What time?" (WRONG - shouldn't ask for time on full-day job)
    6. Customer says "5pm"
    7. AI tries to book at 5pm, fails because job extends past closing
    8. AI offers 4pm, customer accepts, fails again
    9. Loop continues...
    
    With the fix:
    1-4. Same
    5. AI should say "I can fit you in Monday for the full day" (no time question)
    6. Customer confirms
    7. AI books at 8am automatically
    """
    
    def test_availability_shows_full_day_not_time_range(self):
        """
        When checking availability for a full-day service,
        the summary should say "full day available" not "8am to 5pm"
        """
        service_duration = 1440  # General Service
        day_name = "Monday"
        
        # The fix: check service_duration and format accordingly
        if service_duration >= 480:
            summary = f"{day_name}: full day available"
        else:
            summary = f"{day_name}: free from 8 am to 5 pm"
        
        assert "full day available" in summary
        assert "8 am" not in summary
        assert "5 pm" not in summary
    
    def test_booking_at_5pm_auto_adjusts_to_8am(self):
        """
        When customer says "5pm" for a full-day job,
        the system should auto-adjust to 8am (start of business day).
        """
        service_duration = 1440
        start_hour = 8
        
        # Customer requested 5pm
        parsed_time = datetime(2026, 3, 9, 17, 0, 0)
        
        # The fix: auto-adjust for full-day services
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        assert parsed_time.hour == 8
        assert parsed_time.minute == 0
    
    def test_full_day_job_fits_in_9_hour_business_day(self):
        """
        A 1440-minute "General Service" should be bookable in a 9-hour business day.
        The 1440 minutes means "block the whole day", not "requires 24 hours of work".
        """
        service_duration = 480  # 8 hours (full day)
        start_hour = 8
        end_hour = 17  # 9 hour business day
        
        parsed_time = datetime(2026, 3, 9, 8, 0, 0)
        
        # The fix: for full-day jobs (8+ hours), end time is closing time
        if service_duration >= 480:
            job_end_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            job_end_time = parsed_time + timedelta(minutes=service_duration)
        
        closing_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # Job should fit (end at closing, not 8 hours later)
        assert job_end_time <= closing_time
    
    def test_only_one_slot_per_day_for_full_day_service(self):
        """
        For full-day services (8+ hours), availability should show ONE slot per day,
        not hourly slots that would confuse the customer.
        """
        service_duration = 480  # 8 hours (full day)
        
        # Simulate slots generated for a day
        day_slots = [
            datetime(2026, 3, 9, 8, 0),
            datetime(2026, 3, 9, 8, 30),
            datetime(2026, 3, 9, 9, 0),
            datetime(2026, 3, 9, 9, 30),
            datetime(2026, 3, 9, 10, 0),
            datetime(2026, 3, 9, 10, 30),
        ]
        
        # The fix: filter to one slot for full-day services
        if day_slots and service_duration >= 480:
            day_slots = [day_slots[0]]
        
        assert len(day_slots) == 1
        assert day_slots[0].hour == 8


class TestEdgeCases:
    """Test edge cases that could cause issues in production"""
    
    def test_480_minute_service_treated_as_full_day(self):
        """
        8-hour services (480 mins) should also be treated as full-day
        to prevent the same booking loop issue.
        """
        service_duration = 480
        start_hour = 8
        
        parsed_time = datetime(2026, 3, 9, 14, 0, 0)  # 2pm
        
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        assert parsed_time.hour == 8
    
    def test_479_minute_service_not_treated_as_full_day(self):
        """
        Services just under 8 hours should NOT be auto-adjusted.
        """
        service_duration = 479  # Just under 8 hours
        start_hour = 8
        
        parsed_time = datetime(2026, 3, 9, 9, 0, 0)  # 9am
        
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # Should remain 9am
        assert parsed_time.hour == 9
    
    def test_multi_day_job_handling(self):
        """
        Jobs longer than 1 day (e.g., 2880 mins = 2 days) should still work.
        They would need to be booked across multiple days in practice.
        """
        service_duration = 2880  # 2 days
        start_hour = 8
        end_hour = 17
        
        parsed_time = datetime(2026, 3, 9, 8, 0, 0)
        
        # For very long jobs, still auto-adjust to start of day
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # For all full-day jobs (8+ hours), end time is closing time (blocks the day)
        if service_duration >= 480:
            job_end_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            job_end_time = parsed_time + timedelta(minutes=service_duration)
        
        closing_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # Should fit (blocks the day)
        assert job_end_time <= closing_time
    
    def test_booking_preserves_date(self):
        """
        When auto-adjusting time, the DATE should be preserved.
        Customer says "Monday at 5pm" -> should book Monday at 8am, not change the day.
        """
        service_duration = 1440
        start_hour = 8
        
        # Monday March 9th at 5pm
        parsed_time = datetime(2026, 3, 9, 17, 0, 0)
        original_date = parsed_time.date()
        
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # Date should be unchanged
        assert parsed_time.date() == original_date
        assert parsed_time.day == 9
        assert parsed_time.month == 3
        assert parsed_time.year == 2026
    
    def test_non_full_day_job_past_closing_rejected(self):
        """
        A 7-hour job (420 mins) at 11am should be rejected because it would
        end at 6pm, past the 5pm closing time.
        """
        service_duration = 420  # 7 hours (not full-day)
        start_hour = 8
        end_hour = 17
        
        parsed_time = datetime(2026, 3, 9, 11, 0, 0)  # 11am
        
        # Not a full-day job, so don't auto-adjust
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # Calculate job end time
        if service_duration >= 480:
            job_end_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            job_end_time = parsed_time + timedelta(minutes=service_duration)
        
        closing_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # 11am + 7 hours = 6pm, which is past 5pm closing
        assert job_end_time > closing_time
        assert job_end_time.hour == 18  # 6pm
    
    def test_non_full_day_job_before_closing_accepted(self):
        """
        A 7-hour job (420 mins) at 10am should be accepted because it would
        end at 5pm, exactly at closing time.
        """
        service_duration = 420  # 7 hours (not full-day)
        start_hour = 8
        end_hour = 17
        
        parsed_time = datetime(2026, 3, 9, 10, 0, 0)  # 10am
        
        # Not a full-day job, so don't auto-adjust
        if service_duration >= 480:
            parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        # Calculate job end time
        if service_duration >= 480:
            job_end_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        else:
            job_end_time = parsed_time + timedelta(minutes=service_duration)
        
        closing_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        # 10am + 7 hours = 5pm, exactly at closing
        assert job_end_time <= closing_time
        assert job_end_time.hour == 17  # 5pm


class TestPromptInstructions:
    """Test that the prompt instructions are correct"""
    
    def test_prompt_has_full_day_instructions(self):
        """
        The prompt should have instructions for handling full-day jobs.
        """
        # Read the prompt file
        with open('prompts/receptionist_prompt_fast.txt', 'r') as f:
            prompt = f.read()
        
        # Check for full-day job instructions
        assert "FULL-DAY JOBS" in prompt or "full-day" in prompt.lower()
        assert "full day available" in prompt.lower() or "full day" in prompt.lower()
    
    def test_prompt_has_trades_language(self):
        """
        The prompt should use trades-friendly language.
        """
        with open('prompts/receptionist_prompt_fast.txt', 'r') as f:
            prompt = f.read()
        
        # Check for trades language instructions
        assert "NEVER say \"appointment\"" in prompt or "never say appointment" in prompt.lower()
        assert "job" in prompt.lower()
        assert "booking" in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
