"""
Configuration for reschedule workflow
Centralized system messages and patterns for easier maintenance
"""
from typing import Callable, Optional
from datetime import datetime
import re
import json
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

# System messages for reschedule workflow
RESCHEDULE_MESSAGES = {
    "ask_old_time": "[SYSTEM: The user wants to reschedule. Ask them: 'What day and time was your original appointment?']",
    
    "cant_remember_ask_name": "[SYSTEM: The user can't remember their appointment time. Ask them: 'No problem! Can I get your name to look up your appointment?']",
    
    "ask_new_time": "[SYSTEM: Ask them what time they'd like to reschedule to. DO NOT say 'let me check', 'one moment', or any checking phrases - just ask for the time.]",
    
    "confirm_name": lambda name, time: f"[SYSTEM: IMPORTANT - You found the appointment! The appointment at {time} is for {name}. You MUST now say EXACTLY: 'Just to confirm, that appointment is for {name}. Is that correct?' Wait for their confirmation before asking about the new time. DO NOT ask for their name - you already have it from the calendar.]",
    
    "not_found": lambda time: f"[SYSTEM: No appointment was found at {time}. Politely tell the user and ask them to verify the date and time.]",
    
    "name_mismatch": "[SYSTEM: The user's response suggests they may be referring to a recent appointment or providing context. Use your conversation history to understand their intent. If they're clearly confirming this is their appointment (e.g., 'the one I just booked', 'that appointment'), treat it as confirmation. Otherwise, politely ask for the customer name to locate the correct appointment.]",
    
    "success": lambda new_time: f"[SYSTEM: Tell the user: 'Perfect! I've moved you to {new_time}. Looking forward to seeing you then!']",
    
    "failed": "[SYSTEM: Could NOT reschedule the appointment. Either the appointment wasn't found or the new time slot is busy. Ask them for the original appointment date/time and suggest alternative times.]",
    
    "slot_unavailable": lambda requested_time: f"[SYSTEM: Unfortunately, {requested_time} is already booked. Suggest alternative nearby times that are available. Keep the conversation going - don't ask for the original time again since you already know it.]",
    
    "need_specific_time": "[SYSTEM: Customer wants to reschedule but didn't provide a specific time. Ask them what specific date and time they would like to reschedule to (e.g., 'What time would you like to change it to?').]",
}

# Date pattern for checking if time reference includes a date
DATE_PATTERNS = [
    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b',
    r'\b\d{1,2}(?:st|nd|rd|th)?\b',  # Day number
    r'\b(tomorrow|today|next|this)\b',
    r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b'
]


def is_time_vague(time_str: str) -> bool:
    """
    Check if a time reference is too vague to use for rescheduling
    Returns True if vague, False if specific enough
    """
    if not time_str:
        return True
    
    time_lower = time_str.strip().lower()
    
    # Empty or very short strings
    if len(time_lower) < 3:
        return True
    
    # Vague relative references
    vague_indicators = [
        'earlier', 'later', 'sooner', 'another time', 'different time',
        'any time', 'sometime', 'whenever', 'flexible'
    ]
    
    return any(vague in time_lower for vague in vague_indicators)


def is_confirmation_response(text: str) -> bool:
    """
    Use AI to detect if user is confirming/agreeing
    More flexible and robust than word list matching
    """
    if not text:
        return False
    
    # Quick pattern match for obvious single-word cases (optimization)
    text_lower = text.lower().strip()
    if len(text_lower.split()) == 1 and text_lower in ['yes', 'yeah', 'yep', 'yup', 'ok', 'okay', 'correct', 'right', 'sure', 'ya']:
        return True
    
    # Use AI for more complex cases
    try:
        client = get_openai_client()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are detecting if a user's response is confirming or agreeing to something. Consider context and conversational phrases."
                },
                {
                    "role": "user",
                    "content": f"Is this a confirmation/agreement? '{text}'"
                }
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": "detect_confirmation",
                    "description": "Detect if text is a confirmation or agreement",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "is_confirmation": {
                                "type": "boolean",
                                "description": "True if the response is confirming/agreeing"
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence level"
                            }
                        },
                        "required": ["is_confirmation"]
                    }
                }
            }],
            tool_choice={"type": "function", "function": {"name": "detect_confirmation"}}
        )
        
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls and len(tool_calls) > 0:
            parsed = json.loads(tool_calls[0].function.arguments)
            result = parsed.get("is_confirmation", False)
            print(f"🤖 AI confirmation detection for '{text}': {result}")
            return result
    
    except Exception as e:
        print(f"❌ AI confirmation detection error: {e}")
    
    # Fallback to False if AI fails
    return False


def are_times_different(old_time_str: str, new_time_str: str, parse_func: Callable[[str], Optional[datetime]]) -> bool:
    """
    Check if two time references are actually different
    Returns True if different, False if same or can't determine
    
    Args:
        old_time_str: Original appointment time string
        new_time_str: New desired appointment time string
        parse_func: Function to parse datetime strings (should return datetime or None)
    
    Returns:
        bool: True if times are different, False if same or unparseable
    """
    try:
        old_dt = parse_func(old_time_str)
        new_dt = parse_func(new_time_str)
        
        if old_dt and new_dt:
            # Compare both date and time
            is_different = (old_dt.date() != new_dt.date() or old_dt.time() != new_dt.time())
            return is_different
    except Exception:
        pass
    
    # If we can't parse, assume they're different to allow LLM to handle it
    return True


def has_date_indicator(time_str: str) -> bool:
    """Check if a time string contains a date indicator"""
    if not time_str:
        return False
    
    return any(re.search(pattern, time_str.lower()) for pattern in DATE_PATTERNS)
