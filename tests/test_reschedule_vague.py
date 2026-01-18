"""Test that vague reschedule requests are handled properly"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.appointment_detector import AppointmentDetector, AppointmentIntent

# Test vague reschedule requests
test_cases = [
    ("can i reschedule to an earlier time", True),
    ("can i move it to later", True),
    ("can i reschedule to 11am", False),  # Specific time
    ("move it to December 25 at 2pm", False),  # Specific time
]

print("="*60)
print("Testing Vague Reschedule Detection")
print("="*60)

for text, should_be_vague in test_cases:
    print(f"\nTesting: '{text}'")
    result = AppointmentDetector.extract_appointment_details(text)
    intent = result.get("intent")
    new_time = result.get("new_datetime", "")
    
    print(f"  Intent: {intent}")
    print(f"  New time: '{new_time}'")
    
    if intent == AppointmentIntent.RESCHEDULE:
        vague_times = ['earlier', 'later', 'sooner', 'another time', 'different time']
        is_vague = any(vague in (new_time or "").lower() for vague in vague_times)
        
        if should_be_vague:
            if is_vague:
                print(f"  ✅ Correctly identified as vague")
            else:
                print(f"  ❌ Should be vague but wasn't: '{new_time}'")
        else:
            if not is_vague:
                print(f"  ✅ Correctly identified as specific")
            else:
                print(f"  ❌ Should be specific but was vague")
    else:
        print(f"  ⚠️ Not detected as RESCHEDULE intent")

print("\n" + "="*60)
