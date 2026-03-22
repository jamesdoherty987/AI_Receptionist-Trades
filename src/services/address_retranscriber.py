"""
Post-call address re-transcription service.

After a call ends, if address audio was captured, this service:
1. Downloads the captured address audio from R2
2. Re-transcribes it using OpenAI Whisper (slower but higher quality)
3. Validates the transcription with an LLM (Irish address context)
4. Updates the booking and client address in the database
5. Sends the booking confirmation SMS with the corrected address

This runs async after the call — no time pressure.
"""
import asyncio
import io
import time
import httpx
from typing import Optional, Dict, Any
from openai import OpenAI
from src.utils.config import config
from src.utils.ai_logger import ai_logger


# Lazy OpenAI client with generous timeout (no rush, post-call)
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=httpx.Timeout(60.0, connect=15.0)
        )
    return _client


def whisper_transcribe_address(audio_url: str) -> Optional[str]:
    """
    Download address audio and transcribe with OpenAI Whisper.
    Uses the 'whisper-1' model which is slower but much more accurate
    for difficult audio like Irish addresses.

    Args:
        audio_url: URL of the WAV file in R2 storage

    Returns:
        Transcribed text or None on failure
    """
    start = time.time()
    try:
        # Download the audio file
        print(f"[ADDR_RETRANSCRIBE] Downloading audio: {audio_url}")
        resp = httpx.get(audio_url, timeout=30.0)
        resp.raise_for_status()
        audio_bytes = resp.content
        print(f"[ADDR_RETRANSCRIBE] Downloaded {len(audio_bytes)} bytes")

        # Transcribe with Whisper
        client = _get_client()
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "address.wav"

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
            prompt=(
                "This is someone saying their Irish address or eircode over the phone. "
                "Irish townlands and place names: Ballybrack, Ballybeg, Ballynanty, Ballyclough, "
                "Dooradoyle, Castletroy, Raheen, Annacotty, Monaleen, Caherdavin, Corbally, "
                "Castleconnell, Patrickswell, Adare, Croom, Bruff, Kilmallock, Pallasgreen, "
                "Murroe, Cappamore, Doon, Oola, Pallaskenry, Askeaton, Foynes, Glin, Abbeyfeale, "
                "Newcastle West, Rathkeale, Ballingarry, Knockainey, Hospital, Herbertstown, "
                "Silvergrove, Balenbygan, Ennis, Limerick, Clare, Tipperary, Galway, Kilkenny, "
                "Cork, Kerry, Waterford, Wexford, Dublin, Wicklow, Meath, Kildare, Laois, Offaly. "
                "Eircodes like V94 H2P8, D02 WR97, A86 XY12."
            ),
        )

        duration = time.time() - start
        text = transcript.text.strip() if transcript.text else None
        print(f"[ADDR_RETRANSCRIBE] Whisper result ({duration:.1f}s): '{text}'")
        return text

    except Exception as e:
        duration = time.time() - start
        print(f"[ADDR_RETRANSCRIBE] Whisper failed ({duration:.1f}s): {e}")
        return None


def llm_validate_address(whisper_text: str, original_text: str) -> Dict[str, Any]:
    """
    Use an LLM to validate and clean up the Whisper transcription,
    knowing it's an Irish address.

    Args:
        whisper_text: The Whisper transcription of the address audio
        original_text: The original real-time ASR transcription (for context)

    Returns:
        Dict with 'address' (cleaned), 'confidence' (high/medium/low),
        'eircode' (if found), 'reasoning' (why changes were made)
    """
    start = time.time()
    try:
        client = _get_client()

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert on Irish addresses, townlands, eircodes, and place names. "
                        "The address is located in IRELAND. "
                        "A caller gave their address over the phone and it was transcribed by two systems. "
                        "Your job is to produce the most accurate version of the Irish address.\n\n"
                        "Irish address knowledge:\n"
                        "- Irish addresses often include townlands, parishes, and counties (e.g., 'Ballybrack, Ennis, Co. Clare')\n"
                        "- Common townland prefixes: Bally-, Kil-, Knock-, Drum-, Rath-, Dun-, Liss-, Clon-\n"
                        "- Eircodes are 7 characters: 3 routing key + 4 unique identifier (e.g., V94 H2P8, D02 WR97)\n"
                        "- Common ASR errors: O/0 confusion in eircodes, townland misspellings, 'Bally' vs 'Valley'\n"
                        "- County names: Dublin, Cork, Limerick, Galway, Clare, Kerry, Tipperary, Waterford, Kilkenny, Wexford, etc.\n"
                        "- If both transcriptions agree, use that. If they differ, prefer the Whisper version "
                        "but use the real-time version for context\n"
                        "- Format the address naturally with proper Irish capitalisation and commas\n"
                        "- Include 'Co.' before county names where appropriate\n"
                        "- Extract eircode separately if present\n"
                        "- If the text is clearly NOT an address (e.g., 'yes', 'no', 'I don't know', 'that's correct'), "
                        "set confidence to 'none'"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Real-time transcription: \"{original_text}\"\n"
                        f"Whisper transcription: \"{whisper_text}\"\n\n"
                        "This is an Irish address. Return the best version as JSON with keys: "
                        "address, eircode (null if none), confidence (high/medium/low/none), reasoning"
                    )
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300
        )

        import json
        result = json.loads(response.choices[0].message.content)
        duration = time.time() - start
        print(f"[ADDR_RETRANSCRIBE] LLM validation ({duration:.1f}s): "
              f"confidence={result.get('confidence')}, address='{result.get('address')}'")
        return result

    except Exception as e:
        duration = time.time() - start
        print(f"[ADDR_RETRANSCRIBE] LLM validation failed ({duration:.1f}s): {e}")
        return {
            "address": whisper_text,
            "eircode": None,
            "confidence": "low",
            "reasoning": f"LLM validation failed: {e}"
        }


