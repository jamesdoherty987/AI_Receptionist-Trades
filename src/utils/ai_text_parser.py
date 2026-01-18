"""
AI-powered text parsing utilities
Replaces hardcoded regex patterns with flexible AI-based parsing
"""
import json
from typing import Optional, Tuple, Dict, Any
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


# Function definition for time window extraction
TIME_WINDOW_FUNCTION = {
    "name": "extract_time_window",
    "description": "Extract a time window or time preference from natural language",
    "parameters": {
        "type": "object",
        "properties": {
            "has_time_window": {
                "type": "boolean",
                "description": "Whether the text mentions a specific time window or preference"
            },
            "start_hour": {
                "type": "integer",
                "description": "Start hour in 24-hour format (0-23), or null if not specified"
            },
            "end_hour": {
                "type": "integer",
                "description": "End hour in 24-hour format (0-23), or null if not specified"
            },
            "preference": {
                "type": "string",
                "enum": ["morning", "afternoon", "evening", "late", "early", "flexible"],
                "description": "General time preference if specific hours not mentioned"
            }
        },
        "required": ["has_time_window"]
    }
}


# Function definition for name extraction from text
NAME_EXTRACTION_FUNCTION = {
    "name": "extract_name",
    "description": "Extract a person's name from natural language, including corrections",
    "parameters": {
        "type": "object",
        "properties": {
            "has_name": {
                "type": "boolean",
                "description": "Whether the text contains a person's name"
            },
            "name": {
                "type": "string",
                "description": "The extracted name (first and last name)"
            },
            "is_correction": {
                "type": "boolean",
                "description": "True if this appears to be a name correction (e.g., 'no, it's...', 'actually it's...')"
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Confidence level in the extraction"
            }
        },
        "required": ["has_name"]
    }
}


def extract_time_window_ai(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract time window from natural language using AI
    
    Examples:
        "after 2pm" -> (14, 23)
        "between 2 and 4" -> (14, 16)
        "evening" -> (17, 21)
        "late times" -> (16, 23)
    
    Args:
        text: Natural language time preference
        
    Returns:
        Tuple of (start_hour, end_hour) in 24-hour format, or (None, None)
    """
    if not text:
        return (None, None)
    
    try:
        client = get_openai_client()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at parsing time windows and preferences from natural language. Business hours are typically 9 AM to 5 PM."
                },
                {
                    "role": "user",
                    "content": f"Extract the time window or preference from: {text}"
                }
            ],
            functions=[TIME_WINDOW_FUNCTION],
            function_call={"name": "extract_time_window"}
        )
        
        function_call = response.choices[0].message.function_call
        if not function_call:
            return (None, None)
        
        parsed = json.loads(function_call.arguments)
        
        if not parsed.get("has_time_window"):
            return (None, None)
        
        start = parsed.get("start_hour")
        end = parsed.get("end_hour")
        
        # If specific hours provided, use them
        if start is not None and end is not None:
            print(f"🤖 AI extracted time window: {start}:00-{end}:00")
            return (start, end)
        
        # Otherwise, use preference mapping
        preference = parsed.get("preference")
        if preference == "morning":
            return (9, 12)
        elif preference == "afternoon":
            return (12, 17)
        elif preference == "evening" or preference == "late":
            return (17, 21)
        elif preference == "early":
            return (9, 11)
        
        return (None, None)
        
    except Exception as e:
        print(f"❌ AI time window extraction error: {e}")
        return (None, None)


def extract_name_ai(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract person's name from text using AI, including detecting corrections
    
    Args:
        text: User's message that may contain a name
        
    Returns:
        Dict with keys: name, is_correction, confidence, or None if no name found
    """
    if not text:
        return None
    
    try:
        client = get_openai_client()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting people's names from conversational text. Pay attention to corrections like 'no, it's...' or 'actually it's...'."
                },
                {
                    "role": "user",
                    "content": f"Extract the name from: {text}"
                }
            ],
            functions=[NAME_EXTRACTION_FUNCTION],
            function_call={"name": "extract_name"}
        )
        
        function_call = response.choices[0].message.function_call
        if not function_call:
            return None
        
        parsed = json.loads(function_call.arguments)
        
        if not parsed.get("has_name"):
            return None
        
        name = parsed.get("name")
        if name:
            result = {
                "name": name.strip(),
                "is_correction": parsed.get("is_correction", False),
                "confidence": parsed.get("confidence", "medium")
            }
            print(f"🤖 AI extracted name: {result}")
            return result
        
        return None
        
    except Exception as e:
        print(f"❌ AI name extraction error: {e}")
        return None


