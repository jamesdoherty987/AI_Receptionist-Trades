"""
Integration test: Simplified ASR → LLM pipeline.

Tests that the simplified ASR (trusting Deepgram directly) produces
transcripts that the LLM handles correctly in real conversation flows.

Uses actual OpenAI API calls with the real system prompt.
"""
import pytest
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)


def load_system_prompt():
    """Load the system prompt with test business info"""
    with open('prompts/trades_prompt.txt', 'r') as f:
        prompt = f.read()
    prompt = prompt.replace("{{BUSINESS_NAME}}", "Test Builders")
    prompt = prompt.replace("{{BUSINESS_OWNER}}", "John")
    prompt = prompt.replace("{{BUSINESS_HOURS}}", "Mon-Fri 8am-5pm")
    prompt = prompt.replace("{{CALLOUT_FEE}}", "€50")
    return prompt


def get_llm_response(messages):
    """Get a response from the LLM"""
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=120,
        temperature=0.1
    )
    return response.choices[0].message.content


class TestASRTranscriptQuality:
    """
    Test that Deepgram's direct speech_final transcripts (without our
    manual accumulation) produce good LLM responses.
    
    The key concern: Deepgram's speech_final transcript for the last segment
    might only contain the last segment's text, not the full utterance.
    The LLM should still handle this gracefully.
    """
    
    def test_full_utterance_on_speech_final(self):
        """
        Best case: Deepgram gives full utterance on speech_final.
        LLM should respond naturally.
        """
        prompt = load_system_prompt()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "assistant", "content": "Hi, thank you for calling. How can I help you today?"},
            {"role": "user", "content": "Hi, can I book an appointment please for a leak pipe in my bathroom?"},
        ]
        
        reply = get_llm_response(messages)
        print(f"\nLLM: {reply}")
        
        # LLM should engage with the booking request — confirm issue, ask for name, or both
        reply_lower = reply.lower()
        assert any(word in reply_lower for word in ["name", "who", "leak", "correct", "help", "book", "problem"]), \
            f"LLM should engage with booking request. Got: {reply}"
    
    def test_partial_transcript_on_speech_final(self):
        """
        Realistic case: speech_final only has the last segment.
        e.g., caller said "Hi, I need to book... a plumber for Tuesday"
        but speech_final transcript is just "a plumber for Tuesday"
        
        LLM should still understand the intent from context.
        """
        prompt = load_system_prompt()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "assistant", "content": "Hi, thank you for calling. How can I help you today?"},
            # This simulates getting only the last segment from speech_final
            {"role": "user", "content": "a plumber for Tuesday"},
        ]
        
        reply = get_llm_response(messages)
        print(f"\nLLM: {reply}")
        
        # LLM should still understand this is a booking request and ask for name
        reply_lower = reply.lower()
        assert any(word in reply_lower for word in ["name", "help", "book", "appointment", "plumb"]), \
            f"LLM should understand booking intent even from partial transcript. Got: {reply}"
    
    def test_eircode_transcript_direct(self):
        """
        Eircode scenario: Deepgram gives just the eircode on speech_final.
        LLM should confirm it back.
        """
        prompt = load_system_prompt()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Hi, I need a brick wall built"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "Josh Smith"},
            {"role": "assistant", "content": "That's J-O-S-H S-M-I-T-H, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Welcome, Josh! Do you know your eircode?"},
            # Deepgram speech_final gives just the eircode
            {"role": "user", "content": "D02 WR97"},
        ]
        
        reply = get_llm_response(messages)
        print(f"\nLLM: {reply}")
        
        # After eircode provided, AI should acknowledge and move on
        # (may ask for email, or proceed to availability)
        reply_lower = reply.lower().replace("-", "").replace(" ", "")
        eircode_confirmed = "d02wr97" in reply_lower or "d02" in reply.lower()
        moved_on = any(word in reply.lower() for word in ["email", "grand", "got that", "lovely", "great", "perfect", "brilliant"])
        assert eircode_confirmed or moved_on, \
            f"LLM should confirm eircode or move to next step. Got: {reply}"
    
    def test_yes_confirmation_direct(self):
        """
        Simple confirmation: Deepgram gives "Yes" on speech_final.
        LLM should proceed to next step.
        """
        prompt = load_system_prompt()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Hi, I need a leak fixed"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "Sarah Murphy"},
            {"role": "assistant", "content": "That's S-A-R-A-H M-U-R-P-H-Y, correct?"},
            {"role": "user", "content": "Yes"},
        ]
        
        reply = get_llm_response(messages)
        print(f"\nLLM: {reply}")
        
        # After name confirmed, should proceed (ask for eircode or look up customer)
        reply_lower = reply.lower()
        assert any(word in reply_lower for word in ["eircode", "address", "welcome", "postcode", "phone", "number", "look", "hold"]), \
            f"LLM should proceed after name confirmation. Got: {reply}"
    
    def test_address_when_no_eircode(self):
        """
        Caller doesn't know eircode. Deepgram gives "No I don't" on speech_final.
        LLM should ask for street address instead.
        """
        prompt = load_system_prompt()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Hi, I need a wall built"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "James O'Brien"},
            {"role": "assistant", "content": "That's J-A-M-E-S O-'-B-R-I-E-N, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Welcome, James! Do you know your eircode?"},
            {"role": "user", "content": "No I don't"},
        ]
        
        reply = get_llm_response(messages)
        print(f"\nLLM: {reply}")
        
        reply_lower = reply.lower()
        assert any(word in reply_lower for word in ["address", "street", "where", "location"]), \
            f"LLM should ask for address when no eircode. Got: {reply}"


