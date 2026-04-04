# BookedForYou — AI Receptionist for Trades Companies

Professional AI-powered phone receptionist with job booking, worker management, and Google Calendar integration — built for plumbing, electrical, heating, and general trade businesses.

## Features

- ☎️ Real-time phone conversations via Twilio Media Streams
- 🤖 Natural language AI using OpenAI GPT-4o-mini with function calling
- 🎤 Speech recognition powered by Deepgram ASR
- 🗣️ Text-to-speech with Deepgram (ElevenLabs fallback)
- 📊 React dashboard — jobs, workers, customers, calendar, call logs, finances, materials, services, insights
- 🔧 Intelligent job booking (emergency / same-day / scheduled / quotes / multi-day)
- 📆 Google Calendar integration with availability checking and bidirectional sync
- 👷 Worker management — assign jobs, track availability, time-off, per-worker calendars
- 💳 Stripe Connect — subscriptions, invoicing with payment links
- 📱 Automatic phone & email capture with validation
- 📍 Address collection with Eircode support and AI re-transcription
- ⚡ Urgency assessment (Emergency / Same-Day / Scheduled / Quote)
- 🏠 Property type tracking (Residential / Commercial)
- 🔔 Email and SMS reminders 24 hours before jobs
- 💬 Reminder confirmations via email or SMS replies
- 🚫 Barge-in / interrupt handling for natural conversations
- 📸 Job photos with Cloudflare R2 storage
- 🧾 Invoice generation and delivery (email / SMS)
- ⚙️ Settings management — business hours, services, pricing, packages, feature toggles
- 🔐 Auth with password hashing (bcrypt), rate limiting, OWASP security headers
- 👨‍🔧 Worker portal — separate login, dashboard, notifications, set-password flow
- 🎬 Remotion video generation for marketing content

## Quick Start

### 1. Install Dependencies

Backend:
```bash
pip install -r requirements.txt
```

Frontend:
```bash
cd frontend
npm install
```

### 2. Environment Variables

Copy `.env.example` or create a `.env` in the project root. Key variables:

```env
# OpenAI
OPENAI_API_KEY=

# Deepgram
DEEPGRAM_API_KEY=

# ElevenLabs (optional fallback TTS)
ELEVENLABS_API_KEY=

# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_SMS_NUMBER=

# Database (PostgreSQL for production, SQLite used automatically in local dev)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Stripe
STRIPE_SECRET_KEY=
STRIPE_PRICE_ID=
STRIPE_WEBHOOK_SECRET=
STRIPE_CONNECT_WEBHOOK_SECRET=

# Cloudflare R2 (job photo storage)
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_ACCOUNT_ID=
R2_BUCKET_NAME=
R2_PUBLIC_URL=

# Email (Resend for transactional, SMTP for reminders)
RESEND_API_KEY=
RESEND_FROM_EMAIL=
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=

# Google Calendar
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
CALENDAR_ID=primary
CALENDAR_TIMEZONE=Europe/Dublin

# URLs (production)
PUBLIC_URL=https://your-backend.onrender.com
WS_PUBLIC_URL=wss://your-backend.onrender.com/media

# App
SECRET_KEY=
FLASK_ENV=local
PORT=5000
TTS_PROVIDER=deepgram
```

### 3. Start Development

Local development uses SQLite automatically — no database setup needed.

