"""
Industry Configuration — Single source of truth for industry-specific behaviour.

To add a new industry:
1. Add an entry to INDUSTRY_PROFILES below
2. Create a matching prompt file in prompts/<industry_type>_prompt.txt
3. Add a matching entry in frontend/src/config/industryProfiles.js

That's it. Everything else reads from these configs.
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

INDUSTRY_PROFILES = {
    'trades': {
        'label': 'Trades & Home Services',
        'prompt_file': 'trades_prompt.txt',
        'terminology': {
            'job': 'Job',
            'jobs': 'Jobs',
            'worker': 'Worker',
            'workers': 'Workers',
            'client': 'Customer',
            'clients': 'Customers',
            'service': 'Service',
            'booking': 'Booking',
        },
        'features': {
            'materials': True,
            'callouts': True,
            'quotes': True,
            'emergency_jobs': True,
            'property_type': True,
            'job_address': True,       # Collect address/eircode per booking
            'job_photos': True,
            'multi_day_jobs': True,
        },
        'booking': {
            'collect_address': True,
            'collect_property_type': True,
            'default_urgency': 'scheduled',
            'urgency_options': ['scheduled', 'same-day', 'quote', 'emergency'],
        },
        'onboarding': {
            'worker_icon': 'fa-hard-hat',
            'worker_label': 'Add Workers',
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
        'terminology': {
            'job': 'Appointment',
            'jobs': 'Appointments',
            'worker': 'Stylist',
            'workers': 'Stylists',
            'client': 'Client',
            'clients': 'Clients',
            'service': 'Service',
            'booking': 'Appointment',
        },
        'features': {
            'materials': False,
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
        'onboarding': {
            'worker_icon': 'fa-user-tie',
            'worker_label': 'Add Stylists',
            'show_materials_step': False,
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
        'terminology': {
            'job': 'Job',
            'jobs': 'Jobs',
            'worker': 'Cleaner',
            'workers': 'Cleaners',
            'client': 'Customer',
            'clients': 'Customers',
            'service': 'Service',
            'booking': 'Booking',
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
        'onboarding': {
            'worker_icon': 'fa-broom',
            'worker_label': 'Add Cleaners',
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
        'terminology': {
            'job': 'Reservation',
            'jobs': 'Reservations',
            'worker': 'Server',
            'workers': 'Staff',
            'client': 'Guest',
            'clients': 'Guests',
            'service': 'Service',
            'booking': 'Reservation',
        },
        'features': {
            'materials': False,
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
        'onboarding': {
            'worker_icon': 'fa-utensils',
            'worker_label': 'Add Staff',
            'show_materials_step': False,
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
