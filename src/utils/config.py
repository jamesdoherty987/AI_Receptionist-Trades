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
    
    # Feature Flags
    USE_GOOGLE_CALENDAR = False  # Database-only by default (scalable for SaaS)
    
    # URLs
    PUBLIC_URL = os.getenv("PUBLIC_URL")
    # WS_PUBLIC_URL: In production (combined server), derive from PUBLIC_URL if not set.
    # The combined server serves WebSocket at /media on the same host as HTTP.
    _ws_url = os.getenv("WS_PUBLIC_URL")
    if not _ws_url and PUBLIC_URL:
        # Convert https://... to wss://... and append /media path
        _ws_url = PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/media"
    WS_PUBLIC_URL = _ws_url
    WS_PATH = os.getenv("WS_PATH", "/media")
    
    # API Keys (configured via environment variables only)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
    ELEVENLABS_FALLBACK_VOICE_ID = os.getenv("ELEVENLABS_FALLBACK_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel as fallback
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    
    # Models
    CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")  # Fast and cost-effective for real-time
    TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
    TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "deepgram")  # elevenlabs or deepgram
    
    # LLM Performance Settings
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.3))  # Lower = more consistent responses
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 150))  # Keep responses concise for phone
    
    # VAD Settings
    VAD_END_SILENCE_MS = int(os.getenv("VAD_END_SILENCE_MS", 900))
    VAD_MIN_SPEECH_MS = int(os.getenv("VAD_MIN_SPEECH_MS", 500))
    VAD_START_ENERGY = int(os.getenv("VAD_START_ENERGY", 1800))
    VAD_CONTINUE_ENERGY = int(os.getenv("VAD_CONTINUE_ENERGY", 1400))
    
    # Barge-in (legacy - kept for compatibility)
    BARGE_IN_ENERGY = int(os.getenv("BARGE_IN_ENERGY", 2600))
    
    # Media Handler - Speech Detection
    SPEECH_ENERGY = int(os.getenv("SPEECH_ENERGY", 1600))
    SILENCE_ENERGY = int(os.getenv("SILENCE_ENERGY", 1000))
    SILENCE_HOLD = float(os.getenv("SILENCE_HOLD", 0.7))
    
    # Media Handler - Interruption Settings
    INTERRUPT_ENERGY = int(os.getenv("INTERRUPT_ENERGY", 2800))
    NO_BARGEIN_WINDOW = float(os.getenv("NO_BARGEIN_WINDOW", 1.5))
    BARGEIN_HOLD = float(os.getenv("BARGEIN_HOLD", 0.4))
    
    # Media Handler - Post-TTS and Speech Processing
    POST_TTS_IGNORE = float(os.getenv("POST_TTS_IGNORE", 0.05))
    MIN_WORDS = int(os.getenv("MIN_WORDS", 1))
    DUPLICATE_WINDOW = float(os.getenv("DUPLICATE_WINDOW", 3.0))
    MIN_SPEECH_DURATION = float(os.getenv("MIN_SPEECH_DURATION", 0.3))
    COMPLETION_WAIT = float(os.getenv("COMPLETION_WAIT", 0.2))
    
    # Media Handler - TTS Settings
    MIN_TOKENS_BEFORE_INTERRUPT = int(os.getenv("MIN_TOKENS_BEFORE_INTERRUPT", 8))
    TTS_TIMEOUT = float(os.getenv("TTS_TIMEOUT", 20.0))
    
    # Media Handler - LLM Processing (filler speech filtering)
    LLM_PROCESSING_TIMEOUT = float(os.getenv("LLM_PROCESSING_TIMEOUT", 8.0))  # Max time to filter filler speech
    
    # Continuation window - allows caller to continue speaking after response starts
    # If speech detected within this window, cancel response and restart with combined text
    # 2s catches natural thinking pauses like "I need to book... um... an appointment for Tuesday"
    # The AI still starts generating immediately - this just allows recovery if caller wasn't done
    CONTINUATION_WINDOW = float(os.getenv("CONTINUATION_WINDOW", 2.0))  # Seconds
    
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
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")  # For voice calls
    TWILIO_SMS_NUMBER = os.getenv("TWILIO_SMS_NUMBER")  # For SMS (can be different from voice number)
    
    # Email (for appointment reminders - works globally)
    # Resend API (recommended - works on all hosts including Render)
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL")  # Must be from verified domain in Resend
    # SMTP fallback (may be blocked on some hosts)
    SMTP_SERVER = os.getenv("SMTP_SERVER")  # e.g., smtp.gmail.com
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Use app password for Gmail
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")  # Must match SMTP auth email
    FROM_EMAIL = os.getenv("FROM_EMAIL")  # Legacy fallback, use SMTP_FROM_EMAIL instead
    REMINDER_METHOD = os.getenv("REMINDER_METHOD", "email")  # "email" or "sms"
    
    # Invoice delivery method: "email" or "sms"
    # When set to "sms", invoices are sent via SMS and email is not required from callers
    INVOICE_DELIVERY_METHOD = os.getenv("INVOICE_DELIVERY_METHOD", "email")
    
    # Stripe Payment
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
    
    # Business branding
    COMPANY_LOGO_URL = os.getenv("COMPANY_LOGO_URL", "")  # URL to company logo for invoices
    
    # Business hours - ONLY defined in database (configure at /settings)
    # These are hardcoded fallbacks only if database is completely unavailable
    BUSINESS_HOURS_START = 9  # Hardcoded fallback only
    BUSINESS_HOURS_END = 17   # Hardcoded fallback only
    # Business days (0=Monday, 6=Sunday)
    BUSINESS_DAYS = [0, 1, 2, 3, 4]  # Monday to Friday (closed weekends)
    
    @staticmethod
    def parse_business_hours_string(hours_str: str) -> dict:
        """Parse business hours from string format like '8 AM - 6 PM Mon-Sat (24/7 emergency available)'"""
        import re
        
        result = {
            'start': Config.BUSINESS_HOURS_START,
            'end': Config.BUSINESS_HOURS_END,
            'days_open': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        }
        
        if not hours_str:
            return result
        
        # Parse time: "8 AM - 6 PM"
        time_match = re.match(r'(\d+)\s*(AM|PM)\s*-\s*(\d+)\s*(AM|PM)', hours_str, re.IGNORECASE)
        if time_match:
            start_hour = int(time_match.group(1))
            start_period = time_match.group(2).upper()
            end_hour = int(time_match.group(3))
            end_period = time_match.group(4).upper()
            
            # Convert to 24-hour format
            if start_period == 'PM' and start_hour != 12:
                start_hour += 12
            elif start_period == 'AM' and start_hour == 12:
                start_hour = 0
            
            if end_period == 'PM' and end_hour != 12:
                end_hour += 12
            elif end_period == 'AM' and end_hour == 12:
                end_hour = 0
            
            result['start'] = start_hour
            result['end'] = end_hour
        
        # Parse days
        hours_lower = hours_str.lower()
        if 'daily' in hours_lower or 'mon-sun' in hours_lower:
            result['days_open'] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        elif 'mon-sat' in hours_lower:
            result['days_open'] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        elif 'mon-fri' in hours_lower:
            result['days_open'] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        else:
            # Parse individual days
            days = []
            day_patterns = [
                ('mon', 'Monday'), ('tue', 'Tuesday'), ('wed', 'Wednesday'),
                ('thu', 'Thursday'), ('fri', 'Friday'), ('sat', 'Saturday'), ('sun', 'Sunday')
            ]
            for abbrev, full in day_patterns:
                if abbrev in hours_lower:
                    days.append(full)
            if days:
                result['days_open'] = days
        
        return result
    
    @staticmethod
    def get_business_hours(company_id: int = None):
        """Get business hours from database settings or fallback to env"""
        try:
            from src.services.database import get_database
            db = get_database()
            
            # Try to get from company's business_hours string first
            if company_id:
                company = db.get_company(company_id)
                if company and company.get('business_hours'):
                    return Config.parse_business_hours_string(company['business_hours'])
            
            # Fallback to business_settings table
            from src.services.settings_manager import get_settings_manager
            settings_mgr = get_settings_manager()
            settings = settings_mgr.get_business_settings(company_id=company_id)
            
            if settings:
                # Check if there's a business_hours string in settings
                if settings.get('business_hours'):
                    return Config.parse_business_hours_string(settings['business_hours'])
                
                # Parse days_open if it's a string
                days_open = settings.get('days_open', [])
                if isinstance(days_open, str):
                    import json
                    days_open = json.loads(days_open)
                
                return {
                    'start': settings.get('opening_hours_start', Config.BUSINESS_HOURS_START),
                    'end': settings.get('opening_hours_end', Config.BUSINESS_HOURS_END),
                    'days_open': days_open if days_open else ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                }
        except Exception as e:
            print(f"[WARNING] Could not load business hours from database: {e}")
        
        # Fallback to env
        return {
            'start': Config.BUSINESS_HOURS_START,
            'end': Config.BUSINESS_HOURS_END,
            'days_open': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        }
    
    @staticmethod
    def get_business_days_indices(company_id: int = None):
        """Get business days as weekday indices (0=Monday, 6=Sunday) from database"""
        try:
            hours = Config.get_business_hours(company_id=company_id)
            days_open = hours.get('days_open', [])
            day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 
                      'Friday': 4, 'Saturday': 5, 'Sunday': 6}
            return [day_map[day] for day in days_open if day in day_map]
        except:
            return Config.BUSINESS_DAYS
    
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
