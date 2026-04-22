# -*- coding: utf-8 -*-
"""
Email Reminder Service
Sends appointment reminders via email - works great in Ireland/EU
Supports Resend API (recommended) with SMTP fallback
"""
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# Try to import resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    print("[WARNING] Resend package not installed. Install with: pip install resend")


class EmailReminderService:
    """Send email reminders for appointments - supports Resend API with SMTP fallback"""
    
    def __init__(self, smtp_server: str = None, smtp_port: int = None, 
                 smtp_user: str = None, smtp_password: str = None, 
                 smtp_from_email: str = None, resend_api_key: str = None,
                 resend_from_email: str = None):
        """
        Initialize email service
        
        Args:
            smtp_server: SMTP server address (e.g., smtp.gmail.com)
            smtp_port: SMTP port (usually 587 for TLS)
            smtp_user: SMTP username/email
            smtp_password: SMTP password or app password
            smtp_from_email: Email address to send from via SMTP (must match SMTP auth)
            resend_api_key: Resend API key (recommended over SMTP)
            resend_from_email: Email address to send from via Resend (must be verified domain)
        """
        from src.utils.config import config
        
        # Try Resend first (recommended - works on all hosts)
        self.resend_api_key = resend_api_key or getattr(config, 'RESEND_API_KEY', None)
        self.resend_from_email = resend_from_email or getattr(config, 'RESEND_FROM_EMAIL', None)
        self.use_resend = bool(self.resend_api_key and RESEND_AVAILABLE)
        
        if self.use_resend:
            resend.api_key = self.resend_api_key
            print(f"[SUCCESS] Email service initialized with Resend API (from: {self.resend_from_email or 'onboarding@resend.dev'})")
        
        # SMTP fallback configuration
        self.smtp_server = smtp_server or getattr(config, 'SMTP_SERVER', None)
        self.smtp_port = smtp_port or getattr(config, 'SMTP_PORT', 587)
        self.smtp_user = smtp_user or getattr(config, 'SMTP_USER', None)
        self.smtp_password = smtp_password or getattr(config, 'SMTP_PASSWORD', None)
        self.smtp_from_email = smtp_from_email or getattr(config, 'SMTP_FROM_EMAIL', None) or getattr(config, 'FROM_EMAIL', None)
        
        self.smtp_configured = all([self.smtp_server, self.smtp_user, self.smtp_password, self.smtp_from_email])
        
        if self.smtp_configured and not self.use_resend:
            print(f"[SUCCESS] Email service initialized with SMTP (from: {self.smtp_from_email})")
        
        # Service is configured if either Resend or SMTP is available
        if self.use_resend:
            self.configured = True
        elif self.smtp_configured:
            self.configured = True
        else:
            print("[WARNING] Email service not configured. Set RESEND_API_KEY (recommended) or SMTP settings.")
            self.configured = False
        
        # For backward compatibility, expose a from_email property
        # Prefers Resend from_email, falls back to SMTP from_email
        self.from_email = self.resend_from_email or self.smtp_from_email
    
    def _send_via_resend(self, to_email: str, subject: str, html_body: str, 
                         text_body: str, from_name: str = None) -> bool:
        """Send email using Resend API. Also stores the email ID for bounce tracking."""
        try:
            from_addr = self.resend_from_email or "onboarding@resend.dev"
            from_address = f"{from_name} <{from_addr}>" if from_name else from_addr
            
            params = {
                "from": from_address,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": text_body,
            }
            
            response = resend.Emails.send(params)
            email_id = response.get('id', 'unknown')
            print(f"[SUCCESS] Email sent via Resend to {to_email} (ID: {email_id})")
            # Store the email ID so the bounce webhook can look it up
            self._last_resend_email_id = email_id
            return True
            
        except Exception as e:
            print(f"[ERROR] Resend failed: {e}")
            self._last_resend_email_id = None
            return False
    
    def _send_via_smtp(self, to_email: str, subject: str, html_body: str, 
                       text_body: str, from_name: str = None) -> bool:
        """Send email using SMTP (fallback)"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f'{from_name} <{self.smtp_from_email}>' if from_name else self.smtp_from_email
            msg['To'] = to_email
            
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f"[SUCCESS] Email sent via SMTP to {to_email}")
            return True
            
        except Exception as e:
            print(f"[ERROR] SMTP failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _send_email(self, to_email: str, subject: str, html_body: str, 
                    text_body: str, from_name: str = None) -> bool:
        """
        Send email using best available method (Resend first, then SMTP fallback)
        """
        if not self.configured:
            print("[ERROR] Email service not configured")
            return False
        
        # Try Resend first
        if self.use_resend:
            success = self._send_via_resend(to_email, subject, html_body, text_body, from_name)
            if success:
                return True
            # If Resend fails, try SMTP fallback
            if self.smtp_configured:
                print("[INFO] Resend failed, trying SMTP fallback...")
                return self._send_via_smtp(to_email, subject, html_body, text_body, from_name)
            return False
        
        # Use SMTP if Resend not configured
        if self.smtp_configured:
            return self._send_via_smtp(to_email, subject, html_body, text_body, from_name)
        
        return False
    
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
            print("[ERROR] Email service not configured")
            return False
        
        try:
            from src.services.settings_manager import get_settings_manager
            
            # Load business name from database
            business_name = 'Your Business'
            try:
                settings_mgr = get_settings_manager()
                settings = settings_mgr.get_business_settings()
                if settings and settings.get('business_name'):
                    business_name = settings['business_name']
            except Exception as e:
                print(f"[WARNING] Could not load business name from database: {e}")
            
            # Format the appointment time
            time_str = appointment_time.strftime('%A, %B %d at %I:%M %p')
            
            subject = f'Reminder: Your {service_type.title()} Appointment Tomorrow'
            
            # Plain text version
            text_body = f"""
