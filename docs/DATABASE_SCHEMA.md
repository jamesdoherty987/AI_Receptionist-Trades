# Database Schema - Trades Company

## Overview
SQLite database optimized for a trades/maintenance business managing customers, jobs, workers, and bookings.

## Tables

### 1. `clients` - Customer Information
Stores customer contact details and history.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `name` | TEXT | Customer full name (stored lowercase for matching) |
| `phone` | TEXT | Phone number (required if no email) |
| `email` | TEXT | Email address (required if no phone) |
| `date_of_birth` | DATE | **DEPRECATED** - kept for backwards compatibility |
| `description` | TEXT | Customer notes/history |
| `first_visit` | DATE | Date of first job |
| `last_visit` | DATE | Date of most recent completed job |
| `total_appointments` | INTEGER | Total number of jobs (default: 0) |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Last update time |

**Notes:**
- Either `phone` OR `email` must be provided (both preferred)
- `name` is stored in lowercase for case-insensitive matching
- `date_of_birth` is no longer collected but retained for legacy data

---

### 2. `bookings` - Job Bookings
Stores all job bookings (past, present, future).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `client_id` | INTEGER | Foreign key to clients table |
| `calendar_event_id` | TEXT | Google Calendar event ID (unique) |
| `appointment_time` | TIMESTAMP | Scheduled job time |
| `service_type` | TEXT | Type of work (e.g., "Plumbing - Leaking tap") |
| `status` | TEXT | Job status: 'scheduled', 'completed', 'cancelled' |
| `urgency` | TEXT | **NEW** - 'emergency', 'same-day', 'scheduled', 'quote' |
| `address` | TEXT | **NEW** - Full job address |
| `eircode` | TEXT | **NEW** - Irish postal code |
| `property_type` | TEXT | **NEW** - 'Residential' or 'Commercial' |
| `phone_number` | TEXT | Contact phone for this job |
| `email` | TEXT | Contact email for this job |
| `charge` | REAL | Total charge for job |
| `payment_status` | TEXT | 'paid', 'unpaid', 'n/a' (for quotes) |
| `payment_method` | TEXT | 'cash', 'card', 'bank transfer' |
| `created_at` | TIMESTAMP | Booking creation time |

**Urgency Levels:**
- `emergency` - Urgent issues (burst pipes, electrical hazards) - €120 callout
- `same-day` - Needs attention today - standard rate
- `scheduled` - Planned future work - standard rate
- `quote` - Free estimate appointment - no charge

---

### 3. `workers` - Tradespeople/Staff
Stores information about workers and their specialties.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `name` | TEXT | Worker full name |
| `phone` | TEXT | Contact phone |
| `email` | TEXT | Contact email |
| `trade_specialty` | TEXT | Primary trade (e.g., "Plumbing & Heating") |
| `status` | TEXT | 'active' or 'inactive' |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Last update time |

**Trade Specialties:**
- Plumbing & Heating
- Electrical
- General Maintenance
- Carpentry
- Painting & Decorating

---

### 4. `appointment_notes` - Job-Specific Notes
Notes attached to specific job bookings.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `booking_id` | INTEGER | Foreign key to bookings table |
| `note` | TEXT | Note content |
| `created_by` | TEXT | Who created the note (default: 'system') |
| `created_at` | TIMESTAMP | Note creation time |
| `updated_at` | TIMESTAMP | Last update time |

---

### 5. `notes` - Customer Notes
General notes about customers (not job-specific).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `client_id` | INTEGER | Foreign key to clients table |
| `note` | TEXT | Note content |
| `created_by` | TEXT | Who created the note (default: 'system') |
| `created_at` | TIMESTAMP | Note creation time |

---

### 6. `call_logs` - Phone Call History
Logs of incoming calls (optional tracking).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `phone_number` | TEXT | Caller's phone number |
| `duration_seconds` | INTEGER | Call duration |
| `summary` | TEXT | Call summary/outcome |
| `created_at` | TIMESTAMP | Call time |

---

## Key Changes from Clinic Version

### Removed/Deprecated:
- ❌ `date_of_birth` - No longer collected (column kept for backwards compatibility)
- ❌ DOB-based customer matching

### Added for Trades:
- ✅ `urgency` - Emergency/Same-Day/Scheduled/Quote classification
- ✅ `address` - Full job address with Eircode
- ✅ `property_type` - Residential vs Commercial tracking
- ✅ `workers` table - Track tradespeople and specialties
- ✅ Enhanced payment tracking (charge, payment_status, payment_method)

### Updated Logic:
- Customer matching now uses: Name + Phone OR Name + Email
- Both phone AND email are mandatory for new customers
- Address collection is mandatory for all jobs
- Job descriptions are detailed and specific

---

## Sample Data

The database comes pre-populated with:
- **10 customers** with realistic Irish names and contact details
- **4 workers** covering plumbing, electrical, maintenance, and carpentry
- **14 past jobs** with varied urgency levels and payment statuses
- **3 upcoming jobs** scheduled in the next week
- **€3,625 total revenue** from completed paid jobs

---

## Database Location

Default: `data/receptionist.db`

## Utilities

### Reset & Populate:
```bash
python scripts/reset_database_trades.py
```

### View Contents:
```bash
python scripts/view_database.py
```

---

## Notes

- All timestamps use Europe/Dublin timezone
- Customer names are normalized to lowercase for matching
- Unique constraint on (name, phone, email) in clients table prevents duplicates
- Calendar event IDs link to Google Calendar for syncing
- Payment status tracking helps with invoicing and reporting
