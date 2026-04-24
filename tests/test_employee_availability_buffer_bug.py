"""
Test for the employee availability buffer mismatch bug.

Bug: When creating a job in the employee portal with multiple employees assigned,
the calendar shows a time slot as available (green) but clicking "Create Job"
fails with "Employee is not available at this time".

Root cause: The calendar availability endpoint computed booking end times using
exact durations (no buffer), but db.check_employee_availability() added a 15-minute
buffer to both the new appointment and existing bookings. This caused the
pre-submit availability check (checkEmployeeAvailability) to find false conflicts
for slots immediately after existing bookings.

Fix: Removed the phantom 15-minute buffer from check_employee_availability and
get_conflicting_bookings so they match the calendar display.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestBufferMismatchFix:
    """Verify that check_employee_availability matches calendar slot availability."""

    def _make_db(self):
        """Create a real DB wrapper instance (no DB connection needed for _calculate_job_end_time)."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
        return db

    def test_no_buffer_in_calculate_job_end_time_default(self):
        """_calculate_job_end_time should default to 0 buffer (no phantom gap)."""
        db = self._make_db()
        start = datetime(2026, 3, 30, 9, 0)
        # 1-hour job starting at 9am should end at exactly 10am, not 10:15
        end = db._calculate_job_end_time(start, 60, 9, 17)
        assert end == datetime(2026, 3, 30, 10, 0), f"Expected 10:00, got {end}"

    def test_no_buffer_in_calculate_job_end_time_full_day(self):
        """Full-day job should end at business close, not 15 mins after."""
        db = self._make_db()
        start = datetime(2026, 3, 30, 9, 0)
        end = db._calculate_job_end_time(start, 480, 9, 17)
        assert end == datetime(2026, 3, 30, 17, 0), f"Expected 17:00, got {end}"

    def test_explicit_buffer_still_works(self):
        """Callers can still pass an explicit buffer if needed."""
        db = self._make_db()
        start = datetime(2026, 3, 30, 9, 0)
        end = db._calculate_job_end_time(start, 60, 9, 17, buffer_minutes=15)
        assert end == datetime(2026, 3, 30, 10, 15), f"Expected 10:15, got {end}"


