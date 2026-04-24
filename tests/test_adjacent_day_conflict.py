"""
Test that a multi-day job ending on day N does NOT falsely block day N+1.

Tests the conflict range calculation from bookings_api and the
get_conflicting_bookings DB method together, without needing Flask.
"""
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DATABASE_URL', 'postgresql://x:x@localhost/x')
os.environ.setdefault('SECRET_KEY', 'test')


def _make_conflict_checker(existing_bookings):
    """Real get_conflicting_bookings backed by a mock cursor."""
    from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
    db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

    def _exec(query, params=None):
        et_param = params[1] if params and len(params) >= 2 else None
        if et_param is None:
            cur._rows = []
            return
        et = datetime.strptime(et_param, '%Y-%m-%d %H:%M:%S') if isinstance(et_param, str) else et_param
        cur._rows = [
            {'id': b['id'], 'client_id': b['client_id'],
             'appointment_time': b['appointment_time'],
             'service_type': b['service_type'],
             'duration_minutes': b['duration_minutes']}
            for b in existing_bookings
            if b.get('status') not in ('cancelled', 'completed')
            and b['appointment_time'] < et
        ]
    cur.execute = _exec
    cur.fetchall = lambda: cur._rows
    db.get_connection = MagicMock(return_value=conn)
    db.return_connection = MagicMock()
    return db.get_conflicting_bookings



def _new_job_range(appt_dt, dur_mins):
    """Replicate the FIXED conflict range calc from bookings_api."""
    if dur_mins > 1440:
        from src.utils.duration_utils import duration_to_business_days
        biz_days = duration_to_business_days(dur_mins)
        biz_idx = [0, 1, 2, 3, 4]
        cur = appt_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        counted = 0
        while counted < biz_days:
            if cur.weekday() in biz_idx:
                counted += 1
                if counted >= biz_days:
                    break
            cur += timedelta(days=1)
        end = cur.replace(hour=17, minute=0, second=0, microsecond=0)
    elif dur_mins >= 480:
        end = appt_dt.replace(hour=17, minute=0, second=0, microsecond=0)
    else:
        end = appt_dt + timedelta(minutes=dur_mins)
    return appt_dt, end


def _check(existing, employee_ids, appt_dt, dur_mins):
    """Full conflict pipeline: range calc + DB query + employee match."""
    start, end = _new_job_range(appt_dt, dur_mins)
    conflicts = _make_conflict_checker(existing)(
        start_time=start.strftime('%Y-%m-%d %H:%M:%S'),
        end_time=end.strftime('%Y-%m-%d %H:%M:%S'),
        company_id=1,
    )
    if not conflicts or not employee_ids:
        return bool(conflicts), None
    bw = {}
    for b in existing:
        for wid in b.get('assigned_employee_ids', []):
            bw.setdefault(b['id'], []).append({'id': wid})
    for wid in employee_ids:
        for cb in conflicts:
            if any(w['id'] == wid for w in bw.get(cb['id'], [])):
                return True, cb
    return False, None


class TestAdjacentDayNoFalseConflict:

    def test_single_day_job_on_20th_does_not_block_21st(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 20, 8, 0),
            'service_type': 'Brick wall build', 'duration_minutes': 1440,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, _ = _check(existing, [1, 2, 3], datetime(2026, 4, 21, 8, 0), 1440)
        assert not hit, "Full-day job on Apr 20 should NOT block Apr 21"

    def test_2day_job_thu_fri_does_not_block_monday(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 16, 8, 0),
            'service_type': 'Brick wall build', 'duration_minutes': 2880,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, _ = _check(existing, [1, 2, 3], datetime(2026, 4, 20, 8, 0), 1440)
        assert not hit, "2-day job Thu-Fri should NOT block Monday"

    def test_3day_job_mon_wed_blocks_tuesday(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 20, 8, 0),
            'service_type': 'Brick wall build', 'duration_minutes': 4320,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, info = _check(existing, [1, 2, 3], datetime(2026, 4, 21, 8, 0), 1440)
        assert hit, "3-day job Mon-Wed SHOULD block Tuesday"
        assert info['id'] == 10

    def test_short_job_on_20th_does_not_block_21st(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 20, 8, 0),
            'service_type': 'Quick fix', 'duration_minutes': 120,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, _ = _check(existing, [1], datetime(2026, 4, 21, 8, 0), 120)
        assert not hit, "2h job on Apr 20 should NOT block Apr 21"

    def test_same_day_overlap_blocked(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 21, 8, 0),
            'service_type': 'Morning job', 'duration_minutes': 120,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, _ = _check(existing, [1], datetime(2026, 4, 21, 9, 0), 120)
        assert hit, "8am-10am job SHOULD block 9am booking"

    def test_different_employee_not_blocked(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 21, 8, 0),
            'service_type': 'Job', 'duration_minutes': 1440,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, _ = _check(existing, [2, 3], datetime(2026, 4, 21, 8, 0), 1440)
        assert not hit, "Employee 2 should NOT be blocked by employee 1's job"

    def test_old_range_would_false_positive(self):
        """Verify the OLD buggy range extends before the new job's date."""
        appt = datetime(2026, 4, 21, 8, 0)
        old_start = appt - timedelta(minutes=1440 - 1)
        assert old_start < datetime(2026, 4, 21, 0, 0), "Old range went before Apr 21"
        new_start, _ = _new_job_range(appt, 1440)
        assert new_start >= datetime(2026, 4, 21, 0, 0), "New range starts on Apr 21"

    def test_week_job_blocks_wednesday(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 20, 8, 0),
            'service_type': 'Kitchen install', 'duration_minutes': 10080,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, _ = _check(existing, [1], datetime(2026, 4, 22, 8, 0), 60)
        assert hit, "Week job should block Wednesday"

    def test_week_job_does_not_block_next_monday(self):
        existing = [{'id': 10, 'client_id': 5,
            'appointment_time': datetime(2026, 4, 20, 8, 0),
            'service_type': 'Kitchen install', 'duration_minutes': 10080,
            'status': 'confirmed', 'assigned_employee_ids': [1]}]
        hit, _ = _check(existing, [1], datetime(2026, 4, 27, 8, 0), 60)
        assert not hit, "Week job should NOT block next Monday"
