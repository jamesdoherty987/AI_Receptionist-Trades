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
    "one_moment": "One moment.",
    "let_me_check": "Let me check that for you.",
    "bear_with_me": "Bear with me one second.",
    "just_a_moment": "Just a moment.",
    "let_me_look": "Let me have a look.",
    "transferring": "Transferring you now.",
}

# R2 folder for filler audio
R2_FILLER_FOLDER = "audio/fillers"

# In-memory cache for instant playback (loaded at startup)
_audio_cache: dict[str, bytes] = {}
_cache_loaded = False
_loading_in_progress = False


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


def get_random_filler_id() -> str:
    """Get a random generic filler phrase ID (only from loaded cache)"""
    try:
        generic = ["one_moment", "let_me_check", "bear_with_me", "just_a_moment", "let_me_look"]
        available = [f for f in generic if f in _audio_cache]
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
    try:
        # Split into 20ms chunks (160 bytes for mulaw 8kHz)
        # Send all chunks as fast as possible - Twilio buffers them
        chunk_size = 160
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            payload = base64.b64encode(chunk).decode('utf-8')
            
            await websocket.send(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload},
            }))
    except Exception as e:
        # Log but don't raise - TTS fallback will handle it
        print(f"[AUDIO] Error sending pre-recorded audio: {type(e).__name__}: {e}")


def has_prerecorded_fillers() -> bool:
    """Check if any pre-recorded fillers are available"""
    try:
        return len(_audio_cache) > 0
    except Exception:
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
    
    async with websockets.connect(
        uri,
        extra_headers={"xi-api-key": api_key},
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
