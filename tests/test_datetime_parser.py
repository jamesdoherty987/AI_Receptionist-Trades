"""
Test the datetime parser with various inputs
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime

test_cases = [
    "December 25th at 12:00 PM",
    "December 25 at 12 pm",
    "tomorrow at 2pm",
    "next Monday at 9am",
    "Friday at 3:30pm",
    "12 pm",
    "12:00 pm",
    "1 pm",
    "11 am",
]

print("="*60)
print("DATETIME PARSER TESTS")
print("="*60 + "\n")

for test in test_cases:
    try:
        result = parse_datetime(test)
        print(f"[PASS] '{test}'")
        print(f"   -> {result.strftime('%Y-%m-%d %H:%M:%S')} ({result.strftime('%A, %B %d at %I:%M %p')})")
        print(f"   -> Hour: {result.hour} (valid: {0 <= result.hour <= 23})")
        print()
    except Exception as e:
        print(f"[FAIL] '{test}'")
        print(f"   -> Error: {e}")
        print()

print("="*60)
