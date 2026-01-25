# Quick Start: Configure Your Business

## First Time Setup

After installing and starting the AI Receptionist, follow these steps to configure your business:

### 1. Access the Dashboard
Navigate to: `http://localhost:5000/dashboard`

### 2. Configure Services & Pricing

Click **"🛠️ Services Menu"** button in the header

#### Set Business Hours
1. Enter your opening hour (e.g., 9 for 9 AM)
2. Enter your closing hour (e.g., 17 for 5 PM)
3. Click the days you're open (they turn blue when selected)
4. Click **"💾 Save Business Hours"**

**Default**: Monday-Friday, 9 AM - 5 PM

#### Add Your Services

Click **"+ Add New Service"** and fill in:

**Example: Plumbing Service**
- Service Name: `Leak Repairs`
- Category: `Plumbing`
- Description: `Fix leaking pipes, taps, toilets, radiators`
- Duration: `60` (minutes)
- Price: `80` (euros)
- Emergency Price: `150` (euros) - optional
- Status: `Active`

Click **"Save Service"**

Repeat for all your services!

#### Pre-configured Services
The system comes with example services for:
- Plumbing (leak repairs, installations)
- Electrical (wiring, fault-finding)
- Heating (boiler service, radiators)
- Carpentry (doors, general work)
- Painting (interior/exterior)
- General maintenance

**Edit or delete** these to match your actual offerings.

### 3. Test the AI

Call your Twilio number and the AI will:
- ✅ Greet callers with your business name
- ✅ Know your business hours
- ✅ Quote accurate prices from your services menu
- ✅ Describe available services
- ✅ Book appointments in your calendar

### 4. Optional: Customize Business Info

Go to **"⚙️ Settings"** to update:
- Business name
- Contact details
- Service area
- Payment methods
- Cancellation policy

## Common Tasks

### Add a New Service
1. Go to Services Menu (`/settings/menu`)
2. Click "Add New Service"
3. Fill in details
4. Click "Save"

**Done!** AI knows about it immediately.

### Update Prices
1. Go to Services Menu
2. Click "Edit" on the service
3. Update price
4. Click "Save"

### Change Business Hours
1. Go to Services Menu
2. Update hours and days
3. Click "Save Business Hours"

### Deactivate Seasonal Services
1. Find the service in the table
2. Click "Edit"
3. Change Status to "Inactive"
4. Click "Save"

**The AI won't mention inactive services to callers.**

## Tips for Success

### Pricing
- Set realistic prices based on your market
- Use emergency pricing for after-hours (typically 1.5-2x normal)
- Keep a minimum callout fee

### Durations
- Be realistic - helps with scheduling
- Include travel time if needed
- Round to 15-minute increments

### Descriptions
- Be specific about what's included
- Helps the AI explain clearly
- Mention any requirements (e.g., "materials not included")

### Categories
- Use consistent categories
- Makes it easier to manage
- Examples: Plumbing, Electrical, Heating, Carpentry, Painting, Maintenance

## Files to Know

- **`config/services_menu.json`** - Your services and hours
- **`config/business_info.json`** - Company details
- **`.env`** - API keys and settings

### Backup Your Configuration
```bash
# Copy your services configuration
cp config/services_menu.json config/services_menu.backup.json
```

## Next Steps

1. ✅ Configure services and hours
2. ✅ Test with a phone call
3. ✅ Review the dashboard
4. ✅ Set up email reminders (see `docs/REMINDERS.md`)
5. ✅ Customize business information

## Need Help?

- **Full Documentation**: `docs/SERVICES_MENU_SETTINGS.md`
- **Implementation Details**: `SERVICES_MENU_IMPLEMENTATION.md`
- **Main README**: `ReadMe.md`

---

**You're ready to go!** The AI receptionist will handle calls professionally using your configuration.
