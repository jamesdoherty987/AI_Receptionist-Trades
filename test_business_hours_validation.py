"""
Test that business hours validation works correctly
Ensures appointments outside business hours are rejected, not silently modified
"""

from datetime import datetime, timedelta
from src.utils.date_parser import parse_datetime
from src.services.calendar_tools import execute_tool_call
from src.utils.config import Config

def test_parse_datetime_no_silent_adjustment():
    """Test that parse_datetime doesn't silently adjust times anymore"""
    
    # Test 3pm (15:00) - should parse correctly (not adjust)
    result = parse_datetime("tomorrow at 3pm")
    print(f"\n✅ Testing 'tomorrow at 3pm':")
    print(f"   Parsed to: {result}")
    print(f"   Hour: {result.hour if result else 'None'}")
    
    # The hour should be 15, not adjusted to 9
    assert result is not None, "Should parse successfully"
    assert result.hour == 15, f"Expected hour 15, got {result.hour}"
    
    # Test 8am (before business hours) - should parse correctly (not adjust)
    result = parse_datetime("tomorrow at 8am")
    print(f"\n✅ Testing 'tomorrow at 8am':")
    print(f"   Parsed to: {result}")
    print(f"   Hour: {result.hour if result else 'None'}")
    
    assert result is not None, "Should parse successfully"
    assert result.hour == 8, f"Expected hour 8, got {result.hour}"
    
    print("\n✅ All parse_datetime tests passed - no silent adjustment!")

def test_book_job_validation():
    """Test that book_job rejects times outside business hours"""
    
    # Mock services
    class MockGoogleCalendar:
        def check_availability(self, time, duration_minutes):
            return True  # Pretend slot is available
    
    class MockDB:
        pass
    
    services = {
        'google_calendar': MockGoogleCalendar(),
        'db': MockDB()
    }
    
    # Get business hours
    hours = Config.get_business_hours()
    print(f"\n📅 Business hours: {hours['start']}:00 - {hours['end']}:00")
    
    # Test booking at 3pm (outside 9-14 hours)
    print(f"\n✅ Testing book_job with 'tomorrow at 3pm' (outside business hours):")
    result = execute_tool_call(
        "book_job",
        {
            "customer_name": "Test User",
            "phone": "1234567890",
            "email": "test@example.com",
            "job_address": "123 Test St",
            "job_description": "Test job",
            "appointment_datetime": "tomorrow at 3pm",
            "urgency_level": "scheduled"
        },
        services
    )
    
    print(f"   Result: {result}")
    
    # Should fail with error about business hours
    assert result['success'] == False, "Should reject time outside business hours"
    assert 'outside business hours' in result['error'].lower(), f"Error should mention business hours: {result['error']}"
    
    print("\n✅ Correctly rejected 3pm booking (outside 9-14 hours)")
    
    # Test booking at 10am (within 9-14 hours) - should work
    print(f"\n✅ Testing book_job with 'tomorrow at 10am' (within business hours):")
    result2 = execute_tool_call(
        "book_job",
        {
            "customer_name": "Test User",
            "phone": "1234567890",
            "email": "test@example.com",
            "job_address": "123 Test St",
            "job_description": "Test job",
            "appointment_datetime": "tomorrow at 10am",
            "urgency_level": "scheduled"
        },
        services
    )
    
    print(f"   Result success: {result2.get('success')}")
    
    # This should pass business hours check (might fail on calendar booking but that's OK)
    if not result2['success']:
        # If it failed, should NOT be due to business hours
        assert 'outside business hours' not in result2.get('error', '').lower(), \
            f"10am should be within business hours, got error: {result2.get('error')}"
        print(f"   ⚠️ Failed for different reason (expected): {result2.get('error', 'Unknown')}")
    else:
        print(f"   ✅ Passed business hours validation")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Business Hours Validation Fix")
    print("=" * 60)
    
    test_parse_datetime_no_silent_adjustment()
    test_book_job_validation()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Fix is working correctly!")
    print("=" * 60)
