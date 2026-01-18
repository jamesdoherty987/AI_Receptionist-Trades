"""
Quick test to verify the new availability response format
"""
from datetime import datetime, timedelta
from src.services.calendar_tools import execute_tool_call
from src.services.google_calendar import get_calendar_service
from src.services.database import Database

def test_check_availability():
    """Test the updated check_availability function"""
    print("Testing availability checker...")
    
    # Setup services
    calendar = get_calendar_service()
    db = Database()
    services = {
        'google_calendar': calendar,
        'db': db
    }
    
    # Test 1: Check next week
    print("\n" + "="*60)
    print("TEST 1: What's available next week?")
    print("="*60)
    
    today = datetime.now()
    next_week_start = today + timedelta(days=7)
    next_week_end = next_week_start + timedelta(days=4)  # Mon-Fri
    
    result = execute_tool_call(
        "check_availability",
        {
            "start_date": next_week_start.strftime("%Y-%m-%d"),
            "end_date": next_week_end.strftime("%Y-%m-%d")
        },
        services
    )
    
    print("\n📊 RESULT:")
    print(f"Success: {result.get('success')}")
    print(f"Total slots: {result.get('total_count')}")
    print(f"\n💬 Natural Summary:")
    print(f"   {result.get('natural_summary', 'N/A')}")
    print(f"\n📝 Message to LLM:")
    print(f"   {result.get('message', 'N/A')}")
    print(f"\n🎤 Voice Instruction:")
    print(f"   {result.get('voice_instruction', 'N/A')}")
    
    # Test 2: Check specific day (Tuesday)
    print("\n" + "="*60)
    print("TEST 2: What's available on Tuesday?")
    print("="*60)
    
    # Find next Tuesday
    days_until_tuesday = (1 - today.weekday()) % 7  # Tuesday is weekday 1
    if days_until_tuesday == 0:
        days_until_tuesday = 7  # If today is Tuesday, get next Tuesday
    tuesday = today + timedelta(days=days_until_tuesday)
    
    result2 = execute_tool_call(
        "check_availability",
        {
            "start_date": tuesday.strftime("%Y-%m-%d"),
            "end_date": tuesday.strftime("%Y-%m-%d")
        },
        services
    )
    
    print("\n📊 RESULT:")
    print(f"Success: {result2.get('success')}")
    print(f"Total slots: {result2.get('total_count')}")
    print(f"\n💬 Natural Summary:")
    print(f"   {result2.get('natural_summary', 'N/A')}")
    print(f"\n📝 Message to LLM:")
    print(f"   {result2.get('message', 'N/A')}")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    test_check_availability()
