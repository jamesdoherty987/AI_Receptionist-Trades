"""
Deepgram ASR (Automatic Speech Recognition) service

Simple approach: Trust Deepgram's speech_final signal for utterance detection.
Deepgram's VAD is trained on millions of conversations and handles:
- End-of-speech detection (speech_final after endpointing silence)
- Interim results for real-time feedback (used for barge-in)
"""
import asyncio
import json
import time
import websockets
from src.utils.config import config


class DeepgramASR:
    """Manages Deepgram real-time speech recognition"""
    
    def __init__(self):
        self.ws = None
        self.queue = asyncio.Queue()
        self.closed = False
        self._send_task = None
        self._recv_task = None
        
        # Transcription state
        self.text = ""              # Final text when speech_final=true
        self.interim_text = ""      # Latest interim text (for barge-in detection)
        self.speech_final = False   # True when Deepgram signals end of utterance
        
        # Fallback tracking: Deepgram sometimes sends is_final segments
        # but never sends speech_final. Track the last segment so the
        # media handler can use it as a safety net after a long timeout.
        self.last_segment_text = ""
        self.last_segment_time = 0.0

    async def connect(self):
        """Connect to Deepgram websocket"""
        connect_start = time.time()
        
        try:
            self.ws = await asyncio.wait_for(
                websockets.connect(
                    "wss://api.deepgram.com/v1/listen"
                    f"?encoding={config.AUDIO_ENCODING}"
                    f"&sample_rate={config.AUDIO_SAMPLE_RATE}"
                    f"&channels={config.AUDIO_CHANNELS}"
                    "&interim_results=true"
                    "&model=nova-2-phonecall"
                    "&punctuate=true"
                    "&smart_format=true"
                    "&filler_words=false"
                    "&numerals=true"
                    "&language=en"
                    "&utterances=true"
                    "&endpointing=1200",
                    extra_headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"},
                    open_timeout=5,
                    close_timeout=2,
                    ping_interval=20,
                    ping_timeout=10,
                ),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            print(f"[ASR] ❌ TIMEOUT: Deepgram connection timed out after 10s")
            raise
        
        print(f"[ASR] Connected in {time.time() - connect_start:.3f}s")
        
        self._recv_task = asyncio.create_task(self._recv())
        self._send_task = asyncio.create_task(self._send())

    async def _send(self):
        """Send audio data to Deepgram"""
        while not self.closed:
            try:
                data = await asyncio.wait_for(self.queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                print(f"[ASR] ⚠️ No audio received for 30s - connection may be idle")
                continue
            if self.closed:
                break
            try:
                await self.ws.send(data)
            except websockets.exceptions.ConnectionClosed:
                print(f"[ASR] ⚠️ WebSocket closed during send")
                break

    async def _recv(self):
        """Receive transcription results from Deepgram — trust Deepgram's output directly"""
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                
                is_speech_final = data.get("speech_final", False)
                is_final = data.get("is_final", False)
                
                alt = data.get("channel", {}).get("alternatives", [])
                transcript = alt[0].get("transcript", "") if alt else ""
                
                if is_speech_final:
                    # Deepgram says caller finished speaking — use its transcript directly
                    final_text = transcript.strip()
                    
                    if final_text:
                        self.text = final_text
                        self.speech_final = True
                        print(f"[ASR] ✅ SPEECH FINAL: '{final_text}'")
                    
                    # Clear interim and segment tracking for next utterance
                    self.interim_text = ""
                    self.last_segment_text = ""
                    self.last_segment_time = 0.0
                    
                elif is_final:
                    # Segment finalized but caller may still be speaking
                    # Track for barge-in AND as fallback if speech_final never arrives
                    if transcript.strip():
                        self.interim_text = transcript.strip()
                        self.last_segment_text = transcript.strip()
                        self.last_segment_time = time.time()
                        print(f"[ASR] Segment: '{transcript}'")
                        
                else:
                    # Interim result — update for barge-in detection
                    if transcript.strip():
                        self.interim_text = transcript.strip()
                        
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[ASR] ⚠️ Deepgram connection closed: {e}")
            self.closed = True
        except Exception as e:
            print(f"[ASR] ❌ Receive error: {e}")
            self.closed = True

    async def feed(self, audio: bytes):
        """Feed audio data to ASR"""
        if not self.closed:
            try:
                await self.queue.put(audio)
            except Exception:
                pass

    def get_text(self) -> str:
        """Get finalized text (only valid when speech_final=true)"""
        return self.text.strip()
    
    def get_interim(self) -> str:
        """Get interim (in-progress) text for barge-in detection"""
        return self.interim_text.strip()
    
    def is_speech_finished(self) -> bool:
        """Check if Deepgram signaled end of utterance"""
        return self.speech_final

    def has_pending_segment(self, timeout: float = 5.0) -> bool:
        """
        Check if there's a pending is_final segment that never got speech_final.
        
        Returns True if:
        - We have segment text from an is_final event
        - speech_final hasn't arrived
        - The segment is older than `timeout` seconds (caller stopped speaking)
        
        This is a safety net for when Deepgram sends is_final but never speech_final.
        """
        if self.speech_final or not self.last_segment_text or self.last_segment_time == 0.0:
            return False
        return (time.time() - self.last_segment_time) >= timeout

    def promote_segment(self):
        """
        Promote the pending segment to final text.
        Call this when has_pending_segment() returns True.
        """
        if self.last_segment_text:
            self.text = self.last_segment_text
            self.speech_final = True
            print(f"[ASR] ⚠️ FALLBACK: Promoting segment to final: '{self.last_segment_text}'")
            self.last_segment_text = ""
            self.last_segment_time = 0.0
            self.interim_text = ""

    def is_closed(self) -> bool:
        """Check if ASR connection is closed"""
        return self.closed

    async def reconnect(self):
        """Reconnect to Deepgram if connection was lost"""
        if not self.closed:
            return True
        
        print("[ASR] 🔄 Attempting to reconnect...")
        self.closed = False
        
        try:
            await self.connect()
            print("[ASR] ✅ Reconnected successfully")
            return True
        except Exception as e:
            print(f"[ASR] ❌ Reconnect failed: {e}")
            self.closed = True
            return False

    def clear(self):
        """Clear state for next utterance"""
        self.text = ""
        self.interim_text = ""
        self.speech_final = False
        self.last_segment_text = ""
        self.last_segment_time = 0.0

    async def close(self):
        """Close ASR connection"""
        self.closed = True
        
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
