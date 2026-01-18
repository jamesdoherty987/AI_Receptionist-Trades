"""
Test QUERY intent detection for availability questions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.appointment_detector import AppointmentDetector, AppointmentIntent

# Test cases for QUERY intent
test_cases = [
    "is there anything later than that?",
    "do you have anything after 2pm?",
    "what times are available?",
    "is there anything else?",
    "what about later times?",
    "anything available after 3?",
]

print("="*60)
print("Testing QUERY Intent Detection")
print("="*60)

for text in test_cases:
    print(f"\nUser: '{text}'")
    result = AppointmentDetector.extract_appointment_details(text)
    intent = result.get("intent")
    confidence = result.get("confidence", "unknown")
    
    if intent == AppointmentIntent.QUERY:
        print(f"✅ Correctly detected as QUERY (confidence: {confidence})")
    else:
        print(f"❌ Incorrectly detected as {intent} (confidence: {confidence})")

print("\n" + "="*60)
