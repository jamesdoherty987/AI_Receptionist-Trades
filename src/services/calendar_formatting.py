"""
Formatting and utility helpers for calendar operations.

Extracted from calendar_tools.py for maintainability.
Contains: fuzzy_match_name, find_jobs_on_day, format_duration_label,
_format_slot_ranges, naturalize_availability_summary, _parse_booking_date.
"""

import logging
import re

logger = logging.getLogger(__name__)


def fuzzy_match_name(spoken_name: str, candidate_names: list) -> tuple:
    """
    Fuzzy match a spoken name against a list of candidate names.
    Handles common speech-to-text variations and partial matches.
    
    Args:
        spoken_name: The name the caller said (may be partial or have STT errors)
        candidate_names: List of actual customer names from bookings
        
    Returns:
        Tuple of (best_match_name, confidence_score 0-100, matched_booking_index)
    """
    from difflib import SequenceMatcher
    import unicodedata
    
    if not spoken_name or not candidate_names:
        return (None, 0, -1)
    
    def strip_accents(s):
        """Remove accents/diacritics so STT output matches accented names (e.g. Sean matches Seán)"""
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    
    spoken_lower = strip_accents(spoken_name.lower().strip())
    best_match = None
    best_score = 0
    best_index = -1
    
    spoken_parts = spoken_lower.split()
    
    for idx, candidate in enumerate(candidate_names):
        if not candidate:
            continue
        candidate_lower = strip_accents(candidate.lower().strip())
        
        # Strategy 1: Exact match (100%)
        if spoken_lower == candidate_lower:
            return (candidate, 100, idx)
        
        candidate_parts = candidate_lower.split()
        
        # Strategy 2: Both first AND last name match exactly (95%)
        if len(spoken_parts) >= 2 and len(candidate_parts) >= 2:
            if spoken_parts[0] == candidate_parts[0] and spoken_parts[-1] == candidate_parts[-1]:
                score = 95
                if score > best_score:
                    best_score = score
                    best_match = candidate
                    best_index = idx
                continue
        
        # Strategy 3: One name part matches exactly + other part is close
        # BUT only if the non-matching part has high similarity (>= 0.80)
        # This prevents "James Dorothy" matching "James Doherty" (Dorothy/Doherty = 0.67)
        # and "Josh Smith" matching "John Smith" (Josh/John = 0.50)
        strategy3_matched = False
        if len(spoken_parts) >= 2 and len(candidate_parts) >= 2:
            first_exact = spoken_parts[0] == candidate_parts[0]
            last_exact = spoken_parts[-1] == candidate_parts[-1]
            
            if first_exact and not last_exact:
                last_sim = SequenceMatcher(None, spoken_parts[-1], candidate_parts[-1]).ratio()
                if last_sim >= 0.80:
                    score = 80 + int(last_sim * 10)  # 80-90 range
                    if score > best_score:
                        best_score = score
                        best_match = candidate
                        best_index = idx
                    strategy3_matched = True
            elif last_exact and not first_exact:
                first_sim = SequenceMatcher(None, spoken_parts[0], candidate_parts[0]).ratio()
                if first_sim >= 0.80:
                    score = 80 + int(first_sim * 10)  # 80-90 range
                    if score > best_score:
                        best_score = score
                        best_match = candidate
                        best_index = idx
                    strategy3_matched = True
        
        # Strategy 4: Single-word name exact match against any part (75%)
        if len(spoken_parts) == 1 and len(spoken_parts[0]) >= 3:
            for cp in candidate_parts:
                if spoken_parts[0] == cp:
                    score = 75
                    if score > best_score:
                        best_score = score
                        best_match = candidate
                        best_index = idx
        
        # Strategy 5: Full name SequenceMatcher for close typos (scaled 0-75)
        # Only consider if ratio >= 0.85 to avoid false positives
        seq_ratio = SequenceMatcher(None, spoken_lower, candidate_lower).ratio()
        if seq_ratio >= 0.85:
            seq_score = int(seq_ratio * 75)
            if seq_score > best_score:
                best_score = seq_score
                best_match = candidate
                best_index = idx
    
    return (best_match, int(best_score), best_index)


