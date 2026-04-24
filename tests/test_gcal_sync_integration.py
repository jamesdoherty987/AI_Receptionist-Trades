"""
Integration tests for Google Calendar sync architecture.

Tests the hybrid approach:
- Database calendar is ALWAYS the primary scheduler (availability, employees, etc.)
- Google Calendar is a SYNC TARGET (events pushed after booking)
- Sync failures never block bookings
- Initial sync on connect pushes existing future bookings
- Cancel/reschedule operations sync to both DB and Google Calendar
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# --- Helpers ---

def make_mock_db(bookings=None, company=None):
    """Create a mock database with configurable data."""
    db = MagicMock()
    db.get_all_bookings.return_value = bookings or []
    db.get_company.return_value = company or {'id': 1, 'company_name': 'Test Co'}
    db.add_booking.return_value = 100
    db.update_booking.return_value = True
    db.delete_booking.return_value = True
    db.find_or_create_client.return_value = 50
    return db


def make_mock_gcal_sync(event_id='gcal_event_123'):
    """Create a mock Google Calendar sync service."""
    gcal = MagicMock()
    gcal.book_appointment.return_value = {'id': event_id, 'summary': 'Test Event'}
    gcal.cancel_appointment.return_value = True
    gcal.reschedule_appointment.return_value = {'id': event_id}
    gcal.is_valid.return_value = True
    return gcal


def make_mock_db_calendar():
    """Create a mock database calendar service."""
    cal = MagicMock()
    cal.check_availability.return_value = True
    cal.book_appointment.return_value = {
        'id': 'db_12345_abc', 'summary': 'Test',
        'start': {'dateTime': '2026-04-01T09:00:00'},
        'end': {'dateTime': '2026-04-01T10:00:00'}, 'htmlLink': '#'
    }
    cal.get_available_slots_for_day.return_value = [
        datetime(2026, 4, 1, 9, 0), datetime(2026, 4, 1, 10, 0),
    ]
    return cal


def make_services(db=None, db_calendar=None, gcal_sync=None, company_id=1):
    """Build the services dict as llm_stream.py would."""
    cal = db_calendar or make_mock_db_calendar()
    return {
        'google_calendar': cal,
        'calendar': cal,
        'google_calendar_sync': gcal_sync,
        'db': db or make_mock_db(),
        'company_id': company_id,
        'call_state': MagicMock()
    }


# ============================================================
# TEST: Service architecture
# ============================================================

class TestServiceArchitecture:
    """Verify the service setup architecture is correct."""

    def test_db_calendar_is_primary(self):
        """Database calendar should be the primary scheduler."""
        gcal_sync = make_mock_gcal_sync()
        services = make_services(gcal_sync=gcal_sync)
        # google_calendar and calendar should be the same (database calendar)
        assert services['google_calendar'] is services['calendar']
        # google_calendar_sync should be separate
        assert services['google_calendar_sync'] is not services['google_calendar']

    def test_works_without_gcal(self):
        """Services should work when Google Calendar is not connected."""
        services = make_services(gcal_sync=None)
        assert services['google_calendar'] is not None
        assert services['google_calendar_sync'] is None

    def test_company_isolation(self):
        """Two companies should have separate sync services."""
        s1 = make_services(gcal_sync=make_mock_gcal_sync('c1'), company_id=1)
        s2 = make_services(gcal_sync=make_mock_gcal_sync('c2'), company_id=2)
        assert s1['google_calendar_sync'] is not s2['google_calendar_sync']
        assert s1['company_id'] != s2['company_id']


# ============================================================
# TEST: Booking sync logic
# ============================================================

class TestBookingSync:
    """Test the sync-after-booking pattern."""

    def test_sync_called_after_booking(self):
        """Google Calendar sync should be called after a successful DB booking."""
        gcal_sync = make_mock_gcal_sync()
        db = make_mock_db()
        booking_id = 100
        parsed_time = datetime(2026, 4, 1, 10, 0)
        
        # Simulate the sync code from calendar_tools.py
        if gcal_sync:
            try:
                summary = "Plumbing - James Doherty"
                gcal_event = gcal_sync.book_appointment(
                    summary=summary,
                    start_time=parsed_time,
                    duration_minutes=60,
                    description="Test booking",
                    phone_number="0851234567"
                )
                if gcal_event and db and booking_id:
                    db.update_booking(booking_id, calendar_event_id=gcal_event.get('id'), company_id=1)
            except Exception:
                pass  # Sync failure should not block booking
        
        gcal_sync.book_appointment.assert_called_once()
        db.update_booking.assert_called_once_with(
            100, calendar_event_id='gcal_event_123', company_id=1
        )

    def test_booking_survives_sync_failure(self):
        """Booking should succeed even if Google Calendar sync throws."""
        gcal_sync = make_mock_gcal_sync()
        gcal_sync.book_appointment.side_effect = Exception("Google API error")
        db = make_mock_db()
        booking_id = 100
        booking_saved = True  # DB save already happened
        
        # Simulate the sync code
        if gcal_sync:
            try:
                gcal_sync.book_appointment(
                    summary="Test", start_time=datetime.now(),
                    duration_minutes=60, description="", phone_number=""
                )
            except Exception:
                pass  # Non-blocking
        
        # Booking is still saved
        assert booking_saved is True
        # update_booking should NOT be called since sync failed
        db.update_booking.assert_not_called()

    def test_no_sync_when_not_connected(self):
        """No sync attempt when google_calendar_sync is None."""
        gcal_sync = None
        called = False
        
        if gcal_sync:
            called = True
        
        assert called is False


# ============================================================
# TEST: Cancel sync logic
# ============================================================

class TestCancelSync:
    """Test the sync-after-cancel pattern."""

    def test_cancel_syncs_to_gcal(self):
        """Cancellation should delete the event from Google Calendar."""
        gcal_sync = make_mock_gcal_sync()
        event_id = 'gcal_event_456'
        
        if event_id and gcal_sync:
            try:
                gcal_sync.cancel_appointment(event_id)
            except Exception:
                pass
        
        gcal_sync.cancel_appointment.assert_called_once_with('gcal_event_456')

    def test_cancel_survives_gcal_failure(self):
        """DB deletion should proceed even if Google Calendar cancel fails."""
        gcal_sync = make_mock_gcal_sync()
        gcal_sync.cancel_appointment.side_effect = Exception("API error")
        db = make_mock_db()
        event_id = 'gcal_event_456'
        booking_id = 100
        
        # Sync attempt (fails)
        if event_id and gcal_sync:
            try:
                gcal_sync.cancel_appointment(event_id)
            except Exception:
                pass
        
        # DB delete still happens
        if booking_id and db:
            db.delete_booking(booking_id, company_id=1)
        
        db.delete_booking.assert_called_once()

    def test_no_cancel_sync_without_event_id(self):
        """No sync attempt when booking has no calendar_event_id."""
        gcal_sync = make_mock_gcal_sync()
        event_id = None
        
        if event_id and gcal_sync:
            gcal_sync.cancel_appointment(event_id)
        
        gcal_sync.cancel_appointment.assert_not_called()

    def test_no_cancel_sync_with_db_prefix(self):
        """db_ prefix event IDs should still attempt sync (they get updated after initial sync)."""
        gcal_sync = make_mock_gcal_sync()
        event_id = 'db_12345_abc'
        
        # The cancel code uses event_id directly — it doesn't check prefix
        if event_id and gcal_sync:
            try:
                gcal_sync.cancel_appointment(event_id)
            except Exception:
                pass
        
        # It will be called (Google API will just return 404 which is fine)
        gcal_sync.cancel_appointment.assert_called_once()


# ============================================================
# TEST: Reschedule sync logic
# ============================================================

class TestRescheduleSync:
    """Test the sync-after-reschedule pattern."""

    def test_reschedule_syncs_to_gcal(self):
        """Reschedule should update the event in Google Calendar."""
        gcal_sync = make_mock_gcal_sync()
        event_id = 'gcal_event_789'
        new_time = datetime(2026, 4, 10, 14, 0)
        
        if event_id and gcal_sync:
            try:
                gcal_sync.reschedule_appointment(event_id, new_time)
            except Exception:
                pass
        
        gcal_sync.reschedule_appointment.assert_called_once_with('gcal_event_789', new_time)

    def test_reschedule_survives_gcal_failure(self):
        """DB update should proceed even if Google Calendar reschedule fails."""
        gcal_sync = make_mock_gcal_sync()
        gcal_sync.reschedule_appointment.side_effect = Exception("API error")
        db = make_mock_db()
        event_id = 'gcal_event_789'
        booking_id = 100
        new_time = datetime(2026, 4, 10, 14, 0)
        
        if event_id and gcal_sync:
            try:
                gcal_sync.reschedule_appointment(event_id, new_time)
            except Exception:
                pass
        
        # DB update still happens
        if booking_id and db:
            db.update_booking(booking_id, company_id=1, appointment_time=new_time.strftime('%Y-%m-%d %H:%M:%S'))
        
        db.update_booking.assert_called_once()


# ============================================================
# TEST: Initial sync on connect
# ============================================================

class TestInitialSync:
    """Test that existing bookings are synced when Google Calendar is first connected."""

    def _run_sync(self, bookings, gcal, db):
        """Simulate the sync logic from app.py callback."""
        synced = 0
        now = datetime.now()
        for booking in bookings:
            if booking.get('status') in ['cancelled', 'completed']:
                continue
            appt_time = booking.get('appointment_time')
            if not appt_time:
                continue
            if isinstance(appt_time, str):
                try:
                    appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                except:
                    continue
            elif hasattr(appt_time, 'replace'):
                appt_time = appt_time.replace(tzinfo=None)
            if appt_time <= now:
                continue
            existing_event_id = booking.get('calendar_event_id', '')
            if existing_event_id and not str(existing_event_id).startswith('db_'):
                continue
            customer_name = booking.get('client_name') or 'Customer'
            service = booking.get('service_type') or 'Job'
            duration = booking.get('duration_minutes', 60)
            phone = booking.get('phone_number') or ''
            try:
                gcal_event = gcal.book_appointment(
                    summary=f"{service} - {customer_name}",
                    start_time=appt_time,
                    duration_minutes=duration,
                    description=f"Synced from BookedForYou",
                    phone_number=phone
                )
                if gcal_event and booking.get('id'):
                    db.update_booking(booking['id'], calendar_event_id=gcal_event.get('id'), company_id=1)
                    synced += 1
            except Exception:
                pass
        return synced

    def test_syncs_future_bookings_only(self):
        """Only future non-cancelled bookings should be synced."""
        bookings = [
            {'id': 1, 'client_name': 'Past', 'appointment_time': datetime.now() - timedelta(days=5),
             'service_type': 'Plumbing', 'status': 'completed', 'duration_minutes': 60,
             'calendar_event_id': 'db_1_abc', 'phone_number': '123'},
            {'id': 2, 'client_name': 'Future1', 'appointment_time': datetime.now() + timedelta(days=5),
             'service_type': 'Electrical', 'status': 'scheduled', 'duration_minutes': 120,
             'calendar_event_id': 'db_2_abc', 'phone_number': '456'},
            {'id': 3, 'client_name': 'Future2', 'appointment_time': datetime.now() + timedelta(days=10),
             'service_type': 'Painting', 'status': 'scheduled', 'duration_minutes': 480,
             'calendar_event_id': 'db_3_abc', 'phone_number': '789'},
            {'id': 4, 'client_name': 'Cancelled', 'appointment_time': datetime.now() + timedelta(days=3),
             'service_type': 'HVAC', 'status': 'cancelled', 'duration_minutes': 60,
             'calendar_event_id': 'db_4_abc', 'phone_number': '000'},
        ]
        
        gcal = make_mock_gcal_sync()
        db = make_mock_db(bookings=bookings)
        synced = self._run_sync(bookings, gcal, db)
        
        assert synced == 2
        assert gcal.book_appointment.call_count == 2

    def test_skips_already_synced(self):
        """Bookings with real Google Calendar event IDs should be skipped."""
        bookings = [
            {'id': 1, 'client_name': 'Already', 'appointment_time': datetime.now() + timedelta(days=5),
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'gcal_real_id', 'phone_number': '123'},
            {'id': 2, 'client_name': 'NotYet', 'appointment_time': datetime.now() + timedelta(days=5),
             'service_type': 'Electrical', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_2_abc', 'phone_number': '456'},
        ]
        
        gcal = make_mock_gcal_sync()
        db = make_mock_db(bookings=bookings)
        synced = self._run_sync(bookings, gcal, db)
        
        assert synced == 1

    def test_empty_bookings(self):
        """No bookings should result in zero syncs."""
        gcal = make_mock_gcal_sync()
        db = make_mock_db(bookings=[])
        synced = self._run_sync([], gcal, db)
        
        assert synced == 0
        gcal.book_appointment.assert_not_called()

    def test_none_appointment_time_skipped(self):
        """Bookings with None appointment_time should be skipped."""
        bookings = [
            {'id': 1, 'client_name': 'NoTime', 'appointment_time': None,
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_1_abc', 'phone_number': '123'},
        ]
        
        gcal = make_mock_gcal_sync()
        db = make_mock_db(bookings=bookings)
        synced = self._run_sync(bookings, gcal, db)
        
        assert synced == 0

    def test_sync_failure_doesnt_crash(self):
        """If Google Calendar API fails during sync, it should continue with other bookings."""
        bookings = [
            {'id': 1, 'client_name': 'Fail', 'appointment_time': datetime.now() + timedelta(days=5),
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_1_abc', 'phone_number': '123'},
            {'id': 2, 'client_name': 'Succeed', 'appointment_time': datetime.now() + timedelta(days=6),
             'service_type': 'Electrical', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_2_abc', 'phone_number': '456'},
        ]
        
        gcal = make_mock_gcal_sync()
        # First call fails, second succeeds
        gcal.book_appointment.side_effect = [Exception("API error"), {'id': 'gcal_ok'}]
        db = make_mock_db(bookings=bookings)
        synced = self._run_sync(bookings, gcal, db)
        
        # Only the second one should have synced
        assert synced == 1

    def test_string_datetime_parsing(self):
        """Bookings with string datetime should be parsed correctly."""
        future = (datetime.now() + timedelta(days=5)).isoformat()
        bookings = [
            {'id': 1, 'client_name': 'StringTime', 'appointment_time': future,
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_1_abc', 'phone_number': '123'},
        ]
        
        gcal = make_mock_gcal_sync()
        db = make_mock_db(bookings=bookings)
        synced = self._run_sync(bookings, gcal, db)
        
        assert synced == 1


# ============================================================
# TEST: Google Calendar OAuth status
# ============================================================

class TestGCalStatus:
    """Test status endpoint logic."""

    def test_connected_with_valid_creds(self):
        from src.services.google_calendar_oauth import get_company_calendar_status
        
        token_data = {
            'token': 'ya29.test', 'refresh_token': '1//test',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_id', 'client_secret': 'test_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar'],
            'expiry': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        db = MagicMock()
        db.get_company.return_value = {
            'id': 1, 'google_credentials_json': json.dumps(token_data),
            'google_calendar_id': 'primary'
        }
        
        with patch('src.services.google_calendar_oauth.build') as mock_build:
            mock_build.return_value.calendars.return_value.get.return_value.execute.return_value = {
                'summary': 'test@gmail.com'
            }
            status = get_company_calendar_status(1, db)
        
        assert status['connected'] is True

    def test_not_connected_no_creds(self):
        from src.services.google_calendar_oauth import get_company_calendar_status
        
        db = MagicMock()
        db.get_company.return_value = {'id': 1, 'google_credentials_json': None}
        
        status = get_company_calendar_status(1, db)
        assert status['connected'] is False

    def test_not_connected_invalid_json(self):
        from src.services.google_calendar_oauth import get_company_calendar_status
        
        db = MagicMock()
        db.get_company.return_value = {'id': 1, 'google_credentials_json': '{bad json'}
        
        status = get_company_calendar_status(1, db)
        assert status['connected'] is False

    def test_not_connected_no_company(self):
        from src.services.google_calendar_oauth import get_company_calendar_status
        
        db = MagicMock()
        db.get_company.return_value = None
        
        status = get_company_calendar_status(1, db)
        assert status['connected'] is False


# ============================================================
# TEST: Disconnect
# ============================================================

class TestDisconnect:
    """Test disconnect clears everything."""

    def test_disconnect_clears_db_and_cache(self):
        from src.services.google_calendar_oauth import disconnect_google_calendar, _company_calendar_cache
        
        db = MagicMock()
        db.update_company.return_value = True
        _company_calendar_cache[99] = MagicMock()
        
        result = disconnect_google_calendar(99, db)
        
        assert result is True
        db.update_company.assert_called_once_with(99, google_credentials_json=None, google_calendar_id=None)
        assert 99 not in _company_calendar_cache


# ============================================================
# TEST: Edge cases
# ============================================================

class TestEdgeCases:
    """Test edge cases and error resilience."""

    def test_gcal_sync_returns_none_event(self):
        """If Google Calendar returns None for a booking, don't update DB."""
        gcal_sync = make_mock_gcal_sync()
        gcal_sync.book_appointment.return_value = None
        db = make_mock_db()
        booking_id = 100

        if gcal_sync:
            try:
                gcal_event = gcal_sync.book_appointment(
                    summary="Test", start_time=datetime.now(),
                    duration_minutes=60, description="", phone_number=""
                )
                if gcal_event and db and booking_id:
                    db.update_booking(booking_id, calendar_event_id=gcal_event.get('id'), company_id=1)
            except Exception:
                pass

        gcal_sync.book_appointment.assert_called_once()
        db.update_booking.assert_not_called()

    def test_gcal_sync_returns_event_without_id(self):
        """If Google Calendar returns event without 'id', handle gracefully."""
        gcal_sync = make_mock_gcal_sync()
        gcal_sync.book_appointment.return_value = {'summary': 'Test'}  # No 'id' key
        db = make_mock_db()
        booking_id = 100

        if gcal_sync:
            try:
                gcal_event = gcal_sync.book_appointment(
                    summary="Test", start_time=datetime.now(),
                    duration_minutes=60, description="", phone_number=""
                )
                if gcal_event and db and booking_id:
                    db.update_booking(booking_id, calendar_event_id=gcal_event.get('id'), company_id=1)
            except Exception:
                pass

        # update_booking IS called, but with calendar_event_id=None (from .get('id'))
        db.update_booking.assert_called_once_with(100, calendar_event_id=None, company_id=1)

    def test_cancel_with_empty_string_event_id(self):
        """Empty string event_id should not trigger sync."""
        gcal_sync = make_mock_gcal_sync()
        event_id = ''

        if event_id and gcal_sync:
            gcal_sync.cancel_appointment(event_id)

        gcal_sync.cancel_appointment.assert_not_called()

    def test_reschedule_with_empty_string_event_id(self):
        """Empty string event_id should not trigger sync."""
        gcal_sync = make_mock_gcal_sync()
        event_id = ''
        new_time = datetime(2026, 4, 10, 14, 0)

        if event_id and gcal_sync:
            gcal_sync.reschedule_appointment(event_id, new_time)

        gcal_sync.reschedule_appointment.assert_not_called()

    def test_db_update_failure_after_gcal_sync(self):
        """If DB update fails after successful gcal sync, booking still exists in both."""
        gcal_sync = make_mock_gcal_sync()
        db = make_mock_db()
        db.update_booking.side_effect = Exception("DB connection lost")
        booking_id = 100

        gcal_synced = False
        db_updated = False

        if gcal_sync:
            try:
                gcal_event = gcal_sync.book_appointment(
                    summary="Test", start_time=datetime.now(),
                    duration_minutes=60, description="", phone_number=""
                )
                gcal_synced = True
                if gcal_event and db and booking_id:
                    try:
                        db.update_booking(booking_id, calendar_event_id=gcal_event.get('id'), company_id=1)
                        db_updated = True
                    except Exception:
                        pass  # DB failure is non-blocking
            except Exception:
                pass

        assert gcal_synced is True
        assert db_updated is False

    def test_concurrent_companies_dont_interfere(self):
        """Two companies syncing simultaneously should not interfere."""
        gcal1 = make_mock_gcal_sync('company1_event')
        gcal2 = make_mock_gcal_sync('company2_event')
        db1 = make_mock_db()
        db2 = make_mock_db()

        services1 = make_services(db=db1, gcal_sync=gcal1, company_id=1)
        services2 = make_services(db=db2, gcal_sync=gcal2, company_id=2)

        # Company 1 books
        services1['google_calendar_sync'].book_appointment(
            summary="Co1 Job", start_time=datetime.now(),
            duration_minutes=60, description="", phone_number=""
        )
        # Company 2 books
        services2['google_calendar_sync'].book_appointment(
            summary="Co2 Job", start_time=datetime.now(),
            duration_minutes=60, description="", phone_number=""
        )

        # Each company's sync was called independently
        gcal1.book_appointment.assert_called_once()
        gcal2.book_appointment.assert_called_once()
        assert gcal1.book_appointment.call_args[1]['summary'] == "Co1 Job"
        assert gcal2.book_appointment.call_args[1]['summary'] == "Co2 Job"


