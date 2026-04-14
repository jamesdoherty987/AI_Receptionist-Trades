"""
Call Summarization Service
Extracts job-relevant details from call transcripts and adds them to job cards.
Also generates call log summaries for every call.

OPTIMIZED: Uses a single LLM call to extract BOTH job details and call log data,
saving one API round-trip and ~1K duplicate input tokens per call.
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
    """Get or create OpenAI client instance with timeout"""
    global _client
    if _client is None:
        import httpx
        _client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=httpx.Timeout(30.0, connect=10.0)  # 10s connect, 30s total for summarization
        )
    return _client


# Combined function definition — extracts BOTH job details and call log fields in one shot
COMBINED_SUMMARY_FUNCTION = {
    "name": "extract_call_summary",
    "description": "Extract job details AND call log information from a phone call transcript in a single pass.",
    "parameters": {
        "type": "object",
        "properties": {
            # --- Job detail fields (for booking notes) ---
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
            },
            # --- Call log fields (for every call) ---
            "caller_name": {
                "type": "string",
                "description": "The caller's name if mentioned during the call. Leave empty string if not provided."
            },
            "address": {
                "type": "string",
                "description": "The caller's address if mentioned. Leave empty string if not provided."
            },
            "eircode": {
                "type": "string",
                "description": "The caller's eircode/postcode if mentioned. Leave empty string if not provided."
            },
            "email": {
                "type": "string",
                "description": "The caller's email address if mentioned. Leave empty string if not provided."
            },
            "call_outcome": {
                "type": "string",
                "enum": ["booked", "cancelled", "rescheduled", "lost_job", "enquiry", "wrong_number", "hung_up", "no_action"],
                "description": "What happened on the call. Use 'booked' if a new appointment was made. Use 'cancelled' if an existing appointment was cancelled. Use 'rescheduled' if an appointment was moved. Use 'lost_job' if the caller had ANY interest in getting work/service done but did NOT end up booking — this includes: caller asked about a specific service or job, caller described a problem they need fixed, caller asked about availability or pricing for a service, caller said they'd call back or think about it, no suitable availability was found, caller hung up or left during the booking process, caller seemed hesitant or was put off. Use 'enquiry' ONLY for purely informational calls where the caller had absolutely NO intent to get work done. Use 'wrong_number' if the caller had the wrong number. Use 'hung_up' if the caller disconnected very early before any real conversation. Use 'no_action' if the call completed but doesn't fit any other category. When in doubt between 'enquiry' and 'lost_job', prefer 'lost_job'."
            },
            "is_lost_job": {
                "type": "boolean",
                "description": "True if the caller had ANY level of interest in getting a service or job done but did NOT end up with a confirmed booking. False ONLY if: a booking was successfully made, it was purely a cancellation/reschedule, it was a wrong number, the caller hung up before any conversation, or the caller was asking a purely informational question with genuinely zero intent to book any work. Err on the side of marking as true."
            },
            "lost_job_reason": {
                "type": "string",
                "description": "If is_lost_job is true, briefly explain why the job was lost (e.g., 'No availability on requested date', 'Caller hung up during booking'). Leave empty string if not a lost job."
            },
            "ai_summary": {
                "type": "string",
                "description": "A concise 1-3 sentence summary of the entire call from start to finish. Include what the caller wanted, what happened, and the outcome. Be factual and brief."
            }
        },
        "required": ["job_description", "urgency_level", "has_job_content", "call_outcome", "ai_summary", "is_lost_job"]
    }
}

COMBINED_SYSTEM_PROMPT = """You are an expert at extracting information from phone call transcripts for a trades/service business. You extract BOTH detailed job information (for technician notes) AND a concise call log summary in a single pass.

JOB DESCRIPTION RULES:
- Write detailed, descriptive summaries in flowing professional prose (2-4 sentences minimum)
- Include: primary problem, symptoms, timeline, severity, what customer tried, impact
- EXCLUDE: greetings, small talk, generic confirmations, receptionist responses
- If no real job info exists (wrong number, just checking hours), set has_job_content to false and write a minimal job_description

