# Adding a New Industry

The app is built around a per-industry configuration system. To add a new industry (e.g. dental clinic, auto repair, pet grooming), follow these 3 steps.

## Step 1 — Backend Config

Edit `src/utils/industry_config.py`. Add an entry to `INDUSTRY_PROFILES`:

```python
'dental': {
    'label': 'Dental Clinic',
    'prompt_file': 'dental_prompt.txt',
    'filler_keywords': {
        'service_description': ["toothache", "filling", "crown", "extraction", ...],
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
        'employee': 'Dentist',
        'employees': 'Dentists',
        'client': 'Patient',
        'clients': 'Patients',
        'service': 'Treatment',
        'booking': 'Appointment',
        'servicesTab': 'Treatments',
        'inventoryTab': 'Supplies',
        'financesTab': 'Finances',
        'insightsTab': 'Insights',
        'calendarTab': 'Calendar',
        'callsTab': 'Calls',
        'crmTab': 'Patients',
        # Status / action labels used in UI
        'statusBusy': 'With Patient',
        'statusAvailable': 'Available',
        'startAction': 'Start Appointment',
        'completeAction': 'Mark Complete',
        'inProgressLabel': 'In Progress',
    },
    'features': {
        'materials': False,
        'callouts': False,
        'quotes': False,
        'emergency_jobs': True,   # Dental emergencies happen
        'property_type': False,
        'job_address': False,     # Patient comes to clinic
        'job_photos': True,        # X-rays, before/after
        'multi_day_jobs': False,
    },
    'booking': {
        'collect_address': False,
        'collect_property_type': False,
        'default_urgency': 'scheduled',
        'urgency_options': ['scheduled', 'emergency'],
    },
    # Status workflow — controls board columns and status picker
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
        'show_batch_number': False,
        'show_location': True,
        'location_label': 'Storage',
    },
    'onboarding': {
        'employee_icon': 'fa-tooth',
        'employee_label': 'Add Dentists',
        'show_materials_step': False,
        'company_context_placeholder': (
            "Examples:\n"
            "- Accepting new patients\n"
            "- Emergency appointments available\n"
            "- Invisalign certified\n"
            "- Medical card accepted"
        ),
    },
},
```

## Step 2 — Frontend Config

Edit `frontend/src/config/industryProfiles.js`. Add a matching entry with the same keys (camelCase for features):

```javascript
dental: {
  label: 'Dental Clinic',
  terminology: {
    job: 'Appointment', jobs: 'Appointments', employee: 'Dentist', employees: 'Dentists',
    client: 'Patient', clients: 'Patients', service: 'Treatment', booking: 'Appointment',
    servicesTab: 'Treatments', inventoryTab: 'Supplies', financesTab: 'Finances',
    insightsTab: 'Insights', calendarTab: 'Calendar', callsTab: 'Calls', crmTab: 'Patients',
    statusBusy: 'With Patient', statusAvailable: 'Available',
    startAction: 'Start Appointment', completeAction: 'Mark Complete', inProgressLabel: 'In Progress',
  },
  features: {
    materials: false, callouts: false, quotes: false, emergencyJobs: true,
    propertyType: false, jobAddress: false, jobPhotos: true, multiDayJobs: false,
  },
  tabs: {
    jobs: true, calls: true, calendar: true, employees: true, crm: true,
    services: true, inventory: false, finances: true, insights: true,
  },
  icons: { employee: 'fas fa-tooth', job: 'fas fa-calendar-check' },
  statusWorkflow: [
    { key: 'pending', label: 'New', color: '#f59e0b', icon: 'fa-clock' },
    { key: 'scheduled', label: 'Scheduled', color: '#6366f1', icon: 'fa-calendar-check' },
    { key: 'in-progress', label: 'In Progress', color: '#8b5cf6', icon: 'fa-tooth' },
    { key: 'completed', label: 'Completed', color: '#22c55e', icon: 'fa-check-circle' },
  ],
  serviceConfig: { /* ... industry-specific service form config ... */ },
  inventory: { /* ... industry-specific inventory config ... */ },
  onboarding: {
    employeeIcon: 'fa-tooth', employeeLabel: 'Add Dentists', showMaterialsStep: false,
    companyContextPlaceholder: "Examples:\n- Accepting new patients\n- Emergency appointments available\n...",
  },
},
```

