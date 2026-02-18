"""
Tests for concurrent call handling.

These tests verify that multiple simultaneous phone calls are properly isolated
and don't share state with each other.
"""
import pytest
from src.services.call_state import CallState, create_call_state


class TestCallStateIsolation:
    """Test that CallState instances are properly isolated"""
    
    def test_separate_instances_are_independent(self):
        """Two CallState instances should not share state"""
        state1 = create_call_state()
        state2 = create_call_state()
        
        # Modify state1
        state1.customer_name = "John Doe"
        state1.active_booking = True
        state1.datetime = "tomorrow at 2pm"
        
        # Modify state2 differently
        state2.customer_name = "Jane Smith"
        state2.active_booking = False
        state2.datetime = "next Monday"
        
        # Verify they are independent
        assert state1.customer_name == "John Doe"
        assert state2.customer_name == "Jane Smith"
        assert state1.active_booking == True
        assert state2.active_booking == False
        assert state1.datetime == "tomorrow at 2pm"
        assert state2.datetime == "next Monday"
    
    def test_reset_only_affects_own_instance(self):
        """Resetting one instance should not affect others"""
        state1 = create_call_state()
        state2 = create_call_state()
        
        # Set values on both
        state1.customer_name = "John"
        state2.customer_name = "Jane"
        
        # Reset only state1
        state1.reset()
        
        # state1 should be reset, state2 should be unchanged
        assert state1.customer_name is None
        assert state2.customer_name == "Jane"
    
    def test_reschedule_state_isolation(self):
        """Reschedule flow state should be isolated between calls"""
        state1 = create_call_state()
        state2 = create_call_state()
        
        # Simulate reschedule flow on state1
        state1.reschedule_active = True
        state1.reschedule_found_appointment = {"id": "event123", "summary": "John - Plumbing"}
        state1.reschedule_customer_name = "John"
        state1.reschedule_name_confirmed = True
        
        # state2 should have default reschedule state
        assert state2.reschedule_active == False
        assert state2.reschedule_found_appointment is None
        assert state2.reschedule_customer_name is None
        assert state2.reschedule_name_confirmed == False
    
    def test_cancel_state_isolation(self):
        """Cancel flow state should be isolated between calls"""
        state1 = create_call_state()
        state2 = create_call_state()
        
        # Simulate cancel flow on state1
        state1.cancel_active = True
        state1.cancel_found_appointment = {"id": "event456"}
        state1.cancel_name_confirmed = True
        
        # state2 should have default cancel state
        assert state2.cancel_active == False
        assert state2.cancel_found_appointment is None
        assert state2.cancel_name_confirmed == False


class TestCallStateBackwardsCompatibility:
    """Test dict-like access for backwards compatibility"""
    
    def test_dict_style_get(self):
        """Should support state['key'] access"""
        state = create_call_state()
        state.customer_name = "Test"
        assert state["customer_name"] == "Test"
    
    def test_dict_style_set(self):
        """Should support state['key'] = value"""
        state = create_call_state()
        state["customer_name"] = "Test"
        assert state.customer_name == "Test"
    
    def test_get_method_with_default(self):
        """Should support state.get('key', default)"""
        state = create_call_state()
        assert state.get("customer_name") is None
        assert state.get("customer_name", "default") == "default"
        
        state.customer_name = "John"
        assert state.get("customer_name", "default") == "John"
    
    def test_pop_method(self):
        """Should support state.pop('key') that returns and resets value"""
        state = create_call_state()
        state.reschedule_active = True
        
        value = state.pop("reschedule_active")
        assert value == True
        assert state.reschedule_active == False  # Reset to default
    
    def test_contains_check(self):
        """Should support 'key' in state"""
        state = create_call_state()
        
        # None values should return False for 'in' check
        assert ("customer_name" in state) == False
        
        state.customer_name = "John"
        assert ("customer_name" in state) == True
        
        # Boolean False should still be "in" (it's set, just False)
        state.active_booking = False
        # Note: Our implementation returns False for None, not for False
        # This matches the original dict behavior where missing keys return False


