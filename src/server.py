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

# Create the combined ASGI application
# - /media -> WebSocket handler (Twilio media streams)
# - everything else -> Flask HTTP API
app = Starlette(
    routes=[
        WebSocketRoute("/media", media_websocket_endpoint),
        Mount("/", app=flask_asgi),
    ],
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
