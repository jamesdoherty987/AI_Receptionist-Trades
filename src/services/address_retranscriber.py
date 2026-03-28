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
            prompt=(
                "Transcribe ONLY the address or eircode from this audio. "
                "The caller may be saying an Irish eircode (7-character alphanumeric code like V95H5P2, D02WR97, A86DP21) "
                "OR a street address. If they spell out individual letters and numbers, reconstruct the eircode. "
                "Return just the address or eircode itself — no filler words, no conversational phrases "
                "like 'yeah', 'no problem', 'it's', 'sure', 'the address is', etc. "
                "Do NOT convert an eircode into a street address. If you hear a code, return the code."
            ),
        )

        duration = time.time() - start
        text = transcript.text.strip() if transcript.text else None
        print(f"[ADDR_RETRANSCRIBE] gpt-4o-transcribe result ({duration:.1f}s): '{text}'")
        
        # Strip conversational prefixes the caller may have said before the address
        # e.g. "Yeah, it's 13 Oceanview..." → "13 Oceanview..."
        if text:
            import re
            text = re.sub(
                r'^(?:yeah|yes|yep|sure|okay|ok|right|so|well|um|uh|eh|ah)'
                r'[\s,.:;]*'
                r"(?:it'?s|that'?s|the address is|my address is|the eircode is|my eircode is|i'?m at|we'?re at|it is|that is)?"
                r'[\s,.:;]*',
                '', text, count=1, flags=re.IGNORECASE
            ).strip()
            # If stripping removed everything, fall back to original
            if not text:
                text = transcript.text.strip()
            
            # If the result looks like an eircode, normalize it (remove spaces/dashes)
            if _looks_like_eircode(text):
                cleaned_eircode = re.sub(r'[-\s]', '', text.strip()).upper()
                print(f"[ADDR_RETRANSCRIBE] Detected eircode: '{text}' → '{cleaned_eircode}'")
                text = cleaned_eircode
            
            print(f"[ADDR_RETRANSCRIBE] After prefix cleanup: '{text}'")
        
        return text

    except Exception as e:
        duration = time.time() - start
        print(f"[ADDR_RETRANSCRIBE] Transcription failed ({duration:.1f}s): {e}")
        return None


def _looks_like_eircode(text: str) -> bool:
    """Check if text looks like an Irish eircode (e.g. V95H5P2, D02 WR97)."""
    import re
    cleaned = re.sub(r'[-\s]', '', text.strip())
    # Standard eircode: letter + (O or 0) + digit + 4 alphanumeric, OR letter + 2 digits + 4 alphanumeric
    if re.match(r'^[A-Z][O0]\d[A-Z0-9]{4}$', cleaned, re.IGNORECASE):
        return True
    if re.match(r'^[A-Z]\d{2}[A-Z0-9]{4}$', cleaned, re.IGNORECASE):
        return True
    # Looser: 6-8 alphanumeric with at least one letter and one digit (ASR mangled eircode)
    if re.match(r'^[A-Z0-9]{6,8}$', cleaned, re.IGNORECASE) and re.search(r'[A-Z]', cleaned, re.IGNORECASE) and re.search(r'\d', cleaned):
        return True
    return False


def _is_plausible_address_standalone(refined: str) -> bool:
    """
    Check if a refined transcription is plausible when we have NO original to compare against.
    Used when the original address was empty (e.g. eircode-only booking).
    
    Rejects obvious filler/hallucinations. More permissive than the overlap-based check
    since we can't compare — but catches the worst cases.
    """
    import re
    refined_lower = refined.lower().strip().rstrip('.,!? ')
    
    # Accept eircodes
    if _looks_like_eircode(refined):
        return True
    
    # Reject conversational filler
    filler_phrases = [
        'perfect', 'thanks', 'thank you', 'great', 'okay', 'ok', 'yes',
        'no problem', 'that\'s it', 'that\'s correct', 'correct', 'grand',
        'lovely', 'brilliant', 'cheers', 'bye', 'goodbye', 'no', 'yeah',
        'sure', 'right', 'absolutely', 'of course'
    ]
    if refined_lower in filler_phrases:
        print(f"[ADDR_RETRANSCRIBE] Standalone validation: looks like filler")
        return False
    
    # Reject very short non-eircode text (< 3 words and not a code)
    if len(refined_lower.split()) < 2:
        print(f"[ADDR_RETRANSCRIBE] Standalone validation: too short ({len(refined_lower.split())} words)")
        return False
    
    return True


