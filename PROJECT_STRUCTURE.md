# AI Receptionist - Project Structure

## 📁 File Organization

```
AI-Receptionist/
├── 📱 Frontend (Dashboard)
│   └── src/static/
│       ├── dashboard.html      # Main dashboard UI
│       └── dashboard.js        # Frontend JavaScript
│
├── 🖥️ Backend (Server)
│   └── src/
│       ├── app.py             # Flask server & API endpoints
│       ├── media_ws.py        # WebSocket server for Twilio
│       ├── handlers/          # Request handlers
│       │   └── media_handler.py
│       ├── services/          # Core business logic
│       │   ├── appointment_detector.py   # Intent detection
│       │   ├── asr_deepgram.py          # Speech-to-text
│       │   ├── database.py              # SQLite database
│       │   ├── email_reminder.py        # Email notifications
│       │   ├── google_calendar.py       # Calendar integration
│       │   ├── llm_stream.py            # AI conversation
│       │   ├── reminder_scheduler.py    # Reminder system
│       │   ├── sms_reminder.py          # SMS notifications
│       │   ├── tts_deepgram.py          # Text-to-speech (Deepgram)
│       │   └── tts_elevenlabs.py        # Text-to-speech (ElevenLabs)
│       └── utils/             # Helper utilities
│           ├── audio_utils.py
│           ├── config.py
│           └── date_parser.py
│
├── 🧪 Tests
│   └── tests/
│       ├── conftest.py                  # Pytest configuration
│       ├── test_datetime_parser.py      # Date/time parsing tests
│       ├── test_booking_flow.py         # Booking flow tests
│       ├── test_business_hours.py       # Business hours validation
│       ├── test_cancel_reschedule.py    # Cancel/reschedule tests
│       ├── test_complete_booking.py     # End-to-end booking
│       └── [other test files...]
│
├── ⚙️ Configuration
│   ├── config/
│   │   ├── business_info.json    # Business details
│   │   ├── credentials.json      # Google OAuth credentials
│   │   └── token.json           # Google access token
│   ├── prompts/
│   │   └── receptionist_prompt.txt   # AI system prompt
│   ├── .env                     # Environment variables
│   ├── requirements.txt         # Python dependencies
│   └── pytest.ini              # Test configuration
│
├── 📜 Scripts (Utilities)
│   └── scripts/
│       ├── add_test_email.py
│       ├── chat_test.py
│       ├── check_calendar.py
│       ├── check_reminders.py
│       ├── init_dashboard.py
│       ├── setup_calendar.py
│       ├── test_email.py
│       └── validate_reminders.py
│
├── 📖 Documentation
│   └── docs/
│       ├── ARCHITECTURE.md      # System architecture
│       ├── DASHBOARD.md         # Dashboard guide
│       ├── IRELAND_SETUP.md     # Ireland deployment
│       └── REMINDERS.md         # Reminder system docs
│
└── 📦 Data
    ├── data/                    # Runtime data storage
    └── ngrok.yml               # Ngrok tunnel config
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your API keys:
- OPENAI_API_KEY
- DEEPGRAM_API_KEY
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- etc.

### 3. Setup Google Calendar
```bash
python scripts/setup_calendar.py
```

### 4. Run the Server
```bash
python src/app.py
```

### 5. Start Ngrok (for Twilio)
```bash
ngrok http 5000
```

### 6. Access Dashboard
Open http://localhost:5000 in your browser

## 🧪 Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Category
```bash
# Date/time parsing
python tests/test_datetime_parser.py

# Booking flow
pytest tests/test_booking_flow.py -v

# Business hours
pytest tests/test_business_hours.py -v
```

### Run Tests from Dashboard
Navigate to the "Developer Tools" tab and click:
- "Run All Tests" - Runs full pytest suite
- "Run DateTime Tests" - Tests date parsing only

## 📊 Dashboard Features

### Client Management Tab
- View all clients
- Add new clients
- View client details and history
- Add notes to client records
- Track appointments

### Developer Tools Tab
- **Test Runner**: Run automated tests
- **Chat Interface**: Test the AI receptionist
  - Book appointments
  - Cancel appointments
  - Reschedule appointments
  - Query information

## 🔧 API Endpoints

### Public Endpoints
- `POST /twilio/voice` - Twilio voice webhook
- `POST /twilio/sms` - SMS webhook (optional)
- `GET /health` - Health check

### Dashboard API
- `GET /api/stats` - Get dashboard statistics
- `GET /api/clients` - List all clients
- `GET /api/clients/:id` - Get client details
- `POST /api/clients` - Add new client
- `POST /api/clients/:id/notes` - Add client note
- `GET /api/bookings` - List all bookings
- `POST /api/tests/run` - Run test suite
- `POST /api/chat` - Chat with receptionist
- `POST /api/chat/reset` - Reset chat conversation

## 🔐 Security Notes

1. Never commit `.env` file
2. Keep `credentials.json` and `token.json` secure
3. Use environment variables for all secrets
4. Rotate API keys regularly

## 📝 Key Components

### Frontend (Client-Side)
- **Location**: `src/static/`
- **Technology**: Vanilla JavaScript, HTML5, CSS3
- **Purpose**: User interface for managing clients and testing

### Backend (Server-Side)
- **Location**: `src/`
- **Technology**: Flask (Python)
- **Purpose**: API server, webhook handlers, business logic

### Services (Business Logic)
- **Location**: `src/services/`
- **Purpose**: 
  - AI conversation management
  - Calendar integration
  - Speech recognition/synthesis
  - Reminder scheduling
  - Database operations

### Tests (Quality Assurance)
- **Location**: `tests/`
- **Framework**: pytest
- **Purpose**: Automated testing of all components

## 🛠️ Development Workflow

1. **Make Changes**: Edit files in `src/`
2. **Test Changes**: Run relevant tests
3. **Test in Dashboard**: Use chat interface to verify
4. **Check Logs**: Monitor console for errors
5. **Commit**: Use descriptive commit messages

## 📞 Support & Troubleshooting

See documentation in `docs/` folder:
- `ARCHITECTURE.md` - System design
- `DASHBOARD.md` - Dashboard usage
- `REMINDERS.md` - Reminder configuration

## 🎯 Current Status

✅ Working Features:
- Appointment booking via phone
- Google Calendar integration
- SMS/Email reminders
- Client management dashboard
- AI conversation handling
- Date/time parsing
- Business hours validation

✅ All tests configured and passing
✅ File structure organized and documented
