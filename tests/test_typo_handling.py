"""
Test date parser with typos and separate date/time inputs
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime
from datetime import datetime


def test_typo_handling():
    """Test that common typos in month names are handled correctly"""
    print("\n" + "="*60)
    print("Testing Typo Handling")
    print("="*60)
    
    test_cases = [
        ("janary 5th 1pm", "January typo"),
        ("febuary 15th 2pm", "February typo"),
        ("decmber 25th 3pm", "December typo"),
        ("janurary 10th at 10am", "January extra letters"),
    ]
    
    for test_input, description in test_cases:
        print(f"\nTest: {description}")
        print(f"Input: '{test_input}'")
        try:
            result = parse_datetime(test_input)
            if result:
                print(f"✅ Success: {result.strftime('%B %d, %Y at %I:%M %p')}")
            else:
                print(f"❌ Failed: returned None")
        except Exception as e:
            print(f"❌ Error: {e}")


def test_date_only():
    """Test that date-only input returns None (prompting for time)"""
    print("\n" + "="*60)
    print("Testing Date-Only Input (should return None)")
    print("="*60)
    
    test_cases = [
        "january 5th",
        "5th january",
        "jan 5",
        "tomorrow",
        "next friday"
    ]
    
    for test_input in test_cases:
        print(f"\nInput: '{test_input}'")
        result = parse_datetime(test_input)
        if result is None:
            print(f"✅ Correctly returned None (will prompt for time)")
        else:
            print(f"⚠️ Warning: returned {result.strftime('%B %d, %Y at %I:%M %p')}")


def test_time_patterns():
    """Test various time input formats"""
    print("\n" + "="*60)
    print("Testing Time Formats")
    print("="*60)
    
    test_cases = [
        ("january 5th 1pm", "date with 1pm"),
        ("january 5th 1 pm", "date with 1 pm (space)"),
        ("january 5th at 1pm", "date with 'at' prefix"),
        ("january 5th 13:00", "date with 24-hour time - should fail to match"),
        ("january 5th 1:30pm", "date with minutes"),
    ]
    
    for test_input, description in test_cases:
        print(f"\nTest: {description}")
        print(f"Input: '{test_input}'")
        try:
            result = parse_datetime(test_input)
            if result:
                print(f"✅ Result: {result.strftime('%B %d, %Y at %I:%M %p')}")
            else:
                print(f"❌ Failed: returned None")
        except Exception as e:
            print(f"❌ Error: {e}")


def test_combined_parsing():
    """Test scenario where user provides date first, then time"""
    print("\n" + "="*60)
    print("Testing Combined Date+Time Scenario")
    print("="*60)
    
    # Simulate user saying "janary 5th" first
    date_input = "janary 5th"
    print(f"\nUser says: '{date_input}'")
    result1 = parse_datetime(date_input)
    print(f"Parser returns: {result1}")
    
    # Then user says "1pm"
    # In real system, this would be combined: "janary 5th 1pm"
    combined_input = f"{date_input} 1pm"
    print(f"\nCombined with time: '{combined_input}'")
    result2 = parse_datetime(combined_input)
    if result2:
        print(f"✅ Success: {result2.strftime('%B %d, %Y at %I:%M %p')}")
    else:
        print(f"❌ Failed: returned None")


if __name__ == "__main__":
    test_typo_handling()
    test_date_only()
    test_time_patterns()
    test_combined_parsing()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
