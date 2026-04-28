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


def _track_call_minutes(company_id: int, minutes: int):
    """Increment minutes_used for a company's current billing period.
    
    Called after every AI-handled call ends. Skips tracking for:
    - Dashboard-only plans (no AI)
    - Enterprise plans (unlimited — usage counter still ticks for visibility but no billing impact)
    - Companies without an active subscription
    
    Uses an atomic UPDATE...RETURNING to avoid race conditions on the
    usage alert flag — only one concurrent call will see the transition
    from alert_sent=FALSE to TRUE, preventing duplicate alerts.
    """
    from src.services.database import get_database
    db = get_database()
    
    # Check if we should track for this company
    company = db.get_company(company_id)
    if not company:
        return
    
    plan = company.get('subscription_plan', 'professional')
    
    # Skip tracking for plans that don't have metered minutes
    if plan in ('enterprise', 'dashboard'):
        print(f"[USAGE] Skipping tracking for company {company_id} (plan={plan})")
        return
    
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        # Atomic update: increment minutes_used AND conditionally set alert flag.
        # RETURNING gives us the alert flag state AFTER this UPDATE — only the
        # transaction that flipped it from FALSE to TRUE will see TRUE returned
        # with the "was_false_before" condition.
        cursor.execute("""
            UPDATE companies
            SET minutes_used = COALESCE(minutes_used, 0) + %s,
                usage_alert_sent = CASE
                    WHEN COALESCE(usage_alert_sent, FALSE) = FALSE
                         AND COALESCE(included_minutes, 0) > 0
                         AND COALESCE(minutes_used, 0) + %s >= COALESCE(included_minutes, 0) * 0.8
                    THEN TRUE
                    ELSE COALESCE(usage_alert_sent, FALSE)
                END
            WHERE id = %s
            RETURNING
                COALESCE(minutes_used, 0),
                COALESCE(included_minutes, 0),
                COALESCE(usage_alert_sent, FALSE),
                (COALESCE(usage_alert_sent, FALSE) = FALSE) IS NOT NULL
        """, (minutes, minutes, company_id))
        row = cursor.fetchone()
        conn.commit()
        
        if not row:
            print(f"[USAGE] No row returned for company {company_id}")
            return
        
        new_used, included, now_alert_sent, _ = row
        print(f"[USAGE] Company {company_id}: +{minutes} min tracked ({new_used}/{included})")
        
        # Check if we just crossed the 80% threshold (alert_sent flipped in this tx)
        was_alert_sent = company.get('usage_alert_sent', False)
        if not was_alert_sent and now_alert_sent:
            try:
                _send_usage_alert_email(company, new_used, included)
            except Exception as e:
                print(f"[USAGE] Alert email error for company {company_id}: {e}")
    except Exception as e:
        conn.rollback()
        print(f"[USAGE] Error tracking minutes for company {company_id}: {e}")
    finally:
        db.return_connection(conn)


def _send_usage_alert_email(company: dict, minutes_used: int, included: int):
    """Log 80% usage alert. TODO: integrate with email service when available.
    
    Currently this just logs the alert and marks it as sent. When an email
    service is wired up, replace the print with an actual email send.
    """
    try:
        pct = int((minutes_used / included) * 100) if included else 0
        remaining = max(0, included - minutes_used)
        email = company.get('email', 'unknown')
        company_name = company.get('company_name', 'unknown')
        overage_rate = (company.get('overage_rate_cents', 12) or 12) / 100
        
        print(f"[USAGE_ALERT] ⚠️  Company '{company_name}' ({email}) at {pct}% usage")
        print(f"[USAGE_ALERT]    {minutes_used:,}/{included:,} mins used, {remaining:,} remaining")
        print(f"[USAGE_ALERT]    Overage rate: €{overage_rate:.2f}/min once limit reached")
        # TODO: Send actual email via Resend/SMTP when email service is integrated
    except Exception as e:
        print(f"[USAGE] Could not send alert notification: {e}")


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
- Extract caller_name, address, eircode, email if mentioned; leave as empty string if not

