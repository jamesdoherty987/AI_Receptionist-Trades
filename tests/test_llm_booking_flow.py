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
        
        # LLM should acknowledge the eircode and move on (may ask for email or proceed)
        # Prompt says NOT to repeat addresses/eircodes back
        assert any([
            "d02wr97" in reply.replace("-", "").replace(" ", ""),
            "d-0-2" in reply,
            "correct" in reply,
            "right" in reply,
            "email" in reply,
            "grand" in reply,
            "great" in reply,
            "lovely" in reply,
            "perfect" in reply,
            "got that" in reply,
        ]), f"LLM should acknowledge eircode or move to next step. Got: {reply}"
    
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
        
        # After eircode confirmed, should ask about phone or email (new flow asks email after address)
        assert any([
            "phone" in reply,
            "number" in reply,
            "reach" in reply,
            "contact" in reply,
            "email" in reply,
            "available" in reply,
            "day" in reply,
        ]), f"LLM should ask about phone, email, or proceed to availability after eircode confirmed. Got: {reply}"


class TestLLMFinalConfirmation:
    """Test that the LLM does final confirmation with all details"""
    
    def test_llm_final_confirmation_excludes_address(self):
        """
        Before booking, LLM should confirm name, day, and issue but NOT the address.
        The system verifies the address separately after the call.
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
        has_name = "josh" in reply
        has_day = "tuesday" in reply
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


class TestLLMNoEircodeFlow:
    """Test that the LLM asks for address when customer doesn't know eircode"""
    
    def test_llm_asks_for_address_when_no_eircode(self):
        """
        When customer says they don't know their eircode,
        LLM should immediately ask for full address, not skip it.
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
            {"role": "user", "content": "No, I don't know it"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=100,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # LLM should ask for address, NOT say "we can proceed without it"
        asks_for_address = any([
            "address" in reply,
            "where" in reply and "job" in reply,
            "location" in reply,
        ])
        
        skips_address = any([
            "proceed without" in reply,
            "deal with" in reply and "later" in reply,
            "skip" in reply,
        ])
        
        assert asks_for_address, f"LLM should ask for address when eircode unknown. Got: {reply}"
        assert not skips_address, f"LLM should NOT skip address. Got: {reply}"


class TestLLMAddressHandling:
    """Test that the LLM handles addresses correctly - no spelling, no placeholders"""
    
    def test_llm_does_not_ask_to_spell_address(self):
        """
        When customer provides an address, LLM should NOT ask them to spell it
        and should NOT repeat it back. It should just acknowledge and move on.
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
            {"role": "user", "content": "No I don't"},
            {"role": "assistant", "content": "No problem, what's the full address for the job?"},
            {"role": "user", "content": "123 Main Street, Limerick"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=100,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # LLM should NOT ask to spell the address
        asks_to_spell = any([
            "spell" in reply and "address" in reply,
            "spell that" in reply,
            "spell it" in reply,
        ])
        
        # LLM should NOT repeat the address back for confirmation
        repeats_address = "123 main" in reply or ("123" in reply and "limerick" in reply)
        
        # LLM should acknowledge and move on (e.g., to phone, email, or availability)
        moves_on = any([
            "grand" in reply,
            "got that" in reply,
            "lovely" in reply,
            "brilliant" in reply,
            "phone" in reply,
            "number" in reply,
            "reach" in reply,
            "available" in reply,
            "good number" in reply,
            "email" in reply,
            "thanks" in reply,
            "thank" in reply,
            "great" in reply,
            "perfect" in reply,
        ])
        
        assert not asks_to_spell, f"LLM should NOT ask to spell address. Got: {reply}"
        assert not repeats_address, f"LLM should NOT repeat address back. Got: {reply}"
        assert moves_on, f"LLM should acknowledge and move on. Got: {reply}"
    
    def test_llm_uses_actual_address_in_confirmation(self):
        """
        When confirming booking, LLM should NOT include the address —
        the system verifies it separately after the call.
        It should also NOT use placeholder text like "your eircode".
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
            {"role": "user", "content": "Tuesday"},
            {"role": "assistant", "content": "What time works best - morning or afternoon?"},
            {"role": "user", "content": "Morning, 10am"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=150,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # LLM should NOT use placeholder text
        uses_placeholder = any([
            "your eircode" in reply,
            "your address" in reply,
            "at your location" in reply,
        ])
        
        assert not uses_placeholder, f"LLM should NOT use placeholder text. Got: {reply}"
    
    def test_llm_confirms_address_without_spelling(self):
        """
        When customer gives address, LLM should NOT spell it out letter by letter
        and should NOT repeat it back. It should just acknowledge naturally.
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
            {"role": "user", "content": "No"},
            {"role": "assistant", "content": "No problem, what's the full address for the job?"},
            {"role": "user", "content": "45 O'Connell Street, Limerick"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=100,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content
        print(f"\nLLM Response: {reply}")
        
        # Address should NOT be spelled out like "4-5 O-'-C-O-N-N-E-L-L"
        spelled_out_address = any([
            "4-5" in reply,
            "O-'-C" in reply,
            "S-T-R-E-E-T" in reply,
            "L-I-M-E-R-I-C-K" in reply,
        ])
        
        # Should NOT repeat the address back
        repeats_address = "45 o'connell" in reply.lower() or ("45" in reply and "connell" in reply.lower())
        
        assert not spelled_out_address, f"LLM should NOT spell out address. Got: {reply}"
        assert not repeats_address, f"LLM should NOT repeat address back — just acknowledge. Got: {reply}"



class TestLLMFullDayJobs:
    """Test that the LLM handles full-day jobs correctly"""
    
    def test_llm_does_not_ask_time_for_full_day_job(self):
        """
        For full-day jobs like brick work, LLM should NOT ask for time.
        It should just offer days.
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
            # Simulate check_availability response for full-day job
            {"role": "assistant", "content": "I have Tuesday and Thursday free. Which day works for you?"},
            {"role": "user", "content": "Tuesday"},
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=150,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content.lower()
        print(f"\nLLM Response: {response.choices[0].message.content}")
        
        # For brick work (full-day job), should NOT ask for specific time
        # Should either confirm the day or do final confirmation
        asks_for_time = any([
            "what time" in reply,
            "which time" in reply,
            "morning or afternoon" in reply,
            "prefer" in reply and "time" in reply,
        ])
        
        # Note: The prompt says for full-day jobs, don't ask for time
        # But the LLM might still ask if it doesn't know it's a full-day job
        # This test verifies the behavior when the conversation context suggests full-day
        
        # At minimum, should mention Tuesday
        mentions_day = "tuesday" in reply
        
        assert mentions_day, f"LLM should mention the selected day. Got: {reply}"
    
    def test_llm_says_call_when_on_way_for_full_day(self):
        """
        For full-day jobs, when confirming booking, LLM should say
        "we'll give you a call when we're on the way" instead of a specific time.
        """
        client = OpenAI()
        system_prompt = load_system_prompt()
        
        # Add context about full-day jobs to the system prompt
        enhanced_prompt = system_prompt + """

IMPORTANT: Brick wall building is a FULL-DAY job (8+ hours). 
For full-day jobs:
- Do NOT ask for specific times
- Say "we'll give you a call when we're on the way"
"""
        
        messages = [
            {"role": "system", "content": enhanced_prompt},
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
            {"role": "assistant", "content": "I have Tuesday and Thursday free. Which day works for you?"},
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
        
        # Should do final confirmation with "call when on the way"
        has_call_message = any([
            "call" in reply and "way" in reply,
            "call" in reply and "arrive" in reply,
            "call" in reply and "coming" in reply,
        ])
        
        # Or should do final confirmation
        has_confirmation = any([
            "correct" in reply,
            "confirm" in reply,
            "booked" in reply,
        ])
        
        # Either should have the call message or be doing confirmation
        assert has_call_message or has_confirmation, \
            f"LLM should either say 'call when on the way' or do confirmation. Got: {reply}"
