"""
Test what happens when checking availability for Jan 15-21, 2026
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.calendar_tools import execute_tool_call

def test_availability_check():
    """Test the exact scenario from the logs"""
    print("\n" + "="*70)
    print("🧪 TEST: check_availability for Jan 15-21, 2026")
    print("="*70 + "\n")
    
    # Create mock services
    from src.services.google_calendar import GoogleCalendarService
    from src.services.database import Database
    
    services = {
        'google_calendar': GoogleCalendarService(),
        'db': Database()
    }
    
    # Authenticate calendar
    services['google_calendar'].authenticate()
    
    # Call the tool with the same parameters from the logs
    result = execute_tool_call(
        tool_name='check_availability',
        arguments={
            'start_date': '2026-01-15',
            'end_date': '2026-01-21'
        },
        services=services
    )
    
    print("\n" + "="*70)
    print("📊 RESULT:")
    print("="*70)
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")
    print(f"Total slots: {result.get('total_count', 0)}")
    print(f"\nAvailable slots returned:")
    for slot in result.get('available_slots', []):
        print(f"  • {slot['date']} at {slot['time']}")
    
if __name__ == "__main__":
    test_availability_check()