def find_jobs_on_day(target_date, db, company_id: int, google_calendar=None) -> list:
    """
    Find all jobs/bookings on a specific day.
    Handles both full-day jobs and multiple shorter jobs.
    
    Args:
        target_date: The date to search (datetime object)
        db: Database instance
        company_id: Company ID for filtering
        google_calendar: Optional Google Calendar service
        
    Returns:
        List of dicts with job info: [{name, time, service, is_full_day, booking_id, event_id}, ...]
    """
    from datetime import datetime, timedelta
    
    jobs_on_day = []
    
    # Get day boundaries
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    # First check database bookings
    if db:
        try:
            all_bookings = db.get_all_bookings(company_id=company_id)
            for booking in all_bookings:
                if booking.get('status') in ['cancelled', 'completed']:
                    continue
                
                appt_time = booking.get('appointment_time')
                if not appt_time:
                    continue
                
                # Parse appointment time
                if isinstance(appt_time, str):
                    try:
                        appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    except:
                        continue
                elif hasattr(appt_time, 'replace'):
                    appt_time = appt_time.replace(tzinfo=None)
                
                # Check if on target day (including multi-day jobs that span into this day)
                if day_start <= appt_time < day_end:
                    # Job starts on this day
                    duration = booking.get('duration_minutes', 60)
                    is_full_day = duration >= 480  # 8+ hours
                    
                    # Get employee names if assigned
                    employee_names = []
                    assigned_ids = booking.get('assigned_employee_ids', [])
                    if assigned_ids and db:
                        for wid in assigned_ids:
                            employee = db.get_employee(wid, company_id=company_id)
                            if employee:
                                employee_names.append(employee.get('name', ''))
                    
                    jobs_on_day.append({
                        'name': booking.get('client_name') or booking.get('customer_name') or 'Unknown',
                        'time': appt_time.strftime('%I:%M %p') if not is_full_day else 'Full day',
                        'service': booking.get('service_type') or booking.get('service') or 'Job',
                        'is_full_day': is_full_day,
                        'booking_id': booking.get('id'),
                        'event_id': booking.get('calendar_event_id'),
                        'duration_minutes': duration,
                        'assigned_employees': employee_names,
                        'appointment_time': appt_time.strftime('%Y-%m-%d %H:%M:%S')  # Convert to string for JSON
                    })
                elif appt_time < day_start:
                    # Job started before this day — check if it spans into this day
                    duration = booking.get('duration_minutes', 60)
                    if duration > 1440:  # Multi-day job (> 24 hours)
                        # Skip closed days — the job doesn't run on days the company is closed
                        try:
                            from src.utils.config import config as _cfg
                            _biz_day_indices = _cfg.get_business_days_indices(company_id=company_id)
                        except Exception:
                            _biz_day_indices = [0, 1, 2, 3, 4]
                        
                        if day_start.weekday() not in _biz_day_indices:
                            continue  # Target day is a closed day, skip
                        
                        # Use business-day calculation: "1 week" = 5 biz days, not 7
                        from src.utils.duration_utils import duration_to_business_days
                        biz_days_needed = duration_to_business_days(duration, company_id=company_id)
                        # Walk forward from start counting business days
                        _cur = appt_time.replace(hour=0, minute=0, second=0, microsecond=0)
                        _counted = 0
                        _last_biz_day = _cur
                        for _ in range(365):
                            if _cur.weekday() in _biz_day_indices:
                                _counted += 1
                                _last_biz_day = _cur
                                if _counted >= biz_days_needed:
                                    break
                            _cur += timedelta(days=1)
                        # Job ends at closing on the last business day
                        try:
                            _biz_hours = _cfg.get_business_hours(company_id=company_id)
                            _closing_hour = _biz_hours.get('end', 17)
                        except Exception:
                            _closing_hour = 17
                        job_end = _last_biz_day.replace(hour=_closing_hour, minute=0, second=0, microsecond=0)
                        if job_end > day_start:
                            # This multi-day job extends into the target day
                            employee_names = []
                            assigned_ids = booking.get('assigned_employee_ids', [])
                            if assigned_ids and db:
                                for wid in assigned_ids:
                                    employee = db.get_employee(wid, company_id=company_id)
                                    if employee:
                                        employee_names.append(employee.get('name', ''))
                            
                            jobs_on_day.append({
                                'name': booking.get('client_name') or booking.get('customer_name') or 'Unknown',
                                'time': 'Full day (cont.)',
                                'service': booking.get('service_type') or booking.get('service') or 'Job',
                                'is_full_day': True,
                                'booking_id': booking.get('id'),
                                'event_id': booking.get('calendar_event_id'),
                                'duration_minutes': duration,
                                'assigned_employees': employee_names,
                                'appointment_time': day_start.strftime('%Y-%m-%d %H:%M:%S'),  # Show as start of this day
                                'is_continuation': True  # Flag that this is a continuation
                            })
        except Exception as e:
            logger.error(f"[FIND_JOBS] Database error: {e}")
    
    # Also check Google Calendar if available (for legacy/external bookings)
    if google_calendar and hasattr(google_calendar, 'service') and google_calendar.service:
        try:
            time_min = day_start.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            time_max = day_end.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            
            request = google_calendar.service.events().list(
                calendarId=google_calendar.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            )
            events_result = google_calendar._execute_with_retry(request)
            events = events_result.get('items', [])
            
            for event in events:
                event_id = event.get('id')
                # Skip if already found in database
                if any(j.get('event_id') == event_id for j in jobs_on_day):
                    continue
                
                summary = event.get('summary', '')
                # Extract name from summary (format: "Service - Name" or just name)
                if ' - ' in summary:
                    name = summary.split(' - ')[-1].strip()
                    service = summary.split(' - ')[0].strip()
                else:
                    name = summary
                    service = 'Appointment'
                
                # Get event time
                event_start_str = event.get('start', {}).get('dateTime')
                if event_start_str:
                    try:
                        event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                        event_end_str = event.get('end', {}).get('dateTime')
                        if event_end_str:
                            event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00')).replace(tzinfo=None)
                            duration = int((event_end - event_start).total_seconds() / 60)
                        else:
                            duration = 60
                        
                        is_full_day = duration >= 480
                        
                        jobs_on_day.append({
                            'name': name,
                            'time': event_start.strftime('%I:%M %p') if not is_full_day else 'Full day',
                            'service': service,
                            'is_full_day': is_full_day,
                            'booking_id': None,
                            'event_id': event_id,
                            'duration_minutes': duration,
                            'assigned_employees': [],
                            'appointment_time': event_start.strftime('%Y-%m-%d %H:%M:%S')  # Convert to string for JSON
                        })
                    except Exception as e:
                        logger.warning(f"[FIND_JOBS] Could not parse event time: {e}")
        except Exception as e:
            logger.warning(f"[FIND_JOBS] Google Calendar error: {e}")
    
    # Sort by time (appointment_time is now a string)
    jobs_on_day.sort(key=lambda x: x.get('appointment_time') or '0000-00-00 00:00:00')
    
    logger.info(f"[FIND_JOBS] Found {len(jobs_on_day)} jobs on {target_date.strftime('%Y-%m-%d')}: {[j['name'] for j in jobs_on_day]}")
    return jobs_on_day


