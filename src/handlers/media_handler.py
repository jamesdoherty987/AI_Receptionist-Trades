"""
Media Stream WebSocket Handler (Twilio + Telnyx compatible)
Manages real-time voice conversations with ASR, LLM, and TTS

SIMPLIFIED ARCHITECTURE:
1. User speaks → Deepgram speech_final
2. LLM stream starts → yields SPLIT_TTS marker (if tool needed) OR content tokens
3. If SPLIT_TTS: Play filler audio, then continue streaming rest of generator to TTS
4. If no SPLIT_TTS: Stream directly to TTS

NO BUFFERING - tokens flow directly from LLM to TTS for minimum latency.
"""
import asyncio
import json
import base64
import os
import re
import time as time_module
import websockets
from collections import deque

from src.utils.audio_utils import ulaw_energy, mulaw_to_wav, trim_silence_mulaw
from src.utils.config import config
from src.services.asr_deepgram import DeepgramASR
from src.services.llm_stream import stream_llm
from src.services.call_state import create_call_state

# Import pre-recorded audio service with safe fallback
try:
    from src.services.prerecorded_audio import (
        get_filler_audio, get_random_filler_id, send_prerecorded_audio, 
        has_prerecorded_fillers, preload_fillers, get_filler_id_from_message,
    )
    preload_fillers()
    print(f"[AUDIO] Pre-recorded fillers available: {has_prerecorded_fillers()}")
except Exception as e:
    print(f"[AUDIO] Warning: Could not import prerecorded_audio: {e}")
    def has_prerecorded_fillers(): return False
    def get_random_filler_id(tool_name=None): return "one_moment"
    def get_filler_audio(phrase_id): return None
    async def send_prerecorded_audio(ws, sid, data): pass
    def preload_fillers(): pass
    def get_filler_id_from_message(message): return None

# Import TTS
TTS_PROVIDER = config.TTS_PROVIDER if hasattr(config, 'TTS_PROVIDER') else 'deepgram'
if TTS_PROVIDER == 'elevenlabs':
    from src.services.tts_elevenlabs import stream_tts
else:
    from src.services.tts_deepgram import stream_tts


def norm_text(s: str) -> str:
    """Normalize text for comparison"""
    return " ".join((s or "").lower().split())


def content_fingerprint(s: str) -> str:
    """Create content fingerprint for duplicate detection"""
    return re.sub(r'[^a-z0-9]', '', (s or "").lower())


# --- Address audio capture constants ---
AUDIO_BUFFER_SECONDS = 17
MULAW_SAMPLE_RATE = 8000
MULAW_BYTES_PER_PACKET = 160  # 20ms packets
MAX_BUFFER_PACKETS = (AUDIO_BUFFER_SECONDS * MULAW_SAMPLE_RATE) // MULAW_BYTES_PER_PACKET  # ~500

ADDRESS_ASK_KEYWORDS = ['address', 'eircode', 'eir code', 'location', 'where', 'job site', 'job location', 'work location']

# Phrases that indicate the AI is confirming/repeating an address, NOT asking for one.
# These prevent Phase 1 from re-triggering when the AI says things like
# "Just confirming your address: 32 Silver Grove, correct?"
ADDRESS_CONFIRM_PATTERNS = ['confirm', 'correct?', 'right?', 'is it', 'is that', 'so the address is',
                            'booked in for', 'booked for', 'job at', 'job for',
                            'i have your address', 'i have the address', 'your address is',
                            'your address as', 'the address as', 'address on file',
                            'address we have', 'same address', 'still the same address',
                            'same address as before', 'address as before', 'address still',
                            'email address']

# Keywords that indicate the AI is asking for the caller's email address
EMAIL_ASK_KEYWORDS = ['email', 'e-mail', 'email address', 'e-mail address']

# Phrases that indicate the AI is reading back/confirming an email, NOT asking for one
EMAIL_CONFIRM_PATTERNS = ['your email is', 'your email as', 'email on file',
                          'same email', 'still the same email', 'email we have']


def ai_asked_for_address(text: str) -> bool:
    """Check if the AI's response is asking the caller for their address/eircode.
    
    Returns False if the AI is merely confirming/repeating an address it already has,
    to prevent Phase 1 from re-triggering on confirmation questions like
    'Just confirming your address: 32 Silver Grove, correct?'
    """
    lower = text.lower()
    if not any(kw in lower for kw in ADDRESS_ASK_KEYWORDS):
        return False
    # If the AI is confirming/repeating back an address, don't trigger capture
    if any(cp in lower for cp in ADDRESS_CONFIRM_PATTERNS):
        return False
    return True


def ai_asked_for_email(text: str) -> bool:
    """Check if the AI's response is asking the caller for their email address.
    
    Returns False if the AI is merely confirming/repeating an email it already has.
    """
    lower = text.lower()
    if not any(kw in lower for kw in EMAIL_ASK_KEYWORDS):
        return False
    if any(cp in lower for cp in EMAIL_CONFIRM_PATTERNS):
        return False
    return True


