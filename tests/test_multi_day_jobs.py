"""
Tests for multi-day job handling across the system.

Ensures that jobs of any duration (1 hour to 1 month) work correctly for:
1. Worker availability checking (clash detection across multiple days)
2. Job end time calculation (_calculate_job_end_time)
3. Conflict detection (get_conflicting_bookings)
4. Calendar display (find_jobs_on_day shows multi-day jobs on all spanned days)
5. Multi-worker multi-day availability (_find_worker_available_days)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock


class TestCalculateJobEndTime:
    """Test the _calculate_job_end_time helper for all duration ranges."""

    def _make_db(self):
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            return db

    def test_short_job_1_hour(self):
        """1-hour job: end = start + 60 + 15 buffer"""
        db = self._make_db()
        start = datetime(2026, 3, 23, 10, 0)
        end = db._calculate_job_end_time(start, 60, 9, 17, 15)
        assert end == datetime(2026, 3, 23, 11, 15)

    def test_short_job_4_hours(self):
        """4-hour job: end = start + 240 + 15 buffer"""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)
        end = db._calculate_job_end_time(start, 240, 9, 17, 15)
        assert end == datetime(2026, 3, 23, 13, 15)

    def test_full_day_job_480_mins(self):
        """8-hour (full day) job: end = closing time + buffer"""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)
        end = db._calculate_job_end_time(start, 480, 9, 17, 15)
        assert end == datetime(2026, 3, 23, 17, 15)

    def test_full_day_job_1440_mins(self):
        """24-hour (1 day) job: end = closing time + buffer (same day)"""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)
        end = db._calculate_job_end_time(start, 1440, 9, 17, 15)
        assert end == datetime(2026, 3, 23, 17, 15)

    @patch('src.utils.config.config.get_business_days_indices', return_value=[0, 1, 2, 3, 4])
    def test_multi_day_2_days(self, mock_biz_days):
        """2-day job (2880 mins): should span 2 business days"""
        db = self._make_db()
        # Monday 9am, 9-17 business hours
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        end = db._calculate_job_end_time(start, 2880, 9, 17, 15)
        # 2880 / 1440 = 2 business days
        # Day 1 (Mon): counted
        # Day 2 (Tue): counted -> ends Tue closing
        assert end == datetime(2026, 3, 24, 17, 15)

    @patch('src.utils.config.config.get_business_days_indices', return_value=[0, 1, 2, 3, 4])
    def test_multi_day_1_week(self, mock_biz_days):
        """1-week job (10080 mins): spans 7 business days, skips weekends"""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        end = db._calculate_job_end_time(start, 10080, 9, 17, 15)
        # 10080 / 1440 = 7 business days
        # Mon(1), Tue(2), Wed(3), Thu(4), Fri(5), skip Sat/Sun, Mon(6), Tue(7)
        # Ends Tue Mar 31 at closing
        assert end == datetime(2026, 3, 31, 17, 15)

    @patch('src.utils.config.config.get_business_days_indices', return_value=[0, 1, 2, 3, 4])
    def test_multi_day_skips_weekends(self, mock_biz_days):
        """Multi-day job starting Friday should skip weekend"""
        db = self._make_db()
        # Friday 9am, job just over 1 day (1441 mins)
        start = datetime(2026, 3, 27, 9, 0)  # Friday
        end = db._calculate_job_end_time(start, 1441, 9, 17, 15)
        # 1441 / 1440 = 1.0007 -> ceil = 2 business days
        # Day 1 (Fri): counted
        # Skip Sat, Sun
        # Day 2 (Mon Mar 30): counted -> ends Mon closing
        assert end == datetime(2026, 3, 30, 17, 15)

    def test_zero_buffer(self):
        """Job with zero buffer"""
        db = self._make_db()
        start = datetime(2026, 3, 23, 10, 0)
        end = db._calculate_job_end_time(start, 60, 9, 17, 0)
        assert end == datetime(2026, 3, 23, 11, 0)


class TestWorkerAvailabilityMultiDay:
    """Test that worker availability correctly detects conflicts with multi-day jobs."""

    def _make_db_with_jobs(self, existing_jobs):
        """Create a mock DB that returns the given existing jobs for a worker."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = existing_jobs

        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            return db

    def test_2_day_job_blocks_second_day(self):
        """A 2-day job starting Monday should block Tuesday."""
        existing_jobs = [{
            'id': 1,
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday 9am
            'duration_minutes': 2880,  # 2 days
            'service_type': 'Renovation',
            'client_name': 'Test Client',
            'address': '123 Main St'
        }]
        db = self._make_db_with_jobs(existing_jobs)

        # Try to book Tuesday 9am — should conflict
        result = db.check_worker_availability(
            worker_id=1,
            appointment_time='2026-03-24T09:00:00',  # Tuesday
            duration_minutes=60,
            company_id=1
        )
        assert result['available'] is False
        assert len(result['conflicts']) == 1

    def test_2_day_job_doesnt_block_next_week(self):
        """A 2-day job starting Monday should NOT block next Monday."""
        existing_jobs = [{
            'id': 1,
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday 9am
            'duration_minutes': 2880,  # 2 days
            'service_type': 'Renovation',
            'client_name': 'Test Client',
            'address': '123 Main St'
        }]
        db = self._make_db_with_jobs(existing_jobs)

        # Try to book next Monday — should be fine
        result = db.check_worker_availability(
            worker_id=1,
            appointment_time='2026-03-30T09:00:00',  # Next Monday
            duration_minutes=60,
            company_id=1
        )
        assert result['available'] is True

    def test_1_week_job_blocks_all_5_days(self):
        """A 1-week job should block all business days it spans."""
        existing_jobs = [{
            'id': 1,
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday 9am
            'duration_minutes': 10080,  # 1 week
            'service_type': 'Major Renovation',
            'client_name': 'Test Client',
            'address': '123 Main St'
        }]
        db = self._make_db_with_jobs(existing_jobs)

        # Wednesday of the same week should conflict
        result = db.check_worker_availability(
            worker_id=1,
            appointment_time='2026-03-25T09:00:00',  # Wednesday
            duration_minutes=60,
            company_id=1
        )
        assert result['available'] is False

    def test_short_job_no_false_multi_day_conflict(self):
        """A 1-hour job should NOT block the next day."""
        existing_jobs = [{
            'id': 1,
            'appointment_time': datetime(2026, 3, 23, 10, 0),  # Monday 10am
            'duration_minutes': 60,  # 1 hour
            'service_type': 'Quick Fix',
            'client_name': 'Test Client',
            'address': '123 Main St'
        }]
        db = self._make_db_with_jobs(existing_jobs)

        # Tuesday should be free
        result = db.check_worker_availability(
            worker_id=1,
            appointment_time='2026-03-24T10:00:00',  # Tuesday
            duration_minutes=60,
            company_id=1
        )
        assert result['available'] is True

    def test_full_day_job_blocks_same_day_only(self):
        """A full-day (480 min) job should block same day but not next day."""
        existing_jobs = [{
            'id': 1,
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday 9am
            'duration_minutes': 480,  # 8 hours (full day)
            'service_type': 'Full Day Job',
            'client_name': 'Test Client',
            'address': '123 Main St'
        }]
        db = self._make_db_with_jobs(existing_jobs)

        # Same day afternoon should conflict
        result = db.check_worker_availability(
            worker_id=1,
            appointment_time='2026-03-23T14:00:00',  # Monday 2pm
            duration_minutes=60,
            company_id=1
        )
        assert result['available'] is False

        # Next day should be free
        result = db.check_worker_availability(
            worker_id=1,
            appointment_time='2026-03-24T09:00:00',  # Tuesday
            duration_minutes=60,
            company_id=1
        )
        assert result['available'] is True


