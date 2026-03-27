"""
Natural language date/time parsing utilities using AI
"""
from datetime import datetime, timedelta
import re
from openai import OpenAI
from src.utils.config import config

# Lazy initialization
_client = None

def get_openai_client():
    """Get or create OpenAI client instance with timeout"""
    global _client
    if _client is None:
        import httpx
        _client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=httpx.Timeout(15.0, connect=5.0)  # 5s connect, 15s total for date parsing
        )
    return _client


# OpenAI function for date/time parsing
DATETIME_PARSE_FUNCTION = {
    "name": "parse_datetime",
    "description": "Parse natural language date and time references into structured datetime components. CRITICAL: For weekday names (Monday, Tuesday, etc.), ALWAYS use day_of_week field, NEVER use month/day fields.",
    "parameters": {
        "type": "object",
        "properties": {
            "has_date": {
                "type": "boolean",
                "description": "Whether a specific date was mentioned (e.g., 'January 5', 'tomorrow', 'next Monday')"
            },
            "has_time": {
                "type": "boolean",
                "description": "Whether a specific time was mentioned (e.g., '2pm', '9:30 AM', 'morning')"
            },
            "year": {
                "type": "integer",
                "description": "Year if explicitly mentioned, otherwise null. DO NOT set this for weekday references like 'Monday' or 'next Tuesday'."
            },
            "month": {
                "type": "integer",
                "description": "Month number (1-12) ONLY if a specific month was mentioned (e.g., 'January 5', 'March 10'). DO NOT set this for weekday references like 'Monday' or 'next Friday'."
            },
            "day": {
                "type": "integer",
                "description": "Day of month (1-31) ONLY if a specific day number was mentioned (e.g., 'the 5th', 'January 10'). DO NOT set this for weekday references like 'Monday' or 'next Tuesday'."
            },
            "hour": {
                "type": "integer",
                "description": "Hour in 24-hour format (0-23). For times without AM/PM: 1-7 should default to PM (13-19), 8-11 should default to AM (8-11), 12 should default to noon (12)."
            },
            "minute": {
                "type": "integer",
                "description": "Minute (0-59), defaults to 0 if not specified"
            },
            "relative_days": {
                "type": "integer",
                "description": "Number of days from today ONLY for 'today' (0), 'tomorrow' (1), 'day after tomorrow' (2). Do NOT use for weekday names like Monday/Tuesday/etc - use day_of_week instead."
            },
            "day_of_week": {
                "type": "string",
                "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                "description": "CRITICAL: Day of week if ANY weekday name is mentioned (e.g., 'Monday', 'next Friday', 'this Tuesday', 'on Wednesday'). ALWAYS use this field for weekday names instead of month/day fields. This is the PRIMARY field for weekday references."
            },
            "is_next_week": {
                "type": "boolean",
                "description": "True ONLY if the phrase 'next week' was explicitly mentioned (not just 'next Monday'). For 'next Monday', use day_of_week='monday' instead."
            },
            "is_birth_date": {
                "type": "boolean",
                "description": "True if this appears to be a date of birth (year before 2007) rather than an appointment date"
            },
            "needs_clarification": {
                "type": "string",
                "description": "What information is missing or unclear: 'date', 'time', 'both', or null if complete"
            }
        },
        "required": ["has_date", "has_time"]
    }
}


