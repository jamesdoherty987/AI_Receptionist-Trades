"""
Twilio Media Stream WebSocket Handler
Manages real-time voice conversations with VAD, ASR, LLM, and TTS
"""
import asyncio
import json
import base64
import re
import time as time_module  # For timing logs
import websockets

from src.utils.audio_utils import ulaw_energy
from src.utils.config import config
from src.services.asr_deepgram import DeepgramASR
from src.services.llm_stream import stream_llm, process_appointment_with_calendar
from src.services.call_state import CallState, create_call_state

# Import pre-recorded audio service with safe fallback
try:
    from src.services.prerecorded_audio import (
        get_filler_audio, get_random_filler_id, send_prerecorded_audio, 
        has_prerecorded_fillers, preload_fillers, get_filler_id_from_message
    )
    # Pre-load filler audio at module import (safe - never raises)
    preload_fillers()
    print(f"[AUDIO] Pre-recorded fillers available: {has_prerecorded_fillers()}")
except Exception as e:
    print(f"[AUDIO] Warning: Could not import prerecorded_audio: {e}")
    # Provide stub functions so the rest of the code works
    def has_prerecorded_fillers(): return False
    def get_random_filler_id(tool_name=None): return "one_moment"
    def get_filler_audio(phrase_id): return None
    async def send_prerecorded_audio(ws, sid, data): pass
    def preload_fillers(): pass
    def get_filler_id_from_message(message): return None

# Import TTS based on provider setting
TTS_PROVIDER = config.TTS_PROVIDER if hasattr(config, 'TTS_PROVIDER') else 'deepgram'

if TTS_PROVIDER == 'elevenlabs':
    from src.services.tts_elevenlabs import stream_tts
else:
    from src.services.tts_deepgram import stream_tts


def norm_text(s: str) -> str:
    """Normalize text for comparison"""
    return " ".join((s or "").lower().split())


def content_fingerprint(s: str) -> str:
    """
    Create a content fingerprint for duplicate detection.
    Removes all spaces and punctuation to catch cases where the same content
    is transcribed with different spacing (e.g., "v 9 5 h 5 p 2" vs "v95h5p2").
    """
    # Remove all non-alphanumeric characters and lowercase
    return re.sub(r'[^a-z0-9]', '', (s or "").lower())


def has_sentence_end(text: str) -> bool:
    """Check if text ends with sentence-ending punctuation"""
    text = text.strip()
    return bool(re.search(r'[.!?]$', text))


def should_respond(text: str, min_words: int = 2) -> bool:
    """Check if we have enough content to generate a response"""
    words = text.split()
    return len(words) >= min_words and (has_sentence_end(text) or len(words) >= 5)