CALL LOG RULES:
- Classify call_outcome accurately. When in doubt between 'enquiry' and 'lost_job', ALWAYS choose 'lost_job'
- A caller who discusses ANY specific service need is a lost job, not an enquiry
- ai_summary should be 1-3 factual sentences covering what happened start to finish
- Extract caller_name, address, eircode, email if mentioned; leave as empty string if not"""


def _build_transcript(conversation_log: List[Dict[str, Any]]) -> Optional[str]:
    """Build transcript text from conversation log. Returns None if empty."""
    transcript_lines = []
    for msg in conversation_log:
        role = "Customer" if msg.get('role') == 'user' else "Receptionist"
        content = msg.get('content', '').strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    return "\n".join(transcript_lines) if transcript_lines else None


def _empty_call_log(outcome: str = "hung_up", summary: str = "Call ended before any conversation took place.") -> Dict[str, Any]:
    """Return a minimal call log dict for early-exit cases."""
    return {
        "call_outcome": outcome,
        "ai_summary": summary,
        "caller_name": "",
        "address": "",
        "eircode": "",
        "email": "",
        "is_lost_job": False,
        "lost_job_reason": "",
    }


def summarize_call_combined(conversation_log: List[Dict[str, Any]], caller_phone: str = None) -> Dict[str, Any]:
    """
    Single LLM call that extracts BOTH job details and call log data.
    
    Returns a dict with all fields from COMBINED_SUMMARY_FUNCTION.
    The caller can split this into job_details vs call_log fields as needed.
    
    For empty/no-conversation calls, returns defaults without calling the LLM.
    """
    if not conversation_log:
        return {**_empty_call_log(), "has_job_content": False, "job_description": "", "urgency_level": "normal"}

    # Check if caller ever spoke
    customer_messages = [m for m in conversation_log if m.get('role') == 'user']
    if not customer_messages:
        return {
            **_empty_call_log("hung_up", "Caller hung up before speaking. No conversation took place."),
            "has_job_content": False, "job_description": "", "urgency_level": "normal",
        }

    transcript = _build_transcript(conversation_log)
    if not transcript:
        return {**_empty_call_log(), "has_job_content": False, "job_description": "", "urgency_level": "normal"}

    start_time = time.time()

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=config.SUMMARIZER_MODEL,
            messages=[
                {"role": "system", "content": COMBINED_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract job details and call log from this transcript:\n\n{transcript}"},
            ],
            tools=[{"type": "function", "function": COMBINED_SUMMARY_FUNCTION}],
            tool_choice={"type": "function", "function": {"name": "extract_call_summary"}},
            temperature=0.1,
            **config.max_tokens_param(model=config.SUMMARIZER_MODEL, value=1000),
        )

        duration_ms = (time.time() - start_time) * 1000

        tool_calls = response.choices[0].message.tool_calls
        if tool_calls and len(tool_calls) > 0:
            result = json.loads(tool_calls[0].function.arguments)
            ai_logger.info(
                "Combined call summary extracted",
                operation="summarize_call_combined",
                duration_ms=round(duration_ms, 2),
                has_job=result.get("has_job_content", False),
                outcome=result.get("call_outcome", "unknown"),
                transcript_length=len(transcript),
            )
            return result

        ai_logger.warning("Combined summarization returned no tool calls", operation="summarize_call_combined", duration_ms=round(duration_ms, 2))
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        ai_logger.error("Combined summarization failed", exception=e, operation="summarize_call_combined", duration_ms=round(duration_ms, 2))

    # Fallback
    return {
        **_empty_call_log("no_action", "Call summary could not be generated."),
        "has_job_content": False, "job_description": "", "urgency_level": "normal",
    }


# ---------------------------------------------------------------------------
# Public API — kept backwards-compatible so callers don't need to change
# ---------------------------------------------------------------------------

def summarize_call(conversation_log: List[Dict[str, Any]], caller_phone: str = None) -> Optional[Dict[str, Any]]:
    """
    Extract job-relevant details from a call transcript.
    Now delegates to the combined summarizer and returns only the job fields.
    
    Returns dict with job details, or None if no job content.
    """
    combined = summarize_call_combined(conversation_log, caller_phone)
    if not combined.get("has_job_content", False):
        return None
    # Return only the job-detail fields (what the old summarize_call returned)
    return {
        "job_description": combined.get("job_description", ""),
        "urgency_level": combined.get("urgency_level", "normal"),
        "urgency_notes": combined.get("urgency_notes", ""),
        "location_details": combined.get("location_details", ""),
        "property_info": combined.get("property_info", ""),
        "access_instructions": combined.get("access_instructions", ""),
        "special_requirements": combined.get("special_requirements", ""),
        "previous_work": combined.get("previous_work", ""),
        "customer_availability": combined.get("customer_availability", ""),
        "has_job_content": True,
    }


def generate_call_log_summary(conversation_log: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Generate a call log summary for ANY call.
    Now delegates to the combined summarizer and returns only the call-log fields.
    """
    combined = summarize_call_combined(conversation_log)
    return {
        "caller_name": combined.get("caller_name", ""),
        "address": combined.get("address", ""),
        "eircode": combined.get("eircode", ""),
        "email": combined.get("email", ""),
        "call_outcome": combined.get("call_outcome", "no_action"),
        "ai_summary": combined.get("ai_summary", ""),
        "is_lost_job": combined.get("is_lost_job", False),
        "lost_job_reason": combined.get("lost_job_reason", ""),
    }


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


