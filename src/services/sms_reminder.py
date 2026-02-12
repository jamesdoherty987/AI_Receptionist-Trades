"""
SMS Reminder Service using Twilio
Sends appointment reminders 24 hours before scheduled time
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


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
