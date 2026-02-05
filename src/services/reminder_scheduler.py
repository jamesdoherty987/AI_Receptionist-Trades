"""
Appointment Reminder Scheduler
Checks for appointments 24 hours ahead and sends reminders via email or SMS
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set, Dict, Any
import re

from src.services.google_calendar import GoogleCalendarService
from src.services.sms_reminder import get_sms_service
from src.services.email_reminder import get_email_service
from src.utils.config import config


class ReminderScheduler:
    """Schedule and send appointment reminders"""
    
    def __init__(self):
        """Initialize reminder scheduler"""
        # Only initialize calendar if enabled
        self.calendar = None
        if config.USE_GOOGLE_CALENDAR:
            try:
                self.calendar = GoogleCalendarService()
            except Exception as e:
                print(f"⚠️ Could not initialize calendar service: {e}")
        
        self.reminder_method = config.REMINDER_METHOD.lower()
        
        # Initialize only the service we need
        self.sms_service = None
        self.email_service = None
        
        if self.reminder_method == "sms":
            self.sms_service = get_sms_service()
            print("📱 Using SMS reminders")
        else:
            self.email_service = get_email_service()
            print("📧 Using email reminders (default)")
        
        # Track sent reminders to avoid duplicates
        self.sent_reminders_file = Path("config/sent_reminders.json")
        self.sent_reminders: Set[str] = self._load_sent_reminders()
    
    def _load_sent_reminders(self) -> Set[str]:
        """Load tracking of already-sent reminders"""
        if self.sent_reminders_file.exists():
            try:
                with open(self.sent_reminders_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('sent', []))
            except Exception as e:
                print(f"⚠️ Error loading sent reminders: {e}")
        return set()
    
    def _save_sent_reminders(self):
        """Save tracking of sent reminders"""
        try:
            self.sent_reminders_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sent_reminders_file, 'w') as f:
                json.dump({'sent': list(self.sent_reminders)}, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving sent reminders: {e}")
    
    def _extract_phone_from_description(self, description: str) -> str:
        """
        Extract phone number from event description
        
        Args:
            description: Event description text
            
        Returns:
            Phone number or empty string if not found
        """
        if not description:
            return ""
        
        # Look for "Phone: +1234567890" pattern
        phone_match = re.search(r'Phone:\s*([\+\d\s\-\(\)]+)', description)
        if phone_match:
            phone = phone_match.group(1).strip()
            return phone
        
        return ""
    
    def _extract_email_from_description(self, description: str) -> str:
        """
        Extract email address from event description
        
        Args:
            description: Event description text
            
        Returns:
            Email address or empty string if not found
        """
        if not description:
            return ""
        
        # Look for "Email: user@example.com" pattern
        email_match = re.search(r'Email:\s*([\w\.-]+@[\w\.-]+\.\w+)', description)
        if email_match:
            return email_match.group(1).strip()
        
        return ""
    
    def _extract_customer_name_from_summary(self, summary: str) -> str:
        """
        Extract customer name from event summary
        Format: "Service - Customer Name"
        
        Args:
            summary: Event summary/title
            
        Returns:
            Customer name or "Customer" if not found
        """
        if not summary:
            return "Customer"
        
        # Try to extract name after dash
        parts = summary.split(' - ')
        if len(parts) >= 2:
            return parts[1].strip()
        
        return "Customer"
    
    def _extract_service_from_summary(self, summary: str) -> str:
        """
        Extract service type from event summary
        Format: "Service - Customer Name"
        
        Args:
            summary: Event summary/title
            
        Returns:
            Service type or "appointment"
        """
        if not summary:
            return "appointment"
        
        # Try to extract service before dash
        parts = summary.split(' - ')
        if len(parts) >= 1:
            return parts[0].strip().lower()
        
        return "appointment"
    
    def check_and_send_reminders(self):
        """
        Check for appointments 24 hours ahead and send reminders
        This should be called periodically (e.g., every hour)
        """
        print("\n" + "="*60)
        print("🔔 Checking for appointments needing reminders...")
        print("="*60)
        
        # Skip if calendar is disabled
        if not self.calendar:
            print("⚠️ Calendar service is disabled - skipping reminder check")
            return
        
        # Get appointments for next 2 days
        upcoming = self.calendar.get_upcoming_appointments(days_ahead=2)
        
        if not upcoming:
            print("📅 No upcoming appointments found")
            return
        
        now = datetime.utcnow()
        target_time_min = now + timedelta(hours=23)
        target_time_max = now + timedelta(hours=25)
        
        reminders_sent = 0
        
        for event in upcoming:
            try:
                event_id = event.get('id')
                summary = event.get('summary', '')
                description = event.get('description', '')
                
                # Parse start time
                start = event.get('start', {})
                start_time_str = start.get('dateTime', start.get('date'))
                if not start_time_str:
                    continue
                
                # Parse datetime
                if 'T' in start_time_str:
                    event_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    # All-day event, skip reminders
                    continue
                
                # Remove timezone info for comparison
                event_time_naive = event_time.replace(tzinfo=None)
                
                # Check if this event is in the 24-hour reminder window
                if not (target_time_min <= event_time_naive <= target_time_max):
                    continue
                
                # Check if we already sent a reminder for this event
                reminder_key = f"{event_id}_{start_time_str}"
                if reminder_key in self.sent_reminders:
                    print(f"⏭️ Already sent reminder for: {summary}")
                    continue
                
                # Extract contact info based on reminder method
                if self.reminder_method == "sms":
                    phone = self._extract_phone_from_description(description)
                    if not phone:
                        print(f"⚠️ No phone number for appointment: {summary}")
                        continue
                    contact_info = phone
                else:  # email
                    email = self._extract_email_from_description(description)
                    if not email:
                        print(f"⚠️ No email address for appointment: {summary}")
                        continue
                    contact_info = email
                
                # Extract details
                customer_name = self._extract_customer_name_from_summary(summary)
                service_type = self._extract_service_from_summary(summary)
                
                # Send reminder
                print(f"\n📬 Sending reminder for:")
                print(f"   Customer: {customer_name}")
                print(f"   Service: {service_type}")
                print(f"   Time: {event_time_naive.strftime('%B %d at %I:%M %p')}")
                print(f"   Contact: {contact_info}")
                
                # Send via appropriate method
                if self.reminder_method == "sms":
                    success = self.sms_service.send_reminder(
                        to_number=contact_info,
                        appointment_time=event_time_naive,
                        customer_name=customer_name,
                        service_type=service_type
                    )
                else:  # email
                    phone = self._extract_phone_from_description(description)
                    success = self.email_service.send_reminder(
                        to_email=contact_info,
                        appointment_time=event_time_naive,
                        customer_name=customer_name,
                        service_type=service_type,
                        phone_number=phone
                    )
                
                if success:
                    # Mark as sent
                    self.sent_reminders.add(reminder_key)
                    self._save_sent_reminders()
                    reminders_sent += 1
                    print(f"   ✅ Reminder sent successfully")
                else:
                    print(f"   ❌ Failed to send reminder")
            
            except Exception as e:
                print(f"❌ Error processing event {event.get('id')}: {e}")
                continue
        
        print("\n" + "="*60)
        print(f"📊 Reminders sent: {reminders_sent}")
        print("="*60 + "\n")


def run_reminder_check():
    """Standalone function to run reminder check"""
    scheduler = ReminderScheduler()
    scheduler.check_and_send_reminders()


if __name__ == "__main__":
    # Can be run directly for testing
    run_reminder_check()