## Step 3 — AI Prompt

Create `prompts/dental_prompt.txt`. Copy `trades_prompt.txt` as a starting point and adapt:
- Change greeting and tone
- Remove callout/quote references
- Remove address collection logic (patients come to the clinic)
- Adapt for your industry's booking flow

## Step 4 — Done

That's literally it. A business owner can now pick "Dental Clinic" from the Industry dropdown in Settings. The UI tabs, AI prompt, terminology, and onboarding all adapt automatically.

## Architecture Reference

### What's configurable per industry

| Config Key | Where Used | Example |
|---|---|---|
| `terminology.*` | All UI labels (tabs, buttons, headings) | `job: 'Reservation'` |
| `terminology.statusBusy` | Employee status badge | `'Working'` vs `'On Job'` |
| `terminology.startAction` | Employee dashboard start button | `'Start Shift'` vs `'Start Job'` |
| `terminology.completeAction` | Employee dashboard complete button | `'End Shift'` vs `'Mark Complete'` |
| `terminology.inProgressLabel` | In-progress section header | `'Working'` vs `'In Progress'` |
| `features.*` | Feature gates (callouts, quotes, etc.) | `callouts: false` |
| `tabs.*` | Tab visibility in dashboard | `crm: false` |
| `statusWorkflow` | Board columns & status picker | `[{key:'pending',label:'New'}, ...]` |
| `filler_keywords.*` | AI phone call intent detection | `['table', 'reservation', ...]` |
| `address_capture` | Whether to capture caller address audio | `enabled: false` |
| `serviceConfig.*` | Service form field visibility & labels | `showCapacity: true` |
| `inventory.*` | Inventory categories, units, fields | `categories: ['Proteins', ...]` |
| `onboarding.*` | Setup wizard customisation | `employeeLabel: 'Add Staff'` |
| `booking.*` | Booking flow (address, urgency) | `collect_address: false` |

### Where industry affects behaviour

**Backend:**
- `src/services/llm_stream.py` → `load_system_prompt()` picks prompt file based on `industry_type`
- `src/services/calendar_tools.py` → `book_job` skips address validation when `features.job_address == False`
- `src/handlers/media_handler.py` → sets `call_state.industry_type` at call start

**Frontend:**
- `frontend/src/context/IndustryContext.jsx` → provides `useIndustry()` hook
- `frontend/src/pages/Dashboard.jsx` → tab labels and visibility
- `frontend/src/components/dashboard/*.jsx` → tab component labels
- `frontend/src/components/modals/AddJobModal.jsx` → feature gates for callouts/quotes/emergency
- `frontend/src/components/dashboard/OnboardingWizard.jsx` → employee label, materials step visibility
- `frontend/src/pages/CustomerPortal.jsx` → uses data from portal API directly
- `frontend/src/pages/EmployeeDashboard.jsx` → uses industry from employee auth endpoint

### Data flow for customer portal

The customer portal is different from admin/employee UIs — it's public, token-based, and can't use the AuthContext.
The portal API (`GET /api/portal/<token>`) returns `industry_type` and `industry_profile` directly in the response,
and `CustomerPortal.jsx` reads them from `data` instead of using the `useIndustry()` hook.

### Database

`companies.industry_type` stores the active industry (default: `'trades'`). See `db_scripts/add_industry_type_column.py` for the migration.

### Fallback behaviour

If the industry-specific prompt file doesn't exist yet, the backend falls back to `trades_prompt.txt` automatically — nothing breaks.
Same for any missing frontend config keys — they default to the `trades` profile.