class TestEmployeeAvailabilityNoFalseConflict:
    """
    Reproduce the exact bug scenario:
    - Employee A has a job from 9:00-10:00
    - Calendar shows 10:00 as available (green)
    - check_employee_availability should ALSO say 10:00 is available
    """

    def _make_db_mock(self, existing_jobs):
        """Create a mock DB that returns the given existing jobs for an employee."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # First query: time-off check → no time off
        # Second query: existing jobs
        mock_cursor.fetchone.return_value = None  # No time off
        mock_cursor.fetchall.return_value = existing_jobs

        db.get_connection = MagicMock(return_value=mock_conn)
        db.return_connection = MagicMock()

        return db

    def test_slot_right_after_existing_job_is_available(self):
        """A slot starting exactly when another job ends should be available."""
        # Employee has a 1-hour job from 9:00-10:00
        existing_jobs = [{
            'id': 100,
            'appointment_time': datetime(2026, 3, 30, 9, 0),
            'duration_minutes': 60,
            'service_type': 'Plumbing',
            'client_name': 'John',
            'address': '123 Main St'
        }]

        db = self._make_db_mock(existing_jobs)

        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]

            # Check availability at 10:00 (right after the existing job ends)
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time=datetime(2026, 3, 30, 10, 0),
                duration_minutes=60,
                company_id=1
            )

        assert result['available'] is True, (
            f"Slot at 10:00 should be available (existing job ends at 10:00). "
            f"Got: available={result['available']}, message={result.get('message', '')}"
        )

    def test_overlapping_slot_is_unavailable(self):
        """A slot that genuinely overlaps with an existing job should be unavailable."""
        # Employee has a 2-hour job from 9:00-11:00
        existing_jobs = [{
            'id': 100,
            'appointment_time': datetime(2026, 3, 30, 9, 0),
            'duration_minutes': 120,
            'service_type': 'Plumbing',
            'client_name': 'John',
            'address': '123 Main St'
        }]

        db = self._make_db_mock(existing_jobs)

        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]

            # Check availability at 10:00 (overlaps with 9:00-11:00 job)
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time=datetime(2026, 3, 30, 10, 0),
                duration_minutes=60,
                company_id=1
            )

        assert result['available'] is False, (
            f"Slot at 10:00 should be unavailable (existing job runs 9:00-11:00). "
            f"Got: available={result['available']}"
        )

    def test_multi_employee_back_to_back_all_available(self):
        """
        Reproduce the exact user scenario:
        3 employees, each has different jobs, but all are free at 14:00.
        check_employee_availability should say available for all of them.
        """
        # Employee 1: job 9:00-10:00
        jobs_w1 = [{
            'id': 101, 'appointment_time': datetime(2026, 3, 30, 9, 0),
            'duration_minutes': 60, 'service_type': 'Plumbing',
            'client_name': 'Alice', 'address': '1 St'
        }]
        # Employee 2: job 10:00-12:00
        jobs_w2 = [{
            'id': 102, 'appointment_time': datetime(2026, 3, 30, 10, 0),
            'duration_minutes': 120, 'service_type': 'Electrical',
            'client_name': 'Bob', 'address': '2 St'
        }]
        # Employee 3: job 12:00-13:00
        jobs_w3 = [{
            'id': 103, 'appointment_time': datetime(2026, 3, 30, 12, 0),
            'duration_minutes': 60, 'service_type': 'Painting',
            'client_name': 'Carol', 'address': '3 St'
        }]

        for employee_id, jobs, label in [(1, jobs_w1, 'W1'), (2, jobs_w2, 'W2'), (3, jobs_w3, 'W3')]:
            db = self._make_db_mock(jobs)
            with patch('src.utils.config.config') as mock_config:
                mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
                mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]

                result = db.check_employee_availability(
                    employee_id=employee_id,
                    appointment_time=datetime(2026, 3, 30, 14, 0),
                    duration_minutes=60,
                    company_id=1
                )

            assert result['available'] is True, (
                f"{label} should be available at 14:00 but got: "
                f"available={result['available']}, message={result.get('message', '')}"
            )

    def test_back_to_back_slot_not_falsely_rejected(self):
        """
        The key bug scenario: Employee has job ending at 13:00.
        User picks 13:00 slot (shown as green on calendar).
        check_employee_availability must NOT reject it.
        """
        existing_jobs = [{
            'id': 100,
            'appointment_time': datetime(2026, 3, 30, 12, 0),
            'duration_minutes': 60,
            'service_type': 'Plumbing',
            'client_name': 'John',
            'address': '123 Main St'
        }]

        db = self._make_db_mock(existing_jobs)

        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]

            result = db.check_employee_availability(
                employee_id=1,
                appointment_time=datetime(2026, 3, 30, 13, 0),
                duration_minutes=60,
                company_id=1
            )

        assert result['available'] is True, (
            f"13:00 slot should be available (previous job ends at 13:00). "
            f"This was the bug — the 15-min buffer falsely rejected this. "
            f"Got: available={result['available']}, conflicts={result.get('conflicts', [])}"
        )


class TestGetConflictingBookingsNoBuffer:
    """Verify get_conflicting_bookings doesn't use phantom buffer."""

    def test_no_false_conflict_for_adjacent_booking(self):
        """A booking starting right when another ends should not be flagged as conflicting."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Existing booking: 9:00-10:00 (60 min)
        mock_cursor.fetchall.return_value = [{
            'id': 100,
            'client_id': 1,
            'appointment_time': datetime(2026, 3, 30, 9, 0),
            'service_type': 'Plumbing',
            'duration_minutes': 60
        }]

        db.get_connection = MagicMock(return_value=mock_conn)
        db.return_connection = MagicMock()

        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]

            # New booking at 10:00-11:00 — should NOT conflict
            conflicts = db.get_conflicting_bookings(
                start_time='2026-03-30 10:00:00',
                end_time='2026-03-30 11:00:00',
                company_id=1
            )

        assert len(conflicts) == 0, (
            f"Booking at 10:00 should not conflict with 9:00-10:00 booking. "
            f"Got {len(conflicts)} conflicts: {conflicts}"
        )

    def test_true_overlap_is_detected(self):
        """A booking that genuinely overlaps should be detected."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Existing booking: 9:00-11:00 (120 min)
        mock_cursor.fetchall.return_value = [{
            'id': 100,
            'client_id': 1,
            'appointment_time': datetime(2026, 3, 30, 9, 0),
            'service_type': 'Plumbing',
            'duration_minutes': 120
        }]

        db.get_connection = MagicMock(return_value=mock_conn)
        db.return_connection = MagicMock()

        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]

            # New booking at 10:00-11:00 — SHOULD conflict with 9:00-11:00
            conflicts = db.get_conflicting_bookings(
                start_time='2026-03-30 10:00:00',
                end_time='2026-03-30 11:00:00',
                company_id=1
            )

        assert len(conflicts) == 1, (
            f"Booking at 10:00 should conflict with 9:00-11:00 booking. "
            f"Got {len(conflicts)} conflicts"
        )
