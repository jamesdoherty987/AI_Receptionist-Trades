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
            from src.services.settings_manager import get_settings_manager
            
            # Load business name from database
            business_name = 'Your Business'
            try:
                settings_mgr = get_settings_manager()
                settings = settings_mgr.get_business_settings()
                if settings and settings.get('business_name'):
                    business_name = settings['business_name']
            except Exception as e:
                print(f"⚠️ Could not load business name from database: {e}")
            
            # Format the appointment time
            time_str = appointment_time.strftime('%A, %B %d at %I:%M %p')
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Reminder: Your {service_type.title()} Appointment Tomorrow'
            msg['From'] = f'{business_name} <{self.from_email}>'
            msg['To'] = to_email
            
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
            <p style="margin: 5px 0;"><strong>📅 Date & Time:</strong> {time_str}</p>
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
                    charge: float, appointment_time: datetime = None,
                    stripe_payment_link: str = None, job_address: str = None,
                    invoice_number: str = None) -> bool:
        """
        Send a professional invoice email with optional Stripe payment link
        
        Args:
            to_email: Recipient email address
            customer_name: Customer's name
            service_type: Type of service performed
            charge: Amount to charge
            appointment_time: Appointment datetime (optional)
            stripe_payment_link: Stripe payment URL (optional)
            job_address: Address where service was performed (optional)
            invoice_number: Unique invoice number (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.configured:
            print("❌ Email service not configured")
            return False
        
        try:
            from src.services.database import get_database
            from src.services.settings_manager import get_settings_manager
            from src.utils.config import config
            
            # Load business info from database
            business_name = None
            business_phone = ''
            business_email = self.from_email
            business_website = ''
            business_city = ''
            
            try:
                # Use SettingsManager instead of direct database call
                settings_mgr = get_settings_manager()
                settings = settings_mgr.get_business_settings()
                if settings:
                    business_name = settings.get('business_name')
                    business_phone = settings.get('phone', '') or settings.get('business_phone', '')
                    business_email = settings.get('email', self.from_email) or settings.get('business_email', self.from_email)
                    business_website = settings.get('website', '')
                    business_city = settings.get('city', '')
                    print(f"📧 Invoice loaded from database - Business: {business_name}")
                else:
                    print("⚠️ No business settings found in database")
            except Exception as db_error:
                print(f"⚠️ Database error: {db_error}")
                import traceback
                traceback.print_exc()
            
            # Final fallback if database didn't work
            if not business_name:
                business_name = 'Your Business'
                print("⚠️ Using fallback business name")
            
            # Get logo URL from config
            logo_url = getattr(config, 'COMPANY_LOGO_URL', '') or ''
            
            # Format the date if provided
            date_str = appointment_time.strftime('%A, %B %d, %Y') if appointment_time else 'Recent service'
            
            # Generate invoice number if not provided
            if not invoice_number:
                from datetime import datetime as dt
                invoice_number = f"INV-{dt.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Invoice #{invoice_number} from {business_name}'
            msg['From'] = f'{business_name} <{self.from_email}>'
            msg['To'] = to_email
            
            # Payment link text
            payment_text = ""
            if stripe_payment_link:
                payment_text = f"\nPay securely online: {stripe_payment_link}"
            
            # Plain text version
            text_body = f"""
{business_name}
Invoice #{invoice_number}
{'='*50}

Dear {customer_name},

Thank you for choosing {business_name}!

INVOICE DETAILS:
----------------
Invoice Number: {invoice_number}
Service: {service_type}
Date: {date_str}
{f'Location: {job_address}' if job_address else ''}

AMOUNT DUE: €{charge:.2f}
{payment_text}

Payment Methods:
- Online: Click the payment link above
- Cash or Card on completion
- Bank Transfer

If you have any questions about this invoice, please contact us:
Phone: {business_phone}
Email: {business_email}

Best regards,
{business_name}
{business_city}

---
This invoice was generated automatically.
            """.strip()
            
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
                        💳 PAY NOW - €{charge:.2f}
                    </a>
                    <p style="margin-top: 15px; font-size: 13px; color: #047857;">
                        🔒 Secure payment powered by Stripe
                    </p>
                </div>
                '''
            else:
                payment_button_html = f'''
                <div style="text-align: center; margin: 35px 0; padding: 25px; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 12px; border: 2px solid #f59e0b;">
                    <p style="margin: 0 0 10px 0; font-size: 18px; color: #92400e; font-weight: 700;">Amount Due: €{charge:.2f}</p>
                    <p style="margin: 0; font-size: 14px; color: #b45309;">
                        Please contact us to arrange payment via cash, card, or bank transfer.
                    </p>
                </div>
                '''
            
            # HTML version (professional design)
            html_body = f'''
<!DOCTYPE html>
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
                                <span style="color: #64748b; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Date</span>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">
                                <span style="color: #1e293b; font-weight: 500; font-size: 15px;">{date_str}</span>
                            </td>
                        </tr>
                        {f'''<tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0;">
                                <span style="color: #64748b; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Location</span>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">
                                <span style="color: #1e293b; font-weight: 500; font-size: 14px;">{job_address}</span>
                            </td>
                        </tr>''' if job_address else ''}
                    </table>
                    
                    <!-- Amount Due -->
                    <div style="margin-top: 20px; padding-top: 20px; border-top: 2px dashed #cbd5e1; text-align: center;">
                        <div style="color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Amount Due</div>
                        <div style="font-size: 42px; font-weight: 800; color: #059669; letter-spacing: -1px;">€{charge:.2f}</div>
                    </div>
                </div>
                
                <!-- Payment Button -->
                {payment_button_html}
                
                <!-- Alternative Payment Methods -->
                <div style="background: #fefce8; border-radius: 8px; padding: 16px; margin-bottom: 25px; border-left: 4px solid #eab308;">
                    <div style="font-weight: 600; color: #854d0e; font-size: 14px; margin-bottom: 8px;">
                        💡 Other Payment Options
                    </div>
                    <div style="color: #a16207; font-size: 13px; line-height: 1.6;">
                        Cash or Card on completion • Bank Transfer
                    </div>
                </div>
                
                <!-- Contact Section -->
                <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e5e7eb;">
                    <p style="color: #6b7280; font-size: 14px; margin: 0 0 15px 0;">Questions about this invoice?</p>
                    <div style="display: inline-block;">
                        {f'<a href="tel:{business_phone}" style="color: #3b82f6; text-decoration: none; font-weight: 600; font-size: 14px; margin: 0 10px;">📞 {business_phone}</a>' if business_phone else ''}
                        {f'<a href="mailto:{business_email}" style="color: #3b82f6; text-decoration: none; font-weight: 600; font-size: 14px; margin: 0 10px;">✉️ {business_email}</a>' if business_email else ''}
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="background: #1e293b; padding: 24px; text-align: center;">
                <div style="color: white; font-weight: 700; font-size: 16px; margin-bottom: 5px;">{business_name}</div>
                <div style="color: #94a3b8; font-size: 13px;">{business_city}</div>
                {f'<div style="color: #64748b; font-size: 12px; margin-top: 8px;">{business_website}</div>' if business_website else ''}
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
            
            print(f"✅ Invoice email sent to {to_email} (Invoice #{invoice_number})")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send invoice email: {e}")
            import traceback
            traceback.print_exc()
            return False


# Global instance
_email_service = None


def get_email_service() -> EmailReminderService:
    """Get or create global email service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailReminderService()
    return _email_service
