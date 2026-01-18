"""
Test business hours and improved availability checking
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime
from src.services.google_calendar import GoogleCalendarService
from src.utils.config import config

print("="*80)
print("TESTING BUSINESS HOURS & AVAILABILITY")
print("="*80 + "\n")

print(f"[1] BUSINESS HOURS CONFIGURATION")
print(f"   Start: {config.BUSINESS_HOURS_START}:00 (9 AM)")
print(f"   End: {config.BUSINESS_HOURS_END}:00 (5 PM)")
print()

print(f"[2] DATETIME PARSING WITH BUSINESS HOURS")
test_cases = [
    "December 26 at 8am",  # Before business hours
    "December 26 at 9am",  # Opening time
    "December 26 at 5pm",  # At closing (should be rejected)
    "December 26 at 6pm",  # After business hours
    "December 26 at 2pm",  # During business hours
]

for test in test_cases:
    parsed = parse_datetime(test)
    print(f"   '{test}'")
    print(f"   -> {parsed.strftime('%B %d at %I:%M %p')} (Hour: {parsed.hour})")
    in_hours = config.BUSINESS_HOURS_START <= parsed.hour < config.BUSINESS_HOURS_END
    print(f"   -> Within business hours: {in_hours}")
    print()

print(f"[3] AVAILABILITY CHECK - December 26 at Different Times")
calendar = GoogleCalendarService()
calendar.authenticate()

# Test different times on Dec 26
test_times = [
    parse_datetime("December 26 at 9am"),
    parse_datetime("December 26 at 10am"),
    parse_datetime("December 26 at 2pm"),
    parse_datetime("December 26 at 5pm"),
]

for test_time in test_times:
    print(f"\n   Checking: {test_time.strftime('%B %d at %I:%M %p')}")
    is_available = calendar.check_availability(test_time, duration_minutes=60)
    print(f"   -> Available: {'[YES]' if is_available else '[NO - BUSY]'}")

print("\n" + "="*60)
print("TESTING COMPLETE")
print("="*60)
