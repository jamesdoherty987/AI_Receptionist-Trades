"""
Per-call state management for concurrent call handling.

This module provides a CallState class that encapsulates all state that needs
to be isolated per phone call. This replaces the global _appointment_state
dictionary to enable proper concurrent call handling.

Usage:
    # In media_handler.py, create state at start of call:
    call_state = CallState()
    
    # Pass to stream_llm:
    async for token in stream_llm(messages, call_state=call_state, ...):
        ...
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class CallState:
    """
    Encapsulates all per-call state for appointment booking and call handling.
    
    Each phone call gets its own instance of this class, ensuring complete
    isolation between concurrent calls.
    """
    
    # --- Appointment booking state ---
    active_booking: bool = False
    initial_request: Optional[str] = None  # Track user's original request (e.g., "book job")
    customer_name: Optional[str] = None
    datetime: Optional[str] = None
    service_type: Optional[str] = None
    job_address: Optional[str] = None  # Address or eircode where work will be performed
    job_description: Optional[str] = None  # What needs doing
    urgency_level: Optional[str] = None  # Same-Day/Scheduled/Quote (no emergency)
    property_type: Optional[str] = None  # Residential/Commercial
    gathering_started: bool = False
    already_booked: bool = False  # Track if we've already completed a booking
    phone_number: Optional[str] = None
    phone_confirmed: bool = False
    caller_identified: bool = False  # Track if we've identified the caller
    client_info: Optional[Dict[str, Any]] = None  # Store client info from database
    last_booking_turn: int = 0  # Track which turn the last booking was made (for cooldown)
    current_turn: int = 0  # Track current conversation turn
    
    # --- Birth year (optional for trades) ---
    birth_year: Optional[str] = None
    
    # --- Phone confirmation state ---
    caller_phone_declined: bool = False
    asked_for_alternate_phone: bool = False
    phone_needs_confirmation: bool = False
    
    # --- Reschedule flow state ---
    reschedule_active: bool = False
    reschedule_found_appointment: Optional[Dict[str, Any]] = None
    reschedule_customer_name: Optional[str] = None
    reschedule_name_confirmed: bool = False
    reschedule_final_asked: bool = False
    reschedule_new_datetime: Optional[str] = None
    reschedule_display_time: Optional[str] = None
    reschedule_last_attempted_time: Optional[str] = None
    
    # --- Cancel flow state ---
    cancel_active: bool = False
    cancel_found_appointment: Optional[Dict[str, Any]] = None
    cancel_customer_name: Optional[str] = None
    cancel_name_confirmed: bool = False
    cancel_final_asked: bool = False
    
    # --- Address audio capture ---
    address_audio_url: Optional[str] = None
    address_audio_captured: bool = False
    awaiting_address_audio: bool = False
    _addr_audio_phase1_time: float = 0.0
    _addr_audio_collecting: bool = False  # True while caller is speaking their address (deferred capture)
    
    # --- LLM response control ---
    skip_llm_response: bool = False
    
    def reset(self):
        """Reset all state to initial values."""
        self.active_booking = False
        self.initial_request = None
        self.customer_name = None
        self.datetime = None
        self.service_type = None
        self.job_address = None
        self.job_description = None
        self.urgency_level = None
        self.property_type = None
        self.gathering_started = False
        self.already_booked = False
        self.phone_number = None
        self.phone_confirmed = False
        self.caller_identified = False
        self.client_info = None
        self.last_booking_turn = 0
        self.current_turn = 0
        self.birth_year = None
        self.caller_phone_declined = False
        self.asked_for_alternate_phone = False
        self.phone_needs_confirmation = False
        self.reschedule_active = False
        self.reschedule_found_appointment = None
        self.reschedule_customer_name = None
        self.reschedule_name_confirmed = False
        self.reschedule_final_asked = False
        self.reschedule_new_datetime = None
        self.reschedule_display_time = None
        self.reschedule_last_attempted_time = None
        self.cancel_active = False
        self.cancel_found_appointment = None
        self.cancel_customer_name = None
        self.cancel_name_confirmed = False
        self.cancel_final_asked = False
        self.skip_llm_response = False
        self.address_audio_url = None
        self.address_audio_captured = False
        self.awaiting_address_audio = False
        self._addr_audio_phase1_time = 0.0
        self._addr_audio_collecting = False
    
    def reset_reschedule(self):
        """Reset only reschedule-related state."""
        self.reschedule_active = False
        self.reschedule_found_appointment = None
        self.reschedule_customer_name = None
        self.reschedule_name_confirmed = False
        self.reschedule_final_asked = False
        self.reschedule_new_datetime = None
        self.reschedule_display_time = None
        self.reschedule_last_attempted_time = None
    
    def reset_cancel(self):
        """Reset only cancel-related state."""
        self.cancel_active = False
        self.cancel_found_appointment = None
        self.cancel_customer_name = None
        self.cancel_name_confirmed = False
        self.cancel_final_asked = False
    
    def reset_booking(self):
        """Reset booking state after successful booking."""
        self.datetime = None
        self.service_type = None
        self.customer_name = None
        self.job_address = None
        self.job_description = None
        self.urgency_level = None
        self.property_type = None
        self.active_booking = False
        self.gathering_started = False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get for backwards compatibility.
        Returns default if attribute doesn't exist OR if value is None."""
        value = getattr(self, key, default)
        if value is None:
            return default
        return value
    
    def pop(self, key: str, default: Any = None) -> Any:
        """Dict-like pop for backwards compatibility - gets value and resets to default."""
        value = getattr(self, key, default)
        # Reset to appropriate default based on type
        if isinstance(value, bool):
            setattr(self, key, False)
        elif isinstance(value, int):
            setattr(self, key, 0)
        else:
            setattr(self, key, None)
        return value
    
    def __setitem__(self, key: str, value: Any):
        """Dict-like set for backwards compatibility."""
        setattr(self, key, value)
    
    def __getitem__(self, key: str) -> Any:
        """Dict-like get for backwards compatibility."""
        return getattr(self, key)
    
    def __contains__(self, key: str) -> bool:
        """Dict-like contains for backwards compatibility."""
        return hasattr(self, key) and getattr(self, key) is not None


def create_call_state() -> CallState:
    """Factory function to create a new CallState instance."""
    return CallState()
