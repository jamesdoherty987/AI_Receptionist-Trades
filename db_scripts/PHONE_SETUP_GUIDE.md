# Quick Start: Adding Phone Numbers to Database

## ✅ What Changed
- **Removed from database:** `twilio_account_sid` and `twilio_auth_token`
- **Kept in database:** Only `twilio_phone_number` (assigned from pool)
- **Environment variables:** Twilio credentials now come from Render environment variables

## 📋 What You Need

**Twilio Master Account Credentials** (set in Render environment variables):
- `TWILIO_ACCOUNT_SID` - Your Twilio account SID
- `TWILIO_AUTH_TOKEN` - Your Twilio auth token

**Phone Numbers** - Buy phone numbers from your Twilio account

## 🚀 Adding Phone Numbers to Production

### Step 1: Get your DATABASE_URL from Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click on your PostgreSQL database
3. Copy the **External Database URL** (starts with `postgresql://`)

### Step 2: Add DATABASE_URL to your .env file

Open your `.env` file in the project root and add:

```env
# Database (Production - get from Render Dashboard)
DATABASE_URL=postgresql://user:password@host.render.com:5432/database_name
```

### Step 3: Add phone numbers to the database

```bash
# Simply run the script - it automatically loads from .env
python db_scripts/add_phone_numbers_production.py +353123456789 +353987654321
```

### Step 4: Verify

The script will show you:
- ✅ Numbers successfully added
- ⚠️ Numbers already in database (skipped)
- 📊 Current phone pool status

**Example output:**
```
📞 Adding 2 phone numbers to database...
Database type: PostgreSQL

   ✅ Added: +353123456789
   ✅ Added: +353987654321

✨ Successfully added 2 phone numbers

📊 Current Phone Pool Status:
   Available: 2
   Assigned: 0
   Total: 2

🔍 Phone Number Details:
   +353123456789 - available
   +353987654321 - available
```

## 🔄 How It Works

1. **Signup:** When a company signs up, they are automatically assigned an available phone number from the pool
2. **Twilio Config:** All companies use the same Twilio account (from environment variables)
3. **Incoming Calls:** Twilio webhook routes calls by phone number: `WHERE twilio_phone_number = incoming_number`
4. **No API Keys:** Companies never configure API keys - it's all handled automatically

## 🛠️ Additional Commands

**View current phone pool:**
```bash
python db_scripts/add_phone_numbers_production.py
```

**Add from a file:**
```bash
# Create a file with one phone number per line
python db_scripts/add_phone_numbers_production.py --from-file numbers.txt
```

**Reset phone pool (unassign all):**
```bash
python db_scripts/reset_phone_pool.py
```

## 📝 Notes

- Phone numbers must be in international format: `+353...` (Ireland), `+1...` (US), etc.
- Buy numbers from your Twilio console: https://console.twilio.com/
- Each number can only be assigned to one company
- Numbers are automatically assigned on company signup (first available)
- The script handles duplicates safely (skips if already exists)

## 🔐 Environment Variables Required on Render

Make sure these are set in your Render Web Service:

```env
TWILIO_ACCOUNT_SID=AC...your_account_sid
TWILIO_AUTH_TOKEN=...your_auth_token
DATABASE_URL=postgresql://...  (automatically set by Render)
```

That's it! Your phone pool system is ready to go! 🎉
