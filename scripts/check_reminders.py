"""
Standalone script to check and send appointment reminders
Run this periodically (e.g., via cron every hour) to send reminders 24 hours before appointments
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.reminder_scheduler import run_reminder_check

if __name__ == "__main__":
    print("🔔 Running appointment reminder check...")
    try:
        run_reminder_check()
        print("✅ Reminder check complete")
    except Exception as e:
        print(f"❌ Error running reminder check: {e}")
        sys.exit(1)
