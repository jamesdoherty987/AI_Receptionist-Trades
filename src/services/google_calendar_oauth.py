"""
Google Calendar OAuth2 flow for per-company calendar integration.
Uses web-based OAuth (not InstalledAppFlow) so it works in production.
Stores tokens in the companies table (google_credentials_json column).
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from src.utils.config import config

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Cache of per-company calendar services
_company_calendar_cache: Dict[int, 'CompanyGoogleCalendar'] = {}


def _get_client_config() -> dict:
    """Build OAuth client config from env vars."""
    client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ValueError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set")
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": []
        }
    }


def get_oauth_redirect_uri() -> str:
    """Get the OAuth redirect URI based on PUBLIC_URL."""
    base = config.PUBLIC_URL or 'http://localhost:5000'
    return f"{base.rstrip('/')}/api/google-calendar/callback"


def start_oauth_flow(company_id: int) -> str:
    """Start the OAuth flow — returns the authorization URL to redirect the user to."""
    client_config = _get_client_config()
    redirect_uri = get_oauth_redirect_uri()

    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=str(company_id)
    )
    return authorization_url


def handle_oauth_callback(authorization_response: str, company_id: int, db) -> bool:
    """Exchange the auth code for tokens and store them in the DB."""
    client_config = _get_client_config()
    redirect_uri = get_oauth_redirect_uri()

    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    flow.fetch_token(authorization_response=authorization_response)

    creds = flow.credentials
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes) if creds.scopes else SCOPES,
        'expiry': creds.expiry.isoformat() if creds.expiry else None
    }

    # Store in DB
    db.update_company(company_id,
                      google_credentials_json=json.dumps(token_data),
                      google_calendar_id='primary')

    # Clear cache so next call picks up new creds
    _company_calendar_cache.pop(company_id, None)

    logger.info(f"[GCAL_OAUTH] Stored Google Calendar tokens for company {company_id}")
    return True


def disconnect_google_calendar(company_id: int, db) -> bool:
    """Remove stored Google Calendar credentials for a company."""
    db.update_company(company_id,
                      google_credentials_json=None,
                      google_calendar_id=None)
    _company_calendar_cache.pop(company_id, None)
    logger.info(f"[GCAL_OAUTH] Disconnected Google Calendar for company {company_id}")
    return True


def get_company_calendar_status(company_id: int, db) -> dict:
    """Check if a company has Google Calendar connected."""
    company = db.get_company(company_id)
    if not company:
        return {'connected': False}

    creds_json = company.get('google_credentials_json')
    if not creds_json:
        return {'connected': False}

    try:
        token_data = json.loads(creds_json)
        # Try to build credentials and check validity
        expiry = None
        if token_data.get('expiry'):
            try:
                expiry = datetime.fromisoformat(token_data['expiry'])
            except (ValueError, TypeError):
                pass
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes'),
            expiry=expiry
        )

        # If expired, try to refresh
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed token back to DB
                token_data['token'] = creds.token
                token_data['expiry'] = creds.expiry.isoformat() if creds.expiry else None
                db.update_company(company_id, google_credentials_json=json.dumps(token_data))
            except Exception as e:
                logger.warning(f"[GCAL_OAUTH] Token refresh failed for company {company_id}: {e}")
                return {'connected': False, 'error': 'Token expired and refresh failed'}

        # Get the calendar email for display
        calendar_email = None
        try:
            service = build('calendar', 'v3', credentials=creds)
            calendar = service.calendars().get(calendarId='primary').execute()
            calendar_email = calendar.get('summary', calendar.get('id', ''))
        except Exception:
            pass

        return {
            'connected': True,
            'calendar_id': company.get('google_calendar_id', 'primary'),
            'calendar_email': calendar_email
        }
    except Exception as e:
        logger.error(f"[GCAL_OAUTH] Error checking calendar status for company {company_id}: {e}")
        return {'connected': False, 'error': str(e)}


def get_company_google_calendar(company_id: int, db) -> Optional['CompanyGoogleCalendar']:
    """Get a Google Calendar service instance for a company, or None if not connected."""
    # Check cache first
    if company_id in _company_calendar_cache:
        cached = _company_calendar_cache[company_id]
        if cached.is_valid():
            return cached

    company = db.get_company(company_id)
    if not company:
        return None

    creds_json = company.get('google_credentials_json')
    if not creds_json:
        return None

    try:
        token_data = json.loads(creds_json)
        expiry = None
        if token_data.get('expiry'):
            try:
                expiry = datetime.fromisoformat(token_data['expiry'])
            except (ValueError, TypeError):
                pass
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes'),
            expiry=expiry
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_data['token'] = creds.token
            token_data['expiry'] = creds.expiry.isoformat() if creds.expiry else None
            db.update_company(company_id, google_credentials_json=json.dumps(token_data))

        calendar_id = company.get('google_calendar_id') or 'primary'
        service = build('calendar', 'v3', credentials=creds)

        cal = CompanyGoogleCalendar(service, calendar_id, company_id)
        _company_calendar_cache[company_id] = cal
        logger.info(f"[GCAL_OAUTH] Created Google Calendar service for company {company_id}")
        return cal
    except Exception as e:
        logger.error(f"[GCAL_OAUTH] Failed to create calendar for company {company_id}: {e}")
        _company_calendar_cache.pop(company_id, None)
        return None


class CompanyGoogleCalendar:
    """Thin wrapper around Google Calendar API for a specific company.
    Implements the same interface as DatabaseCalendarService so it can be
    used as a drop-in replacement in calendar_tools.py.
    """

    def __init__(self, service, calendar_id: str, company_id: int):
        self.service = service
        self.calendar_id = calendar_id
        self.company_id = company_id
        self._created_at = datetime.now()
        self.timezone = config.CALENDAR_TIMEZONE

    def is_valid(self) -> bool:
        """Check if this cached instance is still usable (max 50 min)."""
        age = (datetime.now() - self._created_at).total_seconds()
        return age < 3000  # refresh before the 1hr token expiry

    def _execute_with_retry(self, request, max_retries=3):
        """Execute a Google API request with retry logic."""
        import time
        for attempt in range(max_retries):
            try:
                return request.execute()
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise

    def book_appointment(self, summary: str, start_time, duration_minutes: int = 60,
                         description: str = '', phone_number: str = '') -> Optional[dict]:
        """Create a calendar event."""
        from datetime import timedelta

        # For multi-day jobs, calculate end time using business days (skip closed days)
        if duration_minutes > 1440:
            try:
                from src.utils.duration_utils import duration_to_business_days
                biz_days_needed = duration_to_business_days(duration_minutes, company_id=self.company_id)
                try:
                    biz_day_indices = config.get_business_days_indices(company_id=self.company_id)
                except Exception:
                    biz_day_indices = [0, 1, 2, 3, 4]
                try:
                    biz_hours = config.get_business_hours(company_id=self.company_id)
                    biz_end_hour = biz_hours.get('end', 17)
                except Exception:
                    biz_end_hour = 17
                # Walk forward counting only business days
                cur = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                counted = 0
                for _ in range(365):
                    if cur.weekday() in biz_day_indices:
                        counted += 1
                        if counted >= biz_days_needed:
                            break
                    cur += timedelta(days=1)
                end_time = cur.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
            except Exception:
                # Fallback to simple addition
                end_time = start_time + timedelta(minutes=duration_minutes)
        elif duration_minutes >= 480:
            # Full-day job: start at opening, end at closing time on the same day
            try:
                biz_hours = config.get_business_hours(company_id=self.company_id)
                biz_start_hour = biz_hours.get('start', 9)
                biz_end_hour = biz_hours.get('end', 17)
            except Exception:
                biz_start_hour = 9
                biz_end_hour = 17
            # Ensure start is at opening hour so the event doesn't span overnight
            start_time = start_time.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
            end_time = start_time.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
        else:
            end_time = start_time + timedelta(minutes=duration_minutes)

        full_description = description
        if phone_number:
            full_description += f"\n\nCustomer Phone: {phone_number}"

        event = {
            'summary': summary,
            'description': full_description.strip(),
            'start': {
                'dateTime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': self.timezone,
            },
            'end': {
                'dateTime': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': self.timezone,
            },
            'extendedProperties': {
                'private': {'bookedForYou': 'true'},
            },
        }

        request = self.service.events().insert(calendarId=self.calendar_id, body=event)
        created = self._execute_with_retry(request)
        logger.info(f"[GCAL] Created event: {created.get('id')} for company {self.company_id}")
        return created

    def check_availability(self, start_time, duration_minutes: int = 60) -> bool:
        """Check if a time slot is available."""
        from datetime import timedelta
        end_time = start_time + timedelta(minutes=duration_minutes)

        time_min = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        time_max = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        request = self.service.events().list(
            calendarId=self.calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            timeZone=self.timezone,
            singleEvents=True
        )
        result = self._execute_with_retry(request)
        events = result.get('items', [])
        return len(events) == 0

    def cancel_appointment(self, event_id: str) -> bool:
        """Delete a calendar event."""
        try:
            request = self.service.events().delete(
                calendarId=self.calendar_id, eventId=event_id)
            self._execute_with_retry(request)
            return True
        except Exception as e:
            logger.error(f"[GCAL] Cancel failed: {e}")
            return False

    def reschedule_appointment(self, event_id: str, new_start_time,
                               duration_minutes: int = None,
                               description: str = None,
                               summary: str = None) -> Optional[dict]:
        """Move an event to a new time, applying the same full-day/multi-day
        business-day logic used when creating events.
        Optionally updates the description in the same API call to avoid
        a race condition where a separate update_event_description could
        overwrite the corrected times with stale data."""
        from datetime import timedelta
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id, eventId=event_id).execute()

            # Calculate duration from existing event if not provided
            if not duration_minutes:
                old_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                old_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                duration_minutes = int((old_end - old_start).total_seconds() / 60)

            # Apply the same end-time logic as book_appointment so that
            # full-day and multi-day jobs don't stretch into nights/weekends.
            if duration_minutes > 1440:
                try:
                    from src.utils.duration_utils import duration_to_business_days
                    biz_days_needed = duration_to_business_days(duration_minutes, company_id=self.company_id)
                    try:
                        biz_day_indices = config.get_business_days_indices(company_id=self.company_id)
                    except Exception:
                        biz_day_indices = [0, 1, 2, 3, 4]
                    try:
                        biz_hours = config.get_business_hours(company_id=self.company_id)
                        biz_end_hour = biz_hours.get('end', 17)
                    except Exception:
                        biz_end_hour = 17
                    cur = new_start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    counted = 0
                    for _ in range(365):
                        if cur.weekday() in biz_day_indices:
                            counted += 1
                            if counted >= biz_days_needed:
                                break
                        cur += timedelta(days=1)
                    new_end = cur.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
                except Exception:
                    new_end = new_start_time + timedelta(minutes=duration_minutes)
            elif duration_minutes >= 480:
                try:
                    biz_hours = config.get_business_hours(company_id=self.company_id)
                    biz_start_hour = biz_hours.get('start', 9)
                    biz_end_hour = biz_hours.get('end', 17)
                except Exception:
                    biz_start_hour = 9
                    biz_end_hour = 17
                # Ensure start is at opening hour so the event doesn't span overnight
                new_start_time = new_start_time.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
                new_end = new_start_time.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
            else:
                new_end = new_start_time + timedelta(minutes=duration_minutes)

            event['start'] = {
                'dateTime': new_start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': self.timezone,
            }
            event['end'] = {
                'dateTime': new_end.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': self.timezone,
            }

            # Update description in the same call if provided, avoiding a
            # separate get+update that could revert the time changes.
            if description is not None:
                event['description'] = description

            # Update summary if provided (e.g. to add ✅ for completed jobs)
            if summary is not None:
                event['summary'] = summary

            # Ensure extendedProperties are set (older events may lack them)
            if 'extendedProperties' not in event:
                event['extendedProperties'] = {}
            if 'private' not in event['extendedProperties']:
                event['extendedProperties']['private'] = {}
            event['extendedProperties']['private']['bookedForYou'] = 'true'

            request = self.service.events().update(
                calendarId=self.calendar_id, eventId=event_id, body=event)
            return self._execute_with_retry(request)
        except Exception as e:
            logger.error(f"[GCAL] Reschedule failed: {e}")
            return None

    def find_appointment_by_details(self, customer_name: str = None,
                                     appointment_time=None,
                                     days_to_search: int = 30) -> Optional[dict]:
        """Find an event by customer name and/or time."""
        from datetime import timedelta
        now = datetime.utcnow()
        time_min = (appointment_time - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ') if appointment_time else now.strftime('%Y-%m-%dT%H:%M:%SZ')
        time_max = (appointment_time + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ') if appointment_time else (now + timedelta(days=days_to_search)).strftime('%Y-%m-%dT%H:%M:%SZ')

        kwargs = {
            'calendarId': self.calendar_id,
            'timeMin': time_min,
            'timeMax': time_max,
            'timeZone': self.timezone,
            'singleEvents': True,
            'orderBy': 'startTime',
        }
        if customer_name:
            kwargs['q'] = customer_name

        request = self.service.events().list(**kwargs)
        result = self._execute_with_retry(request)
        events = result.get('items', [])
        return events[0] if events else None

    def get_available_slots_for_day(self, target_date, service_duration: int = 60):
        """Get available time slots for a given day."""
        from datetime import timedelta
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        time_min = day_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        time_max = day_end.strftime('%Y-%m-%dT%H:%M:%SZ')

        request = self.service.events().list(
            calendarId=self.calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            timeZone=self.timezone,
            singleEvents=True,
            orderBy='startTime'
        )
        result = self._execute_with_retry(request)
        events = result.get('items', [])

        # Build list of busy periods
        busy = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            try:
                busy.append((
                    datetime.fromisoformat(start.replace('Z', '+00:00')).replace(tzinfo=None),
                    datetime.fromisoformat(end.replace('Z', '+00:00')).replace(tzinfo=None)
                ))
            except Exception:
                continue

        # Generate slots based on business hours
        from src.utils.config import Config
        hours = Config.get_business_hours(company_id=self.company_id)
        biz_start = hours.get('start', 9)
        biz_end = hours.get('end', 17)

        slots = []
        current = day_start.replace(hour=biz_start, minute=0)
        end_of_day = day_start.replace(hour=biz_end, minute=0)

        while current + timedelta(minutes=service_duration) <= end_of_day:
            slot_end = current + timedelta(minutes=service_duration)
            is_free = all(slot_end <= b_start or current >= b_end for b_start, b_end in busy)
            if is_free:
                slots.append(current)
            current += timedelta(minutes=30)

        return slots

    def update_event_description(self, event_id: str, description: str) -> bool:
        """Update the description of an existing event."""
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id, eventId=event_id).execute()
            event['description'] = description
            request = self.service.events().update(
                calendarId=self.calendar_id, eventId=event_id, body=event)
            self._execute_with_retry(request)
            return True
        except Exception as e:
            logger.error(f"[GCAL] Update description failed: {e}")
            return False

    def get_future_events(self, days_ahead: int = 90) -> list:
        """Fetch all future events from Google Calendar.

        Returns a list of dicts with keys:
            id, summary, description, start (datetime), end (datetime),
            duration_minutes
        """
        from datetime import timedelta

        now = datetime.now()
        time_min = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        time_max = (now + timedelta(days=days_ahead)).strftime('%Y-%m-%dT%H:%M:%SZ')

        events = []
        page_token = None

        while True:
            kwargs = {
                'calendarId': self.calendar_id,
                'timeMin': time_min,
                'timeMax': time_max,
                'timeZone': self.timezone,
                'singleEvents': True,
                'orderBy': 'startTime',
                'maxResults': 250,
            }
            if page_token:
                kwargs['pageToken'] = page_token

            request = self.service.events().list(**kwargs)
            result = self._execute_with_retry(request)

            for item in result.get('items', []):
                start_raw = item.get('start', {}).get('dateTime')
                end_raw = item.get('end', {}).get('dateTime')
                if not start_raw or not end_raw:
                    # All-day events use 'date' instead of 'dateTime' — skip
                    continue
                try:
                    start_dt = datetime.fromisoformat(
                        start_raw.replace('Z', '+00:00')
                    ).replace(tzinfo=None)
                    end_dt = datetime.fromisoformat(
                        end_raw.replace('Z', '+00:00')
                    ).replace(tzinfo=None)
                except Exception:
                    continue

                duration = int((end_dt - start_dt).total_seconds() / 60)
                ext_props = item.get('extendedProperties', {})
                events.append({
                    'id': item['id'],
                    'summary': item.get('summary', ''),
                    'description': item.get('description', ''),
                    'start': start_dt,
                    'end': end_dt,
                    'duration_minutes': duration,
                    'extendedProperties': ext_props,
                })

            page_token = result.get('nextPageToken')
            if not page_token:
                break

        logger.info(
            f"[GCAL] Fetched {len(events)} future events for company {self.company_id}"
        )
        return events

