# Services Menu & Business Hours Configuration

## Overview

The AI Receptionist now supports dynamic configuration of business hours and services/menu through a user-friendly settings interface. No need to edit `.env` files or restart the application!

## Features

### 1. **Business Hours Management**
- Configure opening and closing hours (24-hour format)
- Select which days of the week you're open
- Set timezone
- Add custom notes (e.g., "Emergency callouts available 24/7")

### 2. **Services Menu Management**
- Add/Edit/Delete services offered
- Configure for each service:
  - Service name and category
  - Description
  - Duration (in minutes)
  - Regular price
  - Emergency price (optional)
  - Active/Inactive status
- AI receptionist automatically uses this information when talking to callers

### 3. **Pricing & Policies**
- Configure callout fees
- Set hourly rates
- Payment methods
- Cancellation policies
- Warranty information

## How to Use

### Access the Settings

1. **From Dashboard**: Click the "🛠️ Services Menu" button in the header
2. **Direct URL**: Navigate to `/settings/menu`

### Configure Business Hours

1. Go to Services Menu Settings
2. In the "Business Hours" section:
   - Set start hour (e.g., 9 for 9:00 AM)
   - Set end hour (e.g., 17 for 5:00 PM)
   - Click days you're open (they will highlight in blue)
   - Select your timezone
   - Add any notes
3. Click "💾 Save Business Hours"

**Default**: Monday-Friday, 9:00 AM - 5:00 PM

### Manage Services

#### Add a New Service
1. Click "➕ Add New Service" button
2. Fill in the form:
   - **Service Name**: e.g., "Plumbing Leak Repair"
   - **Category**: e.g., "Plumbing"
   - **Description**: What the service includes
   - **Duration**: Time needed in minutes
   - **Price**: Regular price in euros
   - **Emergency Price**: Optional higher price for urgent work
   - **Status**: Active or Inactive
3. Click "Save Service"

#### Edit a Service
1. Find the service in the table
2. Click "Edit" button
3. Modify the details
4. Click "Save Service"

#### Delete a Service
1. Find the service in the table
2. Click "Delete" button
3. Confirm deletion

## File Structure

### Configuration Files

**`config/services_menu.json`**
- Stores all business hours and services
- Automatically updated when you make changes in the UI
- JSON format for easy backup/restore

**`config/business_info.json`**
- General business information (name, contact, location)
- Still used for company details

### Database

**`data/receptionist.db`**
- Settings history (tracks who changed what and when)
- Business and developer settings

## AI Integration

The AI receptionist automatically:
- ✅ Reads business hours to inform callers when you're open/closed
- ✅ Quotes prices from your services menu
- ✅ Describes available services accurately
- ✅ Mentions emergency pricing when applicable
- ✅ Informs about payment methods and policies

**No restart required!** The AI loads the latest information from the config files.

## Backward Compatibility

The system still respects `.env` file settings as fallbacks:
```env
BUSINESS_HOURS_START=9
BUSINESS_HOURS_END=17
```

**Priority**: Services Menu JSON > .env file

## API Endpoints

For developers or integrations:

- `GET /api/services/menu` - Get full services menu
- `POST /api/services/menu` - Update entire menu
- `POST /api/services/menu/service` - Add new service
- `PUT /api/services/menu/service/<id>` - Update service
- `DELETE /api/services/menu/service/<id>` - Delete service
- `GET /api/services/business-hours` - Get business hours
- `POST /api/services/business-hours` - Update business hours

## Example Services Menu

Here's an example of services configured for a trade business:

| Service | Category | Duration | Price | Emergency |
|---------|----------|----------|-------|-----------|
| Leak Repairs | Plumbing | 60 min | €80 | €150 |
| Electrical Wiring | Electrical | 120 min | €100 | €180 |
| Boiler Service | Heating | 90 min | €95 | €170 |
| Door Installation | Carpentry | 90 min | €85 | - |
| Interior Painting | Painting | 240 min | €200 | - |
| General Handyman | Maintenance | 60 min | €60 | €110 |

## Tips

1. **Keep services active/inactive**: Deactivate seasonal services instead of deleting them
2. **Emergency pricing**: Set emergency prices 1.5-2x regular price
3. **Duration accuracy**: Be realistic with durations for better scheduling
4. **Clear descriptions**: Help the AI explain services better to callers
5. **Regular updates**: Review and update prices quarterly

## Troubleshooting

**Q: Changes don't appear in AI responses?**
A: The system should load changes immediately. If not, check the console for errors.

**Q: Can I edit the JSON file directly?**
A: Yes, but use the UI when possible for validation and history tracking.

**Q: How do I backup my services?**
A: Copy `config/services_menu.json` to a safe location.

**Q: Can I import services from another location?**
A: Yes, replace `config/services_menu.json` with your backup file.

## Future Enhancements

- Import/Export services to Excel/CSV
- Service categories management
- Multiple pricing tiers
- Seasonal schedules
- Holiday management
- Service duration estimation based on history

---

**Need help?** Check the main dashboard or contact support.
