"""
Tests for DatabaseCalendarService multi-day job handling.
Covers the no-worker code path (database_calendar.py).
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


def make_service(bookings=None):
    """Create a DatabaseCalendarService with mocked DB and config."""
    from src.services.database_calendar import DatabaseCalendarService
    db = MagicMock()
    db.get_all_bookings = MagicMock(return_value=bookings or [])
    svc = DatabaseCalendarService(db, company_id=1)
    return svc


# Patch config and settings for all tests
@pytest.fixture(autouse=True)
def patch_config():
    mock_config = MagicMock()
    mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
    mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
    mock_config.BUSINESS_HOURS_START = 9
    mock_config.BUSINESS_HOURS_END = 17

    mock_settings = MagicMock()
    mock_settings.get_default_duration_minutes.return_value = 60

    with patch('src.services.database_calendar.config', mock_config), \
         patch('src.services.database_calendar.get_settings_manager', return_value=mock_settings, create=True), \
         patch('src.services.settings_manager.get_settings_manager', return_value=mock_settings, create=True):
        yield


class TestCalculateJobEndTime:
    """Test the _calculate_job_end_time helper on DatabaseCalendarService."""

    def test_short_job(self):
        svc = make_service()
        start = datetime(2026, 3, 23, 10, 0)  # Monday
        end = svc._calculate_job_end_time(start, 60)
        assert end == datetime(2026, 3, 23, 11, 0)

    def test_full_day_job(self):
        svc = make_service()
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        end = svc._calculate_job_end_time(start, 480)
        assert end == datetime(2026, 3, 23, 17, 0)

    def test_1440_min_job(self):
        svc = make_service()
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        end = svc._calculate_job_end_time(start, 1440)
        assert end == datetime(2026, 3, 23, 17, 0)

    def test_2_day_job(self):
        svc = make_service()
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        end = svc._calculate_job_end_time(start, 2880)  # 2 days
        assert end == datetime(2026, 3, 24, 17, 0)  # Tuesday 5pm

    def test_1_week_job(self):
        svc = make_service()
        start = datetime(2026, 3, 23, 9, 0)  # Monday
        end = svc._calculate_job_end_time(start, 10080)  # 1 week = 5 biz days
        # 5 biz days from Monday: Mon(1),Tue(2),Wed(3),Thu(4),Fri(5) = Mar 27
        assert end == datetime(2026, 3, 27, 17, 0)

    def test_2_day_job_thursday_skips_weekend(self):
        svc = make_service()
        start = datetime(2026, 3, 26, 9, 0)  # Thursday
        end = svc._calculate_job_end_time(start, 2880)  # 2 days
        # Thu + Fri = 2 biz days, ends Friday 5pm
        assert end == datetime(2026, 3, 27, 17, 0)

    def test_3_day_job_thursday_skips_weekend(self):
        svc = make_service()
        start = datetime(2026, 3, 26, 9, 0)  # Thursday
        end = svc._calculate_job_end_time(start, 4320)  # 3 days
        # Thu, Fri, (skip Sat/Sun), Mon = 3 biz days, ends Monday 5pm
        assert end == datetime(2026, 3, 30, 17, 0)


class TestGetAvailableSlotsMultiDay:
    """Test that get_available_slots_for_day detects multi-day jobs from previous days."""

    def test_2_day_job_blocks_second_day(self):
        """A 2-day job starting Monday should block Tuesday too."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 2880,  # 2 days
        }]
        svc = make_service(bookings)
        # Check Tuesday — should have NO slots (blocked by Monday's 2-day job)
        tuesday = datetime(2026, 3, 24, 9, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)  # Sunday (past check)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            slots = svc.get_available_slots_for_day(tuesday, service_duration=60)
        assert len(slots) == 0

    def test_2_day_job_doesnt_block_wednesday(self):
        """A 2-day job Mon-Tue should NOT block Wednesday."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 2880,  # 2 days
        }]
        svc = make_service(bookings)
        wednesday = datetime(2026, 3, 25, 9, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            slots = svc.get_available_slots_for_day(wednesday, service_duration=60)
        assert len(slots) > 0

    def test_1_week_job_blocks_friday(self):
        """A 1-week (7 biz day) job starting Monday should block Friday."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 10080,  # 7 biz days
        }]
        svc = make_service(bookings)
        friday = datetime(2026, 3, 27, 9, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            slots = svc.get_available_slots_for_day(friday, service_duration=60)
        assert len(slots) == 0

    def test_cancelled_job_doesnt_block(self):
        """Cancelled multi-day jobs should not block anything."""
        bookings = [{
            'status': 'cancelled',
            'appointment_time': datetime(2026, 3, 23, 9, 0),
            'duration_minutes': 2880,
        }]
        svc = make_service(bookings)
        tuesday = datetime(2026, 3, 24, 9, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            slots = svc.get_available_slots_for_day(tuesday, service_duration=60)
        assert len(slots) > 0


class TestCheckAvailabilityMultiDay:
    """Test that check_availability detects multi-day job overlaps."""

    def test_2_day_job_conflicts_on_second_day(self):
        """Booking on Tuesday should conflict with a 2-day job starting Monday."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 2880,
        }]
        svc = make_service(bookings)
        tuesday_10am = datetime(2026, 3, 24, 10, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = svc.check_availability(tuesday_10am, duration_minutes=60)
        assert result is False

    def test_no_conflict_after_multiday_ends(self):
        """Booking on Wednesday should NOT conflict with Mon-Tue 2-day job."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 23, 9, 0),
            'duration_minutes': 2880,
        }]
        svc = make_service(bookings)
        wednesday_10am = datetime(2026, 3, 25, 10, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = svc.check_availability(wednesday_10am, duration_minutes=60)
        assert result is True

    def test_new_multiday_conflicts_with_existing_multiday(self):
        """A new 1-week job should conflict with an existing 2-day job in the same period."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 25, 9, 0),  # Wednesday
            'duration_minutes': 2880,  # 2 days (Wed-Thu)
        }]
        svc = make_service(bookings)
        # Try to book a 1-week job starting Monday — should conflict (overlaps Wed-Thu)
        monday_9am = datetime(2026, 3, 23, 9, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = svc.check_availability(monday_9am, duration_minutes=10080)
        assert result is False

    def test_short_job_no_conflict_with_short_job_different_time(self):
        """Two short jobs at different times should not conflict."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 23, 9, 0),
            'duration_minutes': 60,
        }]
        svc = make_service(bookings)
        monday_2pm = datetime(2026, 3, 23, 14, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = svc.check_availability(monday_2pm, duration_minutes=60)
        assert result is True

    def test_4_week_job_blocks_week_3(self):
        """A 4-week job should block a day in week 3."""
        bookings = [{
            'status': 'confirmed',
            'appointment_time': datetime(2026, 3, 23, 9, 0),  # Monday
            'duration_minutes': 40320,  # 4 weeks = 28 biz days
        }]
        svc = make_service(bookings)
        # Week 3 Wednesday = April 8
        week3_wed = datetime(2026, 4, 8, 10, 0)
        with patch('src.services.database_calendar.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 22, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = svc.check_availability(week3_wed, duration_minutes=60)
        assert result is False
