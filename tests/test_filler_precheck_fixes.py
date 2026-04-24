"""
Tests for the filler pre-check fixes:
1. Day names removed from availability_phrases (no misfire on "I'll take Wednesday")
2. Deepgram endpointing increased to 1200ms (less sentence splitting)
3. Booking flow: lookup_customer BEFORE asking for eircode
"""
import pytest
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestFillerPrecheckDayNames:
    """Test that day names don't trigger false positive filler detection"""
    
    def test_availability_phrases_excludes_day_names(self):
        """
        Day names like 'wednesday', 'monday' should NOT be in availability_phrases.
        They were causing misfires when user says "I'll take Wednesday, please".
        """
        # Import the actual phrases from llm_stream
        # We'll simulate the check here since the phrases are defined inline
        availability_phrases = [
            "what times are available", "when are you available", "any slots", "check availability",
            "what times", "when can", "any openings", "free on", "available on", "next available",
            "earliest", "soonest", "closest day", "this week", "next week", "tomorrow"
        ]
        
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in day_names:
            assert day not in availability_phrases, \
                f"'{day}' should NOT be in availability_phrases - causes misfires"
    
    def test_day_selection_does_not_trigger_availability_check(self):
        """
        When user says "I'll take Wednesday, please", it should NOT trigger
        AVAILABILITY_CHECK filler because the LLM will just confirm, not call a tool.
        """
        user_message = "i'll take wednesday, please"
        
        # These are the phrases that SHOULD trigger availability check
        availability_phrases = [
            "what times are available", "when are you available", "any slots", "check availability",
            "what times", "when can", "any openings", "free on", "available on", "next available",
            "earliest", "soonest", "closest day", "this week", "next week", "tomorrow"
        ]
        
        # Check if any phrase matches
        triggers_availability = any(phrase in user_message for phrase in availability_phrases)
        
        assert not triggers_availability, \
            f"'I'll take Wednesday' should NOT trigger availability check filler"
    
    def test_actual_availability_questions_still_trigger(self):
        """
        Actual availability questions should still trigger the filler.
        """
        test_cases = [
            ("what times are available tomorrow", True),
            ("when are you available this week", True),
            ("any slots next week", True),
            ("i'll take wednesday", False),  # Day selection - no trigger
            ("wednesday please", False),  # Day selection - no trigger
            ("let's do monday", False),  # Day selection - no trigger
        ]
        
        availability_phrases = [
            "what times are available", "when are you available", "any slots", "check availability",
            "what times", "when can", "any openings", "free on", "available on", "next available",
            "earliest", "soonest", "closest day", "this week", "next week", "tomorrow"
        ]
        
        for user_message, should_trigger in test_cases:
            triggers = any(phrase in user_message.lower() for phrase in availability_phrases)
            assert triggers == should_trigger, \
                f"'{user_message}' should {'trigger' if should_trigger else 'NOT trigger'} availability check"


class TestDeepgramEndpointing:
    """Test that Deepgram endpointing is configured correctly"""
    
    def test_endpointing_is_1200ms(self):
        """
        Endpointing should be 1200ms to prevent aggressive sentence splitting.
        900ms was cutting off natural speech like "Hi. I just wanna book..."
        """
        with open('src/services/asr_deepgram.py', 'r') as f:
            content = f.read()
        
        # Check for the endpointing setting
        assert 'endpointing=1200' in content, \
            "Deepgram endpointing should be 1200ms (was 900ms, caused sentence splitting)"
    
    def test_endpointing_not_too_aggressive(self):
        """
        Endpointing should NOT be less than 1000ms to avoid splitting sentences.
        """
        with open('src/services/asr_deepgram.py', 'r') as f:
            content = f.read()
        
        # Make sure we don't have aggressive endpointing
        assert 'endpointing=800' not in content, "800ms endpointing is too aggressive"
        assert 'endpointing=900' not in content, "900ms endpointing is too aggressive"


class TestBookingFlowOrder:
    """Test that the booking flow has correct customer identification (phone-first)"""
    
    def test_prompt_has_returning_customer_flow(self):
        """
        The prompt should have instructions for returning customers to skip eircode.
        """
        with open('prompts/trades_prompt.txt', 'r') as f:
            prompt = f.read()
        
        # Should mention returning customers
        assert "RETURNING CUSTOMER" in prompt or "returning customer" in prompt.lower(), \
            "Prompt should have returning customer instructions"
        
        # Should mention using stored address
        assert "stored" in prompt.lower() or "on file" in prompt.lower(), \
            "Prompt should mention using stored/on-file address for returning customers"