def _parse_booking_date(date_iso: str):
    """Parse an ISO date string and return just the date portion."""
    from datetime import datetime as dt_cls
    try:
        return dt_cls.fromisoformat(date_iso).date()
    except (ValueError, TypeError):
        return None


def format_duration_label(duration_minutes: int) -> str:
    """Convert duration in minutes to a human-readable label like '1 week' or '2 days'."""
    if duration_minutes >= 40320:
        return "about a month"
    elif duration_minutes >= 30240:
        return "about 3 weeks"
    elif duration_minutes >= 20160:
        return "about 2 weeks"
    elif duration_minutes >= 10080:
        return "about a week"
    elif duration_minutes >= 5760:
        days = round(duration_minutes / 1440)
        return f"about a {days} day"
    elif duration_minutes >= 2880:
        days = round(duration_minutes / 1440)
        return f"about a {days} day"
    elif duration_minutes >= 1440:
        return "a full day"
    elif duration_minutes >= 480:
        return "a full day"
    else:
        hours = duration_minutes / 60
        whole = int(hours)
        fraction = hours - whole
        # Convert .5 to "and a half" for natural TTS speech
        if abs(fraction - 0.5) < 0.01:
            if whole == 0:
                return "about a half hour"
            return f"about a {whole} and a half hour"
        elif hours == whole:
            return f"about a {whole} hour"
        return f"about a {hours:.1f} hour"


