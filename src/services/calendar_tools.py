"""
OpenAI Tools/Function definitions for calendar operations.

ARCHITECTURE: Hybrid Approach
- TOOLS: Check availability (queries) - fast, maintains context
- CALLBACKS: Booking/cancellation/rescheduling - uses existing verification flow
"""

import logging

# Set up logger for this module
logger = logging.getLogger(__name__)

# Import address validation utilities
from src.utils.address_validator import (
    AddressValidator, 
    validate_address_input,
    extract_eircode_from_text,
    is_address_incomplete,
    get_address_completion_prompt
)
from src.utils.duration_utils import format_duration
from src.utils.security import normalize_phone_for_comparison

CALENDAR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_next_available",
            "description": "Find the next 2-4 available days for a job. Use this FIRST when you need to offer availability to a customer. Returns the soonest available days with natural language summary. ALWAYS use this after confirming customer details to suggest initial booking options. For full-day jobs (8+ hours), returns available DAYS only (no times).",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_description": {
                        "type": "string",
                        "description": "Description of the job/service needed (e.g., 'burst pipe', 'cobblestone wall', 'painting'). This determines the service duration."
                    },
                    "weeks_to_search": {
                        "type": "integer",
                        "description": "How many weeks ahead to search (default 3). Increase if customer needs dates further out."
                    }
                },
                "required": ["job_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_availability",
            "description": "Search for availability based on customer's specific request. Use when customer asks about specific dates, times, or constraints like 'after 4pm', 'next week', 'in 2 weeks', 'do you have anything on Monday', 'what about mornings'. Understands natural language date/time queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The customer's availability request in natural language (e.g., 'next week', 'after 4pm on Thursday', 'in 2 weeks time', 'Monday or Tuesday', 'any morning slots')"
                    },
                    "job_description": {
                        "type": "string",
                        "description": "Description of the job/service needed. This determines the service duration."
                    }
                },
                "required": ["query", "job_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "LEGACY - prefer get_next_available or search_availability. Check available time slots for a specific date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format or natural language"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format or natural language"
                    },
                    "job_description": {
                        "type": "string",
                        "description": "Description of the job/service needed"
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
            "description": "Look up existing customer information by name or phone. Call this right after spelling back the name and getting confirmation. CRITICAL: Use the FULL NAME (first AND last name) that you confirmed with the customer. Example: If you spelled 'J-A-M-E-S D-O-H-E-R-T-Y' and they said yes, use 'James Doherty' NOT just 'Doherty'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's FULL NAME (first name + last name) - e.g., 'James Doherty' NOT just 'Doherty'"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number (optional - use caller's number if available)"
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
            "description": "Book a new appointment for a customer. CRITICAL: You MUST have a SPECIFIC date and time before calling this (e.g., 'tomorrow at 2pm', 'Monday at 9am'). DO NOT call this with vague times like 'within 2 hours', 'as soon as possible', or 'ASAP'. For urgent requests, suggest the next available time slot using check_availability first. Required info: name, phone, SPECIFIC appointment datetime, and reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's full name"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number (MANDATORY) - use the caller's number unless they provide a different one"
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
            "description": "Cancel an existing appointment. WORKFLOW: 1) Ask customer what DAY the booking is for (not time - there may be multiple jobs or full-day jobs). 2) Call this with ONLY appointment_date (the day). 3) System returns ALL jobs on that day with customer names. 4) Read the names to the caller and ask them to confirm which one is theirs. 5) Listen to their response and call again with appointment_date AND customer_name to complete cancellation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_date": {
                        "type": "string",
                        "description": "The DAY of the appointment to cancel (e.g., 'Monday', 'Thursday', 'January 15th'). Do NOT include time - we look up all jobs on that day first."
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name - ONLY provide this AFTER the caller confirms which name is theirs from the list of jobs on that day."
                    }
                },
                "required": ["appointment_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new time. WORKFLOW: 1) Ask customer what DAY the booking is for (not time - there may be multiple jobs or full-day jobs). 2) Call this with ONLY current_date (the day). 3) System returns ALL jobs on that day with customer names. 4) Read the names to the caller and ask them to confirm which one is theirs. 5) Listen to their response, then ask what day they want to reschedule to. 6) Call again with current_date, customer_name, AND new_datetime to complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_date": {
                        "type": "string",
                        "description": "The DAY of the current appointment (e.g., 'Monday', 'Thursday', 'January 15th'). Do NOT include time - we look up all jobs on that day first."
                    },
                    "new_datetime": {
                        "type": "string",
                        "description": "New date and time for the appointment. ONLY provide this AFTER confirming the customer name."
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name - ONLY provide this AFTER the caller confirms which name is theirs from the list of jobs on that day."
                    }
                },
                "required": ["current_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_job",
            "description": "Book a new trade job/appointment for a customer. CRITICAL: You MUST have a SPECIFIC date and time before calling this (e.g., 'tomorrow at 2pm', 'Monday at 9am'). DO NOT call this with vague times like 'within 2 hours', 'as soon as possible', or 'ASAP'. Required info: FULL customer name (first + last), phone (mandatory), job address or eircode, job description, SPECIFIC datetime, and urgency level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's FULL NAME (first name + last name) - e.g., 'James Doherty' NOT just 'Doherty'"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number (MANDATORY) - use the caller's number unless they provide a different one"
                    },
                    "email": {
                        "type": "string",
                        "description": "Customer's email address (OPTIONAL) - only include if the customer voluntarily provides it"
                    },
                    "job_address": {
                        "type": "string",
                        "description": "Job location - can be eircode (preferred, e.g., 'V94 ABC1') or full address (e.g., '32 Silvergrove, Ballybeg, Ennis, Clare'). Always confirm by reading back."
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
                        "enum": ["same-day", "scheduled", "quote"],
                        "description": "Urgency level: 'same-day' for jobs needed today, 'scheduled' for planned work on a future date, 'quote' for estimate visits"
                    },
                    "property_type": {
                        "type": "string",
                        "enum": ["residential", "commercial"],
                        "description": "Type of property: 'residential' for homes, 'commercial' for businesses"
                    }
                },
                "required": ["customer_name", "phone", "job_address", "job_description", "appointment_datetime", "urgency_level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_job",
            "description": "Cancel an existing job/appointment. WORKFLOW: 1) Ask customer what DAY the booking is for (not time - there may be multiple jobs or full-day jobs). 2) Call this with ONLY appointment_date (the day). 3) System returns ALL jobs on that day with customer names. 4) Read the names to the caller and ask them to confirm which one is theirs. 5) Listen to their response and call again with appointment_date AND customer_name to complete cancellation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_date": {
                        "type": "string",
                        "description": "The DAY of the job to cancel (e.g., 'Monday', 'Thursday', 'January 15th'). Do NOT include time - we look up all jobs on that day first."
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name - ONLY provide this AFTER the caller confirms which name is theirs from the list of jobs on that day."
                    }
                },
                "required": ["appointment_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_job",
            "description": "Reschedule an existing job to a new time. WORKFLOW: 1) Ask customer what DAY the booking is for (not time - there may be multiple jobs or full-day jobs). 2) Call this with ONLY current_date (the day). 3) System returns ALL jobs on that day with customer names. 4) Read the names to the caller and ask them to confirm which one is theirs. 5) Listen to their response, then ask what day they want to reschedule to. 6) Call again with current_date, customer_name, AND new_datetime to complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_date": {
                        "type": "string",
                        "description": "The DAY of the current job (e.g., 'Monday', 'Thursday', 'January 15th'). Do NOT include time - we look up all jobs on that day first."
                    },
                    "new_datetime": {
                        "type": "string",
                        "description": "New date and time for the job. ONLY provide this AFTER confirming the customer name."
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name - ONLY provide this AFTER the caller confirms which name is theirs from the list of jobs on that day."
                    }
                },
                "required": ["current_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "IMMEDIATELY transfer the call to a real human/staff member when customer asks to speak with a person, human, manager, owner, or real person. CRITICAL: You MUST call this function - do not just say you will transfer, actually invoke this tool. The system will automatically say 'transferring you now' - you just need to call the function.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for the transfer (e.g., 'customer requested human', 'complex inquiry', 'complaint')"
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_job",
            "description": "Modify details of an existing job/appointment. Use when customer wants to change the address, job description, or other details of a booking WITHOUT changing the time. WORKFLOW: 1) Get the appointment date/time from the user. 2) Call this function with ONLY appointment_datetime to look up the booking. 3) System returns customer name and current details. 4) Confirm with user: 'That appointment is for [name]. What would you like to change?' 5) When they tell you what to change, call this function again with the datetime, customer_name, and the fields to update.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Date and time of the job to modify (e.g., 'Thursday at 3pm', 'January 15th at 10am')"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name (provide AFTER user confirms the booking lookup)"
                    },
                    "new_address": {
                        "type": "string",
                        "description": "New job address or eircode if customer wants to change location"
                    },
                    "new_job_description": {
                        "type": "string",
                        "description": "Updated job description if customer wants to change what needs to be done"
                    },
                    "new_phone": {
                        "type": "string",
                        "description": "New contact phone number if customer wants to update it"
                    },
                    "new_email": {
                        "type": "string",
                        "description": "New email address if customer wants to update it"
                    },
                    "new_urgency": {
                        "type": "string",
                        "enum": ["same-day", "scheduled", "quote"],
                        "description": "New urgency level if customer wants to change it"
                    }
                },
                "required": ["appointment_datetime"]
            }
        }
    }
]


def _find_worker_available_days(db, worker_ids: list, duration_minutes: int, exclude_booking_id: int = None, company_id: int = None, days_to_check: int = 14) -> list:
    """
    Find available days for specific worker(s) in the next N days.
    Used during rescheduling to suggest alternative days when the requested day isn't available.
    
    Args:
        db: Database instance
        worker_ids: List of worker IDs that must ALL be available
        duration_minutes: Duration of the job in minutes
        exclude_booking_id: Booking ID to exclude (the one being rescheduled)
        company_id: Company ID for filtering
        days_to_check: Number of days to look ahead (default 14)
        
    Returns:
        List of day names like ["Wednesday", "Thursday", "Friday"]
    """
    from datetime import datetime, timedelta
    from src.utils.config import config
    
    if not db or not worker_ids:
        return []
    
    available_days = []
    today = datetime.now()
    
    # Get business days and hours
    try:
        business_days = config.get_business_days_indices()
    except:
        business_days = [0, 1, 2, 3, 4]  # Mon-Fri default
    
    try:
        business_hours = config.get_business_hours(company_id=company_id)
        biz_start_hour = business_hours.get('start', 9)
        biz_end_hour = business_hours.get('end', 17)
    except:
        biz_start_hour = 9
        biz_end_hour = 17
    
    for day_offset in range(1, days_to_check + 1):
        check_date = today + timedelta(days=day_offset)
        
        # Skip non-business days
        if check_date.weekday() not in business_days:
            continue
        
        # For full-day jobs, check if the whole day is available
        if duration_minutes >= 480:
            check_time = check_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
        else:
            # For shorter jobs, check a few time slots throughout the day
            check_time = check_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
        
        # Check if ALL assigned workers are available on this day
        all_available = True
        for worker_id in worker_ids:
            availability = db.check_worker_availability(
                worker_id=worker_id,
                appointment_time=check_time,
                duration_minutes=duration_minutes,
                exclude_booking_id=exclude_booking_id,
                company_id=company_id
            )
            if not availability.get('available', False):
                all_available = False
                break
        
        if all_available:
            day_name = check_date.strftime('%A')
            # Include date for clarity (e.g., "Wednesday the 12th")
            day_num = check_date.day
            suffix = 'th' if 11 <= day_num <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day_num % 10, 'th')
            available_days.append(f"{day_name} the {day_num}{suffix}")
    
    logger.info(f"[RESCHEDULE] Found {len(available_days)} available days for workers {worker_ids}: {available_days[:5]}")
    return available_days


def fuzzy_match_name(spoken_name: str, candidate_names: list) -> tuple:
    """
    Fuzzy match a spoken name against a list of candidate names.
    Handles common speech-to-text variations and partial matches.
    
    Args:
        spoken_name: The name the caller said (may be partial or have STT errors)
        candidate_names: List of actual customer names from bookings
        
    Returns:
        Tuple of (best_match_name, confidence_score 0-100, matched_booking_index)
    """
    from difflib import SequenceMatcher
    
    if not spoken_name or not candidate_names:
        return (None, 0, -1)
    
    spoken_lower = spoken_name.lower().strip()
    best_match = None
    best_score = 0
    best_index = -1
    
    for idx, candidate in enumerate(candidate_names):
        if not candidate:
            continue
        candidate_lower = candidate.lower().strip()
        
        # Strategy 1: Exact match (100%)
        if spoken_lower == candidate_lower:
            return (candidate, 100, idx)
        
        # Strategy 2: One contains the other (90%)
        if spoken_lower in candidate_lower or candidate_lower in spoken_lower:
            score = 90
            if score > best_score:
                best_score = score
                best_match = candidate
                best_index = idx
            continue
        
        # Strategy 3: First name or last name match (85%)
        spoken_parts = spoken_lower.split()
        candidate_parts = candidate_lower.split()
        for sp in spoken_parts:
            if len(sp) >= 3:  # Ignore very short parts
                for cp in candidate_parts:
                    if sp == cp or (len(sp) >= 4 and sp in cp) or (len(cp) >= 4 and cp in sp):
                        score = 85
                        if score > best_score:
                            best_score = score
                            best_match = candidate
                            best_index = idx
        
        # Strategy 4: Sequence matcher for typos/STT errors (scaled 0-80)
        seq_score = SequenceMatcher(None, spoken_lower, candidate_lower).ratio() * 80
        if seq_score > best_score:
            best_score = seq_score
            best_match = candidate
            best_index = idx
    
    return (best_match, int(best_score), best_index)


def find_jobs_on_day(target_date, db, company_id: int, google_calendar=None) -> list:
    """
    Find all jobs/bookings on a specific day.
    Handles both full-day jobs and multiple shorter jobs.
    
    Args:
        target_date: The date to search (datetime object)
        db: Database instance
        company_id: Company ID for filtering
        google_calendar: Optional Google Calendar service
        
    Returns:
        List of dicts with job info: [{name, time, service, is_full_day, booking_id, event_id}, ...]
    """
    from datetime import datetime, timedelta
    
    jobs_on_day = []
    
    # Get day boundaries
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    # First check database bookings
    if db:
        try:
            all_bookings = db.get_all_bookings(company_id=company_id)
            for booking in all_bookings:
                if booking.get('status') in ['cancelled', 'completed']:
                    continue
                
                appt_time = booking.get('appointment_time')
                if not appt_time:
                    continue
                
                # Parse appointment time
                if isinstance(appt_time, str):
                    try:
                        appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                    except:
                        continue
                elif hasattr(appt_time, 'replace'):
                    appt_time = appt_time.replace(tzinfo=None)
                
                # Check if on target day
                if day_start <= appt_time < day_end:
                    duration = booking.get('duration_minutes', 60)
                    is_full_day = duration >= 480  # 8+ hours
                    
                    # Get worker names if assigned
                    worker_names = []
                    assigned_ids = booking.get('assigned_worker_ids', [])
                    if assigned_ids and db:
                        for wid in assigned_ids:
                            worker = db.get_worker(wid, company_id=company_id)
                            if worker:
                                worker_names.append(worker.get('name', ''))
                    
                    jobs_on_day.append({
                        'name': booking.get('client_name') or booking.get('customer_name') or 'Unknown',
                        'time': appt_time.strftime('%I:%M %p') if not is_full_day else 'Full day',
                        'service': booking.get('service_type') or booking.get('service') or 'Job',
                        'is_full_day': is_full_day,
                        'booking_id': booking.get('id'),
                        'event_id': booking.get('calendar_event_id'),
                        'duration_minutes': duration,
                        'assigned_workers': worker_names,
                        'appointment_time': appt_time.strftime('%Y-%m-%d %H:%M:%S')  # Convert to string for JSON
                    })
        except Exception as e:
            logger.error(f"[FIND_JOBS] Database error: {e}")
    
    # Also check Google Calendar if available (for legacy/external bookings)
    if google_calendar and hasattr(google_calendar, 'service') and google_calendar.service:
        try:
            time_min = day_start.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            time_max = day_end.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            
            request = google_calendar.service.events().list(
                calendarId=google_calendar.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            )
            events_result = google_calendar._execute_with_retry(request)
            events = events_result.get('items', [])
            
            for event in events:
                event_id = event.get('id')
                # Skip if already found in database
                if any(j.get('event_id') == event_id for j in jobs_on_day):
                    continue
                
                summary = event.get('summary', '')
                # Extract name from summary (format: "Service - Name" or just name)
                if ' - ' in summary:
                    name = summary.split(' - ')[-1].strip()
                    service = summary.split(' - ')[0].strip()
                else:
                    name = summary
                    service = 'Appointment'
                
                # Get event time
                event_start_str = event.get('start', {}).get('dateTime')
                if event_start_str:
                    try:
                        event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                        event_end_str = event.get('end', {}).get('dateTime')
                        if event_end_str:
                            event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00')).replace(tzinfo=None)
                            duration = int((event_end - event_start).total_seconds() / 60)
                        else:
                            duration = 60
                        
                        is_full_day = duration >= 480
                        
                        jobs_on_day.append({
                            'name': name,
                            'time': event_start.strftime('%I:%M %p') if not is_full_day else 'Full day',
                            'service': service,
                            'is_full_day': is_full_day,
                            'booking_id': None,
                            'event_id': event_id,
                            'duration_minutes': duration,
                            'assigned_workers': [],
                            'appointment_time': event_start.strftime('%Y-%m-%d %H:%M:%S')  # Convert to string for JSON
                        })
                    except Exception as e:
                        logger.warning(f"[FIND_JOBS] Could not parse event time: {e}")
        except Exception as e:
            logger.warning(f"[FIND_JOBS] Google Calendar error: {e}")
    
    # Sort by time (appointment_time is now a string)
    jobs_on_day.sort(key=lambda x: x.get('appointment_time') or '0000-00-00 00:00:00')
    
    logger.info(f"[FIND_JOBS] Found {len(jobs_on_day)} jobs on {target_date.strftime('%Y-%m-%d')}: {[j['name'] for j in jobs_on_day]}")
    return jobs_on_day


