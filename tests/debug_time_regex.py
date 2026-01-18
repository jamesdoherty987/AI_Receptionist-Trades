"""
Debug the time parsing
"""
import re

test_strings = [
    "December 25th at 12:00 PM",
    "December 25 at 12 pm",
    "at 12 pm",
    "12 pm",
]

pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'

for test in test_strings:
    matches = re.findall(pattern, test.lower())
    print(f"'{test}'")
    print(f"  Matches: {matches}")
    print()
