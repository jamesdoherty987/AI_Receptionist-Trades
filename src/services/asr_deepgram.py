"""
Deepgram ASR (Automatic Speech Recognition) service

Three-layer end-of-speech detection:
1. speech_final (endpointing) — VAD detects silence after speech (~1.2s)
2. UtteranceEnd (utterance_end_ms) — word-timing gap detection, works in noisy
   environments where VAD fails (~1.2s)
3. Fallback timer — 3s safety net if Deepgram sends is_final but neither
   speech_final nor UtteranceEnd ever arrives
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
        # but never sends speech_final or UtteranceEnd. Accumulate all pending
        # segments and reset the timer on each new one. The media handler uses
        # this as a safety net — if 3s pass since the LAST segment with no
        # speech_final/UtteranceEnd, the accumulated text gets promoted.
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
                    "&endpointing=1200"
                    "&utterance_end_ms=1200",
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
                
                # Handle UtteranceEnd — Deepgram detected a word-timing gap.
                # This works even in noisy environments where speech_final
                # (VAD-based) fails. Promote accumulated segments to final.
                msg_type = data.get("type", "")
                if msg_type == "UtteranceEnd":
                    if self.last_segment_text and not self.speech_final:
                        self.text = self.last_segment_text
                        self.speech_final = True
                        print(f"[ASR] ✅ UTTERANCE END: '{self.last_segment_text}'")
                        self.last_segment_text = ""
                        self.last_segment_time = 0.0
                        self.interim_text = ""
                    continue
                
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
                    elif self.last_segment_text:
                        # speech_final arrived with empty transcript, but we have
                        # accumulated is_final segments. This happens when Deepgram's
                        # VAD detects silence after speech but the speech_final event
                        # itself has no transcript (the text was in earlier is_final
                        # segments). Promote the accumulated text instead of losing it.
                        self.text = self.last_segment_text
                        self.speech_final = True
                        print(f"[ASR] ✅ SPEECH FINAL (empty, promoting accumulated): '{self.last_segment_text}'")
                    
                    # Clear interim and segment tracking for next utterance
                    self.interim_text = ""
                    self.last_segment_text = ""
                    self.last_segment_time = 0.0
                    
                elif is_final:
                    # Segment finalized but caller may still be speaking
                    # Track for barge-in AND as fallback if speech_final never arrives
                    if transcript.strip():
                        self.interim_text = transcript.strip()
                        # Accumulate text from all is_final segments, but reset the
                        # timer on each new one. This way:
                        # - Long utterances: timer keeps resetting as segments arrive,
                        #   fallback never fires prematurely
                        # - Deepgram bug (no speech_final or UtteranceEnd): 3s after
                        #   the LAST segment, fallback fires with full accumulated text
                        if not self.last_segment_text:
                            self.last_segment_text = transcript.strip()
                        else:
                            self.last_segment_text += " " + transcript.strip()
                        # Always update time to the latest segment — this is the
                        # "silence timer" that measures how long since caller stopped
                        self.last_segment_time = time.time()
                        print(f"[ASR] Segment: '{transcript}' → accumulated: '{self.last_segment_text[:80]}'")
                        
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
        - We have accumulated segment text from is_final events
        - speech_final hasn't arrived
        - The LAST segment is older than `timeout` seconds (caller stopped speaking)
        
        This is a safety net for when Deepgram sends is_final but never speech_final.
        The timer resets on each new segment, so it measures silence since the caller
        last spoke. This prevents premature promotion during long multi-segment utterances.
        Subsequent is_final segments are appended to preserve the full utterance.
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
