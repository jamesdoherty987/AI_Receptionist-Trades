"""
Configuration management for AI Receptionist
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    """Centralized configuration management"""
    
    # Flask
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    PORT = int(os.getenv("PORT", 5000))
    
    # URLs
    PUBLIC_URL = os.getenv("PUBLIC_URL")
    WS_PUBLIC_URL = os.getenv("WS_PUBLIC_URL")
    WS_PATH = os.getenv("WS_PATH", "/media")
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    
    # Models
    CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
    TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "deepgram")  # elevenlabs or deepgram
    
    # VAD Settings
    VAD_END_SILENCE_MS = int(os.getenv("VAD_END_SILENCE_MS", 900))
    VAD_MIN_SPEECH_MS = int(os.getenv("VAD_MIN_SPEECH_MS", 500))
    VAD_START_ENERGY = int(os.getenv("VAD_START_ENERGY", 1800))
    VAD_CONTINUE_ENERGY = int(os.getenv("VAD_CONTINUE_ENERGY", 1400))
    
    # Barge-in
    BARGE_IN_ENERGY = int(os.getenv("BARGE_IN_ENERGY", 2600))
    
    # TTS Chunk Sizes
    MIN_TTS_CHUNK_CHARS = int(os.getenv("MIN_TTS_CHUNK_CHARS", 20))
    MAX_TTS_CHUNK_CHARS = int(os.getenv("MAX_TTS_CHUNK_CHARS", 120))
    
    # Google Calendar (optional)
    GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "config/credentials.json")
    GOOGLE_CALENDAR_TOKEN = os.getenv("GOOGLE_CALENDAR_TOKEN", "config/token.json")
    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    CALENDAR_TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "Europe/Dublin")
    
    # Twilio (for SMS reminders - check regional availability)
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
    
    # Email (for appointment reminders - works globally)
    SMTP_SERVER = os.getenv("SMTP_SERVER")  # e.g., smtp.gmail.com
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Use app password for Gmail
    FROM_EMAIL = os.getenv("FROM_EMAIL")
    REMINDER_METHOD = os.getenv("REMINDER_METHOD", "email")  # "email" or "sms"
    
    # Business hours (24-hour format)
    BUSINESS_HOURS_START = int(os.getenv("BUSINESS_HOURS_START", 9))
    BUSINESS_HOURS_END = int(os.getenv("BUSINESS_HOURS_END", 17))
    # Business days (0=Monday, 6=Sunday)
    BUSINESS_DAYS = [0, 1, 2, 3, 4]  # Monday to Friday (closed weekends)
    
    # Financial settings
    DEFAULT_APPOINTMENT_CHARGE = float(os.getenv("DEFAULT_APPOINTMENT_CHARGE", 50.0))
    
    # Audio settings (Twilio-specific requirements)
    AUDIO_SAMPLE_RATE = 8000  # Twilio requires 8kHz for mulaw
    AUDIO_ENCODING = "mulaw"  # Twilio voice encoding
    AUDIO_CHANNELS = 1  # Mono audio
    
    # Polling and refresh intervals (milliseconds)
    NOTIFICATION_POLL_INTERVAL = int(os.getenv("NOTIFICATION_POLL_INTERVAL", 30000))  # 30 seconds
    TTS_CHUNK_DELAY = float(os.getenv("TTS_CHUNK_DELAY", 0.25))  # 250ms between chunks
    
    # Appointment scheduling limits
    MAX_BOOKING_DAYS_AHEAD = int(os.getenv("MAX_BOOKING_DAYS_AHEAD", 90))  # 3 months
    APPOINTMENT_SLOT_DURATION = int(os.getenv("APPOINTMENT_SLOT_DURATION", 60))  # minutes
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            "OPENAI_API_KEY",
            "DEEPGRAM_API_KEY",
            "WS_PUBLIC_URL"
        ]
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


config = Config()