def naturalize_availability_summary(day_summaries: list, is_full_day: bool = False) -> str:
    """
    Convert structured day availability into natural, conversational speech.
    Uses GPT-4o-mini for fast, natural language generation.
    
    Args:
        day_summaries: List of day summaries like ["Monday the 16th: full day available", "Tuesday the 17th: 2 pm or 4 pm"]
        is_full_day: Whether this is a full-day service
        
    Returns:
        Natural language summary suitable for voice
    """
    import time as time_module
    
    if not day_summaries:
        return "I don't have any availability for that time period."
    
    # For single day with simple availability, just clean it up without API call
    if len(day_summaries) == 1:
        summary = day_summaries[0]
        # Simple cleanup for single day
        if "full day available" in summary.lower():
            day = summary.split(":")[0]
            return f"I've got {day} wide open for you"
        elif "free from" in summary.lower():
            parts = summary.split(": ")
            day = parts[0]
            times = parts[1].replace("free from ", "")
            return f"On {day}, I'm free {times}"
        elif "only" in summary.lower():
            parts = summary.split(": ")
            day = parts[0]
            time = parts[1].replace(" only", "")
            return f"I've only got {time} on {day}"
        else:
            return summary.replace(": ", ", I have ")
    
    # For 2-4 days, build a natural sentence without API call for speed
    if len(day_summaries) <= 4:
        if is_full_day:
            # Extract just the day names for full-day jobs
            days = []
            for summary in day_summaries:
                day = summary.split(":")[0].strip()
                days.append(day)
            
            if len(days) == 2:
                return f"I'm available all day on {days[0]} and {days[1]}"
            elif len(days) == 3:
                return f"I'm available all day on {days[0]}, {days[1]}, and {days[2]}"
            else:
                return f"I'm available all day on {days[0]}, {days[1]}, {days[2]}, and {days[3]}"
        else:
            # For shorter jobs, include time info
            parts = []
            for summary in day_summaries[:3]:  # Max 3 for readability
                if ": " in summary:
                    day, times = summary.split(": ", 1)
                    if "free from" in times.lower():
                        times = times.replace("free from ", "")
                        parts.append(f"{day} from {times}")
                    elif "or" in times:
                        parts.append(f"{day} at {times}")
                    else:
                        parts.append(f"{day} {times}")
                else:
                    parts.append(summary)
            
            if len(parts) == 2:
                return f"I have {parts[0]}, and {parts[1]}"
            else:
                return f"I have {', '.join(parts[:-1])}, and {parts[-1]}"
    
    # For more than 4 days, use a quick LLM call to make it conversational
    try:
        from openai import OpenAI
        from src.utils.config import config
        
        start_time = time_module.time()
        
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Build the raw data
        raw_summary = "; ".join(day_summaries)
        
        # Different prompts for full-day vs short jobs
        if is_full_day:
            system_prompt = "Convert availability into ONE natural sentence. ALWAYS mention 2-4 specific days. Example: 'I've got a full day open on Tuesday, Wednesday, and Thursday'. Be brief. Max 20 words."
        else:
            system_prompt = "Convert availability into ONE natural sentence. ALWAYS mention 2-4 specific days with times. Example: 'I have Tuesday morning, Wednesday at 2, and Thursday afternoon free'. Be brief. Max 25 words."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": raw_summary
                }
            ],
            max_tokens=60,
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        duration = time_module.time() - start_time
        logger.info(f"[NATURALIZE] Converted availability in {duration:.2f}s: '{result[:50]}...'")
        
        return result
        
    except Exception as e:
        logger.warning(f"[NATURALIZE] Failed to naturalize, using fallback: {e}")
        # Fallback: simple join
        if len(day_summaries) == 2:
            return f"{day_summaries[0]}, and {day_summaries[1]}"
        else:
            return f"{', '.join(day_summaries[:-1])}, and {day_summaries[-1]}"


class ServiceMatcher:
    """
    Intelligent service matching using multiple strategies.
    
    Scalable approach that works with any services without hardcoded values:
    1. Exact/substring matching (fastest)
    2. Fuzzy string matching using difflib (handles typos)
    3. Token-based TF-IDF style scoring (semantic similarity)
    4. N-gram matching (catches partial word matches)
    
    Falls back to "General Service" when confidence is low.
    """
    
    # Common English stop words to ignore in matching
    # NOTE: Do NOT add domain-specific words here (paint, electrical, pipe, etc.)
    # Only add truly generic words that don't help distinguish services
    STOP_WORDS = frozenset([
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
        'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
        'because', 'until', 'while', 'although', 'though', 'after', 'before',
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
        'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
        'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them',
        'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this',
        'that', 'these', 'those', 'am', 'been', 'being', 'got', 'get', 'getting',
        # Generic job/service words that don't help with matching
        'work', 'works', 'working', 'job', 'jobs', 'service', 'services',
        'help', 'helps', 'helping', 'needed', 'needs', 'want', 'wants',
        'like', 'please', 'thanks', 'thank', 'done', 'complete', 'completed'
    ])
    
    # Minimum confidence threshold for a match (0-100)
    MATCH_THRESHOLD = 35
    
    @classmethod
    def tokenize(cls, text: str) -> list:
        """
        Tokenize text into meaningful words, removing stop words.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of meaningful tokens
        """
        import re
        if not text:
            return []
        
        # Convert to lowercase and extract words (3+ chars)
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        
        # Remove stop words
        return [w for w in words if w not in cls.STOP_WORDS]
    
    @classmethod
    def get_ngrams(cls, text: str, n: int = 3) -> set:
        """
        Generate character n-grams from text for fuzzy matching.
        
        Args:
            text: Input text
            n: N-gram size (default 3 for trigrams)
            
        Returns:
            Set of n-grams
        """
        text = text.lower().replace(' ', '')
        if len(text) < n:
            return {text}
        return {text[i:i+n] for i in range(len(text) - n + 1)}
    
    @classmethod
    def ngram_similarity(cls, text1: str, text2: str, n: int = 3) -> float:
        """
        Calculate n-gram similarity between two strings.
        
        Args:
            text1: First string
            text2: Second string
            n: N-gram size
            
        Returns:
            Similarity score (0-1)
        """
        ngrams1 = cls.get_ngrams(text1, n)
        ngrams2 = cls.get_ngrams(text2, n)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0
    
    @classmethod
    def fuzzy_match_score(cls, text1: str, text2: str) -> float:
        """
        Calculate fuzzy match score using multiple methods.
        
        Args:
            text1: First string
            text2: Second string
            
        Returns:
            Combined similarity score (0-1)
        """
        from difflib import SequenceMatcher
        
        if not text1 or not text2:
            return 0.0
        
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        # Method 1: Sequence matcher (handles insertions, deletions, substitutions)
        seq_score = SequenceMatcher(None, text1_lower, text2_lower).ratio()
        
        # Method 2: N-gram similarity (handles partial matches)
        ngram_score = cls.ngram_similarity(text1_lower, text2_lower)
        
        # Combine scores (weighted average)
        return (seq_score * 0.6) + (ngram_score * 0.4)
    
    @classmethod
    def token_overlap_score(cls, tokens1: list, tokens2: list) -> float:
        """
        Calculate token overlap score with TF-IDF style weighting.
        
        Longer/rarer words get higher weight.
        
        Args:
            tokens1: First token list
            tokens2: Second token list
            
        Returns:
            Weighted overlap score (0-1)
        """
        if not tokens1 or not tokens2:
            return 0.0
        
        set1 = set(tokens1)
        set2 = set(tokens2)
        
        # Find matching tokens
        matches = set1 & set2
        
        if not matches:
            return 0.0
        
        # Weight by token length (longer words are more specific)
        weighted_match_score = sum(len(t) for t in matches)
        max_possible = sum(len(t) for t in set1 | set2)
        
        return weighted_match_score / max_possible if max_possible > 0 else 0.0
    
    @classmethod
    def calculate_match_score(cls, job_description: str, service: dict) -> tuple:
        """
        Calculate comprehensive match score between job description and service.
        
        Prioritizes service NAME matches over description matches.
        
        Args:
            job_description: The job description from customer
            service: Service dict with name, description, category
            
        Returns:
            Tuple of (score 0-100, match_details dict)
        """
        service_name = (service.get('name') or '').strip()
        service_desc = (service.get('description') or '').strip()
        service_category = (service.get('category') or '').strip()
        
        job_lower = job_description.lower().strip()
        name_lower = service_name.lower()
        desc_lower = service_desc.lower()
        
        # Tokenize job description
        job_tokens = cls.tokenize(job_description)
        
        # Tokenize service name ONLY (prioritize name matches)
        name_tokens = cls.tokenize(service_name)
        
        # Tokenize description separately
        desc_tokens = cls.tokenize(service_desc)
        
        # Tokenize full service text (name + description + category)
        service_text = f"{service_name} {service_desc} {service_category}"
        service_tokens = cls.tokenize(service_text)
        
        score = 0
        match_type = "none"
        
        # Strategy 1: Exact match (100 points)
        if job_lower == name_lower:
            return (100, {"type": "exact", "matched": service_name})
        
        # Strategy 2: Substring match (85-95 points)
        if name_lower in job_lower:
            score = 95
            match_type = "name_in_job"
        elif job_lower in name_lower:
            score = 90
            match_type = "job_in_name"
        elif len(name_lower) > 4 and any(name_lower in job_lower.replace(' ', '') for _ in [1]):
            # Check without spaces (e.g., "pipe repair" matches "piperepair")
            score = 85
            match_type = "substring_nospace"
        
        if score >= 85:
            return (score, {"type": match_type, "matched": service_name})
        
        # Strategy 3: NAME token overlap (up to 85 points) - PRIORITIZED
        name_token_score = cls.token_overlap_score(job_tokens, name_tokens)
        if name_token_score > 0:
            # Scale to 0-85 range (higher than description matches)
            name_token_points = int(name_token_score * 85)
            if name_token_points > score:
                score = name_token_points
                match_type = "name_token_overlap"
        
        # Strategy 4: Fuzzy name match (up to 80 points)
        fuzzy_name_score = cls.fuzzy_match_score(job_description, service_name)
        if fuzzy_name_score > 0.5:  # Only consider if reasonably similar
            fuzzy_points = int(fuzzy_name_score * 80)
            if fuzzy_points > score:
                score = fuzzy_points
                match_type = "fuzzy_name"
        
        # Strategy 5: Description keyword match (up to 75 points)
        # Check if job description words appear in service description
        # This helps differentiate similar services (Interior vs Exterior Painting)
        desc_token_score = cls.token_overlap_score(job_tokens, desc_tokens)
        if desc_token_score > 0:
            desc_token_points = int(desc_token_score * 75)
            if desc_token_points > score:
                score = desc_token_points
                match_type = "desc_token_overlap"
        
        # Strategy 6: Full token overlap including description (up to 70 points)
        token_score = cls.token_overlap_score(job_tokens, service_tokens)
        if token_score > 0:
            # Scale to 0-70 range (lower than name-only matches)
            token_points = int(token_score * 70)
            if token_points > score:
                score = token_points
                match_type = "token_overlap"
        
        # Strategy 7: Fuzzy description match (up to 55 points)
        if service_desc:
            fuzzy_desc_score = cls.fuzzy_match_score(job_description, service_desc)
            if fuzzy_desc_score > 0.4:
                fuzzy_desc_points = int(fuzzy_desc_score * 55)
                if fuzzy_desc_points > score:
                    score = fuzzy_desc_points
                    match_type = "fuzzy_description"
        
        # Strategy 8: Category match bonus (+10 points)
        if service_category and service_category.lower() in job_lower:
            score = min(100, score + 10)
            match_type = f"{match_type}+category"
        
        # Strategy 9: Individual word fuzzy match against NAME ONLY (catches typos)
        # Only match against service name tokens, not description
        if score < cls.MATCH_THRESHOLD:
            for job_word in job_tokens:
                if len(job_word) >= 4:  # Only check meaningful words
                    for name_word in name_tokens:
                        if len(name_word) >= 4:
                            word_similarity = cls.fuzzy_match_score(job_word, name_word)
                            # Lower threshold (0.6) to catch word variations like paint/painting
                            if word_similarity > 0.6:
                                word_score = int(word_similarity * 60)
                                if word_score > score:
                                    score = word_score
                                    match_type = f"name_word_match:{job_word}~{name_word}"
        
        # Strategy 10: Stem matching - check if job word is prefix of name word or vice versa
        # This catches paint->painting, electric->electrical, etc.
        if score < cls.MATCH_THRESHOLD:
            for job_word in job_tokens:
                if len(job_word) >= 4:
                    for name_word in name_tokens:
                        if len(name_word) >= 4:
                            # Check if one is prefix of the other (stem match)
                            if name_word.startswith(job_word) or job_word.startswith(name_word):
                                stem_score = 50  # Good match for stem
                                if stem_score > score:
                                    score = stem_score
                                    match_type = f"stem_match:{job_word}~{name_word}"
        
        # Strategy 11: Description keyword bonus when name matches are tied
        # If we have a name match, check description for differentiating keywords
        # Also check for stem/plural matches (fence/fences, wall/walls)
        if score >= cls.MATCH_THRESHOLD and desc_tokens:
            desc_overlap = set(job_tokens) & set(desc_tokens)
            
            # Also check for stem matches in description
            for job_word in job_tokens:
                if len(job_word) >= 4:
                    for desc_word in desc_tokens:
                        if len(desc_word) >= 4:
                            # Check if one is prefix of the other (stem/plural match)
                            if desc_word.startswith(job_word) or job_word.startswith(desc_word):
                                desc_overlap.add(job_word)
            
            if desc_overlap:
                # Add bonus for description keyword matches
                bonus = min(15, len(desc_overlap) * 5)
                score = min(100, score + bonus)
                match_type = f"{match_type}+desc_bonus"
        
        return (score, {"type": match_type, "matched": service_name, "tokens_matched": len(set(job_tokens) & set(service_tokens))})
    
    @classmethod
    def match(cls, job_description: str, services: list, default_duration: int = 1440) -> dict:
        """
        Match a job description to the best service.
        
        Args:
            job_description: Description of the job from customer
            services: List of service dicts from database
            default_duration: Default duration if no match found (1 day for trades)
            
        Returns:
            Dict with matched service info
        """
        if not job_description or not job_description.strip():
            return cls._create_general_fallback(services, default_duration, "empty_description")
        
        best_match = None
        best_score = 0
        best_details = {}
        general_service = None
        
        for service in services:
            service_name = (service.get('name') or '').lower()
            service_category = (service.get('category') or '').lower()
            
            # Track General service for fallback
            if 'general' in service_name or service_category == 'general':
                general_service = service
                continue  # Don't match against General service directly
            
            score, details = cls.calculate_match_score(job_description, service)
            
            if score > best_score:
                best_score = score
                best_match = service
                best_details = details
        
        # Check if match meets threshold
        if best_match and best_score >= cls.MATCH_THRESHOLD:
            matched_name = best_match.get('name', 'Unknown')
            logger.debug(f"Service match: '{job_description}' -> '{matched_name}' (score: {best_score}, type: {best_details.get('type', 'unknown')})")
            return {
                'service': best_match,
                'score': best_score,
                'matched_name': matched_name,
                'match_details': best_details,
                'is_general': False
            }
        
        # Fall back to General service
        return cls._create_general_fallback(
            services, 
            default_duration, 
            f"low_score:{best_score}" if best_match else "no_services",
            general_service
        )
    
    @classmethod
    def _create_general_fallback(cls, services: list, default_duration: int, reason: str, general_service: dict = None) -> dict:
        """Create a General service fallback response."""
        from src.utils.config import config
        
        # Get default charge from config
        default_charge = getattr(config, 'DEFAULT_APPOINTMENT_CHARGE', 50.0)
        
        # Use existing General service if available
        if general_service:
            # Ensure General service has a price (use default if not set)
            if not general_service.get('price') or general_service.get('price') == 0:
                general_service = dict(general_service)  # Make a copy
                general_service['price'] = default_charge
            logger.debug(f"Using General Service (reason: {reason})")
            return {
                'service': general_service,
                'score': 0,
                'matched_name': general_service.get('name', 'General Service'),
                'match_details': {'type': 'fallback', 'reason': reason},
                'is_general': True
            }
        
        # Find General service in list
        for service in services:
            service_name = (service.get('name') or '').lower()
            service_category = (service.get('category') or '').lower()
            if 'general' in service_name or service_category == 'general':
                # Ensure it has a price
                if not service.get('price') or service.get('price') == 0:
                    service = dict(service)  # Make a copy
                    service['price'] = default_charge
                logger.debug(f"Using General Service (reason: {reason})")
                return {
                    'service': service,
                    'score': 0,
                    'matched_name': service.get('name', 'General Service'),
                    'match_details': {'type': 'fallback', 'reason': reason},
                    'is_general': True
                }
        
        # Create virtual General service with default charge
        logger.debug(f"Creating virtual General Service (reason: {reason})")
        return {
            'service': {
                'id': 'general_default',
                'name': 'General Service',
                'category': 'General',
                'description': 'Default service',
                'duration_minutes': default_duration,
                'price': default_charge,
                'emergency_price': default_charge * 1.5  # 50% more for emergency
            },
            'score': 0,
            'matched_name': 'General Service (default)',
            'match_details': {'type': 'virtual_fallback', 'reason': reason},
            'is_general': True
        }


