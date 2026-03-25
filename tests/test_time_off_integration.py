"""
Integration tests for worker time-off blocking bookings.

Tests that:
1. check_worker_availability blocks when worker has approved leave
2. check_worker_availability allows when leave is pending/denied
3. _find_available_workers_batch skips workers on leave
4. Normal bookings still work when no leave
5. Search availability skips leave days
6. Multi-day leave blocks all days in range
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def next_weekday(hour=10, days_ahead=7):
    """Return a future weekday datetime."""
    d = datetime.now() + timedelta(days=days_ahead)
    while d.weekday() >= 5:  # Skip weekends
        d += timedelta(days=1)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


def make_db_with_time_off(time_off_records=None, existing_bookings=None):
    """
    Create a mock DB wrapper that supports time-off checking
    in check_worker_availability.
    """
    from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper

    real_db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    time_off_records = time_off_records or []
    existing_bookings = existing_bookings or []

    # Track which query is being executed
    _last_query = [None]
    _last_params = [None]

    def tracking_execute(query, params=None):
        _last_query[0] = query
        _last_params[0] = params

    mock_cursor.execute = tracking_execute

    def cursor_fetchone():
        query = _last_query[0] or ''
        params = _last_params[0]
        if 'worker_time_off' in query and params:
            worker_id = params[0]
            appt_date = params[1]
            for rec in time_off_records:
                if rec['worker_id'] != worker_id:
                    continue
                if rec.get('status', 'approved') != 'approved':
                    continue
                s = rec['start_date']
                e = rec['end_date']
                if isinstance(s, str):
                    s = date.fromisoformat(s)
                if isinstance(e, str):
                    e = date.fromisoformat(e)
                if isinstance(appt_date, datetime):
                    appt_date = appt_date.date()
                if s <= appt_date <= e:
                    return {
                        'id': rec.get('id', 1),
                        'start_date': rec['start_date'],
                        'end_date': rec['end_date'],
                        'type': rec.get('type', 'vacation')
                    }
            return None
        return None

    def cursor_fetchall():
        query = _last_query[0] or ''
        params = _last_params[0]
        if 'worker_assignments' in query or 'bookings' in query:
            if params and len(params) >= 1:
                worker_id = params[0]
                return [b for b in existing_bookings
                        if worker_id in b.get('assigned_worker_ids', [])]
        return []

    mock_cursor.fetchone = cursor_fetchone
    mock_cursor.fetchall = cursor_fetchall

    real_db.get_connection = MagicMock(return_value=mock_conn)
    real_db.return_connection = MagicMock()

    return real_db


# ============================================================
# Test: check_worker_availability blocks on approved leave
# ============================================================

class TestTimeOffBlocksAvailability:
    """Worker with approved time-off should be unavailable."""

    def test_approved_leave_blocks_booking(self):
        """Worker on approved vacation should not be available."""
        appt = next_weekday(hour=10)
        appt_date_str = appt.strftime('%Y-%m-%d')

        db = make_db_with_time_off(time_off_records=[{
            'id': 1,
            'worker_id': 1,
            'start_date': appt_date_str,
            'end_date': appt_date_str,
            'type': 'vacation',
            'status': 'approved'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is False
        assert result.get('on_leave') is True
        assert 'vacation' in result.get('message', '').lower()

    def test_approved_sick_leave_blocks_booking(self):
        """Worker on approved sick leave should not be available."""
        appt = next_weekday(hour=14)
        appt_date_str = appt.strftime('%Y-%m-%d')

        db = make_db_with_time_off(time_off_records=[{
            'id': 2,
            'worker_id': 5,
            'start_date': appt_date_str,
            'end_date': appt_date_str,
            'type': 'sick',
            'status': 'approved'
        }])

        result = db.check_worker_availability(
            worker_id=5,
            appointment_time=appt.isoformat(),
            duration_minutes=120,
            company_id=1
        )

        assert result['available'] is False
        assert result.get('on_leave') is True
        assert 'sick' in result.get('message', '').lower()

    def test_multi_day_leave_blocks_all_days(self):
        """Leave spanning multiple days should block any day in range."""
        start = next_weekday(hour=10, days_ahead=14)
        # 3-day leave
        leave_start = start.strftime('%Y-%m-%d')
        leave_end = (start + timedelta(days=2)).strftime('%Y-%m-%d')

        db = make_db_with_time_off(time_off_records=[{
            'id': 3,
            'worker_id': 1,
            'start_date': leave_start,
            'end_date': leave_end,
            'type': 'vacation',
            'status': 'approved'
        }])

        # Check each day in the range
        for day_offset in range(3):
            appt = start + timedelta(days=day_offset)
            result = db.check_worker_availability(
                worker_id=1,
                appointment_time=appt.isoformat(),
                duration_minutes=60,
                company_id=1
            )
            assert result['available'] is False, f"Day offset {day_offset} should be blocked"
            assert result.get('on_leave') is True

    def test_day_before_leave_is_available(self):
        """Day before leave starts should still be available."""
        leave_day = next_weekday(hour=10, days_ahead=14)
        day_before = leave_day - timedelta(days=1)
        # Make sure day_before is a weekday
        while day_before.weekday() >= 5:
            day_before -= timedelta(days=1)

        db = make_db_with_time_off(time_off_records=[{
            'id': 4,
            'worker_id': 1,
            'start_date': leave_day.strftime('%Y-%m-%d'),
            'end_date': leave_day.strftime('%Y-%m-%d'),
            'type': 'vacation',
            'status': 'approved'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=day_before.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is True

    def test_day_after_leave_is_available(self):
        """Day after leave ends should still be available."""
        leave_day = next_weekday(hour=10, days_ahead=14)
        day_after = leave_day + timedelta(days=1)
        while day_after.weekday() >= 5:
            day_after += timedelta(days=1)

        db = make_db_with_time_off(time_off_records=[{
            'id': 5,
            'worker_id': 1,
            'start_date': leave_day.strftime('%Y-%m-%d'),
            'end_date': leave_day.strftime('%Y-%m-%d'),
            'type': 'vacation',
            'status': 'approved'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=day_after.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is True


class TestPendingDeniedLeaveDoesNotBlock:
    """Pending or denied leave should NOT block bookings."""

    def test_pending_leave_does_not_block(self):
        """Pending leave should not prevent booking."""
        appt = next_weekday(hour=10)

        db = make_db_with_time_off(time_off_records=[{
            'id': 10,
            'worker_id': 1,
            'start_date': appt.strftime('%Y-%m-%d'),
            'end_date': appt.strftime('%Y-%m-%d'),
            'type': 'vacation',
            'status': 'pending'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is True

    def test_denied_leave_does_not_block(self):
        """Denied leave should not prevent booking."""
        appt = next_weekday(hour=10)

        db = make_db_with_time_off(time_off_records=[{
            'id': 11,
            'worker_id': 1,
            'start_date': appt.strftime('%Y-%m-%d'),
            'end_date': appt.strftime('%Y-%m-%d'),
            'type': 'personal',
            'status': 'denied'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is True


class TestOtherWorkerLeaveDoesNotAffect:
    """Leave for one worker should not affect another."""

    def test_different_worker_leave_no_effect(self):
        """Worker 2's leave should not block Worker 1."""
        appt = next_weekday(hour=10)

        db = make_db_with_time_off(time_off_records=[{
            'id': 20,
            'worker_id': 2,
            'start_date': appt.strftime('%Y-%m-%d'),
            'end_date': appt.strftime('%Y-%m-%d'),
            'type': 'vacation',
            'status': 'approved'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is True


# ============================================================
# Test: _find_available_workers_batch respects leave
# ============================================================

class TestBatchAvailabilityWithLeave:
    """The batch availability function should skip workers on leave."""

    def _make_batch_db(self):
        """Create a minimal DB mock for _calculate_job_end_time."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        db.get_connection = MagicMock(return_value=mock_conn)
        db.return_connection = MagicMock()
        return db

    def test_worker_on_leave_excluded_from_batch(self):
        """Worker with approved leave should not appear in available list."""
        from src.services.calendar_tools import _find_available_workers_batch

        slot = next_weekday(hour=10)
        db = self._make_batch_db()

        leave_records = [{
            'worker_id': 1,
            'start_date': slot.strftime('%Y-%m-%d'),
            'end_date': slot.strftime('%Y-%m-%d'),
        }]

        result = _find_available_workers_batch(
            slot_time=slot,
            duration_minutes=60,
            worker_bookings_by_id={1: [], 2: []},
            all_worker_ids=[1, 2],
            db=db,
            company_id=1,
            leave_records=leave_records
        )

        assert 1 not in result
        assert 2 in result

    def test_no_leave_all_workers_available(self):
        """Without leave records, all workers should be available."""
        from src.services.calendar_tools import _find_available_workers_batch

        slot = next_weekday(hour=10)
        db = self._make_batch_db()

        result = _find_available_workers_batch(
            slot_time=slot,
            duration_minutes=60,
            worker_bookings_by_id={1: [], 2: [], 3: []},
            all_worker_ids=[1, 2, 3],
            db=db,
            company_id=1,
            leave_records=[]
        )

        assert set(result) == {1, 2, 3}

    def test_all_workers_on_leave_none_available(self):
        """If all workers are on leave, none should be available."""
        from src.services.calendar_tools import _find_available_workers_batch

        slot = next_weekday(hour=10)
        db = self._make_batch_db()

        leave_records = [
            {'worker_id': 1, 'start_date': slot.strftime('%Y-%m-%d'), 'end_date': slot.strftime('%Y-%m-%d')},
            {'worker_id': 2, 'start_date': slot.strftime('%Y-%m-%d'), 'end_date': slot.strftime('%Y-%m-%d')},
        ]

        result = _find_available_workers_batch(
            slot_time=slot,
            duration_minutes=60,
            worker_bookings_by_id={1: [], 2: []},
            all_worker_ids=[1, 2],
            db=db,
            company_id=1,
            leave_records=leave_records
        )

        assert len(result) == 0

    def test_leave_on_different_day_no_effect(self):
        """Leave on a different day should not affect the slot day."""
        from src.services.calendar_tools import _find_available_workers_batch

        slot = next_weekday(hour=10)
        other_day = (slot + timedelta(days=3)).strftime('%Y-%m-%d')
        db = self._make_batch_db()

        leave_records = [{
            'worker_id': 1,
            'start_date': other_day,
            'end_date': other_day,
        }]

        result = _find_available_workers_batch(
            slot_time=slot,
            duration_minutes=60,
            worker_bookings_by_id={1: []},
            all_worker_ids=[1],
            db=db,
            company_id=1,
            leave_records=leave_records
        )

        assert 1 in result

    def test_multi_day_leave_blocks_middle_day(self):
        """Multi-day leave should block a slot in the middle of the range."""
        from src.services.calendar_tools import _find_available_workers_batch

        slot = next_weekday(hour=10, days_ahead=14)
        leave_start = (slot - timedelta(days=1)).strftime('%Y-%m-%d')
        leave_end = (slot + timedelta(days=1)).strftime('%Y-%m-%d')
        db = self._make_batch_db()

        leave_records = [{
            'worker_id': 1,
            'start_date': leave_start,
            'end_date': leave_end,
        }]

        result = _find_available_workers_batch(
            slot_time=slot,
            duration_minutes=60,
            worker_bookings_by_id={1: [], 2: []},
            all_worker_ids=[1, 2],
            db=db,
            company_id=1,
            leave_records=leave_records
        )

        assert 1 not in result
        assert 2 in result


# ============================================================
# Test: Normal bookings still work (no regressions)
# ============================================================

class TestNormalBookingsStillWork:
    """Ensure normal booking flow is not broken by time-off changes."""

    def test_worker_available_no_leave_no_conflicts(self):
        """Worker with no leave and no conflicts should be available."""
        appt = next_weekday(hour=10)

        db = make_db_with_time_off(time_off_records=[], existing_bookings=[])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is True

    def test_worker_unavailable_due_to_conflict_not_leave(self):
        """Worker with a conflicting booking (not leave) should be unavailable."""
        appt = next_weekday(hour=10)

        db = make_db_with_time_off(
            time_off_records=[],
            existing_bookings=[{
                'id': 100,
                'appointment_time': appt,
                'duration_minutes': 120,
                'service_type': 'Plumbing',
                'client_name': 'Test',
                'address': '123 Main St',
                'assigned_worker_ids': [1]
            }]
        )

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is False
        # Should NOT be marked as on_leave
        assert result.get('on_leave') is not True

    def test_different_time_no_conflict(self):
        """Worker with a booking at a different time should be available."""
        appt = next_weekday(hour=10)
        other_time = appt.replace(hour=15)

        db = make_db_with_time_off(
            time_off_records=[],
            existing_bookings=[{
                'id': 101,
                'appointment_time': other_time,
                'duration_minutes': 60,
                'service_type': 'Cleaning',
                'client_name': 'Test',
                'address': '',
                'assigned_worker_ids': [1]
            }]
        )

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert result['available'] is True


# ============================================================
# Test: get_workers_on_leave DB function
# ============================================================

class TestGetWorkersOnLeave:
    """Test the get_workers_on_leave database function."""

    def test_function_exists(self):
        """get_workers_on_leave should exist on the DB wrapper."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        assert hasattr(PostgreSQLDatabaseWrapper, 'get_workers_on_leave')

    def test_returns_list(self):
        """get_workers_on_leave should return a list."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper

        db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        db.get_connection = MagicMock(return_value=mock_conn)
        db.return_connection = MagicMock()

        result = db.get_workers_on_leave(1, date.today(), date.today() + timedelta(days=7))
        assert isinstance(result, list)

    def test_handles_missing_table_gracefully(self):
        """Should return empty list if table doesn't exist."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper

        db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("relation does not exist")
        db.get_connection = MagicMock(return_value=mock_conn)
        db.return_connection = MagicMock()

        result = db.get_workers_on_leave(1, date.today(), date.today() + timedelta(days=7))
        assert result == []


# ============================================================
# Test: Leave message content
# ============================================================

class TestLeaveMessageContent:
    """Verify the leave message returned to the AI is informative."""

    def test_message_includes_leave_type(self):
        """The unavailability message should mention the leave type."""
        appt = next_weekday(hour=10)

        db = make_db_with_time_off(time_off_records=[{
            'id': 30,
            'worker_id': 1,
            'start_date': appt.strftime('%Y-%m-%d'),
            'end_date': appt.strftime('%Y-%m-%d'),
            'type': 'personal',
            'status': 'approved'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert 'personal' in result['message'].lower()

    def test_message_includes_date_range(self):
        """The unavailability message should include the leave dates."""
        appt = next_weekday(hour=10, days_ahead=14)
        start = appt.strftime('%Y-%m-%d')
        end = (appt + timedelta(days=4)).strftime('%Y-%m-%d')

        db = make_db_with_time_off(time_off_records=[{
            'id': 31,
            'worker_id': 1,
            'start_date': start,
            'end_date': end,
            'type': 'vacation',
            'status': 'approved'
        }])

        result = db.check_worker_availability(
            worker_id=1,
            appointment_time=appt.isoformat(),
            duration_minutes=60,
            company_id=1
        )

        assert start in result['message'] or end in result['message']
