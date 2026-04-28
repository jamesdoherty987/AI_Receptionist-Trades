"""
Flask application for Telnyx TeXML voice webhook
Secured against OWASP Top 10 vulnerabilities
"""
# Set process timezone to business timezone so datetime.now() returns local time.
# This must happen before any datetime usage.
import os
import time as _time
if not os.environ.get("TZ"):
    os.environ["TZ"] = os.getenv("CALENDAR_TIMEZONE", "Europe/Dublin")
    if hasattr(_time, 'tzset'):
        _time.tzset()

import sys
import secrets
import stripe
from pathlib import Path
from functools import wraps
import io

# Configure UTF-8 encoding for Windows console to prevent OSError with special characters
if sys.platform == 'win32':
    # Reconfigure stdout and stderr to use UTF-8 encoding with error handling
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    # Set environment variable for subprocesses
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Safe print function for Windows - handles encoding errors gracefully
def safe_print(*args, **kwargs):
    """Print function that handles encoding errors on Windows"""
    try:
        print(*args, **kwargs)
    except (UnicodeEncodeError, OSError) as e:
        # If encoding fails, print a safe message instead
        try:
            print(f"[PRINT ERROR] Could not print message due to encoding issue: {type(e).__name__}")
        except:
            pass  # If even this fails, silently continue

from flask import Flask, Response, request, jsonify, session, g
from flask_cors import CORS
# VoiceResponse/MessagingResponse generate XML that is compatible with both
# Twilio TwiML and Telnyx TeXML — we keep using the twilio package as an XML builder.
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from src.utils.config import config
from src.services.database import get_database
from src.utils.security import (
    hash_password, verify_password, needs_rehash,
    get_rate_limiter, get_security_logger,
    sanitize_string, validate_email,
    apply_security_headers, configure_secure_session,
)
# Google Calendar disabled - USE_GOOGLE_CALENDAR = False


def _validate_password(password: str) -> str | None:
    """
    Validate password strength (OWASP recommendations).
    Returns an error message string if invalid, or None if valid.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 128:
        return "Password is too long"
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_upper and has_lower and has_digit):
        return "Password must contain at least one uppercase letter, one lowercase letter, and one number"
    return None

# Set up Flask to serve React build or development files
static_folder = Path(__file__).parent / "static" / "dist"
if not static_folder.exists():
    # Fallback to regular static folder during development
    static_folder = Path(__file__).parent / "static"

app = Flask(__name__, 
            static_folder=str(static_folder),
            static_url_path='')

# Configure CORS - environment-aware origins
_is_production = os.getenv('FLASK_ENV') == 'production'

_production_origins = [
    "https://www.bookedforyou.info",
    "https://bookedforyou.info",
    "https://www.bookedforyou.ie",
    "https://bookedforyou.ie",
]

_dev_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5000",
]

allowed_origins = _production_origins if _is_production else _production_origins + _dev_origins

# Add ngrok URLs from environment if present
public_url = os.getenv('PUBLIC_URL')
if public_url:
    allowed_origins.append(public_url)
    # Also add without https:// prefix variations
    if public_url.startswith('https://'):
        allowed_origins.append(public_url.replace('https://', 'http://'))

CORS(app, resources={r"/api/*": {
    "origins": allowed_origins,
    "allow_headers": ["Content-Type", "X-Auth-Token", "X-Admin-Secret"],
    "expose_headers": ["X-Auth-Token"],
}}, supports_credentials=True)

# Configure secure session
# In production, SECRET_KEY MUST be set — fail fast if missing
if os.getenv('FLASK_ENV') == 'production' and not os.getenv('SECRET_KEY'):
    raise RuntimeError(
        "FATAL: SECRET_KEY environment variable is required in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
configure_secure_session(app)

if not os.getenv('SECRET_KEY'):
    print("⚠️ WARNING: SECRET_KEY not set. Sessions will reset on restart.")

# --- Auth token helpers (fallback for cross-origin cookie issues) ---
_token_serializer = URLSafeTimedSerializer(app.secret_key, salt='auth-token')

def generate_auth_token(company_id: int, email: str) -> str:
    """Generate a signed auth token encoding company_id and email."""
    return _token_serializer.dumps({'cid': company_id, 'email': email})

def verify_auth_token(token: str, max_age: int = 432000) -> dict | None:
    """Verify and decode an auth token. Returns payload or None.
    max_age=432000 = 5 days, matching PERMANENT_SESSION_LIFETIME."""
    try:
        return _token_serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

# Security: Add security headers to all responses
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response = apply_security_headers(response)
    
    # Log Set-Cookie headers for auth endpoints (debugging)
    if request.path.startswith('/api/auth/') and 'Set-Cookie' in response.headers:
        cookie_header = response.headers.get('Set-Cookie', '')
        # Don't log the actual cookie value, just the attributes
        cookie_attrs = [attr.split('=')[0] for attr in cookie_header.split(';')]
        print(f"[COOKIE] Setting cookie for {request.path}: {', '.join(cookie_attrs)}")
    
    return response

# Security: Log request details for security monitoring
@app.before_request
def log_request():
    """Log request for security monitoring"""
    g.request_start_time = __import__('time').time()
    g.client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if g.client_ip and ',' in g.client_ip:
        g.client_ip = g.client_ip.split(',')[0].strip()
    
    # Log authentication requests for debugging
    if request.path.startswith('/api/auth/'):
        origin = request.headers.get('Origin', 'no-origin')
        has_cookie = 'session' in request.cookies
        print(f"[AUTH_REQUEST] {request.method} {request.path} from {origin} - Has session cookie: {has_cookie}")


def get_client_ip():
    """Get the real client IP address"""
    return getattr(g, 'client_ip', request.remote_addr)


def login_required(f):
    """Decorator to require login for API endpoints.
    Checks Flask session cookie first, falls back to X-Auth-Token header
    (needed when cross-origin cookies are blocked by the browser).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Try session cookie (preferred)
        company_id = session.get('company_id')
        if company_id and isinstance(company_id, int):
            return f(*args, **kwargs)

        # 2. Fallback: signed auth token header
        token = request.headers.get('X-Auth-Token')
        if token:
            payload = verify_auth_token(token)
            if payload and payload.get('cid'):
                # Populate session from token so downstream code works unchanged
                session['company_id'] = payload['cid']
                session['email'] = payload['email']
                return f(*args, **kwargs)

        get_security_logger().log_failed_auth(
            request.path,
            get_client_ip(),
            'No session or valid token'
        )
        return jsonify({"error": "Authentication required"}), 401
    return decorated_function


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """Decorator for rate limiting API endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            limiter = get_rate_limiter()
            ip = get_client_ip()
            
            # Use IP + endpoint as key so rate limits are per-endpoint
            rate_key = f"{ip}:{request.path}"
            
            allowed, remaining = limiter.check_rate_limit(
                rate_key, max_requests, window_seconds
            )
            
            if not allowed:
                get_security_logger().log_rate_limit(ip, request.path)
                return jsonify({
                    "error": "Too many requests. Please try again later."
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================
# IMAGE UPLOAD HELPER (R2 STORAGE)
# ============================================

# Maximum upload size: 5MB
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}


def upload_base64_image_to_r2(base64_data: str, company_id: int, file_type: str = 'images') -> str:
    """
    Upload a base64 image to R2 storage with size and type validation.
    
    Args:
        base64_data: Base64 encoded image data (e.g., 'data:image/png;base64,...')
        company_id: Company ID for folder separation
        file_type: Type of file (logos, employees, services, etc.)
    
    Returns:
        R2 public URL if successful, or original base64 if R2 fails/not configured
    """
    if not base64_data or not base64_data.startswith('data:image/'):
        return base64_data or ''
    
    try:
        from src.services.storage_r2 import upload_company_file, is_r2_enabled
        import base64
        import io
        from datetime import datetime
        
        if not is_r2_enabled():
            print("⚠️ R2 not configured, image will be stored as base64 in database")
            return base64_data
        
        # Extract and validate content type
        header, encoded = base64_data.split(',', 1)
        content_type = header.split(';')[0].split(':')[1]
        
        if content_type not in ALLOWED_IMAGE_TYPES:
            print(f"[WARNING] Rejected upload: unsupported type {content_type}")
            return ''
        
        extension = content_type.split('/')[-1]
        image_data = base64.b64decode(encoded)
        
        # Enforce size limit
        if len(image_data) > MAX_IMAGE_SIZE_BYTES:
            print(f"[WARNING] Rejected upload: {len(image_data)} bytes exceeds {MAX_IMAGE_SIZE_BYTES} limit")
            return ''
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{file_type}_{timestamp}_{secrets.token_hex(4)}.{extension}"
        
        public_url = upload_company_file(
            company_id=company_id,
            file_data=io.BytesIO(image_data),
            filename=filename,
            file_type=file_type,
            content_type=content_type
        )
        
        if public_url:
            print(f"[SUCCESS] Image uploaded to R2: {public_url}")
            return public_url
        else:
            print("⚠️ R2 upload returned None, storing as base64")
            return base64_data
            
    except Exception as e:
        print(f"[WARNING] R2 upload failed, storing as base64: {e}")
        return base64_data


# Flag to track if scheduler has been started (for employee-based initialization)
_scheduler_started = False

def start_scheduler_once():
    """Start the auto-complete scheduler only once across all employees.
    Uses a simple file lock to ensure only one employee starts the scheduler.
    """
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    
    # Use file-based locking to ensure only one employee starts the scheduler
    # This works with uvicorn, gunicorn, and any multi-employee setup
    import tempfile
    import fcntl
    
    lock_file = os.path.join(tempfile.gettempdir(), 'bookedforyou_scheduler.lock')
    
    try:
        # Try to acquire exclusive lock (non-blocking)
        lock_fd = open(lock_file, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # We got the lock - this employee starts the scheduler
        # NOTE: Auto-complete scheduler removed — employees now manually mark jobs complete
        
        # Start SMS day-before reminder scheduler (sends at 5 PM daily)
        try:
            from src.services.sms_reminder import start_sms_reminder_scheduler
            start_sms_reminder_scheduler(check_hour=17)
            print("✅ SMS day-before reminder scheduler started\\n")
        except Exception as e:
            print(f"[WARNING] Could not start SMS reminder scheduler: {e}\\n")
        
        # Keep lock file open to maintain the lock
        # Don't close lock_fd - we want to keep the lock for the lifetime of this employee
        
    except (IOError, OSError):
        # Another employee already has the lock - that's fine
        print("[INFO] Scheduler already running in another worker\\n")
        try:
            lock_fd.close()
        except:
            pass


# ============================================
# Subscription helpers (must be defined before routes that use @subscription_required)
# ============================================

def get_subscription_info(company: dict) -> dict:
    """Get comprehensive subscription info for a company"""
    now = datetime.now()
    
    subscription_tier = company.get('subscription_tier', 'none')
    subscription_status = company.get('subscription_status', 'inactive')
    trial_end = company.get('trial_end')
    current_period_end = company.get('subscription_current_period_end')
    cancel_at_period_end = bool(company.get('subscription_cancel_at_period_end', 0))
    
    print(f"[GET_SUB_INFO] Company {company.get('id')} raw data:")
    print(f"[GET_SUB_INFO]   - subscription_tier: {subscription_tier}")
    print(f"[GET_SUB_INFO]   - subscription_status: {subscription_status}")
    print(f"[GET_SUB_INFO]   - trial_end: {trial_end}")
    print(f"[GET_SUB_INFO]   - current_period_end: {current_period_end}")
    print(f"[GET_SUB_INFO]   - cancel_at_period_end: {cancel_at_period_end}")
    print(f"[GET_SUB_INFO]   - stripe_customer_id: {company.get('stripe_customer_id')}")
    print(f"[GET_SUB_INFO]   - stripe_subscription_id: {company.get('stripe_subscription_id')}")
    
    # Parse dates if they're strings and ensure they're timezone-naive for comparison
    if isinstance(trial_end, str):
        try:
            parsed = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
            # Convert to naive datetime for comparison with datetime.now()
            trial_end = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except:
            trial_end = None
    elif trial_end and hasattr(trial_end, 'tzinfo') and trial_end.tzinfo:
        # If it's already a datetime with timezone, make it naive
        trial_end = trial_end.replace(tzinfo=None)
    
    if isinstance(current_period_end, str):
        try:
            parsed = datetime.fromisoformat(current_period_end.replace('Z', '+00:00'))
            current_period_end = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except:
            current_period_end = None
    elif current_period_end and hasattr(current_period_end, 'tzinfo') and current_period_end.tzinfo:
        current_period_end = current_period_end.replace(tzinfo=None)
    
    # Normalize legacy tier names (must happen before any tier-dependent logic)
    if subscription_tier == 'professional':
        subscription_tier = 'pro'
    
    # Calculate trial days remaining (round up to include partial days)
    trial_days_remaining = 0
    if subscription_tier == 'trial' and trial_end:
        # Calculate days remaining, rounding up for partial days
        import math
        seconds_remaining = (trial_end - now).total_seconds()
        if seconds_remaining > 0:
            trial_days_remaining = math.ceil(seconds_remaining / 86400)
        else:
            trial_days_remaining = 0
    
    # Determine if subscription is active (can use the app)
    is_active = False
    if subscription_tier == 'trial':
        is_active = bool(trial_end and trial_end > now)
        print(f"[GET_SUB_INFO] Trial check: trial_end={trial_end}, now={now}, is_active={is_active}")
        # Fix stale subscription_status in DB when trial has expired
        if not is_active and subscription_status == 'active' and company.get('id'):
            try:
                db = get_database()
                db.update_company(company['id'], subscription_status='expired')
                subscription_status = 'expired'
                print(f"[GET_SUB_INFO] Updated stale subscription_status to 'expired' for company {company['id']}")
            except Exception as e:
                print(f"[GET_SUB_INFO] Failed to update stale status: {e}")
    elif subscription_tier == 'pro':
        # Pro is active if status is active, trialing, or past_due (grace period)
        is_active = subscription_status in ('active', 'trialing', 'past_due')
        print(f"[GET_SUB_INFO] Pro check: status={subscription_status}, is_active={is_active}")
    else:
        print(f"[GET_SUB_INFO] Unknown tier '{subscription_tier}', is_active=False")
    
    # Usage tracking
    included_minutes = company.get('included_minutes', 200)
    overage_rate_cents = company.get('overage_rate_cents', 12)
    minutes_used = company.get('minutes_used', 0)
    usage_period_start = company.get('usage_period_start')
    usage_period_end = company.get('usage_period_end')
    usage_alert_sent = bool(company.get('usage_alert_sent', False))

    # Parse usage period dates (fix: direct assignment, locals() mutation doesn't work)
    if isinstance(usage_period_start, str):
        try:
            parsed = datetime.fromisoformat(usage_period_start.replace('Z', '+00:00'))
            usage_period_start = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except Exception:
            usage_period_start = None
    elif usage_period_start and hasattr(usage_period_start, 'tzinfo') and usage_period_start.tzinfo:
        usage_period_start = usage_period_start.replace(tzinfo=None)

    if isinstance(usage_period_end, str):
        try:
            parsed = datetime.fromisoformat(usage_period_end.replace('Z', '+00:00'))
            usage_period_end = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except Exception:
            usage_period_end = None
    elif usage_period_end and hasattr(usage_period_end, 'tzinfo') and usage_period_end.tzinfo:
        usage_period_end = usage_period_end.replace(tzinfo=None)

    overage_minutes = max(0, minutes_used - included_minutes)
    overage_cost_cents = overage_minutes * overage_rate_cents

    result = {
        'tier': subscription_tier,
        'status': subscription_status,
        'is_active': is_active,
        'plan': company.get('subscription_plan', 'pro'),
        'trial_end': trial_end.isoformat() if trial_end else None,
        'trial_days_remaining': trial_days_remaining,
        'current_period_end': current_period_end.isoformat() if current_period_end else None,
        'cancel_at_period_end': cancel_at_period_end,
        'has_used_trial': bool(company.get('has_used_trial', 0)) or bool(company.get('trial_start')),
        'stripe_customer_id': company.get('stripe_customer_id'),
        'stripe_subscription_id': company.get('stripe_subscription_id'),
        'custom_monthly_price': float(company['custom_monthly_price']) if company.get('custom_monthly_price') else None,
        'custom_dashboard_price': float(company['custom_dashboard_price']) if company.get('custom_dashboard_price') else None,
        'custom_pro_price': float(company['custom_pro_price']) if company.get('custom_pro_price') else None,
        # Usage-based pricing fields
        'included_minutes': included_minutes,
        'overage_rate_cents': overage_rate_cents,
        'minutes_used': minutes_used,
        'overage_minutes': overage_minutes,
        'overage_cost_cents': overage_cost_cents,
        'usage_period_start': usage_period_start.isoformat() if usage_period_start and hasattr(usage_period_start, 'isoformat') else usage_period_start,
        'usage_period_end': usage_period_end.isoformat() if usage_period_end and hasattr(usage_period_end, 'isoformat') else usage_period_end,
        'usage_alert_sent': usage_alert_sent,
        'max_monthly_overage_cents': company.get('max_monthly_overage_cents'),
    }
    
    print(f"[GET_SUB_INFO] Returning: tier={result['tier']}, is_active={result['is_active']}, minutes={minutes_used}/{included_minutes}")
    
    return result


def subscription_required(f):
    """Decorator to require active subscription for write operations.
    
    GET requests are always allowed so users can browse the app.
    POST/PUT/DELETE requests require an active subscription (trial or pro).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow GET requests through — users can look around without a subscription
        if request.method == 'GET':
            return f(*args, **kwargs)
        
        # For write operations, check subscription status
        # Check session cookie first, fall back to auth token header
        if 'company_id' not in session:
            token = request.headers.get('X-Auth-Token')
            if token:
                payload = verify_auth_token(token)
                if payload:
                    session['company_id'] = payload['cid']
                    session['email'] = payload['email']
            
            if 'company_id' not in session:
                return jsonify({"error": "Authentication required"}), 401
        
        db = get_database()
        company = db.get_company(session['company_id'])
        
        if not company:
            return jsonify({"error": "Company not found"}), 404
        
        subscription_info = get_subscription_info(company)
        
        if not subscription_info['is_active']:
            return jsonify({
                "error": "Subscription required",
                "subscription_status": "inactive",
                "message": "Your trial has expired or subscription is inactive. Please subscribe to continue.",
                "subscription": subscription_info
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function


# Initialize scheduler on first request (lazy init)
_scheduler_initialized = False

@app.before_request
def init_scheduler():
    """Initialize scheduler on first request"""
    global _scheduler_initialized
    if not _scheduler_initialized:
        _scheduler_initialized = True
        start_scheduler_once()


@app.route("/telnyx/voice", methods=["POST"])
@app.route("/twilio/voice", methods=["POST"])  # backwards compatibility
def twilio_voice():
    """
    Telnyx TeXML voice webhook endpoint - identifies company by incoming phone number.
    Returns TeXML (TwiML-compatible XML) to connect call to media stream OR forward to business phone.
    Also accessible at /twilio/voice for backwards compatibility.
    """
    db = get_database()
    
    # Extract TO number (the Twilio number that was called)
    to_number = request.form.get("To", "")
    caller_phone = request.form.get("From", "")
    
    # Find company by their assigned Twilio phone number
    try:
        conn = db.get_connection()
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM companies WHERE twilio_phone_number = %s", (to_number,))
        company = cursor.fetchone()
        db.return_connection(conn)
        company = dict(company) if company else None
    except Exception as e:
        print(f"[WARNING] Error fetching company by phone {to_number}: {e}")
        company = None
    
    if not company:
        # No company found for this number - return error
        twiml = VoiceResponse()
        twiml.say("This phone number is not configured. Please contact support.")
        print(f"[ERROR] No company found for Telnyx number: {to_number}")
        return Response(str(twiml), mimetype="text/xml")
    
    # Check if subscription is active — expired accounts should not use AI
    subscription_info = get_subscription_info(company)
    subscription_expired = not subscription_info['is_active']
    if subscription_expired:
        print(f"[SUBSCRIPTION] Company {company.get('id')} subscription expired — forwarding to business phone")
    
    # Hard cap protection: check if overage has exceeded the company's max allowed
    over_hard_cap = False
    max_overage = company.get('max_monthly_overage_cents')
    if max_overage is not None and max_overage > 0:
        current_overage_cost = subscription_info.get('overage_cost_cents', 0)
        if current_overage_cost >= max_overage:
            over_hard_cap = True
            print(f"[USAGE] Company {company.get('id')} hit overage hard cap (€{current_overage_cost/100:.2f} >= €{max_overage/100:.2f}) — forwarding to business phone")
    
    # Check if account is dashboard-only (no AI features)
    is_dashboard_only = company.get('subscription_plan', 'pro') == 'dashboard'
    if is_dashboard_only:
        print(f"[PLAN] Company {company.get('id')} is dashboard-only — forwarding to business phone")
    
    # Check if caller is in the bypass list (always forward to fallback)
    bypass_numbers_raw = company.get('bypass_numbers', '[]')
    bypass_forward = False
    try:
        import json
        import re
        bypass_list = json.loads(bypass_numbers_raw) if bypass_numbers_raw else []
        if bypass_list and isinstance(bypass_list, list):
            # Normalize caller phone for comparison (strip spaces, dashes, parens)
            caller_normalized = re.sub(r'[\s\-\(\)\+]', '', caller_phone)
            for entry in bypass_list:
                if not isinstance(entry, dict):
                    continue
                entry_phone = re.sub(r'[\s\-\(\)\+]', '', entry.get('phone', ''))
                if entry_phone and len(entry_phone) >= 7 and caller_normalized[-9:] == entry_phone[-9:]:
                    bypass_forward = True
                    print(f"[BYPASS] Caller {caller_phone} matches bypass entry: {entry.get('name', 'Unknown')} ({entry.get('phone', '')})")
                    break
    except Exception as e:
        print(f"[WARNING] Error checking bypass numbers: {e}")
    
    # Check if AI receptionist is enabled
    ai_enabled = company.get('ai_enabled', True)
    
    # Check if AI should be off based on schedule
    ai_schedule_off = False
    if ai_enabled:
        # Check for manual override first
        ai_override = company.get('ai_schedule_override', False)
        ai_schedule_raw = company.get('ai_schedule', '')
        if ai_schedule_raw:
            try:
                import json as _json
                schedule = _json.loads(ai_schedule_raw) if isinstance(ai_schedule_raw, str) else ai_schedule_raw
                if schedule and schedule.get('enabled') and schedule.get('slots'):
                    from datetime import datetime as _dt
                    from dateutil import tz as _tz
                    tzinfo = _tz.gettz(schedule.get('timezone', 'Europe/Dublin'))
                    if tzinfo is None:
                        tzinfo = _tz.gettz('Europe/Dublin')
                    now = _dt.now(tzinfo)
                    current_day = now.strftime('%A').lower()
                    current_minutes = now.hour * 60 + now.minute
                    
                    in_schedule = False
                    for slot in schedule['slots']:
                        if current_day in [d.lower() for d in slot.get('days', [])]:
                            start_mins = slot.get('startMinutes', 0)
                            end_mins = slot.get('endMinutes', 0)
                            if start_mins <= current_minutes < end_mins:
                                in_schedule = True
                                break
                    
                    if ai_override and in_schedule:
                        # We're back in scheduled hours — auto-clear the override
                        try:
                            db.update_company(company_id, ai_schedule_override=False)
                            print(f"[AI-SCHEDULE] Auto-cleared override — back in scheduled hours")
                        except Exception:
                            pass
                    elif ai_override and not in_schedule:
                        # Override active, outside hours — AI stays on
                        print(f"[AI-SCHEDULE] Override active — AI stays on outside scheduled hours")
                    elif not in_schedule:
                        ai_schedule_off = True
                        print(f"[AI-SCHEDULE] AI receptionist is outside scheduled hours ({current_day} {now.strftime('%H:%M')})")
            except Exception as e:
                print(f"[WARNING] Error checking AI schedule: {e}")
        elif ai_override:
            # Override set but no schedule — clear it
            try:
                db.update_company(company_id, ai_schedule_override=False)
            except Exception:
                pass
    
    twiml = VoiceResponse()
    
    if not ai_enabled or bypass_forward or ai_schedule_off or subscription_expired or is_dashboard_only or over_hard_cap:
        # AI is disabled - forward to business phone number
        business_phone = company.get('phone') if company else None
        
        print("=" * 60)
        print(f"📞 Incoming Call - {'BYPASS NUMBER' if bypass_forward else 'SUBSCRIPTION EXPIRED' if subscription_expired else 'OVERAGE CAP REACHED' if over_hard_cap else 'DASHBOARD ONLY' if is_dashboard_only else 'SCHEDULED OFF' if ai_schedule_off else 'AI DISABLED'}")
        print(f"[PHONE] Caller: {caller_phone}")
        print(f"[PHONE] Forwarding to business phone: {business_phone or 'No phone number set!'}")
        print("=" * 60)
        
        if business_phone:
            twiml.say("Please hold while we connect you.")
            # Create Dial verb with proper nested Number noun
            dial = twiml.dial(timeout=60, action='/telnyx/dial-status', method='POST')
            dial.number(business_phone)
            print(f"[INFO] Generated TwiML for forwarding:")
            print(str(twiml))
        else:
            twiml.say("We're sorry, but our AI receptionist is currently unavailable and no business phone number is configured. Please try again later.")
    else:
        # AI is enabled - connect to media stream
        ws_url = config.WS_PUBLIC_URL
        
        with twiml.connect() as connect:
            stream = connect.stream(url=ws_url)
            # Pass caller phone as custom parameter
            if caller_phone:
                stream.parameter(name="From", value=caller_phone)
            # Pass company ID so the WebSocket handler knows which business this call is for
            stream.parameter(name="CompanyId", value=str(company.get('id', '')))

        print("=" * 60)
        print("📞 Incoming Call - AI ENABLED")
        print(f"[PHONE] Caller: {caller_phone}")
        print(f"[COMPANY] ID: {company.get('id')}, Name: {company.get('company_name')}")
        print(f"[AI] Connecting to AI at: {ws_url}")
        print("=" * 60)
    
    return Response(str(twiml), mimetype="text/xml")


@app.route("/telnyx/dial-status", methods=["POST"])
@app.route("/twilio/dial-status", methods=["POST"])  # backwards compatibility
def dial_status():
    """Callback for dial status - helps debug forwarding issues"""
    dial_status = request.form.get("DialCallStatus", "unknown")
    dial_duration = request.form.get("DialCallDuration", "0")
    error_code = request.form.get("ErrorCode", "")
    error_message = request.form.get("ErrorMessage", "")
    
    print("=" * 60)
    print("📞 Dial Status Callback")
    print(f"Status: {dial_status}")
    print(f"Duration: {dial_duration}s")
    if error_code:
        print(f"[WARNING] ERROR {error_code}: {error_message}")
    print(f"Full data: {dict(request.form)}")
    print("=" * 60)
    
    # Return empty TwiML to end the call gracefully
    response = VoiceResponse()
    if dial_status in ["busy", "no-answer", "failed"]:
        if error_code == "13227":
            # Geo-permissions error - provide helpful message
            response.say("We're sorry, call forwarding is not currently configured. Please contact us directly.")
        else:
            response.say("We're sorry, but we couldn't connect your call. Please try again later.")
    
    return Response(str(response), mimetype="text/xml")


@app.route("/telnyx/transfer", methods=["POST"])
@app.route("/twilio/transfer", methods=["POST"])  # backwards compatibility
def transfer_call():
    """Transfer an active call to a human (fallback number)"""
    transfer_number = request.args.get('number')
    
    if not transfer_number:
        print("⚠️ Transfer endpoint called without number parameter")
        response = VoiceResponse()
        response.say("Sorry, transfer failed. No number provided.")
        return Response(str(response), mimetype="text/xml")
    
    print("=" * 60)
    print("📞 TRANSFER ENDPOINT CALLED")
    print(f"[PHONE] Transferring to: {transfer_number}")
    print("=" * 60)
    
    # Create TeXML to transfer the call
    response = VoiceResponse()
    response.say("Transferring you now. Please hold.")
    dial = response.dial(timeout=60, action='/telnyx/dial-status', method='POST')
    dial.number(transfer_number)
    
    print(f"[INFO] Generated transfer TeXML:\n{str(response)}")
    
    return Response(str(response), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "AI Receptionist"}


@app.route("/api/image-proxy", methods=["GET"])
def image_proxy():
    """
    Proxy images from R2 storage to avoid CORS/ad-blocker issues.
    Usage: /api/image-proxy?url=https://...r2.dev/path/to/image.jpg
    """
    import requests
    from flask import Response
    
    image_url = request.args.get('url')
    if not image_url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    # Only allow R2 URLs for security
    allowed_domains = ['r2.dev', 'r2.cloudflarestorage.com']
    if not any(domain in image_url for domain in allowed_domains):
        return jsonify({"error": "Invalid image URL"}), 403
    
    try:
        # Fetch the image from R2
        resp = requests.get(image_url, timeout=10, stream=True)
        if resp.status_code != 200:
            return jsonify({"error": "Image not found"}), 404
        
        # Get content type from response or default to jpeg
        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        
        # Return the image with proper headers
        return Response(
            resp.content,
            mimetype=content_type,
            headers={
                'Cache-Control': 'public, max-age=31536000',
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        print(f"[IMAGE_PROXY] Error fetching image: {e}")
        return jsonify({"error": "Failed to fetch image"}), 500


@app.route("/api/media-proxy", methods=["GET"])
def media_proxy():
    """
    Proxy audio/media files from R2 storage to avoid CORS issues.
    Usage: /api/media-proxy?url=https://...r2.dev/path/to/audio.wav
    """
    import requests as req_lib
    from flask import Response

    media_url = request.args.get('url')
    if not media_url:
        return jsonify({"error": "Missing url parameter"}), 400

    allowed_domains = ['r2.dev', 'r2.cloudflarestorage.com']
    if not any(domain in media_url for domain in allowed_domains):
        return jsonify({"error": "Invalid media URL"}), 403

    try:
        resp = req_lib.get(media_url, timeout=15, stream=True)
        if resp.status_code != 200:
            return jsonify({"error": "Media not found"}), 404

        content_type = resp.headers.get('Content-Type', 'audio/wav')

        return Response(
            resp.content,
            mimetype=content_type,
            headers={
                'Cache-Control': 'no-cache, must-revalidate',
                'Access-Control-Allow-Origin': '*',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(len(resp.content)),
            }
        )
    except Exception as e:
        print(f"[MEDIA_PROXY] Error fetching media: {e}")
        return jsonify({"error": "Failed to fetch media"}), 500


@app.route("/api/config-check", methods=["GET"])
@login_required
def config_check():
    """
    Diagnostic endpoint to check production configuration
    Helps debug session cookie and CORS issues
    """
    import sys
    
    is_production = os.getenv('FLASK_ENV') == 'production'
    
    config_info = {
        "flask_env": os.getenv('FLASK_ENV', 'not set'),
        "is_production_mode": is_production,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "session_config": {
            "cookie_secure": app.config.get('SESSION_COOKIE_SECURE'),
            "cookie_httponly": app.config.get('SESSION_COOKIE_HTTPONLY'),
            "cookie_samesite": app.config.get('SESSION_COOKIE_SAMESITE'),
            "permanent_lifetime": str(app.config.get('PERMANENT_SESSION_LIFETIME')),
        },
        "cors_config": {
            "supports_credentials": True
        },
        "urls": {
            "public_url": os.getenv('PUBLIC_URL', 'not set'),
            "frontend_url": os.getenv('FRONTEND_URL', 'not set')
        },
        "database_connected": False,
        "recommendations": []
    }
    
    # Test database connection
    try:
        db = get_database()
        # Simple query to test connection
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT COUNT(*) as count FROM companies")
        result = cursor.fetchone()
        cursor.close()
        db.return_connection(conn)
        config_info["database_connected"] = True
    except Exception as e:
        config_info["database_error"] = str(e)
    
    # Add recommendations based on configuration
    if not is_production and os.getenv('PUBLIC_URL', '').startswith('https://'):
        config_info["recommendations"].append(
            "⚠️ FLASK_ENV is not set to 'production' but you have a production URL. "
            "Set FLASK_ENV=production to enable secure session cookies."
        )
    
    if is_production and not app.config.get('SESSION_COOKIE_SECURE'):
        config_info["recommendations"].append(
            "⚠️ SESSION_COOKIE_SECURE should be True in production."
        )
    
    if is_production and app.config.get('SESSION_COOKIE_SAMESITE') != 'None':
        config_info["recommendations"].append(
            "⚠️ SESSION_COOKIE_SAMESITE should be 'None' for cross-origin requests in production."
        )
    
    if not app.secret_key or app.secret_key == 'dev':
        config_info["recommendations"].append(
            "⚠️ SECRET_KEY is not set or is using default value. Generate a secure key."
        )
    else:
        # Check if SECRET_KEY env var is actually set (vs generated at runtime)
        if not os.getenv('SECRET_KEY'):
            config_info["recommendations"].append(
                "⚠️ CRITICAL: SECRET_KEY environment variable is not set! "
                "A random key is being generated at runtime. "
                "All sessions will be invalidated when the server restarts. "
                "Set SECRET_KEY in your environment variables."
            )
            config_info["secret_key_env_set"] = False
        else:
            config_info["secret_key_env_set"] = True
    
    # Check origin header
    origin = request.headers.get('Origin')
    if origin:
        config_info["request_origin"] = origin
        config_info["origin_allowed"] = origin in allowed_origins
        if origin not in allowed_origins:
            config_info["recommendations"].append(
                f"⚠️ Request origin '{origin}' is not in allowed_origins list. "
                "CORS requests from this origin will fail."
            )
    
    if not config_info["recommendations"]:
        config_info["recommendations"].append("✅ Configuration looks good!")
    
    return jsonify(config_info)


@app.route("/api/ai-logs", methods=["GET"])
@login_required
def get_ai_logs():
    """
    Get AI operation logs for debugging.
    Returns recent errors and statistics.
    
    Query params:
        - errors_only: If 'true', only return errors
        - limit: Number of recent errors to return (default 20)
    """
    try:
        from src.utils.ai_logger import ai_logger
        
        errors_only = request.args.get('errors_only', 'false').lower() == 'true'
        limit = min(int(request.args.get('limit', 20)), 100)  # Cap at 100
        
        stats = ai_logger.get_stats()
        recent_errors = ai_logger.get_recent_errors(limit)
        
        response_data = {
            "stats": stats,
            "recent_errors": recent_errors if errors_only or recent_errors else [],
            "log_file_hint": "Check logs/ai_YYYYMMDD.log for full logs"
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to get AI logs: {str(e)}",
            "stats": {},
            "recent_errors": []
        }), 500


# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

@app.route("/api/auth/signup", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=300)  # 5 signups per 5 minutes
def signup():
    """Create a new company account"""
    data = request.json
    
    # Validate required fields
    required_fields = ['company_name', 'owner_name', 'email', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"{field.replace('_', ' ').title()} is required"}), 400
    
    # Validate and sanitize email
    email = data['email'].lower().strip()
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400
    
    # Validate password strength (OWASP recommendations)
    password = data['password']
    password_error = _validate_password(password)
    if password_error:
        return jsonify({"error": password_error}), 400
    
    # Sanitize input fields
    company_name = sanitize_string(data['company_name'], max_length=200)
    owner_name = sanitize_string(data['owner_name'], max_length=200)
    
    db = get_database()
    
    # Check if email already exists
    existing = db.get_company_by_email(email)
    if existing:
        return jsonify({"error": "An account with this email already exists"}), 409
    
    # Hash password using secure algorithm (bcrypt)
    password_hash = hash_password(password)
    company_id = db.create_company(
        company_name=company_name,
        owner_name=owner_name,
        email=email,
        password_hash=password_hash,
        phone=sanitize_string(data.get('phone', ''), max_length=20),
        trade_type=sanitize_string(data.get('trade_type', ''), max_length=100)
    )
    
    if company_id:
        # Don't auto-start trial - user will choose to start trial or subscribe in settings
        db.update_company(
            company_id,
            subscription_tier='none',
            subscription_status='inactive'
        )
        
        # Log the user in (phone number will be configured separately)
        session['company_id'] = company_id
        session['email'] = email
        
        # Generate auth token as fallback for cross-origin cookie issues
        auth_token = generate_auth_token(company_id, email)
        
        company = db.get_company(company_id)
        return jsonify({
            "success": True,
            "message": "Account created successfully!",
            "auth_token": auth_token,
            "user": {
                "id": company_id,
                "company_name": company['company_name'],
                "owner_name": company['owner_name'],
                "email": company['email'],
                "subscription_tier": 'none',
                "twilio_phone_number": company.get('twilio_phone_number'),
                "easy_setup": company.get('easy_setup', True)
            }
        }), 201
    else:
        return jsonify({"error": "Failed to create account"}), 500


@app.route("/api/auth/login", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=60)  # 10 login attempts per minute
def login():
    """Log in to an existing account"""
    data = request.json
    security_logger = get_security_logger()
    rate_limiter = get_rate_limiter()
    client_ip = get_client_ip()
    
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    
    # Log detailed request information
    origin = request.headers.get('Origin', 'no-origin')
    user_agent = request.headers.get('User-Agent', 'unknown')[:100]
    print(f"[LOGIN] ========== Login Attempt ==========")
    print(f"[LOGIN] Email: {email}")
    print(f"[LOGIN] Origin: {origin}")
    print(f"[LOGIN] Client IP: {client_ip}")
    print(f"[LOGIN] User Agent: {user_agent}")
    print(f"[LOGIN] CORS Allowed: {origin in allowed_origins}")
    
    if not email or not password:
        print(f"[LOGIN] FAILED - Missing credentials")
        return jsonify({
            "error": "Email and password are required",
            "code": "MISSING_CREDENTIALS"
        }), 400
    
    # Check if this email is blocked due to too many failed attempts
    if rate_limiter.is_blocked(email):
        security_logger.log_failed_auth(
            '/api/auth/login',
            client_ip,
            'Account temporarily blocked'
        )
        print(f"[LOGIN] Blocked due to too many failed attempts: {email}")
        return jsonify({
            "error": "Too many failed attempts. Please try again later."
        }), 429
    
    db = get_database()
    company = db.get_company_by_email(email)
    
    if not company:
        # Record failed attempt but don't reveal if email exists
        rate_limiter.record_failed_login(email)
        security_logger.log_login_attempt(email, client_ip, False)
        print(f"[LOGIN] FAILED - User not found: {email}")
        
        return jsonify({
            "error": "Invalid email or password",
            "code": "INVALID_CREDENTIALS"
        }), 401
    
    if not verify_password(password, company['password_hash']):
        # Record failed attempt
        should_block = rate_limiter.record_failed_login(email)
        security_logger.log_login_attempt(email, client_ip, False)
        print(f"[LOGIN] FAILED - Invalid password for: {email}")
        
        if should_block:
            print(f"[LOGIN] Account temporarily locked due to too many failed attempts")
            return jsonify({
                "error": "Too many failed login attempts. Your account has been temporarily locked for security.",
                "code": "ACCOUNT_LOCKED",
                "help": "Please wait 15 minutes before trying again."
            }), 429
        
        return jsonify({
            "error": "Invalid email or password",
            "code": "INVALID_CREDENTIALS"
        }), 401
    
    # Successful login - clear failed attempts
    rate_limiter.clear_failed_logins(email)
    security_logger.log_login_attempt(email, client_ip, True)
    
    # Check if password hash needs upgrade (migrate from weak hash)
    if needs_rehash(company['password_hash']):
        new_hash = hash_password(password)
        db.update_company_password(company['id'], new_hash)
        print(f"[SUCCESS] Upgraded password hash for user {company['id']}")
    
    # Update last login
    db.update_last_login(company['id'])
    
    # Create session
    session['company_id'] = company['id']
    session['email'] = company['email']
    session.permanent = True  # Make session permanent (uses PERMANENT_SESSION_LIFETIME)
    
    # Generate auth token as fallback for cross-origin cookie issues
    auth_token = generate_auth_token(company['id'], company['email'])
    
    # Log session creation for debugging
    print(f"[LOGIN] SUCCESS - User {company['id']} ({email}) from {origin} | "
          f"Secure={app.config.get('SESSION_COOKIE_SECURE')}, "
          f"SameSite={app.config.get('SESSION_COOKIE_SAMESITE')}")
    return jsonify({
        "success": True,
        "message": "Logged in successfully",
        "auth_token": auth_token,
        "user": {
            "id": company['id'],
            "company_name": company['company_name'],
            "owner_name": company['owner_name'],
            "email": company['email'],
            "phone": company['phone'],
            "trade_type": company['trade_type'],
            "logo_url": company['logo_url'],
            "subscription_tier": company['subscription_tier'],
            "twilio_phone_number": company.get('twilio_phone_number'),
            "easy_setup": company.get('easy_setup', True)
        },
        "subscription": get_subscription_info(company)
    })


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """Log out the current user"""
    company_id = session.get('company_id', 'unknown')
    email = session.get('email', 'unknown')
    print(f"[LOGOUT] User {company_id} ({email}) logging out")
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


@app.route("/api/auth/delete-account", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=300)  # 10 attempts per 5 minutes
def delete_account():
    """
    Permanently delete the user's account and all associated data.
    Requires confirmation text to prevent accidental deletion.
    """
    data = request.json or {}
    confirmation = data.get('confirmation', '').strip().lower()
    
    if confirmation != 'delete account':
        return jsonify({
            "error": "Please type 'delete account' to confirm deletion"
        }), 400
    
    company_id = session.get('company_id')
    email = session.get('email', 'unknown')
    
    db = get_database()
    company = db.get_company(company_id)
    
    if not company:
        return jsonify({"error": "Account not found"}), 404
    
    # Cancel any active Stripe subscription before deleting
    stripe_subscription_id = company.get('stripe_subscription_id')
    if stripe_subscription_id:
        try:
            stripe.Subscription.cancel(stripe_subscription_id)
            print(f"[DELETE_ACCOUNT] Cancelled Stripe subscription {stripe_subscription_id}")
        except Exception as e:
            print(f"[WARNING] Could not cancel Stripe subscription: {e}")
    
    # Note: We don't delete the Stripe Connect account as it may have pending payouts
    # The account will remain but won't be linked to any company
    stripe_connect_id = company.get('stripe_connect_account_id')
    if stripe_connect_id:
        print(f"[DELETE_ACCOUNT] Stripe Connect account {stripe_connect_id} will be orphaned (not deleted)")
    
    # Delete the company and all associated data
    success = db.delete_company(company_id)
    
    if success:
        print(f"[DELETE_ACCOUNT] Successfully deleted account {company_id} ({email})")
        session.clear()
        return jsonify({
            "success": True,
            "message": "Your account has been permanently deleted"
        })
    else:
        return jsonify({
            "error": "Failed to delete account. Please contact support."
        }), 500


@app.route("/api/auth/export-data", methods=["GET"])
@login_required
@rate_limit(max_requests=5, window_seconds=3600)  # 5 exports per hour
def export_user_data():
    """
    GDPR Article 20 - Data Portability.
    Export all personal data for the logged-in user in JSON format.
    """
    company_id = session.get('company_id')
    db = get_database()
    company = db.get_company(company_id)

    if not company:
        return jsonify({"error": "Account not found"}), 404

    conn = db.get_connection()
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    def fetch_all(query, params=(company_id,)):
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def serialize(obj):
        """JSON-safe serializer for dates/decimals."""
        if obj is None:
            return None
        import decimal
        from datetime import datetime, date
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return str(obj)

    try:
        export = {
            "exported_at": __import__('datetime').datetime.utcnow().isoformat() + "Z",
            "account": {
                "company_name": company.get('company_name'),
                "owner_name": company.get('owner_name'),
                "email": company.get('email'),
                "phone": company.get('phone'),
                "address": company.get('address'),
                "trade_type": company.get('trade_type'),
                "industry_type": company.get('industry_type'),
                "business_hours": company.get('business_hours'),
                "created_at": serialize(company.get('created_at')),
            },
            "clients": fetch_all(
                "SELECT name, phone, email, date_of_birth, description, address, eircode, first_visit, last_visit, total_appointments, created_at FROM clients WHERE company_id = %s ORDER BY id"
            ),
            "bookings": fetch_all(
                "SELECT appointment_time, duration_minutes, service_type, status, urgency, address, eircode, phone_number, email, charge, charge_max, payment_status, payment_method, created_at FROM bookings WHERE company_id = %s ORDER BY id"
            ),
            "employees": fetch_all(
                "SELECT name, phone, email, trade_specialty, status, weekly_hours_expected, created_at FROM employees WHERE company_id = %s ORDER BY id"
            ),
            "services": fetch_all(
                "SELECT name, description, price, duration_minutes, created_at FROM services WHERE company_id = %s ORDER BY id"
            ),
            "call_logs": fetch_all(
                "SELECT phone_number, caller_name, duration_seconds, call_outcome, ai_summary, created_at FROM call_logs WHERE company_id = %s ORDER BY id"
            ),
        }

        # Optional tables — skip gracefully if they don't exist yet
        optional_queries = {
            "expenses": "SELECT description, amount, category, date, created_at FROM expenses WHERE company_id = %s ORDER BY id",
            "quotes": "SELECT title, description, total, status, valid_until, created_at FROM quotes WHERE company_id = %s ORDER BY id",
            "messages": "SELECT sender_type, content, created_at FROM messages WHERE company_id = %s ORDER BY id",
        }
        for key, query in optional_queries.items():
            cursor.execute("SAVEPOINT sp_export")
            try:
                export[key] = fetch_all(query)
                cursor.execute("RELEASE SAVEPOINT sp_export")
            except Exception:
                cursor.execute("ROLLBACK TO SAVEPOINT sp_export")
                export[key] = []

        db.return_connection(conn)

        # Serialize dates/decimals in nested data
        import json
        json_str = json.dumps(export, default=serialize, indent=2)

        response = Response(json_str, mimetype='application/json')
        response.headers['Content-Disposition'] = f'attachment; filename="bookedforyou-data-export-{company_id}.json"'
        print(f"[GDPR_EXPORT] Data export generated for company {company_id}")
        return response

    except Exception as e:
        db.return_connection(conn)
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to export data. Please try again or contact support."}), 500


@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    """Get the currently logged in user"""
    client_ip = get_client_ip()
    
    # Check session cookie first, then fall back to auth token header
    has_session = 'company_id' in session
    company_id = session.get('company_id')
    
    if not has_session:
        token = request.headers.get('X-Auth-Token')
        if token:
            payload = verify_auth_token(token)
            if payload:
                company_id = payload['cid']
                session['company_id'] = company_id
                session['email'] = payload['email']
                has_session = True
    
    print(f"[AUTH_CHECK] Request from {client_ip} - Session exists: {has_session}, Company ID: {company_id or 'none'}")
    
    if not has_session:
        print(f"[AUTH_CHECK] No session or token found - user not authenticated")
        return jsonify({"authenticated": False}), 200
    
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        print(f"[AUTH_CHECK] Company {company_id} not found in database - clearing session")
        session.clear()
        return jsonify({"authenticated": False}), 200
    
    print(f"[AUTH_CHECK] Authenticated user: {company['email']} (ID: {company['id']})")
    
    # Get subscription info
    subscription_info = get_subscription_info(company)
    
    print(f"[AUTH_CHECK] Subscription for {company['email']}: tier={subscription_info['tier']}, is_active={subscription_info['is_active']}")
    
    return jsonify({
        "authenticated": True,
        "user": {
            "id": company['id'],
            "company_name": company['company_name'],
            "owner_name": company['owner_name'],
            "email": company['email'],
            "phone": company['phone'],
            "trade_type": company['trade_type'],
            "address": company['address'],
            "logo_url": company['logo_url'],
            "subscription_tier": company['subscription_tier'],
            "subscription_status": company['subscription_status'],
            "twilio_phone_number": company.get('twilio_phone_number'),
            "easy_setup": company.get('easy_setup', True)
        },
        "subscription": subscription_info
    })


@app.route("/api/dashboard", methods=["GET"])
@login_required
def get_dashboard_data():
    """
    Batch endpoint to get all dashboard data in one request.
    Reduces 4 separate API calls to 1, improving page load performance.

    Query params:
        since_days (int, default 180): only return bookings from the last N days.
            Pass since_days=0 or a large number to disable the window.
        limit (int, optional): cap booking count for very large tenants.
    """
    try:
        db = get_database()
        company_id = session.get('company_id')

        # Time-window bookings by default so the payload stays small on big tenants.
        try:
            since_days = int(request.args.get('since_days', 180))
        except (TypeError, ValueError):
            since_days = 180
        since_days = None if since_days <= 0 else since_days

        limit_arg = request.args.get('limit')
        try:
            limit = int(limit_arg) if limit_arg else None
        except ValueError:
            limit = None

        # Get all data filtered by company_id
        bookings = db.get_all_bookings(
            company_id=company_id, since_days=since_days, limit=limit
        )
        clients = db.get_all_clients(company_id=company_id)
        employees = db.get_all_employees(company_id=company_id)

        # Finances use the already-loaded bookings (window-limited). If you need
        # lifetime revenue, use /api/finances instead.
        total_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings if b.get('status') == 'completed')
        pending_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings if b.get('status') in ['pending', 'scheduled'])

        finances = {
            'total_revenue': total_revenue,
            'pending_revenue': pending_revenue,
            'completed_jobs': len([b for b in bookings if b.get('status') == 'completed']),
            'pending_jobs': len([b for b in bookings if b.get('status') in ['pending', 'scheduled']])
        }

        return jsonify({
            'success': True,
            'data': {
                'bookings': bookings,
                'clients': clients,
                'employees': employees,
                'finances': finances,
                'window_days': since_days,
            }
        })

    except Exception as e:
        print(f"[ERROR] Dashboard data error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/auth/profile", methods=["PUT"])
@login_required
def update_profile():
    """Update company profile"""
    data = request.json
    db = get_database()
    
    # Handle logo upload to R2 if logo_url is base64
    if 'logo_url' in data and data['logo_url'] and data['logo_url'].startswith('data:image/'):
        data['logo_url'] = upload_base64_image_to_r2(data['logo_url'], session['company_id'], 'logos')
    
    # Filter allowed fields (basic business info only)
    allowed_updates = {}
    basic_fields = ['company_name', 'owner_name', 'phone', 'trade_type', 'address', 'logo_url']
    
    for field in basic_fields:
        if field in data:
            allowed_updates[field] = data[field]
    
    if allowed_updates:
        success = db.update_company(session['company_id'], **allowed_updates)
        if success:
            company = db.get_company(session['company_id'])
            return jsonify({
                "success": True,
                "message": "Profile updated successfully",
                "user": {
                    "id": company['id'],
                    "company_name": company['company_name'],
                    "owner_name": company['owner_name'],
                    "email": company['email'],
                    "phone": company['phone'],
                    "trade_type": company['trade_type'],
                    "address": company['address'],
                    "logo_url": company['logo_url'],
                    "subscription_tier": company['subscription_tier']
                }
            })
    
    return jsonify({"error": "No valid fields to update"}), 400


@app.route("/api/auth/change-password", methods=["POST"])
@login_required
@rate_limit(max_requests=5, window_seconds=300)  # 5 password changes per 5 minutes
def change_password():
    """Change password for logged in user"""
    data = request.json
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    if not current_password or not new_password:
        return jsonify({"error": "Current and new password are required"}), 400
    
    # Validate new password strength
    password_error = _validate_password(new_password)
    if password_error:
        return jsonify({"error": password_error}), 400
    
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not verify_password(current_password, company['password_hash']):
        get_security_logger().log_failed_auth(
            '/api/auth/change-password',
            get_client_ip(),
            'Invalid current password'
        )
        return jsonify({"error": "Current password is incorrect"}), 401
    
    # Hash with secure algorithm
    new_hash = hash_password(new_password)
    success = db.update_company_password(session['company_id'], new_hash)
    
    if success:
        get_security_logger().log_password_change(
            session['company_id'],
            get_client_ip()
        )
        return jsonify({"success": True, "message": "Password changed successfully"})
    
    return jsonify({"error": "Failed to change password"}), 500


# ============================================
# PASSWORD RESET ENDPOINTS
# ============================================

@app.route("/api/auth/forgot-password", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=300)  # 5 requests per 5 minutes
def forgot_password():
    """Send password reset email"""
    import secrets
    import sys
    from datetime import datetime, timedelta
    
    data = request.json
    email = data.get('email', '').lower().strip()
    
    if not email or not validate_email(email):
        return jsonify({"error": "Please provide a valid email address"}), 400
    
    db = get_database()
    company = db.get_company_by_email(email)
    
    # Always return success message to prevent email enumeration
    success_msg = {
        "success": True,
        "message": "If an account with that email exists, we've sent a password reset link."
    }
    
    if not company:
        print(f"[FORGOT-PW] No account found for {email}", flush=True)
        return jsonify(success_msg)
    
    print(f"[FORGOT-PW] Account found for {email} (ID: {company['id']})", flush=True)
    
    # Generate secure reset token
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.now() + timedelta(hours=1)
    
    # Store token in database
    db.update_company(company['id'], 
                      reset_token=reset_token, 
                      reset_token_expires=reset_expires.isoformat())
    
    # Build reset link - use request origin or PUBLIC_URL
    origin = request.headers.get('Origin', '')
    if not origin:
        origin = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
    reset_link = f"{origin}/reset-password?token={reset_token}"
    
    print(f"[FORGOT-PW] Reset link: {reset_link}", flush=True)
    
    # Send email
    try:
        from src.services.email_reminder import get_email_service
        email_service = get_email_service()
        
        # Get business name for the email
        business_name = 'BookedForYou'
        try:
            business_name = company.get('company_name', 'BookedForYou') or 'BookedForYou'
        except Exception:
            pass
        
        email_sent = email_service.send_password_reset(email, reset_link, business_name)
        
        if email_sent:
            print(f"[FORGOT-PW] Reset email sent to {email}", flush=True)
        else:
            print(f"[FORGOT-PW] Email service not configured - link logged above", flush=True)
    except Exception as e:
        print(f"[FORGOT-PW] Email send error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
    
    return jsonify(success_msg)


@app.route("/api/auth/reset-password", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=300)  # 10 attempts per 5 minutes
def reset_password():
    """Reset password using token"""
    data = request.json
    token = data.get('token', '').strip()
    new_password = data.get('new_password', '')
    
    if not token:
        return jsonify({"error": "Reset token is required"}), 400
    
    if not new_password:
        return jsonify({"error": "New password is required"}), 400
    
    # Validate password strength
    password_error = _validate_password(new_password)
    if password_error:
        return jsonify({"error": password_error}), 400
    
    db = get_database()
    company = db.get_company_by_reset_token(token)
    
    if not company:
        get_security_logger().log_failed_auth(
            '/api/auth/reset-password',
            get_client_ip(),
            'Invalid reset token'
        )
        return jsonify({"error": "Invalid or expired reset link. Please request a new one."}), 400
    
    # Check if token has expired
    from datetime import datetime
    token_expires = company.get('reset_token_expires')
    if token_expires:
        if isinstance(token_expires, str):
            try:
                token_expires = datetime.fromisoformat(token_expires)
            except ValueError:
                token_expires = None
        
        if token_expires and datetime.now() > token_expires:
            # Clear expired token
            db.update_company(company['id'], reset_token=None, reset_token_expires=None)
            return jsonify({"error": "Reset link has expired. Please request a new one."}), 400
    
    # Update password
    new_hash = hash_password(new_password)
    success = db.update_company_password(company['id'], new_hash)
    
    if success:
        # Clear the reset token
        db.update_company(company['id'], reset_token=None, reset_token_expires=None)
        
        get_security_logger().log_password_change(
            company['id'],
            get_client_ip()
        )
        
        return jsonify({
            "success": True,
            "message": "Password has been reset successfully. You can now log in with your new password."
        })
    
    return jsonify({"error": "Failed to reset password. Please try again."}), 500


# ============================================
# EMPLOYEE PORTAL AUTH ENDPOINTS
# ============================================

_employee_token_serializer = URLSafeTimedSerializer(
    app.secret_key, salt='employee-auth-token'
)


def generate_employee_auth_token(employee_id: int, company_id: int, email: str) -> str:
    """Generate a signed auth token for an employee."""
    return _employee_token_serializer.dumps({
        'wid': employee_id, 'cid': company_id, 'email': email, 'role': 'employee'
    })


def verify_employee_auth_token(token: str, max_age: int = 432000) -> dict | None:
    """Verify and decode an employee auth token. Returns payload or None.
    max_age=432000 = 5 days, matching PERMANENT_SESSION_LIFETIME."""
    try:
        return _employee_token_serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def employee_login_required(f):
    """Decorator to require employee login for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session first
        employee_id = session.get('employee_id')
        if employee_id and isinstance(employee_id, int):
            return f(*args, **kwargs)

        # Fallback: signed auth token header
        token = request.headers.get('X-Auth-Token')
        if token:
            payload = verify_employee_auth_token(token)
            if payload and payload.get('wid') and payload.get('role') == 'employee':
                session['employee_id'] = payload['wid']
                session['employee_company_id'] = payload['cid']
                session['employee_email'] = payload['email']
                return f(*args, **kwargs)

        return jsonify({"error": "Authentication required"}), 401
    return decorated_function


@app.route("/api/employee/auth/login", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=60)
def employee_login():
    """Log in as an employee"""
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = get_database()
    account = db.get_employee_account_by_email(email)

    if not account:
        return jsonify({"error": "Invalid email or password"}), 401

    if not account.get('password_set') or not account.get('password_hash'):
        return jsonify({
            "error": "Please set your password first using the invite link sent to your email."
        }), 401

    if not verify_password(password, account['password_hash']):
        return jsonify({"error": "Invalid email or password"}), 401

    # Get the employee record for profile info
    employee = db.get_employee(account['employee_id'])
    if not employee:
        return jsonify({"error": "Employee profile not found"}), 500

    # Get company name
    company = db.get_company(account['company_id'])
    company_name = company['company_name'] if company else ''

    # Update last login
    db.update_employee_account_last_login(account['id'])

    # Create session
    session['employee_id'] = account['employee_id']
    session['employee_company_id'] = account['company_id']
    session['employee_email'] = account['email']
    session.permanent = True

    # Generate auth token
    auth_token = generate_employee_auth_token(
        account['employee_id'], account['company_id'], account['email']
    )

    return jsonify({
        "success": True,
        "auth_token": auth_token,
        "user": {
            "id": account['employee_id'],
            "name": employee['name'],
            "email": account['email'],
            "phone": employee.get('phone', ''),
            "trade_specialty": employee.get('trade_specialty', ''),
            "image_url": employee.get('image_url', ''),
            "company_name": company_name,
            "role": "employee"
        }
    })


@app.route("/api/employee/auth/me", methods=["GET"])
def get_current_employee():
    """Get the currently logged in employee"""
    employee_id = session.get('employee_id')

    if not employee_id:
        token = request.headers.get('X-Auth-Token')
        if token:
            payload = verify_employee_auth_token(token)
            if payload and payload.get('wid') and payload.get('role') == 'employee':
                employee_id = payload['wid']
                session['employee_id'] = payload['wid']
                session['employee_company_id'] = payload['cid']
                session['employee_email'] = payload['email']

    if not employee_id:
        return jsonify({"authenticated": False}), 200

    db = get_database()
    employee = db.get_employee(employee_id)
    account = db.get_employee_account_by_employee_id(employee_id)

    if not employee or not account:
        session.pop('employee_id', None)
        session.pop('employee_company_id', None)
        session.pop('employee_email', None)
        return jsonify({"authenticated": False}), 200

    company = db.get_company(account['company_id'])
    company_name = company['company_name'] if company else ''
    
    # Include industry profile so employee portal shows correct terminology
    from src.utils.industry_config import get_industry_profile
    industry_type = (company or {}).get('industry_type') or 'trades'
    industry_profile = get_industry_profile(industry_type)

    return jsonify({
        "authenticated": True,
        "user": {
            "id": employee['id'],
            "name": employee['name'],
            "email": account['email'],
            "phone": employee.get('phone', ''),
            "trade_specialty": employee.get('trade_specialty', ''),
            "image_url": employee.get('image_url', ''),
            "company_name": company_name,
            "role": "employee",
            "industry_type": industry_type,
            "industry_profile": industry_profile,
        }
    })


@app.route("/api/employee/auth/logout", methods=["POST"])
def employee_logout():
    """Log out employee"""
    session.pop('employee_id', None)
    session.pop('employee_company_id', None)
    session.pop('employee_email', None)
    return jsonify({"success": True, "message": "Logged out"})


@app.route("/api/employee/auth/set-password", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=60)
def employee_set_password():
    """Set password for an employee account using invite token"""
    data = request.json
    token = data.get('token', '').strip()
    new_password = data.get('password', '')

    if not token:
        return jsonify({"error": "Invite token is required"}), 400

    if not new_password:
        return jsonify({"error": "Password is required"}), 400

    password_error = _validate_password(new_password)
    if password_error:
        return jsonify({"error": password_error}), 400

    db = get_database()
    account = db.get_employee_account_by_invite_token(token)

    if not account:
        return jsonify({"error": "Invalid or expired invite link."}), 400

    # Check if token has expired
    from datetime import datetime
    expires = account.get('invite_expires_at')
    if expires:
        if isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires)
            except ValueError:
                expires = None
        if expires and datetime.now() > expires:
            return jsonify({"error": "Invite link has expired. Ask your employer to resend the invite."}), 400

    # Set the password
    password_hash = hash_password(new_password)
    success = db.set_employee_account_password(account['id'], password_hash)

    if success:
        return jsonify({
            "success": True,
            "message": "Password set successfully! You can now log in."
        })

    return jsonify({"error": "Failed to set password. Please try again."}), 500


@app.route("/api/employee/auth/forgot-password", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=300)
def employee_forgot_password():
    """Send password reset email for an employee account"""
    import secrets
    from datetime import datetime, timedelta

    data = request.json
    email = data.get('email', '').lower().strip()

    if not email or not validate_email(email):
        return jsonify({"error": "Please provide a valid email address"}), 400

    success_msg = {
        "success": True,
        "message": "If an employee account with that email exists, we've sent a password reset link."
    }

    db = get_database()
    account = db.get_employee_account_by_email(email)

    if not account:
        print(f"[EMPLOYEE-FORGOT-PW] No employee account found for {email}", flush=True)
        return jsonify(success_msg)

    if not account.get('password_set'):
        print(f"[EMPLOYEE-FORGOT-PW] Employee {email} hasn't set password yet - they should use invite link", flush=True)
        return jsonify(success_msg)

    print(f"[EMPLOYEE-FORGOT-PW] Account found for {email} (ID: {account['id']})", flush=True)

    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.now() + timedelta(hours=1)

    db.update_employee_account_reset_token(account['id'], reset_token, reset_expires.isoformat())

    origin = request.headers.get('Origin', '')
    if not origin:
        origin = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
    reset_link = f"{origin}/employee/reset-password?token={reset_token}"

    print(f"[EMPLOYEE-FORGOT-PW] Reset link: {reset_link}", flush=True)

    try:
        from src.services.email_reminder import get_email_service
        email_service = get_email_service()

        company = db.get_company(account['company_id'])
        business_name = company.get('company_name', 'BookedForYou') if company else 'BookedForYou'

        email_sent = email_service.send_password_reset(email, reset_link, business_name)
        if email_sent:
            print(f"[EMPLOYEE-FORGOT-PW] Reset email sent to {email}", flush=True)
        else:
            print(f"[EMPLOYEE-FORGOT-PW] Email service not configured - link logged above", flush=True)
    except Exception as e:
        print(f"[EMPLOYEE-FORGOT-PW] Email send error: {e}", flush=True)

    return jsonify(success_msg)


@app.route("/api/employee/auth/reset-password", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=300)
def employee_reset_password():
    """Reset password for an employee account using token"""
    from datetime import datetime

    data = request.json
    token = data.get('token', '').strip()
    new_password = data.get('new_password', '')

    if not token:
        return jsonify({"error": "Reset token is required"}), 400

    if not new_password:
        return jsonify({"error": "New password is required"}), 400

    password_error = _validate_password(new_password)
    if password_error:
        return jsonify({"error": password_error}), 400

    db = get_database()
    account = db.get_employee_account_by_reset_token(token)

    if not account:
        get_security_logger().log_failed_auth(
            '/api/employee/auth/reset-password',
            get_client_ip(),
            'Invalid employee reset token'
        )
        return jsonify({"error": "Invalid or expired reset link. Please request a new one."}), 400

    token_expires = account.get('reset_token_expires')
    if token_expires:
        if isinstance(token_expires, str):
            try:
                token_expires = datetime.fromisoformat(token_expires)
            except ValueError:
                token_expires = None
        if token_expires and datetime.now() > token_expires:
            db.update_employee_account_reset_token(account['id'], None, None)
            return jsonify({"error": "Reset link has expired. Please request a new one."}), 400

    new_hash = hash_password(new_password)
    success = db.reset_employee_account_password(account['id'], new_hash)

    if success:
        get_security_logger().log_password_change(
            f"employee:{account['id']}",
            get_client_ip()
        )
        return jsonify({
            "success": True,
            "message": "Password has been reset successfully. You can now log in."
        })

    return jsonify({"error": "Failed to reset password. Please try again."}), 500


@app.route("/api/employee/invite", methods=["POST"])
@login_required
@subscription_required
def invite_employee():
    """Create an employee account and generate invite link (owner only)"""
    company_id = session.get('company_id')
    data = request.json
    employee_id = data.get('employee_id')

    if not employee_id:
        return jsonify({"error": "Employee ID is required"}), 400

    db = get_database()

    # Verify the employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    if not employee.get('email'):
        return jsonify({"error": "Employee must have an email address to be invited"}), 400

    # Check if account already exists
    existing = db.get_employee_account_by_employee_id(employee_id)
    if existing and existing.get('password_set'):
        return jsonify({"error": "This employee already has an active account"}), 409

    # Generate invite token
    from datetime import datetime, timedelta
    invite_token = secrets.token_urlsafe(32)
    invite_expires = datetime.now() + timedelta(days=7)

    email = employee['email'].lower().strip()

    if existing:
        # Re-send invite: update the existing account's token
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE employee_accounts 
                SET invite_token = %s, invite_expires_at = %s, email = %s, updated_at = NOW()
                WHERE id = %s
            """, (invite_token, invite_expires, email, existing['id']))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[EMPLOYEE-INVITE] Failed to update invite: {e}")
            return jsonify({"error": "Failed to update invite. Please try again."}), 500
        finally:
            db.return_connection(conn)
    else:
        account_id = db.create_employee_account(
            employee_id=employee_id,
            company_id=company_id,
            email=email,
            invite_token=invite_token,
            invite_expires_at=invite_expires
        )
        if not account_id:
            return jsonify({"error": "This email is already registered as an employee on another account. An employee can currently only be linked to one company. Please use a different email address."}), 409

    # Build invite link
    origin = request.headers.get('Origin', '')
    if not origin:
        origin = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
    invite_link = f"{origin}/employee/set-password?token={invite_token}"

    # Try to send email
    email_sent = False
    try:
        from src.services.email_reminder import get_email_service
        email_service = get_email_service()
        company = db.get_company(company_id)
        business_name = company.get('company_name', 'Your Employer') if company else 'Your Employer'

        # Reuse password reset email template — same flow (click link to set password)
        email_sent = email_service.send_password_reset(
            to_email=email,
            reset_link=invite_link,
            business_name=business_name
        )
    except Exception as e:
        print(f"[EMPLOYEE-INVITE] Email send error: {e}")

    return jsonify({
        "success": True,
        "invite_link": invite_link,
        "email_sent": email_sent,
        "message": f"Invite {'sent to ' + email if email_sent else 'link generated. Share it with the employee manually.'}"
    })


@app.route("/api/employee/dashboard", methods=["GET"])
@employee_login_required
def employee_dashboard():
    """Get employee's dashboard data (their jobs and schedule)"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    db = get_database()
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    schedule = db.get_employee_schedule(employee_id)

    return jsonify({
        "success": True,
        "employee": {
            "id": employee['id'],
            "name": employee['name'],
            "phone": employee.get('phone', ''),
            "email": employee.get('email', ''),
            "trade_specialty": employee.get('trade_specialty', ''),
            "image_url": employee.get('image_url', ''),
            "status": employee.get('status', 'active'),
            "weekly_hours_expected": employee.get('weekly_hours_expected', 40.0)
        },
        "jobs": jobs,
        "schedule": schedule
    })


@app.route("/api/employee/profile", methods=["PUT"])
@employee_login_required
def update_employee_profile():
    """Allow employee to update their own profile (limited fields)"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    data = request.json

    # Employees can update phone and image
    allowed_fields = {}
    if 'phone' in data:
        allowed_fields['phone'] = sanitize_string(data['phone'], max_length=20)
    if 'image_url' in data:
        image_url = data['image_url']
        # Handle base64 image upload to R2
        if image_url and image_url.startswith('data:image/') and company_id:
            image_url = upload_base64_image_to_r2(image_url, company_id, 'employees')
        allowed_fields['image_url'] = image_url

    if not allowed_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    db = get_database()
    db.update_employee(employee_id, **allowed_fields)

    employee = db.get_employee(employee_id)
    return jsonify({
        "success": True,
        "employee": {
            "id": employee['id'],
            "name": employee['name'],
            "phone": employee.get('phone', ''),
            "email": employee.get('email', ''),
            "trade_specialty": employee.get('trade_specialty', ''),
            "image_url": employee.get('image_url', ''),
        }
    })


@app.route("/api/employee/jobs/<int:job_id>", methods=["GET"])
@employee_login_required
def employee_job_detail(job_id):
    """Get full job details for an employee (only if assigned to them)"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    db = get_database()

    # Verify employee is assigned to this job
    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    job_ids = [j['id'] for j in employee_jobs]
    if job_id not in job_ids:
        return jsonify({"error": "Job not found or not assigned to you"}), 404

    # Get full booking details
    booking = db.get_booking(job_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Job not found"}), 404

    # Get assigned employees for this job
    assigned_employees = db.get_job_employees(job_id, company_id=company_id)

    # Get appointment notes
    notes = db.get_appointment_notes(job_id)

    return jsonify({
        "success": True,
        "job": booking,
        "assigned_employees": assigned_employees,
        "notes": notes
    })


@app.route("/api/employee/jobs/<int:job_id>/photos", methods=["POST"])
@employee_login_required
def employee_upload_job_photo(job_id):
    """Allow employee to upload photos and videos to their assigned jobs.
    Accepts either:
      - JSON with base64 image: {"image": "data:image/..."}
      - Multipart form with file: file field named 'file' (for videos)
    """
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    db = get_database()

    # Verify employee is assigned to this job
    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    job_ids = [j['id'] for j in employee_jobs]
    if job_id not in job_ids:
        return jsonify({"error": "Job not found or not assigned to you"}), 404

    import json as _json
    import io
    from datetime import datetime as _dt

    ALLOWED_MEDIA_TYPES = {
        'image/png', 'image/jpeg', 'image/gif', 'image/webp',
        'video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo',
    }
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB

    media_url = None

    # Check if multipart file upload (videos)
    if request.files and 'file' in request.files:
        file = request.files['file']
        if not file or not file.filename:
            return jsonify({"error": "No file provided"}), 400

        content_type = file.content_type or ''
        if content_type not in ALLOWED_MEDIA_TYPES:
            return jsonify({"error": f"Unsupported file type: {content_type}"}), 400

        file_data = file.read()
        is_video = content_type.startswith('video/')
        max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE_BYTES

        if len(file_data) > max_size:
            limit_mb = max_size // (1024 * 1024)
            return jsonify({"error": f"File too large. Max {limit_mb}MB"}), 400

        try:
            from src.services.storage_r2 import upload_company_file, is_r2_enabled
            if not is_r2_enabled():
                return jsonify({"error": "Storage not configured"}), 500

            ext = content_type.split('/')[-1]
            if ext == 'quicktime':
                ext = 'mov'
            elif ext == 'x-msvideo':
                ext = 'avi'
            timestamp = _dt.now().strftime('%Y%m%d_%H%M%S')
            filename = f"job_media_{timestamp}_{secrets.token_hex(4)}.{ext}"

            media_url = upload_company_file(
                company_id=company_id,
                file_data=io.BytesIO(file_data),
                filename=filename,
                file_type='job_photos',
                content_type=content_type
            )
        except Exception as e:
            print(f"[ERROR] Employee media upload failed: {e}")
            return jsonify({"error": "Failed to upload file"}), 500
    else:
        # Base64 image upload
        data = request.json
        image_data = data.get('image') if data else None
        if not image_data:
            return jsonify({"error": "No image data provided"}), 400

        media_url = upload_base64_image_to_r2(image_data, company_id, 'job-photos')

    if not media_url or media_url.startswith('data:'):
        return jsonify({"error": "Failed to upload media"}), 500

    booking = db.get_booking(job_id, company_id=company_id)
    existing_photos = booking.get('photo_urls') or []
    if isinstance(existing_photos, str):
        try:
            import json as _json2
            existing_photos = _json2.loads(existing_photos)
        except Exception:
            existing_photos = []
    updated_photos = existing_photos + [media_url]

    # Use raw SQL for jsonb column (update_booking passes lists as text[] which fails)
    import json as _json
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE bookings SET photo_urls = %s WHERE id = %s AND company_id = %s",
            (_json.dumps(updated_photos), job_id, company_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to save media URL: {e}")
        return jsonify({"error": "Failed to save media"}), 500
    finally:
        cursor.close()
        db.return_connection(conn)

    return jsonify({"success": True, "photo_url": media_url, "photo_urls": updated_photos})


@app.route("/api/employee/jobs/<int:job_id>/notes", methods=["GET", "POST"])
@employee_login_required
def employee_job_notes(job_id):
    """Get or add notes to a job (employee can log what they did, materials used, etc.)"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    db = get_database()

    # Verify employee is assigned to this job
    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    job_ids = [j['id'] for j in employee_jobs]
    if job_id not in job_ids:
        return jsonify({"error": "Job not found or not assigned to you"}), 404

    if request.method == "GET":
        notes = db.get_appointment_notes(job_id)
        return jsonify({"success": True, "notes": notes})

    # POST - add a note
    data = request.json
    note_text = data.get('note', '').strip()
    if not note_text:
        return jsonify({"error": "Note text is required"}), 400

    # Get employee name for the created_by field
    employee = db.get_employee(employee_id, company_id=company_id)
    created_by = f"employee:{employee['name']}" if employee else "employee"

    note_id = db.add_appointment_note(
        booking_id=job_id,
        note=sanitize_string(note_text, max_length=2000),
        created_by=created_by
    )

    if note_id:
        return jsonify({"success": True, "id": note_id, "message": "Note added"}), 201
    return jsonify({"error": "Failed to add note"}), 500


@app.route("/api/employee/jobs/<int:job_id>/status", methods=["PUT"])
@employee_login_required
def employee_update_job_status(job_id):
    """Allow employee to update job status"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    db = get_database()

    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    job_ids = [j['id'] for j in employee_jobs]
    if job_id not in job_ids:
        return jsonify({"error": "Job not found or not assigned to you"}), 404

    data = request.json
    new_status = data.get('status', '').strip()

    allowed_statuses = ['pending', 'confirmed', 'quote_sent', 'scheduled', 'in-progress', 'completed', 'cancelled']
    if new_status not in allowed_statuses:
        return jsonify({"error": f"Invalid status. Allowed: {', '.join(allowed_statuses)}"}), 400

    # Build update kwargs
    update_kwargs = {'status': new_status}

    # Custom status label — free-text, per-job
    if 'status_label' in data:
        status_label = (data.get('status_label') or '').strip()
        update_kwargs['status_label'] = status_label if status_label else None
    elif new_status in ('completed', 'cancelled'):
        # Clear label when job reaches a terminal status
        update_kwargs['status_label'] = None

    # If starting job, record start time
    started_at = data.get('started_at')
    if started_at:
        update_kwargs['job_started_at'] = started_at

    # If completing job, record end time and actual duration
    completed_at = data.get('completed_at')
    if completed_at:
        update_kwargs['job_completed_at'] = completed_at

    actual_duration = data.get('actual_duration_minutes')
    if actual_duration is not None:
        try:
            update_kwargs['actual_duration_minutes'] = int(actual_duration)
        except (ValueError, TypeError):
            pass

    db.update_booking(job_id, company_id=company_id, **update_kwargs)

    # Auto-create next occurrence for recurring jobs
    if new_status == 'completed':
        try:
            booking = db.get_booking(job_id, company_id=company_id)
            pattern = booking.get('recurrence_pattern') if booking else None
            if pattern and pattern in ('weekly', 'biweekly', 'monthly', 'quarterly'):
                from datetime import datetime, timedelta
                end_date = booking.get('recurrence_end_date')
                appt = booking.get('appointment_time')
                if isinstance(appt, str):
                    appt = datetime.fromisoformat(appt.replace('Z', '+00:00')).replace(tzinfo=None)
                elif hasattr(appt, 'replace'):
                    appt = appt.replace(tzinfo=None)

                # Calculate next date
                if pattern == 'weekly':
                    next_date = appt + timedelta(weeks=1)
                elif pattern == 'biweekly':
                    next_date = appt + timedelta(weeks=2)
                elif pattern == 'monthly':
                    month = appt.month + 1
                    year = appt.year
                    if month > 12:
                        month = 1
                        year += 1
                    try:
                        next_date = appt.replace(year=year, month=month)
                    except ValueError:
                        # Handle months with fewer days
                        import calendar
                        last_day = calendar.monthrange(year, month)[1]
                        next_date = appt.replace(year=year, month=month, day=min(appt.day, last_day))
                elif pattern == 'quarterly':
                    month = appt.month + 3
                    year = appt.year
                    while month > 12:
                        month -= 12
                        year += 1
                    try:
                        next_date = appt.replace(year=year, month=month)
                    except ValueError:
                        import calendar
                        last_day = calendar.monthrange(year, month)[1]
                        next_date = appt.replace(year=year, month=month, day=min(appt.day, last_day))

                # Check if within end date
                skip = False
                if end_date:
                    if isinstance(end_date, str):
                        end_date = datetime.fromisoformat(end_date).replace(tzinfo=None)
                    if next_date.date() > end_date.date() if hasattr(end_date, 'date') else next_date > end_date:
                        skip = True

                if not skip:
                    # Create next booking
                    conn = db.get_connection()
                    try:
                        from psycopg2.extras import RealDictCursor
                        cur = conn.cursor(cursor_factory=RealDictCursor)
                        cur.execute("""
                            INSERT INTO bookings (company_id, client_id, appointment_time, service_type,
                                charge, charge_max, status, payment_status, address, eircode, property_type,
                                duration_minutes, requires_callout, requires_quote,
                                recurrence_pattern, recurrence_end_date, parent_booking_id,
                                created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, 'scheduled', 'unpaid', %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            RETURNING id
                        """, (
                            company_id, booking.get('client_id'), next_date.isoformat(),
                            booking.get('service_type'), booking.get('charge'), booking.get('charge_max'),
                            booking.get('address'), booking.get('eircode'), booking.get('property_type'),
                            booking.get('duration_minutes'), booking.get('requires_callout'), booking.get('requires_quote'),
                            pattern, booking.get('recurrence_end_date'), job_id
                        ))
                        new_booking = cur.fetchone()
                        new_id = new_booking['id']

                        # Copy employee assignments
                        cur.execute("""
                            INSERT INTO employee_assignments (booking_id, employee_id)
                            SELECT %s, employee_id FROM employee_assignments WHERE booking_id = %s
                        """, (new_id, job_id))
                        conn.commit()
                        cur.close()
                        print(f"[RECURRING] Created next occurrence #{new_id} for {next_date.isoformat()} from job #{job_id}")
                    except Exception as e:
                        conn.rollback()
                        print(f"[RECURRING] Failed to create next occurrence: {e}")
                    finally:
                        db.return_connection(conn)
        except Exception as e:
            print(f"[RECURRING] Error checking recurrence: {e}")

    return jsonify({"success": True, "status": new_status})


@app.route("/api/employee/jobs/bulk-complete", methods=["POST"])
@employee_login_required
def employee_bulk_complete_jobs():
    """Allow employee to mark multiple past jobs as completed at once"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    db = get_database()
    data = request.json or {}
    filter_type = data.get('filter', 'all')  # 'today', 'week', 'all'

    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)

    from datetime import datetime, timedelta
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())  # Monday

    completed_ids = []
    skipped_statuses = {'completed', 'cancelled'}

    for job in employee_jobs:
        if job['status'] in skipped_statuses:
            continue

        appt_time = job['appointment_time']
        if isinstance(appt_time, str):
            appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
        elif hasattr(appt_time, 'replace'):
            appt_time = appt_time.replace(tzinfo=None)

        # Only complete jobs whose appointment time is in the past
        if appt_time >= now:
            continue

        if filter_type == 'today' and appt_time < today_start:
            continue
        elif filter_type == 'week' and appt_time < week_start:
            continue

        completed_at = now.isoformat()
        db.update_booking(job['id'], company_id=company_id, status='completed', job_completed_at=completed_at)
        completed_ids.append(job['id'])

    return jsonify({
        "success": True,
        "completed_count": len(completed_ids),
        "completed_ids": completed_ids
    })


@app.route("/api/employee/jobs/<int:job_id>/details", methods=["PUT"])
@employee_login_required
def employee_update_job_details(job_id):
    """Allow employee to edit job details like actual charge and actual duration after completion"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    db = get_database()

    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    job_ids = [j['id'] for j in employee_jobs]
    if job_id not in job_ids:
        return jsonify({"error": "Job not found or not assigned to you"}), 404

    data = request.json
    update_kwargs = {}

    # Employees can update actual charge
    if 'actual_charge' in data:
        try:
            val = float(data['actual_charge']) if data['actual_charge'] not in (None, '') else None
            if val is not None and val >= 0:
                update_kwargs['charge'] = val
                update_kwargs['charge_max'] = None  # Clear range — actual charge is now final
        except (ValueError, TypeError):
            pass

    # Employees can update actual duration
    if 'actual_duration_minutes' in data:
        try:
            val = int(data['actual_duration_minutes'])
            if val > 0:
                update_kwargs['actual_duration_minutes'] = val
        except (ValueError, TypeError):
            pass

    # Employees can update job_started_at and job_completed_at
    if 'job_started_at' in data:
        update_kwargs['job_started_at'] = data['job_started_at']
    if 'job_completed_at' in data:
        update_kwargs['job_completed_at'] = data['job_completed_at']

    if not update_kwargs:
        return jsonify({"error": "No valid fields to update"}), 400

    db.update_booking(job_id, company_id=company_id, **update_kwargs)
    return jsonify({"success": True})


@app.route("/api/employee/time-off", methods=["GET", "POST"])
@employee_login_required
def employee_time_off():
    """Get or create time-off requests"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    db = get_database()

    if request.method == "GET":
        requests_list = db.get_employee_time_off(employee_id)
        return jsonify({"success": True, "requests": requests_list})

    # POST - create new request
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    reason = sanitize_string(data.get('reason', ''), max_length=500)
    leave_type = sanitize_string(data.get('type', 'vacation'), max_length=50)

    if not start_date or not end_date:
        return jsonify({"error": "Start and end dates are required"}), 400

    # Validate dates
    from datetime import datetime, date
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    if end < start:
        return jsonify({"error": "End date must be on or after start date"}), 400

    if start < date.today():
        return jsonify({"error": "Cannot request time off in the past"}), 400

    request_id = db.create_time_off_request(
        employee_id=employee_id,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        leave_type=leave_type
    )

    if request_id:
        # Check for existing bookings that conflict with the requested dates
        conflicting_jobs = []
        try:
            employee_jobs = db.get_employee_jobs(employee_id, include_completed=False, company_id=company_id)
            for job in employee_jobs:
                job_date = job.get('appointment_time')
                if job_date:
                    if isinstance(job_date, str):
                        job_date = datetime.fromisoformat(job_date.replace('Z', '+00:00'))
                    jd = job_date.date() if hasattr(job_date, 'date') else job_date
                    if start <= jd <= end and job.get('status') not in ('completed', 'cancelled'):
                        conflicting_jobs.append({
                            'id': job.get('id'),
                            'date': str(jd),
                            'service': job.get('service_type', 'Job'),
                            'client': job.get('client_name', '')
                        })
        except Exception:
            pass

        # Notify the owner about the time-off request
        try:
            employee = db.get_employee(employee_id, company_id=company_id)
            employee_name = employee['name'] if employee else 'An employee'
            db.create_notification(
                company_id=company_id,
                recipient_type='owner',
                recipient_id=company_id,
                notif_type='time_off_request',
                message=f"{employee_name} requested time off ({start_date} to {end_date})",
                metadata={'employee_id': employee_id, 'employee_name': employee_name,
                          'request_id': request_id, 'leave_type': leave_type}
            )
        except Exception as e:
            print(f"[WARNING] Could not create time-off notification: {e}")

        return jsonify({
            "success": True,
            "id": request_id,
            "message": "Time-off request submitted",
            "conflicting_jobs": conflicting_jobs,
            "has_conflicts": len(conflicting_jobs) > 0
        }), 201
    return jsonify({"error": "Failed to create request"}), 500


@app.route("/api/employee/time-off/<int:request_id>", methods=["DELETE"])
@employee_login_required
def employee_delete_time_off(request_id):
    """Delete a pending time-off request"""
    employee_id = session.get('employee_id')
    db = get_database()

    success = db.delete_time_off_request(request_id, employee_id)
    if success:
        return jsonify({"success": True, "message": "Request cancelled"})
    return jsonify({"error": "Cannot cancel this request (may already be reviewed)"}), 400


@app.route("/api/employee/change-password", methods=["POST"])
@employee_login_required
def employee_change_password():
    """Allow employee to change their password"""
    employee_id = session.get('employee_id')
    data = request.json

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({"error": "Current and new passwords are required"}), 400

    password_error = _validate_password(new_password)
    if password_error:
        return jsonify({"error": password_error}), 400

    db = get_database()
    account = db.get_employee_account_by_employee_id(employee_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    if not verify_password(current_password, account['password_hash']):
        return jsonify({"error": "Current password is incorrect"}), 401

    new_hash = hash_password(new_password)
    success = db.set_employee_account_password(account['id'], new_hash)

    if success:
        return jsonify({"success": True, "message": "Password changed successfully"})
    return jsonify({"error": "Failed to change password"}), 500


@app.route("/api/employee/hours-summary", methods=["GET"])
@employee_login_required
def employee_hours_summary():
    """Get employee's hours summary"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    db = get_database()

    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    # Get hours this week
    hours_data = db.get_employee_hours_this_week(employee_id)
    hours_this_week = hours_data if isinstance(hours_data, (int, float)) else 0

    # Get job counts
    all_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    active_jobs = [j for j in all_jobs if j['status'] not in ('completed', 'cancelled')]
    completed_jobs = [j for j in all_jobs if j['status'] == 'completed']

    return jsonify({
        "success": True,
        "hours_this_week": hours_this_week,
        "weekly_hours_expected": employee.get('weekly_hours_expected', 40.0),
        "active_jobs": len(active_jobs),
        "completed_jobs": len(completed_jobs),
        "total_jobs": len(all_jobs)
    })


@app.route("/api/employee/customers", methods=["GET"])
@employee_login_required
def employee_customers():
    """Get unique customers the employee has dealt with through their assigned jobs"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    db = get_database()

    conn = db.get_connection()
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT DISTINCT c.id, c.name, c.phone, c.email, c.address, c.eircode, c.description,
                   COUNT(b.id) as total_jobs,
                   COUNT(CASE WHEN b.status = 'completed' THEN 1 END) as completed_jobs,
                   MAX(b.appointment_time) as last_job_date
            FROM employee_assignments wa
            JOIN bookings b ON wa.booking_id = b.id
            JOIN clients c ON b.client_id = c.id
            WHERE wa.employee_id = %s AND b.company_id = %s
            GROUP BY c.id, c.name, c.phone, c.email, c.address, c.eircode, c.description
            ORDER BY MAX(b.appointment_time) DESC
        """, (employee_id, company_id))
        customers = [dict(row) for row in cursor.fetchall()]
    finally:
        db.return_connection(conn)

    return jsonify({"success": True, "customers": customers})


# --- Employee endpoints for job creation ---

@app.route("/api/employee/services", methods=["GET"])
@employee_login_required
def employee_services():
    """Get services menu for the employee's company"""
    company_id = session.get('employee_company_id')
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    menu = settings_mgr.get_services_menu(company_id=company_id)
    return jsonify(menu)


@app.route("/api/employee/clients", methods=["GET"])
@employee_login_required
def employee_clients():
    """Get all clients for the employee's company"""
    company_id = session.get('employee_company_id')
    db = get_database()
    clients = db.get_all_clients(company_id=company_id)
    return jsonify(clients)


@app.route("/api/employee/clients/<int:client_id>", methods=["GET"])
@employee_login_required
def employee_client_detail(client_id):
    """Get a single client's details"""
    company_id = session.get('employee_company_id')
    db = get_database()
    client = db.get_client(client_id, company_id=company_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404
    return jsonify(client)


@app.route("/api/employee/clients/create", methods=["POST"])
@employee_login_required
@rate_limit(max_requests=30, window_seconds=60)
def employee_create_client():
    """Create a new client as an employee"""
    company_id = session.get('employee_company_id')
    session['company_id'] = company_id
    return clients_api()


@app.route("/api/employee/employees", methods=["GET"])
@employee_login_required
def employee_list_employees():
    """Get all employees for the employee's company (for assigning to jobs)"""
    company_id = session.get('employee_company_id')
    db = get_database()
    employees = db.get_all_employees(company_id=company_id)
    return jsonify(employees)


@app.route("/api/employee/availability", methods=["GET"])
@employee_login_required
def employee_check_availability():
    """Check daily availability — mirrors /api/bookings/availability for employee context"""
    company_id = session.get('employee_company_id')
    session['company_id'] = company_id
    return check_availability_api()


@app.route("/api/employee/availability/month", methods=["GET"])
@employee_login_required
def employee_check_monthly_availability():
    """Check monthly availability — mirrors /api/bookings/availability/month for employee context"""
    company_id = session.get('employee_company_id')
    session['company_id'] = company_id
    return check_monthly_availability_api()


@app.route("/api/employee/employees/<int:wid>/availability", methods=["GET"])
@employee_login_required
def employee_check_employee_availability(wid):
    """Check a specific employee's availability — mirrors /api/employees/<id>/availability"""
    company_id = session.get('employee_company_id')
    session['company_id'] = company_id
    return check_employee_availability_api(wid)


@app.route("/api/employee/bookings", methods=["POST"])
@employee_login_required
@rate_limit(max_requests=30, window_seconds=60)
def employee_create_booking():
    """Create a new booking as an employee — reuses the owner booking creation logic"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')

    # Inject company_id so the existing bookings_api logic works
    session['company_id'] = company_id

    # Employee always gets assigned to their own job
    data = request.json
    employee_ids = data.get('employee_ids', [])
    if employee_id not in employee_ids:
        data['employee_ids'] = [employee_id] + employee_ids
    # Don't use auto_assign — we've explicitly set the employee(s)
    data['auto_assign_employee'] = False

    return bookings_api()


# --- Owner endpoints for managing time-off requests ---

@app.route("/api/time-off/requests", methods=["GET"])
@login_required
def get_time_off_requests():
    """Get all time-off requests for the company (owner view)"""
    company_id = session.get('company_id')
    db = get_database()
    status_filter = request.args.get('status')
    requests_list = db.get_company_time_off_requests(company_id, status=status_filter)
    return jsonify({"success": True, "requests": requests_list})


@app.route("/api/time-off/requests/<int:request_id>", methods=["PUT"])
@login_required
@subscription_required
def review_time_off_request(request_id):
    """Approve or deny a time-off request (owner only)"""
    company_id = session.get('company_id')
    data = request.json
    status = data.get('status')
    note = sanitize_string(data.get('note', ''), max_length=500)

    if status not in ('approved', 'denied'):
        return jsonify({"error": "Status must be 'approved' or 'denied'"}), 400

    db = get_database()
    success = db.update_time_off_status(request_id, company_id, status, note)

    if success:
        # If approving, check for conflicting bookings and return a warning
        conflicting_jobs = []
        if status == 'approved':
            try:
                all_requests = db.get_company_time_off_requests(company_id)
                the_req = next((r for r in all_requests if r['id'] == request_id), None)
                if the_req:
                    from datetime import datetime as _dt, date as _date
                    s = _dt.strptime(str(the_req['start_date']), '%Y-%m-%d').date() if isinstance(the_req['start_date'], str) else the_req['start_date']
                    e = _dt.strptime(str(the_req['end_date']), '%Y-%m-%d').date() if isinstance(the_req['end_date'], str) else the_req['end_date']
                    employee_jobs = db.get_employee_jobs(the_req['employee_id'], include_completed=False, company_id=company_id)
                    for job in employee_jobs:
                        job_date = job.get('appointment_time')
                        if job_date:
                            if isinstance(job_date, str):
                                job_date = _dt.fromisoformat(job_date.replace('Z', '+00:00'))
                            jd = job_date.date() if hasattr(job_date, 'date') else job_date
                            if s <= jd <= e and job.get('status') not in ('completed', 'cancelled'):
                                conflicting_jobs.append({
                                    'id': job.get('id'),
                                    'date': str(jd),
                                    'service': job.get('service_type', 'Job'),
                                    'client': job.get('client_name', '')
                                })
            except Exception:
                pass

        # Notify the employee about the decision
        try:
            # Look up the request to get the employee_id
            all_requests = db.get_company_time_off_requests(company_id)
            the_request = next((r for r in all_requests if r['id'] == request_id), None)
            if the_request:
                status_label = 'approved' if status == 'approved' else 'denied'
                msg = f"Your time-off request ({the_request['start_date']} to {the_request['end_date']}) was {status_label}"
                if note:
                    msg += f": {note}"
                db.create_notification(
                    company_id=company_id,
                    recipient_type='employee',
                    recipient_id=the_request['employee_id'],
                    notif_type=f'time_off_{status_label}',
                    message=msg,
                    metadata={'request_id': request_id, 'status': status_label}
                )

                # Sync approved time-off to Google Calendar
                if status == 'approved':
                    try:
                        from src.services.google_calendar_oauth import get_company_google_calendar
                        gcal = get_company_google_calendar(company_id, db)
                        if gcal and gcal.is_valid():
                            employee_name = the_request.get('employee_name', 'Employee')
                            leave_type = the_request.get('leave_type', 'time off')
                            emoji = '🏖️' if leave_type == 'vacation' else '🤒' if leave_type == 'sick' else '📅'
                            summary = f"{emoji} {employee_name} - {leave_type.title()}"
                            description = f"Employee time off ({leave_type})"
                            if note:
                                description += f"\nNote: {note}"
                            gcal.create_all_day_event(
                                summary=summary,
                                start_date=the_request['start_date'],
                                end_date=the_request['end_date'],
                                description=description
                            )
                    except Exception as e:
                        print(f"[WARNING] Could not sync time-off to Google Calendar: {e}")

        except Exception as e:
            print(f"[WARNING] Could not create time-off review notification: {e}")

        return jsonify({
            "success": True,
            "message": f"Request {status}",
            "conflicting_jobs": conflicting_jobs,
            "has_conflicts": len(conflicting_jobs) > 0
        })
    return jsonify({"error": "Request not found"}), 404


# ============================================
# PHONE NUMBER MANAGEMENT ENDPOINTS
# ============================================

@app.route("/api/phone-numbers/available", methods=["GET"])
@login_required
def get_available_phone_numbers():
    """Get list of available phone numbers"""
    db = get_database()
    
    try:
        available_numbers = db.get_available_phone_numbers()
        return jsonify({
            "success": True,
            "numbers": available_numbers,
            "count": len(available_numbers)
        })
    except AttributeError as e:
        # Method doesn't exist - return friendly error
        print(f"[WARNING] Method not found: {e}")
        return jsonify({
            "success": False,
            "error": "Phone number management not configured",
            "numbers": []
        }), 500
    except Exception as e:
        print(f"[ERROR] Error getting phone numbers: {e}")
        return jsonify({
            "success": False,
            "error": f"Database error: {str(e)}",
            "numbers": []
        }), 500


@app.route("/api/phone-numbers/assign", methods=["POST"])
@login_required
@subscription_required
def assign_phone_number():
    """Assign a phone number to the current company"""
    data = request.json
    phone_number = data.get('phone_number')
    
    if not phone_number:
        return jsonify({"error": "Phone number is required"}), 400
    
    db = get_database()
    company_id = session['company_id']
    
    # Only pro plan accounts can have a phone number
    company = db.get_company(company_id)
    if company.get('subscription_plan', 'pro') == 'dashboard':
        return jsonify({
            "success": False,
            "error": "Phone numbers are only available on the Pro plan. Please upgrade to assign a number."
        }), 403
    
    # Check if company already has a phone number
    if company.get('twilio_phone_number'):
        return jsonify({
            "success": False,
            "error": "Company already has a phone number assigned"
        }), 400
    
    try:
        assigned_number = db.assign_phone_number(company_id, phone_number)
        return jsonify({
            "success": True,
            "message": "Phone number assigned successfully",
            "phone_number": assigned_number
        })
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Phone assignment failed for company {company_id}: {error_msg}")
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400


@app.route("/api/phone-numbers/current", methods=["GET"])
@login_required
def get_current_phone_number():
    """Get the current company's assigned phone number"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    return jsonify({
        "success": True,
        "phone_number": company.get('twilio_phone_number'),
        "has_phone": bool(company.get('twilio_phone_number'))
    })


# ============================================
# ADMIN MANAGED SETUP ENDPOINTS
# ============================================

from datetime import datetime, timedelta  # ensure available for admin endpoints

ADMIN_SECRET = os.getenv('ADMIN_SECRET', '')


def admin_required(f):
    """Decorator to require admin secret for admin-only endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('X-Admin-Secret', '')
        if not ADMIN_SECRET or auth_header != ADMIN_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route("/api/admin/create-account", methods=["POST"])
@admin_required
@rate_limit(max_requests=20, window_seconds=60)
def admin_create_account():
    """Admin endpoint to create a managed account (easy_setup=false).
    Creates the company, optionally assigns phone, sets context, adds employees, etc.
    Returns an invite link for the owner to set their password.
    """
    data = request.json or {}

    # Validate required fields
    required = ['company_name', 'owner_name', 'email']
    for field in required:
        if not data.get(field, '').strip():
            return jsonify({"error": f"{field.replace('_', ' ').title()} is required"}), 400

    email = data['email'].lower().strip()
    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    company_name = sanitize_string(data['company_name'], max_length=200)
    owner_name = sanitize_string(data['owner_name'], max_length=200)

    db = get_database()

    # Check if email already exists
    existing = db.get_company_by_email(email)
    if existing:
        return jsonify({"error": "An account with this email already exists"}), 409

    # Create with a placeholder password hash (owner will set real password via invite)
    placeholder_hash = hash_password(secrets.token_hex(32))
    company_id = db.create_company(
        company_name=company_name,
        owner_name=owner_name,
        email=email,
        password_hash=placeholder_hash,
        phone=sanitize_string(data.get('phone', ''), max_length=20),
        trade_type=sanitize_string(data.get('trade_type', ''), max_length=100)
    )

    if not company_id:
        return jsonify({"error": "Failed to create account"}), 500

    # Set managed setup flags
    update_fields = {
        'easy_setup': False,
        'setup_wizard_complete': True,
    }

    # Set subscription (admin can activate directly)
    sub_tier = data.get('subscription_tier', 'pro')
    sub_status = data.get('subscription_status', 'active')
    update_fields['subscription_tier'] = sub_tier
    update_fields['subscription_status'] = sub_status

    # Set subscription plan (dashboard, starter, professional, or business)
    sub_plan = data.get('subscription_plan', 'professional')
    if sub_plan in ('dashboard', 'starter', 'professional', 'business', 'enterprise', 'pro'):
        update_fields['subscription_plan'] = sub_plan

    # Optional fields the admin can set
    if data.get('company_context'):
        update_fields['company_context'] = sanitize_string(data['company_context'], max_length=5000)
    if data.get('coverage_area'):
        update_fields['coverage_area'] = sanitize_string(data['coverage_area'], max_length=1000)
    if data.get('business_hours'):
        update_fields['business_hours'] = data['business_hours']
    if data.get('address'):
        update_fields['address'] = sanitize_string(data['address'], max_length=500)
    if data.get('industry_type'):
        update_fields['industry_type'] = sanitize_string(data['industry_type'], max_length=50)

    # Usage-based pricing fields
    if data.get('included_minutes') is not None and data.get('included_minutes') != '':
        try:
            update_fields['included_minutes'] = int(data['included_minutes'])
        except (ValueError, TypeError):
            pass
    if data.get('overage_rate_cents') is not None and data.get('overage_rate_cents') != '':
        try:
            update_fields['overage_rate_cents'] = int(data['overage_rate_cents'])
        except (ValueError, TypeError):
            pass
    if data.get('max_monthly_overage_cents') is not None and data.get('max_monthly_overage_cents') != '':
        try:
            update_fields['max_monthly_overage_cents'] = int(data['max_monthly_overage_cents'])
        except (ValueError, TypeError):
            pass
    
    # Enterprise plan defaults to unlimited if not specified
    if sub_plan == 'enterprise' and 'included_minutes' not in update_fields:
        update_fields['included_minutes'] = 99999
        update_fields['overage_rate_cents'] = 0
    # For other plans, set defaults from PLANS config if not specified
    elif sub_plan in ('starter', 'professional', 'business') and 'included_minutes' not in update_fields:
        from src.services.stripe_service import PLANS as STRIPE_PLANS
        plan_cfg = STRIPE_PLANS.get(sub_plan, {})
        update_fields['included_minutes'] = plan_cfg.get('included_minutes', 200)
        update_fields['overage_rate_cents'] = plan_cfg.get('overage_rate_cents', 12)

    # Custom per-account pricing (per-plan)
    for plan_key in ('dashboard', 'pro'):
        price_field = f'custom_{plan_key}_price'
        stripe_field = f'custom_{plan_key}_stripe_price_id'
        
        price_val = data.get(price_field)
        if price_val is not None and price_val != '':
            try:
                update_fields[price_field] = float(price_val)
            except (ValueError, TypeError):
                pass
        
        stripe_val = data.get(stripe_field, '').strip() if data.get(stripe_field) else None
        if stripe_val:
            update_fields[stripe_field] = stripe_val

    # Set the active custom price based on the selected plan
    active_plan = sub_plan
    plan_price = data.get(f'custom_{active_plan}_price')
    plan_stripe_id = data.get(f'custom_{active_plan}_stripe_price_id', '').strip() if data.get(f'custom_{active_plan}_stripe_price_id') else None
    
    if plan_price is not None and plan_price != '':
        try:
            update_fields['custom_monthly_price'] = float(plan_price)
        except (ValueError, TypeError):
            pass
    if plan_stripe_id:
        update_fields['custom_stripe_price_id'] = plan_stripe_id

    # Generate owner invite token (7-day expiry)
    invite_token = secrets.token_urlsafe(32)
    invite_expires = datetime.now() + timedelta(days=7)
    update_fields['owner_invite_token'] = invite_token
    update_fields['owner_invite_expires'] = invite_expires

    db.update_company(company_id, **update_fields)

    # Assign phone number if requested (AI plans only)
    assigned_phone = None
    if sub_plan in ('pro', 'starter', 'professional', 'business', 'enterprise'):
        if data.get('phone_number'):
            try:
                assigned_phone = db.assign_phone_number(company_id, data['phone_number'])
            except Exception as e:
                print(f"[ADMIN] Phone assignment failed: {e}")
        elif data.get('auto_assign_phone'):
            try:
                assigned_phone = db.assign_phone_number(company_id)
            except Exception as e:
                print(f"[ADMIN] Auto phone assignment failed: {e}")

    # Add employees if provided
    employees_created = []
    for employee_data in data.get('employees', []):
        if not employee_data.get('name'):
            continue
        try:
            employee_id = db.add_employee(
                name=sanitize_string(employee_data['name'], max_length=200),
                phone=sanitize_string(employee_data.get('phone', ''), max_length=20),
                email=employee_data.get('email', '').lower().strip() if employee_data.get('email') else None,
                trade_specialty=sanitize_string(employee_data.get('trade_specialty', ''), max_length=200),
                company_id=company_id
            )
            if employee_id:
                employees_created.append({'id': employee_id, 'name': employee_data['name']})
        except Exception as e:
            print(f"[ADMIN] Employee creation failed: {e}")

    # Add services if provided
    services_created = []
    for svc in data.get('services', []):
        if not svc.get('name'):
            continue
        try:
            from src.services.settings_manager import get_settings_manager
            mgr = get_settings_manager()
            svc_dict = {
                'id': f"admin_{company_id}_{secrets.token_hex(4)}",
                'category': svc.get('category', 'General'),
                'name': svc['name'],
                'description': svc.get('description', ''),
                'duration_minutes': int(svc.get('duration_minutes', 60)),
                'price': float(svc.get('price', 0)),
                'emergency_price': float(svc['emergency_price']) if svc.get('emergency_price') else None,
                'currency': svc.get('currency', 'EUR'),
                'active': True,
                'sort_order': svc.get('sort_order', 100),
                'requires_callout': svc.get('requires_callout', False),
                'requires_quote': svc.get('requires_quote', False),
            }
            mgr.add_service(svc_dict, company_id=company_id)
            services_created.append(svc['name'])
        except Exception as e:
            print(f"[ADMIN] Service creation failed: {e}")

    # Build invite link
    # Admin calls come from curl/API tools, not the browser, so we can't rely on Origin header.
    # Use explicit frontend_url param, or fall back to the first production frontend origin.
    frontend_url = data.get('frontend_url', '').strip()
    if not frontend_url:
        # Try Origin header (in case called from a browser)
        frontend_url = request.headers.get('Origin', '').strip()
    if not frontend_url:
        # Fall back to PUBLIC_URL (works when frontend is served from same domain as backend)
        frontend_url = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
    invite_link = f"{frontend_url}/set-password?token={invite_token}"

    # Try to send invite email
    email_sent = False
    try:
        from src.services.email_reminder import get_email_service
        email_service = get_email_service()
        email_sent = email_service.send_password_reset(
            to_email=email,
            reset_link=invite_link,
            business_name=company_name
        )
    except Exception as e:
        print(f"[ADMIN] Email send error: {e}")

    return jsonify({
        "success": True,
        "company_id": company_id,
        "invite_link": invite_link,
        "email_sent": email_sent,
        "phone_number": assigned_phone,
        "employees_created": employees_created,
        "services_created": services_created,
        "message": f"Account created for {company_name}. {'Invite email sent to ' + email if email_sent else 'Share the invite link manually.'}"
    }), 201


@app.route("/api/admin/accounts", methods=["GET"])
@admin_required
def admin_list_accounts():
    """List all company accounts for admin management."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, company_name, owner_name, email, phone, trade_type,
                   subscription_tier, subscription_status, twilio_phone_number,
                   easy_setup, setup_wizard_complete, created_at
            FROM companies ORDER BY id DESC
        """)
        accounts = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        # Convert datetime objects to strings
        for acc in accounts:
            for key in list(acc.keys()):
                if acc.get(key) and hasattr(acc[key], 'isoformat'):
                    acc[key] = acc[key].isoformat()
        return jsonify({"success": True, "accounts": accounts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/admin/accounts/<int:company_id>", methods=["GET"])
@admin_required
def admin_get_account(company_id):
    """Get full details of a specific account."""
    db = get_database()
    company = db.get_company(company_id)
    if not company:
        return jsonify({"error": "Account not found"}), 404

    # Get employees for this company
    employees = db.get_all_employees(company_id=company_id)

    # Convert datetime fields in company
    for key in list(company.keys()):
        if company.get(key) and hasattr(company[key], 'isoformat'):
            company[key] = company[key].isoformat()

    # Convert datetime fields in employees
    for w in employees:
        for key in list(w.keys()):
            if w.get(key) and hasattr(w[key], 'isoformat'):
                w[key] = w[key].isoformat()

    return jsonify({
        "success": True,
        "account": company,
        "employees": employees
    })


@app.route("/api/admin/accounts/<int:company_id>", methods=["PUT"])
@admin_required
def admin_update_account(company_id):
    """Update any field on a company account (admin only)."""
    data = request.json or {}
    db = get_database()

    company = db.get_company(company_id)
    if not company:
        return jsonify({"error": "Account not found"}), 404

    update_fields = {}
    # Allow admin to update these fields
    admin_updatable = [
        'company_name', 'owner_name', 'phone', 'email', 'trade_type',
        'address', 'business_hours', 'company_context', 'coverage_area',
        'subscription_tier', 'subscription_status', 'ai_enabled',
        'subscription_plan', 'industry_type',
        'easy_setup', 'setup_wizard_complete',
        'send_confirmation_sms', 'send_reminder_sms',
        'show_finances_tab', 'show_insights_tab', 'show_invoice_buttons',
        'bank_iban', 'bank_bic', 'bank_name', 'bank_account_holder',
        'revolut_phone', 'bypass_numbers', 'ai_schedule',
        'custom_stripe_price_id', 'custom_monthly_price',
        'custom_dashboard_price', 'custom_dashboard_stripe_price_id',
        'custom_pro_price', 'custom_pro_stripe_price_id',
        'admin_tab_visibility',
        'included_minutes', 'overage_rate_cents', 'minutes_used',
        'usage_period_start', 'usage_period_end', 'usage_alert_sent',
        'max_monthly_overage_cents',
    ]
    for field in admin_updatable:
        if field in data:
            update_fields[field] = data[field]

    # Handle per-plan custom pricing fields — allow clearing by sending empty/null
    for plan_key in ('dashboard', 'pro'):
        price_field = f'custom_{plan_key}_price'
        stripe_field = f'custom_{plan_key}_stripe_price_id'
        
        if price_field in data:
            val = data[price_field]
            if val is not None and val != '':
                try:
                    update_fields[price_field] = float(val)
                except (ValueError, TypeError):
                    update_fields[price_field] = None
            else:
                update_fields[price_field] = None
        
        if stripe_field in data:
            val = data[stripe_field]
            update_fields[stripe_field] = val.strip() if val else None

    # Sync the active custom price fields based on the account's current plan
    current_plan = data.get('subscription_plan') or company.get('subscription_plan', 'pro')
    active_price = update_fields.get(f'custom_{current_plan}_price', company.get(f'custom_{current_plan}_price'))
    active_stripe_id = update_fields.get(f'custom_{current_plan}_stripe_price_id', company.get(f'custom_{current_plan}_stripe_price_id'))
    
    if active_price is not None:
        try:
            update_fields['custom_monthly_price'] = float(active_price)
        except (ValueError, TypeError):
            update_fields['custom_monthly_price'] = None
    else:
        update_fields['custom_monthly_price'] = None
    update_fields['custom_stripe_price_id'] = active_stripe_id.strip() if active_stripe_id else None

    if update_fields:
        db.update_company(company_id, **update_fields)

    return jsonify({"success": True, "message": "Account updated"})


@app.route("/api/admin/accounts/<int:company_id>/resend-invite", methods=["POST"])
@admin_required
def admin_resend_invite(company_id):
    """Regenerate and resend the owner invite link."""
    db = get_database()
    company = db.get_company(company_id)
    if not company:
        return jsonify({"error": "Account not found"}), 404

    invite_token = secrets.token_urlsafe(32)
    invite_expires = datetime.now() + timedelta(days=7)
    db.update_company(company_id,
                      owner_invite_token=invite_token,
                      owner_invite_expires=invite_expires)

    data = request.json or {}
    frontend_url = data.get('frontend_url', '').strip()
    if not frontend_url:
        frontend_url = request.headers.get('Origin', '').strip()
    if not frontend_url:
        frontend_url = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
    invite_link = f"{frontend_url}/set-password?token={invite_token}"

    email_sent = False
    try:
        from src.services.email_reminder import get_email_service
        email_service = get_email_service()
        email_sent = email_service.send_password_reset(
            to_email=company['email'],
            reset_link=invite_link,
            business_name=company.get('company_name', 'Your Business')
        )
    except Exception as e:
        print(f"[ADMIN] Resend invite email error: {e}")

    return jsonify({
        "success": True,
        "invite_link": invite_link,
        "email_sent": email_sent
    })


@app.route("/api/admin/accounts/<int:company_id>/assign-phone", methods=["POST"])
@admin_required
def admin_assign_phone(company_id):
    """Assign a phone number to a company (admin)."""
    data = request.json or {}
    phone_number = data.get('phone_number')

    db = get_database()
    company = db.get_company(company_id)
    if not company:
        return jsonify({"error": "Account not found"}), 404

    if company.get('subscription_plan', 'pro') == 'dashboard':
        return jsonify({"error": "Phone numbers are only available on the Pro plan"}), 400

    if company.get('twilio_phone_number'):
        return jsonify({"error": "Company already has a phone number assigned"}), 400

    try:
        assigned = db.assign_phone_number(company_id, phone_number)
        return jsonify({"success": True, "phone_number": assigned})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/admin/accounts/<int:company_id>/impersonate", methods=["POST"])
@admin_required
def admin_impersonate(company_id):
    """Log in as a specific company account (admin only).
    Returns an auth token that the frontend can use to access the account.
    """
    db = get_database()
    company = db.get_company(company_id)
    if not company:
        return jsonify({"error": "Account not found"}), 404

    # Generate an auth token for this company
    auth_token = generate_auth_token(company['id'], company['email'])

    return jsonify({
        "success": True,
        "auth_token": auth_token,
        "user": {
            "id": company['id'],
            "company_name": company['company_name'],
            "owner_name": company['owner_name'],
            "email": company['email'],
            "phone": company['phone'],
            "trade_type": company['trade_type'],
            "address": company.get('address'),
            "logo_url": company.get('logo_url'),
            "subscription_tier": company['subscription_tier'],
            "subscription_status": company['subscription_status'],
            "twilio_phone_number": company.get('twilio_phone_number'),
            "easy_setup": company.get('easy_setup', True)
        }
    })


@app.route("/api/admin/phone-numbers/available", methods=["GET"])
@admin_required
def admin_available_phone_numbers():
    """Get available phone numbers (admin only)."""
    db = get_database()
    try:
        available_numbers = db.get_available_phone_numbers()
        return jsonify({"success": True, "numbers": available_numbers, "count": len(available_numbers)})
    except Exception as e:
        return jsonify({"success": False, "numbers": [], "error": str(e)}), 500


@app.route("/api/owner/set-password", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=300)
def owner_set_password():
    """Set password for an owner account using invite token (managed setup flow)."""
    data = request.json or {}
    token = data.get('token', '').strip()
    new_password = data.get('password', '')

    if not token:
        return jsonify({"error": "Invite token is required"}), 400

    if not new_password:
        return jsonify({"error": "Password is required"}), 400

    password_error = _validate_password(new_password)
    if password_error:
        return jsonify({"error": password_error}), 400

    db = get_database()

    # Find company by invite token
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT * FROM companies WHERE owner_invite_token = %s",
            (token,)
        )
        company = cursor.fetchone()
        cursor.close()
    finally:
        db.return_connection(conn)

    if not company:
        return jsonify({"error": "Invalid or expired invite link."}), 400

    # Check expiry
    expires = company.get('owner_invite_expires')
    if expires:
        if isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires)
            except ValueError:
                expires = None
        if expires and datetime.now() > expires:
            return jsonify({"error": "Invite link has expired. Please contact support for a new one."}), 400

    # Set the password and clear the invite token
    password_hash_val = hash_password(new_password)
    db.update_company(
        company['id'],
        password_hash=password_hash_val,
        owner_invite_token=None,
        owner_invite_expires=None
    )

    return jsonify({
        "success": True,
        "message": "Password set successfully! You can now log in."
    })


# ============================================
# SUBSCRIPTION & STRIPE ENDPOINTS
# ============================================

from datetime import datetime, timedelta
from src.services.stripe_service import (
    create_checkout_session,
    create_billing_portal_session,
    get_subscription_status,
    cancel_subscription,
    reactivate_subscription,
    upgrade_subscription,
    handle_webhook_event,
    get_customer_invoices,
    get_or_create_customer,
    is_stripe_configured,
    get_plan_from_price_id,
    TRIAL_DAYS,
    PLANS
)

# Webhook secret for Stripe events
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')


def _ensure_payment_columns(db):
    """Ensure bank/payment columns exist in companies table.
    Note: These columns are created by _run_migrations() at startup.
    This function is kept as a safety net for edge cases.
    """
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        for col_name, col_type in {
            'bank_iban': 'TEXT', 'bank_bic': 'TEXT', 'bank_name': 'TEXT',
            'bank_account_holder': 'TEXT', 'revolut_phone': 'TEXT',
        }.items():
            try:
                cursor.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}")
                conn.commit()
            except Exception:
                conn.rollback()
    finally:
        db.return_connection(conn)


@app.route("/api/subscription/status", methods=["GET"])
@login_required
def get_subscription_status_endpoint():
    """Get current subscription status"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    subscription_info = get_subscription_info(company)
    
    # Debug logging
    print(f"[SUBSCRIPTION_STATUS] Company {company['id']}: tier={subscription_info['tier']}, is_active={subscription_info['is_active']}, stripe_sub_id={company.get('stripe_subscription_id')}")
    
    return jsonify({
        "success": True,
        "subscription": subscription_info
    })


@app.route("/api/subscription/create-checkout", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)
def create_checkout():
    """Create a Stripe checkout session for subscription"""
    print(f"[CHECKOUT] ========== CREATE CHECKOUT CALLED ==========")
    print(f"[CHECKOUT] Company ID from session: {session.get('company_id')}")
    
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        print(f"[CHECKOUT] ERROR: Company not found!")
        return jsonify({"error": "Company not found"}), 404
    
    print(f"[CHECKOUT] Company: {company['id']} ({company['email']})")
    print(f"[CHECKOUT] Current stripe_customer_id: {company.get('stripe_customer_id')}")
    
    if not is_stripe_configured():
        print(f"[CHECKOUT] ERROR: Stripe not configured!")
        return jsonify({"error": "Payment system not configured"}), 503
    
    data = request.json or {}
    
    # Get base URL for redirects
    base_url = data.get('base_url', os.getenv('FRONTEND_URL', 'http://localhost:3000'))
    plan = data.get('plan', 'pro')
    
    # Validate plan
    if plan not in ('dashboard', 'starter', 'professional', 'business', 'enterprise', 'pro'):
        return jsonify({"error": "Invalid plan. Choose 'starter', 'professional', or 'business'."}), 400
    
    print(f"[CHECKOUT] Base URL: {base_url}")
    print(f"[CHECKOUT] Plan: {plan}")
    
    # Use per-plan custom price if set for the selected plan
    custom_price_id = company.get(f'custom_{plan}_stripe_price_id') or None
    
    result = create_checkout_session(
        company_id=company['id'],
        email=company['email'],
        company_name=company['company_name'],
        success_url=f"{base_url}/settings?subscription=success",
        cancel_url=f"{base_url}/settings?subscription=cancelled",
        with_trial=False,  # Trial is handled separately via start-trial endpoint
        plan=plan,
        custom_price_id=custom_price_id,
        existing_customer_id=company.get('stripe_customer_id')
    )
    
    if result:
        print(f"[CHECKOUT] Checkout session created successfully:")
        print(f"[CHECKOUT]   - session_id: {result.get('session_id')}")
        print(f"[CHECKOUT]   - customer_id: {result.get('customer_id')}")
        
        # Save the Stripe customer ID immediately so sync can work even before webhook
        if result.get('customer_id'):
            if not company.get('stripe_customer_id'):
                db.update_company(company['id'], stripe_customer_id=result['customer_id'])
                print(f"[CHECKOUT] SAVED stripe_customer_id={result['customer_id']} to database for company {company['id']}")
            else:
                print(f"[CHECKOUT] stripe_customer_id already exists: {company.get('stripe_customer_id')}")
        
        # Verify it was saved
        updated_company = db.get_company(company['id'])
        print(f"[CHECKOUT] Verified stripe_customer_id in DB: {updated_company.get('stripe_customer_id')}")
        
        return jsonify({
            "success": True,
            "checkout_url": result['url'],
            "session_id": result['session_id']
        })
    else:
        print(f"[CHECKOUT] ERROR: create_checkout_session returned None!")
        return jsonify({"error": "Failed to create checkout session"}), 500


@app.route("/api/subscription/upgrade", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)
def upgrade_plan():
    """Upgrade an existing subscription to a higher plan (e.g. dashboard -> pro)"""
    db = get_database()
    company = db.get_company(session['company_id'])

    if not company:
        return jsonify({"error": "Company not found"}), 404

    subscription_id = company.get('stripe_subscription_id')
    if not subscription_id:
        return jsonify({"error": "No active subscription to upgrade. Please subscribe first."}), 400

    data = request.json or {}
    new_plan = data.get('plan', 'professional')

    if new_plan not in ('dashboard', 'starter', 'professional', 'business', 'enterprise', 'pro'):
        return jsonify({"error": "Invalid plan"}), 400

    current_plan = company.get('subscription_plan', 'pro')
    if current_plan == new_plan:
        return jsonify({"error": f"You are already on the {new_plan} plan"}), 400

    custom_price_id = company.get(f'custom_{new_plan}_stripe_price_id') or None

    result = upgrade_subscription(subscription_id, new_plan=new_plan, custom_price_id=custom_price_id)

    if result:
        db.update_company(company['id'], subscription_plan=new_plan)
        return jsonify({"success": True, "plan": new_plan})
    else:
        return jsonify({"error": "Failed to upgrade subscription. Please try again or contact support."}), 500


@app.route("/api/subscription/start-trial", methods=["POST"])
@login_required
@rate_limit(max_requests=5, window_seconds=300)
def start_trial():
    """Start a one-time 14-day free trial"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    # Check if already on active trial or pro
    subscription_info = get_subscription_info(company)
    if subscription_info['is_active'] and subscription_info['tier'] == 'pro':
        return jsonify({"error": "You already have an active Pro subscription"}), 400
    
    if subscription_info['is_active'] and subscription_info['tier'] == 'trial':
        return jsonify({"error": "You already have an active trial"}), 400
    
    # Prevent re-use of the free trial
    # Also check trial_start/trial_end for legacy accounts created before has_used_trial column existed
    if company.get('has_used_trial') or company.get('trial_start'):
        return jsonify({"error": "Free trial has already been used. Please subscribe to continue."}), 400
    
    # Start 14-day trial
    from datetime import timedelta
    trial_start = datetime.now()
    trial_end = trial_start + timedelta(days=14)
    
    db.update_company(
        company['id'],
        subscription_tier='trial',
        subscription_status='active',
        trial_start=trial_start,
        trial_end=trial_end,
        has_used_trial=1,
        # Trial users get 1000 minutes during their 14 days
        included_minutes=1000,
        overage_rate_cents=0,
        minutes_used=0,
        usage_period_start=trial_start,
        usage_period_end=trial_end,
        usage_alert_sent=False,
    )
    
    print(f"[SUCCESS] Free trial started for company {company['id']} until {trial_end}")
    
    return jsonify({
        "success": True,
        "message": "Your 14-day free trial has started!",
        "trial_end": trial_end.isoformat()
    })


@app.route("/api/subscription/billing-portal", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)
def billing_portal():
    """Create a Stripe billing portal session"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    # Enterprise accounts are billed manually, no Stripe portal available
    if company.get('subscription_plan') == 'enterprise':
        return jsonify({
            "error": "Enterprise accounts are billed manually. Please contact support at contact@bookedforyou.ie for billing inquiries."
        }), 400
    
    customer_id = company.get('stripe_customer_id')
    if not customer_id:
        return jsonify({"error": "No billing account found. Please subscribe first."}), 400
    
    data = request.json or {}
    base_url = data.get('base_url', os.getenv('FRONTEND_URL', 'http://localhost:3000'))
    
    portal_url = create_billing_portal_session(customer_id, f"{base_url}/settings")
    
    if portal_url:
        return jsonify({
            "success": True,
            "portal_url": portal_url
        })
    else:
        return jsonify({"error": "Failed to create billing portal session"}), 500


@app.route("/api/subscription/cancel", methods=["POST"])
@login_required
@rate_limit(max_requests=5, window_seconds=300)
def cancel_subscription_endpoint():
    """Cancel subscription at end of billing period"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    subscription_id = company.get('stripe_subscription_id')
    if not subscription_id:
        return jsonify({"error": "No active subscription found"}), 400
    
    success = cancel_subscription(subscription_id, at_period_end=True)
    
    if success:
        # Update local database
        db.update_company(session['company_id'], subscription_cancel_at_period_end=1)
        
        return jsonify({
            "success": True,
            "message": "Subscription will be cancelled at the end of the billing period"
        })
    else:
        return jsonify({"error": "Failed to cancel subscription"}), 500


@app.route("/api/subscription/reactivate", methods=["POST"])
@login_required
@rate_limit(max_requests=5, window_seconds=300)
def reactivate_subscription_endpoint():
    """Reactivate a subscription that was set to cancel"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    subscription_id = company.get('stripe_subscription_id')
    if not subscription_id:
        return jsonify({"error": "No subscription found"}), 400
    
    success = reactivate_subscription(subscription_id)
    
    if success:
        # Update local database
        db.update_company(session['company_id'], subscription_cancel_at_period_end=0)
        
        return jsonify({
            "success": True,
            "message": "Subscription has been reactivated"
        })
    else:
        return jsonify({"error": "Failed to reactivate subscription"}), 500


@app.route("/api/subscription/invoices", methods=["GET"])
@login_required
def get_invoices():
    """Get billing invoices for the company"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    customer_id = company.get('stripe_customer_id')
    if not customer_id:
        return jsonify({"success": True, "invoices": []})
    
    invoices = get_customer_invoices(customer_id, subscription_id=company.get('stripe_subscription_id'))
    
    return jsonify({
        "success": True,
        "invoices": invoices
    })


@app.route("/api/subscription/usage-history", methods=["GET"])
@login_required
def get_usage_history():
    """Get historical monthly usage for the company (last 12 months)."""
    db = get_database()
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({"error": "Authentication required"}), 401
    
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT period_start, period_end, minutes_used, included_minutes,
                   overage_minutes, overage_cost_cents, plan
            FROM usage_history
            WHERE company_id = %s
            ORDER BY period_start DESC
            LIMIT 12
        """, (company_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        for row in rows:
            for k in ('period_start', 'period_end'):
                if row.get(k) and hasattr(row[k], 'isoformat'):
                    row[k] = row[k].isoformat()
        return jsonify({"success": True, "history": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/subscription/sync", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)
def sync_subscription():
    """
    Manually sync subscription status from Stripe.
    Useful if webhook was delayed or missed.
    """
    print(f"[SYNC] ========== SYNC ENDPOINT CALLED ==========")
    print(f"[SYNC] Session company_id: {session.get('company_id')}")
    
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        print(f"[SYNC] ERROR: Company not found in database!")
        return jsonify({"error": "Company not found"}), 404
    
    customer_id = company.get('stripe_customer_id')
    subscription_id = company.get('stripe_subscription_id')
    current_tier = company.get('subscription_tier')
    current_status = company.get('subscription_status')
    
    print(f"[SYNC] Company {company['id']} ({company['email']}):")
    print(f"[SYNC]   - stripe_customer_id: {customer_id}")
    print(f"[SYNC]   - stripe_subscription_id: {subscription_id}")
    print(f"[SYNC]   - current_tier: {current_tier}")
    print(f"[SYNC]   - current_status: {current_status}")
    
    if not customer_id:
        print(f"[SYNC] No Stripe customer found - returning current subscription info")
        sub_info = get_subscription_info(company)
        print(f"[SYNC] Returning: tier={sub_info['tier']}, is_active={sub_info['is_active']}")
        return jsonify({
            "success": True,
            "message": "No Stripe customer found - nothing to sync",
            "subscription": sub_info
        })
    
    try:
        import stripe
        print(f"[SYNC] Stripe API key configured: {bool(stripe.api_key)}")
        
        # Get the latest subscription from Stripe
        if subscription_id:
            print(f"[SYNC] Trying to retrieve subscription by ID: {subscription_id}")
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                print(f"[SYNC] Found subscription by ID: status={sub.status}")
            except stripe.error.InvalidRequestError as e:
                print(f"[SYNC] Subscription ID invalid: {e}")
                subscription_id = None
        
        if not subscription_id:
            print(f"[SYNC] Searching for subscription by customer_id: {customer_id}")
            
            # Try to find active subscription by customer
            print(f"[SYNC] Trying status='active'...")
            subs = stripe.Subscription.list(customer=customer_id, status='active', limit=1)
            print(f"[SYNC] Found {len(subs.data)} active subscriptions")
            
            if not subs.data:
                print(f"[SYNC] Trying status='trialing'...")
                subs = stripe.Subscription.list(customer=customer_id, status='trialing', limit=1)
                print(f"[SYNC] Found {len(subs.data)} trialing subscriptions")
            
            if not subs.data:
                print(f"[SYNC] Trying status='past_due'...")
                subs = stripe.Subscription.list(customer=customer_id, status='past_due', limit=1)
                print(f"[SYNC] Found {len(subs.data)} past_due subscriptions")
            
            if not subs.data:
                print(f"[SYNC] Trying all subscriptions...")
                subs = stripe.Subscription.list(customer=customer_id, limit=5)
                print(f"[SYNC] Found {len(subs.data)} total subscriptions")
                for i, s in enumerate(subs.data):
                    print(f"[SYNC]   Sub {i}: id={s.id}, status={s.status}")
            
            if subs.data:
                sub = subs.data[0]
                subscription_id = sub.id
                print(f"[SYNC] Using subscription: id={subscription_id}, status={sub.status}")
            else:
                print(f"[SYNC] NO SUBSCRIPTION FOUND IN STRIPE for customer {customer_id}")
                sub_info = get_subscription_info(company)
                return jsonify({
                    "success": True,
                    "message": "No subscription found in Stripe",
                    "subscription": sub_info
                })
        
        # Update database based on Stripe subscription status
        status = sub.status
        is_active = status in ('active', 'trialing', 'past_due')
        
        print(f"[SYNC] Stripe subscription details:")
        print(f"[SYNC]   - id: {subscription_id}")
        print(f"[SYNC]   - status: {status}")
        print(f"[SYNC]   - is_active: {is_active}")
        print(f"[SYNC]   - cancel_at_period_end: {sub.cancel_at_period_end}")
        print(f"[SYNC]   - current_period_end: {sub.current_period_end}")
        
        update_data = {
            'stripe_subscription_id': subscription_id,
            'subscription_status': status,
            'subscription_cancel_at_period_end': 1 if sub.cancel_at_period_end else 0,
        }
        
        if sub.current_period_end:
            update_data['subscription_current_period_end'] = datetime.fromtimestamp(sub.current_period_end)
        
        # If subscription is active or trialing (paid subscription with trial period), set tier to pro
        if is_active:
            update_data['subscription_tier'] = 'pro'
            update_data['trial_start'] = None
            update_data['trial_end'] = None
            # Detect plan from subscription metadata
            plan = sub.metadata.get('plan')
            if plan in ('dashboard', 'pro'):
                update_data['subscription_plan'] = plan
            print(f"[SYNC] SETTING TIER TO 'pro' (plan={plan}) for company {company['id']}")
        elif status in ('canceled', 'unpaid', 'incomplete_expired'):
            update_data['subscription_tier'] = 'expired'
            print(f"[SYNC] SETTING TIER TO 'expired' for company {company['id']}")
        else:
            print(f"[SYNC] NOT CHANGING TIER - status is: {status}")
        
        print(f"[SYNC] Update data: {update_data}")
        
        db.update_company(company['id'], **update_data)
        print(f"[SYNC] Database updated for company {company['id']}")
        
        # Get updated subscription info
        updated_company = db.get_company(company['id'])
        subscription_info = get_subscription_info(updated_company)
        
        print(f"[SYNC] ========== SYNC COMPLETED ==========")
        print(f"[SYNC] Final result for company {company['id']}:")
        print(f"[SYNC]   - tier: {subscription_info['tier']}")
        print(f"[SYNC]   - is_active: {subscription_info['is_active']}")
        print(f"[SYNC]   - status: {subscription_info['status']}")
        
        return jsonify({
            "success": True,
            "message": f"Subscription synced from Stripe: {status}",
            "subscription": subscription_info
        })
        
    except stripe.error.StripeError as e:
        print(f"[SYNC] STRIPE ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to sync from Stripe: {str(e)}"}), 500
    except Exception as e:
        print(f"[SYNC] UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to sync subscription"}), 500


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events"""
    print(f"[WEBHOOK] ========== WEBHOOK RECEIVED ==========")
    
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    
    print(f"[WEBHOOK] Payload size: {len(payload)} bytes")
    print(f"[WEBHOOK] Signature header present: {bool(sig_header)}")
    
    if not STRIPE_WEBHOOK_SECRET:
        print("[WEBHOOK] ERROR: Stripe webhook secret not configured!")
        return jsonify({"error": "Webhook not configured"}), 400
    
    result = handle_webhook_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    
    if not result['success']:
        print(f"[WEBHOOK] ERROR: Webhook validation failed: {result['error']}")
        return jsonify({"error": result['error']}), 400
    
    event_type = result['event_type']
    data = result['data']
    event_id = result.get('event_id')
    db = get_database()
    
    print(f"[WEBHOOK] Event type: {event_type}")
    print(f"[WEBHOOK] Event ID: {event_id}")
    
    # Idempotency check — skip if this event has already been processed.
    # Stripe retries failed webhooks, so we need to ensure we don't double-apply
    # effects like resetting usage counters or archiving history.
    if event_id:
        conn_check = db.get_connection()
        try:
            cur_check = conn_check.cursor()
            cur_check.execute(
                "SELECT 1 FROM webhook_events WHERE event_id = %s LIMIT 1",
                (event_id,)
            )
            if cur_check.fetchone():
                print(f"[WEBHOOK] Duplicate event {event_id} — already processed, acknowledging without reprocessing")
                return jsonify({"received": True, "duplicate": True})
            # Insert the event record up front. If processing fails, Stripe will
            # retry with the same event_id and we'll skip it — accept this rather
            # than risk double-processing.
            cur_check.execute(
                "INSERT INTO webhook_events (event_id, event_type) VALUES (%s, %s) ON CONFLICT (event_id) DO NOTHING",
                (event_id, event_type)
            )
            conn_check.commit()
        except Exception as e:
            conn_check.rollback()
            # Table might not exist yet (migration not run). Log and continue.
            print(f"[WEBHOOK] Idempotency check failed (table may not exist): {e}")
        finally:
            db.return_connection(conn_check)
    
    def get_company_id_from_event(event_data, db_instance):
        """Helper to get company_id from event data with fallbacks"""
        # Try metadata first
        company_id = int(event_data.get('metadata', {}).get('company_id', 0))
        print(f"[WEBHOOK] Looking for company_id in metadata: {company_id}")
        if company_id:
            return company_id
        
        # Try to find by stripe_customer_id
        customer_id = event_data.get('customer')
        print(f"[WEBHOOK] Looking for company by customer_id: {customer_id}")
        if customer_id:
            company = db_instance.get_company_by_stripe_customer_id(customer_id)
            if company:
                return company['id']
        
        # Try to find by stripe_subscription_id (for subscription events)
        subscription_id = event_data.get('id') or event_data.get('subscription')
        if subscription_id:
            company = db_instance.get_company_by_stripe_subscription_id(subscription_id)
            if company:
                return company['id']
        
        return 0
    
    try:
        if event_type == 'checkout.session.completed':
            # Subscription checkout completed
            print(f"[WEBHOOK] Processing checkout.session.completed...")
            print(f"[WEBHOOK] Session data keys: {list(data.keys())}")
            print(f"[WEBHOOK] Metadata: {data.get('metadata')}")
            
            company_id = get_company_id_from_event(data, db)
            customer_id = data.get('customer')
            subscription_id = data.get('subscription')
            
            print(f"[WEBHOOK] checkout.session.completed:")
            print(f"[WEBHOOK]   - company_id: {company_id}")
            print(f"[WEBHOOK]   - customer_id: {customer_id}")
            print(f"[WEBHOOK]   - subscription_id: {subscription_id}")
            
            if company_id and subscription_id:
                # Get subscription details
                import stripe
                sub = stripe.Subscription.retrieve(subscription_id)
                
                # Determine which plan from metadata
                plan = data.get('metadata', {}).get('plan') or sub.metadata.get('plan', 'pro')
                if plan not in ('dashboard', 'starter', 'professional', 'business', 'enterprise', 'pro'):
                    plan = 'professional'
                
                # Get usage limits from plan config
                from src.services.stripe_service import PLANS as STRIPE_PLANS
                plan_config = STRIPE_PLANS.get(plan, STRIPE_PLANS.get('pro', {}))
                plan_included_minutes = plan_config.get('included_minutes', 800)
                plan_overage_rate = plan_config.get('overage_rate_cents', 12)
                
                print(f"[WEBHOOK] Stripe subscription retrieved:")
                print(f"[WEBHOOK]   - status: {sub.status}")
                print(f"[WEBHOOK]   - current_period_end: {sub.current_period_end}")
                print(f"[WEBHOOK]   - plan: {plan}")
                
                # Clear trial fields when upgrading to pro to ensure clean state
                print(f"[WEBHOOK] Updating company {company_id} (plan={plan})...")
                db.update_company(
                    company_id,
                    subscription_tier=plan,
                    subscription_status='active',
                    subscription_plan=plan,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    subscription_current_period_end=datetime.fromtimestamp(sub.current_period_end),
                    subscription_cancel_at_period_end=0,
                    trial_start=None,
                    trial_end=None,
                    # Initialize usage tracking for new subscription
                    minutes_used=0,
                    usage_period_start=datetime.fromtimestamp(sub.current_period_start) if hasattr(sub, 'current_period_start') and sub.current_period_start else datetime.now(),
                    usage_period_end=datetime.fromtimestamp(sub.current_period_end),
                    usage_alert_sent=False,
                    included_minutes=plan_included_minutes,
                    overage_rate_cents=plan_overage_rate,
                )
                
                # Verify the update
                updated_company = db.get_company(company_id)
                print(f"[WEBHOOK] Company {company_id} updated successfully:")
                print(f"[WEBHOOK]   - subscription_tier: {updated_company.get('subscription_tier')}")
                print(f"[WEBHOOK]   - subscription_status: {updated_company.get('subscription_status')}")
                print(f"[WEBHOOK]   - stripe_subscription_id: {updated_company.get('stripe_subscription_id')}")
            else:
                print(f"[WEBHOOK] WARNING: Could not process checkout.session.completed!")
                print(f"[WEBHOOK]   - company_id found: {company_id}")
                print(f"[WEBHOOK]   - subscription_id found: {subscription_id}")
                print(f"[WEBHOOK]   - metadata: {data.get('metadata')}")
                print(f"[WEBHOOK]   - customer: {customer_id}")
        
        elif event_type == 'customer.subscription.updated':
            # Subscription updated (e.g., renewed, cancelled, plan changed)
            subscription_id = data.get('id')
            status = data.get('status')
            cancel_at_period_end = data.get('cancel_at_period_end', False)
            current_period_end = data.get('current_period_end')
            
            # Find company by multiple methods
            company_id = get_company_id_from_event(data, db)
            
            if company_id:
                update_data = {
                    'subscription_status': status,
                    'subscription_cancel_at_period_end': 1 if cancel_at_period_end else 0
                }
                
                if current_period_end:
                    update_data['subscription_current_period_end'] = datetime.fromtimestamp(current_period_end)
                
                # If subscription is active or trialing (paid subscription), ensure tier is pro
                # 'trialing' here means a paid Stripe subscription with trial period, not our free trial
                if status in ('active', 'trialing', 'past_due'):
                    update_data['subscription_tier'] = 'pro'
                    # Detect plan from subscription metadata
                    plan = data.get('metadata', {}).get('plan')
                    if plan in ('dashboard', 'starter', 'professional', 'business', 'enterprise', 'pro'):
                        update_data['subscription_plan'] = plan
                        # Also update usage limits to match the new plan
                        from src.services.stripe_service import PLANS as STRIPE_PLANS
                        plan_cfg = STRIPE_PLANS.get(plan)
                        if plan_cfg:
                            update_data['included_minutes'] = plan_cfg.get('included_minutes', 800)
                            update_data['overage_rate_cents'] = plan_cfg.get('overage_rate_cents', 12)
                
                db.update_company(company_id, **update_data)
                print(f"[SUCCESS] Subscription updated for company {company_id}: {status}")
            else:
                print(f"[WARNING] customer.subscription.updated: Could not find company_id (subscription: {subscription_id})")
        
        elif event_type == 'customer.subscription.deleted':
            # Subscription cancelled/expired
            company_id = get_company_id_from_event(data, db)
            
            if company_id:
                db.update_company(
                    company_id,
                    subscription_tier='expired',
                    subscription_status='cancelled',
                    stripe_subscription_id=None
                )
                print(f"[WARNING] Subscription cancelled for company {company_id}")
            else:
                print(f"[WARNING] customer.subscription.deleted: Could not find company_id")
        
        elif event_type == 'invoice.payment_succeeded':
            # Payment succeeded - this fires on renewals
            customer_id = data.get('customer')
            subscription_id = data.get('subscription')
            
            if subscription_id:
                # Find company
                company = db.get_company_by_stripe_subscription_id(subscription_id)
                if not company and customer_id:
                    company = db.get_company_by_stripe_customer_id(customer_id)
                
                if company:
                    # Update subscription status to active and ensure tier is pro
                    import stripe
                    sub = stripe.Subscription.retrieve(subscription_id)
                    
                    new_period_end = datetime.fromtimestamp(sub.current_period_end)
                    new_period_start = datetime.fromtimestamp(sub.current_period_start) if hasattr(sub, 'current_period_start') and sub.current_period_start else datetime.now()
                    
                    # Detect current plan and its limits
                    plan = sub.metadata.get('plan') if sub.metadata else None
                    if plan not in ('dashboard', 'starter', 'professional', 'business', 'enterprise', 'pro'):
                        plan = company.get('subscription_plan', 'professional')
                    
                    from src.services.stripe_service import PLANS as STRIPE_PLANS
                    plan_cfg = STRIPE_PLANS.get(plan, STRIPE_PLANS.get('professional', {}))
                    plan_included = plan_cfg.get('included_minutes', 800)
                    plan_overage = plan_cfg.get('overage_rate_cents', 12)
                    
                    # Archive the previous period's usage to usage_history
                    try:
                        prev_used = company.get('minutes_used', 0) or 0
                        prev_included = company.get('included_minutes', 0) or 0
                        prev_period_start = company.get('usage_period_start')
                        prev_period_end = company.get('usage_period_end')
                        prev_plan = company.get('subscription_plan', 'professional')
                        if prev_used > 0 and prev_period_start and prev_period_end:
                            overage_mins = max(0, prev_used - prev_included)
                            overage_cost = overage_mins * (company.get('overage_rate_cents', 12) or 12)
                            conn_h = db.get_connection()
                            try:
                                cur_h = conn_h.cursor()
                                cur_h.execute("""
                                    INSERT INTO usage_history 
                                    (company_id, period_start, period_end, minutes_used, included_minutes, overage_minutes, overage_cost_cents, plan)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """, (company['id'], prev_period_start, prev_period_end, prev_used, prev_included, overage_mins, overage_cost, prev_plan))
                                conn_h.commit()
                                print(f"[USAGE] Archived period: {prev_used}/{prev_included} mins, {overage_mins} overage")
                            finally:
                                db.return_connection(conn_h)
                    except Exception as e:
                        print(f"[USAGE] Could not archive usage history: {e}")
                    
                    db.update_company(
                        company['id'],
                        subscription_tier='pro',
                        subscription_status='active',
                        subscription_plan=plan,
                        subscription_current_period_end=new_period_end,
                        subscription_cancel_at_period_end=0,
                        # Reset usage counters for new billing period
                        minutes_used=0,
                        usage_period_start=new_period_start,
                        usage_period_end=new_period_end,
                        usage_alert_sent=False,
                        # Set limits to match current plan (in case of upgrade/downgrade)
                        included_minutes=plan_included,
                        overage_rate_cents=plan_overage,
                    )
                    print(f"[SUCCESS] Payment succeeded, subscription renewed for company {company['id']} (plan={plan}, {plan_included} mins included) — usage reset to 0")
        
        elif event_type == 'invoice.payment_failed':
            # Payment failed
            customer_id = data.get('customer')
            subscription_id = data.get('subscription')
            
            company_id = 0
            if subscription_id:
                company = db.get_company_by_stripe_subscription_id(subscription_id)
                if company:
                    company_id = company['id']
            if not company_id and customer_id:
                company = db.get_company_by_stripe_customer_id(customer_id)
                if company:
                    company_id = company['id']
            
            if company_id:
                db.update_company(company_id, subscription_status='past_due')
                print(f"[WARNING] Payment failed for company {company_id}")
    
    except Exception as e:
        print(f"[ERROR] Error processing webhook {event_type}: {e}")
        import traceback
        traceback.print_exc()
        # Still return 200 to acknowledge receipt
    
    return jsonify({"received": True})


# ==================== STRIPE CONNECT ENDPOINTS ====================
# These endpoints allow users (tradespeople) to connect their Stripe account
# to receive payments from their customers

from src.services.stripe_connect_service import (
    create_connect_account,
    create_account_link,
    create_login_link,
    get_account_status,
    delete_connect_account,
    create_payment_link,
    get_account_balance,
    get_account_payouts,
    handle_connect_webhook_event
)


# ---------------------------------------------------------------------------
# Resend webhook — handles email bounce/complaint events.
# When an email bounces, falls back to SMS so the customer still gets notified.
# Configure in Resend dashboard: POST https://yourdomain.com/resend/webhook
# Events to subscribe: email.bounced, email.complained
# ---------------------------------------------------------------------------
@app.route("/resend/webhook", methods=["POST"])
def resend_webhook():
    """Handle Resend webhook events (bounces, complaints)."""
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "Invalid payload"}), 400

        event_type = payload.get('type', '')
        data = payload.get('data', {})
        email_id = data.get('email_id') or data.get('id', '')

        print(f"[RESEND_WEBHOOK] Event: {event_type}, Email ID: {email_id}")

        if event_type in ('email.bounced', 'email.complained'):
            from src.services.sms_reminder import handle_email_bounce
            bounce_type = 'bounce' if event_type == 'email.bounced' else 'complaint'
            handle_email_bounce(email_id, bounce_type=bounce_type)
        else:
            print(f"[RESEND_WEBHOOK] Ignoring event type: {event_type}")

        return jsonify({"received": True}), 200
    except Exception as e:
        print(f"[RESEND_WEBHOOK] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/connect/status", methods=["GET"])
@login_required
def get_connect_status():
    """Get the current Stripe Connect status for the user"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    account_id = company.get('stripe_connect_account_id')
    remove_stripe_connect = company.get('remove_stripe_connect', False)
    if remove_stripe_connect:
        return jsonify({
            "success": True,
            "connected": False,
            "status": "stripe_removed",
            "message": "Stripe Connect has been removed for this user. Please use bank transfer or Revolut."
        })
    if not account_id:
        return jsonify({
            "success": True,
            "connected": False,
            "status": "not_connected",
            "message": "Connect your Stripe account to receive payments"
        })
    
    # Get live status from Stripe
    account_status = get_account_status(account_id)
    
    # Determine overall status
    if not account_status['exists']:
        status = 'error'
        message = 'Account not found. Please reconnect.'
    elif account_status['charges_enabled'] and account_status['payouts_enabled']:
        status = 'active'
        message = 'Your Stripe account is fully set up and ready to receive payments!'
    elif account_status['details_submitted']:
        status = 'pending'
        message = 'Account submitted. Waiting for Stripe verification.'
    else:
        status = 'incomplete'
        message = 'Please complete your Stripe account setup.'
    
    return jsonify({
        "success": True,
        "connected": True,
        "status": status,
        "message": message,
        "account_id": account_id,
        "details_submitted": account_status['details_submitted'],
        "charges_enabled": account_status['charges_enabled'],
        "payouts_enabled": account_status['payouts_enabled'],
        "requirements": account_status.get('currently_due', []),
        "errors": account_status.get('errors', [])
    })


@app.route("/api/connect/create", methods=["POST"])
@login_required
def create_connect():
    """Create a new Stripe Connect account for the user"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    # Check if already has an account
    existing_account = company.get('stripe_connect_account_id')
    if existing_account:
        # Check if the existing account is still valid
        status = get_account_status(existing_account)
        if status['exists']:
            return jsonify({
                "error": "You already have a connected Stripe account",
                "account_id": existing_account
            }), 400
    
    data = request.json or {}
    country = data.get('country', 'IE')  # Default to Ireland
    
    # Create the Connect account
    result = create_connect_account(
        company_id=company['id'],
        email=company['email'],
        company_name=company['company_name'],
        country=country
    )
    
    if not result:
        return jsonify({"error": "Failed to create Stripe Connect account"}), 500
    
    # Save the account ID
    db.update_company(
        company['id'],
        stripe_connect_account_id=result['account_id'],
        stripe_connect_status='pending'
    )
    
    return jsonify({
        "success": True,
        "account_id": result['account_id'],
        "message": "Stripe Connect account created. Please complete the onboarding."
    })


@app.route("/api/connect/onboarding-link", methods=["POST"])
@login_required
def get_onboarding_link():
    """Get/create the onboarding link for Stripe Connect setup"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    # Ensure Stripe API key is set (may not be loaded at module level in some envs)
    import stripe as stripe_lib
    if not stripe_lib.api_key:
        stripe_lib.api_key = os.getenv('STRIPE_SECRET_KEY')
    
    if not stripe_lib.api_key or not stripe_lib.api_key.startswith(('sk_test_', 'sk_live_')):
        print("❌ Stripe Connect: STRIPE_SECRET_KEY not configured")
        return jsonify({"error": "Stripe is not configured. Please set STRIPE_SECRET_KEY in your environment."}), 503
    
    try:
        # Ensure stripe_connect columns exist
        _ensure_payment_columns(db)
        
        account_id = company.get('stripe_connect_account_id')
        
        # If no account exists, create one first
        if not account_id:
            data = request.json or {}
            country = data.get('country', 'IE')
            
            print(f"[STRIPE] Creating Stripe Connect account for company {company['id']} ({company['email']})...")
            
            result = create_connect_account(
                company_id=company['id'],
                email=company['email'],
                company_name=company['company_name'],
                country=country
            )
            
            if not result:
                return jsonify({"error": "Failed to create Stripe Connect account. Check your Stripe API key."}), 500
            
            account_id = result['account_id']
            db.update_company(
                company['id'],
                stripe_connect_account_id=account_id,
                stripe_connect_status='pending'
            )
            print(f"[SUCCESS] Stripe Connect account {account_id} created and saved for company {company['id']}")
        
        data = request.json or {}
        base_url = data.get('base_url', os.getenv('FRONTEND_URL', 'http://localhost:3000'))
        
        print(f"[STRIPE] Creating onboarding link for account {account_id}, return to {base_url}")
        
        # Create the account link
        onboarding_url = create_account_link(
            account_id=account_id,
            refresh_url=f"{base_url}/settings?connect=refresh",
            return_url=f"{base_url}/settings?connect=return"
        )
        
        if not onboarding_url:
            # If the account link fails, the account may be invalid — clear it and let them retry
            print(f"[WARNING] Could not create onboarding link for {account_id}, clearing stale account")
            db.update_company(company['id'], stripe_connect_account_id=None, stripe_connect_status='not_connected')
            return jsonify({"error": "Could not create setup link. Please try connecting again."}), 500
        
        return jsonify({
            "success": True,
            "onboarding_url": onboarding_url
        })
    
    except Exception as e:
        print(f"[ERROR] Stripe Connect onboarding error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Stripe error: {str(e)}"}), 500


@app.route("/api/connect/dashboard-link", methods=["POST"])
@login_required
def get_dashboard_link():
    """Get a link to the user's Stripe Express Dashboard"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    account_id = company.get('stripe_connect_account_id')
    if not account_id:
        return jsonify({"error": "No Stripe Connect account found"}), 400
    
    dashboard_url = create_login_link(account_id)
    
    if not dashboard_url:
        return jsonify({"error": "Failed to create dashboard link"}), 500
    
    return jsonify({
        "success": True,
        "dashboard_url": dashboard_url
    })


@app.route("/api/connect/disconnect", methods=["POST"])
@login_required
def disconnect_connect():
    """Disconnect the Stripe Connect account"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    account_id = company.get('stripe_connect_account_id')
    if not account_id:
        return jsonify({"error": "No Stripe Connect account to disconnect"}), 400
    
    # Note: We don't actually delete the Stripe account, just unlink it from our platform
    # The user can reconnect later or use their Stripe account elsewhere
    
    db.update_company(
        company['id'],
        stripe_connect_account_id=None,
        stripe_connect_status='not_connected',
        stripe_connect_onboarding_complete=0,
        remove_stripe_connect=True
    )
    print(f"[INFO] Stripe Connect removed for company {company['id']}")
    return jsonify({
        "success": True,
        "message": "Stripe account disconnected and removed successfully"
    })


@app.route("/api/connect/balance", methods=["GET"])
@login_required
def get_connect_balance():
    """Get the balance for the connected account"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    account_id = company.get('stripe_connect_account_id')
    if not account_id:
        return jsonify({"error": "No Stripe Connect account found"}), 400
    
    balance = get_account_balance(account_id)
    
    if not balance:
        return jsonify({"error": "Failed to get balance"}), 500
    
    return jsonify({
        "success": True,
        "balance": balance
    })


@app.route("/api/connect/payouts", methods=["GET"])
@login_required
def get_connect_payouts():
    """Get recent payouts for the connected account"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    account_id = company.get('stripe_connect_account_id')
    if not account_id:
        return jsonify({"error": "No Stripe Connect account found"}), 400
    
    payouts = get_account_payouts(account_id)
    
    return jsonify({
        "success": True,
        "payouts": payouts
    })


@app.route("/stripe/connect/webhook", methods=["POST"])
def stripe_connect_webhook():
    """Handle Stripe Connect webhook events"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    
    # Use a separate webhook secret for Connect events if configured
    connect_webhook_secret = os.getenv('STRIPE_CONNECT_WEBHOOK_SECRET', STRIPE_WEBHOOK_SECRET)
    
    if not connect_webhook_secret:
        print("⚠️ Stripe Connect webhook secret not configured")
        return jsonify({"error": "Webhook not configured"}), 400
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, connect_webhook_secret
        )
    except ValueError as e:
        return jsonify({"error": f"Invalid payload: {e}"}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({"error": f"Invalid signature: {e}"}), 400
    
    event_type = event['type']
    data = event['data']['object']
    
    print(f"[WEBHOOK] Received Stripe Connect webhook: {event_type}")
    
    db = get_database()
    
    def _auto_win_linked_quotes(booking_id, company_id):
        """When a booking is paid, move any linked quotes to 'won' in the pipeline"""
        try:
            conn_q = db.get_connection()
            cur_q = conn_q.cursor()
            cur_q.execute("""
                UPDATE quotes SET pipeline_stage = 'won', status = 'converted',
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = %s 
                    AND (source_booking_id = %s OR converted_booking_id = %s)
                    AND status NOT IN ('converted', 'declined')
                    AND (pipeline_stage IS NULL OR pipeline_stage NOT IN ('won', 'lost'))
            """, (company_id, booking_id, booking_id))
            updated = cur_q.rowcount
            conn_q.commit()
            cur_q.close()
            db.return_connection(conn_q)
            if updated > 0:
                print(f"[WEBHOOK] Auto-moved {updated} linked quote(s) to 'won' for booking {booking_id}")
        except Exception as e:
            print(f"[WARNING] Could not auto-win quotes for booking {booking_id}: {e}")
    
    try:
        # Handle account updates (onboarding completed, verification, etc.)
        if event_type == 'account.updated':
            account_id = data.get('id')
            charges_enabled = data.get('charges_enabled', False)
            payouts_enabled = data.get('payouts_enabled', False)
            details_submitted = data.get('details_submitted', False)
            
            # Find company by connect account ID and update status
            try:
                conn = db.get_connection()
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SELECT id FROM companies WHERE stripe_connect_account_id = %s", (account_id,))
                row = cursor.fetchone()
                db.return_connection(conn)
                
                if row:
                    company_id = row['id']
                    if charges_enabled and payouts_enabled:
                        db.update_company(company_id, stripe_connect_status='active', stripe_connect_onboarding_complete=1)
                        print(f"[SUCCESS] Connect account {account_id} is now fully active for company {company_id}")
                    elif details_submitted:
                        db.update_company(company_id, stripe_connect_status='pending')
                        print(f"[INFO] Connect account {account_id} submitted, waiting for verification")
            except Exception as e:
                print(f"[WARNING] Error updating company for Connect account {account_id}: {e}")
        
        # Handle checkout session completed (customer paid an invoice)
        elif event_type == 'checkout.session.completed':
            booking_id = data.get('metadata', {}).get('booking_id')
            if booking_id:
                try:
                    booking_id = int(booking_id)
                    # SECURITY NOTE: This is a webhook from Stripe - we get booking first to extract company_id
                    # The booking_id comes from trusted Stripe metadata set during payment link creation
                    booking = db.get_booking(booking_id)  # company_id extracted from booking itself
                    if booking:
                        db.update_booking(booking_id, company_id=booking.get('company_id'),
                                          payment_status='paid',
                                          payment_method='stripe')
                        # Clear the checkout URL so /pay/:id shows "Already Paid"
                        try:
                            conn_upd = db.get_connection()
                            cur_upd = conn_upd.cursor()
                            cur_upd.execute("UPDATE bookings SET stripe_checkout_url = NULL WHERE id = %s", (booking_id,))
                            conn_upd.commit()
                            cur_upd.close()
                            db.return_connection(conn_upd)
                        except Exception:
                            pass
                        print(f"[SUCCESS] Booking {booking_id} marked as paid via Stripe Connect checkout")
                        _auto_win_linked_quotes(booking_id, booking.get('company_id'))
                    else:
                        print(f"[WARNING] Booking {booking_id} not found for checkout session")
                except Exception as e:
                    print(f"[WARNING] Error updating booking {booking_id}: {e}")
        
        # Handle payment intent succeeded
        elif event_type == 'payment_intent.succeeded':
            booking_id = data.get('metadata', {}).get('booking_id')
            if booking_id:
                try:
                    booking_id = int(booking_id)
                    booking = db.get_booking(booking_id)
                    if booking:
                        db.update_booking(booking_id, company_id=booking.get('company_id'),
                                          payment_status='paid',
                                          payment_method='stripe')
                        # Clear the checkout URL so /pay/:id shows "Already Paid"
                        try:
                            conn_pi = db.get_connection()
                            cur_pi = conn_pi.cursor()
                            cur_pi.execute("UPDATE bookings SET stripe_checkout_url = NULL WHERE id = %s", (booking_id,))
                            conn_pi.commit()
                            cur_pi.close()
                            db.return_connection(conn_pi)
                        except Exception:
                            pass
                        print(f"[SUCCESS] Booking {booking_id} marked as paid via payment intent")
                        _auto_win_linked_quotes(booking_id, booking.get('company_id'))
                    else:
                        print(f"[WARNING] Booking {booking_id} not found for payment intent")
                except Exception as e:
                    print(f"[WARNING] Error updating booking {booking_id}: {e}")
            else:
                print(f"[WEBHOOK] payment_intent.succeeded received but no booking_id in metadata")

        # Handle charge.succeeded as another fallback
        elif event_type == 'charge.succeeded':
            booking_id = data.get('metadata', {}).get('booking_id')
            if booking_id:
                try:
                    booking_id = int(booking_id)
                    booking = db.get_booking(booking_id)
                    if booking and booking.get('payment_status') != 'paid':
                        db.update_booking(booking_id, company_id=booking.get('company_id'),
                                          payment_status='paid',
                                          payment_method='stripe')
                        print(f"[SUCCESS] Booking {booking_id} marked as paid via charge.succeeded")
                        _auto_win_linked_quotes(booking_id, booking.get('company_id'))
                except Exception as e:
                    print(f"[WARNING] Error updating booking from charge.succeeded: {e}")
    
    except Exception as e:
        print(f"[ERROR] Error processing Connect webhook {event_type}: {e}")
    
    return jsonify({"received": True})


@app.route("/payment-success")
def payment_success_page():
    """Thank-you page shown after a customer pays an invoice via Stripe"""
    # Try to get company info from the session_id to show their branding
    session_id = request.args.get('session_id')
    company_name = ''
    logo_url = ''
    if session_id:
        try:
            import stripe as stripe_lib
            if not stripe_lib.api_key:
                stripe_lib.api_key = os.getenv('STRIPE_SECRET_KEY')
            checkout = stripe_lib.checkout.Session.retrieve(session_id)
            booking_id = checkout.metadata.get('booking_id')
            if booking_id:
                db = get_database()
                booking = db.get_booking(int(booking_id))
                if booking and booking.get('company_id'):
                    company = db.get_company(booking['company_id'])
                    if company:
                        company_name = company.get('company_name', '')
                        logo_url = company.get('logo_url', '')
        except Exception as e:
            print(f"[PAYMENT-SUCCESS] Could not fetch company info: {e}")
    
    logo_html = f'<img src="{logo_url}" alt="{company_name}" style="width:56px;height:56px;border-radius:12px;object-fit:contain;margin-bottom:16px">' if logo_url and not logo_url.startswith('data:') else ''
    name_html = f'<p style="font-weight:600;color:#1e293b;margin:0 0 20px;font-size:15px">{company_name}</p>' if company_name else ''
    
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payment Successful</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f0fdf4;color:#166534}}
.card{{text-align:center;background:#fff;padding:48px 40px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:440px}}
.icon{{font-size:64px;margin-bottom:16px}}h1{{margin:0 0 12px;font-size:24px}}p{{margin:0;color:#4b5563;line-height:1.6}}</style></head>
<body><div class="card">{logo_html}{name_html}<div class="icon">✅</div><h1>Payment Received</h1><p>Thank you! Your payment has been processed successfully. You can close this page.</p></div></body></html>""", 200


@app.route("/payment-cancelled")
def payment_cancelled_page():
    """Page shown when a customer cancels the Stripe checkout"""
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payment Cancelled</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#fefce8;color:#854d0e}
.card{text-align:center;background:#fff;padding:48px 40px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:440px}
.icon{font-size:64px;margin-bottom:16px}h1{margin:0 0 12px;font-size:24px}p{margin:0;color:#4b5563;line-height:1.6}</style></head>
<body><div class="card"><div class="icon">↩️</div><h1>Payment Cancelled</h1><p>No worries — your payment was not processed. You can use the payment link again whenever you're ready.</p></div></body></html>""", 200


def _pay_error_page(title, message):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f8fafc;color:#475569}}
.card{{text-align:center;background:#fff;padding:48px 40px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:440px}}
.icon{{width:64px;height:64px;border-radius:50%;background:#fef2f2;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:28px}}
h1{{margin:0 0 12px;font-size:22px;color:#1e293b}}p{{margin:0;color:#64748b;line-height:1.6;font-size:15px}}</style></head>
<body><div class="card"><div class="icon">⚠️</div><h1>{title}</h1><p>{message}</p></div></body></html>"""

def _pay_success_page():
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Payment Complete</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f8fafc;color:#475569}
.card{text-align:center;background:#fff;padding:48px 40px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:440px}
.icon{width:64px;height:64px;border-radius:50%;background:#ecfdf5;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:28px}
h1{margin:0 0 12px;font-size:22px;color:#1e293b}p{margin:0;color:#64748b;line-height:1.6;font-size:15px}</style></head>
<body><div class="card"><div class="icon">✅</div><h1>Already Paid</h1><p>This invoice has already been paid. Thank you!</p></div></body></html>"""

@app.route("/api/pay/<int:booking_id>")
@app.route("/pay/<int:booking_id>")
def short_payment_redirect(booking_id):
    """Short URL redirect to Stripe checkout for invoice payments.
    
    This allows SMS invoices to use a clean short URL like:
    yourdomain.com/pay/1234
    instead of the long Stripe checkout URL.
    """
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT b.stripe_checkout_url, b.company_id, b.charge, b.service_type, 
                   b.status, b.payment_status, c.name as client_name
            FROM bookings b 
            LEFT JOIN clients c ON b.client_id = c.id 
            WHERE b.id = %s
        """, (booking_id,))
        row = cur.fetchone()
        cur.close()
        
        if not row:
            return _pay_error_page("Booking Not Found", "This payment link is not valid."), 404
        
        # If already paid, show a success message
        if row.get('payment_status') in ('paid',):
            return _pay_success_page(), 200
        
        # Try stored URL first
        if row.get('stripe_checkout_url'):
            from flask import redirect
            return redirect(row['stripe_checkout_url'])
        
        # No stored URL — try to create a fresh Stripe checkout session
        company_id = row.get('company_id')
        charge = float(row.get('charge') or 0)
        
        if charge <= 0:
            return _pay_error_page("No Amount Due", "This invoice has no charge amount. Please contact the business."), 400
        
        company = db.get_company(company_id)
        connected_account_id = company.get('stripe_connect_account_id') if company else None
        
        if not connected_account_id:
            return _pay_error_page("Payment Not Available", "Online payment is not set up for this business. Please contact them directly to arrange payment."), 503
        
        # Verify the Connect account can accept charges
        try:
            import stripe
            stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
            if not stripe_secret_key:
                return _pay_error_page("Payment Not Configured", "Payment system is not configured. Please contact the business."), 503
            
            stripe.api_key = stripe_secret_key
            connect_acct = stripe.Account.retrieve(connected_account_id)
            if not connect_acct.get('charges_enabled'):
                return _pay_error_page("Payment Setup Incomplete", "The business is still setting up their payment account. Please contact them directly to arrange payment."), 503
            amount_cents = int(charge * 100)
            service_type = row.get('service_type') or 'Service'
            client_name = row.get('client_name') or 'Customer'
            
            checkout_params = {
                'payment_method_types': ['card'],
                'line_items': [{
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': f"{service_type} - Invoice #{booking_id}",
                            'description': f"Service for {client_name}",
                        },
                        'unit_amount': amount_cents,
                    },
                    'quantity': 1,
                }],
                'mode': 'payment',
                'success_url': f"{os.getenv('PUBLIC_URL', 'http://localhost:5000')}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
                'cancel_url': f"{os.getenv('PUBLIC_URL', 'http://localhost:5000')}/payment-cancelled",
                'metadata': { 'booking_id': str(booking_id), 'customer_name': client_name },
            }
            
            platform_fee_cents = int(os.getenv('STRIPE_PLATFORM_FEE_CENTS', '200'))
            if platform_fee_cents > 0:
                checkout_params['payment_intent_data'] = {
                    'application_fee_amount': platform_fee_cents,
                    'metadata': { 'booking_id': str(booking_id), 'company_id': str(company_id) },
                }
            else:
                checkout_params['payment_intent_data'] = {
                    'metadata': { 'booking_id': str(booking_id), 'company_id': str(company_id) },
                }
            
            checkout_session = stripe.checkout.Session.create(**checkout_params, stripe_account=connected_account_id)
            
            # Store for future use
            conn2 = db.get_connection()
            try:
                cur2 = conn2.cursor()
                cur2.execute("UPDATE bookings SET stripe_checkout_url = %s, stripe_checkout_session_id = %s WHERE id = %s",
                             (checkout_session.url, checkout_session.id, booking_id))
                conn2.commit()
                cur2.close()
            finally:
                db.return_connection(conn2)
            
            from flask import redirect
            return redirect(checkout_session.url)
        except Exception as stripe_err:
            print(f"[PAY] Stripe error: {stripe_err}")
            return _pay_error_page("Payment Error", "Could not create payment session. Please contact the business."), 500
    except Exception as e:
        print(f"[PAY] Error: {e}")
        return _pay_error_page("Error", "Something went wrong. Please contact the business."), 500
    finally:
        db.return_connection(conn)


@app.route("/telnyx/sms", methods=["POST"])
@app.route("/twilio/sms", methods=["POST"])  # backwards compatibility
def twilio_sms():
    """
    Handle incoming SMS messages (for appointment confirmations/cancellations)
    Supports both Telnyx and legacy Twilio webhook formats.
    Only active if REMINDER_METHOD=sms in .env
    """
    try:
        # Check if SMS reminders are enabled
        if config.REMINDER_METHOD.lower() != "sms":
            print("⚠️ SMS webhook called but REMINDER_METHOD is not 'sms'. Ignoring.")
            resp = MessagingResponse()
            resp.message("Please contact us by phone for appointment inquiries.")
            return Response(str(resp), mimetype="text/xml")
        
        # Get message details - support both Telnyx and Twilio formats
        # Telnyx sends JSON, Twilio sends form data
        if request.is_json:
            # Telnyx webhook format
            telnyx_data = request.json or {}
            payload = telnyx_data.get('data', {}).get('payload', {})
            from_number = payload.get('from', {}).get('phone_number', '')
            message_body = payload.get('text', '').strip().upper()
        else:
            # Twilio/TeXML form format
            from_number = request.form.get('From', '')
            message_body = request.form.get('Body', '').strip().upper()
        
        print(f"\n[SMS] SMS received from {from_number}: {message_body}")
        
        # Create response
        resp = MessagingResponse()
        
        if 'YES' in message_body or 'CONFIRM' in message_body:
            # User confirmed the appointment
            reply = "Thank you! Your appointment is confirmed. We look forward to seeing you!"
            resp.message(reply)
            print(f"[SUCCESS] Appointment confirmed by {from_number}")
            
        elif 'CANCEL' in message_body:
            # User wants to cancel - we would need event ID to actually cancel
            # For now, just acknowledge and ask them to call
            reply = "We received your cancellation request. Please call us to confirm the cancellation and reschedule if needed."
            resp.message(reply)
            print(f"[WARNING] Cancellation request from {from_number}")
            
        else:
            # Unknown response
            reply = "Thank you for your message. Please reply YES to confirm or CANCEL to cancel your appointment."
            resp.message(reply)
        
        return Response(str(resp), mimetype="text/xml")
        
    except Exception as e:
        print(f"[ERROR] Error handling SMS: {e}")
        resp = MessagingResponse()
        resp.message("Sorry, we encountered an error processing your message. Please call us directly.")
        return Response(str(resp), mimetype="text/xml")


# Dashboard and API endpoints
from flask import redirect

@app.route("/")
def index():
    """Health check endpoint - backend only serves API, not frontend"""
    return jsonify({
        "status": "healthy",
        "service": "AI Receptionist Backend",
        "message": "Frontend is served by Vercel. This backend only handles API requests."
    })


# Legacy redirects for backwards compatibility
@app.route("/dashboard")
def dashboard_redirect():
    frontend_url = os.getenv('FRONTEND_URL', '/')
    return redirect(frontend_url, code=302)


@app.route("/settings")
def settings_page():
    """Redirect to frontend app"""
    frontend_url = os.getenv('FRONTEND_URL', '/')
    return redirect(f"{frontend_url}/settings", code=302)


@app.route("/settings/menu")
def settings_menu_page():
    """Redirect to frontend app"""
    frontend_url = os.getenv('FRONTEND_URL', '/')
    return redirect(f"{frontend_url}/settings/menu", code=302)


@app.route("/settings/developer")
def developer_settings_page():
    """Redirect to frontend app"""
    frontend_url = os.getenv('FRONTEND_URL', '/')
    return redirect(f"{frontend_url}/settings/developer", code=302)


@app.route("/api/settings/business", methods=["GET", "POST"])
@login_required
@subscription_required
def business_settings_api():
    """Get or update business settings (now stored in companies table)"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        company = db.get_company(company_id)
        if not company:
            return jsonify({"error": "Company not found"}), 404
        
        # Return company data in the format the frontend expects
        # API keys configured via environment variables only (not user-configurable)
        # Twilio phone number assigned from pool (read-only)
        settings = {
            'business_name': company.get('company_name'),
            'owner_name': company.get('owner_name'),
            'business_type': company.get('trade_type'),  # Trade type from signup
            'industry_type': company.get('industry_type', 'trades'),
            'business_phone': company.get('phone'),            'business_email': company.get('email'),
            'business_address': company.get('address'),
            'logo_url': company.get('logo_url'),
            'country_code': '+353',  # Default, could be added to schema if needed
            'business_hours': company.get('business_hours', ''),
            'twilio_phone_number': company.get('twilio_phone_number'),  # Read-only, assigned from pool
            'ai_enabled': company.get('ai_enabled', True),
            # Bank details for invoice bank transfer option
            'bank_iban': company.get('bank_iban', ''),
            'bank_bic': company.get('bank_bic', ''),
            'bank_name': company.get('bank_name', ''),
            'bank_account_holder': company.get('bank_account_holder', ''),
            # Revolut payment option
            'revolut_phone': company.get('revolut_phone', ''),
            # Company context for AI receptionist
            'company_context': company.get('company_context', ''),
            # Coverage area for AI receptionist
            'coverage_area': company.get('coverage_area', ''),
            # Dashboard feature toggles
            'show_finances_tab': company.get('show_finances_tab', True) if company.get('show_finances_tab') is not None else True,
            'show_insights_tab': company.get('show_insights_tab', True) if company.get('show_insights_tab') is not None else True,
            'show_invoice_buttons': company.get('show_invoice_buttons', True) if company.get('show_invoice_buttons') is not None else True,
            # SMS toggles
            'send_confirmation_sms': company.get('send_confirmation_sms', True) if company.get('send_confirmation_sms') is not None else True,
            'send_reminder_sms': company.get('send_reminder_sms', False) if company.get('send_reminder_sms') is not None else False,
            # Google Calendar employee invites toggle
            'gcal_invite_employees': company.get('gcal_invite_employees', False) if company.get('gcal_invite_employees') is not None else False,
            # Bypass numbers - always forward to fallback
            'bypass_numbers': company.get('bypass_numbers', '[]'),
            # AI receptionist schedule (auto off times)
            'ai_schedule': company.get('ai_schedule', ''),
            # Setup wizard permanently dismissed
            'setup_wizard_complete': bool(company.get('setup_wizard_complete', False)),
            # Managed setup mode
            'easy_setup': company.get('easy_setup', True),
            # Accounting integration
            'accounting_provider': company.get('accounting_provider', 'builtin'),
            # Admin-controlled tab visibility
            'admin_tab_visibility': company.get('admin_tab_visibility') or {
                'jobs': True, 'calls': True, 'calendar': True, 'employees': True,
                'crm': True, 'services': True, 'inventory': True, 'finances': True,
                'insights': True, 'reviews': True,
            },
            # Custom per-account pricing
            'custom_stripe_price_id': company.get('custom_stripe_price_id', ''),
            'custom_monthly_price': float(company['custom_monthly_price']) if company.get('custom_monthly_price') else None,
            'custom_dashboard_price': float(company['custom_dashboard_price']) if company.get('custom_dashboard_price') else None,
            'custom_dashboard_stripe_price_id': company.get('custom_dashboard_stripe_price_id', ''),
            'custom_pro_price': float(company['custom_pro_price']) if company.get('custom_pro_price') else None,
            'custom_pro_stripe_price_id': company.get('custom_pro_stripe_price_id', ''),
        }
        
        # Include the industry profile so the frontend has feature flags and terminology
        from src.utils.industry_config import get_industry_profile, get_available_industries
        settings['industry_profile'] = get_industry_profile(settings['industry_type'])
        settings['available_industries'] = get_available_industries()
        
        return jsonify(settings)
    
    elif request.method == "POST":
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Handle logo upload to R2 if logo_url is base64
        if 'logo_url' in data and data['logo_url'] and data['logo_url'].startswith('data:image/'):
            try:
                uploaded_url = upload_base64_image_to_r2(data['logo_url'], company_id, 'logos')
                if uploaded_url and not uploaded_url.startswith('data:'):
                    # Successfully uploaded to R2
                    data['logo_url'] = uploaded_url
                elif uploaded_url and uploaded_url.startswith('data:'):
                    # R2 not configured, base64 returned - check size
                    # Don't store huge base64 strings in database (limit to ~500KB)
                    if len(uploaded_url) > 500000:
                        print(f"[WARNING] Logo too large to store in database ({len(uploaded_url)} bytes). Configure R2 storage.")
                        return jsonify({"error": "Logo file too large. Please use a smaller image or contact support to enable cloud storage."}), 400
                    data['logo_url'] = uploaded_url
                else:
                    # Upload failed or returned empty - don't update logo
                    print(f"[WARNING] Logo upload failed for company {company_id}, keeping existing logo")
                    del data['logo_url']
            except Exception as e:
                print(f"[ERROR] Logo upload error: {e}")
                import traceback
                traceback.print_exc()
                # Don't fail the whole save, just skip logo update
                del data['logo_url']
        
        # Map frontend field names to database column names
        update_data = {}
        field_mapping = {
            'business_name': 'company_name',
            'owner_name': 'owner_name',
            'business_type': 'trade_type',  # Trade type from signup
            'industry_type': 'industry_type',
            'business_phone': 'phone',
            'business_email': 'email',
            'business_address': 'address',
            'logo_url': 'logo_url',
            'business_hours': 'business_hours',
            'ai_enabled': 'ai_enabled',
            'bank_iban': 'bank_iban',
            'bank_bic': 'bank_bic',
            'bank_name': 'bank_name',
            'bank_account_holder': 'bank_account_holder',
            'revolut_phone': 'revolut_phone',
            'company_context': 'company_context',
            'coverage_area': 'coverage_area',
            'show_finances_tab': 'show_finances_tab',
            'show_insights_tab': 'show_insights_tab',
            'show_invoice_buttons': 'show_invoice_buttons',
            'send_confirmation_sms': 'send_confirmation_sms',
            'send_reminder_sms': 'send_reminder_sms',
            'gcal_invite_employees': 'gcal_invite_employees',
            'bypass_numbers': 'bypass_numbers',
            'ai_schedule': 'ai_schedule',
            'setup_wizard_complete': 'setup_wizard_complete',
            'easy_setup': 'easy_setup',
            'accounting_provider': 'accounting_provider',
            'custom_stripe_price_id': 'custom_stripe_price_id',
            'custom_monthly_price': 'custom_monthly_price',
        }
        
        for frontend_field, db_field in field_mapping.items():
            if frontend_field in data:
                update_data[db_field] = data[frontend_field]
        
        if update_data:
            # Ensure bank/payment columns exist before updating
            bank_fields = {'bank_iban', 'bank_bic', 'bank_name', 'bank_account_holder', 'revolut_phone'}
            has_bank_fields = any(f in update_data for f in bank_fields)
            if has_bank_fields:
                try:
                    _ensure_payment_columns(db)
                except Exception as e:
                    print(f"[WARNING] Could not ensure payment columns: {e}")
            
            try:
                print(f"[SETTINGS] Updating company {company_id} with fields: {list(update_data.keys())}")
                success = db.update_company(company_id, **update_data)
                print(f"[SETTINGS] Update result: {success}")
                
                # Sync business_hours string → business_settings table so both stay in sync
                if 'business_hours' in update_data and update_data['business_hours']:
                    try:
                        from src.utils.config import Config
                        from src.services.settings_manager import get_settings_manager
                        parsed = Config.parse_business_hours_string(update_data['business_hours'])
                        sync_data = {
                            'opening_hours_start': parsed['start'],
                            'opening_hours_end': parsed['end'],
                            'days_open': parsed['days_open'],
                        }
                        get_settings_manager().update_business_settings(sync_data, company_id=company_id)
                        print(f"[SETTINGS] Synced business_hours to business_settings: days_open={parsed['days_open']}")
                    except Exception as sync_e:
                        print(f"[WARNING] Could not sync business_hours to business_settings: {sync_e}")
                
                # Return success even if no rows changed (data might be identical)
                return jsonify({"message": "Settings updated successfully"})
            except Exception as e:
                print(f"[ERROR] Error updating settings: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": f"Failed to save: {str(e)}"}), 500
        
        print(f"[SETTINGS] No valid fields to update. Received fields: {list(data.keys())}")
        return jsonify({"error": "No valid fields to update"}), 400


# Developer settings endpoint removed - all settings now in companies table via /api/settings/business


@app.route("/api/ai-receptionist/toggle", methods=["GET", "POST"])
@login_required
@subscription_required
def ai_receptionist_toggle_api():
    """Get or toggle AI receptionist status (now stored in companies table)"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        company = db.get_company(company_id)
        if not company:
            return jsonify({"error": "Company not found"}), 404
        
        enabled = company.get('ai_enabled', True)
        business_phone = company.get('phone')
        ai_schedule = company.get('ai_schedule', '')
        ai_schedule_override = company.get('ai_schedule_override', False)
        
        return jsonify({
            "enabled": bool(enabled) if isinstance(enabled, int) else enabled,
            "business_phone": business_phone,
            "ai_schedule": ai_schedule,
            "ai_schedule_override": bool(ai_schedule_override) if ai_schedule_override is not None else False
        })
    
    elif request.method == "POST":
        data = request.json
        enabled = data.get("enabled", True)
        ai_schedule = data.get("ai_schedule", None)
        
        print(f"[AI-TOGGLE] Received request to set ai_enabled={enabled} for company {company_id}")
        
        # Get current company data
        company = db.get_company(company_id)
        if not company:
            print(f"[AI-TOGGLE] Company {company_id} not found")
            return jsonify({"error": "Company not found"}), 404
        
        print(f"[AI-TOGGLE] Company data: phone={company.get('phone')}, current ai_enabled={company.get('ai_enabled')}")
        
        # Validation: Cannot disable AI without a business phone number
        if not enabled:
            business_phone = company.get('phone')
            
            if not business_phone or business_phone.strip() == '':
                print(f"[AI-TOGGLE] Cannot disable - no business phone configured")
                return jsonify({
                    "error": "Cannot disable AI receptionist without a business phone number configured. Please add your business phone in settings first."
                }), 400
        
        # Validation: Cannot set a schedule without a business phone (calls need somewhere to go)
        if ai_schedule:
            try:
                import json as _json
                sched = _json.loads(ai_schedule) if isinstance(ai_schedule, str) else ai_schedule
                if sched and sched.get('enabled') and sched.get('slots'):
                    business_phone = company.get('phone')
                    if not business_phone or business_phone.strip() == '':
                        return jsonify({
                            "error": "Cannot set an AI schedule without a business phone number configured. Calls need a fallback number outside scheduled hours."
                        }), 400
            except Exception:
                pass  # Invalid JSON will just be stored as-is (harmless)
        
        # Build update kwargs
        update_kwargs = {'ai_enabled': enabled}
        if ai_schedule is not None:
            update_kwargs['ai_schedule'] = ai_schedule
        # Clear override when toggling off, or when saving a new schedule
        if not enabled:
            update_kwargs['ai_schedule_override'] = False
        if ai_schedule is not None:
            update_kwargs['ai_schedule_override'] = False
        # Check if caller explicitly set override
        if data.get('ai_schedule_override') is not None:
            update_kwargs['ai_schedule_override'] = data.get('ai_schedule_override')
        
        # Update AI status in companies table (use boolean for PostgreSQL)
        try:
            success = db.update_company(company_id, **update_kwargs)
            print(f"[AI-TOGGLE] Update result: success={success}")
            
            if success:
                status = "enabled" if enabled else "disabled"
                return jsonify({
                    "message": f"AI Receptionist {status} successfully",
                    "enabled": enabled
                })
            else:
                # Even if rowcount is 0, the update might have succeeded (same value)
                # Verify by re-fetching
                updated_company = db.get_company(company_id)
                current_status = updated_company.get('ai_enabled', True) if updated_company else None
                print(f"[AI-TOGGLE] After update, ai_enabled={current_status}")
                
                if current_status == enabled or (current_status in [0, False] and not enabled) or (current_status in [1, True] and enabled):
                    status = "enabled" if enabled else "disabled"
                    return jsonify({
                        "message": f"AI Receptionist {status} successfully",
                        "enabled": enabled
                    })
                
                return jsonify({"error": "Failed to update AI receptionist status"}), 500
        except Exception as e:
            print(f"[AI-TOGGLE] Error updating: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Failed to update: {str(e)}"}), 500


@app.route("/api/settings/history", methods=["GET"])
@login_required
def settings_history_api():
    """Get settings change history"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    
    limit = request.args.get('limit', 50, type=int)
    history = settings_mgr.get_settings_history(limit)
    return jsonify(history)


@app.route("/api/services/menu", methods=["GET", "POST"])
@login_required
@subscription_required
def services_menu_api():
    """Get or update services menu"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        # ?include_inactive=true returns all services (for ServicesTab management)
        # Default returns active-only (for AddJobModal, employee views, etc.)
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        menu = settings_mgr.get_services_menu(company_id=company_id, active_only=not include_inactive)
        return jsonify(menu)
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_services_menu(data, company_id=company_id)
        if success:
            return jsonify({"message": "Services menu updated successfully"})
        return jsonify({"error": "Failed to update services menu"}), 500


@app.route("/api/services/menu/service", methods=["POST"])
@login_required
@subscription_required
def add_service_api():
    """Add a new service"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    # Check subscription for creating services
    db = get_database()
    company = db.get_company(company_id)
    subscription_info = get_subscription_info(company)
    if not subscription_info['is_active']:
        return jsonify({
            "error": "Active subscription required to create services",
            "subscription_status": "inactive"
        }), 403
    
    data = request.json
    
    # Validate required field: name
    name = data.get('name', '').strip() if data.get('name') else ''
    if not name:
        return jsonify({"error": "Service name is required"}), 400
    
    # Sanitize and validate optional fields
    try:
        price = float(data.get('price', 0)) if data.get('price') else 0
        if price < 0:
            price = 0
    except (ValueError, TypeError):
        price = 0
    
    # Sanitize price_max for price ranges
    try:
        price_max = float(data.get('price_max', 0)) if data.get('price_max') else None
        if price_max is not None and price_max <= price:
            price_max = None  # Only store if it's actually a range
    except (ValueError, TypeError):
        price_max = None
    
    try:
        duration = int(data.get('duration_minutes', 1440)) if data.get('duration_minutes') else 1440
        if duration < 1:
            duration = 1440
    except (ValueError, TypeError):
        duration = 1440
    
    # Upload image to R2 if it's base64
    image_url = data.get('image_url', '')
    if image_url and image_url.startswith('data:image/'):
        image_url = upload_base64_image_to_r2(image_url, company_id, 'services')
    
    # Validate and sanitize employee_restrictions
    restrictions = data.get('employee_restrictions')
    if restrictions and isinstance(restrictions, dict):
        valid_types = ['all', 'only', 'except']
        if restrictions.get('type') not in valid_types:
            restrictions = None
        elif restrictions.get('type') != 'all' and not restrictions.get('employee_ids'):
            restrictions = None  # 'only' and 'except' require employee_ids
        elif restrictions.get('type') == 'all':
            restrictions = None  # 'all' doesn't need to be stored
    else:
        restrictions = None
    
    # Build sanitized service data
    sanitized_data = {
        'name': name,
        'price': price,
        'price_max': price_max,
        'duration_minutes': duration,
        'image_url': image_url if image_url else None,
        'category': data.get('category', 'General'),
        'description': data.get('description', '').strip() if data.get('description') else None,
        'employees_required': max(1, int(data.get('employees_required', 1)) if data.get('employees_required') else 1),
        'employee_restrictions': restrictions,
        'requires_callout': bool(data.get('requires_callout', False)),
        'requires_quote': bool(data.get('requires_quote', False)),
        'default_materials': data.get('default_materials', [])
    }
    
    # ─── New industry-specific fields ─────────────────────────────────
    import json as _json
    
    # Tags (array of strings)
    tags = data.get('tags')
    if tags and isinstance(tags, list):
        sanitized_data['tags'] = _json.dumps([str(t).strip() for t in tags if str(t).strip()])
    else:
        sanitized_data['tags'] = None
    
    # Capacity (restaurant party size)
    try:
        cap_min = int(data['capacity_min']) if data.get('capacity_min') else None
        sanitized_data['capacity_min'] = cap_min if cap_min and cap_min > 0 else None
    except (ValueError, TypeError):
        sanitized_data['capacity_min'] = None
    try:
        cap_max = int(data['capacity_max']) if data.get('capacity_max') else None
        sanitized_data['capacity_max'] = cap_max if cap_max and cap_max > 0 else None
    except (ValueError, TypeError):
        sanitized_data['capacity_max'] = None
    
    # Area (restaurant dining section)
    sanitized_data['area'] = data.get('area', '').strip() if data.get('area') else None
    
    # Deposit
    sanitized_data['requires_deposit'] = bool(data.get('requires_deposit', False))
    try:
        dep = float(data['deposit_amount']) if data.get('deposit_amount') else None
        sanitized_data['deposit_amount'] = dep if dep and dep > 0 else None
    except (ValueError, TypeError):
        sanitized_data['deposit_amount'] = None
    
    # Warranty
    sanitized_data['warranty'] = data.get('warranty', '').strip() if data.get('warranty') else None
    
    # Seasonal
    sanitized_data['seasonal'] = bool(data.get('seasonal', False))
    seasonal_months = data.get('seasonal_months')
    if seasonal_months and isinstance(seasonal_months, list):
        sanitized_data['seasonal_months'] = _json.dumps([int(m) for m in seasonal_months if isinstance(m, (int, float)) and 0 <= int(m) <= 11])
    else:
        sanitized_data['seasonal_months'] = None
    
    # AI Notes
    sanitized_data['ai_notes'] = data.get('ai_notes', '').strip() if data.get('ai_notes') else None
    
    # Follow-up service
    sanitized_data['follow_up_service_id'] = data.get('follow_up_service_id') if data.get('follow_up_service_id') else None
    
    success = settings_mgr.add_service(sanitized_data, company_id=company_id)
    if success:
        return jsonify({"message": "Service added successfully"})
    return jsonify({"error": "Failed to add service"}), 500


@app.route("/api/services/menu/service/<service_id>", methods=["PUT", "DELETE"])
@login_required
@subscription_required
def manage_service_api(service_id):
    """Update or delete a service"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    if request.method == "PUT":
        data = request.json
        
        # Validate name if provided
        if 'name' in data:
            name = data.get('name', '').strip() if data.get('name') else ''
            if not name:
                return jsonify({"error": "Service name is required"}), 400
            data['name'] = name
        
        # Sanitize price if provided
        if 'price' in data:
            try:
                price = float(data.get('price', 0)) if data.get('price') else 0
                data['price'] = price if price >= 0 else 0
            except (ValueError, TypeError):
                data['price'] = 0
        
        # Sanitize price_max if provided
        if 'price_max' in data:
            try:
                price_max = float(data.get('price_max', 0)) if data.get('price_max') else None
                price_val = data.get('price', 0) or 0
                if price_max is not None and price_max <= float(price_val):
                    price_max = None
                data['price_max'] = price_max
            except (ValueError, TypeError):
                data['price_max'] = None
        
        # Sanitize duration if provided
        if 'duration_minutes' in data:
            try:
                duration = int(data.get('duration_minutes', 1440)) if data.get('duration_minutes') else 1440
                data['duration_minutes'] = duration if duration > 0 else 1440
            except (ValueError, TypeError):
                data['duration_minutes'] = 1440
        
        # Sanitize employees_required if provided
        if 'employees_required' in data:
            try:
                employees = int(data.get('employees_required', 1)) if data.get('employees_required') else 1
                data['employees_required'] = max(1, employees)
            except (ValueError, TypeError):
                data['employees_required'] = 1
        
        # Handle employee_restrictions if provided
        if 'employee_restrictions' in data:
            # Validate structure: {type: 'all'|'only'|'except', employee_ids: [...]}
            restrictions = data.get('employee_restrictions')
            if restrictions and isinstance(restrictions, dict):
                valid_types = ['all', 'only', 'except']
                if restrictions.get('type') not in valid_types:
                    restrictions = None
                elif restrictions.get('type') != 'all' and not restrictions.get('employee_ids'):
                    restrictions = None  # 'only' and 'except' require employee_ids
                elif restrictions.get('type') == 'all':
                    restrictions = None  # 'all' doesn't need to be stored
            else:
                restrictions = None
            data['employee_restrictions'] = restrictions
        
        # Handle requires_callout if provided
        if 'requires_callout' in data:
            data['requires_callout'] = bool(data.get('requires_callout', False))
        
        # Handle requires_quote if provided
        if 'requires_quote' in data:
            data['requires_quote'] = bool(data.get('requires_quote', False))
        
        # Handle package_only if provided
        if 'package_only' in data:
            data['package_only'] = bool(data.get('package_only', False))
        
        # ─── New industry-specific fields ─────────────────────────────
        import json as _json
        
        if 'tags' in data:
            tags = data.get('tags')
            if tags and isinstance(tags, list):
                data['tags'] = _json.dumps([str(t).strip() for t in tags if str(t).strip()])
            else:
                data['tags'] = None
        
        if 'capacity_min' in data:
            try:
                v = int(data['capacity_min']) if data.get('capacity_min') else None
                data['capacity_min'] = v if v and v > 0 else None
            except (ValueError, TypeError):
                data['capacity_min'] = None
        
        if 'capacity_max' in data:
            try:
                v = int(data['capacity_max']) if data.get('capacity_max') else None
                data['capacity_max'] = v if v and v > 0 else None
            except (ValueError, TypeError):
                data['capacity_max'] = None
        
        if 'area' in data:
            data['area'] = data.get('area', '').strip() if data.get('area') else None
        
        if 'requires_deposit' in data:
            data['requires_deposit'] = bool(data.get('requires_deposit', False))
        
        if 'deposit_amount' in data:
            try:
                v = float(data['deposit_amount']) if data.get('deposit_amount') else None
                data['deposit_amount'] = v if v and v > 0 else None
            except (ValueError, TypeError):
                data['deposit_amount'] = None
        
        if 'warranty' in data:
            data['warranty'] = data.get('warranty', '').strip() if data.get('warranty') else None
        
        if 'seasonal' in data:
            data['seasonal'] = bool(data.get('seasonal', False))
        
        if 'seasonal_months' in data:
            sm = data.get('seasonal_months')
            if sm and isinstance(sm, list):
                data['seasonal_months'] = _json.dumps([int(m) for m in sm if isinstance(m, (int, float)) and 0 <= int(m) <= 11])
            else:
                data['seasonal_months'] = None
        
        if 'ai_notes' in data:
            data['ai_notes'] = data.get('ai_notes', '').strip() if data.get('ai_notes') else None
        
        if 'follow_up_service_id' in data:
            data['follow_up_service_id'] = data.get('follow_up_service_id') if data.get('follow_up_service_id') else None
        
        # Upload image to R2 if it's base64
        if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
            data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'services')
        elif 'image_url' in data and not data['image_url']:
            data['image_url'] = None
        
        success = settings_mgr.update_service(service_id, data, company_id=company_id)
        if success:
            return jsonify({"message": "Service updated successfully"})
        # Debug: check if service exists at all (without company_id filter)
        db = get_database()
        svc_any = db.get_service(service_id)
        svc_co = db.get_service(service_id, company_id=company_id) if company_id else None
        print(f"[DEBUG] update_service FAILED for id={service_id}, company_id={company_id}")
        print(f"[DEBUG]   exists_any={svc_any is not None}, exists_for_company={svc_co is not None}")
        if svc_any:
            print(f"[DEBUG]   service company_id={svc_any.get('company_id')}, active={svc_any.get('active')}")
        return jsonify({"error": "Service not found"}), 404
    
    elif request.method == "DELETE":
        result = settings_mgr.delete_service(service_id, company_id=company_id)
        if result.get('success'):
            return jsonify({
                "message": "Service deleted successfully",
                "jobs_affected": result.get('jobs_affected', 0)
            })
        return jsonify({"error": result.get('error', 'Service not found')}), 404


@app.route("/api/services/menu/service/<service_id>/toggle-active", methods=["POST"])
@login_required
@subscription_required
def toggle_service_active_api(service_id):
    """Toggle a service's active/inactive status"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    data = request.json or {}
    active = bool(data.get('active', True))
    
    success = settings_mgr.update_service(service_id, {'active': active}, company_id=company_id)
    if success:
        status = 'activated' if active else 'deactivated'
        return jsonify({"message": f"Service {status} successfully", "active": active})
    return jsonify({"error": "Service not found"}), 404


@app.route("/api/services/categories", methods=["GET", "POST"])
@login_required
def service_categories_api():
    """Get or create service categories for the company"""
    db = get_database()
    company_id = session.get('company_id')

    if request.method == "GET":
        cats = db.get_service_categories(company_id)
        return jsonify(cats)

    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Category name is required"}), 400
    color = data.get('color')
    success = db.add_service_category(company_id, name, color)
    if success:
        return jsonify({"message": "Category added"})
    return jsonify({"error": "Category already exists or failed to add"}), 409


@app.route("/api/services/categories/<int:cat_id>", methods=["PUT", "DELETE"])
@login_required
def manage_service_category_api(cat_id):
    """Update or delete a service category"""
    db = get_database()
    company_id = session.get('company_id')

    if request.method == "DELETE":
        success = db.delete_service_category(company_id, cat_id)
        if success:
            return jsonify({"message": "Category deleted"})
        return jsonify({"error": "Category not found"}), 404

    data = request.json or {}
    success = db.update_service_category(company_id, cat_id, **{k: v for k, v in data.items() if k in ('name', 'color', 'sort_order')})
    if success:
        return jsonify({"message": "Category updated"})
    return jsonify({"error": "Category not found"}), 404


# ============================================================
# Packages API (Service Bundles)
# ============================================================

@app.route("/api/packages", methods=["GET"])
@login_required
def get_packages_api():
    """Get all packages for the authenticated company"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    packages = settings_mgr.get_packages(company_id=company_id)
    return jsonify(packages)


@app.route("/api/packages", methods=["POST"])
@login_required
@subscription_required
def create_package_api():
    """Create a new package"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')

    db = get_database()
    company = db.get_company(company_id)
    subscription_info = get_subscription_info(company)
    if not subscription_info['is_active']:
        return jsonify({"error": "Active subscription required to create packages"}), 403

    data = request.json or {}
    result = settings_mgr.add_package(data, company_id=company_id)
    if result.get('success'):
        return jsonify({"message": "Package created", "package_id": result.get('package_id')})
    return jsonify({"error": result.get('error', 'Failed to create package')}), 400


@app.route("/api/packages/<package_id>", methods=["PUT"])
@login_required
@subscription_required
def update_package_api(package_id):
    """Update an existing package"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    data = request.json or {}
    result = settings_mgr.update_package(package_id, data, company_id=company_id)
    if result.get('success'):
        return jsonify({"message": "Package updated"})
    return jsonify({"error": result.get('error', 'Package not found')}), 404


@app.route("/api/packages/<package_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_package_api(package_id):
    """Delete a package"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    result = settings_mgr.delete_package(package_id, company_id=company_id)
    if result.get('success'):
        return jsonify({"message": "Package deleted", "jobs_affected": result.get('jobs_affected', 0)})
    return jsonify({"error": result.get('error', 'Package not found')}), 404


# ============================================================
# Materials Catalog & Job Materials API
# ============================================================

def _adjust_inventory_stock(db, company_id, material_id, quantity_delta):
    """Auto-adjust inventory stock when materials are added/removed from jobs.
    quantity_delta: negative = used on job (decrement), positive = returned to stock (increment).
    Only adjusts if the material has stock tracking enabled (stock_on_hand IS NOT NULL).
    """
    if not material_id:
        return  # Custom items (no catalog link) can't be tracked
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT stock_on_hand FROM materials WHERE id = %s AND company_id = %s",
            (material_id, company_id)
        )
        row = cursor.fetchone()
        if not row or row[0] is None:
            return  # Stock tracking not enabled for this item
        current = float(row[0])
        new_stock = max(0, current + quantity_delta)
        cursor.execute(
            "UPDATE materials SET stock_on_hand = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND company_id = %s",
            (new_stock, material_id, company_id)
        )
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[WARNING] Stock auto-adjust failed for material {material_id}: {e}")
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        db.return_connection(conn)


@app.route("/api/materials", methods=["GET", "POST"])
@login_required
@subscription_required
def materials_api():
    """Get all materials or create a new one"""
    company_id = session.get('company_id')
    db = get_database()

    if request.method == "GET":
        conn = db.get_connection()
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                "SELECT * FROM materials WHERE company_id = %s ORDER BY category NULLS LAST, name",
                (company_id,)
            )
            materials = [dict(r) for r in cursor.fetchall()]
            # Convert Decimal to float for JSON serialization
            low_stock_count = 0
            expiring_soon_count = 0
            from datetime import date, timedelta
            soon = date.today() + timedelta(days=7)
            for m in materials:
                if m.get('unit_price') is not None:
                    m['unit_price'] = float(m['unit_price'])
                if m.get('cost_price') is not None:
                    m['cost_price'] = float(m['cost_price'])
                if m.get('stock_on_hand') is not None:
                    m['stock_on_hand'] = float(m['stock_on_hand'])
                if m.get('reorder_level') is not None:
                    m['reorder_level'] = float(m['reorder_level'])
                if m.get('ideal_stock') is not None:
                    m['ideal_stock'] = float(m['ideal_stock'])
                # Convert expiry_date to ISO string for JSON
                if m.get('expiry_date') is not None:
                    exp = m['expiry_date']
                    # Compare before converting to string
                    is_expiring = exp <= soon if isinstance(exp, date) else False
                    is_expired = exp < date.today() if isinstance(exp, date) else False
                    m['expiry_date'] = exp.isoformat() if hasattr(exp, 'isoformat') else str(exp)
                    m['expiring_soon'] = is_expiring
                    m['expired'] = is_expired
                    if is_expiring and not is_expired:
                        expiring_soon_count += 1
                else:
                    m['expiring_soon'] = False
                    m['expired'] = False
                # Flag low stock items (at or below reorder level but still in stock)
                if (m.get('stock_on_hand') is not None and m.get('reorder_level') is not None
                        and m['stock_on_hand'] <= m['reorder_level']):
                    m['low_stock'] = True
                    if m['stock_on_hand'] > 0:
                        low_stock_count += 1
                else:
                    m['low_stock'] = False
            return jsonify({"materials": materials, "low_stock_count": low_stock_count, "expiring_soon_count": expiring_soon_count})
        finally:
            cursor.close()
            db.return_connection(conn)

    # POST - create new material
    data = request.json
    name = sanitize_string(data.get('name', ''), max_length=255)
    if not name:
        return jsonify({"error": "Material name is required"}), 400

    try:
        unit_price = float(data.get('unit_price', 0))
        if unit_price < 0:
            unit_price = 0
    except (ValueError, TypeError):
        unit_price = 0

    unit = sanitize_string(data.get('unit', 'each'), max_length=50) or 'each'
    category = sanitize_string(data.get('category', ''), max_length=100) or None
    supplier = sanitize_string(data.get('supplier', ''), max_length=255) or None
    sku = sanitize_string(data.get('sku', ''), max_length=100) or None
    notes = sanitize_string(data.get('notes', ''), max_length=2000) or None
    location = sanitize_string(data.get('location', ''), max_length=255) or None
    batch_number = sanitize_string(data.get('batch_number', ''), max_length=100) or None

    # Cost price (purchase price)
    cost_price = None
    if data.get('cost_price') is not None and data.get('cost_price') != '':
        try:
            cost_price = max(0, float(data['cost_price']))
        except (ValueError, TypeError):
            cost_price = None

    # Stock fields — None means "not tracked"
    stock_on_hand = None
    if data.get('stock_on_hand') is not None and data.get('stock_on_hand') != '':
        try:
            stock_on_hand = max(0, float(data['stock_on_hand']))
        except (ValueError, TypeError):
            stock_on_hand = None

    reorder_level = None
    if data.get('reorder_level') is not None and data.get('reorder_level') != '':
        try:
            reorder_level = max(0, float(data['reorder_level']))
        except (ValueError, TypeError):
            reorder_level = None

    ideal_stock = None
    if data.get('ideal_stock') is not None and data.get('ideal_stock') != '':
        try:
            ideal_stock = max(0, float(data['ideal_stock']))
        except (ValueError, TypeError):
            ideal_stock = None

    expiry_date = None
    if data.get('expiry_date'):
        try:
            from datetime import date as _date
            expiry_date = _date.fromisoformat(data['expiry_date'])
        except (ValueError, TypeError):
            expiry_date = None

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO materials (company_id, name, unit_price, cost_price, unit, category, supplier, sku, notes,
               stock_on_hand, reorder_level, ideal_stock, location, expiry_date, batch_number)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (company_id, name, unit_price, cost_price, unit, category, supplier, sku, notes,
             stock_on_hand, reorder_level, ideal_stock, location, expiry_date, batch_number)
        )
        material_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"success": True, "id": material_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.return_connection(conn)


@app.route("/api/materials/<int:material_id>", methods=["PUT", "DELETE"])
@login_required
@subscription_required
def material_detail_api(material_id):
    """Update or delete a material"""
    company_id = session.get('company_id')
    db = get_database()

    if request.method == "PUT":
        data = request.json
        fields, values = [], []

        if 'name' in data:
            name = sanitize_string(data['name'], max_length=255)
            if not name:
                return jsonify({"error": "Name is required"}), 400
            fields.append("name = %s"); values.append(name)
        if 'unit_price' in data:
            try:
                p = max(0, float(data['unit_price']))
            except (ValueError, TypeError):
                p = 0
            fields.append("unit_price = %s"); values.append(p)
        if 'cost_price' in data:
            if data['cost_price'] is None or data['cost_price'] == '':
                fields.append("cost_price = %s"); values.append(None)
            else:
                try:
                    fields.append("cost_price = %s"); values.append(max(0, float(data['cost_price'])))
                except (ValueError, TypeError):
                    pass
        if 'unit' in data:
            fields.append("unit = %s"); values.append(sanitize_string(data['unit'], max_length=50) or 'each')
        if 'category' in data:
            fields.append("category = %s"); values.append(sanitize_string(data['category'], max_length=100) or None)
        if 'supplier' in data:
            fields.append("supplier = %s"); values.append(sanitize_string(data['supplier'], max_length=255) or None)
        if 'sku' in data:
            fields.append("sku = %s"); values.append(sanitize_string(data['sku'], max_length=100) or None)
        if 'notes' in data:
            fields.append("notes = %s"); values.append(sanitize_string(data['notes'], max_length=2000) or None)
        if 'location' in data:
            fields.append("location = %s"); values.append(sanitize_string(data['location'], max_length=255) or None)
        if 'batch_number' in data:
            fields.append("batch_number = %s"); values.append(sanitize_string(data['batch_number'], max_length=100) or None)
        if 'stock_on_hand' in data:
            if data['stock_on_hand'] is None or data['stock_on_hand'] == '':
                fields.append("stock_on_hand = %s"); values.append(None)
            else:
                try:
                    fields.append("stock_on_hand = %s"); values.append(max(0, float(data['stock_on_hand'])))
                except (ValueError, TypeError):
                    pass
        if 'reorder_level' in data:
            if data['reorder_level'] is None or data['reorder_level'] == '':
                fields.append("reorder_level = %s"); values.append(None)
            else:
                try:
                    fields.append("reorder_level = %s"); values.append(max(0, float(data['reorder_level'])))
                except (ValueError, TypeError):
                    pass
        if 'ideal_stock' in data:
            if data['ideal_stock'] is None or data['ideal_stock'] == '':
                fields.append("ideal_stock = %s"); values.append(None)
            else:
                try:
                    fields.append("ideal_stock = %s"); values.append(max(0, float(data['ideal_stock'])))
                except (ValueError, TypeError):
                    pass
        if 'expiry_date' in data:
            if data['expiry_date'] is None or data['expiry_date'] == '':
                fields.append("expiry_date = %s"); values.append(None)
            else:
                try:
                    from datetime import date as _date
                    fields.append("expiry_date = %s"); values.append(_date.fromisoformat(data['expiry_date']))
                except (ValueError, TypeError):
                    pass

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([material_id, company_id])

        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE materials SET {', '.join(fields)} WHERE id = %s AND company_id = %s",
                values
            )
            conn.commit()
            return jsonify({"success": cursor.rowcount > 0})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            db.return_connection(conn)

    elif request.method == "DELETE":
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM materials WHERE id = %s AND company_id = %s", (material_id, company_id))
            conn.commit()
            return jsonify({"success": cursor.rowcount > 0})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            db.return_connection(conn)


@app.route("/api/materials/<int:material_id>/adjust-stock", methods=["POST"])
@login_required
@subscription_required
def material_adjust_stock(material_id):
    """Quick stock adjustment: add or subtract from current stock_on_hand"""
    company_id = session.get('company_id')
    db = get_database()
    data = request.json
    try:
        adjustment = float(data.get('adjustment', 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid adjustment value"}), 400

    if adjustment == 0:
        return jsonify({"error": "Adjustment cannot be zero"}), 400

    conn = db.get_connection()
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get current stock
        cursor.execute(
            "SELECT stock_on_hand FROM materials WHERE id = %s AND company_id = %s",
            (material_id, company_id)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Material not found"}), 404

        current = float(row['stock_on_hand']) if row['stock_on_hand'] is not None else None
        if current is None:
            return jsonify({"error": "Stock tracking not enabled for this item"}), 400
        new_stock = max(0, current + adjustment)

        cursor.execute(
            "UPDATE materials SET stock_on_hand = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND company_id = %s",
            (new_stock, material_id, company_id)
        )
        conn.commit()
        return jsonify({"success": True, "stock_on_hand": new_stock})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.return_connection(conn)


@app.route("/api/bookings/<int:booking_id>/materials", methods=["GET", "POST"])
@login_required
@subscription_required
def job_materials_api(booking_id):
    """Get or add materials for a job"""
    company_id = session.get('company_id')
    db = get_database()

    from psycopg2.extras import RealDictCursor

    if request.method == "GET":
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                "SELECT * FROM job_materials WHERE booking_id = %s AND company_id = %s ORDER BY created_at",
                (booking_id, company_id)
            )
            items = [dict(r) for r in cursor.fetchall()]
            # Convert Decimal to float for JSON serialization
            for item in items:
                for k in ('unit_price', 'quantity', 'total_cost'):
                    if item.get(k) is not None:
                        item[k] = float(item[k])
            total = sum(item.get('total_cost', 0) for item in items)
            return jsonify({"materials": items, "total_cost": round(total, 2)})
        finally:
            cursor.close()
            db.return_connection(conn)

    # POST - add material to job
    data = request.json
    name = sanitize_string(data.get('name', ''), max_length=255)
    if not name:
        return jsonify({"error": "Material name is required"}), 400

    try:
        unit_price = max(0, float(data.get('unit_price', 0)))
    except (ValueError, TypeError):
        unit_price = 0
    try:
        quantity = max(0.01, float(data.get('quantity', 1)))
    except (ValueError, TypeError):
        quantity = 1

    unit = sanitize_string(data.get('unit', 'each'), max_length=50) or 'each'
    material_id = data.get('material_id')  # nullable for custom items
    total_cost = round(unit_price * quantity, 2)
    added_by = data.get('added_by', 'owner')

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO job_materials (booking_id, company_id, material_id, name, unit_price, unit, quantity, total_cost, added_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (booking_id, company_id, material_id, name, unit_price, unit, quantity, total_cost, added_by)
        )
        item_id = cursor.fetchone()[0]
        conn.commit()
        # Auto-decrement inventory stock
        _adjust_inventory_stock(db, company_id, material_id, -quantity)
        return jsonify({"success": True, "id": item_id, "total_cost": total_cost})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.return_connection(conn)


@app.route("/api/bookings/<int:booking_id>/materials/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
@subscription_required
def job_material_detail_api(booking_id, item_id):
    """Update or delete a job material item"""
    company_id = session.get('company_id')
    db = get_database()

    if request.method == "DELETE":
        conn = db.get_connection()
        from psycopg2.extras import RealDictCursor as _RDC
        cursor = conn.cursor(cursor_factory=_RDC)
        try:
            # Get the item before deleting so we can restore stock
            cursor.execute(
                "SELECT material_id, quantity FROM job_materials WHERE id = %s AND booking_id = %s AND company_id = %s",
                (item_id, booking_id, company_id)
            )
            item = cursor.fetchone()
            cursor.execute(
                "DELETE FROM job_materials WHERE id = %s AND booking_id = %s AND company_id = %s",
                (item_id, booking_id, company_id)
            )
            conn.commit()
            # Restore stock for the removed quantity
            if item and item.get('material_id'):
                _adjust_inventory_stock(db, company_id, item['material_id'], float(item.get('quantity', 0)))
            return jsonify({"success": cursor.rowcount > 0})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            db.return_connection(conn)

    elif request.method == "PUT":
        data = request.json
        fields, values = [], []
        if 'quantity' in data:
            try:
                q = max(0.01, float(data['quantity']))
            except (ValueError, TypeError):
                q = 1
            fields.append("quantity = %s"); values.append(q)
        if 'unit_price' in data:
            try:
                p = max(0, float(data['unit_price']))
            except (ValueError, TypeError):
                p = 0
            fields.append("unit_price = %s"); values.append(p)
        if 'name' in data:
            fields.append("name = %s"); values.append(sanitize_string(data['name'], max_length=255))

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        # Recalculate total_cost
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            # Get current values for recalculation
            from psycopg2.extras import RealDictCursor
            cur2 = conn.cursor(cursor_factory=RealDictCursor)
            cur2.execute("SELECT * FROM job_materials WHERE id = %s AND booking_id = %s AND company_id = %s", (item_id, booking_id, company_id))
            existing = cur2.fetchone()
            cur2.close()
            if not existing:
                return jsonify({"error": "Not found"}), 404

            new_qty = float(data.get('quantity', existing['quantity']))
            new_price = float(data.get('unit_price', existing['unit_price']))
            total = round(new_qty * new_price, 2)
            fields.append("total_cost = %s"); values.append(total)

            values.extend([item_id, booking_id, company_id])
            cursor.execute(
                f"UPDATE job_materials SET {', '.join(fields)} WHERE id = %s AND booking_id = %s AND company_id = %s",
                values
            )
            conn.commit()
            # Adjust stock for quantity change (negative delta = more used, positive = less used)
            if 'quantity' in data and existing.get('material_id'):
                old_qty = float(existing['quantity'])
                qty_delta = old_qty - new_qty  # positive if reduced, negative if increased
                if qty_delta != 0:
                    _adjust_inventory_stock(db, company_id, existing['material_id'], qty_delta)
            return jsonify({"success": True, "total_cost": total})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            db.return_connection(conn)


# Employee endpoint for adding materials to their jobs
@app.route("/api/employee/jobs/<int:job_id>/materials", methods=["GET", "POST"])
@employee_login_required
def employee_job_materials_api(job_id):
    """Employees can view and add materials to their assigned jobs"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    db = get_database()

    # Verify employee is assigned
    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    if job_id not in [j['id'] for j in employee_jobs]:
        return jsonify({"error": "Job not found or not assigned to you"}), 404

    from psycopg2.extras import RealDictCursor

    if request.method == "GET":
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                "SELECT * FROM job_materials WHERE booking_id = %s AND company_id = %s ORDER BY created_at",
                (job_id, company_id)
            )
            items = [dict(r) for r in cursor.fetchall()]
            # Also get the materials catalog for the autocomplete
            cursor.execute(
                "SELECT id, name, unit_price, unit, category FROM materials WHERE company_id = %s ORDER BY name",
                (company_id,)
            )
            catalog = [dict(r) for r in cursor.fetchall()]
            # Convert Decimal to float for JSON serialization
            for item in items:
                for k in ('unit_price', 'quantity', 'total_cost'):
                    if item.get(k) is not None:
                        item[k] = float(item[k])
            for c in catalog:
                if c.get('unit_price') is not None:
                    c['unit_price'] = float(c['unit_price'])
            total = sum(item.get('total_cost', 0) for item in items)
            return jsonify({"materials": items, "catalog": catalog, "total_cost": round(total, 2)})
        finally:
            cursor.close()
            db.return_connection(conn)

    # POST
    data = request.json
    name = sanitize_string(data.get('name', ''), max_length=255)
    if not name:
        return jsonify({"error": "Material name is required"}), 400

    try:
        unit_price = max(0, float(data.get('unit_price', 0)))
    except (ValueError, TypeError):
        unit_price = 0
    try:
        quantity = max(0.01, float(data.get('quantity', 1)))
    except (ValueError, TypeError):
        quantity = 1

    unit = sanitize_string(data.get('unit', 'each'), max_length=50) or 'each'
    material_id = data.get('material_id')
    total_cost = round(unit_price * quantity, 2)

    # Get employee name for added_by
    employee_name = 'employee'
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        from psycopg2.extras import RealDictCursor as RDC
        cur2 = conn.cursor(cursor_factory=RDC)
        cur2.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
        w = cur2.fetchone()
        cur2.close()
        if w:
            employee_name = w['name']

        cursor.execute(
            """INSERT INTO job_materials (booking_id, company_id, material_id, name, unit_price, unit, quantity, total_cost, added_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (job_id, company_id, material_id, name, unit_price, unit, quantity, total_cost, f"employee:{employee_name}")
        )
        item_id = cursor.fetchone()[0]
        conn.commit()
        # Auto-decrement inventory stock
        _adjust_inventory_stock(db, company_id, material_id, -quantity)
        return jsonify({"success": True, "id": item_id, "total_cost": total_cost})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.return_connection(conn)


@app.route("/api/employee/jobs/<int:job_id>/materials/<int:item_id>", methods=["DELETE"])
@employee_login_required
def employee_delete_job_material(job_id, item_id):
    """Employees can remove materials they added"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    db = get_database()

    employee_jobs = db.get_employee_jobs(employee_id, include_completed=True, company_id=company_id)
    if job_id not in [j['id'] for j in employee_jobs]:
        return jsonify({"error": "Job not found"}), 404

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        # Get the item before deleting so we can restore stock
        from psycopg2.extras import RealDictCursor as _RDC2
        cur2 = conn.cursor(cursor_factory=_RDC2)
        cur2.execute(
            "SELECT material_id, quantity FROM job_materials WHERE id = %s AND booking_id = %s AND company_id = %s",
            (item_id, job_id, company_id)
        )
        item = cur2.fetchone()
        cur2.close()
        cursor.execute(
            "DELETE FROM job_materials WHERE id = %s AND booking_id = %s AND company_id = %s",
            (item_id, job_id, company_id)
        )
        conn.commit()
        # Restore stock for the removed quantity
        if item and item.get('material_id'):
            _adjust_inventory_stock(db, company_id, item['material_id'], float(item.get('quantity', 0)))
        return jsonify({"success": cursor.rowcount > 0})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.return_connection(conn)


@app.route("/api/services/business-hours", methods=["GET", "POST"])
@login_required
@subscription_required
def business_hours_api():
    """Get or update business hours"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        hours = settings_mgr.get_business_hours(company_id=company_id)
        return jsonify(hours)
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_business_hours(data, company_id=company_id)
        if success:
            # Sync: build days_open from per-day closed flags and update business_settings + companies table
            try:
                all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                days_open = [day for day in all_days if not data.get(f'{day.lower()}_closed', False)]
                
                # Also extract opening/closing hours from the per-day data if available
                # Use the first open day's hours as the canonical start/end
                start_hour = data.get('opening_hours_start')
                end_hour = data.get('opening_hours_end')
                if start_hour is None or end_hour is None:
                    for day in days_open:
                        open_val = data.get(f'{day.lower()}_open', '')
                        close_val = data.get(f'{day.lower()}_close', '')
                        if open_val and close_val:
                            try:
                                start_hour = int(open_val.split(':')[0])
                                end_hour = int(close_val.split(':')[0])
                            except (ValueError, IndexError):
                                pass
                            break
                
                # Update days_open in business_settings
                sync_data = {'days_open': days_open}
                if start_hour is not None:
                    sync_data['opening_hours_start'] = start_hour
                if end_hour is not None:
                    sync_data['opening_hours_end'] = end_hour
                settings_mgr.update_business_settings(sync_data, company_id=company_id)
                
                # Build and sync the business_hours string to companies table
                if start_hour is not None and end_hour is not None:
                    start_period = 'AM' if start_hour < 12 else 'PM'
                    end_period = 'AM' if end_hour < 12 else 'PM'
                    display_start = start_hour if start_hour <= 12 else start_hour - 12
                    display_end = end_hour if end_hour <= 12 else end_hour - 12
                    if display_start == 0: display_start = 12
                    if display_end == 0: display_end = 12
                    
                    if len(days_open) == 7:
                        days_text = 'Daily'
                    elif len(days_open) == 6 and 'Sunday' not in days_open:
                        days_text = 'Mon-Sat'
                    elif len(days_open) == 5 and 'Saturday' not in days_open and 'Sunday' not in days_open:
                        days_text = 'Mon-Fri'
                    else:
                        abbrevs = {'Monday': 'Mon', 'Tuesday': 'Tue', 'Wednesday': 'Wed',
                                   'Thursday': 'Thu', 'Friday': 'Fri', 'Saturday': 'Sat', 'Sunday': 'Sun'}
                        days_text = ', '.join(abbrevs.get(d, d) for d in days_open)
                    
                    hours_str = f"{display_start} {start_period} - {display_end} {end_period} {days_text}"
                    db = get_database()
                    db.update_company(company_id, business_hours=hours_str)
                    print(f"[BIZ-HOURS] Synced to companies table: {hours_str}")
                
                print(f"[BIZ-HOURS] Synced days_open={days_open} to business_settings")
            except Exception as sync_e:
                print(f"[WARNING] Could not sync business hours: {sync_e}")
            
            return jsonify({"message": "Business hours updated successfully"})
        return jsonify({"error": "Failed to update business hours"}), 500


@app.route("/api/clients", methods=["GET", "POST"])
@login_required
@subscription_required
@rate_limit(max_requests=30, window_seconds=60)
def clients_api():
    """Get all clients or create a new client"""
    from src.utils.security import normalize_name_for_comparison, normalize_phone_for_comparison
    
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        clients = db.get_all_clients(company_id=company_id)
        return jsonify(clients)
    
    elif request.method == "POST":
        # Check subscription for creating clients
        company = db.get_company(company_id)
        subscription_info = get_subscription_info(company)
        if not subscription_info['is_active']:
            return jsonify({
                "error": "Active subscription required to create clients",
                "subscription_status": "inactive"
            }), 403
        
        data = request.json
        
        # Validate required field: name
        name = data.get('name', '').strip() if data.get('name') else ''
        if not name:
            return jsonify({"error": "Customer name is required"}), 400
        
        # Sanitize optional fields - convert empty strings to None
        phone = data.get('phone', '').strip() if data.get('phone') else None
        email = data.get('email', '').strip() if data.get('email') else None
        
        # Check for duplicate customer using normalized comparison
        # (case-insensitive, ignores apostrophes/hyphens, normalized phone)
        if phone:
            normalized_name = normalize_name_for_comparison(name)
            normalized_phone = normalize_phone_for_comparison(phone)
            
            existing_clients = db.get_all_clients(company_id=company_id)
            for client in existing_clients:
                client_normalized_name = normalize_name_for_comparison(client.get('name', ''))
                client_normalized_phone = normalize_phone_for_comparison(client.get('phone') or '')
                
                if client_normalized_name == normalized_name and client_normalized_phone == normalized_phone:
                    # Return existing client instead of creating duplicate
                    return jsonify({
                        "id": client['id'], 
                        "message": "Existing customer found with matching name and phone",
                        "merged": True
                    }), 200
        
        client_id = db.add_client(
            name=name,
            phone=phone if phone else None,
            email=email if email else None,
            address=data.get('address', '').strip() or None,
            eircode=data.get('eircode', '').strip() or None,
            company_id=company_id
        )
        return jsonify({"id": client_id, "message": "Client created"}), 201


@app.route("/api/clients/<int:client_id>", methods=["GET", "PUT", "DELETE"])
@login_required
@subscription_required
def client_api(client_id):
    """Get, update or delete a specific client"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        # Get client with company_id filter for security
        client = db.get_client(client_id, company_id=company_id)
        if client:
            # Get bookings filtered by company_id
            bookings = db.get_client_bookings(client_id, company_id=company_id)
            client['bookings'] = bookings
            # Note: client['notes'] is already populated as a formatted string by get_client()
            # Don't overwrite it with the raw array from get_client_notes()
            
            # If client doesn't have address/eircode/email stored, get from most recent booking
            if not client.get('address') and bookings:
                # Find most recent booking with an address
                for booking in sorted(bookings, key=lambda b: b.get('appointment_time', ''), reverse=True):
                    if booking.get('address'):
                        client['address'] = booking['address']
                        break
            if not client.get('eircode') and bookings:
                # Find most recent booking with an eircode
                for booking in sorted(bookings, key=lambda b: b.get('appointment_time', ''), reverse=True):
                    if booking.get('eircode'):
                        client['eircode'] = booking['eircode']
                        break
            if not client.get('property_type') and bookings:
                for booking in sorted(bookings, key=lambda b: b.get('appointment_time', ''), reverse=True):
                    if booking.get('property_type'):
                        client['property_type'] = booking['property_type']
                        break
            if not client.get('email') and bookings:
                # Find most recent booking with an email
                for booking in sorted(bookings, key=lambda b: b.get('appointment_time', ''), reverse=True):
                    if booking.get('email'):
                        client['email'] = booking['email']
                        break
            
            # Get address_audio_url from most recent booking that has one
            if bookings:
                for booking in sorted(bookings, key=lambda b: b.get('appointment_time', ''), reverse=True):
                    if booking.get('address_audio_url'):
                        client['address_audio_url'] = booking['address_audio_url']
                        break
            
            return jsonify(client)
        return jsonify({"error": "Client not found"}), 404
    
    elif request.method == "PUT":
        # Verify client belongs to this company before updating
        client = db.get_client(client_id, company_id=company_id)
        if not client:
            return jsonify({"error": "Client not found"}), 404
        
        data = request.json
        
        # Sanitize fields
        sanitized_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip()
                # Name is required, don't allow empty
                if key == 'name':
                    if not value:
                        return jsonify({"error": "Customer name is required"}), 400
                    sanitized_data[key] = value
                # Optional fields - convert empty to None
                elif key in ['phone', 'email', 'notes', 'address']:
                    sanitized_data[key] = value if value else None
                else:
                    sanitized_data[key] = value
            else:
                sanitized_data[key] = value
        
        db.update_client(client_id, **sanitized_data)
        return jsonify({"message": "Client updated"})
    
    elif request.method == "DELETE":
        # Verify client belongs to this company before deleting
        client = db.get_client(client_id, company_id=company_id)
        if not client:
            return jsonify({"error": "Client not found"}), 404
        
        result = db.delete_client(client_id, company_id=company_id)
        if result.get('success'):
            return jsonify({
                "message": "Customer deleted",
                "bookings_deleted": result.get('bookings_deleted', 0)
            })
        return jsonify({"error": result.get('error', 'Failed to delete customer')}), 500


@app.route("/api/clients/<int:client_id>/notes", methods=["POST"])
@login_required
@subscription_required
def add_note_api(client_id):
    """Add a note to a client"""
    print(f"[ADD_NOTE] Adding note for client {client_id}")
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify client belongs to this company
    client = db.get_client(client_id, company_id=company_id)
    if not client:
        print(f"[ADD_NOTE] Client {client_id} not found for company {company_id}")
        return jsonify({"error": "Client not found"}), 404
    
    data = request.json
    print(f"[ADD_NOTE] Note data: {data}")
    
    note_id = db.add_note(
        client_id=client_id,
        note=data['note'],
        created_by=data.get('created_by', 'user')
    )
    print(f"[ADD_NOTE] Note added with ID: {note_id}")
    return jsonify({"id": note_id, "message": "Note added"}), 201


@app.route("/api/clients/<int:client_id>/timeline", methods=["GET"])
@login_required
def get_client_timeline(client_id):
    """Get a chronological activity timeline for a client — jobs, quotes, invoices, call logs, notes."""
    db = get_database()
    company_id = session.get('company_id')
    client = db.get_client(client_id, company_id=company_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    timeline = []
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Jobs/bookings
        cur.execute("""
            SELECT id, appointment_time as date, service_type, status, charge, payment_status, duration_minutes
            FROM bookings WHERE client_id = %s AND company_id = %s ORDER BY appointment_time DESC
        """, (client_id, company_id))
        for row in cur.fetchall():
            timeline.append({
                'type': 'job', 'date': str(row['date']),
                'title': row['service_type'] or 'Job',
                'status': row['status'], 'amount': float(row['charge'] or 0),
                'payment_status': row.get('payment_status'),
                'id': row['id'],
                'icon': 'fa-wrench', 'color': '#3b82f6'
            })

        # Quotes
        cur.execute("""
            SELECT id, created_at as date, title, status, total
            FROM quotes WHERE client_id = %s AND company_id = %s ORDER BY created_at DESC
        """, (client_id, company_id))
        for row in cur.fetchall():
            timeline.append({
                'type': 'quote', 'date': str(row['date']),
                'title': row['title'] or 'Quote',
                'status': row['status'], 'amount': float(row['total'] or 0),
                'id': row['id'],
                'icon': 'fa-file-invoice', 'color': '#8b5cf6'
            })

        # Credit notes
        cur.execute("""
            SELECT id, created_at as date, credit_note_number, amount, reason, stripe_refund_id
            FROM credit_notes WHERE client_id = %s AND company_id = %s ORDER BY created_at DESC
        """, (client_id, company_id))
        for row in cur.fetchall():
            timeline.append({
                'type': 'credit_note', 'date': str(row['date']),
                'title': f"{row['credit_note_number']} — {row['reason'] or 'Refund'}",
                'amount': float(row['amount'] or 0),
                'stripe_refunded': bool(row.get('stripe_refund_id')),
                'id': row['id'],
                'icon': 'fa-undo', 'color': '#ef4444'
            })

        # Call logs (if table exists)
        try:
            cur.execute("""
                SELECT id, created_at as date, duration_seconds, summary, caller_phone
                FROM call_logs WHERE company_id = %s AND caller_phone = %s ORDER BY created_at DESC LIMIT 20
            """, (company_id, client.get('phone') or ''))
            for row in cur.fetchall():
                dur = row.get('duration_seconds') or 0
                timeline.append({
                    'type': 'call', 'date': str(row['date']),
                    'title': row.get('summary') or f"Phone call ({dur // 60}m {dur % 60}s)",
                    'duration_seconds': dur,
                    'id': row['id'],
                    'icon': 'fa-phone', 'color': '#10b981'
                })
        except Exception:
            pass  # call_logs table may not exist

        # Client notes
        try:
            cur.execute("""
                SELECT id, created_at as date, note, created_by
                FROM client_notes WHERE client_id = %s ORDER BY created_at DESC
            """, (client_id,))
            for row in cur.fetchall():
                timeline.append({
                    'type': 'note', 'date': str(row['date']),
                    'title': row['note'][:120] + ('...' if len(row['note'] or '') > 120 else ''),
                    'created_by': row.get('created_by', 'user'),
                    'id': row['id'],
                    'icon': 'fa-sticky-note', 'color': '#f59e0b'
                })
        except Exception:
            pass

        cur.close()
    finally:
        db.return_connection(conn)

    # Sort by date descending
    timeline.sort(key=lambda x: x.get('date', ''), reverse=True)
    return jsonify(timeline)


@app.route("/api/bookings/<int:booking_id>/notes", methods=["GET", "POST"])
@login_required
@subscription_required
def appointment_notes_api(booking_id):
    """Get or add notes for a specific appointment"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    if request.method == "GET":
        notes = db.get_appointment_notes(booking_id)
        return jsonify(notes)
    
    elif request.method == "POST":
        client_id = booking['client_id']
        
        data = request.json
        note_id = db.add_appointment_note(
            booking_id=booking_id,
            note=data['note'],
            created_by=data.get('created_by', 'user')
        )
        
        # Update client description after adding note
        print(f"\n[UPDATE] Updating client description for client_id: {client_id} after adding note...")
        try:
            from src.services.client_description_generator import update_client_description
            success = update_client_description(client_id, company_id=company_id)
            if success:
                print(f"[SUCCESS] Successfully updated description for client {client_id}")
            else:
                print(f"[WARNING] Description update returned False for client {client_id}")
        except Exception as e:
            print(f"[ERROR] ERROR updating description for client {client_id}: {e}")
            import traceback
            traceback.print_exc()
        
        return jsonify({"id": note_id, "message": "Appointment note added"}), 201


@app.route("/api/bookings/<int:booking_id>/notes/<int:note_id>", methods=["PUT", "DELETE"])
@login_required
@subscription_required
def appointment_note_api(booking_id, note_id):
    """Update or delete a specific appointment note"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    # Get client_id for description update
    client_id = booking['client_id'] if booking else None
    
    if request.method == "PUT":
        data = request.json
        success = db.update_appointment_note(note_id, data['note'], booking_id=booking_id)
        if success:
            # Update client description after editing note
            if client_id:
                print(f"\n[UPDATE] Updating client description for client_id: {client_id} after editing note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id, company_id=company_id)
                    if success:
                        print(f"[SUCCESS] Successfully updated description for client {client_id}")
                    else:
                        print(f"[WARNING] Description update returned False for client {client_id}")
                except Exception as e:
                    print(f"[ERROR] ERROR updating description: {e}")
                    import traceback
                    traceback.print_exc()
            return jsonify({"message": "Note updated"})
        return jsonify({"error": "Note not found"}), 404
    
    elif request.method == "DELETE":
        success = db.delete_appointment_note(note_id, booking_id=booking_id)
        if success:
            # Update client description after deleting note
            if client_id:
                print(f"\n[UPDATE] Updating client description for client_id: {client_id} after deleting note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id, company_id=company_id)
                    if success:
                        print(f"[SUCCESS] Successfully updated description for client {client_id}")
                    else:
                        print(f"[WARNING] Description update returned False for client {client_id}")
                except Exception as e:
                    print(f"[ERROR] ERROR updating description: {e}")
                    import traceback
                    traceback.print_exc()
            return jsonify({"message": "Note deleted"})
        return jsonify({"error": "Note not found"}), 404


@app.route("/api/bookings", methods=["GET", "POST"])
@login_required
@subscription_required
@rate_limit(max_requests=30, window_seconds=60)
def bookings_api():
    """Get all bookings or create a new booking"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        bookings = db.get_all_bookings(company_id=company_id)
        # DEBUG: Log appointment_time types and values to diagnose timezone display issues
        if bookings:
            sample = bookings[0]
            raw_time = sample.get('appointment_time')
            from datetime import datetime as _dt
            print(f"[TZ_DEBUG] Server datetime.now()={_dt.now()}, sample appointment_time={raw_time} (type={type(raw_time).__name__})")
            if hasattr(raw_time, 'tzinfo'):
                print(f"[TZ_DEBUG] appointment_time.tzinfo={raw_time.tzinfo}")
            import json
            try:
                serialized = json.dumps(raw_time, default=str)
                print(f"[TZ_DEBUG] JSON serialized: {serialized}")
            except:
                pass
        return jsonify(bookings)
    
    elif request.method == "POST":
        # Check subscription for creating bookings
        company = db.get_company(company_id)
        subscription_info = get_subscription_info(company)
        if not subscription_info['is_active']:
            return jsonify({
                "error": "Active subscription required to create bookings",
                "subscription_status": "inactive"
            }), 403
        
        data = request.json
        
        # Required fields - validate they exist and are not empty
        client_id = data.get('client_id')
        appointment_time = data.get('appointment_time')
        service_type = data.get('service_type', '').strip() if data.get('service_type') else ''
        
        if not client_id:
            return jsonify({"error": "Customer is required"}), 400
        if not appointment_time:
            return jsonify({"error": "Date & Time is required"}), 400
        if not service_type:
            return jsonify({"error": "Service type is required"}), 400
        
        try:
            # Parse appointment time
            from datetime import datetime, timedelta
            if isinstance(appointment_time, str):
                appointment_dt = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
            else:
                appointment_dt = appointment_time
            
            # Get service duration
            from src.services.settings_manager import get_settings_manager
            settings_mgr = get_settings_manager()
            
            # Get duration from request or look up from service
            duration_minutes = data.get('duration_minutes')
            if duration_minutes:
                try:
                    duration_minutes = int(duration_minutes)
                except (ValueError, TypeError):
                    duration_minutes = None
            if not duration_minutes:
                # Try to get duration from service type
                service = settings_mgr.get_service_by_name(service_type, company_id=company_id)
                if service and service.get('duration_minutes'):
                    duration_minutes = service['duration_minutes']
                else:
                    duration_minutes = settings_mgr.get_default_duration_minutes(company_id=company_id)
            
            # Check for time conflicts using actual duration (no buffer)
            # Employee-aware: if specific employees are assigned, only check THEIR conflicts
            # 
            # We need to find any existing booking whose time span overlaps with the
            # NEW job's time span.  get_conflicting_bookings already computes each
            # existing booking's true end (including multi-day spans) and checks
            # overlap with the query window, so we just pass the new job's window.
            #
            # For multi-day / full-day jobs, compute the proper end via the same
            # helper the DB layer uses; for shorter jobs use simple arithmetic.
            if duration_minutes > 1440:
                # Multi-day: walk business days forward
                from src.utils.duration_utils import duration_to_business_days
                _biz_days = duration_to_business_days(duration_minutes, company_id=company_id)
                try:
                    from src.utils.config import config as _cfg
                    _biz_indices = _cfg.get_business_days_indices(company_id=company_id)
                    _bh = _cfg.get_business_hours(company_id=company_id)
                    _bh_end = _bh.get('end', 17)
                except Exception:
                    _biz_indices = [0, 1, 2, 3, 4]
                    _bh_end = 17
                _cur = appointment_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                _counted = 0
                while _counted < _biz_days:
                    if _cur.weekday() in _biz_indices:
                        _counted += 1
                        if _counted >= _biz_days:
                            break
                    _cur += timedelta(days=1)
                new_job_end = _cur.replace(hour=_bh_end, minute=0, second=0, microsecond=0)
            elif duration_minutes >= 480:
                # Full-day job: ends at business close same day
                try:
                    from src.utils.config import config as _cfg
                    _bh = _cfg.get_business_hours(company_id=company_id)
                    _bh_end = _bh.get('end', 17)
                except Exception:
                    _bh_end = 17
                new_job_end = appointment_dt.replace(hour=_bh_end, minute=0, second=0, microsecond=0)
            else:
                new_job_end = appointment_dt + timedelta(minutes=duration_minutes)
            
            conflict_range_start = appointment_dt
            conflict_range_end = new_job_end
            
            # Parse employee_ids early so we can use them for conflict checking
            requested_employee_ids = [int(w) for w in data.get('employee_ids', []) if w]
            single_wid = data.get('employee_id')
            if single_wid and not requested_employee_ids:
                try:
                    requested_employee_ids = [int(single_wid)]
                except (ValueError, TypeError):
                    pass
            
            conflicting_bookings = db.get_conflicting_bookings(
                start_time=conflict_range_start.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=conflict_range_end.strftime('%Y-%m-%d %H:%M:%S'),
                company_id=company_id
            )
            
            if conflicting_bookings and requested_employee_ids:
                # Employees are assigned — only block if one of THOSE employees is on a conflicting booking
                employee_conflict = None
                for wid in requested_employee_ids:
                    for cb in conflicting_bookings:
                        assigned = db.get_job_employees(cb['id'])
                        if any(w['id'] == wid for w in assigned):
                            employee_conflict = (wid, cb)
                            break
                    if employee_conflict:
                        break
                
                if employee_conflict:
                    wid, conflict = employee_conflict
                    conflict_time = datetime.fromisoformat(str(conflict['appointment_time']))
                    conflict_client = db.get_client(conflict['client_id'], company_id=company_id)
                    conflict_client_name = conflict_client['name'] if conflict_client else 'Unknown'
                    conflict_employee = db.get_employee(wid, company_id=company_id)
                    conflict_employee_name = conflict_employee['name'] if conflict_employee else f'Employee {wid}'
                    
                    return jsonify({
                        "error": f"Time conflict: {conflict_employee_name} already has a booking at {conflict_time.strftime('%I:%M %p')} for {conflict_client_name} ({conflict['service_type']}). Please choose a different time or remove this employee.",
                        "conflict": True,
                        "conflicting_time": conflict_time.isoformat(),
                        "conflicting_client": conflict_client_name,
                        "conflicting_employee": conflict_employee_name
                    }), 409
            elif conflicting_bookings and not requested_employee_ids:
                # No employees assigned — keep the general conflict check as a safety net
                # BUT skip this if auto_assign_employee is set, because the auto-assign
                # logic will find a free employee (the calendar already showed availability)
                if not data.get('auto_assign_employee'):
                    conflict = conflicting_bookings[0]
                    conflict_time = datetime.fromisoformat(str(conflict['appointment_time']))
                    conflict_client = db.get_client(conflict['client_id'], company_id=company_id)
                    conflict_client_name = conflict_client['name'] if conflict_client else 'Unknown'
                    
                    return jsonify({
                        "error": f"Time conflict: There is already a booking at {conflict_time.strftime('%I:%M %p')} for {conflict_client_name} ({conflict['service_type']}). Please choose a different time.",
                        "conflict": True,
                        "conflicting_time": conflict_time.isoformat(),
                        "conflicting_client": conflict_client_name
                    }), 409
            
            # Google Calendar integration disabled (USE_GOOGLE_CALENDAR = False)
            calendar_event_id = None
            
            # Get client info (already verified by company_id)
            client = db.get_client(client_id, company_id=company_id)
            if not client:
                return jsonify({"error": "Customer not found"}), 404
            
            # Sanitize optional fields - convert empty strings to None
            job_address = (data.get('job_address') or data.get('address') or '').strip()
            job_address = job_address if job_address else None
            
            job_eircode = (data.get('eircode') or '').strip()
            job_eircode = job_eircode if job_eircode else None
            
            job_property_type = (data.get('property_type') or '').strip()
            job_property_type = job_property_type if job_property_type else None
            
            # If address not provided, try to get from client's previous bookings
            previous_address_audio_url = None
            previous_booking = db.get_client_last_booking_with_address(client_id)
            if previous_booking:
                if not job_address and previous_booking['address']:
                    job_address = previous_booking['address']
                    print(f"[INFO] Using address from previous booking: {job_address}")
                
                if not job_eircode and previous_booking['eircode']:
                    job_eircode = previous_booking['eircode']
                    print(f"[INFO] Using eircode from previous booking: {job_eircode}")
                
                if not job_property_type and previous_booking.get('property_type'):
                    job_property_type = previous_booking['property_type']
                    print(f"[INFO] Using property type from previous booking: {job_property_type}")
                
                if previous_booking.get('address_audio_url'):
                    previous_address_audio_url = previous_booking['address_audio_url']
                    print(f"[INFO] Will carry over address audio from previous booking: {previous_address_audio_url}")
            
            # Create booking - accept both 'charge' and 'estimated_charge' from frontend
            # Sanitize charge value
            job_charge = data.get('charge') or data.get('estimated_charge')
            if job_charge:
                try:
                    job_charge = round(float(job_charge), 2)
                    if job_charge < 0:
                        job_charge = None
                except (ValueError, TypeError):
                    job_charge = None
            else:
                job_charge = None
            
            # Sanitize charge_max for price ranges
            job_charge_max = data.get('estimated_charge_max')
            if job_charge_max:
                try:
                    job_charge_max = round(float(job_charge_max), 2)
                    if job_charge_max <= (job_charge or 0):
                        job_charge_max = None
                except (ValueError, TypeError):
                    job_charge_max = None
            else:
                job_charge_max = None
            
            booking_id = db.add_booking(
                client_id=client_id,
                calendar_event_id=calendar_event_id,
                appointment_time=appointment_dt,
                service_type=service_type,
                phone_number=data.get('phone_number'),
                email=data.get('email'),
                address=job_address,
                eircode=job_eircode,
                property_type=job_property_type,
                charge=job_charge,
                charge_max=job_charge_max,
                company_id=company_id,
                duration_minutes=duration_minutes,
                requires_callout=bool(data.get('requires_callout', False)),
                requires_quote=bool(data.get('requires_quote', False)),
                table_number=(data.get('table_number') or '').strip() or None,
                party_size=int(data['party_size']) if data.get('party_size') else None,
                dining_area=(data.get('dining_area') or '').strip() or None,
                special_requests=(data.get('special_requests') or '').strip() or None,
            )
            
            # Add initial note if provided
            if data.get('notes'):
                db.add_appointment_note(
                    booking_id=booking_id,
                    note=data['notes'],
                    created_by="user"
                )
            
            # Carry over address audio recording from previous booking for returning customers
            if previous_address_audio_url and booking_id:
                try:
                    db.update_booking(booking_id, address_audio_url=previous_address_audio_url)
                    print(f"[INFO] Address audio URL carried over to booking {booking_id}: {previous_address_audio_url}")
                except Exception as e:
                    print(f"[WARNING] Could not carry over address audio URL: {e}")

            # Save recurrence pattern if set
            recurrence_pattern = data.get('recurrence_pattern', '').strip()
            recurrence_end_date = data.get('recurrence_end_date', '').strip() or None
            if recurrence_pattern and recurrence_pattern in ('weekly', 'biweekly', 'monthly', 'quarterly'):
                db.update_booking(booking_id, company_id=company_id,
                    recurrence_pattern=recurrence_pattern,
                    recurrence_end_date=recurrence_end_date)
            
            # Assign employee(s) — reuse the employee_ids parsed earlier for conflict checking
            assigned_employee_ids_for_notif = []
            for wid in requested_employee_ids:
                try:
                    employee = db.get_employee(wid, company_id=company_id)
                    if employee:
                        db.assign_employee_to_job(booking_id, wid)
                        assigned_employee_ids_for_notif.append(wid)
                        print(f"[INFO] Employee {wid} assigned to booking {booking_id}")
                except Exception as e:
                    print(f"[WARNING] Could not assign employee {wid}: {e}")
            
            # Auto-assign an available employee if requested (from "Any available employee" mode)
            if data.get('auto_assign_employee') and not requested_employee_ids:
                try:
                    all_employees = db.get_all_employees(company_id=company_id)
                    
                    # Respect service employee_restrictions
                    eligible_employees = all_employees
                    if service_type:
                        service = settings_mgr.get_service_by_name(service_type, company_id=company_id)
                        if service and service.get('employee_restrictions'):
                            wr = service['employee_restrictions']
                            wr_type = wr.get('type', 'all')
                            wr_ids = wr.get('employee_ids', [])
                            if wr_type == 'only' and wr_ids:
                                eligible_employees = [w for w in all_employees if w['id'] in wr_ids]
                            elif wr_type == 'except' and wr_ids:
                                eligible_employees = [w for w in all_employees if w['id'] not in wr_ids]
                    
                    # Find the first available employee
                    assigned_auto = False
                    for w in eligible_employees:
                        avail = db.check_employee_availability(
                            w['id'], appointment_dt, duration_minutes, company_id=company_id
                        )
                        if avail.get('available'):
                            db.assign_employee_to_job(booking_id, w['id'])
                            assigned_employee_ids_for_notif.append(w['id'])
                            print(f"[INFO] Auto-assigned employee {w['id']} ({w.get('name')}) to booking {booking_id}")
                            assigned_auto = True
                            break
                    
                    if not assigned_auto:
                        print(f"[WARNING] No available employee found for auto-assignment on booking {booking_id}")
                        # All employees are busy — delete the booking and return an error
                        try:
                            db.delete_booking(booking_id, company_id=company_id)
                        except Exception:
                            pass
                        return jsonify({
                            "error": "No employees are available at this time. All employees are already booked. Please choose a different time slot.",
                            "conflict": True,
                            "no_employees_available": True
                        }), 409
                except Exception as e:
                    print(f"[WARNING] Auto-assign employee failed: {e}")

            # Notify assigned employees about the new job
            for wid in assigned_employee_ids_for_notif:
                try:
                    appt_str = appointment_dt.strftime('%b %d at %I:%M %p')
                    customer_name = client.get('name', 'a customer') if client else 'a customer'
                    db.create_notification(
                        company_id=company_id,
                        recipient_type='employee',
                        recipient_id=wid,
                        notif_type='job_assigned',
                        message=f"You've been booked for {service_type or 'a job'} with {customer_name} on {appt_str}",
                        metadata={'booking_id': booking_id, 'service_type': service_type,
                                  'appointment_time': appointment_dt.isoformat()}
                    )
                except Exception as e:
                    print(f"[WARNING] Could not notify employee {wid}: {e}")
            
            # Update client description
            try:
                from src.services.client_description_generator import update_client_description
                update_client_description(client_id, company_id=company_id)
            except Exception as e:
                print(f"[WARNING] Could not update client description: {e}")

            # Send confirmation email/SMS to customer (same as AI-booked jobs)
            try:
                _company_info = db.get_company(company_id)
                _send_confirm = _company_info.get('send_confirmation_sms', True) if _company_info else True
                if _send_confirm:
                    from src.services.sms_reminder import notify_customer, get_or_create_portal_link
                    _company_name = _company_info.get('company_name') if _company_info else None
                    _cust_email = (data.get('email') or '').strip() or (client.get('email') or '').strip() or None
                    _cust_phone = (data.get('phone_number') or '').strip() or (client.get('phone') or '').strip() or None

                    # Build portal link for the customer
                    _portal_link = ''
                    if _cust_email and client_id and company_id:
                        try:
                            _portal_link = get_or_create_portal_link(company_id, client_id)
                        except Exception:
                            pass

                    # Gather assigned employee names
                    _employee_names = []
                    if assigned_employee_ids_for_notif:
                        for _wid in assigned_employee_ids_for_notif:
                            _w = db.get_employee(_wid, company_id=company_id)
                            if _w:
                                _employee_names.append(_w.get('name', ''))

                    notify_customer(
                        'booking_confirmation',
                        customer_email=_cust_email,
                        customer_phone=_cust_phone,
                        appointment_time=appointment_dt,
                        customer_name=client.get('name', 'Customer') if client else 'Customer',
                        service_type=service_type or 'appointment',
                        company_name=_company_name,
                        company_email=(_company_info.get('email') or '').strip() if _company_info else None,
                        employee_names=_employee_names if _employee_names else None,
                        address=job_address,
                        portal_link=_portal_link,
                    )
                    print(f"[INFO] Confirmation notification sent for manual booking {booking_id}")
            except Exception as e:
                print(f"[WARNING] Could not send confirmation for manual booking: {e}")
            
            # Auto-attach default materials from service/package
            try:
                default_materials = []
                # Check if this is a package first, then fall back to service
                all_packages = settings_mgr.get_packages(company_id=company_id, active_only=True)
                matched_package = next((p for p in all_packages if p.get('name') == service_type), None)
                if matched_package and matched_package.get('default_materials'):
                    dm = matched_package['default_materials']
                    if isinstance(dm, str):
                        import json as _json
                        dm = _json.loads(dm)
                    default_materials = dm if isinstance(dm, list) else []
                else:
                    service = settings_mgr.get_service_by_name(service_type, company_id=company_id)
                    if service and service.get('default_materials'):
                        dm = service['default_materials']
                        if isinstance(dm, str):
                            import json as _json
                            dm = _json.loads(dm)
                        default_materials = dm if isinstance(dm, list) else []
                
                if default_materials:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    try:
                        attached_count = 0
                        for mat in default_materials:
                            if not isinstance(mat, dict):
                                continue
                            mat_name = mat.get('name', '')
                            if not mat_name:
                                continue
                            try:
                                mat_price = float(mat.get('unit_price', 0) or 0)
                            except (ValueError, TypeError):
                                mat_price = 0
                            try:
                                mat_qty = float(mat.get('quantity', 1) or 1)
                            except (ValueError, TypeError):
                                mat_qty = 1
                            mat_unit = mat.get('unit', 'each') or 'each'
                            mat_id = mat.get('material_id')
                            total = round(mat_price * mat_qty, 2)
                            cursor.execute(
                                """INSERT INTO job_materials (booking_id, company_id, material_id, name, unit_price, unit, quantity, total_cost, added_by)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                (booking_id, company_id, mat_id, mat_name, mat_price, mat_unit, mat_qty, total, 'auto')
                            )
                            attached_count += 1
                        conn.commit()
                        if attached_count > 0:
                            print(f"[INFO] Auto-attached {attached_count} default materials to booking {booking_id}")
                        # Auto-decrement inventory stock for attached materials
                        for mat in default_materials:
                            if isinstance(mat, dict) and mat.get('material_id'):
                                try:
                                    _qty = float(mat.get('quantity', 1) or 1)
                                    _adjust_inventory_stock(db, company_id, mat['material_id'], -_qty)
                                except Exception:
                                    pass
                    except Exception as mat_err:
                        conn.rollback()
                        print(f"[WARNING] Could not auto-attach materials: {mat_err}")
                    finally:
                        cursor.close()
                        db.return_connection(conn)
            except Exception as e:
                print(f"[WARNING] Default materials lookup failed: {e}")
            
            # Sync to Google Calendar if connected
            try:
                from src.services.google_calendar_oauth import get_company_google_calendar
                gcal = get_company_google_calendar(company_id, db)
                if gcal:
                    customer_name = client.get('name', 'Customer')
                    phone = data.get('phone_number') or client.get('phone') or ''
                    summary = f"{service_type} - {customer_name}"

                    # Build employee info for description
                    job_employees = db.get_job_employees(booking_id, company_id=company_id)
                    employee_lines = ''
                    if job_employees:
                        employee_names = [f"{w['name']}{' (' + w['trade_specialty'] + ')' if w.get('trade_specialty') else ''}" for w in job_employees]
                        employee_lines = f"\nEmployees: {', '.join(employee_names)}"

                    desc = (
                        f"Synced from BookedForYou\n"
                        f"Customer: {customer_name}\n"
                        f"Phone: {phone}\n"
                        f"Address: {job_address or ''}\n"
                        f"Duration: {duration_minutes} mins"
                        f"{employee_lines}"
                    )

                    # Check if employee invites are enabled
                    attendee_emails = None
                    company = db.get_company(company_id)
                    if company and company.get('gcal_invite_employees'):
                        attendee_emails = [w['email'] for w in job_employees if w.get('email')]
                        if not attendee_emails:
                            attendee_emails = None

                    gcal_event = gcal.book_appointment(
                        summary=summary,
                        start_time=appointment_dt,
                        duration_minutes=duration_minutes,
                        description=desc,
                        phone_number=phone,
                        attendee_emails=attendee_emails
                    )
                    if gcal_event and gcal_event.get('id'):
                        db.update_booking(
                            booking_id,
                            calendar_event_id=gcal_event['id'],
                            company_id=company_id
                        )
            except Exception as e:
                safe_print(f"[GCAL] Auto-sync on manual create failed (non-critical): {e}")
            
            # EMERGENCY JOB: If is_emergency flag is set, update urgency and dispatch to employees
            if data.get('is_emergency') and booking_id:
                try:
                    from datetime import datetime as _edt
                    db.update_booking(booking_id, urgency='emergency', emergency_status='pending_acceptance')
                    
                    # Notify all employees
                    all_employees = db.get_all_employees(company_id=company_id) or []
                    _company_info = db.get_company(company_id)
                    _company_name = _company_info.get('company_name', 'Your employer') if _company_info else 'Your employer'
                    customer_name = client.get('name', 'Customer') if client else 'Customer'
                    
                    for _ew in all_employees:
                        db.create_notification(
                            company_id=company_id,
                            recipient_type='employee',
                            recipient_id=_ew['id'],
                            notif_type='emergency_job',
                            message=f"EMERGENCY: {service_type} at {job_address or job_eircode or 'TBD'} for {customer_name}. Accept to dispatch.",
                            metadata={
                                'booking_id': booking_id,
                                'customer_name': customer_name,
                                'job_description': service_type,
                                'address': job_address or job_eircode or '',
                                'appointment_time': appointment_dt.isoformat(),
                            }
                        )
                        # Email employee
                        _ew_email = _ew.get('email')
                        if _ew_email:
                            try:
                                from src.services.email_reminder import get_email_service
                                _esvc = get_email_service()
                                if _esvc.configured:
                                    _time_str = appointment_dt.strftime('%A, %B %d at %I:%M %p')
                                    _subj = f"EMERGENCY JOB - {service_type} - Action Required"
                                    _txt = (
                                        f"{_company_name}\n\nEMERGENCY JOB ALERT\n\n"
                                        f"Customer: {customer_name}\nIssue: {service_type}\n"
                                        f"Location: {job_address or job_eircode or 'TBD'}\n"
                                        f"When: {_time_str}\n\n"
                                        f"Log in to your dashboard to accept this job."
                                    )
                                    _html = f'''<html><body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
    <div style="background:linear-gradient(135deg,#dc2626 0%,#ef4444 100%);padding:25px;text-align:center;border-radius:12px 12px 0 0;">
        <div style="font-size:24px;font-weight:800;color:white;">EMERGENCY JOB</div>
    </div>
    <div style="background:white;padding:25px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;">
        <p style="color:#dc2626;font-weight:700;font-size:18px;margin:0 0 15px;">Immediate response needed</p>
        <div style="background:#fef2f2;border-left:4px solid #ef4444;padding:15px;margin:20px 0;border-radius:0 8px 8px 0;">
            <p style="margin:5px 0;"><strong>Customer:</strong> {customer_name}</p>
            <p style="margin:5px 0;"><strong>Issue:</strong> {service_type}</p>
            <p style="margin:5px 0;"><strong>Location:</strong> {job_address or job_eircode or 'TBD'}</p>
            <p style="margin:5px 0;"><strong>When:</strong> {_time_str}</p>
        </div>
        <p>Log in to your employee dashboard to accept this emergency job.</p>
        <p style="margin-top:25px;">— {_company_name}</p>
    </div>
</div></body></html>'''
                                    _esvc._send_email(_ew_email, _subj, _html, _txt, _company_name)
                            except Exception:
                                pass
                    
                    print(f"[INFO] Emergency job {booking_id} — notified {len(all_employees)} employees")
                except Exception as emg_err:
                    print(f"[WARNING] Emergency dispatch failed: {emg_err}")
            
            # Auto-generate a draft quote for the job
            try:
                import json as _json
                conn_q = db.get_connection()
                cur_q = conn_q.cursor()
                # Generate quote number
                _company_q = db.get_company(company_id)
                _next_num = int(_company_q.get('invoice_next_number', 1) or 1) if _company_q else 1
                _quote_number = f"QTE-{_next_num:04d}"
                _charge = job_charge or 0
                _line_items = _json.dumps([{"description": service_type, "quantity": 1, "amount": _charge}])
                cur_q.execute("""
                    INSERT INTO quotes (company_id, client_id, quote_number, title, description,
                                        line_items, subtotal, tax_rate, tax_amount, total,
                                        status, notes, source_booking_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, %s, 'draft', %s, %s)
                """, (company_id, client_id, _quote_number, service_type, '',
                      _line_items, _charge, _charge,
                      data.get('notes', ''), booking_id))
                conn_q.commit()
                cur_q.close()
                db.return_connection(conn_q)
                print(f"[INFO] Auto-generated draft quote {_quote_number} for booking {booking_id}")
            except Exception as q_err:
                print(f"[WARNING] Auto-quote generation failed (non-critical): {q_err}")
                try:
                    conn_q.rollback()
                    db.return_connection(conn_q)
                except:
                    pass
            
            return jsonify({
                "success": True,
                "booking_id": booking_id,
                "message": "Job created successfully"
            }), 201
            
        except Exception as e:
            print(f"[ERROR] Error creating booking: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


@app.route("/api/bookings/availability", methods=["GET"])
@login_required
def check_availability_api():
    """Check available time slots for a given date, optionally filtered by employee"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Get parameters
    date_str = request.args.get('date')
    service_type = request.args.get('service_type')  # Optional: to get service-specific duration
    employee_id = request.args.get('employee_id')  # Optional: filter by employee availability
    any_employee = request.args.get('any_employee', 'false').lower() == 'true'  # Show combined availability across all employees
    override_duration = request.args.get('duration_minutes', type=int)  # Optional: override service duration
    
    if not date_str:
        return jsonify({"error": "Date parameter required (YYYY-MM-DD)"}), 400
    
    # Convert employee_id to int if provided
    if employee_id:
        try:
            employee_id = int(employee_id)
        except (ValueError, TypeError):
            employee_id = None
    
    try:
        from datetime import datetime, timedelta
        from src.services.settings_manager import get_settings_manager
        
        # Parse the date
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = target_date.strftime('%A').lower()
        
        # Get settings manager for duration
        settings_mgr = get_settings_manager()
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)
        
        # Get service-specific duration if service_type provided
        slot_duration = default_duration
        if override_duration and override_duration > 0:
            slot_duration = override_duration
        elif service_type:
            service = settings_mgr.get_service_by_name(service_type, company_id=company_id)
            if service and service.get('duration_minutes'):
                slot_duration = service['duration_minutes']
        
        # Get business hours from company settings (stored as string like "8 AM - 6 PM Mon-Sat")
        business_hours = {
            'start': 9,  # Default 9 AM
            'end': 17,   # Default 5 PM
            'interval': 30,  # 30 minute slot intervals
            'is_open': True,
            'default_duration': default_duration
        }
        
        # Try to get configured business hours from company settings
        try:
            company = db.get_company(company_id)
            if company and company.get('business_hours'):
                hours_str = company['business_hours']
                # Parse format: "8 AM - 6 PM Mon-Sat (24/7 emergency available)"
                import re
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
                    
                    business_hours['start'] = start_hour
                    business_hours['end'] = end_hour
                
                # Parse days from the string
                hours_lower = hours_str.lower()
                day_map = {
                    'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
                    'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
                }
                day_abbrev = day_map.get(day_name, day_name[:3])
                
                # Check if this day is open
                is_open = True
                if 'daily' in hours_lower or 'mon-sun' in hours_lower:
                    is_open = True
                elif 'mon-sat' in hours_lower:
                    is_open = day_name != 'sunday'
                elif 'mon-fri' in hours_lower:
                    is_open = day_name not in ['saturday', 'sunday']
                else:
                    # Check for individual day mentions
                    is_open = day_abbrev in hours_lower or day_name in hours_lower
                
                business_hours['is_open'] = is_open
                
        except Exception as e:
            print(f"[WARNING] Could not load business hours: {e}")
        
        # Generate time slots for the day
        slots = []
        
        # Check if business is open on this day
        if not business_hours.get('is_open', True):
            return jsonify({
                'date': date_str,
                'slots': [],
                'business_hours': business_hours,
                'message': 'Business is closed on this day'
            })
        
        # Get all bookings for this day to check conflicts
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        all_bookings = db.get_all_bookings(company_id=company_id)

        # Helper: compute booking end time for a given booking
        def _compute_booking_end(appt_time, booking_duration):
            if booking_duration > 1440:
                from src.utils.duration_utils import duration_to_business_days
                _biz_days = duration_to_business_days(booking_duration, company_id=company_id)
                try:
                    from src.utils.config import config as _cfg
                    _biz_indices = _cfg.get_business_days_indices(company_id=company_id)
                except Exception:
                    _biz_indices = [0, 1, 2, 3, 4]
                _cur_day = appt_time.replace(hour=0, minute=0, second=0, microsecond=0)
                _counted = 0
                _last_biz = _cur_day
                for _ in range(365):
                    if _cur_day.weekday() in _biz_indices:
                        _counted += 1
                        _last_biz = _cur_day
                        if _counted >= _biz_days:
                            break
                    _cur_day += timedelta(days=1)
                return _last_biz.replace(hour=business_hours.get('end', 17), minute=0, second=0, microsecond=0)
            elif booking_duration >= 480:
                return appt_time.replace(hour=business_hours.get('end', 17), minute=0, second=0, microsecond=0)
            else:
                return appt_time + timedelta(minutes=booking_duration)

        # Helper: filter bookings that overlap with the target day, optionally for a specific employee
        def _get_day_bookings(filter_employee_id=None):
            result = []
            for booking in all_bookings:
                if booking.get('status') in ['cancelled', 'completed']:
                    continue
                if filter_employee_id:
                    assigned_ids = booking.get('assigned_employee_ids') or []
                    # Unassigned bookings block all employees (could be assigned to anyone)
                    if len(assigned_ids) > 0 and filter_employee_id not in assigned_ids and str(filter_employee_id) not in [str(x) for x in assigned_ids]:
                        continue
                appt_time = booking.get('appointment_time')
                if isinstance(appt_time, str):
                    appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00').replace('+00:00', ''))
                if not appt_time:
                    continue
                booking_duration = booking.get('duration_minutes') or default_duration
                booking_end = _compute_booking_end(appt_time, booking_duration)
                if (day_start <= appt_time < day_end) or (appt_time < day_start and booking_end > day_start):
                    result.append({
                        'start': max(appt_time, day_start),
                        'end': min(booking_end, day_end),
                        'duration': booking_duration,
                        'booking': booking
                    })
            return result

        # Helper: check if a single slot conflicts with a list of day_bookings
        def _slot_has_conflict(slot_time, slot_end, bookings_list):
            for bd in bookings_list:
                if slot_time < bd['end'] and slot_end > bd['start']:
                    return bd
            return None

        # Build per-employee booking lists for "any employee" mode
        if any_employee:
            all_employees = db.get_all_employees(company_id=company_id)
            # Apply service employee_restrictions if applicable
            eligible_employee_ids = [w['id'] for w in all_employees]
            if service_type:
                from src.services.settings_manager import get_settings_manager as _gsm
                _svc = _gsm().get_service_by_name(service_type, company_id=company_id)
                if _svc and _svc.get('employee_restrictions'):
                    wr = _svc['employee_restrictions']
                    if wr.get('type') == 'only' and wr.get('employee_ids'):
                        eligible_employee_ids = [wid for wid in eligible_employee_ids if wid in wr['employee_ids']]
                    elif wr.get('type') == 'except' and wr.get('employee_ids'):
                        eligible_employee_ids = [wid for wid in eligible_employee_ids if wid not in wr['employee_ids']]
            per_employee_bookings = {wid: _get_day_bookings(filter_employee_id=wid) for wid in eligible_employee_ids}
            # Load work schedules for eligible employees
            employee_work_schedules = {}
            for emp in all_employees:
                if emp['id'] in eligible_employee_ids and emp.get('work_schedule'):
                    employee_work_schedules[emp['id']] = emp['work_schedule']
        else:
            day_bookings = _get_day_bookings(filter_employee_id=employee_id)
            # Load work schedule for the specific employee
            employee_work_schedules = {}
            if employee_id:
                emp = db.get_employee(employee_id, company_id=company_id)
                if emp and emp.get('work_schedule'):
                    employee_work_schedules[employee_id] = emp['work_schedule']

        # Helper: check if a slot time is within an employee's work schedule
        day_abbrevs = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        target_day_key = day_abbrevs[target_date.weekday()]

        def _is_within_work_schedule(emp_id, slot_time, slot_end_time):
            ws = employee_work_schedules.get(emp_id)
            if not ws:
                return True  # No schedule set = available during business hours
            day_sched = ws.get(target_day_key)
            if not day_sched:
                return True  # Day not in schedule = use business hours
            if not day_sched.get('enabled', True):
                return False  # Employee doesn't work this day
            sched_start = day_sched.get('start')
            sched_end = day_sched.get('end')
            if not sched_start or not sched_end:
                return True
            sp = sched_start.split(':')
            ep = sched_end.split(':')
            sched_start_mins = int(sp[0]) * 60 + (int(sp[1]) if len(sp) > 1 else 0)
            sched_end_mins = int(ep[0]) * 60 + (int(ep[1]) if len(ep) > 1 else 0)
            slot_mins = slot_time.hour * 60 + slot_time.minute
            slot_end_mins = slot_end_time.hour * 60 + slot_end_time.minute
            return slot_mins >= sched_start_mins and slot_end_mins <= sched_end_mins

        # Check employee time-off / leave for this day
        employees_on_leave_today = set()
        try:
            if hasattr(db, 'get_employees_on_leave'):
                from datetime import date as date_cls
                leave_records = db.get_employees_on_leave(company_id, day_start, day_end)
                for rec in leave_records:
                    s = rec['start_date']
                    e = rec['end_date']
                    if isinstance(s, str):
                        s = date_cls.fromisoformat(s)
                    if isinstance(e, str):
                        e = date_cls.fromisoformat(e)
                    if s <= target_date <= e:
                        employees_on_leave_today.add(rec['employee_id'])
        except Exception:
            pass

        # If a specific employee is on leave, all slots are unavailable
        employee_on_leave = employee_id and employee_id in employees_on_leave_today

        # For "any employee" mode, remove employees on leave from the pool
        had_eligible_employees = any_employee and bool(per_employee_bookings)
        if any_employee and per_employee_bookings and employees_on_leave_today:
            per_employee_bookings = {wid: bk for wid, bk in per_employee_bookings.items() if wid not in employees_on_leave_today}

        # For "today", compute the current time so we can mark past slots
        now = datetime.now()
        is_today = (target_date == now.date())

        current_hour = business_hours['start']
        current_minute = 0
        end_hour = business_hours['end']

        # If any_employee mode but no employees exist at all (not just on leave),
        # fall back to general (non-employee) availability so the daily view
        # matches the monthly calendar which also falls back.
        # But if eligible employees existed and are ALL on leave, keep slots unavailable.
        all_employees_on_leave = any_employee and not per_employee_bookings and had_eligible_employees
        no_employees_exist = any_employee and not per_employee_bookings and not had_eligible_employees
        if no_employees_exist:
            day_bookings = _get_day_bookings(filter_employee_id=None)
        
        while current_hour < end_hour or (current_hour == end_hour and current_minute == 0):
            slot_time = datetime.combine(target_date, datetime.min.time().replace(hour=current_hour, minute=current_minute))
            
            # Calculate slot end time (no buffer)
            slot_end = slot_time + timedelta(minutes=slot_duration)
            
            # Don't show slots that would extend past business hours
            business_end = datetime.combine(target_date, datetime.min.time().replace(hour=end_hour))
            if slot_end > business_end:
                current_minute += 30
                if current_minute >= 60:
                    current_minute = 0
                    current_hour += 1
                continue
            
            # Check for conflicts
            is_available = True
            booking_info = None

            # Mark past slots for today as unavailable
            if is_today and slot_time <= now:
                is_available = False
                booking_info = {'past': True, 'reason': 'Time has passed'}
            # If the specific employee is on leave, mark all slots unavailable
            elif employee_on_leave:
                is_available = False
                booking_info = {'leave': True, 'reason': 'Employee is on leave this day'}
            # If a specific employee is selected, check their work schedule
            elif employee_id and not any_employee and not _is_within_work_schedule(employee_id, slot_time, slot_end):
                is_available = False
                ws = employee_work_schedules.get(employee_id, {}).get(target_day_key, {})
                booking_info = {'outside_schedule': True, 'reason': f"Outside shift ({ws.get('start', '?')} - {ws.get('end', '?')})"}
            elif any_employee and per_employee_bookings:
                # Slot is available if at least one eligible employee is free AND within their shift
                any_free = False
                first_conflict = None
                for wid, wb_list in per_employee_bookings.items():
                    # Skip employees not working at this time
                    if not _is_within_work_schedule(wid, slot_time, slot_end):
                        continue
                    conflict = _slot_has_conflict(slot_time, slot_end, wb_list)
                    if not conflict:
                        any_free = True
                        break
                    elif not first_conflict:
                        first_conflict = conflict
                is_available = any_free
                if not is_available and first_conflict:
                    conflict_booking = first_conflict['booking']
                    client = db.get_client(conflict_booking['client_id'], company_id=company_id)
                    booking_info = {
                        'client_name': client['name'] if client else 'Unknown',
                        'service_type': conflict_booking['service_type'],
                        'time': str(conflict_booking['appointment_time']),
                        'duration_minutes': first_conflict['duration']
                    }
            elif all_employees_on_leave:
                # All employees are on leave — no availability
                is_available = False
                booking_info = {'leave': True, 'reason': 'All employees on leave'}
            elif no_employees_exist:
                # No employees exist — fall back to general conflict check
                for booking_data in day_bookings:
                    if slot_time < booking_data['end'] and slot_end > booking_data['start']:
                        is_available = False
                        conflict = booking_data['booking']
                        client = db.get_client(conflict['client_id'], company_id=company_id)
                        booking_info = {
                            'client_name': client['name'] if client else 'Unknown',
                            'service_type': conflict['service_type'],
                            'time': str(conflict['appointment_time']),
                            'duration_minutes': booking_data['duration']
                        }
                        break
            else:
                for booking_data in day_bookings:
                    if slot_time < booking_data['end'] and slot_end > booking_data['start']:
                        is_available = False
                        conflict = booking_data['booking']
                        client = db.get_client(conflict['client_id'], company_id=company_id)
                        booking_info = {
                            'client_name': client['name'] if client else 'Unknown',
                            'service_type': conflict['service_type'],
                            'time': str(conflict['appointment_time']),
                            'duration_minutes': booking_data['duration']
                        }
                        break
            
            slots.append({
                'time': slot_time.strftime('%H:%M'),
                'datetime': slot_time.isoformat(),
                'available': is_available,
                'booking': booking_info,
                'slot_duration': slot_duration
            })
            
            # Move to next slot (30 minute intervals)
            current_minute += 30
            if current_minute >= 60:
                current_minute = 0
                current_hour += 1
        
        return jsonify({
            'date': date_str,
            'slots': slots,
            'business_hours': business_hours
        })
        
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    except Exception as e:
        print(f"[ERROR] Error checking availability: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/bookings/availability/month", methods=["GET"])
@login_required
def check_monthly_availability_api():
    """Return day-level availability for an entire month (for mini-calendar colouring)."""
    db = get_database()
    company_id = session.get('company_id')

    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    service_type = request.args.get('service_type')
    employee_id = request.args.get('employee_id', type=int)
    any_employee = request.args.get('any_employee', 'false').lower() == 'true'
    override_duration = request.args.get('duration_minutes', type=int)

    if not year or not month:
        return jsonify({"error": "year and month parameters required"}), 400

    try:
        from datetime import datetime, timedelta, date as date_cls
        import calendar as cal_mod
        from src.services.settings_manager import get_settings_manager

        safe_print(f"[MONTHLY_AVAIL] year={year}, month={month}, service_type={service_type}, employee_id={employee_id}, any_employee={any_employee}, override_duration={override_duration}")

        settings_mgr = get_settings_manager()
        default_duration = settings_mgr.get_default_duration_minutes(company_id=company_id)

        slot_duration = default_duration
        if override_duration and override_duration > 0:
            slot_duration = override_duration
        elif service_type:
            service = settings_mgr.get_service_by_name(service_type, company_id=company_id)
            if service and service.get('duration_minutes'):
                slot_duration = service['duration_minutes']

        # Business hours
        bh_start, bh_end, open_days_set = 9, 17, None
        try:
            company = db.get_company(company_id)
            if company and company.get('business_hours'):
                import re
                hours_str = company['business_hours']
                time_match = re.match(r'(\d+)\s*(AM|PM)\s*-\s*(\d+)\s*(AM|PM)', hours_str, re.IGNORECASE)
                if time_match:
                    sh = int(time_match.group(1))
                    sp = time_match.group(2).upper()
                    eh = int(time_match.group(3))
                    ep = time_match.group(4).upper()
                    if sp == 'PM' and sh != 12: sh += 12
                    elif sp == 'AM' and sh == 12: sh = 0
                    if ep == 'PM' and eh != 12: eh += 12
                    elif ep == 'AM' and eh == 12: eh = 0
                    bh_start, bh_end = sh, eh

                hours_lower = hours_str.lower()
                if 'daily' in hours_lower or 'mon-sun' in hours_lower:
                    open_days_set = {0,1,2,3,4,5,6}
                elif 'mon-sat' in hours_lower:
                    open_days_set = {0,1,2,3,4,5}
                elif 'mon-fri' in hours_lower:
                    open_days_set = {0,1,2,3,4}
        except Exception:
            pass

        # Total available slots per open day
        total_minutes = (bh_end - bh_start) * 60
        if slot_duration >= 1440:
            slots_per_day = 1  # full-day: 1 slot
        else:
            slots_per_day = max(1, total_minutes // 30)  # 30-min interval slots
        
        safe_print(f"[MONTHLY_AVAIL] slot_duration={slot_duration}, bh_start={bh_start}, bh_end={bh_end}, total_minutes={total_minutes}, slots_per_day={slots_per_day}")

        # Gather all bookings for the month window (with buffer for multi-day)
        month_start = datetime(year, month, 1)
        _, last_day = cal_mod.monthrange(year, month)
        month_end = datetime(year, month, last_day, 23, 59, 59)
        buffer_start = month_start - timedelta(days=45)

        all_bookings = db.get_all_bookings(company_id=company_id)

        # Helper: compute booking end for overlap calculation
        def _booking_end(appt, dur):
            if dur > 1440:
                from src.utils.duration_utils import duration_to_business_days
                biz_days = duration_to_business_days(dur, company_id=company_id)
                try:
                    from src.utils.config import config as _cfg
                    biz_indices = _cfg.get_business_days_indices(company_id=company_id)
                except Exception:
                    biz_indices = [0,1,2,3,4]
                cur = appt.replace(hour=0, minute=0, second=0, microsecond=0)
                counted = 0
                last_biz = cur
                for _ in range(365):
                    if cur.weekday() in biz_indices:
                        counted += 1
                        last_biz = cur
                        if counted >= biz_days:
                            break
                    cur += timedelta(days=1)
                return last_biz.replace(hour=bh_end, minute=0)
            elif dur >= 480:
                return appt.replace(hour=bh_end, minute=0)
            else:
                return appt + timedelta(minutes=dur)

        # Helper: filter bookings for a specific employee
        def _filter_bookings(filter_employee_id=None):
            result = []
            for b in all_bookings:
                if b.get('status') in ['cancelled', 'completed']:
                    continue
                if filter_employee_id:
                    assigned_ids = b.get('assigned_employee_ids') or []
                    # Unassigned bookings block all employees (could be assigned to anyone)
                    if len(assigned_ids) > 0 and filter_employee_id not in assigned_ids and str(filter_employee_id) not in [str(x) for x in assigned_ids]:
                        continue
                appt = b.get('appointment_time')
                if isinstance(appt, str):
                    try:
                        appt = datetime.fromisoformat(appt.replace('Z', '+00:00').replace('+00:00', ''))
                    except Exception:
                        continue
                if not appt:
                    continue
                dur = b.get('duration_minutes') or default_duration
                result.append({'start': appt, 'duration': dur, 'booking': b})
            return result

        # Helper: count booked slots for a day given a list of bookings
        def _count_booked_slots(day_date, bookings_list):
            day_start = datetime.combine(day_date, datetime.min.time())
            day_end_dt = day_start + timedelta(days=1)
            bh_end_dt = day_start.replace(hour=bh_end, minute=0, second=0)
            booked = 0

            # For today, count past time slots as "booked" so the calendar
            # accurately reflects only the remaining available slots.
            now = datetime.now()
            is_today_day = (day_date == now.date())
            past_slots_count = 0
            if is_today_day and slot_duration < 1440:
                bh_start_dt = day_start.replace(hour=bh_start, minute=0, second=0)
                past_end = min(now, bh_end_dt)
                if past_end >= bh_start_dt:
                    past_mins = (past_end - bh_start_dt).total_seconds() / 60
                    # +1 because the slot AT bh_start is also past (daily uses <=)
                    past_slots_count = min(int(past_mins // 30) + 1, slots_per_day)
                    booked += past_slots_count

            for rb in bookings_list:
                appt = rb['start']
                dur = rb['duration']
                b_end = _booking_end(appt, dur)
                if appt < day_end_dt and b_end > day_start:
                    overlap_start = max(appt, day_start)
                    overlap_end = min(b_end, bh_end_dt)
                    # For today, only count the future portion of bookings
                    # to avoid double-counting with past slots
                    if is_today_day and past_slots_count > 0:
                        overlap_start = max(overlap_start, now)
                    if overlap_end > overlap_start:
                        overlap_mins = (overlap_end - overlap_start).total_seconds() / 60
                        if slot_duration >= 1440:
                            booked += 1
                        else:
                            booked += max(1, int(overlap_mins // 30))
            return min(booked, slots_per_day)

        # Prepare per-employee or single booking lists
        if any_employee:
            all_employees = db.get_all_employees(company_id=company_id)
            eligible_employee_ids = [w['id'] for w in all_employees]
            safe_print(f"[MONTHLY_AVAIL] any_employee mode: {len(all_employees)} total employees, {len(eligible_employee_ids)} eligible")
            if service_type:
                from src.services.settings_manager import get_settings_manager as _gsm2
                _svc = _gsm2().get_service_by_name(service_type, company_id=company_id)
                if _svc and _svc.get('employee_restrictions'):
                    wr = _svc['employee_restrictions']
                    if wr.get('type') == 'only' and wr.get('employee_ids'):
                        eligible_employee_ids = [wid for wid in eligible_employee_ids if wid in wr['employee_ids']]
                    elif wr.get('type') == 'except' and wr.get('employee_ids'):
                        eligible_employee_ids = [wid for wid in eligible_employee_ids if wid not in wr['employee_ids']]
            per_employee_bookings = {wid: _filter_bookings(filter_employee_id=wid) for wid in eligible_employee_ids}
        else:
            relevant = _filter_bookings(filter_employee_id=employee_id)

        # Pre-fetch approved time-off for the month
        leave_by_employee = {}  # employee_id -> set of date strings on leave
        try:
            if hasattr(db, 'get_employees_on_leave'):
                leave_records = db.get_employees_on_leave(company_id, month_start, month_end)
                for rec in leave_records:
                    wid = rec['employee_id']
                    if wid not in leave_by_employee:
                        leave_by_employee[wid] = set()
                    s = rec['start_date']
                    e = rec['end_date']
                    if isinstance(s, str):
                        s = date_cls.fromisoformat(s)
                    if isinstance(e, str):
                        e = date_cls.fromisoformat(e)
                    cur = s
                    while cur <= e:
                        if date_cls(year, month, 1) <= cur <= date_cls(year, month, last_day):
                            leave_by_employee[wid].add(cur.isoformat())
                        cur += timedelta(days=1)
        except Exception:
            pass

        # Helper: check if a specific employee is on leave for a date
        def _employee_on_leave(wid, day_iso):
            return day_iso in leave_by_employee.get(wid, set())

        # Helper: check if ALL eligible employees are on leave for a date
        def _all_employees_on_leave(day_iso, employee_ids):
            if not leave_by_employee:
                return False
            return all(day_iso in leave_by_employee.get(wid, set()) for wid in employee_ids)

        # Build per-day info
        days = {}
        for day_num in range(1, last_day + 1):
            d = date_cls(year, month, day_num)
            day_name = d.strftime('%A').lower()
            weekday = d.weekday()

            is_open = True
            if open_days_set is not None:
                is_open = weekday in open_days_set

            if not is_open:
                days[d.isoformat()] = {'date': d.isoformat(), 'status': 'closed', 'booked': 0, 'total': 0}
                continue

            if any_employee and per_employee_bookings:
                # For "any employee" mode, check per-employee availability individually.
                # Employees on leave are excluded for this day.
                num_employees = len(per_employee_bookings)
                employees_fully_free = 0
                employees_with_space = 0
                employees_available = 0  # not on leave
                total_booked = 0
                day_iso = d.isoformat()
                for wid, wb_list in per_employee_bookings.items():
                    if _employee_on_leave(wid, day_iso):
                        continue  # Skip employees on leave
                    employees_available += 1
                    wb = _count_booked_slots(d, wb_list)
                    total_booked += min(wb, slots_per_day)
                    if wb == 0:
                        employees_fully_free += 1
                    if wb < slots_per_day:
                        employees_with_space += 1

                if employees_available == 0:
                    # All employees on leave
                    status = 'leave'
                    booked_slots = 0
                    day_total = 0
                    free = 0
                elif employees_with_space == 0:
                    status = 'full'
                    booked_slots = total_booked
                    day_total = employees_available * slots_per_day
                    free = day_total - booked_slots
                elif employees_fully_free > 0:
                    status = 'free'
                    booked_slots = total_booked
                    day_total = employees_available * slots_per_day
                    free = day_total - booked_slots
                else:
                    status = 'partial'
                    booked_slots = total_booked
                    day_total = employees_available * slots_per_day
                    free = day_total - booked_slots
            elif any_employee and not per_employee_bookings:
                # No employees — show general availability
                booked_slots = _count_booked_slots(d, _filter_bookings())
                day_total = slots_per_day
                free = day_total - booked_slots
                if free <= 0:
                    status = 'full'
                elif free < day_total:
                    status = 'partial'
                else:
                    status = 'free'
            else:
                day_iso = d.isoformat()
                if employee_id and _employee_on_leave(employee_id, day_iso):
                    status = 'leave'
                    booked_slots = 0
                    day_total = 0
                    free = 0
                else:
                    booked_slots = _count_booked_slots(d, relevant)
                    day_total = slots_per_day
                    free = day_total - booked_slots
                    if free <= 0:
                        status = 'full'
                    elif free < day_total:
                        status = 'partial'
                    else:
                        status = 'free'

            days[d.isoformat()] = {
                'date': d.isoformat(),
                'status': status,
                'booked': booked_slots,
                'total': day_total,
                'free': free
            }

        # Sample first few days for debug
        sample_days = {k: v for i, (k, v) in enumerate(days.items()) if i < 3}
        safe_print(f"[MONTHLY_AVAIL] Returning {len(days)} days. Sample: {sample_days}")
        
        return jsonify({'year': year, 'month': month, 'days': days, 'business_hours': {'start': bh_start, 'end': bh_end}})

    except Exception as e:
        print(f"[ERROR] Monthly availability: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/bookings/<int:booking_id>", methods=["GET", "PUT", "DELETE"])
@login_required
@subscription_required
def booking_detail_api(booking_id):
    """Get, update or delete a specific booking"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        # Get booking details using database method with company_id filter for security
        booking = db.get_booking(booking_id, company_id=company_id)
        
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
        # Get notes for this booking
        appointment_notes = db.get_appointment_notes(booking_id)
        notes_text = appointment_notes[0]['note'] if appointment_notes else ''
        
        # Get client details if client_id exists
        if booking.get('client_id'):
            client = db.get_client(booking['client_id'], company_id=company_id)
            if client:
                booking['client_name'] = client.get('name')
                booking['customer_name'] = client.get('name')
                booking['client_phone'] = client.get('phone')
                booking['client_email'] = client.get('email')
        
        response_booking = {
            'id': booking.get('id'),
            'client_id': booking.get('client_id'),
            'calendar_event_id': booking.get('calendar_event_id'),
            'appointment_time': booking.get('appointment_time'),
            'service_type': booking.get('service_type'),
            'service': booking.get('service_type'),
            'status': booking.get('status'),
            'phone_number': booking.get('phone_number'),
            'phone': booking.get('phone_number') or booking.get('client_phone'),
            'email': (booking.get('email') or '').strip() or (booking.get('client_email') or '').strip() or None,
            'created_at': booking.get('created_at'),
            'charge': booking.get('charge'),
            'estimated_charge': booking.get('charge'),
            'estimated_charge_max': booking.get('charge_max'),
            'payment_status': booking.get('payment_status'),
            'payment_method': booking.get('payment_method'),
            'urgency': booking.get('urgency'),
            'address': booking.get('address'),
            'job_address': booking.get('address'),
            'eircode': booking.get('eircode'),
            'property_type': booking.get('property_type'),
            'customer_name': booking.get('customer_name') or booking.get('client_name'),
            'client_name': booking.get('client_name') or booking.get('customer_name'),
            'notes': notes_text,
            'address_audio_url': booking.get('address_audio_url'),
            'photo_urls': booking.get('photo_urls') or [],
            'customer_photo_urls': booking.get('customer_photo_urls') or [],
            'job_started_at': booking.get('job_started_at'),
            'job_completed_at': booking.get('job_completed_at'),
            'actual_duration_minutes': booking.get('actual_duration_minutes'),
            'duration_minutes': booking.get('duration_minutes'),
            'recurrence_pattern': booking.get('recurrence_pattern'),
            'recurrence_end_date': booking.get('recurrence_end_date'),
            'status_label': booking.get('status_label'),
            'stripe_checkout_session_id': booking.get('stripe_checkout_session_id'),
            'table_number': booking.get('table_number'),
            'party_size': booking.get('party_size'),
            'dining_area': booking.get('dining_area'),
            'special_requests': booking.get('special_requests'),
            'course_status': booking.get('course_status'),
        }
        
        return jsonify(response_booking)
    
    elif request.method == "PUT":
        # Verify booking belongs to this company before updating
        booking = db.get_booking(booking_id, company_id=company_id)
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
        # Update booking
        data = request.json
        
        # Handle notes separately (stored in appointment_notes table)
        notes = data.pop('notes', None)
        
        # Handle job_address mapping - frontend sends 'job_address', DB expects 'address'
        if 'job_address' in data:
            data['address'] = data.pop('job_address')
        
        # Sanitize fields - convert empty strings to None for optional fields
        sanitized_data = {}
        for key, value in data.items():
            if key in ['charge', 'estimated_charge', 'estimated_charge_max']:
                # Sanitize charge values — handle both string and numeric inputs
                db_key = 'charge_max' if key == 'estimated_charge_max' else key
                if value is not None and value != '':
                    try:
                        float_val = float(value)
                        sanitized_data[db_key] = float_val if float_val >= 0 else None
                    except (ValueError, TypeError):
                        sanitized_data[db_key] = None
                else:
                    sanitized_data[db_key] = None
            elif key == 'party_size':
                if value is not None and value != '':
                    try:
                        sanitized_data[key] = int(value)
                    except (ValueError, TypeError):
                        sanitized_data[key] = None
                else:
                    sanitized_data[key] = None
            elif isinstance(value, str):
                value = value.strip()
                # For optional text fields, convert empty to None
                if key in ['address', 'eircode', 'property_type', 'phone_number', 'email', 'phone', 'status_label', 'table_number', 'dining_area', 'special_requests', 'course_status']:
                    sanitized_data[key] = value if value else None
                else:
                    sanitized_data[key] = value
            else:
                sanitized_data[key] = value
        
        # --- CONFLICT DETECTION when time or duration changes ---
        time_changed = False
        duration_changed = False
        old_appointment_time = booking.get('appointment_time')
        old_duration = booking.get('duration_minutes') or 60
        
        new_appointment_time_str = sanitized_data.get('appointment_time')
        new_duration = sanitized_data.get('duration_minutes')
        if new_duration is not None:
            try:
                new_duration = int(new_duration)
            except (ValueError, TypeError):
                new_duration = None
        
        # Determine if time or duration actually changed
        if new_appointment_time_str:
            from datetime import datetime, timedelta
            try:
                new_appt_dt = datetime.fromisoformat(new_appointment_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, TypeError):
                new_appt_dt = None
            if new_appt_dt:
                old_appt_dt = old_appointment_time
                if isinstance(old_appt_dt, str):
                    old_appt_dt = datetime.fromisoformat(old_appt_dt.replace('Z', '+00:00')).replace(tzinfo=None)
                elif hasattr(old_appt_dt, 'replace'):
                    old_appt_dt = old_appt_dt.replace(tzinfo=None)
                if old_appt_dt and abs((new_appt_dt - old_appt_dt).total_seconds()) > 60:
                    time_changed = True
        else:
            from datetime import datetime, timedelta
            new_appt_dt = old_appointment_time
            if isinstance(new_appt_dt, str):
                new_appt_dt = datetime.fromisoformat(new_appt_dt.replace('Z', '+00:00')).replace(tzinfo=None)
            elif hasattr(new_appt_dt, 'replace'):
                new_appt_dt = new_appt_dt.replace(tzinfo=None)
        
        if new_duration is not None and new_duration != old_duration:
            duration_changed = True
        
        effective_duration = new_duration if new_duration else old_duration
        conflicts = []
        
        if (time_changed or duration_changed) and new_appt_dt:
            # Calculate the new job's end time
            if effective_duration > 1440:
                from src.utils.duration_utils import duration_to_business_days
                _biz_days = duration_to_business_days(effective_duration, company_id=company_id)
                try:
                    from src.utils.config import config as _cfg
                    _biz_indices = _cfg.get_business_days_indices(company_id=company_id)
                    _bh = _cfg.get_business_hours(company_id=company_id)
                    _bh_end = _bh.get('end', 17)
                except Exception:
                    _biz_indices = [0, 1, 2, 3, 4]
                    _bh_end = 17
                _cur = new_appt_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                _counted = 0
                while _counted < _biz_days:
                    if _cur.weekday() in _biz_indices:
                        _counted += 1
                        if _counted >= _biz_days:
                            break
                    _cur += timedelta(days=1)
                new_job_end = _cur.replace(hour=_bh_end, minute=0, second=0, microsecond=0)
            elif effective_duration >= 480:
                try:
                    from src.utils.config import config as _cfg
                    _bh = _cfg.get_business_hours(company_id=company_id)
                    _bh_end = _bh.get('end', 17)
                except Exception:
                    _bh_end = 17
                new_job_end = new_appt_dt.replace(hour=_bh_end, minute=0, second=0, microsecond=0)
            else:
                new_job_end = new_appt_dt + timedelta(minutes=effective_duration)
            
            # Check employee conflicts
            assigned_employees = db.get_job_employees(booking_id, company_id=company_id)
            for emp in assigned_employees:
                emp_bookings = db.get_employee_bookings_in_range(
                    emp['id'], new_appt_dt, new_job_end,
                    exclude_booking_id=booking_id, company_id=company_id
                )
                for eb in emp_bookings:
                    eb_start = eb['appointment_time']
                    eb_dur = eb.get('duration_minutes') or 60
                    eb_end = db._calculate_job_end_time(eb_start, eb_dur, company_id=company_id)
                    # Check overlap
                    if eb_start < new_job_end and eb_end > new_appt_dt:
                        conflicts.append({
                            'employee_name': emp.get('name', 'Employee'),
                            'conflicting_booking_id': eb['id'],
                            'conflict_start': eb_start.isoformat() if hasattr(eb_start, 'isoformat') else str(eb_start),
                        })
            
            # Also check general company conflicts (for unassigned jobs)
            if not assigned_employees:
                general_conflicts = db.get_conflicting_bookings(
                    new_appt_dt.isoformat(), new_job_end.isoformat(),
                    company_id=company_id
                )
                # Exclude the current booking from conflicts
                general_conflicts = [c for c in general_conflicts if c['id'] != booking_id]
                for gc in general_conflicts:
                    conflicts.append({
                        'employee_name': None,
                        'conflicting_booking_id': gc['id'],
                        'service_type': gc.get('service_type', ''),
                    })
        
        # If force_save is not set and there are conflicts, return warning (don't save yet)
        force_save = data.get('force_save', False) or request.args.get('force', 'false') == 'true'
        # Remove force_save from sanitized_data so it doesn't get passed to DB
        sanitized_data.pop('force_save', None)
        if conflicts and not force_save:
            return jsonify({
                "warning": "Schedule conflict detected",
                "conflicts": conflicts,
                "message": f"{len(conflicts)} conflict(s) found. Save anyway?"
            }), 409
        
        success = db.update_booking(booking_id, company_id=company_id, **sanitized_data)
        
        # Auto-move linked quotes to 'won' when payment is marked as paid
        if success and sanitized_data.get('payment_status') == 'paid':
            try:
                conn_q = db.get_connection()
                cur_q = conn_q.cursor()
                cur_q.execute("""
                    UPDATE quotes SET pipeline_stage = 'won', status = 'converted',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = %s 
                        AND (source_booking_id = %s OR converted_booking_id = %s)
                        AND status NOT IN ('converted', 'declined')
                        AND (pipeline_stage IS NULL OR pipeline_stage NOT IN ('won', 'lost'))
                """, (company_id, booking_id, booking_id))
                updated_q = cur_q.rowcount
                conn_q.commit()
                cur_q.close()
                db.return_connection(conn_q)
                if updated_q > 0:
                    print(f"[MARK-PAID] Auto-moved {updated_q} linked quote(s) to 'won' for booking {booking_id}")
            except Exception as e:
                print(f"[WARNING] Could not auto-win quotes for booking {booking_id}: {e}")

        # Auto-create next occurrence for recurring jobs when completed
        if success and sanitized_data.get('status') == 'completed':
            try:
                updated = db.get_booking(booking_id, company_id=company_id)
                rec_pattern = updated.get('recurrence_pattern') if updated else None
                if rec_pattern and rec_pattern in ('weekly', 'biweekly', 'monthly', 'quarterly'):
                    from datetime import datetime, timedelta
                    appt = updated.get('appointment_time')
                    if isinstance(appt, str):
                        appt = datetime.fromisoformat(appt.replace('Z', '+00:00')).replace(tzinfo=None)
                    elif hasattr(appt, 'replace'):
                        appt = appt.replace(tzinfo=None)
                    if rec_pattern == 'weekly': next_dt = appt + timedelta(weeks=1)
                    elif rec_pattern == 'biweekly': next_dt = appt + timedelta(weeks=2)
                    elif rec_pattern == 'monthly':
                        m, y = appt.month + 1, appt.year
                        if m > 12: m, y = 1, y + 1
                        import calendar
                        next_dt = appt.replace(year=y, month=m, day=min(appt.day, calendar.monthrange(y, m)[1]))
                    elif rec_pattern == 'quarterly':
                        m, y = appt.month + 3, appt.year
                        while m > 12: m, y = m - 12, y + 1
                        import calendar
                        next_dt = appt.replace(year=y, month=m, day=min(appt.day, calendar.monthrange(y, m)[1]))
                    end_d = updated.get('recurrence_end_date')
                    skip = False
                    if end_d:
                        if isinstance(end_d, str): end_d = datetime.fromisoformat(end_d).replace(tzinfo=None)
                        if next_dt.date() > (end_d.date() if hasattr(end_d, 'date') else end_d): skip = True
                    if not skip:
                        conn2 = db.get_connection()
                        try:
                            from psycopg2.extras import RealDictCursor
                            cur2 = conn2.cursor(cursor_factory=RealDictCursor)
                            cur2.execute("""
                                INSERT INTO bookings (company_id, client_id, appointment_time, service_type,
                                    charge, charge_max, status, payment_status, address, eircode, property_type,
                                    duration_minutes, requires_callout, requires_quote,
                                    recurrence_pattern, recurrence_end_date, parent_booking_id,
                                    created_at, updated_at)
                                VALUES (%s,%s,%s,%s,%s,%s,'scheduled','unpaid',%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                                RETURNING id
                            """, (company_id, updated.get('client_id'), next_dt.isoformat(),
                                  updated.get('service_type'), updated.get('charge'), updated.get('charge_max'),
                                  updated.get('address'), updated.get('eircode'), updated.get('property_type'),
                                  updated.get('duration_minutes'), updated.get('requires_callout'), updated.get('requires_quote'),
                                  rec_pattern, updated.get('recurrence_end_date'), booking_id))
                            new_b = cur2.fetchone()
                            cur2.execute("INSERT INTO employee_assignments (booking_id, employee_id) SELECT %s, employee_id FROM employee_assignments WHERE booking_id = %s", (new_b['id'], booking_id))
                            conn2.commit(); cur2.close()
                        except Exception as e:
                            conn2.rollback(); print(f"[RECURRING] Main update recurring failed: {e}")
                        finally:
                            db.return_connection(conn2)
            except Exception as e:
                print(f"[RECURRING] Error in main update: {e}")

        # Send review email when job is marked as completed
        if success and sanitized_data.get('status') == 'completed':
            try:
                safe_print(f"[REVIEW] Job {booking_id} marked completed, checking review email...")
                company = db.get_company(company_id)
                send_reviews_enabled = company.get('send_review_emails', True) if company else True
                if send_reviews_enabled:
                    updated_b = db.get_booking(booking_id, company_id=company_id)
                    client_id_r = updated_b.get('client_id') if updated_b else None
                    client_r = db.get_client(client_id_r, company_id=company_id) if client_id_r else None
                    customer_email_r = (updated_b or {}).get('email') or (client_r.get('email') if client_r else None)
                    if customer_email_r:
                        existing_review = db.get_booking_review(booking_id, company_id=company_id)
                        if not existing_review:
                            import secrets
                            review_token = secrets.token_urlsafe(32)
                            customer_name_r = (client_r.get('name') if client_r else None) or 'Customer'
                            service_type_r = (updated_b or {}).get('service_type', 'Service')
                            review_record = db.create_job_review(
                                booking_id=booking_id, company_id=company_id,
                                client_id=client_id_r, review_token=review_token,
                                customer_name=customer_name_r, service_type=service_type_r
                            )
                            if review_record:
                                public_url = os.getenv('PUBLIC_URL', os.getenv('FRONTEND_URL', 'https://bookedforyou.ie'))
                                review_url = f"{public_url}/review/{review_token}"
                                from src.services.email_reminder import get_email_service
                                email_svc = get_email_service()
                                email_svc.company_reply_to = (company.get('email') or '').strip() if company else None
                                sent = email_svc.send_satisfaction_survey(
                                    to_email=customer_email_r, customer_name=customer_name_r,
                                    service_type=service_type_r, review_url=review_url,
                                    company_name=company.get('company_name', '') if company else '',
                                    appointment_time=(updated_b or {}).get('appointment_time')
                                )
                                if sent:
                                    db.mark_review_email_sent(review_record['id'])
                                    safe_print(f"[REVIEW] Review email sent to {customer_email_r} for booking {booking_id}")
                                else:
                                    safe_print(f"[REVIEW] Email service returned False for {customer_email_r}")
                            else:
                                safe_print(f"[REVIEW] Failed to create review record for booking {booking_id}")
                        else:
                            safe_print(f"[REVIEW] Review already exists for booking {booking_id}, skipping")
                    else:
                        safe_print(f"[REVIEW] No email on file for booking {booking_id}, skipping review")
                else:
                    safe_print(f"[REVIEW] Review emails disabled for company {company_id}")
            except Exception as e:
                safe_print(f"[REVIEW] Review email failed (non-critical): {e}")
                import traceback; traceback.print_exc()

        # Update notes if provided
        if notes is not None:
            # Clear existing notes and add the new note
            db.delete_appointment_notes_by_booking(booking_id)
            
            notes_text = notes.strip() if isinstance(notes, str) else ''
            if notes_text:
                db.add_appointment_note(booking_id, notes_text, created_by="user")
            success = True
        
        if success:
            # Sync changes to Google Calendar if connected
            try:
                from src.services.google_calendar_oauth import get_company_google_calendar
                gcal = get_company_google_calendar(company_id, db)
                updated_booking = db.get_booking(booking_id, company_id=company_id)
                if gcal and updated_booking:
                    event_id = updated_booking.get('calendar_event_id', '')
                    if event_id and not str(event_id).startswith('db_'):
                        appt_time = updated_booking.get('appointment_time')
                        if isinstance(appt_time, str):
                            from datetime import datetime as _dt
                            appt_time = _dt.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                        elif hasattr(appt_time, 'replace'):
                            appt_time = appt_time.replace(tzinfo=None)
                        # get_booking doesn't JOIN clients, so look up the name
                        client = db.get_client(updated_booking.get('client_id'), company_id=company_id)
                        customer_name = (client.get('name') if client else None) or 'Customer'
                        service = updated_booking.get('service_type') or 'Job'
                        duration = updated_booking.get('duration_minutes', 60)
                        phone = updated_booking.get('phone_number') or (client.get('phone') if client else '') or ''
                        address = updated_booking.get('address') or ''
                        is_completed = updated_booking.get('status') == 'completed'
                        summary = f"{'✅ ' if is_completed else ''}{service} - {customer_name}"
                        desc = (
                            f"Synced from BookedForYou\n"
                            f"{'Status: COMPLETED\n' if is_completed else ''}"
                            f"Customer: {customer_name}\n"
                            f"Phone: {phone}\n"
                            f"Address: {address}\n"
                            f"Duration: {duration} mins"
                        )
                        gcal.reschedule_appointment(
                            event_id, appt_time, duration_minutes=duration,
                            description=desc, summary=summary
                        )
            except Exception as e:
                safe_print(f"[GCAL] Auto-sync on edit failed (non-critical): {e}")
            
            # Send reschedule email to customer if time/date changed
            if time_changed or duration_changed:
                try:
                    updated_b2 = db.get_booking(booking_id, company_id=company_id)
                    client_id_rs = updated_b2.get('client_id') if updated_b2 else None
                    client_rs = db.get_client(client_id_rs, company_id=company_id) if client_id_rs else None
                    customer_email_rs = (updated_b2 or {}).get('email') or (client_rs.get('email') if client_rs else None)
                    customer_name_rs = (client_rs.get('name') if client_rs else None) or 'Customer'
                    service_type_rs = (updated_b2 or {}).get('service_type', 'appointment')
                    company_obj = db.get_company(company_id)
                    company_name_rs = company_obj.get('company_name', '') if company_obj else ''
                    
                    if customer_email_rs and new_appt_dt:
                        from src.services.email_reminder import get_email_service
                        email_svc = get_email_service()
                        email_svc.company_reply_to = (company_obj.get('email') or '').strip() if company_obj else None
                        is_full_day_rs = effective_duration >= 480
                        email_svc.send_reschedule_email(
                            to_email=customer_email_rs,
                            customer_name=customer_name_rs,
                            new_time=new_appt_dt,
                            service_type=service_type_rs,
                            company_name=company_name_rs,
                            is_full_day=is_full_day_rs
                        )
                        safe_print(f"[RESCHEDULE] Sent reschedule email to {customer_email_rs} for booking {booking_id}")
                except Exception as e:
                    safe_print(f"[RESCHEDULE] Email failed (non-critical): {e}")
            
            return jsonify({"success": True, "time_changed": time_changed, "duration_changed": duration_changed})
        return jsonify({"error": "Failed to update booking"}), 400
    
    elif request.method == "DELETE":
        # Verify booking belongs to this company before deleting
        booking = db.get_booking(booking_id, company_id=company_id)
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
        # Cancel in Google Calendar if connected
        try:
            from src.services.google_calendar_oauth import get_company_google_calendar
            gcal = get_company_google_calendar(company_id, db)
            event_id = booking.get('calendar_event_id', '')
            if gcal and event_id and not str(event_id).startswith('db_'):
                gcal.cancel_appointment(event_id)
        except Exception as e:
            safe_print(f"[GCAL] Auto-sync on delete failed (non-critical): {e}")
        
        success = db.delete_booking(booking_id, company_id=company_id)
        if success:
            return jsonify({"success": True, "message": "Booking deleted"})
        return jsonify({"error": "Failed to delete booking"}), 400


@app.route("/api/bookings/<int:booking_id>/reject", methods=["POST"])
@login_required
@subscription_required
def reject_booking_api(booking_id):
    """Reject/refuse a booking. Sets status to 'rejected', notifies customer, removes from calendar."""
    db = get_database()
    company_id = session.get('company_id')

    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    data = request.get_json() or {}
    reason = sanitize_string(data.get('reason', ''))

    # Update status to rejected
    success = db.update_booking(booking_id, company_id=company_id, status='rejected')
    if not success:
        return jsonify({"error": "Failed to reject booking"}), 500

    # Store rejection reason as a note
    if reason:
        db.add_appointment_note(booking_id, f"[REJECTED] {reason}", created_by="owner")

    # Remove from Google Calendar
    try:
        from src.services.google_calendar_oauth import get_company_google_calendar
        gcal = get_company_google_calendar(company_id, db)
        event_id = booking.get('calendar_event_id', '')
        if gcal and event_id and not str(event_id).startswith('db_'):
            gcal.cancel_appointment(event_id)
    except Exception as e:
        safe_print(f"[GCAL] Failed to remove rejected booking from calendar: {e}")

    # Send rejection email to customer
    customer_email = (booking.get('email') or '').strip()
    if not customer_email and booking.get('client_id'):
        try:
            client = db.get_client(booking['client_id'], company_id=company_id)
            if client:
                customer_email = (client.get('email') or '').strip()
        except Exception:
            pass

    company = db.get_company(company_id)
    company_name = company.get('company_name') if company else 'Your Service Provider'
    customer_name = booking.get('customer_name') or 'Customer'
    service_type = booking.get('service_type') or 'appointment'
    appt_time = booking.get('appointment_time')

    if customer_email:
        try:
            from src.services.email_reminder import get_email_service
            email_svc = get_email_service()
            if email_svc.configured:
                email_svc.company_reply_to = (company.get('email') or '').strip() if company else None
                email_svc.send_rejection_email(
                    to_email=customer_email,
                    customer_name=customer_name,
                    service_type=service_type,
                    appointment_time=appt_time,
                    company_name=company_name,
                    reason=reason,
                )
        except Exception as e:
            print(f"[WARNING] Failed to send rejection email: {e}")

    return jsonify({"success": True, "message": "Job rejected and customer notified"})


@app.route("/api/bookings/<int:booking_id>/photos", methods=["POST"])
@login_required
@subscription_required
@rate_limit(max_requests=20, window_seconds=60)
def upload_job_photo_api(booking_id):
    """Upload a photo or video to a job card, stored in R2.
    Accepts either:
      - JSON with base64 image: {"image": "data:image/..."}
      - Multipart form with file: file field named 'file'
    """
    db = get_database()
    company_id = session.get('company_id')

    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    import json as _json
    import io
    from datetime import datetime as _dt

    ALLOWED_MEDIA_TYPES = {
        'image/png', 'image/jpeg', 'image/gif', 'image/webp',
        'video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo',
    }
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB for videos

    media_url = None

    # Check if multipart file upload
    if request.files and 'file' in request.files:
        file = request.files['file']
        if not file or not file.filename:
            return jsonify({"error": "No file provided"}), 400

        content_type = file.content_type or ''
        if content_type not in ALLOWED_MEDIA_TYPES:
            return jsonify({"error": f"Unsupported file type: {content_type}"}), 400

        # Read file data and check size
        file_data = file.read()
        is_video = content_type.startswith('video/')
        max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE_BYTES

        if len(file_data) > max_size:
            limit_mb = max_size // (1024 * 1024)
            return jsonify({"error": f"File too large. Max {limit_mb}MB"}), 400

        try:
            from src.services.storage_r2 import upload_company_file, is_r2_enabled
            if not is_r2_enabled():
                return jsonify({"error": "Storage not configured"}), 500

            ext = content_type.split('/')[-1]
            if ext == 'quicktime':
                ext = 'mov'
            elif ext == 'x-msvideo':
                ext = 'avi'
            timestamp = _dt.now().strftime('%Y%m%d_%H%M%S')
            filename = f"job_media_{timestamp}_{secrets.token_hex(4)}.{ext}"

            media_url = upload_company_file(
                company_id=company_id,
                file_data=io.BytesIO(file_data),
                filename=filename,
                file_type='job_photos',
                content_type=content_type
            )
        except Exception as e:
            print(f"[ERROR] Media upload failed: {e}")
            return jsonify({"error": "Failed to upload file"}), 500

    else:
        # Fallback: base64 image upload (original behavior)
        data = request.json or {}
        image_data = data.get('image')
        if not image_data or not image_data.startswith('data:image/'):
            return jsonify({"error": "Invalid image data"}), 400

        media_url = upload_base64_image_to_r2(image_data, company_id, file_type='job_photos')

    if not media_url or media_url.startswith('data:'):
        return jsonify({"error": "Failed to upload media"}), 500

    # Append to photo_urls JSON array
    existing = booking.get('photo_urls') or []
    if isinstance(existing, str):
        try:
            existing = _json.loads(existing)
        except Exception:
            existing = []
    existing.append(media_url)

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE bookings SET photo_urls = %s WHERE id = %s AND company_id = %s",
            (_json.dumps(existing), booking_id, company_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to save media URL: {e}")
        return jsonify({"error": "Failed to save media"}), 500
    finally:
        cursor.close()
        db.return_connection(conn)

    return jsonify({"success": True, "photo_url": media_url, "photo_urls": existing})


@app.route("/api/bookings/<int:booking_id>/photos/delete", methods=["POST"])
@login_required
@subscription_required
def delete_job_photo_api(booking_id):
    """Delete a photo from a job card"""
    db = get_database()
    company_id = session.get('company_id')

    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    data = request.json or {}
    photo_url = data.get('photo_url')
    if not photo_url:
        return jsonify({"error": "photo_url required"}), 400

    import json as _json
    existing = booking.get('photo_urls') or []
    if isinstance(existing, str):
        try:
            existing = _json.loads(existing)
        except Exception:
            existing = []

    if photo_url not in existing:
        return jsonify({"error": "Photo not found on this job"}), 404

    # Delete from R2
    try:
        from src.services.storage_r2 import delete_company_file
        delete_company_file(company_id, photo_url)
    except Exception as e:
        print(f"[WARNING] R2 delete failed (non-critical): {e}")

    existing.remove(photo_url)

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE bookings SET photo_urls = %s WHERE id = %s AND company_id = %s",
            (_json.dumps(existing), booking_id, company_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to update photo_urls: {e}")
        return jsonify({"error": "Failed to delete photo"}), 500
    finally:
        cursor.close()
        db.return_connection(conn)

    return jsonify({"success": True, "photo_urls": existing})


@app.route("/api/bookings/<int:booking_id>/complete", methods=["POST"])
@login_required
@subscription_required
def complete_booking_api(booking_id):
    """Mark appointment as complete and update client description using AI"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Get the booking to find the client with company_id filter for security
    booking = db.get_booking(booking_id, company_id=company_id)
    
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    client_id = booking['client_id']
    current_status = booking['status']
    
    # Update booking status to completed - pass company_id for security
    db.update_booking(booking_id, company_id=company_id, status='completed')
    
    # Send customer satisfaction email (non-blocking, best-effort)
    try:
        # Check if review emails are enabled for this company
        company = db.get_company(company_id)
        send_reviews_enabled = company.get('send_review_emails', True) if company else True
        
        if send_reviews_enabled:
            # Get client info for email
            client = db.get_client(client_id, company_id=company_id)
            customer_email = booking.get('email') or (client.get('email') if client else None)
            customer_name = (client.get('name') if client else None) or booking.get('customer_name') or 'Customer'
            service = booking.get('service_type') or 'Job'
            
            if customer_email:
                # Check if a review already exists for this booking (prevent duplicates)
                existing_review = db.get_booking_review(booking_id, company_id=company_id)
                if existing_review:
                    safe_print(f"[REVIEW] Review already exists for booking {booking_id}, skipping")
                else:
                    import secrets
                    review_token = secrets.token_urlsafe(32)
                    review_record = db.create_job_review(
                        booking_id=booking_id,
                        company_id=company_id,
                        client_id=client_id,
                        review_token=review_token,
                        customer_name=customer_name,
                        service_type=service
                    )
                    if review_record:
                        from src.utils.config import config
                        public_url = getattr(config, 'PUBLIC_URL', 'https://bookedforyou.ie')
                        review_url = f"{public_url}/review/{review_token}"
                        
                        from src.services.email_reminder import get_email_service
                        email_svc = get_email_service()
                        email_svc.company_reply_to = (company.get('email') or '').strip() if company else None
                        sent = email_svc.send_satisfaction_survey(
                            to_email=customer_email,
                            customer_name=customer_name,
                            service_type=service,
                            review_url=review_url,
                            appointment_time=booking.get('appointment_time')
                        )
                        if sent:
                            db.mark_review_email_sent(review_record['id'])
                            safe_print(f"[REVIEW] Satisfaction email sent to {customer_email} for booking {booking_id}")
                        else:
                            safe_print(f"[REVIEW] Failed to send satisfaction email to {customer_email}")
            else:
                safe_print(f"[REVIEW] No email on file for booking {booking_id}, skipping satisfaction survey")
        else:
            safe_print(f"[REVIEW] Review emails disabled for company {company_id}, skipping")
    except Exception as e:
        safe_print(f"[REVIEW] Satisfaction email failed (non-critical): {e}")
    
    # Sync completed status to Google Calendar if connected
    try:
        from src.services.google_calendar_oauth import get_company_google_calendar
        gcal = get_company_google_calendar(company_id, db)
        if gcal:
            event_id = booking.get('calendar_event_id', '')
            if event_id and not str(event_id).startswith('db_'):
                appt_time = booking.get('appointment_time')
                if isinstance(appt_time, str):
                    from datetime import datetime as _dt
                    appt_time = _dt.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                elif hasattr(appt_time, 'replace'):
                    appt_time = appt_time.replace(tzinfo=None)
                # get_booking doesn't JOIN clients, so look up the name
                client = db.get_client(client_id, company_id=company_id)
                customer_name = (client.get('name') if client else None) or 'Customer'
                service = booking.get('service_type') or 'Job'
                duration = booking.get('duration_minutes', 60)
                phone = booking.get('phone_number') or (client.get('phone') if client else '') or ''
                address = booking.get('address') or ''
                summary = f"✅ {service} - {customer_name}"
                desc = (
                    f"Synced from BookedForYou\n"
                    f"Status: COMPLETED\n"
                    f"Customer: {customer_name}\n"
                    f"Phone: {phone}\n"
                    f"Address: {address}\n"
                    f"Duration: {duration} mins"
                )
                gcal.reschedule_appointment(
                    event_id, appt_time, duration_minutes=duration,
                    description=desc, summary=summary
                )
    except Exception as e:
        safe_print(f"[GCAL] Auto-sync on complete failed (non-critical): {e}")
    
    # Generate/update client description using AI based on all appointments and notes
    try:
        from src.services.client_description_generator import update_client_description
        success = update_client_description(client_id, company_id=company_id)
        
        if success:
            # Get the updated client info with new description
            client = db.get_client(client_id, company_id=company_id)
            return jsonify({
                "success": True,
                "message": "Appointment completed and description updated",
                "description": client.get('description') if client else None
            })
        else:
            return jsonify({
                "success": True,
                "message": "Appointment completed (no description generated)",
                "description": None
            })
    except Exception as e:
        print(f"[ERROR] Error updating description: {e}")
        return jsonify({
            "success": True,
            "message": "Appointment completed but description update failed",
            "error": str(e)
        }), 500


@app.route("/api/invoice-config", methods=["GET"])
@login_required
def get_invoice_config():
    """Get invoice configuration status — email first, SMS fallback"""
    db = get_database()
    company_id = session.get('company_id')
    return jsonify(_build_invoice_config(db, company_id))


def _build_invoice_config(db, company_id):
    """Compute invoice-config payload (reusable for batch endpoints)."""
    company = db.get_company(company_id)

    # Check email service
    email_configured = False
    try:
        from src.services.email_reminder import get_email_service
        email_svc = get_email_service()
        email_configured = email_svc.configured
    except Exception:
        pass

    # Check if Twilio SMS is configured
    from src.services.sms_reminder import get_sms_service
    sms_service = get_sms_service()
    sms_configured = sms_service.client is not None

    # Delivery method priority
    if email_configured:
        delivery_method = 'email'
        service_name = 'Email (SMS fallback)'
    else:
        delivery_method = 'sms'
        service_name = 'SMS (Twilio)'

    service_configured = email_configured or sms_configured

    # Check payment methods configured
    has_stripe = bool(company.get('stripe_connect_account_id')) if company else False
    stripe_charges_enabled = False
    stripe_check_failed = False
    if has_stripe:
        try:
            import stripe
            stripe_key = os.getenv('STRIPE_SECRET_KEY')
            if stripe_key:
                stripe.api_key = stripe_key
                acct = stripe.Account.retrieve(company['stripe_connect_account_id'])
                stripe_charges_enabled = acct.get('charges_enabled', False)
            else:
                # No key to verify — assume configured since account ID exists
                stripe_check_failed = True
        except Exception:
            # API call failed — don't penalise the user; assume configured
            stripe_check_failed = True

    has_bank = bool(company.get('bank_iban')) if company else False
    has_revolut = bool(company.get('revolut_phone')) if company else False
    # Stripe counts as a payment method if the account exists (even if we
    # couldn't verify charges_enabled due to API failure)
    stripe_is_payment = has_stripe and (stripe_charges_enabled or stripe_check_failed)
    has_any_payment = stripe_is_payment or has_bank or has_revolut

    can_send_invoice = service_configured

    warnings = []
    if not service_configured:
        warnings.append("Neither email nor SMS is configured. Set up email (RESEND_API_KEY) or Twilio for SMS.")
    if has_stripe and not stripe_charges_enabled and not stripe_check_failed:
        warnings.append("Stripe Connect setup is incomplete. Complete your Stripe account to accept online payments. Invoices will be sent without a payment link.")
    elif not has_stripe:
        warnings.append("Stripe Connect not set up. Invoices will be sent without an online payment link. Set up Stripe in Settings > Payments.")
    if not has_any_payment:
        warnings.append("No payment methods configured. Add Stripe, bank details, or Revolut in Settings > Payment Setup.")

    return {
        "delivery_method": delivery_method,
        "service_name": service_name,
        "service_configured": service_configured,
        "email_configured": email_configured,
        "sms_configured": sms_configured,
        "can_send_invoice": can_send_invoice,
        "has_stripe_connect": stripe_is_payment,
        "stripe_setup_incomplete": has_stripe and not stripe_charges_enabled and not stripe_check_failed,
        "payment_methods": {
            "stripe": stripe_is_payment,
            "stripe_incomplete": has_stripe and not stripe_charges_enabled and not stripe_check_failed,
            "bank_transfer": has_bank,
            "revolut": has_revolut,
            "any_configured": has_any_payment
        },
        "warnings": warnings
    }


@app.route("/api/job-setup-data", methods=["GET"])
@login_required
def get_job_setup_data():
    """Batch endpoint: invoice-config + services menu + packages in a single request.

    Replaces 3 sequential fetches from the Jobs tab with one round-trip.
    """
    from src.services.settings_manager import get_settings_manager
    db = get_database()
    company_id = session.get('company_id')
    settings_mgr = get_settings_manager()

    try:
        services_menu = settings_mgr.get_services_menu(company_id=company_id)
    except Exception as e:
        print(f"[WARN] get_job_setup_data services_menu failed: {e}")
        services_menu = {"services": []}

    try:
        packages = settings_mgr.get_packages(company_id=company_id)
    except Exception as e:
        print(f"[WARN] get_job_setup_data packages failed: {e}")
        packages = {"packages": []}

    try:
        invoice_config = _build_invoice_config(db, company_id)
    except Exception as e:
        print(f"[WARN] get_job_setup_data invoice_config failed: {e}")
        invoice_config = {}

    return jsonify({
        "invoice_config": invoice_config,
        "services_menu": services_menu,
        "packages": packages,
    })


@app.route("/api/reviews", methods=["GET"])
@login_required
def get_company_reviews():
    """Get all reviews for the logged-in company."""
    db = get_database()
    company_id = session.get('company_id')
    try:
        reviews = db.get_company_reviews(company_id)
    except Exception as e:
        # job_reviews table may not exist yet
        if 'relation' in str(e) and 'does not exist' in str(e):
            return jsonify({"reviews": []})
        raise
    return jsonify({"reviews": reviews})


@app.route("/api/bookings/<int:booking_id>/review", methods=["GET"])
@login_required
def get_booking_review(booking_id):
    """Get the review for a specific booking."""
    db = get_database()
    company_id = session.get('company_id')
    review = db.get_booking_review(booking_id, company_id=company_id)
    return jsonify({"review": review})


@app.route("/api/review/<token>", methods=["GET"])
def get_review_by_token(token):
    """Public endpoint: get review info by token for the submission page."""
    db = get_database()
    print(f"[REVIEW] Looking up review token: {token[:20]}...")
    review = db.get_review_by_token(token)
    if not review:
        print(f"[REVIEW] Token not found: {token}")
        return jsonify({"error": "Review not found or link expired"}), 404
    if review.get('submitted_at'):
        return jsonify({"already_submitted": True, "rating": review.get('rating')})
    return jsonify({
        "customer_name": review.get('customer_name'),
        "service_type": review.get('service_type'),
        "company_name": review.get('company_name'),
    })


@app.route("/api/review/<token>", methods=["POST"])
def submit_review(token):
    """Public endpoint: submit a customer review."""
    db = get_database()
    data = request.get_json() or {}
    rating = data.get('rating')
    review_text = data.get('review_text', '').strip()

    if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    review = db.get_review_by_token(token)
    if not review:
        return jsonify({"error": "Review not found"}), 404
    if review.get('submitted_at'):
        return jsonify({"error": "Review already submitted"}), 400

    success = db.submit_review(token, rating, review_text or None)
    if success:
        # Check if we should redirect to Google Reviews
        google_url = None
        try:
            company_id = review.get('company_id')
            if company_id:
                company = db.get_company(company_id)
                if company:
                    threshold = company.get('google_review_threshold', 4) or 4
                    g_url = (company.get('review_google_url') or '').strip()
                    if g_url and rating >= threshold:
                        google_url = g_url
        except Exception:
            pass
        return jsonify({"success": True, "message": "Thank you for your review!", "google_review_url": google_url})
    return jsonify({"error": "Failed to submit review"}), 500


# ============================================
# LEADS / CRM API
# ============================================

@app.route("/api/leads", methods=["GET"])
@login_required
def get_leads():
    """Get all leads for the company."""
    from psycopg2.extras import RealDictCursor
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM leads
            WHERE company_id = %s
            ORDER BY
                CASE stage
                    WHEN 'new' THEN 1
                    WHEN 'contacted' THEN 2
                    WHEN 'quoted' THEN 3
                    WHEN 'won' THEN 4
                    WHEN 'lost' THEN 5
                END,
                created_at DESC
        """, (company_id,))
        leads = cursor.fetchall()
        for lead in leads:
            for key in ('created_at', 'updated_at', 'converted_at', 'follow_up_date'):
                if lead.get(key) and hasattr(lead[key], 'isoformat'):
                    lead[key] = lead[key].isoformat()
        return jsonify({"leads": leads})
    except Exception as e:
        # Table may not exist yet
        err_str = str(e).lower()
        if 'does not exist' in err_str or 'relation' in err_str:
            conn.rollback()
            return jsonify({"leads": []})
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/leads", methods=["POST"])
@login_required
@subscription_required
def create_lead():
    """Create a new lead."""
    from psycopg2.extras import RealDictCursor
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Lead name is required"}), 400

    conn = db.get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            INSERT INTO leads (company_id, name, phone, email, address, source, stage,
                               notes, service_interest, estimated_value, follow_up_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            company_id, name,
            (data.get('phone') or '').strip() or None,
            (data.get('email') or '').strip() or None,
            (data.get('address') or '').strip() or None,
            data.get('source', 'manual'),
            data.get('stage', 'new'),
            (data.get('notes') or '').strip() or None,
            (data.get('service_interest') or '').strip() or None,
            data.get('estimated_value'),
            data.get('follow_up_date') or None,
        ))
        lead_id = cursor.fetchone()['id']
        conn.commit()
        return jsonify({"id": lead_id, "message": "Lead created"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/leads/<int:lead_id>", methods=["PUT"])
@login_required
@subscription_required
def update_lead(lead_id):
    """Update a lead (stage, notes, etc.)."""
    from psycopg2.extras import RealDictCursor
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}

    conn = db.get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Verify ownership
        cursor.execute("SELECT id FROM leads WHERE id = %s AND company_id = %s", (lead_id, company_id))
        if not cursor.fetchone():
            return jsonify({"error": "Lead not found"}), 404

        fields = []
        values = []
        for col in ('name', 'phone', 'email', 'address', 'stage', 'notes',
                     'service_interest', 'estimated_value', 'lost_reason', 'follow_up_date', 'source'):
            if col in data:
                fields.append(f"{col} = %s")
                val = data[col]
                if isinstance(val, str):
                    val = val.strip() or None
                values.append(val)

        # If stage changed to 'won', set converted_at
        if data.get('stage') == 'won':
            fields.append("converted_at = CURRENT_TIMESTAMP")

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([lead_id, company_id])

        cursor.execute(
            f"UPDATE leads SET {', '.join(fields)} WHERE id = %s AND company_id = %s",
            values
        )
        conn.commit()
        return jsonify({"message": "Lead updated"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_lead(lead_id):
    """Delete a lead."""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM leads WHERE id = %s AND company_id = %s", (lead_id, company_id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Lead not found"}), 404
        return jsonify({"message": "Lead deleted"})
    except Exception as e:
        conn.rollback()
        if 'relation "leads" does not exist' in str(e):
            return jsonify({"error": "Lead not found"}), 404
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/leads/<int:lead_id>/convert", methods=["POST"])
@login_required
@subscription_required
def convert_lead_to_client(lead_id):
    """Convert a lead into a client and mark it as won."""
    from psycopg2.extras import RealDictCursor
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM leads WHERE id = %s AND company_id = %s", (lead_id, company_id))
        lead = cursor.fetchone()
        if not lead:
            return jsonify({"error": "Lead not found"}), 404

        # Check if a customer with this phone already exists (avoid duplicates)
        existing_client_id = None
        if lead.get('phone'):
            cursor.execute(
                "SELECT id FROM clients WHERE company_id = %s AND phone = %s LIMIT 1",
                (company_id, lead['phone'])
            )
            row = cursor.fetchone()
            if row:
                existing_client_id = row['id']
                # Enrich existing client with any new info from the lead
                enrich_parts = []
                enrich_vals = []
                if lead.get('address'):
                    enrich_parts.append("address = COALESCE(NULLIF(address, ''), %s)")
                    enrich_vals.append(lead['address'])
                if lead.get('email'):
                    enrich_parts.append("email = COALESCE(NULLIF(email, ''), %s)")
                    enrich_vals.append(lead['email'])
                if enrich_parts:
                    enrich_vals.append(existing_client_id)
                    cursor.execute(f"UPDATE clients SET {', '.join(enrich_parts)} WHERE id = %s", tuple(enrich_vals))

        if not existing_client_id:
            # Create client from lead data
            existing_client_id = db.add_client(
                name=lead['name'],
                phone=lead.get('phone'),
                email=lead.get('email'),
                address=lead.get('address'),
                company_id=company_id,
            )

        if not existing_client_id:
            return jsonify({"error": "Failed to create customer profile"}), 500

        # Update lead as won with client reference
        cursor.execute("""
            UPDATE leads SET stage = 'won', client_id = %s, converted_at = CURRENT_TIMESTAMP,
                             updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND company_id = %s
        """, (existing_client_id, lead_id, company_id))
        conn.commit()
        return jsonify({"client_id": existing_client_id, "message": "Lead converted to customer"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/clients/<int:client_id>/tags", methods=["PUT"])
@login_required
@subscription_required
def update_client_tags(client_id):
    """Update tags on a client for CRM segmentation."""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    tags = data.get('tags', [])

    client = db.get_client(client_id, company_id=company_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE clients SET tags = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND company_id = %s",
            (tags, client_id, company_id)
        )
        conn.commit()
        return jsonify({"message": "Tags updated"})
    except Exception as e:
        conn.rollback()
        # tags column may not exist
        if 'column "tags"' in str(e):
            return jsonify({"message": "Tags feature not yet migrated"}), 200
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/crm/stats", methods=["GET"])
@login_required
def get_crm_stats():
    """Get CRM overview stats: customer health, lead pipeline counts, etc."""
    from psycopg2.extras import RealDictCursor
    db = get_database()
    company_id = session.get('company_id')

    # Fetch client stats and customer health first
    conn = db.get_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Client stats
        cursor.execute("""
            SELECT COUNT(*) as total_clients,
                   COUNT(CASE WHEN created_at > CURRENT_TIMESTAMP - INTERVAL '30 days' THEN 1 END) as new_this_month
            FROM clients WHERE company_id = %s
        """, (company_id,))
        client_stats = cursor.fetchone()

        # Booking-based customer health
        cursor.execute("""
            SELECT c.id, c.name, c.phone, c.email, c.created_at,
                   COUNT(b.id) as total_jobs,
                   COUNT(CASE WHEN b.status = 'completed' THEN 1 END) as completed_jobs,
                   COALESCE(SUM(CASE WHEN b.status = 'completed' THEN COALESCE(b.charge, 0) END), 0) as total_revenue,
                   MAX(b.appointment_time) as last_job_date
            FROM clients c
            LEFT JOIN bookings b ON b.client_id = c.id AND b.company_id = c.company_id
            WHERE c.company_id = %s
            GROUP BY c.id, c.name, c.phone, c.email, c.created_at
        """, (company_id,))
        customer_health = cursor.fetchall()

        for ch in customer_health:
            for key in ('created_at', 'last_job_date'):
                if ch.get(key) and hasattr(ch[key], 'isoformat'):
                    ch[key] = ch[key].isoformat()
    finally:
        db.return_connection(conn)

    # Fetch lead counts separately so a missing leads table doesn't break everything
    lead_counts = {'new': 0, 'contacted': 0, 'quoted': 0, 'won': 0, 'lost': 0}
    conn2 = db.get_connection()
    try:
        cursor2 = conn2.cursor(cursor_factory=RealDictCursor)
        cursor2.execute("""
            SELECT stage, COUNT(*) as count FROM leads
            WHERE company_id = %s GROUP BY stage
        """, (company_id,))
        for row in cursor2.fetchall():
            lead_counts[row['stage']] = row['count']
    except Exception:
        pass  # leads table may not exist yet — that's fine
    finally:
        db.return_connection(conn2)

    return jsonify({
        "client_stats": client_stats,
        "customer_health": customer_health,
        "lead_counts": lead_counts,
    })


@app.route("/api/bookings/<int:booking_id>/send-invoice", methods=["POST"])
@login_required
@subscription_required
def send_invoice_api(booking_id):
    """Send invoice via SMS"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Get optional invoice data overrides from request body
    request_data = request.get_json() or {}
    
    # Always use SMS for invoices
    from src.services.sms_reminder import get_sms_service
    sms_service = get_sms_service()
    if not sms_service.client:
        return jsonify({
            "error": "SMS service not configured. Please configure Twilio settings.",
            "details": "Twilio credentials are missing from server configuration."
        }), 503
    
    # Check subscription for sending invoices
    company = db.get_company(company_id)
    subscription_info = get_subscription_info(company)
    if not subscription_info['is_active']:
        return jsonify({
            "error": "Active subscription required to send invoices",
            "subscription_status": "inactive"
        }), 403
    
    try:
        # Get the booking details using database method with company_id filter for security
        booking = db.get_booking(booking_id, company_id=company_id)
        
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
        # Get client details if client_id exists
        if booking.get('client_id'):
            client = db.get_client(booking['client_id'], company_id=company_id)
            if client:
                booking['client_name'] = client.get('name')
                booking['customer_name'] = client.get('name')
                booking['client_phone'] = client.get('phone')
                booking['client_email'] = client.get('email')
                # Use client email/phone if booking doesn't have them
                if not booking.get('phone_number'):
                    booking['phone_number'] = client.get('phone')
                if not booking.get('email'):
                    booking['email'] = client.get('email')
        
        # Normalize booking dict for compatibility
        booking_dict = {
            'id': booking.get('id'),
            'client_id': booking.get('client_id'),
            'calendar_event_id': booking.get('calendar_event_id'),
            'appointment_time': booking.get('appointment_time'),
            'service_type': booking.get('service_type'),
            'status': booking.get('status'),
            'phone_number': booking.get('phone_number'),
            'phone': booking.get('phone_number') or booking.get('client_phone'),
            'email': (booking.get('email') or '').strip() or (booking.get('client_email') or '').strip() or None,
            'created_at': booking.get('created_at'),
            'charge': booking.get('charge'),
            'estimated_charge': booking.get('charge'),
            'estimated_charge_max': booking.get('charge_max'),
            'payment_status': booking.get('payment_status'),
            'payment_method': booking.get('payment_method'),
            'urgency': booking.get('urgency'),
            'address': booking.get('address'),
            'job_address': booking.get('address'),
            'eircode': booking.get('eircode'),
            'property_type': booking.get('property_type'),
            'customer_name': booking.get('customer_name') or booking.get('client_name'),
            'client_name': booking.get('client_name') or booking.get('customer_name')
        }
        
        # Apply overrides from request data (from confirmation modal)
        if request_data.get('customer_name'):
            booking_dict['customer_name'] = request_data['customer_name']
            booking_dict['client_name'] = request_data['customer_name']
        if request_data.get('phone'):
            booking_dict['phone'] = request_data['phone']
            booking_dict['phone_number'] = request_data['phone']
        if request_data.get('service_type'):
            booking_dict['service_type'] = request_data['service_type']
        if request_data.get('charge'):
            booking_dict['charge'] = float(request_data['charge'])
            booking_dict['estimated_charge'] = float(request_data['charge'])
        if request_data.get('job_address'):
            booking_dict['address'] = request_data['job_address']
            booking_dict['job_address'] = request_data['job_address']
        if request_data.get('eircode'):
            booking_dict['eircode'] = request_data['eircode']
        if request_data.get('email'):
            booking_dict['email'] = request_data['email']
        
        safe_print(f"[INVOICE] Invoice: Using charge amount EUR{booking_dict['charge']} for booking {booking_id}")
        
        # Validate required fields - need at least email or phone
        to_phone = booking_dict['phone']
        to_email_check = booking_dict.get('email') or booking_dict.get('client_email')
        if not to_phone and not to_email_check:
            return jsonify({"error": "Customer has no email or phone number. Please add contact details to the customer profile."}), 400
        
        if not booking_dict['client_name']:
            return jsonify({"error": "Customer name not found"}), 400
        
        # Get charge amount - use charge or estimated_charge, default to None if not set
        charge_amount = booking_dict.get('charge') or booking_dict.get('estimated_charge')
        
        if not charge_amount or charge_amount <= 0:
            return jsonify({"error": "Invalid charge amount"}), 400
        
        charge_amount = float(charge_amount)
        safe_print(f"[INVOICE] Invoice: Final charge amount = EUR{charge_amount}")
        
        # Generate Stripe payment link
        from datetime import datetime
        stripe_payment_link = None
        stripe_payment_link_sms = None
        stripe_payment_link_email = None
        
        # Get the user's company to check for Stripe Connect account
        company = db.get_company(session['company_id'])
        connected_account_id = company.get('stripe_connect_account_id') if company else None
        
        # Try to create Stripe payment link if configured
        from src.utils.config import config
        stripe_secret_key = getattr(config, 'STRIPE_SECRET_KEY', None)
        
        # Debug: Check if key is loaded
        if stripe_secret_key:
            print(f"[STRIPE] Stripe key found: {stripe_secret_key[:12]}...{stripe_secret_key[-4:]}")
        else:
            # Try loading directly from environment as fallback
            stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
            if stripe_secret_key:
                print(f"[STRIPE] Stripe key loaded from env: {stripe_secret_key[:12]}...{stripe_secret_key[-4:]}")
            else:
                print("[INFO] STRIPE_SECRET_KEY not found - invoice will be sent without payment link")
        
        # Only create Stripe payment link if the user has a fully-enabled Connect account
        if stripe_secret_key and connected_account_id:
            try:
                import stripe
                stripe.api_key = stripe_secret_key
                
                # Check if the Connect account can actually accept charges
                try:
                    connect_acct = stripe.Account.retrieve(connected_account_id)
                    if not connect_acct.get('charges_enabled'):
                        print(f"[STRIPE] Connect account {connected_account_id} has charges_enabled=False — skipping payment link")
                        connected_account_id = None  # Treat as not configured
                except Exception as acct_err:
                    print(f"[STRIPE] Could not verify Connect account: {acct_err}")
                    connected_account_id = None
            except Exception:
                pass
        
        if stripe_secret_key and connected_account_id:
            try:
                import stripe
                stripe.api_key = stripe_secret_key
                
                # Amount must be in cents
                amount_cents = int(charge_amount * 100)
                
                print(f"[STRIPE] Creating Stripe checkout via Connect account {connected_account_id} for EUR{charge_amount} ({amount_cents} cents)...")
                
                # Build checkout session params
                checkout_params = {
                    'payment_method_types': ['card'],
                    'line_items': [{
                        'price_data': {
                            'currency': 'eur',
                            'product_data': {
                                'name': f"{booking_dict.get('service_type') or 'Service'} - Invoice #{booking_id}",
                                'description': f"Service for {booking_dict['client_name']}",
                            },
                            'unit_amount': amount_cents,
                        },
                        'quantity': 1,
                    }],
                    'mode': 'payment',
                    'success_url': f"{os.getenv('PUBLIC_URL', 'http://localhost:5000')}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
                    'cancel_url': f"{os.getenv('PUBLIC_URL', 'http://localhost:5000')}/payment-cancelled",
                    'metadata': {
                        'booking_id': str(booking_id),
                        'customer_name': booking_dict['client_name'],
                    }
                }
                
                # Fixed €2 platform fee per transaction
                platform_fee_cents = int(os.getenv('STRIPE_PLATFORM_FEE_CENTS', '200'))
                if platform_fee_cents > 0:
                    checkout_params['payment_intent_data'] = {
                        'application_fee_amount': platform_fee_cents,
                        'metadata': {
                            'booking_id': str(booking_id),
                            'company_id': str(company_id),
                        },
                    }
                else:
                    checkout_params['payment_intent_data'] = {
                        'metadata': {
                            'booking_id': str(booking_id),
                            'company_id': str(company_id),
                        },
                    }
                
                checkout_session = stripe.checkout.Session.create(
                    **checkout_params,
                    stripe_account=connected_account_id
                )
                
                stripe_payment_link = checkout_session.url
                print(f"[SUCCESS] Stripe payment link created: {stripe_payment_link}")
                
                # Store the full Stripe URL on the booking for the /pay redirect
                try:
                    db.update_booking(booking_id, company_id=company_id,
                                      stripe_checkout_url=checkout_session.url)
                    conn2 = db.get_connection()
                    try:
                        cur2 = conn2.cursor()
                        cur2.execute("UPDATE bookings SET stripe_checkout_session_id = %s WHERE id = %s AND company_id = %s",
                                     (checkout_session.id, booking_id, company_id))
                        conn2.commit()
                        cur2.close()
                    finally:
                        db.return_connection(conn2)
                except Exception:
                    pass  # Non-critical
                
                # For SMS: use short URL via frontend /pay/:id route (clean, no % chars)
                # The React app redirects /pay/:id to the backend /api/pay/:id
                # which then redirects to the Stripe checkout URL
                public_url = os.getenv('PUBLIC_URL', '').rstrip('/')
                if public_url:
                    stripe_payment_link_sms = f"{public_url}/pay/{booking_id}"
                    stripe_payment_link_email = checkout_session.url
                    print(f"[SUCCESS] SMS payment URL: {stripe_payment_link_sms}")
                    print(f"[SUCCESS] Email payment URL: {stripe_payment_link_email[:60]}...")
                else:
                    stripe_payment_link_sms = checkout_session.url
                    stripe_payment_link_email = checkout_session.url
            except Exception as stripe_error:
                print(f"[WARNING] Could not create Stripe payment link: {stripe_error}")
                import traceback
                traceback.print_exc()
        elif not connected_account_id:
            print("ℹ️ No Stripe Connect account - invoice will be sent without payment link")
        
        # Get bank details for bank transfer option on invoice
        bank_details = None
        revolut_phone = None
        if company:
            bank_iban = company.get('bank_iban', '')
            bank_bic = company.get('bank_bic', '')
            bank_name = company.get('bank_name', '')
            account_holder = company.get('bank_account_holder', '')
            revolut_phone_val = company.get('revolut_phone', '')
            if bank_iban or bank_bic or bank_name or account_holder:
                bank_details = {
                    'iban': bank_iban,
                    'bic': bank_bic,
                    'bank_name': bank_name,
                    'account_holder': account_holder,
                }
            revolut_phone = revolut_phone_val if revolut_phone_val else None
        
        # Parse appointment time
        appointment_time = None
        if booking_dict.get('appointment_time'):
            try:
                apt_time = booking_dict['appointment_time']
                if isinstance(apt_time, datetime):
                    appointment_time = apt_time
                elif isinstance(apt_time, str):
                    appointment_time = datetime.fromisoformat(apt_time.replace('Z', '+00:00'))
            except Exception as e:
                print(f"[WARNING] Could not parse appointment_time: {e}")
        
        # Generate invoice number
        invoice_number = f"INV-{booking_id}-{datetime.now().strftime('%Y%m%d')}"
        
        # Get job address (include eircode if available)
        job_address = booking_dict.get('address') or booking_dict.get('job_address') or ''
        eircode = booking_dict.get('eircode') or ''
        if eircode and eircode not in job_address:
            job_address = f"{job_address} ({eircode})" if job_address else eircode
        
        # Get business details from the company record
        company_business_name = company.get('company_name') or company.get('business_name') or company.get('name') or None if company else None
        
        # Try email first, then SMS fallback
        sent_via = None
        # Resolve email: check booking dict, then re-fetch from client directly
        to_email = booking_dict.get('email')
        if not to_email and booking.get('client_id'):
            # Re-fetch client to get email (in case booking record doesn't have it)
            _client_for_email = db.get_client(booking['client_id'], company_id=company_id)
            if _client_for_email:
                to_email = _client_for_email.get('email')
        # Strip whitespace and treat empty string as None
        if to_email:
            to_email = to_email.strip()
        if not to_email:
            to_email = None
        
        safe_print(f"[INVOICE] Email resolution: to_email={to_email}, to_phone={to_phone}")
        
        if to_email:
            try:
                from src.services.email_reminder import get_email_service
                email_svc = get_email_service()
                safe_print(f"[INVOICE] Email service configured: {email_svc.configured}, use_resend: {email_svc.use_resend}, smtp_configured: {email_svc.smtp_configured}")
                # Set reply-to to company's email so customer replies go to the business
                email_svc.company_reply_to = (company.get('email') or '').strip() if company else None
                if email_svc.configured:
                    safe_print(f"[INVOICE] Attempting email send to {to_email}...")
                    email_sent = email_svc.send_invoice(
                        to_email=to_email,
                        customer_name=booking_dict['client_name'],
                        service_type=booking_dict.get('service_type') or 'Service',
                        charge=charge_amount,
                        invoice_number=invoice_number,
                        stripe_payment_link=stripe_payment_link_email,
                        job_address=job_address,
                        appointment_time=appointment_time,
                        company_name=company_business_name,
                        bank_details=bank_details,
                        revolut_phone=revolut_phone
                    )
                    safe_print(f"[INVOICE] Email send result: {email_sent}")
                    if email_sent:
                        sent_via = 'email'
                        safe_print(f"[INVOICE] ✅ Invoice sent via email to {to_email}")
                    else:
                        safe_print(f"[INVOICE] ❌ Email send returned False — falling back to SMS")
                else:
                    safe_print(f"[INVOICE] Email service not configured — skipping email, will try SMS")
            except Exception as email_err:
                safe_print(f"[INVOICE] ❌ Email send exception: {email_err}")
                import traceback; traceback.print_exc()
        else:
            safe_print(f"[INVOICE] No email address found — will try SMS directly")
        
        # Fallback to SMS
        if not sent_via and to_phone:
            safe_print(f"[INVOICE] Attempting SMS fallback to {to_phone}, payment_link_sms={stripe_payment_link_sms}")
            try:
                success = sms_service.send_invoice(
                    to_number=to_phone,
                    customer_name=booking_dict['client_name'],
                    service_type=booking_dict.get('service_type') or 'Service',
                    charge=charge_amount,
                    invoice_number=invoice_number,
                    stripe_payment_link=stripe_payment_link_sms,
                    job_address=job_address,
                    appointment_time=appointment_time,
                    company_name=company_business_name,
                    bank_details=bank_details,
                    revolut_phone=revolut_phone
                )
                if success:
                    sent_via = 'sms'
                    safe_print(f"[INVOICE] ✅ Invoice sent via SMS to {to_phone}")
                else:
                    safe_print(f"[INVOICE] ❌ SMS send returned False")
            except Exception as sms_err:
                safe_print(f"[INVOICE] ❌ SMS send exception: {sms_err}")
        
        if sent_via:
            # Update payment status to 'invoiced' so we know an invoice was sent
            try:
                db.update_booking(booking_id, company_id=company_id, payment_status='invoiced')
            except Exception:
                pass  # Non-critical, don't fail the response
            
            sent_to = to_email if sent_via == 'email' else to_phone
            return jsonify({
                "success": True,
                "message": f"Invoice sent via {sent_via} to {sent_to}",
                "sent_to": sent_to,
                "delivery_method": sent_via,
                "invoice_number": invoice_number,
                "has_payment_link": stripe_payment_link_email is not None or stripe_payment_link_sms is not None
            })
        else:
            # Build specific error message
            if to_email and to_phone:
                err = f"Both email to {to_email} and SMS to {to_phone} failed. Check server logs for details."
            elif to_email:
                err = f"Email to {to_email} failed and no phone number for SMS fallback."
            elif to_phone:
                err = f"SMS to {to_phone} failed. No email address for email fallback."
            else:
                err = "No email or phone number available. Add contact details to the customer profile."
            return jsonify({"error": err}), 500
            
    except Exception as e:
        safe_print(f"[ERROR] Error sending invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"An error occurred while sending the invoice: {str(e)}"}), 500


@app.route("/api/finances/stats", methods=["GET"])
@login_required
def financial_stats_api():
    """Get financial statistics"""
    db = get_database()
    company_id = session.get('company_id')
    stats = db.get_financial_stats(company_id=company_id)
    return jsonify(stats)


@app.route("/api/stats", methods=["GET"])
@login_required
def stats_api():
    """Get dashboard statistics"""
    db = get_database()
    company_id = session.get('company_id')
    # Google Calendar disabled (USE_GOOGLE_CALENDAR = False)
    
    clients = db.get_all_clients(company_id=company_id)
    bookings = db.get_all_bookings(company_id=company_id)
    upcoming = []  # Calendar disabled
    
    stats = {
        "total_clients": len(clients),
        "total_bookings": len(bookings),
        "upcoming_appointments": len(upcoming),
        "recent_clients": clients[:5] if clients else []
    }
    
    return jsonify(stats)


@app.route("/api/config", methods=["GET"])
def config_api():
    """Get application configuration for frontend"""
    return jsonify({
        "default_charge": config.DEFAULT_APPOINTMENT_CHARGE,
        "currency": "EUR",
        "business_hours": {
            "start": config.BUSINESS_HOURS_START,
            "end": config.BUSINESS_HOURS_END
        },
        "timezone": config.CALENDAR_TIMEZONE,
        "notification_poll_interval": config.NOTIFICATION_POLL_INTERVAL,
        "max_booking_days_ahead": config.MAX_BOOKING_DAYS_AHEAD,
        "appointment_slot_duration": config.APPOINTMENT_SLOT_DURATION
    })


@app.route("/api/call-logs", methods=["GET"])
@login_required
def call_logs_api():
    """Get call logs for the company with optional filtering and pagination."""
    db = get_database()
    company_id = session.get('company_id')

    outcome = request.args.get('outcome', 'all')
    search = request.args.get('search', '').strip() or None
    lost_only = request.args.get('lost_only', '').lower() == 'true'
    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(int(request.args.get('per_page', 50)), 100)
    except (ValueError, TypeError):
        per_page = 50
    offset = (page - 1) * per_page

    # "no_booking" groups multiple outcomes server-side + lost jobs
    outcomes = None
    include_lost = False
    if outcome == 'no_booking':
        outcomes = ['hung_up', 'no_action', 'wrong_number', 'enquiry', 'cancelled', 'lost_job']
        include_lost = True
        outcome = 'all'  # Don't also apply single outcome filter

    logs = db.get_call_logs(
        company_id=company_id,
        limit=per_page,
        offset=offset,
        outcome_filter=outcome,
        search=search,
        lost_only=lost_only,
        outcomes=outcomes,
        include_lost=include_lost,
    )
    total = db.get_call_log_count(
        company_id=company_id,
        outcome_filter=outcome,
        search=search,
        lost_only=lost_only,
        outcomes=outcomes,
        include_lost=include_lost,
    )

    # Serialize datetimes
    for log in logs:
        if log.get('created_at'):
            log['created_at'] = log['created_at'].isoformat() if hasattr(log['created_at'], 'isoformat') else str(log['created_at'])

    return jsonify({
        "call_logs": logs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, -(-total // per_page)),  # ceil division
    })


@app.route("/api/call-logs/unseen-count", methods=["GET"])
@login_required
def call_logs_unseen_count():
    """Count call logs created after a given timestamp."""
    db = get_database()
    company_id = session.get('company_id')
    since = request.args.get('since')
    if not since:
        return jsonify({"count": 0})
    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM call_logs WHERE company_id = %s AND created_at > %s",
            (company_id, since),
        )
        count = cursor.fetchone()[0]
        return jsonify({"count": count})
    except Exception as e:
        print(f"[ERROR] unseen count: {e}")
        return jsonify({"count": 0})
    finally:
        if conn:
            db.return_connection(conn)


# ============================================
# CRM EMAIL ENDPOINTS
# ============================================

@app.route("/api/crm/send-email", methods=["POST"])
@login_required
@subscription_required
def crm_send_email():
    """Send an individual email to a customer from the CRM."""
    db = get_database()
    company_id = session['company_id']
    data = request.get_json() or {}

    to_email = (data.get('to_email') or '').strip()
    subject = (data.get('subject') or '').strip()
    body_html = (data.get('body_html') or '').strip()
    body_text = (data.get('body_text') or '').strip()
    client_id = data.get('client_id')

    if not to_email:
        return jsonify({"error": "Recipient email is required"}), 400
    if not subject:
        return jsonify({"error": "Subject is required"}), 400
    if not body_html and not body_text:
        return jsonify({"error": "Email body is required"}), 400

    # Get company name and email for from_name and reply-to
    company = db.get_company(company_id)
    company_name = company.get('company_name', 'BookedForYou') if company else 'BookedForYou'
    company_email = (company.get('email') or company.get('business_email') or '').strip() if company else ''

    # If no HTML provided, wrap plain text in basic HTML
    if not body_html:
        body_html = f"<div style='font-family:sans-serif;font-size:14px;color:#333;line-height:1.6;'>{body_text.replace(chr(10), '<br>')}</div>"
    if not body_text:
        # Strip HTML tags for plain text fallback
        import re
        body_text = re.sub(r'<[^>]+>', '', body_html)

    try:
        from src.services.email_reminder import get_email_service
        email_svc = get_email_service()
        if not email_svc.configured:
            return jsonify({"error": "Email service is not configured. Set up RESEND_API_KEY or SMTP settings."}), 400

        sent = email_svc._send_email(to_email, subject, body_html, body_text, from_name=company_name, reply_to=company_email or None)
        if sent:
            # Log the activity on the client timeline if client_id provided
            if client_id:
                conn_note = None
                try:
                    conn_note = db.get_connection()
                    cursor = conn_note.cursor()
                    cursor.execute("""
                        INSERT INTO client_notes (client_id, company_id, note, created_at)
                        VALUES (%s, %s, %s, NOW())
                    """, (client_id, company_id, f"📧 Email sent: {subject}"))
                    conn_note.commit()
                except Exception:
                    if conn_note:
                        conn_note.rollback()
                finally:
                    if conn_note:
                        db.return_connection(conn_note)
            return jsonify({"success": True, "message": "Email sent successfully"})
        else:
            return jsonify({"error": "Failed to send email. Check your email configuration."}), 500
    except Exception as e:
        print(f"[CRM-EMAIL] Error sending email: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/crm/send-bulk-email", methods=["POST"])
@login_required
@subscription_required
def crm_send_bulk_email():
    """Send a bulk email to multiple customers from the CRM."""
    db = get_database()
    company_id = session['company_id']
    data = request.get_json() or {}

    recipients = data.get('recipients') or []  # list of {email, name, client_id}
    subject = (data.get('subject') or '').strip()
    body_html = (data.get('body_html') or '').strip()
    body_text = (data.get('body_text') or '').strip()
    segment = data.get('segment')  # optional: 'all', 'vip', 'loyal', 'dormant', 'new', 'regular'

    if not subject:
        return jsonify({"error": "Subject is required"}), 400
    if not body_html and not body_text:
        return jsonify({"error": "Email body is required"}), 400

    # If segment provided, fetch recipients from DB
    if segment and not recipients:
        conn_seg = None
        try:
            conn_seg = db.get_connection()
            from psycopg2.extras import RealDictCursor
            cursor = conn_seg.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, name, email FROM clients
                WHERE company_id = %s AND email IS NOT NULL AND email != ''
            """, (company_id,))
            all_clients = cursor.fetchall()
            recipients = [{"email": c["email"], "name": c["name"], "client_id": c["id"]} for c in all_clients]
        except Exception as e:
            return jsonify({"error": f"Failed to fetch recipients: {e}"}), 500
        finally:
            if conn_seg:
                db.return_connection(conn_seg)

    if not recipients:
        return jsonify({"error": "No recipients provided or found"}), 400

    # Filter out empty emails
    recipients = [r for r in recipients if (r.get('email') or '').strip()]
    if not recipients:
        return jsonify({"error": "No valid email addresses found"}), 400

    company = db.get_company(company_id)
    company_name = company.get('company_name', 'BookedForYou') if company else 'BookedForYou'
    company_email = (company.get('email') or company.get('business_email') or '').strip() if company else ''

    if not body_html:
        body_html = f"<div style='font-family:sans-serif;font-size:14px;color:#333;line-height:1.6;'>{body_text.replace(chr(10), '<br>')}</div>"
    if not body_text:
        import re
        body_text = re.sub(r'<[^>]+>', '', body_html)

    try:
        from src.services.email_reminder import get_email_service
        email_svc = get_email_service()
        if not email_svc.configured:
            return jsonify({"error": "Email service is not configured"}), 400

        sent_count = 0
        failed_count = 0
        for r in recipients:
            to = (r.get('email') or '').strip()
            if not to:
                continue
            # Personalize: replace {{name}} with customer name
            name = r.get('name') or 'Customer'
            personalized_html = body_html.replace('{{name}}', name)
            personalized_text = body_text.replace('{{name}}', name)
            try:
                ok = email_svc._send_email(to, subject, personalized_html, personalized_text, from_name=company_name, reply_to=company_email or None)
                if ok:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1

        return jsonify({
            "success": True,
            "sent": sent_count,
            "failed": failed_count,
            "total": len(recipients),
            "message": f"Sent {sent_count} of {len(recipients)} emails"
        })
    except Exception as e:
        print(f"[CRM-BULK-EMAIL] Error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# Outbound Calls — Lost Job Callback
# ============================================

@app.route("/api/call-logs/<int:call_log_id>/callback", methods=["POST"])
@login_required
def trigger_lost_job_callback(call_log_id):
    """Trigger an AI callback to a lost job caller. Gated by OUTBOUND_CALLS_ENABLED."""
    from src.services.outbound_caller import is_outbound_enabled, initiate_lost_job_callback

    if not is_outbound_enabled():
        return jsonify({"error": "Outbound calls are not enabled"}), 403

    db = get_database()
    company_id = session.get('company_id')

    # Fetch the call log
    conn = None
    try:
        conn = db.get_connection()
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT * FROM call_logs WHERE id = %s AND company_id = %s",
            (call_log_id, company_id),
        )
        log = cursor.fetchone()
    except Exception as e:
        print(f"[ERROR] Fetching call log for callback: {e}")
        return jsonify({"error": "Failed to fetch call log"}), 500
    finally:
        if conn:
            db.return_connection(conn)

    if not log:
        return jsonify({"error": "Call log not found"}), 404

    log = dict(log)
    if not log.get("phone_number"):
        return jsonify({"error": "No phone number on this call log"}), 400

    result = initiate_lost_job_callback(
        to_number=log["phone_number"],
        company_id=company_id,
        call_log_id=call_log_id,
        caller_name=log.get("caller_name", ""),
        lost_job_reason=log.get("lost_job_reason", ""),
        ai_summary=log.get("ai_summary", ""),
    )

    if result.get("success"):
        return jsonify(result)
    else:
        return jsonify(result), 500


@app.route("/api/outbound-calls/enabled", methods=["GET"])
@login_required
def outbound_calls_enabled():
    """Check if outbound calling feature is enabled (for UI feature gating)."""
    from src.services.outbound_caller import is_outbound_enabled
    return jsonify({"enabled": is_outbound_enabled()})


@app.route("/telnyx/outbound-voice", methods=["POST"])
def telnyx_outbound_voice():
    """
    Telnyx TeXML webhook for outbound calls.
    When the outbound call connects, Telnyx POSTs here and we return TeXML
    to connect the call to our media stream — same as inbound calls but with
    outbound context parameters passed via query string.
    """
    # Context passed via query params from outbound_caller.py
    company_id = request.args.get("company_id", "")
    call_log_id = request.args.get("call_log_id", "")
    call_type = request.args.get("call_type", "lost_job_callback")
    caller_name = request.args.get("caller_name", "")
    lost_reason = request.args.get("lost_reason", "")
    ai_summary = request.args.get("ai_summary", "")
    to_number = request.form.get("To", "") or request.args.get("To", "")

    ws_url = config.WS_PUBLIC_URL

    print(f"📞 [OUTBOUND] Call connected — company={company_id}, call_log={call_log_id}, to={to_number}")

    twiml = VoiceResponse()
    with twiml.connect() as connect:
        stream = connect.stream(url=ws_url)
        stream.parameter(name="From", value=to_number)
        stream.parameter(name="CompanyId", value=company_id)
        stream.parameter(name="CallType", value=call_type or "lost_job_callback")
        stream.parameter(name="CallLogId", value=call_log_id)
        stream.parameter(name="CallerName", value=caller_name)
        stream.parameter(name="LostReason", value=lost_reason)
        stream.parameter(name="AISummary", value=ai_summary)

    return Response(str(twiml), mimetype="text/xml")


@app.route("/api/notifications", methods=["GET"])
@login_required
def notifications_api():
    """Get recent booking activity for notifications"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Get 'since' parameter (ISO timestamp) to only fetch new notifications
    since = request.args.get('since')
    try:
        limit = min(int(request.args.get('limit', 20)), 50)
    except (ValueError, TypeError):
        limit = 20
    
    conn = None
    try:
        conn = db.get_connection()
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get recent bookings with their status changes
        if since:
            cursor.execute("""
                SELECT b.id, b.service_type, b.status, b.appointment_time, b.created_at,
                       c.name as client_name
                FROM bookings b
                LEFT JOIN clients c ON b.client_id = c.id
                WHERE b.company_id = %s AND b.created_at > %s
                ORDER BY b.created_at DESC
                LIMIT %s
            """, (company_id, since, limit))
        else:
            # Get recent activity from last 24 hours
            cursor.execute("""
                SELECT b.id, b.service_type, b.status, b.appointment_time, b.created_at,
                       c.name as client_name
                FROM bookings b
                LEFT JOIN clients c ON b.client_id = c.id
                WHERE b.company_id = %s AND b.created_at > NOW() - INTERVAL '24 hours'
                ORDER BY b.created_at DESC
                LIMIT %s
            """, (company_id, limit))
        
        rows = cursor.fetchall()
        
        notifications = []
        for row in rows:
            status = row['status'] or 'scheduled'
            
            # Determine notification type and message
            if status == 'cancelled':
                notif_type = 'cancelled'
                message = f"Job cancelled: {row['service_type'] or 'Appointment'}"
            elif status == 'completed':
                notif_type = 'completed'
                message = f"Job completed: {row['service_type'] or 'Appointment'}"
            elif status == 'rescheduled':
                notif_type = 'rescheduled'
                message = f"Job rescheduled: {row['service_type'] or 'Appointment'}"
            else:
                notif_type = 'new_booking'
                message = f"New booking: {row['service_type'] or 'Appointment'}"
            
            notifications.append({
                'id': row['id'],
                'type': notif_type,
                'message': message,
                'client_name': row['client_name'] or 'Unknown',
                'appointment_time': row['appointment_time'].isoformat() if row['appointment_time'] else None,
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'metadata': {'booking_id': row['id']}
            })
        
        # Also fetch owner notifications from the notifications table
        try:
            owner_notifs = db.get_owner_notifications(company_id, limit=limit)
            for n in owner_notifs:
                notifications.append({
                    'id': f"n_{n['id']}",
                    'type': n['type'],
                    'message': n['message'],
                    'client_name': (n.get('metadata') or {}).get('employee_name', ''),
                    'appointment_time': None,
                    'created_at': n['created_at'].isoformat() if n.get('created_at') else None,
                    'metadata': n.get('metadata') or {}
                })
            # Sort all notifications by created_at descending
            notifications.sort(key=lambda x: x.get('created_at') or '', reverse=True)
            notifications = notifications[:limit]
        except Exception as e2:
            print(f"[WARNING] Could not fetch owner notifications: {e2}")

        return jsonify({
            'notifications': notifications,
            'count': len(notifications)
        })
        
    except Exception as e:
        print(f"[ERROR] Failed to get notifications: {e}")
        return jsonify({'notifications': [], 'count': 0})
    finally:
        if conn:
            db.return_connection(conn)


@app.route("/api/employee/notifications", methods=["GET"])
@employee_login_required
def employee_notifications_api():
    """Get notifications for the logged-in employee"""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    db = get_database()

    try:
        limit = min(int(request.args.get('limit', 20)), 50)
    except (ValueError, TypeError):
        limit = 20

    notifs = db.get_employee_notifications(employee_id, company_id, limit=limit)
    notifications = []
    for n in notifs:
        notifications.append({
            'id': n['id'],
            'type': n['type'],
            'message': n['message'],
            'metadata': n.get('metadata') or {},
            'created_at': n['created_at'].isoformat() if n.get('created_at') else None
        })

    return jsonify({'notifications': notifications, 'count': len(notifications)})


@app.route("/api/employee/emergency/<int:booking_id>/accept", methods=["POST"])
@employee_login_required
def employee_accept_emergency(booking_id):
    """Employee accepts an emergency job — assigns them and updates status."""
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    db = get_database()

    # Direct lookup — don't fetch all bookings just to find one
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT b.id, b.service_type, b.emergency_status, b.phone_number, b.email,
                   b.address, b.appointment_time, b.urgency,
                   c.name as customer_name, c.phone as client_phone, c.email as client_email
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE b.id = %s AND b.company_id = %s
        """, (booking_id, company_id))
        booking = cursor.fetchone()
    finally:
        db.return_connection(conn)

    if not booking:
        return jsonify({'error': 'Job not found'}), 404
    booking = dict(booking)

    if booking.get('emergency_status') != 'pending_acceptance':
        if booking.get('emergency_status') == 'accepted':
            return jsonify({'error': 'This emergency job has already been accepted by another employee'}), 409
        return jsonify({'error': 'This job is not awaiting acceptance'}), 400

    from datetime import datetime
    try:
        # Atomic update: only succeeds if status is still pending_acceptance
        # This prevents race conditions where two employees accept simultaneously
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE bookings 
                SET emergency_status = 'accepted', 
                    emergency_accepted_by = %s, 
                    emergency_accepted_at = %s
                WHERE id = %s AND emergency_status = 'pending_acceptance'
            """, (employee_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), booking_id))
            conn.commit()
            if cursor.rowcount == 0:
                # Another employee already accepted
                db.return_connection(conn)
                return jsonify({'error': 'This emergency job has already been accepted by another employee'}), 409
        finally:
            db.return_connection(conn)

        # Assign this employee to the job
        db.assign_employee_to_job(booking_id, employee_id)

        employee = db.get_employee(employee_id, company_id=company_id)
        employee_name = employee['name'] if employee else 'An employee'

        # Notify owner that an employee accepted
        db.create_notification(
            company_id=company_id,
            recipient_type='owner',
            recipient_id=0,
            notif_type='emergency_accepted',
            message=f"{employee_name} accepted the emergency job: {booking.get('service_type', 'Emergency')} for {booking.get('customer_name', 'customer')}",
            metadata={'booking_id': booking_id, 'employee_id': employee_id}
        )

        # Send confirmation SMS/email to customer
        try:
            from src.services.sms_reminder import notify_customer, get_or_create_portal_link
            _company = db.get_company(company_id)
            _company_name = _company.get('company_name') if _company else None
            appt_time = booking.get('appointment_time')
            if isinstance(appt_time, str):
                try:
                    appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    appt_time = datetime.now()
            _emerg_email = booking.get('email') or booking.get('client_email')
            _emerg_portal_link = ''
            if _emerg_email and booking.get('client_id') and company_id:
                try:
                    _emerg_portal_link = get_or_create_portal_link(company_id, booking['client_id'])
                except Exception:
                    pass
            notify_customer(
                'booking_confirmation',
                customer_email=_emerg_email,
                customer_phone=booking.get('phone_number') or booking.get('client_phone'),
                appointment_time=appt_time,
                customer_name=booking.get('customer_name', 'Customer'),
                service_type=booking.get('service_type', 'Emergency'),
                company_name=_company_name,
                company_email=(_company.get('email') or '').strip() if _company else None,
                employee_names=[employee_name],
                address=booking.get('address'),
                portal_link=_emerg_portal_link,
            )
        except Exception as e:
            print(f"[WARNING] Could not send emergency confirmation to customer: {e}")

        return jsonify({
            'success': True,
            'message': f'Emergency job accepted. You are now assigned to this job.',
            'booking_id': booking_id
        })
    except Exception as e:
        print(f"[ERROR] Failed to accept emergency job: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to accept job. Please try again.'}), 500


# ── Owner-Employee Messaging ─────────────────────────────────────────

@app.route("/api/messages/conversations", methods=["GET"])
@login_required
def get_conversations():
    """Get all conversation summaries for the owner."""
    from src.utils.ttl_cache import settings_cache
    company_id = session.get('company_id')
    cache_key = ("conversations_summary", company_id)
    cached = settings_cache.get(cache_key)
    if cached is not None:
        return jsonify({'conversations': cached})

    db = get_database()
    summaries = db.get_owner_conversations_summary(company_id)
    for s in summaries:
        if s.get('last_message_at'):
            s['last_message_at'] = s['last_message_at'].isoformat()
    # Cache for 15 seconds — short enough to feel real-time, long enough to absorb rapid polls
    settings_cache.set(cache_key, summaries, ttl_seconds=15)
    return jsonify({'conversations': summaries})


@app.route("/api/messages/<int:employee_id>", methods=["GET"])
@login_required
def get_messages(employee_id):
    """Get conversation between owner and an employee."""
    db = get_database()
    company_id = session.get('company_id')

    # Verify employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404

    try:
        limit = min(int(request.args.get('limit', 50)), 100)
    except (ValueError, TypeError):
        limit = 50
    before_id = request.args.get('before_id', type=int)

    messages = db.get_conversation(company_id, employee_id, limit=limit, before_id=before_id)
    # Mark employee messages as read
    read_count = db.mark_messages_read(company_id, employee_id, 'owner')
    # Invalidate unread cache if any messages were marked read
    if read_count > 0:
        from src.utils.ttl_cache import settings_cache
        settings_cache.invalidate(("unread_msg_counts", company_id))
    for m in messages:
        if m.get('created_at'):
            m['created_at'] = m['created_at'].isoformat()
    return jsonify({'messages': messages})


@app.route("/api/messages/<int:employee_id>", methods=["POST"])
@login_required
@subscription_required
@rate_limit(max_requests=60, window_seconds=60)
def send_message_to_employee(employee_id):
    """Owner sends a message to an employee."""
    db = get_database()
    company_id = session.get('company_id')

    # Verify employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404

    data = request.json or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'Message content is required'}), 400
    if len(content) > 2000:
        return jsonify({'error': 'Message too long (max 2000 chars)'}), 400

    msg = db.send_message(company_id, employee_id, 'owner', content)
    if not msg:
        return jsonify({'error': 'Failed to send message'}), 500

    # Invalidate conversations cache so next poll picks up the new message
    from src.utils.ttl_cache import settings_cache
    settings_cache.invalidate(("conversations_summary", company_id))

    # Create notification for the employee
    employee_name = employee.get('name', 'Employee')
    company = db.get_company(company_id)
    company_name = company.get('business_name', 'Your employer') if company else 'Your employer'
    preview = content[:80] + ('...' if len(content) > 80 else '')
    db.create_notification(
        company_id, 'employee', employee_id, 'new_message',
        f"New message from {company_name}: {preview}",
        {'sender': 'owner'}
    )

    if msg.get('created_at'):
        msg['created_at'] = msg['created_at'].isoformat()
    return jsonify({'message': msg})


@app.route("/api/messages/unread-counts", methods=["GET"])
@login_required
def get_unread_message_counts():
    """Get unread message counts per employee for the owner."""
    from src.utils.ttl_cache import settings_cache
    company_id = session.get('company_id')
    cache_key = ("unread_msg_counts", company_id)
    cached = settings_cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    db = get_database()
    counts = db.get_unread_message_counts(company_id)
    total = sum(counts.values())
    result = {'counts': counts, 'total': total}
    # Cache for 10 seconds — absorbs rapid polls without feeling stale
    settings_cache.set(cache_key, result, ttl_seconds=10)
    return jsonify(result)


@app.route("/api/employee/messages", methods=["GET"])
@employee_login_required
def employee_get_messages():
    """Employee gets their conversation with the owner."""
    db = get_database()
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    try:
        limit = min(int(request.args.get('limit', 50)), 100)
    except (ValueError, TypeError):
        limit = 50
    before_id = request.args.get('before_id', type=int)

    messages = db.get_conversation(company_id, employee_id, limit=limit, before_id=before_id)
    # Mark owner messages as read
    db.mark_messages_read(company_id, employee_id, 'employee')
    for m in messages:
        if m.get('created_at'):
            m['created_at'] = m['created_at'].isoformat()
    return jsonify({'messages': messages})


@app.route("/api/employee/messages", methods=["POST"])
@employee_login_required
@rate_limit(max_requests=60, window_seconds=60)
def employee_send_message():
    """Employee sends a message to the owner."""
    db = get_database()
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    data = request.json or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'Message content is required'}), 400
    if len(content) > 2000:
        return jsonify({'error': 'Message too long (max 2000 chars)'}), 400

    msg = db.send_message(company_id, employee_id, 'employee', content)
    if not msg:
        return jsonify({'error': 'Failed to send message'}), 500

    # Invalidate conversations cache so owner's next poll picks up the new message
    from src.utils.ttl_cache import settings_cache
    settings_cache.invalidate(("conversations_summary", company_id))

    # Create notification for the owner
    employee = db.get_employee(employee_id)
    employee_name = employee.get('name', 'Employee') if employee else 'Employee'
    preview = content[:80] + ('...' if len(content) > 80 else '')
    db.create_notification(
        company_id, 'owner', 0, 'new_message',
        f"New message from {employee_name}: {preview}",
        {'sender': 'employee', 'employee_id': employee_id, 'employee_name': employee_name}
    )

    if msg.get('created_at'):
        msg['created_at'] = msg['created_at'].isoformat()
    return jsonify({'message': msg})


@app.route("/api/employee/messages/unread-count", methods=["GET"])
@employee_login_required
def employee_unread_count():
    """Get unread message count for the employee."""
    db = get_database()
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    count = db.get_employee_unread_count(company_id, employee_id)
    return jsonify({'unread_count': count})


@app.route("/api/employees", methods=["GET", "POST"])
@login_required
@subscription_required
@rate_limit(max_requests=30, window_seconds=60)
def employees_api():
    """Get all employees or create a new employee"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        employees = db.get_all_employees(company_id=company_id)
        return jsonify(employees)
    
    elif request.method == "POST":
        # Check subscription for creating employees
        company = db.get_company(company_id)
        subscription_info = get_subscription_info(company)
        if not subscription_info['is_active']:
            return jsonify({
                "error": "Active subscription required to create employees",
                "subscription_status": "inactive"
            }), 403
        
        data = request.json
        
        # Validate required field: name
        name = data.get('name', '').strip() if data.get('name') else ''
        if not name:
            return jsonify({"error": "Employee name is required"}), 400
        
        # Sanitize optional fields - convert empty strings to None
        phone = data.get('phone', '').strip() if data.get('phone') else None
        email = data.get('email', '').strip() if data.get('email') else None
        trade_specialty = data.get('trade_specialty', '').strip() if data.get('trade_specialty') else None
        # Also check 'specialty' as frontend might send that
        if not trade_specialty:
            trade_specialty = data.get('specialty', '').strip() if data.get('specialty') else None
        
        # Upload image to R2 if it's base64
        image_url = data.get('image_url', '')
        if image_url and image_url.startswith('data:image/'):
            image_url = upload_base64_image_to_r2(image_url, company_id, 'employees')
        
        # Handle weekly_hours_expected - default to 40.0 if not provided or invalid
        try:
            weekly_hours = float(data.get('weekly_hours_expected', 40.0))
            if weekly_hours < 0 or weekly_hours > 168:
                weekly_hours = 40.0
        except (ValueError, TypeError):
            weekly_hours = 40.0
        
        employee_id = db.add_employee(
            name=name,
            phone=phone if phone else None,
            email=email if email else None,
            trade_specialty=trade_specialty if trade_specialty else None,
            image_url=image_url if image_url else None,
            weekly_hours_expected=weekly_hours,
            company_id=company_id
        )
        return jsonify({"id": employee_id, "message": "Employee added"}), 201


def _build_default_work_schedule(company_id):
    """Build a default weekly work schedule from the company's business hours.
    Returns: { 'mon': {'enabled': True, 'start': '08:00', 'end': '18:00'}, ... }
    """
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    biz = settings_mgr.get_business_hours(company_id=company_id)
    start_hour = biz.get('start_hour', 9)
    end_hour = biz.get('end_hour', 17)
    days_open = biz.get('days_open', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    # Normalise to title-case set for lookup
    days_open_set = {d.strip().title() for d in days_open}
    start_str = f'{int(start_hour):02d}:00'
    end_str = f'{int(end_hour):02d}:00'
    day_keys = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    day_full = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    schedule = {}
    for i, d in enumerate(day_keys):
        is_open = day_full[i] in days_open_set
        schedule[d] = {
            'enabled': is_open,
            'start': start_str if is_open else '09:00',
            'end': end_str if is_open else '17:00',
        }
    return schedule


@app.route("/api/employees/work-schedules", methods=["GET"])
@login_required
@subscription_required
def all_employee_work_schedules_api():
    """Get work schedules for all employees (for timetable export)."""
    db = get_database()
    company_id = session.get('company_id')
    employees = db.get_all_employees(company_id=company_id)

    default_schedule = _build_default_work_schedule(company_id)

    result = []
    for emp in employees:
        ws = emp.get('work_schedule') or default_schedule
        result.append({
            'id': emp['id'],
            'name': emp['name'],
            'specialty': emp.get('specialty') or emp.get('trade_specialty') or '',
            'work_schedule': ws,
        })
    return jsonify({"employees": result, "default_schedule": default_schedule})


@app.route("/api/employee/my-work-schedule", methods=["GET"])
@employee_login_required
def employee_my_work_schedule():
    """Employee portal: get own work schedule."""
    db = get_database()
    employee_id = session.get('employee_id')
    company_id = session.get('employee_company_id')
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    work_schedule = employee.get('work_schedule')
    if not work_schedule:
        work_schedule = _build_default_work_schedule(company_id)
    return jsonify({"work_schedule": work_schedule, "weekly_hours_expected": employee.get('weekly_hours_expected', 40.0)})


@app.route("/api/employees/<int:employee_id>", methods=["GET", "PUT", "DELETE"])
@login_required
@subscription_required
def employee_api(employee_id):
    """Get, update or delete a specific employee"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        # Get employee with company_id filter for security
        employee = db.get_employee(employee_id, company_id=company_id)
        if employee:
            # Include portal status
            account = db.get_employee_account_by_employee_id(employee_id)
            if account and account.get('password_set'):
                employee['portal_status'] = 'active'
            elif account:
                employee['portal_status'] = 'invited'
            else:
                employee['portal_status'] = None
            return jsonify(employee)
        return jsonify({"error": "Employee not found"}), 404
    
    elif request.method == "PUT":
        # Verify employee belongs to this company before updating
        employee = db.get_employee(employee_id, company_id=company_id)
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        
        data = request.json
        
        # Upload image to R2 if it's base64
        if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
            data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'employees')
        
        # Sanitize fields
        sanitized_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip()
                # Name is required, don't allow empty
                if key == 'name':
                    if not value:
                        return jsonify({"error": "Employee name is required"}), 400
                    sanitized_data[key] = value
                # Optional fields - convert empty to None
                elif key in ['phone', 'email', 'trade_specialty', 'specialty', 'image_url']:
                    sanitized_data[key] = value if value else None
                else:
                    sanitized_data[key] = value
            elif key == 'weekly_hours_expected':
                # Validate weekly hours
                try:
                    hours = float(value) if value is not None else 40.0
                    if hours < 0 or hours > 168:
                        hours = 40.0
                    sanitized_data[key] = hours
                except (ValueError, TypeError):
                    sanitized_data[key] = 40.0
            else:
                sanitized_data[key] = value
        
        db.update_employee(employee_id, **sanitized_data)
        return jsonify({"message": "Employee updated"})
    
    elif request.method == "DELETE":
        # Verify employee belongs to this company before deleting
        employee = db.get_employee(employee_id, company_id=company_id)
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        
        result = db.delete_employee(employee_id, company_id=company_id)
        if result.get('success'):
            return jsonify({
                "message": "Employee deleted",
                "assignments_removed": result.get('assignments_removed', 0)
            })
        return jsonify({"error": result.get('error', 'Failed to delete employee')}), 500


@app.route("/api/bookings/<int:booking_id>/assign-employee", methods=["POST"])
@login_required
@subscription_required
def assign_employee_to_job_api(booking_id):
    """Assign an employee to a job with availability checking"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.json
    employee_id = data.get('employee_id')
    force_assign = data.get('force', False)  # Allow forcing assignment even with conflicts
    
    if not employee_id:
        return jsonify({"error": "employee_id is required"}), 400
    
    # Convert employee_id to int (may come as string from frontend)
    try:
        employee_id = int(employee_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid employee_id"}), 400
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    # Verify employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    # Check employee availability at the booking time
    appointment_time = booking.get('appointment_time')
    duration_minutes = booking.get('duration_minutes') or 60
    
    availability = db.check_employee_availability(
        employee_id=employee_id,
        appointment_time=appointment_time,
        duration_minutes=duration_minutes,
        company_id=company_id
    )
    
    if not availability['available'] and not force_assign:
        return jsonify({
            "success": False,
            "error": "Employee is not available at this time",
            "conflicts": availability['conflicts'],
            "message": availability['message'],
            "can_force": True  # Allow UI to offer force option
        }), 409  # Conflict status code
    
    result = db.assign_employee_to_job(booking_id, employee_id)
    
    if result['success']:
        # Include warning if forced despite conflicts
        if not availability['available']:
            result['warning'] = f"Employee assigned despite conflicts: {availability['message']}"

        # Update Google Calendar event with new employee info
        try:
            from src.services.google_calendar_oauth import get_company_google_calendar
            calendar_event_id = booking.get('calendar_event_id', '')
            appt_time = booking.get('appointment_time')
            if calendar_event_id and not str(calendar_event_id).startswith('db_') and appt_time:
                gcal = get_company_google_calendar(company_id, db)
                if gcal:
                    job_employees = db.get_job_employees(booking_id, company_id=company_id)
                    employee_names = [f"{w['name']}{' (' + w['trade_specialty'] + ')' if w.get('trade_specialty') else ''}" for w in job_employees]
                    employee_line = f"\nEmployees: {', '.join(employee_names)}" if employee_names else ''
                    customer_name = booking.get('client_name') or booking.get('customer_name') or 'Customer'
                    phone = booking.get('phone_number') or ''
                    address = booking.get('address') or ''
                    duration = booking.get('duration_minutes') or 60
                    desc = (
                        f"Synced from BookedForYou\n"
                        f"Customer: {customer_name}\n"
                        f"Phone: {phone}\n"
                        f"Address: {address}\n"
                        f"Duration: {duration} mins"
                        f"{employee_line}"
                    )
                    attendee_emails = None
                    company = db.get_company(company_id)
                    if company and company.get('gcal_invite_employees'):
                        attendee_emails = [w['email'] for w in job_employees if w.get('email')]
                        if not attendee_emails:
                            attendee_emails = None
                    gcal.reschedule_appointment(
                        calendar_event_id, appt_time,
                        duration_minutes=duration, description=desc,
                        attendee_emails=attendee_emails
                    )
        except Exception as e:
            print(f"[GCAL] Employee assign sync failed (non-critical): {e}")

        # Notify the employee about the job assignment
        try:
            from datetime import datetime as _dt
            appt = booking.get('appointment_time')
            appt_str = appt.strftime('%b %d at %I:%M %p') if hasattr(appt, 'strftime') else str(appt)
            customer_name = booking.get('client_name') or booking.get('customer_name') or 'a customer'
            svc = booking.get('service_type') or 'a job'
            db.create_notification(
                company_id=company_id,
                recipient_type='employee',
                recipient_id=employee_id,
                notif_type='job_assigned',
                message=f"You've been booked for {svc} with {customer_name} on {appt_str}",
                metadata={'booking_id': booking_id, 'service_type': svc,
                          'appointment_time': appt.isoformat() if hasattr(appt, 'isoformat') else str(appt)}
            )
        except Exception as e:
            print(f"[WARNING] Could not notify employee of assignment: {e}")

        return jsonify(result), 201
    else:
        return jsonify(result), 400


@app.route("/api/bookings/<int:booking_id>/remove-employee", methods=["POST"])
@login_required
@subscription_required
def remove_employee_from_job_api(booking_id):
    """Remove an employee from a job"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.json
    employee_id = data.get('employee_id')
    
    if not employee_id:
        return jsonify({"error": "employee_id is required"}), 400
    
    # Convert employee_id to int (may come as string from frontend)
    try:
        employee_id = int(employee_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid employee_id"}), 400
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    success = db.remove_employee_from_job(booking_id, employee_id)
    
    if success:
        # Update Google Calendar event with updated employee info
        try:
            from src.services.google_calendar_oauth import get_company_google_calendar
            calendar_event_id = booking.get('calendar_event_id', '')
            appt_time = booking.get('appointment_time')
            if calendar_event_id and not str(calendar_event_id).startswith('db_') and appt_time:
                gcal = get_company_google_calendar(company_id, db)
                if gcal:
                    job_employees = db.get_job_employees(booking_id, company_id=company_id)
                    employee_names = [f"{w['name']}{' (' + w['trade_specialty'] + ')' if w.get('trade_specialty') else ''}" for w in job_employees]
                    employee_line = f"\nEmployees: {', '.join(employee_names)}" if employee_names else ''
                    customer_name = booking.get('client_name') or booking.get('customer_name') or 'Customer'
                    phone = booking.get('phone_number') or ''
                    address = booking.get('address') or ''
                    duration = booking.get('duration_minutes') or 60
                    desc = (
                        f"Synced from BookedForYou\n"
                        f"Customer: {customer_name}\n"
                        f"Phone: {phone}\n"
                        f"Address: {address}\n"
                        f"Duration: {duration} mins"
                        f"{employee_line}"
                    )
                    attendee_emails = None
                    company = db.get_company(company_id)
                    if company and company.get('gcal_invite_employees'):
                        attendee_emails = [w['email'] for w in job_employees if w.get('email')]
                        if not attendee_emails:
                            attendee_emails = None
                    gcal.reschedule_appointment(
                        calendar_event_id, appt_time,
                        duration_minutes=duration, description=desc,
                        attendee_emails=attendee_emails
                    )
        except Exception as e:
            print(f"[GCAL] Employee remove sync failed (non-critical): {e}")

        return jsonify({"success": True, "message": "Employee removed from job"})
    else:
        return jsonify({"error": "Employee assignment not found"}), 404


@app.route("/api/bookings/<int:booking_id>/employees", methods=["GET"])
@login_required
def get_job_employees_api(booking_id):
    """Get all employees assigned to a job"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    employees = db.get_job_employees(booking_id, company_id=company_id)
    return jsonify(employees)


@app.route("/api/employees/<int:employee_id>/jobs", methods=["GET"])
@login_required
def get_employee_jobs_api(employee_id):
    """Get all jobs assigned to an employee"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    include_completed = request.args.get('include_completed', 'false').lower() == 'true'
    jobs = db.get_employee_jobs(employee_id, include_completed, company_id=company_id)
    
    # Ensure customer_name is set for frontend consistency
    for job in jobs:
        if not job.get('customer_name') and job.get('client_name'):
            job['customer_name'] = job['client_name']
    
    return jsonify(jobs)


@app.route("/api/employees/<int:employee_id>/schedule", methods=["GET"])
@login_required
def get_employee_schedule_api(employee_id):
    """Get employee's schedule"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    schedule = db.get_employee_schedule(employee_id, start_date, end_date)
    return jsonify(schedule)


@app.route("/api/employees/<int:employee_id>/work-schedule", methods=["GET", "PUT"])
@login_required
@subscription_required
def employee_work_schedule_api(employee_id):
    """Get or update an employee's default weekly work schedule.
    Format: { "mon": {"enabled": true, "start": "09:00", "end": "17:00"}, ... }
    """
    db = get_database()
    company_id = session.get('company_id')
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    if request.method == "GET":
        work_schedule = employee.get('work_schedule')
        if not work_schedule:
            work_schedule = _build_default_work_schedule(company_id)
        return jsonify({"work_schedule": work_schedule})

    elif request.method == "PUT":
        data = request.json
        work_schedule = data.get('work_schedule')
        if not work_schedule or not isinstance(work_schedule, dict):
            return jsonify({"error": "work_schedule object required"}), 400
        # Validate structure
        valid_days = {'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'}
        for day, val in work_schedule.items():
            if day not in valid_days:
                return jsonify({"error": f"Invalid day: {day}"}), 400
            if not isinstance(val, dict) or 'enabled' not in val:
                return jsonify({"error": f"Invalid schedule for {day}"}), 400
        # Auto-calculate weekly hours from the schedule
        total_hours = 0.0
        for day_key in valid_days:
            day_data = work_schedule.get(day_key, {})
            if day_data.get('enabled') and day_data.get('start') and day_data.get('end'):
                try:
                    sh, sm = map(int, day_data['start'].split(':'))
                    eh, em = map(int, day_data['end'].split(':'))
                    h = (eh + em / 60) - (sh + sm / 60)
                    if h > 0:
                        total_hours += h
                except (ValueError, TypeError):
                    pass
        total_hours = round(total_hours, 1)
        from psycopg2.extras import Json
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE employees SET work_schedule = %s, weekly_hours_expected = %s, updated_at = NOW() WHERE id = %s AND company_id = %s",
                (Json(work_schedule), total_hours, employee_id, company_id)
            )
            conn.commit()
        finally:
            db.return_connection(conn)
        return jsonify({"success": True, "work_schedule": work_schedule, "weekly_hours_expected": total_hours})


@app.route("/api/employees/hours-this-week", methods=["GET"])
@login_required
def get_employees_hours_this_week_api():
    """Batch: hours worked this week for every employee in the company.

    Returns {"hours": {employee_id: hours_worked}}. Replaces N per-employee requests.
    """
    db = get_database()
    company_id = session.get('company_id')
    try:
        hours_map = db.get_employees_hours_this_week(company_id)
    except AttributeError:
        # Older DB wrapper without batch method — fall back gracefully
        employees = db.get_all_employees(company_id=company_id) or []
        hours_map = {}
        for w in employees:
            try:
                hours_map[w['id']] = db.get_employee_hours_this_week(w['id'])
            except Exception:
                hours_map[w['id']] = 0
    # Keys must be strings for JSON
    return jsonify({"hours": {str(k): v for k, v in hours_map.items()}})


@app.route("/api/employees/<int:employee_id>/hours-this-week", methods=["GET"])
@login_required
def get_employee_hours_this_week_api(employee_id):
    """Get hours worked by employee this week"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    hours = db.get_employee_hours_this_week(employee_id)
    return jsonify({"hours_worked": hours})


@app.route("/api/employees/<int:employee_id>/availability", methods=["GET"])
@login_required
def check_employee_availability_api(employee_id):
    """Check if an employee is available at a specific time"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify employee belongs to this company
    employee = db.get_employee(employee_id, company_id=company_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    appointment_time = request.args.get('appointment_time')
    duration_minutes = request.args.get('duration_minutes', 60, type=int)
    exclude_booking_id = request.args.get('exclude_booking_id', type=int)
    
    if not appointment_time:
        return jsonify({"error": "appointment_time is required"}), 400
    
    availability = db.check_employee_availability(
        employee_id=employee_id,
        appointment_time=appointment_time,
        duration_minutes=duration_minutes,
        exclude_booking_id=exclude_booking_id,
        company_id=company_id
    )
    
    return jsonify(availability)


@app.route("/api/bookings/<int:booking_id>/available-employees", methods=["GET"])
@login_required
def get_available_employees_for_job_api(booking_id):
    """Get all employees who are available for a specific job"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    appointment_time = booking.get('appointment_time')
    duration_minutes = booking.get('duration_minutes', 60)
    
    # Get all employees for this company
    all_employees = db.get_all_employees(company_id=company_id)
    
    # Check availability for each employee
    available_employees = []
    busy_employees = []
    
    for employee in all_employees:
        availability = db.check_employee_availability(
            employee_id=employee['id'],
            appointment_time=appointment_time,
            duration_minutes=duration_minutes,
            exclude_booking_id=booking_id,  # Exclude this booking from conflict check
            company_id=company_id
        )
        
        employee_info = {
            'id': employee['id'],
            'name': employee['name'],
            'phone': employee.get('phone'),
            'trade_specialty': employee.get('trade_specialty'),
            'available': availability['available'],
            'conflicts': availability.get('conflicts', [])
        }
        
        if availability['available']:
            available_employees.append(employee_info)
        else:
            busy_employees.append(employee_info)
    
    return jsonify({
        'available': available_employees,
        'busy': busy_employees,
        'booking_time': appointment_time,
        'duration_minutes': duration_minutes
    })


@app.route("/api/email/send", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)  # Rate limit email sending
def send_email_to_client():
    """Send email to a client"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        data = request.json
        client_id = data.get('client_id')
        to_email = data.get('to_email')
        client_name = data.get('client_name')
        
        if not to_email:
            return jsonify({
                "success": False,
                "error": "No email address provided"
            }), 400
        
        # Get email configuration from environment - prefer SMTP_FROM_EMAIL, fallback to FROM_EMAIL
        from_email = os.getenv('SMTP_FROM_EMAIL') or os.getenv('FROM_EMAIL', 'contact@bookedforyou.ie')
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER', from_email)
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if not smtp_password:
            return jsonify({
                "success": False,
                "error": "Email not configured. Please set SMTP_PASSWORD in .env file"
            }), 500
        
        # Get business name from settings
        from src.services.settings_manager import get_settings_manager
        settings_mgr = get_settings_manager()
        business_settings = settings_mgr.get_business_settings()
        business_name = business_settings.get('business_name', 'Your Business')
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Message from {business_name}'
        msg['From'] = f'{business_name} <{from_email}>'
        msg['To'] = to_email
        
        # Email body
        text_body = f"""
Hello {client_name},

Thank you for choosing {business_name} for your service needs.

We wanted to reach out and see if there's anything we can help you with. Whether you need a quote, want to book a service, or have any questions, we're here to help!

Best regards,
{business_name} Team

---
This is an automated message. Please reply to this email if you need assistance.
        """
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">Hello {client_name},</h2>
        
        <p>Thank you for choosing <strong>{business_name}</strong> for your service needs.</p>
        
        <p>We wanted to reach out and see if there's anything we can help you with. Whether you need a quote, want to book a service, or have any questions, we're here to help!</p>
        
        <div style="margin: 30px 0; padding: 20px; background-color: #f8fafc; border-left: 4px solid #2563eb;">
            <p style="margin: 0;"><strong>Contact us:</strong></p>
            <p style="margin: 5px 0;">📧 Email: {from_email}</p>
            <p style="margin: 5px 0;">📞 Phone: Available in your records</p>
        </div>
        
        <p style="color: #64748b; font-size: 0.9em; margin-top: 30px;">
            Best regards,<br>
            <strong>{business_name} Team</strong>
        </p>
        
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        
        <p style="color: #94a3b8; font-size: 0.8em;">
            This is an automated message. Please reply to this email if you need assistance.
        </p>
    </div>
</body>
</html>
        """
        
        # Attach both plain text and HTML versions
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email via SMTP
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        safe_print(f"[SUCCESS] Email sent successfully to {to_email}")
        
        return jsonify({
            "success": True,
            "message": f"Email sent successfully to {client_name}"
        })
        
    except Exception as e:
        safe_print(f"[ERROR] Error sending email: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/tests/run", methods=["POST"])
@login_required
def run_tests():
    """Run test suite (development only)"""
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({"error": "Not available in production"}), 403
    
    import subprocess
    data = request.json
    test_type = data.get('test_type', 'all')
    
    try:
        # Set environment variable to use UTF-8 encoding for subprocess
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        if test_type == 'datetime':
            result = subprocess.run(
                [sys.executable, 'tests/test_datetime_parser.py'], 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                timeout=10,
                env=env
            )
        else:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/', '-v'], 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                timeout=30,
                env=env
            )
        
        return jsonify({
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr
        })
    except Exception as e:
        return jsonify({"success": False, "output": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
@rate_limit(max_requests=20, window_seconds=60)
def chat():
    """Chat with the AI receptionist"""
    import asyncio
    from src.services.llm_stream import stream_llm, SYSTEM_PROMPT
    from src.services.call_state import create_call_state
    
    data = request.json
    user_message = data.get('message', '')
    conversation = data.get('conversation', [])
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    # Add user message to conversation
    conversation.append({"role": "user", "content": user_message})
    
    # Add system prompt to first message (same as phone calls, with web-specific notes)
    if len(conversation) == 1:
        # Use the EXACT same system prompt as phone calls
        main_prompt = {
            "role": "system",
            "content": SYSTEM_PROMPT + """

[WEB CHAT MODE NOTES:
- You are handling a web chat, NOT a phone call
- DO NOT say things like "calling number" or "I have your number from the call"
- Use slightly longer responses (2-3 sentences OK for web chat)
- Phone number is OPTIONAL for web chat - can book without it if they provide name, date/time, and reason
- All other rules from the main system prompt apply exactly the same]"""
        }
        conversation.insert(0, main_prompt)
    
    # Get response from LLM
    async def get_response():
        response_text = ""
        try:
            # Create per-request call state for web chat
            # Note: Web chat is stateless, so state doesn't persist between requests
            chat_call_state = create_call_state()
            # Don't pass caller_phone since this is web chat
            async for token in stream_llm(conversation, caller_phone=None, call_state=chat_call_state):
                # Filter out special markers that are meant for TTS only
                if token != "<<<FLUSH>>>":
                    response_text += token
            
            # Add debug logging
            print(f"[CHAT] Chat response generated ({len(response_text)} chars): {response_text[:100]}...")
            
            # If response is empty or suspiciously short, add fallback
            if not response_text or len(response_text.strip()) < 5:
                print("⚠️ WARNING: Chat response is empty or too short, using fallback")
                response_text = "I'm here to help. What can I do for you today?"
            
            return response_text
        except Exception as e:
            print(f"[ERROR] Chat error in get_response: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"
    
    # Run async function
    try:
        response = asyncio.run(get_response())
        conversation.append({"role": "assistant", "content": response})
        return jsonify({
            "response": response,
            "conversation": conversation
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/reset", methods=["POST"])
def chat_reset():
    """Reset chat conversation state"""
    # Note: With per-call state, this endpoint is less relevant
    # Each chat request now gets its own CallState
    # This endpoint is kept for backwards compatibility
    return jsonify({"message": "Chat state reset (note: each request now has isolated state)"})


@app.route("/api/finances", methods=["GET"])
@login_required
def get_finances():
    """Get financial overview and stats"""
    try:
        db = get_database()
        company_id = session.get('company_id')
        bookings = db.get_all_bookings(company_id=company_id)
        
        # Calculate revenue metrics
        # A job is considered paid only if payment_status is 'paid'
        paid_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings 
                          if b.get('payment_status') == 'paid')
        unpaid_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings 
                            if b.get('status') != 'cancelled'
                            and b.get('payment_status') != 'paid')
        total_revenue = paid_revenue + unpaid_revenue
        
        # Build transactions list for detailed view
        transactions = []
        for booking in bookings:
            if booking.get('charge') and float(booking.get('charge', 0)) > 0:
                # Get customer name from client (bookings already filtered by company_id)
                customer_name = booking.get('customer_name') or booking.get('client_name')
                if not customer_name and booking.get('client_id'):
                    client = db.get_client(booking['client_id'], company_id=company_id)
                    if client:
                        customer_name = client.get('name')
                
                transactions.append({
                    'id': booking.get('id'),
                    'booking_id': booking.get('id'),
                    'customer_name': customer_name or 'Unknown',
                    'description': booking.get('service_type') or booking.get('service') or 'Service',
                    'amount': float(booking.get('charge', 0)),
                    'status': booking.get('status'),
                    'payment_status': booking.get('payment_status'),
                    'payment_method': booking.get('payment_method'),
                    'date': booking.get('appointment_time'),
                })
        
        # Group by day for chart (include all charged bookings, not just paid)
        from collections import defaultdict
        from datetime import datetime, timedelta
        daily = defaultdict(float)
        for booking in bookings:
            if booking.get('charge') and float(booking.get('charge', 0) or 0) > 0 and booking.get('appointment_time'):
                if booking.get('status') == 'cancelled':
                    continue
                try:
                    appt_time = booking['appointment_time']
                    if isinstance(appt_time, datetime):
                        date = appt_time
                    elif isinstance(appt_time, str):
                        date = datetime.fromisoformat(appt_time.replace('Z', '+00:00'))
                    else:
                        continue
                    day_key = date.strftime('%Y-%m-%d')
                    daily[day_key] += float(booking.get('charge', 0) or 0)
                except Exception:
                    pass
        
        # Sort chronologically and apply range filter
        all_daily = [{"day": k, "revenue": v} for k, v in sorted(daily.items())]
        
        chart_range = request.args.get('range', 'year')
        now = datetime.now()
        if chart_range == 'month':
            cutoff = (now - timedelta(days=30)).strftime('%Y-%m-%d')
            daily_revenue = [d for d in all_daily if d['day'] >= cutoff]
        elif chart_range == 'all':
            daily_revenue = all_daily
        else:  # 'year' default
            cutoff = (now - timedelta(days=365)).strftime('%Y-%m-%d')
            daily_revenue = [d for d in all_daily if d['day'] >= cutoff]
        
        # Calculate materials costs
        from psycopg2.extras import RealDictCursor as _RDC
        total_materials_cost = 0
        materials_by_booking = {}
        try:
            conn = db.get_connection()
            try:
                cur = conn.cursor(cursor_factory=_RDC)
                cur.execute("SELECT booking_id, SUM(total_cost) as cost FROM job_materials WHERE company_id = %s GROUP BY booking_id", (company_id,))
                for row in cur.fetchall():
                    materials_by_booking[row['booking_id']] = float(row['cost'] or 0)
                    total_materials_cost += float(row['cost'] or 0)
                cur.close()
            finally:
                db.return_connection(conn)
        except Exception:
            pass  # Table might not exist yet

        gross_profit = total_revenue - total_materials_cost
        profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

        # Calculate total refunds/credit notes
        total_refunds = 0
        try:
            conn_cn = db.get_connection()
            try:
                cur_cn = conn_cn.cursor(cursor_factory=_RDC)
                cur_cn.execute("SELECT COALESCE(SUM(amount), 0) as total FROM credit_notes WHERE company_id = %s", (company_id,))
                row_cn = cur_cn.fetchone()
                total_refunds = float(row_cn['total'] or 0) if row_cn else 0
                cur_cn.close()
            finally:
                db.return_connection(conn_cn)
        except Exception:
            pass  # Table might not exist yet

        # Adjust revenue figures for refunds
        paid_revenue = paid_revenue - total_refunds

        # Include manual revenue entries
        manual_revenue = 0
        try:
            conn_re = db.get_connection()
            try:
                cur_re = conn_re.cursor(cursor_factory=_RDC)
                cur_re.execute("SELECT COALESCE(SUM(amount), 0) as total FROM revenue_entries WHERE company_id = %s", (company_id,))
                row_re = cur_re.fetchone()
                manual_revenue = float(row_re['total'] or 0) if row_re else 0
                cur_re.close()
            finally:
                db.return_connection(conn_re)
        except Exception:
            pass  # Table might not exist yet

        paid_revenue = paid_revenue + manual_revenue
        total_revenue = paid_revenue + unpaid_revenue
        gross_profit = total_revenue - total_materials_cost
        profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

        # Add materials_cost to each transaction
        for t in transactions:
            t['materials_cost'] = materials_by_booking.get(t['id'], 0)
            t['profit'] = t['amount'] - t['materials_cost']

        return jsonify({
            "total_revenue": total_revenue,
            "paid_revenue": paid_revenue,
            "unpaid_revenue": unpaid_revenue,
            "pending_revenue": unpaid_revenue,
            "completed_revenue": paid_revenue,
            "manual_revenue": round(manual_revenue, 2),
            "total_materials_cost": round(total_materials_cost, 2),
            "total_refunds": round(total_refunds, 2),
            "gross_profit": round(gross_profit, 2),
            "profit_margin": round(profit_margin, 1),
            "daily_revenue": daily_revenue,
            "monthly_revenue": daily_revenue,
            "transactions": transactions
        })
    except Exception as e:
        print(f"Finances error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/finances/mark-paid", methods=["POST"])
@login_required
@subscription_required
def mark_bookings_paid():
    """Bulk mark past bookings as paid.
    
    Body: { "scope": "all" | "today" | "week" }
    - all: all past bookings
    - today: bookings from today and earlier
    - week: bookings from this week (Mon-Sun) and earlier
    """
    from datetime import datetime, timedelta
    
    db = get_database()
    company_id = session.get('company_id')
    data = request.json or {}
    scope = data.get('scope', 'all')
    
    if scope not in ('all', 'today', 'week'):
        return jsonify({"error": "Invalid scope. Use 'all', 'today', or 'week'."}), 400
    
    try:
        now = datetime.now()
        
        if scope == 'today':
            cutoff = now.replace(hour=23, minute=59, second=59, microsecond=0)
        elif scope == 'week':
            # End of current week (Sunday 23:59)
            days_until_sunday = 6 - now.weekday()
            cutoff = (now + timedelta(days=days_until_sunday)).replace(hour=23, minute=59, second=59, microsecond=0)
        else:
            cutoff = now
        
        bookings = db.get_all_bookings(company_id=company_id)
        updated = 0
        
        for booking in bookings:
            # Skip cancelled or already paid
            if booking.get('status') == 'cancelled':
                continue
            if booking.get('payment_status') == 'paid':
                continue
            # Skip bookings with no charge
            if not booking.get('charge') or float(booking.get('charge', 0) or 0) <= 0:
                continue
            
            appt_time = booking.get('appointment_time')
            if not appt_time:
                continue
            
            # Parse appointment time
            if isinstance(appt_time, str):
                try:
                    appt_time = datetime.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    continue
            elif hasattr(appt_time, 'replace'):
                appt_time = appt_time.replace(tzinfo=None)
            
            # Only mark past bookings (up to cutoff)
            if appt_time <= cutoff:
                try:
                    db.update_booking(booking['id'], company_id=company_id,
                                      payment_status='paid',
                                      payment_method='manual')
                    updated += 1
                except Exception as e:
                    print(f"[MARK_PAID] Failed to update booking {booking['id']}: {e}")
        
        scope_label = {'all': 'all past', 'today': "today's and earlier", 'week': "this week's and earlier"}
        return jsonify({
            "success": True,
            "updated": updated,
            "message": f"Marked {updated} {scope_label[scope]} booking(s) as paid"
        })
    except Exception as e:
        print(f"[MARK_PAID] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



# ============================================
# EXPENSES API
# ============================================

@app.route("/api/expenses", methods=["GET"])
@login_required
def get_expenses():
    """Get all expenses for the company"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM expenses WHERE company_id = %s ORDER BY date DESC",
            (company_id,)
        )
        expenses = cur.fetchall()
        cur.close()
        # Convert Decimal to float for JSON
        for e in expenses:
            e['amount'] = float(e.get('amount', 0) or 0)
        return jsonify(expenses)
    except Exception as ex:
        import traceback; traceback.print_exc()
        return jsonify([])
    finally:
        db.return_connection(conn)


@app.route("/api/expenses", methods=["POST"])
@login_required
@subscription_required
def create_expense():
    """Create a new expense"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        return jsonify({"error": "Amount is required and must be positive"}), 400
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO expenses (company_id, amount, category, description, vendor, date,
                                  receipt_url, is_recurring, recurring_frequency, tax_deductible, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            company_id, float(amount), data.get('category', 'other'),
            data.get('description', ''), data.get('vendor', ''),
            data.get('date', None), data.get('receipt_url'),
            data.get('is_recurring', False), data.get('recurring_frequency'),
            data.get('tax_deductible', True), data.get('notes', '')
        ))
        expense = cur.fetchone()
        conn.commit()
        cur.close()
        expense['amount'] = float(expense.get('amount', 0) or 0)
        return jsonify(expense), 201
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
@login_required
@subscription_required
def update_expense(expense_id):
    """Update an expense"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id FROM expenses WHERE id = %s AND company_id = %s", (expense_id, company_id))
        if not cur.fetchone():
            cur.close()
            return jsonify({"error": "Expense not found"}), 404
        fields = []
        values = []
        for key in ['amount', 'category', 'description', 'vendor', 'date',
                     'receipt_url', 'is_recurring', 'recurring_frequency', 'tax_deductible', 'notes']:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])
        if not fields:
            return jsonify({"error": "No fields to update"}), 400
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([expense_id, company_id])
        cur.execute(f"UPDATE expenses SET {', '.join(fields)} WHERE id = %s AND company_id = %s RETURNING *", values)
        expense = cur.fetchone()
        conn.commit()
        cur.close()
        expense['amount'] = float(expense.get('amount', 0) or 0)
        return jsonify(expense)
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_expense(expense_id):
    """Delete an expense"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM expenses WHERE id = %s AND company_id = %s", (expense_id, company_id))
        conn.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# REVENUE ENTRIES (INCOME LEDGER) API
# ============================================

@app.route("/api/revenue-entries", methods=["GET"])
@login_required
def get_revenue_entries():
    """Get all manual revenue entries for the company"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM revenue_entries WHERE company_id = %s ORDER BY date DESC, created_at DESC",
            (company_id,)
        )
        entries = cur.fetchall()
        cur.close()
        for e in entries:
            e['amount'] = float(e.get('amount', 0) or 0)
        return jsonify(entries)
    except Exception as ex:
        import traceback; traceback.print_exc()
        return jsonify([])
    finally:
        db.return_connection(conn)


@app.route("/api/revenue-entries", methods=["POST"])
@login_required
@subscription_required
def create_revenue_entry():
    """Create a new manual revenue entry"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        return jsonify({"error": "Amount is required and must be positive"}), 400
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO revenue_entries (company_id, amount, category, description,
                                         payment_method, date, notes, booking_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            company_id, float(amount), data.get('category', 'other'),
            data.get('description', ''), data.get('payment_method', 'cash'),
            data.get('date', None), data.get('notes', ''),
            data.get('booking_id') or None
        ))
        entry = cur.fetchone()
        conn.commit()
        cur.close()
        entry['amount'] = float(entry.get('amount', 0) or 0)
        return jsonify(entry), 201
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/revenue-entries/<int:entry_id>", methods=["PUT"])
@login_required
@subscription_required
def update_revenue_entry(entry_id):
    """Update a revenue entry"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id FROM revenue_entries WHERE id = %s AND company_id = %s", (entry_id, company_id))
        if not cur.fetchone():
            cur.close()
            return jsonify({"error": "Entry not found"}), 404
        fields = []
        values = []
        for key in ['amount', 'category', 'description', 'payment_method', 'date', 'notes', 'booking_id']:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key] if data[key] != '' else None)
        if not fields:
            return jsonify({"error": "No fields to update"}), 400
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([entry_id, company_id])
        cur.execute(f"UPDATE revenue_entries SET {', '.join(fields)} WHERE id = %s AND company_id = %s RETURNING *", values)
        entry = cur.fetchone()
        conn.commit()
        cur.close()
        entry['amount'] = float(entry.get('amount', 0) or 0)
        return jsonify(entry)
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/revenue-entries/<int:entry_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_revenue_entry(entry_id):
    """Delete a revenue entry"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM revenue_entries WHERE id = %s AND company_id = %s", (entry_id, company_id))
        conn.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# QUOTES / ESTIMATES API
# ============================================

@app.route("/api/quotes", methods=["GET"])
@login_required
def get_quotes():
    """Get all quotes for the company"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT q.*, c.name as client_name, c.phone as client_phone, c.email as client_email
            FROM quotes q
            LEFT JOIN clients c ON q.client_id = c.id
            WHERE q.company_id = %s
            ORDER BY q.created_at DESC
        """, (company_id,))
        quotes = cur.fetchall()
        cur.close()
        for q in quotes:
            for f in ['subtotal', 'tax_rate', 'tax_amount', 'total']:
                q[f] = float(q.get(f, 0) or 0)
        return jsonify(quotes)
    except Exception as ex:
        import traceback; traceback.print_exc()
        return jsonify([])
    finally:
        db.return_connection(conn)


@app.route("/api/quotes", methods=["POST"])
@login_required
@subscription_required
def create_quote():
    """Create a new quote/estimate"""
    import json
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    
    # Generate quote number
    company = db.get_company(company_id)
    prefix = company.get('invoice_prefix', 'INV') if company else 'INV'
    next_num = int(company.get('invoice_next_number', 1) or 1)
    quote_number = f"QTE-{next_num:04d}"
    
    line_items = data.get('line_items', [])
    tax_rate = float(data.get('tax_rate', company.get('tax_rate', 0) or 0))
    subtotal = sum(float(item.get('amount', 0)) * float(item.get('quantity', 1)) for item in line_items)
    tax_amount = round(subtotal * tax_rate / 100, 2)
    total = round(subtotal + tax_amount, 2)
    
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO quotes (company_id, client_id, quote_number, title, description,
                                line_items, subtotal, tax_rate, tax_amount, total,
                                status, valid_until, notes, source_booking_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            company_id, data.get('client_id'), quote_number,
            data.get('title', ''), data.get('description', ''),
            json.dumps(line_items), subtotal, tax_rate, tax_amount, total,
            'draft', data.get('valid_until'), data.get('notes', ''),
            data.get('booking_id') or None
        ))
        quote = cur.fetchone()
        conn.commit()
        cur.close()
        for f in ['subtotal', 'tax_rate', 'tax_amount', 'total']:
            quote[f] = float(quote.get(f, 0) or 0)
        return jsonify(quote), 201
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/quotes/<int:quote_id>", methods=["PUT"])
@login_required
@subscription_required
def update_quote(quote_id):
    """Update a quote"""
    import json
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM quotes WHERE id = %s AND company_id = %s", (quote_id, company_id))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            return jsonify({"error": "Quote not found"}), 404
        
        line_items = data.get('line_items', existing.get('line_items', []))
        if isinstance(line_items, str):
            line_items = json.loads(line_items)
        
        company = db.get_company(company_id)
        tax_rate = float(data.get('tax_rate', existing.get('tax_rate', 0) or 0))
        subtotal = sum(float(item.get('amount', 0)) * float(item.get('quantity', 1)) for item in line_items)
        tax_amount = round(subtotal * tax_rate / 100, 2)
        total = round(subtotal + tax_amount, 2)
        
        cur.execute("""
            UPDATE quotes SET client_id = %s, title = %s, description = %s,
                line_items = %s, subtotal = %s, tax_rate = %s, tax_amount = %s, total = %s,
                status = %s, valid_until = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND company_id = %s RETURNING *
        """, (
            data.get('client_id', existing.get('client_id')),
            data.get('title', existing.get('title', '')),
            data.get('description', existing.get('description', '')),
            json.dumps(line_items), subtotal, tax_rate, tax_amount, total,
            data.get('status', existing.get('status', 'draft')),
            data.get('valid_until', existing.get('valid_until')),
            data.get('notes', existing.get('notes', '')),
            quote_id, company_id
        ))
        quote = cur.fetchone()
        conn.commit()
        cur.close()
        for f in ['subtotal', 'tax_rate', 'tax_amount', 'total']:
            quote[f] = float(quote.get(f, 0) or 0)
        return jsonify(quote)
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/quotes/<int:quote_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_quote(quote_id):
    """Delete a quote"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM quotes WHERE id = %s AND company_id = %s", (quote_id, company_id))
        conn.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/quotes/<int:quote_id>/convert", methods=["POST"])
@login_required
@subscription_required
def convert_quote_to_job(quote_id):
    """Convert an accepted quote into a booking/job"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM quotes WHERE id = %s AND company_id = %s", (quote_id, company_id))
        quote = cur.fetchone()
        if not quote:
            cur.close()
            return jsonify({"error": "Quote not found"}), 404
        
        appointment_time = data.get('appointment_time')
        if not appointment_time:
            return jsonify({"error": "appointment_time is required"}), 400
        
        duration_minutes = data.get('duration_minutes', 60)
        employee_ids = data.get('employee_ids', [])
        auto_assign_employee = data.get('auto_assign_employee', False)
        notes = data.get('notes', '')

        # Create booking from quote
        cur.execute("""
            INSERT INTO bookings (company_id, client_id, appointment_time, service_type,
                                  charge, status, payment_status, address, duration_minutes, notes, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, 'scheduled', 'unpaid', %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
        """, (
            company_id, quote.get('client_id'), appointment_time,
            quote.get('title', 'Service'), float(quote.get('total', 0)),
            data.get('address', ''), duration_minutes, notes
        ))
        booking = cur.fetchone()
        booking_id = booking['id']

        # Assign employees if provided
        if employee_ids:
            for wid in employee_ids:
                cur.execute("""
                    INSERT INTO employee_assignments (booking_id, employee_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, (booking_id, wid))
        elif auto_assign_employee:
            # Auto-assign: find first available employee
            try:
                all_employees = db.get_all_employees(company_id=company_id)
                for w in all_employees:
                    try:
                        from src.services.calendar_tools import check_employee_availability
                        avail = check_employee_availability(db, company_id, w['id'], appointment_time, duration_minutes)
                        if avail.get('available'):
                            cur.execute("""
                                INSERT INTO employee_assignments (booking_id, employee_id)
                                VALUES (%s, %s) ON CONFLICT DO NOTHING
                            """, (booking_id, w['id']))
                            break
                    except Exception:
                        pass
            except Exception:
                pass
        
        # Mark quote as converted
        cur.execute("""
            UPDATE quotes SET status = 'converted', converted_booking_id = %s,
                              accepted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND company_id = %s
        """, (booking_id, quote_id, company_id))
        
        conn.commit()
        cur.close()
        return jsonify({"success": True, "booking_id": booking_id})
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/quotes/<int:quote_id>/send", methods=["POST"])
@login_required
@subscription_required
def send_quote_sms(quote_id):
    """Send quote to customer — email first, SMS fallback"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT q.*, c.name as client_name, c.phone as client_phone, c.email as client_email FROM quotes q LEFT JOIN clients c ON q.client_id = c.id WHERE q.id = %s AND q.company_id = %s", (quote_id, company_id))
        quote = cur.fetchone()
        if not quote:
            cur.close()
            return jsonify({"error": "Quote not found"}), 404

        email = (quote.get('client_email') or '').strip() or None
        phone = (quote.get('client_phone') or '').strip() or None
        if not email and not phone:
            cur.close()
            return jsonify({"error": "Customer has no email or phone number on file"}), 400

        company = db.get_company(company_id)
        company_name = company.get('company_name', '') or company.get('business_name', '') or 'Our Company' if company else 'Our Company'

        # Build quote content
        items_summary = ""
        if quote.get('line_items'):
            items = quote['line_items'] if isinstance(quote['line_items'], list) else []
            if items:
                items_summary = "\n".join([f"• {i.get('description', 'Item')}: €{float(i.get('amount', 0)) * int(i.get('quantity', 1)):.2f}" for i in items[:5]])
                if len(items) > 5:
                    items_summary += f"\n  ...and {len(items) - 5} more items"

        total = float(quote.get('total', 0))
        title = quote.get('title', f"Quote #{quote.get('quote_number', '')}")
        valid_until = ""
        if quote.get('valid_until'):
            from datetime import datetime
            try:
                vu = datetime.fromisoformat(str(quote['valid_until']).replace('Z', '+00:00'))
                valid_until = f"\nValid until: {vu.strftime('%d %b %Y')}"
            except Exception:
                pass

        sent_via = None

        # Auto-generate accept token so the customer can accept via link
        import secrets as _secrets_q
        accept_token = quote.get('accept_token')
        if not accept_token:
            accept_token = _secrets_q.token_urlsafe(32)
            cur.execute("UPDATE quotes SET accept_token = %s WHERE id = %s AND company_id = %s",
                        (accept_token, quote_id, company_id))
            conn.commit()
        public_url = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
        accept_link = f"{public_url}/quote/accept/{accept_token}"

        # Try email first
        if email:
            try:
                from src.services.email_reminder import get_email_service
                email_svc = get_email_service()
                if email_svc.configured:
                    # Set reply-to so customer replies go to the business
                    email_svc.company_reply_to = (company.get('email') or '').strip() if company else None
                    items_html = ""
                    if quote.get('line_items'):
                        li = quote['line_items'] if isinstance(quote['line_items'], list) else []
                        if li:
                            rows = "".join([f"<tr><td style='padding:8px;border-bottom:1px solid #f1f5f9'>{i.get('description','Item')}</td><td style='padding:8px;text-align:center;border-bottom:1px solid #f1f5f9'>{i.get('quantity',1)}</td><td style='padding:8px;text-align:right;border-bottom:1px solid #f1f5f9'>€{float(i.get('amount',0))*int(i.get('quantity',1)):.2f}</td></tr>" for i in li])
                            items_html = f"<table style='width:100%;border-collapse:collapse;margin:16px 0'><thead><tr><th style='padding:8px;text-align:left;border-bottom:2px solid #e2e8f0;color:#64748b;font-size:12px'>Item</th><th style='padding:8px;text-align:center;border-bottom:2px solid #e2e8f0;color:#64748b;font-size:12px'>Qty</th><th style='padding:8px;text-align:right;border-bottom:2px solid #e2e8f0;color:#64748b;font-size:12px'>Amount</th></tr></thead><tbody>{rows}</tbody></table>"

                    vu_html = f"<p style='color:#94a3b8;font-size:13px'>Valid until: {vu.strftime('%d %b %Y')}</p>" if quote.get('valid_until') else ""
                    html = f"""<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:560px;margin:0 auto'>
<h2 style='color:#1e293b;margin:0 0 4px'>Quote from {company_name}</h2>
<p style='color:#64748b;margin:0 0 20px'>{title}</p>
{items_html}
<div style='text-align:right;padding:12px 0;border-top:2px solid #6366f1'>
<span style='font-size:14px;color:#64748b'>Total: </span>
<span style='font-size:22px;font-weight:700;color:#1e293b'>€{total:.2f}</span>
</div>
{vu_html}
{f"<p style='color:#475569;font-size:13px;background:#f8fafc;padding:10px;border-radius:6px'>{quote.get('notes')}</p>" if quote.get('notes') else ""}
<div style='text-align:center;margin:24px 0'>
<a href='{accept_link}' style='display:inline-block;background:#10b981;color:white;text-decoration:none;padding:14px 40px;font-size:16px;font-weight:700;border-radius:8px;box-shadow:0 4px 12px rgba(16,185,129,0.3)'>Accept Quote</a>
</div>
<p style='color:#94a3b8;font-size:12px;text-align:center'>Or reply to this email if you have any questions.</p>
</div>"""
                    txt = f"Quote from {company_name}\n\n{title}\n{items_summary}\n\nTotal: €{total:.2f}{valid_until}\n\nPlease reply to accept or decline."
                    subject = f"Quote from {company_name} — {title} (€{total:.2f})"
                    email_svc._send_email(email, subject, html, txt, company_name)
                    sent_via = 'email'
            except Exception as ex:
                safe_print(f"[QUOTE] Email send failed, falling back to SMS: {ex}")

        # Fallback to SMS if email didn't work
        if not sent_via and phone:
            try:
                msg = f"Hi {quote.get('client_name', 'there')}, here's your quote from {company_name}:\n\n{title}\n{items_summary}\n\nTotal: €{total:.2f}{valid_until}\n\nPlease reply to accept or decline."
                from src.services.sms_reminder import get_sms_service
                sms_service = get_sms_service()
                if not sms_service.client:
                    safe_print(f"[QUOTE] SMS fallback failed: Twilio not configured")
                else:
                    twilio_number = company.get('twilio_phone_number') if company else None
                    if not twilio_number:
                        safe_print(f"[QUOTE] SMS fallback failed: No Twilio phone number for company {company_id}")
                    else:
                        safe_print(f"[QUOTE] Sending quote SMS to {phone} from {twilio_number}")
                        sms_service.client.messages.create(body=msg, from_=twilio_number, to=phone)
                        sent_via = 'sms'
                        safe_print(f"[QUOTE] Quote sent via SMS to {phone}")
            except Exception as sms_ex:
                safe_print(f"[QUOTE] SMS send failed: {sms_ex}")
                import traceback; traceback.print_exc()

        if not sent_via:
            cur.close()
            # Build specific error message
            if not email and not phone:
                err = "Customer has no email or phone number on file"
            elif email and not phone:
                err = f"Email send failed to {email} and no phone number for SMS fallback"
            elif phone and not email:
                err = f"SMS send failed to {phone}. Check the phone number format (must include country code, e.g. +353...)"
            else:
                err = f"Both email ({email}) and SMS ({phone}) failed. Check contact details."
            return jsonify({"error": err}), 503

        # Update status and pipeline_stage to sent if still draft
        if quote.get('status') == 'draft':
            cur.execute("UPDATE quotes SET status = 'sent', pipeline_stage = 'sent', sent_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND company_id = %s", (quote_id, company_id))
            # Also update linked booking status to 'quote_sent' if still pending
            source_booking_id = quote.get('source_booking_id')
            if source_booking_id:
                cur.execute("UPDATE bookings SET status = 'quote_sent', updated_at = CURRENT_TIMESTAMP WHERE id = %s AND company_id = %s AND status = 'pending'", (source_booking_id, company_id))
            conn.commit()

        cur.close()
        return jsonify({"success": True, "sent_to": email if sent_via == 'email' else phone, "sent_via": sent_via})
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# TAX SETTINGS API
# ============================================

@app.route("/api/settings/tax", methods=["GET"])
@login_required
def get_tax_settings():
    """Get tax/invoice configuration"""
    db = get_database()
    company_id = session.get('company_id')
    company = db.get_company(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404
    return jsonify({
        "tax_rate": float(company.get('tax_rate', 0) or 0),
        "tax_id_number": company.get('tax_id_number', ''),
        "tax_id_label": company.get('tax_id_label', 'VAT'),
        "invoice_prefix": company.get('invoice_prefix', 'INV'),
        "invoice_next_number": int(company.get('invoice_next_number', 1) or 1),
        "invoice_payment_terms_days": int(company.get('invoice_payment_terms_days', 14) or 14),
        "invoice_footer_note": company.get('invoice_footer_note', ''),
        "default_expense_categories": company.get('default_expense_categories', ''),
    })


@app.route("/api/settings/tax", methods=["POST"])
@login_required
@subscription_required
def update_tax_settings():
    """Update tax/invoice configuration"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        fields = []
        values = []
        allowed = ['tax_rate', 'tax_id_number', 'tax_id_label', 'invoice_prefix',
                    'invoice_next_number', 'invoice_payment_terms_days',
                    'invoice_footer_note', 'default_expense_categories']
        for key in allowed:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])
        if fields:
            values.append(company_id)
            cur = conn.cursor()
            cur.execute(f"UPDATE companies SET {', '.join(fields)} WHERE id = %s", values)
            conn.commit()
            cur.close()
        return jsonify({"success": True})
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# P&L REPORT API
# ============================================

@app.route("/api/reports/pnl", methods=["GET"])
@login_required
def get_pnl_report():
    """Get Profit & Loss report"""
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    db = get_database()
    company_id = session.get('company_id')
    period = request.args.get('period', 'year')  # month, quarter, year, all
    
    now = datetime.now()
    if period == 'month':
        start_date = now.replace(day=1)
    elif period == 'quarter':
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        start_date = now.replace(month=quarter_month, day=1)
    elif period == 'all':
        start_date = datetime(2020, 1, 1)
    else:
        start_date = now.replace(month=1, day=1)
    
    try:
        bookings = db.get_all_bookings(company_id=company_id)
        
        # Revenue from bookings
        revenue_by_month = defaultdict(float)
        total_revenue = 0
        for b in bookings:
            if b.get('status') == 'cancelled':
                continue
            charge = float(b.get('charge', 0) or 0)
            if charge <= 0:
                continue
            appt = b.get('appointment_time')
            if not appt:
                continue
            if isinstance(appt, str):
                try:
                    appt = datetime.fromisoformat(appt.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    continue
            if appt < start_date:
                continue
            month_key = appt.strftime('%Y-%m')
            revenue_by_month[month_key] += charge
            total_revenue += charge
        
        # Materials costs
        conn = db.get_connection()
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT jm.booking_id, SUM(jm.total_cost) as cost
                FROM job_materials jm
                WHERE jm.company_id = %s
                GROUP BY jm.booking_id
            """, (company_id,))
            materials_by_booking = {}
            total_materials = 0
            for row in cur.fetchall():
                materials_by_booking[row['booking_id']] = float(row['cost'] or 0)
                total_materials += float(row['cost'] or 0)
            
            # Expenses
            cur.execute("""
                SELECT category, SUM(amount) as total, COUNT(*) as count
                FROM expenses
                WHERE company_id = %s AND date >= %s
                GROUP BY category
                ORDER BY total DESC
            """, (company_id, start_date.date()))
            expense_categories = []
            total_expenses = 0
            for row in cur.fetchall():
                amt = float(row['total'] or 0)
                expense_categories.append({
                    'category': row['category'],
                    'total': amt,
                    'count': row['count']
                })
                total_expenses += amt
            
            # Monthly expense breakdown
            cur.execute("""
                SELECT TO_CHAR(date, 'YYYY-MM') as month, SUM(amount) as total
                FROM expenses
                WHERE company_id = %s AND date >= %s
                GROUP BY TO_CHAR(date, 'YYYY-MM')
                ORDER BY month
            """, (company_id, start_date.date()))
            expenses_by_month = {}
            for row in cur.fetchall():
                expenses_by_month[row['month']] = float(row['total'] or 0)
            
            # Mileage costs
            cur.execute("""
                SELECT SUM(cost) as total
                FROM mileage_logs
                WHERE company_id = %s AND date >= %s
            """, (company_id, start_date.date()))
            mileage_row = cur.fetchone()
            total_mileage = float(mileage_row['total'] or 0) if mileage_row and mileage_row['total'] else 0

            cur.execute("""
                SELECT TO_CHAR(date, 'YYYY-MM') as month, SUM(cost) as total
                FROM mileage_logs
                WHERE company_id = %s AND date >= %s
                GROUP BY TO_CHAR(date, 'YYYY-MM')
                ORDER BY month
            """, (company_id, start_date.date()))
            mileage_by_month = {}
            for row in cur.fetchall():
                mileage_by_month[row['month']] = float(row['total'] or 0)

            # Credit notes / refunds (reduce revenue)
            cur.execute("""
                SELECT SUM(amount) as total
                FROM credit_notes
                WHERE company_id = %s AND created_at >= %s
            """, (company_id, start_date))
            cn_row = cur.fetchone()
            total_credits = float(cn_row['total'] or 0) if cn_row and cn_row['total'] else 0

            cur.execute("""
                SELECT TO_CHAR(created_at, 'YYYY-MM') as month, SUM(amount) as total
                FROM credit_notes
                WHERE company_id = %s AND created_at >= %s
                GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                ORDER BY month
            """, (company_id, start_date))
            credits_by_month = {}
            for row in cur.fetchall():
                credits_by_month[row['month']] = float(row['total'] or 0)

            # Manual revenue entries (income ledger)
            manual_revenue_total = 0
            try:
                cur.execute("""
                    SELECT SUM(amount) as total
                    FROM revenue_entries
                    WHERE company_id = %s AND date >= %s
                """, (company_id, start_date.date()))
                mr_row = cur.fetchone()
                manual_revenue_total = float(mr_row['total'] or 0) if mr_row and mr_row['total'] else 0
            except Exception:
                pass

            manual_revenue_by_month = {}
            try:
                cur.execute("""
                    SELECT TO_CHAR(date, 'YYYY-MM') as month, SUM(amount) as total
                    FROM revenue_entries
                    WHERE company_id = %s AND date >= %s
                    GROUP BY TO_CHAR(date, 'YYYY-MM')
                    ORDER BY month
                """, (company_id, start_date.date()))
                for row in cur.fetchall():
                    manual_revenue_by_month[row['month']] = float(row['total'] or 0)
            except Exception:
                pass
            
            # Monthly materials breakdown (from bookings appointment_time)
            materials_by_month = defaultdict(float)
            for b in bookings:
                if b.get('status') == 'cancelled':
                    continue
                bid = b.get('id')
                mat_cost = materials_by_booking.get(bid, 0)
                if mat_cost <= 0:
                    continue
                appt = b.get('appointment_time')
                if not appt:
                    continue
                if isinstance(appt, str):
                    try:
                        appt = datetime.fromisoformat(appt.replace('Z', '+00:00')).replace(tzinfo=None)
                    except Exception:
                        continue
                if appt < start_date:
                    continue
                materials_by_month[appt.strftime('%Y-%m')] += mat_cost
            
            cur.close()
        finally:
            db.return_connection(conn)
        
        # Build monthly P&L (expenses + materials + mileage combined, credits reduce revenue, manual revenue adds to it)
        all_months = sorted(set(list(revenue_by_month.keys()) + list(expenses_by_month.keys()) + list(materials_by_month.keys()) + list(mileage_by_month.keys()) + list(credits_by_month.keys()) + list(manual_revenue_by_month.keys())))
        monthly_pnl = []
        for month in all_months:
            rev = revenue_by_month.get(month, 0) + manual_revenue_by_month.get(month, 0) - credits_by_month.get(month, 0)
            mat = materials_by_month.get(month, 0)
            exp = expenses_by_month.get(month, 0)
            mil = mileage_by_month.get(month, 0)
            total_cost = mat + exp + mil
            gross = rev - mat
            monthly_pnl.append({
                'month': month,
                'revenue': round(rev, 2),
                'materials': round(mat, 2),
                'gross_profit': round(gross, 2),
                'expenses': round(exp, 2),
                'mileage': round(mil, 2),
                'total_costs': round(total_cost, 2),
                'net_profit': round(rev - total_cost, 2)
            })
        
        total_all_costs = total_materials + total_expenses + total_mileage
        total_revenue_combined = total_revenue + manual_revenue_total
        net_revenue = total_revenue_combined - total_credits
        gross_profit = net_revenue - total_materials
        net_profit = net_revenue - total_all_costs
        
        return jsonify({
            "period": period,
            "start_date": start_date.strftime('%Y-%m-%d'),
            "total_revenue": round(total_revenue_combined, 2),
            "booking_revenue": round(total_revenue, 2),
            "manual_revenue": round(manual_revenue_total, 2),
            "total_credits": round(total_credits, 2),
            "net_revenue": round(net_revenue, 2),
            "total_materials": round(total_materials, 2),
            "gross_profit": round(gross_profit, 2),
            "total_expenses": round(total_expenses, 2),
            "total_mileage": round(total_mileage, 2),
            "total_costs": round(total_all_costs, 2),
            "net_profit": round(net_profit, 2),
            "profit_margin": round((net_profit / net_revenue * 100) if net_revenue > 0 else 0, 1),
            "gross_margin": round((gross_profit / net_revenue * 100) if net_revenue > 0 else 0, 1),
            "expense_categories": expense_categories,
            "monthly_pnl": monthly_pnl,
        })
    except Exception as e:
        print(f"P&L error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================
# INVOICE AGING API
# ============================================

@app.route("/api/finances/aging", methods=["GET"])
@login_required
def get_invoice_aging():
    """Get accounts receivable aging report"""
    from datetime import datetime, timedelta
    
    db = get_database()
    company_id = session.get('company_id')
    
    try:
        bookings = db.get_all_bookings(company_id=company_id)
        now = datetime.now()
        
        buckets = {
            'current': {'label': 'Current (0-14 days)', 'total': 0, 'count': 0, 'items': []},
            '15_30': {'label': '15-30 days', 'total': 0, 'count': 0, 'items': []},
            '31_60': {'label': '31-60 days', 'total': 0, 'count': 0, 'items': []},
            '61_90': {'label': '61-90 days', 'total': 0, 'count': 0, 'items': []},
            'over_90': {'label': '90+ days', 'total': 0, 'count': 0, 'items': []},
        }
        
        for b in bookings:
            if b.get('status') == 'cancelled':
                continue
            if b.get('payment_status') == 'paid':
                continue
            charge = float(b.get('charge', 0) or 0)
            if charge <= 0:
                continue
            
            # Use invoice_due_date if set, otherwise appointment_time
            due_date = b.get('invoice_due_date') or b.get('appointment_time')
            if not due_date:
                continue
            if isinstance(due_date, str):
                try:
                    due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    continue
            elif hasattr(due_date, 'replace'):
                due_date = due_date.replace(tzinfo=None)
            
            days_overdue = (now - due_date).days
            if days_overdue < 0:
                days_overdue = 0
            
            # Get customer name
            customer_name = b.get('customer_name') or b.get('client_name', 'Unknown')
            if not customer_name or customer_name == 'Unknown':
                if b.get('client_id'):
                    client = db.get_client(b['client_id'], company_id=company_id)
                    if client:
                        customer_name = client.get('name', 'Unknown')
            
            item = {
                'booking_id': b['id'],
                'customer_name': customer_name,
                'service': b.get('service_type', 'Service'),
                'amount': charge,
                'date': b.get('appointment_time').isoformat() if hasattr(b.get('appointment_time'), 'isoformat') else str(b.get('appointment_time', '')),
                'days_overdue': days_overdue,
            }
            
            if days_overdue <= 14:
                bucket = 'current'
            elif days_overdue <= 30:
                bucket = '15_30'
            elif days_overdue <= 60:
                bucket = '31_60'
            elif days_overdue <= 90:
                bucket = '61_90'
            else:
                bucket = 'over_90'
            
            buckets[bucket]['total'] += charge
            buckets[bucket]['count'] += 1
            buckets[bucket]['items'].append(item)
        
        # Round totals
        for b in buckets.values():
            b['total'] = round(b['total'], 2)
        
        total_outstanding = sum(b['total'] for b in buckets.values())
        
        return jsonify({
            "buckets": buckets,
            "total_outstanding": round(total_outstanding, 2),
        })
    except Exception as e:
        print(f"Aging error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================
# JOB SUB-TASKS API
# ============================================

@app.route("/api/bookings/<int:booking_id>/tasks", methods=["GET"])
@login_required
def get_job_tasks(booking_id):
    """Get sub-tasks for a job"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM job_tasks
            WHERE booking_id = %s AND company_id = %s
            ORDER BY sort_order, created_at
        """, (booking_id, company_id))
        tasks = cur.fetchall()
        cur.close()
        for t in tasks:
            t['estimated_cost'] = float(t.get('estimated_cost', 0) or 0)
        return jsonify(tasks)
    except Exception as ex:
        import traceback; traceback.print_exc()
        return jsonify([])
    finally:
        db.return_connection(conn)


@app.route("/api/bookings/<int:booking_id>/tasks", methods=["POST"])
@login_required
@subscription_required
def create_job_task(booking_id):
    """Add a sub-task to a job"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    
    # Verify booking belongs to company
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO job_tasks (booking_id, company_id, title, description, status,
                                   estimated_cost, assigned_employee_id, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            booking_id, company_id, data.get('title', ''),
            data.get('description', ''), data.get('status', 'pending'),
            float(data.get('estimated_cost', 0) or 0),
            data.get('assigned_employee_id'), data.get('sort_order', 0)
        ))
        task = cur.fetchone()
        conn.commit()
        cur.close()
        task['estimated_cost'] = float(task.get('estimated_cost', 0) or 0)
        return jsonify(task), 201
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/bookings/<int:booking_id>/tasks/<int:task_id>", methods=["PUT"])
@login_required
@subscription_required
def update_job_task(booking_id, task_id):
    """Update a sub-task"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        fields = []
        values = []
        for key in ['title', 'description', 'status', 'estimated_cost', 'assigned_employee_id', 'sort_order']:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])
        if not fields:
            return jsonify({"error": "No fields to update"}), 400
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([task_id, booking_id, company_id])
        cur.execute(f"UPDATE job_tasks SET {', '.join(fields)} WHERE id = %s AND booking_id = %s AND company_id = %s RETURNING *", values)
        task = cur.fetchone()
        if not task:
            cur.close()
            return jsonify({"error": "Task not found"}), 404
        conn.commit()
        cur.close()
        task['estimated_cost'] = float(task.get('estimated_cost', 0) or 0)
        return jsonify(task)
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/bookings/<int:booking_id>/tasks/<int:task_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_job_task(booking_id, task_id):
    """Delete a sub-task"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM job_tasks WHERE id = %s AND booking_id = %s AND company_id = %s", (task_id, booking_id, company_id))
        conn.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# PURCHASE ORDERS API
# ============================================

@app.route("/api/purchase-orders", methods=["GET"])
@login_required
def get_purchase_orders():
    """Get all purchase orders"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM purchase_orders
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (company_id,))
        orders = cur.fetchall()
        cur.close()
        for o in orders:
            o['total'] = float(o.get('total', 0) or 0)
        return jsonify(orders)
    except Exception as ex:
        import traceback; traceback.print_exc()
        return jsonify([])
    finally:
        db.return_connection(conn)


@app.route("/api/purchase-orders", methods=["POST"])
@login_required
@subscription_required
def create_purchase_order():
    """Create a purchase order (optionally auto-generated from job materials)"""
    import json
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    
    # Generate PO number
    company = db.get_company(company_id)
    prefix = company.get('invoice_prefix', 'INV') if company else 'INV'
    
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get next PO number
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 as next_num FROM purchase_orders WHERE company_id = %s", (company_id,))
        next_num = cur.fetchone()['next_num']
        po_number = f"PO-{next_num:04d}"
        
        items = data.get('items', [])
        total = sum(float(i.get('unit_price', 0)) * float(i.get('quantity', 1)) for i in items)
        
        cur.execute("""
            INSERT INTO purchase_orders (company_id, po_number, supplier, items, total,
                                         status, notes, booking_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            company_id, po_number, data.get('supplier', ''),
            json.dumps(items), total, 'draft',
            data.get('notes', ''), data.get('booking_id')
        ))
        order = cur.fetchone()
        conn.commit()
        cur.close()
        order['total'] = float(order.get('total', 0) or 0)
        return jsonify(order), 201
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/purchase-orders/<int:po_id>", methods=["PUT"])
@login_required
@subscription_required
def update_purchase_order(po_id):
    """Update a purchase order status"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        fields = []
        values = []
        for key in ['supplier', 'status', 'notes']:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])
        if 'items' in data:
            import json
            fields.append("items = %s")
            values.append(json.dumps(data['items']))
            total = sum(float(i.get('unit_price', 0)) * float(i.get('quantity', 1)) for i in data['items'])
            fields.append("total = %s")
            values.append(total)
        if not fields:
            return jsonify({"error": "No fields to update"}), 400
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.extend([po_id, company_id])
        cur.execute(f"UPDATE purchase_orders SET {', '.join(fields)} WHERE id = %s AND company_id = %s RETURNING *", values)
        order = cur.fetchone()
        if not order:
            cur.close()
            return jsonify({"error": "Purchase order not found"}), 404
        conn.commit()
        cur.close()
        order['total'] = float(order.get('total', 0) or 0)
        return jsonify(order)
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/purchase-orders/<int:po_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_purchase_order(po_id):
    """Delete a purchase order"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM purchase_orders WHERE id = %s AND company_id = %s", (po_id, company_id))
        conn.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/purchase-orders/generate-from-job/<int:booking_id>", methods=["POST"])
@login_required
@subscription_required
def generate_po_from_job(booking_id):
    """Auto-generate a purchase order from a job's materials"""
    import json
    db = get_database()
    company_id = session.get('company_id')
    
    booking = db.get_booking(booking_id, company_id=company_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get job materials
        cur.execute("SELECT * FROM job_materials WHERE booking_id = %s AND company_id = %s", (booking_id, company_id))
        materials = cur.fetchall()
        if not materials:
            cur.close()
            return jsonify({"error": "No materials on this job to create a PO from"}), 400
        
        # Group by supplier from catalog
        items = []
        supplier_name = ''
        for m in materials:
            # Try to get supplier from catalog
            if m.get('material_id'):
                cur.execute("SELECT supplier FROM materials WHERE id = %s AND company_id = %s", (m['material_id'], company_id))
                cat_mat = cur.fetchone()
                if cat_mat and cat_mat.get('supplier'):
                    supplier_name = cat_mat['supplier']
            items.append({
                'name': m['name'],
                'unit_price': float(m.get('unit_price', 0) or 0),
                'quantity': float(m.get('quantity', 1) or 1),
                'unit': m.get('unit', 'each'),
            })
        
        total = sum(i['unit_price'] * i['quantity'] for i in items)
        
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 as next_num FROM purchase_orders WHERE company_id = %s", (company_id,))
        next_num = cur.fetchone()['next_num']
        po_number = f"PO-{next_num:04d}"
        
        customer_name = booking.get('customer_name') or booking.get('client_name') or 'Unknown'
        service = booking.get('service_type') or 'Service'
        
        cur.execute("""
            INSERT INTO purchase_orders (company_id, po_number, supplier, items, total,
                                         status, notes, booking_id)
            VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s)
            RETURNING *
        """, (
            company_id, po_number, supplier_name,
            json.dumps(items), total,
            f"Materials for {service} - {customer_name}",
            booking_id
        ))
        order = cur.fetchone()
        conn.commit()
        cur.close()
        order['total'] = float(order.get('total', 0) or 0)
        return jsonify(order), 201
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# MILEAGE TRACKING API
# ============================================

@app.route("/api/mileage", methods=["GET"])
@login_required
def get_mileage_logs():
    """Get mileage logs"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM mileage_logs WHERE company_id = %s ORDER BY date DESC", (company_id,))
        logs = cur.fetchall()
        cur.close()
        for l in logs:
            l['distance_km'] = float(l.get('distance_km', 0) or 0)
            l['cost'] = float(l.get('cost', 0) or 0)
        return jsonify(logs)
    except Exception:
        return jsonify([])
    finally:
        db.return_connection(conn)


@app.route("/api/mileage", methods=["POST"])
@login_required
@subscription_required
def create_mileage_log():
    """Log a mileage trip"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    distance = float(data.get('distance_km', 0) or 0)
    if distance <= 0:
        return jsonify({"error": "Distance is required"}), 400
    rate = float(data.get('rate_per_km', 0.338) or 0.338)  # Irish Revenue rate
    cost = round(distance * rate, 2)
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO mileage_logs (company_id, date, from_location, to_location,
                                      distance_km, rate_per_km, cost, booking_id, driver_name, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (company_id, data.get('date'), data.get('from_location', ''),
              data.get('to_location', ''), distance, rate, cost,
              data.get('booking_id') or None, data.get('driver_name', ''), data.get('notes', '')))
        log = cur.fetchone()
        conn.commit()
        cur.close()
        log['distance_km'] = float(log.get('distance_km', 0) or 0)
        log['cost'] = float(log.get('cost', 0) or 0)
        return jsonify(log), 201
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/mileage/<int:log_id>", methods=["PUT"])
@login_required
@subscription_required
def update_mileage_log(log_id):
    """Update a mileage log"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    distance = float(data.get('distance_km', 0) or 0)
    if distance <= 0:
        return jsonify({"error": "Distance is required"}), 400
    rate = float(data.get('rate_per_km', 0.338) or 0.338)
    cost = round(distance * rate, 2)
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            UPDATE mileage_logs SET date = %s, from_location = %s, to_location = %s,
                distance_km = %s, rate_per_km = %s, cost = %s, driver_name = %s, notes = %s
            WHERE id = %s AND company_id = %s RETURNING *
        """, (data.get('date'), data.get('from_location', ''), data.get('to_location', ''),
              distance, rate, cost, data.get('driver_name', ''), data.get('notes', ''),
              log_id, company_id))
        log = cur.fetchone()
        conn.commit()
        cur.close()
        if not log:
            return jsonify({"error": "Not found"}), 404
        log['distance_km'] = float(log.get('distance_km', 0) or 0)
        log['cost'] = float(log.get('cost', 0) or 0)
        return jsonify(log)
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/mileage/<int:log_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_mileage_log(log_id):
    """Delete a mileage log"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM mileage_logs WHERE id = %s AND company_id = %s", (log_id, company_id))
        conn.commit()
        cur.close()
        return jsonify({"success": True})
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# CREDIT NOTES API
# ============================================

@app.route("/api/credit-notes", methods=["GET"])
@login_required
def get_credit_notes():
    """Get credit notes"""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT cn.*, c.name as client_name
            FROM credit_notes cn
            LEFT JOIN clients c ON cn.client_id = c.id
            WHERE cn.company_id = %s ORDER BY cn.created_at DESC
        """, (company_id,))
        notes = cur.fetchall()
        cur.close()
        for n in notes:
            n['amount'] = float(n.get('amount', 0) or 0)
        return jsonify(notes)
    except Exception:
        return jsonify([])
    finally:
        db.return_connection(conn)


@app.route("/api/credit-notes", methods=["POST"])
@login_required
@subscription_required
def create_credit_note():
    """Create a credit note / refund. Optionally process Stripe refund."""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    amount = float(data.get('amount', 0) or 0)
    if amount <= 0:
        return jsonify({"error": "Amount is required"}), 400
    
    booking_id = data.get('booking_id') or None
    client_id = data.get('client_id') or None
    process_stripe_refund = data.get('stripe_refund', False)
    stripe_refund_id = None
    stripe_refund_error = None
    
    # Attempt Stripe refund if requested
    if process_stripe_refund and booking_id:
        try:
            booking = db.get_booking(booking_id, company_id=company_id)
            if booking:
                company = db.get_company(company_id)
                connected_account_id = company.get('stripe_connect_account_id') if company else None
                session_id = booking.get('stripe_checkout_session_id')
                
                if connected_account_id and session_id:
                    import stripe
                    from src.utils.config import config
                    stripe.api_key = getattr(config, 'STRIPE_SECRET_KEY', None) or os.getenv('STRIPE_SECRET_KEY')
                    
                    if stripe.api_key:
                        # Retrieve the checkout session to get the payment_intent
                        checkout = stripe.checkout.Session.retrieve(
                            session_id, stripe_account=connected_account_id
                        )
                        payment_intent_id = checkout.get('payment_intent')
                        
                        if payment_intent_id:
                            amount_cents = int(amount * 100)
                            refund = stripe.Refund.create(
                                payment_intent=payment_intent_id,
                                amount=amount_cents,
                                stripe_account=connected_account_id
                            )
                            stripe_refund_id = refund.id
                            print(f"[REFUND] Stripe refund {refund.id} created for €{amount} on PI {payment_intent_id}")
                        else:
                            stripe_refund_error = "No payment found for this booking"
                    else:
                        stripe_refund_error = "Stripe not configured"
                else:
                    stripe_refund_error = "No Stripe payment on record for this booking"
        except Exception as e:
            stripe_refund_error = str(e)
            print(f"[REFUND] Stripe refund failed: {e}")
            import traceback; traceback.print_exc()
    
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Generate credit note number
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 as n FROM credit_notes WHERE company_id = %s", (company_id,))
        cn_num = f"CN-{cur.fetchone()['n']:04d}"
        cur.execute("""
            INSERT INTO credit_notes (company_id, credit_note_number, client_id, booking_id,
                                      amount, reason, notes, stripe_refund_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *
        """, (company_id, cn_num, client_id, booking_id,
              amount, data.get('reason', ''), data.get('notes', ''), stripe_refund_id))
        note = cur.fetchone()
        
        # Update booking payment_status if full refund
        if booking_id and amount > 0:
            try:
                booking = db.get_booking(int(booking_id), company_id=company_id)
                if booking:
                    booking_charge = float(booking.get('charge', 0) or 0)
                    # Check total refunds for this booking
                    cur2 = conn.cursor(cursor_factory=RealDictCursor)
                    cur2.execute("SELECT COALESCE(SUM(amount), 0) as total FROM credit_notes WHERE booking_id = %s AND company_id = %s", (booking_id, company_id))
                    total_refunded = float(cur2.fetchone()['total'] or 0)
                    cur2.close()
                    if total_refunded >= booking_charge and booking_charge > 0:
                        db.update_booking(int(booking_id), company_id=company_id, payment_status='refunded')
                        print(f"[REFUND] Booking {booking_id} fully refunded — payment_status set to 'refunded'")
                    elif total_refunded > 0:
                        db.update_booking(int(booking_id), company_id=company_id, payment_status='partial_refund')
                        print(f"[REFUND] Booking {booking_id} partially refunded (€{total_refunded} of €{booking_charge})")
            except Exception as e:
                print(f"[WARNING] Could not update booking payment_status after refund: {e}")
        
        conn.commit()
        cur.close()
        note['amount'] = float(note.get('amount', 0) or 0)
        
        result = dict(note)
        if stripe_refund_id:
            result['stripe_refund_id'] = stripe_refund_id
            result['stripe_refund_status'] = 'success'
        elif stripe_refund_error:
            result['stripe_refund_error'] = stripe_refund_error
            result['stripe_refund_status'] = 'failed'
        
        return jsonify(result), 201
    except Exception as ex:
        conn.rollback()
        return jsonify({"error": str(ex)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/credit-notes/<int:credit_note_id>/refund", methods=["POST"])
@login_required
@subscription_required
def process_credit_note_refund(credit_note_id):
    """Process a Stripe refund for an existing credit note that hasn't been refunded yet."""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM credit_notes WHERE id = %s AND company_id = %s", (credit_note_id, company_id))
        note = cur.fetchone()
        if not note:
            cur.close()
            return jsonify({"error": "Credit note not found"}), 404

        if note.get('stripe_refund_id'):
            cur.close()
            return jsonify({"error": "This credit note has already been refunded via Stripe", "stripe_refund_id": note['stripe_refund_id']}), 400

        booking_id = note.get('booking_id')
        if not booking_id:
            cur.close()
            return jsonify({"error": "No job linked to this credit note — cannot process Stripe refund"}), 400

        booking = db.get_booking(booking_id, company_id=company_id)
        if not booking:
            cur.close()
            return jsonify({"error": "Linked job not found"}), 404

        company = db.get_company(company_id)
        connected_account_id = company.get('stripe_connect_account_id') if company else None
        session_id = booking.get('stripe_checkout_session_id')

        if not connected_account_id or not session_id:
            cur.close()
            return jsonify({"error": "No Stripe payment found for this job. The customer may not have paid via Stripe.", "stripe_refund_status": "failed"}), 400

        import stripe
        from src.utils.config import config
        stripe.api_key = getattr(config, 'STRIPE_SECRET_KEY', None) or os.getenv('STRIPE_SECRET_KEY')

        if not stripe.api_key:
            cur.close()
            return jsonify({"error": "Stripe not configured on server"}), 503

        checkout = stripe.checkout.Session.retrieve(session_id, stripe_account=connected_account_id)
        payment_intent_id = checkout.get('payment_intent')

        if not payment_intent_id:
            cur.close()
            return jsonify({"error": "No payment intent found for this checkout session"}), 400

        amount = float(note.get('amount', 0))
        amount_cents = int(amount * 100)
        refund = stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=amount_cents,
            stripe_account=connected_account_id
        )

        # Update the credit note with the refund ID
        cur.execute("UPDATE credit_notes SET stripe_refund_id = %s WHERE id = %s AND company_id = %s",
                     (refund.id, credit_note_id, company_id))
        conn.commit()
        cur.close()

        return jsonify({
            "success": True,
            "stripe_refund_id": refund.id,
            "stripe_refund_status": "success",
            "amount_refunded": amount
        })
    except Exception as ex:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"error": str(ex), "stripe_refund_status": "failed"}), 500
    finally:
        db.return_connection(conn)


# ============================================
# CUSTOMER STATEMENTS API
# ============================================

@app.route("/api/clients/<int:client_id>/statement", methods=["GET"])
@login_required
def get_customer_statement(client_id):
    """Get a customer statement showing all invoices, payments, and balance"""
    db = get_database()
    company_id = session.get('company_id')
    client = db.get_client(client_id, company_id=company_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
    bookings = db.get_all_bookings(company_id=company_id)
    client_bookings = [b for b in bookings if b.get('client_id') == client_id]
    
    items = []
    total_charged = 0
    total_paid = 0
    
    for b in sorted(client_bookings, key=lambda x: x.get('appointment_time', '') or ''):
        charge = float(b.get('charge', 0) or 0)
        if charge <= 0:
            continue
        is_paid = b.get('payment_status') == 'paid'
        total_charged += charge
        if is_paid:
            total_paid += charge
        items.append({
            'date': str(b.get('appointment_time', '')),
            'description': b.get('service_type', 'Service'),
            'amount': charge,
            'status': 'paid' if is_paid else 'unpaid',
            'booking_id': b.get('id'),
        })
    
    # Get credit notes for this client
    conn = db.get_connection()
    total_credits = 0
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM credit_notes WHERE company_id = %s AND client_id = %s ORDER BY created_at", (company_id, client_id))
        for cn in cur.fetchall():
            amt = float(cn.get('amount', 0) or 0)
            total_credits += amt
            items.append({
                'date': str(cn.get('created_at', '')),
                'description': f"Credit Note {cn.get('credit_note_number', '')} - {cn.get('reason', 'Refund')}",
                'amount': -amt,
                'status': 'credit',
                'booking_id': cn.get('booking_id'),
            })
        cur.close()
    except Exception:
        pass
    finally:
        db.return_connection(conn)
    
    balance = total_charged - total_paid - total_credits
    
    return jsonify({
        "client": {"id": client.get('id'), "name": client.get('name'), "phone": client.get('phone'), "email": client.get('email')},
        "items": items,
        "total_charged": round(total_charged, 2),
        "total_paid": round(total_paid, 2),
        "total_credits": round(total_credits, 2),
        "balance_due": round(balance, 2),
    })


@app.route("/api/calendar/events", methods=["GET"])
def get_calendar_events():
    """Get calendar events (disabled - USE_GOOGLE_CALENDAR = False)"""
    # Google Calendar integration disabled
    return jsonify([])


# ==========================================
# Google Calendar OAuth Integration
# ==========================================

@app.route("/api/google-calendar/status", methods=["GET"])
@login_required
def google_calendar_status():
    """Check if Google Calendar is connected for this company."""
    try:
        from src.services.google_calendar_oauth import get_company_calendar_status
        db = get_database()
        company_id = session.get('company_id')
        status = get_company_calendar_status(company_id, db)
        return jsonify(status)
    except Exception as e:
        safe_print(f"[GCAL] Status check error: {e}")
        return jsonify({'connected': False, 'error': str(e)})


@app.route("/api/google-calendar/connect", methods=["POST"])
@login_required
@subscription_required
def google_calendar_connect():
    """Start the Google Calendar OAuth flow — returns the auth URL."""
    try:
        from src.services.google_calendar_oauth import start_oauth_flow
        company_id = session.get('company_id')
        auth_url = start_oauth_flow(company_id)
        return jsonify({'auth_url': auth_url})
    except ValueError as e:
        safe_print(f"[GCAL] OAuth config error: {e}")
        return jsonify({'error': 'Google Calendar OAuth is not configured on the server'}), 500
    except Exception as e:
        safe_print(f"[GCAL] Connect error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/google-calendar/callback", methods=["GET"])
def google_calendar_callback():
    """OAuth callback from Google — exchanges code for tokens."""
    try:
        from src.services.google_calendar_oauth import handle_oauth_callback
        company_id = request.args.get('state')
        if not company_id:
            return "Missing state parameter", 400

        company_id = int(company_id)
        db = get_database()

        # Build the full authorization response URL
        authorization_response = request.url
        # Ensure it uses https in production (Render terminates TLS at the proxy)
        if config.PUBLIC_URL and config.PUBLIC_URL.startswith('https'):
            authorization_response = authorization_response.replace('http://', 'https://', 1)

        handle_oauth_callback(authorization_response, company_id, db)

        # Bidirectional sync on first connect (non-blocking best-effort)
        try:
            from src.services.google_calendar_oauth import get_company_google_calendar
            gcal = get_company_google_calendar(company_id, db)
            if gcal:
                all_bookings = db.get_all_bookings(company_id=company_id)
                push_synced = 0
                pull_imported = 0
                from datetime import datetime as dt, timedelta as _td
                import re as _re
                now = dt.now()
                sync_cutoff = now - _td(days=30)

                # Build set of known gcal IDs from existing bookings
                known_gcal_ids = set()
                for booking in all_bookings:
                    eid = booking.get('calendar_event_id', '')
                    if eid and not str(eid).startswith('db_'):
                        known_gcal_ids.add(eid)

                # Phase 1: Push DB → Google Calendar
                for booking in all_bookings:
                    if booking.get('status') == 'cancelled':
                        continue
                    is_completed = booking.get('status') == 'completed'
                    appt_time = booking.get('appointment_time')
                    if not appt_time:
                        continue
                    if isinstance(appt_time, str):
                        try:
                            appt_time = dt.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
                        except:
                            continue
                    elif hasattr(appt_time, 'replace'):
                        appt_time = appt_time.replace(tzinfo=None)
                    if appt_time < sync_cutoff:
                        continue
                    customer_name = booking.get('client_name') or booking.get('customer_name') or 'Customer'
                    service = booking.get('service_type') or 'Job'
                    duration = booking.get('duration_minutes', 60)
                    phone = booking.get('phone_number') or ''
                    address = booking.get('address') or ''
                    summary = f"{'✅ ' if is_completed else ''}{service} - {customer_name}"
                    desc = (
                        f"Synced from BookedForYou\n"
                        f"{'Status: COMPLETED\n' if is_completed else ''}"
                        f"Customer: {customer_name}\n"
                        f"Phone: {phone}\n"
                        f"Address: {address}\n"
                        f"Duration: {duration} mins"
                    )
                    existing_event_id = booking.get('calendar_event_id', '')
                    has_real_gcal = existing_event_id and not str(existing_event_id).startswith('db_')
                    if has_real_gcal:
                        # Update existing gcal event (single API call)
                        try:
                            gcal.reschedule_appointment(
                                existing_event_id, appt_time, duration_minutes=duration,
                                description=desc, summary=summary
                            )
                            push_synced += 1
                        except Exception:
                            pass
                    else:
                        # Create new gcal event for any booking in the sync window
                        try:
                            gcal_event = gcal.book_appointment(
                                summary=summary,
                                start_time=appt_time,
                                duration_minutes=duration,
                                description=desc,
                                phone_number=phone
                            )
                            if gcal_event and booking.get('id'):
                                new_id = gcal_event.get('id')
                                db.update_booking(booking['id'], calendar_event_id=new_id, company_id=company_id)
                                if new_id:
                                    known_gcal_ids.add(new_id)
                                push_synced += 1
                        except Exception:
                            pass

                # Phase 2: Pull Google Calendar → DB
                try:
                    gcal_events = gcal.get_future_events(days_ahead=90)
                    from db_scripts.sync_gcal import process_gcal_pull_events
                    records, _skip_count = process_gcal_pull_events(
                        gcal_events, known_gcal_ids, int(company_id), db
                    )
                    for rec in records:
                        try:
                            existing = db.get_booking_by_calendar_event_id(rec['gcal_id'])
                            if existing:
                                known_gcal_ids.add(rec['gcal_id'])
                                continue
                            client_id = db.find_or_create_client(
                                name=rec['customer_name'], phone=rec['phone'] or None,
                                email=rec['import_email'], company_id=int(company_id)
                            )
                            booking_id = db.add_booking(
                                client_id=client_id, calendar_event_id=rec['gcal_id'],
                                appointment_time=rec['start_dt'].strftime('%Y-%m-%d %H:%M:%S'),
                                service_type=rec['service_type'],
                                phone_number=rec['phone'] or None,
                                email=rec['import_email'] if not rec['phone'] else None,
                                company_id=int(company_id), duration_minutes=rec['duration'],
                                address=rec['address'] or None
                            )
                            if booking_id:
                                known_gcal_ids.add(rec['gcal_id'])
                                pull_imported += 1
                        except Exception:
                            pass
                except Exception:
                    pass

                safe_print(f"[GCAL] Initial sync for company {company_id}: pushed={push_synced}, imported={pull_imported}")
        except Exception as sync_err:
            safe_print(f"[GCAL] Initial sync failed (non-critical): {sync_err}")

        # Redirect to settings page with success message
        frontend_url = os.getenv('FRONTEND_URL', config.PUBLIC_URL or 'http://localhost:5173')
        return f"""
        <html><body>
        <script>
            window.opener ? window.opener.postMessage('google-calendar-connected', '*') : null;
            window.location.href = '{frontend_url}/settings?tab=business&gcal=connected';
        </script>
        <p>Google Calendar connected! Redirecting...</p>
        </body></html>
        """
    except Exception as e:
        safe_print(f"[GCAL] Callback error: {e}")
        import traceback
        traceback.print_exc()
        frontend_url = os.getenv('FRONTEND_URL', config.PUBLIC_URL or 'http://localhost:5173')
        return f"""
        <html><body>
        <script>
            window.location.href = '{frontend_url}/settings?tab=business&gcal=error';
        </script>
        <p>Error connecting Google Calendar: {str(e)}</p>
        </body></html>
        """


@app.route("/api/google-calendar/disconnect", methods=["POST"])
@login_required
@subscription_required
def google_calendar_disconnect():
    """Disconnect Google Calendar for this company."""
    try:
        from src.services.google_calendar_oauth import disconnect_google_calendar
        db = get_database()
        company_id = session.get('company_id')
        disconnect_google_calendar(company_id, db)
        return jsonify({'success': True, 'message': 'Google Calendar disconnected'})
    except Exception as e:
        safe_print(f"[GCAL] Disconnect error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/google-calendar/sync", methods=["POST"])
@login_required
@subscription_required
def google_calendar_sync():
    """Bidirectional sync between the database and Google Calendar.

    Phase 1 — DB → Google Calendar (push):
      For each future, non-cancelled DB booking:
        - Has a real gcal event → update it (fixes durations/times).
        - Has only a db_ placeholder or nothing → create a new gcal event.

    Phase 2 — Google Calendar → DB (pull):
      For each future gcal event that is NOT already linked to a DB booking:
        - Parse customer name from the event summary.
        - Calculate duration from event start/end.
        - Create a client (find_or_create_client) and booking in the DB.
    """
    from datetime import datetime as dt

    company_id = session.get('company_id')
    db = get_database()

    try:
        from src.services.google_calendar_oauth import get_company_google_calendar
        gcal = get_company_google_calendar(company_id, db)
        if not gcal:
            return jsonify({'error': 'Google Calendar is not connected'}), 400
    except Exception as e:
        safe_print(f"[GCAL_SYNC] Could not load Google Calendar: {e}")
        return jsonify({'error': 'Google Calendar is not connected'}), 400

    # ── Phase 1: DB → Google Calendar ──────────────────────────────
    all_bookings = db.get_all_bookings(company_id=company_id)
    now = dt.now()
    from datetime import timedelta
    sync_cutoff = now - timedelta(days=30)
    push_created = 0
    push_updated = 0
    push_skipped = 0
    push_errors = 0

    # Build a set of gcal event IDs already linked to DB bookings
    known_gcal_ids = set()

    # Check if employee invites are enabled (once, outside the loop)
    company = db.get_company(company_id)
    invite_employees = company.get('gcal_invite_employees', False) if company else False

    for booking in all_bookings:
        existing_event_id = booking.get('calendar_event_id', '')
        has_real_gcal = existing_event_id and not str(existing_event_id).startswith('db_')
        if has_real_gcal:
            known_gcal_ids.add(existing_event_id)

        if booking.get('status') == 'cancelled':
            push_skipped += 1
            continue

        is_completed = booking.get('status') == 'completed'

        appt_time = booking.get('appointment_time')
        if not appt_time:
            push_skipped += 1
            continue
        if isinstance(appt_time, str):
            try:
                appt_time = dt.fromisoformat(appt_time.replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                push_skipped += 1
                continue
        elif hasattr(appt_time, 'replace'):
            appt_time = appt_time.replace(tzinfo=None)

        # Include future bookings + last 30 days of past bookings (keeps gcal in sync)
        if appt_time < sync_cutoff:
            push_skipped += 1
            continue

        # Skip bookings already synced and not modified since last sync
        if has_real_gcal:
            gcal_synced_at = booking.get('gcal_synced_at')
            updated_at = booking.get('updated_at')
            if gcal_synced_at and updated_at:
                # Normalize both to naive datetimes for comparison
                if hasattr(gcal_synced_at, 'replace'):
                    gcal_synced_at = gcal_synced_at.replace(tzinfo=None)
                if hasattr(updated_at, 'replace'):
                    updated_at = updated_at.replace(tzinfo=None)
                if updated_at <= gcal_synced_at:
                    push_skipped += 1
                    continue

        customer_name = booking.get('client_name') or booking.get('customer_name') or 'Customer'
        service = booking.get('service_type') or 'Job'
        duration = booking.get('duration_minutes', 60)
        phone = booking.get('phone_number') or ''
        address = booking.get('address') or ''
        summary = f"{'✅ ' if is_completed else ''}{service} - {customer_name}"

        # Build employee info for description and attendees
        bid = booking.get('id')
        job_employees = db.get_job_employees(bid, company_id=company_id) if bid else []
        employee_lines = ''
        if job_employees:
            employee_names = [f"{w['name']}{' (' + w['trade_specialty'] + ')' if w.get('trade_specialty') else ''}" for w in job_employees]
            employee_lines = f"\nEmployees: {', '.join(employee_names)}"

        desc = (
            f"Synced from BookedForYou\n"
            f"{'Status: COMPLETED\n' if is_completed else ''}"
            f"Customer: {customer_name}\n"
            f"Phone: {phone}\n"
            f"Address: {address}\n"
            f"Duration: {duration} mins"
            f"{employee_lines}"
        )

        # Build attendee list if employee invites are enabled
        attendee_emails = None
        if invite_employees and job_employees:
            attendee_emails = [w['email'] for w in job_employees if w.get('email')]
            if not attendee_emails:
                attendee_emails = None

        try:
            if has_real_gcal:
                result = gcal.reschedule_appointment(
                    existing_event_id, appt_time, duration_minutes=duration,
                    description=desc, summary=summary,
                    attendee_emails=attendee_emails
                )
                if result is not None:
                    push_updated += 1
                    # Stamp gcal_synced_at so we skip this booking next sync
                    if booking.get('id'):
                        db.stamp_gcal_synced(booking['id'], company_id=company_id)
                else:
                    push_skipped += 1
            else:
                # Create new gcal event for any booking in the sync window
                gcal_event = gcal.book_appointment(
                    summary=summary,
                    start_time=appt_time,
                    duration_minutes=duration,
                    description=desc,
                    phone_number=phone,
                    attendee_emails=attendee_emails
                )
                if gcal_event:
                    new_gcal_id = gcal_event.get('id')
                    if booking.get('id'):
                        db.update_booking(
                            booking['id'],
                            calendar_event_id=new_gcal_id,
                            company_id=company_id
                        )
                        db.stamp_gcal_synced(booking['id'], company_id=company_id)
                    if new_gcal_id:
                        known_gcal_ids.add(new_gcal_id)
                    push_created += 1
        except Exception as e:
            err_str = str(e)
            # Birthday/special event types can't be modified — skip silently
            if 'eventTypeRestriction' in err_str or 'birthday' in err_str.lower():
                safe_print(f"[GCAL_SYNC] Skipping special event type for booking {booking.get('id')}")
                push_skipped += 1
            else:
                safe_print(f"[GCAL_SYNC] Push error booking {booking.get('id')}: {e}")
                push_errors += 1

    # ── Phase 2: Google Calendar → DB (pull) ───────────────────────
    pull_imported = 0
    pull_skipped = 0
    pull_errors = 0

    try:
        gcal_events = gcal.get_future_events(days_ahead=90)
    except Exception as e:
        safe_print(f"[GCAL_SYNC] Could not fetch Google Calendar events: {e}")
        gcal_events = []

    from db_scripts.sync_gcal import process_gcal_pull_events
    records, skip_count = process_gcal_pull_events(
        gcal_events, known_gcal_ids, company_id, db
    )
    pull_skipped += skip_count

    for rec in records:
        try:
            existing = db.get_booking_by_calendar_event_id(rec['gcal_id'])
            if existing:
                known_gcal_ids.add(rec['gcal_id'])
                pull_skipped += 1
                continue

            client_id = db.find_or_create_client(
                name=rec['customer_name'],
                phone=rec['phone'] or None,
                email=rec['import_email'],
                company_id=company_id
            )

            booking_id = db.add_booking(
                client_id=client_id,
                calendar_event_id=rec['gcal_id'],
                appointment_time=rec['start_dt'].strftime('%Y-%m-%d %H:%M:%S'),
                service_type=rec['service_type'],
                phone_number=rec['phone'] or None,
                email=rec['import_email'] if not rec['phone'] else None,
                company_id=company_id,
                duration_minutes=rec['duration'],
                address=rec['address'] or None
            )

            if booking_id:
                known_gcal_ids.add(rec['gcal_id'])
                pull_imported += 1
            else:
                pull_skipped += 1
        except Exception as e:
            if 'UniqueViolation' in type(e).__name__ or 'unique constraint' in str(e).lower():
                pull_skipped += 1
            else:
                safe_print(f"[GCAL_SYNC] Pull error for event {rec['gcal_id']}: {e}")
                pull_errors += 1

    total_errors = push_errors + pull_errors
    safe_print(
        f"[GCAL_SYNC] Company {company_id}: "
        f"push(created={push_created}, updated={push_updated}, skipped={push_skipped}, errors={push_errors}) "
        f"pull(imported={pull_imported}, skipped={pull_skipped}, errors={pull_errors})"
    )

    # Count active jobs without employees assigned (for warning)
    jobs_without_employees = 0
    try:
        all_bookings_check = db.get_all_bookings(company_id=company_id)
        for b in all_bookings_check:
            if b.get('status') in ('completed', 'paid', 'cancelled'):
                continue
            employees = db.get_job_employees(b['id'], company_id=company_id)
            if not employees:
                jobs_without_employees += 1
    except Exception:
        pass

    parts = []
    if push_created:
        parts.append(f"{push_created} pushed to Google")
    if push_updated:
        parts.append(f"{push_updated} updated on Google")
    if pull_imported:
        parts.append(f"{pull_imported} imported from Google")
    if not parts:
        parts.append("Everything already in sync")
    msg = ", ".join(parts)
    if total_errors:
        msg += f" ({total_errors} failed)"

    return jsonify({
        'success': True,
        'push_created': push_created,
        'push_updated': push_updated,
        'pull_imported': pull_imported,
        'errors': total_errors,
        'jobs_without_employees': jobs_without_employees,
        'message': msg
    })


# Global error handlers
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors - API only (frontend on Vercel)"""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    safe_print(f"Internal server error: {e}")
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all uncaught exceptions"""
    safe_print(f"Unhandled exception: {e}")
    return jsonify({"error": "An unexpected error occurred"}), 500


# ==================== ACCOUNTING INTEGRATION ENDPOINTS ====================

@app.route("/api/accounting/status", methods=["GET"])
@login_required
def accounting_status():
    """Get the current accounting integration status."""
    try:
        from src.services.accounting_oauth import get_accounting_status
        db = get_database()
        company_id = session.get('company_id')
        status = get_accounting_status(company_id, db)
        return jsonify(status)
    except Exception as e:
        safe_print(f"[ACCOUNTING] Status error: {e}")
        return jsonify({'provider': 'builtin', 'connected': False}), 200


@app.route("/api/accounting/provider", methods=["POST"])
@login_required
@subscription_required
def accounting_set_provider():
    """Switch accounting provider (builtin, xero, quickbooks, disabled)."""
    try:
        from src.services.accounting_oauth import set_accounting_provider
        db = get_database()
        company_id = session.get('company_id')
        provider = request.json.get('provider', 'builtin')
        set_accounting_provider(company_id, provider, db)
        return jsonify({'success': True, 'provider': provider})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        safe_print(f"[ACCOUNTING] Set provider error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/accounting/xero/connect", methods=["POST"])
@login_required
@subscription_required
def accounting_xero_connect():
    """Start the Xero OAuth flow."""
    try:
        from src.services.accounting_oauth import start_xero_oauth
        company_id = session.get('company_id')
        auth_url = start_xero_oauth(company_id)
        return jsonify({'auth_url': auth_url})
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        safe_print(f"[XERO] Connect error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/accounting/xero/callback", methods=["GET"])
def accounting_xero_callback():
    """OAuth callback from Xero."""
    try:
        from src.services.accounting_oauth import handle_xero_callback
        code = request.args.get('code')
        state = request.args.get('state')
        if not code or not state:
            raise ValueError("Missing code or state parameter")

        db = get_database()
        company_id = handle_xero_callback(code, state, db)

        frontend_url = os.getenv('FRONTEND_URL', config.PUBLIC_URL or 'http://localhost:5173')
        return f"""
        <html><body>
        <script>
            window.opener ? window.opener.postMessage('accounting-connected', '*') : null;
            window.location.href = '{frontend_url}/settings?tab=business&accounting=xero_connected';
        </script>
        <p>Xero connected! Redirecting...</p>
        </body></html>
        """
    except Exception as e:
        safe_print(f"[XERO] Callback error: {e}")
        import traceback
        traceback.print_exc()
        frontend_url = os.getenv('FRONTEND_URL', config.PUBLIC_URL or 'http://localhost:5173')
        return f"""
        <html><body>
        <script>
            window.location.href = '{frontend_url}/settings?tab=business&accounting=error';
        </script>
        <p>Error connecting Xero: {str(e)}</p>
        </body></html>
        """


@app.route("/api/accounting/xero/disconnect", methods=["POST"])
@login_required
@subscription_required
def accounting_xero_disconnect():
    """Disconnect Xero."""
    try:
        from src.services.accounting_oauth import disconnect_xero
        db = get_database()
        company_id = session.get('company_id')
        disconnect_xero(company_id, db)
        return jsonify({'success': True, 'message': 'Xero disconnected'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/api/accounting/quickbooks/connect", methods=["POST"])
@login_required
@subscription_required
def accounting_quickbooks_connect():
    """Start the QuickBooks OAuth flow."""
    try:
        from src.services.accounting_oauth import start_quickbooks_oauth
        company_id = session.get('company_id')
        auth_url = start_quickbooks_oauth(company_id)
        return jsonify({'auth_url': auth_url})
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        safe_print(f"[QB] Connect error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/accounting/quickbooks/callback", methods=["GET"])
def accounting_quickbooks_callback():
    """OAuth callback from QuickBooks."""
    try:
        from src.services.accounting_oauth import handle_quickbooks_callback
        code = request.args.get('code')
        state = request.args.get('state')
        realm_id = request.args.get('realmId')
        if not code or not state or not realm_id:
            raise ValueError("Missing code, state, or realmId parameter")

        db = get_database()
        company_id = handle_quickbooks_callback(code, state, realm_id, db)

        frontend_url = os.getenv('FRONTEND_URL', config.PUBLIC_URL or 'http://localhost:5173')
        return f"""
        <html><body>
        <script>
            window.opener ? window.opener.postMessage('accounting-connected', '*') : null;
            window.location.href = '{frontend_url}/settings?tab=business&accounting=quickbooks_connected';
        </script>
        <p>QuickBooks connected! Redirecting...</p>
        </body></html>
        """
    except Exception as e:
        safe_print(f"[QB] Callback error: {e}")
        import traceback
        traceback.print_exc()
        frontend_url = os.getenv('FRONTEND_URL', config.PUBLIC_URL or 'http://localhost:5173')
        return f"""
        <html><body>
        <script>
            window.location.href = '{frontend_url}/settings?tab=business&accounting=error';
        </script>
        <p>Error connecting QuickBooks: {str(e)}</p>
        </body></html>
        """


@app.route("/api/accounting/quickbooks/disconnect", methods=["POST"])
@login_required
@subscription_required
def accounting_quickbooks_disconnect():
    """Disconnect QuickBooks."""
    try:
        from src.services.accounting_oauth import disconnect_quickbooks
        db = get_database()
        company_id = session.get('company_id')
        disconnect_quickbooks(company_id, db)
        return jsonify({'success': True, 'message': 'QuickBooks disconnected'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ADMIN INSIGHTS ENDPOINTS ====================

@app.route("/api/admin/insights/overview", methods=["GET"])
@admin_required
def admin_insights_overview():
    """Platform-wide overview stats for admin dashboard."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Total accounts
        cursor.execute("SELECT COUNT(*) as total FROM companies")
        total_accounts = cursor.fetchone()['total']

        # Active subscriptions
        cursor.execute("SELECT subscription_tier, COUNT(*) as cnt FROM companies GROUP BY subscription_tier")
        tier_counts = {row['subscription_tier'] or 'none': row['cnt'] for row in cursor.fetchall()}

        # Accounts with Stripe Connect
        cursor.execute("SELECT COUNT(*) as cnt FROM companies WHERE stripe_connect_account_id IS NOT NULL")
        stripe_connected = cursor.fetchone()['cnt']

        # Accounts with phone numbers
        cursor.execute("SELECT COUNT(*) as cnt FROM companies WHERE twilio_phone_number IS NOT NULL")
        with_phone = cursor.fetchone()['cnt']

        # Total bookings platform-wide
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                   COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
                   COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_jobs,
                   COUNT(CASE WHEN payment_status = 'paid' AND payment_method = 'stripe' THEN 1 END) as stripe_paid_jobs,
                   COUNT(CASE WHEN payment_status = 'paid' AND (payment_method IS NULL OR payment_method != 'stripe') THEN 1 END) as non_stripe_paid_jobs,
                   COALESCE(SUM(CASE WHEN payment_status = 'paid' AND payment_method = 'stripe' THEN charge ELSE 0 END), 0) as stripe_revenue,
                   COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN charge ELSE 0 END), 0) as paid_revenue
            FROM bookings
        """)
        booking_stats = cursor.fetchone()

        # Total call logs
        cursor.execute("SELECT COUNT(*) as total, COUNT(CASE WHEN call_outcome = 'booking_made' THEN 1 END) as booked, COUNT(CASE WHEN is_lost_job = TRUE THEN 1 END) as lost FROM call_logs")
        call_stats = cursor.fetchone()

        # Total revenue platform-wide
        cursor.execute("SELECT COALESCE(SUM(charge), 0) as total FROM bookings WHERE status != 'cancelled'")
        total_revenue = float(cursor.fetchone()['total'])

        # Platform fee revenue (€2 per Stripe payment)
        platform_fee_cents = int(os.getenv('STRIPE_PLATFORM_FEE_CENTS', '200'))
        stripe_paid_count = int(booking_stats.get('stripe_paid_jobs', 0))
        platform_fee_revenue = round(stripe_paid_count * platform_fee_cents / 100, 2)

        # Accounts created per month (last 6 months)
        cursor.execute("""
            SELECT TO_CHAR(created_at, 'YYYY-MM') as month, COUNT(*) as cnt
            FROM companies
            WHERE created_at >= NOW() - INTERVAL '6 months'
            GROUP BY month ORDER BY month
        """)
        signups_by_month = [dict(r) for r in cursor.fetchall()]

        # Recent accounts (last 10)
        cursor.execute("""
            SELECT id, company_name, owner_name, email, subscription_tier, subscription_status,
                   twilio_phone_number, created_at, stripe_connect_account_id
            FROM companies ORDER BY created_at DESC LIMIT 10
        """)
        recent = []
        for row in cursor.fetchall():
            d = dict(row)
            for k in list(d.keys()):
                if d.get(k) and hasattr(d[k], 'isoformat'):
                    d[k] = d[k].isoformat()
            recent.append(d)

        cursor.close()
        return jsonify({
            "success": True,
            "overview": {
                "total_accounts": total_accounts,
                "tier_counts": tier_counts,
                "stripe_connected": stripe_connected,
                "with_phone": with_phone,
                "booking_stats": dict(booking_stats),
                "call_stats": dict(call_stats),
                "total_revenue": total_revenue,
                "platform_fee_revenue": platform_fee_revenue,
                "signups_by_month": signups_by_month,
                "recent_accounts": recent,
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/admin/insights/company/<int:company_id>", methods=["GET"])
@admin_required
def admin_company_insights(company_id):
    """Detailed insights for a specific company."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Company info
        cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        company = cursor.fetchone()
        if not company:
            cursor.close()
            return jsonify({"error": "Company not found"}), 404
        company = dict(company)
        for k in list(company.keys()):
            if company.get(k) and hasattr(company[k], 'isoformat'):
                company[k] = company[k].isoformat()
        # Remove sensitive fields
        for f in ['password_hash', 'owner_invite_token', 'verification_token', 'reset_token',
                   'google_credentials_json', 'openai_api_key', 'deepgram_api_key',
                   'elevenlabs_api_key']:
            company.pop(f, None)

        # Booking stats
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                   COUNT(CASE WHEN status = 'scheduled' THEN 1 END) as scheduled,
                   COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
                   COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress,
                   COALESCE(SUM(CASE WHEN status != 'cancelled' THEN charge ELSE 0 END), 0) as total_revenue,
                   COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN charge ELSE 0 END), 0) as paid_revenue,
                   COALESCE(SUM(CASE WHEN payment_status = 'unpaid' AND status != 'cancelled' THEN charge ELSE 0 END), 0) as unpaid_revenue,
                   COUNT(CASE WHEN payment_method = 'stripe' THEN 1 END) as stripe_payments,
                   COUNT(CASE WHEN payment_method = 'cash' THEN 1 END) as cash_payments,
                   COUNT(CASE WHEN payment_method = 'bank_transfer' THEN 1 END) as bank_payments,
                   COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_count,
                   COUNT(CASE WHEN payment_status = 'unpaid' AND status != 'cancelled' THEN 1 END) as unpaid_count
            FROM bookings WHERE company_id = %s
        """, (company_id,))
        booking_stats = dict(cursor.fetchone())
        for k, v in booking_stats.items():
            if isinstance(v, (int, float)):
                booking_stats[k] = float(v) if '.' in str(v) else int(v)

        # Monthly bookings (last 12 months)
        cursor.execute("""
            SELECT TO_CHAR(appointment_time, 'YYYY-MM') as month,
                   COUNT(*) as total,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                   COUNT(CASE WHEN payment_method = 'stripe' THEN 1 END) as stripe_paid,
                   COALESCE(SUM(CASE WHEN status != 'cancelled' THEN charge ELSE 0 END), 0) as revenue
            FROM bookings WHERE company_id = %s
            GROUP BY month ORDER BY month DESC LIMIT 12
        """, (company_id,))
        monthly = []
        for row in cursor.fetchall():
            d = dict(row)
            d['revenue'] = float(d['revenue'])
            monthly.append(d)

        # Call log stats
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN call_outcome = 'booking_made' THEN 1 END) as booked,
                   COUNT(CASE WHEN call_outcome = 'callback_requested' THEN 1 END) as callbacks,
                   COUNT(CASE WHEN call_outcome = 'info_provided' THEN 1 END) as info_only,
                   COUNT(CASE WHEN is_lost_job = TRUE THEN 1 END) as lost_jobs,
                   COALESCE(AVG(duration_seconds), 0) as avg_duration
            FROM call_logs WHERE company_id = %s
        """, (company_id,))
        call_stats = dict(cursor.fetchone())
        call_stats['avg_duration'] = round(float(call_stats['avg_duration']), 1)

        # Employees
        cursor.execute("SELECT COUNT(*) as cnt FROM employees WHERE company_id = %s", (company_id,))
        employee_count = cursor.fetchone()['cnt']

        # Clients
        cursor.execute("SELECT COUNT(*) as cnt FROM clients WHERE company_id = %s", (company_id,))
        client_count = cursor.fetchone()['cnt']

        # Services
        cursor.execute("SELECT COUNT(*) as cnt FROM services WHERE company_id = %s", (company_id,))
        service_count = cursor.fetchone()['cnt']

        # Stripe Connect status
        stripe_info = {
            'connect_account_id': company.get('stripe_connect_account_id'),
            'connect_status': company.get('stripe_connect_status', 'not_connected'),
            'connect_onboarding_complete': bool(company.get('stripe_connect_onboarding_complete')),
            'customer_id': company.get('stripe_customer_id'),
            'subscription_id': company.get('stripe_subscription_id'),
        }

        # Recent call logs (last 5)
        cursor.execute("""
            SELECT id, phone_number, caller_name, call_outcome, is_lost_job,
                   duration_seconds, ai_summary, created_at
            FROM call_logs WHERE company_id = %s
            ORDER BY created_at DESC LIMIT 5
        """, (company_id,))
        recent_calls = []
        for row in cursor.fetchall():
            d = dict(row)
            for k2 in list(d.keys()):
                if d.get(k2) and hasattr(d[k2], 'isoformat'):
                    d[k2] = d[k2].isoformat()
            recent_calls.append(d)

        cursor.close()
        return jsonify({
            "success": True,
            "company": company,
            "insights": {
                "booking_stats": booking_stats,
                "monthly_bookings": monthly,
                "call_stats": call_stats,
                "employee_count": employee_count,
                "client_count": client_count,
                "service_count": service_count,
                "stripe_info": stripe_info,
                "recent_calls": recent_calls,
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


@app.route("/api/admin/search", methods=["GET"])
@admin_required
def admin_search():
    """Search across companies, clients, bookings for support."""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400

    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        term = f"%{q}%"

        # Search companies
        cursor.execute("""
            SELECT id, company_name, owner_name, email, phone, twilio_phone_number,
                   subscription_tier, subscription_status
            FROM companies
            WHERE company_name ILIKE %s OR owner_name ILIKE %s OR email ILIKE %s
                  OR phone ILIKE %s OR twilio_phone_number ILIKE %s
            LIMIT 10
        """, (term, term, term, term, term))
        companies = [dict(r) for r in cursor.fetchall()]

        # Search clients
        cursor.execute("""
            SELECT c.id, c.name, c.phone, c.email, c.company_id, co.company_name
            FROM clients c
            JOIN companies co ON c.company_id = co.id
            WHERE c.name ILIKE %s OR c.phone ILIKE %s OR c.email ILIKE %s
            LIMIT 10
        """, (term, term, term))
        clients = [dict(r) for r in cursor.fetchall()]

        # Search call logs by phone or caller name
        cursor.execute("""
            SELECT cl.id, cl.phone_number, cl.caller_name, cl.call_outcome,
                   cl.ai_summary, cl.company_id, co.company_name, cl.created_at
            FROM call_logs cl
            JOIN companies co ON cl.company_id = co.id
            WHERE cl.phone_number ILIKE %s OR cl.caller_name ILIKE %s
            ORDER BY cl.created_at DESC LIMIT 10
        """, (term, term))
        calls = []
        for r in cursor.fetchall():
            d = dict(r)
            for k in list(d.keys()):
                if d.get(k) and hasattr(d[k], 'isoformat'):
                    d[k] = d[k].isoformat()
            calls.append(d)

        cursor.close()
        return jsonify({
            "success": True,
            "results": {
                "companies": companies,
                "clients": clients,
                "calls": calls,
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.return_connection(conn)


# ============================================
# QUOTE PIPELINE API
# ============================================

PIPELINE_STAGES = ['draft', 'sent', 'viewed', 'follow_up', 'accepted', 'won', 'lost']

@app.route("/api/quotes/pipeline", methods=["GET"])
@login_required
def get_quote_pipeline():
    """Get all quotes organized for pipeline view."""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT q.*, c.name as client_name, c.phone as client_phone, c.email as client_email
            FROM quotes q LEFT JOIN clients c ON q.client_id = c.id
            WHERE q.company_id = %s ORDER BY q.created_at DESC
        """, (company_id,))
        quotes = cur.fetchall()
        for q in quotes:
            for k in list(q.keys()):
                if q.get(k) and hasattr(q[k], 'isoformat'):
                    q[k] = q[k].isoformat()
            if q.get('line_items') and isinstance(q['line_items'], str):
                import json
                try: q['line_items'] = json.loads(q['line_items'])
                except: pass
            # Ensure pipeline_stage has a value (fallback from status)
            if not q.get('pipeline_stage'):
                status = q.get('status', 'draft')
                q['pipeline_stage'] = {'converted': 'won', 'declined': 'lost', 'accepted': 'accepted', 'sent': 'sent', 'expired': 'lost'}.get(status, 'draft')
        # Stats
        active = [q for q in quotes if q.get('pipeline_stage') not in ('won', 'lost')]
        won = [q for q in quotes if q.get('pipeline_stage') == 'won' or q.get('status') == 'converted']
        total_pipeline = sum(float(q.get('total') or 0) for q in active)
        total_won = sum(float(q.get('total') or 0) for q in won)
        total = len(quotes)
        conversion = round(len(won) / total * 100) if total > 0 else 0
        return jsonify({
            "quotes": quotes,
            "stats": {
                "active": len(active), "won": len(won), "lost": len([q for q in quotes if q.get('pipeline_stage') == 'lost']),
                "pipeline_value": total_pipeline, "won_value": total_won, "conversion_rate": conversion, "total": total
            }
        })
    except Exception as e:
        if 'column "pipeline_stage" does not exist' in str(e) or 'column "accept_token" does not exist' in str(e):
            conn.rollback()
            # Fallback: query without new columns
            cur2 = conn.cursor(cursor_factory=RealDictCursor)
            cur2.execute("""
                SELECT q.*, c.name as client_name, c.phone as client_phone, c.email as client_email
                FROM quotes q LEFT JOIN clients c ON q.client_id = c.id
                WHERE q.company_id = %s ORDER BY q.created_at DESC
            """, (company_id,))
            quotes = cur2.fetchall()
            for q in quotes:
                for k in list(q.keys()):
                    if q.get(k) and hasattr(q[k], 'isoformat'):
                        q[k] = q[k].isoformat()
                status = q.get('status', 'draft')
                q['pipeline_stage'] = {'converted': 'won', 'declined': 'lost', 'accepted': 'accepted', 'sent': 'sent', 'expired': 'lost'}.get(status, 'draft')
            cur2.close()
            active = [q for q in quotes if q.get('pipeline_stage') not in ('won', 'lost')]
            won = [q for q in quotes if q.get('pipeline_stage') == 'won']
            total = len(quotes)
            return jsonify({
                "quotes": quotes,
                "stats": {
                    "active": len(active), "won": len(won), "lost": len([q for q in quotes if q.get('pipeline_stage') == 'lost']),
                    "pipeline_value": sum(float(q.get('total') or 0) for q in active),
                    "won_value": sum(float(q.get('total') or 0) for q in won),
                    "conversion_rate": round(len(won) / total * 100) if total > 0 else 0, "total": total
                }
            })
        raise
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/quotes/<int:quote_id>/pipeline-stage", methods=["PUT"])
@login_required
@subscription_required
def update_quote_pipeline_stage(quote_id):
    """Move a quote to a different pipeline stage."""
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    stage = data.get('stage', '').strip()
    if stage not in PIPELINE_STAGES:
        return jsonify({"error": f"Invalid stage: {stage}"}), 400
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        extra_sql = ""
        params = [stage]
        if stage == 'won':
            extra_sql = ", won_at = CURRENT_TIMESTAMP, status = 'accepted'"
        elif stage == 'lost':
            reason = data.get('lost_reason', '')
            extra_sql = ", lost_at = CURRENT_TIMESTAMP, lost_reason = %s, status = 'declined'"
            params.append(reason)
        params.extend([quote_id, company_id])
        cur.execute(f"UPDATE quotes SET pipeline_stage = %s, updated_at = CURRENT_TIMESTAMP{extra_sql} WHERE id = %s AND company_id = %s", params)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/quotes/<int:quote_id>/accept-link", methods=["POST"])
@login_required
@subscription_required
def generate_quote_accept_link(quote_id):
    """Generate a public accept link for a quote."""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Reuse existing token if present
        cur.execute("SELECT accept_token FROM quotes WHERE id = %s AND company_id = %s", (quote_id, company_id))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Quote not found"}), 404
        token = row.get('accept_token')
        if not token:
            token = secrets.token_urlsafe(32)
            cur.execute("UPDATE quotes SET accept_token = %s WHERE id = %s AND company_id = %s", (token, quote_id, company_id))
            conn.commit()
        public_url = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
        link = f"{public_url}/quote/accept/{token}"
        return jsonify({"link": link, "token": token})
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/quote/accept/<token>", methods=["GET"])
def get_quote_by_accept_token(token):
    """Public: get quote details for acceptance page."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT q.*, c.name as client_name, co.company_name, co.business_phone
            FROM quotes q
            LEFT JOIN clients c ON q.client_id = c.id
            LEFT JOIN companies co ON q.company_id = co.id
            WHERE q.accept_token = %s
        """, (token,))
        quote = cur.fetchone()
        if not quote:
            return jsonify({"error": "Quote not found"}), 404
        for k in list(quote.keys()):
            if quote.get(k) and hasattr(quote[k], 'isoformat'):
                quote[k] = quote[k].isoformat()
        if quote.get('line_items') and isinstance(quote['line_items'], str):
            import json
            try: quote['line_items'] = json.loads(quote['line_items'])
            except: pass
        return jsonify({"quote": quote})
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/quote/accept/<token>", methods=["POST"])
def accept_quote_by_token(token):
    """Public: customer accepts a quote."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, company_id, status, pipeline_stage FROM quotes WHERE accept_token = %s", (token,))
        quote = cur.fetchone()
        if not quote:
            return jsonify({"error": "Quote not found"}), 404
        if quote.get('status') in ('accepted', 'converted'):
            return jsonify({"already_accepted": True})
        cur.execute("""
            UPDATE quotes SET status = 'accepted', pipeline_stage = 'accepted',
            updated_at = CURRENT_TIMESTAMP WHERE id = %s
        """, (quote['id'],))
        conn.commit()
        return jsonify({"success": True, "message": "Quote accepted! We'll be in touch to schedule your job."})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


# ============================================
# FOLLOW-UP SEQUENCES API
# ============================================

@app.route("/api/sequences", methods=["GET"])
@login_required
def get_sequences():
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM follow_up_sequences WHERE company_id = %s ORDER BY created_at DESC", (company_id,))
        seqs = cur.fetchall()
        for s in seqs:
            for k in list(s.keys()):
                if s.get(k) and hasattr(s[k], 'isoformat'):
                    s[k] = s[k].isoformat()
        return jsonify({"sequences": seqs})
    except Exception as e:
        if 'relation "follow_up_sequences" does not exist' in str(e):
            conn.rollback()
            return jsonify({"sequences": []})
        raise
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/sequences", methods=["POST"])
@login_required
@subscription_required
def create_sequence():
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    name = sanitize_string(data.get('name', 'Untitled Sequence'))
    trigger_type = data.get('trigger_type', 'quote_sent')
    steps = data.get('steps', [])
    conn = db.get_connection()
    try:
        import json
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO follow_up_sequences (company_id, name, trigger_type, steps)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (company_id, name, trigger_type, json.dumps(steps)))
        seq_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"id": seq_id, "success": True}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/sequences/<int:seq_id>", methods=["PUT"])
@login_required
@subscription_required
def update_sequence(seq_id):
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        import json
        cur = conn.cursor()
        cur.execute("""
            UPDATE follow_up_sequences SET name = %s, trigger_type = %s, steps = %s,
            enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND company_id = %s
        """, (
            sanitize_string(data.get('name', '')), data.get('trigger_type', 'quote_sent'),
            json.dumps(data.get('steps', [])), data.get('enabled', True), seq_id, company_id
        ))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/sequences/<int:seq_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_sequence(seq_id):
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM follow_up_sequences WHERE id = %s AND company_id = %s", (seq_id, company_id))
        conn.commit()
        return jsonify({"success": True})
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/quotes/<int:quote_id>/follow-up", methods=["POST"])
@login_required
@subscription_required
def send_quote_follow_up(quote_id):
    """Manually send a follow-up for a quote."""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT q.*, c.name as client_name, c.email as client_email, c.phone as client_phone
            FROM quotes q LEFT JOIN clients c ON q.client_id = c.id
            WHERE q.id = %s AND q.company_id = %s
        """, (quote_id, company_id))
        quote = cur.fetchone()
        if not quote:
            return jsonify({"error": "Quote not found"}), 404
        email = (quote.get('client_email') or '').strip()
        phone = (quote.get('client_phone') or '').strip()
        if not email and not phone:
            return jsonify({"error": "Customer has no contact info"}), 400
        company = db.get_company(company_id)
        company_name = (company.get('company_name', '') or company.get('business_name', '') or 'Our Company') if company else 'Our Company'
        total = float(quote.get('total', 0))
        title = quote.get('title', f"Quote #{quote.get('quote_number', '')}")
        sent_via = None
        req_data = request.get_json() or {}
        custom_msg = sanitize_string(req_data.get('message', ''))
        body = custom_msg or f"Hi {quote.get('client_name', 'there')}, just following up on your quote for {title} (€{total:.2f}). Are you still interested? We'd love to get this scheduled for you."
        if email:
            try:
                from src.services.email_reminder import get_email_service
                email_svc = get_email_service()
                if email_svc.configured:
                    email_svc.company_reply_to = (company.get('email') or '').strip() if company else None
                    html = f"""<div style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:560px;margin:0 auto'>
<h2 style='color:#1e293b'>Following up on your quote</h2>
<p style='color:#475569'>{body}</p>
<div style='background:#f8fafc;padding:14px;border-radius:8px;margin:16px 0'>
<strong>{title}</strong><br><span style='font-size:1.2em;color:#1e293b'>€{total:.2f}</span>
</div>
<p style='color:#64748b;font-size:13px'>Reply to this email or call us to proceed.</p>
</div>"""
                    email_svc._send_email(email, f"Following up — {title}", html, body, company_name)
                    sent_via = 'email'
            except Exception:
                pass
        if not sent_via and phone:
            try:
                from src.services.sms_reminder import get_sms_service
                sms_service = get_sms_service()
                twilio_number = company.get('twilio_phone_number') if company else None
                if sms_service.client and twilio_number:
                    sms_service.client.messages.create(body=body, from_=twilio_number, to=phone)
                    sent_via = 'sms'
            except Exception:
                pass
        if not sent_via:
            return jsonify({"error": "Could not send follow-up"}), 500
        # Update follow-up count
        cur2 = conn.cursor()
        cur2.execute("UPDATE quotes SET follow_up_count = COALESCE(follow_up_count, 0) + 1, last_follow_up_at = CURRENT_TIMESTAMP, pipeline_stage = CASE WHEN pipeline_stage = 'sent' THEN 'follow_up' ELSE pipeline_stage END WHERE id = %s", (quote_id,))
        conn.commit()
        cur2.close()
        return jsonify({"success": True, "sent_via": sent_via})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


# ============================================
# WORKFLOW AUTOMATIONS API
# ============================================

@app.route("/api/automations", methods=["GET"])
@login_required
def get_automations():
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM workflow_automations WHERE company_id = %s ORDER BY created_at DESC", (company_id,))
        rows = cur.fetchall()
        for r in rows:
            for k in list(r.keys()):
                if r.get(k) and hasattr(r[k], 'isoformat'):
                    r[k] = r[k].isoformat()
        return jsonify({"automations": rows})
    except Exception as e:
        if 'relation "workflow_automations" does not exist' in str(e):
            conn.rollback()
            return jsonify({"automations": []})
        raise
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/automations", methods=["POST"])
@login_required
@subscription_required
def create_automation():
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        import json
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO workflow_automations (company_id, name, trigger_type, trigger_config, actions)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (company_id, sanitize_string(data.get('name', '')), data.get('trigger_type', ''),
              json.dumps(data.get('trigger_config', {})), json.dumps(data.get('actions', []))))
        aid = cur.fetchone()[0]
        conn.commit()
        return jsonify({"id": aid, "success": True}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/automations/<int:auto_id>", methods=["PUT"])
@login_required
@subscription_required
def update_automation(auto_id):
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        import json
        cur = conn.cursor()
        cur.execute("""
            UPDATE workflow_automations SET name = %s, trigger_type = %s, trigger_config = %s,
            actions = %s, enabled = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND company_id = %s
        """, (sanitize_string(data.get('name', '')), data.get('trigger_type', ''),
              json.dumps(data.get('trigger_config', {})), json.dumps(data.get('actions', [])),
              data.get('enabled', True), auto_id, company_id))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/automations/<int:auto_id>", methods=["DELETE"])
@login_required
@subscription_required
def delete_automation(auto_id):
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM workflow_automations WHERE id = %s AND company_id = %s", (auto_id, company_id))
        conn.commit()
        return jsonify({"success": True})
    finally:
        cur.close()
        db.return_connection(conn)


# ============================================
# CUSTOMER PORTAL API
# ============================================

@app.route("/api/clients/<int:client_id>/portal-link", methods=["POST"])
@login_required
@subscription_required
def generate_portal_link(client_id):
    """Generate a portal access link for a customer."""
    db = get_database()
    company_id = session.get('company_id')
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Check client belongs to company
        cur.execute("SELECT id FROM clients WHERE id = %s AND company_id = %s", (client_id, company_id))
        if not cur.fetchone():
            return jsonify({"error": "Client not found"}), 404
        # Reuse existing token or create new
        cur.execute("SELECT token FROM customer_portal_tokens WHERE client_id = %s AND company_id = %s", (client_id, company_id))
        existing = cur.fetchone()
        if existing:
            token = existing['token']
        else:
            token = secrets.token_urlsafe(32)
            cur.execute("""
                INSERT INTO customer_portal_tokens (company_id, client_id, token)
                VALUES (%s, %s, %s)
            """, (company_id, client_id, token))
            conn.commit()
        public_url = os.getenv('PUBLIC_URL', request.host_url.rstrip('/'))
        link = f"{public_url}/portal/{token}"
        return jsonify({"link": link, "token": token})
    except Exception as e:
        conn.rollback()
        if 'relation "customer_portal_tokens" does not exist' in str(e):
            return jsonify({"error": "Portal not set up yet. Run the migration first."}), 500
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/portal/<token>", methods=["GET"])
def get_portal_data(token):
    """Public: customer portal — get jobs, invoices, quotes for a customer."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT pt.client_id, pt.company_id, c.name as client_name, c.email, c.phone,
                   co.company_name, co.phone as business_phone, co.logo_url as company_logo
            FROM customer_portal_tokens pt
            JOIN clients c ON pt.client_id = c.id
            JOIN companies co ON pt.company_id = co.id
            WHERE pt.token = %s
        """, (token,))
        portal = cur.fetchone()
        if not portal:
            return jsonify({"error": "Invalid portal link"}), 404
        
        # Safely get industry_type (column may not exist if migration hasn't run)
        _portal_industry_type = 'trades'
        try:
            cur.execute("SELECT industry_type FROM companies WHERE id = %s", (portal['company_id'],))
            _it_row = cur.fetchone()
            if _it_row and _it_row.get('industry_type'):
                _portal_industry_type = _it_row['industry_type']
        except Exception:
            pass  # Column doesn't exist yet — use default
        client_id = portal['client_id']
        company_id = portal['company_id']
        # Update last accessed
        cur.execute("UPDATE customer_portal_tokens SET last_accessed_at = CURRENT_TIMESTAMP WHERE token = %s", (token,))
        conn.commit()
        # Get upcoming jobs
        try:
            cur.execute("""
                SELECT id, service_type, appointment_time, status, address, duration_minutes, charge,
                       photo_urls, customer_photo_urls
                FROM bookings WHERE company_id = %s AND client_id = %s AND status NOT IN ('cancelled', 'rejected')
                ORDER BY appointment_time DESC LIMIT 20
            """, (company_id, client_id))
        except Exception:
            conn.rollback()
            # Fallback if customer_photo_urls column doesn't exist yet
            cur.execute("""
                SELECT id, service_type, appointment_time, status, address, duration_minutes, charge,
                       photo_urls
                FROM bookings WHERE company_id = %s AND client_id = %s AND status NOT IN ('cancelled', 'rejected')
                ORDER BY appointment_time DESC LIMIT 20
            """, (company_id, client_id))
        jobs = cur.fetchall()
        import json as _json_portal
        for j in jobs:
            for k in list(j.keys()):
                if j.get(k) and hasattr(j[k], 'isoformat'):
                    j[k] = j[k].isoformat()
            # Parse JSON photo arrays
            for photo_field in ('photo_urls', 'customer_photo_urls'):
                val = j.get(photo_field)
                if val and isinstance(val, str):
                    try:
                        j[photo_field] = _json_portal.loads(val)
                    except Exception:
                        j[photo_field] = []
                elif not val:
                    j[photo_field] = []
        # Get quotes
        cur.execute("""
            SELECT id, quote_number, title, total, status, pipeline_stage, created_at, valid_until, accept_token
            FROM quotes WHERE company_id = %s AND client_id = %s
            ORDER BY created_at DESC LIMIT 10
        """, (company_id, client_id))
        quotes = cur.fetchall()
        for q in quotes:
            for k in list(q.keys()):
                if q.get(k) and hasattr(q[k], 'isoformat'):
                    q[k] = q[k].isoformat()
        # Get industry profile so customer portal can show the correct terminology
        from src.utils.industry_config import get_industry_profile
        _industry_profile = get_industry_profile(_portal_industry_type)
        
        return jsonify({
            "client_name": portal['client_name'],
            "company_name": portal['company_name'],
            "company_phone": portal['business_phone'],
            "company_logo": portal.get('company_logo') or '',
            "email": portal['email'],
            "jobs": jobs,
            "quotes": quotes,
            "industry_type": _portal_industry_type,
            "industry_profile": _industry_profile,
        })
    except Exception as e:
        if 'relation "customer_portal_tokens" does not exist' in str(e):
            conn.rollback()
            return jsonify({"error": "Portal not available"}), 404
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/portal/<token>/request-job", methods=["POST"])
def portal_request_job(token):
    """Public: customer requests a new job through the portal."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT pt.client_id, pt.company_id, c.name, c.phone, c.email
            FROM customer_portal_tokens pt JOIN clients c ON pt.client_id = c.id
            WHERE pt.token = %s
        """, (token,))
        portal = cur.fetchone()
        if not portal:
            return jsonify({"error": "Invalid link"}), 404
        data = request.get_json() or {}
        service = sanitize_string(data.get('service_type', 'General'))
        description = sanitize_string(data.get('description', ''))
        address = sanitize_string(data.get('address', ''))
        # Create as a lead
        cur.execute("""
            INSERT INTO leads (company_id, client_id, name, phone, email, source, stage, service_interest, notes, address)
            VALUES (%s, %s, %s, %s, %s, 'portal', 'new', %s, %s, %s) RETURNING id
        """, (portal['company_id'], portal['client_id'], portal['name'],
              portal['phone'], portal['email'], service, description, address))
        lead_id = cur.fetchone()['id']
        conn.commit()

        # Notify owner about the portal job request
        try:
            svc_text = f" for {service}" if service and service != 'General' else ""
            db.create_notification(
                company_id=portal['company_id'],
                recipient_type='owner',
                recipient_id=0,
                notif_type='new_lead',
                message=f"Portal request from {portal['name']}{svc_text}",
                metadata={'lead_id': lead_id, 'source': 'portal'},
            )
        except Exception:
            pass

        return jsonify({"success": True, "lead_id": lead_id, "message": "Request submitted! We'll be in touch soon."})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


@app.route("/api/portal/<token>/jobs/<int:job_id>/photos", methods=["POST"])
@rate_limit(max_requests=20, window_seconds=60)
def portal_upload_job_photo(token, job_id):
    """Public: customer uploads a photo/video to their job via the portal."""
    db = get_database()
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Validate token and get client/company
        cur.execute("""
            SELECT pt.client_id, pt.company_id
            FROM customer_portal_tokens pt
            WHERE pt.token = %s
        """, (token,))
        portal = cur.fetchone()
        if not portal:
            return jsonify({"error": "Invalid portal link"}), 404
        client_id = portal['client_id']
        company_id = portal['company_id']
        # Verify job belongs to this customer
        try:
            cur.execute("""
                SELECT id, customer_photo_urls FROM bookings
                WHERE id = %s AND company_id = %s AND client_id = %s AND status NOT IN ('cancelled')
            """, (job_id, company_id, client_id))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT id FROM bookings
                WHERE id = %s AND company_id = %s AND client_id = %s AND status NOT IN ('cancelled')
            """, (job_id, company_id, client_id))
        booking = cur.fetchone()
        if not booking:
            return jsonify({"error": "Job not found"}), 404

        import json as _json_pu
        import io
        from datetime import datetime as _dt_pu

        ALLOWED_MEDIA_TYPES = {
            'image/png', 'image/jpeg', 'image/gif', 'image/webp',
            'video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo',
        }
        MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB

        media_url = None

        # Multipart file upload
        if request.files and 'file' in request.files:
            file = request.files['file']
            if not file or not file.filename:
                return jsonify({"error": "No file provided"}), 400
            content_type = file.content_type or ''
            if content_type not in ALLOWED_MEDIA_TYPES:
                return jsonify({"error": f"Unsupported file type: {content_type}"}), 400
            file_data = file.read()
            is_video = content_type.startswith('video/')
            max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE_BYTES
            if len(file_data) > max_size:
                limit_mb = max_size // (1024 * 1024)
                return jsonify({"error": f"File too large. Max {limit_mb}MB"}), 400
            try:
                from src.services.storage_r2 import upload_company_file, is_r2_enabled
                if not is_r2_enabled():
                    return jsonify({"error": "Storage not configured"}), 500
                ext = content_type.split('/')[-1]
                if ext == 'quicktime': ext = 'mov'
                elif ext == 'x-msvideo': ext = 'avi'
                timestamp = _dt_pu.now().strftime('%Y%m%d_%H%M%S')
                filename = f"customer_media_{timestamp}_{secrets.token_hex(4)}.{ext}"
                media_url = upload_company_file(
                    company_id=company_id, file_data=io.BytesIO(file_data),
                    filename=filename, file_type='customer_photos', content_type=content_type
                )
            except Exception as e:
                print(f"[ERROR] Portal media upload failed: {e}")
                return jsonify({"error": "Failed to upload file"}), 500
        else:
            # Base64 image upload
            data = request.json or {}
            image_data = data.get('image')
            if not image_data or not image_data.startswith('data:image/'):
                return jsonify({"error": "Invalid image data"}), 400
            media_url = upload_base64_image_to_r2(image_data, company_id, file_type='customer_photos')

        if not media_url or media_url.startswith('data:'):
            return jsonify({"error": "Failed to upload media"}), 500

        # Append to customer_photo_urls
        existing = booking.get('customer_photo_urls') or []
        if isinstance(existing, str):
            try:
                existing = _json_pu.loads(existing)
            except Exception:
                existing = []
        existing.append(media_url)

        cur.execute(
            "UPDATE bookings SET customer_photo_urls = %s WHERE id = %s AND company_id = %s",
            (_json_pu.dumps(existing), job_id, company_id)
        )
        conn.commit()
        return jsonify({"success": True, "photo_url": media_url, "customer_photo_urls": existing})
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Portal photo upload failed: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


# ============================================
# REVIEW AUTOMATION SETTINGS API
# ============================================

@app.route("/api/settings/review-automation", methods=["GET"])
@login_required
def get_review_automation_settings():
    db = get_database()
    company_id = session.get('company_id')
    try:
        company = db.get_company(company_id)
        return jsonify({
            "review_auto_send": company.get('review_auto_send', True) if company else True,
            "review_delay_hours": company.get('review_delay_hours', 24) if company else 24,
            "review_google_url": company.get('review_google_url', '') if company else '',
            "google_review_threshold": company.get('google_review_threshold', 4) if company else 4,
        })
    except Exception:
        # Columns may not exist yet
        return jsonify({
            "review_auto_send": True,
            "review_delay_hours": 24,
            "review_google_url": '',
            "google_review_threshold": 4,
        })


@app.route("/api/settings/review-automation", methods=["POST"])
@login_required
@subscription_required
def update_review_automation_settings():
    db = get_database()
    company_id = session.get('company_id')
    data = request.get_json() or {}
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE companies SET
                review_auto_send = %s, review_delay_hours = %s,
                review_google_url = %s, google_review_threshold = %s
            WHERE id = %s
        """, (
            data.get('review_auto_send', True),
            int(data.get('review_delay_hours', 24)),
            sanitize_string(data.get('review_google_url', '')),
            int(data.get('google_review_threshold', 4)),
            company_id
        ))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        db.return_connection(conn)


if __name__ == "__main__":
    try:
        config.validate()
        print("[SUCCESS] Configuration validated")
        print(f"[SERVER] Starting Flask server on port {config.PORT}")
        # Bind to 0.0.0.0 for production (Render/cloud), 127.0.0.1 for local dev
        host = "0.0.0.0" if config.FLASK_ENV == "production" else "127.0.0.1"
        app.run(host=host, port=config.PORT, debug=(config.FLASK_ENV == "development"), use_reloader=False)
    except ValueError as e:
        print(f"[ERROR] Configuration error: {e}")
        exit(1)