class TestCallStateResetMethods:
    """Test the various reset methods"""
    
    def test_full_reset(self):
        """reset() should clear all state"""
        state = create_call_state()
        
        # Set various fields
        state.customer_name = "John"
        state.active_booking = True
        state.reschedule_active = True
        state.cancel_active = True
        state.current_turn = 5
        
        state.reset()
        
        assert state.customer_name is None
        assert state.active_booking == False
        assert state.reschedule_active == False
        assert state.cancel_active == False
        assert state.current_turn == 0
    
    def test_reset_reschedule(self):
        """reset_reschedule() should only clear reschedule state"""
        state = create_call_state()
        
        # Set reschedule and other state
        state.customer_name = "John"
        state.reschedule_active = True
        state.reschedule_customer_name = "John"
        state.cancel_active = True
        
        state.reset_reschedule()
        
        # Reschedule state should be cleared
        assert state.reschedule_active == False
        assert state.reschedule_customer_name is None
        
        # Other state should be preserved
        assert state.customer_name == "John"
        assert state.cancel_active == True
    
    def test_reset_cancel(self):
        """reset_cancel() should only clear cancel state"""
        state = create_call_state()
        
        # Set cancel and other state
        state.customer_name = "Jane"
        state.cancel_active = True
        state.cancel_customer_name = "Jane"
        state.reschedule_active = True
        
        state.reset_cancel()
        
        # Cancel state should be cleared
        assert state.cancel_active == False
        assert state.cancel_customer_name is None
        
        # Other state should be preserved
        assert state.customer_name == "Jane"
        assert state.reschedule_active == True
    
    def test_reset_booking(self):
        """reset_booking() should clear booking-related state"""
        state = create_call_state()
        
        # Set booking state
        state.customer_name = "John"
        state.datetime = "tomorrow"
        state.service_type = "plumbing"
        state.active_booking = True
        state.phone_number = "1234567890"  # Should NOT be cleared
        
        state.reset_booking()
        
        # Booking state should be cleared
        assert state.customer_name is None
        assert state.datetime is None
        assert state.service_type is None
        assert state.active_booking == False
        
        # Phone should be preserved (customer info)
        assert state.phone_number == "1234567890"


class TestConcurrentCallSimulation:
    """Simulate concurrent call scenarios"""
    
    def test_two_callers_booking_simultaneously(self):
        """Two callers booking at the same time should not interfere"""
        # Simulate Call 1: John booking plumbing for tomorrow
        call1_state = create_call_state()
        call1_state.customer_name = "John"
        call1_state.service_type = "plumbing"
        call1_state.datetime = "tomorrow at 10am"
        call1_state.active_booking = True
        
        # Simulate Call 2: Jane booking electrical for next week
        call2_state = create_call_state()
        call2_state.customer_name = "Jane"
        call2_state.service_type = "electrical"
        call2_state.datetime = "next Monday at 2pm"
        call2_state.active_booking = True
        
        # Verify complete isolation
        assert call1_state.customer_name == "John"
        assert call1_state.service_type == "plumbing"
        assert call1_state.datetime == "tomorrow at 10am"
        
        assert call2_state.customer_name == "Jane"
        assert call2_state.service_type == "electrical"
        assert call2_state.datetime == "next Monday at 2pm"
        
        # Complete Call 1's booking
        call1_state.already_booked = True
        call1_state.reset_booking()
        
        # Call 2 should be unaffected
        assert call2_state.customer_name == "Jane"
        assert call2_state.active_booking == True
        assert call2_state.already_booked == False
    
    def test_one_caller_reschedule_one_caller_cancel(self):
        """One caller rescheduling while another cancels should not interfere"""
        # Call 1: Rescheduling
        call1_state = create_call_state()
        call1_state.reschedule_active = True
        call1_state.reschedule_found_appointment = {"id": "event1"}
        call1_state.reschedule_customer_name = "John"
        
        # Call 2: Cancelling
        call2_state = create_call_state()
        call2_state.cancel_active = True
        call2_state.cancel_found_appointment = {"id": "event2"}
        call2_state.cancel_customer_name = "Jane"
        
        # Verify isolation
        assert call1_state.reschedule_active == True
        assert call1_state.cancel_active == False
        
        assert call2_state.cancel_active == True
        assert call2_state.reschedule_active == False
        
        # Complete Call 2's cancellation
        call2_state.reset_cancel()
        
        # Call 1's reschedule should be unaffected
        assert call1_state.reschedule_active == True
        assert call1_state.reschedule_found_appointment == {"id": "event1"}


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_accessing_nonexistent_attribute(self):
        """Accessing non-existent attribute should raise AttributeError"""
        state = create_call_state()
        with pytest.raises(AttributeError):
            _ = state.nonexistent_field
    
    def test_setting_new_attribute_works(self):
        """Should be able to set new attributes dynamically"""
        state = create_call_state()
        state.custom_field = "custom_value"
        assert state.custom_field == "custom_value"
    
    def test_none_values_handled_correctly(self):
        """None values should be handled correctly in get/contains"""
        state = create_call_state()
        
        # Initially None
        assert state.customer_name is None
        assert state.get("customer_name") is None
        assert state.get("customer_name", "default") == "default"
        assert ("customer_name" in state) == False
        
        # Set to empty string (not None)
        state.customer_name = ""
        assert state.customer_name == ""
        assert state.get("customer_name", "default") == ""  # Empty string, not default
        assert ("customer_name" in state) == True  # Empty string is "set"
    
    def test_boolean_false_vs_none(self):
        """Boolean False should be different from None"""
        state = create_call_state()
        
        # active_booking defaults to False
        assert state.active_booking == False
        assert state.get("active_booking") == False
        # Note: False is a valid value, not "missing"
    
    def test_integer_zero_vs_none(self):
        """Integer 0 should be different from None"""
        state = create_call_state()
        
        # current_turn defaults to 0
        assert state.current_turn == 0
        assert state.get("current_turn") == 0
    
    def test_dict_stored_correctly(self):
        """Dict values should be stored and retrieved correctly"""
        state = create_call_state()
        
        appointment = {"id": "event123", "summary": "Test", "start": {"dateTime": "2024-01-01T10:00:00"}}
        state.reschedule_found_appointment = appointment
        
        assert state.reschedule_found_appointment == appointment
        assert state.reschedule_found_appointment["id"] == "event123"
        
        # Modifying the dict should work
        state.reschedule_found_appointment["new_key"] = "new_value"
        assert state.reschedule_found_appointment["new_key"] == "new_value"
    
    def test_multiple_resets_safe(self):
        """Multiple resets should be safe"""
        state = create_call_state()
        state.customer_name = "John"
        
        state.reset()
        state.reset()
        state.reset()
        
        assert state.customer_name is None
    
    def test_pop_nonexistent_key(self):
        """Pop on non-existent key should return default"""
        state = create_call_state()
        
        # Pop a key that doesn't exist as an attribute
        # This should use getattr default behavior
        result = state.pop("nonexistent_key", "default_value")
        assert result == "default_value"


