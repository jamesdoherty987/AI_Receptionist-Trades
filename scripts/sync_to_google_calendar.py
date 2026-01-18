"""
Sync local database bookings to Google Calendar

This script creates real Google Calendar events for bookings that only exist
in the local database (i.e., test bookings with fake event IDs).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import Database
from src.services.google_calendar import GoogleCalendarService
from datetime import datetime
import json

def sync_bookings_to_calendar():
    """Sync all local bookings to Google Calendar"""
    
    # Initialize services
    print("Initializing services...")
    db = Database()
    calendar = GoogleCalendarService()
    
    # Get all bookings
    print("Fetching bookings from database...")
    bookings = db.get_all_bookings()
    
    if not bookings:
        print("No bookings found in database.")
        return
    
    print(f"\nFound {len(bookings)} bookings in database.")
    
    # Track statistics
    created = 0
    updated = 0
    errors = 0
    skipped = 0
    
    for booking in bookings:
        booking_id = booking['id']
        client_name = booking['client_name']
        appointment_time = booking['appointment_time']
        phone = booking.get('phone_number')
        email = booking.get('email')
        calendar_event_id = booking.get('calendar_event_id')
        
        # Skip if already has real calendar event (not test_event_*)
        if calendar_event_id and not calendar_event_id.startswith('test_event_'):
            print(f"✓ Skipping {client_name} - already has real calendar event")
            skipped += 1
            continue
        
        try:
            # Parse appointment time
            appt_dt = datetime.fromisoformat(appointment_time)
            
            # Create event in Google Calendar
            print(f"\nCreating calendar event for {client_name}...")
            print(f"  Time: {appt_dt.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Phone: {phone or 'N/A'}")
            print(f"  Email: {email or 'N/A'}")
            
            result = calendar.book_appointment(
                summary=f"Appointment - {client_name}",
                start_time=appt_dt,
                duration_minutes=60,
                description=f"Client: {client_name}\nEmail: {email or 'N/A'}",
                phone_number=phone or ""
            )
            
            if result and 'id' in result:
                event_id = result['id']
                # Update database with real event ID
                success = db.update_booking(
                    booking_id=booking_id,
                    calendar_event_id=event_id
                )
                
                if success:
                    print(f"✓ Created calendar event: {event_id}")
                    created += 1
                else:
                    print(f"✗ Failed to update database with event ID")
                    errors += 1
            else:
                print(f"✗ Failed to create calendar event")
                errors += 1
                
        except Exception as e:
            print(f"✗ Error processing booking {booking_id}: {str(e)}")
            errors += 1
    
    # Print summary
    print("\n" + "="*50)
    print("SYNC COMPLETE")
    print("="*50)
    print(f"Created: {created}")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print("="*50)
    
    if created > 0:
        print(f"\n✓ Successfully synced {created} bookings to Google Calendar!")
        print("Check your Google Calendar to see the new events.")
    elif skipped > 0 and errors == 0:
        print("\n✓ All bookings already synced to Google Calendar.")
    elif errors > 0:
        print(f"\n⚠ Completed with {errors} errors. Check the output above for details.")

if __name__ == "__main__":
    print("="*50)
    print("Google Calendar Sync Tool")
    print("="*50)
    print("\nThis script will create Google Calendar events for all")
    print("database bookings that don't have real calendar events yet.")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
        sync_bookings_to_calendar()
    except KeyboardInterrupt:
        print("\n\nSync cancelled by user.")
