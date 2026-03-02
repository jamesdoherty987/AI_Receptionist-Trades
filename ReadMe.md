# AI Receptionist for Trades Companies

Professional AI-powered phone receptionist with job booking and Google Calendar integration - optimized for plumbing, electrical, heating, and general trade businesses.

## ✨ Modern React Dashboard

This project now features a **professional React-based web interface** for managing your AI receptionist.

### Features
- ☎️ **Real-time phone conversations** via Twilio Media Streams
- 🤖 **Natural language AI** using OpenAI GPT-4o-mini
- 🎤 **Speech recognition** powered by Deepgram ASR
- 🗣️ **Text-to-speech** with Deepgram/ElevenLabs
- 📊 **Modern React Dashboard** - Manage everything from a beautiful web interface
- 🔧 **Intelligent job booking** (emergency/same-day/scheduled/quotes)
- 📆 **Google Calendar integration** with availability checking
- 📱 **Automatic phone & email capture** with validation
- 📍 **Address collection** for on-site work
- ⚡ **Urgency assessment** (Emergency/Same-Day/Scheduled/Quote)
- 🏠 **Property type tracking** (Residential/Commercial)
- 🔔 **Email/SMS reminders** sent 24 hours before jobs
- 💬 **Reminder confirmations** via email or SMS replies
- 🚫 **Interrupt handling** for natural conversations
- ⚙️ **Settings management** - Configure business hours, services, and pricing via web UI
- 🎨 **Beautiful UI** - Glassmorphism design with smooth animations

## 🚀 Quick Start

### 1. Install Dependencies

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### 2. Start Development

**Local Development (No Remote Access):**
```bash
# Terminal 1 - Backend
python src/app.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

**With Ngrok (Access from Other Devices):**

Open 4 separate terminals and run these commands:

**Terminal 1 - Flask Backend:**
```bash
venv\Scripts\activate
python src/app.py
```

**Terminal 2 - WebSocket Server:**
```bash
venv\Scripts\activate
python src/media_ws.py
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 4 - Ngrok:**
```bash
ngrok start --config=ngrok.yml --all
```

After ngrok starts, check the ngrok window for your public URLs:
- Frontend: `https://xxxx-xxxx-xxxx.ngrok-free.app` (port 3000)
- Backend: `https://xxxx-xxxx-xxxx.ngrok-free.app` (port 5000)
- WebSocket: `https://xxxx-xxxx-xxxx.ngrok-free.app` (port 8765)

**Note:** If accessing from remote devices, you may need to update `frontend/vite.config.js` to change the API proxy target from `http://localhost:5000` to your ngrok backend URL.

### 3. Access Dashboard
- **Local:** http://localhost:3000
- **Remote:** Use the frontend ngrok URL from Terminal 4

## 📁 Project Structure

```
AI-Receptionist-Trades/
├── frontend/                     # ⚛️ React Dashboard (NEW)
│   ├── src/
│   │   ├── components/          # Reusable React components
│   │   ├── pages/               # Dashboard, Settings, etc.
│   │   ├── services/            # API client
│   │   └── utils/               # Helper functions
│   ├── package.json
│   └── vite.config.js
├── src/                          # 🐍 Python Backend
│   ├── app.py                   # Flask server (API + webhooks)
│   ├── media_ws.py              # WebSocket for audio streaming
│   ├── handlers/                # Request handlers
│   │   └── media_handler.py    # Real-time audio processing
│   ├── services/                # Core services
│   │   ├── asr_deepgram.py         # Speech-to-text
│   │   ├── google_calendar.py      # Calendar operations
│   │   ├── llm_stream.py           # AI conversation
│   │   ├── sms_reminder.py         # SMS reminders
│   │   ├── tts_deepgram.py         # Text-to-speech
│   │   └── settings_manager.py     # Settings management
│   ├── static/
│   │   └── dist/                # React build output
│   └── utils/                   # Utilities
├── config/                       # Configuration files
│   ├── business_info.json       # Business details
│   └── sent_reminders.json      # Tracks sent reminders
├── db_scripts/                   # 🗄️ Database Management Tools
│   ├── add_phone_numbers_production.py  # Add phones to production
│   ├── manage_phone_numbers.py          # Local phone management
│   ├── reset_phone_pool.py              # Reset phone pool
│   ├── seed_production_db.py            # Seed production database
│   └── import_services_to_db.py         # Import services
├── docs/                         # 📚 Documentation
│   ├── HOW_TO_ADD_PHONE_NUMBERS.md     # Phone number management guide
│   ├── credentials.json                 # Google Calendar credentials
│   └── token.json                       # Google Calendar auth token
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

## Configuration

### Environment Variables
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

# Twilio - Master Account (phone numbers assigned from pool)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890  # Your first phone number for the pool

# Database (Production - get from Render Dashboard)
DATABASE_URL=postgresql://user:password@host.render.com:5432/database_name

# Email (for appointment reminders - recommended for Ireland/EU)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com
REMINDER_METHOD=email  # Use "email" or "sms"

# Stripe Payment (for invoices with payment links)
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLIC_KEY=pk_live_your_stripe_public_key

# Company Branding (optional)
COMPANY_LOGO_URL=https://your-domain.com/logo.png

# Google Calendar
CALENDAR_ID=primary
CALENDAR_TIMEZONE=Europe/Dublin

# Business Hours
BUSINESS_HOURS_START=9
BUSINESS_HOURS_END=17
```

### Database Setup

#### Local Development (SQLite)
Local development automatically uses SQLite - no setup needed!

#### Production (PostgreSQL on Render)

**Get your database URL:**
1. Go to Render Dashboard: https://dashboard.render.com
2. Click on your PostgreSQL database
3. Copy the **External Database URL**

**Add to your .env file:**
```env
# Database (Production - get from Render Dashboard)
DATABASE_URL=postgresql://user:password@host.render.com:5432/database_name
```

**Add phone numbers to production database:**

```bash
# Simply run the script - it automatically loads DATABASE_URL from .env
python db_scripts/add_phone_numbers_production.py +353123456789 +353987654321
```

**List phone numbers in pool:**
```powershell
python add_phone_numbers_production.py --list
```

See [docs/HOW_TO_ADD_PHONE_NUMBERS.md](docs/HOW_TO_ADD_PHONE_NUMBERS.md) for detailed instructions.

### Set Up Google Calendar
```bash
python scripts/setup_calendar.py
```
Follow the prompts to authenticate with Google Calendar.

### Configure Business Information
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

### Configure Twilio

**New Phone Number Pool System:**

Users no longer configure Twilio credentials. Instead:

1. **Initialize Phone Pool:**
   ```bash
   python manage_phone_numbers.py
   ```
   This adds your TWILIO_PHONE_NUMBER to the pool.

2. **Add More Numbers (Optional):**
   ```bash
   python manage_phone_numbers.py +1234567890 +1234567891
   ```

3. **Configure Webhooks in Twilio Console:**
   - Go to Phone Numbers → Manage → Active Numbers
   - Click each phone number
   - Under "Voice Configuration":
     - **A Call Comes In**: Webhook
     - **URL**: `https://your-backend.onrender.com/twilio/voice`
     - **HTTP Method**: POST
   - Save

**How it works:**
- When users sign up, they automatically get assigned a phone number from the pool
- Users see their assigned number in Settings (read-only)
- Incoming calls route to the correct company based on which number was called
- No Twilio configuration needed by users!

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

1. Enable Google Calendar API in Google Cloud Console
2. Download OAuth credentials to `config/credentials.json`
3. Run `python scripts/setup_calendar.py` - it will prompt for authorization