def _format_slot_ranges(day_slots: list) -> str:
    """
    Format a list of slot datetimes into a human-readable range string,
    correctly handling gaps (e.g., "from 8 am to 2 pm" or "from 8 am to 10 am and 3 pm").
    
    Consecutive slots (up to 60 min apart) are grouped into ranges.
    Non-consecutive slots start a new range.
    """
    from datetime import timedelta
    
    if not day_slots:
        return ""
    
    # Auto-detect slot interval from the data (handles both 30-min and 60-min slots)
    if len(day_slots) >= 2:
        gap = (day_slots[1] - day_slots[0]).total_seconds() / 60
        max_gap = max(gap + 5, 65)  # Allow small tolerance above detected interval
    else:
        max_gap = 65  # Default: allow up to 65 min gap (covers 60-min slots)
    
    # Group consecutive slots into ranges
    ranges = []
    range_start = day_slots[0]
    range_end = day_slots[0]
    
    for i in range(1, len(day_slots)):
        if (day_slots[i] - range_end).total_seconds() / 60 <= max_gap:
            range_end = day_slots[i]
        else:
            ranges.append((range_start, range_end))
            range_start = day_slots[i]
            range_end = day_slots[i]
    ranges.append((range_start, range_end))
    
    def fmt(t):
        if t.minute == 0:
            return t.strftime('%I %p').lstrip('0').lower()
        return t.strftime('%I:%M %p').lstrip('0').lower()
    
    # Single range
    if len(ranges) == 1:
        s, e = ranges[0]
        if s == e:
            return fmt(s)
        return f"from {fmt(s)} to {fmt(e)}"
    
    # Multiple ranges — format each, then join naturally
    parts = []
    single_slots = []
    for s, e in ranges:
        if s == e:
            single_slots.append(fmt(s))
        else:
            parts.append(f"{fmt(s)} to {fmt(e)}")
    
    # If ALL ranges are single slots, use "at X or Y" style
    if not parts and single_slots:
        if len(single_slots) == 2:
            return f"at {single_slots[0]} or {single_slots[1]}"
        return f"at {', '.join(single_slots[:-1])}, or {single_slots[-1]}"
    
    # Mix of ranges and single slots — combine them
    all_parts = parts + [f"at {s}" for s in single_slots]
    if len(all_parts) == 2:
        return f"from {all_parts[0]} and {all_parts[1]}"
    return f"from {', '.join(all_parts[:-1])}, and {all_parts[-1]}"


