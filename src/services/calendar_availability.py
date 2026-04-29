"""
Availability checking helpers for calendar operations.

Extracted from calendar_tools.py for maintainability.
These functions handle slot checking, employee availability, and day finding.
"""

import logging

logger = logging.getLogger(__name__)


def _check_slot_against_bookings(slot_time, duration_minutes, employee_bookings_by_id, employee_ids, db, company_id=None):
    """
    Check if a time slot is free for ALL employees by comparing against pre-fetched bookings.
    Uses in-memory overlap checks instead of individual DB queries.
    """
    from src.utils.config import config
    try:
        business_hours = config.get_business_hours(company_id=company_id)
        biz_start = business_hours.get('start', 9)
        biz_end = business_hours.get('end', 17)
    except:
        biz_start = 9
        biz_end = 17
    
    buffer_minutes = 0
    slot_end = db._calculate_job_end_time(slot_time, duration_minutes, biz_start, biz_end, buffer_minutes, company_id=company_id)
    
    for wid in employee_ids:
        bookings = employee_bookings_by_id.get(wid, [])
        for bk in bookings:
            bk_start = bk['appointment_time']
            bk_dur = bk.get('duration_minutes') or 60
            bk_end = db._calculate_job_end_time(bk_start, bk_dur, biz_start, biz_end, buffer_minutes, company_id=company_id)
            if slot_time < bk_end and slot_end > bk_start:
                return False
    return True


def _find_available_employees_batch(slot_time, duration_minutes, employee_bookings_by_id, all_employee_ids, db, company_id=None, employee_restrictions=None, leave_records=None):
    """
    Find which employees from the pool are free at a given slot using pre-fetched bookings.
    Returns list of available employee IDs (in-memory, no DB calls).
    """
    from src.utils.config import config
    try:
        business_hours = config.get_business_hours(company_id=company_id)
        biz_start = business_hours.get('start', 9)
        biz_end = business_hours.get('end', 17)
    except:
        biz_start = 9
        biz_end = 17
    
    buffer_minutes = 0
    slot_end = db._calculate_job_end_time(slot_time, duration_minutes, biz_start, biz_end, buffer_minutes, company_id=company_id)
    
    available = []
    slot_date = slot_time.date() if hasattr(slot_time, 'date') else slot_time
    
    # Build set of employees on leave for this specific slot date
    employees_on_leave = set()
    if leave_records:
        from datetime import date as _date, datetime as _dt
        for rec in leave_records:
            s = rec['start_date']
            e = rec['end_date']
            if isinstance(s, str):
                s = _dt.strptime(s, '%Y-%m-%d').date()
            elif isinstance(s, _dt):
                s = s.date()
            if isinstance(e, str):
                e = _dt.strptime(e, '%Y-%m-%d').date()
            elif isinstance(e, _dt):
                e = e.date()
            if s <= slot_date <= e:
                employees_on_leave.add(rec['employee_id'])
    
    for wid in all_employee_ids:
        if wid in employees_on_leave:
            continue
        bookings = employee_bookings_by_id.get(wid, [])
        is_free = True
        for bk in bookings:
            bk_start = bk['appointment_time']
            bk_dur = bk.get('duration_minutes') or 60
            bk_end = db._calculate_job_end_time(bk_start, bk_dur, biz_start, biz_end, buffer_minutes, company_id=company_id)
            if slot_time < bk_end and slot_end > bk_start:
                is_free = False
                break
        if is_free:
            available.append(wid)
    
    # Apply employee restrictions (service-level)
    if employee_restrictions and available:
        restriction_type = employee_restrictions.get('type', 'all')
        restricted_ids = employee_restrictions.get('employee_ids', [])
        if restriction_type == 'only' and restricted_ids:
            available = [w for w in available if w in restricted_ids]
        elif restriction_type == 'except' and restricted_ids:
            available = [w for w in available if w not in restricted_ids]
    
    return available


def _find_employee_available_days(db, employee_ids: list, duration_minutes: int, exclude_booking_id: int = None, company_id: int = None, days_to_check: int = 28, exclude_date=None) -> list:
    """
    Find available days for specific employee(s) in the next N days.
    Used during rescheduling to suggest alternative days when the requested day isn't available.
    """
    from datetime import datetime, timedelta
    from src.utils.config import config
    
    if not db or not employee_ids:
        return [], []
    
    available_days = []
    available_dates_iso = []
    today = datetime.now()
    
    try:
        business_days = config.get_business_days_indices(company_id=company_id)
    except:
        business_days = [0, 1, 2, 3, 4]
    
    try:
        business_hours = config.get_business_hours(company_id=company_id)
        biz_start_hour = business_hours.get('start', 9)
        biz_end_hour = business_hours.get('end', 17)
    except:
        biz_start_hour = 9
        biz_end_hour = 17
    
    if duration_minutes > 1440:
        from src.utils.duration_utils import duration_to_business_days
        biz_days_needed = duration_to_business_days(duration_minutes, company_id=company_id)
    else:
        biz_days_needed = 1
    
    for day_offset in range(1, days_to_check + 1):
        check_date = today + timedelta(days=day_offset)
        
        if check_date.weekday() not in business_days:
            continue
        
        if exclude_date and check_date.date() == exclude_date.date():
            continue
        
        if duration_minutes >= 480:
            check_time = check_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
        else:
            check_time = check_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
        
        if biz_days_needed > 1:
            all_days_free = True
            span_date = check_date
            days_checked = 0
            while days_checked < biz_days_needed:
                if span_date.weekday() not in business_days:
                    span_date += timedelta(days=1)
                    continue
                
                span_time = span_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
                for employee_id in employee_ids:
                    availability = db.check_employee_availability(
                        employee_id=employee_id,
                        appointment_time=span_time,
                        duration_minutes=480,
                        exclude_booking_id=exclude_booking_id,
                        company_id=company_id
                    )
                    if not availability.get('available', False):
                        all_days_free = False
                        break
                
                if not all_days_free:
                    break
                days_checked += 1
                span_date += timedelta(days=1)
            
            if not all_days_free:
                continue
        else:
            all_available = True
            for employee_id in employee_ids:
                availability = db.check_employee_availability(
                    employee_id=employee_id,
                    appointment_time=check_time,
                    duration_minutes=duration_minutes,
                    exclude_booking_id=exclude_booking_id,
                    company_id=company_id
                )
                if not availability.get('available', False):
                    all_available = False
                    break
            
            if not all_available:
                continue
        
        day_name = check_date.strftime('%A')
        month_name = check_date.strftime('%B')
        day_num = check_date.day
        suffix = 'th' if 11 <= day_num <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day_num % 10, 'th')
        if biz_days_needed > 1:
            available_days.append(f"{day_name} the {day_num}{suffix} of {month_name} ({biz_days_needed} days)")
        else:
            available_days.append(f"{day_name} the {day_num}{suffix} of {month_name}")
        available_dates_iso.append(check_date.strftime('%Y-%m-%d'))
    
    logger.info(f"[RESCHEDULE] Found {len(available_days)} available days for employees {employee_ids}: {available_days[:5]}")
    return available_days, available_dates_iso
