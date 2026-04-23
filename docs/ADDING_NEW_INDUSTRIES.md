# Adding a New Industry

The app is built around a per-industry configuration system. To add a new industry (e.g. dental clinic, auto repair, pet grooming), follow these 3 steps.

## Step 1 — Backend Config

Edit `src/utils/industry_config.py`. Add an entry to `INDUSTRY_PROFILES`:

```python
'dental': {
    'label': 'Dental Clinic',
    'prompt_file': 'dental_prompt.txt',
    'terminology': {
        'job': 'Appointment',
        'jobs': 'Appointments',
        'worker': 'Dentist',
        'workers': 'Dentists',
        'client': 'Patient',
        'clients': 'Patients',
        'service': 'Treatment',
        'booking': 'Appointment',
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
    'onboarding': {
        'worker_icon': 'fa-tooth',
        'worker_label': 'Add Dentists',
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
  terminology: { job: 'Appointment', jobs: 'Appointments', worker: 'Dentist', workers: 'Dentists', client: 'Patient', clients: 'Patients', service: 'Treatment', booking: 'Appointment' },
  features: {
    materials: false,
    callouts: false,
    quotes: false,
    emergencyJobs: true,
    propertyType: false,
    jobAddress: false,
    jobPhotos: true,
    multiDayJobs: false,
  },
  tabs: {
    jobs: true, calls: true, calendar: true, workers: true, crm: true,
    services: true, materials: false, finances: true, insights: true,
  },
  icons: {
    worker: 'fas fa-tooth',
    job: 'fas fa-calendar-check',
  },
  onboarding: {
    workerIcon: 'fa-tooth',
    workerLabel: 'Add Dentists',
    showMaterialsStep: false,
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
- `frontend/src/components/dashboard/OnboardingWizard.jsx` → worker label, materials step visibility
- `frontend/src/pages/CustomerPortal.jsx` → uses data from portal API directly
- `frontend/src/pages/WorkerDashboard.jsx` → uses industry from worker auth endpoint

### Data flow for customer portal

The customer portal is different from admin/worker UIs — it's public, token-based, and can't use the AuthContext.
The portal API (`GET /api/portal/<token>`) returns `industry_type` and `industry_profile` directly in the response,
and `CustomerPortal.jsx` reads them from `data` instead of using the `useIndustry()` hook.

### Database

`companies.industry_type` stores the active industry (default: `'trades'`). See `db_scripts/add_industry_type_column.py` for the migration.

### Fallback behaviour

If the industry-specific prompt file doesn't exist yet, the backend falls back to `trades_prompt.txt` automatically — nothing breaks.
Same for any missing frontend config keys — they default to the `trades` profile.