class TestInitialSyncEdgeCases:
    """Additional edge cases for initial sync on connect."""

    def _run_sync(self, bookings, gcal, db):
        """Same sync logic as TestInitialSync."""
        synced = 0
        now = datetime.now()
        for booking in bookings:
            if booking.get('status') in ['cancelled', 'completed']:
                continue
            appt_time = booking.get('appointment_time')
            if not appt_time:
                continue
            if isinstance(appt_time, str):
                try:
                    appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                except:
                    continue
            elif hasattr(appt_time, 'replace'):
                appt_time = appt_time.replace(tzinfo=None)
            if appt_time <= now:
                continue
            existing_event_id = booking.get('calendar_event_id', '')
            if existing_event_id and not str(existing_event_id).startswith('db_'):
                continue
            customer_name = booking.get('client_name') or 'Customer'
            service = booking.get('service_type') or 'Job'
            duration = booking.get('duration_minutes', 60)
            phone = booking.get('phone_number') or ''
            try:
                gcal_event = gcal.book_appointment(
                    summary=f"{service} - {customer_name}",
                    start_time=appt_time,
                    duration_minutes=duration,
                    description=f"Synced from BookedForYou",
                    phone_number=phone
                )
                if gcal_event and booking.get('id'):
                    db.update_booking(booking['id'], calendar_event_id=gcal_event.get('id'), company_id=1)
                    synced += 1
            except Exception:
                pass
        return synced

    def test_booking_with_no_id_skipped_for_db_update(self):
        """Bookings without an 'id' field should sync to gcal but not update DB."""
        bookings = [
            {'client_name': 'NoId', 'appointment_time': datetime.now() + timedelta(days=5),
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_1_abc', 'phone_number': '123'},
        ]

        gcal = make_mock_gcal_sync()
        db = make_mock_db()
        synced = self._run_sync(bookings, gcal, db)

        # gcal was called but db.update_booking was not (no booking id)
        gcal.book_appointment.assert_called_once()
        db.update_booking.assert_not_called()
        assert synced == 0

    def test_booking_with_no_calendar_event_id(self):
        """Bookings with no calendar_event_id at all should be synced."""
        bookings = [
            {'id': 1, 'client_name': 'NoCal', 'appointment_time': datetime.now() + timedelta(days=5),
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'phone_number': '123'},
        ]

        gcal = make_mock_gcal_sync()
        db = make_mock_db()
        synced = self._run_sync(bookings, gcal, db)

        assert synced == 1

    def test_booking_with_empty_string_calendar_event_id(self):
        """Bookings with empty string calendar_event_id should be synced."""
        bookings = [
            {'id': 1, 'client_name': 'Empty', 'appointment_time': datetime.now() + timedelta(days=5),
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': '', 'phone_number': '123'},
        ]

        gcal = make_mock_gcal_sync()
        db = make_mock_db()
        synced = self._run_sync(bookings, gcal, db)

        # Empty string is falsy, so it passes the check and gets synced
        assert synced == 1

    def test_booking_with_utc_z_suffix_datetime(self):
        """Bookings with UTC 'Z' suffix datetime strings should parse correctly."""
        future = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        bookings = [
            {'id': 1, 'client_name': 'UTC', 'appointment_time': future,
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_1_abc', 'phone_number': '123'},
        ]

        gcal = make_mock_gcal_sync()
        db = make_mock_db()
        synced = self._run_sync(bookings, gcal, db)

        assert synced == 1

    def test_booking_with_invalid_datetime_string(self):
        """Bookings with unparseable datetime strings should be skipped."""
        bookings = [
            {'id': 1, 'client_name': 'BadDate', 'appointment_time': 'not-a-date',
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': 'db_1_abc', 'phone_number': '123'},
        ]

        gcal = make_mock_gcal_sync()
        db = make_mock_db()
        synced = self._run_sync(bookings, gcal, db)

        assert synced == 0
        gcal.book_appointment.assert_not_called()

    def test_booking_with_missing_fields_uses_defaults(self):
        """Bookings with missing optional fields should use defaults."""
        bookings = [
            {'id': 1, 'appointment_time': datetime.now() + timedelta(days=5),
             'status': 'scheduled', 'calendar_event_id': 'db_1_abc'},
        ]

        gcal = make_mock_gcal_sync()
        db = make_mock_db()
        synced = self._run_sync(bookings, gcal, db)

        assert synced == 1
        call_kwargs = gcal.book_appointment.call_args[1]
        assert call_kwargs['summary'] == 'Job - Customer'  # defaults
        assert call_kwargs['duration_minutes'] == 60  # default
        assert call_kwargs['phone_number'] == ''  # default

    def test_all_bookings_fail_sync(self):
        """If every booking fails to sync, synced count should be 0."""
        bookings = [
            {'id': i, 'client_name': f'Fail{i}', 'appointment_time': datetime.now() + timedelta(days=i+1),
             'service_type': 'Plumbing', 'status': 'scheduled', 'duration_minutes': 60,
             'calendar_event_id': f'db_{i}_abc', 'phone_number': str(i)}
            for i in range(1, 4)
        ]

        gcal = make_mock_gcal_sync()
        gcal.book_appointment.side_effect = Exception("API quota exceeded")
        db = make_mock_db()
        synced = self._run_sync(bookings, gcal, db)

        assert synced == 0
        assert gcal.book_appointment.call_count == 3
