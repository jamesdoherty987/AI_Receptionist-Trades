"""
Pre-recorded audio service for instant filler phrases
Eliminates TTS latency for common phrases like "One moment" or "Let me check that"

Audio files are stored in R2 and cached in memory at startup for instant playback.
Uses the same ElevenLabs voice as live TTS for seamless experience.

WHEN FILLERS ARE PLAYED:
- Availability checks: "what times are available", "when can I book"
- Booking confirmations: user says "yes" after AI confirms details
- Cancellation requests: "cancel my appointment"
- Reschedule requests: "reschedule", "change my appointment"
- Appointment lookups: "when is my appointment", "do I have an appointment"
- Customer lookups: "my name is John" (triggers database lookup)
- Transfer requests: "speak to a human", "transfer me"
- Any time the LLM decides to call a tool (backup detection)

PRODUCTION NOTES:
- Gracefully degrades to TTS if R2 not configured or files not found
- Never blocks or crashes - all errors are caught and logged
- Thread-safe loading with flags to prevent race conditions
- Works on Render.com and other cloud platforms
"""
import os
import asyncio
import base64
import json
import random
from typing import Optional

# Filler phrase definitions - must match what's generated
# These are the phrases that will be pre-recorded and played instantly
FILLER_PHRASES = {
    # Generic fillers - used for most tool calls
    "one_moment": "One moment.",
    "let_me_check": "Let me check that for you.",
    "bear_with_me": "Bear with me one second.",
    "just_a_moment": "Just a moment.",
    "let_me_look": "Let me have a look.",
    "grand_one_moment": "Grand, one moment.",  # Irish-style acknowledgment for name confirmation
    "sure_one_sec": "Sure, one second.",
    "okay_let_me_see": "Okay, let me see.",
    "right_one_moment": "Right, one moment.",
    "give_me_a_sec": "Give me a second.",
    "let_me_pull_that_up": "Let me pull that up.",
    # Name/spelling confirmation fillers
    "got_it_checking": "Got it, just checking.",
    "perfect_one_moment": "Perfect, one moment.",
    "grand_let_me_check": "Grand, let me check that.",
    # Number/eircode confirmation fillers  
    "thanks_checking": "Thanks, just checking.",
    "okay_checking": "Okay, checking that now.",
    # Name spelling correction filler
    "let_me_look_you_up": "Let me look you up.",
    # Time selection / booking fillers
    "grand_let_me_book": "Grand, let me book that.",
    # Short acknowledgment fillers (for quick confirmations and name introductions)
    "grand": "Grand.",
    "perfect": "Perfect.",
    "great": "Great.",
    "got_it": "Got it.",
    "okay": "Okay.",
    "right": "Right.",
    "sure": "Sure.",
    "no_problem": "No problem.",
    "absolutely": "Absolutely.",
    "of_course": "Of course.",
    # Acknowledgment + one moment (for name introductions and service descriptions)
    "got_it_one_moment": "Got it, one moment.",
    "okay_one_moment": "Okay, one moment.",
    "right_one_moment": "Right, one moment.",
    "sure_one_moment": "Sure, one moment.",
    "no_problem_one_moment": "No problem, one moment.",
    # Booking-specific fillers
    "let_me_book": "Let me book that for you, one moment.",
    "let_me_confirm": "Let me confirm that for you, one moment.",
    "booking_that_now": "Booking that now.",
    # Transfer fillers
    "transferring": "Transferring you now.",
    "connecting": "Connecting you now.",
    "let_me_connect": "Let me get someone for you.",
    # Greeting
    "greeting": "Hi, thank you for calling. How can I help you today?",  # Pre-recorded greeting for instant playback
    # Static direct responses (bypass ElevenLabs TTS for predictable phrases)
    "couldnt_find_name": "I couldn't find that name. Could you spell it for me?",
    "day_fully_booked": "That day is fully booked. Would you like to try a different day?",
    "not_open_that_day": "We're not open that day. What other day would work for you?",
    "couldnt_check_day": "I couldn't check that day. What day works for you?",
    "couldnt_check_availability": "I couldn't check availability. What day would you like to try?",
    "slot_taken": "That time slot just got taken. Would you like to try a different time?",
    "missing_details": "I'm missing some details. Could you confirm the time you'd like?",
    "couldnt_complete_booking": "I couldn't complete that booking. Could you try again?",
    "all_booked": "You're all booked! Is there anything else I can help with?",
    "nothing_available": "I don't have anything available then. Would you like to try different dates?",
    "couldnt_search": "I couldn't search that time period. What dates would you like to check?",
    "didnt_catch_date": "I didn't quite catch the date. Could you tell me the day and month, like March 27th?",
    "no_bookings_found": "I don't see any bookings on that day. Could you double-check the date?",
    "got_that_anything_else": "I've got that. What else can I help with?",
    "worker_no_availability": "The assigned worker has no availability in that period. Would you like to try different dates?",
    "couldnt_check_worker": "I couldn't check the worker's availability. What dates would you like to try?",
    "no_availability_soon": "I don't have any availability soon. Would you like me to check further out?",
}