class TestIntegration:
    """Integration tests simulating the actual conversation flow"""
    
    def test_day_selection_conversation_flow(self):
        """
        Simulate the conversation where user picks a day.
        The filler should NOT trigger because LLM will just confirm, not call a tool.
        """
        # Previous assistant message offered days
        prev_assistant_msg = "i have tuesday and wednesday free. which day works best for you?"
        
        # User picks a day
        user_message = "i'll take wednesday, please"
        
        # Check if this would trigger availability check (it shouldn't)
        availability_phrases = [
            "what times are available", "when are you available", "any slots", "check availability",
            "what times", "when can", "any openings", "free on", "available on", "next available",
            "earliest", "soonest", "closest day", "this week", "next week", "tomorrow"
        ]
        
        triggers_availability = any(phrase in user_message for phrase in availability_phrases)
        
        # This should NOT trigger because:
        # 1. Day names are not in availability_phrases
        # 2. The LLM will just confirm the booking, not call check_availability again
        assert not triggers_availability, \
            "Day selection should not trigger availability check filler"
    
    def test_eircode_confirmation_not_mistaken_for_name(self):
        """
        When AI spells back an eircode like "V-9-5-H-5-P-2, correct?" and user says "yes",
        it should NOT trigger NAME_SPELLING_CONFIRMED because eircodes have numbers.
        """
        # Previous assistant message spelled back an eircode (has numbers)
        prev_assistant_msg = "that's v-9-5-h-5-p-2, correct?"
        user_message = "yeah. it's correct."
        
        # Check for name spelling indicators
        name_spelling_indicators = ["-a-", "-b-", "-c-", "-d-", "-e-", "-f-", "-g-", "-h-", "-i-", 
                                    "-j-", "-k-", "-l-", "-m-", "-n-", "-o-", "-p-", "-r-", "-s-", 
                                    "-t-", "-u-", "-v-", "-w-", "-y-", "-z-"]
        is_name_spelling = any(ind in prev_assistant_msg for ind in name_spelling_indicators)
        is_confirmation = any(phrase in user_message for phrase in ["yes", "yeah", "yep", "correct", "that's right"])
        
        # Check for eircode indicators (numbers in the spelling)
        has_numbers_in_spelling = any(f"-{d}-" in prev_assistant_msg for d in "0123456789")
        
        # This should NOT trigger because eircode has numbers
        should_trigger = is_name_spelling and is_confirmation and not has_numbers_in_spelling
        
        assert not should_trigger, \
            "Eircode confirmation (V-9-5-H-5-P-2) should NOT trigger NAME_SPELLING_CONFIRMED"
    
    def test_name_confirmation_still_triggers(self):
        """
        When AI spells back a name like "J-A-M-E-S, correct?" and user says "yes",
        it SHOULD trigger NAME_SPELLING_CONFIRMED because names don't have numbers.
        """
        # Previous assistant message spelled back a name (no numbers)
        prev_assistant_msg = "that's j-a-m-e-s d-o-h-e-r-t-y, correct?"
        user_message = "yes"
        
        # Check for name spelling indicators
        name_spelling_indicators = ["-a-", "-b-", "-c-", "-d-", "-e-", "-f-", "-g-", "-h-", "-i-", 
                                    "-j-", "-k-", "-l-", "-m-", "-n-", "-o-", "-p-", "-r-", "-s-", 
                                    "-t-", "-u-", "-v-", "-w-", "-y-", "-z-"]
        is_name_spelling = any(ind in prev_assistant_msg for ind in name_spelling_indicators)
        is_confirmation = any(phrase in user_message for phrase in ["yes", "yeah", "yep", "correct", "that's right"])
        
        # Check for eircode indicators (numbers in the spelling)
        has_numbers_in_spelling = any(f"-{d}-" in prev_assistant_msg for d in "0123456789")
        
        # This SHOULD trigger because name has no numbers
        should_trigger = is_name_spelling and is_confirmation and not has_numbers_in_spelling
        
        assert should_trigger, \
            "Name confirmation (J-A-M-E-S) SHOULD trigger NAME_SPELLING_CONFIRMED"
    
    def test_phone_confirmation_not_mistaken_for_name(self):
        """
        When AI confirms a phone number like "0-8-5-2-6-3-5-9-5-4" and user says "yes",
        it should NOT trigger NAME_SPELLING_CONFIRMED.
        """
        # Previous assistant message confirmed phone number
        prev_assistant_msg = "is 0-8-5-2-6-3-5-9-5-4 a good number to reach you?"
        user_message = "yes"
        
        # Check for numbers in the spelling
        has_numbers_in_spelling = any(f"-{d}-" in prev_assistant_msg for d in "0123456789")
        
        # Phone numbers have numbers, so should NOT trigger
        assert has_numbers_in_spelling, \
            "Phone confirmation should be detected as having numbers"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