def parse_datetime(text: str, require_time: bool = True, default_time: tuple = None, allow_past: bool = False) -> datetime:
    """
    Parse natural language date/time into datetime object using AI
    
    Args:
        text: Natural language time reference
        require_time: If True, returns None when no time specified. If False, uses default_time.
        default_time: Tuple of (hour, minute) to use when no time specified. Defaults to (9, 0).
        allow_past: If True, don't auto-adjust dates that are in the past. Defaults to False.
        
    Returns:
        Parsed datetime object, or None if require_time=True and no time specified
    """
    if not text:
        print(f"[WARNING] Empty text provided - returning None to prompt for date and time")
        return None
    
    # Set default time if not provided
    if default_time is None:
        default_time = (9, 0)
    
    text = text.strip()
    now = datetime.now()
    
    # FAST PATH: Handle common patterns without AI to save ~500ms per call
    import re
    
    # Fast path 1: ISO format dates (YYYY-MM-DD)
    iso_date_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$', text)
    if iso_date_match:
        year = int(iso_date_match.group(1))
        month = int(iso_date_match.group(2))
        day = int(iso_date_match.group(3))
        hour = int(iso_date_match.group(4)) if iso_date_match.group(4) else default_time[0]
        minute = int(iso_date_match.group(5)) if iso_date_match.group(5) else default_time[1]
        
        try:
            result = datetime(year, month, day, hour, minute)
            print(f"[DATE] Fast path ISO: '{text}' -> {result}")
            return result
        except ValueError as e:
            print(f"[DATE] Invalid ISO date '{text}': {e}")
            # Fall through to AI parsing
    
    # Fast path 2: "tomorrow at Xam/pm" or "today at Xam/pm"
    text_lower = text.lower().strip()
    relative_time_match = re.match(r'^(today|tomorrow)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', text_lower)
    if relative_time_match:
        rel_day = relative_time_match.group(1)
        hour = int(relative_time_match.group(2))
        minute = int(relative_time_match.group(3) or 0)
        am_pm = relative_time_match.group(4)
        
        # Handle AM/PM or default based on hour
        if am_pm == 'pm' and hour != 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0
        elif am_pm is None:
            # Default: 1-7 = PM, 8-11 = AM, 12 = noon
            if 1 <= hour <= 7:
                hour += 12
        
        days_ahead = 1 if rel_day == 'tomorrow' else 0
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        if days_ahead == 0 and result <= now:
            result += timedelta(days=1)
        print(f"[DATE] Fast path relative: '{text}' -> {result}")
        return result
    
    # Fast path 3: "[weekday] the [ordinal]" with optional time (e.g., "Tuesday the 31st at 8am", "Monday the 5th")
    weekday_names = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    weekday_ordinal_match = re.match(
        r'^(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+the\s+(\d{1,2})(?:st|nd|rd|th)(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?$',
        text_lower
    )
    if weekday_ordinal_match:
        day_name = weekday_ordinal_match.group(1)
        day_num = int(weekday_ordinal_match.group(2))
        hour_str = weekday_ordinal_match.group(3)
        minute_str = weekday_ordinal_match.group(4)
        am_pm = weekday_ordinal_match.group(5)
        
        # Find the next occurrence of this weekday that falls on this day number
        target_weekday = weekday_names[day_name]
        search_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        found_date = None
        for _ in range(365):
            if search_date.day == day_num and search_date.weekday() == target_weekday and search_date.date() >= now.date():
                found_date = search_date
                break
            search_date += timedelta(days=1)
        
        if found_date:
            if hour_str:
                hour = int(hour_str)
                minute = int(minute_str or 0)
                if am_pm == 'pm' and hour != 12:
                    hour += 12
                elif am_pm == 'am' and hour == 12:
                    hour = 0
                elif am_pm is None:
                    if 1 <= hour <= 7:
                        hour += 12
            elif require_time:
                print(f"[DATE] Fast path weekday+ordinal: '{text}' matched {found_date.strftime('%A, %B %d')} but no time specified - returning None")
                return None
            else:
                hour, minute = default_time
            
            result = found_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            print(f"[DATE] Fast path weekday+ordinal: '{text}' -> {result.strftime('%A, %B %d, %Y %I:%M %p')}")
            return result
        else:
            print(f"[DATE] Fast path weekday+ordinal: no {day_name} the {day_num} found in next year - falling through to AI")
    
    # Fast path 4: "[weekday] at Xam/pm" (e.g., "Monday at 2pm", "next Friday at 10am")
    weekday_match = re.match(r'^(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', text_lower)
    if weekday_match:
        day_name = weekday_match.group(1)
        hour = int(weekday_match.group(2))
        minute = int(weekday_match.group(3) or 0)
        am_pm = weekday_match.group(4)
        has_next = text_lower.startswith('next ')
        
        # Handle AM/PM or default
        if am_pm == 'pm' and hour != 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0
        elif am_pm is None:
            if 1 <= hour <= 7:
                hour += 12
        
        target_day = weekday_names[day_name]
        days_ahead = (target_day - now.weekday()) % 7
        
        if days_ahead == 0:
            # Today is the requested day
            requested_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if has_next or requested_time <= now:
                days_ahead = 7
        elif has_next:
            days_ahead += 7
        
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        print(f"[DATE] Fast path weekday: '{text}' -> {result}")
        return result
    
    # Fast path 5: "[weekday] in X weeks" / "[weekday] X weeks" / "in X weeks" / "X weeks time"
    # Handles: "Monday 2 weeks", "Monday in 2 weeks", "in 2 weeks", "2 weeks time", "2 weeks' time"
    weeks_match = re.search(r"(?:in\s+)?(\d+)\s+weeks?(?:['\u2019]?\s*time)?", text_lower)
    if weeks_match:
        num_weeks = int(weeks_match.group(1))
        
        # Check if a weekday was also mentioned
        detected_day = None
        for day_name, day_idx in weekday_names.items():
            if day_name in text_lower:
                detected_day = (day_name, day_idx)
                break
        
        if detected_day:
            day_name, target_day = detected_day
            # "Monday 2 weeks" = the Monday that falls roughly 2 weeks from now
            # Strategy: jump forward num_weeks * 7 days, then find the nearest occurrence
            # of the target weekday (same week or up to 6 days prior)
            future_date = now + timedelta(days=num_weeks * 7)
            # Find the target weekday in the same week as future_date
            days_offset = (target_day - future_date.weekday()) % 7
            # If offset would push us more than 3 days forward, go back instead
            # This keeps us centered around the "X weeks from now" point
            if days_offset > 3:
                days_offset -= 7
            days_ahead = num_weeks * 7 + days_offset
            
            # Check for time component
            time_match = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text_lower)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                am_pm = time_match.group(3)
                if am_pm == 'pm' and hour != 12:
                    hour += 12
                elif am_pm == 'am' and hour == 12:
                    hour = 0
            elif require_time:
                print(f"[DATE] Fast path weeks: '{text}' matched {day_name} in {num_weeks} weeks but no time - returning None")
                return None
            else:
                hour, minute = default_time
            
            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
            print(f"[DATE] Fast path weeks: '{text}' -> {day_name} in {num_weeks} weeks = {result.strftime('%A, %B %d, %Y')}")
            return result
        else:
            # No weekday, just "in 2 weeks" / "2 weeks time"
            days_ahead = num_weeks * 7
            
            time_match = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text_lower)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                am_pm = time_match.group(3)
                if am_pm == 'pm' and hour != 12:
                    hour += 12
                elif am_pm == 'am' and hour == 12:
                    hour = 0
            elif require_time:
                print(f"[DATE] Fast path weeks: '{text}' matched in {num_weeks} weeks but no time - returning None")
                return None
            else:
                hour, minute = default_time
            
            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
            print(f"[DATE] Fast path weeks: '{text}' -> in {num_weeks} weeks = {result.strftime('%A, %B %d, %Y')}")
            return result
    
    try:
        import time as time_module
        parse_start = time_module.time()
        client = get_openai_client()
        
        # Get current day of week for better context
        current_day_name = now.strftime('%A')
        
        # Use AI to parse the date/time with structured output
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are an expert at parsing natural language date and time references.

