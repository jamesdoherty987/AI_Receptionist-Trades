"""
LLM streaming service with appointment handling

CONCURRENCY NOTE: This module is designed to handle multiple concurrent phone calls.
All per-call state is encapsulated in the CallState class, which must be passed
to stream_llm() for each call. Do NOT use global state for call-specific data.
"""
import re
import os
import json
import asyncio
import time  # For timing logs
import random  # For random filler message selection

from openai import OpenAI
from src.utils.config import config
from src.utils.date_parser import parse_datetime
from src.services.calendar_tools import CALENDAR_TOOLS, execute_tool_call
from src.services.call_state import CallState, create_call_state
from src.utils.security import normalize_phone_for_comparison

# --- AI-based utilities for text parsing ---
from src.utils.ai_text_parser import extract_time_window_ai, extract_name_ai, detect_birth_year, is_affirmative_response

# Use AI for time window extraction
def extract_time_window(text):
    """
    Extracts a time window from user text using AI
    Examples: 'after 2', 'late times', 'evening', 'between 2 and 4'
    Returns (start_hour, end_hour) in 24h format, or (None, None) if not found.
    """
    return extract_time_window_ai(text)
from src.services.appointment_detector import AppointmentDetector, AppointmentIntent, print_appointment_action
from src.services.google_calendar import get_calendar_service
from src.services.ai_reschedule_handler import AIRescheduleHandler
from src.utils.reschedule_config import (
    RESCHEDULE_MESSAGES, 
    is_time_vague, 
    is_confirmation_response,
    are_times_different,
    has_date_indicator
)
from datetime import datetime, timedelta
import dateparser


# Configuration constants
MAX_CONVERSATION_HISTORY = 6  # Maximum number of message pairs to keep in context
DEFAULT_APPOINTMENT_DURATION_MINUTES = 1440  # Default duration for AI phone bookings (1 day for trades)
CONFIRMATION_THRESHOLD = 0.7  # Confidence threshold for confirmation detection
SKIP_APPOINTMENT_DETECTION = True  # Skip ALL appointment detection - LLM handles it with tools


def format_for_tts_spelling(text: str) -> str:
    """
    Format text for TTS to read spelled-out content more slowly.
    
    When the AI spells out names, eircodes, or phone numbers (e.g., "D-O-2-W-R-9-7"),
    the TTS tends to rush through them. This function adds spaces between letters
    to make TTS read them more slowly and clearly.
    
    Examples:
        "D-O-2-W-R-9-7" -> "D - O - 2 - W - R - 9 - 7"
        "J-O-H-N" -> "J - O - H - N"
        "085 263 5954" -> "0 8 5 ... 2 6 3 ... 5 9 5 4"
        "V95H5P2" -> "V 9 5 H 5 P 2"
    """
    if not text:
        return text
    
    # Pattern for spelled-out content: single characters separated by dashes
    # e.g., "J-O-H-N" or "D-O-2-W-R-9-7"
    spelled_pattern = re.compile(r'\b([A-Z0-9]-)+[A-Z0-9]\b', re.IGNORECASE)
    
    def add_spaces_to_spelled(match):
        # Add spaces around dashes for slower reading
        spelled = match.group(0)
        return spelled.replace('-', ' - ')
    
    result = spelled_pattern.sub(add_spaces_to_spelled, text)
    
    # Handle Irish phone numbers (085 263 5954 format) - space out each digit group
    # Pattern: digit groups separated by spaces that look like phone numbers
    irish_phone_pattern = re.compile(r'\b(0\d{2})\s+(\d{3})\s+(\d{4})\b')
    
    def space_irish_phone(match):
        g1, g2, g3 = match.groups()
        # Space out each digit with pauses between groups
        spaced_g1 = ' '.join(g1)
        spaced_g2 = ' '.join(g2)
        spaced_g3 = ' '.join(g3)
        return f"{spaced_g1} ... {spaced_g2} ... {spaced_g3}"
    
    result = irish_phone_pattern.sub(space_irish_phone, result)
    
    # Handle eircodes (V95H5P2 or V95 H5P2 format) - space out each character
    # Pattern: letter + 2 digits + optional space + 4 alphanumeric
    eircode_pattern = re.compile(r'\b([A-Z]\d{2})\s?([A-Z0-9]{4})\b', re.IGNORECASE)
    
    def space_eircode(match):
        part1, part2 = match.groups()
        # Space out each character
        spaced_part1 = ' '.join(part1.upper())
        spaced_part2 = ' '.join(part2.upper())
        return f"{spaced_part1} ... {spaced_part2}"
    
    result = eircode_pattern.sub(space_eircode, result)
    
    # Handle any remaining digit sequences (3+ digits together)
    phone_pattern = re.compile(r'\b(\d{3,})\b')
    
    def space_out_digits(match):
        digits = match.group(0)
        if len(digits) >= 7:  # Likely a phone number
            spaced = ' '.join(digits)
            return spaced
        return digits
    
    result = phone_pattern.sub(space_out_digits, result)
    
    return result

# Lazy initialization of OpenAI client with optimized settings
_client = None

def get_openai_client():
    """Get or create OpenAI client instance with optimized connection settings"""
    global _client
    if _client is None:
        import httpx
        # Create client with reasonable timeouts (not too aggressive)
        _client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=httpx.Timeout(60.0, connect=10.0),  # 10s connect, 60s total
            max_retries=2,  # Allow retries for reliability
        )
    return _client


def load_business_info(company_id=None):
    """Load business information from companies table by company_id.
    Falls back to first company if no company_id provided (backwards compatible).
    """
    import time as time_module
    load_start = time_module.time()
    
    from src.services.database import get_database
    
    try:
        db = get_database()
        conn = db.get_connection()
        
        if hasattr(db, 'use_postgres') and db.use_postgres:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Use SELECT * to avoid issues with columns that may not exist yet
            if company_id:
                cursor.execute("SELECT * FROM companies WHERE id = %s", (int(company_id),))
            else:
                cursor.execute("SELECT * FROM companies ORDER BY id LIMIT 1")
            row = cursor.fetchone()
            db.return_connection(conn)
            company = dict(row) if row else None
        else:
            cursor = conn.cursor()
            if company_id:
                cursor.execute("SELECT * FROM companies WHERE id = ?", (int(company_id),))
            else:
                cursor.execute("SELECT * FROM companies ORDER BY id LIMIT 1")
            row = cursor.fetchone()
            if row:
                cursor.execute("PRAGMA table_info(companies)")
                columns = [col[1] for col in cursor.fetchall()]
                company = dict(zip(columns, row))
            else:
                company = None
            conn.close()
        
        load_time = time_module.time() - load_start
        
        if company:
            # Return in the format expected by the rest of the code
            business_name = company.get('company_name') or 'Your Business'
            print(f"[TIMING] load_business_info completed in {load_time:.3f}s (company_id={company_id}: {business_name})")
            
            return {
                'business_name': business_name,
                'business_hours': company.get('business_hours') or '8 AM - 6 PM Mon-Sat',
                'phone': company.get('phone') or 'Not configured',
                'email': company.get('email') or 'Not configured',
                'address': company.get('address') or 'Not configured',
                'company_context': company.get('company_context') or '',
                'coverage_area': company.get('coverage_area') or ''
            }
    except Exception as e:
        load_time = time_module.time() - load_start
        print(f"[TIMING] load_business_info failed after {load_time:.3f}s (company_id={company_id}): {e}")
    
    # Fallback to generic info
    return {
        'business_name': 'Your Business',
        'business_hours': '8 AM - 6 PM Mon-Sat',
        'phone': 'Not configured',
        'email': 'Not configured',
        'address': 'Not configured',
        'coverage_area': ''
    }


def load_services_menu():
    """Load services menu from database"""
    from src.services.settings_manager import get_settings_manager
    
    try:
        settings_mgr = get_settings_manager()
        return settings_mgr.get_services_menu()
    except Exception as e:
        print(f"[WARNING] Error loading services from database: {e}")
        return {
            "business_hours": {
                "start_hour": 9,
                "end_hour": 17,
                "days_open": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            },
            "services": [],
            "pricing_notes": {}
        }


def get_business_hours_from_menu():
    """Get business hours from settings"""
    from src.services.settings_manager import get_settings_manager
    
    try:
        settings_mgr = get_settings_manager()
        hours = settings_mgr.get_business_hours()
        return {
            'start': hours.get('start_hour', config.BUSINESS_HOURS_START),
            'end': hours.get('end_hour', config.BUSINESS_HOURS_END),
            'days_open': hours.get('days_open', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']),
            'notes': ''
        }
    except Exception as e:
        print(f"[WARNING] Error loading business hours: {e}")
        return {
            'start': config.BUSINESS_HOURS_START,
            'end': config.BUSINESS_HOURS_END,
            'days_open': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'notes': ''
        }


def is_business_day(dt: datetime) -> bool:
    """Check if a given datetime is on a business day"""
    try:
        business_hours = config.get_business_days_indices()
        return dt.weekday() in business_hours
    except:
        return dt.weekday() in config.BUSINESS_DAYS


def load_system_prompt(company_id=None):
    """Load system prompt from file and inject business information.
    When company_id is provided, loads that company's specific info.
    
    CACHING: For company_id=None (default), uses cached SYSTEM_PROMPT.
    For specific company_id, loads fresh from DB (company-specific data).
    """
    import time as time_module
    prompt_start = time_module.time()
    
    print(f"\n[PROMPT_DEBUG] load_system_prompt called with company_id={company_id}")
    
    # Use fast/condensed prompt for better performance
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
        'prompts', 'receptionist_prompt_fast.txt'  # Using condensed version for speed
    )
    
    # Load business info (for specific company if ID provided) and services menu
    biz_info_start = time_module.time()
    print(f"[PROMPT_DEBUG] Loading business info...")
    business_info = load_business_info(company_id=company_id)
    biz_info_time = time_module.time() - biz_info_start
    print(f"[PROMPT_DEBUG] Business info loaded in {biz_info_time*1000:.1f}ms")
    
    services_start = time_module.time()
    print(f"[PROMPT_DEBUG] Loading services menu...")
    services_menu = load_services_menu()
    services_time = time_module.time() - services_start
    print(f"[PROMPT_DEBUG] Services menu loaded in {services_time*1000:.1f}ms")
    
    # Get business hours from database settings (pass company_id for company-specific hours)
    hours_start = time_module.time()
    print(f"[PROMPT_DEBUG] Loading business hours...")
    business_hours_data = config.get_business_hours(company_id=company_id)
    hours_time = time_module.time() - hours_start
    print(f"[PROMPT_DEBUG] Business hours loaded in {hours_time*1000:.1f}ms")
    
    business_hours = {
        'start_hour': business_hours_data['start'],
        'end_hour': business_hours_data['end'],
        'days_open': business_hours_data['days_open']
    }
    
    db_total = biz_info_time + services_time + hours_time
    print(f"[TIMING] load_system_prompt DB calls: biz_info={biz_info_time*1000:.1f}ms, services={services_time*1000:.1f}ms, hours={hours_time*1000:.1f}ms, TOTAL={db_total*1000:.1f}ms")
    
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        # Inject business information into the prompt
        prompt = prompt_template.replace("{{BUSINESS_NAME}}", business_info.get("business_name", "Your Business"))
        prompt = prompt.replace("{{PRACTITIONER_NAME}}", business_info.get("staff", {}).get("business_owner", "James"))
        prompt = prompt.replace("{{BUSINESS_OWNER}}", business_info.get("staff", {}).get("business_owner", "James"))
        prompt = prompt.replace("{{BUSINESS_HOURS}}", business_info.get("business_hours", "8 AM - 6 PM Mon-Sat (24/7 emergency available)"))
        prompt = prompt.replace("{{CALLOUT_FEE}}", services_menu.get('pricing_notes', {}).get('callout_fee', '€60'))
        
        # Build services list from menu
        services_list = []
        for service in services_menu.get('services', []):
            if service.get('active', True):
                service_line = f"{service['name']} ({service['category']}) - €{service['price']}"
                if service.get('emergency_price'):
                    service_line += f" (Emergency: €{service['emergency_price']})"
                service_line += f" - {service['duration_minutes']} minutes"
                services_list.append(service_line)
        
        # Build business hours string
        hours_str = f"{business_hours.get('start_hour', 9)}:00 to {business_hours.get('end_hour', 17)}:00"
        days_str = ', '.join(business_hours.get('days_open', ['Monday-Friday']))
        
        # Get coverage area from business info
        coverage_area = business_info.get('coverage_area', '').strip()
        coverage_line = f"COVERAGE AREA: {coverage_area}" if coverage_area else ""
        
        # Get current date/time for context
        now = datetime.now()
        current_day = now.strftime('%A')
        current_date = now.strftime('%B %d, %Y')
        tomorrow_day = (now + timedelta(days=1)).strftime('%A')
        
        # Add business info section at the end of prompt
        business_context = f"""

###############################################################################
## CURRENT DATE/TIME CONTEXT
###############################################################################

TODAY IS: {current_day}, {current_date}
TOMORROW IS: {tomorrow_day}

IMPORTANT: When offering availability for TOMORROW, always say "tomorrow" - never say "{tomorrow_day}" or the date.

###############################################################################
## BUSINESS INFORMATION (Auto-loaded from database)
###############################################################################

BUSINESS: {business_info.get('business_name', 'Your Business')}
TYPE: {business_info.get('business_type', 'Multi-Trade Services Company')}
OWNER: {business_info.get('staff', {}).get('business_owner', 'James')}

{coverage_line}

BUSINESS HOURS: {hours_str}
DAYS OPEN: {days_str}
{business_hours.get('notes', '')}

SERVICES OFFERED:
{chr(10).join('- ' + s for s in services_list) if services_list else '- General trade services'}

PRICING NOTES:
- Callout fee: {services_menu.get('pricing_notes', {}).get('callout_fee', '€60 minimum')}
- Hourly rate: {services_menu.get('pricing_notes', {}).get('hourly_rate', '€50 per hour')}
- Payment methods: {', '.join(services_menu.get('pricing_notes', {}).get('payment_methods', ['Cash', 'Card']))}
- Free quotes: {'Yes' if services_menu.get('pricing_notes', {}).get('free_quotes', True) else 'No'}

POLICIES:
- Cancellation notice: {services_menu.get('service_policies', {}).get('cancellation_notice', '2 hours')}
- Warranty: {services_menu.get('service_policies', {}).get('warranty_months', 12)} months

IMPORTANT: Use this information to answer customer questions accurately. Quote prices from the services list above.
"""
        # Add company-specific context if provided by the business owner
        company_context_text = business_info.get('company_context', '').strip()
        if company_context_text:
            business_context += f"""

###############################################################################
## ADDITIONAL COMPANY DETAILS (Written by the business owner)
###############################################################################

{company_context_text}

IMPORTANT: Use these details when relevant during conversations. For example, if a customer asks about parking, directions, company history, or specific policies mentioned above, use this information to answer accurately.
"""
        prompt += business_context
        
        total_prompt_time = time_module.time() - prompt_start
        print(f"[TIMING] load_system_prompt total: {total_prompt_time:.3f}s (company_id={company_id})")
        
        return prompt
        
    except FileNotFoundError:
        # Fallback to basic prompt if file not found
        hours = get_business_hours_from_menu()
        total_prompt_time = time_module.time() - prompt_start
        print(f"[TIMING] load_system_prompt fallback: {total_prompt_time:.3f}s (file not found)")
        return f"""You are a professional AI receptionist for {business_info.get('business_name', 'Your Business')}.
        
Business hours: {hours['start']}:00 to {hours['end']}:00
Days open: {', '.join(hours['days_open'])}
Keep responses brief (1-2 sentences for phone calls).
Be friendly and natural."""


SYSTEM_PROMPT = load_system_prompt()

# Cache for company-specific prompts (avoids repeated DB queries during a call)
# Key: company_id, Value: (prompt_text, timestamp)
_company_prompt_cache = {}
_PROMPT_CACHE_TTL = 300  # 5 minutes - refresh periodically to pick up changes


def get_cached_system_prompt(company_id=None):
    """Get system prompt with caching for company-specific prompts.
    
    This avoids hitting the database on every LLM call during a conversation.
    Cache TTL is 5 minutes to balance freshness with performance.
    """
    import time as time_module
    
    # No company_id = use the global cached prompt (loaded at startup)
    if company_id is None:
        print(f"[PROMPT_CACHE] Using global SYSTEM_PROMPT (no company_id)")
        return SYSTEM_PROMPT
    
    # Check cache for company-specific prompt
    cache_key = str(company_id)
    now = time_module.time()
    
    if cache_key in _company_prompt_cache:
        cached_prompt, cached_time = _company_prompt_cache[cache_key]
        age = now - cached_time
        if age < _PROMPT_CACHE_TTL:
            print(f"[PROMPT_CACHE] HIT for company_id={company_id} (age={age:.1f}s)")
            return cached_prompt
        else:
            print(f"[PROMPT_CACHE] EXPIRED for company_id={company_id} (age={age:.1f}s > TTL={_PROMPT_CACHE_TTL}s)")
    else:
        print(f"[PROMPT_CACHE] MISS for company_id={company_id}")
    
    # Load fresh from database
    load_start = time_module.time()
    prompt = load_system_prompt(company_id=company_id)
    load_time = time_module.time() - load_start
    
    # Cache it
    _company_prompt_cache[cache_key] = (prompt, now)
    print(f"[PROMPT_CACHE] Cached prompt for company_id={company_id} (loaded in {load_time*1000:.1f}ms)")
    
    return prompt


def get_closed_day_message(dt: datetime) -> str:
    """
    Generate a message for when a requested day is closed.
    Dynamically determines which day(s) are closed based on services menu.
    """
    day_name = dt.strftime('%A')
    
    # Get dynamic business hours from services menu
    try:
        business_hours = config.get_business_hours()
        start_hour = business_hours['start']
        end_hour = business_hours['end']
        open_days = business_hours['days_open']
    except:
        start_hour = config.BUSINESS_HOURS_START
        end_hour = config.BUSINESS_HOURS_END
        all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        open_days = [all_days[i] for i in config.BUSINESS_DAYS]
    
    # Find which days are closed
    all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    closed_days = [day for day in all_days if day not in open_days]
    
    # Format the open days string
    if len(open_days) >= 2:
        open_days_str = ', '.join(open_days[:-1]) + ' and ' + open_days[-1]
    else:
        open_days_str = open_days[0] if open_days else ''
    
    # Format the closed days string
    if len(closed_days) == 1:
        closed_days_str = closed_days[0] + 's'
    elif len(closed_days) == 2:
        closed_days_str = closed_days[0] + 's and ' + closed_days[1] + 's'
    else:
        closed_days_str = ', '.join([d + 's' for d in closed_days[:-1]]) + ' and ' + closed_days[-1] + 's'
    
    # Convert end hour to 12-hour format
    end_hour_12 = end_hour if end_hour <= 12 else end_hour - 12
    end_period = "AM" if end_hour < 12 else "PM"
    
    return f"[SYSTEM: We're not open on {closed_days_str}. Our hours are {open_days_str}, {start_hour}:00 AM to {end_hour_12}:00 {end_period}. Politely let them know and suggest checking availability on a working day instead. Ask when would work for them.]"


