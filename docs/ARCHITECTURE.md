# Reminder System - Clean Implementation

## Architecture Overview

The reminder system is **cleanly separated** into two independent paths:

### 1. Email Path (Recommended for Ireland)
```
reminder_scheduler.py → email_reminder.py → SMTP → Patient Email
```

### 2. SMS Path (For regions with SMS support)
```
reminder_scheduler.py → sms_reminder.py → Twilio API → Patient SMS
app.py (/twilio/sms) → Handle SMS replies
```

## File Structure

### Core Files
- **`src/services/email_reminder.py`** - Email sending via SMTP (works globally)
- **`src/services/sms_reminder.py`** - SMS sending via Twilio (regional limitations)
- **`src/services/reminder_scheduler.py`** - Main scheduler (uses email OR sms based on config)

### Configuration
- **`src/utils/config.py`** - Loads REMINDER_METHOD from .env (defaults to "email")

### Scripts
- **`scripts/check_reminders.py`** - Run this to check and send reminders
- **`scripts/validate_reminders.py`** - Validate your configuration

### Webhooks
- **`src/app.py`** - `/twilio/sms` endpoint (only active if REMINDER_METHOD=sms)

## How It Works

### Initialization (reminder_scheduler.py)
```python
if config.REMINDER_METHOD == "sms":
    self.sms_service = get_sms_service()
    self.email_service = None
else:  # defaults to email
    self.email_service = get_email_service()
    self.sms_service = None
```

### Sending Reminders
```python
if self.reminder_method == "sms":
    self.sms_service.send_reminder(...)
else:
    self.email_service.send_reminder(...)
```

## What Gets Loaded

### With REMINDER_METHOD=email (default)
✅ email_reminder.py loaded  
✅ SMTP configuration checked  
❌ sms_reminder.py NOT loaded  
❌ No Twilio API calls  
❌ SMS webhook inactive  

### With REMINDER_METHOD=sms
❌ email_reminder.py NOT loaded  
✅ sms_reminder.py loaded  
✅ Twilio configuration checked  
✅ SMS webhook active  

## Clean Separation Benefits

1. **No conflicts** - Email and SMS never run simultaneously
2. **No errors** - Missing SMS credentials won't break email mode
3. **No overhead** - Only loads what's needed
4. **Easy testing** - Test each path independently
5. **Clear defaults** - Email is default (best for Ireland)

## Configuration (.env)

### For Email (Recommended)
```env
REMINDER_METHOD=email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com
```

### For SMS (Optional - if your region supports it)
```env
REMINDER_METHOD=sms
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

## Validation

Run this to check your configuration:
```bash
python scripts/validate_reminders.py
```

Output will show:
- Which method is configured
- What credentials are set
- What's missing (if anything)
- Whether you're ready to send reminders

## Key Safety Features

1. **Graceful degradation** - If email/SMS not configured, prints warning but doesn't crash
2. **Method validation** - SMS webhook checks REMINDER_METHOD before processing
3. **Error handling** - All network calls wrapped in try/catch
4. **Duplicate prevention** - Tracks sent reminders in config/sent_reminders.json
5. **Clear logging** - Every action prints clear status messages

## Testing

### Test Email
```bash
# Set REMINDER_METHOD=email in .env
python scripts/validate_reminders.py  # Check config
python scripts/check_reminders.py      # Send reminders
```

### Test SMS (if applicable)
```bash
# Set REMINDER_METHOD=sms in .env
python scripts/validate_reminders.py  # Check config
python scripts/check_reminders.py      # Send reminders
# Send SMS to your Twilio number to test webhook
```

## What's Clean

✅ Single source of truth for reminder method (REMINDER_METHOD in .env)  
✅ No hardcoded SMS/email logic in multiple places  
✅ Each service is independent and self-contained  
✅ Clear initialization and error messages  
✅ No unused imports or dead code  
✅ Webhook checks config before processing  
✅ Email is the safe default for Ireland  

## What Was Removed

Nothing! Both paths are available because:
- Some users (US/UK) can use SMS
- You might want to switch methods later
- Code is cleanly separated, so no interference

## Summary

✅ **Clean separation** - Email and SMS are independent code paths  
✅ **Safe defaults** - Email is default, works in Ireland  
✅ **No errors** - Missing credentials for unused method won't break anything  
✅ **Easy to configure** - One line in .env: `REMINDER_METHOD=email`  
✅ **Easy to test** - Validation script checks everything  
✅ **Easy to use** - Run check_reminders.py when ready  
