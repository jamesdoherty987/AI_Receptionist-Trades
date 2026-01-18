"""
Comprehensive test of date parsing fixes
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime

def test_date_parsing():
    """Test various date parsing scenarios"""
    print("\n" + "="*70)
    print("🧪 COMPREHENSIVE DATE PARSING TESTS")
    print("="*70 + "\n")
    
    tests = [
        ("2026-01-15", False, (9, 0), True, "Date range start (today)"),
        ("2026-01-21", False, (17, 0), True, "Date range end"),
        ("2026-01-22", False, (9, 0), False, "Future appointment (next week)"),
        ("Thursday at 9 AM", True, None, False, "Relative day with time"),
        ("next Monday at 2pm", True, None, False, "Next week appointment"),
    ]
    
    for text, require_time, default_time, allow_past, description in tests:
        print(f"📝 Test: {description}")
        print(f"   Input: '{text}'")
        print(f"   Parameters: require_time={require_time}, default_time={default_time}, allow_past={allow_past}")
        
        result = parse_datetime(text, require_time=require_time, default_time=default_time, allow_past=allow_past)
        
        if result:
            print(f"   ✅ Result: {result.strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"   ❌ Result: None")
        print()

if __name__ == "__main__":
    test_date_parsing()