# Context-specific filler groups
BOOKING_FILLERS = ["let_me_book", "let_me_confirm", "booking_that_now", "grand_let_me_book"]
GENERIC_FILLERS = ["one_moment", "let_me_check", "bear_with_me", "just_a_moment", "let_me_look", 
                   "sure_one_sec", "okay_let_me_see", "right_one_moment", "give_me_a_sec", "let_me_pull_that_up"]
NAME_CONFIRMATION_FILLERS = ["got_it_checking", "perfect_one_moment", "grand_let_me_check", "grand_one_moment", "let_me_look_you_up"]
NUMBER_CONFIRMATION_FILLERS = ["thanks_checking", "okay_checking", "one_moment", "let_me_check"]
SHORT_ACKNOWLEDGMENT_FILLERS = ["grand", "perfect", "great", "got_it", "okay", "right", "sure", "no_problem", "absolutely", "of_course"]
# Acknowledgment + one moment fillers (for name introductions and service descriptions)
ACKNOWLEDGMENT_ONE_MOMENT_FILLERS = ["got_it_one_moment", "okay_one_moment", "right_one_moment", "sure_one_moment", "no_problem_one_moment"]
TRANSFER_FILLERS = ["transferring", "connecting", "let_me_connect"]

# R2 folder for filler audio
R2_FILLER_FOLDER = "audio/fillers"

# In-memory cache for instant playback (loaded at startup)
_audio_cache: dict[str, bytes] = {}
_cache_loaded = False
_loading_in_progress = False

# Typing audio cache (loaded from R2 at startup alongside fillers)
_typing_audio: Optional[bytes] = None
TYPING_AUDIO_ID = "typing_loop"  # R2 key: audio/fillers/typing_loop.raw


def _get_r2_key(phrase_id: str) -> str:
    """Get R2 key for a filler phrase"""
    return f"{R2_FILLER_FOLDER}/{phrase_id}.raw"


def _get_r2_url(phrase_id: str) -> str:
    """Get full R2 URL for a filler phrase"""
    try:
        public_url = os.getenv('R2_PUBLIC_URL', '').rstrip('/')
        if public_url:
            return f"{public_url}/{_get_r2_key(phrase_id)}"
    except Exception:
        pass
    return ""


async def _download_from_r2(phrase_id: str) -> Optional[bytes]:
    """Download audio file from R2 - never raises, returns None on any error"""
    url = _get_r2_url(phrase_id)
    if not url:
        return None
    
    try:
        # Import httpx here to avoid import errors if not installed
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.content
            elif response.status_code == 404:
                print(f"[AUDIO] Filler {phrase_id} not found in R2 - run: python scripts/generate_filler_audio.py")
            else:
                print(f"[AUDIO] Failed to download {phrase_id} from R2: HTTP {response.status_code}")
    except ImportError:
        print("[AUDIO] httpx not installed - pre-recorded fillers disabled")
    except asyncio.TimeoutError:
        print(f"[AUDIO] Timeout downloading {phrase_id} from R2")
    except Exception as e:
        print(f"[AUDIO] Error downloading {phrase_id} from R2: {type(e).__name__}: {e}")
    
    return None