def remove_repetition(text: str) -> str:
    """Remove repeated phrases from the end of text"""
    words = text.split()
    if len(words) < 6:
        return text
    
    # Check if last N words appear earlier (looking for repetition)
    for length in range(3, min(10, len(words) // 2) + 1):
        last_phrase = ' '.join(words[-length:])
        remaining = ' '.join(words[:-length])
        
        if remaining.endswith(last_phrase):
            return remaining
    
    return text


# DEPRECATED: Global state removed for concurrent call support.
# Use CallState class instead - each call gets its own instance.
# This global is kept ONLY for backwards compatibility with resetcall_state()
call_state = None  # Will be lazily initialized if needed for legacy code

def resetcall_state(call_state: CallState = None):
    """
    Reset appointment tracking state.
    
    DEPRECATED: This function exists for backwards compatibility.
    For new code, create a new CallState instance instead.
    
    Args:
        call_state: Optional CallState instance to reset. If None, resets the
                   legacy global state (not recommended for concurrent calls).
    """
    if call_state is not None:
        call_state.reset()
        return
    
    # Legacy behavior: reset global state (NOT safe for concurrent calls)
    global _appointment_state
    _appointment_state = create_call_state()

def check_caller_in_database(caller_name: str, caller_phone: str = None, caller_email: str = None, company_id: int = None) -> dict:
    """
    Check if caller exists in database by name (case-insensitive).
    Can filter by phone or email for better matching.
    MUST pass company_id for proper multi-tenant data isolation.
    Returns dict with client info or indication of new customer.
    """
    # Safety check: ensure caller_name is not None
    if not caller_name:
        return {
            "status": "new",
            "message": "No name provided",
            "clients": []
        }
    
    from src.services.database import get_database
    db = get_database()
    
    # Normalize name for case-insensitive search
    normalized_name = caller_name.lower().strip()
    
    # Get all clients with matching names - MUST filter by company_id for data isolation
    matching_clients = db.get_clients_by_name(normalized_name, company_id=company_id)
    
    if len(matching_clients) == 0:
        print(f"[CLIENT] New customer: {caller_name} (company_id: {company_id})")
        return {
            "status": "new",
            "message": f"Welcome! I'll get you set up in our system.",
            "clients": []
        }
    elif len(matching_clients) == 1:
        client = matching_clients[0]
        print(f"[CLIENT] Returning customer found by name: {client['name']} (ID: {client['id']}, company_id: {company_id})")
        # Include description in the message if available
        description_text = f"\n\nCustomer History: {client['description']}" if client.get('description') else ""
        return {
            "status": "returning",
            "message": f"Great to hear from you again, {caller_name}!{description_text}",
            "clients": [client]
        }
    else:
        # Multiple clients with same name - try to filter by phone or email
        print(f"[CLIENT] Multiple customers found with name: {caller_name} ({len(matching_clients)} matches, company_id: {company_id})")
        
        # Try to narrow down by phone number if provided
        if caller_phone:
            normalized_caller_phone = normalize_phone_for_comparison(caller_phone)
            phone_matches = [c for c in matching_clients if normalize_phone_for_comparison(c.get('phone') or '') == normalized_caller_phone]
            if len(phone_matches) == 1:
                client = phone_matches[0]
                print(f"[SUCCESS] Matched by phone number: {client['name']} (ID: {client['id']})")
                description_text = f"\n\nCustomer History: {client['description']}" if client.get('description') else ""
                return {
                    "status": "returning",
                    "message": f"Great to hear from you again, {caller_name}!{description_text}",
                    "clients": [client]
                }
            elif len(phone_matches) == 0:
                # Phone provided but doesn't match any existing customer - treat as new
                print(f"[CLIENT] Name matched {len(matching_clients)} customers but phone doesn't match any - treating as NEW customer")
                return {
                    "status": "new",
                    "message": f"Welcome! I'll get you set up in our system.",
                    "clients": []
                }
        
        # Try to narrow down by email if provided
        if caller_email:
            email_matches = [c for c in matching_clients if c.get('email') and c.get('email').lower() == caller_email.lower()]
            if len(email_matches) == 1:
                client = email_matches[0]
                print(f"[SUCCESS] Matched by email: {client['name']} (ID: {client['id']})")
                description_text = f"\n\nCustomer History: {client['description']}" if client.get('description') else ""
                return {
                    "status": "returning",
                    "message": f"Great to hear from you again, {caller_name}!{description_text}",
                    "clients": [client]
                }
            elif len(email_matches) == 0:
                # Email provided but doesn't match any existing customer - treat as new
                print(f"[CLIENT] Name matched {len(matching_clients)} customers but email doesn't match any - treating as NEW customer")
                return {
                    "status": "new",
                    "message": f"Welcome! I'll get you set up in our system.",
                    "clients": []
                }
        
        # No phone or email provided - ask for phone to narrow down
        return {
            "status": "multiple",
            "message": f"I have {len(matching_clients)} customers with that name. Can I get your phone number to confirm which {caller_name.split()[0]} you are?",
            "clients": matching_clients,
            "needs_contact": True
        }

def spell_out_name(name: str) -> str:
    """Convert a name to spelled out format (e.g., 'John' -> 'J-O-H-N')"""
    # Split by spaces to handle first and last names
    parts = name.split()
    spelled_parts = []
    
    for part in parts:
        # Handle special characters like apostrophes
        if "'" in part:
            # Split by apostrophe and spell each part
            sub_parts = part.split("'")
            spelled = "-".join(sub_parts[0].upper()) + "-apostrophe-" + "-".join(sub_parts[1].upper())
            spelled_parts.append(spelled)
        else:
            spelled_parts.append("-".join(part.upper()))
    
    return " ".join(spelled_parts)

async def stream_llm(messages, process_appointment_callback=None, caller_phone=None, company_id=None, call_state: CallState = None):
    """
    Stream LLM responses with appointment detection
    
    Args:
        messages: Conversation history
        process_appointment_callback: Optional callback for appointment processing
        caller_phone: Caller's phone number from Twilio
        company_id: Company ID for multi-tenant business context
        call_state: Per-call state for concurrent call handling. If None, creates
                   a new instance (not recommended for production - pass explicitly).
        
    Yields:
        Text tokens from LLM
    """
    import time as time_module
    llm_start_time = time_module.time()
    
    print(f"\n{'='*70}")
    print(f"[LLM_TIMING] stream_llm started at {llm_start_time:.3f}")
    print(f"[LLM_TIMING] Messages count: {len(messages)}")
    print(f"{'='*70}")

    # Use provided call_state or create a new one (for backwards compatibility)
    # WARNING: Creating a new CallState here means state won't persist across turns
    # For proper concurrent call handling, always pass call_state from media_handler
    if call_state is None:
        print("[WARNING] stream_llm called without call_state - creating temporary instance")
        call_state = create_call_state()
    
    setup_time = time_module.time() - llm_start_time
    if setup_time > 0.1:
        print(f"[LLM_TIMING] ⚠️ Call state setup took {setup_time*1000:.1f}ms")
    
    # Track conversation turn for post-booking cooldown
    call_state.current_turn = call_state.current_turn + 1
    current_turn = call_state.current_turn
    last_booking_turn = call_state.last_booking_turn
    
    # Post-booking cooldown: only the immediate turn after booking, be extra careful about reschedule detection
    in_post_booking_cooldown = (last_booking_turn > 0 and current_turn - last_booking_turn <= 1)
    if in_post_booking_cooldown:
        print(f"[COOLDOWN] In post-booking cooldown (turn {current_turn}, booking was turn {last_booking_turn})")
    
    # --- Name Correction Handling using AI ---
    user_text = messages[-1]["content"] if messages and messages[-1].get("role") == "user" else ""
    
    # PERFORMANCE: Skip expensive AI name extraction - let main LLM handle it
    # Only use simple regex for critical name corrections
    name_correction_phrases = ["no it's", "actually it's", "it's actually", "no that's"]
    if any(phrase in user_text.lower() for phrase in name_correction_phrases):
        # Simple extraction for corrections only
        words = user_text.lower().split()
        for phrase in name_correction_phrases:
            if phrase in user_text.lower():
                idx = user_text.lower().index(phrase) + len(phrase)
                potential_name = user_text[idx:].strip().split('.')[0].strip()
                if potential_name and len(potential_name.split()) <= 3:
                    call_state["customer_name"] = potential_name.title()
                    call_state["caller_identified"] = False
                    print(f"[INFO] Name correction detected: {potential_name.title()}")
                break
    
    # --- Birth Year Detection DISABLED ---
    # PERFORMANCE: Removed AI-based birth year detection - it was adding 600ms+ to EVERY response
    # Trades businesses don't need DOB - customers are identified by phone/name only
    # If birth year detection is ever needed, use simple regex instead of OpenAI API call
    
    # Store phone number if provided and not already stored
    if caller_phone and not call_state.get("phone_number"):
        call_state["phone_number"] = caller_phone
        # Automatically confirm phone if it came from Twilio (caller_phone)
        call_state["phone_confirmed"] = True
        print(f"[PHONE] Caller phone automatically captured: {caller_phone}")
    
    # PERFORMANCE: Skip ALL appointment detection when flag is set
    # The LLM handles everything with native tools - no need for pre-processing
    if not SKIP_APPOINTMENT_DETECTION and messages and messages[-1].get("role") == "user":
        # This entire block is skipped when SKIP_APPOINTMENT_DETECTION=True
        # Jump directly to pre-check for faster response times
        user_text = messages[-1]["content"]
        
        # NOTE: All DOB (date of birth) collection logic removed for trades business.
        # Trades companies identify customers by phone/email only.
        # Customer database lookups use phone/email via check_caller_in_database()
        
        # NOTE: Regex-based name detection removed - now using AI-only approach (extract_name_ai)
        # The AI-based extraction happens earlier in this function and is more robust at
        # understanding natural language (e.g., "ya its james doherty" vs requiring "my name is")
        
        # Quick keyword check before expensive OpenAI call
        # Use partial matching to handle typos (e.g., "reschdule" -> "reschedule")
        appointment_keywords = ["appointment", "appoint", "book", "schedule", "schedul", "cancel", "reschedule", "reschedul", "when is my", "yes", "yeah", "ya", "yep", "yup", "correct", "confirm"]
        likely_appointment = any(word in user_text.lower() for word in appointment_keywords)
        
        # Track initial request if user asks to book appointment BEFORE identification
        if not call_state.get("caller_identified") and not call_state.get("initial_request"):
            if any(word in user_text.lower() for word in ["book", "schedule", "make an appointment", "get an appointment"]):
                call_state["initial_request"] = user_text
                print(f"[INFO] Captured initial request: {user_text}")
        
        # Don't trigger appointment detection if user is providing DOB
        # Simple regex check instead of expensive AI call
        birth_year_pattern = r'\b(19\d{2}|20[0-2]\d)\b'  # Years 1900-2029
        birth_year_match = re.search(birth_year_pattern, user_text)
        if birth_year_match:
            print(f"[WARNING] Message contains birth year {birth_year_match.group()} - skipping appointment detection")
            likely_appointment = False
        
        # Check if we're in an active booking or reschedule flow
        if call_state["active_booking"]:
            likely_appointment = True
        
        # Check if we're in an active reschedule flow
        in_reschedule_flow = (call_state.get("reschedule_active") or
                             call_state.get("reschedule_found_appointment") or 
                             call_state.get("reschedule_name_confirmed") or 
                             call_state.get("reschedule_final_asked"))
        if in_reschedule_flow:
            likely_appointment = True
            print(f"[RESCHEDULE] In active reschedule flow - forcing appointment detection (flags: active={call_state.get('reschedule_active')}, found={call_state.get('reschedule_found_appointment')}, name_confirmed={call_state.get('reschedule_name_confirmed')}, final_asked={call_state.get('reschedule_final_asked')})")
        
        # Check if we're in an active cancel flow
        in_cancel_flow = (call_state.get("cancel_active") or
                         call_state.get("cancel_found_appointment") or 
                         call_state.get("cancel_name_confirmed") or 
                         call_state.get("cancel_final_asked"))
        if in_cancel_flow:
            likely_appointment = True
            print(f"🗑️ In active cancel flow - forcing appointment detection (flags: active={call_state.get('cancel_active')}, found={call_state.get('cancel_found_appointment')}, name_confirmed={call_state.get('cancel_name_confirmed')}, final_asked={call_state.get('cancel_final_asked')})")
        
        print(f"🔍 Appointment keyword check: likely_appointment={likely_appointment}, in_reschedule_flow={in_reschedule_flow}, in_cancel_flow={in_cancel_flow}, active_booking={call_state['active_booking']}")
        
        # PERFORMANCE OPTIMIZATION: Skip ALL appointment detection - let LLM use its tools
        # The main LLM has check_availability, cancel_appointment, reschedule_appointment tools
        # It can handle everything without this expensive pre-processing
        if SKIP_APPOINTMENT_DETECTION:
            print("⚡ Skipping ALL appointment detection - LLM handles everything with native tools")
            likely_appointment = False
        
        if likely_appointment:
            print(f"🔍 APPOINTMENT DETECTION TRIGGERED - user_text: '{user_text}'")
            
            # CRITICAL: During reschedule/cancel confirmation step, don't pass full conversation history
            # to avoid AI hallucinating times from previous messages
            reschedule_awaiting_confirmation = (
                call_state.get("reschedule_found_appointment") and 
                not call_state.get("reschedule_name_confirmed")
            )
            
            cancel_awaiting_confirmation = (
                call_state.get("cancel_found_appointment") and 
                not call_state.get("cancel_name_confirmed")
            )
            
            cancel_awaiting_final = (
                call_state.get("cancel_found_appointment") and
                call_state.get("cancel_name_confirmed") and
                not call_state.get("cancel_final_asked")
            )
            
            if reschedule_awaiting_confirmation or cancel_awaiting_confirmation or cancel_awaiting_final:
                if reschedule_awaiting_confirmation:
                    print(f"   ⚠️ In reschedule confirmation - analyzing only current message to avoid hallucination")
                elif cancel_awaiting_confirmation:
                    print(f"   ⚠️ In cancel confirmation - analyzing only current message to avoid hallucination")
                else:
                    print(f"   ⚠️ In cancel final confirmation - analyzing only current message to avoid hallucination")
                # Only analyze current message for confirmation, don't look at full history
                appointment_details = AppointmentDetector.extract_appointment_details(
                    text=user_text,
                    conversation_history=None  # Don't pass history during confirmation
                )
            else:
                # Pass full conversation history for better context understanding
                appointment_details = AppointmentDetector.extract_appointment_details(
                    text=user_text,
                    conversation_history=messages
                )
            
            intent = appointment_details["intent"]
            print(f"🔍 INTENT DETECTED: {intent}, details: {appointment_details}")
            
            # POST-BOOKING COOLDOWN: If we just made a booking, be extra careful about reschedule detection
            # This prevents false reschedule detection when user says "great", "thanks", etc. after booking
            if intent == AppointmentIntent.RESCHEDULE and in_post_booking_cooldown:
                if not call_state.get("reschedule_active"):
                    # Check if user explicitly said "reschedule" or similar
                    explicit_reschedule_words = ["reschedule", "change my appointment", "move my appointment", "different time for my appointment"]
                    user_explicitly_wants_reschedule = any(word in user_text.lower() for word in explicit_reschedule_words)
                    
                    if not user_explicitly_wants_reschedule:
                        # User probably just acknowledged the booking - don't start reschedule flow
                        print(f"[COOLDOWN] Ignoring potential false reschedule detection - user said: '{user_text}'")
                        intent = AppointmentIntent.NONE
                        appointment_details["intent"] = AppointmentIntent.NONE
        
            # Print the detected action
            if intent != AppointmentIntent.NONE:
                print_appointment_action(intent, appointment_details)
                
                # Check if we're in an active reschedule flow
                in_reschedule_flow = (call_state.get("reschedule_active") or
                                     call_state.get("reschedule_found_appointment") or 
                                     call_state.get("reschedule_name_confirmed") or 
                                     call_state.get("reschedule_final_asked"))
                
                # Update state with any new information gathered
                # Don't store customer_name during reschedule - we get it from the appointment
                if appointment_details.get("customer_name") and not in_reschedule_flow:
                    call_state["customer_name"] = appointment_details["customer_name"]
                
                # Handle datetime updates intelligently - combine previous date with new time if needed
                # FIRST: Check if user said "tomorrow" or "today" even if OpenAI didn't extract it
                text_lower = user_text.lower()
                if 'tomorrow' in text_lower and not appointment_details.get("datetime"):
                    print(f"🔄 Detected 'tomorrow' in query - updating state")
                    appointment_details["datetime"] = "tomorrow"
                    call_state["datetime"] = "tomorrow"
                elif 'today' in text_lower and not appointment_details.get("datetime") and not call_state.get("datetime"):
                    print(f"🔄 Detected 'today' in query - updating state")
                    appointment_details["datetime"] = "today"
                    call_state["datetime"] = "today"
                
                # CRITICAL FIX: Extract time directly from current user message
                # This catches cases where user says "12pm" but OpenAI returns "tomorrow" (the previous date)
                time_extraction_patterns = [
                    r'\b(\d{1,2})\s*(pm|am)\b',  # "12 pm", "1pm", "2am"
                    r'\b(\d{1,2}):(\d{2})\s*(pm|am)\b',  # "1:30 pm", "12:00pm"
                ]
                extracted_time = None
                for pattern in time_extraction_patterns:
                    time_match = re.search(pattern, user_text, re.IGNORECASE)
                    if time_match:
                        # Reconstruct the time string
                        if len(time_match.groups()) == 2:  # hour + am/pm
                            extracted_time = f"{time_match.group(1)}{time_match.group(2)}"
                        else:  # hour + minute + am/pm
                            extracted_time = f"{time_match.group(1)}:{time_match.group(2)}{time_match.group(3)}"
                        print(f"🕐 Extracted time from user message: '{extracted_time}'")
                        break
                
                # If no time found with am/pm, check for standalone numbers in time-choosing context
                # Look for patterns like "I'll do 12", "can I do 3", "how about 2"
                if not extracted_time and call_state.get("datetime"):
                    # Check if assistant just offered time slots (last assistant message)
                    if len(messages) >= 2 and messages[-2].get("role") == "assistant":
                        last_assistant_msg = (messages[-2].get("content") or "").lower()
                        # If assistant mentioned available times, user is likely choosing one
                        if any(phrase in last_assistant_msg for phrase in ["available", "works best", "which time", "what time"]):
                            # Look for standalone numbers that could be hours
                            # Match phrases like "do 12", "take 3", "book 10", "at 2"
                            time_choice_match = re.search(r'\b(?:do|take|book|get|at|for)\s+(\d{1,2})\b', user_text, re.IGNORECASE)
                            if time_choice_match:
                                hour = int(time_choice_match.group(1))
                                # Infer am/pm based on business hours (9am-5pm)
                                # 12 = noon (12pm), 1-5 = pm, 9-11 = am
                                if hour == 12:
                                    extracted_time = "12pm"
                                elif 1 <= hour <= 5:
                                    extracted_time = f"{hour}pm"
                                elif 9 <= hour <= 11:
                                    extracted_time = f"{hour}am"
                                elif hour <= 8:
                                    # Ambiguous - but in business context, likely pm
                                    extracted_time = f"{hour}pm"
                                
                                if extracted_time:
                                    print(f"🕐 Inferred time from context: '{extracted_time}' (user said: '{user_text}')")
                            else:
                                # Try simpler match - just a number by itself in short message
                                simple_number_match = re.search(r'\b(\d{1,2})\b', user_text)
                                if simple_number_match and len(user_text.split()) <= 6:
                                    hour = int(simple_number_match.group(1))
                                    if 1 <= hour <= 12:  # Valid clock hour
                                        # Apply same business hours logic
                                        if hour == 12:
                                            extracted_time = "12pm"
                                        elif 1 <= hour <= 5:
                                            extracted_time = f"{hour}pm"
                                        elif 9 <= hour <= 11:
                                            extracted_time = f"{hour}am"
                                        
                                        if extracted_time:
                                            print(f"🕐 Inferred time from simple number: '{extracted_time}' (user said: '{user_text}')")
                
                # If we found a time in the message and have a date in state, combine them
                if extracted_time and call_state.get("datetime"):
                    previous_datetime = call_state["datetime"]
                    # Remove any existing time from previous datetime
                    date_only = re.sub(r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b', '', previous_datetime, flags=re.IGNORECASE).strip()
                    combined_datetime = f"{date_only} {extracted_time}"
                    call_state["datetime"] = combined_datetime
                    print(f"✅ Combined date '{date_only}' with extracted time '{extracted_time}' -> '{combined_datetime}'")
                elif appointment_details.get("datetime"):
                    new_datetime_str = appointment_details["datetime"]
                    
                    # Check if user provided just a time (e.g., "1pm", "2:30pm") without a date
                    # If we already have a date in state, combine them
                    time_only_patterns = [
                        r'^\d{1,2}\s*(pm|am)$',  # "1pm", "2am"
                        r'^\d{1,2}:\d{2}\s*(pm|am)$',  # "1:30pm"
                    ]
                    
                    is_time_only = any(re.match(pattern, new_datetime_str.strip().lower()) for pattern in time_only_patterns)
                    
                    if is_time_only and call_state.get("datetime"):
                        # User provided just time, we have a previous date - REPLACE old time with new time
                        previous_datetime = call_state["datetime"]
                        print(f"🔄 Combining previous date '{previous_datetime}' with new time '{new_datetime_str}'")
                        
                        # Extract just the date portion (remove any existing time)
                        # Look for common date patterns: "tomorrow", "today", "december 29", etc.
                        date_only = previous_datetime.lower()
                        # Remove existing times from the date string
                        date_only = re.sub(r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b', '', date_only, flags=re.IGNORECASE).strip()
                        
                        combined_datetime = f"{date_only} {new_datetime_str}"
                        call_state["datetime"] = combined_datetime
                        print(f"✅ Combined datetime (time replaced): '{combined_datetime}'")
                    else:
                        # Either a full date+time or a new date reference
                        call_state["datetime"] = new_datetime_str
                
                if appointment_details.get("service_type"):
                    call_state["service_type"] = appointment_details["service_type"]
                
                # Extract phone number from user message if not already captured
                if not call_state.get("phone_number"):
                    # Look for phone numbers in various formats
                    phone_patterns = [
                        r'\b\d{10}\b',  # 0851234567
                        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # 085-123-4567
                        r'\b\+\d{1,3}[-.\s]?\d{9,10}\b',  # +353851234567
                        r'\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b'  # (085) 123-4567
                    ]
                    for pattern in phone_patterns:
                        match = re.search(pattern, user_text)
                        if match:
                            phone_number = match.group(0).replace('-', '').replace('.', '').replace(' ', '').replace('(', '').replace(')', '')
                            call_state["phone_number"] = phone_number
                            # For web chat (caller_phone is None), auto-confirm phone since user typed it
                            if caller_phone is None:
                                call_state["phone_confirmed"] = True
                                print(f"📱 Phone number detected and auto-confirmed (web chat): {phone_number}")
                            else:
                                # For phone calls, don't auto-confirm - ask them to confirm
                                call_state["phone_confirmed"] = False
                                call_state["phone_needs_confirmation"] = True
                                print(f"📱 Phone number detected from speech: {phone_number} - needs confirmation")
                                
                                # Add system message asking for confirmation
                                confirm_msg = f"[SYSTEM: User provided phone number {phone_number}. Ask them to confirm: 'Just to confirm, that's {phone_number}, correct?']"
                                messages.append({"role": "system", "content": confirm_msg})
                            break
                    
                    # If user declined caller_phone but didn't provide a number yet, remind them
                    if caller_phone and call_state.get("caller_phone_declined") and not call_state.get("phone_number"):
                        if not call_state.get("asked_for_alternate_phone"):
                            # Add a reminder to ask for their preferred number
                            call_state["asked_for_alternate_phone"] = True
                            reminder_msg = "[SYSTEM: User declined to use caller phone. Ask: 'What's the best phone number to reach you?' DO NOT ask them to say it - they can simply provide it in text or you can collect it via SMS link if needed.]"
                            messages.append({"role": "system", "content": reminder_msg})
                
                # Determine if we should process the booking
                should_process = False
                
                # Check if we're in an active reschedule flow - if so, ignore BOOK intents
                in_reschedule_flow = (call_state.get("reschedule_found_appointment") or 
                                     call_state.get("reschedule_name_confirmed") or 
                                     call_state.get("reschedule_final_asked"))
                
                if in_reschedule_flow and intent == AppointmentIntent.BOOK:
                    print("⚠️ Ignoring BOOK intent - currently in active RESCHEDULE flow")
                    intent = AppointmentIntent.RESCHEDULE  # Force it back to reschedule
                    
                    # CRITICAL: Combine datetime and new_datetime if AI split them (e.g., "tomorrow" + "9am")
                    datetime_part = appointment_details.get("datetime", "")
                    new_datetime_part = appointment_details.get("new_datetime", "")
                    
                    if datetime_part and new_datetime_part:
                        # AI split the time - combine them (e.g., "tomorrow" + "9am" = "tomorrow at 9am")
                        combined_new_time = f"{datetime_part} at {new_datetime_part}"
                        appointment_details["new_datetime"] = combined_new_time
                        print(f"🔄 Combined datetime parts for reschedule: '{datetime_part}' + '{new_datetime_part}' = '{combined_new_time}'")
                    elif datetime_part and not new_datetime_part:
                        # Transfer datetime to new_datetime for reschedule logic
                        appointment_details["new_datetime"] = datetime_part
                        print(f"🔄 Transferred datetime to new_datetime for reschedule: {appointment_details['new_datetime']}")
                
                # Also protect against QUERY intent being treated as BOOK during reschedule
                if in_reschedule_flow and intent == AppointmentIntent.QUERY:
                    print("📋 QUERY during RESCHEDULE flow - this is for checking new appointment times")
                    # Don't change intent, but clear any extracted name to prevent booking logic
                    # The QUERY will check availability but won't trigger booking
                
                # CRITICAL FIX: Handle NONE intent during reschedule flow
                # When user says "yes" or provides simple confirmations, intent may be NONE
                # but we need to continue with the reschedule flow
                if intent == AppointmentIntent.NONE and in_reschedule_flow:
                    # Check if we're waiting for final confirmation (after availability checked)
                    final_asked = call_state.get("reschedule_final_asked", False)
                    name_confirmed = call_state.get("reschedule_name_confirmed", False)
                    found_appointment = call_state.get("reschedule_found_appointment")
                    new_datetime = call_state.get("reschedule_new_datetime")
                    
                    if final_asked and name_confirmed and found_appointment and new_datetime:
                        # Use AI to detect confirmation (more flexible than word lists)
                        is_confirmed = is_affirmative_response(user_text, context="reschedule confirmation") and len(user_text.split()) <= 6
                        
                        if is_confirmed:
                            print("🔄 NONE intent detected but user is confirming reschedule - forcing to RESCHEDULE intent")
                            intent = AppointmentIntent.RESCHEDULE
                            # Populate appointment_details from state
                            appointment_details["customer_name"] = call_state.get("reschedule_customer_name")
                            appointment_details["datetime"] = call_state.get("reschedule_found_appointment", {}).get('start', {}).get('dateTime', '')
                            appointment_details["new_datetime"] = new_datetime
                            print(f"📋 Populated appointment_details for reschedule: old={appointment_details['datetime']}, new={appointment_details['new_datetime']}")
                    # CRITICAL: Also check if we're at the name confirmation stage
                    # User saying "yes" to confirm their name → force RESCHEDULE intent
                    elif found_appointment and not name_confirmed:
                        # Check if this is an affirmative response
                        is_affirmative = is_affirmative_response(user_text, context="appointment confirmation") and len(user_text.split()) <= 6
                        
                        if is_affirmative:
                            print("🔄 NONE intent detected but user confirming appointment name - forcing to RESCHEDULE intent")
                            intent = AppointmentIntent.RESCHEDULE
                            # Populate appointment_details from state
                            appointment_details["customer_name"] = call_state.get("reschedule_customer_name")
                            appointment_details["datetime"] = call_state.get("reschedule_found_appointment", {}).get('start', {}).get('dateTime', '')
                            appointment_details["new_datetime"] = new_datetime
                            print(f"📋 Populated appointment_details for name confirmation step: old={appointment_details['datetime']}, new={appointment_details['new_datetime']}")
                
                # CRITICAL FIX: Handle NONE intent during cancel flow (same issue as reschedule)
                in_cancel_flow = (call_state.get("cancel_active") or
                                call_state.get("cancel_found_appointment") is not None)
                if intent == AppointmentIntent.NONE and in_cancel_flow:
                    found_appointment = call_state.get("cancel_found_appointment")
                    name_confirmed = call_state.get("cancel_name_confirmed", False)
                    final_asked = call_state.get("cancel_final_asked", False)
                    cancel_time = call_state.get("cancel_found_appointment", {}).get('start', {}).get('dateTime', '')
                    
                    # Check if user is confirming at any stage
                    is_affirmative = is_affirmative_response(user_text, context="appointment confirmation") and len(user_text.split()) <= 6
                    
                    if is_affirmative and found_appointment:
                        print("🗑️ NONE intent detected but user confirming during cancel - forcing to CANCEL intent")
                        intent = AppointmentIntent.CANCEL
                        # Populate appointment_details from state
                        appointment_details["customer_name"] = call_state.get("cancel_customer_name")
                        appointment_details["datetime"] = cancel_time
                        print(f"📋 Populated appointment_details for cancel: {appointment_details['datetime']}")
                
                if intent == AppointmentIntent.BOOK:
                    # Mark that we're in an active booking flow
                    call_state["active_booking"] = True
                    call_state["gathering_started"] = True
                    
                    # Check if we've already booked in this session
                    if call_state["already_booked"]:
                        print("⚠️ Already booked in this session - ignoring duplicate booking attempt")
                        should_process = False
                    else:
                        # Store datetime in state if provided (LLM naturally handles corrections)
                        if appointment_details.get("datetime"):
                            if call_state.get("datetime") and call_state.get("datetime") != appointment_details["datetime"]:
                                print(f"✏️ Date/Time updated: old='{call_state.get('datetime')}', new='{appointment_details['datetime']}'")
                            call_state["datetime"] = appointment_details["datetime"]
                            print(f"📅 Stored datetime: {appointment_details['datetime']}")
                        
                        # Check if user is confirming using AI - more flexible than word lists
                        words = user_text.lower().split()
                        is_short = len(words) <= 6
                        
                        # Check if this is a contact confirmation (phone/email), not an appointment confirmation
                        is_contact_confirmation = False
                        if len(messages) >= 2 and messages[-2].get("role") == "assistant":
                            last_assistant_msg = messages[-2]["content"].lower()
                            if any(phrase in last_assistant_msg for phrase in ["on file with", "phone number", "email", "contact", "is that still correct", "number you're calling from"]):
                                is_contact_confirmation = True
                                print(f"🔍 Detected contact confirmation, not booking confirmation")
                        
                        # Use AI to detect confirmation (more flexible than word lists)
                        is_confirmation = is_short and is_affirmative_response(user_text, context="appointment booking") and not is_contact_confirmation
                        
                        # Use accumulated state for checking completeness
                        has_name = call_state["customer_name"] is not None
                        # DOB not required for trades - removed has_dob check
                        has_time = call_state["datetime"] is not None
                        has_service = call_state["service_type"] is not None
                        has_phone = call_state.get("phone_number") is not None
                        phone_confirmed = call_state.get("phone_confirmed", False)
                        
                        # Validate that the datetime includes a specific time (not just a date)
                        if has_time:
                            try:
                                parsed_dt = parse_datetime(call_state["datetime"])
                                if parsed_dt is None:
                                    # Date was provided without time - need to check if ANY slots available first
                                    has_time = False
                                    print(f"⚠️ Date without time detected - checking availability first")
                                    
                                    # Check if there are any available slots on this day
                                    from src.services.google_calendar import get_calendar_service
                                    calendar = get_calendar_service()
                                    if calendar:
                                        # Parse the date to check availability
                                        text_lower = call_state["datetime"].lower().strip()
                                        now = datetime.now()
                                        
                                        if text_lower == 'today':
                                            check_date = now.replace(hour=9, minute=0, second=0, microsecond=0)
                                        elif text_lower == 'tomorrow':
                                            check_date = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
                                        else:
                                            # Try to parse the date
                                            check_date = parse_datetime(call_state["datetime"] + " 9am")
                                        
                                        if check_date:
                                            available_slots = calendar.get_available_slots_for_day(check_date)
                                            
                                            if not available_slots or len(available_slots) == 0:
                                                # No slots available on this day - check if it's because we're past business hours
                                                if text_lower == 'today' and now.hour >= config.BUSINESS_HOURS_END:
                                                    # After business hours today
                                                    missing_time_msg = f"[SYSTEM: NO AVAILABLE SLOTS today because it's after business hours (we close at {config.BUSINESS_HOURS_END}:00 / {config.BUSINESS_HOURS_END - 12 if config.BUSINESS_HOURS_END > 12 else config.BUSINESS_HOURS_END} PM). You MUST tell the user: 'We don't work after {config.BUSINESS_HOURS_END - 12 if config.BUSINESS_HOURS_END > 12 else config.BUSINESS_HOURS_END} PM. Would you like to book for tomorrow or another day?' DO NOT say 'no slots today' - be specific about business hours.]"
                                                else:
                                                    # Fully booked on this day
                                                    missing_time_msg = f"[SYSTEM: NO AVAILABLE SLOTS on {call_state['datetime']}. You MUST tell the user: 'Unfortunately, we don't have any available appointments {call_state['datetime']}. Would you like to check another day?' DO NOT ask for a time - there are no slots available.]"
                                                messages.append({"role": "system", "content": missing_time_msg})
                                                print(f"❌ No slots available on {call_state['datetime']}")
                                            else:
                                                # Slots available - FIRST answer if user asked a question, then show times
                                                times_str = ', '.join([slot.strftime('%I:%M %p') for slot in available_slots[:5]])  # Show first 5
                                                
                                                # Check if user asked a question (can I, is it available, etc.)
                                                user_asked_question = any(phrase in user_text.lower() for phrase in ['can i', 'can we', 'is it', 'do you have', 'are you', 'could i', 'could we'])
                                                
                                                if user_asked_question:
                                                    # Answer YES first, then show times
                                                    missing_time_msg = f"[SYSTEM: The user ASKED if '{call_state['datetime']}' is available. Answer 'Yes!' or 'Absolutely!' first to confirm it's available. Then show the times: {times_str}. Example: 'Yes! I have {times_str} available. What time works best for you?']"
                                                else:
                                                    # Not a question, just show available times
                                                    missing_time_msg = f"[SYSTEM: The user provided a date ('{call_state['datetime']}') but NO TIME. Available times: {times_str}. You MUST tell them the available times and ask which one they prefer. Example: 'I have {times_str} available. Which works best for you?']"
                                                
                                                messages.append({"role": "system", "content": missing_time_msg})
                                                print(f"✅ Found {len(available_slots)} available slots on {call_state['datetime']}")
                                        else:
                                            # Couldn't parse date - just ask for time
                                            missing_time_msg = f"[SYSTEM: The user provided a date ('{call_state['datetime']}') but NO TIME. You MUST ask for a specific time. Say: 'What time works best for you on {call_state['datetime']}?' DO NOT proceed with booking until you have a specific time.]"
                                            messages.append({"role": "system", "content": missing_time_msg})
                                    else:
                                        # No calendar service - just ask for time
                                        missing_time_msg = f"[SYSTEM: The user provided a date ('{call_state['datetime']}') but NO TIME. You MUST ask for a specific time. Say: 'What time works best for you on {call_state['datetime']}?' DO NOT proceed with booking until you have a specific time.]"
                                        messages.append({"role": "system", "content": missing_time_msg})
                                        print(f"⚠️ Date without time detected - prompting for time")
                                else:
                                    # Successfully parsed - update state with parsed datetime for consistency
                                    print(f"✅ Successfully parsed datetime: {parsed_dt}")
                            except Exception as e:
                                print(f"⚠️ Error parsing datetime '{call_state['datetime']}': {e}")
                                # Try to extract just the time from the user's last message
                                time_match = re.search(r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b', user_text, re.IGNORECASE)
                                if time_match:
                                    time_str = time_match.group(0)
                                    print(f"🔍 Found time in message: {time_str}")
                                    # Try combining with previous date if available
                                    if call_state.get("datetime"):
                                        # Look for date in previous datetime string
                                        prev_datetime = call_state["datetime"]
                                        # Try to extract date part
                                        date_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\\s+\\d{1,2}', prev_datetime, re.IGNORECASE)
                                        if date_match:
                                            date_part = date_match.group(0)
                                            combined = f"{date_part} {time_str}"
                                            print(f"🔄 Attempting to combine: '{combined}'")
                                            try:
                                                test_parse = parse_datetime(combined)
                                                if test_parse:
                                                    call_state["datetime"] = combined
                                                    print(f"✅ Successfully combined and parsed: {test_parse}")
                                                    # Don't mark has_time as False - we fixed it!
                                                else:
                                                    has_time = False
                                            except:
                                                has_time = False
                                        else:
                                            has_time = False
                                    else:
                                        has_time = False
                                else:
                                    has_time = False
                        
                        # Check if user is confirming the phone number using AI
                        # Special handling: if caller_phone exists but phone not yet confirmed, check for yes/no response
                        if caller_phone and not call_state.get("phone_number") and not phone_confirmed:
                            # User is being asked if caller_phone is correct
                            if len(words) <= 5:
                                if is_affirmative_response(user_text, context="phone number"):
                                    # User said yes - use the caller's phone number
                                    call_state["phone_number"] = caller_phone
                                    call_state["phone_confirmed"] = True
                                    phone_confirmed = True
                                    has_phone = True
                                    print(f"✅ Caller phone number confirmed and set: {caller_phone}")
                                    
                                    # Add a system message to remind the LLM what info we already have
                                    collected_info = []
                                    if has_name:
                                        collected_info.append(f"Name: {call_state['customer_name']}")
                                    # DOB not shown in collected info
                                    collected_info.append(f"Phone: {caller_phone} (CONFIRMED)")
                                    
                                    reminder_msg = f"[SYSTEM: Phone confirmed as {caller_phone}. Information already collected: {', '.join(collected_info)}. DO NOT ask for any of these again. Now ask: 'How can I help you today?' or 'What brings you in?' to proceed with their request.]"
                                    messages.append({"role": "system", "content": reminder_msg})
                                    print(f"📋 Added reminder message about collected info")
                                elif user_text.lower() in ["no", "nope", "nah", "not that one", "different number", "no that's not it"]:
                                    # User said no - they want to provide a different number
                                    call_state["caller_phone_declined"] = True
                                    print(f"❌ User declined caller phone {caller_phone}, asking for alternate")
                                    
                                    decline_msg = "[SYSTEM: User wants to use a different phone number. Acknowledge with 'No problem!' and ask: 'What number would you like me to use instead?' Wait for them to provide the number - DO NOT ask them to speak it digit by digit.]"
                                    messages.append({"role": "system", "content": decline_msg})
                        elif has_phone and not phone_confirmed:
                            # Use AI to detect phone confirmation (for manually entered phone)
                            if len(words) <= 5 and is_affirmative_response(user_text, context="phone number"):
                                call_state["phone_confirmed"] = True
                                phone_confirmed = True
                                print(f"✅ Phone number confirmed: {call_state['phone_number']}")
                                
                                # Add a system message to remind the LLM what info we already have
                                collected_info = []
                                if has_name:
                                    collected_info.append(f"Name: {call_state['customer_name']}")
                                # DOB not shown in collected info
                                if has_phone:
                                    collected_info.append(f"Phone: {call_state['phone_number']} (CONFIRMED)")
                                
                                reminder_msg = f"[SYSTEM: Phone confirmed. Information already collected: {', '.join(collected_info)}. DO NOT ask for any of these again. Now ask: 'How can I help you today?' or 'What brings you in?' to proceed with their request.]"
                                messages.append({"role": "system", "content": reminder_msg})
                                print(f"📋 Added reminder message about collected info")
                        
                        # For web chat without phone: allow booking if user confirms appointment details
                        # Only require phone for phone calls (when caller_phone is provided)
                        phone_requirement_met = phone_confirmed or (not has_phone and caller_phone is None)
                        
                        print(f"🔍 DEBUG BOOKING CHECK:")
                        print(f"   has_name={has_name}, has_time={has_time}")
                        print(f"   has_phone={has_phone}, phone_confirmed={phone_confirmed}, caller_phone={caller_phone}")
                        print(f"   phone_requirement_met={phone_requirement_met}, is_confirmation={is_confirmation}")
                        
                        # Only book if we have ALL required info: name, time, phone (confirmed), and final confirmation
                        should_process = has_time and has_name and phone_requirement_met and is_confirmation
                        
                        if should_process:
                            print("✅ All booking details collected - proceeding with booking")
                            # Add system message to prevent premature confirmation
                            system_check_msg = "[SYSTEM: User has confirmed their details. System is now checking calendar availability (this happens instantly in the background). DO NOT mention checking, DO NOT say 'let me check', 'one moment', or any delay phrases. Simply wait silently for the system response about availability.]"
                            messages.append({"role": "system", "content": system_check_msg})
                            # Merge state into appointment_details for booking
                            appointment_details["customer_name"] = call_state["customer_name"]
                            # DOB field removed - not needed for trades
                            appointment_details["datetime"] = call_state["datetime"]
                            appointment_details["service_type"] = call_state["service_type"] or "General"
                            appointment_details["phone_number"] = call_state.get("phone_number")
                        else:
                            # Check what's missing and guide the LLM
                            # DOB check removed - not required for trades business
                            if not has_phone and caller_phone:
                                # Missing phone for phone call
                                missing_info_msg = f"[SYSTEM ALERT: MISSING PHONE NUMBER. You MUST collect or confirm the customer's phone number. Ask: 'Is the phone number you're calling from the one you want to use for this appointment?' DO NOT proceed without phone confirmation.]"
                                messages.append({"role": "system", "content": missing_info_msg})
                                print("⚠️ MISSING PHONE - cannot proceed with booking")
                            elif has_time and has_name and phone_requirement_met and not is_confirmation:
                                # Have all info, just need final confirmation
                                try:
                                    req_time = parse_datetime(call_state["datetime"])
                                    prevent_hallucination = f"[SYSTEM: DO NOT make up availability information or say times are busy/available. You do NOT yet have calendar data. Simply confirm the appointment details with the customer: '{call_state['customer_name']}' on '{req_time.strftime('%B %d at %I:%M %p')}' for '{call_state.get('service_type', 'appointment')}'. Ask 'Is that correct?' to get final confirmation. DO NOT say they're booked or all set yet - you must check availability first after they confirm.]"
                                    messages.append({"role": "system", "content": prevent_hallucination})
                                except Exception as e:
                                    print(f"⚠️ Error parsing datetime for confirmation: {e}")
                
                # Handle RESCHEDULE intent
                elif intent == AppointmentIntent.RESCHEDULE:
                    # Mark that we're in an active reschedule flow IMMEDIATELY
                    if not call_state.get("reschedule_active"):
                        call_state["reschedule_active"] = True
                        print(f"🔄 Starting RESCHEDULE flow - setting reschedule_active flag")
                    
                    print(f"🔄 RESCHEDULE FLOW ACTIVE")
                    
                    # For rescheduling, NEW FLOW:
                    # 1. Get old time, find appointment by old time ONLY
                    # 2. Extract customer name from found appointment
                    # 3. Ask user to confirm this is their appointment
                    # 4. Get new time
                    # 5. Confirm and reschedule
                    
                    old_time = appointment_details.get("datetime")
                    new_time = appointment_details.get("new_datetime")
                    customer_name = appointment_details.get("customer_name")
                    
                    # Check for name confirmation state (stored after we find appointment)
                    found_appointment = call_state.get("reschedule_found_appointment")
                    name_confirmed = call_state.get("reschedule_name_confirmed", False)
                    
                    # NEW: Check if user can't remember their appointment time
                    cant_remember_indicators = ['dont remember', "don't remember", 'cant remember', "can't remember", 
                                              'forgot', 'not sure', "i don't know", "don't recall", "can't recall"]
                    user_cant_remember = any(indicator in user_text.lower() for indicator in cant_remember_indicators)
                    
                    # Store flag if user says they can't remember
                    if user_cant_remember:
                        call_state["user_cant_remember_time"] = True
                    
                    # Check if user previously said they can't remember AND we just identified them
                    # This handles the flow: "can't remember" -> name -> phone/email -> now look up their appointment
                    if (call_state.get("user_cant_remember_time") and 
                        call_state.get("caller_identified") and 
                        customer_name and 
                        not found_appointment and
                        not user_cant_remember):  # Don't double-process on the "can't remember" message itself
                        print(f"🔍 User previously said can't remember + now identified -> looking up appointments for {customer_name}")
                        user_cant_remember = True  # Trigger the lookup logic below
                    
                    # If user can't remember and we don't have their name yet, ask for it
                    if user_cant_remember and not old_time and not found_appointment:
                        if not customer_name:
                            # Ask for name to look up appointment
                            messages.append({"role": "system", "content": RESCHEDULE_MESSAGES["cant_remember_ask_name"]})
                            print(f"❓ User can't remember appointment time, asking for their name")
                            should_process = False
                        else:
                            # We have the name, find their next future appointment
                            print(f"🔍 User can't remember time but we have name: {customer_name}")
                            try:
                                from src.services.google_calendar import get_calendar_service
                                calendar = get_calendar_service()
                                
                                if not calendar:
                                    # Calendar disabled
                                    error_msg = "[SYSTEM: Calendar service is currently disabled. Inform the user that rescheduling is not available at the moment.]"
                                    messages.append({"role": "system", "content": error_msg})
                                    call_state.pop("reschedule_active", None)
                                    should_process = False
                                else:
                                    # Find next future appointment by name only
                                    event = calendar.find_next_appointment_by_name(customer_name)
                                
                                    if event:
                                        # Extract appointment details
                                        event_start_str = event.get('start', {}).get('dateTime')
                                        if event_start_str:
                                            event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                                            
                                            # Store found appointment
                                            call_state["reschedule_found_appointment"] = event
                                            call_state["reschedule_customer_name"] = customer_name
                                            
                                            # Ask for confirmation
                                            time_display = event_start.strftime('%B %d at %I:%M %p')
                                            confirm_msg = RESCHEDULE_MESSAGES["confirm_name"](
                                                customer_name, 
                                                time_display
                                            )
                                            messages.append({"role": "system", "content": confirm_msg})
                                            print(f"✅ Found next appointment for {customer_name} at {time_display}, asking for confirmation")
                                            should_process = False
                                    else:
                                        # No future appointments found
                                        no_appt_msg = f"[SYSTEM: I couldn't find any upcoming appointments for {customer_name}. Tell them politely and ask if they'd like to book a new appointment instead.]"
                                        messages.append({"role": "system", "content": no_appt_msg})
                                        print(f"❌ No future appointments found for {customer_name}")
                                        # Clean up state
                                        call_state.pop("reschedule_active", None)
                                        should_process = False
                            except Exception as e:
                                print(f"❌ Error finding appointment by name: {e}")
                                import traceback
                                traceback.print_exc()
                                should_process = False
                    
                    # FALLBACK: If OpenAI didn't extract new_time, try regex extraction
                    elif not new_time and (name_confirmed or found_appointment):
                        # User might be providing new time after name confirmation
                        time_patterns = [
                            r'\b(\d{1,2})\s*(pm|am)\b',  # "10 am", "10am"
                            r'\b(\d{1,2}):(\d{2})\s*(pm|am)\b',  # "10:30 am"
                        ]
                        for pattern in time_patterns:
                            match = re.search(pattern, user_text, re.IGNORECASE)
                            if match:
                                if len(match.groups()) == 2:  # hour + am/pm
                                    new_time = f"{match.group(1)}{match.group(2)}"
                                else:  # hour + minute + am/pm
                                    new_time = f"{match.group(1)}:{match.group(2)}{match.group(3)}"
                                print(f"🔄 Extracted new time via regex fallback: '{new_time}'")
                                appointment_details["new_datetime"] = new_time
                                break
                    
                    # Store new_datetime in state if provided (for query lookups)
                    if new_time:
                        call_state["reschedule_new_datetime"] = new_time
                        print(f"💾 Stored new_datetime in reschedule state: {new_time}")
                    
                    # Use utility function to check if time is vague
                    is_vague_time = is_time_vague(new_time)
                    
                    print(f"🔍 RESCHEDULE DEBUG: appointment_details = {appointment_details}")
                    print(f"🔍 RESCHEDULE DEBUG: old_time = '{old_time}', new_time = '{new_time}'")
                    print(f"🔍 RESCHEDULE STATE: found_appointment={bool(found_appointment)}, name_confirmed={name_confirmed}, is_vague_time={is_vague_time}")
                    
                    # Step 1: If we have old_time but haven't found appointment yet, find it
                    if old_time and not found_appointment:
                        print(f"🔍 Step 1: Finding appointment by old time '{old_time}'")
                        print(f"   📊 State check: found_appointment={bool(found_appointment)}, name_confirmed={name_confirmed}")
                        try:
                            from src.services.google_calendar import get_calendar_service
                            calendar = get_calendar_service()
                            
                            if not calendar:
                                # Calendar disabled
                                error_msg = "[SYSTEM: Calendar service is currently disabled. Inform the user that rescheduling is not available at the moment.]"
                                messages.append({"role": "system", "content": error_msg})
                                call_state.pop("reschedule_active", None)
                                should_process = False
                            else:
                                parsed_old_time = parse_datetime(old_time)
                                
                                if parsed_old_time:
                                    # Find appointment by TIME ONLY (no name required)
                                    event = calendar.find_appointment_by_details(customer_name=None, appointment_time=parsed_old_time)
                                
                                    if event:
                                        # Extract customer name from the appointment
                                        event_summary = event.get('summary', '')
                                        # Parse name from summary (format: "Service - CustomerName" or just "CustomerName")
                                        if ' - ' in event_summary:
                                            extracted_name = event_summary.split(' - ')[-1].strip()
                                        else:
                                            # Try to extract from "between X and Y" format
                                            between_match = re.search(r'between\s+([^and]+)\s+and', event_summary, re.IGNORECASE)
                                            if between_match:
                                                extracted_name = between_match.group(1).strip()
                                            else:
                                                extracted_name = event_summary.strip()
                                        
                                        # Store found appointment and extracted name in state
                                        call_state["reschedule_found_appointment"] = event
                                        call_state["reschedule_customer_name"] = extracted_name
                                        
                                        # Ask for name confirmation using config
                                        time_display = parsed_old_time.strftime('%B %d at %I:%M %p') if parsed_old_time else 'the appointment time'
                                        confirm_msg = RESCHEDULE_MESSAGES["confirm_name"](
                                            extracted_name, 
                                            time_display
                                        )
                                        messages.append({"role": "system", "content": confirm_msg})
                                        print(f"✅ Found appointment for {extracted_name}, asking for confirmation")
                                        should_process = False
                                    else:
                                        # No appointment found at that time - use config
                                        time_display = parsed_old_time.strftime('%B %d at %I:%M %p') if parsed_old_time else 'that time'
                                        not_found_msg = RESCHEDULE_MESSAGES["not_found"](time_display)
                                        messages.append({"role": "system", "content": not_found_msg})
                                        print(f"❌ No appointment found at {time_display}")
                                        should_process = False
                                else:
                                    print(f"⚠️ Could not parse old time: {old_time}")
                                    should_process = False
                        except Exception as e:
                            print(f"❌ Error finding appointment: {e}")
                            should_process = False
                    
                    # Step 2: Check for name confirmation (AI-driven)
                    elif found_appointment and not name_confirmed:
                        print(f"🔍 Checking name confirmation - user said: '{user_text}'")
                        
                        # Check for context-aware confirmation
                        text_lower = user_text.lower().strip()
                        
                        # Check if this is a conversational reference to a recent appointment
                        is_recent_appointment_reference = any(phrase in text_lower for phrase in [
                            'just booked', 'just made', 'just scheduled', 'i just', 
                            'the one i', 'appointment i', 'that one', 'the appointment',
                            'that appointment', 'this appointment'
                        ])
                        
                        # Use AI for affirmative detection (more flexible than word lists)
                        is_affirmative = is_affirmative_response(user_text, context="appointment confirmation") and len(user_text.split()) <= 6
                        
                        # If user is clearly referencing the appointment contextually, treat as confirmation
                        if is_affirmative or is_recent_appointment_reference:
                            call_state["reschedule_name_confirmed"] = True
                            customer_name = call_state.get("reschedule_customer_name")
                            print(f"   ✅ Name confirmed: {customer_name}")
                            
                            # CRITICAL: Check stored state for new_time, not just current extraction
                            # User may have provided new time in initial request
                            stored_new_time = call_state.get("reschedule_new_datetime")
                            if stored_new_time:
                                new_time = stored_new_time
                                print(f"   📋 Using stored new_time from state: {new_time}")
                            
                            # Check if we have new time that's different
                            has_new_time = new_time and not is_time_vague(new_time)
                            times_different = are_times_different(old_time, new_time, parse_datetime) if has_new_time else False
                            
                            if has_new_time and times_different:
                                print(f"   🔍 Times are different - proceeding with reschedule")
                            
                            # Ask for new time if not provided or if same as old
                            if not has_new_time or not times_different:
                                messages.append({"role": "system", "content": RESCHEDULE_MESSAGES["ask_new_time"]})
                                print(f"✅ Name confirmed, asking for new time (has_new={has_new_time}, different={times_different})")
                                should_process = False
                            else:
                                # We already have new time, proceed with reschedule IMMEDIATELY
                                # CRITICAL: Set should_process=True and skip_llm_response=True to prevent
                                # the LLM from checking availability and making false promises
                                print(f"✅ Name confirmed, we have new time, proceeding with reschedule IMMEDIATELY")
                                try:
                                    old_dt = parse_datetime(old_time)
                                    
                                    # Check if only time provided (no date in new_time_reference)
                                    has_date = has_date_indicator(new_time)
                                    
                                    # CRITICAL FIX: If no date in new_time, combine with old date BEFORE parsing
                                    if not has_date:
                                        # Only time provided, so new date should be same as old
                                        combined_time_text = old_dt.strftime('%A') + ' ' + new_time
                                        print(f"🔄 Same-day reschedule detected: combining '{old_dt.strftime('%A')}' + '{new_time}' -> '{combined_time_text}'")
                                        new_dt = parse_datetime(combined_time_text)
                                        display_new_time = old_dt.strftime('%B %d at ') + new_dt.strftime('%I:%M %p')
                                    else:
                                        new_dt = parse_datetime(new_time)
                                        display_new_time = new_dt.strftime('%B %d at %I:%M %p')
                                    
                                    # Store display time for use in success message after callback
                                    call_state["reschedule_final_asked"] = True
                                    call_state["reschedule_display_time"] = display_new_time
                                    call_state["skip_llm_response"] = True  # CRITICAL: Skip LLM to go directly to callback
                                    
                                    # Set the details for the callback
                                    appointment_details["customer_name"] = customer_name
                                    appointment_details["datetime"] = old_time
                                    appointment_details["new_datetime"] = new_time
                                    should_process = True
                                    print(f"🔄 EXECUTING RESCHEDULE: {customer_name} from {old_time} to {new_time}")
                                except Exception as e:
                                    print(f"⚠️ Error creating confirmation message: {e}")
                                    should_process = False
                        else:
                            # User's response was not clearly affirmative
                            # BUT check if they provided a NEW TIME (implicit confirmation)
                            print(f"⚠️ Response not clearly affirmative: '{user_text}'")
                            
                            # Check if user is explicitly saying this is NOT their appointment
                            negative_indicators = ['no', 'not me', 'wrong', 'different', 'someone else', 'not mine']
                            is_clearly_negative = any(phrase in text_lower for phrase in negative_indicators)
                            
                            if is_clearly_negative:
                                # Clear negative - ask for correct name
                                messages.append({"role": "system", "content": RESCHEDULE_MESSAGES["name_mismatch"]})
                                print(f"❌ User clearly indicated wrong appointment, asking for correct customer name")
                                # Reset reschedule state
                                call_state.pop("reschedule_found_appointment", None)
                                call_state.pop("reschedule_customer_name", None)
                                should_process = False
                            elif new_time and not is_vague_time:
                                # User provided a specific new time - implicit confirmation!
                                print(f"✅ User provided new time during name confirmation - treating as implicit 'yes'")
                                call_state["reschedule_name_confirmed"] = True
                                customer_name = call_state.get("reschedule_customer_name")
                                
                                # Proceed with reschedule
                                try:
                                    old_dt = parse_datetime(old_time) if old_time else None
                                    if not old_dt:
                                        print(f"⚠️ Could not parse old_time '{old_time}' - skipping implicit confirmation")
                                        should_process = False
                                    else:
                                        # CRITICAL FIX: Check if new_time has a date BEFORE parsing
                                        # If it's just a time (e.g., "1pm", "same day"), combine with old date first
                                        has_date = has_date_indicator(new_time)
                                        if not has_date:
                                            # Combine old date with new time for "same day" reschedules
                                            combined_time_text = old_dt.strftime('%A') + ' ' + new_time
                                            print(f"🔄 Same-day reschedule detected: combining '{old_dt.strftime('%A')}' + '{new_time}' -> '{combined_time_text}'")
                                            new_dt = parse_datetime(combined_time_text)
                                        else:
                                            new_dt = parse_datetime(new_time)
                                        
                                        if not new_dt:
                                            print(f"⚠️ Could not parse new_time '{new_time}' - asking user for clarification")
                                            messages.append({"role": "system", "content": RESCHEDULE_MESSAGES["ask_new_time"]})
                                            should_process = False
                                        elif not is_business_day(new_dt):
                                            # Check for closed day
                                            messages.append({"role": "system", "content": get_closed_day_message(new_dt)})
                                            print(f"❌ Attempted booking on closed day: {new_dt.strftime('%A')}")
                                            should_process = False
                                        else:
                                            if not has_date:
                                                display_new_time = old_dt.strftime('%B %d at ') + new_dt.strftime('%I:%M %p')
                                            else:
                                                display_new_time = new_dt.strftime('%B %d at %I:%M %p')
                                            
                                            call_state["reschedule_final_asked"] = True
                                            call_state["reschedule_display_time"] = display_new_time
                                            call_state["skip_llm_response"] = True
                                            
                                            appointment_details["customer_name"] = customer_name
                                            appointment_details["datetime"] = old_time
                                            appointment_details["new_datetime"] = new_time
                                            should_process = True
                                            print(f"✅ Proceeding with reschedule (implicit confirmation via new time)")
                                except Exception as e:
                                    print(f"⚠️ Error processing implicit confirmation: {e}")
                                    should_process = False
                            else:
                                # Ambiguous response - let AI interpret in context
                                customer_name = call_state.get("reschedule_customer_name")
                                old_time_formatted = call_state.get("reschedule_found_appointment", {}).get('start', {}).get('dateTime', '')
                                if old_time_formatted:
                                    old_dt = parse_datetime(old_time_formatted)
                                    old_time_display = old_dt.strftime('%B %d at %I:%M %p') if old_dt else (old_time if old_time else 'the appointment time')
                                else:
                                    old_time_display = old_time if old_time else 'the appointment time'
                                
                                context_msg = f"[SYSTEM: User said '{user_text}' in response to confirming the appointment for {customer_name} on {old_time_display}. Use conversation history to interpret their intent. If they're confirming, ask what time they'd like to reschedule to. If unclear or negative, ask for clarification.]"
                                messages.append({"role": "system", "content": context_msg})
                                print(f"🤖 Letting AI interpret ambiguous response in context")
                                should_process = False
                    
                    # Step 3: If name confirmed and we have new time, do final confirmation
                    elif found_appointment and name_confirmed and new_time and not is_vague_time:
                        print(f"🔍 Step 3: Final confirmation for reschedule")
                        customer_name = call_state.get("reschedule_customer_name")
                        
                        # Check if user provided a NEW time (accepting an alternative after slot unavailable)
                        last_attempted_time = call_state.get("reschedule_last_attempted_time")
                        
                        # Parse both times to compare properly
                        is_new_time_attempt = False
                        if last_attempted_time:
                            try:
                                last_dt = parse_datetime(last_attempted_time)
                                new_dt = parse_datetime(new_time)
                                is_new_time_attempt = (last_dt != new_dt)
                                if is_new_time_attempt:
                                    print(f"🔍 Time changed: {last_dt} -> {new_dt}")
                            except Exception as e:
                                print(f"⚠️ Could not compare times: {e}")
                                # If can't parse, check string equality
                                is_new_time_attempt = (last_attempted_time != new_time)
                        
                        if is_new_time_attempt:
                            # User is trying a different time after previous one was unavailable
                            # Proceed directly without additional confirmation
                            print(f"✅ User selected alternative time: {new_time} (previous attempt: {last_attempted_time})")
                            appointment_details["customer_name"] = customer_name
                            appointment_details["datetime"] = old_time
                            appointment_details["new_datetime"] = new_time
                            call_state["reschedule_last_attempted_time"] = new_time  # Track this attempt
                            should_process = True
                        else:
                            # Store this time attempt for future comparison
                            call_state["reschedule_last_attempted_time"] = new_time
                            
                            # Let AI determine if user is confirming (simpler, more flexible)
                            # Just provide context about what we're waiting for
                            need_confirmation = not call_state.get("reschedule_final_asked", False)
                            
                            if need_confirmation:
                                # Proceed directly with availability check - no LLM response needed
                                try:
                                    old_dt = parse_datetime(old_time)
                                    new_dt = parse_datetime(new_time)
                                    
                                    # Check for closed day
                                    if not is_business_day(new_dt):
                                        messages.append({"role": "system", "content": get_closed_day_message(new_dt)})
                                        print(f"❌ Attempted booking on closed day: {new_dt.strftime('%A')}")
                                        should_process = False
                                    else:
                                        has_date = has_date_indicator(new_time)
                                        
                                        if not has_date:
                                            display_new_time = old_dt.strftime('%B %d at ') + new_dt.strftime('%I:%M %p')
                                        else:
                                            display_new_time = new_dt.strftime('%B %d at %I:%M %p')
                                        
                                        # Store state and skip LLM response - callback will add result
                                        call_state["reschedule_final_asked"] = True
                                        call_state["reschedule_display_time"] = display_new_time
                                        call_state["skip_llm_response"] = True
                                        
                                        # Proceed with the reschedule
                                        appointment_details["customer_name"] = customer_name
                                        appointment_details["datetime"] = old_time
                                        appointment_details["new_datetime"] = new_time
                                        should_process = True
                                        print(f"✅ Proceeding with reschedule (Step 3 - new time provided)")
                                except Exception as e:
                                    print(f"⚠️ Error: {e}")
                                    should_process = False
                            else:
                                # Use AI to determine if user confirmed (more flexible than word lists)
                                is_confirmed = is_affirmative_response(user_text, context="appointment time") and len(user_text.split()) <= 6
                                
                                if is_confirmed:
                                    # User confirmed, proceed with availability check - skip LLM response
                                    try:
                                        new_dt = parse_datetime(new_time)
                                        
                                        # Check for closed day
                                        if not is_business_day(new_dt):
                                            messages.append({"role": "system", "content": get_closed_day_message(new_dt)})
                                            print(f"❌ Attempted booking on closed day: {new_dt.strftime('%A')}")
                                            should_process = False
                                        else:
                                            # Calculate display time if not already stored
                                            if not call_state.get("reschedule_display_time"):
                                                try:
                                                    old_dt = parse_datetime(old_time)
                                                    has_date = has_date_indicator(new_time)
                                                    if not has_date:
                                                        display_new_time = old_dt.strftime('%B %d at ') + new_dt.strftime('%I:%M %p')
                                                    else:
                                                        display_new_time = new_dt.strftime('%B %d at %I:%M %p')
                                                    call_state["reschedule_display_time"] = display_new_time
                                                except:
                                                    pass
                                            
                                            call_state["skip_llm_response"] = True  # Skip LLM response, callback will add result
                                            appointment_details["customer_name"] = customer_name
                                            appointment_details["datetime"] = old_time
                                            appointment_details["new_datetime"] = new_time
                                            should_process = True
                                            print("✅ User confirmed - proceeding with reschedule")
                                            # Don't clean up state yet - wait for callback to complete
                                    except Exception as e:
                                        print(f"⚠️ Error checking weekend: {e}")
                                        should_process = False
                                else:
                                    # Let AI re-ask or clarify
                                    should_process = False
                                    clarify_msg = "[SYSTEM: User's response unclear. Politely ask them to confirm if they want to proceed with the reschedule.]"
                                    messages.append({"role": "system", "content": clarify_msg})
                                    print(f"⏳ Asking AI to clarify with user")
                    
                    else:
                        # Still gathering information
                        should_process = False
                        if is_vague_time and name_confirmed:
                            vague_msg = "[SYSTEM: What time would you like to reschedule to?]"
                            messages.append({"role": "system", "content": vague_msg})
                            print(f"⚠️ Waiting for specific new time")
                        elif not old_time:
                            print(f"⚠️ Waiting for old appointment time")
                        print(f"⏳ Reschedule state - old_time: {bool(old_time)}, found: {bool(found_appointment)}, name_confirmed: {name_confirmed}, new_time: {bool(new_time and not is_vague_time)}")
                
                elif intent == AppointmentIntent.CANCEL:
                    # AI-driven cancellation - find appointment and confirm name first
                    cancel_time = appointment_details.get("datetime")
                    found_appointment = call_state.get("cancel_found_appointment")
                    name_confirmed = call_state.get("cancel_name_confirmed", False)
                    final_asked = call_state.get("cancel_final_asked", False)
                    customer_name = appointment_details.get("customer_name") or call_state.get("cancel_customer_name")
                    
                    print(f"\n{'='*80}")
                    print(f"🗑️  CANCEL INTENT DETECTED")
                    print(f"{'='*80}")
                    print(f"📝 User said: '{user_text}'")
                    print(f"📋 appointment_details: {appointment_details}")
                    print(f"🔍 cancel_time from appointment_details: '{cancel_time}'")
                    print(f"🔍 found_appointment: {bool(found_appointment)}")
                    print(f"{'='*80}\n")
                    
                    # CRITICAL: If we're in cancel flow and don't have an appointment yet, 
                    # look for time in the CURRENT user message immediately
                    if not found_appointment and not cancel_time:
                        # Try VERY aggressive extraction from user text
                        time_hints = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                                     'today', 'tomorrow', 'next week', 'this week', 'am', 'pm']
                        has_time_hint = any(hint in user_text.lower() for hint in time_hints)
                        
                        print(f"🔍 Checking for time hints in user text...")
                        print(f"   has_time_hint: {has_time_hint}")
                        
                        if has_time_hint:
                            print(f"✅ AGGRESSIVE FALLBACK: User text contains time hints: '{user_text}'")
                            try:
                                from src.utils.date_parser import parse_datetime
                                parsed_time = parse_datetime(user_text)
                                print(f"   parse_datetime returned: {parsed_time}")
                                if parsed_time:
                                    cancel_time = user_text  # Use the full text as the datetime reference
                                    appointment_details["datetime"] = cancel_time
                                    print(f"✅ AGGRESSIVE FALLBACK extracted cancel_time: '{cancel_time}' -> {parsed_time}")
                                else:
                                    print(f"⚠️  parse_datetime returned None for: '{user_text}'")
                            except Exception as e:
                                print(f"⚠️  AGGRESSIVE FALLBACK parse failed: {e}")
                                import traceback
                                traceback.print_exc()
                    
                    print(f"🗑️  CANCEL START: cancel_time='{cancel_time}', found={bool(found_appointment)}, name_confirmed={name_confirmed}")
                    
                    # Set cancel_active flag when starting cancel flow
                    if not call_state.get("cancel_active"):
                        call_state["cancel_active"] = True
                        print(f"🗑️  Starting CANCEL flow - setting cancel_active flag")
                    
                    # Check if user can't remember their appointment time
                    cant_remember_indicators = ['dont remember', "don't remember", 'cant remember', "can't remember", 
                                              'forgot', 'not sure', "i don't know", "don't recall", "can't recall"]
                    user_cant_remember = any(indicator in user_text.lower() for indicator in cant_remember_indicators)
                    
                    # Store flag if user says they can't remember
                    if user_cant_remember:
                        call_state["user_cant_remember_cancel_time"] = True
                    
                    # If user previously said they can't remember AND we just identified them, look up their appointment
                    if (call_state.get("user_cant_remember_cancel_time") and 
                        call_state.get("caller_identified") and 
                        customer_name and 
                        not found_appointment and
                        not user_cant_remember):  # Don't double-process on the "can't remember" message itself
                        print(f"🔍 User previously said can't remember + now identified -> looking up appointments for {customer_name}")
                        user_cant_remember = True  # Trigger the lookup logic below
                    
                    # If user can't remember and we don't have their name yet, ask for it
                    if user_cant_remember and not cancel_time and not found_appointment:
                        if not customer_name:
                            # Ask for name to look up appointment
                            msg = "[SYSTEM: The user can't remember their appointment time. Ask them: 'No problem! Can I get your name to look up your appointment?']"
                            messages.append({"role": "system", "content": msg})
                            print(f"❓ User can't remember appointment time, asking for their name")
                            should_process = False
                        else:
                            # We have the name, find their next future appointment
                            print(f"🔍 User can't remember time but we have name: {customer_name}")
                            try:
                                from src.services.google_calendar import get_calendar_service
                                calendar = get_calendar_service()
                                
                                if not calendar:
                                    # Calendar disabled
                                    error_msg = "[SYSTEM: Calendar service is currently disabled. Inform the user that cancellation is not available at the moment.]"
                                    messages.append({"role": "system", "content": error_msg})
                                    call_state.pop("cancel_active", None)
                                    should_process = False
                                else:
                                    # Find next future appointment by name only
                                    event = calendar.find_next_appointment_by_name(customer_name)
                                
                                    if event:
                                        # Extract appointment details
                                        event_start_str = event.get('start', {}).get('dateTime')
                                        if event_start_str:
                                            event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
                                            
                                            # Store found appointment
                                            call_state["cancel_found_appointment"] = event
                                            call_state["cancel_customer_name"] = customer_name
                                            
                                            # Ask for confirmation
                                            time_display = event_start.strftime('%B %d at %I:%M %p')
                                            msg = f"[SYSTEM: Confirm this is the right appointment - say something like: 'I found an appointment for {customer_name} on {time_display}. Is that the one you want to cancel?']"
                                            messages.append({"role": "system", "content": msg})
                                            print(f"✅ Found appointment for {customer_name} at {time_display}")
                                            should_process = False
                                    else:
                                        # No future appointments found
                                        msg = f"[SYSTEM: I couldn't find any upcoming appointments for {customer_name}. Ask them if they have an appointment booked or if perhaps it's under a different name.]"
                                        messages.append({"role": "system", "content": msg})
                                        print(f"❌ No future appointments found for {customer_name}")
                                        # Clean up cancel state
                                        call_state.pop("cancel_active", None)
                                        call_state.pop("user_cant_remember_cancel_time", None)
                                        should_process = False
                            except Exception as e:
                                print(f"❌ Error finding appointment by name: {e}")
                                import traceback
                                traceback.print_exc()
                                should_process = False
                    
                    print(f"🗑️ CANCEL BLOCK: time={cancel_time}, found={bool(found_appointment)}, name_confirmed={name_confirmed}, final_asked={final_asked}")
                    print(f"🗑️ STATE CHECK: Step1={cancel_time and not found_appointment}, Step2={found_appointment and not name_confirmed}, Step3={found_appointment and name_confirmed}")
                    
                    # Step 1: Find appointment by time (only if we haven't already found it via name lookup)
                    if cancel_time and not found_appointment and not user_cant_remember:
                        print(f"🔍 Finding appointment to cancel at: {cancel_time}")
                        try:
                            from src.services.google_calendar import get_calendar_service
                            calendar = get_calendar_service()
                            
                            if not calendar:
                                # Calendar disabled
                                error_msg = "[SYSTEM: Calendar service is currently disabled. Inform the user that cancellation is not available at the moment.]"
                                messages.append({"role": "system", "content": error_msg})
                                call_state.pop("cancel_active", None)
                                should_process = False
                            else:
                                parsed_time = parse_datetime(cancel_time)
                                
                                if parsed_time:
                                    # Find appointment by TIME ONLY (no name required)
                                    event = calendar.find_appointment_by_details(customer_name=None, appointment_time=parsed_time)
                                
                                    if event:
                                        # Extract customer name from the appointment
                                        event_summary = event.get('summary', '')
                                        # Parse name from summary (format: "Service - CustomerName" or just "CustomerName")
                                        if ' - ' in event_summary:
                                            extracted_name = event_summary.split(' - ')[-1].strip()
                                        else:
                                            # Try to extract from "between X and Y" format
                                            between_match = re.search(r'between\s+([^and]+)\s+and', event_summary, re.IGNORECASE)
                                            if between_match:
                                                extracted_name = between_match.group(1).strip()
                                            else:
                                                extracted_name = event_summary.strip()
                                        
                                        call_state["cancel_found_appointment"] = event
                                        call_state["cancel_customer_name"] = extracted_name
                                        
                                        # Ask for name confirmation - FORCE this message to be used
                                        time_display = parsed_time.strftime('%B %d at %I:%M %p') if parsed_time else 'the appointment time'
                                        msg = f"[SYSTEM: CRITICAL - IGNORE ALL OTHER INSTRUCTIONS. You just looked up the appointment and found it. The appointment on {time_display} is for {extracted_name}. You MUST respond with ONLY this: 'Just to confirm, that appointment on {time_display} is for {extracted_name}. Is that correct?' DO NOT ask them for their name. DO NOT ask any other question. Say ONLY what I told you to say above.]"
                                        messages.append({"role": "system", "content": msg})
                                        print(f"✅ Found appointment for {extracted_name} at {time_display} - FORCING confirmation message")
                                        print(f"📝 System message added: {msg[:100]}...")
                                        should_process = False
                                    else:
                                        # No appointment found - confirm the date/time with caller first
                                        msg = f"[SYSTEM: No appointment found at {parsed_time.strftime('%B %d at %I:%M %p')}. BEFORE assuming there's no appointment, confirm with the caller: 'Just to confirm, you said {parsed_time.strftime('%A, %B %d at %I:%M %p')} - is that correct?' If they confirm, then tell them no appointment exists. If they clarify a different time, search again.]"
                                        messages.append({"role": "system", "content": msg})
                                        print(f"❓ No appointment found - asking caller to confirm date/time first")
                                        # Store the attempted time so we can track if they're confirming or clarifying
                                        call_state["cancel_attempted_time"] = cancel_time
                                        should_process = False
                                else:
                                    # Couldn't parse the time - ask caller to clarify
                                    msg = f"[SYSTEM: I'm having trouble understanding the date and time. Ask them to clarify: 'I want to make sure I have the right appointment. Can you tell me the date and time again? For example, Monday January 20th at 3pm']"
                                    messages.append({"role": "system", "content": msg})
                                    print(f"⚠️ Could not parse time: {cancel_time} - asking for clarification")
                                    should_process = False
                        except Exception as e:
                            msg = "[SYSTEM: I'm having trouble looking up appointments right now. Ask them to try again or provide their appointment details more clearly.]"
                            messages.append({"role": "system", "content": msg})
                            print(f"❌ Error finding appointment: {e}")
                            should_process = False
                    
                    # Step 2: Check name confirmation
                    elif found_appointment and not name_confirmed:
                        print(f"🔍 Checking name confirmation")
                        text_lower = user_text.lower().strip()
                        
                        # Check if user is re-stating their cancel intent (implicit confirmation)
                        is_restating_cancel_intent = any(phrase in text_lower for phrase in [
                            'cancel', 'cancelling', 'cancel my', 'cancel the', 'need to cancel',
                            'want to cancel', 'would like to cancel', 'trying to cancel'
                        ])
                        
                        # Use AI for affirmative detection (more flexible)
                        is_affirmative = is_affirmative_response(user_text, context="appointment identification") and len(user_text.split()) <= 6
                        
                        if is_affirmative or is_restating_cancel_intent:
                            call_state["cancel_name_confirmed"] = True
                            customer_name = call_state.get("cancel_customer_name")
                            print(f"✅ Name confirmed: {customer_name}")
                            
                            # Ask for final cancellation confirmation
                            try:
                                # Get time from found appointment if cancel_time is not set (can't remember flow)
                                if cancel_time:
                                    cancel_dt = parse_datetime(cancel_time)
                                else:
                                    # Extract from found appointment
                                    event_time_str = found_appointment.get('start', {}).get('dateTime')
                                    if event_time_str:
                                        cancel_dt = datetime.fromisoformat(event_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
                                    else:
                                        cancel_dt = None
                                
                                if cancel_dt:
                                    msg = f"[SYSTEM: Final confirmation - ask if they want to proceed with cancelling the appointment on {cancel_dt.strftime('%B %d at %I:%M %p')}. If yes, proceed.]"
                                    messages.append({"role": "system", "content": msg})
                                    call_state["cancel_final_asked"] = True
                                else:
                                    # Fallback if we can't get the time
                                    msg = "[SYSTEM: Final confirmation - ask if they want to proceed with cancelling this appointment. If yes, proceed.]"
                                    messages.append({"role": "system", "content": msg})
                                    call_state["cancel_final_asked"] = True
                            except Exception as e:
                                print(f"⚠️ Error formatting cancel time: {e}")
                                msg = "[SYSTEM: Final confirmation - ask if they want to proceed with cancelling this appointment. If yes, proceed.]"
                                messages.append({"role": "system", "content": msg})
                                call_state["cancel_final_asked"] = True
                            should_process = False
                        else:
                            # User said no - clear found appointment but keep cancel flow active
                            msg = "[SYSTEM: That's not their appointment. Ask them for the correct date/time of their appointment.]"
                            messages.append({"role": "system", "content": msg})
                            print(f"❌ Name not confirmed - clearing found appointment but keeping cancel flow active")
                            call_state.pop("cancel_found_appointment", None)
                            call_state.pop("cancel_customer_name", None)
                            call_state.pop("cancel_name_confirmed", None)
                            should_process = False
                    
                    # Step 3: Final confirmation to cancel
                    elif found_appointment and name_confirmed:
                        print(f"🔍 STEP 3: Final cancellation confirmation")
                        text_lower = user_text.lower().strip()
                        print(f"🔍 STEP 3: user_text='{user_text}', text_lower='{text_lower}'")
                        # Use AI for affirmative detection (more flexible)
                        affirmative = is_affirmative_response(user_text, context="cancellation confirmation") and len(user_text.split()) <= 6
                        print(f"🔍 STEP 3: affirmative={affirmative}")
                        
                        if affirmative:
                            customer_name = call_state.get("cancel_customer_name")
                            appointment_details["customer_name"] = customer_name
                            
                            # Get appointment time - either from cancel_time or from found_appointment
                            if cancel_time:
                                appointment_details["datetime"] = cancel_time
                            else:
                                # Extract from found appointment (can't remember flow)
                                event_time_str = found_appointment.get('start', {}).get('dateTime')
                                if event_time_str:
                                    appointment_details["datetime"] = event_time_str
                                else:
                                    print("⚠️ Could not extract appointment time from found_appointment")
                            
                            should_process = True
                            print("✅ Final confirmation - proceeding with cancellation")
                            
                            # Add system message to prevent LLM from using tools during cancellation
                            msg = "[SYSTEM: Processing cancellation now. Do not use any tools. Just wait for the result.]"
                            messages.append({"role": "system", "content": msg})
                            
                            # Clean up state
                            call_state.pop("cancel_found_appointment", None)
                            call_state.pop("cancel_customer_name", None)
                            call_state.pop("cancel_name_confirmed", None)
                            call_state.pop("cancel_final_asked", None)
                        else:
                            # User declined final confirmation - ask again or clear if explicit no
                            if any(word in text_lower for word in ['no', 'nope', 'nah', 'dont', "don't", 'never']):
                                # Clear cancel flow if user explicitly says no
                                call_state.pop("cancel_active", None)
                                call_state.pop("cancel_found_appointment", None)
                                call_state.pop("cancel_customer_name", None)
                                call_state.pop("cancel_name_confirmed", None)
                                call_state.pop("cancel_final_asked", None)
                                msg = "[SYSTEM: User decided not to cancel. Ask if there's anything else you can help with.]"
                            else:
                                msg = "[SYSTEM: Ask them to confirm if they want to cancel the appointment.]"
                            messages.append({"role": "system", "content": msg})
                            should_process = False
                    else:
                        # Still waiting for cancel_time - guide the AI to ask for it
                        should_process = False
                        if not cancel_time and not found_appointment:
                            msg = "[SYSTEM: Ask the customer: 'What day and time was your appointment?']"
                            messages.append({"role": "system", "content": msg})
                            print(f"⏳ Waiting for appointment time - asked AI to request it")
                        else:
                            print(f"⏳ Waiting for next step in cancellation flow")
                
                elif intent == AppointmentIntent.QUERY:
                    # Queries can be processed immediately (no confirmation needed)
                    should_process = True
                    print(f"✅ QUERY intent - should_process set to True")
                
                # Try to process with Google Calendar if callback provided and conditions met
                print(f"🔍 PRE-CALLBACK CHECK: process_appointment_callback={process_appointment_callback is not None}, should_process={should_process}, intent={intent}")
                if process_appointment_callback and should_process:
                    print(f"📞 Calling callback for intent: {intent}")
                    booking_result = await process_appointment_callback(intent, appointment_details)
                    print(f"📞 Callback returned: type={type(booking_result)}, value={booking_result if not isinstance(booking_result, list) else f'list of {len(booking_result)} items'}")
                    
                    # Inject booking result into conversation so LLM knows what happened
                    if intent == AppointmentIntent.BOOK:
                        if booking_result:
                            # Booking succeeded - mark temporarily to prevent duplicate in same message
                            call_state["already_booked"] = True
                            # Track when booking was made for post-booking cooldown
                            call_state["last_booking_turn"] = call_state.get("current_turn", 0)
                            requested_time = parse_datetime(appointment_details["datetime"])
                            system_message = f"[SYSTEM: SUCCESS! Booking confirmed for {appointment_details['customer_name']} on {requested_time.strftime('%A, %B %d at %I:%M %p')}. Say EXACTLY: 'Perfect, you're all booked for {requested_time.strftime('%A at %I:%M %p')}. Anything else I can help with?' Then STOP - do not repeat the confirmation.]"
                            messages.append({"role": "system", "content": system_message})
                            # Reset flag to allow additional bookings after this one is complete
                            call_state["already_booked"] = False
                        else:
                            # Booking failed (slot busy)
                            from src.services.google_calendar import get_calendar_service
                            requested_time = parse_datetime(appointment_details["datetime"])
                            calendar = get_calendar_service()
                            
                            if calendar:
                                # Get all available slots for the same day
                                same_day_slots = calendar.get_available_slots_for_day(requested_time)
                                
                                # Also get general alternatives (same day + nearby days)
                                alternatives = calendar.get_alternative_times(requested_time, days_to_check=3)
                            else:
                                same_day_slots = []
                                alternatives = []
                            
                            alt_text = ""
                            if same_day_slots:
                                same_day_text = ", ".join([
                                    alt.strftime('%I:%M %p') for alt in same_day_slots
                                ])
                                alt_text = f"Available times on {requested_time.strftime('%B %d')}: {same_day_text}. "
                            else:
                                alt_text = f"No available times on {requested_time.strftime('%B %d')}. "
                            
                            # Add suggested alternatives from nearby days if different
                            if alternatives:
                                alt_text += "Suggested alternatives: " + ", ".join([
                                    alt.strftime('%A %B %d at %I:%M %p') for alt in alternatives
                                ])
                            
                            system_message = f"[SYSTEM: Unfortunately, that time slot ({requested_time.strftime('%B %d at %I:%M %p')}) is already booked. {alt_text} Politely inform the user that the requested time is unavailable and suggest these alternative times. Keep it natural and helpful.]"
                            messages.append({"role": "system", "content": system_message})
                    
                    elif intent == AppointmentIntent.CANCEL:
                        if booking_result:
                            # Cancellation succeeded - clear appointment state and cancel flow
                            call_state["datetime"] = None
                            call_state["service_type"] = None
                            call_state["customer_name"] = None
                            call_state.pop("cancel_active", None)
                            call_state.pop("cancel_found_appointment", None)
                            call_state.pop("cancel_customer_name", None)
                            call_state.pop("cancel_name_confirmed", None)
                            call_state.pop("cancel_final_asked", None)
                            print(f"🧹 Cleared appointment state and cancel flow after cancellation")
                            
                            system_message = f"[SYSTEM: SUCCESS! Appointment cancelled for {appointment_details.get('customer_name', 'the customer')}. Say EXACTLY: 'That's cancelled for you. Anything else I can help with?' Then STOP - do not repeat.]"
                            messages.append({"role": "system", "content": system_message})
                        else:
                            # Cancellation failed (not found)
                            name = appointment_details.get('customer_name', '')
                            time_ref = appointment_details.get('datetime', '')
                            system_message = f"[SYSTEM: Could NOT find an appointment to cancel for {name if name else 'this customer'}. Ask them for the date and time of their appointment to help locate it.]"
                            messages.append({"role": "system", "content": system_message})
                    
                    elif intent == AppointmentIntent.RESCHEDULE:
                        if booking_result == "need_specific_time":
                            # Customer wants to reschedule but didn't provide specific time - use config
                            messages.append({"role": "system", "content": RESCHEDULE_MESSAGES["need_specific_time"]})
                        elif booking_result == "slot_unavailable":
                            # Requested time slot is busy - keep context, suggest alternatives
                            requested_time = appointment_details.get('new_datetime', 'that time')
                            messages.append({"role": "system", "content": RESCHEDULE_MESSAGES["slot_unavailable"](requested_time)})
                            # Keep reschedule state active but reset final_asked so user can pick alternative
                            call_state.pop("reschedule_final_asked", None)
                            print(f"⚠️ Slot unavailable - keeping reschedule context active, reset final_asked for alternative selection")
                        elif booking_result:
                            # Rescheduling succeeded - NOW tell the AI about the success
                            display_time = call_state.get("reschedule_display_time", "the new time")
                            success_msg = RESCHEDULE_MESSAGES["success"](display_time)
                            messages.append({"role": "system", "content": success_msg})
                            
                            # Clean up state
                            call_state.pop("reschedule_active", None)
                            call_state.pop("reschedule_found_appointment", None)
                            call_state.pop("reschedule_customer_name", None)
                            call_state.pop("reschedule_name_confirmed", None)
                            call_state.pop("reschedule_final_asked", None)
                            call_state.pop("reschedule_display_time", None)
                            print(f"🧹 Cleaned up reschedule state after success")
                        else:
                            # Generic failure (couldn't find appointment, etc.) - use config
                            messages.append({"role": "system", "content": RESCHEDULE_MESSAGES["failed"]})
                    
                    elif intent == AppointmentIntent.QUERY:
                        # If QUERY returned available slots, inform the LLM
                        print(f"🔍 QUERY RESULT CHECK: booking_result type={type(booking_result)}, is_list={isinstance(booking_result, list)}, value={booking_result}")
                        if booking_result and isinstance(booking_result, list):
                            # Pass structured slot data to the LLM - booking_result now contains dicts
                            slot_info = []
                            days_available = set()
                            for slot_dict in booking_result:
                                # Each slot_dict has 'datetime', 'date', 'formatted', 'full_formatted' and possibly 'day_name'
                                day_name = slot_dict.get('day_name', slot_dict['date'].strftime('%A'))
                                date_str = slot_dict['date'].strftime('%B %d, %Y')
                                days_available.add(f"{day_name}, {date_str}")
                                
                                slot_info.append({
                                    "day": day_name,
                                    "date": date_str,
                                    "time": slot_dict['formatted'],
                                    "full": slot_dict['full_formatted']
                                })
                            
                            # Check if this was a "next week" query
                            time_ref = appointment_details.get('datetime', '')
                            is_next_week = 'next week' in time_ref.lower()
                            
                            # Create helpful message for LLM
                            if is_next_week:
                                system_message = (
                                    f"[SYSTEM: Available appointments next week. We have openings on {len(days_available)} day(s): " +
                                    ", ".join(sorted(days_available)) + ".\\n\\n" +
                                    "Here are all available time slots:\\n" +
                                    json.dumps(slot_info, indent=2) +
                                    "\\n\\nRespond naturally and helpfully. Example: 'Great news! We have plenty of availability next week. "
                                    "We have openings on Monday, Tuesday, Wednesday, Thursday, and Friday. What day works best for you?']"
                                )
                            else:
                                system_message = (
                                    "[SYSTEM: The following appointment slots are available. "
                                    "ALWAYS be specific and helpful - if they asked about a specific day, tell them what's available on that day. "
                                    "If they asked what days are available, tell them which days have openings. "
                                    "Present the times clearly and naturally. Here are the available slots:\\n" +
                                    json.dumps(slot_info, indent=2) +
                                    "\\n\\nRespond helpfully based on their question. Examples:\\n"
                                    "- If they asked 'is day after tomorrow free?', say 'Yes! I have 9:00 AM and 10:00 AM available on [date]'\\n"
                                    "- If they asked 'what days are available?', list the days and times\\n"
                                    "- If they asked for early slots, highlight morning times]"
                                )
                            print(f"📋 SYSTEM MESSAGE TO LLM:\\n{system_message}\\n")
                            messages.append({"role": "system", "content": system_message})
                        elif booking_result is None and appointment_details.get('datetime'):
                            # No available slots on requested day/period
                            date_ref = appointment_details.get('datetime', '')
                            
                            # Check if this was a "next week" query
                            if 'next week' in date_ref.lower():
                                system_message = "[SYSTEM: Unfortunately, there are no available appointments next week. All slots are fully booked. Suggest they try the following week or a different timeframe, and ask when would work for them.]"
                            else:
                                try:
                                    parsed = parse_datetime(date_ref)
                                    if parsed:
                                        day_name = parsed.strftime('%A, %B %d')
                                        if not is_business_day(parsed):
                                            system_message = get_closed_day_message(parsed)
                                        else:
                                            system_message = f"[SYSTEM: Unfortunately, there are no available appointments on {day_name}. That day is fully booked. Suggest nearby alternative days when we're open, and ask when would work for them.]"
                                    else:
                                        system_message = f"[SYSTEM: Unfortunately, there are no available appointments on {date_ref}. Suggest alternative days when we're open, and ask when would work for them.]"
                                except:
                                    system_message = f"[SYSTEM: Unfortunately, there are no available appointments on {date_ref}. Suggest alternative days when we're open, and ask when would work for them.]"
                            messages.append({"role": "system", "content": system_message})
    
    # Check if we should skip LLM response (callback added result, now generate single response)
    if call_state.get("skip_llm_response"):
        print("⏭️ Skipping initial LLM response - will generate single response with callback result")
        call_state.pop("skip_llm_response", None)  # Clear flag
        # Don't return - continue to generate response with callback result now in messages
    
    # PRE-CHECK: Detect if user message likely requires a tool call
    # If so, speak acknowledgment IMMEDIATELY before calling OpenAI (to avoid OpenAI latency)
    # IMPORTANT: Filler messages run in PARALLEL with tool execution - TTS speaks while work happens
    # NOTE: Use GENERIC fillers that work for any action - avoid action-specific phrases that could be wrong
    
    precheck_start = time.time()
    time_to_precheck = precheck_start - llm_start_time
    if time_to_precheck > 0.1:
        print(f"[LLM_TIMING] ⚠️ Time before pre-check: {time_to_precheck*1000:.1f}ms (should be <100ms)")
    
    user_message = messages[-1]["content"].lower() if messages and messages[-1].get("role") == "user" else ""
    likely_needs_tool = False
    checking_msg = None
    detected_intent = None
    
    print(f"\n{'='*60}")
    print(f"🔍 [PRE-CHECK] === FILLER PRE-CHECK ANALYSIS ===")
    print(f"🔍 [PRE-CHECK] User message: '{user_message[:80]}...'")
    print(f"{'='*60}")
    
    # Generic filler phrases that work for ANY action - can't be wrong
    # NOTE: These must match the pre-recorded audio files in src/audio/fillers/
    generic_fillers = [
        "One moment.",
        "Let me check that for you.",
        "Bear with me one second.",
        "Just a moment.",
        "Let me have a look.",
    ]
    
    # Detect transfer/human requests - these need specific messaging
    transfer_phrases = ["transfer", "speak to a", "talk to a", "speak with", "talk with", "real person", "actual person", "someone else", "a human", "the manager", "the owner"]
    if any(phrase in user_message for phrase in transfer_phrases):
        likely_needs_tool = True
        detected_intent = "TRANSFER"
        checking_msg = random.choice([
            "Transferring you now.",
            "Connecting you now.",
            "Let me get someone for you."
        ])
        print(f"   ✅ [PRE-CHECK] Detected: TRANSFER REQUEST")
    
    # Detect booking confirmation (user confirming details before ACTUAL booking)
    # Must have booking-related context, not just name/phone confirmation
    booking_confirm_phrases = ["yes", "yeah", "yep", "correct", "that's right", "book it", "sounds good", "perfect", "go ahead", "please book", "book that"]
    prev_assistant_msg = ""
    for msg in reversed(messages[:-1]):
        if msg.get("role") == "assistant":
            prev_assistant_msg = msg.get("content", "").lower()
            break
    
    # Check for ACTUAL booking context - must mention appointment/booking/time, not just name confirmation
    booking_context_phrases = ["book", "appointment", "schedule", "confirm the booking", "confirm your appointment", 
                               "ready to book", "shall i book", "want me to book", "proceed with the booking"]
    has_booking_context = any(phrase in prev_assistant_msg for phrase in booking_context_phrases)
    
    # Exclude name/phone confirmation scenarios - these are NOT booking confirmations
    name_confirmation_phrases = ["is that correct", "is that right", "spell", "j-", "confirm your name", 
                                 "confirm the name", "is that the best number", "reach you"]
    is_just_name_confirmation = any(phrase in prev_assistant_msg for phrase in name_confirmation_phrases) and not has_booking_context
    
    is_booking_confirmation = has_booking_context and any(phrase in user_message for phrase in booking_confirm_phrases) and not is_just_name_confirmation
    
    if not likely_needs_tool and is_booking_confirmation:
        likely_needs_tool = True
        detected_intent = "BOOKING_CONFIRMATION"
        # Use booking-specific fillers for booking confirmations
        checking_msg = random.choice([
            "Let me book that for you, one moment.",
            "Let me confirm that for you, one moment.",
        ])
        print(f"   ✅ [PRE-CHECK] Detected: BOOKING CONFIRMATION")
    
    # Detect availability/schedule checking
    availability_phrases = ["available", "availability", "what times", "when are you", "when can", "any slots", "free", "open"]
    if not likely_needs_tool and any(phrase in user_message for phrase in availability_phrases):
        likely_needs_tool = True
        detected_intent = "AVAILABILITY_CHECK"
        checking_msg = random.choice(generic_fillers)
        print(f"   ✅ [PRE-CHECK] Detected: AVAILABILITY CHECK")
    
    # Detect cancellation requests
    cancel_phrases = ["cancel", "cancelling", "canceling"]
    cancel_context = ["appointment", "booking", "scheduled", "job"]
    if not likely_needs_tool and any(phrase in user_message for phrase in cancel_phrases) and any(ctx in user_message for ctx in cancel_context):
        likely_needs_tool = True
        detected_intent = "CANCELLATION"
        checking_msg = random.choice(generic_fillers)
        print(f"   ✅ [PRE-CHECK] Detected: CANCELLATION REQUEST")
    
    # Detect reschedule requests
    reschedule_phrases = ["reschedule", "change my appointment", "move my appointment", "different time", "move it to"]
    if not likely_needs_tool and any(phrase in user_message for phrase in reschedule_phrases):
        likely_needs_tool = True
        detected_intent = "RESCHEDULE"
        checking_msg = random.choice(generic_fillers)
        print(f"   ✅ [PRE-CHECK] Detected: RESCHEDULE REQUEST")
    
    # Detect modify job requests (changing address, details, etc. without changing time)
    modify_phrases = ["change the address", "change my address", "different address", "update the address", 
                      "change the details", "update the details", "change the job", "modify the job",
                      "change the phone", "update my phone", "different phone", "change my number",
                      "change the email", "update my email", "different email",
                      "change it to emergency", "make it urgent", "change urgency"]
    if not likely_needs_tool and any(phrase in user_message for phrase in modify_phrases):
        likely_needs_tool = True
        detected_intent = "MODIFY_JOB"
        checking_msg = random.choice(generic_fillers)
        print(f"   ✅ [PRE-CHECK] Detected: MODIFY JOB REQUEST")
    
    # Detect lookup/verification requests (when asking about existing appointments)
    lookup_phrases = ["my appointment", "do i have", "what time is my", "when is my"]
    if not likely_needs_tool and any(phrase in user_message for phrase in lookup_phrases):
        likely_needs_tool = True
        detected_intent = "APPOINTMENT_LOOKUP"
        checking_msg = random.choice(generic_fillers)
        print(f"   ✅ [PRE-CHECK] Detected: APPOINTMENT LOOKUP")
    
    # Detect customer lookup (after getting name)
    # IMPORTANT: The LLM is instructed to SPELL BACK the name and get confirmation BEFORE calling lookup_customer
    # So we should NOT trigger a filler when user first gives their name - the LLM will ask for confirmation first
    # Only trigger when user CONFIRMS the spelling (handled by CONFIRMATION_RESPONSE below)
    # DISABLED: This was causing "Let me check that for you" followed by spelling confirmation questions
    # name_intro_patterns = ["my name is ", "the name is ", "name's "]
    # if not likely_needs_tool and any(phrase in user_message for phrase in name_intro_patterns):
    #     # This is DISABLED because LLM will ask for spelling confirmation first, not call lookup_customer
    #     pass
    
    # Detect pricing/quote requests (requires service matching which can take time)
    pricing_phrases = ["how much", "what's the price", "what's the cost", "price for", "cost of", 
                       "quote for", "get a quote", "give me a quote", "estimate for", "how much would"]
    if not likely_needs_tool and any(phrase in user_message for phrase in pricing_phrases):
        likely_needs_tool = True
        detected_intent = "PRICING_INQUIRY"
        checking_msg = random.choice(generic_fillers)
        print(f"   ✅ [PRE-CHECK] Detected: PRICING INQUIRY")
    
    # Detect booking requests (initial booking intent)
    booking_phrases = ["book an appointment", "book a job", "schedule an appointment", "schedule a job",
                       "make an appointment", "make a booking", "i need to book", "i'd like to book",
                       "can i book", "can you book", "want to book", "need an appointment"]
    if not likely_needs_tool and any(phrase in user_message for phrase in booking_phrases):
        likely_needs_tool = True
        detected_intent = "BOOKING_REQUEST"
        checking_msg = random.choice(generic_fillers)
        print(f"   ✅ [PRE-CHECK] Detected: BOOKING REQUEST")
    
    # Detect date/time preference responses (when user gives a time preference)
    time_preference_phrases = ["tomorrow", "next week", "monday", "tuesday", "wednesday", "thursday", 
                               "friday", "saturday", "morning", "afternoon", "evening", "o'clock",
                               "this week", "next monday", "next tuesday", "in the morning", "in the afternoon"]
    # Only trigger if it looks like they're giving a time preference (not just mentioning a day in passing)
    time_context_phrases = ["works", "suits", "good for me", "prefer", "available", "free", "can do", "how about", "what about"]
    if not likely_needs_tool and any(phrase in user_message for phrase in time_preference_phrases):
        # Check if this seems like a scheduling context OR it's a short direct answer
        is_short_answer = len(user_message.split()) <= 4
        has_time_context = any(ctx in user_message for ctx in time_context_phrases)
        # Also check if previous message was asking about times
        prev_asked_time = any(phrase in prev_assistant_msg for phrase in ["when", "what time", "what day", "which day", "suits you", "work for you"])
        
        if has_time_context or (is_short_answer and prev_asked_time):
            likely_needs_tool = True
            detected_intent = "TIME_PREFERENCE"
            checking_msg = random.choice(generic_fillers)
            print(f"   ✅ [PRE-CHECK] Detected: TIME PREFERENCE")
    
    # Detect confirmation responses that might trigger actions (yes to various prompts)
    # IMPORTANT: Be VERY selective - only trigger for confirmations that will DEFINITELY call a tool
    confirmation_phrases = ["yes", "yeah", "yep", "yup", "correct", "that's right", "that's correct", 
                           "confirmed", "confirm", "go ahead", "sounds good", "perfect", "great"]
    # Check if previous message was asking for confirmation
    if not likely_needs_tool and any(phrase in user_message for phrase in confirmation_phrases):
        # Booking/action confirmations - these lead to booking tool calls
        booking_confirmation_prompts = ["ready to book", "shall i book", "want me to book", 
                                        "proceed with the booking", "confirm the booking",
                                        "should i cancel", "should i reschedule", "want to proceed",
                                        "all correct"]
        
        # Name spelling confirmation - AI spelled back name like "J-A-M-E-S", user says "yes"
        # This triggers lookup_customer tool call
        name_spelling_indicators = ["j-", "k-", "l-", "m-", "n-", "o-", "p-", "s-", "t-", "a-", "b-", "c-", "d-", "e-", "f-", "g-", "h-", "i-", "r-", "u-", "v-", "w-", "y-", "z-"]
        is_name_spelling_confirmation = any(indicator in prev_assistant_msg for indicator in name_spelling_indicators)
        
        # Phone/address confirmations - these are quick, no filler needed
        phone_address_indicators = ["is that the best number", "is that still", "same location", "same address", "reach you"]
        is_phone_address_confirmation = any(indicator in prev_assistant_msg for indicator in phone_address_indicators)
        
        is_booking_confirmation = any(prompt in prev_assistant_msg for prompt in booking_confirmation_prompts)
        
        if is_booking_confirmation:
            likely_needs_tool = True
            detected_intent = "CONFIRMATION_RESPONSE"
            checking_msg = random.choice(generic_fillers)
            print(f"   ✅ [PRE-CHECK] Detected: CONFIRMATION RESPONSE (booking action)")
        elif is_name_spelling_confirmation and not is_phone_address_confirmation:
            # User confirmed name spelling - LLM will call lookup_customer
            likely_needs_tool = True
            detected_intent = "NAME_SPELLING_CONFIRMED"
            checking_msg = random.choice([
                "Grand, one moment.",
                "Got it, just checking.",
                "Perfect, one moment.",
                "Grand, let me check that.",
            ])
            print(f"   ✅ [PRE-CHECK] Detected: NAME SPELLING CONFIRMED (will lookup customer)")
        elif is_phone_address_confirmation:
            # User confirmed phone/address - play a short acknowledgment filler
            # This helps fill the gap while LLM processes
            likely_needs_tool = True
            detected_intent = "PHONE_ADDRESS_CONFIRMED"
            checking_msg = random.choice([
                "Grand.",
                "Perfect.",
                "Great.",
            ])
            print(f"   ✅ [PRE-CHECK] Detected: PHONE/ADDRESS CONFIRMED (short acknowledgment)")
    
    # Detect service/job description (when user describes what they need done)
    # When user describes a problem like "I have a leak", the LLM needs time to process
    # Play a filler to acknowledge and buy time for the response
    service_indicators = ["leak", "blocked", "leaking", "broken", "not working", "burst", "flooding", 
                          "no power", "no hot water", "no heating", "dripping", "clogged", "emergency",
                          "urgent", "water damage", "pipe", "drain", "toilet", "sink", "tap", "boiler"]
    if not likely_needs_tool and any(indicator in user_message for indicator in service_indicators):
        likely_needs_tool = True
        detected_intent = "SERVICE_DESCRIPTION"
        # Use a short acknowledgment that won't overlap with LLM response
        checking_msg = "Sure, one moment."
        print(f"   ✅ [PRE-CHECK] Detected: SERVICE DESCRIPTION (will acknowledge)")
    
    precheck_duration = time.time() - precheck_start
    
    if likely_needs_tool and checking_msg:
        print(f"\n   {'─'*50}")
        print(f"   🎯 [PRE-CHECK] FILLER WILL BE TRIGGERED!")
        print(f"   🎯 [PRE-CHECK] Intent: {detected_intent}")
        print(f"   🎯 [PRE-CHECK] Filler message: '{checking_msg}'")
        print(f"   🎯 [PRE-CHECK] Analysis took: {precheck_duration*1000:.1f}ms")
        print(f"   🎯 [PRE-CHECK] Yielding SPLIT_TTS marker NOW (before OpenAI call)")
        print(f"   {'─'*50}\n")
        yield f"<<<SPLIT_TTS:{checking_msg}>>>"
    else:
        print(f"   ❌ [PRE-CHECK] No filler trigger detected")
        print(f"   ❌ [PRE-CHECK] Analysis took: {precheck_duration*1000:.1f}ms")
        print(f"   ❌ [PRE-CHECK] Will proceed directly to OpenAI without filler\n")
    
    # Stream from OpenAI with optimized settings
    client = get_openai_client()
    
    # --- TIMING: System prompt loading ---
    prompt_load_start = time_module.time()
    
    # Add current time context to system prompt
    current_time = datetime.now()
    current_time_str = current_time.strftime('%I:%M %p on %A, %B %d, %Y')
    time_context = f"\n\n[CURRENT TIME: {current_time_str}]\nUse this when discussing appointment times and availability. Times that have already passed today cannot be booked."
    
    # Enhanced prompt for tool usage
    tool_usage_guidance = """

CRITICAL RESPONSE RULES:
- NEVER say "let me check" or "one moment" WITHOUT immediately providing results
- When tools execute, results come back INSTANTLY - no waiting needed
- Provide COMPLETE responses, not partial ones
- If you check availability, IMMEDIATELY share what times are available
- NEVER leave the customer hanging with "checking..." messages

TOOL USAGE INSTRUCTIONS:
1. check_availability: Use IMMEDIATELY when customer asks about available times/slots
   - Tool returns results INSTANTLY (no delay)
   - After calling this tool, you MUST tell customer what times are available
2. lookup_customer: Use to verify customer identity before appointments
3. cancel_appointment: Use when customer confirms they want to cancel. REQUIRES:
   - Appointment date/time (ask customer to confirm)
   - Customer name (from appointment or conversation)
   - Only call after customer confirms the cancellation
4. reschedule_appointment: Use when customer confirms new time. REQUIRES:
   - Current appointment date/time
   - New appointment date/time (must be specific)
   - Customer name
   - Check availability first with check_availability
   - Only call after customer confirms the new time

BOOKING: Continue conversation to collect details (system handles booking through conversation flow)

When customer wants to cancel:
1. Ask for date/time of appointment to cancel: "What day and time was the appointment?"
2. Call cancel_appointment with ONLY the datetime (DO NOT ask for name first)
3. System returns the customer name found at that time
4. Tell customer: "I found the appointment on [date/time] - that's for [NAME]. Is that the one you want to cancel?"
5. When they confirm, call cancel_appointment again with both datetime AND name to complete
6. Confirm completion: "All done! Your appointment on [date/time] has been cancelled."

When customer wants to reschedule:
1. Ask for current appointment date/time
2. Ask what new time they want
3. Use check_availability to verify new time is free
4. Ask "Would you like to move your appointment to [new time]?"
5. When they confirm, call reschedule_appointment tool
"""
    
    # Load company-specific system prompt with CACHING to avoid repeated DB queries
    prompt_load_db_start = time_module.time()
    active_system_prompt = get_cached_system_prompt(company_id=company_id)
    prompt_load_time = time_module.time() - prompt_load_db_start
    print(f"[LLM_TIMING] System prompt retrieved in {prompt_load_time*1000:.1f}ms (company_id={company_id})")
    
    system_prompt_with_time = active_system_prompt + time_context + tool_usage_guidance
    prompt_total_time = time_module.time() - prompt_load_start
    print(f"[LLM_TIMING] Total prompt preparation: {prompt_total_time:.3f}s")
    
    # Sanitize messages to ensure tool messages have their preceding assistant message with tool_calls
    # This prevents the "messages with role 'tool' must be a response to a preceding message with 'tool_calls'" error
    def sanitize_messages(msgs):
        """Remove orphaned tool messages that don't have a preceding assistant message with tool_calls.
        Also validates that tool_call_ids match between assistant and tool messages."""
        if not msgs:
            return []
            
        sanitized = []
        i = 0
        while i < len(msgs):
            msg = msgs[i]
            role = msg.get('role')
            
            if role == 'tool':
                # Check if there's a preceding assistant message with tool_calls
                # Need to look back past any other tool messages (parallel tool calls create multiple tool messages)
                has_valid_assistant = False
                tool_call_id = msg.get('tool_call_id')
                
                for j in range(len(sanitized) - 1, -1, -1):
                    prev_msg = sanitized[j]
                    prev_role = prev_msg.get('role')
                    
                    if prev_role == 'tool':
                        # Keep looking back past other tool messages
                        continue
                    elif prev_role == 'assistant' and prev_msg.get('tool_calls'):
                        # Found an assistant message with tool_calls
                        # Verify this tool message's ID matches one of the tool_calls
                        tool_call_ids = [tc.get('id') for tc in prev_msg.get('tool_calls', [])]
                        if tool_call_id in tool_call_ids:
                            has_valid_assistant = True
                        else:
                            print(f"⚠️ [SANITIZE] Tool message ID {tool_call_id} not in assistant's tool_calls: {tool_call_ids}")
                        break
                    else:
                        # Found a non-tool, non-assistant-with-tool_calls message - stop looking
                        break
                
                if has_valid_assistant:
                    sanitized.append(msg)
                else:
                    # Orphaned tool message - skip it
                    print(f"⚠️ [SANITIZE] Removing orphaned tool message: {msg.get('name', 'unknown')} (id: {tool_call_id})")
                    
            elif role == 'assistant' and msg.get('tool_calls'):
                # Check if there are tool responses following this message in the ORIGINAL list
                has_tool_response = False
                expected_tool_ids = [tc.get('id') for tc in msg.get('tool_calls', [])]
                
                # Look ahead in original messages for matching tool responses
                for k in range(i + 1, len(msgs)):
                    next_msg = msgs[k]
                    if next_msg.get('role') == 'tool':
                        if next_msg.get('tool_call_id') in expected_tool_ids:
                            has_tool_response = True
                            break
                    elif next_msg.get('role') != 'tool':
                        # Hit a non-tool message, stop looking
                        break
                
                if has_tool_response:
                    sanitized.append(msg)
                else:
                    # Assistant message with tool_calls but no tool response - skip it
                    print(f"⚠️ [SANITIZE] Removing assistant message with orphaned tool_calls: {[tc.get('function', {}).get('name') for tc in msg.get('tool_calls', [])]}")
            else:
                sanitized.append(msg)
            i += 1
        
        return sanitized
    
    # Sanitize messages before sending to OpenAI
    sanitized_messages = sanitize_messages(messages)
    if len(sanitized_messages) != len(messages):
        print(f"⚠️ [SANITIZE] Removed {len(messages) - len(sanitized_messages)} orphaned messages")
        print(f"⚠️ [SANITIZE] Original message roles: {[m.get('role') for m in messages]}")
        print(f"⚠️ [SANITIZE] Sanitized message roles: {[m.get('role') for m in sanitized_messages]}")
    
    # Debug: Print message structure before API call
    print(f"[LLM_DEBUG] Message roles being sent: {[m.get('role') for m in sanitized_messages]}")
    for idx, msg in enumerate(sanitized_messages):
        if msg.get('role') == 'tool':
            print(f"[LLM_DEBUG] Message[{idx}] is tool: {msg.get('name', 'unknown')}")
        elif msg.get('role') == 'assistant' and msg.get('tool_calls'):
            print(f"[LLM_DEBUG] Message[{idx}] is assistant with tool_calls: {[tc.get('function', {}).get('name') for tc in msg.get('tool_calls', [])]}")
    
    # FINAL SAFETY CHECK: Verify no orphaned tool messages exist
    # This is a last-resort check before sending to OpenAI
    final_messages = []
    seen_tool_call_ids = set()
    for msg in sanitized_messages:
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            # Track all tool_call IDs from this assistant message
            for tc in msg.get('tool_calls', []):
                seen_tool_call_ids.add(tc.get('id'))
            final_messages.append(msg)
        elif msg.get('role') == 'tool':
            # Only include if we've seen the corresponding tool_call
            if msg.get('tool_call_id') in seen_tool_call_ids:
                final_messages.append(msg)
            else:
                print(f"🚨 [FINAL_CHECK] Removing orphaned tool message at last check: {msg.get('name')} (id: {msg.get('tool_call_id')})")
        else:
            final_messages.append(msg)
    
    if len(final_messages) != len(sanitized_messages):
        print(f"🚨 [FINAL_CHECK] Removed {len(sanitized_messages) - len(final_messages)} messages in final safety check")
    
    try:
        openai_call_start = time_module.time()
        time_since_llm_start = openai_call_start - llm_start_time
        print(f"[LLM_TIMING] Creating OpenAI stream with model={config.CHAT_MODEL}")
        print(f"[LLM_TIMING] Time since stream_llm start: {time_since_llm_start:.3f}s")
        print(f"[LLM_TIMING] Messages count: {len(final_messages)}, company_id={company_id}")
        print(f"[LLM_TIMING] Last user message: {final_messages[-1].get('content', '')[:100] if final_messages else 'N/A'}...")
        stream = client.chat.completions.create(
            model=config.CHAT_MODEL,
            stream=True,
            temperature=0.1,  # Very low for speed and consistency, but not zero to avoid stiffness  
            max_tokens=180,   # Reduced for faster responses while maintaining completeness
            presence_penalty=0.1,  # Reduced to prevent excessive avoidance
            frequency_penalty=0.1, # Reduced to prevent excessive avoidance
            messages=[{"role": "system", "content": system_prompt_with_time}, *final_messages],
            tools=CALENDAR_TOOLS,
            tool_choice="auto",
            parallel_tool_calls=True,  # Enable parallel tool execution for speed
            # Additional optimization parameters
            top_p=0.9,  # Focus on most likely tokens for speed
            stream_options={"include_usage": False}  # Disable usage tracking for speed
        )
        openai_create_time = time_module.time() - openai_call_start
        print(f"[LLM_TIMING] ✅ OpenAI stream created in {openai_create_time:.3f}s")
    except Exception as e:
        print(f"❌ [LLM_ERROR] Error creating LLM stream: {e}")
        print(f"[LLM_ERROR] Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        yield "I apologize, I'm having technical difficulties. Please try again."
        return
    
    full_response = ""
    tool_calls = []
    current_tool_call = None
    token_count = 0
    has_yielded_split_marker = likely_needs_tool  # Already yielded if pre-check detected it
    first_token_time = None  # Track time to first token
    
    try:
        print(f"[LLM_TIMING] Starting to iterate over stream...")
        stream_iter_start = time_module.time()
        for part in stream:
            # Track first token timing
            if first_token_time is None:
                first_token_time = time_module.time()
                ttft = first_token_time - openai_call_start
                total_ttft = first_token_time - llm_start_time
                print(f"[LLM_TIMING] ⚡ FIRST TOKEN received!")
                print(f"[LLM_TIMING]    Time from API call: {ttft:.3f}s")
                print(f"[LLM_TIMING]    Time from stream_llm start: {total_ttft:.3f}s")
            
            delta = part.choices[0].delta
            
            # Handle tool calls
            if delta.tool_calls:
                # IMMEDIATELY yield the split marker on the FIRST tool call detection
                # (only if we didn't already yield it in pre-check)
                if not has_yielded_split_marker:
                    # Try to get tool name for context-aware filler
                    tool_name_hint = ""
                    for tc_delta in delta.tool_calls:
                        if tc_delta.function and tc_delta.function.name:
                            tool_name_hint = tc_delta.function.name
                            break
                    
                    # Context-specific filler messages based on tool type
                    if tool_name_hint == "transfer_to_human":
                        checking_phrases = [
                            "Transferring you now.",
                            "Connecting you now.",
                            "Let me get someone for you."
                        ]
                    elif tool_name_hint in ["book_appointment", "book_job"]:
                        # Booking-specific fillers
                        checking_phrases = [
                            "Let me book that for you, one moment.",
                            "Let me confirm that for you, one moment.",
                        ]
                    else:
                        # Generic fillers for everything else
                        checking_phrases = [
                            "One moment.",
                            "Let me check that for you.",
                            "Bear with me one second.",
                            "Just a moment.",
                            "Let me have a look.",
                        ]
                    
                    checking_msg = random.choice(checking_phrases)
                    print(f"   🗣️ IMMEDIATE: First tool call detected ({tool_name_hint or 'unknown'}) - yielding split marker with: '{checking_msg}'")
                    yield f"<<<SPLIT_TTS:{checking_msg}>>>"
                    has_yielded_split_marker = True
                
                # Now collect the tool call data
                for tool_call_delta in delta.tool_calls:
                    # Initialize new tool call
                    if tool_call_delta.index is not None:
                        while len(tool_calls) <= tool_call_delta.index:
                            tool_calls.append({
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            })
                        current_tool_call = tool_calls[tool_call_delta.index]
                    
                    # Accumulate tool call data
                    if tool_call_delta.id:
                        current_tool_call["id"] = tool_call_delta.id
                    if tool_call_delta.function:
                        if tool_call_delta.function.name:
                            current_tool_call["function"]["name"] = tool_call_delta.function.name
                        if tool_call_delta.function.arguments:
                            current_tool_call["function"]["arguments"] += tool_call_delta.function.arguments
            
            # Handle regular content - but suppress it if we have tool calls OR if we yielded split marker
            if delta.content:
                token_count += 1
                full_response += delta.content  # Keep original for history
                
                # Only yield content if:
                # 1. We're NOT making tool calls (tool calls suppress content)
                # 2. We haven't yielded a split marker (split marker means content comes in continuation)
                if not tool_calls and not has_yielded_split_marker:
                    # Strip markdown formatting to prevent TTS reading "**" as "star star"
                    cleaned_token = delta.content.replace('**', '').replace('__', '').replace('~~', '')
                    # Add pauses for spelled-out content (letters/numbers separated by dashes)
                    cleaned_token = format_for_tts_spelling(cleaned_token)
                    yield cleaned_token  # Send cleaned version to TTS
                
    except Exception as e:
        print(f"❌ [LLM_ERROR] Error during LLM streaming: {e}")
        print(f"[LLM_ERROR] Exception type: {type(e).__name__}")
        print(f"[LLM_ERROR] Token count at error: {token_count}")
        print(f"[LLM_ERROR] Tool calls collected: {len(tool_calls)}")
        import traceback
        traceback.print_exc()
        if not token_count:
            yield "I apologize, I'm having trouble processing your request."
        return
    
    # Check if we got any tokens
    if token_count == 0:
        print("⚠️ WARNING: LLM completed but generated ZERO tokens!")
        print(f"   Tool calls: {len(tool_calls)}")
        print(f"   Full response length: {len(full_response)}")
    
    # SAFETY CHECK: If we yielded a split marker in pre-check but OpenAI didn't actually call tools
    if has_yielded_split_marker and not tool_calls:
        if full_response:
            print(f"\n⚠️ [PRE-CHECK MISFIRE] Filler was played but LLM didn't call any tools!")
            print(f"⚠️ [PRE-CHECK MISFIRE] User message was: '{user_message[:80]}...'")
            print(f"⚠️ [PRE-CHECK MISFIRE] LLM response: '{full_response[:100]}...'")
            print(f"⚠️ [PRE-CHECK MISFIRE] This creates awkward UX - consider disabling this pre-check trigger\n")
            # Yield the response that was collected but suppressed
            # Strip markdown formatting
            cleaned_response = full_response.replace('**', '').replace('__', '').replace('~~', '')
            yield cleaned_response
            messages.append({"role": "assistant", "content": full_response})
        else:
            # Edge case: Pre-check fired but OpenAI returned nothing - provide fallback
            print(f"⚠️ Pre-check fired but OpenAI returned no content and no tools!")
            fallback = "How can I help you with that?"
            yield fallback
            messages.append({"role": "assistant", "content": fallback})
        return
    
    # Process tool calls if any were made
    if tool_calls:
        tool_phase_start = time.time()
        print(f"\n🔧 [TOOL_PHASE] Starting tool execution at {tool_phase_start:.3f}")
        print(f"\n{'='*60}")
        print(f"🔧 [TOOL_PHASE] === TOOL EXECUTION PHASE ===")
        print(f"🔧 [TOOL_PHASE] Start time: {tool_phase_start:.3f}")
        print(f"🔧 [TOOL_PHASE] Tool calls requested: {len(tool_calls)}")
        for i, tc in enumerate(tool_calls):
            print(f"🔧 [TOOL_PHASE]   {i+1}. {tc['function']['name']}")
        print(f"🔧 [TOOL_PHASE] Note: SPLIT_TTS marker was already yielded")
        print(f"🔧 [TOOL_PHASE] Audio should be playing while this executes")
        print(f"{'='*60}\n")
        
        # Import database service (config already imported at module level)
        from src.services.database import get_database
        
        print(f"   📦 [TOOL_SETUP] Preparing services...")
        
        # Prepare services for tool execution
        # Use database calendar by default (scalable for SaaS)
        # Optional: Use Google Calendar if USE_GOOGLE_CALENDAR = True
        calendar = None
        if config.USE_GOOGLE_CALENDAR:
            try:
                from src.services.google_calendar import get_calendar_service as get_cal_service
                calendar = get_cal_service()
                print(f"   📦 [TOOL_SETUP] Using Google Calendar (OAuth-based)")
            except Exception as e:
                print(f"   ⚠️ [TOOL_SETUP] Could not load Google Calendar: {e}")
        
        # Always use database calendar as fallback (or primary if Google disabled)
        if calendar is None:
            try:
                from src.services.database_calendar import get_database_calendar_service
                calendar_company_id = int(company_id) if company_id else None
                calendar = get_database_calendar_service(company_id=calendar_company_id)
                print(f"   📦 [TOOL_SETUP] Using Database Calendar (company_id={calendar_company_id})")
            except Exception as e:
                print(f"   ❌ [TOOL_SETUP] Could not load database calendar: {e}")
        
        db = get_database()
        
        company_id_int = int(company_id) if company_id else None
        services = {
            'google_calendar': calendar,
            'calendar': calendar,
            'db': db,
            'company_id': company_id_int
        }
        print(f"   📦 [TOOL_SETUP] Services ready: calendar={calendar is not None}, db={db is not None}")
        
        # Execute each tool call and collect results
        tool_results = []
        
        # Yield control to event loop before tool execution
        # This allows other tasks (like audio playback) to run
        print(f"   ⏸️ [TOOL_EXEC] Yielding to event loop (allows audio to continue)...")
        await asyncio.sleep(0)
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call["function"]["name"]
            tool_id = tool_call["id"]
            
            print(f"\n   {'─'*50}")
            print(f"   🔧 [TOOL_EXEC] === Executing Tool {i+1}/{len(tool_calls)} ===")
            print(f"   🔧 [TOOL_EXEC] Name: {tool_name}")
            print(f"   🔧 [TOOL_EXEC] ID: {tool_id}")
            
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
                print(f"   🔧 [TOOL_EXEC] Arguments: {json.dumps(arguments)}")
                
                # Execute tool with timeout protection
                try:
                    tool_start = time.time()
                    print(f"   🔧 [TOOL_EXEC] Starting execution at {tool_start:.3f}...")
                    print(f"   🔧 [TOOL_EXEC] Running in thread pool (non-blocking)...")
                    
                    # Run tool execution in thread pool to not block event loop
                    # This allows audio playback to continue during tool execution
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,  # Use default thread pool
                        lambda: execute_tool_call(tool_name, arguments, services)
                    )
                    
                    tool_duration = time.time() - tool_start
                    print(f"   🔧 [TOOL_EXEC] ✅ Tool completed in {tool_duration:.3f}s")
                    
                    if not result:
                        print(f"   ⚠️ [TOOL_EXEC] Tool returned None!")
                        raise Exception("Tool returned None")
                    
                    print(f"   🔧 [TOOL_RESULT] Success: {result.get('success')}, Message: {result.get('message', result.get('error', 'N/A'))[:100]}")
                    
                    # Check if this is a transfer request
                    if result.get("transfer") and result.get("success"):
                        print(f"📞 [TRANSFER] TRANSFER REQUESTED: {result.get('reason')}")
                        print(f"📲 [TRANSFER] Will transfer to: {result.get('fallback_number')}")
                        # Add a special marker in the result for the media handler to detect
                        result["__TRANSFER_REQUESTED__"] = True
                        
                except Exception as tool_error:
                    print(f"   ⚠️ [TOOL_ERROR] Tool execution error for {tool_name}: {tool_error}")
                    print(f"   ⚠️ [TOOL_ERROR] Exception type: {type(tool_error).__name__}")
                    import traceback
                    traceback.print_exc()
                    result = {"success": False, "error": str(tool_error), "message": "Unable to complete request"}
                
                tool_results.append({
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(result)
                })
                
                print(f"   ✅ [TOOL_DONE] Result: {result.get('message', result.get('success'))}")
                
            except Exception as e:
                print(f"   ❌ [TOOL_ERROR] Error executing {tool_name}: {e}")
                print(f"   ❌ [TOOL_ERROR] Exception type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                tool_results.append({
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps({"success": False, "error": str(e)})
                })
        
        # Add assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": full_response if full_response else "",  # Empty string instead of None
            "tool_calls": tool_calls
        })
        
        # Add tool results to history
        messages.extend(tool_results)
        
        # Make another call to get LLM's response based on tool results
        tool_exec_duration = time.time() - tool_phase_start
        print(f"   🔧 [TOOL_PHASE] Tool execution complete in {tool_exec_duration:.3f}s")
        print("   🔄 Getting LLM response with tool results...")
        print(f"   📊 Tool results being sent to LLM: {[{**tr, 'content': tr['content'][:100] + '...' if len(tr['content']) > 100 else tr['content']} for tr in tool_results]}")
        try:
            # Add a system message to ensure LLM provides a complete response WITHOUT repeating the checking message
            messages.append({
                "role": "system",
                "content": "[CRITICAL INSTRUCTION: You ALREADY told the customer 'let me check that for you'. The tool has COMPLETED. You MUST NOW provide the actual results - DO NOT go silent, DO NOT say 'let me check' again. The customer is waiting for your answer. Start immediately with the results: 'I have [times] available' or 'Great to hear from you again!' or 'Your appointment is confirmed' or 'I found your appointment'. NEVER leave the customer waiting in silence.]"
            })
            
            # Sanitize messages again before follow-up call (safety check)
            follow_up_messages = sanitize_messages(messages)
            
            # Apply same final safety check for follow-up call
            follow_up_final = []
            seen_ids = set()
            for msg in follow_up_messages:
                if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                    for tc in msg.get('tool_calls', []):
                        seen_ids.add(tc.get('id'))
                    follow_up_final.append(msg)
                elif msg.get('role') == 'tool':
                    if msg.get('tool_call_id') in seen_ids:
                        follow_up_final.append(msg)
                    else:
                        print(f"🚨 [FOLLOW_UP_CHECK] Removing orphaned tool: {msg.get('name')}")
                else:
                    follow_up_final.append(msg)
            
            follow_up_stream = client.chat.completions.create(
                model=config.CHAT_MODEL,
                stream=True,
                temperature=0.2,  # Optimal balance for natural but fast responses
                max_tokens=200,   # Reduced for faster completion  
                presence_penalty=0.1,
                frequency_penalty=0.1,
                messages=[{"role": "system", "content": system_prompt_with_time}, *follow_up_final],
                tools=CALENDAR_TOOLS,
                tool_choice="none",  # Prevent nested tool calls
                top_p=0.9,  # Focus on most likely tokens
                stream_options={"include_usage": False}  # Disable usage tracking for speed
            )
            
            follow_up_response = ""
            follow_up_token_count = 0
            follow_up_start = time.time()
            print(f"   ⏳ [FOLLOW_UP] Starting follow-up stream at {follow_up_start:.3f}")
            
            # Add timeout protection to prevent infinite hangs
            timeout_seconds = 20  # Increased to prevent cutting off longer responses
            
            for part in follow_up_stream:
                # Check timeout
                if time.time() - follow_up_start > timeout_seconds:
                    print(f"⚠️ WARNING: Follow-up stream timed out after {timeout_seconds}s")
                    break
                    
                delta = part.choices[0].delta.content
                if delta:
                    follow_up_token_count += 1
                    token_time = time.time() - follow_up_start
                    # Strip markdown formatting
                    cleaned_delta = delta.replace('**', '').replace('__', '').replace('~~', '')
                    follow_up_response += delta  # Keep original
                    if follow_up_token_count == 1:
                        print(f"   🗣️ [FOLLOW_UP] First token at {token_time:.3f}s: '{cleaned_delta[:50]}...'")
                    elif follow_up_token_count % 20 == 0:
                        print(f"   🗣️ [FOLLOW_UP] Token #{follow_up_token_count} at {token_time:.3f}s")
                    yield cleaned_delta  # Send cleaned to TTS
            
            total_follow_up_time = time.time() - follow_up_start
            print(f"   📊 [FOLLOW_UP] Stream complete: {follow_up_token_count} tokens in {total_follow_up_time:.3f}s")
            
            # Check if any tool result requested a transfer
            transfer_requested = False
            transfer_info = None
            for tr in tool_results:
                try:
                    result_data = json.loads(tr["content"])
                    if result_data.get("__TRANSFER_REQUESTED__"):
                        transfer_requested = True
                        transfer_info = result_data
                        print(f"📞 Transfer flag detected in tool results")
                        break
                except:
                    pass
            
            if follow_up_token_count == 0:
                print("⚠️ WARNING: Follow-up LLM call generated NO tokens!")
                print(f"   🔍 Debug - Last messages sent to LLM:")
                for i, msg in enumerate(messages[-5:]):
                    role = msg.get('role', 'unknown')
                    content = str(msg.get('content', ''))[:100]
                    print(f"      [{i}] {role}: {content}...")
                
                # Create a context-aware fallback based on the tool that was called
                tool_name = tool_calls[0]["function"]["name"] if tool_calls else None
                
                if tool_name == "check_availability":
                    # Parse the tool result to see what slots were found
                    try:
                        result_content = json.loads(tool_results[0]["content"])
                        if result_content.get("success") and result_content.get("available_times"):
                            times = result_content["available_times"]
                            if len(times) > 0:
                                times_str = ", ".join(times[:3])  # Show first 3
                                fallback = f"I have {times_str} available. Which works best for you?"
                            else:
                                fallback = "Unfortunately that time is fully booked. Would you like to try a different day?"
                        else:
                            fallback = result_content.get("message", "I've checked that for you. What time would work best?")
                    except:
                        fallback = "I've checked that for you. What time would work best?"
                elif tool_name == "lookup_customer":
                    # Parse the lookup result to provide appropriate response
                    try:
                        result_content = json.loads(tool_results[0]["content"])
                        if result_content.get("success"):
                            if result_content.get("is_returning"):
                                customer_name = result_content.get("customer_name", "")
                                fallback = f"Great to hear from you again, {customer_name}! What can I help you with today?"
                            else:
                                fallback = "Welcome! I'll get you set up in our system. What can I help you with today?"
                        else:
                            fallback = "I couldn't find that name in our system. Let me set you up as a new customer. What can I help you with?"
                    except:
                        fallback = "Thanks for that. What can I help you with today?"
                elif tool_name in ["book_appointment", "book_job"]:
                    fallback = "You're all booked! Anything else I can help with?"
                elif tool_name in ["cancel_appointment", "cancel_job"]:
                    fallback = "That's cancelled for you. Anything else?"
                elif tool_name in ["reschedule_appointment", "reschedule_job"]:
                    fallback = "I've moved that for you. Anything else?"
                elif tool_name == "transfer_to_human":
                    fallback = "Let me transfer you now. Please hold."
                else:
                    fallback = "I've checked that for you. What would work best for you?"
                
                print(f"   ⚠️ Using context-aware fallback response: '{fallback}'")
                yield fallback
                follow_up_response = fallback
            else:
                print(f"   ✅ Follow-up complete: {follow_up_token_count} tokens, response: '{follow_up_response[:100]}...'")
            
            # Store the follow-up response
            if follow_up_response:
                cleaned = remove_repetition(follow_up_response.strip())
                messages.append({"role": "assistant", "content": cleaned})
            
            # After the response is sent, check if transfer was requested
            if transfer_requested and transfer_info:
                print(f"📞 INITIATING TRANSFER TO: {transfer_info.get('fallback_number')}")
                # Yield special transfer marker that the media handler will detect
                yield f"<<<TRANSFER:{transfer_info.get('fallback_number')}>>>"
                
        except Exception as e:
            print(f"❌ Error in follow-up LLM stream: {e}")
            import traceback
            traceback.print_exc()
            error_msg = "I've checked that for you. What time would work best for you?"
            print(f"   ⚠️ Yielding error fallback: '{error_msg}'")
            yield error_msg
            messages.append({"role": "assistant", "content": error_msg})
    
    # Store cleaned response for context (if no tool calls were made)
    elif full_response:
        cleaned = remove_repetition(full_response.strip())
        messages.append({"role": "assistant", "content": cleaned})
    else:
        print("⚠️ WARNING: LLM generated NO content and NO tool calls!")
        # Always yield something to prevent silence
        fallback_response = "How can I help you today?"
        yield fallback_response
        messages.append({"role": "assistant", "content": fallback_response})


async def process_appointment_with_calendar(intent: AppointmentIntent, details: dict, company_id: int = None) -> bool:
    """
    Process appointment actions with Google Calendar
    
    NOTE: This is a LEGACY function. The main booking flow now uses the tool-based system
    in stream_llm() which properly passes company_id. This function is kept for backwards
    compatibility but should not be used for new bookings.
    
    Args:
        intent: The appointment intent
        details: Appointment details dictionary
        company_id: Company ID for multi-tenant data isolation (REQUIRED for proper isolation)
        
    Returns:
        True if booking was successful, False otherwise
    """
    calendar = get_calendar_service()
    
    if not calendar:
        print("⚠️ Google Calendar not available - appointment logged only")
        return False
    
    try:
        if intent == AppointmentIntent.BOOK:
            # Parse the requested time from user's speech
            time_reference = details.get("datetime")
            if not time_reference:
                print("❌ No datetime found in details")
                return False
                
            requested_time = parse_datetime(time_reference)
            
            print(f"📅 Requested time: {requested_time.strftime('%B %d, %Y at %I:%M %p')}")
            
            # STEP 1: Check availability first
            print("🔍 Checking calendar availability...")
            is_available = calendar.check_availability(requested_time, duration_minutes=DEFAULT_APPOINTMENT_DURATION_MINUTES)
            
            if not is_available:
                print("\n" + "="*60)
                print("❌ TIME SLOT IS BUSY")
                print("="*60)
                print(f"⏰ Requested: {requested_time.strftime('%B %d at %I:%M %p')}")
                
                # Get alternative times
                alternatives = calendar.get_alternative_times(requested_time, days_to_check=3)
                if alternatives:
                    print("\n💡 Alternative available times:")
                    for i, alt_time in enumerate(alternatives, 1):
                        print(f"   {i}. {alt_time.strftime('%A, %B %d at %I:%M %p')}")
                    print("\n📢 The LLM should inform the user of these alternatives")
                else:
                    print("💡 No alternative times found in the next 3 days")
                
                print("="*60 + "\n")
                return False
            
            print("✅ Time slot is AVAILABLE - proceeding with booking")
            
            # STEP 2: Prepare booking details
            service = details.get("service_type") or "General"
            customer_name = details.get("customer_name", "Customer")
            phone_number = details.get("phone_number", "")
            summary = f"{service.title()} - {customer_name}"
            
            # STEP 3: Book the appointment
            print(f"📝 Booking: {summary}")
            event = calendar.book_appointment(
                summary=summary,
                start_time=requested_time,
                duration_minutes=DEFAULT_APPOINTMENT_DURATION_MINUTES,
                description=f"Booked via AI receptionist\nCustomer: {customer_name}\nReason: {details.get('service_type', 'General appointment')}\nDetails: {details.get('raw_text', 'N/A')}",
                phone_number=phone_number
            )
            
            # STEP 4: Save to database
            if event:
                try:
                    from src.services.database import get_database
                    db = get_database()
                    
                    # Initialize email to avoid undefined variable error
                    email = details.get('email')
                    
                    # Find or create client using phone/email (trades business doesn't use DOB)
                    # CRITICAL: Pass company_id for proper multi-tenant data isolation
                    try:
                        client_id = db.find_or_create_client(
                            name=customer_name,
                            phone=phone_number if phone_number else None,
                            email=email,
                            date_of_birth=None,  # DOB not collected for trades
                            company_id=company_id
                        )
                        
                        # Get the client info to ensure we have contact details
                        client = db.get_client(client_id, company_id=company_id)
                        if client:
                            phone_number = client.get('phone') or phone_number
                            email = client.get('email') or email
                    except ValueError:
                        # No phone or email provided, use a placeholder
                        print("⚠️ No contact info provided, using 'unknown' as placeholder")
                        client_id = db.find_or_create_client(
                            name=customer_name,
                            phone="unknown",
                            email=None,
                            date_of_birth=None,
                            company_id=company_id
                        )
                        phone_number = "unknown"
                        email = None
                    
                    # Add booking (will auto-populate contact info from client if not provided)
                    # Extract urgency, address, and property type from details
                    urgency = details.get('urgency', 'scheduled')
                    address = details.get('address')
                    eircode = details.get('eircode')
                    property_type = details.get('property_type')
                    
                    # CRITICAL: Pass company_id for proper multi-tenant data isolation
                    booking_id = db.add_booking(
                        client_id=client_id,
                        calendar_event_id=event.get('id'),
                        appointment_time=requested_time,
                        service_type=service,
                        phone_number=phone_number,
                        email=email,
                        urgency=urgency,
                        address=address,
                        eircode=eircode,
                        property_type=property_type,
                        company_id=company_id
                    )
                    
                    # Add initial appointment note with booking details
                    initial_note = f"Booked via AI receptionist. Reason: {details.get('service_type', 'General appointment')}"
                    if details.get('raw_text'):
                        initial_note += f"\nCustomer said: {details.get('raw_text')}"
                    db.add_appointment_note(booking_id, initial_note, created_by="system")
                    
                    # Update client description after booking
                    try:
                        from src.services.client_description_generator import update_client_description
                        update_client_description(client_id)
                    except Exception as desc_error:
                        print(f"⚠️ Failed to update client description: {desc_error}")
                    
                    print("✅ Saved to database")
                except Exception as e:
                    print(f"⚠️ Database save failed: {e}")
                
                # STEP 5: Confirm booking
                event_time = requested_time.strftime('%B %d at %I:%M %p')
                print(f"\n{'='*60}")
                print(f"✅ BOOKING SUCCESSFUL!")
                print(f"{'='*60}")
                print(f"👤 Customer: {customer_name}")
                print(f"📞 Phone: {phone_number}")
                print(f"📅 Date/Time: {event_time}")
                print(f"🏥 Service: {service}")
                print(f"🆔 Event ID: {event.get('id')}")
                print(f"🔗 Calendar Link: {event.get('htmlLink')}")
                print(f"{'='*60}\n")
                return True
            else:
                print("❌ Failed to create calendar event - API returned None")
                return False
        
        elif intent == AppointmentIntent.CANCEL:
            # Find appointment to cancel
            customer_name = details.get("customer_name")
            time_reference = details.get("datetime")
            appointment_time = None
            
            if time_reference:
                try:
                    appointment_time = parse_datetime(time_reference)
                except Exception as e:
                    print(f"⚠️ Error parsing time reference '{time_reference}': {e}")
            
            # Search for the appointment
            event = calendar.find_appointment_by_details(customer_name, appointment_time)
            
            if event:
                # Cancel the appointment
                event_id = event.get('id')
                event_summary = event.get('summary', 'Unknown')
                event_time_str = event.get('start', {}).get('dateTime', 'Unknown time')
                
                success = calendar.cancel_appointment(event_id)
                
                if success:
                    # DELETE booking from database completely - MUST filter by company_id for data isolation
                    try:
                        from src.services.database import get_database
                        db = get_database()
                        # Find the booking by calendar event ID and DELETE it
                        # Use company_id from function parameter
                        bookings = db.get_all_bookings(company_id=company_id)
                        for booking in bookings:
                            if booking.get('calendar_event_id') == event_id:
                                # Delete booking completely from database
                                db.delete_booking(booking['id'], company_id=company_id)
                                print(f"✅ DELETED booking from database (ID: {booking['id']}, company_id: {company_id})")
                                break
                    except Exception as e:
                        print(f"⚠️ Failed to delete booking from database: {e}")
                    
                    print(f"\n{'='*60}")
                    print(f"✅ CANCELLATION SUCCESSFUL!")
                    print(f"{'='*60}")
                    print(f"❌ Cancelled: {event_summary}")
                    print(f"📅 Was scheduled for: {event_time_str}")
                    print(f"{'='*60}\n")
                    return True
                else:
                    print(f"❌ Failed to cancel appointment")
                    return False
            else:
                print(f"❌ Could not find appointment to cancel")
                return False
        
        elif intent == AppointmentIntent.RESCHEDULE:
            # Find appointment to reschedule
            customer_name = details.get("customer_name")
            old_time_reference = details.get("datetime")  # This should be the OLD time
            new_time_reference = details.get("new_datetime")  # This should be the NEW time
            
            # Check for vague time references that shouldn't trigger automatic rescheduling
            vague_times = ['earlier', 'later', 'sooner', 'another time', 'different time']
            if new_time_reference and any(vague in new_time_reference.lower() for vague in vague_times):
                print(f"⚠️ Vague time reference detected: '{new_time_reference}' - asking user for specific time")
                return "need_specific_time"  # Special return value to indicate we need more info
            
            # Parse times
            old_time = None
            new_time = None
            
            if old_time_reference:
                try:
                    old_time = parse_datetime(old_time_reference)
                except Exception as e:
                    print(f"⚠️ Error parsing old time reference '{old_time_reference}': {e}")
            
            if new_time_reference:
                try:
                    # CRITICAL FIX: Check if new_time has date BEFORE parsing
                    # If only time provided (e.g., "1pm", "same day"), combine with old date first
                    date_patterns = [
                        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
                        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b',
                        r'\b\d{1,2}(?:st|nd|rd|th)?\b',  # Day number like "26" or "26th"
                        r'\b(tomorrow|today|next|this)\b',
                        r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b'
                    ]
                    has_date = any(re.search(pattern, new_time_reference.lower()) for pattern in date_patterns)
                    
                    print(f"🔍 Reschedule Analysis:")
                    print(f"   New time reference: '{new_time_reference}'")
                    print(f"   Has date indicator: {has_date}")
                    print(f"   Old time: {old_time.strftime('%B %d, %Y at %I:%M %p') if old_time else 'None'}")
                    
                    # If no date and we have old_time, combine before parsing
                    if not has_date and old_time:
                        combined_text = old_time.strftime('%A') + ' ' + new_time_reference
                        print(f"🔄 Same-day reschedule: combining '{old_time.strftime('%A')}' + '{new_time_reference}' -> '{combined_text}'")
                        new_time = parse_datetime(combined_text)
                        print(f"✅ Parsed combined time: {new_time.strftime('%B %d, %Y at %I:%M %p') if new_time else 'None'}")
                    else:
                        new_time = parse_datetime(new_time_reference)
                        print(f"   Parsed new time: {new_time.strftime('%B %d, %Y at %I:%M %p') if new_time else 'None'}")
                    
                except Exception as e:
                    print(f"⚠️ Could not parse new time '{new_time_reference}': {e}")
            
            if not new_time:
                print("❌ No specific new time provided for rescheduling")
                return "need_specific_time"  # Ask for specific time instead of failing
            
            # Check if new time is available
            print(f"🔍 Checking if new time {new_time.strftime('%B %d at %I:%M %p')} is available...")
            is_available = calendar.check_availability(new_time, duration_minutes=DEFAULT_APPOINTMENT_DURATION_MINUTES)
            
            if not is_available:
                print(f"❌ New time slot is already busy")
                # Return special value to indicate slot unavailable (not generic failure)
                return "slot_unavailable"
            
            # Find the old appointment by TIME ONLY (name should already be verified in the flow above)
            event = calendar.find_appointment_by_details(customer_name=None, appointment_time=old_time)
            
            if event:
                event_id = event.get('id')
                event_summary = event.get('summary', 'Unknown')
                old_time_str = event.get('start', {}).get('dateTime', 'Unknown')
                
                # Reschedule the appointment in Google Calendar
                updated_event = calendar.reschedule_appointment(event_id, new_time)
                
                if updated_event:
                    # Also update the database
                    try:
                        from src.services.database import get_database
                        db = get_database()
                        # Find booking by calendar_event_id using database method - filter by company_id for data isolation
                        booking = db.get_booking_by_calendar_event_id(event_id, company_id=company_id)
                        
                        if booking:
                            booking_id = booking['id']
                            # Update the appointment time in database - pass company_id for security
                            db.update_booking(booking_id, company_id=company_id, appointment_time=new_time)
                            print(f"✅ Updated database for booking ID {booking_id} (company_id: {company_id})")
                        else:
                            print(f"⚠️ No database booking found for event {event_id} (company_id: {company_id})")
                    except Exception as db_error:
                        print(f"⚠️ Failed to update database: {db_error}")
                    
                    print(f"\n{'='*60}")
                    print(f"✅ RESCHEDULING SUCCESSFUL!")
                    print(f"{'='*60}")
                    print(f"📝 Appointment: {event_summary}")
                    print(f"📅 Old time: {old_time_str}")
                    print(f"📅 New time: {new_time.strftime('%B %d, %Y at %I:%M %p')}")
                    print(f"{'='*60}\n")
                    return True
                else:
                    print(f"❌ Failed to reschedule appointment")
                    return False
            else:
                print(f"❌ Could not find appointment to reschedule")
                return False
        
        elif intent == AppointmentIntent.QUERY:
            # --- Enhanced logic: handle "next week" by checking ALL weekdays ---
            time_reference = details.get("datetime") or call_state.get("datetime")
            print(f"🔍 DEBUG QUERY: time_reference = {time_reference}")
            print(f"🔍 DEBUG QUERY: details = {details}")
            print(f"🔍 DEBUG QUERY: call_state = {call_state}")

            # Extract time window (e.g., after 2, between 2 and 4, late times)
            start_hour, end_hour = extract_time_window(time_reference or '')
            print(f"🔍 Extracted time window: {start_hour} to {end_hour}")

            # Helper to filter slots by time window (inclusive)
            def filter_slots(slots, start_hour, end_hour):
                if start_hour is None and end_hour is None:
                    return slots
                filtered = [s for s in slots if (start_hour if start_hour is not None else 0) <= s.hour <= (end_hour if end_hour is not None else 23)]
                return filtered

            now = datetime.now()
            
            # Check if "next week" was requested
            is_next_week_query = False
            if time_reference and ('next week' in time_reference.lower()):
                is_next_week_query = True
            
            if is_next_week_query:
                # Handle "next week" - check all weekdays of next week
                print(f"📅 Detected 'next week' query - will check all weekdays")
                
                # Calculate start of next week (next Monday)
                days_until_next_monday = (7 - now.weekday()) % 7
                if days_until_next_monday == 0:  # If today is Monday
                    days_until_next_monday = 7  # Go to next Monday
                
                next_monday = (now + timedelta(days=days_until_next_monday)).replace(hour=9, minute=0, second=0, microsecond=0)
                
                # Check Monday through Friday of next week
                all_slots_by_day = {}
                for day_offset in range(5):  # Monday to Friday
                    check_date = next_monday + timedelta(days=day_offset)
                    slots = calendar.get_available_slots_for_day(check_date)
                    filtered = filter_slots(slots, start_hour, end_hour)
                    if filtered:
                        all_slots_by_day[check_date.date()] = filtered
                
                if all_slots_by_day:
                    print(f"\n{'='*60}")
                    print(f"📅 AVAILABILITY QUERY: Next week")
                    print(f"✅ Found slots on {len(all_slots_by_day)} day(s):")
                    
                    result_slots = []
                    for date, slots in sorted(all_slots_by_day.items()):
                        day_name = datetime.combine(date, datetime.min.time()).strftime('%A')
                        print(f"   {day_name}, {date.strftime('%B %d')}: {len(slots)} slots")
                        for slot in slots:
                            result_slots.append({
                                'datetime': slot,
                                'date': date,
                                'formatted': slot.strftime('%I:%M %p'),
                                'day_name': day_name,
                                'full_formatted': f"{day_name}, {date.strftime('%B %d')} at {slot.strftime('%I:%M %p')}"
                            })
                            print(f"      - {slot.strftime('%I:%M %p')}")
                    
                    print(f"{'='*60}\n")
                    return result_slots
                else:
                    print(f"\n{'='*60}")
                    print(f"📅 AVAILABILITY QUERY: Next week")
                    print(f"❌ No available slots found for next week")
                    print(f"{'='*60}\n")
                    return None
            
            # Handle specific date queries (existing logic)
            query_date = None
            
            # CRITICAL FIX: If in reschedule flow asking about "same day", use the old appointment date
            in_reschedule = call_state.get("reschedule_found_appointment")
            if in_reschedule:
                old_event_time = in_reschedule.get('start', {}).get('dateTime')
                if old_event_time:
                    try:
                        # Parse the ISO datetime from the event
                        from dateutil import parser as dateutil_parser
                        old_appointment_datetime = dateutil_parser.isoparse(old_event_time)
                        # Use this as the reference date for "same day" queries
                        query_date = old_appointment_datetime.replace(hour=9, minute=0, second=0, microsecond=0)
                        print(f"🔄 In reschedule flow - using old appointment date as reference: {query_date.strftime('%B %d, %Y')}")
                    except Exception as e:
                        print(f"⚠️ Could not parse old appointment time: {e}")
            
            # Try to parse a specific date (if not already set from reschedule context)
            if not query_date and time_reference:
                # For QUERY intent, don't require time - use 9 AM as default
                parsed_date = parse_datetime(time_reference, require_time=False, default_time=(9, 0))
                if parsed_date:
                    query_date = parsed_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            if not query_date:
                query_date = now.replace(hour=9, minute=0, second=0, microsecond=0)
            
            # Check the REQUESTED day first (don't search other days)
            if not is_business_day(query_date):
                day_name = query_date.strftime('%A')
                print(f"⚠️ Requested day is closed: {day_name}, {query_date.strftime('%B %d')} - not available")
                print(f"\n{'='*60}")
                print(f"📅 AVAILABILITY QUERY: Closed day requested (office closed on {day_name}s)")
                print(f"{'='*60}\n")
                # Return empty list with message that office is closed on this day
                return []
            
            # Check the specific requested day only
            slots = calendar.get_available_slots_for_day(query_date)
            filtered = filter_slots(slots, start_hour, end_hour)
            
            found_slots = []
            found_date = None
            if filtered:
                found_slots = filtered
                found_date = query_date.date()
            
            print(f"\n{'='*60}")
            if found_date:
                print(f"📅 AVAILABILITY QUERY for {query_date.strftime('%B %d, %Y')} ({query_date.strftime('%A')})")
            else:
                print(f"📅 AVAILABILITY QUERY: No slots available on {query_date.strftime('%B %d, %Y')} ({query_date.strftime('%A')})")
            print(f"{'='*60}")
            if found_slots and found_date:
                print(f"✅ Found {len(found_slots)} available slots:")
                for slot in found_slots:
                    print(f"   - {slot.strftime('%I:%M %p')}")
                print(f"{'='*60}\n")
                # Return slots with the date they're on
                # Format: list of dicts with 'datetime' and 'formatted' keys
                result_slots = []
                for slot in found_slots:
                    result_slots.append({
                        'datetime': slot,
                        'date': found_date,
                        'formatted': slot.strftime('%I:%M %p'),
                        'full_formatted': f"{found_date.strftime('%B %d, %Y')} at {slot.strftime('%I:%M %p')}"
                    })
                return result_slots
            else:
                print(f"❌ No available slots found matching the requested criteria")
                print(f"{'='*60}\n")
                return None
        
    except Exception as e:
        print(f"❌ Error processing with calendar: {e}")
        return False
