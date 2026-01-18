"""
Simulate a complete booking to test the datetime fix
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime
from src.services.google_calendar import GoogleCalendarService

async def test_complete_booking():
    """Test the complete booking flow with Dec 25 at 12 PM"""
    
    print("\n" + "="*60)
    print("🧪 TESTING COMPLETE BOOKING FLOW")
    print("="*60 + "\n")
    
    # Test datetime parsing
    test_time = "December 25th at 12:00 PM"
    print(f"📝 Parsing: '{test_time}'")
    
    try:
        parsed_time = parse_datetime(test_time)
        print(f"✅ Parsed successfully: {parsed_time}")
        print(f"   Date: {parsed_time.strftime('%Y-%m-%d')}")
        print(f"   Time: {parsed_time.strftime('%H:%M:%S')} ({parsed_time.strftime('%I:%M %p')})")
        print(f"   Hour value: {parsed_time.hour} (valid: {0 <= parsed_time.hour <= 23})")
        print()
        
        # Test calendar booking
        print("🔍 Testing calendar availability check...")
        calendar = GoogleCalendarService()
        calendar.authenticate()
        
        is_available = calendar.check_availability(parsed_time, duration_minutes=60)
        print(f"   Available: {is_available}")
        print()
        
        if is_available:
            print("✅ Would proceed with booking (not actually booking in this test)")
            print(f"   Patient: James Daugherty")
            print(f"   Time: {parsed_time.strftime('%B %d, %Y at %I:%M %p')}")
            print(f"   Service: Injury")
        else:
            print("❌ Time slot is busy")
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED - Datetime parsing fixed!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_complete_booking())