async def media_handler(ws):
    """
    Handle Twilio media stream WebSocket connection
    
    Args:
        ws: WebSocket connection from Twilio
    """
    import time as time_module
    call_start_time = time_module.time()
    
    print(f"\n{'='*70}")
    print(f"📞 [CALL_START] New call at {call_start_time:.3f}")
    print(f"📞 [CALL_START] Twilio WS client connected: {ws.remote_address}")
    print(f"{'='*70}")
    
    # CRITICAL: Create per-call state for concurrent call handling
    # Each call gets its own CallState instance - no shared global state
    call_state = create_call_state()

    # --- TIMING: Deepgram ASR connection ---
    asr_connect_start = time_module.time()
    asr = DeepgramASR()
    try:
        await asr.connect()
        asr_connect_time = time_module.time() - asr_connect_start
        print(f"✅ [TIMING] Deepgram connected in {asr_connect_time:.3f}s")
    except Exception as e:
        asr_connect_time = time_module.time() - asr_connect_start
        print(f"❌ [TIMING] Deepgram connect failed after {asr_connect_time:.3f}s: {repr(e)}")
        return

    conversation = []
    stream_sid = None
    call_sid = None  # Store call SID for potential transfer
    caller_phone = None  # Store caller's phone number
    company_id = None  # Store company ID for multi-tenant support
    
    # Conversation logging
    conversation_log = []  # Full conversation transcript
    response_times = []  # Track response times
    
    # --- DETAILED RESPONSE TIMING TRACKER ---
    # Tracks breakdown of each response: ASR -> Pre-check -> OpenAI -> Tool -> TTS
    response_timing_details = []  # List of dicts with timing breakdown per response
    current_response_timing = {}  # Current response being timed

    # --- TTS / turn state ---
    speaking = False
    interrupt = False
    respond_task: asyncio.Task | None = None
    tts_started_at = 0.0
    tts_ended_at = 0.0
    
    # --- LLM processing state (prevents "hello?" confusion) ---
    llm_processing = False  # True while waiting for LLM response
    llm_started_at = 0.0    # When LLM processing started
    queued_speech = []      # Speech detected during LLM processing
    
    # --- Interruption tracking (prevents confusion loops) ---
    interrupt_count = 0           # Track consecutive interruptions
    last_interrupt_time = 0.0     # When last interrupt happened
    interrupted_text = ""         # What the AI was saying when interrupted
    INTERRUPT_COOLDOWN = 1.5      # Seconds to wait after interrupt before allowing another
    MAX_CONSECUTIVE_INTERRUPTS = 3  # After this many, pause and let caller speak fully
    
    # --- COMPLETION_WAIT window (allows caller to continue after speech_final) ---
    # Flow: Caller speaks -> Deepgram detects end (speech_final) -> start generating response
    # COMPLETION_WAIT (2s) runs IN PARALLEL with response generation
    # If caller speaks within COMPLETION_WAIT, cancel response, combine texts, restart
    continuation_window_start = 0.0  # When speech_final triggered and we started generating
    continuation_original_text = ""  # The text that triggered generation
    continuation_energy_since = 0.0  # Track sustained energy for continuation detection
    continuation_recovery_mode = False  # True when we cancelled and are waiting for more speech
    continuation_base_text = ""  # The combined text to build upon during recovery
    tool_execution_in_progress = False  # True when LLM is executing tool calls (unsafe to cancel)

    # --- State tracking ---
    last_committed = ""
    last_response_time = 0.0
    last_audio_time = 0.0  # Track last audio received for watchdog

    # --- Configurable Tunables (loaded from .env via config) ---
    SPEECH_ENERGY = config.SPEECH_ENERGY
    SILENCE_ENERGY = config.SILENCE_ENERGY

    INTERRUPT_ENERGY = config.INTERRUPT_ENERGY
    NO_BARGEIN_WINDOW = config.NO_BARGEIN_WINDOW
    BARGEIN_HOLD = config.BARGEIN_HOLD

    POST_TTS_IGNORE = config.POST_TTS_IGNORE
    MIN_WORDS = config.MIN_WORDS
    DUPLICATE_WINDOW = config.DUPLICATE_WINDOW
    COMPLETION_WAIT = config.COMPLETION_WAIT
    
    # LLM processing timeout - ignore filler speech during this window
    LLM_PROCESSING_TIMEOUT = config.LLM_PROCESSING_TIMEOUT
    # Only filter phrases that are clearly "checking if anyone is there" type filler
    # Don't filter yes/no/okay as those could be legitimate responses
    FILLER_PHRASES = {
        "hello", "hi", "hey",
        "are you there", "you there", "anyone there", 
        "hello?", "hi?", "hey?",
        "um", "uh", "hmm", "hm",
        "can you hear me", "you hear me",
    }

    bargein_since = 0.0

    # Debug energy
    DEBUG_ENERGY = False  # Set to True to see energy values
    debug_countdown = 250

    async def clear_twilio_audio():
        """Clear Twilio audio buffer"""
        if stream_sid:
            try:
                await ws.send(json.dumps({"event": "clear", "streamSid": stream_sid}))
            except Exception:
                pass

    async def start_tts(text_stream, label="tts"):
        """
        Start TTS streaming
        
        Args:
            text_stream: Async iterator of text tokens
            label: Label for logging
        """
        nonlocal speaking, interrupt, respond_task, tts_started_at, tts_ended_at, llm_processing, queued_speech

        async def run():
            nonlocal speaking, tts_started_at, tts_ended_at, call_sid, conversation_log, llm_processing, queued_speech, conversation, tool_execution_in_progress, continuation_window_start, continuation_original_text, continuation_energy_since, continuation_recovery_mode, continuation_base_text, current_response_timing, response_timing_details, response_times
            speaking = True
            interrupt = False
            tts_started_at = asyncio.get_event_loop().time()
            run_start = time_module.time()
            print(f"\n{'='*60}")
            print(f"🗣️ [TTS_START] Starting TTS session: {label}")
            print(f"   Timestamp: {run_start:.3f}")
            print(f"{'='*60}")

            try:
                token_count = 0
                transfer_number = None
                full_text = ""  # Capture full text for logging
                MIN_TOKENS_BEFORE_INTERRUPT = config.MIN_TOKENS_BEFORE_INTERRUPT
                needs_continuation = False  # Track if we need a second TTS session
                used_prerecorded = False  # Track if we used pre-recorded audio
                
                # First TTS session - will speak either the full response OR just the checking message
                print(f"   📍 [FLOW] Phase 1: Getting first token from stream...")
                
                # Buffer for pre-fetched tokens during parallel execution
                prefetch_buffer = []
                prefetch_done = asyncio.Event()
                prefetch_task = None
                
                async def prefetch_remaining():
                    """Pre-fetch remaining tokens while TTS/audio plays the filler"""
                    nonlocal transfer_number, current_response_timing
                    prefetch_start = time_module.time()
                    try:
                        token_received = False
                        token_count_local = 0
                        print(f"\n   {'─'*50}")
                        print(f"   ⚡ [PREFETCH] === PREFETCH TASK STARTED ===")
                        print(f"   ⚡ [PREFETCH] Start time: {prefetch_start:.3f}")
                        print(f"   ⚡ [PREFETCH] This runs IN PARALLEL with audio playback")
                        print(f"   {'─'*50}")
                        
                        async for token in text_stream:
                            token_received = True
                            token_count_local += 1
                            token_time = time_module.time() - prefetch_start
                            
                            if token.startswith("<<<TRANSFER:"):
                                transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                                print(f"   📞 [PREFETCH] TRANSFER MARKER at {token_time:.3f}s: {transfer_number}")
                                continue
                            
                            # Parse timing markers
                            if token.startswith("<<<TIMING:"):
                                timing_data = token.replace("<<<TIMING:", "").replace(">>>", "")
                                print(f"   ⏱️ [PREFETCH] TIMING MARKER: {timing_data}")
                                # Parse timing data and add to current_response_timing
                                for pair in timing_data.split(","):
                                    if "=" in pair:
                                        key, value = pair.split("=", 1)
                                        try:
                                            # Convert ms to seconds for consistency
                                            if key.endswith("_ms"):
                                                current_response_timing[key.replace("_ms", "_time")] = float(value) / 1000
                                            else:
                                                current_response_timing[key] = value
                                        except:
                                            current_response_timing[key] = value
                                continue
                            
                            if token.startswith("<<<") and token.endswith(">>>"):
                                print(f"   🏷️ [PREFETCH] Control marker at {token_time:.3f}s: {token[:50]}")
                                continue
                            
                            prefetch_buffer.append(token)
                            
                            # Log first few tokens and then periodically
                            if token_count_local <= 5:
                                print(f"   ⚡ [PREFETCH] Token #{token_count_local} at {token_time:.3f}s: '{token[:40]}'")
                            elif token_count_local % 10 == 0:
                                print(f"   ⚡ [PREFETCH] Token #{token_count_local} at {token_time:.3f}s (buffered: {len(prefetch_buffer)})")
                        
                        if not token_received:
                            print(f"   ⚠️ [PREFETCH] WARNING: Received NO tokens from stream!")
                            print(f"   ⚠️ [PREFETCH] This means the LLM didn't generate any follow-up response")
                            
                    except Exception as e:
                        print(f"   ❌ [PREFETCH] ERROR: {e}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        prefetch_done.set()
                        total_time = time_module.time() - prefetch_start
                        print(f"\n   {'─'*50}")
                        print(f"   ⚡ [PREFETCH] === PREFETCH TASK COMPLETE ===")
                        print(f"   ⚡ [PREFETCH] Duration: {total_time:.3f}s")
                        print(f"   ⚡ [PREFETCH] Tokens buffered: {len(prefetch_buffer)}")
                        if prefetch_buffer:
                            preview = ''.join(prefetch_buffer)[:100]
                            print(f"   ⚡ [PREFETCH] Preview: '{preview}...'")
                        print(f"   {'─'*50}\n")
                
                # FAST PATH: Check for SPLIT_TTS marker FIRST, before any TTS
                # This allows us to send pre-recorded audio IMMEDIATELY
                first_token = None
                get_token_start = time_module.time()
                try:
                    print(f"   📍 [FLOW] Waiting for first token from LLM stream...")
                    async for token in text_stream:
                        # Skip timing markers, but parse them
                        if token.startswith("<<<TIMING:"):
                            timing_data = token.replace("<<<TIMING:", "").replace(">>>", "")
                            print(f"   ⏱️ [FLOW] TIMING MARKER: {timing_data}")
                            for pair in timing_data.split(","):
                                if "=" in pair:
                                    key, value = pair.split("=", 1)
                                    try:
                                        if key.endswith("_ms"):
                                            current_response_timing[key.replace("_ms", "_time")] = float(value) / 1000
                                        else:
                                            current_response_timing[key] = value
                                    except:
                                        current_response_timing[key] = value
                            continue
                        first_token = token
                        break
                    get_token_time = time_module.time() - get_token_start
                    print(f"   📍 [FLOW] Got first token in {get_token_time:.3f}s: '{first_token[:60] if first_token else 'None'}...'")
                except Exception as e:
                    print(f"   ❌ [FLOW] Error getting first token: {e}")
                    first_token = None
                
                if first_token and first_token.startswith("<<<SPLIT_TTS:"):
                    split_msg = first_token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                    print(f"\n   {'='*50}")
                    print(f"   🔀 [FILLER] SPLIT_TTS MARKER DETECTED!")
                    print(f"   🔀 [FILLER] Filler message: '{split_msg}'")
                    print(f"   🔀 [FILLER] This triggers parallel execution:")
                    print(f"   🔀 [FILLER]   1. Play filler audio (instant)")
                    print(f"   🔀 [FILLER]   2. Prefetch LLM response (in background)")
                    print(f"   {'='*50}\n")
                    
                    # Mark that tool execution is in progress - unsafe to cancel/restart
                    tool_execution_in_progress = True
                    
                    # Try pre-recorded audio FIRST for instant playback
                    # Wrapped in try/except to NEVER fail - falls back to TTS
                    try:
                        has_fillers = has_prerecorded_fillers()
                        print(f"   📊 [FILLER] Checking pre-recorded fillers...")
                        print(f"   📊 [FILLER] has_prerecorded_fillers() = {has_fillers}")
                        
                        if has_fillers:
                            # Try to match the exact filler message first
                            filler_id = get_filler_id_from_message(split_msg)
                            if not filler_id:
                                # Fall back to random filler if no exact match
                                filler_id = get_random_filler_id()
                            filler_audio = get_filler_audio(filler_id)
                            audio_size = len(filler_audio) if filler_audio else 0
                            audio_duration_ms = audio_size / 8 if audio_size > 0 else 0  # 8 bytes per ms
                            
                            print(f"   📊 [FILLER] Selected filler: '{filler_id}'")
                            print(f"   📊 [FILLER] Audio size: {audio_size} bytes")
                            print(f"   📊 [FILLER] Audio duration: {audio_duration_ms:.0f}ms")
                            
                            if filler_audio and len(filler_audio) > 0:
                                parallel_start = time_module.time()
                                
                                # --- RECORD FIRST AUDIO TIMING ---
                                if current_response_timing:
                                    current_response_timing["first_audio_at"] = parallel_start
                                    current_response_timing["filler_played"] = True
                                    current_response_timing["filler_message"] = split_msg
                                    current_response_timing["filler_id"] = filler_id
                                    time_to_filler = parallel_start - current_response_timing.get("response_start_at", parallel_start)
                                    print(f"   ⏱️ [TIMING] Time from speech_final to filler: {time_to_filler:.3f}s")
                                
                                print(f"\n   {'─'*50}")
                                print(f"   ⚡ [PARALLEL] === STARTING PARALLEL EXECUTION ===")
                                print(f"   ⚡ [PARALLEL] Start time: {parallel_start:.3f}")
                                print(f"   ⚡ [PARALLEL] Mode: PRE-RECORDED AUDIO (instant)")
                                print(f"   ⚡ [PARALLEL] Audio: {filler_id} ({audio_duration_ms:.0f}ms)")
                                print(f"   {'─'*50}")
                                
                                async def send_audio_task():
                                    audio_start = time_module.time()
                                    print(f"   🔊 [AUDIO_TASK] Starting audio send at {audio_start:.3f}")
                                    try:
                                        await send_prerecorded_audio(ws, stream_sid, filler_audio)
                                        audio_duration = time_module.time() - audio_start
                                        print(f"   🔊 [AUDIO_TASK] ✓ Audio send complete in {audio_duration:.3f}s")
                                        print(f"   🔊 [AUDIO_TASK] Caller will hear audio for {audio_duration_ms:.0f}ms")
                                    except Exception as e:
                                        print(f"   🔊 [AUDIO_TASK] ⚠️ Error (non-fatal): {e}")
                                
                                # Start both tasks - audio FIRST for instant playback, then prefetch
                                print(f"   ⚡ [PARALLEL] Creating audio task (will send to Twilio)...")
                                audio_task = asyncio.create_task(send_audio_task())
                                
                                # Yield control so audio task can start immediately
                                await asyncio.sleep(0)
                                
                                print(f"   ⚡ [PARALLEL] Creating prefetch task (will run tool calls)...")
                                prefetch_task = asyncio.create_task(prefetch_remaining())
                                
                                print(f"   ⚡ [PARALLEL] Both tasks now running concurrently!")
                                print(f"   ⚡ [PARALLEL] Waiting for audio task to complete...")
                                
                                # Wait for audio to finish (prefetch continues in background)
                                try:
                                    await asyncio.wait_for(audio_task, timeout=5.0)
                                    print(f"   ⚡ [PARALLEL] Audio task finished successfully")
                                except asyncio.TimeoutError:
                                    print(f"   ⚠️ [PARALLEL] Audio send timeout after 5s (continuing anyway)")
                                except Exception as e:
                                    print(f"   ⚠️ [PARALLEL] Audio task error (non-fatal): {e}")
                                
                                parallel_duration = time_module.time() - parallel_start
                                print(f"\n   {'─'*50}")
                                print(f"   ⚡ [PARALLEL] Audio phase complete in {parallel_duration:.3f}s")
                                print(f"   ⚡ [PARALLEL] Prefetch task still running in background...")
                                print(f"   ⚡ [PARALLEL] Will wait for prefetch before continuation TTS")
                                print(f"   {'─'*50}\n")
                                
                                full_text += split_msg + " "
                                needs_continuation = True
                                used_prerecorded = True
                                first_token = None  # Consumed
                            else:
                                print(f"   ⚠️ [FILLER] No audio data for filler '{filler_id}'")
                                print(f"   ⚠️ [FILLER] Falling back to TTS...")
                                print(f"   ⚠️ No audio data for filler {filler_id} - falling back to TTS")
                        else:
                            print(f"   ⚠️ [FILLER] No pre-recorded fillers in cache")
                            print(f"   ⚠️ [FILLER] Falling back to TTS...")
                    except Exception as e:
                        # NEVER let pre-recorded audio crash the call
                        print(f"   ❌ [FILLER] Pre-recorded audio error: {e}")
                        print(f"   ❌ [FILLER] Falling back to TTS...")
                        import traceback
                        traceback.print_exc()
                        used_prerecorded = False
                
                # If we didn't use pre-recorded, fall back to TTS streaming
                if not used_prerecorded:
                    print(f"\n   {'─'*50}")
                    print(f"   📢 [TTS_FALLBACK] Using TTS for filler (no pre-recorded audio)")
                    print(f"   📢 [TTS_FALLBACK] This is slower but still works")
                    print(f"   📢 [TTS_FALLBACK] Filler + LLM work will run IN PARALLEL")
                    print(f"   {'─'*50}\n")
                    
                    # Record timing for TTS fallback
                    if current_response_timing:
                        current_response_timing["first_audio_at"] = time_module.time()
                        current_response_timing["filler_played"] = True
                        current_response_timing["filler_via_tts"] = True
                    
                    async def simple_stream_with_prefetch():
                        nonlocal token_count, speaking, transfer_number, full_text, needs_continuation, prefetch_task, first_token, current_response_timing
                        
                        # Yield the first token if we have one (and it wasn't a pre-recorded marker)
                        if first_token:
                            if first_token.startswith("<<<SPLIT_TTS:"):
                                # TTS fallback for filler
                                split_msg = first_token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                                print(f"   📢 [TTS_FALLBACK] Filler message: '{split_msg}'")
                                
                                # Record filler message for timing
                                if current_response_timing:
                                    current_response_timing["filler_message"] = split_msg
                                
                                # CRITICAL: Start prefetch BEFORE yielding to TTS
                                # This allows tool execution to happen in parallel with TTS
                                print(f"   📢 [TTS_FALLBACK] Starting prefetch task BEFORE TTS generation...")
                                print(f"   📢 [TTS_FALLBACK] Tool execution will run in parallel with TTS")
                                prefetch_task = asyncio.create_task(prefetch_remaining())
                                
                                # Now yield to TTS - prefetch runs in background
                                print(f"   📢 [TTS_FALLBACK] Yielding to TTS: '{split_msg}'")
                                yield split_msg
                                full_text += split_msg + " "
                                needs_continuation = True
                                print(f"   📢 [TTS_FALLBACK] TTS filler complete, will continue with prefetched content")
                                return  # Exit to let TTS speak, then continue
                            elif not first_token.startswith("<<<"):
                                token_count += 1
                                full_text += first_token
                                yield first_token
                        
                        async for token in text_stream:
                            # Check for SPLIT_TTS marker
                            if token.startswith("<<<SPLIT_TTS:"):
                                split_msg = token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                                print(f"   🔀 [TTS_FALLBACK] SPLIT_TTS mid-stream: '{split_msg}'")
                                
                                # Start prefetch BEFORE yielding
                                print(f"   🔀 [TTS_FALLBACK] Starting prefetch for mid-stream split...")
                                prefetch_task = asyncio.create_task(prefetch_remaining())
                                
                                yield split_msg
                                full_text += split_msg + " "
                                needs_continuation = True
                                break
                            
                            # Check for transfer marker
                            if token.startswith("<<<TRANSFER:"):
                                transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                                print(f"   📞 [TTS_FALLBACK] TRANSFER MARKER: {transfer_number}")
                                continue
                            
                            # Skip other control markers
                            if token.startswith("<<<") and token.endswith(">>>"):
                                print(f"   🏷️ [TTS_FALLBACK] Control marker: {token[:40]}")
                                continue
                            
                            token_count += 1
                            full_text += token
                            yield token
                            if token_count == MIN_TOKENS_BEFORE_INTERRUPT:
                                speaking = False
                                print(f"   ✅ [TTS_FALLBACK] Ready to listen (text streaming)")
                    
                    print(f"   📢 [TTS_FALLBACK] Starting TTS stream...")
                    tts_stream_start = time_module.time()
                    await asyncio.wait_for(
                        stream_tts(simple_stream_with_prefetch(), ws, stream_sid, lambda: interrupt),
                        timeout=config.TTS_TIMEOUT
                    )
                    tts_stream_duration = time_module.time() - tts_stream_start
                    print(f"   📢 [TTS_FALLBACK] TTS stream complete in {tts_stream_duration:.3f}s")
                    print(f"   ✅ [FLOW] First TTS session complete")
                
                # If we need continuation (due to SPLIT_TTS or pre-recorded), start a second TTS session
                if needs_continuation:
                    continuation_start = time_module.time()
                    
                    print(f"\n   {'='*50}")
                    print(f"   🔄 [CONTINUATION] === STARTING CONTINUATION PHASE ===")
                    print(f"   🔄 [CONTINUATION] Start time: {continuation_start:.3f}")
                    print(f"   🔄 [CONTINUATION] This speaks the actual LLM response")
                    print(f"   {'='*50}\n")
                    
                    token_count = 0  # Reset for second session
                    
                    # Wait for prefetch to complete (should be done or nearly done by now)
                    if prefetch_task:
                        try:
                            wait_start = time_module.time()
                            print(f"   ⏳ [CONTINUATION] Waiting for prefetch task to complete...")
                            print(f"   ⏳ [CONTINUATION] (Tool execution should be finishing now)")
                            await asyncio.wait_for(prefetch_done.wait(), timeout=15.0)
                            wait_duration = time_module.time() - wait_start
                            
                            print(f"\n   {'─'*50}")
                            print(f"   ✅ [CONTINUATION] Prefetch complete!")
                            print(f"   ✅ [CONTINUATION] Wait time: {wait_duration:.3f}s")
                            print(f"   ✅ [CONTINUATION] Tokens buffered: {len(prefetch_buffer)}")
                            if prefetch_buffer:
                                preview = ''.join(prefetch_buffer)[:150]
                                print(f"   ✅ [CONTINUATION] Response preview: '{preview}...'")
                            print(f"   {'─'*50}\n")
                            
                        except asyncio.TimeoutError:
                            print(f"   ⚠️ [CONTINUATION] Prefetch timeout after 15s!")
                            print(f"   ⚠️ [CONTINUATION] Continuing with {len(prefetch_buffer)} tokens available")
                    else:
                        print(f"   ⚠️ [CONTINUATION] No prefetch task was created!")
                    
                    # CRITICAL: If prefetch buffer is empty, add a fallback response
                    # This prevents the AI from going silent after "let me check"
                    if not prefetch_buffer:
                        print(f"   ⚠️ [CONTINUATION] EMPTY PREFETCH BUFFER!")
                        print(f"   ⚠️ [CONTINUATION] Adding fallback response to prevent silence")
                        prefetch_buffer.append("I've checked that for you. What would you like to do?")
                    
                    async def continuation_stream():
                        nonlocal token_count, speaking, transfer_number, full_text
                        print(f"   🔄 [CONTINUATION] Streaming {len(prefetch_buffer)} tokens to TTS...")
                        # First yield all pre-fetched tokens (these were gathered in parallel)
                        for i, token in enumerate(prefetch_buffer):
                            token_count += 1
                            full_text += token
                            yield token
                            if token_count == MIN_TOKENS_BEFORE_INTERRUPT:
                                speaking = False
                                print(f"   ✅ [CONTINUATION] Ready to listen after {token_count} tokens")
                        print(f"   🔄 [CONTINUATION] All {len(prefetch_buffer)} tokens yielded to TTS")
                    
                    # Second TTS session with the actual results (from prefetch buffer)
                    print(f"   🔄 [CONTINUATION] Starting TTS for continuation...")
                    await asyncio.wait_for(
                        stream_tts(continuation_stream(), ws, stream_sid, lambda: interrupt),
                        timeout=config.TTS_TIMEOUT
                    )
                    
                    continuation_duration = time_module.time() - continuation_start
                    print(f"\n   {'='*50}")
                    print(f"   ✅ [CONTINUATION] === CONTINUATION COMPLETE ===")
                    print(f"   ✅ [CONTINUATION] Duration: {continuation_duration:.3f}s")
                    print(f"   ✅ [CONTINUATION] Tokens spoken: {token_count}")
                    print(f"   {'='*50}\n")
                
                # Log the complete response
                if full_text.strip():
                    conversation_log.append({
                        "role": "assistant",
                        "content": full_text.strip(),
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    print(f"\n{'='*80}")
                    print(f"🤖 RECEPTIONIST: {full_text.strip()}")
                    print(f"{'='*80}\n")
                
                # After TTS completes, check if transfer was requested
                if transfer_number:
                    print(f"📞 INITIATING CALL TRANSFER TO: {transfer_number}")
                    # Use Twilio REST API to redirect/transfer the call
                    try:
                        # Import Twilio client
                        from twilio.rest import Client
                        import os
                        
                        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
                        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
                        
                        if account_sid and auth_token and call_sid:
                            client = Client(account_sid, auth_token)
                            
                            # Update the call to redirect to a new TwiML that dials the transfer number
                            # We'll use the existing /twilio/transfer endpoint
                            from urllib.parse import quote
                            
                            # URL-encode the phone number to handle special characters
                            encoded_number = quote(transfer_number)
                            transfer_url = f"{config.PUBLIC_URL}/twilio/transfer?number={encoded_number}"
                            
                            print(f"📞 Updating call {call_sid} to transfer URL: {transfer_url}")
                            
                            call = client.calls(call_sid).update(
                                url=transfer_url,
                                method='POST'
                            )
                            
                            print(f"✅ Call transfer initiated successfully to {transfer_number}")
                        else:
                            print("⚠️ Missing Twilio credentials or call SID - cannot complete transfer")
                            print(f"   Account SID: {'set' if account_sid else 'missing'}")
                            print(f"   Auth Token: {'set' if auth_token else 'missing'}")
                            print(f"   Call SID: {call_sid if call_sid else 'missing'}")
                            # NOTE: If transfer fails, the call continues normally with AI.
                            # The user already heard "Transferring you now" but call stays with AI.
                            # This is logged for debugging. Consider adding fallback TTS message.
                        
                    except Exception as transfer_error:
                        print(f"❌ Transfer error: {transfer_error}")
                        import traceback
                        traceback.print_exc()
                
            except asyncio.TimeoutError:
                print("⏱️ TTS timeout -> forcing end")
            except asyncio.CancelledError:
                print("🛑 TTS cancelled")
            except Exception as e:
                print(f"❌ TTS error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                finally_start = time_module.time()
                # Cancel prefetch task if still running (cleanup on interrupt/error)
                if prefetch_task and not prefetch_task.done():
                    print(f"   🧹 [CLEANUP] Cancelling prefetch task...")
                    prefetch_task.cancel()
                    try:
                        await prefetch_task
                    except asyncio.CancelledError:
                        pass
                    cleanup_duration = time_module.time() - finally_start
                    print(f"   🧹 Prefetch task cleaned up in {cleanup_duration:.3f}s")
                
                tts_ended_at = asyncio.get_event_loop().time()
                duration = tts_ended_at - tts_started_at
                finally_duration = time_module.time() - finally_start
                print(f"   🧹 [CLEANUP] Finally block took {finally_duration:.3f}s")
                speaking = False
                interrupt = False  # Reset interrupt flag
                llm_processing = False  # LLM response complete
                tool_execution_in_progress = False  # Tool execution complete
                
                # IMPORTANT: Only clear continuation window state if NOT in recovery mode
                # If we're in recovery mode, we were interrupted and need to keep the base text
                # for combining with the new speech
                if not continuation_recovery_mode:
                    continuation_window_start = 0.0
                    continuation_original_text = ""
                    continuation_energy_since = 0.0
                    # Don't clear continuation_base_text here - it's needed for recovery
                
                # Process any queued speech that came in during LLM processing
                if queued_speech:
                    combined_queued = " ".join(queued_speech)
                    print(f"📬 Processing queued speech after TTS: '{combined_queued}'")
                    # Add to conversation so it's included in context for next response
                    # But first check for duplicates - the same text might have been processed already
                    if len(combined_queued.split()) >= 2:  # At least 2 words
                        # Check if this is a duplicate of the last user message
                        is_queued_duplicate = False
                        if conversation:
                            # Find the last user message
                            for msg in reversed(conversation):
                                if msg.get('role') == 'user':
                                    last_user_content = msg.get('content', '')
                                    # Check exact match or fingerprint match
                                    if norm_text(combined_queued) == norm_text(last_user_content):
                                        is_queued_duplicate = True
                                        print(f"📬 Queued speech is duplicate of last user message, skipping")
                                    elif content_fingerprint(combined_queued) == content_fingerprint(last_user_content):
                                        is_queued_duplicate = True
                                        print(f"📬 Queued speech is fingerprint duplicate, skipping")
                                    break
                        
                        if not is_queued_duplicate:
                            conversation.append({"role": "user", "content": combined_queued})
                            conversation_log.append({
                                "role": "user",
                                "content": combined_queued,
                                "timestamp": asyncio.get_event_loop().time()
                            })
                            print(f"📬 Added queued speech to conversation")
                    queued_speech.clear()
                
                # Signal end immediately so user can speak
                print(f"🛑 TTS end ({label}) - duration: {duration:.2f}s")
                print(f"👂 Ready to receive audio again (speaking={speaking}, llm_processing={llm_processing})")
                
                # --- RECORD RESPONSE TIMING ---
                if current_response_timing and label == "respond":
                    response_end_time = time_module.time()
                    current_response_timing["response_end_at"] = response_end_time
                    current_response_timing["total_response_time"] = response_end_time - current_response_timing.get("response_start_at", response_end_time)
                    current_response_timing["tts_duration"] = duration
                    
                    # Calculate time to first audio (filler or actual response)
                    if current_response_timing.get("first_audio_at"):
                        current_response_timing["time_to_first_audio"] = current_response_timing["first_audio_at"] - current_response_timing["response_start_at"]
                    
                    response_timing_details.append(current_response_timing.copy())
                    response_times.append(current_response_timing["total_response_time"])
                    
                    print(f"\n⏱️ [RESPONSE_TIMING] Turn {current_response_timing['turn']} COMPLETE:")
                    print(f"   📝 User said: '{current_response_timing.get('user_text', 'N/A')}'")
                    print(f"   ⏱️ Total response time: {current_response_timing['total_response_time']:.3f}s")
                    if current_response_timing.get("time_to_first_audio"):
                        print(f"   🔊 Time to first audio: {current_response_timing['time_to_first_audio']:.3f}s")
                    if current_response_timing.get("filler_played"):
                        print(f"   💬 Filler played: '{current_response_timing.get('filler_message', 'N/A')}'")
                    print(f"   🗣️ TTS duration: {duration:.2f}s")
                    current_response_timing.clear()  # Use .clear() instead of reassignment
                # Small delay to ensure audio actually finished playing
                await asyncio.sleep(0.1)

        if respond_task and not respond_task.done():
            respond_task.cancel()

        respond_task = asyncio.create_task(run())

    async def greet():
        """Send initial greeting - uses pre-recorded audio if available for instant playback"""
        nonlocal speaking, stream_sid
        import time as time_module
        greet_start = time_module.time()
        
        greeting_text = "Hi, thank you for calling. How can I help you today?"
        
        print(f"\n{'='*80}")
        print(f"🤖 [GREETING] Starting greeting at {greet_start:.3f}")
        print(f"🤖 RECEPTIONIST (GREETING): {greeting_text}")
        print(f"{'='*80}\n")
        conversation_log.append({
            "role": "assistant",
            "content": greeting_text,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Try pre-recorded greeting first for instant playback
        try:
            prerecord_check_start = time_module.time()
            has_fillers = has_prerecorded_fillers()
            prerecord_check_time = time_module.time() - prerecord_check_start
            print(f"[GREETING] Pre-recorded check took {prerecord_check_time:.3f}s, has_fillers={has_fillers}")
            
            if has_fillers:
                audio_fetch_start = time_module.time()
                greeting_audio = get_filler_audio("greeting")
                audio_fetch_time = time_module.time() - audio_fetch_start
                print(f"[GREETING] Audio fetch took {audio_fetch_time:.3f}s, size={len(greeting_audio) if greeting_audio else 0} bytes")
                
                if greeting_audio and len(greeting_audio) > 0 and stream_sid:
                    send_start = time_module.time()
                    print(f"[GREETING] Using pre-recorded greeting ({len(greeting_audio)} bytes)")
                    await send_prerecorded_audio(ws, stream_sid, greeting_audio)
                    send_time = time_module.time() - send_start
                    total_greet_time = time_module.time() - greet_start
                    print(f"[GREETING] ✅ Pre-recorded send took {send_time:.3f}s, total greeting time: {total_greet_time:.3f}s")
                    speaking = False  # Ready to listen immediately
                    return
        except Exception as e:
            print(f"[GREETING] Pre-recorded greeting failed, falling back to TTS: {e}")
        
        # Fallback to TTS
        tts_start = time_module.time()
        print(f"[GREETING] Falling back to TTS at {tts_start:.3f}")
        async def tokens():
            yield greeting_text
        await start_tts(tokens(), label="greet")
        tts_time = time_module.time() - tts_start
        total_greet_time = time_module.time() - greet_start
        print(f"[GREETING] TTS greeting took {tts_time:.3f}s, total greeting time: {total_greet_time:.3f}s")

    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
                event = data.get("event")
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON decode error: {e}")
                continue
            except Exception as e:
                print(f"⚠️ Error parsing message: {e}")
                continue

            if event == "start":
                event_start_time = time_module.time()
                time_since_call_start = event_start_time - call_start_time
                print(f"\n[TIMING] 'start' event received {time_since_call_start:.3f}s after WS connect")
                
                stream_sid = data["start"]["streamSid"]
                # Extract caller phone number and company ID from Twilio metadata
                call_sid = data["start"].get("callSid", "")
                custom_parameters = data["start"].get("customParameters", {})
                caller_phone = custom_parameters.get("From", "") or data["start"].get("from", "")
                company_id = custom_parameters.get("CompanyId", "") or None
                
                print("🎧 start streamSid:", stream_sid)
                print("📞 Call SID:", call_sid)
                print("📱 Caller phone:", caller_phone if caller_phone else "Not available")
                print("🏢 Company ID:", company_id if company_id else "Not available")

                # Format phone number for display (e.g., +353851234567 -> 085 123 4567)
                formatted_phone = caller_phone
                if caller_phone:
                    if caller_phone.startswith('+353'):
                        # Irish number: +353851234567 -> 085 123 4567
                        local_num = '0' + caller_phone[4:]
                        if len(local_num) == 10:
                            formatted_phone = f"{local_num[:3]} {local_num[3:6]} {local_num[6:]}"
                    elif len(caller_phone) == 10 and caller_phone.startswith('0'):
                        formatted_phone = f"{caller_phone[:3]} {caller_phone[3:6]} {caller_phone[6:]}"
                
                # Build phone number instruction - always use caller's number first
                if caller_phone:
                    phone_instruction = (
                        f"PHONE NUMBER: The caller's phone number is {formatted_phone}. "
                        f"When you need their phone number, say: 'I have your number as {formatted_phone}. Is that the best number to reach you?' "
                        "If they say YES, use that number - DO NOT ask again. "
                        "If they say NO, ask: 'What number would you prefer?' and read it back digit by digit to confirm."
                    )
                else:
                    phone_instruction = (
                        "PHONE NUMBER: Could not detect caller's number. "
                        "Ask: 'What's the best phone number to reach you?' and read it back digit by digit."
                    )

                # Inform the LLM that greeting has already been sent to avoid re-introduction
                conversation.append({
                    "role": "system",
                    "content": (
                        "[SYSTEM: Initial greeting has ALREADY been delivered: 'Hi, thank you for calling. How can I help you today?' "
                        "The caller has ALREADY been asked how you can help - DO NOT ask 'how can I help' or 'what can I help with' again. "
                        "Do NOT reintroduce the business or say 'thanks for calling'. Keep replies short. "
                        "NEVER REPEAT QUESTIONS - if you've asked something, don't ask it again. "
                        "If they describe their issue, acknowledge it and ask for their NAME (only ask once). "
                        "CRITICAL - NAME SPELLING: After they give their name, you MUST spell it back letter-by-letter: "
                        "'Just to confirm, that's J-O-H-N S-M-I-T-H, is that right?' Wait for YES before calling lookup_customer. "
                        "If they ask to book, respond briefly: 'Sure, no problem! What day and time works best for you?'. "
                        f"{phone_instruction} "
                        "ADDRESS: Prefer eircode - ask 'Do you know your eircode?' first. If not, get full address. ALWAYS read back addresses and eircodes to confirm. "
                        "CRITICAL: Say things ONCE only - never repeat questions, booking confirmations, goodbyes, or 'thanks for calling'. After confirming a booking, just ask 'Anything else?' once.]"
                    )
                })
                
                greet_task_start = time_module.time()
                time_to_greet = greet_task_start - call_start_time
                print(f"\n[TIMING] ⏱️ Starting greeting task {time_to_greet:.3f}s after call start")
                asyncio.create_task(greet())
                
                # WARMUP: Start OpenAI streaming warmup in parallel with greeting
                # This ensures the streaming connection is hot when we need it
                async def warmup_openai():
                    try:
                        from src.services.llm_stream import get_openai_client
                        client = get_openai_client()
                        warmup_start = time_module.time()
                        
                        # Use streaming to warm up the same path as actual calls
                        def do_warmup():
                            stream = client.chat.completions.create(
                                model=config.CHAT_MODEL,
                                messages=[{"role": "user", "content": "hi"}],
                                max_tokens=1,
                                stream=True,
                                temperature=0.1,
                            )
                            for _ in stream:
                                pass
                        
                        await asyncio.to_thread(do_warmup)
                        warmup_time = time_module.time() - warmup_start
                        print(f"🔥 [WARMUP] OpenAI streaming warmed up in {warmup_time:.2f}s")
                    except Exception as e:
                        print(f"⚠️ [WARMUP] OpenAI warmup failed: {e}")
                
                asyncio.create_task(warmup_openai())

            elif event == "media":
                if not stream_sid:
                    continue

                audio = base64.b64decode(data["media"]["payload"])
                energy = ulaw_energy(audio)
                now = asyncio.get_event_loop().time()
                last_audio_time = now  # Update watchdog

                # Watchdog: if we've been speaking for too long without any user audio processed, reset
                if speaking and (now - tts_started_at) > 25.0:  # 25 seconds max
                    print("⚠️ WATCHDOG: Speaking timeout - forcing reset")
                    speaking = False
                    interrupt = False
                    if respond_task and not respond_task.done():
                        respond_task.cancel()
                    await clear_twilio_audio()

                if DEBUG_ENERGY and debug_countdown > 0:
                    debug_countdown -= 1
                    print(f"⚡ energy={int(energy)} speaking={speaking}")

                # ---- While speaking: barge-in only ----
                if speaking:
                    # --- COMPLETION_WAIT WINDOW: Check FIRST, before NO_BARGEIN_WINDOW ---
                    # This is the parallel window that started when speech_final triggered
                    # If caller continues speaking, cancel response and restart with combined text
                    # IMPORTANT: This must be checked BEFORE NO_BARGEIN_WINDOW because:
                    # - COMPLETION_WAIT is for caller continuing their sentence (not a barge-in)
                    # - NO_BARGEIN_WINDOW blocks ALL interruptions including legitimate continuations
                    # - Without this order, COMPLETION_WAIT only has 0.5s effective window (2.0s - 1.5s)
                    # IMPORTANT: Don't allow cancellation during tool execution (could corrupt data)
                    in_completion_wait_window = (
                        continuation_window_start > 0 and 
                        (now - continuation_window_start) <= COMPLETION_WAIT and
                        continuation_original_text and  # Must have original text to append to
                        not tool_execution_in_progress  # Don't cancel during tool execution
                    )
                    
                    # Debug: Log when we're in the COMPLETION_WAIT window
                    if continuation_window_start > 0:
                        time_in_window = now - continuation_window_start
                        if time_in_window <= COMPLETION_WAIT and energy > SPEECH_ENERGY:
                            print(f"🔍 [COMPLETION_WAIT] In window: {time_in_window:.2f}s/{COMPLETION_WAIT}s, energy={energy}, tool_exec={tool_execution_in_progress}")
                    
                    if in_completion_wait_window:
                        # During COMPLETION_WAIT window, use lower threshold and check for real speech
                        if energy > SPEECH_ENERGY:  # Lower threshold than normal barge-in
                            if continuation_energy_since == 0.0:
                                continuation_energy_since = now
                            elif (now - continuation_energy_since) >= 0.15:  # 150ms sustained speech
                                # Feed audio and check ASR for real words
                                await asr.feed(audio)
                                interim_check = asr.get_interim()
                                words = interim_check.strip().split()
                                
                                # Require at least 1 word and 3 characters (not just noise)
                                # Also check it's different from what triggered the original response
                                is_new_speech = (
                                    len(words) >= 1 and 
                                    len(interim_check.strip()) >= 3 and
                                    norm_text(interim_check) != norm_text(continuation_original_text)
                                )
                                
                                if is_new_speech:
                                    # This is real NEW speech during COMPLETION_WAIT window!
                                    # Cancel current response and restart with combined text
                                    print(f"\n🔄 [COMPLETION_WAIT] Speech detected within {COMPLETION_WAIT}s window - restarting!")
                                    print(f"   Original text: '{continuation_original_text}'")
                                    print(f"   New speech: '{interim_check}'")
                                    
                                    # Cancel current response
                                    await clear_twilio_audio()
                                    if respond_task and not respond_task.done():
                                        respond_task.cancel()
                                    speaking = False
                                    tts_ended_at = now
                                    llm_processing = False
                                    
                                    # Reset continuation tracking
                                    continuation_energy_since = 0.0
                                    
                                    # DON'T clear ASR - let it continue building the transcript
                                    # Deepgram will send speech_final when caller finishes
                                    
                                    # Set recovery mode - we'll prepend the original text when response triggers
                                    continuation_recovery_mode = True
                                    continuation_base_text = continuation_original_text
                                    
                                    # Remove the last user message from conversation (we'll re-add with combined text)
                                    if conversation and conversation[-1].get('role') == 'user':
                                        conversation.pop()
                                    
                                    # Clear last_committed to prevent duplicate detection on combined text
                                    last_committed = ""
                                    
                                    print(f"   Base text saved: '{continuation_base_text}'")
                                    print(f"   Waiting for caller to finish speaking...")
                                    
                                    # Clear continuation window state
                                    continuation_window_start = 0.0
                                    continuation_original_text = ""
                                    
                                    continue
                        else:
                            continuation_energy_since = 0.0
                        
                        # During COMPLETION_WAIT window, still feed audio to ASR
                        await asr.feed(audio)
                        continue
                    
                    # --- Normal barge-in checks (only after COMPLETION_WAIT window has passed) ---
                    # These checks prevent false barge-ins from echo/feedback
                    # They are placed AFTER COMPLETION_WAIT so they don't block legitimate continuations
                    
                    # Don't allow interruption in critical first moments (prevents echo triggering)
                    if (now - tts_started_at) <= NO_BARGEIN_WINDOW:
                        continue
                    
                    # Cooldown: don't allow rapid consecutive interruptions
                    if last_interrupt_time > 0 and (now - last_interrupt_time) < INTERRUPT_COOLDOWN:
                        continue
                    
                    # --- Normal barge-in (after COMPLETION_WAIT window) ---
                    # At this point, COMPLETION_WAIT has expired, so any interruption is a real barge-in
                    # If too many consecutive interrupts, require longer sustained speech
                    required_hold = BARGEIN_HOLD
                    if interrupt_count >= MAX_CONSECUTIVE_INTERRUPTS:
                        required_hold = BARGEIN_HOLD * 2  # Double the hold time required

                    # Require sustained high energy for interruption
                    if energy > INTERRUPT_ENERGY:
                        if bargein_since == 0.0:
                            bargein_since = now
                        elif (now - bargein_since) >= required_hold:
                            # Additional check: ensure this isn't just noise
                            await asr.feed(audio)
                            interim_check = asr.get_interim()
                            # Require substantial speech (at least 5 characters or a recognizable word)
                            words = interim_check.strip().split()
                            min_words_for_interrupt = 2 if interrupt_count >= MAX_CONSECUTIVE_INTERRUPTS else 1
                            if len(words) >= min_words_for_interrupt and len(interim_check.strip()) >= 3:
                                # Track what we were saying when interrupted
                                interrupted_text = last_committed if last_committed else ""
                                interrupt = True
                                interrupt_count += 1
                                last_interrupt_time = now
                                print(f"✋ legitimate interrupt triggered: '{interim_check}' (interrupt #{interrupt_count})")
                                await clear_twilio_audio()
                                if respond_task and not respond_task.done():
                                    respond_task.cancel()
                                speaking = False
                                tts_ended_at = now
                                bargein_since = 0.0
                                
                                # Clear continuation window state on normal interrupt
                                continuation_window_start = 0.0
                                continuation_original_text = ""
                            else:
                                # Reset if not real speech
                                bargein_since = 0.0
                    else:
                        bargein_since = 0.0
                    continue

                # ---- Ignore tail right after TTS ends ----
                if (now - tts_ended_at) < POST_TTS_IGNORE:
                    continue

                # ---- CONTINUATION CHECK DURING LLM PROCESSING (COMPLETION_WAIT window) ----
                # Flow: Caller speaks -> Deepgram speech_final -> start generating response
                # COMPLETION_WAIT (2s) runs IN PARALLEL with response generation
                # If caller speaks within COMPLETION_WAIT, cancel response, combine texts, restart
                #
                # This catches the case where caller pauses mid-sentence and continues before AI responds
                # Example: "I need to book..." [pause] "...an appointment for Tuesday"
                # IMPORTANT: Don't cancel during tool execution (could corrupt data)
                if llm_processing and not speaking and continuation_window_start > 0 and not tool_execution_in_progress:
                    time_since_generation_started = now - continuation_window_start
                    
                    # COMPLETION_WAIT is the window where we allow caller to continue
                    if time_since_generation_started <= COMPLETION_WAIT:
                        # Always feed audio to ASR during COMPLETION_WAIT window so we don't miss speech
                        await asr.feed(audio)
                        
                        # We're in the COMPLETION_WAIT window - check for new speech
                        if energy > SPEECH_ENERGY:
                            if continuation_energy_since == 0.0:
                                continuation_energy_since = now
                            elif (now - continuation_energy_since) >= 0.15:  # 150ms sustained speech
                                # Check ASR for real words (not just noise)
                                interim_check = asr.get_interim()
                                words = interim_check.strip().split()
                                
                                # Require at least 1 word and 3 characters (not just noise)
                                # Also check it's different from what triggered the original response
                                is_new_speech = (
                                    len(words) >= 1 and 
                                    len(interim_check.strip()) >= 3 and
                                    norm_text(interim_check) != norm_text(continuation_original_text)
                                )
                                
                                if is_new_speech:
                                    # Caller is speaking during LLM generation!
                                    # Cancel the LLM and wait for them to finish
                                    print(f"\n🔄 [COMPLETION_WAIT] Speech detected during LLM generation!")
                                    print(f"   Time since response started: {time_since_generation_started:.2f}s (within {COMPLETION_WAIT}s window)")
                                    print(f"   Original text: '{continuation_original_text}'")
                                    print(f"   New speech detected: '{interim_check}'")
                                    
                                    # Cancel current LLM response
                                    if respond_task and not respond_task.done():
                                        respond_task.cancel()
                                        print(f"   ❌ Cancelled LLM task - will restart with combined text")
                                    
                                    llm_processing = False
                                    
                                    # Set recovery mode - we'll prepend the original text when new response triggers
                                    continuation_recovery_mode = True
                                    continuation_base_text = continuation_original_text
                                    
                                    # Remove the last user message (we'll re-add with combined text)
                                    if conversation and conversation[-1].get('role') == 'user':
                                        removed = conversation.pop()
                                        print(f"   Removed from conversation: '{removed.get('content', '')[:50]}...'")
                                    
                                    # Clear last_committed to prevent duplicate detection on combined text
                                    last_committed = ""
                                    
                                    # Clear continuation window state
                                    continuation_window_start = 0.0
                                    continuation_original_text = ""
                                    continuation_energy_since = 0.0
                                    
                                    print(f"   ✅ Waiting for Deepgram speech_final, then will combine texts and restart")
                                    # Continue - audio already fed, Deepgram will send speech_final when done
                                    continue
                        else:
                            continuation_energy_since = 0.0
                        
                        # Audio already fed above, continue to skip duplicate feed below
                        continue

                # ---- Feed audio to ASR ----
                await asr.feed(audio)
                
                # Get transcript for display
                interim = asr.get_interim()

                # ---- SIMPLIFIED: Trust Deepgram's speech_final signal ----
                # Deepgram's VAD handles:
                # - Multi-segment utterances (accumulates automatically)
                # - End-of-speech detection (speech_final after 800ms silence)
                # We just wait for speech_final=true before responding
                
                if asr.is_speech_finished():
                    text = asr.get_text().strip()
                    
                    # Skip if no text
                    if not text:
                        asr.clear()
                        continue
                    
                    # If in continuation recovery mode, prepend the base text
                    if continuation_recovery_mode and continuation_base_text:
                        if not norm_text(text).startswith(norm_text(continuation_base_text)):
                            text = continuation_base_text + " " + text
                            print(f"🔄 [CONTINUATION] Combined text: '{text}'")
                        continuation_recovery_mode = False
                        continuation_base_text = ""
                    
                    if len(text.split()) >= MIN_WORDS:
                        # Simple duplicate detection
                        is_duplicate = (
                            norm_text(text) == norm_text(last_committed) and last_committed
                        ) or (
                            content_fingerprint(text) == content_fingerprint(last_committed) and last_committed
                        )
                        
                        if not is_duplicate:
                            # Safety timeout for LLM processing flag
                            if llm_processing and (now - llm_started_at) > LLM_PROCESSING_TIMEOUT:
                                print(f"⚠️ LLM processing timeout - resetting")
                                llm_processing = False
                            
                            # Check for filler phrases during LLM processing
                            text_lower = text.lower().strip().rstrip('?.,!')
                            is_filler = text_lower in FILLER_PHRASES
                            
                            if llm_processing and is_filler:
                                print(f"🤫 Ignoring filler during LLM processing: '{text}'")
                                asr.clear()
                                continue
                            
                            # Queue substantial speech during LLM processing
                            if llm_processing and not is_filler:
                                # Check for duplicates before queuing
                                text_fp = content_fingerprint(text)
                                is_queue_dup = any(
                                    norm_text(text) == norm_text(q) or text_fp == content_fingerprint(q)
                                    for q in queued_speech
                                )
                                if not is_queue_dup:
                                    print(f"📝 Queuing speech during LLM processing: '{text}'")
                                    queued_speech.append(text)
                                asr.clear()
                                continue
                            
                            # Add interruption context if needed
                            if interrupt_count >= 2:
                                conversation.append({
                                    "role": "system",
                                    "content": f"[SYSTEM: Caller interrupted {interrupt_count} times. Keep response SHORT.]"
                                })
                            if interrupt_count > 0:
                                interrupt_count = 0
                            
                            # Log user speech
                            conversation_log.append({"role": "user", "content": text, "timestamp": now})
                            print(f"\n{'='*80}")
                            print(f"👤 CALLER: {text}")
                            print(f"{'='*80}\n")
                            
                            # Update state
                            last_committed = text
                            last_response_time = now
                            asr.clear()
                            
                            conversation.append({"role": "user", "content": text})
                            
                            # Trim conversation history if needed
                            MAX_HISTORY = 40
                            if len(conversation) > MAX_HISTORY + 1:
                                # Keep system message + recent messages
                                conversation[:] = [conversation[0]] + conversation[-(MAX_HISTORY):]
                                print(f"📝 Trimmed conversation to {len(conversation)} messages")
                            
                            # --- START RESPONSE TIMING ---
                            # Use .clear() and .update() instead of reassignment to preserve nonlocal binding
                            current_response_timing.clear()
                            current_response_timing.update({
                                "turn": len(response_timing_details) + 1,
                                "user_text": text[:50] + "..." if len(text) > 50 else text,
                                "speech_final_at": now,
                                "response_start_at": time_module.time(),
                            })
                            
                            # Start LLM response
                            print(f"🔊 Starting LLM response")
                            print(f"⏱️ [RESPONSE_TIMING] Turn {current_response_timing['turn']} started at {current_response_timing['response_start_at']:.3f}")
                            llm_processing = True
                            llm_started_at = now
                            queued_speech.clear()
                            
                            # Set continuation window
                            continuation_window_start = now
                            continuation_original_text = text
                            
                            try:
                                await start_tts(
                                    stream_llm(conversation, process_appointment_with_calendar, 
                                              caller_phone=caller_phone, company_id=company_id, call_state=call_state),
                                    label="respond"
                                )
                            except Exception as e:
                                print(f"❌ Error starting response: {e}")
                                llm_processing = False
                                queued_speech.clear()
                                speaking = False
                                continuation_window_start = 0.0
                        else:
                            # Duplicate - skip
                            asr.clear()
                    else:
                        # Not enough words - skip
                        asr.clear()

            elif event == "stop":
                print("🛑 stop")
                break
            elif event == "mark":
                pass
            else:
                if event:
                    print(f"❓ Unknown event: {event}")

    except websockets.ConnectionClosed as e:
        print(f"⚠️ Twilio WS disconnected: {e}")
    except Exception as e:
        print(f"❌ Unexpected error in media handler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Calculate total call duration
        call_end_time = time_module.time()
        total_call_duration = call_end_time - call_start_time
        
        # Print conversation summary
        print(f"\n\n{'#'*80}")
        print(f"📊 CALL SUMMARY")
        print(f"{'#'*80}")
        print(f"📞 Call SID: {call_sid}")
        print(f"📱 Caller: {caller_phone}")
        print(f"🏢 Company ID: {company_id}")
        print(f"⏱️ Total call duration: {total_call_duration:.2f}s")
        print(f"🔢 Total messages: {len(conversation_log)}")
        print(f"\n📝 FULL CONVERSATION TRANSCRIPT:")
        print(f"{'-'*80}")
        for i, msg in enumerate(conversation_log, 1):
            role_emoji = "👤" if msg['role'] == 'user' else "🤖"
            role_name = "CALLER" if msg['role'] == 'user' else "RECEPTIONIST"
            print(f"\n[{i}] {role_emoji} {role_name}: {msg['content']}")
        print(f"\n{'-'*80}")
        
        if response_times:
            avg_response = sum(response_times) / len(response_times)
            print(f"\n⏱️ RESPONSE TIME STATS:")
            print(f"   Average: {avg_response:.2f}s")
            print(f"   Fastest: {min(response_times):.2f}s")
            print(f"   Slowest: {max(response_times):.2f}s")
        
        # --- DETAILED TIMING BREAKDOWN ---
        if response_timing_details:
            print(f"\n{'='*80}")
            print(f"⏱️ DETAILED RESPONSE TIMING BREAKDOWN")
            print(f"{'='*80}")
            for timing in response_timing_details:
                print(f"\n📍 Turn {timing.get('turn', '?')}: \"{timing.get('user_text', 'N/A')}\"")
                print(f"   ├─ Total response time: {timing.get('total_response_time', 0):.3f}s")
                if timing.get('time_to_first_audio'):
                    print(f"   ├─ Time to first audio: {timing.get('time_to_first_audio', 0):.3f}s")
                if timing.get('filler_played'):
                    print(f"   ├─ Filler played: '{timing.get('filler_message', 'N/A')}' (ID: {timing.get('filler_id', 'N/A')})")
                if timing.get('precheck_time'):
                    print(f"   ├─ Pre-check analysis: {timing.get('precheck_time', 0)*1000:.1f}ms")
                if timing.get('openai_first_token_time'):
                    print(f"   ├─ OpenAI first token: {timing.get('openai_first_token_time', 0):.3f}s")
                if timing.get('tool_execution_time'):
                    print(f"   ├─ Tool execution: {timing.get('tool_execution_time', 0):.3f}s")
                if timing.get('tts_duration'):
                    print(f"   └─ TTS duration: {timing.get('tts_duration', 0):.2f}s")
            
            # Identify slowest components
            print(f"\n🔍 PERFORMANCE ANALYSIS:")
            slow_responses = [t for t in response_timing_details if t.get('total_response_time', 0) > 2.0]
            if slow_responses:
                print(f"   ⚠️ {len(slow_responses)} responses took >2s:")
                for t in slow_responses:
                    print(f"      - Turn {t.get('turn')}: {t.get('total_response_time', 0):.2f}s - \"{t.get('user_text', 'N/A')}\"")
            else:
                print(f"   ✅ All responses under 2s - good performance!")
            
            # Check for missing fillers
            no_filler_responses = [t for t in response_timing_details if not t.get('filler_played') and t.get('total_response_time', 0) > 1.0]
            if no_filler_responses:
                print(f"   ⚠️ {len(no_filler_responses)} slow responses had NO filler:")
                for t in no_filler_responses:
                    print(f"      - Turn {t.get('turn')}: {t.get('total_response_time', 0):.2f}s - \"{t.get('user_text', 'N/A')}\"")
            print(f"{'='*80}")
        
        # Generate and save call summary to job card
        if conversation_log and caller_phone:
            try:
                from src.services.call_summarizer import add_call_summary_to_booking
                print(f"\n📝 Generating call summary for job card...")
                company_id_int = int(company_id) if company_id else None
                summary_added = await add_call_summary_to_booking(
                    conversation_log=conversation_log,
                    caller_phone=caller_phone,
                    company_id=company_id_int
                )
                if summary_added:
                    print(f"✅ Call summary added to job card")
                else:
                    print(f"ℹ️ No job card updated (no booking found or no job content)")
            except Exception as summary_error:
                print(f"⚠️ Could not add call summary: {summary_error}")
        
        print(f"\n{'#'*80}\n\n")
        
        if respond_task and not respond_task.done():
            respond_task.cancel()
        await asr.close()
        print("✅ Deepgram closed")