async def preload_fillers_async():
    """Pre-load all filler audio from R2 into memory (async version)"""
    global _audio_cache, _cache_loaded, _loading_in_progress
    
    # Prevent concurrent loading
    if _cache_loaded or _loading_in_progress:
        return
    
    _loading_in_progress = True
    
    try:
        public_url = os.getenv('R2_PUBLIC_URL')
        if not public_url:
            print("[AUDIO] R2_PUBLIC_URL not configured - pre-recorded fillers disabled (will use TTS)")
            return
        
        print(f"[AUDIO] Loading pre-recorded fillers from R2...")
        
        # Download all fillers in parallel for speed
        phrase_ids = list(FILLER_PHRASES.keys())
        tasks = [_download_from_r2(phrase_id) for phrase_id in phrase_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        loaded = 0
        for phrase_id, result in zip(phrase_ids, results):
            if isinstance(result, bytes) and len(result) > 0:
                _audio_cache[phrase_id] = result
                loaded += 1
                duration_ms = len(result) / 8  # 8 bytes per ms at 8kHz mulaw
                print(f"[AUDIO] ✓ Loaded {phrase_id}: {len(result)} bytes (~{duration_ms:.0f}ms)")
            elif isinstance(result, Exception):
                print(f"[AUDIO] ✗ Error loading {phrase_id}: {result}")
            # None results are already logged in _download_from_r2
        
        if loaded > 0:
            print(f"[AUDIO] ✅ Pre-loaded {loaded}/{len(FILLER_PHRASES)} filler phrases from R2")
        else:
            print(f"[AUDIO] ⚠️ No filler phrases loaded - will use TTS fallback")
            print(f"[AUDIO] To generate fillers, run: python scripts/generate_filler_audio.py")
        
        # Load typing audio from R2 (separate from filler phrases)
        global _typing_audio
        _typing_audio = await _load_typing_audio_async()
    
    except Exception as e:
        print(f"[AUDIO] Error in preload_fillers_async: {type(e).__name__}: {e}")
    
    finally:
        _cache_loaded = True
        _loading_in_progress = False


def preload_fillers():
    """
    Pre-load all filler audio from R2 into memory (sync wrapper)
    Safe to call at module import time - handles missing event loop gracefully
    NEVER raises exceptions - always fails gracefully
    """
    global _cache_loaded, _loading_in_progress
    
    # Already loaded or loading
    if _cache_loaded or _loading_in_progress:
        return
    
    # Check if R2 is configured before trying to load
    if not os.getenv('R2_PUBLIC_URL'):
        print("[AUDIO] R2_PUBLIC_URL not configured - pre-recorded fillers disabled (will use TTS)")
        _cache_loaded = True
        return
    
    try:
        # Check if we're inside a running event loop
        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context - schedule as task
            # This happens when called from within an async function
            asyncio.create_task(preload_fillers_async())
            print("[AUDIO] Scheduled filler preload (async)")
            return
        except RuntimeError:
            # No running loop - we're at module import time or sync context
            pass
        
        # Create new event loop and run synchronously
        # This is safe at module import time on Render
        asyncio.run(preload_fillers_async())
        
    except Exception as e:
        # NEVER let this crash the server
        print(f"[AUDIO] Error preloading fillers (non-fatal): {type(e).__name__}: {e}")
        _cache_loaded = True  # Mark as loaded to prevent retry loops
        _loading_in_progress = False


def get_random_filler_id(tool_name: str = None, context: str = None) -> str:
    """Get a random filler phrase ID based on context (only from loaded cache)
    
    Args:
        tool_name: Optional tool name to select context-appropriate filler
                   - book_appointment, book_job: Use booking-specific fillers
                   - transfer_to_human: Use transfer filler
                   - lookup_customer: Use name confirmation fillers
                   - Others: Use generic fillers
        context: Optional context hint for filler selection
                 - "name_confirmed": User confirmed name spelling
                 - "number_confirmed": User confirmed phone/eircode
                 - "name_introduction": User gave their name (acknowledgment + one moment)
                 - "service_description": User described their issue (acknowledgment + one moment)
    """
    try:
        # Select appropriate filler group based on context hint first
        if context == "name_confirmed":
            available = [f for f in NAME_CONFIRMATION_FILLERS if f in _audio_cache]
            if available:
                return random.choice(available)
        elif context == "number_confirmed":
            available = [f for f in NUMBER_CONFIRMATION_FILLERS if f in _audio_cache]
            if available:
                return random.choice(available)
        elif context in ["name_introduction", "service_description"]:
            # Use acknowledgment + one moment fillers for these contexts
            available = [f for f in ACKNOWLEDGMENT_ONE_MOMENT_FILLERS if f in _audio_cache]
            if available:
                return random.choice(available)
            # Fall back to generic fillers if acknowledgment ones not available
            available = [f for f in GENERIC_FILLERS if f in _audio_cache]
            if available:
                return random.choice(available)
        
        # Select based on tool name
        if tool_name in ["book_appointment", "book_job"]:
            # Booking-specific fillers
            available = [f for f in BOOKING_FILLERS if f in _audio_cache]
            if available:
                return random.choice(available)
        elif tool_name == "transfer_to_human":
            # Transfer filler
            available = [f for f in TRANSFER_FILLERS if f in _audio_cache]
            if available:
                return random.choice(available)
        elif tool_name == "lookup_customer":
            # Name confirmation fillers
            available = [f for f in NAME_CONFIRMATION_FILLERS if f in _audio_cache]
            if available:
                return random.choice(available)
        
        # Fall back to generic fillers
        available = [f for f in GENERIC_FILLERS if f in _audio_cache]
        if available:
            return random.choice(available)
    except Exception:
        pass
    return "one_moment"  # Safe fallback


def get_filler_audio(phrase_id: str) -> Optional[bytes]:
    """Get pre-recorded audio for a filler phrase (instant - from memory)"""
    try:
        return _audio_cache.get(phrase_id)
    except Exception:
        return None


def get_filler_id_from_message(message: str) -> Optional[str]:
    """Get the filler ID that matches a given message text
    
    Args:
        message: The filler message text (e.g., "Let me book that for you, one moment.")
    
    Returns:
        The phrase ID if found in cache, None otherwise
    """
    try:
        # Normalize the message for comparison
        normalized_msg = message.strip().lower()
        print(f"[FILLER_DEBUG] Looking for match: '{normalized_msg}'")
        
        for phrase_id, phrase_text in FILLER_PHRASES.items():
            phrase_normalized = phrase_text.strip().lower()
            if phrase_normalized == normalized_msg:
                # Only return if we have this audio cached
                if phrase_id in _audio_cache:
                    print(f"[FILLER_DEBUG] ✓ Found exact match: '{phrase_id}' -> '{phrase_text}'")
                    return phrase_id
                else:
                    print(f"[FILLER_DEBUG] ✗ Match found but not in cache: '{phrase_id}'")
        
        # Log near-matches for debugging
        for phrase_id, phrase_text in FILLER_PHRASES.items():
            phrase_normalized = phrase_text.strip().lower()
            if normalized_msg in phrase_normalized or phrase_normalized in normalized_msg:
                print(f"[FILLER_DEBUG] Near-match: '{phrase_id}' -> '{phrase_text}'")
        
        print(f"[FILLER_DEBUG] No exact match found for: '{normalized_msg}'")
        return None
    except Exception as e:
        print(f"[FILLER_DEBUG] Error in get_filler_id_from_message: {e}")
        return None


async def send_prerecorded_audio(websocket, stream_sid: str, audio_data: bytes):
    """
    Send pre-recorded mulaw audio directly to Twilio - INSTANT playback
    This bypasses TTS entirely for zero latency
    
    Args:
        websocket: Twilio websocket connection
        stream_sid: Twilio stream ID
        audio_data: Raw mulaw 8kHz audio bytes
    
    Never raises - errors are logged and ignored (TTS fallback will handle it)
    """
    import time
    send_start = time.time()
    try:
        # Split into 20ms chunks (160 bytes for mulaw 8kHz)
        # Send all chunks as fast as possible - Twilio buffers them
        chunk_size = 160
        chunk_count = 0
        
        # Calculate expected audio duration
        audio_duration_ms = len(audio_data) / 8  # 8 bytes per ms at 8kHz mulaw
        print(f"[AUDIO] 🔊 Sending {len(audio_data)} bytes ({audio_duration_ms:.0f}ms) of pre-recorded audio")
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            payload = base64.b64encode(chunk).decode('utf-8')
            
            await websocket.send(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload},
            }))
            chunk_count += 1
        
        send_duration = time.time() - send_start
        print(f"[AUDIO] ✅ Sent {chunk_count} chunks in {send_duration:.3f}s (audio will play for {audio_duration_ms:.0f}ms)")
        
    except Exception as e:
        # Log but don't raise - TTS fallback will handle it
        print(f"[AUDIO] ❌ Error sending pre-recorded audio: {type(e).__name__}: {e}")


