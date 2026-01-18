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
            "description": "Check available appointment time slots. Use this IMMEDIATELY when patient asks about available times, slots, or when they're looking for appointments. Returns list of available slots with exact times. Use this for queries like 'what times next week', 'what about Monday', 'any slots Thursday'.",
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
            "name": "lookup_patient",
            "description": "Look up existing patient information by name, phone, or date of birth. Use this EARLY to check if patient exists in system. Call this right after getting their name and DOB to see if they're a returning customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Patient's full name to look up"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Patient's phone number (optional)"
                    },
                    "date_of_birth": {
                        "type": "string",
                        "description": "Patient's date of birth in YYYY-MM-DD format"
                    }
                },
                "required": ["patient_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new appointment for a patient. Use this AFTER collecting: name, DOB, phone, appointment date/time, and reason. Verify the time slot is available first with check_availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Patient's full name"
                    },
                    "date_of_birth": {
                        "type": "string",
                        "description": "Patient's date of birth in YYYY-MM-DD format"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Patient's phone number"
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
                "required": ["patient_name", "date_of_birth", "phone", "appointment_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. WORKFLOW: 1) Get the date/time from the user. 2) Call this function with ONLY the appointment_datetime (do NOT ask for patient name). 3) The system will look up the appointment and return the patient name. 4) Confirm with the user: 'Just to confirm, that appointment on [date/time] is for [name]. Is that correct?' 5) If they confirm, call this function again with both datetime and patient_name to complete the cancellation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Date and time of the appointment to cancel in natural language (e.g., 'Thursday at 3pm', 'January 15th at 3:00pm')"
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Name of the patient whose appointment is being cancelled. ONLY provide this AFTER the user has confirmed the name. On first call, omit this to look up the appointment."
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
            "description": "Reschedule an existing appointment to a new time. WORKFLOW: 1) Get the current appointment date/time from the user. 2) Call this function with ONLY current_datetime (do NOT ask for patient name). 3) The system will return the patient name. 4) Confirm: 'Just to confirm, that appointment is for [name]. Is that correct?' 5) If confirmed, ask for new time. 6) Call this function again with all three parameters to complete the reschedule.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_datetime": {
                        "type": "string",
                        "description": "Current date and time of the appointment in natural language"
                    },
                    "new_datetime": {
                        "type": "string",
                        "description": "New date and time for the appointment in natural language. ONLY provide this AFTER confirming the patient name."
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Name of the patient whose appointment is being rescheduled. ONLY provide this AFTER the user has confirmed. On first call, omit this to look up the appointment."
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
    - This handles QUERY tools only (check_availability, lookup_patient)
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
    
    google_calendar = services.get('google_calendar')
    db = services.get('db')
    
    try:
        if tool_name == "check_availability":
            start_date_str = arguments.get('start_date')
            end_date_str = arguments.get('end_date', start_date_str)
            service_type = arguments.get('service_type', 'general')
            
            # Special handling for "next week" - expand to Monday-Friday
            if start_date_str and 'next week' in start_date_str.lower():
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
            
            # Check all days in range (no early exit - we want full picture)
            while current_date <= end_search:
                # Only check weekdays (Monday=0 to Friday=4)
                if current_date.weekday() < 5:
                    print(f"   📅 Checking {current_date.strftime('%A, %B %d')} (weekday {current_date.weekday()})")
                    day_slots = google_calendar.get_available_slots_for_day(current_date)
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
            
            return {
                "success": True,
                "available_slots": formatted_slots,
                "total_count": len(all_slots),
                "natural_summary": natural_summary,
                "message": f"Next week I have: {natural_summary}",
                "voice_instruction": "Say the natural_summary naturally and conversationally. Then ask which day/time works for them."
            }
        
        elif tool_name == "lookup_patient":
            patient_name = arguments.get('patient_name')
            phone = arguments.get('phone')
            date_of_birth = arguments.get('date_of_birth')
            
            if not patient_name:
                return {
                    "success": False,
                    "error": "Patient name is required"
                }
            
            # Check database for existing patient
            if db:
                try:
                    # Try exact match first by name and DOB
                    if date_of_birth:
                        client = db.get_client_by_name_and_dob(patient_name.lower(), date_of_birth)
                        if client:
                            return {
                                "success": True,
                                "patient_exists": True,
                                "patient_info": {
                                    "id": client['id'],
                                    "name": client['name'],
                                    "phone": client.get('phone'),
                                    "email": client.get('email'),
                                    "date_of_birth": client.get('date_of_birth')
                                },
                                "message": f"Found returning patient: {client['name']}"
                            }
                        
                        # FUZZY MATCH: Try phonetically similar names (for ASR errors)
                        # Common ASR errors: Doherty→Dorothy, James→Janes, etc.
                        from difflib import SequenceMatcher
                        all_clients = db.get_all_clients()
                        
                        for potential_client in all_clients:
                            # Check DOB first (exact match required)
                            if potential_client.get('date_of_birth') == date_of_birth:
                                # Check name similarity (80%+ match)
                                similarity = SequenceMatcher(None, 
                                    patient_name.lower(), 
                                    potential_client['name'].lower()).ratio()
                                
                                if similarity >= 0.75:  # 75% similar = likely match
                                    print(f"✅ Fuzzy match: '{patient_name}' → '{potential_client['name']}' (similarity: {similarity:.2%})")
                                    return {
                                        "success": True,
                                        "patient_exists": True,
                                        "fuzzy_match": True,
                                        "heard_name": patient_name,
                                        "actual_name": potential_client['name'],
                                        "patient_info": {
                                            "id": potential_client['id'],
                                            "name": potential_client['name'],
                                            "phone": potential_client.get('phone'),
                                            "email": potential_client.get('email'),
                                            "date_of_birth": potential_client.get('date_of_birth')
                                        },
                                        "message": f"Found returning patient: {potential_client['name']} (I heard {patient_name}, but found a close match)"
                                    }
                    
                    # Try by name only
                    clients = db.get_clients_by_name(patient_name.lower())
                    if len(clients) == 1:
                        client = clients[0]
                        return {
                            "success": True,
                            "patient_exists": True,
                            "needs_dob_verification": not date_of_birth,
                            "patient_info": {
                                "id": client['id'],
                                "name": client['name'],
                                "phone": client.get('phone'),
                                "email": client.get('email'),
                                "date_of_birth": client.get('date_of_birth')
                            },
                            "message": f"Found patient: {client['name']}" + (" - please verify DOB" if not date_of_birth else "")
                        }
                    elif len(clients) > 1:
                        return {
                            "success": True,
                            "patient_exists": True,
                            "multiple_matches": True,
                            "count": len(clients),
                            "message": f"Found {len(clients)} patients named {patient_name}. Need date of birth to confirm which one."
                        }
                    else:
                        return {
                            "success": True,
                            "patient_exists": False,
                            "message": f"No existing patient found for {patient_name}. This is a new patient."
                        }
                except Exception as e:
                    print(f"❌ Error looking up patient: {e}")
                    return {
                        "success": False,
                        "error": f"Database error: {str(e)}"
                    }
            
            return {
                "success": False,
                "error": "Database not available"
            }
        
        elif tool_name == "book_appointment":
            patient_name = arguments.get('patient_name')
            date_of_birth = arguments.get('date_of_birth')
            phone = arguments.get('phone')
            appointment_datetime = arguments.get('appointment_datetime')
            reason = arguments.get('reason', 'General appointment')
            
            # Clean phone number if it's placeholder text
            if phone and ('calling from' in phone.lower() or 'number you' in phone.lower()):
                phone = None  # Will get from caller_phone or ask again
            
            if not all([patient_name, date_of_birth, appointment_datetime]):
                return {
                    "success": False,
                    "error": "Missing required information: patient name, DOB, and appointment time are required"
                }
            
            # Parse the appointment time
            parsed_time = parse_datetime(appointment_datetime)
            if not parsed_time:
                return {
                    "success": False,
                    "error": f"Could not parse date/time: {appointment_datetime}"
                }
            
            # Check if slot is available
            is_available = google_calendar.check_availability(parsed_time, duration_minutes=60)
            if not is_available:
                return {
                    "success": False,
                    "error": f"The time slot at {parsed_time.strftime('%B %d at %I:%M %p')} is not available"
                }
            
            # Create calendar event
            summary = f"{reason.title()} - {patient_name}"
            event = google_calendar.book_appointment(
                summary=summary,
                start_time=parsed_time,
                duration_minutes=60,
                description=f"Booked via AI receptionist\nPatient: {patient_name}\nReason: {reason}\nPhone: {phone}",
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
                        name=patient_name,
                        phone=phone,
                        email=None,
                        date_of_birth=date_of_birth
                    )
                    
                    # Add booking
                    booking_id = db.add_booking(
                        client_id=client_id,
                        calendar_event_id=event.get('id'),
                        appointment_time=parsed_time,
                        service_type=reason,
                        phone_number=phone,
                        email=None
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
                "message": f"Appointment booked for {patient_name} on {parsed_time.strftime('%A, %B %d at %I:%M %p')}",
                "appointment_details": {
                    "patient": patient_name,
                    "time": parsed_time.strftime('%A, %B %d at %I:%M %p'),
                    "reason": reason,
                    "phone": phone
                }
            }
        
        elif tool_name == "cancel_appointment":
            appointment_datetime = arguments.get('appointment_datetime')
            patient_name = arguments.get('patient_name')
            
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
            
            # If no patient name provided, look up by time only and return the name for confirmation
            if not patient_name:
                event = google_calendar.find_appointment_by_details(
                    patient_name=None,  # Look up by time only
                    appointment_time=parsed_time
                )
                
                if not event:
                    return {
                        "success": False,
                        "error": f"No appointment found at {parsed_time.strftime('%B %d at %I:%M %p')}. Please verify the date and time."
                    }
                
                # Extract patient name from the event
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
                    "patient_name": extracted_name,
                    "appointment_time": parsed_time.strftime('%B %d at %I:%M %p'),
                    "message": f"Found appointment at {parsed_time.strftime('%B %d at %I:%M %p')} for {extracted_name}. Please confirm with the patient before proceeding."
                }
            
            # Patient name was provided (confirmation received), proceed with cancellation
            # Find the appointment
            event = google_calendar.find_appointment_by_details(
                patient_name=patient_name,
                appointment_time=parsed_time
            )
            
            if not event:
                return {
                    "success": False,
                    "error": f"No appointment found for {patient_name} at {parsed_time.strftime('%B %d at %I:%M %p')}"
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
                    "message": f"Successfully cancelled appointment for {patient_name} at {parsed_time.strftime('%B %d at %I:%M %p')}"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to cancel appointment in calendar"
                }
        
        elif tool_name == "reschedule_appointment":
            current_datetime = arguments.get('current_datetime')
            new_datetime = arguments.get('new_datetime')
            patient_name = arguments.get('patient_name')
            
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
            
            # If no patient name provided, look up by time only and return the name for confirmation
            if not patient_name:
                event = google_calendar.find_appointment_by_details(
                    patient_name=None,  # Look up by time only
                    appointment_time=current_time
                )
                
                if not event:
                    return {
                        "success": False,
                        "error": f"No appointment found at {current_time.strftime('%B %d at %I:%M %p')}. Please verify the date and time."
                    }
                
                # Extract patient name from the event
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
                    "patient_name": extracted_name,
                    "appointment_time": current_time.strftime('%B %d at %I:%M %p'),
                    "message": f"Found appointment at {current_time.strftime('%B %d at %I:%M %p')} for {extracted_name}. Please confirm with the patient before proceeding."
                }
            
            # Patient name confirmed but no new time yet
            if not new_datetime:
                return {
                    "success": False,
                    "error": "New date/time is required to complete the reschedule. Please ask the patient what time they'd like to move the appointment to."
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
                patient_name=patient_name,
                appointment_time=current_time
            )
            
            if not event:
                return {
                    "success": False,
                    "error": f"No appointment found for {patient_name} at {current_time.strftime('%B %d at %I:%M %p')}"
                }
            
            # Reschedule the appointment
            event_id = event.get('id')
            updated_event = google_calendar.reschedule_appointment(event_id, new_time)
            
            if updated_event:
                # Update database
                if db:
                    try:
                        bookings = db.get_all_bookings()
                        for booking in bookings:
                            if booking.get('calendar_event_id') == event_id:
                                db.update_booking_time(booking['id'], new_time)
                                print(f"✅ Updated booking in database (ID: {booking['id']})")
                                break
                    except Exception as e:
                        print(f"⚠️ Failed to update booking in database: {e}")
                
                return {
                    "success": True,
                    "message": f"Successfully rescheduled appointment for {patient_name} from {current_time.strftime('%B %d at %I:%M %p')} to {new_time.strftime('%B %d at %I:%M %p')}"
                }
            else:
                return {
                    "success": False,
                    "error": "Could not reschedule appointment. Please check the details."
                }
        
        elif tool_name == "lookup_patient":
            patient_name = arguments.get('patient_name')
            phone = arguments.get('phone')
            dob = arguments.get('date_of_birth')
            
            if not db:
                return {
                    "success": False,
                    "error": "Database not available"
                }
            
            # Look up patient
            if patient_name:
                clients = db.get_clients_by_name(patient_name)
                # If multiple clients found, return first match (or handle accordingly)
                client = clients[0] if clients else None
            elif phone:
                client = db.get_client_by_phone(phone)
            else:
                return {
                    "success": False,
                    "error": "Please provide patient name or phone number"
                }
            
            if client:
                return {
                    "success": True,
                    "patient": {
                        "name": client.get('name'),
                        "phone": client.get('phone'),
                        "date_of_birth": client.get('date_of_birth'),
                        "email": client.get('email')
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"No patient found with the provided information"
                }
        
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
