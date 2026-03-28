"""
Deepgram TTS (Text-to-Speech) service

Streams text to Deepgram's Aura TTS and forwards audio to Twilio.
Each TTS request opens a new WebSocket connection (Deepgram's API design).
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


async def stream_tts(text_stream, websocket, stream_sid, interrupt_fn, on_audio_done=None):
    """
    Stream Deepgram TTS audio to Twilio in mulaw format
    
    Args:
        text_stream: Async iterator of text tokens
        websocket: Twilio websocket connection
        stream_sid: Twilio stream ID
        interrupt_fn: Function to check if interrupted
        on_audio_done: Optional callback called when last audio chunk is sent
                       (before waiting for sender to finish)
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

    MAX_TTS_SECONDS = 20.0

    for attempt in (1, 2):
        try:
            connect_start = time.time()
            async with websockets.connect(
                uri,
                extra_headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"},
                open_timeout=10,
                close_timeout=2,
                ping_interval=20,
                ping_timeout=20,
                max_size=2**20,
            ) as tts:
                connect_time = time.time() - connect_start
                print(f"[TTS] ✅ Connected in {connect_time:.3f}s")

                start_time = asyncio.get_event_loop().time()
                sender_done = asyncio.Event()

                async def sender():
                    """Send text tokens to Deepgram"""
                    tokens_sent = 0
                    full_text = ""
                    try:
                        async for token in _aiter(text_stream):
                            if interrupt_fn():
                                print(f"[TTS] ⚠️ Interrupted after {tokens_sent} tokens")
                                return
                            tokens_sent += 1
                            full_text += token
                            if tokens_sent == 1:
                                print(f"[TTS] 📤 First token: '{token[:50]}'")
                            await tts.send(json.dumps({"type": "Speak", "text": token}))
                        print(f"[TTS] 📤 Sent {tokens_sent} tokens: '{full_text[:80]}...'")
                    finally:
                        try:
                            await tts.send(json.dumps({"type": "Flush"}))
                        except Exception:
                            pass
                        sender_done.set()

                async def receiver():
                    """Receive audio from Deepgram and forward to Twilio"""
                    quiet_timeouts = 0
                    got_any_audio = False
                    chunks_sent = 0
                    receiver_start = asyncio.get_event_loop().time()

                    def _notify_audio_done():
                        if on_audio_done and got_any_audio:
                            try:
                                on_audio_done()
                            except Exception:
                                pass

                    while True:
                        if interrupt_fn():
                            _notify_audio_done()
                            return

                        if (asyncio.get_event_loop().time() - start_time) > MAX_TTS_SECONDS:
                            print(f"[TTS] ⚠️ Max duration reached")
                            _notify_audio_done()
                            return
                        
                        # SAFETY: Absolute receiver timeout to prevent infinite hang
                        if (asyncio.get_event_loop().time() - receiver_start) > 25.0:
                            print(f"[TTS] ⚠️ Receiver absolute timeout (25s)")
                            _notify_audio_done()
                            return

                        try:
                            # Reduced timeout from 1.5s to 0.3s for faster exit
                            msg = await asyncio.wait_for(tts.recv(), timeout=0.3)
                        except asyncio.TimeoutError:
                            if sender_done.is_set():
                                quiet_timeouts += 1
                                # Wait for Flushed signal — only exit on quiet timeout if enough silence
                                # (2 timeouts = 0.6s of no data after all text sent)
                                if got_any_audio and quiet_timeouts >= 2:
                                    print(f"[TTS] ✅ Done. Sent {chunks_sent} chunks")
                                    _notify_audio_done()
                                    return
                                if quiet_timeouts >= 4:
                                    print(f"[TTS] ⚠️ TIMEOUT: No audio after 4 quiet timeouts (1.2s total). Sent {chunks_sent} chunks")
                                    _notify_audio_done()
                                    return
                            continue
                        except websockets.ConnectionClosed:
                            print(f"[TTS] ⚠️ TIMEOUT/DISCONNECT: Deepgram TTS connection closed")
                            _notify_audio_done()
                            return

                        if isinstance(msg, bytes):
                            got_any_audio = True
                            chunks_sent += 1
                            
                            if chunks_sent == 1:
                                first_audio = time.time() - tts_start
                                print(f"[TTS] 🔊 First audio at {first_audio:.3f}s")
                            
                            try:
                                payload = base64.b64encode(msg).decode('utf-8')
                                await websocket.send(json.dumps({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": payload},
                                }))
                            except Exception:
                                _notify_audio_done()
                                return
                        
                        elif isinstance(msg, str):
                            try:
                                data = json.loads(msg)
                                if "error" in data:
                                    print(f"[TTS] ❌ Error: {data.get('error')}")
                                # Check for Deepgram's flushed signal (indicates audio complete)
                                if data.get("type") == "Flushed":
                                    print(f"[TTS] ✅ Flushed signal received. Sent {chunks_sent} chunks")
                                    _notify_audio_done()
                                    return
                            except json.JSONDecodeError:
                                pass

                await asyncio.gather(sender(), receiver())
                
                total_time = time.time() - tts_start
                print(f"[TTS] ✅ Complete in {total_time:.3f}s")
                return

        except websockets.ConnectionClosed:
            return
            
        except RuntimeError as e:
            if "close" in str(e).lower():
                return
            raise
            
        except Exception as e:
            print(f"[TTS] ⚠️ Error (attempt {attempt}): {e}")
            if attempt == 2:
                raise
            await asyncio.sleep(0.25)