def has_prerecorded_fillers() -> bool:
    """Check if any pre-recorded fillers are available"""
    try:
        count = len(_audio_cache)
        if count > 0:
            # Log available fillers for debugging
            available = list(_audio_cache.keys())[:5]  # First 5
            print(f"[FILLER_DEBUG] Cache has {count} fillers. Sample: {available}")
        return count > 0
    except Exception as e:
        print(f"[FILLER_DEBUG] Error checking cache: {e}")
        return False


# === Generation functions (for scripts/generate_filler_audio.py) ===

async def generate_filler_audio_elevenlabs(phrase_id: str, text: str) -> bytes:
    """
    Generate mulaw audio for a phrase using ElevenLabs
    Uses the SAME voice as live TTS (ELEVENLABS_VOICE_ID from .env)
    
    This is only called by the generation script, not at runtime.
    """
    import websockets
    from src.utils.config import config
    
    voice_id = config.ELEVENLABS_VOICE_ID
    api_key = config.ELEVENLABS_API_KEY
    
    if not voice_id or not api_key:
        raise ValueError("ELEVENLABS_VOICE_ID and ELEVENLABS_API_KEY must be set in .env")
    
    uri = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
        f"?model_id=eleven_turbo_v2_5"
        f"&output_format=ulaw_8000"
        f"&optimize_streaming_latency=4"
    )
    
    audio_chunks = []
    
    # websockets 12.0+ uses additional_headers (not extra_headers)
    async with websockets.connect(
        uri,
        additional_headers={"xi-api-key": api_key},
        open_timeout=15,
    ) as ws:
        # Initialize with same voice settings as live TTS
        await ws.send(json.dumps({
            "text": " ",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
        }))
        
        # Send the text
        await ws.send(json.dumps({
            "text": text,
            "try_trigger_generation": True
        }))
        
        # Signal end of text
        await ws.send(json.dumps({"text": ""}))
        
        # Collect audio
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                
                if data.get("audio"):
                    # ElevenLabs returns base64-encoded audio
                    audio_bytes = base64.b64decode(data["audio"])
                    audio_chunks.append(audio_bytes)
                
                if data.get("isFinal"):
                    break
                    
            except asyncio.TimeoutError:
                print(f"[AUDIO] ⚠️ TIMEOUT: ElevenLabs filler generation timed out after 5s")
                break
    
    if not audio_chunks:
        raise ValueError(f"No audio generated for phrase: {text}")
    
    return b"".join(audio_chunks)


