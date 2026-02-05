"""
AI-Driven Reschedule Handler
Replaces rigid state machine logic with context-aware AI guidance
"""

from src.utils.date_parser import parse_datetime
from src.services.google_calendar import get_calendar_service
from src.utils.ai_text_parser import is_affirmative_response
import re


class AIRescheduleHandler:
    """Handles reschedule flow using AI context and minimal hardcoded logic"""
    
    @staticmethod
    def create_context_prompt(state, appointment_details, user_text):
        """
        Create a rich context prompt for the AI to understand the reschedule state
        and guide the conversation naturally
        """
        found_appointment = state.get("reschedule_found_appointment")
        customer_name = state.get("reschedule_customer_name")
        name_confirmed = state.get("reschedule_name_confirmed", False)
        last_attempted_time = state.get("reschedule_last_attempted_time")
        
        old_time = appointment_details.get("datetime")
        new_time = appointment_details.get("new_datetime")
        
        context_parts = []
        context_parts.append("[RESCHEDULE CONTEXT]")
        
        # What we know so far
        if found_appointment:
            event_time = found_appointment.get('start', {}).get('dateTime', '')
            if event_time:
                dt = parse_datetime(event_time)
                if dt:
                    context_parts.append(f"- Found appointment: {dt.strftime('%B %d at %I:%M %p')}")
        
        if customer_name:
            context_parts.append(f"- Customer name from appointment: {customer_name}")
        
        if name_confirmed:
            context_parts.append("- Customer confirmed this is their appointment")
        else:
            context_parts.append("- Customer has NOT confirmed this is their appointment yet")
        
        if last_attempted_time:
            context_parts.append(f"- Last attempted new time: {last_attempted_time} (was unavailable)")
        
        # What the AI should do
        context_parts.append("\n[YOUR TASK]")
        
        if not found_appointment:
            context_parts.append("Ask the customer what date/time their current appointment is so you can find it.")
        elif not name_confirmed:
            context_parts.append(f"Confirm this is {customer_name}'s appointment by asking if the name is correct.")
        elif not new_time or new_time == old_time:
            if last_attempted_time:
                context_parts.append("The previous time was unavailable. Ask what other time would work.")
            else:
                context_parts.append("Ask what new date/time they'd like to reschedule to.")
        else:
            if last_attempted_time and last_attempted_time != new_time:
                context_parts.append(f"Customer selected a new time: {new_time}. Proceed with this reschedule.")
            else:
                context_parts.append(f"Confirm moving the appointment to {new_time} and proceed if confirmed.")
        
        return "\n".join(context_parts)
    
    @staticmethod
    def should_proceed_with_reschedule(state, appointment_details, user_text):
        """
        Determine if we have all information needed to proceed with the reschedule.
        Uses minimal logic - mostly checks if we have the required pieces.
        """
        found_appointment = state.get("reschedule_found_appointment")
        name_confirmed = state.get("reschedule_name_confirmed", False)
        old_time = appointment_details.get("datetime")
        new_time = appointment_details.get("new_datetime")
        last_attempted_time = state.get("reschedule_last_attempted_time")
        
        # Need all three: found appointment, name confirmed, and valid new time
        if not (found_appointment and name_confirmed and new_time):
            return False, "Missing required information"
        
        # If times are the same, don't proceed
        if old_time and new_time:
            try:
                old_dt = parse_datetime(old_time)
                new_dt = parse_datetime(new_time)
                if old_dt and new_dt and old_dt == new_dt:
                    return False, "Same time - need different time"
            except:
                pass
        
        # If user is selecting an alternative after previous attempt was unavailable
        if last_attempted_time and last_attempted_time != new_time:
            return True, "User selected alternative time"
        
        # Otherwise, let AI determine if user confirmed
        # We return True and let the callback handle availability checking
        return True, "All information collected"
    
    @staticmethod
    def find_appointment_by_time(old_time_str):
        """Find appointment by time reference"""
        try:
            from src.utils.config import config
            
            # Check if calendar is enabled
            if not config.USE_GOOGLE_CALENDAR:
                return None, "Calendar functionality is currently disabled"
            
            calendar = get_calendar_service()
            if not calendar:
                return None, "Calendar service is unavailable"
                
            parsed_time = parse_datetime(old_time_str)
            
            if not parsed_time:
                return None, "Could not parse time"
            
            event = calendar.find_appointment_by_details(customer_name=None, appointment_time=parsed_time)
            
            if not event:
                return None, f"No appointment found at {parsed_time.strftime('%B %d at %I:%M %p')}"
            
            # Extract customer name
            event_summary = event.get('summary', '')
            if ' - ' in event_summary:
                customer_name = event_summary.split(' - ')[-1].strip()
            else:
                between_match = re.search(r'between\s+([^and]+)\s+and', event_summary, re.IGNORECASE)
                if between_match:
                    customer_name = between_match.group(1).strip()
                else:
                    customer_name = event_summary.strip()
            
            return {
                'event': event,
                'customer_name': customer_name,
                'time': parsed_time
            }, None
        
        except Exception as e:
            return None, f"Error finding appointment: {str(e)}"
    
    @staticmethod
    def detect_user_intent(user_text, state):
        """
        Use AI to detect user intent without rigid word matching.
        Returns: 'confirming', 'denying', 'providing_time', or 'unclear'
        """
        text_lower = user_text.lower().strip()
        
        # Use AI for confirmation/denial detection (more flexible than word lists)
        if is_affirmative_response(user_text, context="appointment confirmation"):
            return 'confirming'
        
        # Simple negative detection (keep as fallback)
        short_negative = text_lower in ['no', 'nope', 'nah', 'wrong', 'incorrect', 'not me']
        if short_negative:
            return 'denying'
        
        # Check for time indicators (let AI handle the rest)
        time_patterns = [
            r'\d{1,2}:\d{2}',  # 10:00, 2:30
            r'\d{1,2}\s*(am|pm|a\.m\.|p\.m\.)',  # 10am, 2 pm
            r'\b(morning|afternoon|evening|noon)\b',
            r'\b(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b'
        ]
        
        has_time = any(re.search(pattern, text_lower) for pattern in time_patterns)
        if has_time:
            return 'providing_time'
        
        return 'unclear'
