"""
Test appointment booking flow with the new improvements
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.appointment_detector import AppointmentDetector
from src.services.llm_stream import process_appointment_with_calendar, _appointment_state, reset_appointment_state

async def test_booking_flow():
    """Test the complete booking flow"""
    
    print("\n" + "="*60)
    print("🧪 TESTING APPOINTMENT BOOKING FLOW")
    print("="*60 + "\n")
    
    # Reset state
    reset_appointment_state()
    
    # Simulate conversation history
    conversation = [
        {"role": "assistant", "content": "Hi, thank you for calling. How can I help you today?"},
        {"role": "user", "content": "hey can i book an appointment please"},
        {"role": "assistant", "content": "I'd be happy to help you book an appointment. May I have your full name please?"},
        {"role": "user", "content": "yeah my name is james daugherty"},
        {"role": "assistant", "content": "Thank you James. What date and time works best for you?"},
        {"role": "user", "content": "at twelve pm please"},
        {"role": "assistant", "content": "And what date would you like?"},
        {"role": "user", "content": "the twenty fifth of december"},
        {"role": "assistant", "content": "What's the reason for your visit?"},
        {"role": "user", "content": "i got injured"},
        {"role": "assistant", "content": "Let me confirm: James Daugherty on December 25th at 12:00 PM for an injury. Is that correct?"},
        {"role": "user", "content": "yeah that's correct"}
    ]
    
    print("📝 Simulating conversation...")
    print(f"Total messages: {len(conversation)}\n")
    
    # Test with final confirmation
    last_user_message = conversation[-1]["content"]
    
    print(f"Testing confirmation detection with: '{last_user_message}'")
    print()
    
    # Test confirmation word variations
    confirmation_tests = ["yeah", "ya", "yes", "yep", "correct", "that's right"]
    for word in confirmation_tests:
        is_match = word in last_user_message.lower()
        print(f"  {'✅' if is_match else '❌'} '{word}' in message: {is_match}")
    
    print()
    
    # Extract details from full conversation
    details = AppointmentDetector.extract_appointment_details(
        text=last_user_message,
        conversation_history=conversation
    )
    
    print("\n📊 EXTRACTED DETAILS:")
    print(f"  Intent: {details['intent']}")
    print(f"  Patient Name: {details.get('patient_name')}")
    print(f"  DateTime: {details.get('datetime')}")
    print(f"  Service Type: {details.get('service_type')}")
    print(f"  Confidence: {details.get('confidence')}")
    
    print("\n" + "="*60)
    print("✅ Test Complete - Check details above")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_booking_flow())
