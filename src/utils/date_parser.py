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
        print(f"⚠️ Empty text provided - returning None to prompt for date and time")
        return None
    
    # Set default time if not provided
    if default_time is None:
        default_time = (9, 0)
    
    text = text.strip()
    now = datetime.now()
    
    try:
        client = get_openai_client()
        
        # Use AI to parse the date/time with structured output
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert at parsing natural language date and time references. Today is {now.strftime('%A, %B %d, %Y')}. Current time is {now.strftime('%I:%M %p')}. CRITICAL: When user mentions a weekday name (Monday, Tuesday, etc.), ALWAYS use the 'day_of_week' field, NOT 'relative_days'. Use 'relative_days' ONLY for 'today', 'tomorrow', 'day after tomorrow'."
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
            print(f"⚠️ No function call returned from AI - falling back to None")
            return None
        
        import json
        parsed = json.loads(function_call.arguments)
        
        print(f"🤖 AI parsed '{text}': {parsed}")
        
        # Check if it's a birth date
        if parsed.get("is_birth_date"):
            print(f"⚠️ Detected birth date in '{text}' - returning default appointment time")
            return now.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # Check if clarification is needed
        if parsed.get("needs_clarification"):
            missing = parsed["needs_clarification"]
            print(f"⚠️ {missing.title()} not specified in '{text}' - returning None to prompt")
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
                    print(f"⚠️ Day of week '{day_name}' provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"📅 Using default time {hour:02d}:{minute:02d} for '{day_name}'")
            
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=days_ahead)
            print(f"📅 Day of week: {day_name} (+{days_ahead} days)")
        
        # Handle relative dates (tomorrow, day after tomorrow, etc.)
        elif parsed.get("relative_days") is not None:
            relative_days = parsed["relative_days"]
            
            # If no time specified, use default or return None
            if hour is None:
                if require_time:
                    print(f"⚠️ Relative date provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"📅 Using default time {hour:02d}:{minute:02d} for relative date")
            
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=relative_days)
            print(f"📅 Relative date: +{relative_days} days from today")
        
        # Handle next week
        elif parsed.get("is_next_week"):
            # If no time specified, use default or return None
            if hour is None:
                if require_time:
                    print(f"⚠️ Next week provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"📅 Using default time {hour:02d}:{minute:02d} for next week")
            
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=7)
            print(f"📅 Next week: +7 days")
        
        # Handle specific date (month/day/year)
        elif parsed.get("month") and parsed.get("day"):
            month = parsed["month"]
            day = parsed["day"]
            year = parsed.get("year", now.year)
            
            if hour is None:
                if require_time:
                    print(f"⚠️ Date provided without time - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"📅 Using default time {hour:02d}:{minute:02d} for specific date")
            
            # Create the date
            try:
                result = datetime(year, month, day, hour, minute or 0, 0, 0)
                # If the DATE (not time) is in the past, assume next year
                # But only if year wasn't explicitly specified
                if not parsed.get("year") and result.date() < now.date():
                    result = datetime(year + 1, month, day, hour, minute, 0, 0)
                    print(f"📅 Date was in past, assuming next year: {month}/{day}/{year + 1}")
                else:
                    print(f"📅 Specific date: {month}/{day}/{year}")
            except ValueError as e:
                print(f"⚠️ Invalid date components: {e}")
                return None
        
        # No date found
        else:
            if hour is None:
                if require_time:
                    print(f"⚠️ No time specified - returning None to prompt")
                    return None
                else:
                    hour, minute = default_time
                    print(f"📅 Using default time {hour:02d}:{minute:02d}")
            # Default to tomorrow
            result = now.replace(hour=hour, minute=minute or 0, second=0, microsecond=0)
            result += timedelta(days=1)
            print(f"📅 No date specified, defaulting to tomorrow")
        
        # Validate result is in the future (unless allow_past is True)
        if result and not allow_past and result <= now:
            result += timedelta(days=1)
            print(f"⏰ Date was in past, moved to future")
        
        return result
        
    except Exception as e:
        print(f"❌ AI date parsing error: {e}")
        # Fallback to simple regex for critical patterns
        return _fallback_parse_datetime(text)


def _fallback_parse_datetime(text: str) -> datetime:
    """
    Fallback regex-based parser for when AI fails
    Only handles the most common patterns
    """
    print(f"🔄 Using fallback parser for '{text}'")
    
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
    
    print(f"⚠️ Fallback parser couldn't parse '{text}' - returning None")
    return None
    """
    Parse natural language date/time into datetime object
    Handles various formats and phrasings
    
    Args:
        text: Natural language time reference
        
    Returns:
        Parsed datetime object, or None if no time specified (to prompt user)
    """
    if not text:
        # No text provided - return None to prompt for date and time
        print(f"⚠️ Empty text provided - returning None to prompt for date and time")
        return None
    
    text = text.lower().strip()
    now = datetime.now()
    
    # Replace common word variations to standardize
    replacements = {
        'twelve': '12', 'eleven': '11', 'ten': '10', 'nine': '9', 'eight': '8',
        'seven': '7', 'six': '6', 'five': '5', 'four': '4', 'three': '3',
        'two': '2', 'one': '1',
        'noon': '12 pm', 'midnight': '12 am',
        'morning': '9 am', 'afternoon': '2 pm', 'evening': '6 pm',
        'a.m.': 'am', 'p.m.': 'pm',
        'o\'clock': '', 'oclock': ''
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Try to parse specific month/day - prepare month_names dictionary first
    month_names = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    # Fuzzy match month names FIRST to handle typos (e.g., "janary" -> "january")
    # This must happen before date-only pattern matching
    words = text.split()
    for i, word in enumerate(words):
        word_clean = word.lower().strip(',.!?')
        if word_clean not in month_names and len(word_clean) >= 3:
            # Try fuzzy matching
            matches = get_close_matches(word_clean, month_names.keys(), n=1, cutoff=0.7)
            if matches:
                # Replace the typo with the correct month name
                print(f"🔧 Fuzzy match: '{word_clean}' -> '{matches[0]}'")
                text = text.replace(word, matches[0])
    
    # Extract time - handle multiple formats
    # Patterns: "12 pm", "12:30pm", "12:30 pm", "at 2pm", "2 in the afternoon"
    time_match = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)
    hour = None  # No default - if no time specified, we'll detect it
    minute = 0
    has_specific_time = False  # Track if user provided a specific time
    
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        am_pm = time_match.group(3)
        has_specific_time = True
        
        # Fix: Handle 12 PM and 12 AM correctly
        if am_pm == 'pm':
            if hour != 12:  # Only add 12 if it's not already 12
                hour += 12
        elif am_pm == 'am':
            if hour == 12:  # 12 AM is midnight (hour 0)
                hour = 0
    else:
        # Try to match time without AM/PM (e.g., "tomorrow at 12", "at 3")
        time_match_no_ampm = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\b', text)
        if time_match_no_ampm:
            hour = int(time_match_no_ampm.group(1))
            minute = int(time_match_no_ampm.group(2)) if time_match_no_ampm.group(2) else 0
            has_specific_time = True
            
            # Default to PM for business hours (9-5), AM for early morning
            if hour >= 1 and hour <= 7:
                # 1-7 without AM/PM likely means PM (1pm-7pm)
                hour += 12
            elif hour >= 8 and hour <= 11:
                # 8-11 could be AM or PM, default to AM for business hours
                pass  # Keep as AM
            elif hour == 12:
                # 12 without AM/PM defaults to 12 PM (noon)
                pass  # Keep as 12
            
            print(f"🔍 Parsed time without AM/PM: {time_match_no_ampm.group(0)} -> {hour}:{minute:02d} (24-hour)")
    
    # Validate hour is in correct range
    if hour is not None and (hour < 0 or hour > 23):
        print(f"⚠️ Invalid hour value: {hour} - returning None to prompt for valid time")
        return None
    
    # If no specific time was provided, return None so system asks for time
    if hour is None and not has_specific_time:
        # Check if this is just a date without time (e.g., "3rd january", "december 25", "jan 5")
        # If user only gave date, we should ask for time instead of defaulting
        date_only_patterns = [
            r'^\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)',
            r'^(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
            r'^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+\d{1,2}',  # Added abbreviated months
            r'^\d{1,2}/\d{1,2}',
            r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$',
            r'^(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$',  # next monday, next friday, etc.
            r'^(tomorrow|today|next week)$'
        ]
        for pattern in date_only_patterns:
            if re.search(pattern, text):
                print(f"⚠️ Date provided without time: '{text}' - returning None to prompt for time")
                return None
        # No time provided - always ask for it
        print(f"⚠️ No time specified in '{text}' - returning None to prompt for time")
        return None
    
    # Check if text contains a birth year (year < current_year - 18)
    # If so, this is likely a DOB, not an appointment date - skip parsing
    year_match = re.search(r'\b(19\d{2}|200[0-7])\b', text)
    if year_match:
        potential_birth_year = int(year_match.group(1))
        if potential_birth_year < now.year - 18:
            # This looks like a date of birth, not an appointment
            # Return tomorrow at 2pm as default to avoid confusion
            print(f"⚠️ Detected birth year {potential_birth_year} in date parsing - returning default appointment time")
            return datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    # Match patterns like "December 25", "Dec 25th", "25th of December"
    date_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})', text)
    if not date_match:
        # Try reverse format: "25th of December"
        date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)', text)
        if date_match:
            day = int(date_match.group(1))
            month_name = date_match.group(2)
            month = month_names[month_name]
            year = now.year
            
            # CRITICAL: If no time specified, return None to prompt user
            if hour is None:
                print(f"⚠️ Date provided ('{text}') without time - returning None to prompt for time")
                return None
            
            # If the date is in the past this year, assume next year
            try_date = datetime(year, month, day, hour, minute, 0, 0)
            if try_date < now:
                year += 1
            
            result = datetime(year, month, day, hour, minute, 0, 0)
        else:
            result = None
    else:
        month_name = date_match.group(1)
        day = int(date_match.group(2))
        month = month_names[month_name]
        year = now.year
        
        # CRITICAL: If no time specified, return None to prompt user
        if hour is None:
            print(f"⚠️ Date provided ('{text}') without time - returning None to prompt for time")
            return None
        
        # If the date is in the past this year, assume next year
        try_date = datetime(year, month, day, hour, minute, 0, 0)
        if try_date < now:
            year += 1
        
        result = datetime(year, month, day, hour, minute, 0, 0)
    
    # If no specific date found, use relative terms
    if result is None:
        # For relative terms without time, we should also ask for time
        if hour is None:
            print(f"⚠️ Relative date without time: '{text}' - returning None to prompt for time")
            return None
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Check for 'day after tomorrow' BEFORE checking 'tomorrow'
        if 'day after tomorrow' in text or 'dayafter tomorrow' in text:
            result += timedelta(days=2)
            print(f"📅 Parsed 'day after tomorrow': {result}")
        elif 'tomorrow' in text:
            result += timedelta(days=1)
        elif 'today' in text:
            pass  # already today
        elif 'next week' in text:
            result += timedelta(days=7)
        elif 'monday' in text:
            days_ahead = (0 - result.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # next monday, not today
            result += timedelta(days=days_ahead)
        elif 'tuesday' in text:
            days_ahead = (1 - result.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            result += timedelta(days=days_ahead)
        elif 'wednesday' in text:
            days_ahead = (2 - result.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            result += timedelta(days=days_ahead)
        elif 'thursday' in text:
            days_ahead = (3 - result.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            result += timedelta(days=days_ahead)
        elif 'friday' in text:
            days_ahead = (4 - result.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            result += timedelta(days=days_ahead)
        elif 'saturday' in text:
            days_ahead = (5 - result.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            result += timedelta(days=days_ahead)
        elif 'sunday' in text:
            days_ahead = (6 - result.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            result += timedelta(days=days_ahead)
        else:
            # Default to tomorrow if no date specified
            result += timedelta(days=1)
        
        # Make sure it's in the future
        if result <= now:
            result += timedelta(days=1)
    
    return result
