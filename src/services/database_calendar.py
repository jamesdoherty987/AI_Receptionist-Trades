"""
Database-based calendar/availability system
No external dependencies - works for all customers out of the box
"""
import logging
import math
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from src.utils.config import config

# Set up logger for this module
logger = logging.getLogger(__name__)


def _make_naive(dt):
    """Strip timezone info from a datetime so comparisons work with naive datetimes."""
    if dt is not None and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


class DatabaseCalendarService:
    """
    Database-only calendar service for multi-tenant SaaS
    - No OAuth required
    - No token management
    - Scales to unlimited customers
    - Works immediately for all businesses
    """
    
    def __init__(self, db, company_id: int = 1):
        """
        Initialize with database connection and company ID
        
        Args:
            db: Database instance
            company_id: Company ID for multi-tenant isolation
        """
        self.db = db
        self.company_id = company_id
    
    def _calculate_job_end_time(self, start_time, duration_minutes: int,
                                biz_start_hour: int = 9, biz_end_hour: int = 17,
                                buffer_minutes: int = 0):
        """
        Calculate the true end time of a job, handling multi-day spans correctly.
        
        For jobs < 8 hours (480 mins): simple start + duration.
        For full-day jobs (480-1440 mins): blocks until closing time on the same day.
        For multi-day jobs (> 1440 mins): spans across multiple business days,
          counting only business days (skipping weekends).
        """
        if duration_minutes < 480:
            return start_time + timedelta(minutes=duration_minutes + buffer_minutes)

        if duration_minutes <= 1440:
            end = start_time.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
            return end + timedelta(minutes=buffer_minutes)

        # Multi-day job: walk forward counting business days
        calendar_days = duration_minutes / 1440.0
        biz_days_needed = math.ceil(calendar_days)

        try:
            business_days = config.get_business_days_indices()
        except Exception:
            business_days = [0, 1, 2, 3, 4]

        current_day = start_time.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
        days_counted = 0
        max_iterations = 365

        for _ in range(max_iterations):
            if current_day.weekday() in business_days:
                days_counted += 1
                if days_counted >= biz_days_needed:
                    end = current_day.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
                    return end + timedelta(minutes=buffer_minutes)
            current_day += timedelta(days=1)
            current_day = current_day.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)

        # Fallback
        return current_day.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)

    def _parse_booking_time(self, appt_time) -> Optional[datetime]:
        """Safely parse a booking time to a naive datetime."""
        if appt_time is None:
            return None
        if isinstance(appt_time, str):
            try:
                appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00'))
            except Exception:
                return None
        return _make_naive(appt_time)
    
    def get_available_slots_for_day(self, date: datetime, service_duration: int = None) -> List[datetime]:
        """
        Get available time slots for a specific day
        
        Args:
            date: Date to check (time will be normalized to start of day)
            service_duration: Duration of the service in minutes (optional, uses default if not provided)
            
        Returns:
            List of available datetime slots
        """
        logger.info(f"[DB_CAL] get_available_slots_for_day called: date={date}, service_duration={service_duration}, company_id={self.company_id}")
        
        # Normalize to start of day
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        # Get business hours from config - MUST use company_id for correct hours
        try:
            business_hours = config.get_business_hours(company_id=self.company_id)
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
            logger.info(f"[DB_CAL] Business hours: {start_hour}:00 - {end_hour}:00")
        except Exception as e:
            logger.warning(f"[DB_CAL] Error getting business hours: {e}")
            start_hour = getattr(config, 'BUSINESS_HOURS_START', 9)
            end_hour = getattr(config, 'BUSINESS_HOURS_END', 17)
        
        # Get buffer time from settings
        try:
            from src.services.settings_manager import get_settings_manager
            settings_mgr = get_settings_manager()
            default_duration = settings_mgr.get_default_duration_minutes(company_id=self.company_id)
        except Exception as e:
            logger.warning(f"[DB_CAL] Error getting default duration: {e}")
            default_duration = 1440  # 1 day default for trades
        
        # Use provided duration or default
        slot_duration = service_duration if service_duration else default_duration
        logger.info(f"[DB_CAL] Using slot duration: {slot_duration} mins")
        
        # Don't return past time slots
        now = datetime.now()
        
        # Get existing bookings for this day - MUST filter by company_id for data isolation
        try:
            all_bookings = self.db.get_all_bookings(company_id=self.company_id)
            logger.info(f"[DB_CAL] Total bookings for company {self.company_id}: {len(all_bookings)}")
        except Exception as e:
            logger.error(f"[DB_CAL] Error getting bookings: {e}")
            import traceback
            traceback.print_exc()
            all_bookings = []
        
        day_bookings = []
        for booking in all_bookings:
            if booking.get('status') in ['cancelled', 'completed']:
                continue  # Skip cancelled/completed bookings
            
            appt_time = self._parse_booking_time(booking.get('appointment_time'))
            if not appt_time:
                continue
            
            # Get the booking's duration (use stored duration or default)
            booking_duration = booking.get('duration_minutes', default_duration)
            
            # Calculate true end time using business-day logic
            booking_end = self._calculate_job_end_time(
                appt_time, booking_duration,
                biz_start_hour=start_hour, biz_end_hour=end_hour
            )
            
            # Include bookings that START on this day OR multi-day bookings
            # from previous days that EXTEND into this day
            if (day_start <= appt_time < day_end) or (appt_time < day_start and booking_end > day_start):
                day_bookings.append({
                    'start': appt_time,
                    'duration': booking_duration,
                    'end': booking_end
                })
        
        logger.info(f"[DB_CAL] Bookings on {day_start.strftime('%Y-%m-%d')}: {len(day_bookings)}")
        
        # Generate all possible slots for the day
        available_slots = []
        current_slot = day_start.replace(hour=start_hour, minute=0)
        end_time = day_start.replace(hour=end_hour, minute=0)
        
        while current_slot < end_time:
            # Skip past time slots
            if current_slot <= now:
                current_slot += timedelta(minutes=30)  # Check every 30 minutes
                continue
            
            # Check if this slot would fit (service duration only, no buffer)
            # For full-day services (8+ hours = 480 mins), the job blocks the whole business day
            # but doesn't actually require that many continuous hours
            if slot_duration >= 480:
                # Full-day job - ends at closing time
                slot_end = end_time
            else:
                slot_end = current_slot + timedelta(minutes=slot_duration)
            
            # Don't allow booking that extends past business hours
            if slot_end > end_time:
                current_slot += timedelta(minutes=30)
                continue
            
            # Check if slot conflicts with existing booking
            is_available = True
            
            for booking in day_bookings:
                booking_start = booking['start']
                booking_end = booking['end']
                
                # Check for overlap
                if (current_slot < booking_end and slot_end > booking_start):
                    is_available = False
                    break
            
            if is_available:
                available_slots.append(current_slot)
            
            current_slot += timedelta(minutes=30)  # Check every 30 minutes for more granular slots
        
        logger.info(f"[DB_CAL] Available slots found: {len(available_slots)}")
        
        # For full-day services (8+ hours), only return ONE slot per day (start of business day)
        # This prevents offering hourly slots that can't actually be booked
        if slot_duration >= 480 and len(available_slots) > 0:
            # Keep only the first slot (start of business day)
            available_slots = [available_slots[0]]
            logger.info(f"[DB_CAL] Full-day service ({slot_duration} mins) - reduced to 1 slot: {available_slots[0].strftime('%I:%M %p')}")
        
        return available_slots
    
    def check_availability(self, start_time: datetime, duration_minutes: int = None) -> bool:
        """
        Check if a specific time slot is available
        
        Args:
            start_time: Start time of the slot
            duration_minutes: Duration of the appointment (optional, uses default if not provided)
            
        Returns:
            True if available, False if booked
        """
        logger.info(f"[DB_CAL] check_availability called: start_time={start_time}, duration={duration_minutes}, company_id={self.company_id}")
        
        start_time = _make_naive(start_time)
        
        # Don't allow booking in the past
        if start_time <= datetime.now():
            logger.warning(f"[DB_CAL] Rejecting past time: {start_time}")
            return False
        
        # Get default duration from settings
        try:
            from src.services.settings_manager import get_settings_manager
            settings_mgr = get_settings_manager()
            default_duration = settings_mgr.get_default_duration_minutes(company_id=self.company_id)
        except Exception as e:
            logger.warning(f"[DB_CAL] Error getting default duration: {e}")
            default_duration = 1440  # 1 day default for trades
        
        # Use provided duration or default
        if duration_minutes is None:
            duration_minutes = default_duration
        
        # Get business hours for full-day job handling
        try:
            business_hours = config.get_business_hours(company_id=self.company_id)
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
        except Exception:
            start_hour = 9
            end_hour = 17
        
        # Calculate slot end using business-day logic
        slot_end = self._calculate_job_end_time(
            start_time, duration_minutes,
            biz_start_hour=start_hour,
            biz_end_hour=end_hour
        )
        logger.info(f"[DB_CAL] Checking slot: {start_time} to {slot_end}")
        
        # Get all non-cancelled bookings - MUST filter by company_id for data isolation
        try:
            all_bookings = self.db.get_all_bookings(company_id=self.company_id)
            logger.info(f"[DB_CAL] Total bookings to check: {len(all_bookings)}")
        except Exception as e:
            logger.error(f"[DB_CAL] Error getting bookings: {e}")
            import traceback
            traceback.print_exc()
            return True  # Fail open - allow booking if we can't check
        
        for booking in all_bookings:
            if booking.get('status') in ['cancelled', 'completed']:
                continue
            
            appt_time = self._parse_booking_time(booking.get('appointment_time'))
            if not appt_time:
                continue
            
            # Get the booking's duration (use stored duration or default)
            booking_duration = booking.get('duration_minutes', default_duration)
            
            # Calculate true end time using business-day logic
            booking_end = self._calculate_job_end_time(
                appt_time, booking_duration,
                biz_start_hour=start_hour, biz_end_hour=end_hour
            )
            
            # Check for overlap
            if (start_time < booking_end and slot_end > appt_time):
                logger.info(f"[DB_CAL] Conflict found with booking: {appt_time} to {booking_end}")
                return False  # Conflict found
        
        logger.info(f"[DB_CAL] Slot is available")
        return True  # No conflicts
    
    def book_appointment(self, summary: str, start_time: datetime, 
                        duration_minutes: int = None, description: str = "",
                        location: str = "", phone_number: str = "") -> Optional[Dict]:
        """
        Book an appointment (database only - no Google Calendar)
        
        This is a placeholder for compatibility. The actual booking
        is done via add_booking() which handles database insertion.
        
        Args:
            summary: Event summary/title
            start_time: Start time of the appointment
            duration_minutes: Duration in minutes (optional, uses default if not provided)
            description: Event description
            location: Event location
            phone_number: Customer phone number
        
        Returns:
            Dict with booking confirmation (compatible with Google Calendar format)
        """
        logger.info(f"[DB_CAL] book_appointment called: summary={summary}, start_time={start_time}, duration={duration_minutes}")
        
        # Get default duration if not provided
        if duration_minutes is None:
            try:
                from src.services.settings_manager import get_settings_manager
                settings_mgr = get_settings_manager()
                duration_minutes = settings_mgr.get_default_duration_minutes(company_id=self.company_id)
            except Exception as e:
                logger.warning(f"[DB_CAL] Error getting default duration: {e}")
                duration_minutes = 1440  # 1 day default for trades
        
        # Generate a unique event ID using timestamp + random suffix to avoid collisions
        # when multiple bookings are made at the same time slot for different customers
        import random
        import string
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        event_id = f"db_{int(start_time.timestamp())}_{random_suffix}"
        
        # Generate a fake "event" dict for compatibility
        event = {
            'id': event_id,
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time.isoformat()},
            'end': {'dateTime': (start_time + timedelta(minutes=duration_minutes)).isoformat()},
            'duration_minutes': duration_minutes,
            'htmlLink': '#'  # Placeholder
        }
        logger.info(f"[DB_CAL] Created event: {event}")
        return event
    
    def find_appointment_by_details(self, customer_name: Optional[str] = None,
                                    appointment_time: Optional[datetime] = None) -> Optional[Dict]:
        """
        Find an appointment by customer name and/or time
        
        Args:
            customer_name: Customer name to search for
            appointment_time: Appointment time to search for
            
        Returns:
            Booking dict if found, None otherwise
        """
        # MUST filter by company_id for data isolation
        all_bookings = self.db.get_all_bookings(company_id=self.company_id)
        
        for booking in all_bookings:
            if booking.get('status') in ['cancelled', 'completed']:
                continue
            
            # Check name match
            name_match = True
            if customer_name:
                client_name = (booking.get('client_name') or '').lower()
                name_match = customer_name.lower() in client_name
            
            # Check time match
            time_match = True
            if appointment_time:
                appt_time = self._parse_booking_time(booking.get('appointment_time'))
                target_time = _make_naive(appointment_time)
                
                # Allow 5-minute tolerance
                if appt_time and target_time:
                    time_diff = abs((appt_time - target_time).total_seconds())
                    time_match = time_diff < 300  # 5 minutes
                else:
                    time_match = False
            
            if name_match and time_match:
                # Convert to Google Calendar-like format for compatibility
                return {
                    'id': str(booking.get('id')),
                    'summary': f"{booking.get('service_type')} - {booking.get('client_name')}",
                    'start': {'dateTime': str(booking.get('appointment_time'))},
                    'booking_id': booking.get('id')
                }
        
        return None
    
    def cancel_appointment(self, event_id: str) -> bool:
        """
        Cancel an appointment by ID
        
        Args:
            event_id: Booking ID (from database)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            booking_id = int(event_id)
            return self.db.update_booking(booking_id, status='cancelled')
        except:
            return False
    
    def reschedule_appointment(self, event_id: str, new_time: datetime) -> Optional[Dict]:
        """
        Reschedule an appointment to a new time
        
        Args:
            event_id: Booking ID
            new_time: New appointment time
            
        Returns:
            Updated booking dict if successful, None otherwise
        """
        try:
            booking_id = int(event_id)
            success = self.db.update_booking(
                booking_id, 
                appointment_time=new_time.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if success:
                # Return updated booking - MUST filter by company_id for data isolation
                bookings = self.db.get_all_bookings(company_id=self.company_id)
                for booking in bookings:
                    if booking.get('id') == booking_id:
                        return {
                            'id': str(booking_id),
                            'summary': f"{booking.get('service_type')} - {booking.get('client_name')}",
                            'start': {'dateTime': str(booking.get('appointment_time'))},
                            'htmlLink': '#'
                        }
            return None
        except:
            return None
    
    def update_event_description(self, event_id: str, description: str) -> bool:
        """
        Update the description/notes of an existing booking.
        
        For database calendar, this adds a note to the booking since
        the description is stored in the booking record itself.
        
        Args:
            event_id: Booking ID
            description: New description text
            
        Returns:
            True if successful, False otherwise
        """
        try:
            booking_id = int(event_id)
            # For database calendar, we don't have a separate description field
            # The description is part of the booking notes
            # This is a no-op for now but maintains API compatibility
            return True
        except:
            return False


def get_database_calendar_service(company_id: int = 1) -> DatabaseCalendarService:
    """
    Get database calendar service instance for a specific company
    
    NOTE: This creates a new instance each time to ensure proper multi-tenant isolation.
    Each company must have their own calendar service with their own company_id.
    
    Args:
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        DatabaseCalendarService instance for the specified company
    """
    from src.services.database import get_database
    db = get_database()
    # Always create a new instance with the correct company_id for proper isolation
    return DatabaseCalendarService(db, company_id)
