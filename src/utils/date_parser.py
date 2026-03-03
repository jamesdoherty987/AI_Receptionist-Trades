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
    
    # Fast path 3: "[weekday] at Xam/pm" (e.g., "Monday at 2pm", "next Friday at 10am")
    weekday_names = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
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
        
        # CRITICAL FIX: If AI returned month/day but text contains a weekday name, override with day_of_week
        # This catches cases where AI incorrectly converts "next Monday" to a specific date
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
        
        if detected_weekday and parsed.get("month") and parsed.get("day") and not parsed.get("day_of_week"):
            # AI incorrectly used month/day instead of day_of_week - fix it
            print(f"[DATE_FIX] AI used month/day for weekday '{detected_weekday}' - correcting to day_of_week")
            parsed["day_of_week"] = detected_weekday
            parsed["month"] = None
            parsed["day"] = None
            parsed["year"] = None
        
        # Check if it's a birth date
        if parsed.get("is_birth_date"):
            print(f"[WARNING] Detected birth date in '{text}' - returning default appointment time")
            return now.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # Check if clarification is needed
        if parsed.get("needs_clarification"):
            missing = parsed["needs_clarification"]
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
            year = parsed.get("year", now.year)
            
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