class AIServiceMatcher:
    """
    AI-powered service matching using OpenAI for complex descriptions.
    
    Use this when:
    - Fuzzy matching returns low confidence (General Service fallback)
    - Customer asks for price/duration information
    
    Performance: ~200-400ms per call (only used as fallback)
    """
    
    # Simple in-memory cache for repeated queries (cleared on restart)
    _cache = {}
    _cache_max_size = 100
    
    @classmethod
    def _get_cache_key(cls, job_description: str, services: list) -> str:
        """Generate cache key from job description and service names"""
        service_names = tuple(sorted(s.get('name', '') for s in services))
        return f"{job_description.lower().strip()}:{hash(service_names)}"
    
    @classmethod
    def match(cls, job_description: str, services: list, default_duration: int = 1440) -> dict:
        """
        Match a job description to the best service using AI.
        
        Args:
            job_description: Description of the job from customer
            services: List of service dicts from database
            default_duration: Default duration if no match found (1 day for trades)
            
        Returns:
            Dict with matched service info
        """
        if not job_description or not job_description.strip():
            return ServiceMatcher._create_general_fallback(services, default_duration, "empty_description")
        
        if not services:
            return ServiceMatcher._create_general_fallback(services, default_duration, "no_services")
        
        # Filter out General Service from matching candidates
        matching_services = [s for s in services if 'general' not in (s.get('name') or '').lower()]
        if not matching_services:
            return ServiceMatcher._create_general_fallback(services, default_duration, "only_general_service")
        
        # Check cache first
        cache_key = cls._get_cache_key(job_description, matching_services)
        if cache_key in cls._cache:
            logger.debug(f"AI match cache hit for: '{job_description[:50]}...'")
            return cls._cache[cache_key]
        
        try:
            import time as time_module
            ai_match_start = time_module.time()
            
            from openai import OpenAI
            from src.utils.config import config
            import json
            
            client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=5.0)  # 5 second timeout
            
            # Build compact service list for the prompt
            service_list = []
            for i, svc in enumerate(matching_services):
                name = svc.get('name', 'Unknown')
                desc = svc.get('description', '')
                # Keep descriptions short to reduce tokens
                if desc and len(desc) > 50:
                    desc = desc[:50] + '...'
                service_list.append(f"{i+1}. {name}" + (f" ({desc})" if desc else ""))
            
            services_text = "\n".join(service_list)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Match customer problem to service. Return JSON: {\"idx\":<1-based index or 0 if no match>,\"conf\":<0-100>}"
                    },
                    {
                        "role": "user",
                        "content": f"Problem: {job_description[:200]}\n\nServices:\n{services_text}"
                    }
                ],
                temperature=0,
                max_tokens=50  # Minimal tokens for speed
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response - handle markdown code blocks
            if '```' in result_text:
                result_text = result_text.split('```')[1].replace('json', '').strip()
            
            result = json.loads(result_text)
            service_index = result.get('idx', result.get('service_index', 0))
            confidence = result.get('conf', result.get('confidence', 0))
            
            ai_match_duration = time_module.time() - ai_match_start
            print(f"[SERVICE_TIMING] ⏱️ AI service match took {ai_match_duration:.3f}s")
            
            # Valid match found
            if service_index > 0 and service_index <= len(matching_services) and confidence >= 40:
                matched_service = matching_services[service_index - 1]
                logger.info(f"AI match: '{job_description[:30]}...' -> '{matched_service.get('name')}' ({confidence}%)")
                
                match_result = {
                    'service': matched_service,
                    'score': confidence,
                    'matched_name': matched_service.get('name', 'Unknown'),
                    'match_details': {'type': 'ai_match'},
                    'is_general': False
                }
                
                # Cache the result (with size limit)
                if len(cls._cache) >= cls._cache_max_size:
                    cls._cache.pop(next(iter(cls._cache)))  # Remove oldest
                cls._cache[cache_key] = match_result
                
                return match_result
            
            # No good match
            logger.debug(f"AI match: No match for '{job_description[:30]}...' (conf: {confidence})")
            return ServiceMatcher._create_general_fallback(services, default_duration, f"ai_low_conf:{confidence}")
            
        except Exception as e:
            ai_match_duration = time_module.time() - ai_match_start
            print(f"[SERVICE_TIMING] ❌ AI service match FAILED after {ai_match_duration:.3f}s: {e}")
            logger.warning(f"AI matching failed: {e}")
            return ServiceMatcher._create_general_fallback(services, default_duration, f"ai_error")


def match_service(job_description: str, company_id: int = None, use_ai_fallback: bool = True) -> dict:
    """
    Match a job description to a service from the services menu.
    
    Uses intelligent multi-strategy matching that works with any services.
    Falls back to AI matching if fuzzy match confidence is low.
    Falls back to "General Service" if no good match is found.
    
    Args:
        job_description: Description of the job (e.g., 'leaking pipe', 'power outage')
        company_id: Company ID for multi-tenant isolation
        use_ai_fallback: Whether to use AI matching when fuzzy match is low confidence (default True)
    
    Returns:
        Dict with matched service info:
        {
            'service': The matched service dict (or General service),
            'score': Match score (0-100),
            'matched_name': Name of matched service,
            'is_general': True if fell back to General service
        }
    """
    from src.services.settings_manager import get_settings_manager
    
    try:
        # Load services from database
        settings_mgr = get_settings_manager()
        services = settings_mgr.get_services(company_id=company_id)
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)
        
        # First try fast fuzzy matching
        result = ServiceMatcher.match(job_description, services, default_duration)
        
        # If fuzzy match has low confidence and we have multiple services, try AI matching
        # AI threshold: score < 50 means fuzzy match isn't confident
        if use_ai_fallback and result.get('is_general', False) and len(services) > 1:
            logger.debug(f"Fuzzy match returned General Service (score: {result.get('score', 0)}) - trying AI matching")
            try:
                ai_result = AIServiceMatcher.match(job_description, services, default_duration)
                # Only use AI result if it found a specific service (not General)
                if not ai_result.get('is_general', True):
                    logger.info(f"AI match improved result: '{job_description}' -> '{ai_result['matched_name']}' (confidence: {ai_result.get('score', 0)})")
                    return ai_result
            except Exception as ai_error:
                logger.warning(f"AI matching failed, using fuzzy result: {ai_error}")
        
        return result
        
    except Exception as e:
        logger.warning(f"Error matching service: {e}")
        from src.utils.config import config
        default_charge = getattr(config, 'DEFAULT_APPOINTMENT_CHARGE', 50.0)
        return {
            'service': {
                'id': 'general_default',
                'name': 'General Service',
                'category': 'General',
                'description': 'Default service',
                'duration_minutes': 60,
                'price': default_charge,
                'emergency_price': default_charge * 1.5
            },
            'score': 0,
            'matched_name': 'General Service (error fallback)',
            'match_details': {'type': 'error', 'error': str(e)},
            'is_general': True
        }


def get_service_price(job_description: str, urgency: str = 'scheduled', company_id: int = None) -> float:
    """
    Get the price for a service from the services menu based on job description and urgency.
    
    Uses the unified match_service function for consistent matching.
    
    Args:
        job_description: Description of the job (e.g., 'exterior painting', 'leak repairs')
        urgency: Urgency level ('emergency', 'same-day', 'scheduled', 'quote')
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Price in EUR, or 0 as default if not found
    """
    try:
        match_result = match_service(job_description, company_id=company_id)
        service = match_result['service']
        
        # Use emergency price if urgency is emergency and available
        if urgency == 'emergency' and service.get('emergency_price'):
            price = float(service['emergency_price'])
            logger.debug(f"Pricing: '{job_description}' -> '{match_result['matched_name']}' - EMERGENCY: EUR{price}")
            return price
        else:
            price = float(service.get('price', 0))
            logger.debug(f"Pricing: '{job_description}' -> '{match_result['matched_name']}' - Standard: EUR{price}")
            return price
        
    except Exception as e:
        logger.warning(f"Error loading service price: {e}, using default EUR0")
        return 0


def match_service_with_ai(job_description: str, company_id: int = None, use_ai: bool = True) -> dict:
    """
    Match a job description to a service, optionally using AI for better accuracy.
    
    Use this when:
    - Customer asks about price or duration
    - Call ends and we need accurate service categorization
    - Fuzzy matching returns low confidence
    
    Args:
        job_description: Description of the job
        company_id: Company ID for multi-tenant isolation
        use_ai: Whether to use AI matching (default True)
    
    Returns:
        Dict with matched service info
    """
    from src.services.settings_manager import get_settings_manager
    
    try:
        settings_mgr = get_settings_manager()
        services = settings_mgr.get_services(company_id=company_id)
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)
        
        if use_ai and len(services) > 1:
            # Use AI matching for better accuracy
            return AIServiceMatcher.match(job_description, services, default_duration)
        else:
            # Use fast fuzzy matching
            return ServiceMatcher.match(job_description, services, default_duration)
            
    except Exception as e:
        logger.warning(f"Error in AI service matching: {e}")
        return match_service(job_description, company_id=company_id)


def get_service_info_with_ai(job_description: str, company_id: int = None) -> dict:
    """
    Get comprehensive service info using AI matching.
    
    Use this when customer asks about price, duration, or service details.
    Returns price, duration, and service name in one call.
    
    Args:
        job_description: Description of the job
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Dict with service info: {
            'service_name': str,
            'price': float,
            'duration_minutes': int,
            'is_general': bool,
            'confidence': int
        }
    """
    match_result = match_service_with_ai(job_description, company_id=company_id, use_ai=True)
    service = match_result['service']
    
    return {
        'service_name': match_result['matched_name'],
        'price': float(service.get('price', 0)),
        'duration_minutes': int(service.get('duration_minutes', 60)),
        'is_general': match_result.get('is_general', False),
        'confidence': match_result.get('score', 0)
    }


def get_service_duration(job_description: str, company_id: int = None) -> int:
    """
    Get the duration for a service from the services menu based on job description.
    
    Uses the unified match_service function for consistent matching.
    
    Args:
        job_description: Description of the job (e.g., 'exterior painting', 'leak repairs')
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Duration in minutes, or default duration if not found
    """
    try:
        from src.services.settings_manager import get_settings_manager
        settings_mgr = get_settings_manager()
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)
        
        match_result = match_service(job_description, company_id=company_id)
        service = match_result['service']
        
        duration = service.get('duration_minutes', default_duration)
        logger.debug(f"Duration: '{job_description}' -> '{match_result['matched_name']}' - {duration} mins")
        return duration
        
    except Exception as e:
        logger.warning(f"Error loading service duration: {e}, using default 1440 mins (1 day)")
        return 1440


def get_matched_service_name(job_description: str, company_id: int = None) -> str:
    """
    Get the matched service name for a job description.
    
    Args:
        job_description: Description of the job
        company_id: Company ID for multi-tenant isolation
    
    Returns:
        Name of the matched service
    """
    match_result = match_service(job_description, company_id=company_id)
    return match_result['matched_name']


