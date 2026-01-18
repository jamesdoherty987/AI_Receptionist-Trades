"""Quick test for the specific problematic phrase"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.appointment_detector import AppointmentDetector, AppointmentIntent

text = "i like 2pm, but is there anything later than that again?"
print(f"Testing: '{text}'")
result = AppointmentDetector.extract_appointment_details(text)
print(f"Intent: {result['intent']}")
print(f"Confidence: {result.get('confidence')}")
print(f"Expected: QUERY")
print(f"Result: {'✅ PASS' if result['intent'] == AppointmentIntent.QUERY else '❌ FAIL'}")
