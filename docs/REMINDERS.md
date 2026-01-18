# Appointment Reminder System

## Overview

This system automatically sends reminders to patients 24 hours before their scheduled appointments.

⚠️ **IMPORTANT FOR IRELAND/EU USERS**: 
- Twilio SMS is limited in Ireland - most Irish numbers don't support inbound SMS
- **Recommended alternatives**: Email reminders or WhatsApp Business
- See "Regional Considerations" section below

## Features

- 📱 **Phone Number Capture**: Automatically captures caller's phone number from Twilio
- ✅ **Phone Confirmation**: Asks patient to confirm their phone number before booking
- 📅 **24-Hour Reminders**: Sends reminders 24 hours before appointments
- 💬 **Reply Handling**: Handles confirmations and cancellations (method depends on channel)
- 🔒 **Duplicate Prevention**: Tracks sent reminders to avoid sending duplicates

## Regional Considerations

### Ireland & EU Limitations

**Twilio SMS Issues:**
- Most Irish Twilio numbers don't support inbound SMS
- Outbound SMS may require specific number types (long codes vs short codes)
- Higher costs and regulatory compliance requirements

**Recommended Solutions for Ireland:**

#### Option 1: Email Reminders (Easiest)
- Use the email service (see email_reminder.py below)
- No additional Twilio setup needed
- Works with existing phone capture
- Free (using SMTP) or cheap (using SendGrid/Mailgun)

#### Option 2: WhatsApp Business (Best User Experience)
- Twilio WhatsApp works great in Ireland
- Higher engagement rates than SMS
- Rich media support
- Requires WhatsApp Business API approval

#### Option 3: US/UK Twilio Number for SMS (If SMS Required)
- Get a US or UK Twilio number with SMS capability
- Costs slightly more for international SMS
- Clearly identify the number in reminders

## Setup

### For Email Reminders (✅ Recommended for Ireland)

#### 1. Add Email Configuration to .env

```env
# Email Configuration (works globally, no regional restrictions)
SMTP_SERVER=smtp.gmail.com  # Or your email provider's SMTP server
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password  # For Gmail, use App Password (not regular password)
FROM_EMAIL=your_email@gmail.com
REMINDER_METHOD=email  # Use "email" for email reminders, "sms" for SMS
```

#### 2. Gmail Setup (Most Common)

If using Gmail:
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Factor Authentication (required for app passwords)
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Create an app password for "Mail"
5. Use this 16-character password in `SMTP_PASSWORD`

#### 3. Other Email Providers

**Outlook/Office 365:**
```env
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your_email@outlook.com
SMTP_PASSWORD=your_password
```

**Yahoo:**
```env
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=your_email@yahoo.com
SMTP_PASSWORD=your_app_password  # Generate in Yahoo account settings
```

**Custom Domain (e.g., via cPanel):**
```env
SMTP_SERVER=mail.yourdomain.com
SMTP_PORT=587
SMTP_USER=info@yourdomain.com
SMTP_PASSWORD=your_email_password
```

### For SMS (US/UK/Supported Regions Only)

⚠️ **Check your number first**: Go to Twilio Console → Phone Numbers → Check "SMS" capability

```env
# Twilio SMS Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890  # Must support SMS
REMINDER_METHOD=sms  # Use "sms" for SMS reminders
```

#### Configure Twilio SMS Webhook

In your Twilio Console:
1. Go to your phone number settings
2. Under "Messaging", set the webhook for "A MESSAGE COMES IN":
   ```
   https://YOUR_PUBLIC_URL/twilio/sms
   ```
3. Method: POST

### 3. Run the Reminder Checker

You have several options to run the reminder checker:

#### Option A: Manual Execution
```bash
python scripts/check_reminders.py
```

#### Option B: Windows Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at a specific time (e.g., 10 AM)
4. Action: Start a program
   - Program: `python`
   - Arguments: `scripts/check_reminders.py`
   - Start in: `C:\Users\jkdoh\VSCodeProjects\AI-Receptionist`

#### Option C: Linux/Mac Cron Job
Add to crontab (`crontab -e`):
```bash
# Run every hour
0 * * * * cd /path/to/AI-Receptionist && python scripts/check_reminders.py >> logs/reminders.log 2>&1
```