def _is_plausible_address(refined: str, original: str) -> bool:
    """
    Check if a refined transcription is plausibly the same address as the original.
    
    Rejects transcriptions that:
    - Are too short to be a real address (< 3 words)
    - Share zero words with the original (likely hallucinated from unrelated audio)
    - Are clearly conversational filler, not an address
    """
    import re
    
    refined_lower = refined.lower().strip()
    original_lower = original.lower().strip()
    
    # If the refined result is an eircode, it's always plausible — the whole point
    # of retranscription is to get a better reading of what the caller said.
    # An eircode is a specific, structured code that gpt-4o-transcribe wouldn't
    # hallucinate from random noise.
    if _looks_like_eircode(refined):
        print(f"[ADDR_RETRANSCRIBE] Validation: refined looks like eircode — accepting")
        return True
    
    # If the original is an eircode/short code and the refined is a street address,
    # the model likely hallucinated an address from the eircode audio. Reject it.
    # Only trigger for short originals (≤7 chars after stripping) that look like codes,
    # not concatenated words from a real address like "32 main st" → "32mainst".
    original_cleaned = re.sub(r'[-\s]', '', original_lower)
    original_word_count = len(original.strip().split())
    if (len(original_cleaned) <= 7 and original_word_count <= 2
            and re.match(r'^[a-z0-9]{2,7}$', original_cleaned)
            and len(refined_lower.split()) >= 3):
        print(f"[ADDR_RETRANSCRIBE] Validation: original looks like a code ('{original}') but refined is a street address — rejecting hallucination")
        return False
    
    # Too short — real addresses have at least a number + street + area
    if len(refined_lower.split()) < 3:
        # But if it's essentially the same as original (just punctuation/casing cleanup), allow it
        import re as _re
        norm_refined = _re.sub(r'[^a-z0-9\s]', '', refined_lower)
        norm_original = _re.sub(r'[^a-z0-9\s]', '', original_lower)
        if norm_refined.split() != norm_original.split():
            print(f"[ADDR_RETRANSCRIBE] Validation: too short ({len(refined_lower.split())} words)")
            return False
    
    # Check for conversational filler that got hallucinated into an address
    filler_phrases = [
        'perfect', 'thanks', 'thank you', 'great', 'okay', 'ok', 'yes',
        'no problem', 'that\'s it', 'that\'s correct', 'correct', 'grand',
        'lovely', 'brilliant', 'cheers', 'bye', 'goodbye'
    ]
    if refined_lower.rstrip('.,!? ') in filler_phrases:
        print(f"[ADDR_RETRANSCRIBE] Validation: looks like filler, not an address")
        return False
    
    # Check word overlap — a legitimate re-transcription of the same audio should
    # share at least some words with the original ASR result. If zero overlap,
    # the audio probably wasn't the caller saying their address at all.
    # Uses fuzzy matching because different ASR engines often mangle the same
    # word differently (e.g. "ocean" vs "oshin", "view" vs "niew").
    from difflib import SequenceMatcher
    
    stop_words = {'the', 'a', 'an', 'of', 'in', 'at', 'to', 'and', 'is', 'it', 'my', 'i', 'county', 'ireland', 'street', 'road', 'avenue', 'drive', 'lane', 'grove', 'park', 'close', 'way', 'place', 'crescent'}
    
    def meaningful_words(text):
        words = set(re.findall(r'\b\w+\b', text.lower()))
        return words - stop_words
    
    def has_fuzzy_overlap(words_a, words_b, threshold=0.6):
        """Check if any word in words_a is a fuzzy match for any word in words_b."""
        for wa in words_a:
            for wb in words_b:
                if SequenceMatcher(None, wa, wb).ratio() >= threshold:
                    return True
        return False
    
    refined_words = meaningful_words(refined)
    original_words = meaningful_words(original)
    
    if refined_words and original_words:
        # First try exact overlap (fast path)
        overlap = refined_words & original_words
        if not overlap and not has_fuzzy_overlap(refined_words, original_words):
            print(f"[ADDR_RETRANSCRIBE] Validation: zero word overlap even with fuzzy matching (refined={refined_words}, original={original_words})")
            return False
    
    return True


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

    # Sanity check: reject hallucinated/garbage transcriptions.
    # gpt-4o-transcribe can hallucinate plausible-sounding addresses when the audio
    # is just filler like "Perfect. Thanks." — validate before overwriting.
    if refined_address and refined_address != original_address:
        if original_address:
            if not _is_plausible_address(refined_address, original_address):
                print(f"[ADDR_RETRANSCRIBE] ⚠️ Refined address looks suspicious — keeping original")
                print(f"[ADDR_RETRANSCRIBE]   Refined:  '{refined_address}'")
                print(f"[ADDR_RETRANSCRIBE]   Original: '{original_address}'")
                refined_address = original_address
        else:
            # Original was empty (e.g. eircode-only booking where validated_address was None).
            # Extra caution: reject if it looks like filler or hallucinated content.
            if not _is_plausible_address_standalone(refined_address):
                print(f"[ADDR_RETRANSCRIBE] ⚠️ Refined address looks suspicious (no original to compare) — discarding")
                print(f"[ADDR_RETRANSCRIBE]   Refined:  '{refined_address}'")
                refined_address = original_address

    # Step 2: Update database
    if refined_address and (booking_id or client_id):
        try:
            from src.services.database import get_database
            db = get_database()

            # If the refined result looks like an eircode, update the eircode field
            # instead of the address field to avoid overwriting with a code
            is_eircode = _looks_like_eircode(refined_address)

            if booking_id:
                if is_eircode:
                    db.update_booking(booking_id, company_id=company_id, eircode=refined_address)
                    print(f"[ADDR_RETRANSCRIBE] ✅ Updated booking {booking_id} eircode")
                else:
                    db.update_booking(booking_id, company_id=company_id, address=refined_address)
                    print(f"[ADDR_RETRANSCRIBE] ✅ Updated booking {booking_id} address")

            if client_id:
                if is_eircode:
                    db.update_client(client_id, eircode=refined_address)
                    print(f"[ADDR_RETRANSCRIBE] ✅ Updated client {client_id} eircode")
                else:
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
