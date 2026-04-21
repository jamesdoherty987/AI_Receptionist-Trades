"""
Outbound Call Service — initiates AI callback calls via Telnyx.

Used for lost job follow-ups: the AI calls the customer back to politely
ask why they didn't book and offer to help them book now.

Feature flag: OUTBOUND_CALLS_ENABLED env var (default: false).
"""
import os
import httpx
from typing import Dict, Any
from src.utils.config import config


# Feature flag — easy to disable globally
OUTBOUND_CALLS_ENABLED = os.getenv("OUTBOUND_CALLS_ENABLED", "false").lower() == "true"


def is_outbound_enabled() -> bool:
    """Check if outbound calling is enabled and properly configured."""
    return (
        OUTBOUND_CALLS_ENABLED
        and bool(config.TELNYX_API_KEY)
        and bool(os.getenv("TELNYX_TEXML_APP_ID"))
    )


def initiate_lost_job_callback(
    to_number: str,
    company_id: int,
    call_log_id: int,
    caller_name: str = "",
    lost_job_reason: str = "",
    ai_summary: str = "",
) -> Dict[str, Any]:
    """
    Initiate an outbound call to follow up on a lost job.
    
    Uses Telnyx TeXML to place the call and connect it to our
    media stream WebSocket, just like inbound calls.
    
    Returns dict with success status and call details.
    """
    if not is_outbound_enabled():
        return {"success": False, "error": "Outbound calls are not enabled"}

    if not config.TELNYX_API_KEY:
        return {"success": False, "error": "Telnyx API key not configured"}

    from_number = config.TELNYX_PHONE_NUMBER or config.TWILIO_PHONE_NUMBER
    if not from_number:
        return {"success": False, "error": "No outbound phone number configured"}

    if not to_number:
        return {"success": False, "error": "No destination phone number"}

    telnyx_app_id = os.getenv("TELNYX_TEXML_APP_ID", "")
    if not telnyx_app_id:
        return {"success": False, "error": "TELNYX_TEXML_APP_ID not configured"}

    # Build the TeXML webhook URL — when the call connects, Telnyx will
    # POST to this endpoint and we return TeXML to connect to our media stream
    public_url = config.PUBLIC_URL
    if not public_url:
        return {"success": False, "error": "PUBLIC_URL not configured"}

    webhook_url = f"{public_url}/telnyx/outbound-voice"

    # Encode context into query params for reliable delivery
    # (custom_headers may not always be forwarded to the TeXML webhook)
    from urllib.parse import urlencode
    query_params = urlencode({
        "company_id": str(company_id),
        "call_log_id": str(call_log_id),
        "call_type": "lost_job_callback",
        "caller_name": (caller_name or "")[:100],
        "lost_reason": (lost_job_reason or "")[:200],
        "ai_summary": (ai_summary or "")[:500],
    })
    webhook_url_with_params = f"{webhook_url}?{query_params}"

    try:
        # Telnyx TeXML call initiation
        resp = httpx.post(
            "https://api.telnyx.com/v2/texml/calls",
            headers={
                "Authorization": f"Bearer {config.TELNYX_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "to": to_number,
                "from": from_number,
                "connection_id": telnyx_app_id,
                "texml_url": webhook_url_with_params,
                "texml_url_method": "POST",
            },
            timeout=15.0,
        )

        if resp.status_code < 300:
            data = resp.json()
            call_sid = data.get("data", {}).get("call_control_id", "")
            print(f"✅ [OUTBOUND] Lost job callback initiated to {to_number} (call_log={call_log_id}, call_sid={call_sid})")
            return {
                "success": True,
                "call_sid": call_sid,
                "to_number": to_number,
                "call_log_id": call_log_id,
            }
        else:
            error_msg = resp.text[:300]
            print(f"❌ [OUTBOUND] Telnyx call failed: {resp.status_code} {error_msg}")
            return {"success": False, "error": f"Telnyx error: {resp.status_code}"}

    except httpx.TimeoutException:
        print(f"❌ [OUTBOUND] Telnyx call timed out for {to_number}")
        return {"success": False, "error": "Call initiation timed out"}
    except Exception as e:
        print(f"❌ [OUTBOUND] Error initiating call: {e}")
        return {"success": False, "error": str(e)}
