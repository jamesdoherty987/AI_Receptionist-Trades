"""
Tests for booking, cancel, and reschedule flows with Google Calendar sync.

Verifies:
- Booking creates a job and syncs to Google Calendar
- Cancel removes the job and syncs cancellation to Google Calendar
- Reschedule MOVES the existing booking (no duplicates) and syncs to Google Calendar
- All operations work correctly without Google Calendar connected
- Sync failures don't block the primary operation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.calendar_tools import execute_tool_call


# ============================================================
# Helpers
# ============================================================

def make_mock_db(bookings=None, has_employees=False):
    db = MagicMock()
    db.get_all_bookings.return_value = bookings or []
    db.add_booking.return_value = 100
    db.update_booking.return_value = True
    db.delete_booking.return_value = True
    db.find_or_create_client.return_value = 50
    db.has_employees.return_value = has_employees
    db.get_employee.return_value = None
    db.get_company.return_value = {'id': 1, 'company_name': 'Test Plumbing'}
    return db


def make_mock_gcal_sync(event_id='gcal_evt_123'):
    gcal = MagicMock()
    gcal.book_appointment.return_value = {'id': event_id, 'summary': 'Test'}
    gcal.cancel_appointment.return_value = True
    gcal.reschedule_appointment.return_value = {'id': event_id}
    gcal.is_valid.return_value = True
    return gcal


def make_mock_calendar():
    cal = MagicMock()
    cal.check_availability.return_value = True
    cal.book_appointment.return_value = {
        'id': 'db_12345_abc', 'summary': 'Test',
        'start': {'dateTime': '2026-04-09T09:00:00'},
        'end': {'dateTime': '2026-04-09T10:00:00'}, 'htmlLink': '#'
    }
    cal.service = None
    return cal


def make_services(bookings=None, has_employees=False, gcal_sync=True):
    db = make_mock_db(bookings, has_employees)
    cal = make_mock_calendar()
    gcal = make_mock_gcal_sync() if gcal_sync else None
    return {
        'db': db,
        'google_calendar': cal,
        'calendar': cal,
        'google_calendar_sync': gcal,
        'company_id': 1,
        'call_state': MagicMock()
    }


THURSDAY_BOOKING = {
    'id': 42,
    'client_name': 'Donald Trump',
    'appointment_time': '2026-04-09 15:00:00',
    'service_type': 'Heat Pump Installation',
    'duration_minutes': 180,
    'status': 'scheduled',
    'calendar_event_id': 'gcal_evt_original',
    'assigned_employee_ids': [],
}


# ============================================================
# TEST: Cancel flow with Google Calendar sync
# ============================================================

class TestCancelWithGCalSync:
    """Cancel should delete from DB AND sync to Google Calendar."""

    def test_cancel_step1_lists_jobs(self):
        """First cancel call with just the day returns job list."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday April 9th'},
            services
        )

        assert result.get('requires_confirmation') is True
        assert 'Donald Trump' in result['message']
        # No deletion yet
        services['db'].delete_booking.assert_not_called()

    def test_cancel_step2_deletes_and_syncs_gcal(self):
        """Second cancel call with name deletes booking and syncs to gcal."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday April 9th', 'customer_name': 'Donald Trump'},
            services
        )

        assert result['success'] is True
        assert 'cancelled' in result['message'].lower()
        # DB deletion
        services['db'].delete_booking.assert_called_once_with(42, company_id=1)
        # Google Calendar sync — event_id is 'gcal_evt_original'
        services['google_calendar_sync'].cancel_appointment.assert_called_once_with('gcal_evt_original')

    def test_cancel_works_without_gcal(self):
        """Cancel should succeed even without Google Calendar connected."""
        services = make_services(bookings=[THURSDAY_BOOKING], gcal_sync=False)

        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday April 9th', 'customer_name': 'Donald Trump'},
            services
        )

        assert result['success'] is True
        services['db'].delete_booking.assert_called_once_with(42, company_id=1)

    def test_cancel_survives_gcal_failure(self):
        """Cancel should succeed even if Google Calendar sync throws."""
        services = make_services(bookings=[THURSDAY_BOOKING])
        services['google_calendar_sync'].cancel_appointment.side_effect = Exception("Google API error")

        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday April 9th', 'customer_name': 'Donald Trump'},
            services
        )

        assert result['success'] is True
        services['db'].delete_booking.assert_called_once()

    def test_cancel_no_event_id_skips_gcal(self):
        """Bookings with no event_id should not try to cancel in gcal."""
        booking = {**THURSDAY_BOOKING, 'calendar_event_id': None}
        services = make_services(bookings=[booking])

        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday April 9th', 'customer_name': 'Donald Trump'},
            services
        )

        assert result['success'] is True
        services['db'].delete_booking.assert_called_once()
        # No event_id means no gcal sync
        services['google_calendar_sync'].cancel_appointment.assert_not_called()


# ============================================================
# TEST: Reschedule flow with Google Calendar sync
# ============================================================

class TestRescheduleWithGCalSync:
    """Reschedule should UPDATE existing booking (not create duplicate) and sync to gcal."""

    def test_reschedule_step1_lists_jobs(self):
        """First reschedule call with just the day returns job list."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        result = execute_tool_call(
            'reschedule_job',
            {'current_date': 'Thursday April 9th'},
            services
        )

        assert result.get('requires_confirmation') is True
        assert 'Donald Trump' in result['message']
        # No update yet
        services['db'].update_booking.assert_not_called()

    def test_reschedule_step2_confirms_name(self):
        """Second call with name confirms and asks for new date."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        result = execute_tool_call(
            'reschedule_job',
            {'current_date': 'Thursday April 9th', 'customer_name': 'Donald Trump'},
            services
        )

        assert result['success'] is False
        assert result.get('customer_name_confirmed') is True
        assert 'Donald Trump' in str(result.get('error', '') or result.get('matched_name', ''))
        # Still no update
        services['db'].update_booking.assert_not_called()

    def test_reschedule_step3_moves_booking_and_syncs(self):
        """Third call with new datetime returns confirmation, fourth call with confirmed=true completes and syncs to gcal."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        # Step 3: provide new datetime - should get confirmation prompt
        result = execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Saturday April 11th at 8am'
            },
            services
        )

        assert result.get('requires_reschedule_confirmation') is True
        assert 'confirm' in result['message'].lower()
        # Nothing should be updated yet
        services['db'].update_booking.assert_not_called()

        # Step 4: confirm the reschedule
        result = execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Saturday April 11th at 8am',
                'confirmed': True
            },
            services
        )

        assert result['success'] is True
        assert 'rescheduled' in result['message'].lower()
        # DB should UPDATE the existing booking, not create a new one
        services['db'].update_booking.assert_called_once()
        call_args = services['db'].update_booking.call_args
        assert call_args[0][0] == 42  # booking ID
        # No new booking should be created
        services['db'].add_booking.assert_not_called()
        # Google Calendar sync
        services['google_calendar_sync'].reschedule_appointment.assert_called_once()

    def test_reschedule_does_not_create_duplicate(self):
        """CRITICAL: Reschedule must NOT create a second booking."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        # Complete the full reschedule flow
        execute_tool_call(
            'reschedule_job',
            {'current_date': 'Thursday April 9th'},
            services
        )
        execute_tool_call(
            'reschedule_job',
            {'current_date': 'Thursday April 9th', 'customer_name': 'Donald Trump'},
            services
        )
        # Step 3: new_datetime without confirmed - gets confirmation prompt
        execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Monday April 13th at 10am'
            },
            services
        )
        # Step 4: confirmed=true - actually moves the booking
        execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Monday April 13th at 10am',
                'confirmed': True
            },
            services
        )

        # add_booking should NEVER be called during reschedule
        services['db'].add_booking.assert_not_called()
        # delete_booking should NEVER be called during reschedule
        services['db'].delete_booking.assert_not_called()
        # update_booking should be called exactly once (the final move)
        assert services['db'].update_booking.call_count == 1

    def test_reschedule_works_without_gcal(self):
        """Reschedule should succeed without Google Calendar connected."""
        services = make_services(bookings=[THURSDAY_BOOKING], gcal_sync=False)

        result = execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Monday April 13th at 10am',
                'confirmed': True
            },
            services
        )

        assert result['success'] is True
        services['db'].update_booking.assert_called_once()

    def test_reschedule_survives_gcal_failure(self):
        """Reschedule should succeed even if Google Calendar sync throws."""
        services = make_services(bookings=[THURSDAY_BOOKING])
        services['google_calendar_sync'].reschedule_appointment.side_effect = Exception("Google API error")

        result = execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Monday April 13th at 10am',
                'confirmed': True
            },
            services
        )

        assert result['success'] is True
        services['db'].update_booking.assert_called_once()

    def test_reschedule_syncs_correct_event_id(self):
        """Reschedule should pass the correct event_id to gcal sync."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Monday April 13th at 10am',
                'confirmed': True
            },
            services
        )

        gcal_call = services['google_calendar_sync'].reschedule_appointment
        gcal_call.assert_called_once()
        args = gcal_call.call_args[0]
        assert args[0] == 'gcal_evt_original'  # event_id from the booking


