"""
Industry Configuration — Single source of truth for industry-specific behaviour.

To add a new industry:
1. Add an entry to INDUSTRY_PROFILES below
2. Create a matching prompt file in prompts/<industry_type>_prompt.txt
3. Add a matching entry in frontend/src/config/industryProfiles.js

That's it. Everything else reads from these configs.

The filler_keywords section controls the filler pre-check in llm_stream.py.
Each key maps to a list of phrases that trigger a specific intent detection.
The guard logic (negative guards, context checks) is universal and stays in llm_stream.py.
Only the keyword lists themselves are industry-specific.

The address_capture section controls whether the media_handler captures
caller audio when the AI asks for an address/eircode. Industries that don't
collect addresses (salon, restaurant) should set enabled: False.
"""

# ─── Default industry when none is set ───────────────────────────────────────
DEFAULT_INDUSTRY = 'trades'

# ─── Industry Profiles ───────────────────────────────────────────────────────
# Each profile defines:
#   prompt_file       – which prompt file to load from prompts/
#   terminology       – label overrides for the UI and AI prompt
#   features          – boolean flags for optional feature areas
#   booking           – booking-flow configuration
#   onboarding        – wizard step customisation
#   inventory         – inventory tab configuration (categories, field visibility)

INDUSTRY_PROFILES = {
    'trades': {
        'label': 'Trades & Home Services',
        'prompt_file': 'trades_prompt.txt',
        # ── Filler pre-check keywords (llm_stream.py) ────────────────────
        # These trigger pre-recorded filler audio while the LLM processes.
        # Only the keyword lists are industry-specific; guard logic is universal.
        'filler_keywords': {
            # SERVICE_DESCRIPTION — caller describes their issue → match_issue tool
            'service_description': [
                "leak", "broken", "fix", "repair", "build",
                "burst", "blocked", "crack", "damage", "flood", "drip",
                "issue", "problem", "need help", "need to get", "need someone",
                "something wrong",
                "plumber", "plumbing", "electrician", "carpenter", "painter", "roofer",
                "heating", "boiler", "radiator", "toilet", "shower", "tap", "pipe",
                "come out", "call out", "callout",
            ],
            # BOOKING_INTENT — caller wants to book (no filler, LLM gathers details)
            'booking_intent': ["book", "appointment", "schedule"],
            # ADDRESS_ASK — phrases the AI uses when asking for an address
            # (used by filler pre-check for ADDRESS_PROVIDED detection)
            'address_ask': [
                "full address", "your address", "eircode", "eir code",
                "where is the property", "where's the property",
                "where is the job", "where's the job",
            ],
            # ADDRESS_CONFIRMATION — phrases indicating AI is confirming a stored address
            'address_confirmation': [
                "same address", "still your address", "your address", "still at",
                "at the same", "same location", "same place", "address as before",
                "address on file", "correct address", "the correct address",
            ],
        },
        # ── Address audio capture (media_handler.py) ─────────────────────
        'address_capture': {
            'enabled': True,
            'ask_keywords': [
                'address', 'eircode', 'eir code', 'location', 'where',
                'job site', 'job location', 'work location',
            ],
            'confirm_patterns': [
                'confirm', 'correct?', 'right?', 'is it', 'is that',
                'so the address is', 'booked in for', 'booked for',
                'job at', 'job for', 'i have your address', 'i have the address',
                'your address is', 'your address as', 'the address as',
                'address on file', 'address we have', 'same address',
                'still the same address', 'same address as before',
                'address as before', 'address still', 'email address',
            ],
        },
        'terminology': {
            'job': 'Job',
            'jobs': 'Jobs',
            'employee': 'Employee',
            'employees': 'Employees',
            'client': 'Customer',
            'clients': 'Customers',
            'service': 'Service',
            'services': 'Services',
            'booking': 'Booking',
            'servicesTab': 'Services',
            'inventoryTab': 'Inventory',
            'financesTab': 'Finances',
            'insightsTab': 'Insights',
            'calendarTab': 'Calendar',
            'callsTab': 'Calls',
            'crmTab': 'CRM',
            # Status / action labels used in UI
            'statusBusy': 'On Job',
            'statusAvailable': 'Available',
            'startAction': 'Start Job',
            'completeAction': 'Mark Complete',
            'inProgressLabel': 'In Progress',
        },
        'features': {
            'materials': True,
            'callouts': True,
            'quotes': True,
            'emergency_jobs': True,
            'property_type': True,
            'job_address': True,
            'job_photos': True,
            'multi_day_jobs': True,
        },
        'booking': {
            'collect_address': True,
            'collect_property_type': True,
            'default_urgency': 'scheduled',
            'urgency_options': ['scheduled', 'same-day', 'quote', 'emergency'],
        },
        # ── Status workflow (board columns & status options) ─────────
        'status_workflow': [
            {'key': 'pending', 'label': 'New'},
            {'key': 'quote_sent', 'label': 'Quote Sent'},
            {'key': 'quote_accepted', 'label': 'Quote Accepted'},
            {'key': 'scheduled', 'label': 'Scheduled'},
            {'key': 'in-progress', 'label': 'In Progress'},
            {'key': 'completed', 'label': 'Completed'},
        ],
        'service_config': {
            'show_category': True,
            'show_tags': True,
            'show_capacity': False,
            'show_area': False,
            'show_deposit': True,
            'show_warranty': True,
            'show_seasonal': True,
            'show_ai_notes': True,
            'show_follow_up': True,
        },
        'inventory': {
            'show_cost_price': True,
            'show_expiry': False,
            'show_batch_number': False,
            'show_location': True,
            'location_label': 'Location',
        },
        'onboarding': {
            'employee_icon': 'fa-hard-hat',
            'employee_label': 'Add Employees',
            'show_materials_step': True,
            'company_context_placeholder': (
                "Examples:\n"
                "- Free parking available behind the building\n"
                "- Family-run business since 2005\n"
                "- All technicians are fully insured\n"
                "- 12-month warranty on all work"
            ),
        },
    },

    'salon': {
        'label': 'Salon & Barbershop',
        'prompt_file': 'salon_prompt.txt',
        'filler_keywords': {
            'service_description': [
                "haircut", "cut", "trim", "colour", "color", "dye", "highlights",
                "balayage", "blowdry", "blow dry", "blowout", "blow out",
                "shave", "beard", "fade", "perm", "straighten", "keratin",
                "extensions", "braids", "updo", "style", "restyle",
                "roots", "toner", "treatment", "deep condition",
                "appointment", "need help", "something wrong",
            ],
            'booking_intent': ["book", "appointment", "schedule"],
            'address_ask': [],
            'address_confirmation': [],
        },
        'address_capture': {
            'enabled': False,
            'ask_keywords': [],
            'confirm_patterns': [],
        },
        'terminology': {
            'job': 'Appointment',
            'jobs': 'Appointments',
            'employee': 'Stylist',
            'employees': 'Stylists',
            'client': 'Client',
            'clients': 'Clients',
            'service': 'Service',
            'services': 'Services',
            'booking': 'Appointment',
            'servicesTab': 'Services',
            'inventoryTab': 'Products',
            'financesTab': 'Finances',
            'insightsTab': 'Insights',
            'calendarTab': 'Calendar',
            'callsTab': 'Calls',
            'crmTab': 'CRM',
            'statusBusy': 'With Client',
            'statusAvailable': 'Available',
            'startAction': 'Start Appointment',
            'completeAction': 'Mark Complete',
            'inProgressLabel': 'In Progress',
        },
        'features': {
            'materials': True,
            'callouts': False,
            'quotes': False,
            'emergency_jobs': False,
            'property_type': False,
            'job_address': False,
            'job_photos': False,
            'multi_day_jobs': False,
        },
        'booking': {
            'collect_address': False,
            'collect_property_type': False,
            'default_urgency': 'scheduled',
            'urgency_options': ['scheduled'],
        },
        'status_workflow': [
            {'key': 'pending', 'label': 'New'},
            {'key': 'scheduled', 'label': 'Scheduled'},
            {'key': 'in-progress', 'label': 'In Progress'},
            {'key': 'completed', 'label': 'Completed'},
        ],
        'service_config': {
            'show_category': True,
            'show_tags': True,
            'show_capacity': False,
            'show_area': False,
            'show_deposit': True,
            'show_warranty': False,
            'show_seasonal': False,
            'show_ai_notes': True,
            'show_follow_up': True,
        },
        'inventory': {
            'show_cost_price': True,
            'show_expiry': True,
            'show_batch_number': True,
            'show_location': True,
            'location_label': 'Storage',
        },
        'onboarding': {
            'employee_icon': 'fa-user-tie',
            'employee_label': 'Add Stylists',
            'show_materials_step': True,
            'company_context_placeholder': (
                "Examples:\n"
                "- Walk-ins welcome\n"
                "- Free WiFi and complimentary drinks\n"
                "- Specialising in colour and balayage\n"
                "- Late opening Thursdays until 9pm"
            ),
        },
    },

    'cleaning': {
        'label': 'Cleaning Services',
        'prompt_file': 'cleaning_prompt.txt',
        'filler_keywords': {
            'service_description': [
                "clean", "cleaning", "deep clean", "spring clean", "end of tenancy",
                "move out", "move in", "carpet", "oven", "windows", "window cleaning",
                "pressure wash", "power wash", "hoover", "vacuum", "mop",
                "stain", "mould", "mold", "dust", "polish",
                "office clean", "commercial clean", "domestic clean",
                "need help", "need someone", "something wrong",
                "issue", "problem",
            ],
            'booking_intent': ["book", "appointment", "schedule"],
            'address_ask': [
                "full address", "your address", "eircode", "eir code",
                "where is the property", "where's the property",
            ],
            'address_confirmation': [
                "same address", "still your address", "your address", "still at",
                "at the same", "same location", "same place", "address as before",
                "address on file", "correct address", "the correct address",
            ],
        },
        'address_capture': {
            'enabled': True,
            'ask_keywords': [
                'address', 'eircode', 'eir code', 'location', 'where',
                'property',
            ],
            'confirm_patterns': [
                'confirm', 'correct?', 'right?', 'is it', 'is that',
                'so the address is', 'booked in for', 'booked for',
                'i have your address', 'i have the address',
                'your address is', 'your address as', 'the address as',
                'address on file', 'address we have', 'same address',
                'still the same address', 'same address as before',
                'address as before', 'address still', 'email address',
            ],
        },
        'terminology': {
            'job': 'Job',
            'jobs': 'Jobs',
            'employee': 'Cleaner',
            'employees': 'Cleaners',
            'client': 'Customer',
            'clients': 'Customers',
            'service': 'Service',
            'services': 'Services',
            'booking': 'Booking',
            'servicesTab': 'Services',
            'inventoryTab': 'Supplies',
            'financesTab': 'Finances',
            'insightsTab': 'Insights',
            'calendarTab': 'Calendar',
            'callsTab': 'Calls',
            'crmTab': 'CRM',
            'statusBusy': 'On Job',
            'statusAvailable': 'Available',
            'startAction': 'Start Job',
            'completeAction': 'Mark Complete',
            'inProgressLabel': 'In Progress',
        },
        'features': {
            'materials': True,
            'callouts': False,
            'quotes': True,
            'emergency_jobs': False,
            'property_type': True,
            'job_address': True,
            'job_photos': False,
            'multi_day_jobs': False,
        },
        'booking': {
            'collect_address': True,
            'collect_property_type': True,
            'default_urgency': 'scheduled',
            'urgency_options': ['scheduled', 'quote'],
        },
        'status_workflow': [
            {'key': 'pending', 'label': 'New'},
            {'key': 'quote_sent', 'label': 'Quote Sent'},
            {'key': 'quote_accepted', 'label': 'Quote Accepted'},
            {'key': 'scheduled', 'label': 'Scheduled'},
            {'key': 'in-progress', 'label': 'In Progress'},
            {'key': 'completed', 'label': 'Completed'},
        ],
        'service_config': {
            'show_category': True,
            'show_tags': True,
            'show_capacity': False,
            'show_area': False,
            'show_deposit': True,
            'show_warranty': False,
            'show_seasonal': True,
            'show_ai_notes': True,
            'show_follow_up': True,
        },
        'inventory': {
            'show_cost_price': True,
            'show_expiry': False,
            'show_batch_number': False,
            'show_location': True,
            'location_label': 'Location',
        },
        'onboarding': {
            'employee_icon': 'fa-broom',
            'employee_label': 'Add Cleaners',
            'show_materials_step': True,
            'company_context_placeholder': (
                "Examples:\n"
                "- Eco-friendly products used\n"
                "- All staff are Garda vetted\n"
                "- We bring all our own supplies\n"
                "- End-of-tenancy deep cleans available"
            ),
        },
    },

    'restaurant': {
        'label': 'Restaurant & Café',
        'prompt_file': 'restaurant_prompt.txt',
        'filler_keywords': {
            'service_description': [
                "table", "reservation", "party of", "table for",
                "birthday", "anniversary", "celebration", "event",
                "private dining", "private room", "function",
                "large group", "group booking", "set menu",
                "dietary", "allergy", "allergies", "vegetarian", "vegan",
                "gluten free", "coeliac", "celiac",
                "high chair", "wheelchair", "accessible",
                "takeaway", "take away", "collection", "order",
                "need help", "something wrong", "issue", "problem",
            ],
            'booking_intent': ["book", "reserve", "reservation", "table"],
            'address_ask': [],
            'address_confirmation': [],
        },
        'address_capture': {
            'enabled': False,
            'ask_keywords': [],
            'confirm_patterns': [],
        },
        'terminology': {
            'job': 'Reservation',
            'jobs': 'Reservations',
            'employee': 'Server',
            'employees': 'Staff',
            'client': 'Guest',
            'clients': 'Guests',
            'service': 'Menu Item',
            'services': 'Menu',
            'booking': 'Reservation',
            'servicesTab': 'Menu',
            'inventoryTab': 'Stock',
            'financesTab': 'Finances',
            'insightsTab': 'Insights',
            'calendarTab': 'Reservations',
            'callsTab': 'Calls',
            'crmTab': 'Guests',
            'statusBusy': 'Working',
            'statusAvailable': 'Available',
            'startAction': 'Start Shift',
            'completeAction': 'End Shift',
            'inProgressLabel': 'Working',
        },
        'features': {
            'materials': True,
            'callouts': False,
            'quotes': False,
            'emergency_jobs': False,
            'property_type': False,
            'job_address': False,
            'job_photos': False,
            'multi_day_jobs': False,
            'menu_designer': True,
            'table_management': True,
            'online_ordering': True,
        },
        'booking': {
            'collect_address': False,
            'collect_property_type': False,
            'default_urgency': 'scheduled',
            'urgency_options': ['scheduled'],
        },
        'status_workflow': [
            {'key': 'pending', 'label': 'New'},
            {'key': 'scheduled', 'label': 'Confirmed'},
            {'key': 'in-progress', 'label': 'Seated'},
            {'key': 'completed', 'label': 'Completed'},
        ],
        'service_config': {
            'show_category': True,
            'show_tags': True,
            'show_capacity': True,
            'show_area': True,
            'show_deposit': True,
            'show_warranty': False,
            'show_seasonal': True,
            'show_ai_notes': True,
            'show_follow_up': False,
        },
        'inventory': {
            'show_cost_price': True,
            'show_expiry': True,
            'show_batch_number': True,
            'show_location': True,
            'location_label': 'Storage',
        },
        'onboarding': {
            'employee_icon': 'fa-utensils',
            'employee_label': 'Add Staff',
            'show_materials_step': True,
            'company_context_placeholder': (
                "Examples:\n"
                "- Outdoor seating available\n"
                "- Vegetarian and vegan options\n"
                "- Private dining room for events\n"
                "- Free parking on site"
            ),
        },
    },
}


