"""
Upload ambient background audio to R2 for use during calls.

Run once:
    python -m scripts.upload_ambient_audio

This uploads audio/ambient/office-noise.mp3 to R2 at audio/ambient/office-noise.mp3
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.services.storage_r2 import get_r2_storage

R2_FOLDER = "audio/ambient"
LOCAL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio", "ambient", "office-noise.mp3")


def main():
    if not os.path.exists(LOCAL_FILE):
        print(f"❌ File not found: {LOCAL_FILE}")
        sys.exit(1)

    file_size = os.path.getsize(LOCAL_FILE)
    print(f"📁 File: {LOCAL_FILE} ({file_size / 1024:.1f} KB)")

    r2 = get_r2_storage()
    if not r2:
        print("❌ R2 storage not configured. Check .env for R2_* variables.")
        sys.exit(1)

    with open(LOCAL_FILE, "rb") as f:
        url = r2.upload_file(
            file_data=f,
            filename="office-noise.mp3",
            folder=R2_FOLDER,
            content_type="audio/mpeg",
        )

    print(f"✅ Uploaded to R2: {url}")
    print(f"\nSet this in your .env or config:")
    print(f"  AMBIENT_AUDIO_URL={url}")


if __name__ == "__main__":
    main()