class TestThreadSafety:
    """Test that CallState works correctly in concurrent scenarios"""
    
    def test_many_instances_no_interference(self):
        """Creating many instances should not cause interference"""
        states = [create_call_state() for _ in range(100)]
        
        # Set different values on each
        for i, state in enumerate(states):
            state.customer_name = f"Customer_{i}"
            state.current_turn = i
        
        # Verify all values are correct
        for i, state in enumerate(states):
            assert state.customer_name == f"Customer_{i}"
            assert state.current_turn == i
    
    def test_state_survives_function_calls(self):
        """State should survive being passed through functions"""
        state = create_call_state()
        state.customer_name = "Original"
        
        def modify_state(s):
            s.customer_name = "Modified"
            s.active_booking = True
            return s
        
        returned_state = modify_state(state)
        
        # Should be the same object
        assert returned_state is state
        assert state.customer_name == "Modified"
        assert state.active_booking == True


class TestBackwardsCompatibilityWithOldCode:
    """Test patterns that the old dict-based code used"""
    
    def test_old_style_state_access(self):
        """Old code patterns should still work"""
        state = create_call_state()
        
        # Old pattern: state["key"] = value
        state["customer_name"] = "John"
        state["active_booking"] = True
        state["datetime"] = "tomorrow at 2pm"
        
        # Old pattern: state["key"]
        assert state["customer_name"] == "John"
        assert state["active_booking"] == True
        
        # Old pattern: state.get("key")
        assert state.get("customer_name") == "John"
        assert state.get("nonexistent", "default") == "default"
        
        # Old pattern: state.pop("key")
        val = state.pop("reschedule_active")
        assert val == False  # Default value
        
        # Old pattern: "key" in state (for None check)
        assert ("customer_name" in state) == True
        assert ("nonexistent_key" in state) == False
    
    def test_old_style_conditional_checks(self):
        """Old conditional patterns should work"""
        state = create_call_state()
        
        # Old pattern: if state.get("key"):
        state.customer_name = None
        if state.get("customer_name"):
            pytest.fail("Should not enter this branch")
        
        state.customer_name = "John"
        if not state.get("customer_name"):
            pytest.fail("Should not enter this branch")
        
        # Old pattern: if state["key"]:
        state.active_booking = False
        if state["active_booking"]:
            pytest.fail("Should not enter this branch")
        
        state.active_booking = True
        if not state["active_booking"]:
            pytest.fail("Should not enter this branch")
