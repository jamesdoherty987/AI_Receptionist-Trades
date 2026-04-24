"""
Live SMS test — sends real confirmation SMS to 0852635954 via Twilio.
Simulates both a new customer and a returning customer booking.
Run manually: python tests/live_sms_test.py
"""
import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.services.sms_reminder import SMSReminderService

TEST_PHONE = "0852635954"

def main():
    sms = SMSReminderService()

    if not sms.client:
        print("ERROR: Twilio not configured. Check TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SMS_NUMBER in .env")
        sys.exit(1)

    print(f"Twilio configured: from={sms.from_number}")
    print(f"Sending to: {TEST_PHONE}")
    print()

    # --- Test 1: New customer booking confirmation ---
    print("=== Test 1: New Customer Booking Confirmation ===")
    appt_time_1 = datetime.now() + timedelta(days=3)
    appt_time_1 = appt_time_1.replace(hour=10, minute=0, second=0, microsecond=0)

    result1 = sms.send_booking_confirmation(
        to_number=TEST_PHONE,
        appointment_time=appt_time_1,
        customer_name="New Customer Test",
        service_type="Plumbing Repair",
        company_name="JP Enterprises",
        employee_names=None,
        address="123 Test Street, Dublin",
    )
    print(f"Result: {'SENT' if result1 else 'FAILED'}")
    print()

    # --- Test 2: Returning customer booking confirmation (with employees) ---
    print("=== Test 2: Returning Customer Booking Confirmation ===")
    appt_time_2 = datetime.now() + timedelta(days=5)
    appt_time_2 = appt_time_2.replace(hour=14, minute=30, second=0, microsecond=0)

    result2 = sms.send_booking_confirmation(
        to_number=TEST_PHONE,
        appointment_time=appt_time_2,
        customer_name="Returning Customer Test",
        service_type="Electrical Rewire",
        company_name="JP Enterprises",
        employee_names=["Mike", "Dave"],
        address="456 Oak Avenue, Cork",
    )
    print(f"Result: {'SENT' if result2 else 'FAILED'}")
    print()

    # Summary
    print("=" * 50)
    if result1 and result2:
        print("Both SMS sent successfully. Check your phone.")
    elif result1:
        print("Only new customer SMS sent. Returning customer SMS failed.")
    elif result2:
        print("Only returning customer SMS sent. New customer SMS failed.")
    else:
        print("Both SMS failed. Check Twilio config and phone number.")


if __name__ == "__main__":
    main()