async def _add_summary_to_booking(job_details: Dict[str, Any], caller_phone: str, company_id: int) -> bool:
    """
    Add job summary to the most recent booking for this caller.
    Only adds summary to bookings created within the last 10 minutes (during this call).
    
    Args:
        job_details: Job-detail fields extracted by the combined summarizer
        caller_phone: Caller's phone number
        company_id: Company ID for multi-tenant lookup
    """
    from datetime import datetime, timedelta

    if not job_details or not job_details.get("has_job_content") or not caller_phone:
        return False

    note_text = format_summary_for_note(job_details)
    if not note_text:
        return False

    try:
        from src.services.database import get_database
        db = get_database()

        client = db.find_client_by_phone(caller_phone, company_id=company_id)
        if not client:
            print(f"[INFO] No client found for phone {caller_phone}")
            return False

        bookings = db.get_client_bookings(client['id'], company_id=company_id)
        if not bookings:
            print(f"[INFO] No bookings found for client {client['id']}")
            return False

        recent_booking = bookings[0]
        booking_id = recent_booking['id']

        booking_created = recent_booking.get('created_at')
        if booking_created:
            if isinstance(booking_created, str):
                try:
                    booking_created = datetime.fromisoformat(booking_created.replace('Z', '+00:00'))
                except ValueError:
                    booking_created = datetime.strptime(booking_created, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            if hasattr(booking_created, 'tzinfo') and booking_created.tzinfo is not None:
                booking_created = booking_created.replace(tzinfo=None)
            if now - booking_created > timedelta(minutes=10):
                print(f"[INFO] Most recent booking is too old, skipping summary")
                return False

        note_id = db.add_appointment_note(
            booking_id=booking_id,
            note=note_text,
            created_by="ai_call_summary"
        )

        if note_id:
            print(f"[SUCCESS] Added call summary to booking {booking_id}")
            if job_details.get('urgency_level') == 'urgent':
                db.update_booking(booking_id, company_id=company_id, urgency='Same-Day')
                print(f"[INFO] Updated booking urgency to Same-Day")
            return True
        return False

    except Exception as e:
        print(f"[ERROR] Failed to add call summary to booking: {e}")
        import traceback
        traceback.print_exc()
        return False


async def _log_call_to_db(
    log_data: Dict[str, Any],
    caller_phone: str,
    company_id: int,
    duration_seconds: int = None,
    call_sid: str = None,
    call_state=None,
) -> Optional[int]:
    """Write call log entry to the database using pre-extracted log data."""
    if not company_id:
        return None

    # Enrich with call_state data if available (more reliable than LLM extraction)
    if call_state:
        if call_state.get('customer_name') and not log_data.get('caller_name'):
            log_data['caller_name'] = call_state.get('customer_name')
        if call_state.get('job_address') and not log_data.get('address'):
            log_data['address'] = call_state.get('job_address')
        if call_state.get('already_booked'):
            log_data['call_outcome'] = 'booked'

    try:
        from src.services.database import get_database
        db = get_database()
        call_log_id = db.create_call_log(
            company_id=int(company_id),
            phone_number=caller_phone,
            caller_name=log_data.get('caller_name') or None,
            address=log_data.get('address') or None,
            eircode=log_data.get('eircode') or None,
            duration_seconds=duration_seconds,
            call_outcome=log_data.get('call_outcome', 'no_action'),
            ai_summary=log_data.get('ai_summary') or None,
            call_sid=call_sid,
            is_lost_job=bool(log_data.get('is_lost_job', False)),
            lost_job_reason=log_data.get('lost_job_reason') or None,
        )
        if call_log_id:
            print(f"[SUCCESS] Call logged (id={call_log_id}, outcome={log_data.get('call_outcome')})")
        return call_log_id
    except Exception as e:
        print(f"[ERROR] Failed to log call: {e}")
        import traceback
        traceback.print_exc()
        return None


async def summarize_and_log_call(
    conversation_log: List[Dict[str, Any]],
    caller_phone: str = None,
    company_id: int = None,
    duration_seconds: int = None,
    call_sid: str = None,
    call_state=None,
) -> Optional[int]:
    """
    Single entry point for all post-call processing.
    Makes ONE LLM call, then uses the result for both:
      1. Adding job notes to the booking (if a booking was made)
      2. Logging the call to call_logs table (always)
    
    Returns the call_log id if successful.
    """
    import asyncio

    if not conversation_log:
        print("[INFO] Cannot summarize: empty conversation log")
        return None

    # One LLM call — run in thread pool since it's synchronous
    loop = asyncio.get_running_loop()
    combined = await loop.run_in_executor(None, summarize_call_combined, conversation_log, caller_phone)

    # 1. Add job summary to booking (if there's job content and a caller phone)
    if combined.get("has_job_content") and caller_phone and company_id:
        try:
            await _add_summary_to_booking(combined, caller_phone, company_id)
        except Exception as e:
            print(f"⚠️ Booking summary error: {e}")

    # 2. Log the call (always)
    call_log_id = None
    if company_id:
        log_data = {
            "caller_name": combined.get("caller_name", ""),
            "address": combined.get("address", ""),
            "eircode": combined.get("eircode", ""),
            "email": combined.get("email", ""),
            "call_outcome": combined.get("call_outcome", "no_action"),
            "ai_summary": combined.get("ai_summary", ""),
            "is_lost_job": combined.get("is_lost_job", False),
            "lost_job_reason": combined.get("lost_job_reason", ""),
        }
        try:
            call_log_id = await _log_call_to_db(
                log_data=log_data,
                caller_phone=caller_phone,
                company_id=company_id,
                duration_seconds=duration_seconds,
                call_sid=call_sid,
                call_state=call_state,
            )
        except Exception as e:
            print(f"⚠️ Call log error: {e}")

    return call_log_id


# ---------------------------------------------------------------------------
# Legacy wrappers — kept for backwards compatibility with any other callers
# ---------------------------------------------------------------------------

async def add_call_summary_to_booking(
    conversation_log: List[Dict[str, Any]],
    caller_phone: str = None,
    company_id: int = None,
) -> bool:
    """Legacy wrapper. Prefer summarize_and_log_call for new code."""
    import asyncio
    loop = asyncio.get_running_loop()
    summary = await loop.run_in_executor(None, summarize_call, conversation_log, caller_phone)
    if not summary:
        return False
    return await _add_summary_to_booking(summary, caller_phone, company_id)


async def log_call(
    conversation_log: List[Dict[str, Any]],
    caller_phone: str = None,
    company_id: int = None,
    duration_seconds: int = None,
    call_sid: str = None,
    call_state=None,
) -> Optional[int]:
    """Legacy wrapper. Prefer summarize_and_log_call for new code."""
    import asyncio
    if not company_id:
        return None
    loop = asyncio.get_running_loop()
    log_data = await loop.run_in_executor(None, generate_call_log_summary, conversation_log)
    if not log_data:
        log_data = _empty_call_log("no_action", "")
    return await _log_call_to_db(log_data, caller_phone, company_id, duration_seconds, call_sid, call_state)
