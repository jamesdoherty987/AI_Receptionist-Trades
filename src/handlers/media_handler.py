"""
Twilio Media Stream WebSocket Handler
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
import re
import time as time_module
import websockets

from src.utils.audio_utils import ulaw_energy
from src.utils.config import config
from src.services.asr_deepgram import DeepgramASR
from src.services.llm_stream import stream_llm
from src.services.call_state import create_call_state

# Import pre-recorded audio service with safe fallback
try:
    from src.services.prerecorded_audio import (
        get_filler_audio, get_random_filler_id, send_prerecorded_audio, 
        has_prerecorded_fillers, preload_fillers, get_filler_id_from_message
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


async def media_handler(ws):
    """Handle Twilio media stream WebSocket connection"""
    call_start_time = time_module.time()
    print(f"\n{'='*70}")
    print(f"📞 [CALL_START] New call at {call_start_time:.3f}")
    print(f"{'='*70}")
    
    # Per-call state
    call_state = create_call_state()
    
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
    
    # TTS state
    speaking = False
    interrupt = False
    respond_task = None
    tts_started_at = 0.0
    tts_ended_at = 0.0
    
    # LLM processing state
    llm_processing = False
    llm_started_at = 0.0
    
    # Tracking
    last_committed = ""
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

    async def clear_twilio_audio():
        """Clear Twilio audio buffer"""
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
        nonlocal speaking, interrupt, respond_task, tts_started_at, tts_ended_at, llm_processing

        async def run():
            nonlocal speaking, tts_started_at, tts_ended_at, llm_processing, conversation_log, response_times
            speaking = True
            interrupt = False
            tts_started_at = asyncio.get_event_loop().time()
            run_start = time_module.time()
            
            full_text = ""
            transfer_number = None
            
            print(f"\n🗣️ [TTS] Starting response stream: {label}")

            try:
                # Get first token to check for SPLIT_TTS marker
                first_token = None
                async for token in text_stream:
                    # Skip timing markers
                    if token.startswith("<<<TIMING:"):
                        continue
                    first_token = token
                    break
                
                if not first_token:
                    print(f"   ⚠️ No tokens from LLM")
                    return
                
                print(f"   📍 First token: '{first_token[:50]}...'")
                
                # Check if this is a SPLIT_TTS marker (filler needed)
                if first_token.startswith("<<<SPLIT_TTS:"):
                    filler_msg = first_token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                    print(f"   🔀 SPLIT_TTS detected: '{filler_msg}'")
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
                        if has_prerecorded_fillers():
                            filler_id = get_filler_id_from_message(filler_msg) or get_random_filler_id()
                            filler_audio = get_filler_audio(filler_id)
                            if filler_audio:
                                print(f"   🔊 Playing filler: {filler_id}")
                                await send_prerecorded_audio(ws, stream_sid, filler_audio)
                                return True
                        # TTS fallback
                        print(f"   📢 TTS filler: '{filler_msg}'")
                        async def filler_tokens():
                            yield filler_msg
                        await stream_tts(filler_tokens(), ws, stream_sid, lambda: interrupt)
                        return True
                    
                    # START BOTH IN PARALLEL - this is the key fix!
                    # LLM work (OpenAI call, tool execution) happens while filler plays
                    print(f"   ⚡ Starting filler + LLM in parallel...")
                    llm_task = asyncio.create_task(consume_llm())
                    filler_task = asyncio.create_task(play_filler())
                    
                    # Wait for filler to finish (LLM continues in background)
                    await filler_task
                    print(f"   🔊 Filler done, streaming LLM response...")
                    
                    # Now stream tokens from queue to TTS
                    # CRITICAL: Add overall timeout to prevent infinite hang
                    MAX_WAIT_SECONDS = 15.0  # Max time to wait for LLM response
                    queue_start_time = time_module.time()
                    
                    async def queued_stream():
                        nonlocal full_text
                        stream_start_time = time_module.time()
                        MAX_STREAM_WAIT = 20.0  # Absolute max time for entire stream
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
                                token = await asyncio.wait_for(token_queue.get(), timeout=0.5)
                                full_text += token
                                yield token
                            except asyncio.TimeoutError:
                                # No token yet, check if LLM is done
                                if llm_done.is_set() and token_queue.empty():
                                    break
                                # Log if waiting too long
                                if elapsed > 5.0 and int(elapsed) % 2 == 0:
                                    print(f"   ⏳ Still waiting for LLM tokens... ({elapsed:.1f}s)")
                                continue
                    
                    await stream_tts(queued_stream(), ws, stream_sid, lambda: interrupt)
                    
                    # Make sure LLM task is done (with timeout to prevent hang)
                    try:
                        await asyncio.wait_for(llm_task, timeout=5.0)
                    except asyncio.TimeoutError:
                        print(f"   ⚠️ LLM task didn't finish in time, cancelling...")
                        llm_task.cancel()
                        try:
                            await llm_task
                        except asyncio.CancelledError:
                            pass
                    print(f"   ✅ Response complete")
                
                else:
                    # No SPLIT_TTS - stream everything directly to TTS
                    print(f"   📢 Direct streaming to TTS")
                    
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
                            if token.startswith("<<<"):
                                continue
                            full_text += token
                            yield token
                    
                    await stream_tts(direct_stream(), ws, stream_sid, lambda: interrupt)
                
                # Log response
                total_time = time_module.time() - run_start
                response_times.append(total_time)
                print(f"   ⏱️ Total response time: {total_time:.3f}s")
                
                if full_text.strip():
                    conversation_log.append({
                        "role": "assistant",
                        "content": full_text.strip(),
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    print(f"\n{'='*60}")
                    print(f"🤖 RECEPTIONIST: {full_text.strip()}")
                    print(f"{'='*60}\n")
                
                # Handle transfer if requested
                if transfer_number:
                    print(f"📞 TRANSFER TO: {transfer_number}")
                    try:
                        from twilio.rest import Client
                        import os
                        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
                        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
                        if account_sid and auth_token and call_sid:
                            client = Client(account_sid, auth_token)
                            from urllib.parse import quote
                            transfer_url = f"{config.PUBLIC_URL}/twilio/transfer?number={quote(transfer_number)}"
                            client.calls(call_sid).update(url=transfer_url, method='POST')
                            print(f"✅ Transfer initiated")
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
                tts_ended_at = asyncio.get_event_loop().time()
                speaking = False
                llm_processing = False
                print(f"👂 Ready to listen")

        if respond_task and not respond_task.done():
            respond_task.cancel()
        respond_task = asyncio.create_task(run())

    async def greet():
        """Send initial greeting"""
        nonlocal speaking, stream_sid
        greeting = "Hi, thank you for calling. How can I help you today?"
        
        print(f"\n🤖 GREETING: {greeting}")
        conversation_log.append({"role": "assistant", "content": greeting, "timestamp": asyncio.get_event_loop().time()})
        
        # Try pre-recorded greeting
        if has_prerecorded_fillers():
            audio = get_filler_audio("greeting")
            if audio:
                await send_prerecorded_audio(ws, stream_sid, audio)
                speaking = False
                return
        
        # Fallback to TTS
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
                stream_sid = data["start"]["streamSid"]
                call_sid = data["start"].get("callSid", "")
                custom_params = data["start"].get("customParameters", {})
                caller_phone = custom_params.get("From", "") or data["start"].get("from", "")
                company_id = custom_params.get("CompanyId", "") or None
                
                print(f"🎧 Stream started: {stream_sid}")
                print(f"📱 Caller: {caller_phone}, Company: {company_id}")

                # Format phone for display
                formatted_phone = caller_phone
                if caller_phone and caller_phone.startswith('+353'):
                    local = '0' + caller_phone[4:]
                    if len(local) == 10:
                        formatted_phone = f"{local[:3]} {local[3:6]} {local[6:]}"
                
                # Phone instruction
                if caller_phone:
                    phone_instruction = (
                        f"PHONE NUMBER: Caller's number is {formatted_phone} (from caller ID). "
                        "DO NOT ask to confirm - we have it. Only ask if they want a different number."
                    )
                else:
                    phone_instruction = "PHONE NUMBER: Not detected. Ask for their number."

                # System context
                conversation.append({
                    "role": "system",
                    "content": (
                        "[SYSTEM: Greeting already sent. DO NOT re-introduce or ask 'how can I help' again. "
                        "Keep replies SHORT. After they describe their issue, ask for NAME (spell it back). "
                        f"{phone_instruction} "
                        "After name confirmed, ask for eircode. Say things ONCE only.]"
                    )
                })
                
                asyncio.create_task(greet())
                
                # Warmup OpenAI
                async def warmup():
                    try:
                        from src.services.llm_stream import get_openai_client
                        from src.services.calendar_tools import CALENDAR_TOOLS
                        client = get_openai_client()
                        def do_warmup():
                            stream = client.chat.completions.create(
                                model=config.CHAT_MODEL,
                                messages=[{"role": "user", "content": "hi"}],
                                max_tokens=1, stream=True, temperature=0.1,
                                tools=CALENDAR_TOOLS, tool_choice="none",
                            )
                            for _ in stream: pass
                        await asyncio.to_thread(do_warmup)
                        print(f"🔥 OpenAI warmed up")
                    except Exception as e:
                        print(f"⚠️ Warmup failed: {e}")
                asyncio.create_task(warmup())

            elif event == "media":
                if not stream_sid:
                    continue

                audio = base64.b64decode(data["media"]["payload"])
                energy = ulaw_energy(audio)
                now = asyncio.get_event_loop().time()

                # ASR health check
                if asr.is_closed():
                    if await asr.reconnect():
                        print("✅ ASR reconnected")
                    else:
                        continue

                # Barge-in while speaking
                if speaking:
                    if (now - tts_started_at) <= NO_BARGEIN_WINDOW:
                        continue
                    
                    if energy > INTERRUPT_ENERGY:
                        if bargein_since == 0.0:
                            bargein_since = now
                        elif (now - bargein_since) >= BARGEIN_HOLD:
                            await asr.feed(audio)
                            interim = asr.get_interim()
                            if len(interim.strip().split()) >= 1:
                                interrupt = True
                                print(f"✋ Interrupt: '{interim}'")
                                await clear_twilio_audio()
                                if respond_task and not respond_task.done():
                                    respond_task.cancel()
                                speaking = False
                                tts_ended_at = now
                                bargein_since = 0.0
                    else:
                        bargein_since = 0.0
                    continue

                # Ignore tail after TTS
                if (now - tts_ended_at) < POST_TTS_IGNORE:
                    continue

                # Feed audio to ASR
                await asr.feed(audio)
                
                # Check for speech_final
                if asr.is_speech_finished():
                    text = asr.get_text().strip()
                    asr.clear()
                    
                    if not text or len(text.split()) < MIN_WORDS:
                        continue
                    
                    # Duplicate check
                    if norm_text(text) == norm_text(last_committed):
                        continue
                    
                    # LLM timeout check
                    if llm_processing and (now - llm_started_at) > LLM_PROCESSING_TIMEOUT:
                        print(f"[MEDIA] ⚠️ TIMEOUT: LLM processing exceeded {LLM_PROCESSING_TIMEOUT}s - resetting state")
                        llm_processing = False
                    
                    # Filter filler during LLM processing
                    if llm_processing and text.lower().strip().rstrip('?.,!') in FILLER_PHRASES:
                        print(f"🤫 Ignoring filler: '{text}'")
                        continue
                    
                    # Log user speech
                    print(f"\n{'='*60}")
                    print(f"👤 CALLER: {text}")
                    print(f"{'='*60}\n")
                    
                    conversation_log.append({"role": "user", "content": text, "timestamp": now})
                    last_committed = text
                    conversation.append({"role": "user", "content": text})
                    
                    # Trim history
                    if len(conversation) > 21:
                        conversation[:] = [conversation[0]] + conversation[-20:]
                    
                    # Start response
                    llm_processing = True
                    llm_started_at = now
                    
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
                break

    except websockets.ConnectionClosed as e:
        print(f"⚠️ WS disconnected: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Call summary
        total_duration = time_module.time() - call_start_time
        print(f"\n{'#'*60}")
        print(f"📊 CALL SUMMARY")
        print(f"Duration: {total_duration:.1f}s, Messages: {len(conversation_log)}")
        if response_times:
            print(f"Avg response: {sum(response_times)/len(response_times):.2f}s")
        print(f"{'#'*60}\n")
        
        # Save call summary
        if conversation_log and caller_phone:
            try:
                from src.services.call_summarizer import add_call_summary_to_booking
                company_id_int = int(company_id) if company_id else None
                await add_call_summary_to_booking(conversation_log, caller_phone, company_id_int)
            except Exception as e:
                print(f"⚠️ Summary error: {e}")
        
        if respond_task and not respond_task.done():
            respond_task.cancel()
        await asr.close()
        print("✅ Cleanup complete")