def execute_tool_call(tool_name: str, arguments: dict, services: dict) -> dict:
    """
    Execute a tool call and return the result.
    
    HYBRID ARCHITECTURE:
    - This handles QUERY tools only (check_availability, lookup_customer)
    - Booking/cancellation/rescheduling use existing callback system
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments for the tool
        services: Dictionary containing service instances (google_calendar, db, company_id, etc.)
    
    Returns:
        Dictionary with success status and result data
    """
    import time as time_module
    from datetime import datetime, timedelta
    from ..utils.date_parser import parse_datetime
    from src.utils.config import config
    
    tool_start_time = time_module.time()
    logger.info(f"[TOOL_EXEC] ========== EXECUTING TOOL: {tool_name} ==========")
    logger.info(f"[TOOL_EXEC] Arguments: {arguments}")
    print(f"[TOOL_TIMING] ⏱️ {tool_name} started at {tool_start_time:.3f}")
    
    google_calendar = services.get('google_calendar')
    db = services.get('db') or services.get('database')  # Support both keys
    # CRITICAL: Extract company_id for proper multi-tenant data isolation
    company_id = services.get('company_id')
    
    logger.info(f"[TOOL_EXEC] Services: calendar={google_calendar is not None}, db={db is not None}, company_id={company_id}")
    
    # Calendar should always be available (database or Google)
    if not google_calendar and tool_name in ['check_availability', 'book_appointment', 'reschedule_appointment', 'cancel_appointment', 'book_job', 'cancel_job', 'reschedule_job']:
        logger.error(f"[TOOL_ERROR] Calendar service is not available for tool {tool_name}")
        return {
            'success': False,
            'message': 'Calendar service is not available. Please contact support.'
        }
    
    try:
        if tool_name == "check_availability":
            logger.info(f"[CHECK_AVAIL] ========== CHECKING AVAILABILITY ==========")
            start_date_str = arguments.get('start_date')
            end_date_str = arguments.get('end_date', start_date_str)
            service_type = arguments.get('service_type', 'general')
            job_description = arguments.get('job_description')  # New: get job description for duration
            
            logger.info(f"[CHECK_AVAIL] start_date={start_date_str}, end_date={end_date_str}, service_type={service_type}, job_description={job_description}")
            
            # Get service duration and workers_required - prefer job_description over service_type for trades
            if job_description:
                match_result = match_service(job_description, company_id=company_id)
                matched_service = match_result['service']
                service_duration = matched_service.get('duration_minutes', 60)
                workers_required = matched_service.get('workers_required', 1) or 1
                worker_restrictions = matched_service.get('worker_restrictions')
                logger.info(f"[CHECK_AVAIL] Service from job_description '{job_description}': {service_duration} mins, {workers_required} worker(s)")
            else:
                match_result = match_service(service_type, company_id=company_id)
                matched_service = match_result['service']
                service_duration = matched_service.get('duration_minutes', 60)
                workers_required = matched_service.get('workers_required', 1) or 1
                worker_restrictions = matched_service.get('worker_restrictions')
                logger.info(f"[CHECK_AVAIL] Service from service_type: {service_duration} mins, {workers_required} worker(s)")
            
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
                logger.info(f"[CHECK_AVAIL] 'this week' expanded to {start_date.strftime('%A, %B %d')} - {end_date.strftime('%A, %B %d')}")
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
                logger.info(f"[CHECK_AVAIL] 'next week' expanded to {start_date.strftime('%A, %B %d')} - {end_date.strftime('%A, %B %d')}")
            else:
                # Parse dates normally - allow_past=True because we're checking a date range
                # get_available_slots_for_day will filter out past time slots
                logger.info(f"[CHECK_AVAIL] Parsing start_date: {start_date_str}")
                start_date = parse_datetime(start_date_str, require_time=False, default_time=(9, 0), allow_past=True)
                if not start_date:
                    logger.warning(f"[CHECK_AVAIL] Could not parse start_date, using today")
                    start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
                
                if end_date_str and end_date_str != start_date_str:
                    end_date = parse_datetime(end_date_str, require_time=False, default_time=(17, 0), allow_past=True)
                    if not end_date:
                        logger.warning(f"[CHECK_AVAIL] Could not parse end_date '{end_date_str}', defaulting to 7 days from start")
                        end_date = start_date + timedelta(days=7)
                        end_date = end_date.replace(hour=17, minute=0, second=0, microsecond=0)
                else:
                    end_date = start_date.replace(hour=17, minute=0)
                
                logger.info(f"[CHECK_AVAIL] Parsed dates: {start_date} to {end_date}")
            
            # Collect available slots across date range
            from collections import defaultdict
            slots_by_day = defaultdict(list)
            current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_search = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            logger.info(f"[CHECK_AVAIL] Searching from {current_date.strftime('%Y-%m-%d')} to {end_search.strftime('%Y-%m-%d')}")
            
            # Get dynamic business days
            try:
                business_days = config.get_business_days_indices()
            except:
                business_days = config.BUSINESS_DAYS
            
            # EDGE CASE: If asking for a single closed day (weekend), return "we're closed" message
            is_single_day = start_date.date() == end_date.date()
            if is_single_day and start_date.weekday() not in business_days:
                day_name = start_date.strftime('%A')
                return {
                    "success": True,
                    "available_slots": [],
                    "message": f"We're not open on {day_name}s. Would you like to try a different day?",
                    "is_closed_day": True
                }
            
            
            logger.info(f"[CHECK_AVAIL] Business days: {business_days}")
            
            # Check if company has workers - if so, we need to filter by worker availability
            has_workers = db.has_workers(company_id) if db else False
            if has_workers:
                logger.info(f"[CHECK_AVAIL] Company has workers, will check WORKER availability (not calendar)")
            
            # Get business hours for slot generation
            try:
                business_hours = config.get_business_hours(company_id=company_id)
                biz_start_hour = business_hours.get('start', 9)
                biz_end_hour = business_hours.get('end', 17)
            except:
                biz_start_hour = 9
                biz_end_hour = 17
            
            # Check all days in range (no early exit - we want full picture)
            while current_date <= end_search:
                # Only check business days (configured in config.BUSINESS_DAYS)
                if current_date.weekday() in business_days:
                    logger.info(f"[CHECK_AVAIL] Checking {current_date.strftime('%A, %B %d')} (weekday {current_date.weekday()})")
                    
                    if has_workers and db:
                        # WORKER-BASED AVAILABILITY: Generate all possible slots and check worker availability
                        # This is the correct approach for multi-worker businesses
                        day_slots = []
                        now = datetime.now()
                        
                        # Generate time slots for the day
                        slot_time = current_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
                        day_end = current_date.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
                        
                        while slot_time < day_end:
                            # Skip past time slots
                            if slot_time <= now:
                                slot_time += timedelta(minutes=30)
                                continue
                            
                            # For full-day services, check if slot + duration fits in business hours
                            if service_duration >= 480:
                                slot_end = day_end  # Full day ends at closing
                            else:
                                slot_end = slot_time + timedelta(minutes=service_duration)
                            
                            # Skip if job would extend past closing
                            if slot_end > day_end:
                                slot_time += timedelta(minutes=30)
                                continue
                            
                            # Check if any qualified worker is available at this slot
                            available_workers = db.find_available_workers_for_slot(
                                appointment_time=slot_time,
                                duration_minutes=service_duration,
                                company_id=company_id
                            )
                            
                            # Apply worker restrictions if any
                            if available_workers and worker_restrictions:
                                restriction_type = worker_restrictions.get('type', 'all')
                                restricted_ids = worker_restrictions.get('worker_ids', [])
                                
                                if restriction_type == 'only' and restricted_ids:
                                    available_workers = [w for w in available_workers if w['id'] in restricted_ids]
                                elif restriction_type == 'except' and restricted_ids:
                                    available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
                            
                            # Slot is available if enough workers are free
                            if available_workers is None or len(available_workers) >= workers_required:
                                day_slots.append(slot_time)
                            
                            slot_time += timedelta(minutes=30)
                        
                        logger.info(f"[CHECK_AVAIL] Worker-based check found {len(day_slots)} slots")
                    else:
                        # NO WORKERS: Use calendar-based availability (any booking blocks the slot)
                        try:
                            day_slots = google_calendar.get_available_slots_for_day(current_date, service_duration=service_duration)
                            logger.info(f"[CHECK_AVAIL] Calendar-based check found {len(day_slots) if day_slots else 0} slots")
                        except Exception as e:
                            logger.error(f"[CHECK_AVAIL] Error checking {current_date.strftime('%A, %B %d')}: {e}")
                            import traceback
                            traceback.print_exc()
                            raise
                    
                    # For full-day services (8+ hours), only keep ONE slot per day (start of business day)
                    # This prevents offering hourly slots that can't actually be booked
                    if day_slots and service_duration >= 480:
                        # Keep only the first slot (start of business day)
                        day_slots = [day_slots[0]]
                        logger.info(f"[CHECK_AVAIL] Full-day service - reduced to 1 slot per day: {day_slots[0].strftime('%I:%M %p')}")
                    
                    if day_slots:
                        day_key = current_date.strftime('%Y-%m-%d')
                        slots_by_day[day_key] = day_slots
                        logger.debug(f"   Found {len(day_slots)} slots")
                    else:
                        logger.debug(f"   No slots available")
                else:
                    logger.debug(f"[SKIP] Skipping {current_date.strftime('%A, %B %d')} (weekend)")
                current_date += timedelta(days=1)
            
            if not slots_by_day:
                # Natural language for no availability
                if start_date.date() == end_date.date():
                    # Same day - use natural language
                    day_name = start_date.strftime('%A')
                    if start_date.date() == datetime.now().date():
                        no_avail_msg = "Today is fully booked"
                    elif (start_date.date() - datetime.now().date()).days == 1:
                        no_avail_msg = "Tomorrow is fully booked"
                    else:
                        no_avail_msg = f"{day_name} is fully booked"
                else:
                    # Date range
                    no_avail_msg = f"No openings between {start_date.strftime('%A')} and {end_date.strftime('%A')}"
                
                return {
                    "success": True,
                    "available_slots": [],
                    "message": no_avail_msg
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
                
                # For full-day services (8+ hours), describe as "full day" instead of time range
                if service_duration >= 480:  # 8 hours or more
                    summary = f"{day_name}: full day available"
                elif len(day_slots) >= 6:
                    # Many slots available - describe as a range
                    # Use trades-friendly language: "free from X to Y" instead of "appointments starting from"
                    summary = f"{day_name}: free from {first_time} to {last_time}"
                elif len(day_slots) >= 3:
                    # Several slots - mention range
                    summary = f"{day_name}: available {first_time} to {last_time}"
                else:
                    # Few slots - list them specifically
                    times = [s.strftime('%I %p').lstrip('0').lower().replace(' 0', ' ') for s in day_slots]
                    if len(times) == 1:
                        summary = f"{day_name}: {times[0]} only"
                    elif len(times) == 2:
                        summary = f"{day_name}: {times[0]} or {times[1]}"
                    else:
                        summary = f"{day_name}: {', '.join(times[:-1])}, or {times[-1]}"
                
                day_summaries.append(summary)
            
            # Convert to natural conversational speech
            is_full_day_service = service_duration >= 480
            natural_summary = naturalize_availability_summary(day_summaries, is_full_day=is_full_day_service)
            
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
            time_reference = "Next week" if (start_date_str and 'next week' in start_date_str.lower()) else "This week"
            
            tool_duration = time_module.time() - tool_start_time
            print(f"[TOOL_TIMING] ✅ check_availability completed in {tool_duration:.3f}s ({len(all_slots)} slots found)")
            
            # Add special instruction for full-day services
            if service_duration >= 480:
                voice_instruction = "Say the natural_summary naturally. For full-day jobs, ask which DAY works - DO NOT ask for a specific time. Just confirm the day."
            else:
                voice_instruction = "Say the natural_summary naturally and conversationally. Then ask which day/time works for them."
            
            return {
                "success": True,
                "available_slots": formatted_slots,
                "total_count": len(all_slots),
                "natural_summary": natural_summary,
                "message": f"{time_reference} I have: {natural_summary}",
                "voice_instruction": voice_instruction,
                "is_full_day_service": service_duration >= 480
            }
        
        elif tool_name == "get_next_available":
            # ========== GET_NEXT_AVAILABLE ==========
            # Find the next 2-4 available days for initial suggestion
            logger.info(f"[GET_NEXT_AVAIL] ========== FINDING NEXT AVAILABLE SLOTS ==========")
            job_description = arguments.get('job_description', 'general service')
            weeks_to_search = arguments.get('weeks_to_search', 3)
            
            # Get service info
            match_result = match_service(job_description, company_id=company_id)
            matched_service = match_result['service']
            service_duration = matched_service.get('duration_minutes', 60)
            workers_required = matched_service.get('workers_required', 1) or 1
            worker_restrictions = matched_service.get('worker_restrictions')
            is_full_day = service_duration >= 480
            
            logger.info(f"[GET_NEXT_AVAIL] Job: '{job_description}' -> {service_duration} mins, {workers_required} worker(s), full_day={is_full_day}")
            
            # Search from today through N weeks
            from collections import defaultdict
            slots_by_day = defaultdict(list)
            today = datetime.now()
            end_search = today + timedelta(weeks=weeks_to_search)
            current_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Get business config
            try:
                business_days = config.get_business_days_indices()
            except:
                business_days = [0, 1, 2, 3, 4]  # Mon-Fri
            
            try:
                business_hours = config.get_business_hours(company_id=company_id)
                biz_start_hour = business_hours.get('start', 9)
                biz_end_hour = business_hours.get('end', 17)
            except:
                biz_start_hour = 9
                biz_end_hour = 17
            
            has_workers = db.has_workers(company_id) if db else False
            available_days = []  # List of (date, slots) tuples
            
            # Search until we find at least 2-4 days or exhaust search range
            while current_date <= end_search and len(available_days) < 4:
                if current_date.weekday() in business_days:
                    day_slots = []
                    now = datetime.now()
                    
                    if has_workers and db:
                        # Worker-based availability
                        slot_time = current_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
                        day_end = current_date.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
                        
                        while slot_time < day_end:
                            if slot_time <= now:
                                slot_time += timedelta(minutes=30)
                                continue
                            
                            if service_duration >= 480:
                                slot_end = day_end
                            else:
                                slot_end = slot_time + timedelta(minutes=service_duration)
                            
                            if slot_end > day_end:
                                slot_time += timedelta(minutes=30)
                                continue
                            
                            available_workers = db.find_available_workers_for_slot(
                                appointment_time=slot_time,
                                duration_minutes=service_duration,
                                company_id=company_id
                            )
                            
                            if available_workers and worker_restrictions:
                                restriction_type = worker_restrictions.get('type', 'all')
                                restricted_ids = worker_restrictions.get('worker_ids', [])
                                if restriction_type == 'only' and restricted_ids:
                                    available_workers = [w for w in available_workers if w['id'] in restricted_ids]
                                elif restriction_type == 'except' and restricted_ids:
                                    available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
                            
                            if available_workers is None or len(available_workers) >= workers_required:
                                day_slots.append(slot_time)
                            
                            slot_time += timedelta(minutes=30)
                    else:
                        # Calendar-based availability
                        try:
                            day_slots = google_calendar.get_available_slots_for_day(current_date, service_duration=service_duration)
                        except:
                            day_slots = []
                    
                    # For full-day services, only keep one slot per day
                    if day_slots and is_full_day:
                        day_slots = [day_slots[0]]
                    
                    if day_slots:
                        available_days.append((current_date, day_slots))
                
                current_date += timedelta(days=1)
            
            if not available_days:
                tool_duration = time_module.time() - tool_start_time
                print(f"[TOOL_TIMING] ✅ get_next_available completed in {tool_duration:.3f}s (0 days found)")
                return {
                    "success": True,
                    "available_days": [],
                    "message": f"I don't have any availability in the next {weeks_to_search} weeks. Would you like me to check further out?",
                    "is_full_day_service": is_full_day
                }
            
            # Build natural language summary - ALWAYS show at least 2 options
            day_summaries = []
            for day_date, day_slots in available_days[:4]:  # Max 4 days
                day_name = day_date.strftime('%A')
                # Add date for clarity (e.g., "Monday the 16th")
                day_num = day_date.day
                suffix = 'th' if 11 <= day_num <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day_num % 10, 'th')
                day_with_date = f"{day_name} the {day_num}{suffix}"
                
                if is_full_day:
                    day_summaries.append(f"{day_with_date}: full day available")
                else:
                    first_time = day_slots[0].strftime('%I %p').lstrip('0').lower()
                    last_time = day_slots[-1].strftime('%I %p').lstrip('0').lower()
                    if len(day_slots) >= 4:
                        day_summaries.append(f"{day_with_date}: free from {first_time} to {last_time}")
                    elif len(day_slots) == 1:
                        day_summaries.append(f"{day_with_date}: {first_time} only")
                    else:
                        times = [s.strftime('%I %p').lstrip('0').lower() for s in day_slots[:3]]
                        day_summaries.append(f"{day_with_date}: {' or '.join(times)}")
            
            # Generate natural summary
            natural_summary = naturalize_availability_summary(day_summaries, is_full_day=is_full_day)
            
            # Build structured data
            formatted_days = []
            for day_date, day_slots in available_days[:4]:
                formatted_days.append({
                    "date": day_date.strftime('%A, %B %d, %Y'),
                    "day_name": day_date.strftime('%A'),
                    "slots_count": len(day_slots),
                    "first_slot": day_slots[0].strftime('%I:%M %p') if day_slots else None,
                    "last_slot": day_slots[-1].strftime('%I:%M %p') if day_slots else None,
                    "iso_date": day_date.strftime('%Y-%m-%d')
                })
            
            tool_duration = time_module.time() - tool_start_time
            print(f"[TOOL_TIMING] ✅ get_next_available completed in {tool_duration:.3f}s ({len(available_days)} days found)")
            
            if is_full_day:
                voice_instruction = "Present these days naturally. Ask which DAY works - don't mention times for full-day jobs."
            else:
                voice_instruction = "Present these options naturally. Ask which day and time works for them."
            
            return {
                "success": True,
                "available_days": formatted_days,
                "natural_summary": natural_summary,
                "message": natural_summary,
                "voice_instruction": voice_instruction,
                "is_full_day_service": is_full_day,
                "days_found": len(available_days)
            }
        
        elif tool_name == "search_availability":
            # ========== SEARCH_AVAILABILITY ==========
            # Handle specific customer queries about dates/times
            logger.info(f"[SEARCH_AVAIL] ========== SEARCHING AVAILABILITY ==========")
            query = arguments.get('query', '')
            job_description = arguments.get('job_description', 'general service')
            
            logger.info(f"[SEARCH_AVAIL] Query: '{query}', Job: '{job_description}'")
            
            # Get service info
            match_result = match_service(job_description, company_id=company_id)
            matched_service = match_result['service']
            service_duration = matched_service.get('duration_minutes', 60)
            workers_required = matched_service.get('workers_required', 1) or 1
            worker_restrictions = matched_service.get('worker_restrictions')
            is_full_day = service_duration >= 480
            
            today = datetime.now()
            query_lower = query.lower().strip()
            
            # FAST PATH: Handle common patterns without AI to save ~1-2s
            start_date = None
            end_date = None
            time_filter = None
            specific_days = None
            used_fast_path = False
            
            # Fast path: "next month" or specific month names
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            
            if 'next month' in query_lower:
                # Next month from today
                next_month = today.replace(day=1) + timedelta(days=32)
                start_date = next_month.replace(day=1)
                # Search first 2 weeks of next month
                end_date = start_date + timedelta(days=14)
                used_fast_path = True
                logger.info(f"[SEARCH_AVAIL] Fast path: 'next month' -> {start_date.date()} to {end_date.date()}")
            else:
                # Check for specific month names
                for month_name, month_num in month_names.items():
                    if month_name in query_lower:
                        # User mentioned a specific month
                        year = today.year
                        if month_num < today.month:
                            year += 1  # Next year if month has passed
                        start_date = datetime(year, month_num, 1)
                        end_date = start_date + timedelta(days=14)
                        used_fast_path = True
                        logger.info(f"[SEARCH_AVAIL] Fast path: month '{month_name}' -> {start_date.date()} to {end_date.date()}")
                        break
            
            # Fast path: "the week after next" or "in 2 weeks"
            if not used_fast_path and ('week after' in query_lower or 'in 2 weeks' in query_lower or 'in two weeks' in query_lower):
                # Find Monday 2 weeks from now
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                next_monday = today + timedelta(days=days_until_monday + 7)  # +7 for "week after next"
                start_date = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=4)  # Monday to Friday
                used_fast_path = True
                logger.info(f"[SEARCH_AVAIL] Fast path: 'week after next' -> {start_date.date()} to {end_date.date()}")
            
            # Fast path: "next week"
            if not used_fast_path and 'next week' in query_lower:
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                next_monday = today + timedelta(days=days_until_monday)
                start_date = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=4)  # Monday to Friday
                used_fast_path = True
                logger.info(f"[SEARCH_AVAIL] Fast path: 'next week' -> {start_date.date()} to {end_date.date()}")
            
            # If fast path didn't match, use AI parsing
            if not used_fast_path:
                from openai import OpenAI
                client = OpenAI(api_key=config.OPENAI_API_KEY)
                
                parse_prompt = f"""Parse this availability query and return JSON with search parameters.
Today is {today.strftime('%A, %B %d, %Y')}.

Query: "{query}"

Return JSON with:
- start_date: ISO date string (YYYY-MM-DD) for when to start searching
- end_date: ISO date string for when to stop searching  
- time_filter: "morning" (before 12pm), "afternoon" (12pm-5pm), "evening" (after 5pm), "after_X" (after specific hour), or null for any time
- specific_days: list of day names if they asked for specific days (e.g., ["Monday", "Tuesday"]), or null

Examples:
- "next week" -> start_date: next Monday, end_date: next Friday, time_filter: null
- "after 4pm next week" -> start_date: next Monday, end_date: next Friday, time_filter: "after_16"
- "in 2 weeks" -> start_date: 2 weeks from today, end_date: 2.5 weeks from today
- "Monday or Tuesday" -> specific_days: ["Monday", "Tuesday"], search next 2 weeks
- "any morning slots" -> time_filter: "morning", search next 2 weeks
- "the week after next" -> start_date: 2 Mondays from now, end_date: that Friday

Return ONLY valid JSON, no explanation."""

                try:
                    parse_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": parse_prompt}],
                        max_tokens=200,
                        temperature=0
                    )
                    
                    import json
                    response_content = parse_response.choices[0].message.content.strip()
                    
                    # Strip markdown code blocks if present (```json ... ```)
                    if response_content.startswith('```'):
                        lines = response_content.split('\n')
                        # Remove first line (```json) and last line (```)
                        json_lines = [l for l in lines if not l.startswith('```')]
                        response_content = '\n'.join(json_lines).strip()
                    
                    logger.info(f"[SEARCH_AVAIL] Raw response: {response_content[:200]}")
                    parse_result = json.loads(response_content)
                    logger.info(f"[SEARCH_AVAIL] Parsed query: {parse_result}")
                    
                    start_date_str = parse_result.get('start_date')
                    end_date_str = parse_result.get('end_date')
                    time_filter = parse_result.get('time_filter')
                    specific_days = parse_result.get('specific_days')
                    
                    # Parse dates
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else today
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else start_date + timedelta(days=14)
                    
                except Exception as e:
                    logger.warning(f"[SEARCH_AVAIL] Failed to parse query, using defaults: {e}")
                    
                    # Smart fallback: detect "other/different/more" queries and search BEYOND initial dates
                    wants_different = any(word in query_lower for word in ['other', 'different', 'else', 'more', 'another', 'alternative'])
                    
                    if wants_different:
                        # User wants different dates than already shown - search 2-4 weeks out
                        start_date = today + timedelta(days=14)  # Start AFTER the initial 2-week window
                        end_date = today + timedelta(days=35)    # Search 3-5 weeks out
                        logger.info(f"[SEARCH_AVAIL] User wants different dates - searching {start_date.date()} to {end_date.date()}")
                    else:
                        start_date = today
                        end_date = today + timedelta(days=14)
                    
                    time_filter = None
                    specific_days = None
            
            # Get business config
            try:
                business_days = config.get_business_days_indices()
            except:
                business_days = [0, 1, 2, 3, 4]
            
            try:
                business_hours = config.get_business_hours(company_id=company_id)
                biz_start_hour = business_hours.get('start', 9)
                biz_end_hour = business_hours.get('end', 17)
            except:
                biz_start_hour = 9
                biz_end_hour = 17
            
            has_workers = db.has_workers(company_id) if db else False
            
            # Search for availability
            from collections import defaultdict
            slots_by_day = defaultdict(list)
            current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_search = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Map day names to weekday indices for filtering
            day_name_to_idx = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
            specific_day_indices = None
            if specific_days:
                specific_day_indices = [day_name_to_idx.get(d.lower()) for d in specific_days if d.lower() in day_name_to_idx]
            
            while current_date <= end_search:
                # Check if this day matches filters
                if current_date.weekday() not in business_days:
                    current_date += timedelta(days=1)
                    continue
                
                if specific_day_indices and current_date.weekday() not in specific_day_indices:
                    current_date += timedelta(days=1)
                    continue
                
                day_slots = []
                now = datetime.now()
                
                if has_workers and db:
                    slot_time = current_date.replace(hour=biz_start_hour, minute=0, second=0, microsecond=0)
                    day_end = current_date.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
                    
                    while slot_time < day_end:
                        if slot_time <= now:
                            slot_time += timedelta(minutes=30)
                            continue
                        
                        # Apply time filter
                        if time_filter:
                            slot_hour = slot_time.hour
                            if time_filter == "morning" and slot_hour >= 12:
                                slot_time += timedelta(minutes=30)
                                continue
                            elif time_filter == "afternoon" and (slot_hour < 12 or slot_hour >= 17):
                                slot_time += timedelta(minutes=30)
                                continue
                            elif time_filter == "evening" and slot_hour < 17:
                                slot_time += timedelta(minutes=30)
                                continue
                            elif time_filter.startswith("after_"):
                                after_hour = int(time_filter.split("_")[1])
                                if slot_hour < after_hour:
                                    slot_time += timedelta(minutes=30)
                                    continue
                        
                        if service_duration >= 480:
                            slot_end = day_end
                        else:
                            slot_end = slot_time + timedelta(minutes=service_duration)
                        
                        if slot_end > day_end:
                            slot_time += timedelta(minutes=30)
                            continue
                        
                        available_workers = db.find_available_workers_for_slot(
                            appointment_time=slot_time,
                            duration_minutes=service_duration,
                            company_id=company_id
                        )
                        
                        if available_workers and worker_restrictions:
                            restriction_type = worker_restrictions.get('type', 'all')
                            restricted_ids = worker_restrictions.get('worker_ids', [])
                            if restriction_type == 'only' and restricted_ids:
                                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
                            elif restriction_type == 'except' and restricted_ids:
                                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
                        
                        if available_workers is None or len(available_workers) >= workers_required:
                            day_slots.append(slot_time)
                        
                        slot_time += timedelta(minutes=30)
                else:
                    try:
                        day_slots = google_calendar.get_available_slots_for_day(current_date, service_duration=service_duration)
                        # Apply time filter for calendar-based
                        if time_filter and day_slots:
                            filtered_slots = []
                            for slot in day_slots:
                                slot_hour = slot.hour
                                if time_filter == "morning" and slot_hour < 12:
                                    filtered_slots.append(slot)
                                elif time_filter == "afternoon" and 12 <= slot_hour < 17:
                                    filtered_slots.append(slot)
                                elif time_filter == "evening" and slot_hour >= 17:
                                    filtered_slots.append(slot)
                                elif time_filter.startswith("after_"):
                                    after_hour = int(time_filter.split("_")[1])
                                    if slot_hour >= after_hour:
                                        filtered_slots.append(slot)
                                elif not time_filter:
                                    filtered_slots.append(slot)
                            day_slots = filtered_slots
                    except:
                        day_slots = []
                
                if day_slots and is_full_day:
                    day_slots = [day_slots[0]]
                
                if day_slots:
                    day_key = current_date.strftime('%Y-%m-%d')
                    slots_by_day[day_key] = day_slots
                
                current_date += timedelta(days=1)
            
            if not slots_by_day:
                tool_duration = time_module.time() - tool_start_time
                print(f"[TOOL_TIMING] ✅ search_availability completed in {tool_duration:.3f}s (0 slots found)")
                
                # Provide helpful message based on what they asked for
                if time_filter:
                    filter_desc = {"morning": "morning", "afternoon": "afternoon", "evening": "evening"}.get(time_filter, f"after {time_filter.split('_')[1]}:00" if time_filter.startswith("after_") else "")
                    no_avail_msg = f"I don't have any {filter_desc} slots available in that time period. Would you like me to check other times?"
                elif specific_days:
                    no_avail_msg = f"I don't have availability on {' or '.join(specific_days)} in that period. Would you like to try different days?"
                else:
                    no_avail_msg = "I don't have any openings in that time period. Would you like me to check a different week?"
                
                return {
                    "success": True,
                    "available_slots": [],
                    "message": no_avail_msg,
                    "is_full_day_service": is_full_day
                }
            
            # Sort by date (chronological for search results)
            sorted_day_keys = sorted(slots_by_day.keys())
            
            # Build summaries - show up to 4 days
            day_summaries = []
            for day_key in sorted_day_keys[:4]:
                day_slots = slots_by_day[day_key]
                day_date = datetime.strptime(day_key, '%Y-%m-%d')
                day_name = day_date.strftime('%A')
                day_num = day_date.day
                suffix = 'th' if 11 <= day_num <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day_num % 10, 'th')
                day_with_date = f"{day_name} the {day_num}{suffix}"
                
                if is_full_day:
                    day_summaries.append(f"{day_with_date}: full day available")
                else:
                    first_time = day_slots[0].strftime('%I %p').lstrip('0').lower()
                    last_time = day_slots[-1].strftime('%I %p').lstrip('0').lower()
                    if len(day_slots) >= 4:
                        day_summaries.append(f"{day_with_date}: free from {first_time} to {last_time}")
                    elif len(day_slots) == 1:
                        day_summaries.append(f"{day_with_date}: {first_time} only")
                    else:
                        times = [s.strftime('%I %p').lstrip('0').lower() for s in day_slots[:3]]
                        day_summaries.append(f"{day_with_date}: {' or '.join(times)}")
            
            natural_summary = naturalize_availability_summary(day_summaries, is_full_day=is_full_day)
            
            # Build structured data
            all_slots = []
            for day_slots in slots_by_day.values():
                all_slots.extend(day_slots)
            
            formatted_slots = []
            for slot in all_slots[:20]:
                formatted_slots.append({
                    "date": slot.strftime('%A, %B %d, %Y'),
                    "time": slot.strftime('%I:%M %p'),
                    "iso": slot.isoformat()
                })
            
            tool_duration = time_module.time() - tool_start_time
            print(f"[TOOL_TIMING] ✅ search_availability completed in {tool_duration:.3f}s ({len(all_slots)} slots found)")
            
            if is_full_day:
                voice_instruction = "Present these days naturally. For full-day jobs, ask which DAY works - don't mention times."
            else:
                voice_instruction = "Present these options naturally and ask which works for them."
            
            return {
                "success": True,
                "available_slots": formatted_slots,
                "total_count": len(all_slots),
                "natural_summary": natural_summary,
                "message": natural_summary,
                "voice_instruction": voice_instruction,
                "is_full_day_service": is_full_day,
                "days_found": len(slots_by_day)
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
                    # Try by name, phone, or email - MUST filter by company_id for data isolation
                    clients = db.get_clients_by_name(customer_name.lower(), company_id=company_id)
                    if len(clients) == 1:
                        client = clients[0]
                        
                        # Get address - prioritize client's stored address, fall back to last booking
                        last_address = client.get('address') or client.get('eircode')
                        if not last_address:
                            # Fall back to most recent booking address
                            bookings = db.get_client_bookings(client['id'], company_id=company_id)
                            if bookings:
                                for booking in bookings:
                                    if booking.get('address') or booking.get('eircode'):
                                        last_address = booking.get('address') or booking.get('eircode')
                                        break
                        
                        # Build the message with all available info and address confirmation
                        msg_parts = [f"Found returning customer: {client['name']}"]
                        if client.get('phone'):
                            msg_parts.append(f"phone {client.get('phone')}")
                        if client.get('email'):
                            msg_parts.append(f"email {client.get('email')}")
                        
                        # Create address confirmation message using validator
                        address_confirmation_msg = None
                        if last_address:
                            from src.utils.address_validator import enhance_customer_address_lookup
                            enhanced_data = enhance_customer_address_lookup(client, "")
                            if enhanced_data.get('address_confirmation_needed'):
                                address_confirmation_msg = enhanced_data['suggested_response']
                            msg_parts.append(f"last address {last_address}")
                        
                        tool_duration = time_module.time() - tool_start_time
                        print(f"[TOOL_TIMING] ✅ lookup_customer completed in {tool_duration:.3f}s (returning customer)")
                        
                        return {
                            "success": True,
                            "customer_exists": True,
                            "customer_info": {
                                "id": client['id'],
                                "name": client['name'],
                                "phone": client.get('phone'),
                                "email": client.get('email'),
                                "last_address": last_address,
                                "address_confirmation_prompt": address_confirmation_msg
                            },
                            "message": ", ".join(msg_parts),
                            "address_prompt": address_confirmation_msg
                        }
                    elif len(clients) > 1:
                        # Multiple customers with same name - try to match by phone or email
                        logger.info(f"[LOOKUP] Multiple customers ({len(clients)}) found with name: {customer_name}")
                        
                        # Try to narrow down by phone number if provided
                        if phone:
                            normalized_phone = normalize_phone_for_comparison(phone)
                            phone_matches = [c for c in clients if normalize_phone_for_comparison(c.get('phone') or '') == normalized_phone]
                            if len(phone_matches) == 1:
                                client = phone_matches[0]
                                logger.info(f"[LOOKUP] Matched by name + phone: {client['name']} (ID: {client['id']})")
                                # Get address - prioritize client's stored address, fall back to last booking
                                last_address = client.get('address') or client.get('eircode')
                                if not last_address:
                                    bookings = db.get_client_bookings(client['id'], company_id=company_id)
                                    if bookings:
                                        for booking in bookings:
                                            if booking.get('address') or booking.get('eircode'):
                                                last_address = booking.get('address') or booking.get('eircode')
                                                break
                                
                                msg_parts = [f"Found returning customer: {client['name']}"]
                                if client.get('phone'):
                                    msg_parts.append(f"phone {client.get('phone')}")
                                if client.get('email'):
                                    msg_parts.append(f"email {client.get('email')}")
                                if last_address:
                                    msg_parts.append(f"last address {last_address}")
                                
                                return {
                                    "success": True,
                                    "customer_exists": True,
                                    "customer_info": {
                                        "id": client['id'],
                                        "name": client['name'],
                                        "phone": client.get('phone'),
                                        "email": client.get('email'),
                                        "last_address": last_address
                                    },
                                    "message": ", ".join(msg_parts)
                                }
                            elif len(phone_matches) == 0:
                                # Phone provided but doesn't match any existing customer - treat as new
                                logger.info(f"[LOOKUP] Name matched {len(clients)} customers but phone doesn't match any - treating as NEW customer")
                                return {
                                    "success": True,
                                    "customer_exists": False,
                                    "message": f"No existing customer found for {customer_name} with that phone number. This is a new customer."
                                }
                        
                        # Try to narrow down by email if provided
                        if email:
                            email_matches = [c for c in clients if c.get('email') and c.get('email').lower() == email.lower()]
                            if len(email_matches) == 1:
                                client = email_matches[0]
                                logger.info(f"[LOOKUP] Matched by name + email: {client['name']} (ID: {client['id']})")
                                # Get address - prioritize client's stored address, fall back to last booking
                                last_address = client.get('address') or client.get('eircode')
                                if not last_address:
                                    bookings = db.get_client_bookings(client['id'], company_id=company_id)
                                    if bookings:
                                        for booking in bookings:
                                            if booking.get('address') or booking.get('eircode'):
                                                last_address = booking.get('address') or booking.get('eircode')
                                                break
                                
                                msg_parts = [f"Found returning customer: {client['name']}"]
                                if client.get('phone'):
                                    msg_parts.append(f"phone {client.get('phone')}")
                                if client.get('email'):
                                    msg_parts.append(f"email {client.get('email')}")
                                if last_address:
                                    msg_parts.append(f"last address {last_address}")
                                
                                return {
                                    "success": True,
                                    "customer_exists": True,
                                    "customer_info": {
                                        "id": client['id'],
                                        "name": client['name'],
                                        "phone": client.get('phone'),
                                        "email": client.get('email'),
                                        "last_address": last_address
                                    },
                                    "message": ", ".join(msg_parts)
                                }
                            elif len(email_matches) == 0:
                                # Email provided but doesn't match any existing customer - treat as new
                                logger.info(f"[LOOKUP] Name matched {len(clients)} customers but email doesn't match any - treating as NEW customer")
                                return {
                                    "success": True,
                                    "customer_exists": False,
                                    "message": f"No existing customer found for {customer_name} with that email. This is a new customer."
                                }
                        
                        # No phone or email provided - ask for phone to confirm
                        return {
                            "success": True,
                            "customer_exists": True,
                            "multiple_matches": True,
                            "count": len(clients),
                            "message": f"Found {len(clients)} customers named {customer_name}. Need phone or email to confirm which one."
                        }
                    else:
                        # FUZZY MATCH: Try phonetically similar names (for ASR errors)
                        # MUST filter by company_id for data isolation
                        from difflib import SequenceMatcher
                        all_clients = db.get_all_clients(company_id=company_id)
                        
                        best_match = None
                        best_similarity = 0
                        best_match_reason = ""
                        
                        # Helper to split name into first/last
                        def split_name(name):
                            parts = name.strip().split()
                            if len(parts) >= 2:
                                return parts[0].lower(), ' '.join(parts[1:]).lower()
                            return name.lower(), ""
                        
                        search_first, search_last = split_name(customer_name)
                        
                        for potential_client in all_clients:
                            client_first, client_last = split_name(potential_client['name'])
                            
                            # Full name similarity
                            full_similarity = SequenceMatcher(None, 
                                customer_name.lower(), 
                                potential_client['name'].lower()).ratio()
                            
                            # First name similarity (important for identity)
                            first_similarity = SequenceMatcher(None, search_first, client_first).ratio()
                            
                            # Last name similarity (often has ASR errors like Dorothy/Doherty)
                            last_similarity = SequenceMatcher(None, search_last, client_last).ratio() if search_last and client_last else 0
                            
                            # Check if phone matches
                            phone_matches = False
                            if phone and potential_client.get('phone'):
                                norm_phone = ''.join(filter(str.isdigit, phone))[-10:]
                                norm_client_phone = ''.join(filter(str.isdigit, potential_client.get('phone', '')))[-10:]
                                phone_matches = norm_phone == norm_client_phone
                            
                            # Matching logic with multiple strategies:
                            match_score = 0
                            match_reason = ""
                            
                            # Strategy 1: Phone matches + first name exact/close + last name reasonable
                            # Catches: "James Dorothy" vs "James Doherty" (ASR error on last name)
                            if phone_matches and first_similarity >= 0.90 and last_similarity >= 0.65:
                                match_score = 0.95 + (last_similarity * 0.05)  # High confidence
                                match_reason = f"phone+first_name (first:{first_similarity:.0%}, last:{last_similarity:.0%})"
                            
                            # Strategy 2: Phone matches + full name 85%+ similar
                            # Catches: minor ASR errors across the name
                            # Note: 85% threshold prevents "Joe Smith" matching "John Smith" (84%)
                            elif phone_matches and full_similarity >= 0.85:
                                match_score = full_similarity + 0.10  # Boost for phone match
                                match_reason = f"phone+name (full:{full_similarity:.0%})"
                            
                            # Strategy 3: No phone but very high name similarity (92%+)
                            # Catches: "Jon Smith" vs "John Smith" without phone
                            elif full_similarity >= 0.92:
                                match_score = full_similarity
                                match_reason = f"name_only (full:{full_similarity:.0%})"
                            
                            if match_score > best_similarity:
                                best_similarity = match_score
                                best_match = potential_client
                                best_match_reason = match_reason
                        
                        logger.info(f"[LOOKUP] Search: '{customer_name}', phone: {phone}, best_match: {best_match['name'] if best_match else 'None'}, score: {best_similarity:.2%}, reason: {best_match_reason}")
                        
                        if best_match:
                            logger.info(f"[LOOKUP] ✅ Fuzzy match: '{customer_name}' -> '{best_match['name']}' ({best_match_reason})")
                            # Get address - prioritize client's stored address, fall back to last booking
                            last_address = best_match.get('address') or best_match.get('eircode')
                            if not last_address:
                                bookings = db.get_client_bookings(best_match['id'], company_id=company_id)
                                if bookings:
                                    for booking in bookings:
                                        if booking.get('address') or booking.get('eircode'):
                                            last_address = booking.get('address') or booking.get('eircode')
                                            break
                            
                            # Build the message with all available info
                            msg_parts = [f"Found returning customer: {best_match['name']} (I heard {customer_name}, but found a close match)"]
                            if best_match.get('phone'):
                                msg_parts.append(f"phone {best_match.get('phone')}")
                            if best_match.get('email'):
                                msg_parts.append(f"email {best_match.get('email')}")
                            if last_address:
                                msg_parts.append(f"last address {last_address}")
                            
                            return {
                                "success": True,
                                "customer_exists": True,
                                "fuzzy_match": True,
                                "heard_name": customer_name,
                                "actual_name": best_match['name'],
                                "customer_info": {
                                    "id": best_match['id'],
                                    "name": best_match['name'],
                                    "phone": best_match.get('phone'),
                                    "email": best_match.get('email'),
                                    "last_address": last_address
                                },
                                "message": ", ".join(msg_parts)
                            }
                        
                        tool_duration = time_module.time() - tool_start_time
                        print(f"[TOOL_TIMING] ✅ lookup_customer completed in {tool_duration:.3f}s (new customer)")
                        
                        return {
                            "success": True,
                            "customer_exists": False,
                            "customer_info": {
                                "name": customer_name,
                                "phone": phone  # Pass through caller's phone for new customers
                            },
                            "message": f"No existing customer found for {customer_name}. This is a new customer."
                        }
                except Exception as e:
                    tool_duration = time_module.time() - tool_start_time
                    print(f"[TOOL_TIMING] ❌ lookup_customer failed after {tool_duration:.3f}s: {e}")
                    logger.error(f" Error looking up customer: {e}")
                    return {
                        "success": False,
                        "error": f"Database error: {str(e)}"
                    }
            
            tool_duration = time_module.time() - tool_start_time
            print(f"[TOOL_TIMING] ⚠️ lookup_customer - no DB after {tool_duration:.3f}s")
            return {
                "success": False,
                "error": "Database not available"
            }
        
        elif tool_name == "book_appointment":
            logger.info(f"[BOOK_APPT] ========== BOOKING APPOINTMENT ==========")
            customer_name = arguments.get('customer_name')
            email = arguments.get('email')
            phone = arguments.get('phone')
            appointment_datetime = arguments.get('appointment_datetime')
            reason = arguments.get('reason', 'General appointment')
            
            logger.info(f"[BOOK_APPT] Customer: {customer_name}, Phone: {phone}, Email: {email}")
            logger.info(f"[BOOK_APPT] DateTime: {appointment_datetime}, Reason: {reason}")
            
            # Clean phone number if it's placeholder text
            if phone and ('calling from' in phone.lower() or 'number you' in phone.lower()):
                logger.info(f"[BOOK_APPT] Cleaning placeholder phone: {phone}")
                phone = None  # Will get from caller_phone or ask again
            
            if not customer_name:
                logger.warning(f"[BOOK_APPT] Missing customer name")
                return {
                    "success": False,
                    "error": "Customer name is required"
                }
            
            if not appointment_datetime:
                logger.warning(f"[BOOK_APPT] Missing appointment datetime")
                return {
                    "success": False,
                    "error": "Appointment date and time are required. Please ask the customer for a specific date and time.",
                    "needs_clarification": "datetime"
                }
            
            # Check for vague time requests
            vague_time_phrases = ["within", "asap", "as soon as possible", "urgently", "quickly", "soon"]
            if any(phrase in appointment_datetime.lower() for phrase in vague_time_phrases):
                logger.warning(f"[BOOK_APPT] Vague time detected: {appointment_datetime}")
                return {
                    "success": False,
                    "error": f"The time '{appointment_datetime}' is not specific enough. Please check availability and suggest the next available time slot to the customer.",
                    "needs_clarification": "datetime",
                    "is_urgent": True
                }
            
            # Parse the appointment time
            logger.info(f"[BOOK_APPT] Parsing datetime: {appointment_datetime}")
            parsed_time = parse_datetime(appointment_datetime)
            if not parsed_time:
                logger.error(f"[BOOK_APPT] Failed to parse datetime: {appointment_datetime}")
                return {
                    "success": False,
                    "error": f"Could not parse date/time: '{appointment_datetime}'. Please ask the customer for a specific date and time (e.g., 'tomorrow at 2pm', 'Monday at 9am').",
                    "needs_clarification": "datetime"
                }
            logger.info(f"[BOOK_APPT] Parsed time: {parsed_time}")
            
            # CRITICAL: Validate day of week if the input contains a weekday name
            # This prevents the LLM from booking the wrong day (e.g., booking Thursday when user said Monday)
            weekday_names = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            input_lower = appointment_datetime.lower()
            mentioned_weekday = None
            for day_name, day_num in weekday_names.items():
                if day_name in input_lower:
                    mentioned_weekday = (day_name, day_num)
                    break
            
            if mentioned_weekday:
                day_name, expected_weekday = mentioned_weekday
                actual_weekday = parsed_time.weekday()
                if actual_weekday != expected_weekday:
                    actual_day_name = parsed_time.strftime('%A')
                    logger.error(f"[BOOK_APPT] DAY MISMATCH: User said '{day_name}' but parsed date {parsed_time.strftime('%Y-%m-%d')} is {actual_day_name}")
                    return {
                        "success": False,
                        "error": f"There's a date mismatch - you mentioned {day_name.capitalize()} but the date provided ({parsed_time.strftime('%B %d')}) is actually a {actual_day_name}. Please use check_availability to find the correct date for {day_name.capitalize()} and try again.",
                        "needs_clarification": "datetime",
                        "expected_day": day_name.capitalize(),
                        "actual_day": actual_day_name
                    }
                logger.info(f"[BOOK_APPT] Day of week validated: {day_name} matches {parsed_time.strftime('%A')}")
            
            # Validate business hours - MUST pass company_id for correct company-specific hours
            from src.utils.config import Config
            business_hours = Config.get_business_hours(company_id=company_id)
            requested_hour = parsed_time.hour
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
            
            logger.info(f"[BOOK_APPT] Business hours: {start_hour}:00 - {end_hour}:00, Requested hour: {requested_hour}")
            
            if requested_hour < start_hour or requested_hour >= end_hour:
                logger.warning(f"[BOOK_APPT] Outside business hours: {requested_hour}")
                # Generate user-friendly message based on whether time is before or after hours
                if requested_hour < start_hour:
                    time_msg = f"We don't open until {start_hour}:00 AM"
                else:
                    # Convert to 12-hour format for end time
                    end_hour_12 = end_hour if end_hour <= 12 else end_hour - 12
                    end_period = "AM" if end_hour < 12 else "PM"
                    time_msg = f"We close at {end_hour_12}:00 {end_period}"
                
                # Format business hours for display
                end_display = end_hour if end_hour <= 12 else end_hour - 12
                end_display_period = "AM" if end_hour < 12 else "PM"
                
                return {
                    "success": False,
                    "error": f"{time_msg}. Please check availability using check_availability and suggest a time within business hours ({start_hour}:00 AM - {end_display}:00 {end_display_period}).",
                    "needs_clarification": "datetime"
                }
            
            # Get service duration based on reason/service type
            logger.info(f"[BOOK_APPT] Matching service for reason: {reason}")
            match_result = match_service(reason, company_id=company_id)
            matched_service_name = match_result['matched_name']
            appointment_duration = match_result['service'].get('duration_minutes', 60)
            workers_required = match_result['service'].get('workers_required', 1) or 1
            worker_restrictions = match_result['service'].get('worker_restrictions')
            logger.info(f"[BOOK_APPT] Matched service: {matched_service_name}, Duration: {appointment_duration} mins, Workers: {workers_required}")
            
            # Check if company has workers configured
            has_workers = db.has_workers(company_id) if db else False
            assigned_workers = []
            
            # AVAILABILITY CHECK: Different logic depending on whether company has workers
            if has_workers:
                # Worker-based availability: check if any qualified worker is free
                logger.info(f"[BOOK_APPT] Checking WORKER availability at {parsed_time} for {appointment_duration} mins")
                available_workers = db.find_available_workers_for_slot(
                    appointment_time=parsed_time,
                    duration_minutes=appointment_duration,
                    company_id=company_id
                )
                
                # Apply worker restrictions if any
                if available_workers and worker_restrictions:
                    restriction_type = worker_restrictions.get('type', 'all')
                    restricted_ids = worker_restrictions.get('worker_ids', [])
                    
                    if restriction_type == 'only' and restricted_ids:
                        available_workers = [w for w in available_workers if w['id'] in restricted_ids]
                    elif restriction_type == 'except' and restricted_ids:
                        available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
                
                logger.info(f"[BOOK_APPT] Available workers: {available_workers}")
                
                if available_workers is None:
                    logger.warning(f"[BOOK_APPT] Worker lookup failed - proceeding without worker assignment")
                elif len(available_workers) < workers_required:
                    logger.warning(f"[BOOK_APPT] Not enough workers: need {workers_required}, have {len(available_workers)}")
                    return {
                        "success": False,
                        "error": f"No workers are available at {parsed_time.strftime('%I:%M %p on %A, %B %d')}. Please check availability and suggest another time."
                    }
                else:
                    assigned_workers = available_workers[:workers_required]
                    logger.info(f"[BOOK_APPT] Auto-assigning worker(s): {[w['name'] for w in assigned_workers]}")
            else:
                # No workers - use simple calendar availability check
                logger.info(f"[BOOK_APPT] Checking CALENDAR availability at {parsed_time} for {appointment_duration} mins")
                is_available = google_calendar.check_availability(parsed_time, duration_minutes=appointment_duration)
                logger.info(f"[BOOK_APPT] Availability check result: {is_available}")
                
                if not is_available:
                    logger.warning(f"[BOOK_APPT] Time slot not available")
                    return {
                        "success": False,
                        "error": f"That time slot is already booked or doesn't have enough time for this appointment ({appointment_duration} mins). Please check availability and suggest another time."
                    }
            
            # Create calendar event with correct duration
            summary = f"{matched_service_name} - {customer_name}"
            logger.info(f"[BOOK_APPT] Creating calendar event: {summary}")
            
            try:
                event = google_calendar.book_appointment(
                    summary=summary,
                    start_time=parsed_time,
                    duration_minutes=appointment_duration,
                    description=f"Booked via AI receptionist\nCustomer: {customer_name}\nService: {matched_service_name}\nCustomer Request: {reason}\nPhone: {phone}\nEmail: {email}\nDuration: {appointment_duration} mins",
                    phone_number=phone
                )
                logger.info(f"[BOOK_APPT] Calendar event created: {event}")
            except Exception as cal_error:
                logger.error(f"[BOOK_APPT] Calendar event creation failed: {cal_error}")
                import traceback
                traceback.print_exc()
                return {
                    "success": False,
                    "error": f"Failed to create calendar event: {str(cal_error)}"
                }
            
            if not event:
                logger.error(f"[BOOK_APPT] Calendar returned None for event")
                return {
                    "success": False,
                    "error": "Failed to create calendar event"
                }
                return {
                    "success": False,
                    "error": "Failed to create calendar event"
                }
            
            # Save to database
            if db:
                logger.info(f"[BOOK_APPT] Saving to database...")
                try:
                    # Find or create client - MUST pass company_id for data isolation
                    logger.info(f"[BOOK_APPT] Finding/creating client: {customer_name}, phone={phone}, email={email}")
                    client_id = db.find_or_create_client(
                        name=customer_name,
                        phone=phone,
                        email=email,
                        date_of_birth=None,
                        company_id=company_id
                    )
                    logger.info(f"[BOOK_APPT] Client ID: {client_id}")
                    
                    # Add booking - MUST pass company_id for data isolation
                    logger.info(f"[BOOK_APPT] Adding booking to database...")
                    booking_id = db.add_booking(
                        client_id=client_id,
                        calendar_event_id=event.get('id'),
                        appointment_time=parsed_time,
                        service_type=matched_service_name,
                        phone_number=phone,
                        email=email,
                        company_id=company_id,
                        duration_minutes=appointment_duration
                    )
                    logger.info(f"[BOOK_APPT] Booking ID: {booking_id}")
                    
                    # Add note with original customer request
                    db.add_appointment_note(booking_id, f"Booked via AI receptionist.\nService: {matched_service_name}\nCustomer Request: {reason}\nDuration: {appointment_duration} mins", created_by="system")
                    
                    # Auto-assign workers if any were selected
                    if assigned_workers:
                        for worker in assigned_workers:
                            try:
                                logger.info(f"[BOOK_APPT] Assigning worker {worker['name']} to booking {booking_id}")
                                assignment_result = db.assign_worker_to_job(booking_id, worker['id'])
                                if assignment_result.get('success'):
                                    logger.info(f"[BOOK_APPT] ✅ Worker {worker['name']} assigned successfully")
                                else:
                                    logger.warning(f"[BOOK_APPT] ⚠️ Failed to assign worker {worker['name']}: {assignment_result.get('error')}")
                            except Exception as worker_err:
                                logger.warning(f"[BOOK_APPT] ⚠️ Could not assign worker {worker['name']}: {worker_err}")
                    
                    # Update client description
                    try:
                        from src.services.client_description_generator import update_client_description
                        update_client_description(client_id)
                    except Exception:
                        pass
                    
                    logger.info(f"[BOOK_APPT] ✅ Booking saved to database (ID: {booking_id}, company_id: {company_id}, duration: {appointment_duration} mins)")
                except Exception as e:
                    logger.error(f"[BOOK_APPT] ❌ Database save failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                logger.warning(f"[BOOK_APPT] No database available - booking not saved to DB")
            
            logger.info(f"[BOOK_APPT] ========== BOOKING COMPLETE ==========")
            return {
                "success": True,
                "message": f"Appointment booked for {customer_name} on {parsed_time.strftime('%A, %B %d at %I:%M %p')} ({format_duration(appointment_duration)})",
                "appointment_details": {
                    "customer": customer_name,
                    "time": parsed_time.strftime('%A, %B %d at %I:%M %p'),
                    "duration_minutes": appointment_duration,
                    "duration_display": format_duration(appointment_duration),
                    "service": matched_service_name,
                    "reason": reason,
                    "phone": phone,
                    "email": email
                }
            }
        
        elif tool_name == "cancel_appointment":
            # New day-based lookup with fuzzy name matching
            appointment_date = arguments.get('appointment_date') or arguments.get('appointment_datetime')
            customer_name = arguments.get('customer_name')
            
            if not appointment_date:
                return {
                    "success": False,
                    "error": "Please ask the customer what day their booking is for."
                }
            
            # Parse the date (we only care about the day, not time)
            # Use require_time=False since we're doing day-based lookup
            parsed_date = parse_datetime(appointment_date, require_time=False, default_time=(9, 0))
            if not parsed_date:
                return {
                    "success": False,
                    "error": f"Could not understand the date: '{appointment_date}'. Please ask for a clearer date like 'Monday' or 'January 15th'."
                }
            
            # Find all jobs on that day
            jobs_on_day = find_jobs_on_day(parsed_date, db, company_id, google_calendar)
            
            if not jobs_on_day:
                return {
                    "success": False,
                    "error": f"No bookings found on {parsed_date.strftime('%A, %B %d')}. Please verify the date with the customer."
                }
            
            # If no customer name provided, return list of names for confirmation
            if not customer_name:
                # Build list of names with job info
                names_list = []
                for job in jobs_on_day:
                    name = job.get('name', 'Unknown')
                    time_str = job.get('time', '')
                    service = job.get('service', '')
                    if job.get('is_full_day'):
                        names_list.append(f"{name} (full day - {service})")
                    else:
                        names_list.append(f"{name} ({time_str} - {service})")
                
                # Format for AI to read out
                if len(jobs_on_day) == 1:
                    return {
                        "success": False,
                        "requires_confirmation": True,
                        "jobs_on_day": jobs_on_day,
                        "customer_names": [j['name'] for j in jobs_on_day],
                        "appointment_date": parsed_date.strftime('%A, %B %d'),
                        "message": f"I have one booking on {parsed_date.strftime('%A, %B %d')} for {names_list[0]}. Is that your booking?"
                    }
                else:
                    names_formatted = ", ".join(names_list[:-1]) + f", and {names_list[-1]}" if len(names_list) > 1 else names_list[0]
                    return {
                        "success": False,
                        "requires_confirmation": True,
                        "jobs_on_day": jobs_on_day,
                        "customer_names": [j['name'] for j in jobs_on_day],
                        "appointment_date": parsed_date.strftime('%A, %B %d'),
                        "message": f"I have {len(jobs_on_day)} bookings on {parsed_date.strftime('%A, %B %d')}: {names_formatted}. Which name is yours?"
                    }
            
            # Customer name provided - use fuzzy matching to find the right job
            candidate_names = [j['name'] for j in jobs_on_day]
            matched_name, confidence, matched_idx = fuzzy_match_name(customer_name, candidate_names)
            
            if confidence < 50 or matched_idx < 0:
                return {
                    "success": False,
                    "error": f"I couldn't find a booking for '{customer_name}' on {parsed_date.strftime('%A, %B %d')}. The bookings I have are for: {', '.join(candidate_names)}. Can you confirm which one is yours?"
                }
            
            matched_job = jobs_on_day[matched_idx]
            logger.info(f"[CANCEL] Fuzzy matched '{customer_name}' to '{matched_name}' with {confidence}% confidence")
            
            # Proceed with cancellation
            event_id = matched_job.get('event_id')
            booking_id = matched_job.get('booking_id')
            
            # Cancel in Google Calendar if event_id exists
            if event_id and google_calendar:
                try:
                    google_calendar.cancel_appointment(event_id)
                except Exception as e:
                    logger.warning(f"[CANCEL] Could not cancel in Google Calendar: {e}")
            
            # Delete from database
            if booking_id and db:
                try:
                    db.delete_booking(booking_id, company_id=company_id)
                    logger.info(f"[CANCEL] Deleted booking {booking_id} from database")
                except Exception as e:
                    logger.error(f"[CANCEL] Failed to delete booking from database: {e}")
            
            time_info = matched_job.get('time', '')
            if matched_job.get('is_full_day'):
                return {
                    "success": True,
                    "message": f"Successfully cancelled the full-day booking for {matched_name} on {parsed_date.strftime('%A, %B %d')}."
                }
            else:
                return {
                    "success": True,
                    "message": f"Successfully cancelled the booking for {matched_name} at {time_info} on {parsed_date.strftime('%A, %B %d')}."
                }
        
        elif tool_name == "reschedule_appointment":
            # New day-based lookup with fuzzy name matching
            current_date = arguments.get('current_date') or arguments.get('current_datetime')
            new_datetime = arguments.get('new_datetime')
            customer_name = arguments.get('customer_name')
            
            if not current_date:
                return {
                    "success": False,
                    "error": "Please ask the customer what day their current booking is for."
                }
            
            # Parse the date (we only care about the day, not time)
            # Use require_time=False since we're doing day-based lookup
            parsed_date = parse_datetime(current_date, require_time=False, default_time=(9, 0))
            if not parsed_date:
                return {
                    "success": False,
                    "error": f"Could not understand the date: '{current_date}'. Please ask for a clearer date like 'Monday' or 'January 15th'."
                }
            
            # Find all jobs on that day
            jobs_on_day = find_jobs_on_day(parsed_date, db, company_id, google_calendar)
            
            if not jobs_on_day:
                return {
                    "success": False,
                    "error": f"No bookings found on {parsed_date.strftime('%A, %B %d')}. Please verify the date with the customer."
                }
            
            # If no customer name provided, return list of names for confirmation
            if not customer_name:
                # Build list of names with job info
                names_list = []
                for job in jobs_on_day:
                    name = job.get('name', 'Unknown')
                    time_str = job.get('time', '')
                    service = job.get('service', '')
                    if job.get('is_full_day'):
                        names_list.append(f"{name} (full day - {service})")
                    else:
                        names_list.append(f"{name} ({time_str} - {service})")
                
                # Format for AI to read out
                if len(jobs_on_day) == 1:
                    return {
                        "success": False,
                        "requires_confirmation": True,
                        "jobs_on_day": jobs_on_day,
                        "customer_names": [j['name'] for j in jobs_on_day],
                        "appointment_date": parsed_date.strftime('%A, %B %d'),
                        "message": f"I have one booking on {parsed_date.strftime('%A, %B %d')} for {names_list[0]}. Is that your booking?"
                    }
                else:
                    names_formatted = ", ".join(names_list[:-1]) + f", and {names_list[-1]}" if len(names_list) > 1 else names_list[0]
                    return {
                        "success": False,
                        "requires_confirmation": True,
                        "jobs_on_day": jobs_on_day,
                        "customer_names": [j['name'] for j in jobs_on_day],
                        "appointment_date": parsed_date.strftime('%A, %B %d'),
                        "message": f"I have {len(jobs_on_day)} bookings on {parsed_date.strftime('%A, %B %d')}: {names_formatted}. Which name is yours?"
                    }
            
            # Customer name provided - use fuzzy matching to find the right job
            candidate_names = [j['name'] for j in jobs_on_day]
            matched_name, confidence, matched_idx = fuzzy_match_name(customer_name, candidate_names)
            
            if confidence < 50 or matched_idx < 0:
                return {
                    "success": False,
                    "error": f"I couldn't find a booking for '{customer_name}' on {parsed_date.strftime('%A, %B %d')}. The bookings I have are for: {', '.join(candidate_names)}. Can you confirm which one is yours?"
                }
            
            matched_job = jobs_on_day[matched_idx]
            logger.info(f"[RESCHEDULE] Fuzzy matched '{customer_name}' to '{matched_name}' with {confidence}% confidence")
            
            # Customer name confirmed but no new time yet - find available days for the assigned worker
            if not new_datetime:
                # Get booking details to find assigned workers
                booking_id = matched_job.get('booking_id')
                booking_duration = matched_job.get('duration_minutes', 60)
                assigned_worker_ids = []
                
                if booking_id and db:
                    try:
                        bookings = db.get_all_bookings(company_id=company_id)
                        for booking in bookings:
                            if booking.get('id') == booking_id:
                                assigned_worker_ids = booking.get('assigned_worker_ids', [])
                                break
                    except Exception as e:
                        logger.warning(f"[RESCHEDULE] Could not get assigned workers: {e}")
                
                # Find available days for the assigned worker(s)
                available_days = []
                if assigned_worker_ids and db:
                    available_days = _find_worker_available_days(
                        db=db,
                        worker_ids=assigned_worker_ids,
                        duration_minutes=booking_duration,
                        exclude_booking_id=booking_id,
                        company_id=company_id
                    )
                
                if available_days:
                    days_str = ", ".join(available_days[:5])  # Limit to 5 days
                    return {
                        "success": False,
                        "customer_name_confirmed": True,
                        "matched_name": matched_name,
                        "matched_job": matched_job,
                        "available_days": available_days,
                        "error": f"Got it, that's the booking for {matched_name}. I have availability on {days_str}. Which day works for you?"
                    }
                else:
                    return {
                        "success": False,
                        "customer_name_confirmed": True,
                        "matched_name": matched_name,
                        "matched_job": matched_job,
                        "error": f"Got it, that's the booking for {matched_name}. What day would you like to move it to?"
                    }
            
            # Get booking details first to check if it's a full-day job
            event_id = matched_job.get('event_id')
            booking_id = matched_job.get('booking_id')
            booking_duration = matched_job.get('duration_minutes', 60)
            is_full_day = matched_job.get('is_full_day', False)
            
            # Parse new time - allow date-only for full-day jobs
            # Use require_time=False and default to business start time
            new_time = parse_datetime(new_datetime, require_time=False, default_time=(9, 0))
            if not new_time:
                return {
                    "success": False,
                    "error": f"Could not understand the new date: '{new_datetime}'. Please ask for a clearer date like 'next Monday' or 'January 20th'."
                }
            
            # For full-day jobs, set time to start of business day
            if is_full_day:
                from src.utils.config import Config
                business_hours = Config.get_business_hours(company_id=company_id)
                start_hour = business_hours.get('start', 8)
                new_time = new_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                logger.info(f"[RESCHEDULE] Full-day job - setting time to {start_hour}:00")
            
            # Check if new time is available
            # Get assigned workers from the job
            assigned_worker_ids = []
            if booking_id and db:
                try:
                    bookings = db.get_all_bookings(company_id=company_id)
                    for booking in bookings:
                        if booking.get('id') == booking_id:
                            assigned_worker_ids = booking.get('assigned_worker_ids', [])
                            break
                except Exception as e:
                    logger.warning(f"[RESCHEDULE] Could not get assigned workers: {e}")
            
            has_workers = db.has_workers(company_id) if db else False
            
            if has_workers and assigned_worker_ids:
                # Check if the assigned workers are available at the new time
                logger.info(f"[RESCHEDULE] Checking if assigned workers {assigned_worker_ids} are available at {new_time}")
                all_workers_available = True
                unavailable_workers = []
                
                for worker_id in assigned_worker_ids:
                    availability = db.check_worker_availability(
                        worker_id=worker_id,
                        appointment_time=new_time,
                        duration_minutes=booking_duration,
                        exclude_booking_id=booking_id,
                        company_id=company_id
                    )
                    if not availability.get('available', False):
                        all_workers_available = False
                        worker = db.get_worker(worker_id, company_id=company_id)
                        worker_name = worker.get('name', f'Worker {worker_id}') if worker else f'Worker {worker_id}'
                        unavailable_workers.append(worker_name)
                
                if not all_workers_available:
                    # Find available days for the assigned worker(s) to suggest alternatives
                    available_days = _find_worker_available_days(
                        db=db,
                        worker_ids=assigned_worker_ids,
                        duration_minutes=booking_duration,
                        exclude_booking_id=booking_id,
                        company_id=company_id
                    )
                    
                    if available_days:
                        days_str = ", ".join(available_days[:5])  # Limit to 5 days
                        return {
                            "success": False,
                            "error": f"The assigned worker ({', '.join(unavailable_workers)}) is not available on {new_time.strftime('%A, %B %d')}. They are available on: {days_str}. Which day works for you?",
                            "new_time_unavailable": True,
                            "available_days": available_days
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"The assigned worker ({', '.join(unavailable_workers)}) is not available on {new_time.strftime('%A, %B %d')} and has no availability in the next 2 weeks. Would you like to speak with someone about this?",
                            "new_time_unavailable": True
                        }
            elif google_calendar:
                # No workers or no assigned workers - use simple calendar check
                is_available = google_calendar.check_availability(new_time, duration_minutes=booking_duration)
                if not is_available:
                    return {
                        "success": False,
                        "error": f"That day is already booked. Please suggest another available day.",
                        "new_time_unavailable": True
                    }
            
            # Reschedule in Google Calendar if event_id exists
            if event_id and google_calendar:
                try:
                    google_calendar.reschedule_appointment(event_id, new_time)
                except Exception as e:
                    logger.warning(f"[RESCHEDULE] Could not reschedule in Google Calendar: {e}")
            
            # Update database
            if booking_id and db:
                try:
                    db.update_booking(booking_id, company_id=company_id, appointment_time=new_time.strftime('%Y-%m-%d %H:%M:%S'))
                    logger.info(f"[RESCHEDULE] Updated booking {booking_id} to {new_time}")
                except Exception as e:
                    logger.error(f"[RESCHEDULE] Failed to update booking in database: {e}")
            
            if is_full_day:
                return {
                    "success": True,
                    "message": f"Successfully rescheduled the full-day booking for {matched_name} from {parsed_date.strftime('%A, %B %d')} to {new_time.strftime('%A, %B %d')}."
                }
            else:
                return {
                    "success": True,
                    "message": f"Successfully rescheduled the booking for {matched_name} to {new_time.strftime('%A, %B %d at %I:%M %p')}."
                }
        
        elif tool_name == "book_job":
            logger.info(f"[BOOK_JOB] ========== BOOKING JOB ==========")
            # Trades-specific booking with additional fields
            customer_name = arguments.get('customer_name')
            phone = arguments.get('phone')
            email = arguments.get('email')
            job_address = arguments.get('job_address')
            job_description = arguments.get('job_description')
            appointment_datetime = arguments.get('appointment_datetime')
            urgency_level = arguments.get('urgency_level', 'scheduled')
            property_type = arguments.get('property_type', 'residential')
            
            logger.info(f"[BOOK_JOB] Customer: {customer_name}, Phone: {phone}, Email: {email}")
            logger.info(f"[BOOK_JOB] Address: {job_address}, Description: {job_description}")
            logger.info(f"[BOOK_JOB] DateTime: {appointment_datetime}, Urgency: {urgency_level}, Property: {property_type}")
            
            # Validation
            if not customer_name:
                logger.warning(f"[BOOK_JOB] Missing customer name")
                return {
                    "success": False,
                    "error": "Customer name is required"
                }
            
            if not phone:
                logger.warning(f"[BOOK_JOB] Missing phone number")
                return {
                    "success": False,
                    "error": "Phone number is MANDATORY. Please ask the customer for their phone number.",
                    "needs_clarification": "phone"
                }
            
            # Check if email is required based on invoice delivery method
            # Email is no longer required - invoices sent via SMS
            # Keep the field optional for backwards compatibility
            
            if not job_address:
                logger.warning(f"[BOOK_JOB] Missing job address")
                return {
                    "success": False,
                    "error": "Job address is required. Please ask for the full address where the work will be performed.",
                    "needs_clarification": "job_address"
                }
            
            # Enhanced address validation and processing
            logger.info(f"[BOOK_JOB] Validating address: {job_address}")
            address_validator = AddressValidator()
            address_data = address_validator.parse_address_input(job_address)
            logger.info(f"[BOOK_JOB] Address validation result: {address_data}")
            
            # Check if address needs clarification
            if address_data['needs_clarification']:
                logger.warning(f"[BOOK_JOB] Address needs clarification: {address_data['suggestions']}")
                return {
                    "success": False,
                    "error": address_data['suggestions'][0] if address_data['suggestions'] else "Please provide a more complete address.",
                    "needs_clarification": "job_address",
                    "address_type": address_data['type']
                }
            
            # Extract and normalize eircode if present
            extracted_eircode = address_data.get('eircode')
            if extracted_eircode:
                logger.info(f"[BOOK_JOB] Extracted eircode: {extracted_eircode}")
            
            # Use validated and potentially enhanced address
            # If address type is 'eircode', don't duplicate it in the address field
            if address_data.get('type') == 'eircode':
                validated_address = None  # Eircode is stored separately
            else:
                validated_address = address_data['full_address']
            logger.info(f"[BOOK_JOB] Validated address: {validated_address}")
            
            if not job_description:
                logger.warning(f"[BOOK_JOB] Missing job description")
                return {
                    "success": False,
                    "error": "Job description is required. Please ask what needs to be done.",
                    "needs_clarification": "job_description"
                }
            
            if not appointment_datetime:
                logger.warning(f"[BOOK_JOB] Missing appointment datetime")
                return {
                    "success": False,
                    "error": "Appointment date and time are required. Please ask the customer for a specific date and time.",
                    "needs_clarification": "datetime"
                }
            
            # Check for vague time requests
            vague_time_phrases = ["within", "asap", "as soon as possible", "urgently", "quickly", "soon", "right away", "immediately"]
            if any(phrase in appointment_datetime.lower() for phrase in vague_time_phrases):
                logger.warning(f"[BOOK_JOB] Vague time detected: {appointment_datetime}")
                return {
                    "success": False,
                    "error": f"The time '{appointment_datetime}' is not specific enough. You must provide a SPECIFIC time. Please check availability using check_availability and suggest the next available time slot to the customer (e.g., 'I have 2pm available today').",
                    "needs_clarification": "datetime",
                    "is_urgent": True
                }
            
            # PRE-CHECK: For full-day services, auto-add start time if only day is provided
            # This prevents the "Could not parse date/time: 'Tuesday'" error for full-day jobs
            match_result_precheck = match_service(job_description, company_id=company_id)
            service_duration_precheck = match_result_precheck['service'].get('duration_minutes', 60)
            
            if service_duration_precheck >= 480:  # Full-day service (8+ hours)
                # Check if appointment_datetime is just a day name without time
                time_indicators = ['am', 'pm', ':', 'morning', 'afternoon', 'evening', 'noon', 'midnight']
                has_time = any(indicator in appointment_datetime.lower() for indicator in time_indicators)
                
                if not has_time:
                    # Get business hours start time
                    from src.utils.config import Config
                    business_hours_precheck = Config.get_business_hours(company_id=company_id)
                    start_hour_precheck = business_hours_precheck.get('start', 8)
                    
                    # Auto-add start time for full-day jobs
                    original_datetime = appointment_datetime
                    appointment_datetime = f"{appointment_datetime} at {start_hour_precheck}am"
                    logger.info(f"[BOOK_JOB] Full-day service detected - auto-added start time: '{original_datetime}' -> '{appointment_datetime}'")
            
            # Parse the appointment time
            logger.info(f"[BOOK_JOB] Parsing datetime: {appointment_datetime}")
            parsed_time = parse_datetime(appointment_datetime)
            if not parsed_time:
                logger.error(f"[BOOK_JOB] Failed to parse datetime: {appointment_datetime}")
                return {
                    "success": False,
                    "error": f"Could not parse date/time: '{appointment_datetime}'. Please ask the customer for a specific date and time (e.g., 'tomorrow at 2pm', 'Monday at 9am').",
                    "needs_clarification": "datetime"
                }
            logger.info(f"[BOOK_JOB] Parsed time: {parsed_time}")
            
            # CRITICAL: Validate day of week if the input contains a weekday name
            # This prevents the LLM from booking the wrong day (e.g., booking Thursday when user said Monday)
            weekday_names = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            input_lower = appointment_datetime.lower()
            mentioned_weekday = None
            for day_name, day_num in weekday_names.items():
                if day_name in input_lower:
                    mentioned_weekday = (day_name, day_num)
                    break
            
            if mentioned_weekday:
                day_name, expected_weekday = mentioned_weekday
                actual_weekday = parsed_time.weekday()
                if actual_weekday != expected_weekday:
                    actual_day_name = parsed_time.strftime('%A')
                    logger.error(f"[BOOK_JOB] DAY MISMATCH: User said '{day_name}' but parsed date {parsed_time.strftime('%Y-%m-%d')} is {actual_day_name}")
                    return {
                        "success": False,
                        "error": f"There's a date mismatch - you mentioned {day_name.capitalize()} but the date provided ({parsed_time.strftime('%B %d')}) is actually a {actual_day_name}. Please use check_availability to find the correct date for {day_name.capitalize()} and try again.",
                        "needs_clarification": "datetime",
                        "expected_day": day_name.capitalize(),
                        "actual_day": actual_day_name
                    }
                logger.info(f"[BOOK_JOB] Day of week validated: {day_name} matches {parsed_time.strftime('%A')}")
            
            # Validate business hours - MUST pass company_id for correct company-specific hours
            from src.utils.config import Config
            business_hours = Config.get_business_hours(company_id=company_id)
            requested_hour = parsed_time.hour
            start_hour = business_hours.get('start', 9)
            end_hour = business_hours.get('end', 17)
            
            logger.info(f"[BOOK_JOB] Business hours: {start_hour}:00 - {end_hour}:00, Requested hour: {requested_hour}")
            
            if requested_hour < start_hour or requested_hour >= end_hour:
                logger.warning(f"[BOOK_JOB] Outside business hours: {requested_hour}")
                # Generate user-friendly message based on whether time is before or after hours
                if requested_hour < start_hour:
                    time_msg = f"We don't open until {start_hour}:00 AM"
                else:
                    # Convert to 12-hour format for end time
                    end_hour_12 = end_hour if end_hour <= 12 else end_hour - 12
                    end_period = "AM" if end_hour < 12 else "PM"
                    time_msg = f"We close at {end_hour_12}:00 {end_period}"
                
                # Format business hours for display
                end_display = end_hour if end_hour <= 12 else end_hour - 12
                end_display_period = "AM" if end_hour < 12 else "PM"
                
                return {
                    "success": False,
                    "error": f"{time_msg}. Please check availability using check_availability and suggest a time within business hours ({start_hour}:00 AM - {end_display}:00 {end_display_period}).",
                    "needs_clarification": "datetime"
                }
            
            # Check if slot is available - use service duration
            # Get matched service info for duration, price, and service name
            logger.info(f"[BOOK_JOB] Matching service for: {job_description}")
            match_result = match_service(job_description, company_id=company_id)
            matched_service = match_result['service']
            matched_service_name = match_result['matched_name']
            service_duration = matched_service.get('duration_minutes', 60)
            logger.info(f"[BOOK_JOB] Matched service: {matched_service_name}, Duration: {service_duration} mins")
            
            # CRITICAL: For full-day services (8+ hours), auto-adjust to start of business day
            # This prevents the confusing loop of "5pm not available, try 4pm, 4pm not available..."
            if service_duration >= 480:  # 8 hours or more (full day job)
                original_time = parsed_time
                parsed_time = parsed_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                logger.info(f"[BOOK_JOB] Full-day service ({service_duration} mins) - auto-adjusted time from {original_time.strftime('%I:%M %p')} to {parsed_time.strftime('%I:%M %p')} (start of business day)")
            
            # CRITICAL: Check if the job can be completed before closing time
            # For full-day services (8+ hours = 480 mins), we only need to check if the DAY is free
            # The duration is meant to BLOCK the whole day, not require that many hours of work
            if service_duration >= 480:
                # Full-day job - just needs the business day to be free
                # The job "ends" at closing time for booking purposes
                job_end_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
                logger.info(f"[BOOK_JOB] Full-day job ({service_duration} mins) - checking if day is free (blocks {start_hour}:00 - {end_hour}:00)")
            else:
                job_end_time = parsed_time + timedelta(minutes=service_duration)
            
            closing_time = parsed_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            
            # For non-full-day jobs, check if job extends past closing time
            if job_end_time > closing_time:
                
                # Calculate the latest possible start time
                latest_start_hour = end_hour - (service_duration // 60)
                latest_start_minute = 60 - (service_duration % 60) if service_duration % 60 > 0 else 0
                if latest_start_minute == 60:
                    latest_start_minute = 0
                else:
                    latest_start_hour -= 1 if service_duration % 60 > 0 else 0
                
                # Format times for display
                end_hour_12 = end_hour if end_hour <= 12 else end_hour - 12
                end_period = "PM" if end_hour >= 12 else "AM"
                latest_hour_12 = latest_start_hour if latest_start_hour <= 12 else latest_start_hour - 12
                latest_period = "PM" if latest_start_hour >= 12 else "AM"
                
                logger.warning(f"[BOOK_JOB] Job would extend past closing: {parsed_time.strftime('%I:%M %p')} + {service_duration} mins = {job_end_time.strftime('%I:%M %p')}, closes at {end_hour}:00")
                return {
                    "success": False,
                    "error": f"This {service_duration}-minute job starting at {parsed_time.strftime('%I:%M %p')} would finish at {job_end_time.strftime('%I:%M %p')}, but we close at {end_hour_12}:00 {end_period}. The latest we can start this job is {latest_hour_12}:{latest_start_minute:02d} {latest_period}. Please suggest an earlier time.",
                    "needs_clarification": "datetime",
                    "service_duration": service_duration,
                    "latest_start_time": f"{latest_hour_12}:{latest_start_minute:02d} {latest_period}"
                }
            
            # Get workers_required from matched service (default 1)
            workers_required = matched_service.get('workers_required', 1) or 1
            worker_restrictions = matched_service.get('worker_restrictions')
            logger.info(f"[BOOK_JOB] Service requires {workers_required} worker(s), restrictions: {worker_restrictions}")
            
            # Check if company has workers configured
            has_workers = db.has_workers(company_id) if db else False
            assigned_workers = []
            logger.info(f"[BOOK_JOB] Company has workers: {has_workers}")
            
            # AVAILABILITY CHECK: Different logic depending on whether company has workers
            # If company has workers, we check WORKER availability (a slot is available if a qualified worker is free)
            # If no workers, we check CALENDAR availability (any booking blocks the slot)
            if has_workers:
                # Worker-based availability: check if any qualified worker is free
                logger.info(f"[BOOK_JOB] Checking WORKER availability at {parsed_time} for {service_duration} mins")
                available_workers = db.find_available_workers_for_slot(
                    appointment_time=parsed_time,
                    duration_minutes=service_duration,
                    company_id=company_id
                )
                
                # Apply worker restrictions if any
                if available_workers and worker_restrictions:
                    restriction_type = worker_restrictions.get('type', 'all')
                    restricted_ids = worker_restrictions.get('worker_ids', [])
                    
                    if restriction_type == 'only' and restricted_ids:
                        # Only these workers can do this job
                        available_workers = [w for w in available_workers if w['id'] in restricted_ids]
                        logger.info(f"[BOOK_JOB] After 'only' restriction: {len(available_workers)} workers")
                    elif restriction_type == 'except' and restricted_ids:
                        # All workers except these can do this job
                        available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
                        logger.info(f"[BOOK_JOB] After 'except' restriction: {len(available_workers)} workers")
                
                logger.info(f"[BOOK_JOB] Available workers: {available_workers}")
                
                if available_workers is None:
                    # Database error - log warning but proceed without worker assignment
                    logger.warning(f"[BOOK_JOB] Worker lookup failed due to database error - proceeding without worker assignment")
                elif len(available_workers) < workers_required:
                    # Not enough workers available at this time
                    logger.warning(f"[BOOK_JOB] Not enough workers available: need {workers_required}, have {len(available_workers)}")
                    day_name = parsed_time.strftime('%A')
                    
                    # Provide more helpful error message based on whether restrictions are in play
                    has_restrictions = worker_restrictions and worker_restrictions.get('type') in ['only', 'except']
                    
                    if len(available_workers) == 0:
                        if has_restrictions:
                            return {
                                "success": False,
                                "error": f"No qualified workers are available for this type of job at {parsed_time.strftime('%I:%M %p on %A, %B %d')}. Please check availability and suggest another time.",
                                "failed_day": day_name,
                                "failed_time": parsed_time.strftime('%I:%M %p'),
                                "service_duration": service_duration
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"No workers are available at {parsed_time.strftime('%I:%M %p on %A, %B %d')}. Please check availability and suggest another time when a worker is free.",
                                "failed_day": day_name,
                                "failed_time": parsed_time.strftime('%I:%M %p'),
                                "service_duration": service_duration
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"This job requires {workers_required} workers but only {len(available_workers)} {'is' if len(available_workers) == 1 else 'are'} available at {parsed_time.strftime('%I:%M %p on %A, %B %d')}. Please check availability and suggest another time.",
                            "failed_day": day_name,
                            "failed_time": parsed_time.strftime('%I:%M %p'),
                            "service_duration": service_duration
                        }
                else:
                    # Select the required number of workers
                    assigned_workers = available_workers[:workers_required]
                    worker_names = ', '.join([w['name'] for w in assigned_workers])
                    logger.info(f"[BOOK_JOB] Auto-assigning {len(assigned_workers)} worker(s): {worker_names}")
            else:
                # No workers configured - use simple calendar availability check
                logger.info(f"[BOOK_JOB] Checking CALENDAR availability at {parsed_time} for {service_duration} mins")
                is_available = google_calendar.check_availability(parsed_time, duration_minutes=service_duration)
                logger.info(f"[BOOK_JOB] Availability check result: {is_available}")
                
                if not is_available:
                    logger.warning(f"[BOOK_JOB] Time slot not available")
                    day_name = parsed_time.strftime('%A')
                    return {
                        "success": False,
                        "error": f"That time slot on {day_name} is already booked. If multiple times on {day_name} have failed, suggest trying a different day instead. Use check_availability to find available times on other days.",
                        "failed_day": day_name,
                        "failed_time": parsed_time.strftime('%I:%M %p'),
                        "service_duration": service_duration
                    }
            
            # Create calendar event with trades details
            summary = f"{urgency_level.upper()}: {job_description[:50]} - {customer_name}"
            logger.info(f"[BOOK_JOB] Creating calendar event: {summary}")
            
            try:
                event = google_calendar.book_appointment(
                    summary=summary,
                    start_time=parsed_time,
                    duration_minutes=service_duration,
                    description=f"Booked via AI receptionist\n\nCustomer: {customer_name}\nPhone: {phone}\nEmail: {email}\n\nJob Address: {validated_address}\nJob Description: {job_description}\nMatched Service: {matched_service_name}\nUrgency: {urgency_level}\nProperty Type: {property_type}\nDuration: {service_duration} mins",
                    phone_number=phone
                )
                logger.info(f"[BOOK_JOB] Calendar event created: {event}")
            except Exception as cal_error:
                logger.error(f"[BOOK_JOB] Calendar event creation failed: {cal_error}")
                import traceback
                traceback.print_exc()
                return {
                    "success": False,
                    "error": f"Failed to create calendar event: {str(cal_error)}"
                }
            
            if not event:
                logger.error(f"[BOOK_JOB] Calendar returned None for event")
                return {
                    "success": False,
                    "error": "Failed to create calendar event"
                }
            
            # Save to database with trades-specific fields
            if db:
                logger.info(f"[BOOK_JOB] Saving to database...")
                try:
                    # Find or create client - MUST pass company_id for data isolation
                    logger.info(f"[BOOK_JOB] Finding/creating client: {customer_name}, phone={phone}, email={email}")
                    client_id = db.find_or_create_client(
                        name=customer_name,
                        phone=phone,
                        email=email,
                        date_of_birth=None,
                        company_id=company_id
                    )
                    logger.info(f"[BOOK_JOB] Client ID: {client_id}")
                    
                    # Get the correct price from matched service
                    if urgency_level == 'emergency' and matched_service.get('emergency_price'):
                        job_charge = float(matched_service['emergency_price'])
                    else:
                        job_charge = float(matched_service.get('price', 0))
                    logger.info(f"[BOOK_JOB] Job charge: EUR{job_charge}")
                    
                    # Add booking with validated address information, correct charge, and duration
                    # MUST pass company_id for data isolation
                    logger.info(f"[BOOK_JOB] Adding booking to database...")
                    booking_id = db.add_booking(
                        client_id=client_id,
                        calendar_event_id=event.get('id'),
                        appointment_time=parsed_time,
                        service_type=matched_service_name,
                        phone_number=phone,
                        email=email,
                        urgency=urgency_level,
                        address=validated_address,
                        eircode=extracted_eircode,  # Use extracted eircode if available
                        property_type=property_type,
                        charge=job_charge,
                        company_id=company_id,
                        duration_minutes=service_duration
                    )
                    logger.info(f"[BOOK_JOB] Booking ID: {booking_id}")
                    
                    # Check if booking was created successfully
                    if not booking_id:
                        logger.error(f"[BOOK_JOB] ❌ Failed to create booking in database")
                        return {
                            "success": False,
                            "error": "Failed to save booking to database. Please try again."
                        }
                    
                    # Add note with job details including matched service and original description
                    db.add_appointment_note(
                        booking_id, 
                        f"Booked via AI receptionist\n\nJob Address: {validated_address}\nCustomer Description: {job_description}\nMatched Service: {matched_service_name}\nUrgency: {urgency_level}\nProperty Type: {property_type}\nDuration: {service_duration} mins", 
                        created_by="system"
                    )
                    
                    # Persist address audio URL if captured during the call
                    call_state = services.get('call_state')
                    if call_state and getattr(call_state, 'address_audio_url', None):
                        try:
                            db.update_booking(booking_id, address_audio_url=call_state.address_audio_url)
                            logger.info(f"[BOOK_JOB] 🎙️ Address audio URL saved: {call_state.address_audio_url}")
                        except Exception as audio_err:
                            logger.warning(f"[BOOK_JOB] ⚠️ Could not save address audio URL: {audio_err}")
                    
                    # Auto-assign workers if any were selected
                    if assigned_workers:
                        for worker in assigned_workers:
                            try:
                                logger.info(f"[BOOK_JOB] Assigning worker {worker['name']} to booking {booking_id}")
                                assignment_result = db.assign_worker_to_job(booking_id, worker['id'])
                                if assignment_result.get('success'):
                                    logger.info(f"[BOOK_JOB] ✅ Worker {worker['name']} assigned successfully")
                                else:
                                    logger.warning(f"[BOOK_JOB] ⚠️ Failed to assign worker {worker['name']}: {assignment_result.get('error')}")
                            except Exception as worker_err:
                                logger.warning(f"[BOOK_JOB] ⚠️ Could not assign worker {worker['name']}: {worker_err}")
                    
                    # Update client description
                    try:
                        from src.services.client_description_generator import update_client_description
                        update_client_description(client_id)
                    except Exception:
                        pass
                    
                    # Update client's address/eircode to most recent, email only if not set
                    try:
                        existing_client = db.get_client(client_id, company_id=company_id)
                        if existing_client:
                            update_fields = {}
                            # Always update address/eircode to keep profile current
                            if validated_address:
                                update_fields['address'] = validated_address
                            if extracted_eircode:
                                update_fields['eircode'] = extracted_eircode
                            # Only update email if not already set
                            if not existing_client.get('email') and email:
                                update_fields['email'] = email
                            if update_fields:
                                db.update_client(client_id, **update_fields)
                                logger.info(f"[BOOK_JOB] Updated client info: {update_fields}")
                    except Exception as addr_err:
                        logger.warning(f"[BOOK_JOB] Could not update client info: {addr_err}")
                    
                    logger.info(f"[BOOK_JOB] ✅ Job booking saved to database (ID: {booking_id}, company_id: {company_id})")
                except Exception as e:
                    logger.error(f"[BOOK_JOB] ❌ Database save failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                logger.warning(f"[BOOK_JOB] No database available - booking not saved to DB")
            
            # Build response message
            if assigned_workers:
                if len(assigned_workers) == 1:
                    worker_msg = f" Assigned to {assigned_workers[0]['name']}."
                else:
                    worker_names = ', '.join([w['name'] for w in assigned_workers])
                    worker_msg = f" Assigned to {worker_names}."
            else:
                worker_msg = ""
            
            tool_duration = time_module.time() - tool_start_time
            print(f"[TOOL_TIMING] ✅ book_job completed in {tool_duration:.3f}s")
            logger.info(f"[BOOK_JOB] ========== JOB BOOKING COMPLETE ==========")
            return {
                "success": True,
                "message": f"Job booked for {customer_name} on {parsed_time.strftime('%A, %B %d at %I:%M %p')} ({format_duration(service_duration)}). {urgency_level.title()} job at {validated_address}.{worker_msg}",
                "appointment_details": {
                    "customer": customer_name,
                    "time": parsed_time.strftime('%A, %B %d at %I:%M %p'),
                    "duration_minutes": service_duration,
                    "duration_display": format_duration(service_duration),
                    "matched_service": matched_service_name,
                    "job_address": validated_address,
                    "job_description": job_description,
                    "urgency": urgency_level,
                    "phone": phone,
                    "email": email,
                    "property_type": property_type,
                    "eircode": extracted_eircode,
                    "assigned_workers": [{'name': w['name'], 'id': w['id']} for w in assigned_workers] if assigned_workers else [],
                    "workers_required": workers_required
                }
            }
        
        elif tool_name == "cancel_job":
            logger.info(f"[CANCEL_JOB] Processing cancel_job request")
            # Map cancel_job arguments to cancel_appointment format
            mapped_args = {
                'appointment_date': arguments.get('appointment_date') or arguments.get('appointment_datetime'),
                'customer_name': arguments.get('customer_name')
            }
            return execute_tool_call("cancel_appointment", mapped_args, services)
        
        elif tool_name == "reschedule_job":
            logger.info(f"[RESCHEDULE_JOB] Processing reschedule_job request")
            # Map reschedule_job arguments to reschedule_appointment format
            mapped_args = {
                'current_date': arguments.get('current_date') or arguments.get('current_datetime'),
                'new_datetime': arguments.get('new_datetime'),
                'customer_name': arguments.get('customer_name')
            }
            return execute_tool_call("reschedule_appointment", mapped_args, services)
        
        elif tool_name == "modify_job":
            """Modify details of an existing job without changing the time"""
            logger.info(f"[MODIFY_JOB] ========== MODIFYING JOB ==========")
            appointment_datetime = arguments.get('appointment_datetime')
            customer_name = arguments.get('customer_name')
            new_address = arguments.get('new_address')
            new_job_description = arguments.get('new_job_description')
            new_phone = arguments.get('new_phone')
            new_email = arguments.get('new_email')
            new_urgency = arguments.get('new_urgency')
            
            logger.info(f"[MODIFY_JOB] DateTime: {appointment_datetime}, Customer: {customer_name}")
            logger.info(f"[MODIFY_JOB] Updates - Address: {new_address}, Description: {new_job_description}, Phone: {new_phone}, Email: {new_email}, Urgency: {new_urgency}")
            
            if not appointment_datetime:
                return {
                    "success": False,
                    "error": "Appointment date/time is required to find the booking"
                }
            
            # Verify database is available
            if not db:
                return {
                    "success": False,
                    "error": "Database service is not available. Please try again later."
                }
            
            # Parse the appointment time
            parsed_time = parse_datetime(appointment_datetime)
            if not parsed_time:
                return {
                    "success": False,
                    "error": f"Could not parse date/time: {appointment_datetime}"
                }
            
            # If no customer name provided, look up by time only and return details for confirmation
            if not customer_name:
                event = google_calendar.find_appointment_by_details(
                    customer_name=None,
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
                
                # Get current booking details from database
                current_details = {}
                event_id = event.get('id')
                try:
                    bookings = db.get_all_bookings(company_id=company_id)
                    for booking in bookings:
                        # Handle both string and int event_id comparison
                        booking_event_id = booking.get('calendar_event_id')
                        if booking_event_id and str(booking_event_id) == str(event_id):
                            current_details = {
                                'address': booking.get('address'),
                                'service_type': booking.get('service_type'),
                                'phone': booking.get('phone_number'),
                                'email': booking.get('email'),
                                'urgency': booking.get('urgency')
                            }
                            break
                except Exception as e:
                    logger.warning(f"[MODIFY_JOB] Could not fetch booking details: {e}")
                
                # Return details for confirmation
                return {
                    "success": False,
                    "requires_confirmation": True,
                    "customer_name": extracted_name,
                    "appointment_time": parsed_time.strftime('%B %d at %I:%M %p'),
                    "current_details": current_details,
                    "message": f"Found appointment at {parsed_time.strftime('%B %d at %I:%M %p')} for {extracted_name}. Current address: {current_details.get('address', 'Not set')}. What would you like to change?"
                }
            
            # Customer name confirmed - check if any updates were provided
            has_updates = any([new_address, new_job_description, new_phone, new_email, new_urgency])
            if not has_updates:
                return {
                    "success": False,
                    "error": "No changes specified. Please ask the customer what they would like to update (address, job description, phone, email, or urgency)."
                }
            
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
            
            event_id = event.get('id')
            
            # Find the booking in database
            booking_id = None
            current_booking = None
            try:
                bookings = db.get_all_bookings(company_id=company_id)
                for booking in bookings:
                    # Handle both string and int event_id comparison
                    booking_event_id = booking.get('calendar_event_id')
                    if booking_event_id and str(booking_event_id) == str(event_id):
                        booking_id = booking['id']
                        current_booking = booking
                        break
            except Exception as e:
                logger.error(f"[MODIFY_JOB] Error finding booking: {e}")
                return {
                    "success": False,
                    "error": f"Database error while finding booking: {str(e)}"
                }
            
            if not booking_id:
                return {
                    "success": False,
                    "error": "Could not find the booking in the database. The calendar event exists but database record is missing."
                }
            
            # Build update fields
            update_fields = {}
            changes_made = []
            
            # Determine the effective urgency (new or existing)
            effective_urgency = new_urgency if new_urgency else current_booking.get('urgency', 'scheduled')
            
            if new_address:
                # Validate the new address
                address_validator = AddressValidator()
                address_data = address_validator.parse_address_input(new_address)
                
                if address_data['needs_clarification']:
                    return {
                        "success": False,
                        "error": address_data['suggestions'][0] if address_data['suggestions'] else "Please provide a more complete address.",
                        "needs_clarification": "new_address"
                    }
                
                update_fields['address'] = address_data['full_address']
                if address_data.get('eircode'):
                    update_fields['eircode'] = address_data['eircode']
                changes_made.append(f"address to {address_data['full_address']}")
            
            if new_job_description:
                # Re-match service based on new description
                match_result = match_service(new_job_description, company_id=company_id)
                matched_service = match_result['service']
                matched_service_name = match_result['matched_name']
                
                update_fields['service_type'] = matched_service_name
                
                # Update charge based on new service and effective urgency
                if effective_urgency == 'emergency' and matched_service.get('emergency_price'):
                    update_fields['charge'] = float(matched_service['emergency_price'])
                else:
                    update_fields['charge'] = float(matched_service.get('price', 0))
                
                # Update duration
                update_fields['duration_minutes'] = matched_service.get('duration_minutes', 60)
                
                changes_made.append(f"job description to '{new_job_description}' (matched service: {matched_service_name})")
            
            if new_phone:
                update_fields['phone_number'] = new_phone
                changes_made.append(f"phone to {new_phone}")
            
            if new_email:
                update_fields['email'] = new_email
                changes_made.append(f"email to {new_email}")
            
            if new_urgency:
                update_fields['urgency'] = new_urgency
                changes_made.append(f"urgency to {new_urgency}")
                
                # If urgency changed and we didn't already update the charge (via job description change),
                # recalculate the charge based on the current service type
                if not new_job_description and current_booking.get('service_type'):
                    try:
                        match_result = match_service(current_booking['service_type'], company_id=company_id)
                        matched_service = match_result['service']
                        if new_urgency == 'emergency' and matched_service.get('emergency_price'):
                            update_fields['charge'] = float(matched_service['emergency_price'])
                        else:
                            update_fields['charge'] = float(matched_service.get('price', 0))
                    except Exception as price_err:
                        logger.warning(f"[MODIFY_JOB] Could not update charge for urgency change: {price_err}")
            
            # Update the booking in database
            try:
                success = db.update_booking(booking_id, company_id=company_id, **update_fields)
                
                if not success:
                    return {
                        "success": False,
                        "error": "Failed to update the booking in the database"
                    }
                
                # Add a note about the modification
                changes_summary = ", ".join(changes_made)
                db.add_appointment_note(
                    booking_id,
                    f"Job modified via AI receptionist: Changed {changes_summary}",
                    created_by="system"
                )
                
                # Update calendar event description if address or description changed
                if new_address or new_job_description:
                    try:
                        # Get updated booking info
                        updated_booking = None
                        refreshed_bookings = db.get_all_bookings(company_id=company_id)
                        for booking in refreshed_bookings:
                            if booking['id'] == booking_id:
                                updated_booking = booking
                                break
                        
                        if updated_booking and hasattr(google_calendar, 'update_event_description'):
                            new_description = f"Booked via AI receptionist\n\nCustomer: {customer_name}\nPhone: {updated_booking.get('phone_number', '')}\nEmail: {updated_booking.get('email', '')}\n\nJob Address: {updated_booking.get('address', '')}\nService: {updated_booking.get('service_type', '')}\nUrgency: {updated_booking.get('urgency', '')}\n\n[Modified: {changes_summary}]"
                            google_calendar.update_event_description(event_id, new_description)
                    except Exception as cal_err:
                        logger.warning(f"[MODIFY_JOB] Could not update calendar description: {cal_err}")
                
                logger.info(f"[MODIFY_JOB] ✅ Job modified successfully: {changes_summary}")
                
                return {
                    "success": True,
                    "message": f"Successfully updated the job for {customer_name} on {parsed_time.strftime('%B %d at %I:%M %p')}. Changed: {changes_summary}.",
                    "changes": changes_made
                }
                
            except Exception as e:
                logger.error(f"[MODIFY_JOB] Error updating booking: {e}")
                import traceback
                traceback.print_exc()
                return {
                    "success": False,
                    "error": f"Error updating booking: {str(e)}"
                }
        
        elif tool_name == "transfer_to_human":
            """Transfer call to a real human"""
            reason = arguments.get('reason', 'customer requested human')
            
            # Get business phone number for transfer
            from src.services.settings_manager import get_settings_manager
            settings_mgr = get_settings_manager()
            transfer_number = settings_mgr.get_fallback_phone_number(company_id=company_id)  # Returns business phone
            
            if not transfer_number:
                return {
                    "success": False,
                    "error": "No business phone number configured. Cannot transfer call.",
                    "message": "I'm sorry, but I don't have a number to transfer you to right now. Is there anything else I can help you with?"
                }
            
            logger.info(f"Transfer: TRANSFER REQUEST: {reason}")
            logger.info(f"Transfer: Transferring to business phone: {transfer_number}")
            
            tool_duration = time_module.time() - tool_start_time
            print(f"[TOOL_TIMING] ✅ {tool_name} completed in {tool_duration:.3f}s")
            
            return {
                "success": True,
                "transfer": True,
                "fallback_number": transfer_number,
                "reason": reason,
                "message": "Let me transfer you now. Please hold."
            }
        
        else:
            tool_duration = time_module.time() - tool_start_time
            print(f"[TOOL_TIMING] ⚠️ Unknown tool {tool_name} after {tool_duration:.3f}s")
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
    
    except Exception as e:
        tool_duration = time_module.time() - tool_start_time
        print(f"[TOOL_TIMING] ❌ {tool_name} FAILED after {tool_duration:.3f}s: {e}")
        logger.error(f"[TOOL_ERROR] ========== TOOL EXECUTION FAILED ==========")
        logger.error(f"[TOOL_ERROR] Tool: {tool_name}")
        logger.error(f"[TOOL_ERROR] Arguments: {arguments}")
        logger.error(f"[TOOL_ERROR] Exception type: {type(e).__name__}")
        logger.error(f"[TOOL_ERROR] Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Error executing {tool_name}: {str(e)}"
        }
