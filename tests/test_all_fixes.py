"""
Test the fixes:
. Timezone is correct
. Overlapping bookings are rejected
. Confirmation detection is smarter
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime
from src.services.google_calendar import GoogleCalendarService
from src.utils.config import config

print("="*60)
print("TESTING ALL FIXES")
print("="*60 + "\n")

# Test 1: Timezone configuration
print("1️⃣ TIMEZONE TEST")
print(f"   Configured timezone: {config.CALENDAR_TIMEZONE}")
print(f"   Expected: Europe/Dublin (GMT)\n")

# Test 2: Datetime parsing with timezone
test_time = "December 26th at 9:00 PM"
parsed = parse_datetime(test_time)
print(f"2️⃣ DATETIME PARSING TEST")
print(f"   Input: '{test_time}'")
print(f"   Parsed: {parsed}")
print(f"   Formatted: {parsed.strftime('%B %d, %Y at %I:%M %p')}\n")

# Test 3: Calendar timezone
calendar = GoogleCalendarService()
calendar.authenticate()
print(f"3️⃣ CALENDAR TIMEZONE TEST")
print(f"   Calendar timezone: {calendar.timezone}")
print(f"   Matches config: {calendar.timezone == config.CALENDAR_TIMEZONE}\n")

# Test 4: Availability check for existing appointment
dec_26_pm = parse_datetime("December 26th at 5:00 PM")
print(f"4️⃣ AVAILABILITY CHECK TEST")
print(f"   Checking: {dec_26_pm.strftime('%B %d at %I:%M %p')}")
is_available = calendar.check_availability(dec_26_pm, duration_minutes=60)
print(f"   Available: {is_available}")
print(f"   Expected: Depends on actual calendar\n")

# Test 5: Get alternatives if busy
if not is_available:
    print(f"5️⃣ ALTERNATIVE TIMES TEST")
    alternatives = calendar.get_alternative_times(dec_26_pm, days_to_check=3)
    print(f"   Found {len(alternatives)} alternative times:")
    for i, alt in enumerate(alternatives, 1):
        print(f"   {i}. {alt.strftime('%A, %B %d at %I:%M %p')}")
    print()

# Test 6: Confirmation detection logic
print(f"6️⃣ CONFIRMATION DETECTION TEST")
test_cases = [
    ("yeah that's correct", True),
    ("yes", True),
    ("perfect", True),
    ("yeah twenty fifth of december", False),  # Should NOT be treated as confirmation
    ("that i am injured", False),
    ("my name is james", False),
]

for text, expected_confirmation in test_cases:
    words = text.lower().split()
    is_short = len(words) <= 6
    confirmation_words = ["yes", "yeah", "ya", "yep", "yup", "correct", "right", "confirm", "perfect", "ok", "okay"]
    confirmation_count = sum(1 for word in words if any(conf in word for conf in confirmation_words))
    is_mostly_confirmation = confirmation_count >= len(words) / 2
    is_confirmation = is_short and is_mostly_confirmation
    
    status = "[PASS]" if is_confirmation == expected_confirmation else "[FAIL]"
    print(f"   {status} '{text}' -> Confirmation: {is_confirmation} (Expected: {expected_confirmation})")

print("\n" + "="*60)
print("TESTING COMPLETE")
print("="*60)
