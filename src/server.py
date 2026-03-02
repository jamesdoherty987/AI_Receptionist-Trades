"""
Combined HTTP + WebSocket server for production deployment.
Serves Flask HTTP API and Twilio Media Stream WebSocket on the same port.

This is required for hosting on platforms like Render that only expose one port.
- HTTP routes (Flask) handle API requests, Twilio webhooks, Stripe, etc.
- WebSocket route (/media) handles real-time Twilio voice media streams.

Usage:
  uvicorn src.server:app --host 0.0.0.0 --port 5000
"""
import asyncio
import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute, Mount
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.middleware.wsgi import WSGIMiddleware

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
        """Async iterate over incoming WebSocket messages from Twilio"""
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
    
    # Start background keepalive task to prevent connection going cold
    global _keepalive_task
    _keepalive_task = asyncio.create_task(openai_keepalive_loop())
    
    total_startup = time.time() - startup_start
    print(f"\n{'='*70}")
    print(f"[STARTUP] ✅ All startup tasks complete in {total_startup:.3f}s")
    print(f"[STARTUP] 🟢 SERVER READY FOR CALLS - OpenAI warmed up, fillers loaded")
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
        # CRITICAL: Include tools to warm up the same path as actual calls
        await asyncio.to_thread(
            client.chat.completions.create,
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            stream=True,  # Use streaming to match actual calls
            tools=CALENDAR_TOOLS,  # Include tools to warm up full path
            tool_choice="none",  # Don't actually call tools
        )
        elapsed = time.time() - start
        print(f"[STARTUP] OpenAI warmup complete in {elapsed:.2f}s (with {len(CALENDAR_TOOLS)} tools)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"[STARTUP] OpenAI warmup failed after {elapsed:.2f}s: {e}")


OPENAI_KEEPALIVE_INTERVAL = 60  # Ping every 60 seconds to keep connection warm
_keepalive_task = None  # Track task for graceful shutdown


async def openai_keepalive_loop():
    """
    Background task that pings OpenAI periodically to keep the connection warm.
    Prevents cold start delays after idle periods.
    
    IMPORTANT: Uses stream=True AND tools to match actual LLM calls - streaming and non-streaming
    may use different connection paths in OpenAI's infrastructure.
    
    Cost: ~$0.01/month (negligible)
    """
    from src.services.llm_stream import get_openai_client
    from src.services.calendar_tools import CALENDAR_TOOLS
    from src.utils.config import config
    
    print(f"[KEEPALIVE] Started OpenAI keepalive (every {OPENAI_KEEPALIVE_INTERVAL}s, with tools)")
    
    consecutive_failures = 0
    max_failures_before_warning = 3
    
    while True:
        try:
            await asyncio.sleep(OPENAI_KEEPALIVE_INTERVAL)
        except asyncio.CancelledError:
            print("[KEEPALIVE] Shutting down gracefully")
            return
        
        try:
            client = get_openai_client()
            start = time.time()
            
            # Use stream=True AND tools to match actual LLM calls
            # This warms up the exact same path used for responses
            def do_streaming_ping():
                stream = client.chat.completions.create(
                    model=config.CHAT_MODEL,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                    stream=True,  # CRITICAL: Match actual LLM calls
                    temperature=0.1,
                    tools=CALENDAR_TOOLS,  # CRITICAL: Include tools
                    tool_choice="none",  # Don't actually call tools
                )
                # Consume the stream to complete the request
                for _ in stream:
                    pass
            
            await asyncio.to_thread(do_streaming_ping)
            elapsed = time.time() - start
            consecutive_failures = 0  # Reset on success
            # Log first ping and then every 5 pings (5 minutes)
            if hasattr(openai_keepalive_loop, '_ping_count'):
                openai_keepalive_loop._ping_count += 1
            else:
                openai_keepalive_loop._ping_count = 1
            if openai_keepalive_loop._ping_count == 1 or openai_keepalive_loop._ping_count % 5 == 0:
                print(f"[KEEPALIVE] ✓ OpenAI streaming connection warm (ping #{openai_keepalive_loop._ping_count}, {elapsed:.2f}s)")
        except asyncio.CancelledError:
            print("[KEEPALIVE] Shutting down gracefully")
            return
        except Exception as e:
            consecutive_failures += 1
            # Only log after multiple failures to avoid log spam
            if consecutive_failures >= max_failures_before_warning:
                print(f"[KEEPALIVE] Ping failed {consecutive_failures}x: {e}")
                consecutive_failures = 0  # Reset to avoid continuous logging


async def shutdown_event():
    """Clean up background tasks on shutdown"""
    global _keepalive_task
    
    print("\n" + "="*70)
    print("[SHUTDOWN] ⚠️ Server shutting down - cleaning up...")
    print("[SHUTDOWN] Active WebSocket connections will be terminated")
    print("="*70 + "\n")
    
    if _keepalive_task and not _keepalive_task.done():
        _keepalive_task.cancel()
        try:
            await _keepalive_task
        except asyncio.CancelledError:
            pass
    
    # Give active calls a moment to wrap up (Render sends SIGTERM then waits)
    print("[SHUTDOWN] Waiting 2s for active calls to finish...")
    await asyncio.sleep(2)
    
    print("[SHUTDOWN] ✅ Cleanup complete")


# Create the combined ASGI application
# - /media -> WebSocket handler (Twilio media streams)
# - everything else -> Flask HTTP API
app = Starlette(
    routes=[
        WebSocketRoute("/media", media_websocket_endpoint),
        Mount("/", app=flask_asgi),
    ],
    on_startup=[startup_event],
    on_shutdown=[shutdown_event],
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