def naturalize_availability_summary(day_summaries: list, is_full_day: bool = False) -> str:
    """
    Convert structured day availability into natural, conversational speech.
    Uses GPT-4o-mini for fast, natural language generation.
    
    Args:
        day_summaries: List of day summaries like ["Monday the 16th: full day available", "Tuesday the 17th: 2 pm or 4 pm"]
        is_full_day: Whether this is a full-day service
        
    Returns:
        Natural language summary suitable for voice
    """
    import time as time_module
    
    if not day_summaries:
        return "I don't have any availability for that time period."
    
    # For single day with simple availability, just clean it up without API call
    if len(day_summaries) == 1:
        summary = day_summaries[0]
        # Simple cleanup for single day
        if "full day available" in summary.lower():
            day = summary.split(":")[0]
            return f"We're available to start on {day}"
        elif ": free " in summary.lower():
            parts = summary.split(": ", 1)
            day = parts[0]
            times = parts[1][5:]  # Strip "free " prefix
            return f"On {day}, I have {times}"
        elif "only" in summary.lower():
            parts = summary.split(": ")
            day = parts[0]
            time = parts[1].replace(" only", "")
            return f"I've only got {time} on {day}"
        else:
            return summary.replace(": ", ", I have ")
    
    # For 2-4 days, build a natural sentence without API call for speed
    if len(day_summaries) <= 4:
        if is_full_day:
            # Extract just the day names for full-day jobs
            days = []
            for summary in day_summaries:
                day = summary.split(":")[0].strip()
                days.append(day)
            
            if len(days) == 2:
                return f"We're available to start on {days[0]} or {days[1]}"
            elif len(days) == 3:
                return f"We're available to start on {days[0]}, {days[1]}, or {days[2]}"
            else:
                return f"We're available to start on {days[0]}, {days[1]}, {days[2]}, or {days[3]}"
        else:
            # For shorter jobs, include time info
            parts = []
            for summary in day_summaries[:3]:  # Max 3 for readability
                if ": " in summary:
                    day, times = summary.split(": ", 1)
                    if times.lower().startswith("free "):
                        # Strip "free " prefix — the rest already has "from"/"at" as needed
                        times = times[5:]
                        parts.append(f"{day} {times}")
                    elif "or" in times:
                        parts.append(f"{day} at {times}")
                    elif "only" in times:
                        parts.append(f"{day} {times}")
                    else:
                        parts.append(f"{day} {times}")
                else:
                    parts.append(summary)
            
            if len(parts) == 2:
                return f"I have {parts[0]}, and {parts[1]}"
            else:
                return f"I have {', '.join(parts[:-1])}, and {parts[-1]}"
    
    # For more than 4 days, use a quick LLM call to make it conversational
    try:
        from openai import OpenAI
        from src.utils.config import config
        
        start_time = time_module.time()
        
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Build the raw data
        raw_summary = "; ".join(day_summaries)
        
        # Different prompts for full-day vs short jobs
        if is_full_day:
            system_prompt = "Convert availability into ONE natural sentence. ALWAYS include the FULL date labels exactly as given (e.g. 'Wednesday the 25th of March') — never shorten to just the day name. Mention 2-4 days. Example: 'I've got a full day open on Wednesday the 25th of March, Thursday the 26th of March, and Friday the 27th of March'. Be brief."
        else:
            system_prompt = "Convert availability into ONE natural sentence. ALWAYS include the FULL date labels exactly as given (e.g. 'Wednesday the 25th of March') — never shorten to just the day name. Mention 2-4 days with times. Example: 'I have Wednesday the 25th of March at 2 pm, Thursday the 26th at 10 am, and Friday the 27th from 9 am to 5 pm'. Be brief."
        
        response = client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": raw_summary
                }
            ],
            **config.max_tokens_param(value=100),
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        # Sanitize: LLM might return bullet points despite "ONE sentence" instruction
        result = re.sub(r'\n\s*[-•*·]\s*', ', ', result)
        result = re.sub(r'\n+', ' ', result)
        result = re.sub(r':\s*,\s*', ': ', result)
        duration = time_module.time() - start_time
        logger.info(f"[NATURALIZE] Converted availability in {duration:.2f}s: '{result[:50]}...'")
        
        return result
        
    except Exception as e:
        logger.warning(f"[NATURALIZE] Failed to naturalize, using fallback: {e}")
        # Fallback: simple join
        if len(day_summaries) == 2:
            return f"{day_summaries[0]}, and {day_summaries[1]}"
        else:
            return f"{', '.join(day_summaries[:-1])}, and {day_summaries[-1]}"

