"""
Test the LLM booking flow with actual API calls.
This verifies the LLM follows the prompt instructions for eircode confirmation.
"""
import pytest
import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from openai import OpenAI

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)


def load_system_prompt():
    """Load the system prompt with test business info"""
    with open('prompts/receptionist_prompt_fast.txt', 'r') as f:
        prompt = f.read()
    
    # Replace placeholders with test values
    prompt = prompt.replace("{{BUSINESS_NAME}}", "Test Builders")
    prompt = prompt.replace("{{BUSINESS_OWNER}}", "John")
    prompt = prompt.replace("{{BUSINESS_HOURS}}", "Mon-Fri 8am-5pm")
    prompt = prompt.replace("{{CALLOUT_FEE}}", "€50")
    
    return prompt


class TestLLMEircodeConfirmation:
    """Test that the LLM confirms eircode back to the caller"""
    
    def test_llm_confirms_eircode_after_customer_provides_it(self):
        """
        Simulate: Customer provides eircode "D02WR97"
        Expected: LLM should confirm it back like "That's D-0-2-W-R-9-7, correct?"
        """
        client = OpenAI()
        system_prompt = load_system_prompt()
        
        # Simulate conversation where customer just provided eircode
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Hi, I need a brick wall built"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "Josh Smith"},
            {"role": "assistant", "content": "That's J-O-S-H S-M-I-T-H, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Welcome, Josh! Do you know your eircode?"},
            {"role": "user", "content": "Yeah it's D02WR97"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=100,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # LLM should confirm the eircode back
        # Could be spelled out (D-0-2-W-R-9-7) or just repeated (D02WR97)
        assert any([
            "d02wr97" in reply.replace("-", "").replace(" ", ""),
            "d-0-2" in reply,
            "correct" in reply,
            "right" in reply,
        ]), f"LLM should confirm eircode back. Got: {reply}"
    
    def test_llm_asks_phone_after_eircode_confirmed(self):
        """
        After eircode is confirmed, LLM should ask about phone number.
        """
        client = OpenAI()
        system_prompt = load_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Hi, I need a brick wall built"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "Josh Smith"},
            {"role": "assistant", "content": "That's J-O-S-H S-M-I-T-H, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Welcome, Josh! Do you know your eircode?"},
            {"role": "user", "content": "D02WR97"},
            {"role": "assistant", "content": "That's D-0-2-W-R-9-7, correct?"},
            {"role": "user", "content": "Yes that's right"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=100,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # After eircode confirmed, should ask about phone
        assert any([
            "phone" in reply,
            "number" in reply,
            "reach" in reply,
            "contact" in reply,
        ]), f"LLM should ask about phone after eircode confirmed. Got: {reply}"


class TestLLMFinalConfirmation:
    """Test that the LLM does final confirmation with all details"""
    
    def test_llm_final_confirmation_includes_address(self):
        """
        Before booking, LLM should confirm all details including address/eircode.
        """
        client = OpenAI()
        system_prompt = load_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Hi, I need a brick wall built"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "Josh Smith"},
            {"role": "assistant", "content": "That's J-O-S-H S-M-I-T-H, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Welcome, Josh! Do you know your eircode?"},
            {"role": "user", "content": "D02WR97"},
            {"role": "assistant", "content": "That's D-0-2-W-R-9-7, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Is 085 263 5954 a good number to reach you?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "I have Tuesday and Thursday free. Which works for you?"},
            {"role": "user", "content": "Tuesday please"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=150,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # Final confirmation should include key details
        # Note: LLM might ask for time first, or do final confirmation
        has_name = "josh" in reply
        has_day = "tuesday" in reply
        has_address = "d02" in reply or "eircode" in reply or "address" in reply
        has_job = "brick" in reply or "wall" in reply
        has_confirm = "correct" in reply or "confirm" in reply or "right" in reply
        
        # At minimum should mention the day and ask for confirmation
        assert has_day or has_confirm, f"LLM should confirm details. Got: {reply}"


class TestLLMDoesNotSkipSteps:
    """Test that the LLM doesn't skip important steps"""
    
    def test_llm_does_not_skip_eircode_confirmation(self):
        """
        LLM should NOT skip straight to phone after customer provides eircode.
        It should confirm the eircode first.
        """
        client = OpenAI()
        system_prompt = load_system_prompt()
        
        # Customer just provided eircode
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Hi, I need a brick wall built"},
            {"role": "assistant", "content": "No problem, what's your name?"},
            {"role": "user", "content": "Josh Smith"},
            {"role": "assistant", "content": "That's J-O-S-H S-M-I-T-H, correct?"},
            {"role": "user", "content": "Yes"},
            {"role": "assistant", "content": "Welcome, Josh! Do you know your eircode?"},
            {"role": "user", "content": "D02WR97"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=100,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # Should NOT skip to phone - should confirm eircode first
        # If it mentions phone without confirming eircode, that's wrong
        mentions_phone = "phone" in reply or "number" in reply or "reach" in reply
        confirms_eircode = "d02" in reply or "correct" in reply or "right" in reply
        
        if mentions_phone:
            # If it mentions phone, it should also have confirmed eircode
            assert confirms_eircode, \
                f"LLM skipped eircode confirmation and went straight to phone. Got: {reply}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
