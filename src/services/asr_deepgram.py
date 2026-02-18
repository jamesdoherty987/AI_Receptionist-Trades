"""
Deepgram ASR (Automatic Speech Recognition) service
"""
import asyncio
import json
import websockets
from src.utils.config import config


class DeepgramASR:
    """Manages Deepgram real-time speech recognition"""
    
    def __init__(self):
        self.text = ""
        self.interim_text = ""
        self.is_final = False
        self.ws = None
        self.queue = asyncio.Queue()
        self.closed = False
        self._send_task = None
        self._recv_task = None
        self._last_final_text = ""  # Track last final to prevent duplicates
        self._last_final_fingerprint = ""  # Fingerprint of last final for fuzzy matching

    async def connect(self):
        """Connect to Deepgram websocket"""
        self.ws = await websockets.connect(
            "wss://api.deepgram.com/v1/listen"
            f"?encoding={config.AUDIO_ENCODING}&sample_rate={config.AUDIO_SAMPLE_RATE}&channels={config.AUDIO_CHANNELS}"
            "&interim_results=true"
            "&model=nova-2-phonecall"  # Optimized for phone calls
            "&punctuate=true"  # Better sentence detection
            "&smart_format=true"  # Format numbers, dates properly
            "&filler_words=false"  # Remove um, uh, etc
            "&profanity_filter=false"  # Don't filter in case addresses contain unexpected words
            "&redact=false"  # Don't redact anything for addresses
            "&numerals=true"  # Better number handling for addresses
            "&language=en"  # General English
            "&diarize=false"  # Single speaker, no need for diarization
            "&utterances=true"  # Better utterance detection
            "&utt_split=0.8"  # Slightly longer pause before splitting utterances
            "&endpointing=300",  # Faster end-of-speech detection (300ms)
            extra_headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"},
            open_timeout=5,   # Faster connection timeout
            close_timeout=2,  # Faster close
            ping_interval=20, # Keep connection alive
            ping_timeout=10,  # Shorter timeout
        )
        self._recv_task = asyncio.create_task(self._recv())
        self._send_task = asyncio.create_task(self._send())

    async def _send(self):
        """Send audio data to Deepgram"""
        while not self.closed:
            data = await self.queue.get()
            if self.closed:
                break
            try:
                await self.ws.send(data)
            except websockets.exceptions.ConnectionClosed:
                break

    async def _recv(self):
        """Receive transcription results from Deepgram"""
        import re
        
        def fingerprint(s: str) -> str:
            """Create fingerprint by removing non-alphanumeric chars"""
            return re.sub(r'[^a-z0-9]', '', (s or "").lower())
        
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                is_final = data.get("is_final", False)
                alt = data.get("channel", {}).get("alternatives", [])
                if alt and alt[0].get("transcript"):
                    transcript = alt[0]["transcript"]
                    transcript_fp = fingerprint(transcript)
                    
                    if is_final:
                        # Check for duplicate using both exact match and fingerprint
                        is_duplicate = (
                            transcript.strip() == self.text.strip() or
                            transcript.strip() == self._last_final_text.strip() or
                            (transcript_fp and transcript_fp == self._last_final_fingerprint)
                        )
                        
                        if transcript.strip() and not is_duplicate:
                            self.text = transcript
                            self.is_final = True
                            self._last_final_text = transcript
                            self._last_final_fingerprint = transcript_fp
                            # Clear interim when we get final to prevent stale data
                            self.interim_text = ""
                            print(f"[ASR] Final transcript: '{transcript}'")
                        elif is_duplicate:
                            # Same text, just mark as final without re-setting
                            self.is_final = True
                            self.interim_text = ""
                            print(f"[ASR] Duplicate final ignored: '{transcript}'")
                    else:
                        # Only update interim if it's actually different
                        # This prevents the same interim from triggering multiple times
                        if transcript.strip() != self.interim_text.strip():
                            self.interim_text = transcript
        except websockets.exceptions.ConnectionClosed:
            pass

    async def feed(self, audio: bytes):
        """
        Feed audio data to ASR
        
        Args:
            audio: Raw audio bytes
        """
        if not self.closed:
            try:
                await self.queue.put(audio)
            except Exception:
                pass

    def get_text(self) -> str:
        """Get finalized transcription text"""
        return self.text.strip()
    
    def get_interim(self) -> str:
        """Get interim (in-progress) transcription text"""
        return self.interim_text.strip()
    
    def reset_final_flag(self):
        """Reset the final flag for next transcription"""
        self.is_final = False

    def clear_all(self):
        """Fully clear all transcription state"""
        self.text = ""
        self.interim_text = ""
        self.is_final = False
        # Note: We intentionally DON'T clear _last_final_text and _last_final_fingerprint
        # because we want to detect duplicates even across clear_all() calls
        # This prevents the same utterance from being processed twice

    async def close(self):
        """Close ASR connection"""
        self.closed = True

        # Unblock _send so it can exit quietly
        try:
            await self.queue.put(b"")
        except Exception:
            pass

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass

        for t in (self._send_task, self._recv_task):
            if t and not t.done():
                t.cancel()
