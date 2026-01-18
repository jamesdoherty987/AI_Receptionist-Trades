"""
Simple test script to send a test email
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.email_reminder import get_email_service

def send_test_email():
    """Send a test appointment reminder email"""
    print("📧 Sending test email...")
    
    email_service = get_email_service()
    
    # Test email details
    test_email = "jkdoherty123@gmail.com"
    tomorrow = datetime.now() + timedelta(days=1)
    
    success = email_service.send_reminder(
        to_email=test_email,
        appointment_time=tomorrow,
        patient_name="Test Patient",
        service_type="Physio",
        phone_number="+353851234567"
    )
    
    if success:
        print(f"\n✅ TEST EMAIL SENT!")
        print(f"📧 Check your inbox: {test_email}")
    else:
        print(f"\n❌ Failed to send test email")
        print("Check your SMTP settings in .env file")

if __name__ == "__main__":
    send_test_email()
