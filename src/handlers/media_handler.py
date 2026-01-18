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
    caller_phone = None  # Store caller's phone number

    # --- TTS / turn state ---
    speaking = False
    interrupt = False
    respond_task: asyncio.Task | None = None
    tts_started_at = 0.0
    tts_ended_at = 0.0

    # --- Speech segmentation with sentence-level detection ---
    in_speech = False
    silence_since = 0.0
    pending_text = ""
    last_committed = ""
    last_interim = ""
    last_response_time = 0.0
    last_audio_time = 0.0  # Track last audio received for watchdog

    # --- Optimized Tunables for Speed and Responsiveness ---
    SPEECH_ENERGY = 1200
    SILENCE_ENERGY = 800
    SILENCE_HOLD = 0.8  # Reduced - respond faster after silence

    INTERRUPT_ENERGY = 2200
    NO_BARGEIN_WINDOW = 0.15  # Reduced - allow interruption very early
    BARGEIN_HOLD = 0.06  # Faster interrupt detection

    POST_TTS_IGNORE = 0.02  # Very short - start listening immediately
    MIN_WORDS = 2  # Reduced - respond to shorter phrases
    DUPLICATE_WINDOW = 2.5  # Reduced - less aggressive duplicate prevention

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
            nonlocal speaking, tts_started_at, tts_ended_at
            speaking = True
            interrupt = False
            tts_started_at = asyncio.get_event_loop().time()
            print(f"🗣️ TTS start ({label})")

            try:
                token_count = 0
                async def simple_stream():
                    nonlocal token_count, speaking
                    async for token in text_stream:
                        token_count += 1
                        yield token
                        # After first token is sent, allow listening immediately
                        if token_count == 1:
                            speaking = False
                            print(f"✅ Ready to listen (text streaming)")
                
                await asyncio.wait_for(
                    stream_tts(simple_stream(), ws, stream_sid, lambda: interrupt),
                    timeout=20.0  # Reduced timeout for faster responses
                )
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
        async def tokens():
            yield "Hi, thank you for calling. How can I help you today?"
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
                    if (now - tts_started_at) <= NO_BARGEIN_WINDOW:
                        continue

                    if energy > INTERRUPT_ENERGY:
                        if bargein_since == 0.0:
                            bargein_since = now
                        elif (now - bargein_since) >= BARGEIN_HOLD:
                            interrupt = True
                            print("✋ interrupt triggered")
                            await clear_twilio_audio()
                            if respond_task and not respond_task.done():
                                respond_task.cancel()
                            speaking = False
                            tts_ended_at = now
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

                # ---- Speech detection ----
                if energy > SPEECH_ENERGY:
                    if not in_speech:
                        in_speech = True
                        silence_since = 0.0

                    silence_since = 0.0

                else:
                    # Low energy - check for silence
                    if in_speech:
                        if energy < SILENCE_ENERGY:
                            if silence_since == 0.0:
                                silence_since = now
                        else:
                            silence_since = 0.0

                        # TRIGGER RESPONSE after silence threshold
                        if silence_since and (now - silence_since) >= SILENCE_HOLD:
                            text = (final_text or pending_text).strip()
                            
                            if text and len(text.split()) >= MIN_WORDS:
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
                                        
                                        # Ensure we're ready to listen again
                                        speaking = False
                                        interrupt = False
                                        in_speech = False
                                        silence_since = 0.0
                                        bargein_since = 0.0
                                        
                                    except Exception as e:
                                        print(f"❌ Error during response: {e}")
                                        import traceback
                                        traceback.print_exc()
                                        
                                        # Reset state on error
                                        speaking = False
                                        interrupt = False
                                        in_speech = False
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
        if respond_task and not respond_task.done():
            respond_task.cancel()
        await asr.close()
        print("✅ Deepgram closed")
