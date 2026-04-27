"""
LLM streaming service with tool-based appointment handling

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
from datetime import datetime, timedelta


# Configuration constants
DEFAULT_APPOINTMENT_DURATION_MINUTES = 1440  # Default duration for AI phone bookings (1 day for trades)


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

def humanize_times_for_tts(text: str) -> str:
    """
    Convert clock-format times into TTS-friendly spoken word forms.
    
    TTS engines read "1:30" as "one three zero" instead of "one thirty".
    This converts times to written-out words so they sound natural when spoken aloud.
    
    Examples:
        "9:00 AM"  -> "nine AM"
        "10:00am"  -> "ten am"
        "2:30 PM"  -> "two thirty PM"
        "12:15pm"  -> "twelve fifteen pm"
        "1:30 pm"  -> "one thirty pm"
        "01:00 PM" -> "one PM"
    """
    if not text:
        return text
    
    # Number-to-word mapping for hours
    hour_words = {
        '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five',
        '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten',
        '11': 'eleven', '12': 'twelve'
    }
    
    # Minute-to-word mapping for common minutes
    minute_words = {
        '00': '', '05': 'oh five', '10': 'ten', '15': 'fifteen',
        '20': 'twenty', '25': 'twenty five', '30': 'thirty',
        '35': 'thirty five', '40': 'forty', '45': 'forty five',
        '50': 'fifty', '55': 'fifty five'
    }
    
    def replace_time(match):
        hour = match.group(1)
        minutes = match.group(2)
        period = match.group(3)
        
        # Strip leading zero (e.g., "01" -> "1") before lookup
        hour_stripped = hour.lstrip('0') or '0'
        hour_word = hour_words.get(hour_stripped, hour)
        
        if minutes == '00':
            return f"{hour_word} {period}"
        
        min_word = minute_words.get(minutes)
        if min_word:
            return f"{hour_word} {min_word} {period}"
        
        # Fallback for uncommon minutes
        return f"{hour_word} {minutes} {period}"
    
    # Remove :00 from on-the-hour times and convert non-zero minutes to words
    result = re.sub(r'(\d{1,2}):(\d{2})\s*((?:a|p)\.?m\.?)', replace_time, text, flags=re.IGNORECASE)
    
    return result

def sanitize_for_tts(text: str) -> str:
    """
    Remove bullet points, dashes, and newline formatting that causes TTS engines
    (like Deepgram) to stop speaking mid-sentence.

    TTS interprets '\\n- ' as end of speech, so we convert list formatting
    into comma-separated natural speech.

    Examples:
        "I have:\\n- Monday at 9 am\\n- Tuesday at 2 pm" -> "I have: Monday at 9 am, Tuesday at 2 pm"
        "Available days:\\n• Monday\\n• Tuesday" -> "Available days: Monday, Tuesday"
    """
    if not text:
        return text

    # Replace newline + bullet/dash patterns with comma-space
    # Handles: \n- , \n• , \n* , \n·
    result = re.sub(r'\n\s*[-•*·]\s*', ', ', text)

    # Replace remaining newlines with space
    result = re.sub(r'\n+', ' ', result)

    # Clean up any resulting double commas or comma after colon
    result = re.sub(r':\s*,\s*', ': ', result)
    result = re.sub(r',\s*,', ',', result)

    # Clean up leading/trailing whitespace
    result = result.strip()

    # Convert clock times to TTS-friendly spoken forms (e.g., "9:00 AM" -> "9 AM")
    result = humanize_times_for_tts(result)

    return result

# Lazy initialization of OpenAI client with optimized settings
_client = None

def get_openai_client():
    """Get or create OpenAI client instance with optimized connection settings"""
    global _client
    if _client is None:
        import httpx
        # Create client with reasonable timeouts
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
                'coverage_area': company.get('coverage_area') or '',
                'industry_type': company.get('industry_type') or 'trades',
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
        'coverage_area': '',
        'industry_type': 'trades',
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


def _build_packages_prompt_section(packages_list):
    """Build the PACKAGES OFFERED section for the AI prompt.
    Returns empty string if no packages exist (no prompt bloat)."""
    if not packages_list:
        return ""

    lines = ["PACKAGES OFFERED (bundles of multiple services):"]
    for pkg in packages_list:
        service_names = " → ".join(s['name'] for s in pkg.get('services', []))
        price = pkg.get('total_price', 0)
        price_max = pkg.get('total_price_max')
        duration_label = pkg.get('duration_label', '')

        uncertain_hint = " [REQUIRES INVESTIGATION — use when caller's issue needs diagnosing first]" if pkg.get('use_when_uncertain') else ""
        line = f"📦 {pkg['name']}{uncertain_hint} | Services: {service_names}"

        if price_max and float(price_max) > float(price):
            line += f" | Price: €{price} to €{price_max}"
        else:
            line += f" | Price: €{price}"

        line += f" | Duration: {duration_label}"

        lines.append(line)

    return "\n".join(lines) + "\n"


def load_system_prompt(company_id=None):
    """Load system prompt from file and inject business information.
    When company_id is provided, loads that company's specific info.
    
    CACHING: For company_id=None (default), uses cached SYSTEM_PROMPT.
    For specific company_id, loads fresh from DB (company-specific data).
    """
    import time as time_module
    prompt_start = time_module.time()
    
    print(f"\n[PROMPT_DEBUG] load_system_prompt called with company_id={company_id}")
    
    # Load business info first — we need industry_type to pick the right prompt
    biz_info_start = time_module.time()
    print(f"[PROMPT_DEBUG] Loading business info...")
    business_info = load_business_info(company_id=company_id)
    biz_info_time = time_module.time() - biz_info_start
    print(f"[PROMPT_DEBUG] Business info loaded in {biz_info_time*1000:.1f}ms")
    
    # Pick prompt file based on industry type (or minimal for debugging)
    use_minimal = config.USE_MINIMAL_PROMPT
    if use_minimal:
        print(f"[PROMPT_DEBUG] ⚡ USING MINIMAL PROMPT (USE_MINIMAL_PROMPT=true)")
        prompt_file = 'receptionist_prompt_minimal.txt'
    else:
        from src.utils.industry_config import get_prompt_file
        industry_type = business_info.get('industry_type', 'trades')
        prompt_file = get_prompt_file(industry_type)
        print(f"[PROMPT_DEBUG] Industry: {industry_type} → prompt: {prompt_file}")
    
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
        'prompts', prompt_file
    )
    
    # Fall back to trades prompt if the industry-specific file doesn't exist yet
    if not os.path.exists(prompt_path) or os.path.getsize(prompt_path) == 0:
        print(f"[PROMPT_DEBUG] Prompt file '{prompt_file}' missing or empty, falling back to trades_prompt.txt")
        prompt_file = 'trades_prompt.txt'
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'prompts', prompt_file
        )
    
    print(f"[PROMPT_DEBUG] Loading prompt from: {prompt_file}")
    
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
        
        # Load active packages for this company
        from src.services.settings_manager import get_settings_manager
        packages_list = []
        try:
            settings_mgr = get_settings_manager()
            packages_list = settings_mgr.get_packages(company_id=company_id)
            print(f"[PROMPT_DEBUG] Loaded {len(packages_list)} packages for company {company_id}")
            for pkg in packages_list:
                print(f"[PROMPT_DEBUG]   📦 {pkg.get('name')} (uncertain={pkg.get('use_when_uncertain')}, services={len(pkg.get('services', []))})")
        except Exception as e:
            print(f"[WARNING] Error loading packages: {e}")
            import traceback
            traceback.print_exc()
            packages_list = []
        
        # Build services list from menu (exclude package_only services)
        services_list = []
        now_month = datetime.now().month - 1  # 0-indexed to match frontend
        for service in services_menu.get('services', []):
            if service.get('active', True) and not service.get('package_only', False):
                # Skip seasonal services outside their active months
                if service.get('seasonal'):
                    months = service.get('seasonal_months')
                    if isinstance(months, str):
                        try:
                            import json as _j
                            months = _j.loads(months)
                        except Exception:
                            months = None
                    if months and isinstance(months, list) and now_month not in months:
                        continue

                price = service['price']
                price_max = service.get('price_max')
                if price_max and float(price_max) > float(price):
                    service_line = f"{service['name']} ({service['category']}) | Price: €{price} to €{price_max}"
                else:
                    service_line = f"{service['name']} ({service['category']}) | Price: €{price}"
                if service.get('emergency_price'):
                    service_line += f" (Emergency: €{service['emergency_price']})"
                service_line += f" | Duration: {service['duration_minutes']} minutes"
                if service.get('requires_callout'):
                    service_line += " [CALLOUT REQUIRED]"
                if service.get('requires_quote'):
                    service_line += " [QUOTE REQUIRED]"
                if service.get('requires_deposit'):
                    dep = service.get('deposit_amount')
                    service_line += f" [DEPOSIT: €{dep}]" if dep else " [DEPOSIT REQUIRED]"
                if service.get('warranty'):
                    service_line += f" [WARRANTY: {service['warranty']}]"
                if service.get('ai_notes'):
                    service_line += f" — NOTE: {service['ai_notes']}"
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

{_build_packages_prompt_section(packages_list)}
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
    Check if caller exists in database by phone number (primary) or name (fallback).
    MUST pass company_id for proper multi-tenant data isolation.
    Returns dict with client info or indication of new customer.
    """
    from src.services.database import get_database
    db = get_database()
    
    # Phone-first lookup
    if caller_phone:
        client = db.find_client_by_phone(caller_phone, company_id=company_id)
        if client:
            print(f"[CLIENT] Returning customer found by phone: {client['name']} (ID: {client['id']}, company_id: {company_id})")
            description_text = f"\n\nCustomer History: {client['description']}" if client.get('description') else ""
            return {
                "status": "returning",
                "message": f"Welcome back, {client['name']}!{description_text}",
                "clients": [client]
            }
    
    # No phone match — new customer
    print(f"[CLIENT] New customer: phone={caller_phone} (company_id: {company_id})")
    return {
        "status": "new",
        "message": "New customer — phone not in our system.",
        "clients": []
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

async def stream_llm(messages, caller_phone=None, company_id=None, call_state: CallState = None):
    """
    Stream LLM responses with tool-based appointment handling
    
    Args:
        messages: Conversation history
        caller_phone: Caller's phone number from Telnyx
        company_id: Company ID for multi-tenant business context
        call_state: Per-call state for concurrent call handling. If None, creates
                   a new instance (not recommended for production - pass explicitly).
        
    Yields:
        Text tokens from LLM
    """
    import time as time_module
    llm_start_time = time_module.time()
    
    print(f"\n[LLM] stream_llm started | {len(messages)} msgs")

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
    
    # Post-booking cooldown: for a few turns after booking, be extra careful about reschedule detection
    # and don't trigger availability/booking pre-check fillers (prevents confirmation loops)
    in_post_booking_cooldown = (last_booking_turn > 0 and current_turn - last_booking_turn <= 3)
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
        # Automatically confirm phone if it came from caller ID
        call_state["phone_confirmed"] = True
        print(f"[PHONE] Caller phone automatically captured: {caller_phone}")
    
    # PRE-CHECK: Detect if user message likely requires a tool call
    # If so, speak acknowledgment IMMEDIATELY before calling OpenAI
    # SIMPLIFIED: Only trigger for HIGH-CONFIDENCE tool call scenarios
    # Misfires (filler plays but no tool) are worse than no filler at all
    
    # === GOODBYE FAST-PATH ===
    # When the caller says "nothing else" / "no thanks" / "that's it" after we asked
    # "anything else?", bypass the LLM entirely and respond with a warm goodbye.
    # This prevents the 2-3s LLM delay that can cause the caller to hang up before hearing goodbye.
    _user_msg_lower = user_text.lower().strip() if user_text else ""
    _prev_assistant = ""
    for _msg in reversed(messages[:-1]):
        if _msg.get("role") == "assistant":
            _prev_assistant = (_msg.get("content") or "").lower()
            break
    
    _goodbye_triggers = [
        "no", "nope", "no thanks", "no thank you", "that's it", "that's all",
        "nothing else", "i'm good", "all good", "that's everything", "i'm all set",
        "no that's it", "no that's all", "no i'm good", "no i'm fine",
        "not at the moment", "not right now", "that'll do", "that will do",
    ]
    _ai_asked_anything_else = any(phrase in _prev_assistant for phrase in [
        "anything else", "anything else i can help", "what else can i help",
        "is there anything", "can i help with anything", "how can i assist",
        "how can i help", "assist you further", "help you further",
        "help with anything", "need anything else"
    ])
    # Also trigger if we're in post-booking cooldown (just booked, caller is wrapping up)
    _is_post_booking = (last_booking_turn > 0 and current_turn - last_booking_turn <= 3)
    
    if (_ai_asked_anything_else or _is_post_booking) and any(t == _user_msg_lower or _user_msg_lower.startswith(t + " ") or _user_msg_lower.startswith(t + ".") or _user_msg_lower.startswith(t + ",") for t in _goodbye_triggers):
        goodbye_responses = [
            "Grand, thanks for calling. Have a great day!",
            "Lovely, thanks for calling. Take care!",
            "Sure, thanks for calling. Have a great day!",
            "Grand, thanks for calling. Bye!",
        ]
        goodbye_msg = random.choice(goodbye_responses)
        print(f"\n👋 [GOODBYE] Fast-path goodbye triggered (user: '{_user_msg_lower}', post_booking={_is_post_booking})")
        print(f"👋 [GOODBYE] Response: '{goodbye_msg}'")
        messages.append({"role": "assistant", "content": goodbye_msg})
        yield goodbye_msg
        return
    
    # Check if pre-check is disabled for debugging
    likely_needs_tool = False
    detected_intent = None
    if config.DISABLE_FILLER_PRECHECK:
        print(f"\n{'='*60}")
        print(f"🔍 [PRE-CHECK] ⚠️ DISABLED (DISABLE_FILLER_PRECHECK=true)")
        print(f"{'='*60}")
        yield f"<<<TIMING:precheck_ms=0,intent=DISABLED>>>"
    else:
        precheck_start = time.time()
        user_message = messages[-1]["content"].lower() if messages and messages[-1].get("role") == "user" else ""
        likely_needs_tool = False
        checking_msg = None
        detected_intent = None
        
        print(f"\n{'='*60}")
        print(f"🔍 [PRE-CHECK] === FILLER PRE-CHECK ANALYSIS ===")
        print(f"🔍 [PRE-CHECK] User message: '{user_message[:80]}...'")
        print(f"{'='*60}")
    
        # Get previous assistant message for context
        prev_assistant_msg = ""
        for msg in reversed(messages[:-1]):
            if msg.get("role") == "assistant":
                prev_assistant_msg = msg.get("content", "").lower()
                break
        
        # Check if lookup_customer was already called
        already_did_lookup = any(
            msg.get("role") == "tool" and msg.get("name") == "lookup_customer"
            for msg in messages
        )
        
        # Generic fillers - safe for any tool call (varied to avoid repetition)
        # Text MUST match pre-recorded phrases exactly for instant playback
        generic_fillers = [
            "One moment.", "Let me check that for you.", "Bear with me one second.",
            "Just a moment.", "Let me have a look.", "Sure, one second.",
            "Okay, let me see.", "Give me a second.", "Let me pull that up.",
        ]
        
        # === HIGH-CONFIDENCE TRIGGERS (tool call is almost certain) ===
        
        # 1. TRANSFER REQUEST - always triggers transfer_to_human tool
        transfer_phrases = ["transfer", "speak to a", "talk to a", "real person", "a human", "the manager"]
        if any(phrase in user_message for phrase in transfer_phrases):
            likely_needs_tool = True
            detected_intent = "TRANSFER"
            checking_msg = "Connecting you now."
            print(f"   ✅ [PRE-CHECK] Detected: TRANSFER REQUEST")
        
        # 2. CANCEL/RESCHEDULE - always triggers cancel_appointment or reschedule_appointment
        if not likely_needs_tool:
            if "cancel" in user_message and ("appointment" in user_message or "booking" in user_message):
                likely_needs_tool = True
                detected_intent = "CANCELLATION"
                checking_msg = random.choice(generic_fillers)
                print(f"   ✅ [PRE-CHECK] Detected: CANCELLATION REQUEST")
            elif "reschedule" in user_message or "move my appointment" in user_message:
                likely_needs_tool = True
                detected_intent = "RESCHEDULE"
                checking_msg = random.choice(generic_fillers)
                print(f"   ✅ [PRE-CHECK] Detected: RESCHEDULE REQUEST")
        
        # 3. NAME SPELLING CONFIRMED - NO LONGER USED (phone-first identification)
        # Kept as comment for reference — lookup_customer is now called at call start by phone
        
        # 3b. NAME SPELLING CORRECTION - NO LONGER USED (phone-first identification)
        # Kept as comment for reference — names are extracted from transcript post-call
        
        # 4. EXPLICIT AVAILABILITY CHECK - triggers check_availability
        # GUARD: Skip if a booking was just completed — caller may be confirming, not asking for new availability
        if not likely_needs_tool and not in_post_booking_cooldown:
            availability_phrases = ["what times are available", "when are you available", "any slots", "check availability",
                                   "what times", "when can", "any openings", "free on", "available on", "next available",
                                   "earliest", "soonest", "closest day", "this week", "next week", "tomorrow",
                                   # Additional phrases for search_availability queries
                                   "week after", "in 2 weeks", "in two weeks", "after 4", "after 5", "after 3",
                                   "morning", "afternoon", "evening", "do you have anything", "what about",
                                   "any other", "different day", "another day", "other options", "what else"]
            # NOTE: Day names (monday, tuesday, etc.) intentionally excluded!
            # Users say day names when PICKING a slot ("I'll take Wednesday") not just checking availability.
            # Including them caused filler misfires where the LLM just confirms details instead of calling a tool.
            if any(phrase in user_message for phrase in availability_phrases):
                likely_needs_tool = True
                detected_intent = "AVAILABILITY_CHECK"
                checking_msg = random.choice(generic_fillers)
                print(f"   ✅ [PRE-CHECK] Detected: AVAILABILITY CHECK")
        
        # 4b. ADDRESS CONFIRMATION - user confirms address, next step is availability check
        if not likely_needs_tool:
            # Only match phrases that are SPECIFICALLY about address/location
            # Removed "is that correct" and "is that right" - too generic, matches booking confirmations too
            address_confirmation_phrases = ["same address", "still your address", "your address", "still at", "at the same", "same location", "same place", "address as before", "address on file", "correct address", "the correct address"]
            ai_asked_address = any(phrase in prev_assistant_msg for phrase in address_confirmation_phrases)
            
            # Extra guard: make sure the AI wasn't asking about a BOOKING confirmation
            # Only block if the message looks like a booking confirmation (has day+time pattern)
            booking_context_phrases = ["booked in for", "book for", "want to book"]
            day_names_in_msg = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            time_patterns_in_msg = ["at 1 pm", "at 2 pm", "at 3 pm", "at 4 pm", "at 5 pm", "at 9 am", "at 10 am", "at 11 am", "at 12 pm"]
            has_booking_phrase = any(phrase in prev_assistant_msg for phrase in booking_context_phrases)
            has_day_and_time = any(d in prev_assistant_msg for d in day_names_in_msg) and any(t in prev_assistant_msg for t in time_patterns_in_msg)
            ai_asking_about_booking = (has_booking_phrase or has_day_and_time) and not any(phrase in prev_assistant_msg for phrase in ["same address", "address as before", "address on file"])
            
            user_confirms = any(phrase in user_message for phrase in ["yes", "yeah", "yep", "correct", "that's right", "it is", "that's it", "that's correct", "correct address"])
            
            if ai_asked_address and user_confirms and not ai_asking_about_booking:
                likely_needs_tool = True
                detected_intent = "ADDRESS_CONFIRMED"
                # Relevant filler — we're about to check the schedule
                address_fillers = ["Let me just check the schedule.", "One moment.", "Bear with me one second.", "Let me have a look."]
                checking_msg = random.choice(address_fillers)
                print(f"   ✅ [PRE-CHECK] Detected: ADDRESS CONFIRMED (will check availability)")
        
        # 4c. ADDRESS PROVIDED - caller gives their address/eircode, next step is get_next_available
        # After the AI asks "what's your address?" or "can you provide your full address?",
        # the caller responds with an actual address. The LLM will acknowledge and call
        # get_next_available, so play a filler to cover the tool call latency.
        if not likely_needs_tool:
            ai_asked_for_address_phrases = ["full address", "your address", "eircode", "eir code", "where is the property", "where's the property", "where is the job", "where's the job"]
            ai_asked_for_addr = any(phrase in prev_assistant_msg for phrase in ai_asked_for_address_phrases)
            # Don't false-trigger on "email address" — that's the email ask, not address ask
            if ai_asked_for_addr and "email address" in prev_assistant_msg:
                ai_asked_for_addr = False
            
            # Fallback: if the AI asked for address earlier but there was back-and-forth
            # in between (e.g. caller said "okay", AI said "I'm ready when you are!"),
            # prev_assistant_msg won't match. Use call_state to detect we're still
            # in address-gathering mode.
            if not ai_asked_for_addr and call_state and getattr(call_state, '_addr_audio_ever_asked', False):
                if not getattr(call_state, 'address_audio_captured', False):
                    ai_asked_for_addr = True
            
            # Caller declined (no, I don't know, etc.) — don't trigger filler
            decline_phrases = ["no", "i don't", "i dont", "not sure", "no idea", "don't know", "dont know"]
            caller_declined = len(user_message.split()) <= 5 and any(phrase in user_message for phrase in decline_phrases)
            
            # Caller gave something substantial (an actual address or eircode)
            caller_gave_address = len(user_message.split()) >= 3 and not caller_declined
            
            if ai_asked_for_addr and caller_gave_address:
                # Don't trigger availability filler if email hasn't been asked yet.
                # The prompt requires email (step 8) BEFORE checking availability (step 9).
                # If we trigger a filler here, the LLM skips email and jumps to get_next_available.
                _email_already_asked = any(
                    "email" in (msg.get("content") or "").lower()
                    for msg in messages
                    if msg.get("role") == "assistant"
                )
                if _email_already_asked:
                    likely_needs_tool = True
                    detected_intent = "ADDRESS_PROVIDED"
                    checking_msg = random.choice(generic_fillers)
                    print(f"   ✅ [PRE-CHECK] Detected: ADDRESS PROVIDED (email already asked, will check availability)")
                else:
                    print(f"   ❌ [PRE-CHECK] ADDRESS PROVIDED but email not yet asked — skipping filler (LLM will ask for email first)")
        
        # 5. BOOKING CONFIRMATION - user confirms booking after AI asked "ready to book?" or confirmed details
        # GUARD: Skip if a booking was already completed — no need to re-confirm
        if not likely_needs_tool and not in_post_booking_cooldown:
            # Check if AI just asked about booking confirmation
            booking_confirmation_phrases = ["ready to book", "shall i book", "want me to book", "confirm the booking", "go ahead and book", "all correct",
                                           "is that correct?", "correct?"]
            # Only match "is that correct?" / "correct?" if the previous message is about a booking (has day+time)
            day_names_lower = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            time_indicators = ["am", "pm", "o'clock"]
            prev_has_day = any(d in prev_assistant_msg for d in day_names_lower)
            prev_has_time = any(t in prev_assistant_msg for t in time_indicators)
            prev_is_booking_context = prev_has_day and prev_has_time
            
            # Filter: generic "correct?" only counts if it's in a booking context
            ai_asked_to_book = False
            for phrase in booking_confirmation_phrases:
                if phrase in prev_assistant_msg:
                    if phrase in ["is that correct?", "correct?"]:
                        # Only trigger if the AI was confirming a booking (day+time present)
                        if prev_is_booking_context:
                            ai_asked_to_book = True
                            break
                    else:
                        ai_asked_to_book = True
                        break
            
            user_confirms = any(phrase in user_message for phrase in ["yes", "yeah", "yep", "please", "go ahead", "book it", "that's perfect", "sounds good", "correct", "that's right", "that's correct"])
            
            # Negative guard: if user is asking about availability, they're NOT confirming a booking
            user_asking_availability = any(word in user_message for word in ["available", "availability", "again", "what's available", "when are you", "repeat"])
            
            if ai_asked_to_book and user_confirms and not user_asking_availability:
                likely_needs_tool = True
                detected_intent = "BOOKING_CONFIRMED"
                checking_msg = "Booking that now."
                print(f"   ✅ [PRE-CHECK] Detected: BOOKING CONFIRMED")
        
        # 6. TIME SELECTION - user picks a time AND a day from offered options
        # Only trigger if user specifies BOTH day and time (or uses "i'll take" style phrases)
        # to avoid misfires where LLM just confirms details instead of booking
        if not likely_needs_tool:
            explicit_pick_phrases = ["i'll take", "let's do", "let's go with", "that one", "the first one", "the second",
                                     "morning one", "afternoon one", "book me in for", "go with"]
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            time_phrases = ["9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm",
                           "9 o'clock", "10 o'clock", "at 9", "at 10", "at 11", "at 12", "at 1", "at 2", "at 3", "at 4", "at 5"]
            time_offered = any(phrase in prev_assistant_msg for phrase in ["available", "free", "i have", "which works", "which time", "which day"])
            
            has_explicit_pick = any(phrase in user_message for phrase in explicit_pick_phrases)
            has_day = any(day in user_message for day in day_names)
            has_time = any(t in user_message for t in time_phrases)
            
            # GUARD: If user's message contains soft confirmation language ("sounds good",
            # "that works", etc.) alongside day+time, the LLM often does a confirmation
            # round ("Just to confirm, that's X on Y at Z. Correct?") instead of immediately
            # calling the booking tool. Don't trigger filler in this case — it causes misfires
            # where the filler says "Grand, let me book that" but the LLM just asks to confirm.
            soft_confirm_phrases = ["sounds good", "that works", "that's good", "that's great",
                                    "perfect", "that'll work", "works for me", "suits me"]
            user_soft_confirming = any(phrase in user_message for phrase in soft_confirm_phrases)
            
            # Only trigger if user gives a clear pick (day+time, or explicit pick phrase with day or time)
            # BUT skip if user is soft-confirming — LLM will likely confirm details first, not book immediately
            if time_offered and (has_explicit_pick or (has_day and has_time)) and not user_soft_confirming:
                likely_needs_tool = True
                detected_intent = "TIME_SELECTED"
                checking_msg = "Grand, let me book that."
                print(f"   ✅ [PRE-CHECK] Detected: TIME SELECTED")
            elif time_offered and (has_day and has_time) and user_soft_confirming:
                detected_intent = "TIME_SELECTED_SOFT_CONFIRM"
                print(f"   ℹ️ [PRE-CHECK] Detected: TIME SELECTED but user soft-confirming (no filler - LLM will confirm details)")
        
        # 7. CANCEL/MODIFY JOB - broader detection
        if not likely_needs_tool:
            cancel_phrases = ["cancel", "cancel my", "need to cancel", "want to cancel"]
            modify_phrases = ["change the", "update my", "modify", "different address", "wrong address"]
            if any(phrase in user_message for phrase in cancel_phrases):
                likely_needs_tool = True
                detected_intent = "CANCEL_REQUEST"
                checking_msg = random.choice(generic_fillers)
                print(f"   ✅ [PRE-CHECK] Detected: CANCEL REQUEST")
            elif any(phrase in user_message for phrase in modify_phrases):
                likely_needs_tool = True
                detected_intent = "MODIFY_REQUEST"
                checking_msg = random.choice(generic_fillers)
                print(f"   ✅ [PRE-CHECK] Detected: MODIFY REQUEST")
        
        # === FIRST TURN ACKNOWLEDGMENT - DISABLED ===
        # Previously played acknowledgment on first turn to cover OpenAI latency
        # DISABLED because it causes misfires - the acknowledgment plays but LLM
        # doesn't call any tools, making the filler feel disconnected from the response.
        # Better to let the user wait 1-2s for a coherent response than play a filler
        # that doesn't match what the AI actually says.
        # if not likely_needs_tool:
        #     is_first_turn = len([m for m in messages if m.get("role") == "user"]) == 1
        #     has_substance = len(user_message.split()) >= 4
        #     if is_first_turn and has_substance:
        #         likely_needs_tool = True
        #         detected_intent = "FIRST_TURN_ACK"
        #         first_turn_acks = ["Sure.", "No problem.", "Grand.", "Okay."]
        #         checking_msg = random.choice(first_turn_acks)
        
        # === MEDIUM-CONFIDENCE (might trigger tool, but not certain) ===
        # These are logged but DON'T trigger fillers to avoid misfires
        
        if not likely_needs_tool:
            # Booking request - LLM will ask for details first, no immediate tool call
            if any(phrase in user_message for phrase in ["book", "appointment", "schedule"]):
                detected_intent = "BOOKING_INTENT"
                print(f"   ℹ️ [PRE-CHECK] Detected: BOOKING INTENT (no filler - LLM will gather details)")
            
            # Service description - LLM WILL call match_issue tool, so play a filler
            elif any(phrase in user_message for phrase in ["leak", "broken", "fix", "repair", "build",
                     "burst", "blocked", "crack", "damage", "flood", "drip", "issue", "problem",
                     "need help", "need to get", "need someone", "something wrong",
                     "plumber", "plumbing", "electrician", "carpenter", "painter", "roofer",
                     "heating", "boiler", "radiator", "toilet", "shower", "tap", "pipe",
                     "come out", "call out", "callout"]):
                likely_needs_tool = True
                detected_intent = "SERVICE_DESCRIPTION"
                # Use short acknowledgments — "Let me check" sounds odd when they just described an issue
                service_ack_fillers = ["Sure.", "Right.", "Okay.", "Got it."]
                checking_msg = random.choice(service_ack_fillers)
                print(f"   ✅ [PRE-CHECK] Detected: SERVICE DESCRIPTION (filler - LLM will call match_issue)")
            
            # Name introduction - LLM may call lookup_customer, play a short acknowledgment
            elif "my name is" in user_message or "name's" in user_message:
                detected_intent = "NAME_INTRODUCTION"
                print(f"   ℹ️ [PRE-CHECK] Detected: NAME INTRODUCTION (no filler - LLM will acknowledge)")
        
        precheck_duration = time.time() - precheck_start
        
        if likely_needs_tool and checking_msg:
            print(f"\n   {'─'*50}")
            print(f"   🎯 [PRE-CHECK] FILLER WILL BE TRIGGERED!")
            print(f"   🎯 [PRE-CHECK] Intent: {detected_intent}")
            print(f"   🎯 [PRE-CHECK] Filler message: '{checking_msg}'")
            print(f"   🎯 [PRE-CHECK] Analysis took: {precheck_duration*1000:.1f}ms")
            print(f"   {'─'*50}\n")
            yield f"<<<TIMING:precheck_ms={precheck_duration*1000:.1f},intent={detected_intent}>>>"
            yield f"<<<SPLIT_TTS:{checking_msg}>>>"
        else:
            print(f"   ❌ [PRE-CHECK] No filler trigger detected")
            print(f"   ❌ [PRE-CHECK] Analysis took: {precheck_duration*1000:.1f}ms\n")
            yield f"<<<TIMING:precheck_ms={precheck_duration*1000:.1f},intent={detected_intent or 'NONE'}>>>"
    
    # Stream from OpenAI with optimized settings
    client = get_openai_client()
    
    # --- TIMING: System prompt loading ---
    prompt_load_start = time_module.time()
    
    # Add current time context to system prompt
    current_time = datetime.now()
    current_time_str = current_time.strftime('%I:%M %p on %A, %B %d, %Y')
    time_context = f"\n\n[CURRENT TIME: {current_time_str}]\nUse this when discussing appointment times and availability. Times that have already passed today cannot be booked."
    
    # Enhanced prompt for tool usage - keep SHORT for speed
    tool_usage_guidance = """

TOOL RULES:
• NEVER say "let me check" without calling a tool - system plays fillers automatically
• Just call tools directly - no announcements needed
• If not calling a tool, ask a question instead"""
    
    # Load company-specific system prompt with CACHING to avoid repeated DB queries
    prompt_load_db_start = time_module.time()
    active_system_prompt = get_cached_system_prompt(company_id=company_id)
    prompt_load_time = time_module.time() - prompt_load_db_start
    if prompt_load_time > 0.05:  # Only log if slow (>50ms)
        print(f"[LLM] System prompt loaded in {prompt_load_time*1000:.0f}ms")
    
    system_prompt_with_time = active_system_prompt + time_context + tool_usage_guidance
    
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
    
    # Debug: Print message structure before API call (only log tool_calls for debugging)
    for idx, msg in enumerate(sanitized_messages):
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            print(f"[LLM] Message[{idx}] assistant with tool_calls: {[tc.get('function', {}).get('name') for tc in msg.get('tool_calls', [])]}")
    
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
        print(f"[LLM] Calling {config.CHAT_MODEL} | {len(final_messages)} msgs | company={company_id}")
        
        # Use ThreadPoolExecutor with timeout to prevent infinite hangs
        import concurrent.futures
        import threading
        
        # Determine if tools should be used
        use_tools = not config.DISABLE_LLM_TOOLS
        
        def create_stream():
            import time as inner_time
            api_start = inner_time.time()
            
            try:
                # Build API call params
                api_params = {
                    "model": config.CHAT_MODEL,
                    "stream": True,
                    "temperature": 0.1,
                    "presence_penalty": 0.1,
                    "frequency_penalty": 0.1,
                    "messages": [{"role": "system", "content": system_prompt_with_time}, *final_messages],
                    "top_p": 0.9,
                    "stream_options": {"include_usage": False},
                    **config.max_tokens_param(value=180)
                }
                
                # Only add tools if enabled
                if use_tools:
                    api_params["tools"] = CALENDAR_TOOLS
                    api_params["tool_choice"] = "auto"
                    api_params["parallel_tool_calls"] = True
                
                result = client.chat.completions.create(**api_params)
                api_done = inner_time.time()
                print(f"[LLM] ✅ Stream created in {(api_done - api_start)*1000:.0f}ms")
                return result
            except Exception as e:
                api_done = inner_time.time()
                print(f"[LLM] ❌ API failed after {(api_done - api_start)*1000:.0f}ms: {e}")
                raise
        
        # CRITICAL FIX: Use asyncio.to_thread to avoid blocking the event loop
        # The old code used future.result() which blocks synchronously
        try:
            stream = await asyncio.wait_for(
                asyncio.to_thread(create_stream),
                timeout=8.0
            )
        except asyncio.TimeoutError:
            print(f"❌ [LLM_ERROR] OpenAI stream creation timed out after 8s!")
            print(f"[LLM_ERROR] Message roles: {[m.get('role') for m in final_messages]}")
            # Log the actual messages for debugging
            for i, msg in enumerate(final_messages[-5:]):  # Last 5 messages
                role = msg.get('role')
                content = msg.get('content', '')[:100] if msg.get('content') else '[no content]'
                print(f"[LLM_ERROR] Msg[-{5-i}] {role}: {content}...")
            # Quick, natural fallback response
            yield "Sorry, could you say that again?"
            return
        
        openai_create_time = time_module.time() - openai_call_start
        print(f"[LLM] OpenAI stream ready in {openai_create_time:.3f}s")
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
        print(f"[LLM] Iterating stream...")
        stream_iter_start = time_module.time()
        STREAM_TIMEOUT = 15.0  # Max seconds to wait for stream to complete
        
        # Wrap synchronous OpenAI stream iteration in a thread to avoid blocking event loop
        import queue
        token_queue = queue.Queue()
        
        def iterate_stream():
            """Run in thread to avoid blocking event loop"""
            try:
                for part in stream:
                    token_queue.put(("token", part))
                token_queue.put(("done", None))
            except Exception as e:
                token_queue.put(("error", e))
        
        # Start stream iteration in background thread
        stream_thread = threading.Thread(target=iterate_stream, daemon=True)
        stream_thread.start()
        
        # Process tokens from queue (non-blocking)
        last_activity = time_module.time()
        IDLE_TIMEOUT = 5.0  # Max seconds without any queue activity
        while True:
            # SAFETY: Check overall timeout
            elapsed = time_module.time() - stream_iter_start
            if elapsed > STREAM_TIMEOUT:
                print(f"⚠️ [LLM_TIMEOUT] First stream timed out after {elapsed:.1f}s")
                break
            
            # SAFETY: Check idle timeout (no activity from thread)
            idle_time = time_module.time() - last_activity
            if idle_time > IDLE_TIMEOUT and not stream_thread.is_alive():
                print(f"⚠️ [LLM_TIMEOUT] Stream thread died, idle for {idle_time:.1f}s")
                break
            
            # Check queue without blocking, yield control if empty
            try:
                msg_type, msg_data = token_queue.get_nowait()
                last_activity = time_module.time()  # Reset idle timer on activity
            except queue.Empty:
                # Queue empty, yield control to event loop and try again
                await asyncio.sleep(0.01)
                continue
            
            if msg_type == "done":
                break
            elif msg_type == "error":
                raise msg_data
            
            part = msg_data
            # Track first token timing
            if first_token_time is None:
                first_token_time = time_module.time()
                ttft = first_token_time - openai_call_start
                print(f"[LLM] ⚡ First token in {ttft:.3f}s")
                # Yield timing marker for media handler
                yield f"<<<TIMING:openai_first_token_ms={ttft*1000:.1f}>>>"
            
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
                # 2. If we yielded a split marker, we STILL yield content so prefetch_remaining() can capture it
                #    (The filler plays while these tokens are being buffered)
                if not tool_calls:
                    # Strip markdown formatting to prevent TTS reading "**" as "star star"
                    cleaned_token = delta.content.replace('**', '').replace('__', '').replace('~~', '')
                    cleaned_token = format_for_tts_spelling(cleaned_token)
                    cleaned_token = humanize_times_for_tts(cleaned_token)
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
    
    # FAST PATH: If no tool calls, return immediately after yielding content
    # This prevents blocking the TTS stream while doing post-processing
    if not tool_calls and not has_yielded_split_marker:
        # SAFETY: Detect if LLM said "let me check" without calling a tool
        # This is a dangerous pattern that causes silence/freeze
        dangerous_phrases = [
            "let me check", "one moment", "let me look", "bear with me",
            "let me see", "checking now", "looking that up", "let me find",
            "i'll check", "i will check", "check availability", "check that"
        ]
        response_lower = full_response.lower() if full_response else ""
        said_checking_phrase = any(phrase in response_lower for phrase in dangerous_phrases)
        
        # SAFETY: Detect if LLM fabricated availability without calling a tool
        # Bug: LLM sometimes says "We're available Monday or Tuesday" without calling
        # get_next_available or search_availability first. This is dangerous because
        # the dates may be wrong (e.g., offering Sunday, or a fully-booked day).
        availability_keywords = [
            "we're available", "we are available", "available to start",
            "i have availability", "we have availability",
            "available on monday", "available on tuesday", "available on wednesday",
            "available on thursday", "available on friday",
            "available tomorrow", "available next",
            "start on monday", "start on tuesday", "start on wednesday",
            "start on thursday", "start on friday", "start tomorrow",
        ]
        fabricated_availability = any(phrase in response_lower for phrase in availability_keywords)
        
        # Check if any availability tool was called in conversation history
        # If not, the LLM is making up availability
        avail_tools_called = any(
            msg.get("role") == "tool" and msg.get("name") in ("get_next_available", "search_availability", "check_availability")
            for msg in messages
        )
        
        if fabricated_availability and not avail_tools_called:
            print(f"\n🚨 [SAFETY] LLM fabricated availability without calling a tool!")
            print(f"🚨 [SAFETY] Response: '{full_response[:150]}...'")
            print(f"🚨 [SAFETY] Replacing with safe response to prevent wrong dates")
            replacement = "Let me check what we have available for you."
            full_response = replacement
            # Don't yield replacement — the fabricated response was already streamed.
            # Instead yield a follow-up that will trigger a tool call on the next turn.
            yield " Let me just check the schedule."
        elif said_checking_phrase:
            print(f"\n🚨 [SAFETY] LLM said checking phrase but didn't call tool!")
            print(f"🚨 [SAFETY] Response: '{full_response[:100]}...'")
            print(f"🚨 [SAFETY] Replacing with a question to prevent silence")
            replacement = "What day works best for you?"
            full_response = replacement
            yield replacement
        
        # Store response in conversation history
        if full_response:
            cleaned = remove_repetition(full_response.strip())
            messages.append({"role": "assistant", "content": cleaned})
        print(f"[LLM] ✅ No tool calls — fast path")
        return
    
    # SAFETY CHECK: If we yielded a split marker in pre-check but OpenAI didn't actually call tools
    # Note: The response tokens were already yielded during streaming (captured by prefetch_remaining)
    # so we just need to log the misfire and update conversation history
    if has_yielded_split_marker and not tool_calls:
        if full_response:
            print(f"\n⚠️ [PRE-CHECK MISFIRE] Filler was played but LLM didn't call any tools!")
            print(f"⚠️ [PRE-CHECK MISFIRE] User message was: '{user_message[:80]}...'")
            print(f"⚠️ [PRE-CHECK MISFIRE] LLM response: '{full_response[:100]}...'")
            print(f"⚠️ [PRE-CHECK MISFIRE] Response tokens were already yielded to prefetch buffer")
            
            # SAFETY: Check if the response promised to check something but didn't
            # If so, we need to yield a follow-up question to prevent silence
            dangerous_phrases = [
                "let me check", "one moment", "let me look", "bear with me",
                "let me see", "checking now", "looking that up", "let me find",
                "i'll check", "i will check", "check availability", "check that"
            ]
            response_lower = full_response.lower()
            said_checking_phrase = any(phrase in response_lower for phrase in dangerous_phrases)
            
            if said_checking_phrase:
                print(f"🚨 [SAFETY] Response promised to check but didn't call tool!")
                print(f"🚨 [SAFETY] Yielding follow-up question to prevent silence")
                # The dangerous response was already yielded, so append a question
                followup = " What day works best for you?"
                yield followup
                full_response += followup
            
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
        # ARCHITECTURE: Database calendar is ALWAYS the primary scheduling engine.
        # It handles employees, availability, overlapping jobs, etc.
        # Google Calendar is a SYNC TARGET — events are pushed there after booking
        # for visibility and third-party integrations (e.g., Tradify).
        calendar = None
        google_calendar_sync = None
        
        # Always use database calendar as the primary scheduler
        if company_id:
            try:
                from src.services.database_calendar import get_database_calendar_service
                calendar_company_id = int(company_id)
                calendar = get_database_calendar_service(company_id=calendar_company_id)
                print(f"   📦 [TOOL_SETUP] Using Database Calendar (company_id={calendar_company_id})")
            except Exception as e:
                print(f"   ❌ [TOOL_SETUP] Could not load database calendar: {e}")
        
        if calendar is None:
            try:
                from src.services.database_calendar import get_database_calendar_service
                calendar = get_database_calendar_service(company_id=None)
                print(f"   📦 [TOOL_SETUP] Using Database Calendar (no company_id)")
            except Exception as e:
                print(f"   ❌ [TOOL_SETUP] Could not load database calendar fallback: {e}")
        
        # Check if Google Calendar is connected for sync (secondary)
        if company_id:
            try:
                from src.services.google_calendar_oauth import get_company_google_calendar
                from src.services.database import get_database as get_db_for_gcal
                gcal_db = get_db_for_gcal()
                gcal = get_company_google_calendar(int(company_id), gcal_db)
                if gcal:
                    google_calendar_sync = gcal
                    print(f"   📦 [TOOL_SETUP] Google Calendar sync enabled (company_id={company_id})")
            except Exception as e:
                print(f"   ⚠️ [TOOL_SETUP] Could not load company Google Calendar for sync: {e}")
        
        db = get_database()
        
        company_id_int = int(company_id) if company_id else None
        services = {
            'google_calendar': calendar,
            'calendar': calendar,
            'google_calendar_sync': google_calendar_sync,
            'db': db,
            'company_id': company_id_int,
            'call_state': call_state,
            'industry_type': call_state.industry_type if call_state and hasattr(call_state, 'industry_type') else 'trades',
        }
        print(f"   📦 [TOOL_SETUP] Services ready: calendar={calendar is not None}, db={db is not None}, gcal_sync={google_calendar_sync is not None}")
        
        # Execute each tool call and collect results
        tool_results = []
        
        # Yield control to event loop before tool execution
        # This allows other tasks (like audio playback) to run
        print(f"   ⏸️ [TOOL_EXEC] Yielding to event loop (allows audio to continue)...")
        await asyncio.sleep(0)
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call["function"]["name"]
            tool_id = tool_call["id"]
            
            # ============================================================
            # RESCHEDULE INTERCEPTION: If user said "reschedule" but LLM
            # called cancel_job, redirect to reschedule_job instead.
            # The LLM often calls cancel_job first (for day lookup), then
            # sees "cancel" in history and goes rogue with cancel+rebook.
            # This forces it onto the correct reschedule_job path.
            # Also catches multi-turn: if reschedule_job was already called
            # in conversation history, we're mid-reschedule and cancel_job
            # should never be called.
            # ============================================================
            reschedule_words = ["reschedule", "move my", "move the", "change the date", "change the day", "move it"]
            cancel_words = ["cancel", "cancel my", "need to cancel", "want to cancel", "cancel that", "cancel the"]
            
            # If the user is explicitly asking to cancel RIGHT NOW, respect that
            # even if there were reschedule_job calls earlier in the conversation.
            user_explicitly_cancelling = (
                detected_intent == "CANCEL_REQUEST"
                or any(w in user_text.lower() for w in cancel_words)
            )
            
            # Multi-turn cancel detection: if a recent user message said "cancel" and
            # the LLM is now following up (e.g. asking for the date), the current
            # message won't contain cancel words.  Also check if cancel_job was
            # already called in this conversation — that means we're mid-cancel flow.
            if not user_explicitly_cancelling:
                # Check if cancel_job was already called earlier
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        for tc in msg["tool_calls"]:
                            if tc.get("function", {}).get("name") in ("cancel_job", "cancel_appointment"):
                                user_explicitly_cancelling = True
                                print(f"   ✅ [CANCEL_OVERRIDE] cancel_job was already called earlier — staying in cancel flow")
                                break
                    if user_explicitly_cancelling:
                        break
            if not user_explicitly_cancelling:
                # Check if a recent user message mentioned cancel
                # Look back up to 5 user messages (covers the "cancel" → clarification → date → name pattern)
                # But stop if we hit a reschedule word first — means user changed their mind
                user_msg_count = 0
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_msg_count += 1
                        msg_text = msg.get("content", "").lower()
                        if any(w in msg_text for w in cancel_words):
                            user_explicitly_cancelling = True
                            print(f"   ✅ [CANCEL_OVERRIDE] Detected cancel intent from recent user message: '{msg_text[:60]}...'")
                            break
                        if any(w in msg_text for w in reschedule_words):
                            # User said "reschedule" more recently than "cancel" — they changed their mind
                            print(f"   ℹ️ [CANCEL_OVERRIDE] Found reschedule intent more recent than cancel — not overriding")
                            break
                        if user_msg_count >= 5:
                            break
            
            user_wants_reschedule = detected_intent == "RESCHEDULE" or any(w in user_text.lower() for w in reschedule_words)
            # Multi-turn: check if reschedule_job was already called earlier in this conversation
            # BUT skip this if the user is now explicitly asking to cancel
            if not user_wants_reschedule and not user_explicitly_cancelling:
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        for tc in msg["tool_calls"]:
                            if tc.get("function", {}).get("name") in ("reschedule_job", "reschedule_appointment"):
                                user_wants_reschedule = True
                                break
                    if user_wants_reschedule:
                        break
            # Multi-turn fallback: check if ANY earlier user message mentioned reschedule
            # This catches the case where turn 1 was "I want to reschedule" (no tool call),
            # and turn 2 is "this Thursday" (LLM calls cancel_job instead of reschedule_job)
            # BUT skip this if the user is now explicitly asking to cancel
            if not user_wants_reschedule and not user_explicitly_cancelling:
                for msg in messages:
                    if msg.get("role") == "user":
                        msg_text = msg.get("content", "").lower()
                        if any(w in msg_text for w in reschedule_words):
                            user_wants_reschedule = True
                            print(f"   🔄 [RESCHEDULE_INTERCEPT] Detected reschedule intent from earlier user message: '{msg_text[:60]}...'")
                            break
            
            # If user explicitly wants to cancel, override any history-based reschedule detection
            if user_explicitly_cancelling and user_wants_reschedule:
                print(f"   ✅ [CANCEL_OVERRIDE] User explicitly wants to cancel — ignoring prior reschedule history")
                user_wants_reschedule = False
            if tool_name in ("cancel_job", "cancel_appointment") and user_wants_reschedule:
                original_name = tool_name
                # Map cancel_job args to reschedule_job args
                try:
                    raw_args = json.loads(tool_call["function"]["arguments"])
                    remapped_args = {
                        "current_date": raw_args.get("appointment_date") or raw_args.get("appointment_datetime"),
                        "customer_name": raw_args.get("customer_name"),
                    }
                    tool_call["function"]["name"] = "reschedule_job"
                    tool_call["function"]["arguments"] = json.dumps(remapped_args)
                    tool_name = "reschedule_job"
                    print(f"   🔄 [RESCHEDULE_INTERCEPT] Redirected {original_name} → reschedule_job (user intent was RESCHEDULE)")
                except Exception as e:
                    print(f"   ⚠️ [RESCHEDULE_INTERCEPT] Failed to remap args: {e}")
            
            # BLOCK book_job during an active reschedule flow — prevents duplicates
            if tool_name in ("book_job", "book_appointment") and user_wants_reschedule:
                print(f"   🚫 [RESCHEDULE_INTERCEPT] BLOCKED {tool_name} during reschedule flow (would create duplicate)")
                tool_results.append({
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps({
                        "success": False,
                        "error": "Cannot book a new job during a reschedule. Use reschedule_job to move the existing booking instead."
                    })
                })
                continue
            
            # REDIRECT get_next_available / search_availability during reschedule
            # The LLM sometimes switches to booking-flow availability tools when the
            # caller says "book" or "I'll take that day".  These tools start from
            # scratch and ignore the reschedule context.  Redirect to reschedule_job
            # with the new date so the existing booking gets moved, not duplicated.
            if tool_name in ("get_next_available", "search_availability") and user_wants_reschedule:
                # Try to find the original date + customer name from earlier reschedule calls
                _resched_original_date = None
                _resched_customer_name = None
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        for tc in msg["tool_calls"]:
                            if tc.get("function", {}).get("name") in ("reschedule_job", "reschedule_appointment"):
                                try:
                                    prev_args = json.loads(tc["function"]["arguments"])
                                    _resched_original_date = prev_args.get("current_date") or prev_args.get("current_datetime")
                                    _resched_customer_name = prev_args.get("customer_name") or _resched_customer_name
                                except:
                                    pass
                
                if _resched_original_date and _resched_customer_name:
                    # The user's latest message likely contains the new date they want
                    # Pass it as new_datetime so reschedule_job can complete the move
                    print(f"   🔄 [RESCHEDULE_INTERCEPT] Redirected {tool_name} → reschedule_job (mid-reschedule, customer='{_resched_customer_name}')")
                    tool_call["function"]["name"] = "reschedule_job"
                    tool_call["function"]["arguments"] = json.dumps({
                        "current_date": _resched_original_date,
                        "customer_name": _resched_customer_name,
                        "new_datetime": user_text,
                        "confirmed": False
                    })
                    tool_name = "reschedule_job"
                else:
                    # No reschedule context found — block and tell LLM to use the right tool
                    print(f"   🚫 [RESCHEDULE_INTERCEPT] BLOCKED {tool_name} during reschedule flow (no booking context)")
                    tool_results.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps({
                            "success": False,
                            "error": "You are in a reschedule flow. Use reschedule_job with the customer's chosen new date as new_datetime to move their existing booking. Do NOT use booking tools."
                        })
                    })
                    continue
            
            # REDIRECT lookup_customer during reschedule → reschedule_job with customer name
            # The LLM sometimes falls into the booking flow (lookup_customer → eircode → book)
            # when it should be continuing the reschedule. Intercept and redirect.
            if tool_name == "lookup_customer" and user_wants_reschedule:
                # Find the original date from the earlier reschedule_job call in history
                original_date = None
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        for tc in msg["tool_calls"]:
                            if tc.get("function", {}).get("name") in ("reschedule_job", "reschedule_appointment"):
                                try:
                                    prev_args = json.loads(tc["function"]["arguments"])
                                    original_date = prev_args.get("current_date") or prev_args.get("current_datetime")
                                except:
                                    pass
                
                customer_name_arg = json.loads(tool_call["function"]["arguments"]).get("customer_name", "")
                if original_date and customer_name_arg:
                    print(f"   🔄 [RESCHEDULE_INTERCEPT] Redirected lookup_customer → reschedule_job (mid-reschedule, name='{customer_name_arg}')")
                    tool_call["function"]["name"] = "reschedule_job"
                    tool_call["function"]["arguments"] = json.dumps({
                        "current_date": original_date,
                        "customer_name": customer_name_arg
                    })
                    tool_name = "reschedule_job"
                else:
                    print(f"   🚫 [RESCHEDULE_INTERCEPT] BLOCKED lookup_customer during reschedule flow")
                    tool_results.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps({
                            "success": False,
                            "error": "You are in a reschedule flow. Use reschedule_job with the customer's name to continue the reschedule — do not use lookup_customer."
                        })
                    })
                    continue
            
            print(f"\n   {'─'*50}")
            print(f"   🔧 [TOOL_EXEC] === Executing Tool {i+1}/{len(tool_calls)} ===")
            print(f"   🔧 [TOOL_EXEC] Name: {tool_name}")
            print(f"   🔧 [TOOL_EXEC] ID: {tool_id}")
            
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
                
                # AUTO-INJECT stored address for book_job if LLM forgot to include it
                # This is a common issue: the caller confirms their address but the LLM
                # doesn't pass it in the book_job arguments, causing the booking to fail.
                if tool_name in ('book_job', 'book_appointment') and not arguments.get('job_address'):
                    stored_addr = call_state.get("customer_address", "") if call_state else ""
                    if not stored_addr:
                        # Scan conversation for address — look for user messages after AI asked for address
                        _ai_asked_addr = False
                        for _msg in messages:
                            if _msg.get("role") == "assistant":
                                _content = (_msg.get("content") or "").lower()
                                if any(p in _content for p in ["full address", "your address", "eircode", "address for the job"]):
                                    _ai_asked_addr = True
                            elif _msg.get("role") == "user" and _ai_asked_addr:
                                _user_text = (_msg.get("content") or "").strip()
                                # Check if this looks like an address (has numbers or multiple words)
                                _words = _user_text.split()
                                _has_number = any(c.isdigit() for c in _user_text)
                                if len(_words) >= 3 and _has_number:
                                    # Clean up common ASR prefixes
                                    for _prefix in ["yeah. ", "yes. ", "sure. ", "it's ", "my address is "]:
                                        if _user_text.lower().startswith(_prefix):
                                            _user_text = _user_text[len(_prefix):]
                                    stored_addr = _user_text.strip().rstrip('.')
                                    break
                                _ai_asked_addr = False  # Reset if user didn't give address
                    if stored_addr:
                        arguments['job_address'] = stored_addr
                        tool_call["function"]["arguments"] = json.dumps(arguments)
                        print(f"   📍 [AUTO-INJECT] Added address to book_job: {stored_addr}")
                
                # SANITIZE email for book_job: ASR transcribes "at" literally
                # e.g., "jkdoherty123atgmail.com" → "jkdoherty123@gmail.com"
                if tool_name in ('book_job', 'book_appointment') and arguments.get('email'):
                    _raw_email = arguments['email']
                    _email = _raw_email
                    # Fix "atgmail" → "@gmail", "atyahoo" → "@yahoo", etc.
                    _email = re.sub(r'(?i)\bat(gmail|yahoo|hotmail|outlook|icloud|live|aol|protonmail|mail)', r'@\1', _email)
                    # Fix "at " or " at " in the middle
                    _email = re.sub(r'\s*at\s+', '@', _email)
                    # Fix "dot com" → ".com", etc.
                    _email = re.sub(r'\s*dot\s*(com|ie|co\.uk|org|net|io|dev)\b', r'.\1', _email, flags=re.IGNORECASE)
                    _email = _email.replace(' ', '')
                    # Ensure @ symbol exists
                    if '@' not in _email and '.' in _email:
                        for _domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com']:
                            _domain_no_dot = _domain.replace('.', '')
                            if _domain_no_dot in _email.lower():
                                _email = _email.lower().replace(_domain_no_dot, _domain)
                                _idx = _email.index(_domain)
                                if _idx > 0 and _email[_idx-1] != '@':
                                    _email = _email[:_idx] + '@' + _email[_idx:]
                                break
                    if _email != _raw_email:
                        arguments['email'] = _email
                        tool_call["function"]["arguments"] = json.dumps(arguments)
                        print(f"   📧 [AUTO-FIX] Email sanitized: '{_raw_email}' → '{_email}'")
                
                print(f"   🔧 [TOOL_EXEC] Arguments: {json.dumps(arguments)}")
                
                # AUTO-INJECT previously suggested dates from call state
                # This makes the "other options" / "different day" flow reliable
                # regardless of whether the LLM remembers to pass them
                # BUT: if the caller asks for the "soonest" / "earliest" / "closest"
                # date, we should NOT skip — they want to circle back to the nearest option
                # ALSO: if the caller is SELECTING a specific date (e.g., "the 31st of March"),
                # don't inject skip dates — they're choosing from what was offered, not browsing
                if tool_name in ('search_availability', 'search_reschedule_availability', 'get_next_available') and call_state and call_state.suggested_dates:
                    if not arguments.get('previously_suggested_dates'):
                        query_text = (arguments.get('query') or '').lower()
                        soonest_patterns = ['soonest', 'earliest', 'closest', 'first available', 'nearest',
                                            'as soon as', 'quickest', 'next available', 'asap']
                        wants_soonest = any(p in query_text for p in soonest_patterns)
                        
                        # Detect if the caller is selecting a specific date/time from what was offered.
                        # This includes ordinal dates ("the 7th"), month+day ("March 31"),
                        # relative days ("tomorrow", "today"), day-of-week names ("Thursday"),
                        # or time selections ("at 1pm", "1 o'clock").
                        # Bare numbers like "2 weeks" or "after 4pm" should NOT match.
                        month_pattern = '(?:january|february|march|april|may|june|july|august|september|october|november|december)'
                        day_pattern = '(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
                        relative_day_pattern = '(?:tomorrow|today)'
                        has_specific_date = bool(
                            re.search(r'\d{1,2}(?:st|nd|rd|th)\b', query_text) or  # ordinal: "31st", "7th"
                            re.search(month_pattern + r'\s+\d{1,2}\b', query_text) or  # "March 31", "April 7"
                            re.search(r'\d{1,2}\s+(?:of\s+)?' + month_pattern, query_text) or  # "31 of March", "7 march"
                            re.search(relative_day_pattern, query_text) or  # "tomorrow", "today"
                            re.search(day_pattern, query_text)  # "Thursday", "Monday" etc.
                        )
                        
                        if wants_soonest:
                            print(f"   🔧 [TOOL_EXEC] Caller wants soonest — NOT injecting skip dates, searching from start")
                        elif has_specific_date:
                            print(f"   🔧 [TOOL_EXEC] Caller selecting specific date — NOT injecting skip dates")
                        else:
                            arguments['previously_suggested_dates'] = list(call_state.suggested_dates)
                            print(f"   🔧 [TOOL_EXEC] Auto-injected {len(call_state.suggested_dates)} previously suggested dates from call state")
                
                # Execute tool with timeout protection
                try:
                    tool_start = time.time()
                    print(f"   🔧 [TOOL_EXEC] Starting execution at {tool_start:.3f}...")
                    print(f"   🔧 [TOOL_EXEC] Running in thread pool (non-blocking)...")
                    
                    # Run tool execution in thread pool to not block event loop
                    # This allows audio playback to continue during tool execution
                    # CRITICAL: Add timeout to prevent infinite hang
                    # Use longer timeout for search operations that may need to check many days
                    TOOL_TIMEOUT = 15.0 if tool_name in ['search_availability', 'search_reschedule_availability', 'get_next_available', 'check_availability', 'book_job'] else 10.0
                    try:
                        result = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None,  # Use default thread pool
                                lambda: execute_tool_call(tool_name, arguments, services)
                            ),
                            timeout=TOOL_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        print(f"   ⚠️ [TOOL_EXEC] Tool timed out after {TOOL_TIMEOUT}s!")
                        result = {"success": False, "error": f"Tool execution timed out after {TOOL_TIMEOUT}s"}
                    
                    tool_duration = time.time() - tool_start
                    print(f"   🔧 [TOOL_EXEC] ✅ Tool completed in {tool_duration:.3f}s")
                    
                    if not result:
                        print(f"   ⚠️ [TOOL_EXEC] Tool returned None!")
                        raise Exception("Tool returned None")
                    
                    print(f"   🔧 [TOOL_RESULT] Success: {result.get('success')}, Message: {result.get('message', result.get('error', 'N/A'))[:100]}")
                    
                    # CAPTURE suggested_dates from tool result into call state
                    # so they auto-inject on the next availability search call
                    if call_state and result.get('suggested_dates'):
                        new_dates = result.get('suggested_dates', [])
                        if new_dates:
                            for d in new_dates:
                                if d not in call_state.suggested_dates:
                                    call_state.suggested_dates.append(d)
                            print(f"   🔧 [TOOL_RESULT] Accumulated {len(call_state.suggested_dates)} total suggested dates in call state")
                    
                    # Clear suggested dates when a booking/reschedule completes successfully
                    # so the next availability search starts fresh
                    if tool_name in ('book_job', 'reschedule_job', 'book_appointment', 'reschedule_appointment') and call_state and result.get('success'):
                        call_state.suggested_dates = []
                        call_state.last_booking_turn = call_state.current_turn
                        print(f"   🔧 [TOOL_RESULT] Cleared suggested dates after successful {tool_name}")
                        print(f"   🔧 [TOOL_RESULT] Set last_booking_turn={call_state.current_turn}")
                    
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
        # IMPORTANT: Use a deep copy of tool_calls so the conversation history
        # reflects any interception changes (e.g., cancel_job → reschedule_job).
        # The in-place mutation above modifies the dict, but to be safe we
        # build fresh dicts from the current state of each tool_call.
        history_tool_calls = [
            {
                "id": tc["id"],
                "type": tc.get("type", "function"),
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]
                }
            }
            for tc in tool_calls
        ]
        messages.append({
            "role": "assistant",
            "content": full_response if full_response else "",  # Empty string instead of None
            "tool_calls": history_tool_calls
        })
        
        # Add tool results to history
        messages.extend(tool_results)
        
        # Debug: confirm what was stored in history (helps verify reschedule interception)
        stored_tool_names = [tc["function"]["name"] for tc in history_tool_calls]
        stored_result_names = [tr.get("name", "?") for tr in tool_results]
        print(f"   📝 [HISTORY] Stored assistant tool_calls: {stored_tool_names}")
        print(f"   📝 [HISTORY] Stored tool results: {stored_result_names}")
        
        # Make another call to get LLM's response based on tool results
        tool_exec_duration = time.time() - tool_phase_start
        print(f"   🔧 [TOOL_PHASE] Tool execution complete in {tool_exec_duration:.3f}s")
        # Yield timing marker for tool execution
        yield f"<<<TIMING:tool_execution_ms={tool_exec_duration*1000:.1f}>>>"
        
        # ============================================================
        # DIRECT RESPONSES: Skip second OpenAI call for speed
        # The tool results contain enough info to respond directly
        # ============================================================
        tool_name = tool_calls[0]["function"]["name"] if tool_calls else None
        direct_response = None
        
        try:
            # Safety check - ensure we have tool results
            if not tool_results:
                print(f"   ⚠️ [DIRECT_RESPONSE] No tool results available")
                direct_response = None
            else:
                result_content = json.loads(tool_results[0]["content"]) if tool_results[0].get("content") else {}
                
                # ========== LOOKUP_CUSTOMER ==========
                if tool_name == "lookup_customer":
                    if result_content.get("success"):
                        customer_info = result_content.get("customer_info", {})
                        customer_name = customer_info.get("name", "")
                        first_name = customer_name.split()[0] if customer_name else "there"
                        last_address = customer_info.get("last_address", "")
                        
                        if result_content.get("customer_exists"):
                            # Returning customer found by phone
                            if last_address:
                                direct_response = f"Is it the same address as before - {last_address}?"
                            else:
                                direct_response = f"Do you know your eircode?"
                        else:
                            # New customer — the LLM should NOT have called lookup_customer
                            # (the system context already told it this is a new customer).
                            # Check if the caller already gave their name in conversation
                            _caller_already_gave_name = False
                            _stored_name = call_state.get("customer_name", "") if call_state else ""
                            if not _stored_name:
                                # Check conversation history for name introduction
                                for _msg in messages:
                                    if _msg.get("role") == "user":
                                        _msg_text = (_msg.get("content") or "").lower()
                                        if "my name is" in _msg_text or "name's" in _msg_text or "i'm " in _msg_text:
                                            _caller_already_gave_name = True
                                            break
                                # Also check if the AI already asked for name and got a response
                                for _idx, _msg in enumerate(messages):
                                    if _msg.get("role") == "assistant":
                                        _content = (_msg.get("content") or "").lower()
                                        if "your name" in _content or "get your name" in _content:
                                            # Check if there's a user response after this
                                            if _idx + 1 < len(messages) and messages[_idx + 1].get("role") == "user":
                                                _caller_already_gave_name = True
                                                break
                            else:
                                _caller_already_gave_name = True
                            
                            if _caller_already_gave_name:
                                # Name already provided — skip to eircode/address
                                direct_response = "Do you know your eircode?"
                            else:
                                # Ask for name since the LLM skipped it.
                                direct_response = "Can I get your name please, and spell it out for me if possible?"
                    else:
                        # Error — check if name was already given before asking again
                        _stored_name = call_state.get("customer_name", "") if call_state else ""
                        if _stored_name:
                            direct_response = "Do you know your eircode?"
                        else:
                            direct_response = "Can I get your name please, and spell it out for me if possible?"
                    
                    if direct_response:
                        print(f"   ⚡ [DIRECT] lookup_customer -> '{direct_response[:50]}...'")
                
                # ========== CHECK_AVAILABILITY ==========
                elif tool_name == "check_availability":
                    if result_content.get("success"):
                        natural_summary = result_content.get("natural_summary", "")
                        available_slots = result_content.get("available_slots", [])
                        message = result_content.get("message", "")
                        is_callout = result_content.get("is_callout_service", False)
                        
                        # Check if this is a full-day job
                        is_full_day = result_content.get("is_full_day_service", False)
                        duration_minutes = result_content.get("duration_minutes", 0)
                        duration_label = result_content.get("duration_label", "")
                        
                        # Also check natural_summary for "full day" or "wide open" as backup
                        if not is_full_day and natural_summary:
                            is_full_day = any(phrase in natural_summary.lower() for phrase in ["full day", "wide open"])
                        
                        # Check if multiple days are mentioned
                        has_multiple_days = natural_summary and any(word in natural_summary.lower() for word in [" and ", ", "])
                        
                        # ALWAYS prefix with job length context for ALL durations
                        duration_prefix = ""
                        if is_callout:
                            duration_prefix = "This service requires a call-out first so we can have a look before scheduling the full job. "
                        elif duration_minutes > 1440 and duration_label:
                            duration_prefix = f"This job takes {duration_label}, but "
                        elif duration_minutes >= 480 and duration_label:
                            duration_prefix = f"This is {duration_label} job, and "
                        elif duration_minutes > 0 and duration_label:
                            duration_prefix = f"This is {duration_label} job. "
                        
                        # For complex queries, use second LLM call for better phrasing
                        if natural_summary:
                            if is_full_day:
                                # Full-day jobs: Don't ask for time, just confirm the day(s)
                                if has_multiple_days:
                                    direct_response = f"{duration_prefix}{natural_summary}. Which day works best for you?"
                                else:
                                    direct_response = f"{duration_prefix}{natural_summary}. Does that day work for you?"
                            else:
                                # Regular jobs: Ask for time preference
                                direct_response = f"{duration_prefix}{natural_summary}. Which time works best for you?"
                        elif available_slots:
                            # Format first few slots
                            times = [f"{s.get('date', '')} at {s.get('time', '')}" for s in available_slots[:3]]
                            direct_response = f"I have {', '.join(times)} available. Which works for you?"
                        elif message:
                            # Use the natural language message from calendar_tools
                            # Add suggestion to try another day
                            direct_response = f"{message}. Would you like to try a different day?"
                        else:
                            direct_response = "That day is fully booked. Would you like to try a different day?"
                    else:
                        error = result_content.get("error", result_content.get("message", ""))
                        if "closed" in error.lower() or "not open" in error.lower():
                            direct_response = "We're not open that day. What other day would work for you?"
                        else:
                            direct_response = "I couldn't check that day. What day works for you?"
                    
                    print(f"   ⚡ [DIRECT] check_availability -> '{direct_response[:50]}...'")
                
                # ========== GET_NEXT_AVAILABLE ==========
                elif tool_name == "get_next_available":
                    if result_content.get("success"):
                        natural_summary = result_content.get("natural_summary", "")
                        available_days = result_content.get("available_days", [])
                        is_full_day = result_content.get("is_full_day_service", False)
                        days_found = result_content.get("days_found", 0)
                        duration_minutes = result_content.get("duration_minutes", 0)
                        duration_label = result_content.get("duration_label", "")
                        is_callout = result_content.get("is_callout_service", False)
                        
                        # ALWAYS prefix with job length context for ALL durations
                        duration_prefix = ""
                        if is_callout:
                            duration_prefix = "This service requires a call-out first so we can have a look before scheduling the full job. "
                        elif duration_minutes > 1440 and duration_label:
                            duration_prefix = f"This job takes {duration_label}, but "
                        elif duration_minutes >= 480 and duration_label:
                            duration_prefix = f"This is {duration_label} job, and "
                        elif duration_minutes > 0 and duration_label:
                            duration_prefix = f"This is {duration_label} job. "
                        
                        if natural_summary:
                            if is_full_day:
                                # Full-day jobs: Ask which day, not time
                                if days_found > 1:
                                    direct_response = f"{duration_prefix}{natural_summary}. Which day suits you?"
                                else:
                                    direct_response = f"{duration_prefix}{natural_summary}. Does that day work for you?"
                            else:
                                # Regular jobs with times
                                direct_response = f"{duration_prefix}{natural_summary}. Which day and time works for you?"
                        elif available_days:
                            # Fallback: list the days
                            day_names = [d.get('day_name', '') for d in available_days[:3]]
                            direct_response = f"I have {', '.join(day_names)} available. Which works for you?"
                        else:
                            direct_response = result_content.get("message", "I don't have any availability soon. Would you like me to check further out?")
                    else:
                        direct_response = "I couldn't check availability. What day would you like to try?"
                    
                    print(f"   ⚡ [DIRECT] get_next_available -> '{direct_response[:50]}...'")
                
                # ========== SEARCH_RESCHEDULE_AVAILABILITY ==========
                elif tool_name == "search_reschedule_availability":
                    if result_content.get("success"):
                        natural_summary = result_content.get("natural_summary", "")
                        message = result_content.get("message", "")
                        days_found = result_content.get("days_found", 0)
                        is_full_day = result_content.get("is_full_day_service", False)
                        
                        if natural_summary:
                            if days_found > 1:
                                direct_response = f"{natural_summary}. Which day works for you?"
                            elif days_found == 1:
                                direct_response = f"{natural_summary}. Does that day work?"
                            else:
                                direct_response = message or "The assigned employee has no availability then. Would you like to speak with someone?"
                        elif message:
                            direct_response = message
                        else:
                            direct_response = "The assigned employee has no availability in that period. Would you like to try different dates?"
                    else:
                        direct_response = result_content.get("error", "I couldn't check the employee's availability. What dates would you like to try?")
                    
                    print(f"   ⚡ [DIRECT] search_reschedule_availability -> '{direct_response[:50]}...'")
                
                # ========== SEARCH_AVAILABILITY ==========
                elif tool_name == "search_availability":
                    if result_content.get("success"):
                        natural_summary = result_content.get("natural_summary", "")
                        available_slots = result_content.get("available_slots", [])
                        message = result_content.get("message", "")
                        is_full_day = result_content.get("is_full_day_service", False)
                        days_found = result_content.get("days_found", 0)
                        duration_minutes = result_content.get("duration_minutes", 0)
                        duration_label = result_content.get("duration_label", "")
                        is_callout = result_content.get("is_callout_service", False)
                        
                        # ALWAYS prefix with job length context for ALL durations
                        duration_prefix = ""
                        if is_callout:
                            duration_prefix = "This service requires a call-out first so we can have a look before scheduling the full job. "
                        elif duration_minutes > 1440 and duration_label:
                            duration_prefix = f"This job takes {duration_label}, but "
                        elif duration_minutes >= 480 and duration_label:
                            duration_prefix = f"This is {duration_label} job, and "
                        elif duration_minutes > 0 and duration_label:
                            duration_prefix = f"This is {duration_label} job. "
                        
                        if natural_summary:
                            if is_full_day:
                                if days_found > 1:
                                    direct_response = f"{duration_prefix}{natural_summary}. Which day works for you?"
                                else:
                                    direct_response = f"{duration_prefix}{natural_summary}. Does that day work?"
                            else:
                                direct_response = f"{duration_prefix}{natural_summary}. Which works best for you?"
                        elif available_slots:
                            times = [f"{s.get('date', '')} at {s.get('time', '')}" for s in available_slots[:3]]
                            direct_response = f"I have {', '.join(times)} available. Which works for you?"
                        elif message:
                            direct_response = message
                        else:
                            direct_response = "I don't have anything available then. Would you like to try different dates?"
                    else:
                        direct_response = "I couldn't search that time period. What dates would you like to check?"
                    
                    print(f"   ⚡ [DIRECT] search_availability -> '{direct_response[:50]}...')")
                
                # ========== BOOK_JOB / BOOK_APPOINTMENT ==========
                elif tool_name in ["book_appointment", "book_job"]:
                    if result_content.get("success"):
                        details = result_content.get("appointment_details", {})
                        time_str = details.get("time", "")
                        address = details.get("job_address", "") or details.get("eircode", "")
                        duration_mins = details.get("duration_minutes", 0)
                        is_callout_booking = result_content.get("is_callout_booking", False)
                        is_quote_booking = result_content.get("is_quote_booking", False)
                        original_service = result_content.get("original_service_name", "")
                        
                        # Check if this is a full-day job (8+ hours)
                        is_full_day = duration_mins >= 480
                        
                        # Check if customer provided an email (for portal message)
                        customer_has_email = bool(details.get("email"))
                        if not customer_has_email and call_state:
                            # Also check if email was mentioned in conversation
                            customer_has_email = bool(call_state.get("customer_email"))
                        
                        # Portal suffix: mention confirmation email + customer portal if email was provided
                        if customer_has_email:
                            portal_suffix = " You'll get a confirmation email shortly with a link to your customer portal — if you could upload any photos or videos of the issue there, that'd be a great help for us to prepare. Is there anything else?"
                        else:
                            portal_suffix = " Is there anything else?"
                        
                        if is_callout_booking:
                            # Callout booking: tell the caller it's a call-out visit
                            if is_full_day and time_str:
                                day_part = time_str.split(" at ")[0] if " at " in time_str else time_str
                                direct_response = f"Grand, you're all booked in for a call-out visit on {day_part}. We'll come out and have a look, and then schedule the full {original_service} job after that.{portal_suffix}"
                            elif time_str:
                                direct_response = f"Grand, you're all booked in for a call-out visit on {time_str}. We'll come out and have a look, and then schedule the full {original_service} job after that.{portal_suffix}"
                            else:
                                direct_response = f"Grand, you're all booked in for a call-out visit. We'll come out and have a look, and then schedule the full job after that.{portal_suffix}"
                        elif is_quote_booking:
                            # Quote booking: tell the caller it's a free quote visit
                            if is_full_day and time_str:
                                day_part = time_str.split(" at ")[0] if " at " in time_str else time_str
                                direct_response = f"Grand, you're all booked in for a free quote visit on {day_part}. We'll come out, have a look, and give you a quote for the {original_service} job.{portal_suffix}"
                            elif time_str:
                                direct_response = f"Grand, you're all booked in for a free quote visit on {time_str}. We'll come out, have a look, and give you a quote for the {original_service} job.{portal_suffix}"
                            else:
                                direct_response = f"Grand, you're all booked in for a free quote visit. We'll come out, have a look, and give you a quote.{portal_suffix}"
                        elif is_full_day and time_str:
                            # For full-day jobs, extract just the day (not the time)
                            day_part = time_str.split(" at ")[0] if " at " in time_str else time_str
                            direct_response = f"Grand, you're all booked in for {day_part}. We'll give you a call when we're on the way.{portal_suffix}"
                        elif time_str:
                            direct_response = f"Grand, you're all booked in for {time_str}.{portal_suffix}"
                        else:
                            direct_response = f"Grand, you're all booked in.{portal_suffix}"
                    else:
                        error = result_content.get("error", result_content.get("message", ""))
                        if "not available" in error.lower() or "already booked" in error.lower():
                            direct_response = "That time slot just got taken. Would you like to try a different time?"
                        elif "missing" in error.lower() or "address" in error.lower():
                            # Specific error about missing address — tell the caller what's needed
                            if "address" in error.lower():
                                # Try to get stored address from call_state
                                stored_addr = call_state.get("customer_address", "") if call_state else ""
                                if stored_addr:
                                    direct_response = f"I just need to confirm the address. Is it still {stored_addr}?"
                                else:
                                    direct_response = "I just need the address for the job. Can I get your eircode or full address?"
                            else:
                                direct_response = "I'm missing some details. Could you confirm the time you'd like?"
                        else:
                            direct_response = "I couldn't complete that booking. Could you try again?"
                    
                    print(f"   ⚡ [DIRECT] book -> '{direct_response[:50]}...')")
                
                # ========== CANCEL_JOB / CANCEL_APPOINTMENT ==========
                elif tool_name in ["cancel_appointment", "cancel_job"]:
                    if result_content.get("success"):
                        # Actual cancellation done
                        direct_response = result_content.get("message", "That's cancelled for you. Is there anything else I can help with?")
                    elif result_content.get("requires_confirmation"):
                        # First call - found jobs on that day, need name confirmation
                        direct_response = result_content.get("message", "")
                    else:
                        # Error — make date parsing failures sound natural
                        error = result_content.get("error", "")
                        if "could not understand the date" in error.lower():
                            direct_response = "I didn't quite catch the date. Could you tell me the day and month, like March 27th?"
                        elif "no bookings found" in error.lower():
                            direct_response = "I don't see any bookings on that day. Could you double-check the date?"
                        else:
                            direct_response = error or "I couldn't find that booking. What day was it for?"
                    
                    print(f"   ⚡ [DIRECT] cancel -> '{direct_response[:50]}...'")
                
                # ========== RESCHEDULE_JOB / RESCHEDULE_APPOINTMENT ==========
                elif tool_name in ["reschedule_appointment", "reschedule_job"]:
                    if result_content.get("success"):
                        # Rescheduled successfully
                        direct_response = result_content.get("message", "Your booking has been rescheduled. Anything else?")
                    elif result_content.get("requires_confirmation"):
                        # First call - found jobs on that day, need name confirmation
                        direct_response = result_content.get("message", "")
                    elif result_content.get("requires_reschedule_confirmation"):
                        # New date chosen, need verbal confirmation before executing
                        direct_response = result_content.get("message", "")
                    elif result_content.get("customer_name_confirmed"):
                        # Name confirmed, need new date
                        direct_response = result_content.get("error", "What day would you like to move it to?")
                    else:
                        # Error — make date parsing failures sound natural
                        error = result_content.get("error", "")
                        if "could not understand the date" in error.lower():
                            direct_response = "I didn't quite catch the date. Could you tell me the day and month, like March 27th?"
                        elif "no bookings found" in error.lower():
                            direct_response = "I don't see any bookings on that day. Could you double-check the date?"
                        else:
                            direct_response = error or "I couldn't find that booking. What day was it for?"
                    
                    print(f"   ⚡ [DIRECT] reschedule -> '{direct_response[:50]}...'")
                
                # ========== MODIFY_JOB ==========
                elif tool_name == "modify_job":
                    if result_content.get("success"):
                        changes = result_content.get("changes", [])
                        if changes:
                            direct_response = f"I've updated that for you. Anything else?"
                        else:
                            customer_name = result_content.get("customer_name", "")
                            if customer_name:
                                direct_response = f"I found the appointment for {customer_name}. What would you like to change?"
                            else:
                                direct_response = "What would you like to change about the appointment?"
                    else:
                        direct_response = "I couldn't find that appointment. What date and time was it for?"
                    
                    print(f"   ⚡ [DIRECT] modify -> '{direct_response[:50]}...'")
                
                # ========== TRANSFER_TO_HUMAN ==========
                elif tool_name == "transfer_to_human":
                    # Transfer is handled by the transfer marker - no response needed
                    if result_content.get("success") and result_content.get("transfer"):
                        direct_response = "Transferring you now, please hold."
                    else:
                        # Transfer failed - use the actual error message instead of pretending to connect
                        direct_response = result_content.get("message", "I'm sorry, I'm unable to transfer you right now. Is there anything else I can help you with?")
                    
                    print(f"   ⚡ [DIRECT] transfer -> '{direct_response}'")
                
                # ========== SEARCH_BOOKINGS ==========
                elif tool_name == "search_bookings":
                    if result_content.get("success"):
                        message = result_content.get("message", "")
                        bookings = result_content.get("bookings", [])
                        if bookings:
                            # Format naturally for the caller
                            direct_response = message if message else "I found your booking."
                        elif message:
                            direct_response = message
                        else:
                            direct_response = "I don't see any bookings matching that. Could you double-check the details?"
                    else:
                        direct_response = "I couldn't find any bookings. What name or date should I search for?"
                    
                    print(f"   ⚡ [DIRECT] search_bookings -> '{direct_response[:50]}...'")
                
                # ========== MATCH_ISSUE — smart response based on results ==========
                elif tool_name == "match_issue":
                    matches = result_content.get("matches", [])
                    top_score = result_content.get("top_score", 0)
                    has_investigation = result_content.get("has_investigation_option", False)
                    needs_clarification = result_content.get("needs_clarification", False)
                    
                    # Check if the TOP match itself requires investigation
                    top_is_investigation = matches[0].get('requires_investigation', False) if matches else False
                    
                    # Check if multiple matches are close in score (within 25 points of top)
                    # This catches cases like "Leak Fix" (service) vs "Leak Fix and Investigation" (package)
                    close_matches = [m for m in matches if m['score'] >= top_score - 25] if matches else []
                    multiple_close = len(close_matches) > 1
                    
                    # GUARD: Check if match_issue was already called AND confirmed earlier
                    # in this conversation. If so, don't re-confirm the service — skip to
                    # None so the second LLM call handles it with full context.
                    _match_already_confirmed = False
                    _prev_match_issue_count = 0
                    for _msg in messages:
                        if _msg.get("role") == "assistant" and _msg.get("tool_calls"):
                            for _tc in _msg["tool_calls"]:
                                if _tc.get("function", {}).get("name") == "match_issue":
                                    _prev_match_issue_count += 1
                    # If match_issue was called before (this is the 2nd+ time), the service
                    # was likely already confirmed. Let the LLM handle it with full context
                    # instead of re-asking "A plumbing, is that correct?"
                    if _prev_match_issue_count > 0:
                        _match_already_confirmed = True
                        print(f"   ⚡ [DIRECT] match_issue already called {_prev_match_issue_count} time(s) before — skipping direct response, letting LLM handle with context")
                        direct_response = None
                    
                    if _match_already_confirmed:
                        # Service was already confirmed earlier — don't re-ask.
                        # Generate a contextual response based on what info we still need.
                        _has_name = bool(call_state.get("customer_name", "")) if call_state else False
                        if not _has_name:
                            # Check conversation for name
                            for _msg in messages:
                                if _msg.get("role") == "user":
                                    _msg_text = (_msg.get("content") or "").lower()
                                    if "my name is" in _msg_text or "name's" in _msg_text:
                                        _has_name = True
                                        break
                        
                        _has_address = bool(call_state.get("customer_address", "")) if call_state else False
                        _email_asked = any(
                            "email" in (msg.get("content") or "").lower()
                            for msg in messages
                            if msg.get("role") == "assistant"
                        )
                        
                        if not _has_name:
                            direct_response = "Can I get your name please, and spell it out for me if possible?"
                        elif not _has_address:
                            direct_response = "Do you know your eircode?"
                        elif not _email_asked:
                            direct_response = "And can I get an email address for the account? Please spell it out for me letter by letter."
                        else:
                            # All info gathered — this shouldn't happen, let LLM handle
                            direct_response = None
                        
                        if direct_response:
                            print(f"   ⚡ [DIRECT] match_issue (repeat) -> '{direct_response[:50]}...' (skipped re-confirmation, advancing flow)")
                        else:
                            print(f"   ⚡ [DIRECT] match_issue (repeat) -> None (all info gathered, falling through to LLM)")
                    elif not matches:
                        # Track consecutive match failures to avoid infinite loop
                        if call_state:
                            call_state.match_issue_fail_count += 1
                        fail_count = call_state.match_issue_fail_count if call_state else 1
                        
                        if fail_count >= 2:
                            # Already asked once for more details — fall back to General Service
                            customer_name = call_state.get("customer_name", "") if call_state else ""
                            stored_address = call_state.get("customer_address", "") if call_state else ""
                            if customer_name:
                                first_name = customer_name.split()[0]
                                # Check if we've already confirmed the name with the caller
                                name_already_confirmed = call_state.get("caller_identified", False) if call_state else False
                                if name_already_confirmed:
                                    name_prefix = f"Grand {first_name}"
                                else:
                                    # First time using the name — attribute it to the system and use FULL name
                                    # so the LLM knows the full name for booking
                                    name_prefix = f"I have the name under this number as {customer_name}. Grand {first_name}"
                                    if call_state:
                                        call_state["caller_identified"] = True
                                
                                if stored_address:
                                    direct_response = f"{name_prefix}, I'll book you in for a general callout and we can take a look. Is it still the same address, {stored_address}?"
                                else:
                                    direct_response = f"{name_prefix}, I'll book you in for a general callout and we can take a look. Can I get your eircode or address?"
                            else:
                                direct_response = "Grand, I'll book you in for a general callout and we can take a look. Can I get your name please?"
                            # Set service type so the booking flow uses General Callout
                            if call_state:
                                call_state.service_type = "General Callout"
                                call_state.active_booking = True
                                call_state.gathering_started = True
                            print(f"   ⚡ [DIRECT] match_issue FALLBACK to General Callout (fail_count={fail_count})")
                        else:
                            direct_response = "Could you give me a bit more detail on the issue so I can narrow it down?"
                    else:
                        # Reset fail count — we found matches
                        if call_state:
                            call_state.match_issue_fail_count = 0
                        
                        if multiple_close or needs_clarification:
                            # Multiple close-scoring matches — ask caller to clarify
                            # This prevents auto-picking "Leak Fix" when "Leak Fix and Investigation" is also a strong match
                            if has_investigation:
                                direct_response = "Do you know what's causing the issue, or would you like us to investigate it first?"
                            else:
                                # List the top 2 options for the caller to choose
                                option_names = [m['name'] for m in close_matches[:2]]
                                if len(option_names) == 2:
                                    direct_response = f"We have a {option_names[0].lower()} and a {option_names[1].lower()}. Which one sounds right for you?"
                                else:
                                    direct_response = "Can you tell me a bit more about the issue so I can match you with the right service?"
                        elif top_score >= 80 and not top_is_investigation:
                            # Clear high-confidence match with no close competitors — confirm it
                            direct_response = f"A {matches[0]['name'].lower()}, is that correct?"
                        elif top_score >= 80 and top_is_investigation:
                            # High confidence but it's an investigation package — still confirm but mention investigation
                            direct_response = f"That sounds like it may need investigation first. We have a {matches[0]['name'].lower()} package — shall we go with that?"
                        elif has_investigation:
                            # Multiple matches and investigation is a contender — ask about the cause
                            direct_response = "Do you know what's causing the issue, or do you think it will need investigation first?"
                        elif len(matches) > 1:
                            direct_response = "Can you tell me a bit more about the issue so I can match you with the right service?"
                        else:
                            direct_response = f"One of the services we offer is a {matches[0]['name'].lower()}. Does that sound like the issue your experiencing?"
                    
                    if direct_response:
                        print(f"   ⚡ [DIRECT] match_issue -> '{direct_response[:50]}...' ({len(matches)} matches, top={top_score}, top_investigation={top_is_investigation})")
                    else:
                        print(f"   ⚡ [DIRECT] match_issue -> None ({len(matches)} matches, top={top_score}, top_investigation={top_is_investigation})")
                
                # ========== FALLBACK FOR ANY OTHER TOOL ==========
                else:
                    # Generic fallback for unknown tools
                    if result_content.get("success"):
                        message = result_content.get("message", "")
                        if message:
                            direct_response = message
                        else:
                            direct_response = "I've done that for you. What else can I help with?"
                    else:
                        error = result_content.get("error", result_content.get("message", ""))
                        if error:
                            direct_response = f"I ran into an issue: {error[:100]}. Could you try again?"
                        else:
                            direct_response = "I couldn't complete that. Could you try again?"
                    
                    print(f"   ⚡ [DIRECT] {tool_name} (fallback) -> '{direct_response[:50]}...'")
                
        except Exception as e:
            print(f"   ⚠️ [DIRECT_RESPONSE] Error generating direct response: {e}")
            import traceback
            traceback.print_exc()
            # On error, set to None so we fall through to second LLM call
            direct_response = None
        
        # ============================================================
        # HYBRID: Use direct response OR second LLM call
        # ============================================================
        
        # Use direct response (fast path) - always use this to save 6-7s
        if direct_response:
            # Sanitize for TTS: remove bullet points, dashes, newlines that cause TTS cutoff
            direct_response = sanitize_for_tts(direct_response)
            yield f"<<<TIMING:direct_response=1>>>"
            print(f"   ✅ [DIRECT] Skipped second OpenAI call (saved ~6-7s)")
            
            # Add to conversation history
            messages.append({"role": "assistant", "content": direct_response})
            
            # After a successful booking, inject a system message to prevent
            # the LLM from re-asking confirmation questions in a loop.
            # The booking is DONE — no need to confirm again.
            if tool_name in ("book_job", "book_appointment") and any(
                json.loads(tr["content"]).get("success") for tr in tool_results
                if tr.get("content")
            ):
                messages.append({
                    "role": "system",
                    "content": (
                        "[SYSTEM: The booking is CONFIRMED and COMPLETE. Do NOT ask for confirmation again. "
                        "Do NOT re-confirm the booking details. Do NOT ask 'is that correct?' about the booking. "
                        "The job is booked. If the caller says anything, just ask if there's anything else you can help with, "
                        "or say goodbye warmly. If they want a SECOND booking, start fresh with match_issue.]"
                    )
                })
            
            # After presenting availability, remind LLM to wait for customer to pick
            # and confirm before booking. Prevents premature book_job calls.
            if tool_name in ("get_next_available", "search_availability") and any(
                json.loads(tr["content"]).get("success") for tr in tool_results
                if tr.get("content")
            ):
                messages.append({
                    "role": "system",
                    "content": (
                        "[SYSTEM: You just presented availability options. WAIT for the customer to pick a SPECIFIC day and time. "
                        "After they pick, CONFIRM with them: 'So that's [day] at [time] for the [issue]. Is that all correct?' "
                        "Do NOT call book_job until the customer explicitly confirms YES. "
                        "If they say 'correct' or 'yes' right now, they may be confirming the ADDRESS, not choosing a booking time — "
                        "ask which day and time they'd like.]"
                    )
                })
            
            # After lookup_customer, remind LLM of the full booking flow
            if tool_name == "lookup_customer":
                # Check if this was a new or returning customer
                _lookup_result = json.loads(tool_results[0]["content"]) if tool_results and tool_results[0].get("content") else {}
                _is_new = not _lookup_result.get("customer_exists", False)
                if _is_new:
                    messages.append({
                        "role": "system",
                        "content": (
                            "[SYSTEM: This is a NEW CUSTOMER. You just asked for their name. "
                            "After they give their name, ask for eircode: 'Do you know your eircode?' "
                            "If they don't know it, ask for full address. "
                            "After getting address, ask for email: 'And can I get an email address for the account? Please spell it out for me letter by letter.' "
                            "After email, call get_next_available. "
                            "Do NOT skip name, address, or email. Do NOT call book_job until ALL details are collected AND the customer confirms.]"
                        )
                    })
                else:
                    messages.append({
                        "role": "system",
                        "content": (
                            "[SYSTEM: Returning customer confirmed. After address is confirmed, "
                            "check if email is on file. If not, ask for it. Then call get_next_available.]"
                        )
                    })
            
            # Check for transfer
            if tool_name == "transfer_to_human" and tool_results:
                try:
                    result_content = json.loads(tool_results[0]["content"])
                    if result_content.get("transfer") and result_content.get("fallback_number"):
                        yield f"<<<TRANSFER:{result_content.get('fallback_number')}>>>"
                except:
                    pass
            
            # Check if this exact phrase is prerecorded (saves ElevenLabs TTS cost)
            try:
                from src.services.prerecorded_audio import get_filler_id_from_message
                prerecorded_id = get_filler_id_from_message(direct_response)
            except Exception:
                prerecorded_id = None
            if prerecorded_id:
                print(f"   🔊 [DIRECT] Using prerecorded audio: {prerecorded_id}")
                yield f"<<<PRERECORDED:{prerecorded_id}>>>"
            else:
                yield direct_response
            return
        
        # This should rarely happen - but if no direct response, use second LLM call
        if not direct_response:
            print(f"   ⚠️ [DIRECT] No direct response generated - falling through to second LLM call")
            
            # Add tool results to messages for the second LLM call
            # First add the assistant message with tool_calls
            assistant_msg = {"role": "assistant", "content": None, "tool_calls": []}
            for tc in tool_calls:
                assistant_msg["tool_calls"].append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"]
                    }
                })
            messages.append(assistant_msg)
            
            # Then add tool results
            for tr in tool_results:
                messages.append(tr)
            
            # Make second LLM call with tool results in context
            try:
                import time as time_module_2
                second_llm_start = time_module_2.time()
                system_prompt_with_time = get_cached_system_prompt(company_id=company_id)
                current_time = datetime.now()
                current_time_str = current_time.strftime('%I:%M %p on %A, %B %d, %Y')
                system_prompt_with_time += f"\n\n[CURRENT TIME: {current_time_str}]"
                
                full_messages = [{"role": "system", "content": system_prompt_with_time}] + messages
                
                # Create stream synchronously (same pattern as main LLM call)
                stream = client.chat.completions.create(
                    model=config.CHAT_MODEL,
                    messages=full_messages,
                    stream=True,
                    temperature=0.3,
                    **config.max_tokens_param(value=200)
                )
                
                second_response = ""
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        second_response += token
                        cleaned_token = token.replace('**', '').replace('__', '').replace('~~', '')
                        cleaned_token = format_for_tts_spelling(cleaned_token)
                        cleaned_token = humanize_times_for_tts(cleaned_token)
                        yield cleaned_token
                
                if second_response:
                    messages.append({"role": "assistant", "content": second_response.strip()})
                    print(f"   ✅ [SECOND_LLM] Response: '{second_response[:80]}...' ({time_module_2.time() - second_llm_start:.1f}s)")
                else:
                    fallback = "Could you give me a bit more detail on the issue so I can help you?"
                    yield fallback
                    messages.append({"role": "assistant", "content": fallback})
            except Exception as e:
                print(f"   ❌ [SECOND_LLM] Error: {e}")
                fallback = "Could you give me a bit more detail on the issue so I can help you?"
                yield fallback
                messages.append({"role": "assistant", "content": fallback})
            return
        
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


