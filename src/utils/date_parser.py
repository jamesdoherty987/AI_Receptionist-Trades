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
    """Get or create OpenAI client instance"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


# OpenAI function for date/time parsing
DATETIME_PARSE_FUNCTION = {
    "name": "parse_datetime",
    "description": "Parse natural language date and time references into structured datetime components",
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
                "description": "Year if explicitly mentioned, otherwise null"
            },
            "month": {
                "type": "integer",
                "description": "Month number (1-12) if mentioned"
            },
            "day": {
                "type": "integer",
                "description": "Day of month (1-31) if mentioned"
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
                "description": "Day of week if ANY weekday name is mentioned (e.g., 'Monday', 'next Friday', 'this Tuesday'). ALWAYS use this field for weekday names, NOT relative_days."
            },
            "is_next_week": {
                "type": "boolean",
                "description": "True if 'next week' was mentioned"
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
    
    try:
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

CRITICAL RULES FOR WEEKDAY NAMES:
- When user says a weekday name (Monday, Tuesday, etc.), ALWAYS use the 'day_of_week' field
- Do NOT use 'relative_days' for weekday names
- Use 'relative_days' ONLY for: 'today' (0), 'tomorrow' (1), 'day after tomorrow' (2)

EXAMPLES:
- "Monday at 2pm" → day_of_week: "monday", hour: 14
- "next Friday" → day_of_week: "friday", hour: null (ask for time)
- "tomorrow at 9am" → relative_days: 1, hour: 9
- "today at 3pm" → relative_days: 0, hour: 15

Remember: Today is {current_day_name}. If user says "{current_day_name}", that means TODAY (relative_days: 0)."""
                },
                {
                    "role": "user",
                    "content": f"Parse this date/time reference: {text}"
                }
            ],
            functions=[DATETIME_PARSE_FUNCTION],
            function_call={"name": "parse_datetime"}
        )
        
        # Extract the parsed data
        function_call = response.choices[0].message.function_call
        if not function_call:
            print(f"[WARNING] No function call returned from AI - falling back to None")
            return None
        
        import json
        parsed = json.loads(function_call.arguments)
        
        print(f"[AI] AI parsed '{text}': {parsed}")
        
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
            if days_ahead == 0:
                days_ahead = 7  # Next occurrence, not today
            
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
            print(f"[DATE] Day of week: {day_name} (+{days_ahead} days)")
        
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
        print(f"[ERROR] AI date parsing error: {e}")
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
