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
        self.speech_final = False  # True when Deepgram signals end of utterance (speech_final event)
        self.ws = None
        self.queue = asyncio.Queue()
        self.closed = False
        self._send_task = None
        self._recv_task = None
        self._last_final_text = ""  # Track last final to prevent duplicates
        self._last_final_fingerprint = ""  # Fingerprint of last final for fuzzy matching
        self._last_final_time = 0.0  # Timestamp of last final for echo detection
        self._last_transcript_time = 0.0  # When the last transcript was received (for staleness check)
        self._accumulated_text = ""  # Accumulate text across multiple is_final segments until speech_final

    async def connect(self):
        """Connect to Deepgram websocket"""
        import time as time_module
        connect_start = time_module.time()
        
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
            "&utterances=true"  # Enable utterance detection - Deepgram will signal end of speech
            "&endpointing=800",  # 800ms - let Deepgram detect end of utterance
            extra_headers={"Authorization": f"Token {config.DEEPGRAM_API_KEY}"},
            open_timeout=5,   # Faster connection timeout
            close_timeout=2,  # Faster close
            ping_interval=20, # Keep connection alive
            ping_timeout=10,  # Shorter timeout
        )
        
        ws_connect_time = time_module.time() - connect_start
        print(f"[ASR_TIMING] WebSocket connected in {ws_connect_time:.3f}s")
        
        self._recv_task = asyncio.create_task(self._recv())
        self._send_task = asyncio.create_task(self._send())
        
        total_connect_time = time_module.time() - connect_start
        print(f"[ASR_TIMING] Total ASR setup: {total_connect_time:.3f}s")

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
        import time
        
        def fingerprint(s: str) -> str:
            """Create fingerprint by removing non-alphanumeric chars"""
            return re.sub(r'[^a-z0-9]', '', (s or "").lower())
        
        def is_repetitive_pattern(text: str) -> bool:
            """
            Detect repetitive patterns like "Yeah. That's correct. Yeah." 
            which often indicate echo/feedback issues.
            """
            words = text.lower().split()
            if len(words) < 4:
                return False
            
            # Check if first and last words are the same short affirmation
            affirmations = {'yeah', 'yes', 'yep', 'ok', 'okay', 'no', 'nope', 'right', 'correct'}
            first_word = words[0].rstrip('.,!?')
            last_word = words[-1].rstrip('.,!?')
            
            if first_word in affirmations and first_word == last_word:
                return True
            
            return False
        
        def clean_repetitive_text(text: str) -> str:
            """Remove trailing repetitive affirmations that are likely echo"""
            words = text.split()
            if len(words) < 4:
                return text
            
            affirmations = {'yeah', 'yes', 'yep', 'ok', 'okay', 'no', 'nope', 'right', 'correct'}
            first_word = words[0].lower().rstrip('.,!?')
            last_word = words[-1].lower().rstrip('.,!?')
            
            # If first and last are same affirmation, remove the last one
            if first_word in affirmations and first_word == last_word:
                # Remove trailing affirmation
                cleaned = ' '.join(words[:-1])
                print(f"[ASR] Cleaned repetitive pattern: '{text}' -> '{cleaned}'")
                return cleaned
            
            return text
        
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                
                # Check for speech_final - this indicates end of utterance
                # This is the key signal that the caller has stopped speaking
                is_speech_final = data.get("speech_final", False)
                is_final = data.get("is_final", False)
                
                alt = data.get("channel", {}).get("alternatives", [])
                if alt and alt[0].get("transcript"):
                    transcript = alt[0]["transcript"]
                    transcript_fp = fingerprint(transcript)
                    
                    if is_final:
                        # Clean repetitive patterns (echo detection)
                        if is_repetitive_pattern(transcript):
                            transcript = clean_repetitive_text(transcript)
                            transcript_fp = fingerprint(transcript)
                        
                        # Accumulate text from this segment
                        if transcript.strip():
                            if self._accumulated_text:
                                self._accumulated_text += " " + transcript.strip()
                            else:
                                self._accumulated_text = transcript.strip()
                            self._last_transcript_time = time.time()
                            print(f"[ASR] Segment final: '{transcript}' (accumulated: '{self._accumulated_text[:60]}...')")
                        
                        # Clear interim when we get final segment
                        self.interim_text = ""
                        
                        # If this is also speech_final, the caller has finished speaking
                        if is_speech_final:
                            full_text = self._accumulated_text.strip()
                            
                            # Check for duplicate using both exact match and fingerprint
                            full_fp = fingerprint(full_text)
                            is_duplicate = (
                                full_text == self.text.strip() or
                                full_text == self._last_final_text.strip() or
                                (full_fp and full_fp == self._last_final_fingerprint)
                            )
                            
                            # Also check if this is a subset of the last final (echo picking up partial)
                            if not is_duplicate and self._last_final_text:
                                last_fp = fingerprint(self._last_final_text)
                                if full_fp in last_fp or last_fp in full_fp:
                                    if (time.time() - self._last_final_time) < 2.0:
                                        is_duplicate = True
                                        print(f"[ASR] Echo duplicate detected (timing): '{full_text}'")
                            
                            if full_text and not is_duplicate:
                                self.text = full_text
                                self.is_final = True
                                self.speech_final = True  # Signal that caller finished speaking
                                self._last_final_text = full_text
                                self._last_final_fingerprint = full_fp
                                self._last_final_time = time.time()
                                print(f"[ASR] ✅ SPEECH FINAL: '{full_text}'")
                            elif is_duplicate:
                                self.is_final = True
                                self.speech_final = True
                                print(f"[ASR] Duplicate speech_final ignored: '{full_text}'")
                            
                            # Reset accumulator for next utterance
                            self._accumulated_text = ""
                    else:
                        # Interim result - update interim text
                        # Combine accumulated text with current interim for full picture
                        if self._accumulated_text:
                            combined = self._accumulated_text + " " + transcript.strip()
                            if combined.strip() != self.interim_text.strip():
                                self.interim_text = combined.strip()
                                self._last_transcript_time = time.time()
                        elif transcript.strip() != self.interim_text.strip():
                            self.interim_text = transcript.strip()
                            self._last_transcript_time = time.time()
                
                # Handle speech_final without transcript (silence detected)
                elif is_speech_final and self._accumulated_text:
                    full_text = self._accumulated_text.strip()
                    full_fp = fingerprint(full_text)
                    
                    is_duplicate = (
                        full_text == self._last_final_text.strip() or
                        (full_fp and full_fp == self._last_final_fingerprint)
                    )
                    
                    if full_text and not is_duplicate:
                        self.text = full_text
                        self.is_final = True
                        self.speech_final = True
                        self._last_final_text = full_text
                        self._last_final_fingerprint = full_fp
                        self._last_final_time = time.time()
                        print(f"[ASR] ✅ SPEECH FINAL (silence): '{full_text}'")
                    
                    self._accumulated_text = ""
                    
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
    
    def get_transcript_age(self) -> float:
        """Get how old the current transcript is in seconds"""
        import time
        if self._last_transcript_time == 0.0:
            return 0.0
        return time.time() - self._last_transcript_time
    
    def reset_final_flag(self):
        """Reset the final flag for next transcription"""
        self.is_final = False
        self.speech_final = False

    def is_speech_finished(self) -> bool:
        """Check if Deepgram has signaled end of utterance (caller stopped speaking)"""
        return self.speech_final

    def clear_all(self):
        """Fully clear all transcription state"""
        self.text = ""
        self.interim_text = ""
        self.is_final = False
        self.speech_final = False
        self._accumulated_text = ""
        self._last_transcript_time = 0.0  # Reset timestamp so old transcripts aren't used
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