def detect_birth_year(text: str) -> Optional[int]:
    """
    Detect if text contains a birth year (for distinguishing DOB from appointment dates)
    
    Args:
        text: Text that may contain a year
        
    Returns:
        Year if it's likely a birth year (< 2007), None otherwise
    """
    try:
        client = get_openai_client()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are detecting if text contains a birth year (typically before 2007) vs an appointment year. Return the year if it's a birth date."
                },
                {
                    "role": "user",
                    "content": f"Does this contain a birth year? {text}"
                }
            ],
            functions=[{
                "name": "detect_birth_year",
                "description": "Detect if text contains a birth year",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "has_birth_year": {
                            "type": "boolean",
                            "description": "Whether text contains a birth year (before 2007)"
                        },
                        "year": {
                            "type": "integer",
                            "description": "The birth year if found"
                        }
                    },
                    "required": ["has_birth_year"]
                }
            }],
            function_call={"name": "detect_birth_year"}
        )
        
        function_call = response.choices[0].message.function_call
        if not function_call:
            return None
        
        parsed = json.loads(function_call.arguments)
        
        if parsed.get("has_birth_year"):
            year = parsed.get("year")
            if year and year < 2007:
                print(f"🤖 AI detected birth year: {year}")
                return year
        
        return None
        
    except Exception as e:
        print(f"❌ AI birth year detection error: {e}")
        return None


def is_affirmative_response(text: str, context: str = None) -> bool:
    """
    Use AI to detect if user is confirming/agreeing with something
    More flexible and robust than hardcoded word lists
    
    Args:
        text: User's message
        context: Optional context about what they're confirming (e.g., "phone number", "appointment time")
    
    Returns:
        True if affirmative/confirming, False otherwise
    """
    if not text or len(text.strip()) == 0:
        return False
    
    # Quick optimization for obvious single-word cases (avoid API call)
    text_lower = text.lower().strip()
    if len(text_lower.split()) == 1 and text_lower in ['yes', 'yeah', 'yep', 'yup', 'ok', 'okay', 'correct', 'right', 'sure', 'ya']:
        return True
    
    # Quick check for obvious negatives
    if len(text_lower.split()) == 1 and text_lower in ['no', 'nope', 'nah', 'wrong', 'incorrect']:
        return False
    
    # Use AI for more complex cases
    try:
        client = get_openai_client()
        
        system_prompt = "Determine if the user's message is confirming/agreeing with something, or if it's saying no/disagreeing."
        if context:
            system_prompt += f" Context: They are responding to a question about {context}."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Is this message confirming/agreeing? Message: '{text}'"}
            ],
            functions=[{
                "name": "classify_response",
                "description": "Classify if user is confirming/agreeing or not",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_affirmative": {
                            "type": "boolean",
                            "description": "True if confirming/agreeing/saying yes, False if denying/disagreeing/saying no or unclear"
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Confidence level of the classification"
                        }
                    },
                    "required": ["is_affirmative", "confidence"]
                }
            }],
            function_call={"name": "classify_response"}
        )
        
        function_call = response.choices[0].message.function_call
        if not function_call:
            return False
        
        parsed = json.loads(function_call.arguments)
        is_affirmative = parsed.get("is_affirmative", False)
        confidence = parsed.get("confidence", "low")
        
        # Only return True if high or medium confidence
        if is_affirmative and confidence in ["high", "medium"]:
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ AI affirmative detection error: {e}")
        # Fallback to simple word matching
        return any(word in text_lower for word in ['yes', 'yeah', 'yep', 'yup', 'correct', 'right', 'ok', 'okay', 'sure', 'ya'])