def get_industry_profile(industry_type: str = None) -> dict:
    """Get the full profile for an industry. Falls back to DEFAULT_INDUSTRY."""
    key = industry_type if industry_type in INDUSTRY_PROFILES else DEFAULT_INDUSTRY
    return INDUSTRY_PROFILES[key]


def get_prompt_file(industry_type: str = None) -> str:
    """Get the prompt filename for an industry."""
    profile = get_industry_profile(industry_type)
    return profile['prompt_file']


def get_terminology(industry_type: str = None) -> dict:
    """Get the terminology map for an industry."""
    profile = get_industry_profile(industry_type)
    return profile['terminology']


def get_features(industry_type: str = None) -> dict:
    """Get the feature flags for an industry."""
    profile = get_industry_profile(industry_type)
    return profile['features']


def get_available_industries() -> list:
    """Return list of available industries for UI dropdowns."""
    return [
        {'value': key, 'label': profile['label']}
        for key, profile in INDUSTRY_PROFILES.items()
    ]


def get_filler_keywords(industry_type: str = None) -> dict:
    """Get the filler keyword lists for an industry.
    
    Returns a dict with keys like 'service_description', 'booking_intent', etc.
    Each value is a list of phrases that trigger that intent.
    Falls back to DEFAULT_INDUSTRY if industry_type is unknown.
    """
    profile = get_industry_profile(industry_type)
    return profile.get('filler_keywords', INDUSTRY_PROFILES[DEFAULT_INDUSTRY]['filler_keywords'])


def get_address_capture_config(industry_type: str = None) -> dict:
    """Get the address audio capture config for an industry.
    
    Returns a dict with 'enabled', 'ask_keywords', and 'confirm_patterns'.
    Falls back to DEFAULT_INDUSTRY if industry_type is unknown.
    """
    profile = get_industry_profile(industry_type)
    return profile.get('address_capture', INDUSTRY_PROFILES[DEFAULT_INDUSTRY]['address_capture'])


def get_status_workflow(industry_type: str = None) -> list:
    """Get the status workflow (board columns) for an industry.
    
    Returns a list of dicts with 'key' and 'label'.
    Falls back to DEFAULT_INDUSTRY if industry_type is unknown.
    """
    profile = get_industry_profile(industry_type)
    return profile.get('status_workflow', INDUSTRY_PROFILES[DEFAULT_INDUSTRY]['status_workflow'])
