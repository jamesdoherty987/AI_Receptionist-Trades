# Utility Scripts

This directory contains utility scripts for testing and managing the AI Receptionist system.

## Scripts

### `chat_test.py`
Interactive text-based testing interface for the AI receptionist.

**Usage:**
```bash
python scripts/chat_test.py
```

**Features:**
- Test conversations without making phone calls
- See detailed appointment detection logs
- Test booking, cancellation, and rescheduling flows
- Type `reset` to clear appointment state
- Type `quit` or `exit` to end session

**Example:**
```
You: Hi, I'm James and I want to book for tomorrow at 2pm for back pain
AI: Let me check if James is available...
     [Shows availability check]
     Perfect! Just to confirm, that's James tomorrow at 2pm for back pain?
You: yes
AI: Awesome, you're all set!
```

### `sync_to_google_calendar.py` ⭐ NEW
Sync local database bookings to Google Calendar.

**Usage:**
```bash
python scripts/sync_to_google_calendar.py
```

**Features:**
- Creates real Google Calendar events for test bookings
- Updates database with actual calendar event IDs
- Skips bookings that already have real calendar events
- Shows detailed progress and summary

**When to use:**
- After running `add_test_users.py` to sync test data to Google Calendar
- If bookings exist in database but not in calendar
- To fix calendar sync issues

**Note:** Test bookings created by `add_test_users.py` use fake event IDs and won't appear in Google Calendar until you run this sync script.

### `check_calendar.py`
View upcoming appointments from Google Calendar.

**Usage:**
```bash
python scripts/check_calendar.py
```

**Output:**
- Lists all upcoming appointments for the next 7 days
- Shows patient names, times, and services
- Useful for verifying bookings worked correctly

### `setup_calendar.py`
Initial Google Calendar authentication setup.

**Usage:**
```bash
python scripts/setup_calendar.py
```

**What it does:**
1. Opens browser for Google authentication
2. Requests calendar access permissions
3. Saves authentication token to `config/token.json`
4. Tests connection by listing upcoming events

**When to run:**
- First time setup
- After changing Google account
- If `token.json` gets corrupted
- When seeing "Could not authenticate" errors

## Tips

**Before Testing:**
- Ensure `.env` is configured with all API keys
- Run `setup_calendar.py` if this is your first time
- Start with `chat_test.py` to validate logic before phone testing

**Troubleshooting:**
- If calendar operations fail, run `setup_calendar.py` again
- If tests fail, check that business hours are set correctly in `.env`
- Use `check_calendar.py` to verify appointments were actually created
