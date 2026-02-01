"""
Deepgram TTS (Text-to-Speech) service
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
    Optimized for speed and reliability - typically 150-300ms latency
    
    Args:
        text_stream: Async iterator of text tokens
        websocket: Twilio websocket connection
        stream_sid: Twilio stream ID
        interrupt_fn: Function to check if interrupted
    """
    # Use faster model and optimized settings for speed
    uri = f"wss://api.deepgram.com/v1/speak?model=aura-luna-en&encoding={config.AUDIO_ENCODING}&sample_rate={config.AUDIO_SAMPLE_RATE}&container=none&filler_words=false&smart_format=true"

    MAX_TTS_SECONDS = 30.0  # Increased to prevent cutting off longer responses

    for attempt in (1, 2):
        try:
            async with websockets.connect(
                uri,
                extra_headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"},
                open_timeout=8,   # Faster connection timeout
                close_timeout=3,  # Faster close
                ping_interval=15, # More frequent pings for stability
                ping_timeout=10,  # Shorter ping timeout
                max_size=2**20,
            ) as tts:

                start_time = asyncio.get_event_loop().time()
                got_audio = False
                sender_done = asyncio.Event()
                flush_requested = asyncio.Event()
                flush_complete = asyncio.Event()

                async def sender():
                    """Send text tokens to Deepgram"""
                    token_sent_count = 0
                    try:
                        async for token in _aiter(text_stream):
                            if interrupt_fn():
                                print(f"   🛑 TTS interrupted after {token_sent_count} tokens")
                                return
                            
                            # Check for flush marker - forces Deepgram to speak NOW
                            if token == "<<<FLUSH>>>":
                                print(f"   💧 FLUSH marker detected - forcing TTS output and waiting for audio to finish...")
                                await tts.send(json.dumps({"type": "Flush"}))
                                flush_requested.set()
                                # Wait for receiver to confirm all audio has been sent
                                try:
                                    await asyncio.wait_for(flush_complete.wait(), timeout=5.0)
                                    print(f"   ✅ FLUSH complete - audio fully sent")
                                except asyncio.TimeoutError:
                                    print(f"   ⚠️ FLUSH timeout - continuing anyway")
                                flush_requested.clear()
                                flush_complete.clear()
                                continue  # Don't count or send this as a real token
                            
                            token_sent_count += 1
                            if token_sent_count == 1:
                                print(f"   📤 First TTS token sent: '{token[:20]}...'")
                            # Send text to Deepgram
                            await tts.send(json.dumps({"type": "Speak", "text": token}))
                    finally:
                        print(f"   ✅ TTS sender done - sent {token_sent_count} tokens")
                        # Signal end of text
                        try:
                            await tts.send(json.dumps({"type": "Flush"}))
                        except Exception:
                            pass
                        sender_done.set()

                async def receiver():
                    """Receive audio from Deepgram and forward to Twilio"""
                    nonlocal got_audio
                    quiet_timeouts = 0
                    last_audio_time = asyncio.get_event_loop().time()

                    while True:
                        if interrupt_fn():
                            return

                        # Hard max duration check
                        if (asyncio.get_event_loop().time() - start_time) > MAX_TTS_SECONDS:
                            return

                        try:
                            msg = await asyncio.wait_for(tts.recv(), timeout=0.3)  # Shorter timeout for flush detection
                        except asyncio.TimeoutError:
                            # Check if we're waiting for a flush to complete
                            if flush_requested.is_set():
                                # No audio for 300ms after flush = audio finished playing
                                if (asyncio.get_event_loop().time() - last_audio_time) > 0.3:
                                    print(f"   💧 Flush audio complete - signaling sender")
                                    flush_complete.set()
                            
                            if sender_done.is_set():
                                quiet_timeouts += 1
                                if got_audio and quiet_timeouts >= 1:  # Exit faster
                                    return
                                if quiet_timeouts >= 3:  # Reduced from 4
                                    return
                            continue

                        # Deepgram sends binary audio directly
                        if isinstance(msg, bytes):
                            got_audio = True
                            last_audio_time = asyncio.get_event_loop().time()
                            
                            # Split into 20ms chunks (160 bytes for mulaw 8kHz)
                            chunk_size = 160
                            for i in range(0, len(msg), chunk_size):
                                if interrupt_fn():
                                    return
                                
                                chunk = msg[i:i+chunk_size]
                                payload = base64.b64encode(chunk).decode('utf-8')
                                
                                await websocket.send(json.dumps({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": payload},
                                }))

                await asyncio.gather(sender(), receiver())
                return

        except Exception as e:
            print(f"⚠️ Deepgram TTS error (attempt {attempt}): {e}")
            if attempt == 2:
                raise
            await asyncio.sleep(config.TTS_CHUNK_DELAY)
