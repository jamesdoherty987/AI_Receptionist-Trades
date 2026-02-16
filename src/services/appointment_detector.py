"""
Appointment intent detection and management using OpenAI function calling
"""
import re
import json
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from openai import OpenAI
from src.utils.config import config


# Lazy initialization of OpenAI client
_client = None

def get_openai_client():
    """Get or create OpenAI client instance"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


class AppointmentIntent(Enum):
    """Types of appointment requests"""
    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    QUERY = "query"
    NONE = "none"


# OpenAI function definition for intent classification
INTENT_FUNCTION = {
    "name": "classify_appointment_intent",
    "description": "Classify the user's intent related to appointments and extract all relevant details from the conversation",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["book", "reschedule", "cancel", "query", "none"],
                "description": """The primary intent of the user. CRITICAL RULES:

1. Use 'reschedule' ONLY if the user EXPLICITLY says words like 'reschedule', 'change my appointment', 'move my appointment', 'different time for my existing appointment'. Do NOT classify as reschedule if:
   - User just confirmed a booking and says 'great', 'thanks', 'perfect', 'sounds good'
   - User is acknowledging information without requesting a change
   - User mentions a time in the context of a NEW booking (not changing an existing one)
   - User says 'yes' or 'no' to a question

2. Use 'book' if they want to schedule a NEW appointment.

3. Use 'query' if asking about available times/slots or existing appointments, especially questions like 'is there anything later?', 'what times are available?', 'do you have anything else?', 'what about after X?'. If the message contains BOTH acceptance and a question about alternatives (e.g., 'I like 2pm but is there anything later?'), classify as 'query'.

4. Use 'cancel' ONLY if user explicitly wants to REMOVE/DELETE an existing appointment.