async def upload_filler_to_r2(phrase_id: str, audio_data: bytes) -> str:
    """Upload filler audio to R2 storage"""
    from src.services.storage_r2 import get_r2_storage
    import io
    
    r2 = get_r2_storage()
    if not r2:
        raise ValueError("R2 storage not configured - set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME")
    
    file_data = io.BytesIO(audio_data)
    
    url = r2.upload_file(
        file_data=file_data,
        filename=f"{phrase_id}.raw",
        folder=R2_FILLER_FOLDER,
        content_type="audio/basic"  # mulaw audio MIME type
    )
    
    return url


# === Background typing audio ===
# Played after filler phrase finishes, loops until TTS response is ready.
# Real typing sound effect stored in R2 alongside other filler audio.
# The ~7.7s clip loops seamlessly for longer waits.


async def _load_typing_audio_async() -> Optional[bytes]:
    """Download typing audio from R2 (called during filler preload)."""
    audio = await _download_from_r2(TYPING_AUDIO_ID)
    if audio and len(audio) > 0:
        duration_ms = len(audio) / 8  # 8 bytes per ms at 8kHz mulaw
        print(f"[TYPING] ✅ Loaded typing audio from R2: {len(audio)} bytes ({duration_ms:.0f}ms)")
        return audio
    print(f"[TYPING] ⚠️ Typing audio not found in R2 — background typing disabled")
    return None


