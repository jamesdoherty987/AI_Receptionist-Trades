"""
Call Summarization Service
Extracts job-relevant details from call transcripts and adds them to job cards.
Filters out small talk and focuses on actionable job information.
"""
import json
import time
from typing import Dict, List, Optional, Any
from openai import OpenAI
from src.utils.config import config
from src.utils.ai_logger import ai_logger


# Lazy initialization of OpenAI client
_client = None


def get_openai_client():
    """Get or create OpenAI client instance"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


# Function definition for structured extraction
CALL_SUMMARY_FUNCTION = {
    "name": "extract_job_details",
    "description": "Extract job-relevant details from a call transcript, filtering out small talk and pleasantries",
    "parameters": {
        "type": "object",
        "properties": {
            "job_description": {
                "type": "string",
                "description": "Write a comprehensive, well-structured description of the job/service requested. Include: (1) The main problem or service needed, (2) Specific symptoms, issues, or observations the customer mentioned, (3) When the problem started or was first noticed, (4) What the customer has already tried if anything, (5) Any relevant context about the situation. Write in clear, professional prose - not bullet points. Be thorough and descriptive while excluding greetings and small talk."
            },
            "urgency_level": {
                "type": "string",
                "enum": ["urgent", "normal", "flexible"],
                "description": "How urgent is this job? Urgent = needs attention within 24-48 hours. Normal = standard scheduling. Flexible = customer has no time pressure."
            },
            "urgency_notes": {
                "type": "string",
                "description": "Any specific urgency details mentioned (e.g., 'water is actively leaking', 'no hot water for 3 days', 'can wait until next week')"
            },
            "location_details": {
                "type": "string",
                "description": "Any location-specific details mentioned (e.g., 'upstairs bathroom', 'kitchen sink', 'back garden', 'commercial property')"
            },
            "property_info": {
                "type": "string",
                "description": "Property details if mentioned (e.g., 'old Victorian house', '3-story building', 'new construction')"
            },
            "access_instructions": {
                "type": "string",
                "description": "Any access or entry instructions (e.g., 'ring doorbell twice', 'key under mat', 'call when arriving')"
            },
            "special_requirements": {
                "type": "string",
                "description": "Any special requirements or considerations (e.g., 'has dogs', 'elderly resident', 'parking difficult', 'needs quote first')"
            },
            "previous_work": {
                "type": "string",
                "description": "Any mention of previous work or history (e.g., 'you fixed this before', 'had another company look at it')"
            },
            "customer_availability": {
                "type": "string",
                "description": "Customer's availability preferences if mentioned (e.g., 'works from home', 'only available mornings', 'flexible')"
            },
            "has_job_content": {
                "type": "boolean",
                "description": "True if the call contains actual job-related content worth saving. False if it's just greetings, wrong numbers, or no actionable information."
            }
        },
        "required": ["job_description", "urgency_level", "has_job_content"]
    }
}


def summarize_call(conversation_log: List[Dict[str, Any]], caller_phone: str = None) -> Optional[Dict[str, Any]]:
    """
    Summarize a call transcript and extract job-relevant details.
    
    Args:
        conversation_log: List of conversation messages with 'role' and 'content'
        caller_phone: Caller's phone number for context
        
    Returns:
        Dictionary with extracted job details, or None if no job content
    """
    if not conversation_log:
        ai_logger.debug("Call summarization skipped: empty conversation log", operation="summarize_call")
        return None
    
    # Build transcript text
    transcript_lines = []
    for msg in conversation_log:
        role = "Customer" if msg.get('role') == 'user' else "Receptionist"
        content = msg.get('content', '').strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    
    if not transcript_lines:
        ai_logger.debug("Call summarization skipped: no transcript content", operation="summarize_call")
        return None
    
    transcript = "\n".join(transcript_lines)
    start_time = time.time()
    
    try:
        client = get_openai_client()
        
        system_prompt = """You are an expert at extracting job-relevant information from phone call transcripts for a trades/service business. Your summaries help technicians arrive prepared and understand the full context of each job.

