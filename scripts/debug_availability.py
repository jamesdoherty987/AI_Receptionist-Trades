"""
Debug script to check what's blocking Monday-Wednesday availability
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.google_calendar import GoogleCalendarService
from src.utils.config import config

def check_availability_debug():
    """Check availability for Monday-Wednesday (Jan 19-21, 2026)"""
    calendar = GoogleCalendarService()
    calendar.authenticate()
    
    print("\n" + "="*70)
    print("🔍 DEBUG: Checking Monday-Wednesday Availability (Jan 19-21, 2026)")
    print("="*70)
    
    # Check each day
    dates_to_check = [
        datetime(2026, 1, 19),  # Monday
        datetime(2026, 1, 20),  # Tuesday
        datetime(2026, 1, 21),  # Wednesday
    ]
    
    for date in dates_to_check:
        day_name = date.strftime('%A, %B %d')
        print(f"\n📅 {day_name}")
        print(f"   Weekday index: {date.weekday()} (0=Mon, 4=Fri, 5=Sat, 6=Sun)")
        print(f"   Is weekend? {date.weekday() >= 5}")
        print(f"   Business hours: {config.BUSINESS_HOURS_START}:00 - {config.BUSINESS_HOURS_END}:00")
        print()
        
        # Get all slots for the day
        slots = calendar.get_available_slots_for_day(date)
        
        if slots:
            print(f"   ✅ Found {len(slots)} available slots:")
            for slot in slots:
                print(f"      • {slot.strftime('%I:%M %p')}")
        else:
            print(f"   ❌ NO available slots found")
            print(f"   🔍 Checking why...")
            
            # Manual check for each hour
            for hour in range(config.BUSINESS_HOURS_START, config.BUSINESS_HOURS_END):
                slot_time = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                is_available = calendar.check_availability(slot_time, duration_minutes=config.APPOINTMENT_SLOT_DURATION)
                
                if not is_available:
                    print(f"      ❌ {slot_time.strftime('%I:%M %p')} - BUSY")
                else:
                    print(f"      ✅ {slot_time.strftime('%I:%M %p')} - Available (but not returned?)")
        
        # Get all events for that day
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        time_min = day_start.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        time_max = day_end.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        
        events_result = calendar.service.events().list(
            calendarId=calendar.calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if events:
            print(f"\n   📌 Events blocking this day:")
            for event in events:
                start_str = event.get('start', {}).get('dateTime', 'Unknown')
                end_str = event.get('end', {}).get('dateTime', 'Unknown')
                summary = event.get('summary', 'Untitled')
                print(f"      • {summary}")
                print(f"        {start_str} → {end_str}")
        else:
            print(f"\n   ✅ No events found for this day")

if __name__ == "__main__":
    check_availability_debug()
