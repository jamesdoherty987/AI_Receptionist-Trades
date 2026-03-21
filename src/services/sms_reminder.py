"""
SMS Reminder Service using Twilio
Sends appointment reminders 24 hours before scheduled time
"""
import os
import re
from datetime import datetime, timedelta
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


def normalize_phone_number(phone: str, default_country_code: str = "+353") -> str:
    """
    Normalize a phone number to include country code.
    Defaults to Ireland (+353) if no country code is present.
    
    Args:
        phone: The phone number to normalize
        default_country_code: Country code to add if missing (default: +353 for Ireland)
        
    Returns:
        Normalized phone number with country code
    """
    if not phone:
        return phone
    
    # Remove all whitespace, dashes, parentheses
    cleaned = re.sub(r'[\s\-\(\)]+', '', phone.strip())
    
    # Already has a + prefix - assume it has country code
    if cleaned.startswith('+'):
        return cleaned
    
    # Starts with 00 (international format) - convert to +
    if cleaned.startswith('00'):
        return '+' + cleaned[2:]
    
    # Starts with 353 (Ireland code without + or 00) - just add +
    if cleaned.startswith('353'):
        return '+' + cleaned
    
    # Irish numbers starting with 0 (local format like 0852635954)
    # Remove leading 0 and add +353
    if cleaned.startswith('0'):
        return default_country_code + cleaned[1:]
    
    # No leading 0 or + - assume it needs the country code
    return default_country_code + cleaned