#### Option D: Background Scheduler (APScheduler)
Install APScheduler:
```bash
pip install apscheduler
```

Add to your app startup code:
```python
from apscheduler.schedulers.background import BackgroundScheduler
from src.services.reminder_scheduler import run_reminder_check

scheduler = BackgroundScheduler()
scheduler.add_job(run_reminder_check, 'interval', hours=1)
scheduler.start()
```

## How It Works

### Phone Number Flow

1. **Call Initiated**: Patient calls your Twilio number
2. **Number Captured**: System extracts phone number from Twilio metadata
3. **Confirmation**: AI asks: "I have your number as [phone]. Is that the best number to reach you?"
4. **Booking**: After confirmation, phone is stored with appointment in Google Calendar

### Reminder Flow

1. **Scheduled Check**: Script runs periodically (e.g., every hour)
2. **Query Appointments**: Checks Google Calendar for appointments 24 hours ahead
3. **Extract Details**: Gets phone number, patient name, and appointment details
4. **Send SMS**: Sends reminder via Twilio
5. **Track Sent**: Marks reminder as sent to prevent duplicates

### SMS Format

**Reminder Message:**
```
Hi [Patient Name]! This is a reminder about your [service] appointment 
tomorrow ([Date] at [Time]). Reply YES to confirm or CANCEL to cancel 
your appointment.
```

**Confirmation Reply:**
```
Thank you! Your appointment is confirmed. We look forward to seeing you!
```

**Cancellation Reply:**
```
We received your cancellation request. Please call us to confirm the 
cancellation and reschedule if needed.
```

## File Structure

```
src/
├── services/
│   ├── sms_reminder.py          # Twilio SMS sending
│   └── reminder_scheduler.py     # Check and send reminders
└── app.py                        # SMS webhook endpoint

scripts/
└── check_reminders.py            # Standalone reminder checker

config/
└── sent_reminders.json           # Tracks sent reminders
```

## Testing

### Test Phone Capture
1. Call your Twilio number
2. Book an appointment
3. Check that phone number is confirmed
4. Verify phone appears in Google Calendar event description

### Test Reminder Sending
1. Book a test appointment 24 hours from now
2. Run: `python scripts/check_reminders.py`
3. Check that SMS is received
4. Reply "YES" or "CANCEL" to test webhook

### Manual Reminder Test
```python
from src.services.sms_reminder import get_sms_service
from datetime import datetime, timedelta

sms = get_sms_service()
tomorrow = datetime.now() + timedelta(days=1)
sms.send_reminder(
    to_number="+1234567890",
    appointment_time=tomorrow,
    patient_name="Test Patient",
    service_type="Cleaning"
)
```

## Troubleshooting

### No SMS Sent
- Check Twilio credentials in .env
- Verify phone number includes country code (e.g., +1)
- Check Twilio account balance
- Look for errors in reminder check output

### Duplicate Reminders
- System tracks sent reminders in `config/sent_reminders.json`
- Each reminder is marked by event ID + datetime
- Delete file to reset if needed

### Phone Not Captured
- Check media_handler.py logs for "📱 Caller phone:"
- Verify Twilio is passing caller metadata
- Test with actual call (not Twilio simulator)

### SMS Reply Not Working
- Verify webhook URL in Twilio Console
- Check Flask app is running and accessible
- Look for "/twilio/sms" logs in app output

## Cost Considerations

**Twilio SMS Pricing** (approximate):
- Outbound SMS: $0.0079 per message (US)
- Inbound SMS: $0.0079 per message (US)

Example monthly cost for 100 appointments:
- 100 reminders sent = $0.79
- 50 replies received = $0.40
- **Total: ~$1.19/month**

## Future Enhancements

- [ ] Email reminders in addition to SMS
- [ ] Configurable reminder timing (12h, 24h, 48h options)
- [ ] Multiple reminders per appointment
- [ ] Direct cancellation via SMS (with event ID lookup)
- [ ] Database for better tracking and analytics
- [ ] Patient portal for managing preferences
- [ ] Support for appointment rescheduling via SMS

## Security Notes

- Never commit `.env` file with Twilio credentials
- Use environment variables in production
- Validate phone numbers before sending
- Rate limit SMS sending to prevent abuse
- Monitor Twilio usage and set spending limits
