"""
Google Calendar Setup Helper
Run this to test your Google Calendar integration
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.google_calendar import get_calendar_service


def main():
    print("=" * 60)
    print("Google Calendar Setup Helper")
    print("=" * 60)
    
    # Check if Google libraries are available
    try:
        calendar = get_calendar_service()
        
        if not calendar:
            print("\n❌ Google Calendar libraries not installed")
            print("\nTo install:")
            print("  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return
        
        print("\n✅ Google Calendar authenticated successfully!")
        
        # Test: Get upcoming appointments
        print("\n📅 Fetching upcoming appointments...")
        appointments = calendar.get_upcoming_appointments(days_ahead=7)
        
        if appointments:
            print(f"\nFound {len(appointments)} upcoming appointments:")
            for apt in appointments:
                start = apt['start'].get('dateTime', apt['start'].get('date'))
                print(f"  • {apt['summary']} - {start}")
        else:
            print("\nNo upcoming appointments found.")
        
        # Test booking (optional)
        print("\n" + "=" * 60)
        response = input("Would you like to test booking an appointment? (y/n): ")
        
        if response.lower() == 'y':
            tomorrow = datetime.now() + timedelta(days=1)
            tomorrow_2pm = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
            
            event = calendar.book_appointment(
                summary="Test Appointment (AI Receptionist)",
                start_time=tomorrow_2pm,
                duration_minutes=30,
                description="This is a test appointment created by the AI Receptionist setup helper."
            )
            
            if event:
                print(f"\n✅ Test appointment booked!")
                print(f"   Link: {event.get('htmlLink')}")
                print(f"\n   (You can delete this test appointment from Google Calendar)")
            else:
                print("\n❌ Failed to book test appointment")
        
        print("\n" + "=" * 60)
        print("✅ Setup complete! Your Google Calendar is ready.")
        print("=" * 60)
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("\nSetup Instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Enable Google Calendar API")
        print("3. Create OAuth credentials (Desktop app)")
        print("4. Download credentials.json")
        print("5. Move it to: config/credentials.json")
        print("\nSee SETUP_GUIDE.md for detailed instructions.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nSee SETUP_GUIDE.md for troubleshooting.")


if __name__ == "__main__":
    main()
