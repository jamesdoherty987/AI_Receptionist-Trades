# AI Receptionist for Trades Companies

Professional AI-powered phone receptionist with job booking and Google Calendar integration for Swift Trade Services - optimized for plumbing, electrical, heating, and general trade businesses.

## Features
- ☎️ **Real-time phone conversations** via Twilio Media Streams
- 🎤 **Speech recognition** powered by Deepgram ASR
- 🤖 **Natural language AI** using OpenAI GPT-4o-mini
- 🗣️ **Text-to-speech** with Deepgram/ElevenLabs
- 🔧 **Intelligent job booking** (emergency/same-day/scheduled/quotes)
- 📆 **Google Calendar integration** with availability checking
- 📱 **Automatic phone & email capture** with validation
- 📍 **Address collection** for on-site work
- ⚡ **Urgency assessment** (Emergency/Same-Day/Scheduled/Quote)
- 🏠 **Property type tracking** (Residential/Commercial)
- 🔔 **Email/SMS reminders** sent 24 hours before jobs
- 💬 **Reminder confirmations** via email or SMS replies
- 🚫 **Interrupt handling** for natural conversations
- ⏰ **Business hours enforcement** (configurable, default 9 AM - 5 PM Mon-Fri)
- 🌍 **Timezone support** (Europe/Dublin)
- 🛠️ **Services menu management** - Add/edit/delete services with pricing via web UI
- ⚙️ **Settings management** - Configure business hours, services, and pricing without editing code
- 📊 **Dashboard** - View bookings, manage clients, track finances

## Project Structure

```
AI-Receptionist/
├── src/                          # Main application code
│   ├── app.py                   # Flask server (voice + SMS webhooks)
│   ├── media_ws.py              # WebSocket server for audio streaming
│   ├── handlers/                # Request handlers
│   │   └── media_handler.py    # Real-time audio processing
│   ├── services/                # Core services
│   │   ├── appointment_detector.py  # Intent classification
│   │   ├── asr_deepgram.py         # Speech-to-text
│   │   ├── google_calendar.py      # Calendar operations
│   │   ├── llm_stream.py           # AI conversation management
│   │   ├── sms_reminder.py         # SMS reminder sending
│   │   ├── reminder_scheduler.py   # 24-hour reminder checker
│   │   ├── tts_deepgram.py         # Text-to-speech (Deepgram)
│   │   └── tts_elevenlabs.py       # Text-to-speech (ElevenLabs)
│   └── utils/                   # Utilities
│       ├── audio_utils.py       # Audio processing
│       ├── config.py            # Configuration loader
│       └── date_parser.py       # Natural language date parsing
├── scripts/                      # Utility scripts
│   └── check_reminders.py       # Reminder checker (run via cron/scheduler)
├── config/                       # Configuration files
│   ├── business_info.json       # Business details (editable)
│   └── sent_reminders.json      # Tracks sent reminders
├── docs/                         # Documentation
│   └── REMINDERS.md             # Reminder system setup guide
│   ├── credentials.json         # Google Calendar credentials
│   └── token.json              # Google Calendar auth token
├── prompts/                      # AI prompts
│   └── receptionist_prompt.txt  # Main system prompt
├── scripts/                      # Utility scripts
│   ├── chat_test.py            # Text-based testing interface
│   ├── check_calendar.py       # View calendar appointments
│   └── setup_calendar.py       # Google Calendar setup
├── tests/                        # Test files
│   ├── test_booking_flow.py    # Booking flow tests
│   ├── test_cancel_reschedule.py  # Cancel/reschedule tests
│   ├── test_business_hours.py  # Business hours validation
│   └── test_datetime_parser.py # Date parsing tests
├── .env                          # Environment variables
├── requirements.txt              # Python dependencies
└── ngrok.yml                     # Ngrok configuration
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Deepgram
DEEPGRAM_API_KEY=your_deepgram_api_key

# ElevenLabs (optional)
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# Twilio (from ngrok URLs)
PUBLIC_URL=https://your-ngrok-url.ngrok.io
WS_PUBLIC_URL=wss://your-ngrok-url.ngrok.io/ws

# Twilio SMS (for appointment reminders - optional, check regional availability)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Email (for appointment reminders - recommended for Ireland/EU)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com
REMINDER_METHOD=email  # Use "email" or "sms"

# Google Calendar
CALENDAR_ID=primary
CALENDAR_TIMEZONE=Europe/Dublin

# Business Hours
BUSINESS_HOURS_START=9
BUSINESS_HOURS_END=17
```

### 3. Set Up Google Calendar
```bash
python scripts/setup_calendar.py
```
Follow the prompts to authenticate with Google Calendar.

### 4. Configure Business Information
Edit `config/business_info.json` with your business details:
```json
{
  "business_name": "Your Business Name",
  "location": {
    "address": "Your Address",
    "parking": "Parking instructions"
  },
  "pricing": {
    "standard_appointment": "€50"
  }
}
```

### 5. Run the Application

**Terminal 1 - Flask Server:**
```bash
python src/app.py
```

**Terminal 2 - WebSocket Server:**
```bash
python src/media_ws.py
```

**Terminal 3 - Ngrok:**
```bash
ngrok start --config=ngrok.yml --all
```