Your task is to create DETAILED, DESCRIPTIVE summaries that paint a complete picture of the customer's situation.

EXCLUDE from your summary:
- Greetings and pleasantries ("Hi", "How are you", "Thanks for calling")
- Weather chat or small talk
- Generic confirmations ("Yes", "Okay", "Sure")
- The receptionist's responses (focus on what the CUSTOMER said about their needs)

INCLUDE in your summary (write in flowing, professional prose):
- The primary problem or service requested - describe it fully
- Specific symptoms, sounds, smells, or observations the customer mentioned
- Timeline: when did the issue start? How long has it been going on?
- Severity: how bad is it? Is it getting worse?
- What the customer has already tried or ruled out
- Any theories the customer has about the cause
- Impact on the customer (e.g., "can't use the kitchen", "water damage spreading")
- Related issues that might be connected
- Any measurements, model numbers, or specific details mentioned

Write the job_description as a detailed narrative paragraph (2-4 sentences minimum) that gives the technician everything they need to understand the situation before arriving. Avoid vague descriptions like "plumbing issue" - instead write "Customer reports a persistent leak under the kitchen sink that started three days ago after they noticed water pooling on the cabinet floor. The leak appears to be coming from the P-trap connection and has been getting progressively worse."

If the call doesn't contain any real job information (e.g., wrong number, just checking hours, no actual service request), set has_job_content to false."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract job details from this call transcript:\n\n{transcript}"}
            ],
            tools=[{"type": "function", "function": CALL_SUMMARY_FUNCTION}],
            tool_choice={"type": "function", "function": {"name": "extract_job_details"}},
            temperature=0.1,
            max_tokens=1000
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Extract the function call result
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls and len(tool_calls) > 0:
            args = json.loads(tool_calls[0].function.arguments)
            
            # Only return if there's actual job content
            if not args.get('has_job_content', False):
                ai_logger.info(
                    "Call summary: No job-relevant content found",
                    operation="summarize_call",
                    duration_ms=round(duration_ms, 2),
                    transcript_length=len(transcript)
                )
                return None
            
            ai_logger.info(
                "Call summarized successfully",
                operation="summarize_call",
                duration_ms=round(duration_ms, 2),
                urgency=args.get('urgency_level', 'normal'),
                has_location=bool(args.get('location_details')),
                has_access_info=bool(args.get('access_instructions'))
            )
            
            return args
        
        ai_logger.warning(
            "Call summarization returned no tool calls",
            operation="summarize_call",
            duration_ms=round(duration_ms, 2)
        )
        return None
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        ai_logger.error(
            "Call summarization failed",
            exception=e,
            operation="summarize_call",
            duration_ms=round(duration_ms, 2),
            transcript_length=len(transcript) if transcript else 0
        )
        return None


def format_summary_for_note(summary: Dict[str, Any]) -> str:
    """
    Format the extracted summary into a readable note for the job card.
    
    Args:
        summary: Dictionary with extracted job details
        
    Returns:
        Formatted string for the appointment note
    """
    if not summary:
        return ""
    
    lines = ["📞 Call Summary"]
    lines.append("─" * 30)
    
    # Job description is the main content - give it prominence
    if summary.get('job_description'):
        lines.append(f"\n{summary['job_description']}")
    
    # Add urgency section if not normal
    urgency = summary.get('urgency_level', 'normal')
    if urgency != 'normal':
        lines.append("")
        urgency_display = {
            'urgent': '⚠️ URGENT - Needs attention within 24-48 hours',
            'flexible': '📅 Flexible - Customer has no time pressure'
        }.get(urgency, urgency.title())
        lines.append(f"Priority: {urgency_display}")
        
        if summary.get('urgency_notes'):
            lines.append(f"  → {summary['urgency_notes']}")
    
    # Build details section if any details exist
    details = []
    
    if summary.get('location_details'):
        details.append(f"📍 Location: {summary['location_details']}")
    
    if summary.get('property_info'):
        details.append(f"🏠 Property: {summary['property_info']}")
    
    if summary.get('access_instructions'):
        details.append(f"🔑 Access: {summary['access_instructions']}")
    
    if summary.get('special_requirements'):
        details.append(f"⚡ Special Notes: {summary['special_requirements']}")
    
    if summary.get('previous_work'):
        details.append(f"📋 History: {summary['previous_work']}")
    
    if summary.get('customer_availability'):
        details.append(f"🕐 Availability: {summary['customer_availability']}")
    
    if details:
        lines.append("")
        lines.extend(details)
    
    return "\n".join(lines)


