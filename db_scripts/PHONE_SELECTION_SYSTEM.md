# Phone Number Selection System

## Overview

The phone number assignment system has been updated to allow users to **manually select** their phone number from an available pool, instead of automatic assignment.

## How It Works

### 1. **Signup Flow**
- User creates account with company info, email, password
- After successful signup, a **modal appears** showing available phone numbers
- User can:
  - **Select a number** from the list and confirm (permanent assignment)
  - **Skip** and configure later in Settings

### 2. **Settings Configuration**
- If user skipped during signup, they can configure their number in **Settings → Phone Configuration**
- The assigned number is displayed (read-only once assigned)
- Users **without** a number see a "Configure Phone" button

### 3. **Number Assignment Rules**
- ✅ Numbers are assigned **permanently** - cannot be changed once confirmed
- ✅ Only **available** numbers are shown in the selection list
- ✅ Once assigned, the number is marked as 'assigned' in database
- ✅ Incoming calls are routed by matching the phone number in database

## Technical Implementation

### Backend API Endpoints

#### `GET /api/phone-numbers/available`
Returns list of available phone numbers from the pool.

**Response:**
```json
{
  "success": true,
  "numbers": [
    {
      "phone_number": "+353123456789",
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

#### `POST /api/phone-numbers/assign`
Assigns a specific phone number to the current company.

**Request:**
```json
{
  "phone_number": "+353123456789"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Phone number assigned successfully",
  "phone_number": "+353123456789"
}
```

**Errors:**
- `400` - Phone number not available
- `400` - Company already has a phone number
- `401` - Not authenticated

#### `GET /api/phone-numbers/current`
Gets the current company's assigned phone number.

**Response:**
```json
{
  "success": true,
  "phone_number": "+353123456789",
  "has_phone": true
}
```

### Database Methods

Both SQLite (`Database`) and PostgreSQL (`PostgreSQLDatabaseWrapper`) have:

```python
def get_available_phone_numbers() -> List[Dict]:
    """Get list of all available phone numbers"""
    
def assign_phone_number(company_id: int, phone_number: str = None):
    """
    Assign a phone number to a company
    - If phone_number is None: assigns first available
    - If phone_number is provided: assigns that specific number
    """
```

### Frontend Components

#### `PhoneConfigModal.jsx`
Reusable modal component for phone number selection.

**Props:**
- `isOpen` - Boolean to show/hide modal
- `onClose` - Callback when modal is closed
- `onSuccess` - Callback when number is successfully assigned
- `allowSkip` - Boolean to allow skipping (true during signup, false in settings)

**Usage:**
```jsx
<PhoneConfigModal
  isOpen={showModal}
  onClose={() => setShowModal(false)}
  onSuccess={(phoneNumber) => handleSuccess(phoneNumber)}
  allowSkip={true}
/>
```

## Production Deployment

### Prerequisites

1. **Database Setup** (PostgreSQL on Render)
   - Ensure `DATABASE_URL` environment variable is set
   - Tables are auto-created on first run

2. **Phone Number Pool**
   - Add numbers using `db_scripts/add_phone_numbers_production.py`
   - Example: `python db_scripts/add_phone_numbers_production.py +353123456789`

3. **Environment Variables** (Render Web Service)
   ```
   DATABASE_URL=postgresql://...  (auto-set by Render)
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   ```

### Vercel Configuration

The frontend is deployed to Vercel. Ensure:

1. **Environment Variables:**
   - `VITE_API_URL` - Points to your Render backend URL

2. **Build Settings:**
   - Build command: `npm run build`
   - Output directory: `dist`
   - Install command: `npm install`

### Testing

Run the test script to verify functionality:

```bash
# Test with local SQLite
python db_scripts/test_phone_assignment.py

# Test with production PostgreSQL (set DATABASE_URL in .env)
DATABASE_URL=postgresql://... python db_scripts/test_phone_assignment.py
```

## Database Schema

### `twilio_phone_numbers` Table

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL/INTEGER | Primary key |
| phone_number | TEXT | Phone number in international format (+353...) |
| assigned_to_company_id | INTEGER | Foreign key to companies table (nullable) |
| assigned_at | TIMESTAMP | When number was assigned |
| status | TEXT | 'available' or 'assigned' |
| created_at | TIMESTAMP | When number was added to pool |

**Constraints:**
- `phone_number` is UNIQUE
- `status` CHECK constraint: must be 'available' or 'assigned'

### `companies` Table Update

| Column | Type | Description |
|--------|------|-------------|
| ... | ... | ... |
| twilio_phone_number | TEXT | Assigned phone number (UNIQUE) |
| ... | ... | ... |

## User Experience Flow

```
┌─────────────────────────────────────────┐
│         User Signs Up                    │
│  (Company info, email, password)         │
└───────────────┬─────────────────────────┘
                │
                v
┌─────────────────────────────────────────┐
│    Account Created Successfully          │
└───────────────┬─────────────────────────┘
                │
                v
┌─────────────────────────────────────────┐
│    Phone Config Modal Appears            │
│  ┌─────────────────────────────────┐    │
│  │  Choose Your Phone Number        │    │
│  │                                  │    │
│  │  ○ +353 86 123 4567             │    │
│  │  ○ +353 86 234 5678             │    │
│  │  ○ +353 86 345 6789             │    │
│  │                                  │    │
│  │  [Skip for Now] [Confirm]        │    │
│  └─────────────────────────────────┘    │
└───────────────┬─────────────────────────┘
                │
        ┌───────┴──────┐
        │              │
        v              v
   [Selects]      [Skips]
        │              │
        v              │
  Number assigned      │
  Permanent!           │
        │              │
        └───────┬──────┘
                v
    ┌─────────────────────────┐
    │   Dashboard (Ready!)    │
    └─────────────────────────┘
                │
    ┌───────────┴──────────────┐
    │  Can configure later in  │
    │  Settings if skipped     │
    └──────────────────────────┘
```

## Migration from Auto-Assignment

If you have existing users with auto-assigned numbers, **no changes needed**. The system is backward compatible:

- Existing assignments remain valid
- New signups use the selection flow
- Database structure is identical

## Troubleshooting

### "No phone numbers available"
**Solution:** Add phone numbers to the pool
```bash
python db_scripts/add_phone_numbers_production.py +353123456789
```

### "Company already has a phone number assigned"
**Expected:** Users can only assign once. This is intentional.

### Phone number not showing in Settings
**Solution:** Refresh user session or check API response includes `twilio_phone_number`

## Security Notes

- ✅ Authentication required for all phone number endpoints
- ✅ Users can only assign to their own company
- ✅ Numbers cannot be reassigned once taken
- ✅ All Twilio credentials stored in environment variables (not database)

## Support

For issues or questions:
1. Check the logs: `heroku logs --tail` or Render dashboard
2. Verify database connection: `python db_scripts/test_phone_assignment.py`
3. Check phone pool status: `python db_scripts/add_phone_numbers_production.py`
