"""
Actually book an appointment to test the complete flow
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime
from src.services.google_calendar import GoogleCalendarService

async def book_test_appointment():
    """Actually book James Daugherty's appointment"""
    
    print("\n" + "="*60)
    print("📅 BOOKING TEST APPOINTMENT")
    print("="*60 + "\n")
    
    # Parse the datetime
    time_text = "December 25th at 12:00 PM"
    print(f"📝 Parsing: '{time_text}'")
    
    try:
        requested_time = parse_datetime(time_text)
        print(f"✅ Parsed: {requested_time.strftime('%B %d, %Y at %I:%M %p')}")
        print()
        
        # Connect to calendar
        calendar = GoogleCalendarService()
        calendar.authenticate()
        
        # Check availability
        print("🔍 Checking availability...")
        is_available = calendar.check_availability(requested_time, duration_minutes=60)
        
        if not is_available:
            print("❌ Time slot is BUSY - cannot book")
            return
        
        print("✅ Time slot is AVAILABLE")
        print()
        
        # Book the appointment
        print("📝 Booking appointment...")
        event = calendar.book_appointment(
            summary="Injury - James Daugherty",
            start_time=requested_time,
            duration_minutes=60,
            description="Test booking via script\nPatient: James Daugherty\nReason: Injury\nBooked for testing purposes"
        )
        
        if event:
            print(f"\n{'='*60}")
            print(f"✅ APPOINTMENT BOOKED SUCCESSFULLY!")
            print(f"{'='*60}")
            print(f"👤 Patient: James Daugherty")
            print(f"📅 Date/Time: {requested_time.strftime('%B %d, %Y at %I:%M %p')}")
            print(f"🏥 Service: Injury")
            print(f"🆔 Event ID: {event.get('id')}")
            print(f"🔗 Link: {event.get('htmlLink')}")
            print(f"{'='*60}\n")
            
            print("✅ Run 'python check_calendar.py' to verify the booking!")
        else:
            print("❌ Failed to book appointment")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(book_test_appointment())
