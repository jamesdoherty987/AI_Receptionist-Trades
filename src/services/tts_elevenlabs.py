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

                start_time = asyncio.get_event_loop().time()

                # Initialize connection
                await tts.send(json.dumps({
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                }))

                sender_done = asyncio.Event()

                async def sender():
                    """Send text tokens to ElevenLabs"""
                    try:
                        async for token in _aiter(text_stream):
                            if interrupt_fn():
                                return
                            await tts.send(json.dumps({
                                "text": token,
                                "try_trigger_generation": True
                            }))
                    finally:
                        # Signal end of text
                        try:
                            await tts.send(json.dumps({"text": ""}))
                        except Exception:
                            pass
                        sender_done.set()

                async def receiver():
                    """Receive audio from ElevenLabs and forward to Twilio"""
                    quiet_timeouts = 0
                    got_any_audio = False

                    while True:
                        if interrupt_fn():
                            return

                        # Hard max duration check
                        if (asyncio.get_event_loop().time() - start_time) > MAX_TTS_SECONDS:
                            return

                        try:
                            msg = await asyncio.wait_for(tts.recv(), timeout=1.5)
                        except asyncio.TimeoutError:
                            # If we already sent all text and we've been quiet, exit
                            if sender_done.is_set():
                                quiet_timeouts += 1
                                if got_any_audio and quiet_timeouts >= 2:
                                    return
                                if quiet_timeouts >= 4:
                                    return
                            continue

                        data = json.loads(msg)

                        if data.get("audio"):
                            got_any_audio = True
                            await websocket.send(json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": data["audio"]},
                            }))

                        if data.get("isFinal"):
                            return

                await asyncio.gather(sender(), receiver())
                return

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