NAME EXTRACTION RULES:
- The caller may say their name naturally ("My name is James Doherty") OR spell it out letter by letter ("J-A-M-E-S D-O-H-E-R-T-Y" or "J A M E S")
- If the name is spelled out, reconstruct the full name from the individual letters
- If both a spoken name and a spelled-out version exist, prefer the spelled-out version (it's more accurate)
- Always capitalize names properly (first letter of each word)

EMAIL EXTRACTION RULES:
- The caller may say their email naturally ("john at gmail dot com") OR spell it out ("j-o-h-n at g-m-a-i-l dot c-o-m")
- Reconstruct the full email address from however it was provided
- Convert "at" to "@" and "dot" to "."
- If both a spoken and spelled-out version exist, prefer the spelled-out version"""


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
      3. Updating client records with extracted name/email/address (phone-first identification)
    
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

    # 2b. Track call minutes for usage-based billing
    if company_id and duration_seconds and duration_seconds > 0:
        try:
            import math
            call_minutes = math.ceil(duration_seconds / 60)  # Round up to nearest minute
            print(f"[USAGE] Tracking {call_minutes} min for company {company_id} (duration={duration_seconds}s)")
            _track_call_minutes(company_id, call_minutes)
        except Exception as e:
            import traceback
            print(f"⚠️ Usage tracking error: {e}")
            traceback.print_exc()
    elif company_id:
        print(f"[USAGE] Skipping tracking: duration_seconds={duration_seconds}")

    # 3. Post-call client record update — update name/email/address from transcript
    # This handles both new customers (whose name was only spoken, not looked up)
    # and returning customers (whose email/address may have been updated during the call)
    if caller_phone and company_id:
        try:
            await _update_client_from_transcript(combined, caller_phone, company_id)
        except Exception as e:
            print(f"⚠️ Client update from transcript error: {e}")

    # 4. Auto-create lead for non-booking calls that had real interest
    # Calls that result in a booking already create a customer, so skip those.
    # Also skip wrong numbers, hang-ups with no conversation, and pure no-action calls.
    if company_id and call_log_id:
        outcome = combined.get("call_outcome", "no_action")
        is_lost = combined.get("is_lost_job", False)
        has_content = combined.get("has_job_content", False)
        # Create a lead if: lost job, enquiry with job content, or cancelled/rescheduled (they may rebook)
        should_create_lead = (
            outcome in ("lost_job", "enquiry") and (is_lost or has_content)
        ) or (
            outcome == "cancelled" and has_content
        )
        if should_create_lead:
            try:
                await _create_lead_from_call(
                    combined=combined,
                    caller_phone=caller_phone,
                    company_id=company_id,
                    call_log_id=call_log_id,
                    call_state=call_state,
                )
            except Exception as e:
                print(f"⚠️ Auto-lead creation error: {e}")

    return call_log_id


async def _create_lead_from_call(
    combined: Dict[str, Any],
    caller_phone: str,
    company_id: int,
    call_log_id: int,
    call_state=None,
) -> Optional[int]:
    """
    Auto-create a lead from a non-booking call.
    Uses phone number, caller name, email, address, job description, and AI summary
    extracted from the call. Skips if:
    - A lead already exists for this call_log_id
    - There's already a recent lead from the same phone (within 24h) — updates it instead
    - The caller is already an existing customer (no need to track as a lead)
    """
    from src.services.database import get_database
    db = get_database()
    conn = None

    # Build lead data from the AI-extracted call summary
    caller_name = combined.get("caller_name", "")
    # Enrich from call_state if available
    if call_state and not caller_name:
        caller_name = call_state.get("customer_name", "")

    # Use phone number as fallback name
    name = caller_name.strip() if caller_name else (caller_phone or "Unknown Caller")
    phone = caller_phone or ""
    email = (combined.get("email") or "").strip()
    address = (combined.get("address") or "").strip()
    job_desc = (combined.get("job_description") or "").strip()
    ai_summary = (combined.get("ai_summary") or "").strip()
    lost_reason = (combined.get("lost_job_reason") or "").strip()
    outcome = combined.get("call_outcome", "no_action")

    # Determine source and initial stage
    source = "ai_call"
    if outcome == "lost_job":
        stage = "new"  # They wanted to book but couldn't — hot lead
    elif outcome == "cancelled":
        stage = "contacted"  # They were a customer, might rebook
    else:
        stage = "new"  # Enquiry or other

    # Build notes from AI summary + lost reason
    notes_parts = []
    if ai_summary:
        notes_parts.append(ai_summary)
    if lost_reason:
        notes_parts.append(f"Reason: {lost_reason}")
    notes = " | ".join(notes_parts) if notes_parts else None

    # Service interest from job description (truncate if very long)
    service_interest = job_desc[:200] if job_desc else None

    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        # Skip if the caller is already an existing customer
        # (they don't need to be tracked as a lead)
        if phone:
            cursor.execute(
                "SELECT id FROM clients WHERE company_id = %s AND phone = %s LIMIT 1",
                (company_id, phone)
            )
            if cursor.fetchone():
                print(f"[LEAD] Caller {phone} is already a customer, skipping lead creation")
                return None

        # Dedup: skip if a lead already exists for this exact call_log_id
        cursor.execute(
            "SELECT id FROM leads WHERE company_id = %s AND call_log_id = %s",
            (company_id, call_log_id)
        )
        if cursor.fetchone():
            print(f"[LEAD] Lead already exists for call_log_id={call_log_id}, skipping")
            return None

        # Dedup: if there's a lead from the same phone in the last 24 hours,
        # update it with the new call info instead of creating a duplicate
        if phone:
            cursor.execute("""
                SELECT id FROM leads
                WHERE company_id = %s AND phone = %s
                  AND created_at > NOW() - INTERVAL '24 hours'
                  AND stage NOT IN ('won', 'lost')
                ORDER BY created_at DESC LIMIT 1
            """, (company_id, phone))
            existing = cursor.fetchone()
            if existing:
                update_vals = []
                set_clauses = ["updated_at = NOW()", "call_log_id = %s"]
                update_vals.append(call_log_id)
                if notes:
                    set_clauses.append("notes = COALESCE(notes, '') || %s")
                    update_vals.append(f"\n📞 Follow-up call: {notes}")
                update_vals.append(existing[0])
                cursor.execute(
                    f"UPDATE leads SET {', '.join(set_clauses)} WHERE id = %s",
                    tuple(update_vals)
                )
                conn.commit()
                print(f"[LEAD] Updated existing lead id={existing[0]} with new call info")
                return existing[0]

        # Create the lead
        cursor.execute("""
            INSERT INTO leads (company_id, call_log_id, name, phone, email, address,
                               source, stage, notes, service_interest, lost_reason,
                               created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        """, (
            company_id, call_log_id, name, phone or None, email or None,
            address or None, source, stage, notes, service_interest,
            lost_reason or None,
        ))
        lead_id = cursor.fetchone()[0]
        conn.commit()
        print(f"[LEAD] Auto-created lead id={lead_id} from call_log_id={call_log_id} "
              f"(outcome={outcome}, name={name}, phone={phone})")

        # Create notification for the owner about the new lead
        try:
            svc_text = f" interested in {service_interest}" if service_interest else ""
            db.create_notification(
                company_id=company_id,
                recipient_type='owner',
                recipient_id=0,
                notif_type='new_lead',
                message=f"New lead: {name}{svc_text}",
                metadata={'lead_id': lead_id, 'source': source, 'phone': phone},
            )
        except Exception:
            pass  # Non-critical

        return lead_id

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] Failed to auto-create lead: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            db.return_connection(conn)


async def _update_client_from_transcript(
    summary: Dict[str, Any],
    caller_phone: str,
    company_id: int,
) -> None:
    """
    Post-call: update client record with name/email/address extracted from transcript.
    For new customers, this fills in the name that was only spoken during the call.
    For returning customers, this can update email/address if they provided new ones.
    """
    from src.services.database import get_database
    
    extracted_name = (summary.get("caller_name") or "").strip()
    extracted_email = (summary.get("email") or "").strip()
    extracted_address = (summary.get("address") or "").strip()
    extracted_eircode = (summary.get("eircode") or "").strip()
    
    if not extracted_name and not extracted_email and not extracted_address and not extracted_eircode:
        print(f"[POST_CALL] No name/email/address extracted from transcript — skipping client update")
        return
    
    db = get_database()
    client = db.find_client_by_phone(caller_phone, company_id=company_id)
    
    if client:
        # Existing client — update fields that are missing or were provided fresh
        updates = {}
        
        # Update name if the current name looks like a placeholder or is missing
        current_name = (client.get('name') or '').strip()
        if extracted_name and (not current_name or current_name.lower() in ('unknown', 'caller', '')):
            updates['name'] = extracted_name
            print(f"[POST_CALL] Updating client name: '{current_name}' → '{extracted_name}'")
        
        # Update email if not already set
        if extracted_email and not client.get('email'):
            updates['email'] = extracted_email
            print(f"[POST_CALL] Setting client email: '{extracted_email}'")
        
        # Always update address from the latest call (most recent address wins)
        if extracted_address:
            if client.get('address') != extracted_address:
                updates['address'] = extracted_address
                print(f"[POST_CALL] Updating client address: '{client.get('address')}' → '{extracted_address}'")
        
        # Always update eircode from the latest call (most recent wins)
        if extracted_eircode:
            if client.get('eircode') != extracted_eircode:
                updates['eircode'] = extracted_eircode
                print(f"[POST_CALL] Updating client eircode: '{client.get('eircode')}' → '{extracted_eircode}'")
        
        if updates:
            try:
                db.update_client(client['id'], **updates)
                print(f"[POST_CALL] ✅ Updated client {client['id']} with: {list(updates.keys())}")
            except Exception as e:
                print(f"[POST_CALL] ❌ Failed to update client {client['id']}: {e}")
        else:
            print(f"[POST_CALL] Client {client['id']} already has all info — no updates needed")
    else:
        print(f"[POST_CALL] No client found for phone {caller_phone} — skipping (client may not have been created yet)")


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