class TestGetConflictingBookingsMultiDay:
    """Test that get_conflicting_bookings detects multi-day overlaps."""

    def test_multi_day_job_detected_on_later_day(self):
        """A 3-day job starting Monday should be detected as conflicting on Wednesday."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # Simulate a booking that started Monday with 3-day duration
        mock_cursor.fetchall.return_value = [{
            'id': 1,
            'client_id': 10,
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'service_type': 'Renovation',
            'duration_minutes': 4320  # 3 days
        }]

        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()

            # Check Wednesday — the multi-day job should show as conflicting
            conflicts = db.get_conflicting_bookings(
                start_time='2026-03-25 08:00:00',  # Wednesday
                end_time='2026-03-25 18:00:00',
                company_id=1
            )
            assert len(conflicts) == 1
            assert conflicts[0]['id'] == 1

    def test_short_job_not_detected_on_next_day(self):
        """A 1-hour job on Monday should NOT conflict with a Wednesday query."""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [{
            'id': 2,
            'client_id': 10,
            'appointment_time': datetime(2026, 3, 23, 10, 0),  # Monday 10am
            'service_type': 'Quick Fix',
            'duration_minutes': 60  # 1 hour
        }]

        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()

            conflicts = db.get_conflicting_bookings(
                start_time='2026-03-25 08:00:00',  # Wednesday
                end_time='2026-03-25 18:00:00',
                company_id=1
            )
            assert len(conflicts) == 0


class TestFindJobsOnDayMultiDay:
    """Test that find_jobs_on_day shows multi-day jobs on all spanned days."""

    def test_multi_day_job_shows_on_second_day(self):
        """A 3-day job starting Monday should appear when querying Tuesday."""
        from src.services.calendar_tools import find_jobs_on_day

        mock_db = MagicMock()
        mock_db.get_all_bookings.return_value = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 4320,  # 3 days
            'service_type': 'Renovation',
            'status': 'confirmed',
            'assigned_worker_ids': [],
            'calendar_event_id': None
        }]

        # Query Tuesday
        tuesday = datetime(2026, 3, 24, 12, 0)
        jobs = find_jobs_on_day(tuesday, mock_db, company_id=1)

        assert len(jobs) == 1
        assert jobs[0]['name'] == 'John Smith'
        assert jobs[0]['is_full_day'] is True
        assert jobs[0].get('is_continuation') is True

    def test_multi_day_job_not_shown_after_end(self):
        """A 2-day job starting Monday should NOT appear on Thursday."""
        from src.services.calendar_tools import find_jobs_on_day

        mock_db = MagicMock()
        mock_db.get_all_bookings.return_value = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 2880,  # 2 days
            'service_type': 'Renovation',
            'status': 'confirmed',
            'assigned_worker_ids': [],
            'calendar_event_id': None
        }]

        # Query Thursday — should not show
        thursday = datetime(2026, 3, 26, 12, 0)
        jobs = find_jobs_on_day(thursday, mock_db, company_id=1)
        assert len(jobs) == 0

    def test_single_day_job_only_on_start_day(self):
        """A 1-hour job should only appear on its start day."""
        from src.services.calendar_tools import find_jobs_on_day

        mock_db = MagicMock()
        mock_db.get_all_bookings.return_value = [{
            'id': 2,
            'client_name': 'Jane Doe',
            'appointment_time': datetime(2026, 3, 23, 14, 0),  # Monday 2pm
            'duration_minutes': 60,
            'service_type': 'Quick Fix',
            'status': 'confirmed',
            'assigned_worker_ids': [],
            'calendar_event_id': None
        }]

        # Monday — should show
        monday = datetime(2026, 3, 23, 12, 0)
        jobs = find_jobs_on_day(monday, mock_db, company_id=1)
        assert len(jobs) == 1

        # Tuesday — should NOT show
        tuesday = datetime(2026, 3, 24, 12, 0)
        jobs = find_jobs_on_day(tuesday, mock_db, company_id=1)
        assert len(jobs) == 0

    def test_1_week_job_shows_on_friday(self):
        """A 1-week job starting Monday should appear on Friday."""
        from src.services.calendar_tools import find_jobs_on_day

        mock_db = MagicMock()
        mock_db.get_all_bookings.return_value = [{
            'id': 3,
            'client_name': 'Big Project Client',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 10080,  # 1 week
            'service_type': 'Major Renovation',
            'status': 'confirmed',
            'assigned_worker_ids': [],
            'calendar_event_id': None
        }]

        # Friday of same week
        friday = datetime(2026, 3, 27, 12, 0)
        jobs = find_jobs_on_day(friday, mock_db, company_id=1)
        assert len(jobs) == 1
        assert jobs[0].get('is_continuation') is True


class TestGoogleCalendarMultiDay:
    """Test that Google Calendar sync handles multi-day events correctly."""

    def test_google_calendar_creates_correct_duration_event(self):
        """book_appointment should create event with correct multi-day duration."""
        from src.services.google_calendar_oauth import CompanyGoogleCalendar

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert

        with patch.object(CompanyGoogleCalendar, '__init__', lambda *a, **kw: None):
            gcal = CompanyGoogleCalendar.__new__(CompanyGoogleCalendar)
            gcal.service = mock_service
            gcal.calendar_id = 'primary'
            gcal.timezone = 'Europe/Dublin'
            gcal.company_id = 1
            gcal._execute_with_retry = MagicMock(return_value={'id': 'test_event_123'})

            start = datetime(2026, 3, 23, 9, 0)
            duration = 10080  # 1 week

            result = gcal.book_appointment(
                summary='Major Renovation - Test Client',
                start_time=start,
                duration_minutes=duration,
                description='Test',
                phone_number='1234567890'
            )

            # Verify the event was created
            assert result is not None
            # Verify the insert was called with correct end time
            call_args = mock_events.insert.call_args
            event_body = call_args[1]['body'] if 'body' in call_args[1] else call_args[0][0] if call_args[0] else call_args[1].get('body')
            
            expected_end = start + timedelta(minutes=duration)
            assert expected_end.strftime('%Y-%m-%dT%H:%M:%S') in event_body['end']['dateTime']

    def test_google_calendar_check_availability_multi_day(self):
        """check_availability should work for multi-day durations."""
        from src.services.google_calendar_oauth import CompanyGoogleCalendar

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_list = MagicMock()
        mock_events.list.return_value = mock_list

        with patch.object(CompanyGoogleCalendar, '__init__', lambda *a, **kw: None):
            gcal = CompanyGoogleCalendar.__new__(CompanyGoogleCalendar)
            gcal.service = mock_service
            gcal.calendar_id = 'primary'
            gcal.timezone = 'Europe/Dublin'
            gcal.company_id = 1
            gcal._execute_with_retry = MagicMock(return_value={'items': []})

            start = datetime(2026, 3, 23, 9, 0)
            # Check availability for a 1-week job
            is_available = gcal.check_availability(start, duration_minutes=10080)
            assert is_available is True

            # Verify the time range queried spans the full duration
            call_args = mock_events.list.call_args
            time_max = call_args[1].get('timeMax') or call_args[0][0] if call_args[0] else None
            # The list call should have been made with a timeMax 1 week out
            expected_end = start + timedelta(minutes=10080)
            assert expected_end.strftime('%Y-%m-%dT%H:%M:%S') in str(call_args)


class TestDurationEdgeCases:
    """Test edge cases for various duration values."""

    def _make_db(self):
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            return db

    def test_30_min_job(self):
        """30-minute job should work correctly."""
        db = self._make_db()
        start = datetime(2026, 3, 23, 10, 0)
        end = db._calculate_job_end_time(start, 30, 9, 17, 15)
        assert end == datetime(2026, 3, 23, 10, 45)

    def test_479_min_job_not_full_day(self):
        """479-minute job (just under 8 hours) should use exact duration, not full-day logic."""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)
        end = db._calculate_job_end_time(start, 479, 9, 17, 15)
        # 479 + 15 = 494 minutes = 8h14m from 9am = 5:14pm
        assert end == datetime(2026, 3, 23, 17, 14)

    def test_480_min_job_is_full_day(self):
        """480-minute job (exactly 8 hours) should use full-day logic."""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)
        end = db._calculate_job_end_time(start, 480, 9, 17, 15)
        assert end == datetime(2026, 3, 23, 17, 15)

    def test_1441_min_triggers_multi_day(self):
        """1441-minute job (just over 1 day) should trigger multi-day logic."""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        with patch('src.utils.config.config.get_business_days_indices', return_value=[0, 1, 2, 3, 4]):
            end = db._calculate_job_end_time(start, 1441, 9, 17, 15)
        # 1441 / 1440 = 1.0007 -> ceil = 2 business days
        # Day 1 Mon: counted, Day 2 Tue: counted -> ends Tue closing
        assert end == datetime(2026, 3, 24, 17, 15)

    @patch('src.utils.config.config.get_business_days_indices', return_value=[0, 1, 2, 3, 4])
    def test_4_week_job(self, mock_biz_days):
        """4-week (1 month) job should span 28 business days."""
        db = self._make_db()
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        end = db._calculate_job_end_time(start, 40320, 9, 17, 15)
        # 40320 / 1440 = 28 business days
        # 28 business days = 5 weeks + 3 days (skipping weekends)
        # Week 1: Mon-Fri (5), Week 2: Mon-Fri (10), Week 3: Mon-Fri (15),
        # Week 4: Mon-Fri (20), Week 5: Mon-Fri (25), Week 6: Mon-Wed (28)
        # Start Mon Mar 23, end Wed Apr 29
        assert end == datetime(2026, 4, 29, 17, 15)
