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
#   inventory         – inventory tab configuration (categories, field visibility)

INDUSTRY_PROFILES = {
    'trades': {
        'label': 'Trades & Home Services',
        'prompt_file': 'trades_prompt.txt',
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
