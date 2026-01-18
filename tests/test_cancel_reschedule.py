"""
Test script for cancellation and rescheduling functionality
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.google_calendar import get_calendar_service
from src.utils.config import config

async def test_cancel_reschedule():
    """Test cancellation and rescheduling"""
    
    calendar = get_calendar_service()
    if not calendar:
        print("❌ Could not initialize Google Calendar")
        return
    
    print("\n" + "="*70)
    print("🧪 TESTING CANCELLATION AND RESCHEDULING")
    print("="*70 + "\n")
    
    # Step 1: Book a test appointment
    print("📝 Step 1: Booking a test appointment...")
    test_time = datetime.now() + timedelta(days=2)
    test_time = test_time.replace(hour=10, minute=0, second=0, microsecond=0)
    
    event = calendar.book_appointment(
        summary="Test Appointment - John Doe",
        start_time=test_time,
        duration_minutes=60,
        description="Test booking for cancellation/reschedule testing"
    )
    
    if not event:
        print("❌ Failed to book test appointment")
        return
    
    event_id = event.get('id')
    print(f"✅ Test appointment booked!")
    print(f"   ID: {event_id}")
    print(f"   Time: {test_time.strftime('%B %d at %I:%M %p')}")
    
    # Step 2: Test finding the appointment
    print(f"\n📝 Step 2: Finding appointment by name...")
    found_event = calendar.find_appointment_by_details(patient_name="John Doe")
    
    if found_event:
        print(f"✅ Found appointment: {found_event.get('summary')}")
    else:
        print("❌ Could not find appointment by name")
        return
    
    # Step 3: Test rescheduling
    print(f"\n📝 Step 3: Rescheduling appointment...")
    new_time = test_time + timedelta(days=1)
    new_time = new_time.replace(hour=14, minute=0)
    
    rescheduled = calendar.reschedule_appointment(event_id, new_time)
    
    if rescheduled:
        print(f"✅ Successfully rescheduled!")
        print(f"   Old time: {test_time.strftime('%B %d at %I:%M %p')}")
        print(f"   New time: {new_time.strftime('%B %d at %I:%M %p')}")
    else:
        print("❌ Failed to reschedule")
        return
    
    # Step 4: Test finding by new time
    print(f"\n📝 Step 4: Finding appointment by new time...")
    found_by_time = calendar.find_appointment_by_details(
        patient_name="John Doe", 
        appointment_time=new_time
    )
    
    if found_by_time:
        print(f"✅ Found appointment at new time")
    else:
        print("❌ Could not find appointment at new time")
    
    # Step 5: Test cancellation
    print(f"\n📝 Step 5: Cancelling appointment...")
    cancelled = calendar.cancel_appointment(event_id)
    
    if cancelled:
        print(f"✅ Successfully cancelled!")
    else:
        print("❌ Failed to cancel")
        return
    
    # Step 6: Verify cancellation
    print(f"\n📝 Step 6: Verifying appointment is gone...")
    still_there = calendar.find_appointment_by_details(patient_name="John Doe")
    
    if not still_there:
        print(f"✅ Appointment successfully removed from calendar")
    else:
        print("⚠️ Appointment still exists (may be marked as cancelled)")
    
    print("\n" + "="*70)
    print("🎉 ALL TESTS COMPLETED!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_cancel_reschedule())
