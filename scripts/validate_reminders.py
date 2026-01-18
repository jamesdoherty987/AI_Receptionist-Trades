"""
Validate reminder system configuration
Checks if email or SMS is properly configured
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import config

def validate_config():
    """Validate reminder configuration"""
    print("="*60)
    print("🔍 VALIDATING REMINDER CONFIGURATION")
    print("="*60)
    
    reminder_method = config.REMINDER_METHOD.lower()
    print(f"\n📋 Reminder Method: {reminder_method.upper()}")
    
    if reminder_method == "email":
        print("\n✅ Using EMAIL reminders (recommended for Ireland)")
        print("\nChecking email configuration...")
        
        required_email = {
            "SMTP_SERVER": config.SMTP_SERVER,
            "SMTP_USER": config.SMTP_USER,
            "SMTP_PASSWORD": config.SMTP_PASSWORD,
            "FROM_EMAIL": config.FROM_EMAIL
        }
        
        missing = []
        for key, value in required_email.items():
            if value:
                print(f"  ✅ {key}: {value if key != 'SMTP_PASSWORD' else '***hidden***'}")
            else:
                print(f"  ❌ {key}: NOT SET")
                missing.append(key)
        
        if missing:
            print(f"\n❌ MISSING: {', '.join(missing)}")
            print("\nAdd these to your .env file:")
            print("SMTP_SERVER=smtp.gmail.com")
            print("SMTP_USER=your_email@gmail.com")
            print("SMTP_PASSWORD=your_app_password")
            print("FROM_EMAIL=your_email@gmail.com")
            return False
        else:
            print("\n✅ EMAIL configuration complete!")
            return True
    
    elif reminder_method == "sms":
        print("\n⚠️  Using SMS reminders")
        print("Note: SMS may not work with Irish Twilio numbers")
        print("\nChecking Twilio SMS configuration...")
        
        required_sms = {
            "TWILIO_ACCOUNT_SID": config.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": config.TWILIO_AUTH_TOKEN,
            "TWILIO_PHONE_NUMBER": config.TWILIO_PHONE_NUMBER
        }
        
        missing = []
        for key, value in required_sms.items():
            if value:
                print(f"  ✅ {key}: {value if key != 'TWILIO_AUTH_TOKEN' else '***hidden***'}")
            else:
                print(f"  ❌ {key}: NOT SET")
                missing.append(key)
        
        if missing:
            print(f"\n❌ MISSING: {', '.join(missing)}")
            print("\nAdd these to your .env file:")
            print("TWILIO_ACCOUNT_SID=your_account_sid")
            print("TWILIO_AUTH_TOKEN=your_auth_token")
            print("TWILIO_PHONE_NUMBER=+1234567890")
            return False
        else:
            print("\n⚠️  SMS configuration found")
            print("Make sure your Twilio number supports SMS!")
            return True
    
    else:
        print(f"\n❌ Unknown reminder method: {reminder_method}")
        print("Set REMINDER_METHOD=email or REMINDER_METHOD=sms in .env")
        return False

def main():
    print("\n")
    success = validate_config()
    
    if success:
        print("\n" + "="*60)
        print("✅ CONFIGURATION VALID")
        print("="*60)
        print("\nYou can now:")
        print("1. Run: python scripts/check_reminders.py")
        print("2. Set up a scheduled task to run it periodically")
        print("\n")
        return 0
    else:
        print("\n" + "="*60)
        print("❌ CONFIGURATION INCOMPLETE")
        print("="*60)
        print("\nFix the issues above and run this script again.")
        print("\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