```bash
# Terminal 1 — Backend
python src/app.py

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Dashboard at http://localhost:3000. The Vite dev server proxies `/api` and `/twilio` requests to the Flask backend on port 5000.

### 4. Production

Production runs a combined HTTP + WebSocket server via Starlette/Uvicorn on a single port:

```bash
uvicorn src.server:app --host 0.0.0.0 --port 5000
```

This serves the Flask API, Twilio webhooks, Stripe webhooks, and the Twilio Media Stream WebSocket (`/media`) all on one port — required for platforms like Render that expose a single port.

## Project Structure

```
├── frontend/                        # React dashboard (Vite)
│   └── src/
│       ├── components/
│       │   ├── dashboard/           # Tab components (Jobs, Workers, Calendar, etc.)
│       │   └── modals/              # AddJob, AddClient, JobDetail, Invoice, etc.
│       ├── context/                 # AuthContext
│       ├── pages/                   # Landing, Login, Signup, Dashboard, Settings,
│       │                            #   WorkerDashboard, WorkerLogin, ForgotPassword, etc.
│       ├── services/api.js          # HTTP client
│       └── utils/                   # Helpers, duration options, security
├── src/                             # Python backend
│   ├── app.py                       # Flask server (API routes, auth, webhooks)
│   ├── server.py                    # Combined ASGI server (HTTP + WebSocket)
│   ├── media_ws.py                  # Standalone WebSocket server (local dev)
│   ├── handlers/
│   │   └── media_handler.py         # Real-time audio pipeline (ASR → LLM → TTS)
│   ├── services/
│   │   ├── asr_deepgram.py          # Speech-to-text
│   │   ├── tts_deepgram.py          # Text-to-speech (Deepgram)
│   │   ├── tts_elevenlabs.py        # Text-to-speech (ElevenLabs fallback)
│   │   ├── llm_stream.py            # AI conversation with function calling
│   │   ├── google_calendar.py       # Google Calendar CRUD
│   │   ├── google_calendar_oauth.py # Per-user OAuth flow
│   │   ├── database_calendar.py     # Database-backed calendar
│   │   ├── calendar_tools.py        # Calendar utilities
│   │   ├── database.py              # Database abstraction (SQLite / PostgreSQL)
│   │   ├── db_postgres_wrapper.py   # PostgreSQL wrapper
│   │   ├── settings_manager.py      # Business settings
│   │   ├── sms_reminder.py          # SMS reminders (Twilio)
│   │   ├── email_reminder.py        # Email reminders (SMTP)
│   │   ├── reminder_scheduler.py    # Reminder scheduling
│   │   ├── stripe_service.py        # Stripe subscriptions
│   │   ├── stripe_connect_service.py # Stripe Connect (invoicing)
│   │   ├── storage_r2.py            # Cloudflare R2 file storage
│   │   ├── call_state.py            # Per-call conversation state
│   │   ├── call_summarizer.py       # Post-call AI summaries
│   │   ├── address_retranscriber.py # AI address correction
│   │   ├── client_description_generator.py
│   │   ├── appointment_auto_complete.py
│   │   ├── prerecorded_audio.py     # Pre-recorded audio playback
│   │   └── service_matcher.py       # (via llm_stream)
│   └── utils/
│       ├── security.py              # Hashing, rate limiting, OWASP headers
│       ├── config.py                # Environment config loader
│       ├── date_parser.py           # Natural language date parsing
│       ├── address_validator.py     # Address / Eircode validation
│       ├── duration_utils.py        # Job duration helpers
│       ├── audio_utils.py           # Audio processing
│       └── ai_logger.py            # AI interaction logging
├── prompts/
│   └── receptionist_prompt_fast.txt # Main AI system prompt
├── db_scripts/                      # Database migrations and utilities
├── scripts/                         # Dev utilities (demo call, filler audio, migration)
├── tests/                           # 50+ pytest test files
├── video/                           # Remotion video generation (marketing)
├── report/                          # LaTeX report
├── config/                          # Runtime config (generated at runtime)
├── .env                             # Environment variables
├── requirements.txt                 # Python dependencies
└── ngrok.yml.example                # Ngrok tunnel config template
```

## Database

- Local dev: SQLite (automatic, no setup)
- Production: PostgreSQL (set `DATABASE_URL` in `.env`)

Migration scripts live in `db_scripts/`. Run them directly:
```bash
python db_scripts/add_worker_accounts_table.py
python db_scripts/add_packages_table.py
# etc.
```

Phone number management:
```bash
python db_scripts/add_phone_numbers_production.py +353123456789
python db_scripts/add_phone_numbers_production.py --list
```

## Twilio Setup

Users don't configure Twilio credentials directly. Phone numbers are managed in a pool:

1. Add numbers to the pool via `db_scripts/manage_phone_numbers.py` or `db_scripts/add_phone_numbers_production.py`
2. When users sign up, they're automatically assigned a number from the pool
3. Configure webhooks in the Twilio Console for each number:
   - Voice webhook: `https://your-backend.onrender.com/twilio/voice` (POST)
   - The WebSocket media stream is handled automatically via `server.py`

## Google Calendar

Per-user OAuth flow — each business connects their own Google Calendar from the Settings page. The backend handles token storage and refresh via `google_calendar_oauth.py`.

## Testing

```bash
pytest tests/
```

50+ test files covering booking flows, cancellation/rescheduling, worker availability, service matching, reminders, security, data isolation, Stripe subscriptions, Google Calendar sync, and more.

## Architecture

```
Phone Call → Twilio → Flask Webhook → WebSocket (Twilio Media Stream)
                                          ↓
                                    media_handler.py
                                          ↓
                          ┌───────────────┼───────────────┐
                          ↓               ↓               ↓
                    Deepgram ASR    LLM (GPT-4o-mini)   Calendar
                     (speech→text)  (function calling)  (availability)
                          ↓               ↓               ↓
                          └───────→ AI Response ←─────────┘
                                          ↓
                                   TTS (Deepgram)
                                          ↓
                                Audio → Twilio → Phone
```

## Local Dev with Ngrok

For testing phone calls locally, use ngrok to tunnel traffic. Copy `ngrok.yml.example` to `ngrok.yml`, add your auth token, then:

```bash
ngrok start --config=ngrok.yml --all
```

Update your `.env` with the ngrok URLs for `PUBLIC_URL` and `WS_PUBLIC_URL`.

## License

Proprietary — BookedForYou
