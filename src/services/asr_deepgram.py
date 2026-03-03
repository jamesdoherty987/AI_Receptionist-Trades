"""
Deepgram ASR (Automatic Speech Recognition) service

Simplified approach: Trust Deepgram's speech_final signal for utterance detection.
Deepgram's VAD is trained on millions of conversations and handles:
- Multi-segment utterances (accumulates automatically)
- End-of-speech detection (speech_final after endpointing silence)
- Interim results for real-time feedback
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
        self.interim_text = ""      # Current interim (in-progress) text
        self.speech_final = False   # True when Deepgram signals end of utterance
        
        # Duplicate detection (prevents echo/feedback loops)
        self._last_final_text = ""
        self._last_final_time = 0.0

    async def connect(self):
        """Connect to Deepgram websocket"""
        connect_start = time.time()
        
        self.ws = await websockets.connect(
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
            "&utterances=true"       # Enable utterance detection
            "&endpointing=900",     # 900ms silence = end of utterance (balanced: 800ms was cutting off, 1200ms too slow)
            extra_headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"},
            open_timeout=5,
            close_timeout=2,
            ping_interval=20,
            ping_timeout=10,
        )
        
        print(f"[ASR] Connected in {time.time() - connect_start:.3f}s")
        
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
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                
                is_speech_final = data.get("speech_final", False)
                is_final = data.get("is_final", False)
                
                alt = data.get("channel", {}).get("alternatives", [])
                transcript = alt[0].get("transcript", "") if alt else ""
                
                if is_speech_final:
                    # Deepgram says caller finished speaking
                    # Use the utterance text if available, otherwise use transcript
                    utterance = data.get("channel", {}).get("alternatives", [{}])[0].get("transcript", "")
                    final_text = utterance.strip() if utterance else transcript.strip()
                    
                    # Also check interim_text in case it has more complete text
                    if self.interim_text and len(self.interim_text) > len(final_text):
                        final_text = self.interim_text.strip()
                    
                    if final_text:
                        # Simple duplicate check
                        is_duplicate = (
                            final_text == self._last_final_text and 
                            (time.time() - self._last_final_time) < 3.0
                        )
                        
                        if not is_duplicate:
                            self.text = final_text
                            self.speech_final = True
                            self._last_final_text = final_text
                            self._last_final_time = time.time()
                            print(f"[ASR] ✅ SPEECH FINAL: '{final_text}'")
                        else:
                            print(f"[ASR] Duplicate ignored: '{final_text}'")
                    
                    # Clear interim for next utterance
                    self.interim_text = ""
                    
                elif is_final:
                    # Segment finalized but caller may still be speaking
                    # Update interim to show accumulated progress
                    if transcript.strip():
                        if self.interim_text:
                            self.interim_text = self.interim_text + " " + transcript.strip()
                        else:
                            self.interim_text = transcript.strip()
                        print(f"[ASR] Segment: '{transcript}' (interim: '{self.interim_text[:50]}...')")
                        
                else:
                    # Interim result - real-time feedback
                    # These come frequently as the user speaks
                    # We need to preserve any accumulated final segments
                    if transcript.strip():
                        # Check if we have accumulated segments from is_final events
                        # If so, the interim is just the current partial word/phrase
                        # Don't overwrite - Deepgram will send the full text on speech_final
                        pass  # Let accumulated interim_text from is_final events persist
                        
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
        """Get interim (in-progress) text for real-time display"""
        return self.interim_text.strip()
    
    def is_speech_finished(self) -> bool:
        """Check if Deepgram signaled end of utterance"""
        return self.speech_final

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
        # Keep _last_final_text for duplicate detection across clears

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
