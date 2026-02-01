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
from src.services.llm_stream import stream_llm, process_appointment_with_calendar

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
    
    # Conversation logging
    conversation_log = []  # Full conversation transcript
    response_times = []  # Track response times

    # --- TTS / turn state ---
    speaking = False
    interrupt = False
    respond_task: asyncio.Task | None = None
    tts_started_at = 0.0
    tts_ended_at = 0.0

    # --- Speech segmentation with sentence-level detection ---
    in_speech = False
    silence_since = 0.0
    speech_start_time = 0.0
    pending_text = ""
    last_committed = ""
    last_interim = ""
    last_response_time = 0.0
    last_audio_time = 0.0  # Track last audio received for watchdog

    # --- Optimized Tunables for Speed and Responsiveness ---
    SPEECH_ENERGY = 1100  # Lower threshold for better detection
    SILENCE_ENERGY = 700   # Lower threshold to detect silence better
    SILENCE_HOLD = 0.6     # Slightly longer to prevent premature cutoff

    INTERRUPT_ENERGY = 3500  # Much higher - require very clear speech to interrupt
    NO_BARGEIN_WINDOW = 1.5  # Protect first 1.5s of response from any interruption
    BARGEIN_HOLD = 0.4       # Require 400ms of sustained loud speech to interrupt

    POST_TTS_IGNORE = 0.05   # Longer to prevent immediate false triggers
    MIN_WORDS = 1            # Allow single word responses
    DUPLICATE_WINDOW = 3.0   # Longer window for better duplicate detection
    
    # Additional settings to prevent cutoffs
    MIN_SPEECH_DURATION = 0.3  # Minimum speech duration before processing
    COMPLETION_WAIT = 0.2      # Wait for sentence completion

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
        nonlocal speaking, interrupt, respond_task, tts_started_at, tts_ended_at

        async def run():
            nonlocal speaking, tts_started_at, tts_ended_at, call_sid, conversation_log
            speaking = True
            interrupt = False
            tts_started_at = asyncio.get_event_loop().time()
            print(f"🗣️ TTS start ({label})")

            try:
                token_count = 0
                transfer_number = None
                full_text = ""  # Capture full text for logging
                MIN_TOKENS_BEFORE_INTERRUPT = 8  # Require at least 8 tokens (~2 words) before allowing interrupt
                
                async def simple_stream():
                    nonlocal token_count, speaking, transfer_number, full_text
                    async for token in text_stream:
                        # Check for transfer marker
                        if token.startswith("<<<TRANSFER:"):
                            # Extract phone number from marker
                            transfer_number = token.replace("<<<TRANSFER:", "").replace(">>>", "").strip()
                            print(f"📞 TRANSFER MARKER DETECTED: {transfer_number}")
                            continue  # Don't send this to TTS
                        
                        # Skip other control markers
                        if token.startswith("<<<") and token.endswith(">>>"):
                            continue
                        
                        token_count += 1
                        full_text += token  # Accumulate for logging
                        yield token
                        # After minimum tokens are sent, allow listening
                        if token_count == MIN_TOKENS_BEFORE_INTERRUPT:
                            speaking = False
                            print(f"✅ Ready to listen (text streaming)")
                
                # Try primary TTS first
                await asyncio.wait_for(
                    stream_tts(simple_stream(), ws, stream_sid, lambda: interrupt),
                    timeout=20.0  # Max timeout - responds immediately when audio done
                )
                
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
                            from src.utils.config import config
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
                tts_ended_at = asyncio.get_event_loop().time()
                duration = tts_ended_at - tts_started_at
                speaking = False
                interrupt = False  # Reset interrupt flag
                # Signal end immediately so user can speak
                print(f"🛑 TTS end ({label}) - duration: {duration:.2f}s")
                print(f"👂 Ready to receive audio again (speaking={speaking})")
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
                # Extract caller phone number from Twilio metadata
                call_sid = data["start"].get("callSid", "")
                custom_parameters = data["start"].get("customParameters", {})
                caller_phone = custom_parameters.get("From", "") or data["start"].get("from", "")
                
                print("🎧 start streamSid:", stream_sid)
                print("📞 Call SID:", call_sid)
                print("📱 Caller phone:", caller_phone if caller_phone else "Not available")

                # Inform the LLM that greeting has already been sent to avoid re-introduction
                conversation.append({
                    "role": "system",
                    "content": (
                        "[SYSTEM: Initial greeting has ALREADY been delivered to the caller. "
                        "Do NOT reintroduce the business or say 'thanks for calling'. Keep replies short. "
                        "If they ask to book, respond briefly: 'Sure, no problem! What day and time works best for you?'. "
                        "ALWAYS spell back their name letter-by-letter and wait for confirmation before proceeding. "
                        "For phone calls, first ask: 'Is the phone number you're calling from the one you want to use for this appointment?'; "
                        "if yes, continue; if no, ask for the preferred number.]"
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
                                    
                                    print(f"🔊 Starting LLM response (conversation length: {len(conversation)})")
                                    # Stream LLM with appointment detection and phone number
                                    try:
                                        await start_tts(
                                            stream_llm(conversation, process_appointment_with_calendar, caller_phone=caller_phone),
                                            label="respond"
                                        )
                                        print(f"✅ Response complete, continuing to listen...")
                                        
                                        # Ensure we're ready to listen again with proper reset
                                        await asyncio.sleep(0.1)  # Small delay for cleanup
                                        speaking = False
                                        interrupt = False
                                        in_speech = False
                                        silence_since = 0.0
                                        bargein_since = 0.0
                                        pending_text = ""
                                        last_interim = ""
                                        
                                        # Clear any remaining audio buffer
                                        await clear_twilio_audio()
                                        
                                    except Exception as e:
                                        print(f"❌ Error during response: {e}")
                                        import traceback
                                        traceback.print_exc()
                                        
                                        # Complete reset on error to prevent stuck states
                                        speaking = False
                                        interrupt = False
                                        in_speech = False
                                        silence_since = 0.0
                                        bargain_since = 0.0
                                        pending_text = ""
                                        last_interim = ""
                                        
                                        # Clear audio and ASR state
                                        await clear_twilio_audio()
                                        asr.text = ""
                                        asr.interim_text = ""
                                        asr.reset_final_flag()
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
        
        print(f"\n{'#'*80}\n\n")
        
        if respond_task and not respond_task.done():
            respond_task.cancel()
        await asr.close()
        print("✅ Deepgram closed")
