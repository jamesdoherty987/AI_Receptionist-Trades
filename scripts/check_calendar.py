"""
Quick script to check if the appointment was actually booked to Google Calendar
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.google_calendar import GoogleCalendarService

def check_recent_appointments():
    """Check for recent appointments in Google Calendar"""
    try:
        calendar = GoogleCalendarService()
        calendar.authenticate()
        
        # Get appointments for the next 7 days
        appointments = calendar.get_upcoming_appointments(days_ahead=7)
        
        print(f"\n{'='*60}")
        print(f"📅 CALENDAR CHECK - Found {len(appointments)} upcoming appointments")
        print(f"{'='*60}\n")
        
        if not appointments:
            print("❌ NO appointments found in calendar")
            print("   The booking did NOT complete successfully.")
            return False
        
        # Look for the James Daugherty appointment on Dec 25
        found_james = False
        for apt in appointments:
            summary = apt.get('summary', '')
            start = apt.get('start', {}).get('dateTime', '')
            
            if start:
                # Parse the start time
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    formatted_time = start_dt.strftime('%B %d, %Y at %I:%M %p')
                except:
                    formatted_time = start
            else:
                formatted_time = "Unknown time"
            
            print(f"📌 {summary}")
            print(f"   ⏰ {formatted_time}")
            print(f"   🔗 {apt.get('htmlLink', 'No link')}")
            print()
            
            # Check if this is the James Daugherty appointment
            if 'daugherty' in summary.lower() or 'james' in summary.lower():
                found_james = True
        
        if found_james:
            print("✅ FOUND: James Daugherty's appointment is BOOKED!")
            return True
        else:
            print("❌ James Daugherty's appointment was NOT found in calendar")
            return False
            
    except FileNotFoundError as e:
        print(f"❌ Calendar credentials not found: {e}")
        print("   Run setup_calendar.py first to authenticate")
        return False
    except Exception as e:
        print(f"❌ Error checking calendar: {e}")
        return False

if __name__ == "__main__":
    check_recent_appointments()
