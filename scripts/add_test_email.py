"""
Add test email to an appointment for testing reminders
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.google_calendar import GoogleCalendarService

def add_email_to_appointment():
    """Add test email to an upcoming appointment"""
    calendar = GoogleCalendarService()
    
    print("🔍 Finding upcoming appointments...")
    upcoming = calendar.get_upcoming_appointments(days_ahead=3)
    
    if not upcoming:
        print("❌ No upcoming appointments found")
        return
    
    print(f"\n📅 Found {len(upcoming)} appointments:")
    for i, event in enumerate(upcoming, 1):
        summary = event.get('summary', 'No title')
        start = event.get('start', {})
        start_time = start.get('dateTime', start.get('date', 'Unknown'))
        print(f"{i}. {summary} - {start_time}")
    
    # Get the first appointment
    event = upcoming[0]
    event_id = event.get('id')
    summary = event.get('summary', '')
    description = event.get('description', '')
    
    print(f"\n✏️ Adding email to: {summary}")
    
    # Add email to description
    test_email = "jkdoherty123@gmail.com"
    
    if "Email:" not in description:
        if description:
            new_description = f"Email: {test_email}\n\n{description}"
        else:
            new_description = f"Email: {test_email}"
        
        # Update the event
        try:
            updated_event = calendar.service.events().patch(
                calendarId=calendar.calendar_id,
                eventId=event_id,
                body={'description': new_description}
            ).execute()
            
            print(f"✅ Added email {test_email} to appointment")
            print(f"📝 Event ID: {event_id}")
            print(f"\nNow run: python scripts/check_reminders.py")
            
        except Exception as e:
            print(f"❌ Error updating event: {e}")
    else:
        print("⚠️ Email already exists in description")

if __name__ == "__main__":
    add_email_to_appointment()
