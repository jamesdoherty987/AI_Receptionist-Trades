"""
OpenAI Tools/Function definitions for calendar operations.

ARCHITECTURE: Hybrid Approach
- TOOLS: Check availability (queries) - fast, maintains context
- CALLBACKS: Booking/cancellation/rescheduling - uses existing verification flow
"""

CALENDAR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment time slots. Use this IMMEDIATELY when customer asks about available times, slots, or when they're looking for appointments. Returns list of available slots with exact times. Use this for queries like 'what times next week', 'what about Monday', 'any slots Thursday'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (YYYY-MM-DD) or natural language like 'today', 'tomorrow', 'next Monday', 'next week'"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (YYYY-MM-DD) or natural language. If checking single day, use same as start_date. For 'next week' use end of week."
                    },
                    "service_type": {
                        "type": "string",
                        "enum": ["consultation", "checkup", "general"],
                        "description": "Type of appointment service"
                    }
                },
                "required": ["start_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Look up existing customer information by name, phone, or email. Use this EARLY to check if customer exists in system. Call this right after getting their name and contact info to see if they're a returning customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's full name to look up"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number (optional)"
                    },
                    "email": {
                        "type": "string",
                        "description": "Customer's email address (optional)"
                    }
                },
                "required": ["customer_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new appointment for a customer. CRITICAL: You MUST have a SPECIFIC date and time before calling this (e.g., 'tomorrow at 2pm', 'Monday at 9am'). DO NOT call this with vague times like 'within 2 hours', 'as soon as possible', or 'ASAP'. For urgent requests, suggest the next available time slot using check_availability first. Required info: name, phone, email, SPECIFIC appointment datetime, and reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's full name"
                    },
                    "email": {
                        "type": "string",
                        "description": "Customer's email address"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number"
                    },
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Date and time for the appointment in natural language (e.g., 'Monday at 9am', 'January 20th at 2pm')"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for visit (e.g., 'injury', 'checkup', 'general')"
                    }
                },
                "required": ["customer_name", "phone", "appointment_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. WORKFLOW: 1) Get the date/time from the user. 2) Call this function with ONLY the appointment_datetime (do NOT ask for customer name). 3) The system will look up the appointment and return the customer name. 4) Confirm with the user: 'Just to confirm, that appointment on [date/time] is for [name]. Is that correct?' 5) If they confirm, call this function again with both datetime and customer_name to complete the cancellation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Date and time of the appointment to cancel in natural language (e.g., 'Thursday at 3pm', 'January 15th at 3:00pm')"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Name of the customer whose appointment is being cancelled. ONLY provide this AFTER the user has confirmed the name. On first call, omit this to look up the appointment."
                    }
                },
                "required": ["appointment_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new time. WORKFLOW: 1) Get the current appointment date/time from the user. 2) Call this function with ONLY current_datetime (do NOT ask for customer name). 3) The system will return the customer name. 4) Confirm: 'Just to confirm, that appointment is for [name]. Is that correct?' 5) If confirmed, ask for new time. 6) Call this function again with all three parameters to complete the reschedule.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_datetime": {
                        "type": "string",
                        "description": "Current date and time of the appointment in natural language"
                    },
                    "new_datetime": {
                        "type": "string",
                        "description": "New date and time for the appointment in natural language. ONLY provide this AFTER confirming the customer name."
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Name of the customer whose appointment is being rescheduled. ONLY provide this AFTER the user has confirmed. On first call, omit this to look up the appointment."
                    }
                },
                "required": ["current_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_job",
            "description": "Book a new trade job/appointment for a customer. CRITICAL: You MUST have a SPECIFIC date and time before calling this (e.g., 'tomorrow at 2pm', 'Monday at 9am'). DO NOT call this with vague times like 'within 2 hours', 'as soon as possible', or 'ASAP'. For emergency requests, check availability first and suggest the next available time slot. Required info: customer name, phone, email (both mandatory), job address, job description, SPECIFIC datetime, and urgency level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's full name"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number (MANDATORY)"
                    },
                    "email": {
                        "type": "string",
                        "description": "Customer's email address (MANDATORY)"
                    },
                    "job_address": {
                        "type": "string",
                        "description": "Full address where the job will be performed (e.g., '32 Silvergrove, Ballybeg, Ennis, Clare')"
                    },
                    "job_description": {
                        "type": "string",
                        "description": "Detailed description of what needs to be done (e.g., 'power outage', 'blocked drain', 'burst pipe')"
                    },
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Date and time for the job in natural language (e.g., 'Monday at 9am', 'tomorrow at 2pm'). Must be SPECIFIC - not 'within 2 hours' or 'ASAP'."
                    },
                    "urgency_level": {
                        "type": "string",
                        "enum": ["emergency", "same-day", "scheduled", "quote"],
                        "description": "Urgency level: 'emergency' for immediate issues (burst pipes, gas leak), 'same-day' for urgent but not critical, 'scheduled' for planned work, 'quote' for estimate visits"
                    },
                    "property_type": {
                        "type": "string",
                        "enum": ["residential", "commercial"],
                        "description": "Type of property: 'residential' for homes, 'commercial' for businesses"
                    }
                },
                "required": ["customer_name", "phone", "email", "job_address", "job_description", "appointment_datetime", "urgency_level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_job",
            "description": "Cancel an existing job/appointment. Same workflow as cancel_appointment - get datetime first to look up, then confirm with customer name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Date and time of the job to cancel"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name (provide after confirmation)"
                    }
                },
                "required": ["appointment_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_job",
            "description": "Reschedule an existing job to a new time. Same workflow as reschedule_appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_datetime": {
                        "type": "string",
                        "description": "Current date and time of the job"
                    },
                    "new_datetime": {
                        "type": "string",
                        "description": "New date and time (provide after customer confirmation)"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name (provide after confirmation)"
                    }
                },
                "required": ["current_datetime"]
            }
        }
    }
]