Hi {customer_name},

This is a friendly reminder about your {service_type} appointment tomorrow:

Date & Time: {time_str}

If you need to cancel or reschedule, please call us as soon as possible.

Best regards,
{business_name}
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
            <p style="margin: 5px 0;"><strong>Date & Time:</strong> {time_str}</p>
        </div>
        
        <p>If you need to cancel or reschedule, please call us as soon as possible.</p>
        
        <p style="margin-top: 30px;">Best regards,<br>
        <strong>{business_name}</strong></p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: #666;">
            This is an automated reminder. Please do not reply to this email.
        </p>
    </div>
</body>
</html>
            """.strip()
            
            return self._send_email(to_email, subject, html_body, text_body, business_name)
            
        except Exception as e:
            print(f"[ERROR] Failed to send reminder email: {e}")
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
            print("[ERROR] Email service not configured")
            return False
        
        try:
            subject = 'Appointment Confirmation'
            text_body = message
            html_body = f"<html><body><p>{message}</p></body></html>"
            
            return self._send_email(to_email, subject, html_body, text_body)
            
        except Exception as e:
            print(f"[ERROR] Failed to send confirmation email: {e}")
            return False
    
    def send_password_reset(self, to_email: str, reset_link: str, business_name: str = 'BookedForYou') -> bool:
        """
        Send a password reset email
        
        Args:
            to_email: Recipient email address
            reset_link: Full URL link for password reset
            business_name: Name of the business
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.configured:
            print(f"[WARNING] Email service not configured. Password reset link: {reset_link}")
            return False
        
        try:
            subject = f'Reset Your Password - {business_name}'
            
            text_body = f"""
Hi,

We received a request to reset your password for your {business_name} account.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email.

Best regards,
{business_name}
            """.strip()
            
            html_body = f"""
<!DOCTYPE html>
<html>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden;">
            <div style="background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); padding: 30px; text-align: center;">
                <div style="font-size: 28px; font-weight: 800; color: white; letter-spacing: -0.5px;">
                    {business_name}
                </div>
            </div>
            <div style="padding: 30px;">
                <h2 style="color: #1e293b; margin: 0 0 15px 0;">Reset Your Password</h2>
                <p style="color: #6b7280; font-size: 15px; line-height: 1.6;">
                    We received a request to reset your password. Click the button below to create a new password.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" 
                       style="display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%); 
                              color: white; text-decoration: none; padding: 16px 40px; font-size: 16px; 
                              font-weight: 700; border-radius: 10px; box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);">
                        Reset Password
                    </a>
                </div>
                <p style="color: #9ca3af; font-size: 13px; margin-top: 20px;">
                    This link will expire in 1 hour. If you didn't request this, you can safely ignore this email.
                </p>
                <p style="color: #9ca3af; font-size: 12px; margin-top: 15px; word-break: break-all;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <a href="{reset_link}" style="color: #3b82f6;">{reset_link}</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
            """.strip()
            
            return self._send_email(to_email, subject, html_body, text_body, business_name)
            
        except Exception as e:
            print(f"[ERROR] Failed to send password reset email: {e}")
            return False
    
    def send_booking_confirmation(self, to_email: str, appointment_time: datetime,
                                    customer_name: str, service_type: str = "appointment",
                                    company_name: str = None, worker_names: list = None,
                                    address: str = None, portal_link: str = None) -> bool:
        """Send a booking confirmation email."""
        if not self.configured:
            return False
        try:
            business_name = company_name or 'Your Business'
            if not company_name:
                try:
                    from src.services.settings_manager import get_settings_manager
                    s = get_settings_manager().get_business_settings()
                    if s and s.get('business_name'):
                        business_name = s['business_name']
                except Exception:
                    pass

            time_str = appointment_time.strftime('%A, %B %d at %I:%M %p')
            date_only = appointment_time.strftime('%A, %B %d')

            worker_line = ""
            if worker_names:
                worker_line = f"<p style='margin:5px 0;'><strong>Assigned:</strong> {', '.join(worker_names)}</p>"
            address_line = ""
            if address:
                address_line = f"<p style='margin:5px 0;'><strong>Location:</strong> {address}</p>"

            portal_section_html = ""
            portal_section_text = ""
            if portal_link:
                portal_section_html = f"""
        <div style="background:#eef2ff;border:1px solid #c7d2fe;padding:15px;margin:20px 0;border-radius:8px;text-align:center;">
            <p style="margin:0 0 8px;font-size:14px;color:#4338ca;font-weight:600;">Your Customer Portal</p>
            <p style="margin:0 0 12px;font-size:13px;color:#64748b;">View your jobs, upload photos of the issue, and manage your bookings.</p>
            <a href="{portal_link}" style="display:inline-block;padding:10px 24px;background:#6366f1;color:white;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">Open My Portal</a>
        </div>"""
                portal_section_text = (
                    f"\nYour Customer Portal: {portal_link}\n"
                    f"View your jobs, upload photos of the issue, and manage your bookings.\n"
                )

            subject = f'Booking Confirmed - {service_type} on {date_only}'

            text_body = (
                f"{business_name}\n\n"
                f"Hi {customer_name},\n\n"
                f"Your booking is confirmed:\n"
                f"Service: {service_type}\n"
                f"Date & Time: {time_str}\n"
                f"{'Assigned: ' + ', '.join(worker_names) if worker_names else ''}\n"
                f"{'Location: ' + address if address else ''}\n"
                f"{portal_section_text}\n"
                f"To cancel or reschedule, please contact us.\n\n"
                f"Best regards,\n{business_name}"
            ).strip()

            html_body = f"""
<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);padding:25px;text-align:center;border-radius:12px 12px 0 0;">
        <div style="font-size:24px;font-weight:800;color:white;">{business_name}</div>
    </div>
    <div style="background:white;padding:25px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;">
        <h2 style="color:#059669;margin:0 0 15px;">Booking Confirmed</h2>
        <p>Hi {customer_name},</p>
        <p>Your booking has been confirmed:</p>
        <div style="background:#f0fdf4;border-left:4px solid #10b981;padding:15px;margin:20px 0;border-radius:0 8px 8px 0;">
            <p style="margin:5px 0;"><strong>Service:</strong> {service_type}</p>
            <p style="margin:5px 0;"><strong>Date & Time:</strong> {time_str}</p>
            {worker_line}
            {address_line}
        </div>
        {portal_section_html}
        <p>To cancel or reschedule, please contact us.</p>
        <p style="margin-top:25px;">Best regards,<br><strong>{business_name}</strong></p>
    </div>
</div></body></html>""".strip()

            return self._send_email(to_email, subject, html_body, text_body, business_name)
        except Exception as e:
            print(f"[ERROR] Failed to send booking confirmation email: {e}")
            return False

    def send_cancellation_email(self, to_email: str, customer_name: str,
                                 appointment_time: datetime, service_type: str = "appointment",
                                 company_name: str = None, is_full_day: bool = False) -> bool:
        """Send a cancellation confirmation email."""
        if not self.configured:
            return False
        try:
            business_name = company_name or 'Your Business'
            if not company_name:
                try:
                    from src.services.settings_manager import get_settings_manager
                    s = get_settings_manager().get_business_settings()
                    if s and s.get('business_name'):
                        business_name = s['business_name']
                except Exception:
                    pass

            date_str = appointment_time.strftime('%A, %B %d')
            if is_full_day:
                when = date_str
            else:
                when = appointment_time.strftime('%A, %B %d at %I:%M %p')

            subject = f'Booking Cancelled - {service_type} on {date_str}'

            text_body = (
                f"{business_name}\n\n"
                f"Hi {customer_name},\n\n"
                f"Your {service_type} on {when} has been cancelled.\n\n"
                f"If you'd like to rebook, please contact us.\n\n"
                f"Best regards,\n{business_name}"
            ).strip()

            html_body = f"""
<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);padding:25px;text-align:center;border-radius:12px 12px 0 0;">
        <div style="font-size:24px;font-weight:800;color:white;">{business_name}</div>
    </div>
    <div style="background:white;padding:25px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;">
        <h2 style="color:#dc2626;margin:0 0 15px;">Booking Cancelled</h2>
        <p>Hi {customer_name},</p>
        <p>Your booking has been cancelled:</p>
        <div style="background:#fef2f2;border-left:4px solid #ef4444;padding:15px;margin:20px 0;border-radius:0 8px 8px 0;">
            <p style="margin:5px 0;"><strong>Service:</strong> {service_type}</p>
            <p style="margin:5px 0;"><strong>Was scheduled for:</strong> {when}</p>
        </div>
        <p>If you'd like to rebook, please contact us.</p>
        <p style="margin-top:25px;">Best regards,<br><strong>{business_name}</strong></p>
    </div>
</div></body></html>""".strip()

            return self._send_email(to_email, subject, html_body, text_body, business_name)
        except Exception as e:
            print(f"[ERROR] Failed to send cancellation email: {e}")
            return False

    def send_rejection_email(self, to_email: str, customer_name: str,
                              service_type: str = "appointment", appointment_time=None,
                              company_name: str = None, reason: str = None) -> bool:
        """Send a job rejection/refusal email to the customer."""
        if not self.configured:
            return False
        try:
            business_name = company_name or 'Your Business'
            time_str = ''
            if appointment_time:
                if isinstance(appointment_time, str):
                    from datetime import datetime as _dt
                    try:
                        appointment_time = _dt.fromisoformat(appointment_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    except Exception:
                        appointment_time = None
                if appointment_time:
                    time_str = appointment_time.strftime('%A, %B %d at %I:%M %p')

            reason_html = ""
            reason_text = ""
            if reason:
                import html as _html_mod
                safe_reason = _html_mod.escape(reason)
                reason_html = f'<p style="margin:10px 0;"><strong>Reason:</strong> {safe_reason}</p>'
                reason_text = f"\nReason: {reason}\n"

            subject = f'Booking Update - {service_type}'

            text_body = (
                f"{business_name}\n\n"
                f"Hi {customer_name},\n\n"
                f"Unfortunately, we're unable to take on your booking"
                f"{' for ' + service_type if service_type != 'appointment' else ''}"
                f"{' on ' + time_str if time_str else ''}.\n"
                f"{reason_text}\n"
                f"We apologise for any inconvenience. Please don't hesitate to contact us "
                f"if you'd like to discuss alternatives or rebook.\n\n"
                f"Best regards,\n{business_name}"
            ).strip()

            html_body = f"""
<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);padding:25px;text-align:center;border-radius:12px 12px 0 0;">
        <div style="font-size:24px;font-weight:800;color:white;">{business_name}</div>
    </div>
    <div style="background:white;padding:25px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;">
        <h2 style="color:#ef4444;margin:0 0 15px;">Booking Update</h2>
        <p>Hi {customer_name},</p>
        <p>Unfortunately, we're unable to take on your booking{' for <strong>' + service_type + '</strong>' if service_type != 'appointment' else ''}{' on <strong>' + time_str + '</strong>' if time_str else ''}.</p>
        {reason_html}
        <p>We apologise for any inconvenience. Please don't hesitate to contact us if you'd like to discuss alternatives or rebook.</p>
        <p style="margin-top:25px;">Best regards,<br><strong>{business_name}</strong></p>
    </div>
</div></body></html>""".strip()

            return self._send_email(to_email, subject, html_body, text_body, business_name)
        except Exception as e:
            print(f"[ERROR] Failed to send rejection email: {e}")
            return False

    def send_reschedule_email(self, to_email: str, customer_name: str,
                               new_time: datetime, service_type: str = "appointment",
                               company_name: str = None, is_full_day: bool = False) -> bool:
        """Send a reschedule confirmation email."""
        if not self.configured:
            return False
        try:
            business_name = company_name or 'Your Business'
            if not company_name:
                try:
                    from src.services.settings_manager import get_settings_manager
                    s = get_settings_manager().get_business_settings()
                    if s and s.get('business_name'):
                        business_name = s['business_name']
                except Exception:
                    pass

            date_str = new_time.strftime('%A, %B %d')
            if is_full_day:
                when = date_str
            else:
                when = new_time.strftime('%A, %B %d at %I:%M %p')

            subject = f'Booking Rescheduled - {service_type} moved to {date_str}'

            text_body = (
                f"{business_name}\n\n"
                f"Hi {customer_name},\n\n"
                f"Your {service_type} has been rescheduled to {when}.\n\n"
                f"See you then!\n\n"
                f"Best regards,\n{business_name}"
            ).strip()

            html_body = f"""
<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);padding:25px;text-align:center;border-radius:12px 12px 0 0;">
        <div style="font-size:24px;font-weight:800;color:white;">{business_name}</div>
    </div>
    <div style="background:white;padding:25px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;">
        <h2 style="color:#2563eb;margin:0 0 15px;">Booking Rescheduled</h2>
        <p>Hi {customer_name},</p>
        <p>Your booking has been moved to a new time:</p>
        <div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:15px;margin:20px 0;border-radius:0 8px 8px 0;">
            <p style="margin:5px 0;"><strong>Service:</strong> {service_type}</p>
            <p style="margin:5px 0;"><strong>New Date & Time:</strong> {when}</p>
        </div>
        <p>See you then!</p>
        <p style="margin-top:25px;">Best regards,<br><strong>{business_name}</strong></p>
    </div>
</div></body></html>""".strip()

            return self._send_email(to_email, subject, html_body, text_body, business_name)
        except Exception as e:
            print(f"[ERROR] Failed to send reschedule email: {e}")
            return False

    def send_day_before_reminder(self, to_email: str, appointment_time: datetime,
                                  customer_name: str, service_type: str = "appointment",
                                  company_name: str = None, worker_names: list = None) -> bool:
        """Send a day-before reminder email."""
        if not self.configured:
            return False
        try:
            business_name = company_name or 'Your Business'
            time_str = appointment_time.strftime('%A, %B %d at %I:%M %p')
            date_only = appointment_time.strftime('%A, %B %d')

            worker_line = ""
            if worker_names:
                worker_line = f"<p style='margin:5px 0;'><strong>Assigned:</strong> {', '.join(worker_names)}</p>"

            subject = f'Reminder: {service_type} Tomorrow - {date_only}'

            text_body = (
                f"{business_name}\n\n"
                f"Hi {customer_name},\n\n"
                f"Reminder: your {service_type} is tomorrow.\n"
                f"Date & Time: {time_str}\n"
                f"{'Assigned: ' + ', '.join(worker_names) if worker_names else ''}\n\n"
                f"To cancel or reschedule, please contact us.\n\n"
                f"Best regards,\n{business_name}"
            ).strip()

            html_body = f"""
<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);padding:25px;text-align:center;border-radius:12px 12px 0 0;">
        <div style="font-size:24px;font-weight:800;color:white;">{business_name}</div>
    </div>
    <div style="background:white;padding:25px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;">
        <h2 style="color:#d97706;margin:0 0 15px;">Appointment Reminder</h2>
        <p>Hi {customer_name},</p>
        <p>This is a friendly reminder about your appointment tomorrow:</p>
        <div style="background:#fffbeb;border-left:4px solid #f59e0b;padding:15px;margin:20px 0;border-radius:0 8px 8px 0;">
            <p style="margin:5px 0;"><strong>Service:</strong> {service_type}</p>
            <p style="margin:5px 0;"><strong>Date & Time:</strong> {time_str}</p>
            {worker_line}
        </div>
        <p>To cancel or reschedule, please contact us.</p>
        <p style="margin-top:25px;">Best regards,<br><strong>{business_name}</strong></p>
    </div>
</div></body></html>""".strip()

            return self._send_email(to_email, subject, html_body, text_body, business_name)
        except Exception as e:
            print(f"[ERROR] Failed to send day-before reminder email: {e}")
            return False

    def send_invoice(self, to_email: str, customer_name: str, service_type: str, 
                    charge: float, appointment_time: datetime = None,
                    stripe_payment_link: str = None, job_address: str = None,
                    invoice_number: str = None, bank_details: dict = None,
                    revolut_phone: str = None, add_bank_details: bool = False, 
                    add_revolut_phone: bool = False, company_name: str = None,
                    company_email: str = None, company_phone: str = None) -> bool:
        """
        Send a professional invoice email with optional Stripe payment link
        
        Args:
            to_email: Recipient email address
            service_type: Type of service performed
            charge: Amount to charge
            appointment_time: Appointment datetime for the job (optional)
            stripe_payment_link: Stripe payment URL (optional)
            job_address: Address where service was performed (optional)
            invoice_number: Unique invoice number (optional)
            company_name: Business name to show on invoice
            company_email: Business email for contact
            company_phone: Business phone for contact
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.configured:
            print("[ERROR] Email service not configured")
            return False
        
        try:
            from src.services.database import get_database
            from src.services.settings_manager import get_settings_manager
            from src.utils.config import config
            from datetime import datetime as dt
            
            business_name = company_name or 'Your Business'
            business_phone = company_phone or ''
            business_email = company_email or ''
            business_website = ''
            business_city = ''
            
            try:
                # Use SettingsManager to get additional business details if not provided
                settings_mgr = get_settings_manager()
                settings = settings_mgr.get_business_settings()
                if settings:
                    # Only override if not already provided by caller
                    if not company_name and settings.get('business_name'):
                        business_name = settings.get('business_name')
                    if not company_phone:
                        business_phone = settings.get('phone', '') or settings.get('business_phone', '')
                    if not company_email:
                        business_email = settings.get('email', '') or settings.get('business_email', '')
                    business_website = settings.get('website', '')
                    business_city = settings.get('city', '')
                    print(f"[EMAIL] Invoice loaded from database - Business: {business_name}, Email: {business_email}")
                else:
                    print("[WARNING] No business settings found in database")
            except Exception as db_error:
                print(f"[WARNING] Database error: {db_error}")
            
            # Final fallback
            if not business_name:
                business_name = 'Your Business'
                print("[WARNING] Using fallback business name")
            
            # Get logo URL from config
            logo_url = getattr(config, 'COMPANY_LOGO_URL', '') or ''
            
            # Use current date as invoice date, and show job date separately if provided
            invoice_date = dt.now().strftime('%B %d, %Y')
            job_date_str = appointment_time.strftime('%B %d, %Y at %I:%M %p') if appointment_time else None
            
            # Generate invoice number if not provided
            if not invoice_number:
                invoice_number = f"INV-{dt.now().strftime('%Y%m%d%H%M%S')}"
            
            # Payment link text
            payment_text = ""
            if stripe_payment_link:
                payment_text = f"\nPay securely online: {stripe_payment_link}"
            
            # Plain text version - build it step by step to avoid nested f-string issues
            location_line = f'Location: {job_address}\n' if job_address else ''
            job_date_line = f'Service Date: {job_date_str}\n' if job_date_str else ''
            online_payment = '\n- Online: Click the payment link above' if stripe_payment_link else ''
            
            bank_transfer_section = ''
            if bank_details and bank_details.get("iban"):
                bank_transfer_section = f'''

BANK TRANSFER DETAILS:
Account Holder: {bank_details["account_holder"]}
IBAN: {bank_details["iban"]}
BIC: {bank_details["bic"]}
Bank: {bank_details["bank_name"]}
Reference: {invoice_number}'''
            
            revolut_section = ''
            if revolut_phone:
                revolut_section = f'''

REVOLUT:
Send payment via Revolut to: {revolut_phone}
Reference: {invoice_number}'''
            
            # Build contact info
            contact_phone = f'Phone: {business_phone}\n' if business_phone else ''
            contact_email = f'Email: {business_email}\n' if business_email else ''
            
            text_body = f'''{business_name}
{'='*50}

Dear {customer_name},

Thank you for choosing {business_name}!

INVOICE DETAILS:
----------------
Invoice Number: {invoice_number}
Invoice Date: {invoice_date}
Service: {service_type}
{job_date_line}{location_line}
AMOUNT DUE: EUR {charge:.2f}
{payment_text}

Payment Methods:{online_payment}
- Cash or Card on completion{bank_transfer_section}{revolut_section}

If you have any questions about this invoice, please contact us:
{contact_phone}{contact_email}
Best regards,
{business_name}
{business_city}

---
This invoice was generated automatically.'''.strip()
            
            # Logo HTML (if URL provided)
            logo_html = ""
            if logo_url:
                logo_html = f'''
                <img src="{logo_url}" alt="{business_name}" style="max-width: 180px; max-height: 80px; margin-bottom: 20px;" />
                '''
            else:
                # Fallback to text logo with styling
                logo_html = f'''
                <div style="font-size: 28px; font-weight: 800; color: #1e40af; margin-bottom: 20px; letter-spacing: -0.5px;">
                    {business_name}
                </div>
                '''
            
            # Payment button HTML - always show a prominent pay section
            if stripe_payment_link:
                payment_button_html = f'''
                <div style="text-align: center; margin: 35px 0; padding: 25px; background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-radius: 12px; border: 2px solid #10b981;">
                    <p style="margin: 0 0 15px 0; font-size: 16px; color: #065f46; font-weight: 600;">Ready to pay? Click below for secure online payment:</p>
                    <a href="{stripe_payment_link}" 
                       style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                              color: white; text-decoration: none; padding: 18px 50px; font-size: 20px; 
                              font-weight: 700; border-radius: 10px; box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
                              letter-spacing: 0.5px;">
                        PAY NOW - EUR {charge:.2f}
                    </a>
                    <p style="margin-top: 15px; font-size: 13px; color: #047857;">
                        [Secure] Secure payment powered by Stripe
                    </p>
                </div>
                '''
            else:
                payment_button_html = f'''
                <div style="text-align: center; margin: 35px 0; padding: 25px; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 12px; border: 2px solid #f59e0b;">
                    <p style="margin: 0 0 10px 0; font-size: 18px; color: #92400e; font-weight: 700;">Amount Due: EUR {charge:.2f}</p>
                    <p style="margin: 0; font-size: 14px; color: #b45309;">
                        Please contact us to arrange payment via cash, card, or bank transfer.
                    </p>
                </div>
                '''
            
            # Pre-build conditional HTML sections to avoid nested f-strings (Python 3.13 compatibility)
            location_row_html = f'''<tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0;">
                                <span style="color: #64748b; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Location</span>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">
                                <span style="color: #1e293b; font-weight: 500; font-size: 14px;">{job_address}</span>
                            </td>
                        </tr>''' if job_address else ''
            
            # Job date row (service date)
            job_date_row_html = f'''<tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0;">
                                <span style="color: #64748b; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Service Date</span>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">
                                <span style="color: #1e293b; font-weight: 500; font-size: 15px;">{job_date_str}</span>
                            </td>
                        </tr>''' if job_date_str else ''
            
            # Bank transfer section
            if bank_details and bank_details.get('iban'):
                bank_transfer_html = f'''<div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 12px; padding: 20px; margin-bottom: 25px; border: 1px solid #93c5fd;">
                    <div style="font-weight: 700; color: #1e40af; font-size: 15px; margin-bottom: 12px;">
                        Bank Transfer Details
                    </div>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 6px 0; color: #64748b; font-size: 13px; width: 120px;">Account Holder:</td>
                            <td style="padding: 6px 0; color: #1e293b; font-weight: 600; font-size: 14px;">{bank_details['account_holder']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; color: #64748b; font-size: 13px;">IBAN:</td>
                            <td style="padding: 6px 0; color: #1e293b; font-weight: 600; font-size: 14px; font-family: 'Courier New', monospace; letter-spacing: 1px;">{bank_details['iban']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; color: #64748b; font-size: 13px;">BIC/SWIFT:</td>
                            <td style="padding: 6px 0; color: #1e293b; font-weight: 600; font-size: 14px; font-family: 'Courier New', monospace;">{bank_details['bic']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Bank:</td>
                            <td style="padding: 6px 0; color: #1e293b; font-weight: 600; font-size: 14px;">{bank_details['bank_name']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Reference:</td>
                            <td style="padding: 6px 0; color: #1e293b; font-weight: 700; font-size: 14px; font-family: 'Courier New', monospace;">{invoice_number}</td>
                        </tr>
                    </table>
                    <div style="margin-top: 10px; font-size: 12px; color: #6b7280;">Please use the reference number when making a bank transfer.</div>
                </div>'''
            else:
                bank_transfer_html = '''<div style="background: #fefce8; border-radius: 8px; padding: 16px; margin-bottom: 25px; border-left: 4px solid #eab308;">
                    <div style="font-weight: 600; color: #854d0e; font-size: 14px; margin-bottom: 8px;">
                        Other Payment Options
                    </div>
                    <div style="color: #a16207; font-size: 13px; line-height: 1.6;">
                        Cash or Card on completion
                    </div>
                </div>'''
            
            # Revolut section
            if revolut_phone:
                revolut_html = f'''<div style="background: linear-gradient(135deg, #f0f4ff 0%, #e8eeff 100%); border-radius: 12px; padding: 20px; margin-bottom: 25px; border: 1px solid #818cf8;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                        <div style="font-weight: 700; color: #4338ca; font-size: 15px;">
                            Pay via Revolut
                        </div>
                    </div>
                    <div style="color: #1e293b; font-size: 14px; line-height: 1.8;">
                        <div>Send to: <strong style="font-family: 'Courier New', monospace;">{revolut_phone}</strong></div>
                        <div>Reference: <strong style="font-family: 'Courier New', monospace;">{invoice_number}</strong></div>
                    </div>
                </div>'''
            else:
                revolut_html = ''
            
            # Contact links
            phone_link_html = f'<a href="tel:{business_phone}" style="color: #3b82f6; text-decoration: none; font-weight: 600; font-size: 14px; margin: 0 10px;">Phone: {business_phone}</a>' if business_phone else ''
            email_link_html = f'<a href="mailto:{business_email}" style="color: #3b82f6; text-decoration: none; font-weight: 600; font-size: 14px; margin: 0 10px;">Email: {business_email}</a>' if business_email else ''
            website_html = f'<div style="color: #64748b; font-size: 12px; margin-top: 8px;">{business_website}</div>' if business_website else ''
            
            # Now build the main HTML body
            html_body = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Main Card -->
        <div style="background: white; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); overflow: hidden;">
            
            <!-- Header with gradient -->
            <div style="background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); padding: 30px; text-align: center;">
                {logo_html.replace('color: #1e40af', 'color: white') if not logo_url else logo_html}
                <div style="font-size: 14px; color: rgba(255,255,255,0.9); margin-top: 5px;">Professional Trade Services</div>
            </div>
            
            <!-- Invoice Badge -->
            <div style="text-align: center; margin-top: -20px;">
                <span style="background: white; border: 3px solid #e5e7eb; padding: 10px 24px; border-radius: 30px; 
                             font-size: 14px; font-weight: 700; color: #374151; display: inline-block;
                             box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    INVOICE #{invoice_number}
                </span>
            </div>
            
            <!-- Content -->
            <div style="padding: 30px;">
                <p style="font-size: 16px; color: #374151; margin: 0 0 25px 0;">
                    Dear <strong>{customer_name}</strong>,
                </p>
                <p style="font-size: 15px; color: #6b7280; margin: 0 0 30px 0; line-height: 1.6;">
                    Thank you for choosing {business_name}. Please find your invoice details below.
                </p>
                
                <!-- Invoice Details Box -->
                <div style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 12px; padding: 24px; margin-bottom: 25px; border: 1px solid #e2e8f0;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0;">
                                <span style="color: #64748b; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Service</span>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">
                                <span style="color: #1e293b; font-weight: 600; font-size: 15px;">{service_type}</span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0;">
                                <span style="color: #64748b; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Invoice Date</span>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">
                                <span style="color: #1e293b; font-weight: 500; font-size: 15px;">{invoice_date}</span>
                            </td>
                        </tr>
                        {job_date_row_html}
                        {location_row_html}
                    </table>
                    
                    <!-- Amount Due -->
                    <div style="margin-top: 20px; padding-top: 20px; border-top: 2px dashed #cbd5e1; text-align: center;">
                        <div style="color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Amount Due</div>
                        <div style="font-size: 42px; font-weight: 800; color: #059669; letter-spacing: -1px;">EUR {charge:.2f}</div>
                    </div>
                </div>
                
                <!-- Payment Button -->
                {payment_button_html}
                
                <!-- Alternative Payment Methods -->
                {bank_transfer_html}
                
                {revolut_html}
                
                <!-- Contact Section -->
                <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0 0 15px 0;">Questions about this invoice?</p>
                    <div style="display: inline-block;">
                        {phone_link_html}
                        {email_link_html}
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="background: #1e293b; padding: 24px; text-align: center;">
                <div style="color: white; font-weight: 700; font-size: 16px; margin-bottom: 5px;">{business_name}</div>
                <div style="color: #94a3b8; font-size: 13px;">{business_city}</div>
                {website_html}
            </div>
        </div>
        
        <!-- Footer Note -->
        <div style="text-align: center; margin-top: 20px;">
            <p style="color: #9ca3af; font-size: 12px; margin: 0;">
                This invoice was generated automatically. Thank you for your business!
            </p>
        </div>
    </div>
</body>
</html>
            '''.strip()
            # Insert extra_payment_html if flags are set
            if add_bank_details or add_revolut_phone:
                print(f"[INFO] Sending invoice to {to_email} with bank details: {add_bank_details}, revolut: {add_revolut_phone}")
            
            # Send email using unified method (Resend or SMTP)
            subject = f'Invoice #{invoice_number} from {business_name}'
            success = self._send_email(to_email, subject, html_body, text_body, business_name)
            
            if success:
                print(f"[SUCCESS] Invoice email sent to {to_email} (Invoice #{invoice_number})")
            
            return success
            
        except Exception as e:
            try:
                import traceback
                error_str = traceback.format_exc()
                print(f"[ERROR] Failed to send invoice email: {e}")
                print(error_str)
            except Exception:
                pass
            return False

    def send_satisfaction_survey(self, to_email: str, customer_name: str,
                                 service_type: str, review_url: str,
                                 company_name: str = None,
                                 appointment_time=None) -> bool:
        """Send a customer satisfaction survey email after job completion."""
        if not self.configured:
            print("[ERROR] Email service not configured")
            return False

        try:
            from src.services.settings_manager import get_settings_manager

            business_name = company_name or 'Your Business'
            try:
                settings_mgr = get_settings_manager()
                settings = settings_mgr.get_business_settings()
                if settings and not company_name:
                    business_name = settings.get('business_name') or business_name
            except Exception:
                pass

            job_date_str = ''
            if appointment_time:
                from datetime import datetime as _dt
                if isinstance(appointment_time, str):
                    appointment_time = _dt.fromisoformat(appointment_time.replace('Z', '+00:00'))
                if hasattr(appointment_time, 'strftime'):
                    job_date_str = appointment_time.strftime('%B %d, %Y')

            date_line = f'Service Date: {job_date_str}\n' if job_date_str else ''
            text_body = f"""Hi {customer_name},

Thank you for choosing {business_name}!

We recently completed your {service_type} job and would love to hear how it went.
{date_line}
Your feedback helps us improve and means a lot to our team.

Please take a moment to leave a quick review:
{review_url}

Thank you,
{business_name}"""

            date_row_html = ''
            if job_date_str:
                date_row_html = f'<p style="color:#6b7280;font-size:14px;margin:0 0 20px;">Service date: {job_date_str}</p>'

            html_body = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background-color:#f3f4f6;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
<div style="background:white;border-radius:16px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);overflow:hidden;">
  <div style="background:linear-gradient(135deg,#059669 0%,#10b981 100%);padding:35px;text-align:center;">
    <h1 style="color:white;margin:0;font-size:22px;font-weight:700;">Job Complete!</h1>
    <p style="color:rgba(255,255,255,0.9);margin:8px 0 0;font-size:14px;">We'd love to hear your feedback</p>
  </div>
  <div style="padding:30px;">
    <p style="font-size:16px;color:#374151;margin:0 0 8px;">Hi <strong>{customer_name}</strong>,</p>
    <p style="font-size:15px;color:#6b7280;margin:0 0 20px;line-height:1.6;">
      Thank you for choosing <strong>{business_name}</strong>! We recently completed your
      <strong>{service_type}</strong> job and would love to hear how it went.
    </p>
    {date_row_html}
    <p style="font-size:15px;color:#6b7280;margin:0 0 25px;line-height:1.6;">
      Your feedback helps us improve and means a lot to our team.
    </p>
    <div style="text-align:center;margin:30px 0;">
      <a href="{review_url}"
         style="display:inline-block;background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);
                color:white;text-decoration:none;padding:16px 44px;font-size:18px;
                font-weight:700;border-radius:10px;box-shadow:0 4px 14px rgba(245,158,11,0.4);
                letter-spacing:0.3px;">
        ⭐ Leave a Review
      </a>
    </div>
    <p style="text-align:center;font-size:13px;color:#9ca3af;margin:20px 0 0;">
      It only takes 30 seconds — we really appreciate it!
    </p>
  </div>
  <div style="background:#1e293b;padding:20px;text-align:center;">
    <div style="color:white;font-weight:700;font-size:15px;">{business_name}</div>
    <div style="color:#94a3b8;font-size:12px;margin-top:4px;">Thank you for your business!</div>
  </div>
</div>
</div>
</body>
</html>'''

            subject = f'How was your {service_type}? — {business_name}'
            success = self._send_email(to_email, subject, html_body, text_body, business_name)
            if success:
                print(f"[SUCCESS] Satisfaction survey sent to {to_email}")
            return success
        except Exception as e:
            print(f"[ERROR] Failed to send satisfaction survey: {e}")
            return False


# Global instance
_email_service = None


def get_email_service() -> EmailReminderService:
    """Get or create global email service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailReminderService()
    return _email_service