CURRENT DATE/TIME:
- Today is {current_day_name}, {now.strftime('%B %d, %Y')}
- Current time is {now.strftime('%I:%M %p')}

CRITICAL RULES FOR WEEKDAY NAMES (VERY IMPORTANT):
- When user says ANY weekday name (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday), you MUST use the 'day_of_week' field
- Do NOT use month/day fields for weekday references
- Do NOT use 'relative_days' for weekday names
- "next Monday", "this Monday", "on Monday", "Monday" → ALL use day_of_week: "monday"
- Use 'relative_days' ONLY for: 'today' (0), 'tomorrow' (1), 'day after tomorrow' (2)

CORRECT EXAMPLES:
- "Monday at 2pm" → day_of_week: "monday", hour: 14 (NOT month/day!)
- "next Monday" → day_of_week: "monday" (NOT month/day!)
- "next Friday at 3" → day_of_week: "friday", hour: 15
- "this Tuesday" → day_of_week: "tuesday"
- "on Wednesday" → day_of_week: "wednesday"
- "tomorrow at 9am" → relative_days: 1, hour: 9
- "today at 3pm" → relative_days: 0, hour: 15
- "January 15 at 2pm" → month: 1, day: 15, hour: 14 (specific date, NOT weekday)

WRONG (DO NOT DO THIS):
- "next Monday" → month: 2, day: 20 ❌ WRONG! Use day_of_week: "monday" instead

