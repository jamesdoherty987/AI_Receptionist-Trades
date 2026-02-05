"""
Google Calendar API integration for appointment management
"""
import os
import json
import time
import socket
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from src.utils.config import config

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("⚠️ Google Calendar libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")


# If modifying these scopes, delete the file token.json
SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarService:
    """Manages Google Calendar API interactions"""
    
    def __init__(self, credentials_path: str = None, 
                 token_path: str = None,
                 calendar_id: str = None,
                 timezone: str = None):
        """
        Initialize Google Calendar service
        
        Args:
            credentials_path: Path to Google OAuth credentials JSON
            token_path: Path to store OAuth token
            calendar_id: Calendar ID to use (default: "primary")
            timezone: Timezone for calendar events (default: Europe/Dublin)
        """
        self.credentials_path = credentials_path or config.GOOGLE_CALENDAR_CREDENTIALS
        self.token_path = token_path or config.GOOGLE_CALENDAR_TOKEN
        self.calendar_id = calendar_id or config.GOOGLE_CALENDAR_ID
        self.timezone = timezone or config.CALENDAR_TIMEZONE
        self.service = None
        
        if not GOOGLE_AVAILABLE:
            raise ImportError("Google Calendar libraries not installed")
    
    def _execute_with_retry(self, request, max_retries=3):
        """Execute a Google API request with retry logic for connection errors"""
        for attempt in range(max_retries):
            try:
                return request.execute()
            except (ConnectionResetError, socket.error, OSError) as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    print(f"⚠️ Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"🔄 Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    # Re-authenticate to get fresh connection
                    self.authenticate()
                else:
                    print(f"❌ Connection failed after {max_retries} attempts")
                    raise
            except HttpError as e:
                # Don't retry on HTTP errors (404, 403, etc.)
                raise
    
    def authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    # Token is invalid/revoked - delete it and re-authenticate
                    print(f"⚠️ Token refresh failed: {e}")
                    print("🔄 Deleting expired token and re-authenticating...")
                    if os.path.exists(self.token_path):
                        os.remove(self.token_path)
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Please download credentials.json from Google Cloud Console"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('calendar', 'v3', credentials=creds)
        print("✅ Google Calendar authenticated")
    
    def book_appointment(self, summary: str, start_time: datetime, 
                        duration_minutes: int = None, 
                        description: str = "", 
                        location: str = "",
                        phone_number: str = "") -> Optional[Dict[str, Any]]:
        """
        Book a new appointment
        
        Args:
            summary: Appointment title
            start_time: Start datetime
            duration_minutes: Duration in minutes
            description: Appointment description
            location: Appointment location
            phone_number: Customer's phone number
            
        Returns:
            Event details or None if failed
        """
        if duration_minutes is None:
            duration_minutes = config.APPOINTMENT_SLOT_DURATION
        
        if not self.service:
            self.authenticate()
        
        try:
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Add phone number to description if provided
            full_description = description
            if phone_number:
                full_description = f"Phone: {phone_number}\n\n{description}" if description else f"Phone: {phone_number}"
            
            event = {
                'summary': summary,
                'location': location,
                'description': full_description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': self.timezone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': self.timezone,
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
            }
            
            request = self.service.events().insert(
                calendarId=self.calendar_id, 
                body=event
            )
            event = self._execute_with_retry(request)
            
            print(f"✅ Appointment booked: {event.get('htmlLink')}")
            return event
            
        except HttpError as error:
            print(f"❌ Error booking appointment: {error}")
            return None
    
    def get_upcoming_appointments(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        Get upcoming appointments
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming events
        """
        if not self.service:
            self.authenticate()
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            end_date = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            request = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=now,
                timeMax=end_date,
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            )
            events_result = self._execute_with_retry(request)
            
            events = events_result.get('items', [])
            return events
            
        except HttpError as error:
            print(f"❌ Error fetching appointments: {error}")
            return []
    
    def cancel_appointment(self, event_id: str) -> bool:
        """
        Cancel an appointment
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            self.authenticate()
        
        try:
            request = self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            )
            self._execute_with_retry(request)
            
            print(f"✅ Appointment cancelled: {event_id}")
            return True
            
        except HttpError as error:
            print(f"❌ Error cancelling appointment: {error}")
            return False
    
    def reschedule_appointment(self, event_id: str, new_start_time: datetime) -> Optional[Dict[str, Any]]:
        """
        Reschedule an existing appointment
        
        Args:
            event_id: Google Calendar event ID
            new_start_time: New start datetime
            
        Returns:
            Updated event details or None if failed
        """
        if not self.service:
            self.authenticate()
        
        try:
            # Get the existing event
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            # Calculate duration
            old_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
            old_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
            duration = old_end - old_start
            
            # Update times
            new_end_time = new_start_time + duration
            event['start']['dateTime'] = new_start_time.isoformat()
            event['end']['dateTime'] = new_end_time.isoformat()
            
            # Update the event
            request = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            )
            updated_event = self._execute_with_retry(request)
            
            print(f"✅ Appointment rescheduled: {updated_event.get('htmlLink')}")
            return updated_event
            
        except HttpError as error:
            print(f"❌ Error rescheduling appointment: {error}")
            return None
    
    def check_availability(self, start_time: datetime, duration_minutes: int = None) -> bool:
        """
        Check if a time slot is available (no conflicts)
        
        Args:
            start_time: Requested start time
            duration_minutes: Duration in minutes
            
        Returns:
            True if available, False if busy
        """
        if duration_minutes is None:
            duration_minutes = config.APPOINTMENT_SLOT_DURATION
        
        if not self.service:
            self.authenticate()
        
        # Check if the requested time is in the past
        now = datetime.now()
        if start_time < now:
            print(f"⚠️ Requested time {start_time.strftime('%I:%M %p')} is in the past (current time: {now.strftime('%I:%M %p')})")
            return False
        
        try:
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Get all events for the day to check for conflicts
            day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            # Format times in RFC3339 format with Z suffix for UTC
            time_min = day_start.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            time_max = day_end.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            
            # Query for events on that day
            request = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            )
            events_result = self._execute_with_retry(request)
            
            events = events_result.get('items', [])
            
            # Check for overlapping events
            conflicts = []
            for event in events:
                event_start_str = event.get('start', {}).get('dateTime')
                event_end_str = event.get('end', {}).get('dateTime')
                
                if not event_start_str or not event_end_str:
                    continue
                
                # Parse event times
                try:
                    # Remove timezone info for comparison
                    event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00')).replace(tzinfo=None)
                except:
                    continue
                
                # Check for overlap: events overlap if one starts before the other ends
                if event_start < end_time and event_end > start_time:
                    conflicts.append(event)
            
            if len(conflicts) > 0:
                print(f"⚠️ Found {len(conflicts)} conflicting event(s) in this time slot:")
                for event in conflicts:
                    event_start = event.get('start', {}).get('dateTime', 'Unknown')
                    print(f"   - {event.get('summary', 'Untitled')} at {event_start}")
            
            # If there are any overlapping events, it's busy
            return len(conflicts) == 0
            
            # If there are any events in this time slot, it's busy
            return len(events) == 0
            
        except HttpError as error:
            print(f"❌ Error checking availability: {error}")
            return False  # Assume busy if we can't check
    
    def find_next_appointment_by_name(self, customer_name: str) -> Optional[Dict[str, Any]]:
        """
        Find the next future appointment for a customer by name only
        Used when customer can't remember their appointment time
        
        Args:
            customer_name: Customer name to search for (case-insensitive)
            
        Returns:
            Next future appointment event dict if found, None otherwise
        """
        if not self.service:
            self.authenticate()
        
        if not customer_name:
            return None
        
        try:
            # Search from now into the future (30 days)
            time_min = datetime.utcnow().isoformat() + 'Z'
            time_max = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
            
            print(f"\n🔍 Searching for next future appointment:")
            print(f"   Customer: {customer_name}")
            print(f"   Search range: {time_min} to {time_max}")
            
            request = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            )
            events_result = self._execute_with_retry(request)
            
            events = events_result.get('items', [])
            print(f"   Found {len(events)} future events")
            
            # Search through events for first match
            customer_lower = customer_name.lower().strip()
            for event in events:
                event_summary = event.get('summary', '').lower()
                event_start_str = event.get('start', {}).get('dateTime', 'N/A')
                
                # Check if customer name appears in summary
                if customer_lower in event_summary:
                    print(f"✅ Found next appointment: {event.get('summary')} at {event_start_str}")
                    return event
                    
                # Also check split format ("Service - Name")
                summary_parts = event_summary.split(' - ')
                if len(summary_parts) > 1:
                    name_part = summary_parts[-1].strip()
                    if customer_lower in name_part or name_part in customer_lower:
                        print(f"✅ Found next appointment: {event.get('summary')} at {event_start_str}")
                        return event
            
            print(f"❌ No future appointments found for {customer_name}")
            return None
            
        except HttpError as error:
            print(f"❌ Error searching for appointment: {error}")
            return None
    
    def find_appointment_by_details(self, customer_name: str = None, appointment_time: datetime = None, days_to_search: int = 30) -> Optional[Dict[str, Any]]:
        """
        Find an appointment by customer name and/or appointment time
        
        Args:
            customer_name: Customer name to search for (case-insensitive)
            appointment_time: Appointment datetime to search for
            days_to_search: Number of days to search (backward and forward)
            
        Returns:
            Event dict if found, None otherwise
        """
        if not self.service:
            self.authenticate()
        
        try:
            # Search from past appointments to future
            time_min = (datetime.utcnow() - timedelta(days=days_to_search)).isoformat() + 'Z'
            time_max = (datetime.utcnow() + timedelta(days=days_to_search)).isoformat() + 'Z'
            
            print(f"\n🔍 Searching for appointment:")
            print(f"   Customer: {customer_name}")
            print(f"   Time: {appointment_time.strftime('%Y-%m-%d %H:%M') if appointment_time else 'any'}")
            print(f"   Search range: {time_min} to {time_max}")
            
            request = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            )
            events_result = self._execute_with_retry(request)
            
            events = events_result.get('items', [])
            print(f"   Found {len(events)} events in range")
            
            # Search through events
            for event in events:
                event_summary = event.get('summary', '')
                event_start_str = event.get('start', {}).get('dateTime', 'N/A')
                print(f"   Checking: '{event_summary}' at {event_start_str}")
                
                # Check if customer name matches (case-insensitive, partial match)
                name_match = False
                if customer_name:
                    summary = event.get('summary', '').lower() if event.get('summary') else ''
                    customer_lower = customer_name.lower().strip() if customer_name else ''
                    # Check if name appears anywhere in summary (handles "Service - Name" format)
                    if customer_lower in summary:
                        name_match = True
                        print(f"      ✓ Name match: '{customer_lower}' in '{summary}'")
                    else:
                        # Also try splitting on " - " and checking the name part
                        summary_parts = summary.split(' - ')
                        if len(summary_parts) > 1:
                            name_part = summary_parts[-1].strip()  # Get the last part (should be name)
                            if customer_lower in name_part or name_part in customer_lower:
                                name_match = True
                                print(f"      ✓ Name match (split): '{customer_lower}' matches '{name_part}'")
                            else:
                                print(f"      ✗ Name mismatch: '{customer_lower}' not in '{summary}' or '{name_part}'")
                        else:
                            print(f"      ✗ Name mismatch: '{customer_lower}' not in '{summary}'")
                else:
                    name_match = True  # If no name provided, consider it a match
                
                # Check if time matches (within same hour)
                time_match = False
                if appointment_time:
                    event_start_str = event.get('start', {}).get('dateTime')
                    if event_start_str:
                        try:
                            event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                            # Match if same day and hour
                            if (event_start.date() == appointment_time.date() and 
                                event_start.hour == appointment_time.hour):
                                time_match = True
                                print(f"      ✓ Time match: {event_start.strftime('%Y-%m-%d %H:%M')} == {appointment_time.strftime('%Y-%m-%d %H:%M')}")
                            else:
                                print(f"      ✗ Time mismatch: {event_start.strftime('%Y-%m-%d %H:%M')} != {appointment_time.strftime('%Y-%m-%d %H:%M')}")
                        except Exception as e:
                            print(f"      ✗ Time parse error: {e}")
                else:
                    time_match = True  # If no time provided, consider it a match
                
                # Return first match where both criteria match
                if name_match and time_match:
                    print(f"✅ Found appointment: {event.get('summary')} at {event.get('start', {}).get('dateTime')}")
                    return event
            
            print(f"❌ No appointment found for {customer_name or 'unknown'} at {appointment_time.strftime('%B %d at %I:%M %p') if appointment_time else 'any time'}")
            return None
            
        except HttpError as error:
            print(f"❌ Error searching for appointment: {error}")
            return None
    
    def get_available_slots_for_day(self, target_date: datetime) -> List[datetime]:
        """
        Get all available time slots for a specific day
        
        Args:
            target_date: The date to check (time component will be ignored)
            
        Returns:
            List of all available datetime slots during business hours (Monday-Friday only)
        """
        if not self.service:
            self.authenticate()
        
        # Check if it's a closed day (use dynamic business days)
        try:
            business_days = config.get_business_days_indices()
            is_closed = target_date.weekday() not in business_days
        except:
            is_closed = target_date.weekday() not in config.BUSINESS_DAYS
        
        if is_closed:
            day_name = target_date.strftime('%A')
            print(f"⏭️ Skipping closed day: {target_date.strftime('%A, %B %d')}")
            return []  # No slots on closed days
        
        available_slots = []
        now = datetime.now()
        
        # Get dynamic business hours from database
        hours = config.get_business_hours()
        business_start = hours['start']
        business_end = hours['end']
        
        # Calculate last appointment time (appointment ends at business_end)
        # For 60-minute appointments, last start time is business_end - 1
        duration_hours = config.APPOINTMENT_SLOT_DURATION // 60
        last_start_hour = business_end - duration_hours
        
        # Check every hour during business hours (up to last_start_hour)
        for hour in range(business_start, last_start_hour + 1):
            slot_time = target_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            # Skip slots that are in the past (for today only)
            if slot_time.date() == now.date() and slot_time <= now:
                print(f"⏭️ Skipping past slot: {slot_time.strftime('%I:%M %p')}")
                continue
            
            if self.check_availability(slot_time, duration_minutes=config.APPOINTMENT_SLOT_DURATION):
                available_slots.append(slot_time)
        
        return available_slots
    
    def get_alternative_times(self, preferred_time: datetime, days_to_check: int = 3) -> List[datetime]:
        """
        Get alternative available time slots near the preferred time
        
        Args:
            preferred_time: The originally requested time
            days_to_check: Number of days to check for alternatives
            
        Returns:
            List of available datetime slots (within business hours)
        """
        if not self.service:
            self.authenticate()
        
        alternatives = []
        
        # FIRST: Check other times on the SAME day (before and after requested time)
        same_day_slots = self.get_available_slots_for_day(preferred_time)
        # Filter out the requested time itself
        same_day_slots = [slot for slot in same_day_slots if slot.hour != preferred_time.hour]
        
        # Prioritize times close to the requested time
        same_day_slots.sort(key=lambda x: abs(x.hour - preferred_time.hour))
        
        # Add up to 3 same-day alternatives
        alternatives.extend(same_day_slots[:3])
        
        # SECOND: If we need more alternatives, check nearby days
        if len(alternatives) < 3:
            # Get dynamic business hours
            hours = config.get_business_hours()
            business_start = hours['start']
            business_end = hours['end']
            
            for day_offset in range(1, days_to_check + 1):
                # Check same time on different days
                alt_time = preferred_time + timedelta(days=day_offset)
                if business_start <= alt_time.hour < business_end:
                    if self.check_availability(alt_time, duration_minutes=config.APPOINTMENT_SLOT_DURATION):
                        if alt_time not in alternatives:
                            alternatives.append(alt_time)
                            if len(alternatives) >= 3:
                                break
        
        return alternatives[:3]  # Return max 3 alternatives


# Singleton instance
_calendar_service: Optional[GoogleCalendarService] = None


def get_calendar_service() -> Optional[GoogleCalendarService]:
    """Get or create Google Calendar service instance"""
    global _calendar_service
    
    # Check if Google Calendar is enabled in config
    if not config.USE_GOOGLE_CALENDAR:
        return None
    
    if not GOOGLE_AVAILABLE:
        return None
    
    if _calendar_service is None:
        try:
            _calendar_service = GoogleCalendarService()
            _calendar_service.authenticate()
        except Exception as e:
            print(f"⚠️ Could not initialize Google Calendar: {e}")
            return None
    
    return _calendar_service