# ============================================================
# TEST: Booking flow with Google Calendar sync
# ============================================================

class TestBookingWithGCalSync:
    """Booking should create in DB and sync to Google Calendar."""

    @patch('src.services.calendar_tools.match_service')
    @patch('src.utils.date_parser.parse_datetime')
    def test_book_job_syncs_to_gcal(self, mock_parse, mock_match):
        """book_job should sync the new booking to Google Calendar."""
        mock_parse.return_value = datetime(2026, 4, 11, 8, 0)
        mock_match.return_value = {
            'matched_name': 'Plumbing',
            'service': {
                'name': 'Plumbing',
                'duration': 60,
                'duration_minutes': 60,
                'price': 100,
                'employees_required': 1,
                'employee_restrictions': None,
                'requires_callout': False,
            },
            'confidence': 100
        }

        services = make_services(bookings=[], has_employees=False)

        result = execute_tool_call(
            'book_job',
            {
                'customer_name': 'John Smith',
                'phone': '0851234567',
                'job_address': '123 Main St',
                'job_description': 'Plumbing',
                'appointment_datetime': 'Saturday April 11th at 8am',
                'urgency_level': 'scheduled',
                'property_type': 'residential'
            },
            services
        )

        assert result['success'] is True
        # DB booking created
        services['db'].add_booking.assert_called_once()
        # Google Calendar sync called
        services['google_calendar_sync'].book_appointment.assert_called_once()

    @patch('src.services.calendar_tools.match_service')
    @patch('src.utils.date_parser.parse_datetime')
    def test_book_job_works_without_gcal(self, mock_parse, mock_match):
        """Booking should succeed without Google Calendar connected."""
        mock_parse.return_value = datetime(2026, 4, 11, 8, 0)
        mock_match.return_value = {
            'matched_name': 'Plumbing',
            'service': {
                'name': 'Plumbing',
                'duration': 60,
                'duration_minutes': 60,
                'price': 100,
                'employees_required': 1,
                'employee_restrictions': None,
                'requires_callout': False,
            },
            'confidence': 100
        }

        services = make_services(bookings=[], has_employees=False, gcal_sync=False)

        result = execute_tool_call(
            'book_job',
            {
                'customer_name': 'John Smith',
                'phone': '0851234567',
                'job_address': '123 Main St',
                'job_description': 'Plumbing',
                'appointment_datetime': 'Saturday April 11th at 8am',
                'urgency_level': 'scheduled',
                'property_type': 'residential'
            },
            services
        )

        assert result['success'] is True
        services['db'].add_booking.assert_called_once()

    @patch('src.services.calendar_tools.match_service')
    @patch('src.utils.date_parser.parse_datetime')
    def test_book_job_survives_gcal_failure(self, mock_parse, mock_match):
        """Booking should succeed even if Google Calendar sync throws."""
        mock_parse.return_value = datetime(2026, 4, 11, 8, 0)
        mock_match.return_value = {
            'matched_name': 'Plumbing',
            'service': {
                'name': 'Plumbing',
                'duration': 60,
                'duration_minutes': 60,
                'price': 100,
                'employees_required': 1,
                'employee_restrictions': None,
                'requires_callout': False,
            },
            'confidence': 100
        }

        services = make_services(bookings=[], has_employees=False)
        services['google_calendar_sync'].book_appointment.side_effect = Exception("Google API error")

        result = execute_tool_call(
            'book_job',
            {
                'customer_name': 'John Smith',
                'phone': '0851234567',
                'job_address': '123 Main St',
                'job_description': 'Plumbing',
                'appointment_datetime': 'Saturday April 11th at 8am',
                'urgency_level': 'scheduled',
                'property_type': 'residential'
            },
            services
        )

        assert result['success'] is True
        services['db'].add_booking.assert_called_once()


# ============================================================
# TEST: Reschedule to closed day
# ============================================================

class TestRescheduleClosedDay:
    """Reschedule should reject moves to days the business is closed."""

    @patch('src.utils.config.Config.get_business_days_indices', return_value=[0, 1, 2, 3, 4])
    def test_reschedule_to_sunday_rejected(self, mock_biz_days):
        """Rescheduling to Sunday should be rejected with helpful message."""
        services = make_services(bookings=[THURSDAY_BOOKING])

        result = execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Thursday April 9th',
                'customer_name': 'Donald Trump',
                'new_datetime': 'Sunday April 12th'
            },
            services
        )

        assert result['success'] is False
        assert 'not open' in result['error'].lower() or 'sunday' in result['error'].lower()
        # No DB changes
        services['db'].update_booking.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