def execute_tool_call(tool_name: str, arguments: dict, services: dict) -> dict:
    """
    Execute a tool call and return the result.
    
    HYBRID ARCHITECTURE:
    - This handles QUERY tools only (check_availability, lookup_customer)
    - Booking/cancellation/rescheduling use existing callback system
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments for the tool
        services: Dictionary containing service instances (google_calendar, db, etc.)
    
    Returns:
        Dictionary with success status and result data
    """
    from datetime import datetime, timedelta
    from ..utils.date_parser import parse_datetime
    from src.utils.config import config
    
    google_calendar = services.get('google_calendar')
    db = services.get('db')
    
    try:
        if tool_name == "check_availability":
            start_date_str = arguments.get('start_date')
            end_date_str = arguments.get('end_date', start_date_str)
            service_type = arguments.get('service_type', 'general')
            
            # Special handling for "this week" - today through Friday
            if start_date_str and 'this week' in start_date_str.lower():
                today = datetime.now()
                # From today through Friday of this week
                days_until_friday = (4 - today.weekday()) % 7  # Friday = 4
                if days_until_friday == 0 and today.weekday() == 4:  # If today is Friday
                    days_until_friday = 0  # Include today
                this_friday = today + timedelta(days=days_until_friday)
                
                start_date = today.replace(hour=9, minute=0, second=0, microsecond=0)
                end_date = this_friday.replace(hour=17, minute=0, second=0, microsecond=0)
                print(f"📅 'this week' expanded to {start_date.strftime('%A, %B %d')} - {end_date.strftime('%A, %B %d')}")
            # Special handling for "next week" - expand to Monday-Friday
            elif start_date_str and 'next week' in start_date_str.lower():
                today = datetime.now()
                # Find next Monday
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7  # If today is Monday, get next Monday
                next_monday = today + timedelta(days=days_until_monday)
                next_friday = next_monday + timedelta(days=4)
                
                start_date = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)
                end_date = next_friday.replace(hour=17, minute=0, second=0, microsecond=0)
                print(f"📅 'next week' expanded to {start_date.strftime('%A, %B %d')} - {end_date.strftime('%A, %B %d')}")
            else:
                # Parse dates normally - allow_past=True because we're checking a date range
                # get_available_slots_for_day will filter out past time slots
                start_date = parse_datetime(start_date_str, require_time=False, default_time=(9, 0), allow_past=True)
                if not start_date:
                    start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
                
                if end_date_str and end_date_str != start_date_str:
                    end_date = parse_datetime(end_date_str, require_time=False, default_time=(17, 0), allow_past=True)
                else:
                    end_date = start_date.replace(hour=17, minute=0)
            
            # Collect available slots across date range
            from collections import defaultdict
            slots_by_day = defaultdict(list)
            current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_search = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            print(f"🔍 Checking availability from {current_date.strftime('%Y-%m-%d')} to {end_search.strftime('%Y-%m-%d')}")
            
            # Get dynamic business days
            try:
                business_days = config.get_business_days_indices()
            except:
                business_days = config.BUSINESS_DAYS
            
            # Check all days in range (no early exit - we want full picture)
            while current_date <= end_search:
                # Only check business days (configured in config.BUSINESS_DAYS)
                if current_date.weekday() in business_days:
                    print(f"   📅 Checking {current_date.strftime('%A, %B %d')} (weekday {current_date.weekday()})")
                    try:
                        day_slots = google_calendar.get_available_slots_for_day(current_date)
                    except Exception as e:
                        print(f"   ⚠️ Connection error checking {current_date.strftime('%A, %B %d')}: {e}")
                        # Re-raise so retry logic in google_calendar handles it
                        raise
                    if day_slots:
                        day_key = current_date.strftime('%Y-%m-%d')
                        slots_by_day[day_key] = day_slots
                        print(f"      Found {len(day_slots)} slots")
                    else:
                        print(f"      No slots available")
                else:
                    print(f"   ⏭️ Skipping {current_date.strftime('%A, %B %d')} (weekend)")
                current_date += timedelta(days=1)
            
            if not slots_by_day:
                return {
                    "success": True,
                    "available_slots": [],
                    "message": f"No available slots between {start_date.strftime('%A, %B %d')} and {end_date.strftime('%A, %B %d')}"
                }
            
            # Sort days by weekday order (Mon-Fri), not chronological date
            # This ensures "next week" always lists Monday first, then Tuesday, etc.
            def weekday_sort_key(day_key):
                day_date = datetime.strptime(day_key, '%Y-%m-%d')
                weekday = day_date.weekday()  # Monday=0, Friday=4
                return weekday
            
            sorted_day_keys = sorted(slots_by_day.keys(), key=weekday_sort_key)
            
            # Build natural language summary for each day
            day_summaries = []
            for day_key in sorted_day_keys:
                day_slots = slots_by_day[day_key]
                day_date = datetime.strptime(day_key, '%Y-%m-%d')
                day_name = day_date.strftime('%A')
                
                # Get first and last available times
                first_time = day_slots[0].strftime('%I %p').lstrip('0').lower().replace(' 0', ' ')
                last_time = day_slots[-1].strftime('%I %p').lstrip('0').lower().replace(' 0', ' ')
                
                if len(day_slots) >= 6:
                    # Many slots available - describe as a range
                    summary = f"{day_name}: slots from {first_time} to {last_time}"
                elif len(day_slots) >= 3:
                    # Several slots - mention range
                    summary = f"{day_name}: {first_time}, {last_time}, and times in between"
                else:
                    # Few slots - list them specifically
                    times = [s.strftime('%I %p').lstrip('0').lower().replace(' 0', ' ') for s in day_slots]
                    if len(times) == 1:
                        summary = f"{day_name}: {times[0]}"
                    elif len(times) == 2:
                        summary = f"{day_name}: {times[0]} and {times[1]}"
                    else:
                        summary = f"{day_name}: {', '.join(times[:-1])}, and {times[-1]}"
                
                day_summaries.append(summary)
            
            # Create conversational message
            if len(day_summaries) == 1:
                natural_summary = day_summaries[0]
            elif len(day_summaries) == 2:
                natural_summary = f"{day_summaries[0]}, and {day_summaries[1]}"
            else:
                natural_summary = f"{', '.join(day_summaries[:-1])}, and {day_summaries[-1]}"
            
            # Also provide structured data for booking
            all_slots = []
            for day_slots in slots_by_day.values():
                all_slots.extend(day_slots)
            
            formatted_slots = []
            for slot in all_slots[:20]:  # Cap at 20 for data size
                formatted_slots.append({
                    "date": slot.strftime('%A, %B %d, %Y'),
                    "time": slot.strftime('%I:%M %p'),
                    "iso": slot.isoformat()
                })
            
            # Determine appropriate time reference for message
            time_reference = "Next week" if 'next week' in start_date_str.lower() else "This week"
            
            return {
                "success": True,
                "available_slots": formatted_slots,
                "total_count": len(all_slots),
                "natural_summary": natural_summary,
                "message": f"{time_reference} I have: {natural_summary}",
                "voice_instruction": "Say the natural_summary naturally and conversationally. Then ask which day/time works for them."
            }
        
        elif tool_name == "lookup_customer":
            customer_name = arguments.get('customer_name')
            phone = arguments.get('phone')
            email = arguments.get('email')
            
            if not customer_name:
                return {
                    "success": False,
                    "error": "Customer name is required"
                }
            
            # Check database for existing customer
            if db:
                try:
                    # Try by name, phone, or email
                    clients = db.get_clients_by_name(customer_name.lower())
                    if len(clients) == 1:
                        client = clients[0]
                        return {
                            "success": True,
                            "customer_exists": True,
                            "customer_info": {
                                "id": client['id'],
                                "name": client['name'],
                                "phone": client.get('phone'),
                                "email": client.get('email')
                            },
                            "message": f"Found customer: {client['name']}"
                        }
                    elif len(clients) > 1:
                        return {
                            "success": True,
                            "customer_exists": True,
                            "multiple_matches": True,
                            "count": len(clients),
                            "message": f"Found {len(clients)} customers named {customer_name}. Need phone or email to confirm which one."
                        }
                    else:
                        # FUZZY MATCH: Try phonetically similar names (for ASR errors)
                        from difflib import SequenceMatcher
                        all_clients = db.get_all_clients()
                        
                        for potential_client in all_clients:
                            # Check name similarity (75%+ match)
                            similarity = SequenceMatcher(None, 
                                customer_name.lower(), 
                                potential_client['name'].lower()).ratio()
                            
                            if similarity >= 0.75:  # 75% similar = likely match
                                print(f"✅ Fuzzy match: '{customer_name}' → '{potential_client['name']}' (similarity: {similarity:.2%})")
                                return {
                                    "success": True,
                                    "customer_exists": True,
                                    "fuzzy_match": True,
                                    "heard_name": customer_name,
                                    "actual_name": potential_client['name'],
                                    "customer_info": {
                                        "id": potential_client['id'],
                                        "name": potential_client['name'],
                                        "phone": potential_client.get('phone'),
                                        "email": potential_client.get('email')
                                    },
                                    "message": f"Found returning customer: {potential_client['name']} (I heard {customer_name}, but found a close match)"
                                }
                        
                        return {
                            "success": True,
                            "customer_exists": False,
                            "message": f"No existing customer found for {customer_name}. This is a new customer."
                        }
                except Exception as e:
                    print(f"❌ Error looking up customer: {e}")
                    return {
                        "success": False,
                        "error": f"Database error: {str(e)}"
                    }
            
            return {
                "success": False,
                "error": "Database not available"
            }
        
        elif tool_name == "book_appointment":
            customer_name = arguments.get('customer_name')
            email = arguments.get('email')
            phone = arguments.get('phone')
            appointment_datetime = arguments.get('appointment_datetime')
            reason = arguments.get('reason', 'General appointment')
            
            # Clean phone number if it's placeholder text
            if phone and ('calling from' in phone.lower() or 'number you' in phone.lower()):
                phone = None  # Will get from caller_phone or ask again
            
            if not customer_name:
                return {
                    "success": False,
                    "error": "Customer name is required"
                }
            
            if not appointment_datetime:
                return {
                    "success": False,
                    "error": "Appointment date and time are required. Please ask the customer for a specific date and time.",
                    "needs_clarification": "datetime"
                }
            
            # Check for vague time requests
            vague_time_phrases = ["within", "asap", "as soon as possible", "urgently", "emergency", "quickly", "soon"]
            if any(phrase in appointment_datetime.lower() for phrase in vague_time_phrases):
                return {
                    "success": False,
                    "error": f"The time '{appointment_datetime}' is not specific enough. For urgent requests, please check availability and suggest the next available time slot to the customer.",
                    "needs_clarification": "datetime",
                    "is_urgent": True
                }
            
            # Parse the appointment time
            parsed_time = parse_datetime(appointment_datetime)
            if not parsed_time:
                return {
                    "success": False,
                    "error": f"Could not parse date/time: '{appointment_datetime}'. Please ask the customer for a specific date and time (e.g., 'tomorrow at 2pm', 'Monday at 9am').",
                    "needs_clarification": "datetime"
                }
            
            # Validate business hours
            from src.utils.config import Config
            business_hours = Config.get_business_hours()
            requested_hour = parsed_time.hour
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
            
            if requested_hour < start_hour or requested_hour >= end_hour:
                return {
                    "success": False,
                    "error": f"The requested time {parsed_time.strftime('%I:%M %p')} is outside business hours ({start_hour}:00 - {end_hour}:00). Please check availability using check_availability and suggest a time within business hours.",
                    "needs_clarification": "datetime"
                }
            
            # Check if slot is available
            is_available = google_calendar.check_availability(parsed_time, duration_minutes=60)
            if not is_available:
                return {
                    "success": False,
                    "error": f"The time slot at {parsed_time.strftime('%B %d at %I:%M %p')} is not available"
                }
            
            # Create calendar event
            summary = f"{reason.title()} - {customer_name}"
            event = google_calendar.book_appointment(
                summary=summary,
                start_time=parsed_time,
                duration_minutes=60,
                description=f"Booked via AI receptionist\nCustomer: {customer_name}\nReason: {reason}\nPhone: {phone}\nEmail: {email}",
                phone_number=phone
            )
            
            if not event:
                return {
                    "success": False,
                    "error": "Failed to create calendar event"
                }
            
            # Save to database
            if db:
                try:
                    # Find or create client
                    client_id = db.find_or_create_client(
                        name=customer_name,
                        phone=phone,
                        email=email,
                        date_of_birth=None
                    )
                    
                    # Add booking
                    booking_id = db.add_booking(
                        client_id=client_id,
                        calendar_event_id=event.get('id'),
                        appointment_time=parsed_time,
                        service_type=reason,
                        phone_number=phone,
                        email=email
                    )
                    
                    # Add note
                    db.add_appointment_note(booking_id, f"Booked via AI receptionist. Reason: {reason}", created_by="system")
                    
                    # Update client description
                    try:
                        from src.services.client_description_generator import update_client_description
                        update_client_description(client_id)
                    except Exception:
                        pass
                    
                    print(f"✅ Booking saved to database (ID: {booking_id})")
                except Exception as e:
                    print(f"⚠️ Database save failed: {e}")
            
            return {
                "success": True,
                "message": f"Appointment booked for {customer_name} on {parsed_time.strftime('%A, %B %d at %I:%M %p')}",
                "appointment_details": {
                    "customer": customer_name,
                    "time": parsed_time.strftime('%A, %B %d at %I:%M %p'),
                    "reason": reason,
                    "phone": phone,
                    "email": email
                }
            }
        
        elif tool_name == "cancel_appointment":
            appointment_datetime = arguments.get('appointment_datetime')
            customer_name = arguments.get('customer_name')
            
            if not appointment_datetime:
                return {
                    "success": False,
                    "error": "Appointment date/time is required"
                }
            
            # Parse the appointment time
            parsed_time = parse_datetime(appointment_datetime)
            if not parsed_time:
                return {
                    "success": False,
                    "error": f"Could not parse date/time: {appointment_datetime}"
                }
            
            # If no customer name provided, look up by time only and return the name for confirmation
            if not customer_name:
                event = google_calendar.find_appointment_by_details(
                    customer_name=None,  # Look up by time only
                    appointment_time=parsed_time
                )
                
                if not event:
                    return {
                        "success": False,
                        "error": f"No appointment found at {parsed_time.strftime('%B %d at %I:%M %p')}. Please verify the date and time."
                    }
                
                # Extract customer name from the event
                event_summary = event.get('summary', '')
                if ' - ' in event_summary:
                    extracted_name = event_summary.split(' - ')[-1].strip()
                else:
                    import re
                    between_match = re.search(r'between\s+([^and]+)\s+and', event_summary, re.IGNORECASE)
                    if between_match:
                        extracted_name = between_match.group(1).strip()
                    else:
                        extracted_name = event_summary.strip()
                
                # Return the name for confirmation - NOT a success
                return {
                    "success": False,
                    "requires_confirmation": True,
                    "customer_name": extracted_name,
                    "appointment_time": parsed_time.strftime('%B %d at %I:%M %p'),
                    "message": f"Found appointment at {parsed_time.strftime('%B %d at %I:%M %p')} for {extracted_name}. Please confirm with the customer before proceeding."
                }
            
            # Customer name was provided (confirmation received), proceed with cancellation
            # Find the appointment
            event = google_calendar.find_appointment_by_details(
                customer_name=customer_name,
                appointment_time=parsed_time
            )
            
            if not event:
                return {
                    "success": False,
                    "error": f"No appointment found for {customer_name} at {parsed_time.strftime('%B %d at %I:%M %p')}"
                }
            
            # Cancel the appointment
            event_id = event.get('id')
            event_summary = event.get('summary', 'Unknown')
            
            success = google_calendar.cancel_appointment(event_id)
            
            if success:
                # Delete from database
                if db:
                    try:
                        bookings = db.get_all_bookings()
                        for booking in bookings:
                            if booking.get('calendar_event_id') == event_id:
                                db.delete_booking(booking['id'])
                                print(f"✅ Deleted booking from database (ID: {booking['id']})")
                                break
                    except Exception as e:
                        print(f"⚠️ Failed to delete booking from database: {e}")
                
                return {
                    "success": True,
                    "message": f"Successfully cancelled appointment for {customer_name} at {parsed_time.strftime('%B %d at %I:%M %p')}"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to cancel appointment in calendar"
                }
        
        elif tool_name == "reschedule_appointment":
            current_datetime = arguments.get('current_datetime')
            new_datetime = arguments.get('new_datetime')
            customer_name = arguments.get('customer_name')
            
            if not current_datetime:
                return {
                    "success": False,
                    "error": "Current appointment date/time is required"
                }
            
            # Parse current time
            current_time = parse_datetime(current_datetime)
            if not current_time:
                return {
                    "success": False,
                    "error": f"Could not parse current date/time: {current_datetime}"
                }
            
            # If no customer name provided, look up by time only and return the name for confirmation
            if not customer_name:
                event = google_calendar.find_appointment_by_details(
                    customer_name=None,  # Look up by time only
                    appointment_time=current_time
                )
                
                if not event:
                    return {
                        "success": False,
                        "error": f"No appointment found at {current_time.strftime('%B %d at %I:%M %p')}. Please verify the date and time."
                    }
                
                # Extract customer name from the event
                event_summary = event.get('summary', '')
                if ' - ' in event_summary:
                    extracted_name = event_summary.split(' - ')[-1].strip()
                else:
                    import re
                    between_match = re.search(r'between\s+([^and]+)\s+and', event_summary, re.IGNORECASE)
                    if between_match:
                        extracted_name = between_match.group(1).strip()
                    else:
                        extracted_name = event_summary.strip()
                
                # Return the name for confirmation - NOT a success
                return {
                    "success": False,
                    "requires_confirmation": True,
                    "customer_name": extracted_name,
                    "appointment_time": current_time.strftime('%B %d at %I:%M %p'),
                    "message": f"Found appointment at {current_time.strftime('%B %d at %I:%M %p')} for {extracted_name}. Please confirm with the customer before proceeding."
                }
            
            # Customer name confirmed but no new time yet
            if not new_datetime:
                return {
                    "success": False,
                    "error": "New date/time is required to complete the reschedule. Please ask the customer what time they'd like to move the appointment to."
                }
            
            # Parse new time
            new_time = parse_datetime(new_datetime)
            if not new_time:
                return {
                    "success": False,
                    "error": f"Could not parse new date/time: {new_datetime}"
                }
            
            # Check if new time is available
            is_available = google_calendar.check_availability(new_time, duration_minutes=60)
            if not is_available:
                return {
                    "success": False,
                    "error": f"The new time slot ({new_time.strftime('%B %d at %I:%M %p')}) is not available",
                    "new_time_unavailable": True
                }
            
            # Find the current appointment
            event = google_calendar.find_appointment_by_details(
                customer_name=customer_name,
                appointment_time=current_time
            )
            
            if not event:
                return {
                    "success": False,
                    "error": f"No appointment found for {customer_name} at {current_time.strftime('%B %d at %I:%M %p')}"
                }
            
            # Reschedule the appointment
            event_id = event.get('id')
            updated_event = google_calendar.reschedule_appointment(event_id, new_time)
            
            if updated_event:
                # Update database
                if db:
                    try:
                        bookings = db.get_all_bookings()
                        print(f"🔍 Looking for booking with calendar_event_id: {event_id}")
                        print(f"📋 Total bookings in database: {len(bookings)}")
                        
                        found = False
                        for booking in bookings:
                            booking_event_id = booking.get('calendar_event_id')
                            if booking_event_id:
                                print(f"   Checking booking {booking['id']}: calendar_event_id = {booking_event_id}")
                                if booking_event_id == event_id:
                                    # Update booking with new appointment time
                                    success = db.update_booking(booking['id'], appointment_time=new_time.strftime('%Y-%m-%d %H:%M:%S'))
                                    if success:
                                        print(f"✅ Updated booking in database (ID: {booking['id']}) to {new_time.strftime('%Y-%m-%d %H:%M:%S')}")
                                    else:
                                        print(f"⚠️ Database update returned False for booking {booking['id']}")
                                    found = True
                                    break
                        
                        if not found:
                            print(f"⚠️ No booking found with calendar_event_id matching: {event_id}")
                            print(f"   Customer: {customer_name}")
                            print(f"   Looking for bookings with similar names...")
                            for booking in bookings:
                                client_name = booking.get('client_name', '').lower()
                                if customer_name.lower() in client_name or client_name in customer_name.lower():
                                    print(f"   Found potential match: Booking {booking['id']} for {booking.get('client_name')} at {booking.get('appointment_time')}")
                                    print(f"      calendar_event_id: {booking.get('calendar_event_id')}")
                    except Exception as e:
                        print(f"⚠️ Failed to update booking in database: {e}")
                        import traceback
                        traceback.print_exc()
                
                return {
                    "success": True,
                    "message": f"Successfully rescheduled appointment for {customer_name} from {current_time.strftime('%B %d at %I:%M %p')} to {new_time.strftime('%B %d at %I:%M %p')}"
                }
            else:
                return {
                    "success": False,
                    "error": "Could not reschedule appointment. Please check the details."
                }
        
        elif tool_name == "book_job":
            # Trades-specific booking with additional fields
            customer_name = arguments.get('customer_name')
            phone = arguments.get('phone')
            email = arguments.get('email')
            job_address = arguments.get('job_address')
            job_description = arguments.get('job_description')
            appointment_datetime = arguments.get('appointment_datetime')
            urgency_level = arguments.get('urgency_level', 'scheduled')
            property_type = arguments.get('property_type', 'residential')
            
            # Validation
            if not customer_name:
                return {
                    "success": False,
                    "error": "Customer name is required"
                }
            
            if not phone:
                return {
                    "success": False,
                    "error": "Phone number is MANDATORY. Please ask the customer for their phone number.",
                    "needs_clarification": "phone"
                }
            
            if not email:
                return {
                    "success": False,
                    "error": "Email address is MANDATORY. Please ask the customer for their email address.",
                    "needs_clarification": "email"
                }
            
            if not job_address:
                return {
                    "success": False,
                    "error": "Job address is required. Please ask for the full address where the work will be performed.",
                    "needs_clarification": "job_address"
                }
            
            if not job_description:
                return {
                    "success": False,
                    "error": "Job description is required. Please ask what needs to be done.",
                    "needs_clarification": "job_description"
                }
            
            if not appointment_datetime:
                return {
                    "success": False,
                    "error": "Appointment date and time are required. Please ask the customer for a specific date and time.",
                    "needs_clarification": "datetime"
                }
            
            # Check for vague time requests
            vague_time_phrases = ["within", "asap", "as soon as possible", "urgently", "emergency", "quickly", "soon", "right away", "immediately"]
            if any(phrase in appointment_datetime.lower() for phrase in vague_time_phrases):
                return {
                    "success": False,
                    "error": f"The time '{appointment_datetime}' is not specific enough. Even for emergencies, you must provide a SPECIFIC time. Please check availability using check_availability and suggest the next available time slot to the customer (e.g., 'We can have someone there at 2pm today').",
                    "needs_clarification": "datetime",
                    "is_urgent": True
                }
            
            # Parse the appointment time
            parsed_time = parse_datetime(appointment_datetime)
            if not parsed_time:
                return {
                    "success": False,
                    "error": f"Could not parse date/time: '{appointment_datetime}'. Please ask the customer for a specific date and time (e.g., 'tomorrow at 2pm', 'Monday at 9am').",
                    "needs_clarification": "datetime"
                }
            
            # Validate business hours
            from src.utils.config import Config
            business_hours = Config.get_business_hours()
            requested_hour = parsed_time.hour
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
            
            if requested_hour < start_hour or requested_hour >= end_hour:
                return {
                    "success": False,
                    "error": f"The requested time {parsed_time.strftime('%I:%M %p')} is outside business hours ({start_hour}:00 - {end_hour}:00). Please check availability using check_availability and suggest a time within business hours.",
                    "needs_clarification": "datetime"
                }
            
            # Check if slot is available
            is_available = google_calendar.check_availability(parsed_time, duration_minutes=60)
            if not is_available:
                return {
                    "success": False,
                    "error": f"The time slot at {parsed_time.strftime('%B %d at %I:%M %p')} is not available. Please check availability and suggest another time."
                }
            
            # Create calendar event with trades details
            summary = f"{urgency_level.upper()}: {job_description[:50]} - {customer_name}"
            event = google_calendar.book_appointment(
                summary=summary,
                start_time=parsed_time,
                duration_minutes=60,
                description=f"Booked via AI receptionist\n\nCustomer: {customer_name}\nPhone: {phone}\nEmail: {email}\n\nJob Address: {job_address}\nJob Description: {job_description}\nUrgency: {urgency_level}\nProperty Type: {property_type}",
                phone_number=phone
            )
            
            if not event:
                return {
                    "success": False,
                    "error": "Failed to create calendar event"
                }
            
            # Save to database with trades-specific fields
            if db:
                try:
                    # Find or create client
                    client_id = db.find_or_create_client(
                        name=customer_name,
                        phone=phone,
                        email=email,
                        date_of_birth=None
                    )
                    
                    # Add booking
                    booking_id = db.add_booking(
                        client_id=client_id,
                        calendar_event_id=event.get('id'),
                        appointment_time=parsed_time,
                        service_type=f"{urgency_level}: {job_description}",
                        phone_number=phone,
                        email=email
                    )
                    
                    # Add note with job details
                    db.add_appointment_note(
                        booking_id, 
                        f"Booked via AI receptionist\n\nJob Address: {job_address}\nJob Description: {job_description}\nUrgency: {urgency_level}\nProperty Type: {property_type}", 
                        created_by="system"
                    )
                    
                    # Update client description
                    try:
                        from src.services.client_description_generator import update_client_description
                        update_client_description(client_id)
                    except Exception:
                        pass
                    
                    print(f"✅ Job booking saved to database (ID: {booking_id})")
                except Exception as e:
                    print(f"⚠️ Database save failed: {e}")
            
            return {
                "success": True,
                "message": f"Job booked for {customer_name} on {parsed_time.strftime('%A, %B %d at %I:%M %p')}. {urgency_level.title()} job at {job_address}.",
                "appointment_details": {
                    "customer": customer_name,
                    "time": parsed_time.strftime('%A, %B %d at %I:%M %p'),
                    "job_address": job_address,
                    "job_description": job_description,
                    "urgency": urgency_level,
                    "phone": phone,
                    "email": email,
                    "property_type": property_type
                }
            }
        
        elif tool_name == "cancel_job":
            # Alias for cancel_appointment - same functionality
            return execute_tool_call("cancel_appointment", arguments, services)
        
        elif tool_name == "reschedule_job":
            # Alias for reschedule_appointment - same functionality
            return execute_tool_call("reschedule_appointment", arguments, services)
        
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
    
    except Exception as e:
        print(f"❌ Error executing tool {tool_name}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Error executing {tool_name}: {str(e)}"
        }
