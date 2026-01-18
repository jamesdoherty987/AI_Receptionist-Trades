"""
Pytest tests for datetime parser
"""
import pytest
from datetime import datetime, timedelta
from src.utils.date_parser import parse_datetime


class TestDateTimeParser:
    """Test suite for date/time parsing functionality"""
    
    def test_full_date_with_time(self):
        """Test parsing full date with time"""
        result = parse_datetime("December 25th at 12:00 PM")
        assert result.month == 12
        assert result.day == 25
        assert result.hour == 12
        assert result.minute == 0
    
    def test_date_without_ordinal(self):
        """Test parsing date without ordinal suffix"""
        result = parse_datetime("December 25 at 12 pm")
        assert result.month == 12
        assert result.day == 25
        assert result.hour == 12
    
    def test_relative_day_tomorrow(self):
        """Test parsing 'tomorrow' keyword"""
        result = parse_datetime("tomorrow at 2pm")
        tomorrow = datetime.now() + timedelta(days=1)
        assert result.date() >= tomorrow.date()
        assert result.hour == 14
    
    def test_next_weekday(self):
        """Test parsing 'next Monday' style"""
        result = parse_datetime("next Monday at 9am")
        assert result.hour == 9
        assert result.minute == 0
    
    def test_specific_weekday(self):
        """Test parsing specific weekday"""
        result = parse_datetime("Friday at 3:30pm")
        assert result.hour == 15
        assert result.minute == 30
    
    def test_time_only_12pm(self):
        """Test parsing time only - noon"""
        result = parse_datetime("12 pm")
        assert result.hour == 12
        assert result.minute == 0
    
    def test_time_only_with_colon(self):
        """Test parsing time with colon"""
        result = parse_datetime("12:00 pm")
        assert result.hour == 12
        assert result.minute == 0
    
    def test_time_only_1pm(self):
        """Test parsing 1pm converts to 13:00"""
        result = parse_datetime("1 pm")
        assert result.hour == 13
    
    def test_time_only_morning(self):
        """Test parsing morning time"""
        result = parse_datetime("11 am")
        assert result.hour == 11
    
    def test_hour_validity(self):
        """Test that all parsed hours are valid (0-23)"""
        test_cases = [
            "12 pm",
            "12:00 pm",
            "1 pm",
            "11 am",
            "9 am",
            "5 pm"
        ]
        for test in test_cases:
            result = parse_datetime(test)
            assert 0 <= result.hour <= 23, f"Invalid hour for '{test}': {result.hour}"
