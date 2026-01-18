"""
WebSocket server for Twilio media streams
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets
from src.handlers.media_handler import media_handler
from src.utils.config import config


async def main():
    """Start WebSocket server"""
    try:
        config.validate()
        print("✅ Configuration validated")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        exit(1)
    
    print("=" * 60)
    print("🚀 AI Receptionist WebSocket Server")
    print(f"📡 Listening on ws://0.0.0.0:8765")
    print(f"🌐 Public URL: {config.WS_PUBLIC_URL}")
    print("=" * 60)
    
    async with websockets.serve(
        media_handler,
        "0.0.0.0",
        8765,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**20,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