async def media_handler(ws):
    """Handle media stream WebSocket connection (Twilio or Telnyx)"""
    call_start_time = time_module.time()
    print(f"\n{'='*70}")
    print(f"📞 [CALL_START] New call at {call_start_time:.3f}")
    print(f"{'='*70}")
    
    # Per-call state
    call_state = create_call_state()
    
    # Rolling audio buffer for address capture (~10 seconds of caller audio)
    audio_buffer = deque(maxlen=MAX_BUFFER_PACKETS)
    
    # Full call recording — collects ALL caller audio for the entire call
    full_call_audio = []
    
    # Connect to Deepgram ASR
    asr = DeepgramASR()
    try:
        await asr.connect()
        print(f"✅ Deepgram connected in {time_module.time() - call_start_time:.3f}s")
    except Exception as e:
        print(f"❌ Deepgram connect failed: {e}")
        return

    # State variables
    conversation = []
    conversation_log = []
    stream_sid = None
    call_sid = None
    caller_phone = None
    company_id = None
    caller_is_returning = False
    caller_customer_name = None
    caller_customer_info = None
    
    # Outbound call state (set in "start" event if this is an outbound call)
    is_outbound = False
    outbound_call_type = ""
    outbound_call_log_id = ""
    outbound_caller_name = ""
    outbound_lost_reason = ""
    outbound_ai_summary = ""
    
    # TTS state
    speaking = False
    interrupt = False
    respond_task = None
    tts_started_at = 0.0
    tts_ended_at = 0.0
    last_tts_audio_done = 0.0  # Monotonic time when TTS audio actually finished sending
    
    # LLM processing state
    llm_processing = False
    llm_started_at = 0.0
    
    # Background ambient audio
    bg_audio_stop = asyncio.Event()
    
    # Tracking
    last_committed = ""
    last_committed_at = 0.0  # When last_committed was set (monotonic time)
    last_tts_success = True  # Whether the last TTS response actually delivered audio
    DUPLICATE_EXPIRY = 10.0  # Allow repeats after this many seconds of silence
    response_times = []
    
    # Config
    INTERRUPT_ENERGY = config.INTERRUPT_ENERGY
    NO_BARGEIN_WINDOW = config.NO_BARGEIN_WINDOW
    BARGEIN_HOLD = config.BARGEIN_HOLD
    POST_TTS_IGNORE = config.POST_TTS_IGNORE
    MIN_WORDS = config.MIN_WORDS
    LLM_PROCESSING_TIMEOUT = config.LLM_PROCESSING_TIMEOUT
    
    FILLER_PHRASES = {"hello", "hi", "hey", "are you there", "you there", "hello?", "um", "uh"}
    bargein_since = 0.0

    async def clear_audio_buffer():
        """Clear the provider's audio playback buffer (works for both Twilio and Telnyx)"""
        if stream_sid:
            try:
                await ws.send(json.dumps({"event": "clear", "streamSid": stream_sid}))
            except Exception:
                pass

    async def start_tts(text_stream, label="tts"):
        """
        Stream LLM response to TTS.
        
        PARALLEL FLOW for SPLIT_TTS:
        1. Get first token - if SPLIT_TTS marker, start filler AND LLM work in parallel
        2. Filler audio plays while LLM does OpenAI call + tool execution
        3. When LLM yields content tokens, stream them to TTS (may overlap with filler end)
        
        Key insight: Don't wait for filler to finish before starting LLM work!
        """
        nonlocal speaking, interrupt, respond_task, tts_started_at, tts_ended_at, llm_processing, last_tts_audio_done, last_tts_success

        async def run():
            nonlocal speaking, tts_started_at, tts_ended_at, llm_processing, conversation_log, response_times, last_tts_audio_done, last_tts_success
            run._prerecorded_playing = False  # Track if prerecorded audio is still playing
            speaking = True
            interrupt = False
            tts_started_at = asyncio.get_event_loop().time()
            run_start = time_module.time()
            
            full_text = ""
            transfer_number = None
            
            print(f"\n🗣️ [TTS] Starting response: {label}")

            try:
                # Get first token to check for SPLIT_TTS marker
                first_token_wait_start = time_module.time()
                first_token = None
                async for token in text_stream:
                    # Skip timing markers
                    if token.startswith("<<<TIMING:"):
                        continue
                    first_token = token
                    break
                
                first_token_wait = time_module.time() - first_token_wait_start
                print(f"[PIPELINE] ⏱️ First token received after {first_token_wait:.3f}s")
                
                if not first_token:
                    print(f"   ⚠️ No tokens from LLM")
                    return
                
                print(f"   📍 First token: '{first_token[:50]}...'")
                
                # Check if this is a SPLIT_TTS marker (filler needed)
                if first_token.startswith("<<<SPLIT_TTS:"):
                    filler_msg = first_token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                    print(f"   🔀 SPLIT_TTS detected: '{filler_msg}'")
                    print(f"[PIPELINE] ⏱️ SPLIT_TTS - starting parallel filler + LLM")
                    full_text += filler_msg + " "
                    
                    # Create a queue to buffer tokens from LLM while filler plays
                    token_queue = asyncio.Queue()
                    llm_done = asyncio.Event()
                    
                    async def consume_llm():
                        """Consume LLM tokens into queue (runs in parallel with filler)"""
                        nonlocal transfer_number
                        consume_start = time_module.time()
                        token_count = 0
                        try:
                            async for token in text_stream:
                                # Safety timeout - don't consume forever
                                if time_module.time() - consume_start > 20.0:
                                    print(f"   ⚠️ consume_llm timeout after 20s, {token_count} tokens")
                                    break
                                if token.startswith("<<<TRANSFER:"):
                                    transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                                    continue
                                # Handle prerecorded audio: resolve to text so TTS can speak it
                                # (prerecorded optimization only works in the direct stream path)
                                if token.startswith("<<<PRERECORDED:"):
                                    phrase_id = token.replace("<<<PRERECORDED:", "").replace(">>>", "").strip()
                                    # Try to play prerecorded audio directly
                                    prerecorded_data = get_filler_audio(phrase_id) if has_prerecorded_fillers() else None
                                    if prerecorded_data:
                                        # Signal the queued_stream to play prerecorded audio instead of TTS
                                        await token_queue.put(f"<<<PLAY_PRERECORDED:{phrase_id}>>>")
                                        token_count += 1
                                    else:
                                        # Fallback: resolve to text for TTS
                                        try:
                                            from src.services.prerecorded_audio import FILLER_PHRASES
                                            resolved_text = FILLER_PHRASES.get(phrase_id, "")
                                        except Exception:
                                            resolved_text = ""
                                        if resolved_text:
                                            token_count += 1
                                            await token_queue.put(resolved_text)
                                    continue
                                if token.startswith("<<<"):
                                    continue
                                token_count += 1
                                await token_queue.put(token)
                            print(f"   📥 consume_llm done: {token_count} tokens in {time_module.time() - consume_start:.2f}s")
                        except Exception as e:
                            print(f"   ❌ consume_llm error: {e}")
                        finally:
                            llm_done.set()
                    
                    async def play_filler():
                        """Play filler audio"""
                        filler_start = time_module.time()
                        if has_prerecorded_fillers():
                            filler_id = get_filler_id_from_message(filler_msg) or get_random_filler_id()
                            filler_audio = get_filler_audio(filler_id)
                            if filler_audio:
                                print(f"   🔊 Playing filler: {filler_id}")
                                await send_prerecorded_audio(ws, stream_sid, filler_audio)
                                print(f"[PIPELINE] ⏱️ Filler audio sent in {time_module.time() - filler_start:.3f}s")
                                return True
                        # TTS fallback
                        print(f"   📢 TTS filler: '{filler_msg}'")
                        async def filler_tokens():
                            yield filler_msg
                        await stream_tts(filler_tokens(), ws, stream_sid, lambda: interrupt)
                        print(f"[PIPELINE] ⏱️ TTS filler done in {time_module.time() - filler_start:.3f}s")
                        return True
                    
                    # START BOTH IN PARALLEL
                    # LLM work (OpenAI call, tool execution) happens while filler plays
                    parallel_start = time_module.time()
                    llm_task = asyncio.create_task(consume_llm())
                    filler_task = asyncio.create_task(play_filler())
                    
                    # Wait for filler to finish (LLM continues in background)
                    await filler_task
                    
                    # Now stream tokens from queue to TTS
                    # CRITICAL: Add overall timeout to prevent infinite hang
                    MAX_WAIT_SECONDS = 30.0  # Max time to wait for LLM response (tools can take 10-15s)
                    queue_start_time = time_module.time()
                    
                    async def queued_stream():
                        nonlocal full_text
                        stream_start_time = time_module.time()
                        MAX_STREAM_WAIT = 35.0  # Absolute max time for entire stream
                        token_count_qs = 0
                        first_token_time_qs = None
                        last_token_time_qs = None
                        wait_start = None
                        while True:
                            # SAFETY: Overall timeout check
                            elapsed = time_module.time() - queue_start_time
                            if elapsed > MAX_WAIT_SECONDS:
                                print(f"   ⚠️ Queue timeout after {elapsed:.1f}s - breaking out")
                                break
                            
                            # SAFETY: Absolute stream timeout
                            total_elapsed = time_module.time() - stream_start_time
                            if total_elapsed > MAX_STREAM_WAIT:
                                print(f"   ⚠️ Absolute stream timeout after {total_elapsed:.1f}s")
                                break
                            
                            # Check if LLM is done and queue is empty
                            if llm_done.is_set() and token_queue.empty():
                                break
                            
                            # SAFETY: If LLM task died unexpectedly, don't wait forever
                            if not llm_task.done() and elapsed > 10.0:
                                # Check if task is actually making progress
                                pass  # Task still running, continue waiting
                            elif llm_task.done() and token_queue.empty():
                                # Task finished and queue drained
                                break
                            
                            try:
                                # Wait for token with timeout
                                if wait_start is None:
                                    wait_start = time_module.time()
                                token = await asyncio.wait_for(token_queue.get(), timeout=0.5)
                                if first_token_time_qs is None:
                                    first_token_time_qs = time_module.time()
                                    wait_duration = first_token_time_qs - (wait_start or first_token_time_qs)
                                    print(f"   📦 [QUEUE] First token after {wait_duration:.3f}s wait (since filler done)")
                                last_token_time_qs = time_module.time()
                                token_count_qs += 1
                                wait_start = None
                                full_text += token
                                yield token
                            except asyncio.TimeoutError:
                                # No token yet, check if LLM is done
                                if llm_done.is_set() and token_queue.empty():
                                    break
                                # Log if waiting too long (only once at 6s)
                                if elapsed > 6.0 and int(elapsed * 10) % 100 == 0:
                                    print(f"   ⏳ Still waiting for LLM tokens... ({elapsed:.0f}s)")
                                continue
                    
                    tts_stream_start = time_module.time()
                    
                    # Check if the response is a prerecorded audio (skip TTS entirely)
                    _prerecorded_played = False
                    # Wait briefly for the first token if queue is empty but LLM is still working
                    if token_queue.empty() and not llm_done.is_set():
                        try:
                            await asyncio.wait_for(llm_done.wait(), timeout=2.0)
                        except asyncio.TimeoutError:
                            pass
                    if not token_queue.empty():
                        try:
                            peek_token = token_queue.get_nowait()
                            if isinstance(peek_token, str) and peek_token.startswith("<<<PLAY_PRERECORDED:"):
                                phrase_id = peek_token.replace("<<<PLAY_PRERECORDED:", "").replace(">>>", "").strip()
                                prerecorded_data = get_filler_audio(phrase_id)
                                if prerecorded_data:
                                    print(f"   🔊 [PARALLEL] Playing prerecorded: {phrase_id}")
                                    await send_prerecorded_audio(ws, stream_sid, prerecorded_data)
                                    playback_seconds = len(prerecorded_data) / 8000.0
                                    tts_ended_at = asyncio.get_event_loop().time() + playback_seconds
                                    last_tts_audio_done = tts_ended_at
                                    last_tts_success = True
                                    run._prerecorded_playing = True
                                    async def _clear_after_prerecorded(delay):
                                        nonlocal speaking
                                        await asyncio.sleep(delay)
                                        asr.clear()
                                        speaking = False
                                        run._prerecorded_playing = False
                                    asyncio.create_task(_clear_after_prerecorded(playback_seconds))
                                    try:
                                        from src.services.prerecorded_audio import FILLER_PHRASES
                                        full_text += FILLER_PHRASES.get(phrase_id, phrase_id)
                                    except Exception:
                                        full_text += phrase_id
                                    _prerecorded_played = True
                            else:
                                # Not a prerecorded token — put it back
                                await token_queue.put(peek_token)
                        except asyncio.QueueEmpty:
                            pass
                    
                    if not _prerecorded_played:
                        _queued_audio_done_fired = False
                        def _on_queued_audio_done():
                            nonlocal last_tts_audio_done, _queued_audio_done_fired, speaking, tts_ended_at, last_tts_success
                            last_tts_audio_done = asyncio.get_event_loop().time()
                            _queued_audio_done_fired = True
                            last_tts_success = True
                            # Clear stale ASR state NOW — the audio just finished sending.
                            asr.clear()
                            # CRITICAL: Mark speaking as done NOW, not when run() returns.
                            # run() takes 4-5s after audio finishes (websocket close, etc).
                            # If we wait, the caller's response gets stuck in barge-in mode
                            # and the fallback check never runs — causing a freeze.
                            speaking = False
                            tts_ended_at = last_tts_audio_done
                            print(f"[AUDIO_DONE] 🧹 ASR cleared + speaking=False at audio finish")
                        tts_pre_call = time_module.time()
                        print(f"   📡 [QUEUE→TTS] Starting TTS stream at {tts_pre_call - parallel_start:.3f}s into parallel flow")
                        await stream_tts(queued_stream(), ws, stream_sid, lambda: interrupt, on_audio_done=_on_queued_audio_done)
                        tts_post_call = time_module.time()
                        print(f"   📡 [QUEUE→TTS] stream_tts returned after {tts_post_call - tts_pre_call:.3f}s")
                        if not _queued_audio_done_fired:
                            last_tts_audio_done = asyncio.get_event_loop().time()
                            asr.clear()  # Fallback clear if callback didn't fire
                            speaking = False
                            tts_ended_at = last_tts_audio_done
                            last_tts_success = False  # TTS didn't deliver audio — allow caller to repeat
                            print(f"[AUDIO_DONE] 🧹 ASR cleared + speaking=False (fallback — callback didn't fire)")
                    tts_stream_time = time_module.time() - tts_stream_start
                    print(f"[PIPELINE] ⏱️ TTS streaming took {tts_stream_time:.3f}s")
                    
                    # Make sure LLM task is done (with timeout to prevent hang)
                    llm_wait_start = time_module.time()
                    try:
                        await asyncio.wait_for(llm_task, timeout=5.0)
                    except asyncio.TimeoutError:
                        print(f"   ⚠️ [LLM] TIMEOUT: LLM task didn't finish after 5s, cancelling...")
                        llm_task.cancel()
                        try:
                            await llm_task
                        except asyncio.CancelledError:
                            pass
                    llm_wait_time = time_module.time() - llm_wait_start
                    if llm_wait_time > 0.1:
                        print(f"   ⏳ [LLM] Waited {llm_wait_time:.3f}s for LLM task to finish after TTS")
                    
                    total_parallel_time = time_module.time() - parallel_start
                    print(f"[PIPELINE] ⏱️ Total parallel flow: {total_parallel_time:.3f}s")
                    print(f"   ✅ Response complete")
                
                else:
                    # No SPLIT_TTS - stream everything directly to TTS
                    print(f"   📢 Direct streaming to TTS")
                    direct_start = time_module.time()
                    
                    # Check if first token is a prerecorded direct response
                    if first_token.startswith("<<<PRERECORDED:"):
                        phrase_id = first_token.replace("<<<PRERECORDED:", "").replace(">>>", "").strip()
                        print(f"   🔊 Playing prerecorded direct response: {phrase_id}")
                        prerecorded_audio = get_filler_audio(phrase_id)
                        if prerecorded_audio:
                            # Drain remaining tokens (transfer markers etc) without TTS
                            async for token in text_stream:
                                if token.startswith("<<<TRANSFER:"):
                                    transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                            # Play prerecorded audio directly
                            speaking = True
                            tts_started_at = time_module.time()
                            await send_prerecorded_audio(ws, stream_sid, prerecorded_audio)
                            # Schedule speaking=False after playback (non-blocking)
                            playback_seconds = len(prerecorded_audio) / 8000.0
                            tts_ended_at = asyncio.get_event_loop().time() + playback_seconds
                            last_tts_audio_done = tts_ended_at
                            last_tts_success = True
                            run._prerecorded_playing = True
                            async def _clear_after_direct_prerecorded(delay):
                                nonlocal speaking
                                await asyncio.sleep(delay)
                                asr.clear()
                                speaking = False
                                run._prerecorded_playing = False
                            asyncio.create_task(_clear_after_direct_prerecorded(playback_seconds))
                            # Get the text for full_text tracking
                            from src.services.prerecorded_audio import FILLER_PHRASES
                            full_text = FILLER_PHRASES.get(phrase_id, phrase_id)
                            print(f"   🔊 Prerecorded direct response done: '{full_text}'")
                        else:
                            # Prerecorded audio not in cache — fall back to TTS
                            print(f"   ⚠️ Prerecorded {phrase_id} not in cache — falling back to TTS")
                            from src.services.prerecorded_audio import FILLER_PHRASES
                            fallback_text = FILLER_PHRASES.get(phrase_id, "")
                            if fallback_text:
                                async def fallback_stream():
                                    yield fallback_text
                                speaking = True
                                tts_started_at = time_module.time()
                                await stream_tts(fallback_stream(), ws, stream_sid, lambda: interrupt)
                                last_tts_audio_done = asyncio.get_event_loop().time()
                                asr.clear()
                                speaking = False
                                tts_ended_at = last_tts_audio_done
                                full_text = fallback_text
                    else:
                        # Normal direct stream — send through TTS
                        direct_start = time_module.time()
                        print(f"   📡 [DIRECT] Starting direct TTS at {direct_start - run_start:.3f}s into response")
                    
                        async def direct_stream():
                            nonlocal transfer_number, full_text
                            # Yield the first token we already got
                            if not first_token.startswith("<<<"):
                                full_text += first_token
                                yield first_token
                            
                            # Continue with rest of stream
                            async for token in text_stream:
                                if token.startswith("<<<TRANSFER:"):
                                    transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                                    continue
                                if token.startswith("<<<SPLIT_TTS:"):
                                    # SPLIT_TTS appeared mid-stream — a tool call is happening.
                                    # We're already in direct mode so we can't switch to parallel.
                                    # The filler text is lost, but the tool result tokens will
                                    # follow shortly. Log this so we can detect pre-check misses.
                                    filler_text = token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                                    print(f"   ⚠️ [DIRECT] SPLIT_TTS mid-stream (pre-check missed): '{filler_text}'")
                                    print(f"   ⚠️ [DIRECT] Tool is executing — tokens will resume after tool completes")
                                    continue
                                if token.startswith("<<<"):
                                    continue
                                full_text += token
                                yield token
                        
                        tts_call_start = time_module.time()
                        _direct_audio_done_fired = False
                        def _on_direct_audio_done():
                            nonlocal last_tts_audio_done, _direct_audio_done_fired, speaking, tts_ended_at, last_tts_success
                            last_tts_audio_done = asyncio.get_event_loop().time()
                            _direct_audio_done_fired = True
                            last_tts_success = True
                            asr.clear()
                            speaking = False
                            tts_ended_at = last_tts_audio_done
                            print(f"[AUDIO_DONE] 🧹 ASR cleared + speaking=False at audio finish")
                        await stream_tts(direct_stream(), ws, stream_sid, lambda: interrupt, on_audio_done=_on_direct_audio_done)
                        if not _direct_audio_done_fired:
                            last_tts_audio_done = asyncio.get_event_loop().time()
                            asr.clear()
                            speaking = False
                            tts_ended_at = last_tts_audio_done
                            last_tts_success = False
                            print(f"[AUDIO_DONE] 🧹 ASR cleared + speaking=False (fallback — callback didn't fire)")
                        tts_call_end = time_module.time()
                        direct_time = tts_call_end - direct_start
                        tts_only_time = tts_call_end - tts_call_start
                        print(f"[PIPELINE] ⏱️ Direct TTS flow took {direct_time:.3f}s (TTS call: {tts_only_time:.3f}s)")
                
                # Log response timing (only warn on slow responses)
                total_time = time_module.time() - run_start
                response_times.append(total_time)
                print(f"   ⏱️ RESPONSE TIME: {total_time:.1f}s (speaking={speaking}, interrupt={interrupt})")
                if total_time > 5.0:
                    print(f"   ⚠️ SLOW RESPONSE: {total_time:.1f}s")
                
                if full_text.strip():
                    conversation_log.append({
                        "role": "assistant",
                        "content": full_text.strip(),
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    print(f"\n{'='*60}")
                    print(f"🤖 RECEPTIONIST: {full_text.strip()}")
                    print(f"{'='*60}\n")
                    
                    # Two-phase address audio: if AI just asked for address/eircode, flag it.
                    # We allow re-setting even if already captured — this handles the case
                    # where AI asked for eircode, caller didn't know, AI then asks for
                    # street address. The second capture overwrites the first (useless) one.
                    #
                    # BUT: if the AI is just confirming/repeating an address back
                    # (e.g., "Just confirming your address: 32 Silver Grove, correct?")
                    # we do NOT re-trigger, because the caller's response will be
                    # "Yes correct" — not the actual address.
                    if ai_asked_for_address(full_text):
                        call_state.awaiting_address_audio = True
                        call_state._addr_audio_collecting = False  # Reset — new ask cycle
                        call_state._addr_audio_ever_asked = True  # Persistent — survives declines
                        call_state._addr_audio_phase1_time = time_module.time()
                        print(f"🎙️ [ADDR_AUDIO] Phase 1: AI asked for address — will capture caller's next response")
                        print(f"🎙️ [ADDR_AUDIO] Phase 1: speaking={speaking}, buffer_len={len(audio_buffer)}")
                    else:
                        # Log when address keywords are present but it's a confirmation
                        full_lower = full_text.lower()
                        if any(kw in full_lower for kw in ADDRESS_ASK_KEYWORDS):
                            print(f"🎙️ [ADDR_AUDIO] Phase 1 SKIPPED: AI mentioned address but is confirming, not asking")
                    
                    # Email audio capture: same mechanism as address audio
                    if ai_asked_for_email(full_text):
                        call_state.awaiting_email_audio = True
                        call_state._email_audio_collecting = False
                        call_state._email_audio_ever_asked = True
                        call_state._email_audio_phase1_time = time_module.time()
                        print(f"📧 [EMAIL_AUDIO] Phase 1: AI asked for email — will capture caller's next response")
                    else:
                        full_lower = full_text.lower()
                        if any(kw in full_lower for kw in EMAIL_ASK_KEYWORDS):
                            print(f"📧 [EMAIL_AUDIO] Phase 1 SKIPPED: AI mentioned email but is confirming, not asking")
                
                # Handle transfer if requested
                if transfer_number:
                    print(f"📞 TRANSFER TO: {transfer_number}")
                    try:
                        import os
                        import httpx
                        
                        # Try Telnyx first, then Twilio
                        telnyx_api_key = os.getenv('TELNYX_API_KEY')
                        twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
                        twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
                        
                        if telnyx_api_key and call_sid:
                            # Telnyx Call Control: transfer via TeXML update
                            from urllib.parse import quote
                            resp = httpx.post(
                                f"https://api.telnyx.com/v2/texml/calls/{call_sid}/update",
                                headers={
                                    "Authorization": f"Bearer {telnyx_api_key}",
                                    "Content-Type": "application/json",
                                },
                                json={"texml": f'<Response><Say>Transferring you now.</Say><Dial timeout="60" action="{config.PUBLIC_URL}/telnyx/dial-status" method="POST"><Number>{transfer_number}</Number></Dial></Response>'},
                                timeout=10.0,
                            )
                            if resp.status_code < 300:
                                print(f"✅ Transfer initiated via Telnyx")
                            else:
                                print(f"⚠️ Telnyx transfer: {resp.status_code}")
                        elif twilio_account_sid and twilio_auth_token and call_sid:
                            # Twilio: update call with TwiML redirect
                            from urllib.parse import quote
                            transfer_twiml_url = f"{config.PUBLIC_URL}/twilio/transfer?number={quote(transfer_number)}"
                            resp = httpx.post(
                                f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Calls/{call_sid}.json",
                                auth=(twilio_account_sid, twilio_auth_token),
                                data={"Url": transfer_twiml_url, "Method": "POST"},
                                timeout=10.0,
                            )
                            if resp.status_code < 300:
                                print(f"✅ Transfer initiated via Twilio")
                            else:
                                print(f"⚠️ Twilio transfer: {resp.status_code}")
                        else:
                            print(f"⚠️ Transfer skipped — no Telnyx or Twilio credentials")
                    except Exception as e:
                        print(f"❌ Transfer error: {e}")
                
            except asyncio.TimeoutError:
                print("⏱️ TTS timeout")
            except asyncio.CancelledError:
                print("🛑 TTS cancelled")
            except Exception as e:
                print(f"❌ TTS error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Safety net: only set speaking=False if no prerecorded playback task
                # is still running (those tasks handle their own speaking=False timing)
                if not hasattr(run, '_prerecorded_playing') or not run._prerecorded_playing:
                    tts_ended_at = asyncio.get_event_loop().time()
                    speaking = False
                llm_processing = False
                ready_time = time_module.time()
                print(f"👂 Ready to listen (total response cycle: {ready_time - run_start:.3f}s)")

        if respond_task and not respond_task.done():
            respond_task.cancel()
        respond_task = asyncio.create_task(run())

    async def greet():
        """Send initial greeting — personalized for returning customers or outbound calls"""
        nonlocal speaking, stream_sid
        
        if is_outbound and outbound_call_type == "lost_job_callback":
            # Outbound: lost job follow-up greeting
            first_name = ""
            if outbound_caller_name and outbound_caller_name.strip():
                first_name = outbound_caller_name.split()[0]
            
            # Get business name for the greeting
            biz_name = "us"
            if company_id:
                try:
                    from src.services.database import get_database
                    _db = get_database()
                    _company = _db.get_company(int(company_id))
                    if _company and _company.get('company_name'):
                        biz_name = _company['company_name']
                    # Set industry type on call state for tool execution
                    call_state.industry_type = (_company or {}).get('industry_type', 'trades')
                except Exception:
                    pass
            
            issue_brief = "your enquiry"
            if outbound_ai_summary:
                issue_brief = outbound_ai_summary.split('.')[0].strip().lower()
                if len(issue_brief) > 60:
                    issue_brief = issue_brief[:57] + "..."
            
            name_part = f" {first_name}" if first_name else ""
            greeting = f"Hi{name_part}, this is {biz_name} calling. You rang us earlier about {issue_brief} — I just wanted to follow up and see if you still need help with that?"
        elif caller_is_returning and caller_customer_name and caller_customer_name.strip():
            first_name = caller_customer_name.split()[0]
            greeting = f"Hi, thank you for calling. How can I help you today?"
        else:
            greeting = "Hi, thank you for calling. How can I help you today?"
        
        print(f"\n🤖 GREETING: {greeting}")
        conversation_log.append({"role": "assistant", "content": greeting, "timestamp": asyncio.get_event_loop().time()})
        
        # Try pre-recorded greeting (generic greeting is the same for all callers now)
        if has_prerecorded_fillers():
            audio = get_filler_audio("greeting")
            if audio:
                await send_prerecorded_audio(ws, stream_sid, audio)
                # Schedule speaking=False after playback (non-blocking)
                playback_seconds = len(audio) / 8000.0
                tts_ended_at = asyncio.get_event_loop().time() + playback_seconds
                last_tts_audio_done = tts_ended_at
                async def _clear_after_greeting(delay):
                    nonlocal speaking
                    await asyncio.sleep(delay)
                    asr.clear()
                    speaking = False
                asyncio.create_task(_clear_after_greeting(playback_seconds))
                return
        
        # Fallback to TTS (always used for returning customers to say their name)
        async def tokens():
            yield greeting
        await start_tts(tokens(), label="greet")

    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
                event = data.get("event")
            except json.JSONDecodeError:
                continue

            if event == "start":
                # Telnyx TeXML uses stream_id; Twilio uses streamSid
                stream_sid = data.get("stream_id") or data.get("start", {}).get("streamSid", "")
                call_sid = data["start"].get("call_control_id", "") or data["start"].get("callSid", "")
                custom_params = data["start"].get("customParameters", {})
                caller_phone = custom_params.get("From", "") or data["start"].get("from", "")
                company_id = custom_params.get("CompanyId", "") or None
                
                # Outbound call detection
                is_outbound = bool(custom_params.get("CallType", ""))
                outbound_call_type = custom_params.get("CallType", "")
                outbound_call_log_id = custom_params.get("CallLogId", "")
                outbound_caller_name = custom_params.get("CallerName", "")
                outbound_lost_reason = custom_params.get("LostReason", "")
                outbound_ai_summary = custom_params.get("AISummary", "")
                
                print(f"🎧 Stream started: {stream_sid}")
                if is_outbound:
                    print(f"📞 [OUTBOUND] Type: {outbound_call_type}, CallLog: {outbound_call_log_id}")
                print(f"📱 Caller: {caller_phone}, Company: {company_id}")

                # Format phone for display
                formatted_phone = caller_phone
                if caller_phone and caller_phone.startswith('+353'):
                    local = '0' + caller_phone[4:]
                    if len(local) == 10:
                        formatted_phone = f"{local[:3]} {local[3:6]} {local[6:]}"
                
                # Phone-first customer identification: look up caller by phone BEFORE the conversation starts
                caller_is_returning = False
                caller_customer_name = None
                caller_customer_info = None
                if caller_phone and company_id:
                    try:
                        from src.services.database import get_database
                        _lookup_db = get_database()
                        _existing_client = _lookup_db.find_client_by_phone(caller_phone, company_id=int(company_id))
                        if _existing_client:
                            caller_is_returning = True
                            caller_customer_name = _existing_client.get('name', '')
                            caller_customer_info = {
                                'id': _existing_client.get('id'),
                                'name': _existing_client.get('name'),
                                'phone': _existing_client.get('phone'),
                                'email': _existing_client.get('email'),
                                'address': _existing_client.get('address'),
                                'eircode': _existing_client.get('eircode'),
                            }
                            # Also get last address from bookings if not on client record
                            if not caller_customer_info.get('address') and not caller_customer_info.get('eircode'):
                                try:
                                    _bookings = _lookup_db.get_client_bookings(_existing_client['id'], company_id=int(company_id))
                                    if _bookings:
                                        for _b in _bookings:
                                            if _b.get('address') or _b.get('eircode'):
                                                caller_customer_info['address'] = _b.get('address') or _b.get('eircode')
                                                break
                                except Exception:
                                    pass
                            print(f"📱 [PHONE_LOOKUP] Returning customer: {caller_customer_name} (ID: {_existing_client.get('id')})")
                        else:
                            print(f"📱 [PHONE_LOOKUP] New customer (phone not in database)")
                    except Exception as e:
                        print(f"⚠️ [PHONE_LOOKUP] Error: {e}")
                
                # Build system context based on call type
                if is_outbound and outbound_call_type == "lost_job_callback":
                    # OUTBOUND: Lost job follow-up call
                    first_name = ""
                    if outbound_caller_name and outbound_caller_name.strip():
                        first_name = outbound_caller_name.split()[0]
                    
                    conversation.append({
                        "role": "system",
                        "content": (
                            f"[SYSTEM: This is an OUTBOUND follow-up call to a customer who called earlier but didn't book. "
                            f"Customer name: {outbound_caller_name or 'unknown'}. "
                            f"What they called about: {outbound_ai_summary or 'unknown'}. "
                            f"Why they didn't book: {outbound_lost_reason or 'unknown'}. "
                            f"Your greeting has already been sent. DO NOT re-greet. "
                            f"Be warm, friendly, NOT pushy. Keep it SHORT — under 2 minutes. "
                            f"If they want to book, use get_next_available / search_availability / book_job. "
                            f"If not interested, thank them and end gracefully. "
                            f"NEVER be aggressive. If they seem annoyed, apologize and end the call. "
                            f"You already know their phone number and name — do NOT ask again.]"
                        )
                    })
                    
                    # Set call_state for outbound context
                    call_state['is_outbound'] = True
                    call_state['outbound_type'] = outbound_call_type
                    call_state['customer_name'] = outbound_caller_name
                
                elif caller_is_returning:
                    # RETURNING CUSTOMER — inject their info so AI can greet them by name
                    first_name = caller_customer_name.split()[0] if caller_customer_name and caller_customer_name.strip() else ''
                    # Store on call_state so direct responses (match_issue fallback etc) can use it
                    if caller_customer_name:
                        call_state['customer_name'] = caller_customer_name
                    # Store address on call_state for direct response templates
                    stored_address = caller_customer_info.get('address') or caller_customer_info.get('eircode') or ''
                    if stored_address:
                        call_state['customer_address'] = stored_address
                    info_parts = [f"RETURNING CUSTOMER identified by phone: {caller_customer_name or 'name unknown'}"]
                    if caller_customer_info.get('email'):
                        info_parts.append(f"email: {caller_customer_info['email']}")
                    if stored_address:
                        info_parts.append(f"address on file: {stored_address}")
                    customer_context = ". ".join(info_parts)
                    
                    phone_instruction = (
                        f"PHONE NUMBER: Caller's number is {formatted_phone} (from caller ID). Already confirmed — do NOT ask again."
                    )
                    
                    if first_name:
                        greeting_note = "Greeting already sent — generic greeting, you did NOT mention the caller's name yet."
                        name_note = (
                            f"This is a RETURNING CUSTOMER. Their name on file is {caller_customer_name} (identified from the phone number in our system). "
                            f"Do NOT reveal their name in the greeting — wait until AFTER they describe their issue and you call match_issue. "
                            f"Then say something like: 'I have the name under this number as {first_name}, is that right?' "
                            f"If they confirm, skip asking for name and continue with the booking flow. "
                            f"Do NOT call lookup_customer — already done."
                        )
                    else:
                        greeting_note = "Greeting already sent. This is a returning customer but their name is not on file yet."
                        name_note = "Ask for their name: 'Can I get your name please, and spell it out for me if possible?'"
                    
                    # Address instruction — tell AI to read the stored address when confirming
                    if stored_address:
                        address_note = (
                            f"ADDRESS ON FILE: {stored_address}. "
                            f"When confirming the address, ALWAYS read it out: 'Is it still the same address, {stored_address}?' "
                            f"If the caller asks what address is on file, tell them: 'The address I have on file is {stored_address}.' "
                            f"Do NOT refuse to read the address — it is safe to share with the caller since they are the account holder."
                        )
                    else:
                        address_note = "No address on file — ask for their eircode or full address."
                    
                    conversation.append({
                        "role": "system",
                        "content": (
                            f"[SYSTEM: {greeting_note} "
                            f"DO NOT re-introduce, re-greet, or ask 'how can I help' again. "
                            f"Keep replies SHORT. "
                            f"{customer_context}. "
                            f"{name_note} Do NOT call lookup_customer — already done. "
                            f"{address_note} "
                            f"{phone_instruction} "
                            f"The system will extract name, address, eircode, and email from the transcript after the call. "
                            f"Say things ONCE only.]"
                        )
                    })
                else:
                    # NEW CUSTOMER — phone not found
                    phone_instruction = (
                        f"PHONE NUMBER: Caller's number is {formatted_phone} (from caller ID). "
                        f"Confirm this number with them: 'Is {formatted_phone} a good number to reach you?'"
                    ) if caller_phone else "PHONE NUMBER: Not detected. Ask for their number."
                    
                    conversation.append({
                        "role": "system",
                        "content": (
                            "[SYSTEM: Greeting already sent. DO NOT re-introduce or ask 'how can I help' again. "
                            "Keep replies SHORT. This is a NEW CUSTOMER (phone not in our system). "
                            "After they describe their issue, ask for their name: 'Can I get your name please, and spell it out for me if possible?' "
                            "Do NOT spell the name back or ask them to confirm spelling — the system will extract the correct name from the transcript after the call. "
                            "Just acknowledge the name and move on. "
                            f"{phone_instruction} "
                            "The system will extract and verify name, address, eircode, and email from the transcript after the call. "
                            "Say things ONCE only.]"
                        )
                    })
                
                asyncio.create_task(greet())
                
                # Start background ambient audio loop via WebSocket
                # Sends low-volume office noise during silence periods.
                # Pauses automatically when AI is speaking (TTS/fillers).
                
                async def background_audio_loop():
                    """Send ambient office noise during silence (when AI isn't speaking)."""
                    try:
                        from src.services.prerecorded_audio import get_ambient_audio
                        ambient = get_ambient_audio()
                        if not ambient:
                            print(f"[BG_AUDIO] ⚠️ No ambient audio loaded — skipping")
                            return
                        
                        # Reduce volume: convert mulaw→PCM16, scale down, convert back to mulaw
                        import audioop
                        AMBIENT_VOLUME = 0.35  # 35% of original volume
                        pcm = audioop.ulaw2lin(ambient, 2)       # mulaw → 16-bit PCM
                        pcm = audioop.mul(pcm, 2, AMBIENT_VOLUME) # scale amplitude
                        ambient = audioop.lin2ulaw(pcm, 2)        # PCM → mulaw
                        
                        # Wait for greeting to start playing before we begin
                        await asyncio.sleep(0.3)
                        
                        chunk_size = 160  # 20ms at 8kHz mulaw
                        total_chunks = len(ambient) // chunk_size
                        if total_chunks == 0:
                            return
                        chunk_idx = 0
                        BATCH_CHUNKS = 5   # 100ms of audio per batch
                        BATCH_INTERVAL = 0.1
                        
                        print(f"[BG_AUDIO] 🔊 Starting ambient audio loop ({len(ambient)} bytes, {total_chunks} chunks, volume={AMBIENT_VOLUME})")
                        
                        while not bg_audio_stop.is_set():
                            # Pause when AI is speaking — TTS handles its own audio
                            # IMPORTANT: Do NOT break out of the loop! Just pause and
                            # resume when speaking finishes. The ambient audio should
                            # play for the entire duration of the call.
                            if speaking:
                                try:
                                    await asyncio.wait_for(bg_audio_stop.wait(), timeout=0.2)
                                    if bg_audio_stop.is_set():
                                        break  # Only break if call is ending
                                except asyncio.TimeoutError:
                                    continue  # Keep pausing while speaking
                            
                            for _ in range(BATCH_CHUNKS):
                                if bg_audio_stop.is_set() or speaking:
                                    break
                                offset = (chunk_idx % total_chunks) * chunk_size
                                chunk = ambient[offset:offset + chunk_size]
                                if len(chunk) < chunk_size:
                                    chunk_idx = 0
                                    chunk = ambient[0:chunk_size]
                                
                                payload = base64.b64encode(chunk).decode('utf-8')
                                try:
                                    await ws.send(json.dumps({
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {"payload": payload},
                                    }))
                                except Exception:
                                    return
                                chunk_idx += 1
                            
                            try:
                                await asyncio.wait_for(bg_audio_stop.wait(), timeout=BATCH_INTERVAL)
                                break  # bg_audio_stop was set — call is ending
                            except asyncio.TimeoutError:
                                pass  # Normal — keep looping
                        
                        print(f"[BG_AUDIO] 🔇 Ambient audio stopped")
                    except Exception as e:
                        print(f"[BG_AUDIO] ⚠️ Error: {e}")
                
                bg_audio_task = asyncio.create_task(background_audio_loop())
                
                # Warmup OpenAI with real system prompt to prime prompt cache
                # (skip for outbound — shorter calls, not worth the extra API call)
                if not is_outbound:
                    async def warmup():
                        try:
                            from src.services.llm_stream import get_openai_client, get_cached_system_prompt
                            from src.services.calendar_tools import CALENDAR_TOOLS
                            client = get_openai_client()
                            # Load the actual company system prompt — primes both
                            # local _company_prompt_cache AND OpenAI's server-side prompt cache
                            system_prompt = get_cached_system_prompt(company_id=company_id)
                            def do_warmup():
                                stream = client.chat.completions.create(
                                    model=config.CHAT_MODEL,
                                    messages=[
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": "hi"},
                                    ],
                                    stream=True, temperature=0.1,
                                    tools=CALENDAR_TOOLS, tool_choice="none",
                                    **config.max_tokens_param(value=5)
                                )
                                for _ in stream: pass
                            await asyncio.to_thread(do_warmup)
                            print(f"🔥 OpenAI warmed up (prompt cache primed for company {company_id})")
                        except Exception as e:
                            print(f"⚠️ Warmup failed: {e}")
                    asyncio.create_task(warmup())

                    # Warmup ElevenLabs TTS (belt-and-suspenders alongside server keepalive)
                    async def warmup_tts():
                        try:
                            if config.TTS_PROVIDER != 'elevenlabs' or not config.ELEVENLABS_API_KEY:
                                return
                            import websockets as ws_lib
                            voice_id = config.ELEVENLABS_VOICE_ID
                            uri = (
                                f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
                                f"?model_id=eleven_flash_v2_5&output_format=ulaw_8000&optimize_streaming_latency=4"
                            )
                            async with ws_lib.connect(
                                uri,
                                extra_headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                                open_timeout=8, close_timeout=3,
                            ) as tts:
                                await tts.send(json.dumps({
                                    "text": " ",
                                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                                }))
                                await tts.send(json.dumps({"text": "Hi.", "try_trigger_generation": True}))
                                await tts.send(json.dumps({"text": ""}))
                                while True:
                                    try:
                                        msg = await asyncio.wait_for(tts.recv(), timeout=5.0)
                                        data_msg = json.loads(msg)
                                        if data_msg.get("isFinal"):
                                            break
                                    except asyncio.TimeoutError:
                                        break
                            print(f"🔥 ElevenLabs TTS warmed up")
                        except Exception as e:
                            print(f"⚠️ ElevenLabs warmup failed: {e}")
                    asyncio.create_task(warmup_tts())

            elif event == "media":
                if not stream_sid:
                    continue

                audio = base64.b64decode(data["media"]["payload"])
                energy = ulaw_energy(audio)
                now = asyncio.get_event_loop().time()
                
                # Append to rolling buffer for address audio capture
                audio_buffer.append(audio)
                
                # Append to full call recording
                full_call_audio.append(audio)

                # ASR health check
                if asr.is_closed():
                    print(f"[ASR] ⚠️ Connection closed, attempting reconnect...")
                    if await asr.reconnect():
                        print("✅ ASR reconnected")
                    else:
                        print(f"[ASR] ❌ Reconnect failed")
                        continue

                # ALWAYS feed audio to keep Deepgram connection alive
                # This prevents the "did not receive audio" timeout
                await asr.feed(audio)

                # Barge-in while speaking
                if speaking:
                    if (now - tts_started_at) <= NO_BARGEIN_WINDOW:
                        continue
                    
                    if energy > INTERRUPT_ENERGY:
                        if bargein_since == 0.0:
                            bargein_since = now
                        elif (now - bargein_since) >= BARGEIN_HOLD:
                            interim = asr.get_interim()
                            if len(interim.strip().split()) >= 1:
                                interrupt = True
                                print(f"✋ Interrupt: '{interim}'")
                                await clear_audio_buffer()
                                if respond_task and not respond_task.done():
                                    respond_task.cancel()
                                speaking = False
                                tts_ended_at = now
                                bargein_since = 0.0
                                # Clear stale ASR state from during TTS playback.
                                # The caller is still speaking — Deepgram will send
                                # fresh interim/is_final/speech_final events within ms.
                                asr.clear()
                    else:
                        bargein_since = 0.0
                    continue

                # Ignore tail after TTS
                if (now - tts_ended_at) < POST_TTS_IGNORE:
                    continue
                
                # DEBUG: Log ASR state when there's a pending segment stuck for too long
                if asr.last_segment_text and not asr.speech_final:
                    seg_age = time_module.time() - asr.last_segment_time if asr.last_segment_time > 0 else -1
                    # Only log after 3s to reduce noise
                    if seg_age > 3.0 and int(seg_age * 10) % 50 == 0:
                        print(f"[ASR] ⚠️ Pending segment stuck: '{asr.last_segment_text[:50]}' age={seg_age:.1f}s")
                
                # Fallback: If Deepgram sent an is_final segment but never sent
                # speech_final or UtteranceEnd, promote it after 5 seconds of silence.
                # This is a last-resort safety net — with utterance_end_ms enabled,
                # this should rarely fire. Using 5s to avoid cutting off the caller's
                # first long utterance (Deepgram VAD calibration can be slow on the
                # first sentence). utterance_end_ms (1.2s) and endpointing (1.2s)
                # catch normal cases much faster.
                if not asr.is_speech_finished() and asr.has_pending_segment(timeout=5.0):
                    asr.promote_segment()
                
                # Check for speech_final — trust Deepgram's signal
                if asr.is_speech_finished():
                    speech_detected_at = time_module.time()
                    text = asr.get_text().strip()
                    asr.clear()
                    
                    if not text or len(text.split()) < MIN_WORDS:
                        print(f"[DEBUG] Dropped (MIN_WORDS): '{text}' words={len(text.split())}")
                        continue
                    
                    # Duplicate check — allow repeats if TTS failed or enough time passed
                    if norm_text(text) == norm_text(last_committed):
                        time_since_committed = time_module.time() - last_committed_at
                        if last_tts_success and time_since_committed < DUPLICATE_EXPIRY:
                            print(f"[DEBUG] Dropped (DUPLICATE): '{text}' == '{last_committed}'")
                            continue
                        else:
                            reason = "TTS failed" if not last_tts_success else f"expired ({time_since_committed:.1f}s > {DUPLICATE_EXPIRY}s)"
                            print(f"[DEBUG] Allowing repeat: '{text}' ({reason})")
                    
                    # LLM timeout check
                    if llm_processing and (now - llm_started_at) > LLM_PROCESSING_TIMEOUT:
                        print(f"[MEDIA] ⚠️ TIMEOUT: LLM processing exceeded {LLM_PROCESSING_TIMEOUT}s - resetting state")
                        llm_processing = False
                    
                    # Filter filler during LLM processing
                    if llm_processing and text.lower().strip().rstrip('?.,!') in FILLER_PHRASES:
                        print(f"🤫 Ignoring filler: '{text}'")
                        continue
                    
                    # Log user speech with timing
                    print(f"\n{'='*60}")
                    print(f"👤 CALLER: {text}")
                    print(f"[PIPELINE] 📍 Speech detected at {speech_detected_at:.3f}")
                    print(f"{'='*60}\n")
                    
                    conversation_log.append({"role": "user", "content": text, "timestamp": now})
                    last_committed = text
                    last_committed_at = time_module.time()
                    conversation.append({"role": "user", "content": text})
                    
                    # Address audio capture — DEFERRED approach
                    # Phase 1 (in start_tts): AI asked for address → awaiting_address_audio = True
                    # Phase 2 (here): First speech_final → start collecting (skip-check only)
                    # Phase 3 (before start_tts below): Caller is done → snapshot buffer, upload
                    #
                    # WHY DEFERRED: Deepgram can split a long address like
                    # "32 Silver Grove, Ballybrack, D18 WR97" into multiple speech_final
                    # events. If we captured on the first one, we'd only get "32 Silver Grove".
                    # By waiting until the LLM is about to respond, we know the caller is
                    # finished and we get the FULL address audio. This is fine because the
                    # recording is for async playback — no real-time requirement.
                    if call_state.awaiting_address_audio:
                        phase1_time = call_state._addr_audio_phase1_time
                        phase_gap = time_module.time() - phase1_time if phase1_time else -1
                        print(f"🎙️ [ADDR_AUDIO] Phase 2: speech_final received, gap since phase1={phase_gap:.1f}s")
                        # Skip capture if the caller clearly didn't give an address
                        text_lower_check = text.lower().strip().rstrip('.,!?')
                        skip_phrases = {'no', "no i don't", "no i dont", "i don't know", "i dont know",
                                        "i'm not sure", "im not sure", "not sure", "no idea",
                                        "okay", "ok", "sure", "yeah", "yes", "yep", "right",
                                        "grand", "go ahead", "fire away"}
                        if text_lower_check in skip_phrases or (len(text.split()) <= 3 and text_lower_check.startswith('no')):
                            print(f"🎙️ [ADDR_AUDIO] Skipping capture — caller declined/doesn't know: '{text}'")
                            # DON'T disarm — keep awaiting so the next response (after AI
                            # re-asks for address) will be captured. Phase 1 will re-arm
                            # with a fresh timestamp when the AI asks again.
                        else:
                            call_state.awaiting_address_audio = False
                            call_state._addr_audio_collecting = True
                            print(f"🎙️ [ADDR_AUDIO] Collecting — will capture full audio before LLM responds")
                    
                    # Fallback: AI asked for address earlier in the call, but the
                    # awaiting flag got cleared (e.g. AI said something unrelated in
                    # between like "I'm ready when you are!"). If the caller now gives
                    # something that looks like an address, capture it anyway.
                    elif (call_state._addr_audio_ever_asked
                          and not call_state.address_audio_captured
                          and not call_state._addr_audio_collecting):
                        text_lower_check = text.lower().strip().rstrip('.,!?')
                        skip_phrases = {'no', "no i don't", "no i dont", "i don't know", "i dont know",
                                        "i'm not sure", "im not sure", "not sure", "no idea",
                                        "okay", "ok", "yeah", "yes", "that's it", "thanks",
                                        "no that's it", "no thanks"}
                        is_short_non_address = text_lower_check in skip_phrases or len(text.split()) <= 2
                        if not is_short_non_address and len(text.split()) >= 3:
                            print(f"🎙️ [ADDR_AUDIO] Phase 2 FALLBACK: Caller gave address-like response after earlier ask")
                            call_state._addr_audio_phase1_time = time_module.time() - 5.0  # Approximate
                            call_state._addr_audio_collecting = True
                    
                    # Email audio capture — Phase 2: same deferred approach as address
                    if call_state.awaiting_email_audio:
                        phase1_time = call_state._email_audio_phase1_time
                        phase_gap = time_module.time() - phase1_time if phase1_time else -1
                        print(f"📧 [EMAIL_AUDIO] Phase 2: speech_final received, gap since phase1={phase_gap:.1f}s")
                        text_lower_check = text.lower().strip().rstrip('.,!?')
                        skip_phrases = {'no', "no i don't", "no i dont", "i don't have one",
                                        "i dont have one", "no email", "no thanks",
                                        "i'm not sure", "not sure", "no idea",
                                        "okay", "ok", "sure", "yeah", "yes", "yep",
                                        "grand", "go ahead", "fire away", "i don't have email",
                                        "i dont have email", "no i don't", "no i dont"}
                        if text_lower_check in skip_phrases or (len(text.split()) <= 3 and text_lower_check.startswith('no')):
                            print(f"📧 [EMAIL_AUDIO] Skipping capture — caller declined: '{text}'")
                            call_state.awaiting_email_audio = False
                            call_state._email_audio_ever_asked = False
                        else:
                            call_state.awaiting_email_audio = False
                            call_state._email_audio_collecting = True
                            print(f"📧 [EMAIL_AUDIO] Collecting — will capture full audio before LLM responds")
                    elif (call_state._email_audio_ever_asked
                          and not call_state.email_audio_captured
                          and not call_state._email_audio_collecting):
                        text_lower_check = text.lower().strip().rstrip('.,!?')
                        skip_phrases = {'no', "no i don't", "no i dont", "no thanks",
                                        "i don't have one", "i dont have one", "no email",
                                        "okay", "ok", "yeah", "yes", "that's it", "thanks"}
                        is_short_decline = text_lower_check in skip_phrases or len(text.split()) <= 2
                        # Email responses are typically short (e.g. "john at gmail dot com")
                        if not is_short_decline and len(text.split()) >= 2:
                            print(f"📧 [EMAIL_AUDIO] Phase 2 FALLBACK: Caller gave email-like response after earlier ask")
                            call_state._email_audio_phase1_time = time_module.time() - 5.0
                            call_state._email_audio_collecting = True
                    
                    # Trim history - keep more context to prevent AI from forgetting
                    # Keep system message + last 50 messages
                    if len(conversation) > 51:
                        conversation[:] = [conversation[0]] + conversation[-50:]
                    
                    # Start response
                    llm_processing = True
                    llm_started_at = now
                    
                    # Phase 3: Deferred address audio capture — caller is done, LLM
                    # is about to respond. Snapshot the buffer NOW so we get the
                    # FULL address even if Deepgram split it across multiple speech_final
                    # events. No rush — this uploads async in the background.
                    if call_state._addr_audio_collecting:
                        call_state._addr_audio_collecting = False
                        call_state._addr_audio_ever_asked = False  # Disable fallbacks — we got the audio
                        call_state.awaiting_address_audio = False  # Fully disarm
                        # Mark captured NOW (synchronously) so book_job defers the SMS.
                        # The actual URL gets set after the async upload, but the deferral
                        # decision must happen before book_job runs.
                        call_state.address_audio_captured = True
                        phase1_time = call_state._addr_audio_phase1_time
                        print(f"🎙️ [ADDR_AUDIO] Phase 3: Capturing full address audio before LLM responds")
                        
                        full_buffer = list(audio_buffer)
                        total_packets = len(full_buffer)
                        now_mono = asyncio.get_event_loop().time()
                        
                        # Time-window: from when TTS finished (AI stopped talking) to now
                        # +2s padding before to catch overlap (caller starts while AI finishes)
                        if last_tts_audio_done > 0:
                            since_audio_end = now_mono - last_tts_audio_done
                            window_seconds = since_audio_end + 2.0
                            packets_to_take = int(window_seconds * MULAW_SAMPLE_RATE / MULAW_BYTES_PER_PACKET)
                            packets_to_take = min(packets_to_take, total_packets)
                            buffer_snapshot = full_buffer[-packets_to_take:] if packets_to_take > 0 else full_buffer
                            print(f"🎙️ [ADDR_AUDIO] Time-window: since_audio_end={since_audio_end:.1f}s, "
                                  f"+2s padding, window={window_seconds:.1f}s, "
                                  f"taking={len(buffer_snapshot)}/{total_packets} packets")
                        elif phase1_time and phase1_time > 0:
                            elapsed = time_module.time() - phase1_time
                            packets_to_take = int((elapsed + 3.0) * MULAW_SAMPLE_RATE / MULAW_BYTES_PER_PACKET)
                            packets_to_take = min(packets_to_take, total_packets)
                            buffer_snapshot = full_buffer[-packets_to_take:] if packets_to_take > 0 else full_buffer
                            print(f"🎙️ [ADDR_AUDIO] Fallback time-window: elapsed={elapsed:.1f}s +3s, "
                                  f"taking={len(buffer_snapshot)}/{total_packets}")
                        else:
                            buffer_snapshot = full_buffer
                            print(f"🎙️ [ADDR_AUDIO] No timestamps — using full buffer")
                        
                        raw_total = sum(len(p) for p in buffer_snapshot)
                        print(f"🎙️ [ADDR_AUDIO] Buffer: {len(buffer_snapshot)} packets, "
                              f"{raw_total} bytes, ~{raw_total / MULAW_SAMPLE_RATE:.1f}s")
                        
                        # Light trim — strip line noise / ambient at the leading edge.
                        # Adaptive threshold auto-adjusts to the call's noise floor.
                        # Leading pad reduced to 10 packets (~200ms) — enough for speech
                        # onset without letting seconds of empty sound through.
                        # Trailing pad stays generous (25) to avoid clipping final syllable.
                        captured_audio = trim_silence_mulaw(buffer_snapshot, energy_threshold=30.0, pad_packets=10)
                        cap_bytes = len(captured_audio)
                        cap_duration = cap_bytes / MULAW_SAMPLE_RATE
                        
                        # Safety net: if trim is too aggressive (<1.5s), use full buffer.
                        # An address/eircode takes at least 2-3s to say.
                        if cap_duration < 1.5 and len(buffer_snapshot) > 0:
                            raw_duration = raw_total / MULAW_SAMPLE_RATE
                            print(f"🎙️ [ADDR_AUDIO] ⚠️ Trim too short ({cap_duration:.1f}s) — using full buffer ({raw_duration:.1f}s)")
                            captured_audio = b''.join(buffer_snapshot)
                            cap_bytes = len(captured_audio)
                        
                        print(f"🎙️ [ADDR_AUDIO] Final: {cap_bytes} bytes, ~{cap_bytes / MULAW_SAMPLE_RATE:.1f}s")
                        
                        import time as _time_mod
                        capture_ts = int(_time_mod.time())
                        async def _capture_address_audio(raw_audio, ts=capture_ts):
                            try:
                                if not raw_audio:
                                    print(f"⚠️ [ADDR_AUDIO] Upload skipped — empty audio")
                                    return
                                print(f"🎙️ [ADDR_AUDIO] Converting {len(raw_audio)} bytes mulaw → WAV")
                                wav_data = await asyncio.to_thread(mulaw_to_wav, raw_audio)
                                wav_len = len(wav_data)
                                wav_duration = (wav_len - 44) / (MULAW_SAMPLE_RATE * 2)
                                print(f"🎙️ [ADDR_AUDIO] WAV: {wav_len} bytes, {wav_duration:.1f}s")
                                
                                from src.services.storage_r2 import upload_company_file
                                import io
                                company_id_int = int(company_id) if company_id else None
                                if not company_id_int:
                                    print(f"⚠️ [ADDR_AUDIO] No company_id, skipping upload")
                                    return
                                
                                filename = f"{call_sid or 'unknown'}_{ts}.wav"
                                print(f"🎙️ [ADDR_AUDIO] Uploading: company_{company_id_int}/address_audio/{filename}")
                                url = await asyncio.to_thread(
                                    upload_company_file,
                                    company_id_int,
                                    io.BytesIO(wav_data),
                                    filename,
                                    'address_audio',
                                    'audio/wav'
                                )
                                if url:
                                    call_state.address_audio_url = url
                                    call_state.address_audio_captured = True
                                    print(f"🎙️ [ADDR_AUDIO] ✅ Uploaded: {url} ({wav_duration:.1f}s)")
                                else:
                                    print(f"⚠️ [ADDR_AUDIO] Upload returned None")
                            except ValueError as ve:
                                print(f"⚠️ [ADDR_AUDIO] WAV error: {ve}")
                            except Exception as audio_err:
                                print(f"⚠️ [ADDR_AUDIO] Capture failed: {audio_err}")
                                import traceback
                                traceback.print_exc()
                        asyncio.create_task(_capture_address_audio(captured_audio))
                    
                    # Phase 3: Deferred email audio capture — same mechanism as address
                    if call_state._email_audio_collecting:
                        call_state._email_audio_collecting = False
                        call_state._email_audio_ever_asked = False
                        call_state.awaiting_email_audio = False
                        call_state.email_audio_captured = True
                        phase1_time = call_state._email_audio_phase1_time
                        print(f"📧 [EMAIL_AUDIO] Phase 3: Capturing email audio before LLM responds")
                        
                        full_buffer = list(audio_buffer)
                        total_packets = len(full_buffer)
                        now_mono = asyncio.get_event_loop().time()
                        
                        if last_tts_audio_done > 0:
                            since_audio_end = now_mono - last_tts_audio_done
                            window_seconds = since_audio_end + 2.0
                            packets_to_take = int(window_seconds * MULAW_SAMPLE_RATE / MULAW_BYTES_PER_PACKET)
                            packets_to_take = min(packets_to_take, total_packets)
                            email_buffer_snapshot = full_buffer[-packets_to_take:] if packets_to_take > 0 else full_buffer
                        elif phase1_time and phase1_time > 0:
                            elapsed = time_module.time() - phase1_time
                            packets_to_take = int((elapsed + 3.0) * MULAW_SAMPLE_RATE / MULAW_BYTES_PER_PACKET)
                            packets_to_take = min(packets_to_take, total_packets)
                            email_buffer_snapshot = full_buffer[-packets_to_take:] if packets_to_take > 0 else full_buffer
                        else:
                            email_buffer_snapshot = full_buffer
                        
                        raw_total = sum(len(p) for p in email_buffer_snapshot)
                        print(f"📧 [EMAIL_AUDIO] Buffer: {len(email_buffer_snapshot)} packets, "
                              f"{raw_total} bytes, ~{raw_total / MULAW_SAMPLE_RATE:.1f}s")
                        
                        captured_email_audio = trim_silence_mulaw(email_buffer_snapshot, energy_threshold=30.0, pad_packets=10)
                        cap_bytes = len(captured_email_audio)
                        cap_duration = cap_bytes / MULAW_SAMPLE_RATE
                        
                        if cap_duration < 1.0 and len(email_buffer_snapshot) > 0:
                            captured_email_audio = b''.join(email_buffer_snapshot)
                            cap_bytes = len(captured_email_audio)
                        
                        print(f"📧 [EMAIL_AUDIO] Final: {cap_bytes} bytes, ~{cap_bytes / MULAW_SAMPLE_RATE:.1f}s")
                        
                        import time as _time_mod2
                        email_capture_ts = int(_time_mod2.time())
                        async def _capture_email_audio(raw_audio, ts=email_capture_ts):
                            try:
                                if not raw_audio:
                                    print(f"⚠️ [EMAIL_AUDIO] Upload skipped — empty audio")
                                    return
                                wav_data = await asyncio.to_thread(mulaw_to_wav, raw_audio)
                                wav_len = len(wav_data)
                                wav_duration = (wav_len - 44) / (MULAW_SAMPLE_RATE * 2)
                                print(f"📧 [EMAIL_AUDIO] WAV: {wav_len} bytes, {wav_duration:.1f}s")
                                
                                from src.services.storage_r2 import upload_company_file
                                import io
                                company_id_int = int(company_id) if company_id else None
                                if not company_id_int:
                                    print(f"⚠️ [EMAIL_AUDIO] No company_id, skipping upload")
                                    return
                                
                                filename = f"{call_sid or 'unknown'}_email_{ts}.wav"
                                print(f"📧 [EMAIL_AUDIO] Uploading: company_{company_id_int}/email_audio/{filename}")
                                url = await asyncio.to_thread(
                                    upload_company_file,
                                    company_id_int,
                                    io.BytesIO(wav_data),
                                    filename,
                                    'email_audio',
                                    'audio/wav'
                                )
                                if url:
                                    call_state.email_audio_url = url
                                    call_state.email_audio_captured = True
                                    print(f"📧 [EMAIL_AUDIO] ✅ Uploaded: {url} ({wav_duration:.1f}s)")
                                else:
                                    print(f"⚠️ [EMAIL_AUDIO] Upload returned None")
                            except ValueError as ve:
                                print(f"⚠️ [EMAIL_AUDIO] WAV error: {ve}")
                            except Exception as audio_err:
                                print(f"⚠️ [EMAIL_AUDIO] Capture failed: {audio_err}")
                                import traceback
                                traceback.print_exc()
                        asyncio.create_task(_capture_email_audio(captured_email_audio))
                    
                    print(f"[PIPELINE] 🚀 Starting LLM response...")
                    print(f"[PIPELINE] ⏱️ Time since speech detected: {time_module.time() - speech_detected_at:.3f}s")
                    
                    try:
                        await start_tts(
                            stream_llm(conversation, caller_phone=caller_phone, 
                                      company_id=company_id, call_state=call_state),
                            label="respond"
                        )
                    except Exception as e:
                        print(f"❌ Response error: {e}")
                        llm_processing = False

            elif event == "stop":
                print("🛑 Call ended")
                bg_audio_stop.set()
                break

    except websockets.ConnectionClosed as e:
        print(f"⚠️ WS disconnected: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bg_audio_stop.set()
        # Call summary
        total_duration = time_module.time() - call_start_time
        print(f"\n{'#'*60}")
        print(f"📊 CALL SUMMARY")
        print(f"Duration: {total_duration:.1f}s, Messages: {len(conversation_log)}")
        if response_times:
            print(f"Avg response: {sum(response_times)/len(response_times):.2f}s")
        # Address audio final state
        print(f"🎙️ Address audio: captured={call_state.address_audio_captured}, url={'set' if call_state.address_audio_url else 'None'}")
        if call_state.address_audio_url:
            print(f"🎙️ Audio URL: {call_state.address_audio_url}")
        print(f"📧 Email audio: captured={call_state.email_audio_captured}, url={'set' if call_state.email_audio_url else 'None'}")
        if call_state.email_audio_url:
            print(f"📧 Email audio URL: {call_state.email_audio_url}")
        print(f"{'#'*60}\n")
        
        # Post-call email re-transcription pipeline (runs FIRST so the refined
        # email is available for the booking confirmation sent by the address pipeline)
        _retranscribed_email = None
        if call_state.email_audio_url:
            _client_id = getattr(call_state, '_deferred_sms_client_id', None)
            if _client_id:
                try:
                    from src.services.address_retranscriber import retranscribe_email
                    company_id_int = int(company_id) if company_id else None
                    _retranscribed_email = await retranscribe_email(
                        audio_url=call_state.email_audio_url,
                        client_id=_client_id,
                        company_id=company_id_int,
                    )
                except Exception as e:
                    print(f"⚠️ Email retranscription error: {e}")
            else:
                print(f"📧 Email audio captured but no client_id — skipping email retranscription")
        
        # Post-call address re-transcription pipeline
        # If address audio was captured and SMS was deferred, run the
        # gpt-4o-transcribe re-transcription → DB update → SMS pipeline.
        _deferred_sms = getattr(call_state, '_deferred_sms_kwargs', None)
        if call_state.address_audio_url and _deferred_sms:
            try:
                from src.services.address_retranscriber import retranscribe_and_update
                company_id_int = int(company_id) if company_id else None
                # Use retranscribed email if available, otherwise fall back to deferred email
                _deferred_email = _retranscribed_email or getattr(call_state, '_deferred_customer_email', None)
                if _deferred_email:
                    _deferred_sms['_customer_email'] = _deferred_email
                await retranscribe_and_update(
                    audio_url=call_state.address_audio_url,
                    original_address=getattr(call_state, '_deferred_sms_original_address', None) or call_state.job_address or '',
                    caller_phone=caller_phone,
                    company_id=company_id_int,
                    booking_id=getattr(call_state, '_deferred_sms_booking_id', None),
                    client_id=getattr(call_state, '_deferred_sms_client_id', None),
                    send_sms=True,
                    sms_kwargs=_deferred_sms,
                )
            except Exception as e:
                print(f"⚠️ Address retranscription error: {e}")
                # Fallback: send SMS with original address
                try:
                    # Fallback: send notification with original address (email-first)
                    _deferred_email = _retranscribed_email or getattr(call_state, '_deferred_customer_email', None)
                    _fallback_phone = _deferred_sms.pop('to_number', None)
                    # Generate portal link for fallback notification
                    _fallback_portal_link = _deferred_sms.pop('portal_link', '')
                    if not _fallback_portal_link and _deferred_email and company_id_int:
                        try:
                            _fb_client_id = getattr(call_state, '_deferred_sms_client_id', None)
                            if _fb_client_id:
                                from src.services.sms_reminder import get_or_create_portal_link
                                _fallback_portal_link = get_or_create_portal_link(company_id_int, _fb_client_id)
                        except Exception:
                            pass
                    from src.services.sms_reminder import notify_customer
                    notify_customer(
                        'booking_confirmation',
                        customer_email=_deferred_email,
                        customer_phone=_fallback_phone or caller_phone,
                        appointment_time=_deferred_sms.get('appointment_time'),
                        customer_name=_deferred_sms.get('customer_name', 'Customer'),
                        service_type=_deferred_sms.get('service_type', 'appointment'),
                        company_name=_deferred_sms.get('company_name'),
                        employee_names=_deferred_sms.get('employee_names'),
                        address=_deferred_sms.get('address'),
                        portal_link=_fallback_portal_link,
                    )
                    print(f"📨 Fallback: sent notification with original address")
                except Exception as sms_err:
                    print(f"⚠️ Fallback notification also failed: {sms_err}")
        elif _deferred_sms and not call_state.address_audio_url:
            # Notification was deferred but the async R2 upload failed.
            # Send with the original ASR address — better than nothing.
            print(f"⚠️ Address audio upload failed but notification was deferred — sending with original address")
            try:
                _deferred_email = _retranscribed_email or getattr(call_state, '_deferred_customer_email', None)
                _fallback_phone = _deferred_sms.pop('to_number', None)
                _fallback_portal_link2 = _deferred_sms.pop('portal_link', '')
                _company_id_int2 = int(company_id) if company_id else None
                if not _fallback_portal_link2 and _deferred_email and _company_id_int2:
                    try:
                        _fb_client_id2 = getattr(call_state, '_deferred_sms_client_id', None)
                        if _fb_client_id2:
                            from src.services.sms_reminder import get_or_create_portal_link
                            _fallback_portal_link2 = get_or_create_portal_link(_company_id_int2, _fb_client_id2)
                    except Exception:
                        pass
                from src.services.sms_reminder import notify_customer
                notify_customer(
                    'booking_confirmation',
                    customer_email=_deferred_email,
                    customer_phone=_fallback_phone or caller_phone,
                    appointment_time=_deferred_sms.get('appointment_time'),
                    customer_name=_deferred_sms.get('customer_name', 'Customer'),
                    service_type=_deferred_sms.get('service_type', 'appointment'),
                    company_name=_deferred_sms.get('company_name'),
                    employee_names=_deferred_sms.get('employee_names'),
                    address=_deferred_sms.get('address'),
                    portal_link=_fallback_portal_link2,
                )
                print(f"📨 Sent deferred notification with original address (upload failed)")
            except Exception as sms_err:
                print(f"⚠️ Deferred notification fallback also failed: {sms_err}")
        elif call_state.address_audio_url and not _deferred_sms:
            # Address audio captured but no deferred SMS (no booking made, or SMS already sent)
            print(f"🎙️ Address audio captured but no deferred SMS — skipping retranscription pipeline")
        
        # Combined post-call summarization: single LLM call for both job notes + call log
        call_log_id = None
        if conversation_log and company_id:
            try:
                from src.services.call_summarizer import summarize_and_log_call
                company_id_int = int(company_id) if company_id else None
                call_log_id = await summarize_and_log_call(
                    conversation_log=conversation_log,
                    caller_phone=caller_phone,
                    company_id=company_id_int,
                    duration_seconds=int(total_duration),
                    call_sid=call_sid,
                    call_state=call_state,
                )
            except Exception as e:
                print(f"⚠️ Post-call summary/log error: {e}")
        
        # Upload full call recording to R2 (async, non-blocking)
        if company_id and full_call_audio and len(full_call_audio) > 50:
            try:
                raw_audio = b''.join(full_call_audio)
                audio_duration = len(raw_audio) / MULAW_SAMPLE_RATE
                print(f"🎙️ [RECORDING] Converting {len(raw_audio)} bytes ({audio_duration:.1f}s) to WAV...")
                
                if audio_duration < 1.0:
                    print(f"🎙️ [RECORDING] ⚠️ Recording too short ({audio_duration:.1f}s) — skipping upload")
                else:
                    wav_data = await asyncio.to_thread(mulaw_to_wav, raw_audio)
                    
                    from src.services.storage_r2 import upload_company_file
                    import io
                    company_id_int = int(company_id)
                    rec_filename = f"{call_sid or 'call'}_{int(call_start_time)}.wav"
                    
                    recording_url = await asyncio.to_thread(
                        upload_company_file,
                        company_id_int,
                        io.BytesIO(wav_data),
                        rec_filename,
                        'call_recordings',
                        'audio/wav'
                    )
                    
                    if recording_url and call_log_id:
                        from src.services.database import get_database
                        db = get_database()
                        db.update_call_log(call_log_id, recording_url=recording_url)
                        print(f"🎙️ [RECORDING] ✅ Saved ({audio_duration:.1f}s): {recording_url}")
                    elif recording_url:
                        print(f"🎙️ [RECORDING] ✅ Uploaded but no call_log_id to attach to")
                    else:
                        print(f"🎙️ [RECORDING] ⚠️ Upload returned None (R2 not configured?)")
            except Exception as e:
                print(f"⚠️ Recording upload error: {e}")
                import traceback
                traceback.print_exc()
        elif company_id:
            print(f"🎙️ [RECORDING] ⚠️ No audio captured (full_call_audio has {len(full_call_audio)} packets)")
        
        # Free memory
        full_call_audio.clear()
        
        if respond_task and not respond_task.done():
            respond_task.cancel()
        await asr.close()
        print("✅ Cleanup complete")
