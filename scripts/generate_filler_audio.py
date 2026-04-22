#!/usr/bin/env python3
"""
Generate pre-recorded filler audio files using ElevenLabs TTS
Uses the SAME voice as your live calls (ELEVENLABS_VOICE_ID from .env)
Uploads to R2 for fast global access

Run once to create the audio files:
    python scripts/generate_filler_audio.py

The server will automatically load these from R2 at startup.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file BEFORE importing config
from dotenv import load_dotenv
env_path = project_root / '.env'
load_dotenv(env_path, override=True)
print(f"📁 Loaded .env from: {env_path}")

from src.utils.config import config
from src.services.prerecorded_audio import (
    FILLER_PHRASES,
    generate_filler_audio_elevenlabs,
    upload_filler_to_r2
)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate pre-recorded filler audio files using ElevenLabs TTS")
    parser.add_argument("--new-only", action="store_true",
                        help="Only generate phrases that don't already exist in R2 (skip existing)")
    args = parser.parse_args()

    print("🎙️  Generating pre-recorded filler audio files...")
    print(f"   ElevenLabs Voice ID: {config.ELEVENLABS_VOICE_ID or 'NOT SET'}")
    print(f"   R2 Public URL: {os.getenv('R2_PUBLIC_URL') or 'NOT SET'}")
    if args.new_only:
        print(f"   Mode: NEW ONLY (skipping existing phrases)")
    print()
    
    # Check required config
    errors = []
    if not config.ELEVENLABS_API_KEY:
        errors.append("ELEVENLABS_API_KEY not set in .env")
    if not config.ELEVENLABS_VOICE_ID:
        errors.append("ELEVENLABS_VOICE_ID not set in .env")
    if not os.getenv('R2_ACCOUNT_ID'):
        errors.append("R2_ACCOUNT_ID not set in .env")
    if not os.getenv('R2_ACCESS_KEY_ID'):
        errors.append("R2_ACCESS_KEY_ID not set in .env")
    if not os.getenv('R2_SECRET_ACCESS_KEY'):
        errors.append("R2_SECRET_ACCESS_KEY not set in .env")
    if not os.getenv('R2_BUCKET_NAME'):
        errors.append("R2_BUCKET_NAME not set in .env")
    if not os.getenv('R2_PUBLIC_URL'):
        errors.append("R2_PUBLIC_URL not set in .env")
    
    if errors:
        print("❌ Missing required configuration:")
        for err in errors:
            print(f"   - {err}")
        print()
        print("Please set these in your .env file and try again.")
        return
    
    success_count = 0
    skipped_count = 0
    
    for phrase_id, text in FILLER_PHRASES.items():
        # In --new-only mode, check if this phrase already exists in R2
        if args.new_only:
            try:
                import httpx
                url = f"{os.getenv('R2_PUBLIC_URL').rstrip('/')}/audio/fillers/{phrase_id}.raw"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.head(url)
                    if resp.status_code == 200:
                        print(f"⏭️  Skipping (exists): '{text}'")
                        skipped_count += 1
                        continue
            except Exception:
                pass  # If check fails, generate anyway
        
        print(f"📝 Generating: '{text}'")
        
        try:
            # Generate audio using ElevenLabs (same voice as live calls)
            audio_data = await generate_filler_audio_elevenlabs(phrase_id, text)
            
            if not audio_data or len(audio_data) == 0:
                print(f"   ❌ No audio data generated")
                continue
                
            duration_ms = len(audio_data) / 8  # 8 bytes per ms at 8kHz mulaw
            print(f"   ✓ Generated: {len(audio_data)} bytes (~{duration_ms:.0f}ms)")
            
            # Upload to R2
            url = await upload_filler_to_r2(phrase_id, audio_data)
            print(f"   ✓ Uploaded to R2: {url}")
            
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print(f"{'='*60}")
    total = len(FILLER_PHRASES)
    if args.new_only and skipped_count > 0:
        print(f"⏭️  Skipped {skipped_count} existing phrases")
    if success_count == total - skipped_count:
        print(f"✅ Success! Generated {success_count} new filler phrases ({total} total in library)")
    elif success_count > 0:
        print(f"⚠️ Partial success: Generated {success_count}/{total - skipped_count} new filler phrases")
    else:
        if skipped_count == total:
            print(f"✅ All {total} phrases already exist in R2 — nothing to generate")
        else:
            print(f"❌ Failed to generate any filler phrases")
            return
    
    print()
    print("The server will automatically load these from R2 at startup.")
    print("Restart your server to use the new pre-recorded audio.")


if __name__ == "__main__":
    asyncio.run(main())
