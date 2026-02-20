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
    
    # --- Continuation window (allows caller to continue after response starts) ---
    # If caller speaks within this window after response starts, cancel and restart with combined text
    CONTINUATION_WINDOW = config.CONTINUATION_WINDOW if hasattr(config, 'CONTINUATION_WINDOW') else 2.0
    continuation_window_start = 0.0  # When we started generating (for continuation check)
    continuation_original_text = ""  # The text that triggered generation
    continuation_energy_since = 0.0  # Track sustained energy for continuation detection
    continuation_recovery_mode = False  # True when we cancelled and are waiting for more speech
    continuation_base_text = ""  # The combined text to build upon during recovery
    tool_execution_in_progress = False  # True when LLM is executing tool calls (unsafe to cancel)
    
    # --- Pre-response interruption (during COMPLETION_WAIT) ---
    # If caller continues speaking during COMPLETION_WAIT, discard pending response and combine texts
    pre_response_pending = False  # True when we're in COMPLETION_WAIT and about to respond
    pre_response_text = ""  # The text that would trigger response
    pre_response_start = 0.0  # When we entered COMPLETION_WAIT

    # --- Speech segmentation with sentence-level detection ---
    in_speech = False
    silence_since = 0.0
    speech_start_time = 0.0
    pending_text = ""
    last_committed = ""
    last_interim = ""
    last_response_time = 0.0
    last_audio_time = 0.0  # Track last audio received for watchdog

    # --- Configurable Tunables (loaded from .env via config) ---
    SPEECH_ENERGY = config.SPEECH_ENERGY
    SILENCE_ENERGY = config.SILENCE_ENERGY
    SILENCE_HOLD = config.SILENCE_HOLD

    INTERRUPT_ENERGY = config.INTERRUPT_ENERGY
    NO_BARGEIN_WINDOW = config.NO_BARGEIN_WINDOW
    BARGEIN_HOLD = config.BARGEIN_HOLD

    POST_TTS_IGNORE = config.POST_TTS_IGNORE
    MIN_WORDS = config.MIN_WORDS
    DUPLICATE_WINDOW = config.DUPLICATE_WINDOW
    MIN_SPEECH_DURATION = config.MIN_SPEECH_DURATION
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
            nonlocal speaking, tts_started_at, tts_ended_at, call_sid, conversation_log, llm_processing, queued_speech, conversation, tool_execution_in_progress, continuation_window_start, continuation_original_text, continuation_energy_since, continuation_recovery_mode, continuation_base_text
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
                    nonlocal transfer_number
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
                                
                                # Start both tasks - prefetch first so it starts immediately
                                print(f"   ⚡ [PARALLEL] Creating prefetch task (will run tool calls)...")
                                prefetch_task = asyncio.create_task(prefetch_remaining())
                                
                                print(f"   ⚡ [PARALLEL] Creating audio task (will send to Twilio)...")
                                audio_task = asyncio.create_task(send_audio_task())
                                
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
                    print(f"   {'─'*50}\n")
                    
                    async def simple_stream_with_prefetch():
                        nonlocal token_count, speaking, transfer_number, full_text, needs_continuation, prefetch_task, first_token
                        
                        # Yield the first token if we have one (and it wasn't a pre-recorded marker)
                        if first_token:
                            if first_token.startswith("<<<SPLIT_TTS:"):
                                # TTS fallback for filler
                                split_msg = first_token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                                print(f"   📢 [TTS_FALLBACK] Filler message: '{split_msg}'")
                                
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
                    await asyncio.wait_for(
                        stream_tts(simple_stream_with_prefetch(), ws, stream_sid, lambda: interrupt),
                        timeout=config.TTS_TIMEOUT
                    )
                    print(f"   📢 [TTS_FALLBACK] TTS stream complete")
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
                # Cancel prefetch task if still running (cleanup on interrupt/error)
                if prefetch_task and not prefetch_task.done():
                    prefetch_task.cancel()
                    try:
                        await prefetch_task
                    except asyncio.CancelledError:
                        pass
                    print(f"   🧹 Prefetch task cleaned up")
                
                tts_ended_at = asyncio.get_event_loop().time()
                duration = tts_ended_at - tts_started_at
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
                    if len(combined_queued.split()) >= 2:  # At least 2 words
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
                    print(f"⚡ energy={int(energy)} speaking={speaking} in_speech={in_speech}")

                # ---- While speaking: barge-in only ----
                if speaking:
                    # Don't allow interruption in critical first moments
                    if (now - tts_started_at) <= NO_BARGEIN_WINDOW:
                        continue
                    
                    # Cooldown: don't allow rapid consecutive interruptions
                    if last_interrupt_time > 0 and (now - last_interrupt_time) < INTERRUPT_COOLDOWN:
                        continue
                    
                    # --- CONTINUATION WINDOW: If caller speaks within CONTINUATION_WINDOW after response starts ---
                    # Cancel response and restart with combined text
                    # Note: We use CONTINUATION_WINDOW (2.0s default) not COMPLETION_WAIT (0.2s)
                    # because the filler phrase takes ~1-2s to play
                    # IMPORTANT: Don't allow cancellation during tool execution (could corrupt data)
                    in_continuation_window = (
                        continuation_window_start > 0 and 
                        (now - continuation_window_start) <= CONTINUATION_WINDOW and
                        continuation_original_text and  # Must have original text to append to
                        not tool_execution_in_progress  # Don't cancel during tool execution
                    )
                    
                    if in_continuation_window:
                        # During continuation window, use lower threshold and check for real speech
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
                                    # This is real NEW speech during continuation window!
                                    # Cancel current response and restart with combined text
                                    print(f"\n🔄 [CONTINUATION] Speech detected within {CONTINUATION_WINDOW}s - restarting!")
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
                                    # The ASR will naturally include the continuation speech
                                    
                                    # Reset speech detection state to capture the rest
                                    in_speech = True
                                    silence_since = 0.0
                                    speech_start_time = now - 0.2  # Pretend speech started slightly earlier
                                    
                                    # Set recovery mode - we'll prepend the original text when response triggers
                                    continuation_recovery_mode = True
                                    continuation_base_text = continuation_original_text
                                    
                                    # Set pending_text to current ASR output (will be combined with base later)
                                    pending_text = interim_check
                                    
                                    # Remove the last user message from conversation (we'll re-add with combined text)
                                    if conversation and conversation[-1].get('role') == 'user':
                                        conversation.pop()
                                    
                                    print(f"   Base text saved: '{continuation_base_text}'")
                                    print(f"   Waiting for caller to finish speaking...")
                                    
                                    # Clear continuation window state
                                    continuation_window_start = 0.0
                                    continuation_original_text = ""
                                    
                                    continue
                        else:
                            continuation_energy_since = 0.0
                        
                        # During continuation window, still feed audio to ASR
                        await asr.feed(audio)
                        continue
                    
                    # --- Normal barge-in (after continuation window) ---
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

                # ---- Feed audio to ASR ----
                await asr.feed(audio)
                
                # Get transcript
                interim = asr.get_interim()
                final_text = asr.get_text()
                current_text = final_text if final_text else interim

                # Update pending text
                if current_text and current_text != last_interim:
                    last_interim = current_text
                    pending_text = current_text.strip()

                # ---- Speech detection with improved stability ----
                if energy > SPEECH_ENERGY:
                    if not in_speech:
                        in_speech = True
                        silence_since = 0.0
                        speech_start_time = now  # Track speech start

                    silence_since = 0.0
                    
                    # Check if we're in pre-response wait and caller started speaking again
                    if pre_response_pending and energy > SPEECH_ENERGY:
                        # Caller is continuing to speak during COMPLETION_WAIT
                        # Reset the wait and let them continue
                        print(f"🔄 [PRE-RESPONSE] Caller continuing during wait, resetting...")
                        pre_response_pending = False
                        # Keep pre_response_text - we'll combine it with new speech
                        # Don't reset speech state - let it continue building

                else:
                    # Low energy - check for silence
                    if in_speech:
                        if energy < SILENCE_ENERGY:
                            if silence_since == 0.0:
                                silence_since = now
                        else:
                            silence_since = 0.0

                        # TRIGGER RESPONSE after silence threshold AND minimum speech duration
                        if (silence_since and 
                            (now - silence_since) >= SILENCE_HOLD and
                            (now - speech_start_time) >= MIN_SPEECH_DURATION):
                            text = (final_text or pending_text).strip()
                            
                            # If we were in pre-response wait and got more speech, combine texts
                            if pre_response_text and text != pre_response_text:
                                # Check if the new text already contains the pre-response text
                                if not norm_text(text).startswith(norm_text(pre_response_text)):
                                    # New speech detected after pre-response wait - combine them
                                    combined = pre_response_text + " " + text
                                    print(f"🔄 [PRE-RESPONSE] Combined texts: '{pre_response_text}' + '{text}' = '{combined}'")
                                    text = combined
                                else:
                                    print(f"🔄 [PRE-RESPONSE] ASR already combined: '{text}'")
                                # Reset pre-response state
                                pre_response_pending = False
                                pre_response_text = ""
                                pre_response_start = 0.0
                            
                            # If in continuation recovery mode, prepend the base text
                            if continuation_recovery_mode and continuation_base_text:
                                # Check if ASR already included the base text (sometimes it does)
                                if not norm_text(text).startswith(norm_text(continuation_base_text)):
                                    text = continuation_base_text + " " + text
                                    print(f"🔄 [CONTINUATION] Combined text: '{text}'")
                                # Reset recovery mode
                                continuation_recovery_mode = False
                                continuation_base_text = ""
                            
                            if text and len(text.split()) >= MIN_WORDS:
                                # Check if sentence appears complete
                                is_complete_thought = (
                                    text.endswith(('.', '!', '?')) or
                                    len(text.split()) >= 4 or  # Longer phrases are usually complete
                                    any(word in text.lower() for word in ['yes', 'no', 'okay', 'thanks', 'hello', 'help'])
                                )
                                
                                # If not complete, wait a bit more unless it's been too long
                                if not is_complete_thought and (now - silence_since) < (SILENCE_HOLD + COMPLETION_WAIT):
                                    # Don't wait - start generating but track we're in early response window
                                    # If caller speaks within COMPLETION_WAIT, we'll cancel and restart
                                    pass  # Fall through to start response
                                
                                # Enhanced duplicate detection
                                is_duplicate = False
                                
                                # Check for exact match with last committed (regardless of time window)
                                # This catches echo/feedback issues where the same text appears again
                                if norm_text(text) == norm_text(last_committed) and last_committed:
                                    is_duplicate = True
                                    print(f"🔄 Duplicate detected (exact match with last): '{text}'")
                                
                                # Check for content fingerprint match (catches "v 9 5" vs "v95" duplicates)
                                # This handles cases where ASR transcribes the same speech with different spacing
                                if not is_duplicate and last_committed:
                                    text_fp = content_fingerprint(text)
                                    last_fp = content_fingerprint(last_committed)
                                    if text_fp and last_fp and text_fp == last_fp:
                                        is_duplicate = True
                                        print(f"🔄 Duplicate detected (fingerprint match): '{text}' == '{last_committed}'")
                                
                                # Time-windowed duplicate checks
                                if not is_duplicate and (now - last_response_time) < DUPLICATE_WINDOW:
                                    # New text is just the old text with more words (continuation)
                                    if norm_text(last_committed) and len(norm_text(last_committed)) > 5 and norm_text(text).startswith(norm_text(last_committed)):
                                        is_duplicate = True
                                        print(f"🔄 Duplicate detected (continuation): '{text}' starts with '{last_committed}'")
                                    # Old text is just the new text with more words (shouldn't happen but safety check)
                                    elif norm_text(text) and len(norm_text(text)) > 5 and norm_text(last_committed).startswith(norm_text(text)):
                                        is_duplicate = True
                                        print(f"🔄 Duplicate detected (subset): '{text}' is subset of '{last_committed}'")
                                
                                if not is_duplicate:
                                    # Safety timeout: if llm_processing has been true for too long, reset it
                                    if llm_processing and (now - llm_started_at) > LLM_PROCESSING_TIMEOUT:
                                        print(f"⚠️ LLM processing timeout ({LLM_PROCESSING_TIMEOUT}s) - resetting flag")
                                        llm_processing = False
                                    
                                    # Check if we're currently waiting for LLM and this is just filler
                                    text_lower = text.lower().strip().rstrip('?.,!')
                                    is_filler = text_lower in FILLER_PHRASES or (len(text.split()) <= 2 and any(f in text_lower for f in ['hello', 'there', 'hi']))
                                    
                                    if llm_processing and is_filler:
                                        # Ignore filler phrases while LLM is thinking
                                        print(f"🤫 Ignoring filler during LLM processing: '{text}'")
                                        in_speech = False
                                        silence_since = 0.0
                                        pending_text = ""
                                        last_interim = ""
                                        asr.clear_all()
                                        continue
                                    
                                    # If LLM is processing and this is substantial speech, queue it
                                    if llm_processing and not is_filler:
                                        print(f"📝 Queuing speech during LLM processing: '{text}'")
                                        queued_speech.append(text)
                                        in_speech = False
                                        silence_since = 0.0
                                        pending_text = ""
                                        last_interim = ""
                                        asr.clear_all()
                                        continue
                                    
                                    # If there have been multiple interruptions, add context for the AI
                                    # Check BEFORE resetting the counter
                                    if interrupt_count >= 2:
                                        conversation.append({
                                            "role": "system", 
                                            "content": f"[SYSTEM: The caller has interrupted {interrupt_count} times. They may be trying to say something important. Listen carefully, keep your response SHORT (1 sentence max), and pause to let them finish speaking. Don't repeat yourself.]"
                                        })
                                        print(f"⚠️ Added interruption context to conversation (count: {interrupt_count})")
                                    
                                    # Successful turn completion - reset interrupt counter AFTER adding context
                                    if interrupt_count > 0:
                                        print(f"✅ Successful turn - resetting interrupt counter (was {interrupt_count})")
                                        interrupt_count = 0
                                    
                                    # Log the user speech
                                    conversation_log.append({
                                        "role": "user",
                                        "content": text,
                                        "timestamp": now
                                    })
                                    print(f"\n{'='*80}")
                                    print(f"👤 CALLER: {text}")
                                    print(f"{'='*80}\n")
                                    
                                    # Calculate response time if this is a follow-up
                                    if len(conversation_log) > 1:
                                        prev_msg = conversation_log[-2]
                                        if prev_msg['role'] == 'assistant':
                                            response_time = now - prev_msg['timestamp']
                                            response_times.append(response_time)
                                            print(f"⏱️ Caller response time: {response_time:.2f}s")
                                    
                                    # Reset state
                                    in_speech = False
                                    silence_since = 0.0
                                    pending_text = ""
                                    last_interim = ""
                                    last_committed = text
                                    last_response_time = now
                                    
                                    # Reset pre-response wait state
                                    pre_response_pending = False
                                    pre_response_text = ""
                                    pre_response_start = 0.0
                                    
                                    # Clear ASR state
                                    asr.clear_all()
                                    
                                    print(f"👤 USER: {text}")
                                    
                                    conversation.append({"role": "user", "content": text})
                                    
                                    # Trim conversation history to prevent context overflow
                                    # Keep system message (first) + last N message pairs
                                    # CRITICAL: Must preserve tool_calls + tool message pairs together
                                    MAX_HISTORY = 40  # Keep last 40 messages (20 turns) - much larger to preserve context
                                    if len(conversation) > MAX_HISTORY + 1:  # +1 for system message
                                        # BEFORE trimming: Extract key context from tool results we're about to lose
                                        # This prevents the AI from forgetting customer info after trimming
                                        context_summary = []
                                        for msg in conversation[1:]:  # Skip system message
                                            if msg.get('role') == 'tool' and msg.get('name') == 'lookup_customer':
                                                try:
                                                    result = json.loads(msg.get('content', '{}'))
                                                    if result.get('success') and result.get('customer_exists'):
                                                        info = result.get('customer_info', {})
                                                        context_summary.append(f"RETURNING CUSTOMER: {info.get('name', 'Unknown')}, phone: {info.get('phone', 'N/A')}, address: {info.get('last_address', 'N/A')}")
                                                except:
                                                    pass
                                            elif msg.get('role') == 'tool' and msg.get('name') == 'book_job':
                                                try:
                                                    result = json.loads(msg.get('content', '{}'))
                                                    if result.get('success'):
                                                        context_summary.append(f"JOB BOOKED: {result.get('message', 'Booking confirmed')}")
                                                except:
                                                    pass
                                        
                                        # Find a safe trim point that doesn't break tool call sequences
                                        # Tool messages MUST follow an assistant message with tool_calls
                                        messages_to_keep = conversation[-(MAX_HISTORY):]
                                        
                                        # Check if first message to keep is a 'tool' role - if so, we need to include the preceding assistant message
                                        while messages_to_keep and messages_to_keep[0].get('role') == 'tool':
                                            # Find the index in original conversation
                                            trim_start = len(conversation) - len(messages_to_keep)
                                            if trim_start > 1:  # Make sure we have room to go back
                                                # Include one more message (should be the assistant with tool_calls)
                                                messages_to_keep = conversation[trim_start - 1:] 
                                            else:
                                                # Can't go back further, remove the orphaned tool message
                                                messages_to_keep = messages_to_keep[1:]
                                                break
                                        
                                        # Also check for assistant messages with tool_calls that lost their tool responses
                                        # Remove any assistant message with tool_calls if not followed by tool messages
                                        cleaned_messages = []
                                        i = 0
                                        while i < len(messages_to_keep):
                                            msg = messages_to_keep[i]
                                            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                                                # Check if next message(s) are tool responses
                                                has_tool_response = (i + 1 < len(messages_to_keep) and 
                                                                    messages_to_keep[i + 1].get('role') == 'tool')
                                                if has_tool_response:
                                                    # Keep the assistant message and all following tool messages
                                                    cleaned_messages.append(msg)
                                                    i += 1
                                                    while i < len(messages_to_keep) and messages_to_keep[i].get('role') == 'tool':
                                                        cleaned_messages.append(messages_to_keep[i])
                                                        i += 1
                                                else:
                                                    # Skip this orphaned assistant message with tool_calls
                                                    i += 1
                                            else:
                                                cleaned_messages.append(msg)
                                                i += 1
                                        
                                        # Add context summary as a system message if we extracted any
                                        if context_summary:
                                            context_msg = {
                                                "role": "system",
                                                "content": f"[CONTEXT FROM EARLIER IN CALL - DO NOT ASK FOR THIS INFO AGAIN: {'; '.join(context_summary)}]"
                                            }
                                            conversation[:] = [conversation[0], context_msg] + cleaned_messages
                                            print(f"📝 Trimmed conversation to {len(conversation)} messages (preserved context: {context_summary})")
                                        else:
                                            conversation[:] = [conversation[0]] + cleaned_messages
                                            print(f"📝 Trimmed conversation to {len(conversation)} messages (preserved tool call sequences)")
                                    
                                    print(f"🔊 Starting LLM response (conversation length: {len(conversation)})")
                                    # Set LLM processing state to filter filler speech
                                    # This flag is cleared in start_tts finally block when TTS completes
                                    llm_processing = True
                                    llm_started_at = now
                                    queued_speech.clear()  # Clear any old queued speech (use .clear() to keep same list reference)
                                    
                                    # Set continuation window state - allows caller to continue speaking
                                    # within 2 seconds and have their speech appended to original
                                    continuation_window_start = now
                                    continuation_original_text = text
                                    continuation_energy_since = 0.0
                                    
                                    # --- TIMING: End-to-end response latency ---
                                    response_trigger_time = time_module.time()
                                    time_since_call_start = response_trigger_time - call_start_time
                                    print(f"\n[E2E_TIMING] 🎯 Response triggered {time_since_call_start:.3f}s after call start")
                                    print(f"[E2E_TIMING] User said: '{text[:50]}...'")
                                    
                                    # Stream LLM with appointment detection, phone number, and company context
                                    try:
                                        # Note: start_tts creates a background task and returns immediately
                                        # The llm_processing flag is cleared in the TTS finally block
                                        await start_tts(
                                            stream_llm(conversation, process_appointment_with_calendar, caller_phone=caller_phone, company_id=company_id, call_state=call_state),
                                            label="respond"
                                        )
                                        # Code here runs immediately after task creation, not after TTS completes
                                        # State cleanup happens in TTS finally block
                                        
                                    except Exception as e:
                                        print(f"❌ Error starting response: {e}")
                                        import traceback
                                        traceback.print_exc()
                                        
                                        # Reset on error to prevent stuck states
                                        llm_processing = False
                                        queued_speech.clear()
                                        speaking = False
                                        interrupt = False
                                        continuation_window_start = 0.0
                                        continuation_original_text = ""
                                else:
                                    # Duplicate detected, just reset
                                    in_speech = False
                                    silence_since = 0.0
                            else:
                                # Not enough words
                                in_speech = False
                                silence_since = 0.0

            elif event == "stop":
                print("🛑 stop")
                break
            elif event == "mark":
                # Twilio mark events - ignore
                pass
            else:
                # Unknown event type
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
