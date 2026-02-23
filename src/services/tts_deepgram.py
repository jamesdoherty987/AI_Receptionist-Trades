"""
Deepgram TTS (Text-to-Speech) service
Rewritten to match ElevenLabs' proven streaming pattern
"""
import asyncio
import base64
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
    Stream Deepgram TTS audio to Twilio in mulaw format
    
    Args:
        text_stream: Async iterator of text tokens
        websocket: Twilio websocket connection
        stream_sid: Twilio stream ID
        interrupt_fn: Function to check if interrupted
    """
    import time
    tts_start = time.time()
    print(f"[TTS] 🎤 Starting Deepgram TTS at {tts_start:.3f}")
    
    # Deepgram Aura TTS - aura-asteria-en is a natural conversational voice
    uri = (
        f"wss://api.deepgram.com/v1/speak"
        f"?model=aura-asteria-en"
        f"&encoding={config.AUDIO_ENCODING}"
        f"&sample_rate={config.AUDIO_SAMPLE_RATE}"
        f"&container=none"
    )

    # Max timeout (safety limit)
    MAX_TTS_SECONDS = 20.0

    for attempt in (1, 2):
        try:
            async with websockets.connect(
                uri,
                extra_headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"},
                open_timeout=12,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=20,
                max_size=2**20,
            ) as tts:
                print(f"[TTS] ✅ Connected to Deepgram TTS WebSocket")
                print(f"[TTS] 🔗 Stream SID: {stream_sid}")

                start_time = asyncio.get_event_loop().time()
                sender_done = asyncio.Event()

                async def sender():
                    """Send text tokens to Deepgram"""
                    tokens_sent = 0
                    full_text = ""
                    try:
                        print(f"[TTS] 📤 Sender started, streaming text to Deepgram...")
                        async for token in _aiter(text_stream):
                            if interrupt_fn():
                                print(f"[TTS] ⚠️ Sender interrupted after {tokens_sent} tokens")
                                return
                            tokens_sent += 1
                            full_text += token
                            if tokens_sent == 1:
                                print(f"[TTS] 📤 First token sent: '{token[:50]}'")
                            # Send text to Deepgram
                            await tts.send(json.dumps({"type": "Speak", "text": token}))
                        print(f"[TTS] 📤 All {tokens_sent} tokens sent. Full text: '{full_text[:100]}...'")
                    finally:
                        # Signal end of text with Flush
                        try:
                            await tts.send(json.dumps({"type": "Flush"}))
                            print(f"[TTS] 📤 Flush signal sent to Deepgram")
                        except Exception as e:
                            print(f"[TTS] ⚠️ Failed to send flush: {e}")
                        sender_done.set()

                async def receiver():
                    """Receive audio from Deepgram and forward to Twilio"""
                    quiet_timeouts = 0
                    got_any_audio = False
                    audio_chunks_received = 0
                    audio_chunks_sent = 0
                    total_audio_bytes = 0

                    print(f"[TTS] 📥 Receiver started, waiting for audio from Deepgram...")

                    while True:
                        if interrupt_fn():
                            print(f"[TTS] ⚠️ Interrupted! Received {audio_chunks_received} chunks, sent {audio_chunks_sent}")
                            return

                        # Hard max duration check
                        if (asyncio.get_event_loop().time() - start_time) > MAX_TTS_SECONDS:
                            print(f"[TTS] ⚠️ Max duration reached! Received {audio_chunks_received} chunks, sent {audio_chunks_sent}")
                            return

                        try:
                            # Use same timeout as ElevenLabs (1.5s)
                            msg = await asyncio.wait_for(tts.recv(), timeout=1.5)
                        except asyncio.TimeoutError:
                            # If we already sent all text and we've been quiet, exit
                            if sender_done.is_set():
                                quiet_timeouts += 1
                                # Same exit logic as ElevenLabs
                                if got_any_audio and quiet_timeouts >= 2:
                                    print(f"[TTS] ✅ Done (quiet timeout). Received {audio_chunks_received} chunks ({total_audio_bytes} bytes), sent {audio_chunks_sent} to Twilio")
                                    return
                                if quiet_timeouts >= 4:
                                    print(f"[TTS] ⚠️ No audio received after 4 timeouts. Received {audio_chunks_received} chunks, sent {audio_chunks_sent}")
                                    return
                            continue
                        except websockets.ConnectionClosed as e:
                            print(f"   ℹ️ Deepgram connection closed: {e}")
                            print(f"[TTS] 📊 Final stats: Received {audio_chunks_received} chunks ({total_audio_bytes} bytes), sent {audio_chunks_sent} to Twilio")
                            return

                        # Deepgram sends binary audio directly (not JSON like ElevenLabs)
                        if isinstance(msg, bytes):
                            got_any_audio = True
                            audio_chunks_received += 1
                            audio_bytes = len(msg)
                            total_audio_bytes += audio_bytes
                            
                            if audio_chunks_received == 1:
                                print(f"[TTS] 🔊 First audio chunk received! Size: {audio_bytes} bytes")
                            elif audio_chunks_received % 20 == 0:
                                print(f"[TTS] 🔊 Audio chunk #{audio_chunks_received}, total: {total_audio_bytes} bytes")
                            
                            # Convert to base64 and send to Twilio
                            # ElevenLabs sends pre-encoded base64, Deepgram sends raw bytes
                            try:
                                payload = base64.b64encode(msg).decode('utf-8')
                                await websocket.send(json.dumps({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": payload},
                                }))
                                audio_chunks_sent += 1
                            except (websockets.ConnectionClosed, RuntimeError) as send_err:
                                print(f"   ℹ️ Twilio connection closed during TTS (caller likely hung up)")
                                print(f"[TTS] 📊 Final stats: Received {audio_chunks_received} chunks, sent {audio_chunks_sent} to Twilio before disconnect")
                                return
                        
                        # Deepgram may send JSON messages for metadata
                        elif isinstance(msg, str):
                            try:
                                data = json.loads(msg)
                                if "error" in data:
                                    print(f"[TTS] ❌ Deepgram error: {data.get('error')}")
                                # Deepgram doesn't have isFinal like ElevenLabs, 
                                # it just stops sending audio
                            except json.JSONDecodeError:
                                pass

                await asyncio.gather(sender(), receiver())
                
                total_tts_time = time.time() - tts_start
                print(f"[TTS] ✅ TTS complete in {total_tts_time:.3f}s")
                return

        except websockets.ConnectionClosed as e:
            print(f"   ℹ️ Deepgram TTS connection closed (attempt {attempt}): {e}")
            return  # Don't retry, just exit gracefully
            
        except RuntimeError as e:
            if "close message" in str(e).lower() or "closed" in str(e).lower():
                print(f"   ℹ️ Twilio connection closed during TTS (caller hung up)")
                return
            raise
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️ Deepgram TTS error (attempt {attempt}): {e}")
            print(f"   📋 Error type: {type(e).__name__}")
            
            if "Unauthorized" in error_msg or "401" in error_msg:
                print(f"   ❌ API KEY ISSUE: Check DEEPGRAM_API_KEY in .env")
            
            import traceback
            print(f"   📋 Traceback:\n{traceback.format_exc()}")
            
            if attempt == 2:
                print(f"   ❌ Deepgram TTS failed after {attempt} attempts")
                raise
            await asyncio.sleep(config.TTS_CHUNK_DELAY)
