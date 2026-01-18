"""Test the next week expansion"""
from datetime import datetime
from src.services.calendar_tools import execute_tool_call
from src.services.google_calendar import get_calendar_service
from src.services.database import Database

def test_next_week():
    print("Testing 'next week' expansion...")
    
    calendar = get_calendar_service()
    db = Database()
    services = {
        'google_calendar': calendar,
        'db': db
    }
    
    print("\n" + "="*60)
    print("TEST: User asks 'what do you have next week?'")
    print("="*60)
    
    result = execute_tool_call(
        "check_availability",
        {
            "start_date": "next week",
            "end_date": "next week"
        },
        services
    )
    
    print("\n📊 RESULT:")
    print(f"Success: {result.get('success')}")
    print(f"Total slots: {result.get('total_count')}")
    print(f"\n💬 Natural Summary:")
    print(f"   {result.get('natural_summary', 'N/A')}")
    print(f"\n📝 Message:")
    print(f"   {result.get('message', 'N/A')}")

if __name__ == "__main__":
    test_next_week()
