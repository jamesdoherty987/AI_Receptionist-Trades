"""
Twilio Media Stream WebSocket Handler
Manages real-time voice conversations with VAD, ASR, LLM, and TTS
"""
import asyncio
import json
import base64
import re
import websockets

from src.utils.audio_utils import ulaw_energy
from src.utils.config import config
from src.services.asr_deepgram import DeepgramASR
from src.services.llm_stream import stream_llm, process_appointment_with_calendar, reset_appointment_state

# Import TTS based on provider setting
TTS_PROVIDER = config.TTS_PROVIDER if hasattr(config, 'TTS_PROVIDER') else 'deepgram'

if TTS_PROVIDER == 'elevenlabs':
    from src.services.tts_elevenlabs import stream_tts
else:
    from src.services.tts_deepgram import stream_tts


def norm_text(s: str) -> str:
    """Normalize text for comparison"""
    return " ".join((s or "").lower().split())


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
    print("✅ Twilio WS client connected:", ws.remote_address)
    
    # CRITICAL: Reset appointment state at the start of each call
    # This prevents state from previous calls bleeding into new calls
    reset_appointment_state()

    asr = DeepgramASR()
    try:
        await asr.connect()
        print("✅ Deepgram connected")
    except Exception as e:
        print("❌ Deepgram connect failed:", repr(e))
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
            nonlocal speaking, tts_started_at, tts_ended_at, call_sid, conversation_log, llm_processing, queued_speech, conversation
            speaking = True
            interrupt = False
            tts_started_at = asyncio.get_event_loop().time()
            print(f"🗣️ TTS start ({label})")

            try:
                token_count = 0
                transfer_number = None
                full_text = ""  # Capture full text for logging
                MIN_TOKENS_BEFORE_INTERRUPT = config.MIN_TOKENS_BEFORE_INTERRUPT
                needs_continuation = False  # Track if we need a second TTS session
                
                # First TTS session - will speak either the full response OR just the checking message
                print(f"   🗣️ Starting first TTS session...")
                
                # Buffer for pre-fetched tokens during parallel execution
                prefetch_buffer = []
                prefetch_done = asyncio.Event()
                prefetch_task = None
                
                async def prefetch_remaining():
                    """Pre-fetch remaining tokens while TTS speaks the filler"""
                    nonlocal transfer_number
                    try:
                        async for token in text_stream:
                            if token.startswith("<<<TRANSFER:"):
                                transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                                print(f"📞 TRANSFER MARKER DETECTED (prefetch): {transfer_number}")
                                continue
                            if token.startswith("<<<") and token.endswith(">>>"):
                                continue
                            prefetch_buffer.append(token)
                    except Exception as e:
                        print(f"⚠️ Prefetch error: {e}")
                    finally:
                        prefetch_done.set()
                        print(f"   ⚡ Prefetch complete: {len(prefetch_buffer)} tokens buffered")
                
                async def simple_stream_with_prefetch():
                    nonlocal token_count, speaking, transfer_number, full_text, needs_continuation, prefetch_task
                    
                    async for token in text_stream:
                        # Check for SPLIT_TTS marker - this means we need to speak something NOW
                        # while continuing to process the LLM stream in PARALLEL
                        if token.startswith("<<<SPLIT_TTS:"):
                            # Extract the message to speak immediately
                            split_msg = token.replace("<<<SPLIT_TTS:", "").replace(">>>", "").strip()
                            print(f"🔀 SPLIT_TTS MARKER DETECTED: '{split_msg}'")
                            # Yield this message so it gets spoken now
                            yield split_msg
                            full_text += split_msg + " "
                            needs_continuation = True
                            
                            # START PARALLEL PREFETCH - LLM/tool work happens while TTS speaks
                            print(f"   ⚡ Starting parallel prefetch while TTS speaks...")
                            prefetch_task = asyncio.create_task(prefetch_remaining())
                            
                            # Break to let TTS speak the filler
                            break
                        
                        # Check for transfer marker
                        if token.startswith("<<<TRANSFER:"):
                            transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                            print(f"📞 TRANSFER MARKER DETECTED: {transfer_number}")
                            continue
                        
                        # Skip other control markers
                        if token.startswith("<<<") and token.endswith(">>>"):
                            continue
                        
                        token_count += 1
                        full_text += token
                        yield token
                        if token_count == MIN_TOKENS_BEFORE_INTERRUPT:
                            speaking = False
                            print(f"✅ Ready to listen (text streaming)")
                
                await asyncio.wait_for(
                    stream_tts(simple_stream_with_prefetch(), ws, stream_sid, lambda: interrupt),
                    timeout=config.TTS_TIMEOUT
                )
                print(f"   ✅ First TTS session complete")
                
                # If we need continuation (due to SPLIT_TTS), start a second TTS session for the rest
                if needs_continuation:
                    print(f"   🔄 Starting second TTS session for remaining content...")
                    token_count = 0  # Reset for second session
                    
                    # Wait for prefetch to complete (should be done or nearly done by now)
                    if prefetch_task:
                        try:
                            await asyncio.wait_for(prefetch_done.wait(), timeout=15.0)
                            print(f"   ⚡ Prefetch ready: {len(prefetch_buffer)} tokens available")
                        except asyncio.TimeoutError:
                            print(f"   ⚠️ Prefetch timeout - continuing with available tokens")
                    
                    async def continuation_stream():
                        nonlocal token_count, speaking, transfer_number, full_text
                        # First yield all pre-fetched tokens (these were gathered in parallel)
                        for token in prefetch_buffer:
                            token_count += 1
                            full_text += token
                            yield token
                            if token_count == MIN_TOKENS_BEFORE_INTERRUPT:
                                speaking = False
                                print(f"✅ Ready to listen (continuation)")
                    
                    # Second TTS session with the actual results (from prefetch buffer)
                    await asyncio.wait_for(
                        stream_tts(continuation_stream(), ws, stream_sid, lambda: interrupt),
                        timeout=config.TTS_TIMEOUT
                    )
                    print(f"   ✅ Second TTS session complete")
                
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
        """Send initial greeting"""
        greeting_text = "Hi, thank you for calling. How can I help you today?"
        async def tokens():
            yield greeting_text
        print(f"\n{'='*80}")
        print(f"🤖 RECEPTIONIST (GREETING): {greeting_text}")
        print(f"{'='*80}\n")
        conversation_log.append({
            "role": "assistant",
            "content": greeting_text,
            "timestamp": asyncio.get_event_loop().time()
        })
        await start_tts(tokens(), label="greet")

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
                        "[SYSTEM: Initial greeting has ALREADY been delivered to the caller. "
                        "Do NOT reintroduce the business or say 'thanks for calling'. Keep replies short. "
                        "If they ask to book, respond briefly: 'Sure, no problem! What day and time works best for you?'. "
                        "ALWAYS spell back their name letter-by-letter and wait for confirmation before proceeding. "
                        f"{phone_instruction} "
                        "ADDRESS: Prefer eircode - ask 'Do you know your eircode?' first. If not, get full address. ALWAYS read back addresses and eircodes to confirm. "
                        "CRITICAL: Say things ONCE only - never repeat booking confirmations, goodbyes, or 'thanks for calling'. After confirming a booking, just ask 'Anything else?' once.]"
                    )
                })
                
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

                    # Require sustained high energy for interruption
                    if energy > INTERRUPT_ENERGY:
                        if bargein_since == 0.0:
                            bargein_since = now
                        elif (now - bargein_since) >= BARGEIN_HOLD:
                            # Additional check: ensure this isn't just noise
                            await asr.feed(audio)
                            interim_check = asr.get_interim()
                            # Require substantial speech (at least 5 characters or a recognizable word)
                            words = interim_check.strip().split()
                            if len(words) >= 1 and len(interim_check.strip()) >= 3:
                                interrupt = True
                                print(f"✋ legitimate interrupt triggered: '{interim_check}'")
                                await clear_twilio_audio()
                                if respond_task and not respond_task.done():
                                    respond_task.cancel()
                                speaking = False
                                tts_ended_at = now
                                bargein_since = 0.0
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
                            
                            if text and len(text.split()) >= MIN_WORDS:
                                # Check if sentence appears complete
                                is_complete_thought = (
                                    text.endswith(('.', '!', '?')) or
                                    len(text.split()) >= 4 or  # Longer phrases are usually complete
                                    any(word in text.lower() for word in ['yes', 'no', 'okay', 'thanks', 'hello', 'help'])
                                )
                                
                                # If not complete, wait a bit more unless it's been too long
                                if not is_complete_thought and (now - silence_since) < (SILENCE_HOLD + COMPLETION_WAIT):
                                    continue
                                
                                # Enhanced duplicate detection
                                is_duplicate = False
                                
                                if (now - last_response_time) < DUPLICATE_WINDOW:
                                    if norm_text(text) == norm_text(last_committed):
                                        is_duplicate = True
                                    elif norm_text(last_committed) and norm_text(text).startswith(norm_text(last_committed)):
                                        is_duplicate = True
                                    elif norm_text(text) and norm_text(last_committed).startswith(norm_text(text)):
                                        is_duplicate = True
                                
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
                                        asr.text = ""
                                        asr.interim_text = ""
                                        asr.reset_final_flag()
                                        continue
                                    
                                    # If LLM is processing and this is substantial speech, queue it
                                    if llm_processing and not is_filler:
                                        print(f"📝 Queuing speech during LLM processing: '{text}'")
                                        queued_speech.append(text)
                                        in_speech = False
                                        silence_since = 0.0
                                        pending_text = ""
                                        last_interim = ""
                                        asr.text = ""
                                        asr.interim_text = ""
                                        asr.reset_final_flag()
                                        continue
                                    
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
                                    
                                    # Clear ASR state
                                    asr.text = ""
                                    asr.interim_text = ""
                                    asr.reset_final_flag()
                                    
                                    print(f"👤 USER: {text}")
                                    
                                    conversation.append({"role": "user", "content": text})
                                    
                                    # Trim conversation history to prevent context overflow
                                    # Keep system message (first) + last N message pairs
                                    MAX_HISTORY = 12  # Keep last 12 messages (6 turns)
                                    if len(conversation) > MAX_HISTORY + 1:  # +1 for system message
                                        # Keep first message (system) and last MAX_HISTORY messages
                                        conversation[:] = [conversation[0]] + conversation[-(MAX_HISTORY):]
                                        print(f"📝 Trimmed conversation to {len(conversation)} messages")
                                    
                                    print(f"🔊 Starting LLM response (conversation length: {len(conversation)})")
                                    # Set LLM processing state to filter filler speech
                                    # This flag is cleared in start_tts finally block when TTS completes
                                    llm_processing = True
                                    llm_started_at = now
                                    queued_speech.clear()  # Clear any old queued speech (use .clear() to keep same list reference)
                                    
                                    # Stream LLM with appointment detection, phone number, and company context
                                    try:
                                        # Note: start_tts creates a background task and returns immediately
                                        # The llm_processing flag is cleared in the TTS finally block
                                        await start_tts(
                                            stream_llm(conversation, process_appointment_with_calendar, caller_phone=caller_phone, company_id=company_id),
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
        # Print conversation summary
        print(f"\n\n{'#'*80}")
        print(f"📊 CALL SUMMARY")
        print(f"{'#'*80}")
        print(f"📞 Call SID: {call_sid}")
        print(f"📱 Caller: {caller_phone}")
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