Remember: Today is {current_day_name}. If user says "{current_day_name}", that means TODAY (relative_days: 0)."""
                },
                {
                    "role": "user",
                    "content": f"Parse this date/time reference: {text}"
                }
            ],
            tools=[{"type": "function", "function": DATETIME_PARSE_FUNCTION}],
            tool_choice={"type": "function", "function": {"name": "parse_datetime"}},
            temperature=0.1,
            max_tokens=200
        )
        
        # Extract the parsed data
        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls or len(tool_calls) == 0:
            print(f"[WARNING] No tool call returned from AI - falling back to None")
            return None
        
        import json
        parsed = json.loads(tool_calls[0].function.arguments)
        
        parse_duration = time_module.time() - parse_start
        print(f"[DATE_TIMING] ⏱️ AI date parse took {parse_duration:.3f}s for '{text[:50]}'")
        
        print(f"[AI] AI parsed '{text}': {parsed}")
        
        # CRITICAL FIX: If AI returned month/day but text contains a weekday name WITHOUT an explicit date,
        # override with day_of_week. This catches cases where AI incorrectly converts "next Monday" to a specific date.
        # BUT: If the text contains an explicit date (month name, day number, or year), trust the AI's month/day parsing.
        text_lower = text.lower()
        weekday_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        detected_weekday = None
        for day_name, day_num in weekday_names.items():
            if day_name in text_lower:
                detected_weekday = day_name
                break
        
        # Check if text contains explicit date indicators (month names, day numbers, years)
        month_names = ['january', 'february', 'march', 'april', 'may', 'june', 
                       'july', 'august', 'september', 'october', 'november', 'december',
                       'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        # Check for day numbers like "the 23rd", "15th", "1st" - but NOT times like "at 9"
        day_number_match = re.search(r'\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b', text_lower)
        has_month_name = any(month in text_lower for month in month_names)
        has_year = bool(re.search(r'\b20\d{2}\b', text_lower))
        has_explicit_date = has_month_name or day_number_match or has_year
        
        # Extract the explicit day number if present (for "Monday the 23rd" type inputs)
        explicit_day_num = int(day_number_match.group(1)) if day_number_match else None
        
        if detected_weekday and parsed.get("month") and parsed.get("day") and not parsed.get("day_of_week") and not has_explicit_date:
            # AI incorrectly used month/day instead of day_of_week - fix it
            # Only do this when there's NO explicit date in the input
            print(f"[DATE_FIX] AI used month/day for weekday '{detected_weekday}' (no explicit date) - correcting to day_of_week")
            parsed["day_of_week"] = detected_weekday
            parsed["month"] = None
            parsed["day"] = None
            parsed["year"] = None
        elif detected_weekday and parsed.get("month") and parsed.get("day") and explicit_day_num and not has_month_name and not has_year:
            # AI returned month/day but input is "Wednesday the 1st" (weekday + ordinal, no month name)
            # We need to verify the weekday matches, or find the correct date
            target_weekday = weekday_names[detected_weekday]
            try:
                ai_date = datetime(parsed.get("year", now.year), parsed["month"], parsed["day"])
                if ai_date.weekday() != target_weekday:
                    # AI's date doesn't match the weekday - find the correct date
                    print(f"[DATE_FIX] AI date {ai_date.strftime('%B %d')} is {ai_date.strftime('%A')}, not {detected_weekday.capitalize()} - searching for correct date")
                    search_date = now
                    for _ in range(365):
                        if search_date.day == explicit_day_num and search_date.weekday() == target_weekday:
                            parsed["month"] = search_date.month
                            parsed["year"] = search_date.year
                            parsed["relative_days"] = None
                            print(f"[DATE_FIX] Found matching date: {search_date.strftime('%B %d, %Y')} is a {detected_weekday.capitalize()}")
                            break
                        search_date += timedelta(days=1)
                else:
                    print(f"[DATE] Weekday '{detected_weekday}' matches AI's date - trusting AI's month/day parsing")
                    parsed["relative_days"] = None
            except ValueError:
                print(f"[DATE_FIX] Invalid AI date - searching for {detected_weekday} the {explicit_day_num}")
                search_date = now
                for _ in range(365):
                    if search_date.day == explicit_day_num and search_date.weekday() == target_weekday:
                        parsed["month"] = search_date.month
                        parsed["year"] = search_date.year
                        parsed["relative_days"] = None
                        print(f"[DATE_FIX] Found matching date: {search_date.strftime('%B %d, %Y')} is a {detected_weekday.capitalize()}")
                        break
                    search_date += timedelta(days=1)
        elif detected_weekday and parsed.get("month") and parsed.get("day") and (has_month_name or has_year):
            # Has explicit month name or year - trust AI's parsing but validate weekday
            print(f"[DATE] Weekday '{detected_weekday}' found with explicit month/year - trusting AI's month/day parsing")
        elif detected_weekday and parsed.get("day_of_week") and explicit_day_num and not parsed.get("day"):
            # AI returned day_of_week but there's an explicit day number like "Monday the 23rd"
            # We need to find the next occurrence of that weekday that falls on that day number
            print(f"[DATE_FIX] AI used day_of_week but explicit day number {explicit_day_num} present - will find matching date")
            # Set the day so the specific date logic handles it
            parsed["day"] = explicit_day_num
            # Try to find the month where this weekday falls on this day
            target_weekday = weekday_names[detected_weekday]
            search_date = now
            for _ in range(365):  # Search up to a year ahead
                if search_date.day == explicit_day_num and search_date.weekday() == target_weekday:
                    parsed["month"] = search_date.month
                    parsed["year"] = search_date.year
                    parsed["day_of_week"] = None  # Clear day_of_week so specific date logic is used
                    parsed["relative_days"] = None  # Clear relative_days so specific date logic is used
                    print(f"[DATE_FIX] Found matching date: {search_date.strftime('%B %d, %Y')} is a {detected_weekday.capitalize()}")
                    break
                search_date += timedelta(days=1)
        elif detected_weekday and explicit_day_num and parsed.get("day") and not parsed.get("month") and not parsed.get("day_of_week"):
            # AI returned just day number without month or day_of_week (e.g., "Wednesday the 25th" -> {day: 25})
            # We need to find the next occurrence of that weekday that falls on that day number
            print(f"[DATE_FIX] AI returned day={parsed.get('day')} without month - finding {detected_weekday} the {explicit_day_num}")
            target_weekday = weekday_names[detected_weekday]
            search_date = now
            for _ in range(365):  # Search up to a year ahead
                if search_date.day == explicit_day_num and search_date.weekday() == target_weekday:
                    parsed["month"] = search_date.month
                    parsed["year"] = search_date.year
                    # Clear relative_days so the specific date logic is used
                    parsed["relative_days"] = None
                    print(f"[DATE_FIX] Found matching date: {search_date.strftime('%B %d, %Y')} is a {detected_weekday.capitalize()}")
                    break
                search_date += timedelta(days=1)
            else:
                # No match found in next year - this shouldn't happen but handle gracefully
                print(f"[DATE_FIX] WARNING: Could not find {detected_weekday} the {explicit_day_num} in next year")
        
        # Check if it's a birth date
        if parsed.get("is_birth_date"):
            print(f"[WARNING] Detected birth date in '{text}' - returning default appointment time")
            return now.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # Check if clarification is needed
        # BUT: if we already resolved a weekday+ordinal to a specific month/day above, 
        # ignore the AI's needs_clarification flag since we've figured it out ourselves
        if parsed.get("needs_clarification"):
            missing = parsed["needs_clarification"]
            # If the AI said "date" needs clarification but we resolved month+day from weekday+ordinal, proceed
            has_resolved_date = parsed.get("month") and parsed.get("day")
            has_resolved_weekday = parsed.get("day_of_week") is not None
            if missing == "date" and (has_resolved_date or has_resolved_weekday):
                print(f"[DATE_FIX] AI said needs_clarification='date' but we resolved it - proceeding")
            elif missing == "time" and parsed.get("hour") is not None:
                print(f"[DATE_FIX] AI said needs_clarification='time' but hour is set - proceeding")
            elif missing == "month" and parsed.get("day"):
                # Day number given without month (e.g., "the 27th", "the 5th")
                # Infer: if that day hasn't passed this month, use this month; otherwise next month
                day_num = parsed["day"]
                try:
                    candidate = now.replace(day=day_num, hour=default_time[0], minute=default_time[1], second=0, microsecond=0)
                    if candidate.date() < now.date():
                        # Day already passed this month — use next month
                        if now.month == 12:
                            candidate = candidate.replace(year=now.year + 1, month=1)
                        else:
                            candidate = candidate.replace(month=now.month + 1)
                    parsed["month"] = candidate.month
                    parsed["year"] = candidate.year
                    print(f"[DATE_FIX] Inferred month for 'the {day_num}' → {candidate.strftime('%B %d, %Y')}")
                except ValueError:
                    # Invalid day for this month (e.g., Feb 31) — try next month
                    try:
                        next_month = now.month + 1 if now.month < 12 else 1
                        next_year = now.year if now.month < 12 else now.year + 1
                        candidate = datetime(next_year, next_month, day_num, default_time[0], default_time[1])
                        parsed["month"] = candidate.month
                        parsed["year"] = candidate.year
                        print(f"[DATE_FIX] Day {day_num} invalid this month, using {candidate.strftime('%B %d, %Y')}")
                    except ValueError:
                        print(f"[WARNING] Cannot resolve day {day_num} to a valid date - returning None")
                        return None
            else:
                print(f"[WARNING] {missing.title()} not specified in '{text}' - returning None to prompt")
                return None
        
        # Build the datetime from parsed components
        result = None
        hour = parsed.get("hour")
        minute = parsed.get("minute", 0)
        
        # Handle day of week (next Monday, Friday, etc.)
        # PRIORITY: day_of_week is more specific than relative_days
        if parsed.get("day_of_week"):
            day_name = parsed["day_of_week"]
            days_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            target_day = days_map[day_name]
            days_ahead = (target_day - now.weekday()) % 7
            
            # Check if user said "next [weekday]" - this means next week's occurrence
            has_next_prefix = 'next ' + day_name in text_lower or 'next' in text_lower.split()
            
            # If today is the requested day and we have a time that's still in the future, use today
            # UNLESS user explicitly said "next Monday" etc.
            if days_ahead == 0:
                if has_next_prefix:
                    # User said "next Monday" on a Monday - they mean next week
                    days_ahead = 7
                    print(f"[DATE] Day of week: {day_name} is TODAY but user said 'next {day_name}' - using next week")
                elif hour is not None:
                    # Check if the requested time is still in the future today
                    requested_time_today = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
                    if requested_time_today > now:
                        # Time is still in the future today - use today
                        days_ahead = 0
                        print(f"[DATE] Day of week: {day_name} is TODAY and time {hour}:{minute or 0} is still in the future")
                    else:
                        # Time has passed today - use next week
                        days_ahead = 7
                        print(f"[DATE] Day of week: {day_name} is TODAY but time {hour}:{minute or 0} has passed - using next week")
                else:
                    # No time specified - default to next occurrence to be safe
                    days_ahead = 7
                    print(f"[DATE] Day of week: {day_name} is TODAY but no time specified - using next week")
            elif has_next_prefix and days_ahead < 7:
                # User said "next Monday" but it's not Monday today - still means next week's Monday
                # Only apply this if the day is coming up this week (days_ahead < 7)
                # "next Monday" on a Wednesday should be next week's Monday, not this week's
                days_ahead += 7
                print(f"[DATE] Day of week: user said 'next {day_name}' - adding 7 days to get next week")
            
            # If no time specified, use default or return None
            if hour is None:
                if require_time:
                    print(f"[WARNING] Day of week '{day_name}' provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"[DATE] Using default time {hour:02d}:{minute:02d} for '{day_name}'")
            
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=days_ahead)
            print(f"[DATE] Day of week: {day_name} (+{days_ahead} days) = {result.strftime('%A, %B %d, %Y')}")
        
        # Handle relative dates (tomorrow, day after tomorrow, etc.)
        elif parsed.get("relative_days") is not None:
            relative_days = parsed["relative_days"]
            
            # If no time specified, use default or return None
            if hour is None:
                if require_time:
                    print(f"[WARNING] Relative date provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"[DATE] Using default time {hour:02d}:{minute:02d} for relative date")
            
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=relative_days)
            print(f"[DATE] Relative date: +{relative_days} days from today")
        
        # Handle next week
        elif parsed.get("is_next_week"):
            # If no time specified, use default or return None
            if hour is None:
                if require_time:
                    print(f"[WARNING] Next week provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"[DATE] Using default time {hour:02d}:{minute:02d} for next week")
            
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=7)
            print(f"[DATE] Next week: +7 days")
        
        # Handle specific date (month/day/year)
        elif parsed.get("month") and parsed.get("day"):
            month = parsed["month"]
            day = parsed["day"]
            year = parsed.get("year") or now.year
            
            if hour is None:
                if require_time:
                    print(f"[WARNING] Date provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"[DATE] Using default time {hour:02d}:{minute:02d} for specific date")
            
            # Create the date
            try:
                result = datetime(year, month, day, hour, minute or 0, 0, 0)
                # If the DATE (not time) is in the past, assume next year
                # But only if year wasn't explicitly specified
                if not parsed.get("year") and result.date() < now.date():
                    result = datetime(year + 1, month, day, hour, minute, 0, 0)
                    print(f"[DATE] Date was in past, assuming next year: {month}/{day}/{year + 1}")
                else:
                    print(f"[DATE] Specific date: {month}/{day}/{year}")
            except ValueError as e:
                print(f"[WARNING] Invalid date components: {e}")
                return None
        
        # No date found
        else:
            if hour is None:
                if require_time:
                    print(f"[WARNING] No time specified - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"[DATE] Using default time {hour:02d}:{minute:02d}")
            # Default to tomorrow
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=1)
            print(f"[DATE] No date specified, defaulting to tomorrow")
        
        # Validate result is in the future (unless allow_past is True)
        if result and not allow_past and result <= now:
            result += timedelta(days=1)
            print(f"[TIME] Date was in past, moved to future")
        
        return result
        
    except Exception as e:
        parse_duration = time_module.time() - parse_start
        print(f"[DATE_TIMING] ❌ AI date parse FAILED after {parse_duration:.3f}s")
        print(f"[DATE_PARSER_ERROR] ========== AI DATE PARSING FAILED ==========")
        print(f"[DATE_PARSER_ERROR] Input text: '{text}'")
        print(f"[DATE_PARSER_ERROR] Exception type: {type(e).__name__}")
        print(f"[DATE_PARSER_ERROR] Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fallback to simple regex for critical patterns
        return _fallback_parse_datetime(text)


def _fallback_parse_datetime(text: str) -> datetime:
    """
    Fallback regex-based parser for when AI fails
    Only handles the most common patterns
    """
    print(f"[RETRY] Using fallback parser for '{text}'")
    
    text = text.lower().strip()
    now = datetime.now()
    
    # Extract time (simple patterns only)
    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        am_pm = time_match.group(3)
        
        if am_pm == 'pm' and hour != 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0
        
        # Simple relative dates
        if 'tomorrow' in text:
            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            result += timedelta(days=1)
            return result
        elif 'today' in text:
            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if result <= now:
                result += timedelta(days=1)
            return result
    
    print(f"[WARNING] Fallback parser couldn't parse '{text}' - returning None")
    return None