### 6. Configure Twilio
1. Update `.env` with your ngrok URLs
2. In Twilio Console, set your phone number's webhook to:
   ```
   https://YOUR_PUBLIC_URL/twilio/voice
   ```

## Testing

### Text-Based Testing (No Phone Required)
```bash
python scripts/chat_test.py
```
This provides a text interface to test the conversation flow without making phone calls.

### Check Calendar
```bash
python scripts/check_calendar.py
```
View upcoming appointments in Google Calendar.

### Run Unit Tests
```bash
python tests/test_booking_flow.py
python tests/test_cancel_reschedule.py
python tests/test_business_hours.py
```

## Appointment Management

The AI receptionist can:

### Book Appointments
**User:** "Hi, I'm James Doherty and I want to book for tomorrow at 2pm for an injury"
**AI:** Checks availability → Confirms details → Books to Google Calendar

### Cancel Appointments
**User:** "I need to cancel my appointment tomorrow at 2pm"
**AI:** Finds appointment → Cancels → Confirms cancellation

### Reschedule Appointments
**User:** "Can I move my Friday 2pm appointment to Monday at 11am?"
**AI:** Finds old appointment → Checks new time availability → Reschedules → Confirms

### Check Availability
- Automatically checks for conflicts before booking
- Suggests alternative times if requested slot is busy
- Shows all available slots on a given day

## Customization

### Business Information
Edit `config/business_info.json` to update:
- Business name and contact details
- Location and parking information
- Services offered
- Pricing and payment methods
- Staff names

Changes take effect after restarting the application.

### System Prompt
Edit `prompts/receptionist_prompt.txt` to customize:
- Conversation style and tone
- Greeting messages
- Booking flow steps
- Example responses

### Business Hours
Update `.env`:
```env
BUSINESS_HOURS_START=9  # 9 AM
BUSINESS_HOURS_END=17   # 5 PM
```

## Architecture

### Real-Time Voice Flow
```
Phone Call → Twilio → Flask Webhook → WebSocket Connection
                                          ↓
                                     Media Handler
                                          ↓
                        ┌─────────────────┼─────────────────┐
                        ↓                 ↓                 ↓
                    Deepgram ASR    Intent Detection    Google Calendar
                        ↓                 ↓                 ↓
                    User Text      Appointment Action   Availability
                        ↓                 ↓                 ↓
                        └────────→ OpenAI LLM ←───────────┘
                                          ↓
                                    AI Response
                                          ↓
                                     TTS (Deepgram)
                                          ↓
                                    Audio Stream → Twilio → Phone
```

### Key Components

**Appointment Detection:** Uses OpenAI function calling to classify intents (book/cancel/reschedule/query) and extract details (name, date, time, service).

**Date Parsing:** Converts natural language ("tomorrow at 2pm", "next Friday", "noon") to datetime objects with business hours enforcement.

**Calendar Integration:** Full CRUD operations with Google Calendar API, including availability checking and conflict detection.

**Conversation State:** Maintains context across multiple turns to gather all required information before booking.

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `DEEPGRAM_API_KEY` | Deepgram API key | `...` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key (optional) | `...` |
| `PUBLIC_URL` | Public HTTP URL from ngrok | `https://abc123.ngrok.io` |
| `WS_PUBLIC_URL` | Public WebSocket URL from ngrok | `wss://abc123.ngrok.io/ws` |
| `CALENDAR_ID` | Google Calendar ID | `primary` |
| `CALENDAR_TIMEZONE` | Calendar timezone | `Europe/Dublin` |
| `BUSINESS_HOURS_START` | Opening hour (24h) | `9` |
| `BUSINESS_HOURS_END` | Closing hour (24h) | `17` |
| `TTS_PROVIDER` | TTS provider | `deepgram` or `elevenlabs` |

## Troubleshooting

### "Could not authenticate with Google Calendar"
Run `python scripts/setup_calendar.py` to re-authenticate.

### "No appointment detected"
The AI may need more specific information. Test with: "I want to book an appointment for tomorrow at 2pm"

### Phone call audio issues
1. Check ngrok URLs are correct in `.env`
2. Verify Twilio webhook is set correctly
3. Ensure WebSocket server is running

### Appointment not booking
1. Check Google Calendar authentication
2. Verify business hours configuration
3. Test with `python scripts/chat_test.py`

## Contributing

This is a professional AI receptionist system built for Munster Physio. For customization or issues, refer to:
- `config/business_info.json` for business details
- `prompts/receptionist_prompt.txt` for conversation flow
- `.env` for runtime configuration

## License

Proprietary - Munster Physio
```

## Google Calendar Setup

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed Google Calendar integration instructions.

Quick steps:
1. Enable Google Calendar API in Cloud Console
2. Download OAuth credentials to `config/credentials.json`
3. Run the app - it will prompt for authorization on first use

## Project Structure

```
src/
├── app.py                    # Flask application
├── media_ws.py              # WebSocket server
├── handlers/                # Request handlers
├── services/                # Core services (ASR, TTS, LLM, Calendar)
└── utils/                   # Utilities and config
```

## Documentation
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete setup instructions
- [OPTIMIZATION_NOTES.md](OPTIMIZATION_NOTES.md) - Performance details

## License
MIT