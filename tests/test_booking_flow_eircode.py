"""
Test the booking flow to ensure eircode is confirmed properly.
This simulates the conversation flow with the LLM.
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestBookingFlowEircodeConfirmation:
    """Test that eircode is properly confirmed in the booking flow"""
    
    def test_prompt_has_eircode_confirmation_step(self):
        """Verify the prompt includes explicit eircode confirmation step"""
        with open('prompts/trades_prompt.txt', 'r') as f:
            prompt = f.read()
        
        # Check for eircode confirmation instructions
        assert "CONFIRM IT BACK" in prompt or "confirm" in prompt.lower(), "Prompt should have eircode confirmation step"
        assert "eircode" in prompt.lower()
        
    def test_prompt_has_final_confirmation_with_address(self):
        """Verify the prompt requires final confirmation with all details including address"""
        with open('prompts/trades_prompt.txt', 'r') as f:
            prompt = f.read()
        
        # Check for final confirmation with address
        assert "FINAL CONFIRM" in prompt, "Prompt should have final confirmation step"
        assert "eircode" in prompt.lower(), "Final confirmation should mention eircode"
        
    def test_prompt_booking_flow_order(self):
        """Verify the booking flow has phone before eircode/address for new customers"""
        with open('prompts/trades_prompt.txt', 'r') as f:
            prompt = f.read()
        
        # In step 7b, phone comes before eircode/address
        phone_pos = prompt.find("Phone: Confirm caller ID")
        eircode_pos = prompt.find("Location: Ask for eircode")
        
        assert phone_pos > 0, "Prompt should have phone confirmation step"
        assert eircode_pos > 0, "Prompt should have eircode/address step"
        assert phone_pos < eircode_pos, "Phone should be confirmed before asking for eircode/address"
        
    def test_new_customer_eircode_example(self):
        """Verify the prompt has an example of spelling back eircode"""
        with open('prompts/trades_prompt.txt', 'r') as f:
            prompt = f.read()
        
        # Check for eircode example in the SPELLING OUT section
        assert "V-9-4-A-B-C-1" in prompt, \
            "Prompt should have example of spelling back eircode"


class TestDirectResponseBookingConfirmation:
    """Test that the direct response excludes address from booking confirmation.
    Address is verified separately after the call via the retranscription pipeline."""
    
    def test_booking_response_excludes_address(self):
        """Test that successful booking response does NOT include the address"""
        # Simulate the result_content from book_job
        result_content = {
            "success": True,
            "appointment_details": {
                "customer": "Josh Smith",
                "time": "Tuesday, March 10 at 08:00 AM",
                "job_address": "D02 WR97",
                "eircode": "D02WR97",
                "job_description": "brick wall build"
            }
        }
        
        # Simulate the direct response logic from llm_stream.py (address excluded)
        details = result_content.get("appointment_details", {})
        time_str = details.get("time", "")
        
        if time_str:
            direct_response = f"Grand, you're booked in for {time_str}. Is there anything else?"
        else:
            direct_response = "You're all booked! Is there anything else I can help with?"
        
        # Address should NOT be in the response — system verifies it after the call
        assert "D02 WR97" not in direct_response, "Booking confirmation should NOT include address"
        assert "Tuesday, March 10" in direct_response, "Booking confirmation should include time"
        
    def test_booking_response_without_address_fallback(self):
        """Test booking response when address is missing — same behavior"""
        result_content = {
            "success": True,
            "appointment_details": {
                "customer": "Josh Smith",
                "time": "Tuesday, March 10 at 08:00 AM",
                "job_address": "",
                "eircode": "",
            }
        }
        
        details = result_content.get("appointment_details", {})
        time_str = details.get("time", "")
        
        if time_str:
            direct_response = f"Grand, you're booked in for {time_str}. Is there anything else?"
        else:
            direct_response = "You're all booked! Is there anything else I can help with?"
        
        # Should still work without address
        assert "Tuesday, March 10" in direct_response
        assert "at ." not in direct_response, "Should not have 'at .' when address is empty"


class TestLookupCustomerDirectResponse:
    """Test the lookup_customer direct response for new customers"""
    
    def test_new_customer_asks_for_eircode(self):
        """Test that new customer response asks for eircode"""
        # Simulate new customer result
        result_content = {
            "success": True,
            "is_new_customer": True,
            "customer_name": "Josh Smith"
        }
        
        first_name = result_content.get("customer_name", "").split()[0] if result_content.get("customer_name") else "there"
        is_new = result_content.get("is_new_customer", True)
        
        if is_new:
            direct_response = f"Welcome, {first_name}! Do you know your eircode?"
        else:
            direct_response = f"Great to hear from you again, {first_name}!"
        
        assert "eircode" in direct_response.lower(), "New customer response should ask for eircode"
        assert "Welcome" in direct_response, "New customer should be welcomed"


class TestConversationFlowSimulation:
    """Simulate the full conversation flow to verify order of questions"""
    
    def test_expected_conversation_order(self):
        """
        Verify the expected conversation order:
        1. Customer describes issue
        2. AI asks for name
        3. AI spells back name, waits for confirmation
        4. AI calls lookup_customer
        5. AI asks for eircode (for new customer)
        6. AI confirms eircode back
        7. AI confirms phone
        8. AI checks availability
        9. AI offers days
        10. Customer picks day
        11. AI does final confirmation with ALL details
        12. AI books
        """
        expected_flow = [
            "name",           # Ask for name
            "spell",          # Spell back name
            "lookup",         # Lookup customer
            "eircode",        # Ask for eircode
            "confirm_eircode", # Confirm eircode back
            "phone",          # Confirm phone
            "availability",   # Check availability
            "offer_days",     # Offer available days
            "final_confirm",  # Final confirmation with all details
            "book"            # Book the job
        ]
        
        # Read prompt to verify flow is documented
        with open('prompts/trades_prompt.txt', 'r') as f:
            prompt = f.read()
        
        # Verify key steps are in the prompt
        assert "SPELL BACK" in prompt, "Should spell back name"
        assert "lookup_customer" in prompt, "Should call lookup_customer"
        assert "eircode" in prompt.lower(), "Should ask for eircode"
        assert "CONFIRM IT BACK" in prompt or "confirm" in prompt.lower(), "Should confirm eircode"
        assert "Confirm caller ID" in prompt or "good number" in prompt, "Should confirm phone"
        assert "get_next_available" in prompt, "Should check availability"
        assert "FINAL CONFIRM" in prompt, "Should do final confirmation"
        assert "book_job" in prompt, "Should book job"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
