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
            from_number: Twilio phone number to send from
        """
        from src.utils.config import config
        
        self.account_sid = account_sid or config.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or config.TWILIO_AUTH_TOKEN
        self.from_number = from_number or config.TWILIO_PHONE_NUMBER
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            print("⚠️ Twilio credentials not configured. SMS reminders will not be sent.")
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
            print("✅ Twilio SMS service initialized")
    
    def send_reminder(self, to_number: str, appointment_time: datetime, 
                     patient_name: str, service_type: str = "appointment") -> bool:
        """
        Send an appointment reminder SMS
        
        Args:
            to_number: Recipient phone number
            appointment_time: Appointment datetime
            patient_name: Patient's name
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
                f"Hi {patient_name}! This is a reminder about your {service_type} "
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


# Global instance
_sms_service = None


def get_sms_service() -> SMSReminderService:
    """Get or create global SMS service instance"""
    global _sms_service
    if _sms_service is None:
        _sms_service = SMSReminderService()
    return _sms_service
