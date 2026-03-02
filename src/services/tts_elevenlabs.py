"""
ElevenLabs TTS (Text-to-Speech) service
"""
import asyncio
import json
import websockets
from src.utils.config import config


async def _aiter(text_stream):
    """Convert text stream to async iterator"""
    if hasattr(text_stream, "__aiter__"):
        async for x in text_stream:
            yield x
    else:
        for x in text_stream:
            yield x


async def stream_tts(text_stream, websocket, stream_sid, interrupt_fn):
    """
    Stream ElevenLabs TTS audio to Twilio in ulaw_8000 format
    
    Args:
        text_stream: Async iterator of text tokens
        websocket: Twilio websocket connection
        stream_sid: Twilio stream ID
        interrupt_fn: Function to check if interrupted
    """
    import time
    tts_start = time.time()
    print(f"[TTS] 🎤 Starting ElevenLabs TTS at {tts_start:.3f}")
    
    # Try primary voice first, fallback to backup if it fails
    voice_id = config.ELEVENLABS_VOICE_ID
    
    uri = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
            f"?model_id=eleven_turbo_v2_5"  # ADD THIS
            f"&output_format=ulaw_8000"
            f"&optimize_streaming_latency=4"  # ADD THIS (max optimization)
        )

    # Max timeout (responds immediately when audio done - this is just safety)
    MAX_TTS_SECONDS = 20.0

    for attempt in (1, 2):
        try:
            async with websockets.connect(
                uri,
                extra_headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                open_timeout=12,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=20,
                max_size=2**20,
            ) as tts:
                print(f"[TTS] ✅ Connected to ElevenLabs WebSocket")
                print(f"[TTS] 🔗 Voice ID: {voice_id}")
                print(f"[TTS] 🔗 Stream SID: {stream_sid}")

                start_time = asyncio.get_event_loop().time()

                # Initialize connection
                print(f"[TTS] 📤 Sending initialization message...")
                await tts.send(json.dumps({
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                }))
                print(f"[TTS] ✅ Initialization sent")

                sender_done = asyncio.Event()

                async def sender():
                    """Send text tokens to ElevenLabs"""
                    tokens_sent = 0
                    full_text = ""
                    try:
                        print(f"[TTS] 📤 Sender started, streaming text to ElevenLabs...")
                        async for token in _aiter(text_stream):
                            if interrupt_fn():
                                print(f"[TTS] ⚠️ Sender interrupted after {tokens_sent} tokens")
                                return
                            tokens_sent += 1
                            full_text += token
                            if tokens_sent == 1:
                                print(f"[TTS] 📤 First token sent: '{token[:50]}'")
                            await tts.send(json.dumps({
                                "text": token,
                                "try_trigger_generation": True
                            }))
                        print(f"[TTS] 📤 All {tokens_sent} tokens sent. Full text: '{full_text[:100]}...'")
                    finally:
                        # Signal end of text
                        try:
                            await tts.send(json.dumps({"text": ""}))
                            print(f"[TTS] 📤 End-of-text signal sent to ElevenLabs")
                        except Exception as e:
                            print(f"[TTS] ⚠️ Failed to send end-of-text: {e}")
                        sender_done.set()

                async def receiver():
                    """Receive audio from ElevenLabs and forward to Twilio"""
                    quiet_timeouts = 0
                    got_any_audio = False
                    audio_chunks_received = 0
                    audio_chunks_sent = 0
                    total_audio_bytes = 0

                    print(f"[TTS] 📥 Receiver started, waiting for audio from ElevenLabs...")

                    while True:
                        if interrupt_fn():
                            print(f"[TTS] ⚠️ Interrupted! Received {audio_chunks_received} chunks, sent {audio_chunks_sent}")
                            return

                        # Hard max duration check
                        if (asyncio.get_event_loop().time() - start_time) > MAX_TTS_SECONDS:
                            print(f"[TTS] ⚠️ Max duration reached! Received {audio_chunks_received} chunks, sent {audio_chunks_sent}")
                            return

                        try:
                            msg = await asyncio.wait_for(tts.recv(), timeout=0.5)
                        except asyncio.TimeoutError:
                            # If we already sent all text and we've been quiet, exit
                            if sender_done.is_set():
                                quiet_timeouts += 1
                                # Exit quickly after audio done
                                if got_any_audio and quiet_timeouts >= 1:
                                    print(f"[TTS] ✅ Done (quiet timeout). Received {audio_chunks_received} chunks ({total_audio_bytes} bytes), sent {audio_chunks_sent} to Twilio")
                                    return
                                if quiet_timeouts >= 2:
                                    print(f"[TTS] ⚠️ No audio received after 2 timeouts. Received {audio_chunks_received} chunks, sent {audio_chunks_sent}")
                                    return
                            continue
                        except websockets.ConnectionClosed as e:
                            # ElevenLabs connection closed
                            print(f"   ℹ️ ElevenLabs connection closed: {e}")
                            print(f"[TTS] 📊 Final stats: Received {audio_chunks_received} chunks ({total_audio_bytes} bytes), sent {audio_chunks_sent} to Twilio")
                            return

                        data = json.loads(msg)
                        
                        # Log non-audio messages for debugging
                        if not data.get("audio"):
                            msg_keys = list(data.keys())
                            if "error" in data:
                                print(f"[TTS] ❌ ElevenLabs error: {data.get('error')}")
                            elif "message" in data:
                                print(f"[TTS] 📨 ElevenLabs message: {data.get('message')}")
                            elif msg_keys != ['isFinal']:
                                print(f"[TTS] 📨 ElevenLabs response keys: {msg_keys}")

                        if data.get("audio"):
                            got_any_audio = True
                            audio_chunks_received += 1
                            audio_bytes = len(data["audio"])
                            total_audio_bytes += audio_bytes
                            
                            if audio_chunks_received == 1:
                                print(f"[TTS] 🔊 First audio chunk received! Size: {audio_bytes} bytes")
                            elif audio_chunks_received % 20 == 0:
                                print(f"[TTS] 🔊 Audio chunk #{audio_chunks_received}, total: {total_audio_bytes} bytes")
                            
                            try:
                                await websocket.send(json.dumps({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": data["audio"]},
                                }))
                                audio_chunks_sent += 1
                            except (websockets.ConnectionClosed, RuntimeError) as send_err:
                                # Twilio connection closed (caller hung up) - this is normal
                                print(f"   ℹ️ Twilio connection closed during TTS (caller likely hung up)")
                                print(f"[TTS] 📊 Final stats: Received {audio_chunks_received} chunks, sent {audio_chunks_sent} to Twilio before disconnect")
                                return

                        if data.get("isFinal"):
                            print(f"[TTS] ✅ isFinal received. Total: {audio_chunks_received} chunks ({total_audio_bytes} bytes), sent {audio_chunks_sent} to Twilio")
                            return

                await asyncio.gather(sender(), receiver())
                return

        except websockets.ConnectionClosed as e:
            # Connection closed - usually means caller hung up, not a real error
            print(f"   ℹ️ ElevenLabs TTS connection closed (attempt {attempt}): {e}")
            return  # Don't retry, just exit gracefully
            
        except RuntimeError as e:
            # RuntimeError from trying to send on closed connection
            if "close message" in str(e).lower() or "closed" in str(e).lower():
                print(f"   ℹ️ Twilio connection closed during TTS (caller hung up)")
                return  # Don't retry, just exit gracefully
            # Re-raise other RuntimeErrors
            raise
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️ ElevenLabs TTS error (attempt {attempt}): {e}")
            print(f"   📋 Error type: {type(e).__name__}")
            print(f"   📋 Error details: {repr(e)}")
            
            # Provide helpful diagnostics
            if "Unauthorized" in error_msg or "401" in error_msg:
                print(f"   ❌ API KEY ISSUE: Check ELEVENLABS_API_KEY in .env")
            elif "does not exist" in error_msg or "404" in error_msg:
                print(f"   ❌ VOICE ID ISSUE: Voice {voice_id} not found")
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                print(f"   ❌ CONNECTION TIMEOUT: Network issue or API slow")
            elif not error_msg or error_msg.strip() == "":
                print(f"   ❌ EMPTY ERROR: Likely connection closed unexpectedly")
                print(f"   💡 This usually means: 1) API key invalid, 2) Voice ID wrong, 3) Network issue")
            
            import traceback
            print(f"   📋 Traceback:\n{traceback.format_exc()}")
            
            # If voice doesn't exist and we haven't tried fallback yet, try fallback voice
            if "does not exist" in error_msg and voice_id == config.ELEVENLABS_VOICE_ID and hasattr(config, 'ELEVENLABS_FALLBACK_VOICE_ID'):
                print(f"   🔄 Trying fallback voice: {config.ELEVENLABS_FALLBACK_VOICE_ID}")
                voice_id = config.ELEVENLABS_FALLBACK_VOICE_ID
                uri = (
                    f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
                    f"?output_format=ulaw_8000"
                )
                continue  # Try again with fallback voice
            
            if attempt == 2:
                print(f"   ❌ ElevenLabs TTS failed after {attempt} attempts")
                raise
            await asyncio.sleep(config.TTS_CHUNK_DELAY)
