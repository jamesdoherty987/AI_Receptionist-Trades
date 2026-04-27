"""
Combined HTTP + WebSocket server for production deployment.
Serves Flask HTTP API and Twilio Media Stream WebSocket on the same port.

This is required for hosting on platforms like Render that only expose one port.
- HTTP routes (Flask) handle API requests, Twilio webhooks, Stripe, etc.
- WebSocket route (/media) handles real-time Twilio voice media streams.

Usage:
  uvicorn src.server:app --host 0.0.0.0 --port 5000
"""
# CRITICAL: Set process timezone to business timezone BEFORE any imports.
# Render servers run in UTC, but datetime.now() must return the business's
# local time so bookings are stored correctly (e.g., "11am" means 11am Irish time,
# not 11am UTC which would be 12pm during BST).
import os
import time as _time
_tz = os.getenv("CALENDAR_TIMEZONE", "Europe/Dublin")
os.environ["TZ"] = _tz
if hasattr(_time, 'tzset'):
    _time.tzset()

import asyncio
import json
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute, Mount
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.middleware.wsgi import WSGIMiddleware
from contextlib import asynccontextmanager

# Import websockets for exception compatibility with media_handler
import websockets

# Import the async media handler
from src.handlers.media_handler import media_handler

# Import Flask app (this initializes Flask, CORS, routes, etc.)
from src.app import app as flask_app


class WebSocketAdapter:
    """
    Adapts a Starlette WebSocket to the interface expected by media_handler
    (compatible with websockets.WebSocketServerProtocol).
    
    The media_handler uses:
      - ws.remote_address (property)
      - async for msg in ws: (async iteration)
      - await ws.send(data) (send text/bytes)
    """

    def __init__(self, starlette_ws: WebSocket):
        self._ws = starlette_ws
        self.remote_address = (
            starlette_ws.client.host if starlette_ws.client else "unknown",
            starlette_ws.client.port if starlette_ws.client else 0,
        )

    async def send(self, data):
        """Send data to the WebSocket client (Twilio)"""
        try:
            if isinstance(data, bytes):
                await self._ws.send_bytes(data)
            else:
                await self._ws.send_text(str(data))
        except WebSocketDisconnect:
            raise websockets.ConnectionClosed(None, None)
        except RuntimeError:
            # Connection already closed
            raise websockets.ConnectionClosed(None, None)

    async def __aiter__(self):
        """Async iterate over incoming WebSocket messages from Telnyx TeXML"""
        try:
            while True:
                message = await self._ws.receive()
                msg_type = message.get("type", "")

                if msg_type == "websocket.receive":
                    # Twilio sends JSON text frames
                    if "text" in message:
                        yield message["text"]
                    elif "bytes" in message:
                        yield message["bytes"]
                elif msg_type == "websocket.disconnect":
                    # Clean disconnect
                    return
        except WebSocketDisconnect:
            # Starlette raises this on abnormal disconnect
            raise websockets.ConnectionClosed(None, None)


