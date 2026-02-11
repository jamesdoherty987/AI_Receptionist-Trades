"""
Database-based calendar/availability system
No external dependencies - works for all customers out of the box
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from src.utils.config import config


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
    
    def get_available_slots_for_day(self, date: datetime) -> List[datetime]:
        """
        Get available time slots for a specific day
        
        Args:
            date: Date to check (time will be normalized to start of day)
            
        Returns:
            List of available datetime slots
        """
        # Normalize to start of day
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        # Get business hours from config - MUST use company_id for correct hours
        try:
            business_hours = config.get_business_hours(company_id=self.company_id)
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
        except Exception:
            start_hour = getattr(config, 'BUSINESS_HOURS_START', 9)
            end_hour = getattr(config, 'BUSINESS_HOURS_END', 17)
        
        # Get slot duration from config (default 60 minutes)
        slot_duration = getattr(config, 'APPOINTMENT_SLOT_DURATION', 60)
        
        # Don't return past time slots
        now = datetime.now()
        
        # Get existing bookings for this day - MUST filter by company_id for data isolation
        all_bookings = self.db.get_all_bookings(company_id=self.company_id)
        day_bookings = []
        for booking in all_bookings:
            if booking.get('status') in ['cancelled', 'completed']:
                continue  # Skip cancelled/completed bookings
            
            appt_time = self._parse_booking_time(booking.get('appointment_time'))
            if appt_time and day_start <= appt_time < day_end:
                day_bookings.append(appt_time)
        
        # Generate all possible slots for the day
        available_slots = []
        current_slot = day_start.replace(hour=start_hour, minute=0)
        end_time = day_start.replace(hour=end_hour, minute=0)
        
        while current_slot < end_time:
            # Skip past time slots
            if current_slot <= now:
                current_slot += timedelta(minutes=slot_duration)
                continue
            
            # Check if slot conflicts with existing booking
            slot_end = current_slot + timedelta(minutes=slot_duration)
            is_available = True
            
            for booking_time in day_bookings:
                booking_end = booking_time + timedelta(minutes=slot_duration)
                
                # Check for overlap
                if (current_slot < booking_end and slot_end > booking_time):
                    is_available = False
                    break
            
            if is_available:
                available_slots.append(current_slot)
            
            current_slot += timedelta(minutes=slot_duration)
        
        return available_slots
    
    def check_availability(self, start_time: datetime, duration_minutes: int = 60) -> bool:
        """
        Check if a specific time slot is available
        
        Args:
            start_time: Start time of the slot
            duration_minutes: Duration of the appointment
            
        Returns:
            True if available, False if booked
        """
        start_time = _make_naive(start_time)
        
        # Don't allow booking in the past
        if start_time <= datetime.now():
            return False
        
        slot_end = start_time + timedelta(minutes=duration_minutes)
        
        # Get all non-cancelled bookings - MUST filter by company_id for data isolation
        all_bookings = self.db.get_all_bookings(company_id=self.company_id)
        
        for booking in all_bookings:
            if booking.get('status') in ['cancelled', 'completed']:
                continue
            
            appt_time = self._parse_booking_time(booking.get('appointment_time'))
            if not appt_time:
                continue
            
            booking_end = appt_time + timedelta(minutes=duration_minutes)
            
            # Check for overlap
            if (start_time < booking_end and slot_end > appt_time):
                return False  # Conflict found
        
        return True  # No conflicts
    
    def book_appointment(self, summary: str, start_time: datetime, 
                        duration_minutes: int = 60, description: str = "",
                        location: str = "", phone_number: str = "") -> Optional[Dict]:
        """
        Book an appointment (database only - no Google Calendar)
        
        This is a placeholder for compatibility. The actual booking
        is done via add_booking() which handles database insertion.
        
        Returns:
            Dict with booking confirmation (compatible with Google Calendar format)
        """
        # Generate a fake "event" dict for compatibility
        return {
            'id': f"db_{int(start_time.timestamp())}",
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time.isoformat()},
            'end': {'dateTime': (start_time + timedelta(minutes=duration_minutes)).isoformat()},
            'htmlLink': '#'  # Placeholder
        }
    
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