async def add_call_summary_to_booking(
    conversation_log: List[Dict[str, Any]],
    caller_phone: str = None,
    company_id: int = None
) -> bool:
    """
    Summarize a call and add the summary to the most recent booking for this caller.
    Only adds summary to bookings created within the last 10 minutes (during this call).
    
    Args:
        conversation_log: List of conversation messages
        caller_phone: Caller's phone number
        company_id: Company ID for multi-tenant lookup
        
    Returns:
        True if summary was added successfully, False otherwise
    """
    import asyncio
    from datetime import datetime, timedelta
    
    if not conversation_log or not caller_phone:
        print("[INFO] Cannot add call summary: missing conversation log or caller phone")
        return False
    
    # Run the synchronous OpenAI call in a thread pool to avoid blocking
    loop = asyncio.get_running_loop()
    summary = await loop.run_in_executor(None, summarize_call, conversation_log, caller_phone)
    
    if not summary:
        print("[INFO] No job-relevant content to summarize")
        return False
    
    # Format the summary
    note_text = format_summary_for_note(summary)
    
    if not note_text:
        return False
    
    try:
        from src.services.database import get_database
        db = get_database()
        
        # Find the most recent booking for this caller
        # First, find the client by phone number
        client = db.find_client_by_phone(caller_phone, company_id=company_id)
        
        if not client:
            print(f"[INFO] No client found for phone {caller_phone}")
            return False
        
        # Get the most recent booking for this client
        bookings = db.get_client_bookings(client['id'], company_id=company_id)
        
        if not bookings:
            print(f"[INFO] No bookings found for client {client['id']}")
            return False
        
        # Get the most recent booking (first in list since ordered by DESC)
        recent_booking = bookings[0]
        booking_id = recent_booking['id']
        
        # Only add summary to bookings created within the last 10 minutes (during this call)
        booking_created = recent_booking.get('created_at')
        if booking_created:
            # Handle both datetime objects and strings
            if isinstance(booking_created, str):
                try:
                    booking_created = datetime.fromisoformat(booking_created.replace('Z', '+00:00'))
                except ValueError:
                    booking_created = datetime.strptime(booking_created, '%Y-%m-%d %H:%M:%S')
            
            # Make comparison timezone-naive if needed
            now = datetime.now()
            if hasattr(booking_created, 'tzinfo') and booking_created.tzinfo is not None:
                booking_created = booking_created.replace(tzinfo=None)
            
            time_since_booking = now - booking_created
            if time_since_booking > timedelta(minutes=10):
                print(f"[INFO] Most recent booking is {time_since_booking} old, skipping summary (not from this call)")
                return False
        
        # Add the summary as a note
        note_id = db.add_appointment_note(
            booking_id=booking_id,
            note=note_text,
            created_by="ai_call_summary"
        )
        
        if note_id:
            print(f"[SUCCESS] Added call summary to booking {booking_id}")
            
            # Also update urgency if it was detected as urgent
            urgency = summary.get('urgency_level')
            if urgency == 'urgent':
                db.update_booking(booking_id, company_id=company_id, urgency='Same-Day')
                print(f"[INFO] Updated booking urgency to Same-Day")
            
            return True
        
        return False
        
    except Exception as e:
        print(f"[ERROR] Failed to add call summary to booking: {e}")
        import traceback
        traceback.print_exc()
        return False
