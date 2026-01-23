"""
Reset Google Calendar and sync all appointments from database

This script will:
1. Delete all existing appointments from Google Calendar
2. Create new calendar events for all appointments in the database
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import Database
from src.services.google_calendar import GoogleCalendarService
from datetime import datetime, timedelta

def clear_all_calendar_events(calendar):
    """Delete all events from Google Calendar"""
    print("\n🗑️  Clearing all events from Google Calendar...")
    
    # Get events from far past to far future to catch everything
    time_min = (datetime.now() - timedelta(days=365)).isoformat() + 'Z'
    time_max = (datetime.now() + timedelta(days=730)).isoformat() + 'Z'
    
    try:
        events = calendar.get_upcoming_appointments(days_ahead=730)
        
        # Also get past events
        if calendar.service:
            past_events_result = calendar.service.events().list(
                calendarId=calendar.calendar_id,
                timeMin=time_min,
                timeMax=datetime.now().isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            past_events = past_events_result.get('items', [])
            events.extend(past_events)
        
        if not events:
            print("✓ Calendar is already empty")
            return 0
        
        print(f"Found {len(events)} events to delete...")
        deleted = 0
        errors = 0
        
        for event in events:
            event_id = event.get('id')
            summary = event.get('summary', 'Untitled')
            
            try:
                if calendar.cancel_appointment(event_id):
                    deleted += 1
                    print(f"  ✓ Deleted: {summary}")
                else:
                    errors += 1
                    print(f"  ✗ Failed to delete: {summary}")
            except Exception as e:
                errors += 1
                print(f"  ✗ Error deleting {summary}: {str(e)}")
        
        print(f"\n✓ Deleted {deleted} events ({errors} errors)")
        return deleted
        
    except Exception as e:
        print(f"❌ Error clearing calendar: {str(e)}")
        return 0

def sync_database_to_calendar(db, calendar):
    """Create calendar events for all database appointments"""
    print("\n📅 Syncing database appointments to Google Calendar...")
    
    # Get all bookings from database
    bookings = db.get_all_bookings()
    
    if not bookings:
        print("No bookings found in database.")
        return 0
    
    print(f"Found {len(bookings)} appointments in database...")
    
    created = 0
    errors = 0
    
    for booking in bookings:
        booking_id = booking['id']
        client_name = booking['client_name']
        appointment_time = booking['appointment_time']
        phone = booking.get('phone_number')
        email = booking.get('email')
        
        try:
            # Parse appointment time
            appt_dt = datetime.fromisoformat(appointment_time)
            
            # Format description
            description_parts = [f"Client: {client_name}"]
            if phone:
                description_parts.append(f"Phone: {phone}")
            if email:
                description_parts.append(f"Email: {email}")
            
            description = "\n".join(description_parts)
            
            # Create event in Google Calendar
            print(f"\n  Creating: {client_name} - {appt_dt.strftime('%Y-%m-%d %H:%M')}")
            
            result = calendar.book_appointment(
                summary=f"Appointment - {client_name}",
                start_time=appt_dt,
                duration_minutes=60,
                description=description,
                phone_number=phone or ""
            )
            
            if result and 'id' in result:
                event_id = result['id']
                
                # Update database with new calendar event ID
                db.update_booking(
                    booking_id=booking_id,
                    calendar_event_id=event_id
                )
                
                print(f"  ✓ Created and linked: {event_id}")
                created += 1
            else:
                print(f"  ✗ Failed to create calendar event")
                errors += 1
                
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            errors += 1
    
    print(f"\n✓ Created {created} calendar events ({errors} errors)")
    return created

def main():
    """Main execution"""
    print("="*70)
    print("  RESET AND SYNC GOOGLE CALENDAR")
    print("="*70)
    print("\n⚠️  WARNING: This will DELETE ALL events from your Google Calendar")
    print("   and recreate them from the database.")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
        return
    
    # Initialize services
    print("\n📡 Initializing services...")
    db = Database()
    calendar = GoogleCalendarService()
    
    # Authenticate with Google
    print("🔐 Authenticating with Google Calendar...")
    calendar.authenticate()
    
    # Step 1: Clear all calendar events
    deleted_count = clear_all_calendar_events(calendar)
    
    # Step 2: Sync database to calendar
    created_count = sync_database_to_calendar(db, calendar)
    
    # Summary
    print("\n" + "="*70)
    print("  SYNC COMPLETE")
    print("="*70)
    print(f"  Deleted from calendar: {deleted_count} events")
    print(f"  Created from database: {created_count} events")
    print("="*70)
    
    if created_count > 0:
        print("\n✅ Successfully reset and synced your Google Calendar!")
        print("   Check your Google Calendar to see the appointments.")
    else:
        print("\n⚠️  No appointments were created. Check the output above for details.")

if __name__ == "__main__":
    main()