async def retranscribe_and_update(
    audio_url: str,
    original_address: str,
    caller_phone: str,
    company_id: int,
    booking_id: int = None,
    client_id: int = None,
    send_sms: bool = True,
    sms_kwargs: Dict[str, Any] = None,
) -> Optional[str]:
    """
    Full post-call address refinement pipeline:
    1. Whisper re-transcription
    2. LLM validation
    3. DB update (booking + client)
    4. Send confirmation SMS with corrected address

    All runs in background — no rush.

    Args:
        audio_url: R2 URL of captured address audio
        original_address: Address from real-time ASR (what the AI heard during call)
        caller_phone: Caller's phone number
        company_id: Company ID
        booking_id: Booking ID to update (if known)
        client_id: Client ID to update (if known)
        send_sms: Whether to send confirmation SMS after
        sms_kwargs: Additional kwargs for send_booking_confirmation

    Returns:
        The refined address string, or None if refinement failed
    """
    import asyncio

    print(f"\n{'='*60}")
    print(f"[ADDR_RETRANSCRIBE] Starting post-call address refinement")
    print(f"[ADDR_RETRANSCRIBE] Audio: {audio_url}")
    print(f"[ADDR_RETRANSCRIBE] Original ASR: '{original_address}'")
    print(f"[ADDR_RETRANSCRIBE] Booking: {booking_id}, Client: {client_id}")
    print(f"{'='*60}")

    loop = asyncio.get_running_loop()

    # Step 1: Whisper re-transcription (run in thread — it's synchronous)
    whisper_text = await loop.run_in_executor(None, whisper_transcribe_address, audio_url)

    if not whisper_text:
        print(f"[ADDR_RETRANSCRIBE] Whisper failed — falling back to original: '{original_address}'")
        refined_address = original_address
        refined_eircode = None
    else:
        # Step 2: LLM validation
        result = await loop.run_in_executor(
            None, llm_validate_address, whisper_text, original_address or ""
        )

        confidence = result.get("confidence", "low")
        refined_address = result.get("address")
        refined_eircode = result.get("eircode")

        if confidence == "none":
            print(f"[ADDR_RETRANSCRIBE] LLM says not an address — keeping original: '{original_address}'")
            refined_address = original_address
            refined_eircode = None
        elif confidence in ("high", "medium"):
            print(f"[ADDR_RETRANSCRIBE] Using refined address ({confidence}): '{refined_address}'")
        else:
            # Low confidence — still use it but log warning
            print(f"[ADDR_RETRANSCRIBE] ⚠️ Low confidence — using refined anyway: '{refined_address}'")

    # Step 3: Update database
    if refined_address and (booking_id or client_id):
        try:
            from src.services.database import get_database
            db = get_database()

            if booking_id:
                update_fields = {"address": refined_address}
                if refined_eircode:
                    update_fields["eircode"] = refined_eircode
                db.update_booking(booking_id, company_id=company_id, **update_fields)
                print(f"[ADDR_RETRANSCRIBE] ✅ Updated booking {booking_id} address")

            if client_id:
                update_fields = {}
                if refined_address:
                    update_fields["address"] = refined_address
                if refined_eircode:
                    update_fields["eircode"] = refined_eircode
                if update_fields:
                    db.update_client(client_id, **update_fields)
                    print(f"[ADDR_RETRANSCRIBE] ✅ Updated client {client_id} address")

        except Exception as e:
            print(f"[ADDR_RETRANSCRIBE] ⚠️ DB update failed: {e}")

    # Step 4: Send confirmation SMS with refined address
    if send_sms and sms_kwargs:
        try:
            from src.services.sms_reminder import get_sms_service
            sms = get_sms_service()
            sms_kwargs["address"] = refined_address
            sms.send_booking_confirmation(**sms_kwargs)
            print(f"[ADDR_RETRANSCRIBE] ✅ Confirmation SMS sent with refined address")
        except Exception as e:
            print(f"[ADDR_RETRANSCRIBE] ⚠️ SMS send failed: {e}")

    print(f"[ADDR_RETRANSCRIBE] Pipeline complete. Final address: '{refined_address}'")
    print(f"{'='*60}\n")

    return refined_address