async def media_websocket_endpoint(websocket: WebSocket):
    """
    Handle Twilio Media Stream WebSocket connections.
    Accepts the connection and delegates to the async media_handler.
    """
    await websocket.accept()

    adapter = WebSocketAdapter(websocket)
    client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    print(f"[WS] Media stream connected from {client_info}")
    try:
        await media_handler(adapter)
    except websockets.ConnectionClosed:
        print(f"[WS] Twilio media stream disconnected (clean): {client_info}")
    except WebSocketDisconnect:
        print(f"[WS] Twilio media stream disconnected (starlette): {client_info}")
    except Exception as e:
        print(f"[WS] WebSocket error from {client_info}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# Wrap Flask WSGI app for ASGI compatibility
# This runs Flask in a thread pool - fully compatible with all Flask features
flask_asgi = WSGIMiddleware(flask_app)


async def startup_event():
    """Pre-load resources at server startup"""
    import time
    startup_start = time.time()
    print(f"\n{'='*70}")
    print(f"[STARTUP] Running startup tasks at {startup_start:.3f}")
    print(f"{'='*70}")
    
    # --- TIMING: Filler audio preload ---
    try:
        filler_start = time.time()
        from src.services.prerecorded_audio import preload_fillers_async, has_prerecorded_fillers
        await preload_fillers_async()
        filler_time = time.time() - filler_start
        print(f"[STARTUP] ✅ Filler audio loaded in {filler_time:.3f}s, ready: {has_prerecorded_fillers()}")
    except Exception as e:
        print(f"[STARTUP] ⚠️ Could not pre-load fillers: {e}")
    
    # --- TIMING: OpenAI warmup ---
    try:
        warmup_start = time.time()
        await warmup_openai()
        warmup_time = time.time() - warmup_start
        print(f"[STARTUP] ✅ OpenAI warmup completed in {warmup_time:.3f}s")
    except Exception as e:
        print(f"[STARTUP] ⚠️ OpenAI warmup failed: {e}")
    
    # --- TIMING: ElevenLabs warmup (startup only, no keepalive to save credits) ---
    try:
        el_warmup_start = time.time()
        await warmup_elevenlabs()
        el_warmup_time = time.time() - el_warmup_start
        print(f"[STARTUP] ✅ ElevenLabs warmup completed in {el_warmup_time:.3f}s")
    except Exception as e:
        print(f"[STARTUP] ⚠️ ElevenLabs warmup failed: {e}")
    
    # NOTE: No keepalive loop needed. The OpenAI Python SDK uses httpx which
    # has a default keepalive_expiry of 5 seconds — idle connections are dropped
    # automatically. A periodic ping can't keep them warm. The startup warmup
    # above is sufficient; subsequent calls just open fresh connections (fast).
    
    total_startup = time.time() - startup_start
    print(f"\n{'='*70}")
    print(f"[STARTUP] ✅ All startup tasks complete in {total_startup:.3f}s")
    print(f"[STARTUP] 🟢 SERVER READY FOR CALLS - OpenAI warmed up, ElevenLabs warmed up, fillers loaded")
    print(f"{'='*70}\n")


async def warmup_openai():
    """
    Warmup OpenAI API connection to avoid cold start delay on first real call.
    Makes a minimal API call to establish the HTTPS connection and warm up the client.
    IMPORTANT: Uses tools to match actual call path - tool definitions affect latency.
    """
    import time
    from src.services.llm_stream import get_openai_client
    from src.services.calendar_tools import CALENDAR_TOOLS
    from src.utils.config import config
    
    print("[STARTUP] Warming up OpenAI connection (with tools)...")
    start = time.time()
    
    try:
        client = get_openai_client()
        # Run sync OpenAI call in thread pool to avoid blocking event loop
        # Include tools to warm up the same path as actual calls
        await asyncio.to_thread(
            client.chat.completions.create,
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
            tools=CALENDAR_TOOLS,
            tool_choice="none",
            **config.max_tokens_param(value=5)
        )
        elapsed = time.time() - start
        print(f"[STARTUP] OpenAI warmup complete in {elapsed:.2f}s (with {len(CALENDAR_TOOLS)} tools)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"[STARTUP] OpenAI warmup failed after {elapsed:.2f}s: {e}")


async def warmup_elevenlabs():
    """
    Warmup ElevenLabs TTS WebSocket to avoid cold start on first real call.
    Opens a WebSocket, sends a tiny text, receives audio, then closes.
    This ensures ElevenLabs has our voice model loaded and ready.
    """
    import time
    from src.utils.config import config
    
    if config.TTS_PROVIDER != 'elevenlabs':
        print("[STARTUP] Skipping ElevenLabs warmup (TTS provider is not elevenlabs)")
        return
    
    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        print("[STARTUP] Skipping ElevenLabs warmup (missing API key or voice ID)")
        return
    
    voice_id = config.ELEVENLABS_VOICE_ID
    uri = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
        f"?model_id=eleven_flash_v2_5"
        f"&output_format=ulaw_8000"
        f"&optimize_streaming_latency=4"
    )
    
    print(f"[STARTUP] Warming up ElevenLabs TTS (voice: {voice_id})...")
    start = time.time()
    
    try:
        async with websockets.connect(
            uri,
            extra_headers={"xi-api-key": config.ELEVENLABS_API_KEY},
            open_timeout=10,
            close_timeout=5,
        ) as tts:
            # Send init + a short word + end-of-text to trigger audio generation
            await tts.send(json.dumps({
                "text": " ",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
            }))
            await tts.send(json.dumps({"text": "Hi.", "try_trigger_generation": True}))
            await tts.send(json.dumps({"text": ""}))
            
            # Consume audio response (we don't need it, just warming the connection)
            chunks = 0
            while True:
                try:
                    msg = await asyncio.wait_for(tts.recv(), timeout=5.0)
                    data = json.loads(msg)
                    if data.get("audio"):
                        chunks += 1
                    if data.get("isFinal"):
                        break
                except asyncio.TimeoutError:
                    break
            
            elapsed = time.time() - start
            print(f"[STARTUP] ElevenLabs warmup complete in {elapsed:.2f}s ({chunks} audio chunks received)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"[STARTUP] ElevenLabs warmup failed after {elapsed:.2f}s: {e}")


async def shutdown_event():
    """Clean up background tasks on shutdown"""
    print("\n" + "="*70)
    print("[SHUTDOWN] ⚠️ Server shutting down - cleaning up...")
    print("[SHUTDOWN] Active WebSocket connections will be terminated")
    print("[SHUTDOWN] ⚠️ If a call is active, it will be interrupted!")
    print("="*70 + "\n")
    
    # Give active calls more time to wrap up (Render sends SIGTERM then waits up to 30s)
    print("[SHUTDOWN] Waiting 5s for active calls to finish...")
    await asyncio.sleep(5)
    
    print("[SHUTDOWN] ✅ Cleanup complete")


@asynccontextmanager
async def lifespan(app):
    """Lifespan handler: startup and shutdown logic."""
    await startup_event()
    yield
    await shutdown_event()


# Create the combined ASGI application
# - /media -> WebSocket handler (Twilio media streams)
# - everything else -> Flask HTTP API
app = Starlette(
    routes=[
        WebSocketRoute("/media", media_websocket_endpoint),
        Mount("/", app=flask_asgi),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 5000))
    print("=" * 60)
    print("AI Receptionist - Combined HTTP + WebSocket Server")
    print(f"HTTP API:   http://0.0.0.0:{port}")
    print(f"WebSocket:  ws://0.0.0.0:{port}/media")
    print("=" * 60)

    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
