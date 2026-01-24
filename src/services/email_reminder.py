"""
Email Reminder Service
Sends appointment reminders via email - works great in Ireland/EU
"""
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


class EmailReminderService:
    """Send email reminders for appointments"""
    
    def __init__(self, smtp_server: str = None, smtp_port: int = None, 
                 smtp_user: str = None, smtp_password: str = None, 
                 from_email: str = None):
        """
        Initialize email service
        
        Args:
            smtp_server: SMTP server address (e.g., smtp.gmail.com)
            smtp_port: SMTP port (usually 587 for TLS)
            smtp_user: SMTP username/email
            smtp_password: SMTP password or app password
            from_email: Email address to send from
        """
        from src.utils.config import config
        
        # Try to get from config/env, fall back to parameters
        self.smtp_server = smtp_server or getattr(config, 'SMTP_SERVER', None)
        self.smtp_port = smtp_port or getattr(config, 'SMTP_PORT', 587)
        self.smtp_user = smtp_user or getattr(config, 'SMTP_USER', None)
        self.smtp_password = smtp_password or getattr(config, 'SMTP_PASSWORD', None)
        self.from_email = from_email or getattr(config, 'FROM_EMAIL', None)
        
        if not all([self.smtp_server, self.smtp_user, self.smtp_password, self.from_email]):
            print("⚠️ Email service not fully configured. Email reminders will not be sent.")
            self.configured = False
        else:
            self.configured = True
            print("✅ Email reminder service initialized")
    
    def send_reminder(self, to_email: str, appointment_time: datetime, 
                     customer_name: str, service_type: str = "appointment",
                     phone_number: str = "") -> bool:
        """
        Send an appointment reminder email
        
        Args:
            to_email: Recipient email address
            appointment_time: Appointment datetime
            customer_name: Customer's name
            service_type: Type of appointment/service
            phone_number: Customer's phone number (for contact info)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.configured:
            print("❌ Email service not configured")
            return False
        
        try:
            # Format the appointment time
            time_str = appointment_time.strftime('%A, %B %d at %I:%M %p')
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Reminder: Your {service_type.title()} Appointment Tomorrow'
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Plain text version
            text_body = f"""
Hi {customer_name},

This is a friendly reminder about your {service_type} appointment tomorrow:

Date & Time: {time_str}
Location: Munster Physio

If you need to cancel or reschedule, please call us as soon as possible.

Best regards,
Munster Physio Team
            """.strip()
            
            # HTML version (prettier)
            html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">Appointment Reminder</h2>
        
        <p>Hi {customer_name},</p>
        
        <p>This is a friendly reminder about your <strong>{service_type}</strong> appointment:</p>
        
        <div style="background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>📅 Date & Time:</strong> {time_str}</p>
            <p style="margin: 5px 0;"><strong>📍 Location:</strong> Munster Physio</p>
        </div>
        
        <p>If you need to cancel or reschedule, please call us as soon as possible.</p>
        
        <p style="margin-top: 30px;">Best regards,<br>
        <strong>Munster Physio Team</strong></p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: #666;">
            This is an automated reminder. Please do not reply to this email.
        </p>
    </div>
</body>
</html>
            """.strip()
            
            # Attach both versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ Email reminder sent to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False
    
    def send_confirmation_reply(self, to_email: str, message: str) -> bool:
        """
        Send a confirmation email
        
        Args:
            to_email: Recipient email address
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.configured:
            print("❌ Email service not configured")
            return False
        
        try:
            msg = MIMEText(message)
            msg['Subject'] = 'Appointment Confirmation'
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ Email sent to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False
    
    def send_invoice(self, to_email: str, customer_name: str, service_type: str, 
                    charge: float, appointment_time: datetime = None) -> bool:
        """
        Send an invoice email
        
        Args:
            to_email: Recipient email address
            customer_name: Customer's name
            service_type: Type of service performed
            charge: Amount to charge
            appointment_time: Appointment datetime (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.configured:
            print("❌ Email service not configured")
            return False
        
        try:
            # Format the date if provided
            date_str = appointment_time.strftime('%A, %B %d, %Y') if appointment_time else 'Recent service'
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Invoice for {service_type.title()} Service'
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Plain text version
            text_body = f"""
Hi {customer_name},

Thank you for choosing our services!

INVOICE DETAILS:
Service: {service_type}
Date: {date_str}
Amount Due: €{charge:.2f}

Please remit payment at your earliest convenience.

If you have any questions about this invoice, please don't hesitate to contact us.

Best regards,
The Team
            """.strip()
            
            # HTML version (prettier)
            html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">INVOICE</h2>
        
        <p>Hi {customer_name},</p>
        
        <p>Thank you for choosing our services!</p>
        
        <div style="background-color: #f8f9fa; border-left: 4px solid #10b981; padding: 20px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #2c3e50;">Invoice Details</h3>
            <p style="margin: 5px 0;"><strong>Service:</strong> {service_type}</p>
            <p style="margin: 5px 0;"><strong>Date:</strong> {date_str}</p>
            <p style="margin: 15px 0 5px 0; font-size: 1.3em;">
                <strong>Amount Due:</strong> 
                <span style="color: #10b981; font-weight: bold;">€{charge:.2f}</span>
            </p>
        </div>
        
        <p>Please remit payment at your earliest convenience.</p>
        
        <p>If you have any questions about this invoice, please don't hesitate to contact us.</p>
        
        <p style="margin-top: 30px;">Best regards,<br>
        <strong>The Team</strong></p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: #666;">
            This is an automated invoice. Thank you for your business!
        </p>
    </div>
</body>
</html>
            """.strip()
            
            # Attach both versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ Invoice email sent to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send invoice email: {e}")
            return False


# Global instance
_email_service = None


def get_email_service() -> EmailReminderService:
    """Get or create global email service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailReminderService()
    return _email_service