def get_typing_audio() -> Optional[bytes]:
    """Get the typing loop audio (mulaw 8kHz). Returns None if not loaded."""
    return _typing_audio


async def send_typing_audio_loop(websocket, stream_sid: str, stop_event: asyncio.Event,
                                  max_duration_s: float = 30.0):
    """
    Send typing audio to the call in a loop until stop_event is set.
    
    This runs as an async task. When the TTS response is ready, the caller
    sets stop_event which causes this to stop sending new chunks. The caller
    then sends a 'clear' event to flush any buffered typing audio from Telnyx
    before starting TTS.
    
    Args:
        websocket: Telnyx websocket connection
        stream_sid: Telnyx stream ID
        stop_event: asyncio.Event — set this to stop the typing
        max_duration_s: Safety timeout to prevent infinite typing
    """
    import time
    start = time.time()
    typing_audio = get_typing_audio()
    if not typing_audio:
        print("[TYPING] ⚠️ No typing audio available — skipping")
        return
    
    chunk_size = 160  # 20ms at 8kHz mulaw
    total_chunks = len(typing_audio) // chunk_size
    chunk_idx = 0
    chunks_sent = 0
    
    # Pace the sending: Telnyx buffers everything we send, so if we blast
    # 15s of audio instantly, the clear event has to flush a huge buffer.
    # Instead, send in real-time-ish pace (batches of ~100ms every 100ms)
    # so the buffer stays small and clear is near-instant.
    BATCH_CHUNKS = 5  # 5 chunks = 100ms of audio
    BATCH_INTERVAL = 0.1  # Send every 100ms
    
    print(f"[TYPING] ⌨️ Starting typing audio loop (max {max_duration_s}s)")
    
    try:
        while not stop_event.is_set():
            # Safety timeout
            elapsed = time.time() - start
            if elapsed > max_duration_s:
                print(f"[TYPING] ⚠️ Max duration reached ({max_duration_s}s) — stopping")
                break
            
            # Send a batch of chunks
            for _ in range(BATCH_CHUNKS):
                if stop_event.is_set():
                    break
                
                offset = (chunk_idx % total_chunks) * chunk_size
                chunk = typing_audio[offset:offset + chunk_size]
                if len(chunk) < chunk_size:
                    # Wrap around to start of typing audio
                    chunk_idx = 0
                    offset = 0
                    chunk = typing_audio[0:chunk_size]
                
                payload = base64.b64encode(chunk).decode('utf-8')
                await websocket.send(json.dumps({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                }))
                chunk_idx += 1
                chunks_sent += 1
            
            # Wait before sending next batch — yields control to event loop
            # so stop_event can be checked promptly
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=BATCH_INTERVAL)
                # stop_event was set during our wait — exit
                break
            except asyncio.TimeoutError:
                # Normal — keep sending
                pass
    
    except Exception as e:
        if "ConnectionClosed" in type(e).__name__:
            print(f"[TYPING] ⚠️ WebSocket closed during typing audio")
        else:
            print(f"[TYPING] ❌ Error in typing loop: {type(e).__name__}: {e}")
    
    duration = time.time() - start
    audio_sent_ms = chunks_sent * 20  # Each chunk is 20ms
    print(f"[TYPING] ⌨️ Typing stopped after {duration:.2f}s ({chunks_sent} chunks, ~{audio_sent_ms}ms audio sent)")
