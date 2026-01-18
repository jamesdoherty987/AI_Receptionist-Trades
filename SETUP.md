# Setup Guide

Complete setup instructions for the AI Receptionist system.

## Prerequisites

- Python 3.9 or higher
- Google Account (for Calendar API)
- Twilio Account (for phone integration)
- OpenAI API key
- Deepgram API key
- ElevenLabs API key (optional, can use Deepgram TTS)
- Ngrok account (for public URLs)

## Step-by-Step Setup

### 1. Clone and Install

```bash
# Clone the repository
git clone <repository-url>
cd AI-Receptionist

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# ============================================
# API KEYS
# ============================================

# OpenAI (required)
OPENAI_API_KEY=sk-your-openai-api-key-here
CHAT_MODEL=gpt-4o-mini

# Deepgram (required)
DEEPGRAM_API_KEY=your-deepgram-api-key-here

# ElevenLabs (optional - can use Deepgram TTS instead)
ELEVENLABS_API_KEY=your-elevenlabs-api-key-here
ELEVENLABS_VOICE_ID=your-voice-id-here

# ============================================
# TWILIO & NGROK
# ============================================

# Public URLs (update after running ngrok)
PUBLIC_URL=https://your-ngrok-subdomain.ngrok.io
WS_PUBLIC_URL=wss://your-ngrok-subdomain.ngrok.io/ws

# ============================================
# GOOGLE CALENDAR
# ============================================

CALENDAR_ID=primary
CALENDAR_TIMEZONE=Europe/Dublin

# ============================================
# BUSINESS CONFIGURATION
# ============================================

# Business hours (24-hour format)
BUSINESS_HOURS_START=9
BUSINESS_HOURS_END=17

# TTS Provider (deepgram or elevenlabs)
TTS_PROVIDER=deepgram
```

### 3. Set Up Google Calendar

#### 3.1. Get Google Calendar Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Calendar API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Desktop app"
   - Download the JSON file
5. Save as `config/credentials.json`

#### 3.2. Authenticate

```bash
python scripts/setup_calendar.py
```

This will:
- Open a browser window for Google authentication
- Request calendar access permissions
- Save the token to `config/token.json`
- Test the connection

### 4. Configure Business Information

Edit `config/business_info.json` with your business details:

```json
{
  "business_name": "Your Business Name",
  "staff": {
    "primary_practitioner": "Your Name"
  },
  "location": {
    "address": "Your Full Address",
    "parking": "Parking instructions for customers"
  },
  "services": {
    "offerings": [
      "Service 1",
      "Service 2",
      "Service 3"
    ]
  },
  "pricing": {
    "standard_appointment": "€50",
    "payment_methods": ["cash", "card", "Apple Pay"]
  }
}
```

### 5. Set Up Ngrok

#### 5.1. Install Ngrok

Download from [ngrok.com](https://ngrok.com) and install.

#### 5.2. Configure Ngrok

The `ngrok.yml` file is already configured:

```yaml
version: "2"
authtoken: YOUR_NGROK_AUTH_TOKEN  # Update this
tunnels:
  flask:
    addr: 5050
    proto: http
  websocket:
    addr: 8000
    proto: http
```

Update `authtoken` with your ngrok auth token from [ngrok.com/dashboard](https://dashboard.ngrok.com).

### 6. Set Up Twilio

1. Go to [Twilio Console](https://console.twilio.com/)
2. Get a phone number (or use existing)
3. Configure the number:
   - Under "Voice & Fax"
   - Set "A CALL COMES IN" webhook to: `https://YOUR_PUBLIC_URL/twilio/voice`
   - Method: `POST`
4. Save

### 7. Test the System

Before running the full system, test with the text interface:

```bash
python scripts/chat_test.py
```

Try these test cases:
- "Hi, I'm John Doe and I want to book for tomorrow at 2pm for back pain"
- "Can I reschedule my appointment to Friday at 3pm?"
- "I need to cancel my appointment"

### 8. Run the Application

Open 3 terminal windows:

**Terminal 1 - Flask Server:**
```bash
python src/app.py
```
Should show: `Running on http://0.0.0.0:5050`

**Terminal 2 - WebSocket Server:**
```bash
python src/media_ws.py
```
Should show: `WebSocket server listening on 0.0.0.0:8000`

**Terminal 3 - Ngrok:**
```bash
ngrok start --config=ngrok.yml --all
```
Should show two forwarding URLs.

### 9. Update Environment with Ngrok URLs

After ngrok starts, you'll see:
```
flask     https://abc123.ngrok.io -> http://localhost:5050
websocket https://xyz789.ngrok.io -> http://localhost:8000
```

Update `.env`:
```env
PUBLIC_URL=https://abc123.ngrok.io
WS_PUBLIC_URL=wss://xyz789.ngrok.io/ws
```

Restart Flask server (Terminal 1) to pick up new URLs.

### 10. Make a Test Call

1. Call your Twilio phone number
2. The AI receptionist should answer
3. Try: "Hi, I'd like to book an appointment for tomorrow at 2pm"

## Verification Checklist

- [ ] Python virtual environment activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured with all API keys
- [ ] Google Calendar authenticated (`python scripts/setup_calendar.py`)
- [ ] `config/business_info.json` updated with your business details
- [ ] Ngrok auth token configured in `ngrok.yml`
- [ ] Flask server running on port 5050
- [ ] WebSocket server running on port 8000
- [ ] Ngrok tunnels active
- [ ] `.env` updated with ngrok URLs
- [ ] Twilio webhook configured
- [ ] Test call successful

## Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "Could not authenticate with Google Calendar"
```bash
python scripts/setup_calendar.py
```

### "Connection refused" errors
- Check all three servers are running (Flask, WebSocket, Ngrok)
- Verify ports 5050 and 8000 are not in use

### "Invalid API key" errors
- Double-check API keys in `.env`
- Ensure no extra spaces or quotes around keys

### Ngrok URLs not working
- Make sure ngrok is running
- Update `.env` with correct URLs
- Restart Flask server after updating `.env`

### Appointment not booking
- Verify Google Calendar authentication
- Check business hours in `.env`
- Test with `python scripts/chat_test.py` first

## Next Steps

After successful setup:

1. **Customize the prompt:** Edit `prompts/receptionist_prompt.txt`
2. **Adjust business hours:** Update `.env` BUSINESS_HOURS_START/END
3. **Change voice:** Update ELEVENLABS_VOICE_ID in `.env`
4. **Test thoroughly:** Use `python scripts/chat_test.py` for rapid iteration
5. **Monitor logs:** Watch terminal output during calls for debugging

## Production Considerations

For production deployment:

- Use a production OpenAI API key
- Set up Twilio production phone number
- Use ngrok paid plan or deploy to a server with static IP
- Set up monitoring and logging
- Configure backup/redundancy for Google Calendar credentials
- Set up error alerting
- Consider rate limiting on API calls

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review test output from `scripts/chat_test.py`
3. Check terminal logs for error messages
4. Verify all API keys are valid and have sufficient credits
