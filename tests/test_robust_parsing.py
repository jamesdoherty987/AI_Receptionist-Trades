"""
Test various ways users might say dates and times
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime

test_cases = [
    # Time variations
    "12 pm",
    "12pm",
    "12:00 pm",
    "twelve pm",
    "noon",
    "12 in the afternoon",
    
    # Date + Time variations
    "December 25th at 12:00 PM",
    "December 25 at 12 pm",
    "Dec 25th at noon",
    "25th of December at 12pm",
    "the 25th of December at twelve pm",
    
    # Relative dates
    "tomorrow at 2pm",
    "tomorrow afternoon",
    "next Monday at 9am",
    "Friday at 3:30pm",
    "Monday morning",
    
    # Other formats
    "2 o'clock pm",
    "3:30 in the afternoon",
    "9 a.m.",
    "6 p.m.",
]

print("="*80)
print("ROBUST DATETIME PARSER TESTS")
print("="*80 + "\n")

for i, test in enumerate(test_cases, 1):
    try:
        result = parse_datetime(test)
        print(f"✅ Test {i:2d}: '{test}'")
        print(f"           → {result.strftime('%A, %B %d, %Y at %I:%M %p')}")
    except Exception as e:
        print(f"❌ Test {i:2d}: '{test}'")
        print(f"           → ERROR: {e}")
    print()

print("="*80)