5. Use 'none' if:
   - No appointment-related intent
   - Just confirmation words like 'yes', 'no', 'correct', 'that's right', 'great', 'thanks', 'perfect' without any appointment action
   - Providing requested information like name, phone, address
   - Acknowledging or thanking after a booking is confirmed
   - Saying goodbye or ending the conversation"""
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Confidence level in the classification"
            },
            "customer_name": {
                "type": "string",
                "description": "The customer's full name if mentioned"
            },
            "service_type": {
                "type": "string",
                "description": "Type of service or reason for visit (e.g., checkup, cleaning, consultation, injury, illness)"
            },
            "time_reference": {
                "type": "string",
                "description": "Any time, date, or day mentioned for the appointment. CRITICAL RULES: 1) Extract relative dates EXACTLY as the user says them: 'tomorrow', 'day after tomorrow', 'next week', 'Monday', etc. - do NOT convert to specific dates. 2) For RESCHEDULE, this should be the ORIGINAL/OLD appointment time. 3) For BOOK or CANCEL, this is the appointment time. 4) If a date includes a year before 2007 (e.g., '15th May 1985'), this is a DATE OF BIRTH, NOT an appointment time - return null/empty. 5) If user only says confirmation words like 'yes', 'no', 'correct', 'that\'s right' WITHOUT mentioning a time, return null/empty - do NOT infer from previous context. Examples: User says 'day after tomorrow' → extract 'day after tomorrow' (not a specific date); User says 'January 5th' → extract 'January 5th'; User says 'yes' → return null (no time mentioned)."
            },
            "new_time_reference": {
                "type": "string",
                "description": "Only for RESCHEDULE intent: the NEW time the user wants to move the appointment to (e.g., 'tomorrow at 2pm', 'next Friday at 10am'). CRITICAL: 1) Only extract this if the user EXPLICITLY provides a new time in their CURRENT message. 2) If they say 'earlier', 'later', 'sooner', or 'another time' without specifying when, return the word as-is (e.g., 'earlier'). 3) If user only says 'yes', 'no', 'correct', or other confirmation words WITHOUT mentioning a time, return null/empty - do NOT infer or guess from context. 4) Do NOT extract times from previous messages in the conversation."
            }
        },
        "required": ["intent", "confidence"]
    }
}


class AppointmentDetector:
    """Detects appointment-related intents using OpenAI function calling"""
    
    @classmethod
    def detect_intent(cls, text: str) -> AppointmentIntent:
        """
        Detect the appointment intent from user text using OpenAI function calling
        
        Args:
            text: User's spoken text
            
        Returns:
            AppointmentIntent enum value
        """
        try:
            client = get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at classifying user intents for a receptionist AI. Analyze the user's message and classify their appointment-related intent.

CRITICAL: Be very careful about 'reschedule' classification. Only use 'reschedule' if the user EXPLICITLY mentions wanting to change/move an EXISTING appointment. 

Common phrases that are NOT reschedule requests:
- "great", "thanks", "perfect", "sounds good" (acknowledgments)
- "yes", "no", "correct" (confirmations)
- Mentioning a time when booking a NEW appointment
- Asking about availability (this is 'query')

Only classify as 'reschedule' for phrases like:
- "I need to reschedule"
- "Can I change my appointment"
- "Move my appointment to..."
- "I can't make that time, can we change it" (referring to an existing booking)"""
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                tools=[{"type": "function", "function": INTENT_FUNCTION}],
                tool_choice={"type": "function", "function": {"name": "classify_appointment_intent"}},
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=100
            )
            
            # Extract tool call result
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls and len(tool_calls) > 0:
                args = json.loads(tool_calls[0].function.arguments)
                intent_str = args.get("intent", "none")
                
                # Convert string to enum
                intent_map = {
                    "book": AppointmentIntent.BOOK,
                    "reschedule": AppointmentIntent.RESCHEDULE,
                    "cancel": AppointmentIntent.CANCEL,
                    "query": AppointmentIntent.QUERY,
                    "none": AppointmentIntent.NONE
                }
                
                return intent_map.get(intent_str, AppointmentIntent.NONE)
            
            return AppointmentIntent.NONE
            
        except Exception as e:
            print(f"⚠️ Error in OpenAI intent detection: {e}")
            # Fallback to simple keyword matching
            return cls._fallback_detect_intent(text)
    
    @classmethod
    def _fallback_detect_intent(cls, text: str) -> AppointmentIntent:
        """Fallback keyword-based detection if OpenAI fails"""
        text_lower = text.lower()
        
        # Check for explicit reschedule keywords - must be very specific
        reschedule_phrases = ["reschedule", "change my appointment", "move my appointment", "change the appointment"]
        if any(phrase in text_lower for phrase in reschedule_phrases):
            return AppointmentIntent.RESCHEDULE
        
        if any(word in text_lower for word in ["cancel", "delete", "remove"]):
            return AppointmentIntent.CANCEL
        
        if any(word in text_lower for word in ["when is", "what time", "do i have", "check"]):
            return AppointmentIntent.QUERY
        
        if any(word in text_lower for word in ["book", "schedule", "make", "set up", "arrange"]):
            return AppointmentIntent.BOOK
        
        return AppointmentIntent.NONE
    
    @classmethod
    def extract_appointment_details(cls, text: str = None, conversation_history: list = None) -> Dict[str, Any]:
        """
        Extract appointment details from text using OpenAI function calling
        
        Args:
            text: User's spoken text (for backward compatibility)
            conversation_history: Full conversation history for better context
            
        Returns:
            Dictionary with extracted details
        """
        try:
            client = get_openai_client()
            
            # Get current date for context
            from datetime import datetime
            current_date = datetime.now()
            date_context = f"Today is {current_date.strftime('%A, %B %d, %Y')}. When extracting dates, keep relative references like 'tomorrow', 'day after tomorrow', etc. EXACTLY as they are - do NOT convert them to specific dates."
            
            # Build messages with full context if available
            if conversation_history:
                # Check if there was a recent booking confirmation in the conversation
                recent_booking = False
                for msg in reversed(conversation_history[-4:]):  # Check last 4 messages
                    content = msg.get("content", "").lower()
                    if any(phrase in content for phrase in ["you're all booked", "booking confirmed", "you're all set", "that's booked"]):
                        recent_booking = True
                        break
                
                booking_context = ""
                if recent_booking:
                    booking_context = " IMPORTANT: A booking was just confirmed in this conversation. If the user says 'great', 'thanks', 'perfect', or similar acknowledgments, classify as 'none' - they are NOT asking to reschedule."
                
                messages = [
                    {
                        "role": "system",
                        "content": f"""You are an expert at classifying user intents for a receptionist AI. {date_context} Analyze the ENTIRE conversation to understand what the user wants and extract appointment-related information.{booking_context}

CRITICAL RULES:
1. When user says 'day after tomorrow', 'tomorrow', or similar relative dates, extract them EXACTLY as they said them - do NOT convert to specific dates.
2. Only classify as 'reschedule' if the user EXPLICITLY says they want to change/move an EXISTING appointment. Phrases like 'great', 'thanks', 'perfect', 'sounds good' after a booking are NOT reschedule requests.
3. If a booking was just confirmed and user responds positively, classify as 'none'."""
                    },
                    *conversation_history
                ]
            else:
                messages = [
                    {
                        "role": "system",
                        "content": f"""You are an expert at classifying user intents for a receptionist AI. {date_context} Analyze the user's message and extract appointment-related information.

CRITICAL RULES:
1. When user says 'day after tomorrow', 'tomorrow', or similar relative dates, extract them EXACTLY as they said them - do NOT convert to specific dates.
2. Only classify as 'reschedule' if the user EXPLICITLY says they want to change/move an EXISTING appointment."""
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ]
            
            # Clean messages to only include user and assistant messages
            # The intent detection doesn't need tool calls or tool responses
            cleaned_messages = []
            for msg in messages:
                # Only include user and assistant messages
                if msg.get('role') in ['user', 'assistant']:
                    # Remove tool_calls and function_call keys from assistant messages
                    cleaned_msg = {k: v for k, v in msg.items() if k not in ['tool_calls', 'function_call']}
                    cleaned_messages.append(cleaned_msg)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=cleaned_messages,
                tools=[{"type": "function", "function": INTENT_FUNCTION}],
                tool_choice={"type": "function", "function": {"name": "classify_appointment_intent"}},
                temperature=0.1,
                max_tokens=200
            )
            
            # Extract tool call result
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls and len(tool_calls) > 0:
                args = json.loads(tool_calls[0].function.arguments)
                
                intent_str = args.get("intent", "none")
                intent_map = {
                    "book": AppointmentIntent.BOOK,
                    "reschedule": AppointmentIntent.RESCHEDULE,
                    "cancel": AppointmentIntent.CANCEL,
                    "query": AppointmentIntent.QUERY,
                    "none": AppointmentIntent.NONE
                }
                
                details = {
                    "intent": intent_map.get(intent_str, AppointmentIntent.NONE),
                    "raw_text": text or "conversation context",
                    "datetime": args.get("time_reference"),
                    "new_datetime": args.get("new_time_reference"),  # For rescheduling
                    "service_type": args.get("service_type"),
                    "customer_name": args.get("customer_name"),
                    "confidence": args.get("confidence", "unknown")
                }
                
                return details
            
        except Exception as e:
            print(f"⚠️ Error in OpenAI detail extraction: {e}")
        
        # Fallback to basic detection
        return {
            "intent": cls.detect_intent(text),
            "raw_text": text,
            "datetime": None,
            "service_type": None,
            "confidence": "low"
        }


