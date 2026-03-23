#!/usr/bin/env python3
"""
Generate a realistic demo phone call audio for the landing page.
Uses ElevenLabs TTS with Irish accent voices:
  - AI Receptionist: the actual production voice from .env (ELEVENLABS_VOICE_ID)
  - Customer: Irish accent voice (DbwWo4rVEd5NrejHYUnm or fallback)

Output: scripts/demo_call.mp3
"""

import os
import sys
import requests
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from pydub import AudioSegment

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AI_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")  # 2fe8mwpfJcqvj9RGBsC1 - production AI voice
CUSTOMER_VOICE_ID = "DbwWo4rVEd5NrejHYUnm"  # Irish accent male
FALLBACK_VOICE_ID = os.getenv("ELEVENLABS_FALLBACK_VOICE_ID")  # cfgXMWoeQsY6I5kM4gP3

API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Realistic plumbing booking conversation - natural Irish phrasing
CONVERSATION = [
    # (speaker, text, pause_after_ms)
    ("ai", "Hi there, thanks for calling Plumbing Ireland, how can I help?", 300),
    ("customer", "Hi, yeah I've got a leak under my kitchen sink, and it's after getting worse since this morning.", 250),
    ("ai", "Ah no, sorry to hear that. I can get one of our lads out to you. Can I grab your name?", 250),
    ("customer", "Yeah, it's Mary O'Brien.", 200),
    ("ai", "Grand, Mary. And what's the best number to reach you on?", 250),
    ("customer", "Oh eight seven, six five four, three two one oh.", 200),
    ("ai", "Perfect. And what's the address for the job?", 250),
    ("customer", "Twelve Oakfield Drive, Swords.", 250),
    ("ai", "Lovely. I have a slot available tomorrow morning at ten, would that suit you?", 300),
    ("customer", "Ya, tomorrow at ten sounds great.", 200),
    ("ai", "Brilliant, I've booked that in for you Mary. You'll get a confirmation text shortly with all the details. Is there anything else I can help with?", 300),
    ("customer", "No that's perfect, thanks a million.", 200),
    ("ai", "No problem at all, we'll see you tomorrow. Have a great day!", 0),
]


def generate_elevenlabs(voice_id: str, text: str, label: str) -> AudioSegment:
    """Generate speech using ElevenLabs API."""
    print(f"  [{label}] {text[:65]}...")

    url = f"{API_URL}/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"    ⚠️  Voice {voice_id} failed ({resp.status_code}), trying fallback...")
        # Try fallback voice
        fallback = FALLBACK_VOICE_ID if voice_id != FALLBACK_VOICE_ID else AI_VOICE_ID
        url = f"{API_URL}/{fallback}"
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"ElevenLabs API error: {resp.status_code} - {resp.text[:200]}")

    return AudioSegment.from_mp3(BytesIO(resp.content))


def apply_phone_filter(audio: AudioSegment) -> AudioSegment:
    """Subtle phone-quality effect on the customer voice."""
    return audio.high_pass_filter(300).low_pass_filter(3400)


def main():
    print("🎙️  Generating demo call with ElevenLabs Irish voices...\n")
    print(f"   AI Voice: {AI_VOICE_ID}")
    print(f"   Customer Voice: {CUSTOMER_VOICE_ID}")
    print(f"   Fallback Voice: {FALLBACK_VOICE_ID}\n")

    # Start with a brief pause
    final_audio = AudioSegment.silent(duration=400)

    for speaker, text, pause_ms in CONVERSATION:
        if speaker == "ai":
            voice_id = AI_VOICE_ID
            label = "AI"
        else:
            voice_id = CUSTOMER_VOICE_ID
            label = "Customer"

        line_audio = generate_elevenlabs(voice_id, text, label)

        # Phone filter on customer voice only
        if speaker == "customer":
            line_audio = apply_phone_filter(line_audio)
            line_audio = line_audio - 2  # Slightly quieter

        final_audio += line_audio

        if pause_ms > 0:
            final_audio += AudioSegment.silent(duration=pause_ms)

    # Normalize
    final_audio = final_audio.normalize()

    # Export
    output_path = Path(__file__).parent / "demo_call.mp3"
    final_audio.export(str(output_path), format="mp3", bitrate="192k")

    duration_s = len(final_audio) / 1000
    size_kb = output_path.stat().st_size / 1024

    print(f"\n✅ Demo call saved to: {output_path}")
    print(f"   Duration: {duration_s:.1f}s")
    print(f"   Size: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
