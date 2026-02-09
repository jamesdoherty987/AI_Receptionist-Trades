"""
Standalone WebSocket server for Twilio media streams.

For LOCAL DEVELOPMENT ONLY (with ngrok tunneling two separate ports).
In production, use src/server.py which combines HTTP + WebSocket on one port.

Usage (local dev):
  python -m src.media_ws
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from src.handlers.media_handler import media_handler
from src.utils.config import config


async def main():
    """Start standalone WebSocket server for local development"""
    try:
        config.validate()
        print("[SUCCESS] Configuration validated")
    except ValueError as e:
        print(f"[ERROR] Configuration error: {e}")
        exit(1)
    
    # Use WS_PORT env var or default to 8765 for local dev
    port = int(os.getenv("WS_PORT", 8765))
    
    print("=" * 60)
    print("AI Receptionist WebSocket Server (standalone / local dev)")
    print(f"Listening on ws://0.0.0.0:{port}")
    print(f"Public URL: {config.WS_PUBLIC_URL}")
    print("NOTE: For production, use src/server.py (combined HTTP+WS)")
    print("=" * 60)
    
    async with websockets.serve(
        media_handler,
        "0.0.0.0",
        port,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**20,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
