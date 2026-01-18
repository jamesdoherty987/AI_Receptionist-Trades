# Quick Setup for Ireland - Email Reminders

Since you're in Ireland and Twilio SMS isn't reliable there, here's the quick setup for email reminders:

## Why Email Instead of SMS?

- ✅ **Works in Ireland** - No regional restrictions
- ✅ **Free** - Using Gmail/your existing email
- ✅ **Reliable** - Better deliverability than SMS in EU
- ✅ **Professional** - Nicely formatted HTML emails
- ❌ SMS in Ireland - Most Irish Twilio numbers don't support inbound SMS

## Setup Steps (5 minutes)

### 1. Update Your .env File

Add these lines to your `.env`:

```env
# Email Reminders (for Ireland)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_business_email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # 16-character app password from Google
FROM_EMAIL=your_business_email@gmail.com
REMINDER_METHOD=email
```

### 2. Get Gmail App Password

1. Go to: https://myaccount.google.com/security
2. Enable **2-Factor Authentication** (if not already on)
3. Go to: https://myaccount.google.com/apppasswords
4. Select "Mail" and your device
5. Copy the 16-character password (like `abcd efgh ijkl mnop`)
6. Paste it into `SMTP_PASSWORD` in your `.env` file

### 3. Modify Phone Prompt to Ask for Email

Since you need email for reminders, update the prompt to ask for email:

In `prompts/receptionist_prompt.txt`, change STEP 4 to:

```
STEP 4: Confirm Contact Details
- Say: "And I have your number as [phone number]. Could I also get your email address for appointment reminders?"
- Wait for user to provide email
- Confirm email: "So that's [email]@[domain]. Perfect!"
```

### 4. Update Booking to Capture Email

You'll need to modify the booking flow to capture and store email addresses. I can help with this if you want.

### 5. Test It

```bash
# Book a test appointment 24 hours from now
# Then run the reminder checker:
python scripts/check_reminders.py
```

You should receive a nicely formatted HTML email reminder!

## What Users Will Receive

**Subject:** Reminder: Your Physio Appointment Tomorrow

**Email Body:**
```
Hi John,

This is a friendly reminder about your physio appointment:

📅 Date & Time: Wednesday, December 22 at 2:00 PM
📍 Location: Munster Physio

If you need to cancel or reschedule, please call us as soon as possible.

Best regards,
Munster Physio Team
```

## Cost

**FREE** if using Gmail/your existing email provider!

## Alternative: Get Email During Booking

You have two options:

### Option A: Use Phone Number Only (Current Setup)
- Keep capturing phone during calls
- Manually add emails to calendar events
- Reminders go to emails you add manually

### Option B: Ask for Email Too (Better)
- AI asks for both phone AND email during booking
- Email stored in calendar event
- Automatic reminders to patient's email

I can implement Option B if you'd like - it would:
1. Update the AI prompt to ask for email
2. Store email in calendar description
3. Send automatic email reminders 24h before

Let me know which you prefer!