class TestConversationFlowWithDirectTranscripts:
    """
    Test full conversation flows using direct Deepgram transcripts.
    Each user message simulates what speech_final would give us.
    """
    
    def test_full_booking_flow_steps(self):
        """
        Walk through the booking flow step by step.
        Each user message is what Deepgram's speech_final would produce.
        """
        prompt = load_system_prompt()
        client = OpenAI()
        
        conversation = [
            {"role": "system", "content": prompt},
            {"role": "assistant", "content": "Hi, thank you for calling. How can I help you today?"},
        ]
        
        # Step 1: Booking request
        conversation.append({"role": "user", "content": "I need to book a plumber for a leak"})
        reply1 = get_llm_response(conversation)
        conversation.append({"role": "assistant", "content": reply1})
        print(f"\n[Step 1] User: I need to book a plumber for a leak")
        print(f"[Step 1] LLM: {reply1}")
        assert any(w in reply1.lower() for w in ["name", "who", "leak", "correct", "help", "problem"]), \
            f"Step 1: Should engage with booking request. Got: {reply1}"
        
        # Step 2: Give name
        conversation.append({"role": "user", "content": "Mary Kelly"})
        reply2 = get_llm_response(conversation)
        conversation.append({"role": "assistant", "content": reply2})
        print(f"\n[Step 2] User: Mary Kelly")
        print(f"[Step 2] LLM: {reply2}")
        # Should spell back name or confirm it
        assert any(w in reply2.lower() for w in ["m-a-r-y", "mary", "k-e-l-l-y", "kelly", "correct", "spell"]), \
            f"Step 2: Should confirm/spell name. Got: {reply2}"
        
        # Step 3: Confirm name
        conversation.append({"role": "user", "content": "Yes that's right"})
        reply3 = get_llm_response(conversation)
        conversation.append({"role": "assistant", "content": reply3})
        print(f"\n[Step 3] User: Yes that's right")
        print(f"[Step 3] LLM: {reply3}")
        # Should proceed — ask for eircode, look up customer, or ask for address
        assert any(w in reply3.lower() for w in ["eircode", "address", "welcome", "postcode", "phone", "look", "hold"]), \
            f"Step 3: Should proceed after name confirmed. Got: {reply3}"
    
    def test_short_responses_handled(self):
        """
        Test that very short speech_final transcripts (1-2 words) 
        are handled correctly by the LLM in context.
        """
        prompt = load_system_prompt()
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "assistant", "content": "Hi, thank you for calling. How can I help you today?"},
            {"role": "user", "content": "Booking please"},
        ]
        
        reply = get_llm_response(messages)
        print(f"\nLLM: {reply}")
        
        # Even with a very short transcript, LLM should understand and ask for details
        reply_lower = reply.lower()
        assert any(w in reply_lower for w in ["name", "help", "what", "service", "book"]), \
            f"LLM should handle short transcript. Got: {reply}"
    
    def test_phone_number_transcript(self):
        """
        Phone numbers from Deepgram with numerals=true.
        Deepgram should give clean numbers.
        """
        prompt = load_system_prompt()
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Hi, I need a wall built"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "Tom Walsh"},
            {"role": "assistant", "content": "That's T-O-M W-A-L-S-H, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Welcome, Tom! Is 087 123 4567 a good number to reach you?"},
            {"role": "user", "content": "Yes that's my number"},
        ]
        
        reply = get_llm_response(messages)
        print(f"\nLLM: {reply}")
        
        # After phone confirmed, should ask for eircode/address
        reply_lower = reply.lower()
        assert any(w in reply_lower for w in ["eircode", "address", "postcode", "where", "location"]), \
            f"LLM should ask for address after phone confirmed. Got: {reply}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
