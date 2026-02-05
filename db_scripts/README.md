# Database Management Scripts

This folder contains all database and phone number management tools for the AI Receptionist system.

## 📋 Files Overview

### Production Database Management

#### `add_phone_numbers_production.py`
**Purpose:** Add phone numbers to the production database (PostgreSQL on Render)

**Setup:**
1. Add DATABASE_URL to your `.env` file:
```env
DATABASE_URL=postgresql://user:password@host.render.com:5432/db_name
```

**Usage:**
```bash
# Add one or more phone numbers
python db_scripts/add_phone_numbers_production.py +353123456789 +353987654321

# View current phone pool status
python db_scripts/add_phone_numbers_production.py

# Add from a file
python db_scripts/add_phone_numbers_production.py --from-file numbers.txt
```

**Features:**
- Connects to production PostgreSQL database
- Adds multiple phone numbers to the pool
- Lists current phone number status
- Shows available/assigned numbers
- Safe duplicate handling

---

#### `seed_production_db.py`
**Purpose:** Initialize and seed the production database with default data

**Usage:**
```bash
python db_scripts/seed_production_db.py
```

**What it does:**
- Creates database tables if they don't exist
- Adds default services (plumbing, electrical, etc.)
- Sets up initial configuration
- Safe to run multiple times (won't duplicate data)

---

### Local Development Tools

#### `manage_phone_numbers.py`
**Purpose:** Quick local phone number management utility

**Usage:**
```bash
python db_scripts/manage_phone_numbers.py
```

**Features:**
- Works with local SQLite database
- Add/remove phone numbers
- View phone pool status
- Interactive command-line interface

---

#### `reset_phone_pool.py`
**Purpose:** Reset all phone numbers to unassigned status

**Usage:**
```bash
python db_scripts/reset_phone_pool.py
```

**Warning:** This will unassign all phone numbers from companies. Use carefully!

---

#### `import_services_to_db.py`
**Purpose:** Import services from JSON configuration into database

**Usage:**
```bash
python db_scripts/import_services_to_db.py
```

**What it does:**
- Reads services from `config/services_menu.json`
- Imports them into the database
- Updates existing services if needed

---

## 🔧 Environment Variables

All production scripts require:

```env
DATABASE_URL=postgresql://user:password@host.render.com:5432/database_name
```

Get this from your Render Dashboard:
1. Go to https://dashboard.render.com
2. Click on your PostgreSQL database
3. Copy the **External Database URL**

---

## 📝 Notes

- **Local development:** Uses SQLite (`local_receptionist.db`) automatically
- **Production:** Uses PostgreSQL via `DATABASE_URL` environment variable
- **Phone numbers:** Assigned automatically on company signup
- **No API keys in database:** Companies use shared Twilio account

---

## 🚀 Quick Reference

**Add phone to production:**
```bash
python db_scripts/add_phone_numbers_production.py +353123456789
```

**Seed production database:**
```bash
python db_scripts/seed_production_db.py
```

**Local phone management:**
```bash
python db_scripts/manage_phone_numbers.py
```

**Import services:**
```bash
python db_scripts/import_services_to_db.py
```
