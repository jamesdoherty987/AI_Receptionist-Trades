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
        """Send an appointment reminder SMS (kept under 160 chars, no emojis)."""
        if not self.client:
            return False
        
        to_number = normalize_phone_number(to_number)
        
        try:
            time_str = appointment_time.strftime('%b %-d at %-I:%M %p')
            message_body = (
                f"Hi {customer_name}, reminder:\n"
                f"{service_type} - tomorrow {time_str}\n"
                f"Reply YES to confirm or CANCEL."
            )
            
            message = self.client.messages.create(
                body=message_body, from_=self.from_number, to=to_number
            )
            print(f"[SMS] Reminder sent to {to_number} (SID: {message.sid})")
            return True
        except Exception as e:
            print(f"[SMS] Failed to send reminder: {e}")
            return False

    def send_day_before_reminder(self, to_number: str, appointment_time: datetime,
                                  customer_name: str, service_type: str = "appointment",
                                  company_name: str = None,
                                  worker_names: list = None) -> bool:
        """Send a day-before SMS reminder (kept under 160 chars, no emojis)."""
        if not self.client:
            return False

        to_number = normalize_phone_number(to_number)

        try:
            time_str = appointment_time.strftime('%-I:%M %p')
            date_str = appointment_time.strftime('%b %-d')
            business = company_name or 'Your service provider'

            lines = [
                f"{business}",
                f"Hi {customer_name}, reminder:",
                f"{service_type} - {date_str} at {time_str}",
            ]
            if worker_names:
                worker_line = f"Assigned: {', '.join(worker_names)}"
                if len("\n".join(lines + [worker_line, "To cancel/reschedule, contact us."])) <= 160:
                    lines.append(worker_line)
            lines.append("To cancel/reschedule, contact us.")
            message_body = "\n".join(lines)

            message = self.client.messages.create(
                body=message_body, from_=self.from_number, to=to_number
            )
            print(f"[SMS] Day-before reminder sent to {to_number} (SID: {message.sid})")
            return True
        except Exception as e:
            print(f"[SMS] Failed to send day-before reminder: {e}")
            return False

    def send_confirmation_reply(self, to_number: str, message: str) -> bool:
        """Send a reply to user's SMS response."""
        if not self.client:
            return False
        
        to_number = normalize_phone_number(to_number)
        
        try:
            msg = self.client.messages.create(
                body=message, from_=self.from_number, to=to_number
            )
            print(f"[SMS] Reply sent to {to_number}")
            return True
        except Exception as e:
            print(f"[SMS] Failed to send reply: {e}")
            return False

    def send_booking_confirmation(self, to_number: str, appointment_time: datetime,
                                   customer_name: str, service_type: str = "appointment",
                                   company_name: str = None,
                                   worker_names: list = None,
                                   address: str = None) -> bool:
        """Send booking confirmation SMS (kept under 160 chars, no emojis)."""
        if not self.client:
            return False

        to_number = normalize_phone_number(to_number)

        try:
            time_str = appointment_time.strftime('%-I:%M %p')
            date_str = appointment_time.strftime('%b %-d')
            business = company_name or 'Your service provider'

            lines = [
                f"{business}",
                f"Hi {customer_name}, confirmed:",
                f"{service_type} - {date_str} at {time_str}",
            ]
            if worker_names:
                worker_line = f"With: {', '.join(worker_names)}"
                if len("\n".join(lines + [worker_line])) <= 160:
                    lines.append(worker_line)
            if address:
                addr_line = f"At: {address}"
                if len("\n".join(lines + [addr_line])) <= 160:
                    lines.append(addr_line)
            message_body = "\n".join(lines)

            message = self.client.messages.create(
                body=message_body, from_=self.from_number, to=to_number
            )
            print(f"[SMS] Booking confirmation sent to {to_number} (SID: {message.sid})")
            return True
        except Exception as e:
            print(f"[SMS] Failed to send booking confirmation: {e}")
            return False

    def send_cancellation_sms(self, to_number: str, customer_name: str,
                              appointment_time: datetime, service_type: str = "appointment",
                              company_name: str = None, is_full_day: bool = False) -> bool:
        """Send cancellation SMS (kept under 160 chars, no emojis)."""
        if not self.client:
            return False

        to_number = normalize_phone_number(to_number)
        try:
            date_str = appointment_time.strftime('%b %-d')
            business = company_name or 'Your service provider'

            if is_full_day:
                when = date_str
            else:
                time_str = appointment_time.strftime('%-I:%M %p')
                when = f"{date_str} at {time_str}"

            body = (
                f"{business}\n"
                f"Hi {customer_name}, your {service_type} on {when} has been cancelled.\n"
                f"Contact us to rebook."
            )

            message = self.client.messages.create(body=body, from_=self.from_number, to=to_number)
            print(f"[SMS] Cancellation sent to {to_number} (SID: {message.sid})")
            return True
        except Exception as e:
            print(f"[SMS] Failed to send cancellation: {e}")
            return False

    def send_reschedule_sms(self, to_number: str, customer_name: str,
                            new_time: datetime, service_type: str = "appointment",
                            company_name: str = None, is_full_day: bool = False) -> bool:
        """Send reschedule SMS (kept under 160 chars, no emojis)."""
        if not self.client:
            return False

        to_number = normalize_phone_number(to_number)
        try:
            new_date_str = new_time.strftime('%b %-d')
            business = company_name or 'Your service provider'

            if is_full_day:
                when = new_date_str
            else:
                new_time_str = new_time.strftime('%-I:%M %p')
                when = f"{new_date_str} at {new_time_str}"

            body = (
                f"{business}\n"
                f"Hi {customer_name}, your {service_type} has been moved to {when}.\n"
                f"See you then!"
            )

            message = self.client.messages.create(body=body, from_=self.from_number, to=to_number)
            print(f"[SMS] Reschedule sent to {to_number} (SID: {message.sid})")
            return True
        except Exception as e:
            print(f"[SMS] Failed to send reschedule: {e}")
            return False

    
    def send_invoice(self, to_number: str, customer_name: str, service_type: str,
                    charge: float, invoice_number: str = None,
                    stripe_payment_link: str = None, job_address: str = None,
                    appointment_time: datetime = None, company_name: str = None,
                    bank_details: dict = None, revolut_phone: str = None) -> bool:
        """
        Send a compact invoice SMS. If a Stripe payment link is provided,
        the message is kept to essentials + link (aim for 1-2 segments).
        No emojis to stay in GSM-7 encoding.
        """
        if not self.client:
            return False
        
        to_number = normalize_phone_number(to_number)
        
        try:
            from datetime import datetime as dt
            
            business_name = company_name or 'Your Business'
            if not company_name:
                try:
                    from src.services.settings_manager import get_settings_manager
                    settings_mgr = get_settings_manager()
                    settings = settings_mgr.get_business_settings()
                    if settings and settings.get('business_name'):
                        business_name = settings['business_name']
                except Exception:
                    pass
            
            if not invoice_number:
                invoice_number = f"INV-{dt.now().strftime('%Y%m%d%H%M%S')}"
            
            # Build compact message — prioritize payment link
            if stripe_payment_link:
                message_body = (
                    f"{business_name}\n"
                    f"{service_type} - EUR {charge:.2f}\n"
                    f"Pay here: {stripe_payment_link}"
                )
                # If there's room, add the customer greeting
                with_name = (
                    f"{business_name}\n"
                    f"Hi {customer_name}, your invoice:\n"
                    f"{service_type} - EUR {charge:.2f}\n"
                    f"Pay here: {stripe_payment_link}"
                )
                if len(with_name) <= 160:
                    message_body = with_name
            else:
                # No payment link — include bank/revolut details compactly
                lines = [
                    f"{business_name}",
                    f"Hi {customer_name}, your invoice:",
                    f"{service_type} - EUR {charge:.2f}",
                ]
                if bank_details and bank_details.get('iban'):
                    lines.append(f"IBAN: {bank_details['iban']}")
                    lines.append(f"Ref: {invoice_number}")
                if revolut_phone:
                    lines.append(f"Revolut: {revolut_phone}")
                if not bank_details and not revolut_phone:
                    lines.append("Pay by cash or card on completion.")
                message_body = "\n".join(lines)
            
            message = self.client.messages.create(
                body=message_body, from_=self.from_number, to=to_number
            )
            print(f"[SMS] Invoice sent to {to_number} (SID: {message.sid}, Inv: {invoice_number})")
            return True
        except Exception as e:
            print(f"[SMS] Failed to send invoice: {e}")
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
                COALESCE(comp.send_reminder_sms, FALSE) AS send_reminder_sms,
                ARRAY_AGG(w.name) FILTER (WHERE w.name IS NOT NULL) AS worker_names
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
            LEFT JOIN companies comp ON b.company_id = comp.id
            LEFT JOIN worker_assignments wa ON b.id = wa.booking_id
            LEFT JOIN workers w ON wa.worker_id = w.id
            WHERE b.appointment_time >= %s
              AND b.appointment_time < %s
              AND b.status = 'scheduled'
              AND COALESCE(b.reminder_sent, FALSE) = FALSE
            GROUP BY b.id, b.appointment_time, b.service_type,
                     b.phone_number, b.company_id,
                     c.name, c.phone, comp.company_name, comp.send_reminder_sms
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

        # Check if reminder SMS is enabled for this company
        if booking.get('send_reminder_sms') is False:
            print(f"  [SKIP] Booking {booking['id']}: reminder SMS disabled for company {booking.get('company_id')}")
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
            # Mark reminder as sent so it won't be re-sent on redeploy
            try:
                mark_conn = db.get_connection()
                mark_cursor = mark_conn.cursor()
                mark_cursor.execute(
                    "UPDATE bookings SET reminder_sent = TRUE WHERE id = %s",
                    (booking['id'],)
                )
                mark_conn.commit()
                db.return_connection(mark_conn)
            except Exception as e:
                print(f"  [WARNING] Could not mark booking {booking['id']} as reminder_sent: {e}")

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

        # On startup, if we're already past check_hour, assume today's
        # reminders were already sent (prevents duplicate sends on redeploy).
        now = datetime.now()
        if now.hour >= check_hour:
            last_run_date = now.date()
            print(f"[SMS-REMINDER] Past {check_hour}:00 on startup — skipping today to avoid duplicate sends")

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

