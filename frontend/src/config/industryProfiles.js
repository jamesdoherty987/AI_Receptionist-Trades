/**
 * Industry Profiles — Frontend mirror of src/utils/industry_config.py
 *
 * This is the LOCAL fallback used before settings load from the API.
 * Once settings load, the backend-provided industry_profile takes precedence
 * (via IndustryContext). This file ensures the UI never flashes wrong labels.
 *
 * To add a new industry:
 *   1. Add an entry here
 *   2. Add a matching entry in src/utils/industry_config.py (backend)
 *   3. Create a prompt file in prompts/<key>_prompt.txt
 */

const industryProfiles = {
  trades: {
    label: 'Trades & Home Services',
    terminology: {
      job: 'Job',
      jobs: 'Jobs',
      employee: 'Employee',
      employees: 'Employees',
      client: 'Customer',
      clients: 'Customers',
      service: 'Service',
      booking: 'Booking',
    },
    features: {
      materials: true,
      callouts: true,
      quotes: true,
      emergencyJobs: true,
      propertyType: true,
      jobAddress: true,
      jobPhotos: true,
      multiDayJobs: true,
    },
    tabs: {
      jobs: true,
      calls: true,
      calendar: true,
      employees: true,
      crm: true,
      services: true,
      inventory: true,
      finances: true,
      insights: true,
    },
    icons: {
      employee: 'fas fa-hard-hat',
      job: 'fas fa-briefcase',
    },
    onboarding: {
      employeeIcon: 'fa-hard-hat',
      employeeLabel: 'Add Employees',
      showMaterialsStep: true,
      companyContextPlaceholder: 'Examples:\n- Free parking available behind the building\n- Family-run business since 2005\n- All technicians are fully insured\n- 12-month warranty on all work',
    },
  },

  salon: {
    label: 'Salon & Barbershop',
    terminology: {
      job: 'Appointment',
      jobs: 'Appointments',
      employee: 'Stylist',
      employees: 'Stylists',
      client: 'Client',
      clients: 'Clients',
      service: 'Service',
      booking: 'Appointment',
    },
    features: {
      materials: true,
      callouts: false,
      quotes: false,
      emergencyJobs: false,
      propertyType: false,
      jobAddress: false,
      jobPhotos: false,
      multiDayJobs: false,
    },
    tabs: {
      jobs: true,
      calls: true,
      calendar: true,
      employees: true,
      crm: true,
      services: true,
      inventory: true,
      finances: true,
      insights: true,
    },
    icons: {
      employee: 'fas fa-user-tie',
      job: 'fas fa-calendar-check',
    },
    onboarding: {
      employeeIcon: 'fa-user-tie',
      employeeLabel: 'Add Stylists',
      showMaterialsStep: true,
      companyContextPlaceholder: 'Examples:\n- Walk-ins welcome\n- Free WiFi and complimentary drinks\n- Specialising in colour and balayage\n- Late opening Thursdays until 9pm',
    },
  },

  cleaning: {
    label: 'Cleaning Services',
    terminology: {
      job: 'Job',
      jobs: 'Jobs',
      employee: 'Cleaner',
      employees: 'Cleaners',
      client: 'Customer',
      clients: 'Customers',
      service: 'Service',
      booking: 'Booking',
    },
    features: {
      materials: true,
      callouts: false,
      quotes: true,
      emergencyJobs: false,
      propertyType: true,
      jobAddress: true,
      jobPhotos: false,
      multiDayJobs: false,
    },
    tabs: {
      jobs: true,
      calls: true,
      calendar: true,
      employees: true,
      crm: true,
      services: true,
      inventory: true,
      finances: true,
      insights: true,
    },
    icons: {
      employee: 'fas fa-broom',
      job: 'fas fa-briefcase',
    },
    onboarding: {
      employeeIcon: 'fa-broom',
      employeeLabel: 'Add Cleaners',
      showMaterialsStep: true,
      companyContextPlaceholder: 'Examples:\n- Eco-friendly products used\n- All staff are Garda vetted\n- We bring all our own supplies\n- End-of-tenancy deep cleans available',
    },
  },

  restaurant: {
    label: 'Restaurant & Caf\u00e9',
    terminology: {
      job: 'Reservation',
      jobs: 'Reservations',
      employee: 'Server',
      employees: 'Staff',
      client: 'Guest',
      clients: 'Guests',
      service: 'Service',
      booking: 'Reservation',
    },
    features: {
      materials: true,
      callouts: false,
      quotes: false,
      emergencyJobs: false,
      propertyType: false,
      jobAddress: false,
      jobPhotos: false,
      multiDayJobs: false,
    },
    tabs: {
      jobs: true,
      calls: true,
      calendar: true,
      employees: true,
      crm: true,
      services: true,
      inventory: true,
      finances: true,
      insights: true,
    },
    icons: {
      employee: 'fas fa-utensils',
      job: 'fas fa-calendar-check',
    },
    onboarding: {
      employeeIcon: 'fa-utensils',
      employeeLabel: 'Add Staff',
      showMaterialsStep: true,
      companyContextPlaceholder: 'Examples:\n- Outdoor seating available\n- Vegetarian and vegan options\n- Private dining room for events\n- Free parking on site',
    },
  },
};

export default industryProfiles;
