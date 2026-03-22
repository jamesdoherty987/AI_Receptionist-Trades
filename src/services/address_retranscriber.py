"""
Post-call address re-transcription service.

After a call ends, if address audio was captured, this service:
1. Downloads the captured address audio from R2
2. Re-transcribes it using OpenAI gpt-4o-transcribe (highest quality STT)
3. Updates the booking and client address in the database
4. Sends the booking confirmation SMS with the corrected address

This runs async after the call — no time pressure.
Uses the same OPENAI_API_KEY as the rest of the system.
"""
import asyncio
import io
import time
import httpx
from typing import Optional, Dict, Any
from openai import OpenAI
from src.utils.config import config


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


def transcribe_address_audio(audio_url: str) -> Optional[str]:
    """
    Download address audio and re-transcribe with OpenAI gpt-4o-transcribe.
    This model has significantly lower word error rates than whisper-1,
    especially for accented English and proper nouns.

    No time pressure — this runs after the call ends.

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

        client = _get_client()
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "address.wav"

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file,
        )

        duration = time.time() - start
        text = transcript.text.strip() if transcript.text else None
        print(f"[ADDR_RETRANSCRIBE] gpt-4o-transcribe result ({duration:.1f}s): '{text}'")
        return text

    except Exception as e:
        duration = time.time() - start
        print(f"[ADDR_RETRANSCRIBE] Transcription failed ({duration:.1f}s): {e}")
        return None


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
    Post-call address refinement pipeline:
    1. gpt-4o-transcribe re-transcription of the address audio
    2. DB update (booking + client)
    3. Send confirmation SMS with the corrected address

    All runs after the call ends — no rush.

    Args:
        audio_url: R2 URL of captured address audio
        original_address: Address from real-time ASR (what Deepgram heard during call)
        caller_phone: Caller's phone number
        company_id: Company ID
        booking_id: Booking ID to update (if known)
        client_id: Client ID to update (if known)
        send_sms: Whether to send confirmation SMS after
        sms_kwargs: Additional kwargs for send_booking_confirmation

    Returns:
        The refined address string, or None if refinement failed
    """
    print(f"\n{'='*60}")
    print(f"[ADDR_RETRANSCRIBE] Starting post-call address refinement")
    print(f"[ADDR_RETRANSCRIBE] Audio: {audio_url}")
    print(f"[ADDR_RETRANSCRIBE] Original ASR: '{original_address}'")
    print(f"[ADDR_RETRANSCRIBE] Booking: {booking_id}, Client: {client_id}")
    print(f"{'='*60}")

    loop = asyncio.get_running_loop()

    # Step 1: Re-transcribe with gpt-4o-transcribe (run in thread — it's synchronous)
    refined_address = await loop.run_in_executor(None, transcribe_address_audio, audio_url)

    if not refined_address:
        print(f"[ADDR_RETRANSCRIBE] Transcription failed — falling back to original: '{original_address}'")
        refined_address = original_address

    # Step 2: Update database
    if refined_address and (booking_id or client_id):
        try:
            from src.services.database import get_database
            db = get_database()

            if booking_id:
                db.update_booking(booking_id, company_id=company_id, address=refined_address)
                print(f"[ADDR_RETRANSCRIBE] ✅ Updated booking {booking_id} address")

            if client_id:
                db.update_client(client_id, address=refined_address)
                print(f"[ADDR_RETRANSCRIBE] ✅ Updated client {client_id} address")

        except Exception as e:
            print(f"[ADDR_RETRANSCRIBE] ⚠️ DB update failed: {e}")

    # Step 3: Send confirmation SMS with refined address
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