class SMSReminderService:
    """Send SMS reminders for appointments using Twilio"""
    
    def __init__(self, account_sid: str = None, auth_token: str = None, from_number: str = None):
        """
        Initialize Twilio SMS service
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: Twilio phone number to send SMS from
        """
        from src.utils.config import config
        
        self.account_sid = account_sid or config.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or config.TWILIO_AUTH_TOKEN
        # Use dedicated SMS number if available, otherwise fall back to voice number
        self.from_number = from_number or config.TWILIO_SMS_NUMBER or config.TWILIO_PHONE_NUMBER
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            print("⚠️ Twilio credentials not configured. SMS reminders will not be sent.")
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
            print("✅ Twilio SMS service initialized")
    
    def send_reminder(self, to_number: str, appointment_time: datetime, 
                     customer_name: str, service_type: str = "appointment") -> bool:
        """
        Send an appointment reminder SMS
        
        Args:
            to_number: Recipient phone number
            appointment_time: Appointment datetime
            customer_name: Customer's name
            service_type: Type of appointment/service
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.client:
            print("❌ SMS service not configured")
            return False
        
        # Normalize phone number to include country code (default: Ireland +353)
        to_number = normalize_phone_number(to_number)
        
        try:
            # Format the appointment time nicely
            time_str = appointment_time.strftime('%B %d at %I:%M %p')
            
            # Create reminder message
            message_body = (
                f"Hi {customer_name}! This is a reminder about your {service_type} "
                f"appointment tomorrow ({time_str}). "
                f"Reply YES to confirm or CANCEL to cancel your appointment."
            )
            
            # Send SMS
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            print(f"✅ SMS reminder sent to {to_number}")
            print(f"   Message SID: {message.sid}")
            return True
            
        except TwilioRestException as e:
            print(f"❌ Failed to send SMS: {e}")
            return False
        except Exception as e:
            print(f"❌ Error sending SMS reminder: {e}")
            return False

    def send_day_before_reminder(self, to_number: str, appointment_time: datetime,
                                  customer_name: str, service_type: str = "appointment",
                                  company_name: str = None,
                                  worker_names: list = None) -> bool:
        """
        Send a day-before SMS reminder with company name and job details.

        Args:
            to_number: Recipient phone number
            appointment_time: Appointment datetime
            customer_name: Customer's name
            service_type: Type of service/job
            company_name: Business name
            worker_names: List of assigned worker names

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.client:
            print("SMS service not configured")
            return False

        to_number = normalize_phone_number(to_number)

        try:
            time_str = appointment_time.strftime('%I:%M %p')
            date_str = appointment_time.strftime('%A, %B %d')
            business = company_name or 'Your service provider'

            lines = [
                f"Hi {customer_name}, this is a reminder from {business}.",
                f"",
                f"You have a {service_type} appointment tomorrow ({date_str}) at {time_str}.",
            ]

            if worker_names:
                names = ", ".join(worker_names)
                lines.append(f"Assigned: {names}")

            lines.append("")
            lines.append("If you need to cancel or reschedule, please contact us as soon as possible.")

            message_body = "\n".join(lines)

            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )

            print(f"Day-before SMS reminder sent to {to_number} (SID: {message.sid})")
            return True

        except TwilioRestException as e:
            print(f"Failed to send day-before SMS reminder: {e}")
            return False
        except Exception as e:
            print(f"Error sending day-before SMS reminder: {e}")
            return False

    def send_confirmation_reply(self, to_number: str, message: str) -> bool:
        """
        Send a reply to user's SMS response
        
        Args:
            to_number: Recipient phone number
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.client:
            print("❌ SMS service not configured")
            return False
        
        # Normalize phone number to include country code (default: Ireland +353)
        to_number = normalize_phone_number(to_number)
        
        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            print(f"✅ SMS reply sent to {to_number}")
            return True
            
        except TwilioRestException as e:
            print(f"❌ Failed to send SMS reply: {e}")
            return False

    def send_booking_confirmation(self, to_number: str, appointment_time: datetime,
                                   customer_name: str, service_type: str = "appointment",
                                   company_name: str = None,
                                   worker_names: list = None,
                                   address: str = None) -> bool:
        """
        Send an SMS confirmation immediately after a booking is created.

        Args:
            to_number: Recipient phone number
            appointment_time: Appointment datetime
            customer_name: Customer's name
            service_type: Type of service/job
            company_name: Business name
            worker_names: List of assigned worker names
            address: Job address if applicable

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.client:
            print("[SMS-CONFIRM] SMS service not configured")
            return False

        to_number = normalize_phone_number(to_number)

        try:
            time_str = appointment_time.strftime('%I:%M %p')
            date_str = appointment_time.strftime('%A, %B %d')
            business = company_name or 'Your service provider'

            lines = [
                f"Hi {customer_name}, your {service_type} booking with {business} is confirmed.",
                f"",
                f"Date: {date_str}",
                f"Time: {time_str}",
            ]

            if address:
                lines.append(f"Address: {address}")

            if worker_names:
                names = ", ".join(worker_names)
                lines.append(f"Assigned: {names}")

            lines.append("")
            lines.append("If you need to cancel or reschedule, please contact us.")

            message_body = "\n".join(lines)

            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )

            print(f"[SMS-CONFIRM] Booking confirmation sent to {to_number} (SID: {message.sid})")
            return True

        except TwilioRestException as e:
            print(f"[SMS-CONFIRM] Failed to send booking confirmation: {e}")
            return False
        except Exception as e:
            print(f"[SMS-CONFIRM] Error sending booking confirmation: {e}")
            return False

    
    def send_invoice(self, to_number: str, customer_name: str, service_type: str,
                    charge: float, invoice_number: str = None,
                    stripe_payment_link: str = None, job_address: str = None,
                    appointment_time: datetime = None, company_name: str = None,
                    bank_details: dict = None, revolut_phone: str = None) -> bool:
        """
        Send an invoice via SMS with optional Stripe payment link and bank details
        
        Args:
            to_number: Recipient phone number
            customer_name: Customer's name
            service_type: Type of service performed
            charge: Amount to charge
            invoice_number: Unique invoice number (optional)
            stripe_payment_link: Stripe payment URL (optional)
            job_address: Address where service was performed (optional)
            appointment_time: Appointment datetime for the job (optional)
            company_name: Business name to show on invoice
            bank_details: Dict with iban, bic, bank_name, account_holder (optional)
            revolut_phone: Revolut phone number for payment (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.client:
            print("❌ SMS service not configured")
            return False
        
        # Normalize phone number to include country code (default: Ireland +353)
        to_number = normalize_phone_number(to_number)
        
        try:
            from src.services.settings_manager import get_settings_manager
            from datetime import datetime as dt
            
            # Get business name from settings if not provided
            business_name = company_name or 'Your Business'
            if not company_name:
                try:
                    settings_mgr = get_settings_manager()
                    settings = settings_mgr.get_business_settings()
                    if settings and settings.get('business_name'):
                        business_name = settings['business_name']
                except Exception as e:
                    print(f"[WARNING] Could not load business name: {e}")
            
            # Generate invoice number if not provided
            if not invoice_number:
                invoice_number = f"INV-{dt.now().strftime('%Y%m%d%H%M%S')}"
            
            # Build the SMS message
            lines = [
                f"📄 INVOICE from {business_name}",
                f"Invoice #: {invoice_number}",
                f"",
                f"Hi {customer_name},",
                f"",
                f"Service: {service_type}",
            ]
            
            if job_address:
                lines.append(f"Location: {job_address}")
            
            if appointment_time:
                time_str = appointment_time.strftime('%B %d, %Y')
                lines.append(f"Date: {time_str}")
            
            lines.append(f"")
            lines.append(f"💰 AMOUNT DUE: EUR {charge:.2f}")
            
            # Add Stripe payment link if available
            if stripe_payment_link:
                lines.append(f"")
                lines.append(f"💳 Pay online:")
                lines.append(stripe_payment_link)
            
            # Add bank transfer details if available
            if bank_details and bank_details.get('iban'):
                lines.append(f"")
                lines.append(f"🏦 Bank Transfer:")
                lines.append(f"IBAN: {bank_details['iban']}")
                if bank_details.get('bic'):
                    lines.append(f"BIC: {bank_details['bic']}")
                if bank_details.get('account_holder'):
                    lines.append(f"Name: {bank_details['account_holder']}")
                lines.append(f"Ref: {invoice_number}")
            
            # Add Revolut details if available
            if revolut_phone:
                lines.append(f"")
                lines.append(f"📱 Revolut: {revolut_phone}")
                lines.append(f"Ref: {invoice_number}")
            
            # If no payment methods configured, add note
            if not stripe_payment_link and not (bank_details and bank_details.get('iban')) and not revolut_phone:
                lines.append(f"")
                lines.append(f"Payment: Cash or card on completion")
            
            lines.append(f"")
            lines.append(f"Thank you for your business!")
            
            message_body = "\n".join(lines)
            
            # Send SMS
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_number
            )
            
            print(f"✅ Invoice SMS sent to {to_number}")
            print(f"   Message SID: {message.sid}")
            print(f"   Invoice #: {invoice_number}")
            return True
            
        except TwilioRestException as e:
            print(f"❌ Failed to send invoice SMS: {e}")
            return False
        except Exception as e:
            print(f"❌ Error sending invoice SMS: {e}")
            import traceback
            traceback.print_exc()
            return False


# Global instance
_sms_service = None


def get_sms_service() -> SMSReminderService:
    """Get or create global SMS service instance"""
    global _sms_service
    if _sms_service is None:
        _sms_service = SMSReminderService()
    return _sms_service


def send_day_before_reminders() -> int:
    """
    Query all bookings scheduled for tomorrow and send SMS reminders.
    Runs across all companies (multi-tenant).

    Returns:
        Number of reminders sent
    """
    from src.services.database import get_database

    db = get_database()
    sms = get_sms_service()

    if not sms.client:
        print("[SMS-REMINDER] Twilio not configured, skipping day-before reminders")
        return 0

    now = datetime.now()
    tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + timedelta(days=1)

    print(f"\n{'='*60}")
    print(f"[SMS-REMINDER] Checking for tomorrow's appointments ({tomorrow_start.strftime('%Y-%m-%d')})...")

    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT
                b.id, b.appointment_time, b.service_type,
                b.phone_number, b.company_id,
                c.name AS client_name, c.phone AS client_phone,
                comp.company_name,
                ARRAY_AGG(w.name) FILTER (WHERE w.name IS NOT NULL) AS worker_names
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
            LEFT JOIN companies comp ON b.company_id = comp.id
            LEFT JOIN worker_assignments wa ON b.id = wa.booking_id
            LEFT JOIN workers w ON wa.worker_id = w.id
            WHERE b.appointment_time >= %s
              AND b.appointment_time < %s
              AND b.status = 'scheduled'
            GROUP BY b.id, b.appointment_time, b.service_type,
                     b.phone_number, b.company_id,
                     c.name, c.phone, comp.company_name
            ORDER BY b.appointment_time
        """, (tomorrow_start.strftime("%Y-%m-%d %H:%M:%S"),
              tomorrow_end.strftime("%Y-%m-%d %H:%M:%S")))
        bookings = cursor.fetchall()
    finally:
        db.return_connection(conn)

    if not bookings:
        print("[SMS-REMINDER] No appointments found for tomorrow")
        print(f"{'='*60}\n")
        return 0

    print(f"[SMS-REMINDER] Found {len(bookings)} appointment(s) for tomorrow")

    sent_count = 0
    for booking in bookings:
        phone = booking.get('phone_number') or booking.get('client_phone')
        if not phone:
            print(f"  [SKIP] Booking {booking['id']}: no phone number")
            continue

        customer_name = booking.get('client_name') or 'Customer'
        service_type = booking.get('service_type') or 'appointment'
        company_name = booking.get('company_name')
        worker_names = booking.get('worker_names') or []
        appt_time = booking['appointment_time']

        if isinstance(appt_time, str):
            appt_time = datetime.strptime(appt_time, "%Y-%m-%d %H:%M:%S")

        success = sms.send_day_before_reminder(
            to_number=phone,
            appointment_time=appt_time,
            customer_name=customer_name,
            service_type=service_type,
            company_name=company_name,
            worker_names=worker_names,
        )
        if success:
            sent_count += 1

    print(f"[SMS-REMINDER] Sent {sent_count}/{len(bookings)} day-before reminders")
    print(f"{'='*60}\n")
    return sent_count



def start_sms_reminder_scheduler(check_hour: int = 17):
    """
    Start a background thread that sends day-before SMS reminders once per day.
    Defaults to running at 5 PM so customers get the reminder the evening before.

    Args:
        check_hour: Hour of day (0-23) to send reminders (default: 17 = 5 PM)
    """
    import threading
    import time as time_module

    def scheduler_loop():
        print(f"[SMS-REMINDER] Scheduler started (will send reminders daily at {check_hour}:00)")
        last_run_date = None

        while True:
            now = datetime.now()
            today = now.date()

            # Run once per day at or after check_hour
            if now.hour >= check_hour and last_run_date != today:
                try:
                    send_day_before_reminders()
                except Exception as e:
                    print(f"[SMS-REMINDER] Error in scheduler: {e}")
                last_run_date = today

            # Sleep 15 minutes between checks
            time_module.sleep(15 * 60)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    return thread