def print_appointment_action(intent: AppointmentIntent, details: Dict[str, Any]):
    """
    Print appointment action in a formatted way
    
    Args:
        intent: The detected appointment intent
        details: Dictionary with appointment details
    """
    if intent == AppointmentIntent.NONE:
        return
    
    confidence = details.get("confidence", "unknown").upper()
    
    print("\n" + "="*60)
    print(f"📅 APPOINTMENT ACTION DETECTED: {intent.value.upper()}")
    print(f"🎯 Confidence: {confidence}")
    print("="*60)
    
    if intent == AppointmentIntent.BOOK:
        print("✅ ACTION: Book new appointment")
    elif intent == AppointmentIntent.RESCHEDULE:
        print("🔄 ACTION: Reschedule existing appointment")
    elif intent == AppointmentIntent.CANCEL:
        print("❌ ACTION: Cancel appointment")
    elif intent == AppointmentIntent.QUERY:
        print("❓ ACTION: Query appointment details")
    
    print(f"📝 User said: {details['raw_text']}")
    
    if details.get("customer_name"):
        print(f"👤 Customer: {details['customer_name']}")
    
    if details.get("service_type"):
        print(f"🏥 Service: {details['service_type']}")
    
    if details.get("datetime"):
        if intent == AppointmentIntent.RESCHEDULE:
            print(f"🕐 Old time: {details['datetime']}")
        else:
            print(f"🕐 Time reference: {details['datetime']}")
    
    if details.get("new_datetime") and intent == AppointmentIntent.RESCHEDULE:
        print(f"🕐 New time: {details['new_datetime']}")
    
    print("="*60 + "\n")
