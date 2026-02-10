"""
Flask application for Twilio voice webhook
Secured against OWASP Top 10 vulnerabilities
"""
import os
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
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
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

CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

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
    """Decorator to require login for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'company_id' not in session:
            get_security_logger().log_failed_auth(
                request.path,
                get_client_ip(),
                'No session'
            )
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """Decorator for rate limiting API endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            limiter = get_rate_limiter()
            ip = get_client_ip()
            
            allowed, remaining = limiter.check_rate_limit(
                ip, max_requests, window_seconds
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
        file_type: Type of file (logos, workers, services, etc.)
    
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


# Flag to track if scheduler has been started (for worker-based initialization)
_scheduler_started = False

def start_scheduler_once():
    """Start the auto-complete scheduler only once per worker"""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    
    # Only start scheduler if this is the main worker (worker 0) or in development
    worker_id = os.getenv('GUNICORN_WORKER_ID', os.getenv('WORKER_ID', '0'))
    is_main_worker = worker_id in ('0', '', None)
    
    if not is_main_worker:
        return
    
    print("\\n🚀 Starting appointment auto-complete scheduler...")
    try:
        from src.services.appointment_auto_complete import start_auto_complete_scheduler
        start_auto_complete_scheduler(interval_minutes=60)  # Check every hour
        print("✅ Auto-complete scheduler started successfully\\n")
    except Exception as e:
        print(f"[WARNING] Warning: Could not start auto-complete scheduler: {e}\\n")


# Initialize scheduler on first request (lazy init)
_scheduler_initialized = False

@app.before_request
def init_scheduler():
    """Initialize scheduler on first request"""
    global _scheduler_initialized
    if not _scheduler_initialized:
        _scheduler_initialized = True
        start_scheduler_once()


@app.route("/twilio/voice", methods=["POST"])
def twilio_voice():
    """
    Twilio voice webhook endpoint - identifies company by incoming phone number
    Returns TwiML to connect call to media stream OR forward to business phone
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
        print(f"[ERROR] No company found for Twilio number: {to_number}")
        return Response(str(twiml), mimetype="text/xml")
    
    # Check if AI receptionist is enabled
    ai_enabled = company.get('ai_enabled', True)
    
    twiml = VoiceResponse()
    
    if not ai_enabled:
        # AI is disabled - forward to business phone number
        business_phone = company.get('phone') if company else None
        
        print("=" * 60)
        print("📞 Incoming Twilio Call - AI DISABLED")
        print(f"[PHONE] Caller: {caller_phone}")
        print(f"[PHONE] Forwarding to business phone: {business_phone or 'No phone number set!'}")
        print("=" * 60)
        
        if business_phone:
            twiml.say("Please hold while we connect you.")
            # Create Dial verb with proper nested Number noun
            dial = twiml.dial(timeout=60, action='/twilio/dial-status', method='POST')
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
        print("📞 Incoming Twilio Call - AI ENABLED")
        print(f"[PHONE] Caller: {caller_phone}")
        print(f"[COMPANY] ID: {company.get('id')}, Name: {company.get('company_name')}")
        print(f"[AI] Connecting to AI at: {ws_url}")
        print("=" * 60)
    
    return Response(str(twiml), mimetype="text/xml")


@app.route("/twilio/dial-status", methods=["POST"])
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


@app.route("/twilio/transfer", methods=["POST"])
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
    
    # Create TwiML to transfer the call
    response = VoiceResponse()
    response.say("Transferring you now. Please hold.")
    dial = response.dial(timeout=60, action='/twilio/dial-status', method='POST')
    dial.number(transfer_number)
    
    print(f"[INFO] Generated transfer TwiML:\n{str(response)}")
    
    return Response(str(response), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "AI Receptionist"}


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
        # Set up 14-day trial
        from datetime import datetime, timedelta
        trial_start = datetime.now()
        trial_end = trial_start + timedelta(days=14)
        
        db.update_company(
            company_id,
            subscription_tier='trial',
            subscription_status='active',
            trial_start=trial_start,
            trial_end=trial_end
        )
        
        # Log the user in (phone number will be configured separately)
        session['company_id'] = company_id
        session['email'] = email
        
        company = db.get_company(company_id)
        return jsonify({
            "success": True,
            "message": "Account created successfully. Your 14-day free trial has started!",
            "user": {
                "id": company_id,
                "company_name": company['company_name'],
                "owner_name": company['owner_name'],
                "email": company['email'],
                "subscription_tier": company['subscription_tier'],
                "trial_end": trial_end.isoformat(),
                "twilio_phone_number": company.get('twilio_phone_number')
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
    
    # Check if this IP/email is blocked due to too many failed attempts
    if rate_limiter.is_blocked(email) or rate_limiter.is_blocked(client_ip):
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
        rate_limiter.record_failed_login(client_ip)
        security_logger.log_login_attempt(email, client_ip, False)
        print(f"[LOGIN] FAILED - User not found: {email}")
        
        return jsonify({
            "error": "Invalid email or password",
            "code": "INVALID_CREDENTIALS"
        }), 401
    
    if not verify_password(password, company['password_hash']):
        # Record failed attempt
        should_block = rate_limiter.record_failed_login(email)
        rate_limiter.record_failed_login(client_ip)
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
    rate_limiter.clear_failed_logins(client_ip)
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
    
    # Log session creation for debugging
    print(f"[LOGIN] SUCCESS - User {company['id']} ({email}) from {origin} | "
          f"Secure={app.config.get('SESSION_COOKIE_SECURE')}, "
          f"SameSite={app.config.get('SESSION_COOKIE_SAMESITE')}")
    return jsonify({
        "success": True,
        "message": "Logged in successfully",
        "user": {
            "id": company['id'],
            "company_name": company['company_name'],
            "owner_name": company['owner_name'],
            "email": company['email'],
            "phone": company['phone'],
            "trade_type": company['trade_type'],
            "logo_url": company['logo_url'],
            "subscription_tier": company['subscription_tier'],
            "twilio_phone_number": company.get('twilio_phone_number')
        }
    })


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """Log out the current user"""
    company_id = session.get('company_id', 'unknown')
    email = session.get('email', 'unknown')
    print(f"[LOGOUT] User {company_id} ({email}) logging out")
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    """Get the currently logged in user"""
    client_ip = get_client_ip()
    
    # Debug logging for session check
    has_session = 'company_id' in session
    company_id = session.get('company_id', 'none')
    print(f"[AUTH_CHECK] Request from {client_ip} - Session exists: {has_session}, Company ID: {company_id}")
    
    if not has_session:
        print(f"[AUTH_CHECK] No session found - user not authenticated")
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
            "twilio_phone_number": company.get('twilio_phone_number')
        },
        "subscription": subscription_info
    })


@app.route("/api/dashboard", methods=["GET"])
@login_required
def get_dashboard_data():
    """
    Batch endpoint to get all dashboard data in one request.
    Reduces 4 separate API calls to 1, improving page load performance.
    """
    try:
        db = get_database()
        company_id = session.get('company_id')
        
        # Get all data filtered by company_id
        bookings = db.get_all_bookings(company_id=company_id)
        clients = db.get_all_clients(company_id=company_id)
        workers = db.get_all_workers(company_id=company_id)
        
        # Calculate finances
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
                'workers': workers,
                'finances': finances
            }
        })
        
    except Exception as e:
        print(f"[ERROR] Dashboard data error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/auth/profile", methods=["PUT"])
def update_profile():
    """Update company profile"""
    if 'company_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    
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
@rate_limit(max_requests=5, window_seconds=300)  # 5 password changes per 5 minutes
def change_password():
    """Change password for logged in user"""
    if 'company_id' not in session:
        return jsonify({"error": "Authentication required"}), 401
    
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
def assign_phone_number():
    """Assign a phone number to the current company"""
    data = request.json
    phone_number = data.get('phone_number')
    
    if not phone_number:
        return jsonify({"error": "Phone number is required"}), 400
    
    db = get_database()
    company_id = session['company_id']
    
    # Check if company already has a phone number
    company = db.get_company(company_id)
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
# SUBSCRIPTION & STRIPE ENDPOINTS
# ============================================

from datetime import datetime, timedelta
from src.services.stripe_service import (
    create_checkout_session,
    create_billing_portal_session,
    get_subscription_status,
    cancel_subscription,
    reactivate_subscription,
    handle_webhook_event,
    get_customer_invoices,
    get_or_create_customer,
    is_stripe_configured,
    TRIAL_DAYS
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


def get_subscription_info(company: dict) -> dict:
    """Get comprehensive subscription info for a company"""
    now = datetime.now()
    
    subscription_tier = company.get('subscription_tier', 'trial')
    subscription_status = company.get('subscription_status', 'active')
    trial_end = company.get('trial_end')
    current_period_end = company.get('subscription_current_period_end')
    cancel_at_period_end = bool(company.get('subscription_cancel_at_period_end', 0))
    
    # Parse dates if they're strings
    if isinstance(trial_end, str):
        try:
            trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
        except:
            trial_end = None
    
    if isinstance(current_period_end, str):
        try:
            current_period_end = datetime.fromisoformat(current_period_end.replace('Z', '+00:00'))
        except:
            current_period_end = None
    
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
        is_active = trial_end and trial_end > now
    elif subscription_tier == 'pro':
        is_active = subscription_status == 'active'
    
    return {
        'tier': subscription_tier,
        'status': subscription_status,
        'is_active': is_active,
        'trial_end': trial_end.isoformat() if trial_end else None,
        'trial_days_remaining': trial_days_remaining,
        'current_period_end': current_period_end.isoformat() if current_period_end else None,
        'cancel_at_period_end': cancel_at_period_end,
        'stripe_customer_id': company.get('stripe_customer_id'),
        'stripe_subscription_id': company.get('stripe_subscription_id')
    }


def subscription_required(f):
    """Decorator to require active subscription for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
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


@app.route("/api/subscription/status", methods=["GET"])
@login_required
def get_subscription_status_endpoint():
    """Get current subscription status"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    subscription_info = get_subscription_info(company)
    
    return jsonify({
        "success": True,
        "subscription": subscription_info
    })


@app.route("/api/subscription/create-checkout", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)
def create_checkout():
    """Create a Stripe checkout session for subscription"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    if not is_stripe_configured():
        return jsonify({"error": "Payment system not configured"}), 503
    
    data = request.json or {}
    
    # Get base URL for redirects
    base_url = data.get('base_url', os.getenv('FRONTEND_URL', 'http://localhost:3000'))
    
    # Determine if this is a trial signup (new) or upgrade (existing/expired trial)
    subscription_info = get_subscription_info(company)
    with_trial = subscription_info['tier'] == 'trial' and subscription_info['is_active']
    
    # If trial is expired or never had trial, no trial period on checkout
    if subscription_info['tier'] == 'trial' and not subscription_info['is_active']:
        with_trial = False
    
    result = create_checkout_session(
        company_id=company['id'],
        email=company['email'],
        company_name=company['company_name'],
        success_url=f"{base_url}/settings?subscription=success",
        cancel_url=f"{base_url}/settings?subscription=cancelled",
        with_trial=False  # Trial is separate, checkout is for immediate subscription
    )
    
    if result:
        return jsonify({
            "success": True,
            "checkout_url": result['url'],
            "session_id": result['session_id']
        })
    else:
        return jsonify({"error": "Failed to create checkout session"}), 500


@app.route("/api/subscription/start-trial", methods=["POST"])
@login_required
def start_trial():
    """Start or restart a 14-day free trial"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    # Check if already on active trial or pro
    subscription_info = get_subscription_info(company)
    if subscription_info['is_active'] and subscription_info['tier'] == 'pro':
        return jsonify({"error": "You already have an active subscription"}), 400
    
    # Start 14-day trial
    from datetime import timedelta
    trial_start = datetime.now()
    trial_end = trial_start + timedelta(days=14)
    
    db.update_company(
        company['id'],
        subscription_tier='trial',
        subscription_status='active',
        trial_start=trial_start,
        trial_end=trial_end
    )
    
    print(f"[SUCCESS] Free trial started for company {company['id']} until {trial_end}")
    
    return jsonify({
        "success": True,
        "message": "Your 14-day free trial has started!",
        "trial_end": trial_end.isoformat()
    })


@app.route("/api/subscription/billing-portal", methods=["POST"])
@login_required
def billing_portal():
    """Create a Stripe billing portal session"""
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
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
    
    invoices = get_customer_invoices(customer_id)
    
    return jsonify({
        "success": True,
        "invoices": invoices
    })


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    
    if not STRIPE_WEBHOOK_SECRET:
        print("⚠️ Stripe webhook secret not configured")
        return jsonify({"error": "Webhook not configured"}), 400
    
    result = handle_webhook_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    
    if not result['success']:
        print(f"[ERROR] Webhook error: {result['error']}")
        return jsonify({"error": result['error']}), 400
    
    event_type = result['event_type']
    data = result['data']
    db = get_database()
    
    try:
        if event_type == 'checkout.session.completed':
            # Subscription checkout completed
            company_id = int(data.get('metadata', {}).get('company_id', 0))
            customer_id = data.get('customer')
            subscription_id = data.get('subscription')
            
            if company_id:
                # Get subscription details
                import stripe
                sub = stripe.Subscription.retrieve(subscription_id)
                
                db.update_company(
                    company_id,
                    subscription_tier='pro',
                    subscription_status='active',
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    subscription_current_period_end=datetime.fromtimestamp(sub.current_period_end),
                    subscription_cancel_at_period_end=0
                )
                print(f"[SUCCESS] Subscription activated for company {company_id}")
        
        elif event_type == 'customer.subscription.updated':
            # Subscription updated (e.g., renewed, cancelled)
            subscription_id = data.get('id')
            status = data.get('status')
            cancel_at_period_end = data.get('cancel_at_period_end', False)
            current_period_end = data.get('current_period_end')
            
            # Find company by subscription ID
            # We need to search by stripe_subscription_id
            company_id = int(data.get('metadata', {}).get('company_id', 0))
            
            if company_id:
                update_data = {
                    'subscription_status': status,
                    'subscription_cancel_at_period_end': 1 if cancel_at_period_end else 0
                }
                
                if current_period_end:
                    update_data['subscription_current_period_end'] = datetime.fromtimestamp(current_period_end)
                
                db.update_company(company_id, **update_data)
                print(f"[SUCCESS] Subscription updated for company {company_id}: {status}")
        
        elif event_type == 'customer.subscription.deleted':
            # Subscription cancelled/expired
            company_id = int(data.get('metadata', {}).get('company_id', 0))
            
            if company_id:
                db.update_company(
                    company_id,
                    subscription_tier='expired',
                    subscription_status='cancelled',
                    stripe_subscription_id=None
                )
                print(f"[WARNING] Subscription cancelled for company {company_id}")
        
        elif event_type == 'invoice.payment_failed':
            # Payment failed
            customer_id = data.get('customer')
            company_id = int(data.get('subscription_details', {}).get('metadata', {}).get('company_id', 0))
            
            if company_id:
                db.update_company(company_id, subscription_status='past_due')
                print(f"[WARNING] Payment failed for company {company_id}")
    
    except Exception as e:
        print(f"[ERROR] Error processing webhook {event_type}: {e}")
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
                    db.update_booking(booking_id, payment_status='paid', status='completed')
                    print(f"[SUCCESS] Booking {booking_id} marked as paid via Stripe Connect checkout")
                except Exception as e:
                    print(f"[WARNING] Error updating booking {booking_id}: {e}")
        
        # Handle payment intent succeeded
        elif event_type == 'payment_intent.succeeded':
            booking_id = data.get('metadata', {}).get('booking_id')
            if booking_id:
                try:
                    booking_id = int(booking_id)
                    db.update_booking(booking_id, payment_status='paid', status='completed')
                    print(f"[SUCCESS] Booking {booking_id} marked as paid via payment intent")
                except Exception as e:
                    print(f"[WARNING] Error updating booking {booking_id}: {e}")
    
    except Exception as e:
        print(f"[ERROR] Error processing Connect webhook {event_type}: {e}")
    
    return jsonify({"received": True})


@app.route("/twilio/sms", methods=["POST"])
def twilio_sms():
    """
    Handle incoming SMS messages (for appointment confirmations/cancellations)
    Only active if REMINDER_METHOD=sms in .env
    """
    try:
        # Check if SMS reminders are enabled
        if config.REMINDER_METHOD.lower() != "sms":
            print("⚠️ SMS webhook called but REMINDER_METHOD is not 'sms'. Ignoring.")
            resp = MessagingResponse()
            resp.message("Please contact us by phone for appointment inquiries.")
            return Response(str(resp), mimetype="text/xml")
        
        # Get message details
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
            'business_phone': company.get('phone'),
            'business_email': company.get('email'),
            'business_address': company.get('address'),
            'logo_url': company.get('logo_url'),
            'country_code': '+353',  # Default, could be added to schema if needed
            'business_hours': company.get('business_hours') or '8 AM - 6 PM Mon-Sat (24/7 emergency available)',
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
        }
        return jsonify(settings)
    
    elif request.method == "POST":
        data = request.json
        
        # Handle logo upload to R2 if logo_url is base64
        if 'logo_url' in data and data['logo_url'] and data['logo_url'].startswith('data:image/'):
            data['logo_url'] = upload_base64_image_to_r2(data['logo_url'], company_id, 'logos')
        
        # Map frontend field names to database column names
        update_data = {}
        field_mapping = {
            'business_name': 'company_name',
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
                success = db.update_company(company_id, **update_data)
                if success:
                    return jsonify({"message": "Settings updated successfully"})
                else:
                    return jsonify({"error": "No changes were saved"}), 500
            except Exception as e:
                print(f"[ERROR] Error updating settings: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": f"Failed to save: {str(e)}"}), 500
        
        return jsonify({"error": "No valid fields to update"}), 400


# Developer settings endpoint removed - all settings now in companies table via /api/settings/business


@app.route("/api/ai-receptionist/toggle", methods=["GET", "POST"])
@login_required
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
        
        return jsonify({
            "enabled": bool(enabled) if isinstance(enabled, int) else enabled,
            "business_phone": business_phone
        })
    
    elif request.method == "POST":
        data = request.json
        enabled = data.get("enabled", True)
        
        # Get current company data
        company = db.get_company(company_id)
        if not company:
            return jsonify({"error": "Company not found"}), 404
        
        # Validation: Cannot disable AI without a business phone number
        if not enabled:
            business_phone = company.get('phone')
            
            if not business_phone:
                return jsonify({
                    "error": "Cannot disable AI receptionist without a business phone number configured"
                }), 400
        
        # Update AI status in companies table
        success = db.update_company(company_id, ai_enabled=1 if enabled else 0)
        
        if success:
            status = "enabled" if enabled else "disabled"
            return jsonify({
                "message": f"AI Receptionist {status} successfully",
                "enabled": enabled
            })
        return jsonify({"error": "Failed to update AI receptionist status"}), 500


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
def services_menu_api():
    """Get or update services menu"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        menu = settings_mgr.get_services_menu(company_id=company_id)
        return jsonify(menu)
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_services_menu(data, company_id=company_id)
        if success:
            return jsonify({"message": "Services menu updated successfully"})
        return jsonify({"error": "Failed to update services menu"}), 500


@app.route("/api/services/menu/service", methods=["POST"])
@login_required
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
    
    # Upload image to R2 if it's base64
    if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
        data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'services')
    
    success = settings_mgr.add_service(data, company_id=company_id)
    if success:
        return jsonify({"message": "Service added successfully"})
    return jsonify({"error": "Failed to add service"}), 500


@app.route("/api/services/menu/service/<service_id>", methods=["PUT", "DELETE"])
@login_required
def manage_service_api(service_id):
    """Update or delete a service"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    if request.method == "PUT":
        data = request.json
        
        # Upload image to R2 if it's base64
        if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
            data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'services')
        
        success = settings_mgr.update_service(service_id, data, company_id=company_id)
        if success:
            return jsonify({"message": "Service updated successfully"})
        return jsonify({"error": "Service not found"}), 404
    
    elif request.method == "DELETE":
        success = settings_mgr.delete_service(service_id, company_id=company_id)
        if success:
            return jsonify({"message": "Service deleted successfully"})
        return jsonify({"error": "Service not found"}), 404


@app.route("/api/services/business-hours", methods=["GET", "POST"])
@login_required
def business_hours_api():
    """Get or update business hours"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        menu = settings_mgr.get_services_menu(company_id=company_id)
        return jsonify(menu.get('business_hours', {}))
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_business_hours(data, company_id=company_id)
        if success:
            return jsonify({"message": "Business hours updated successfully"})
        return jsonify({"error": "Failed to update business hours"}), 500


@app.route("/api/clients", methods=["GET", "POST"])
@login_required
@rate_limit(max_requests=30, window_seconds=60)
def clients_api():
    """Get all clients or create a new client"""
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
        client_id = db.add_client(
            name=data['name'],
            phone=data.get('phone'),
            email=data.get('email'),
            company_id=company_id
        )
        return jsonify({"id": client_id, "message": "Client created"}), 201


@app.route("/api/clients/<int:client_id>", methods=["GET", "PUT"])
@login_required
def client_api(client_id):
    """Get or update a specific client"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        client = db.get_client(client_id)
        # Verify client belongs to this company
        if client and client.get('company_id') and client.get('company_id') != company_id:
            return jsonify({"error": "Client not found"}), 404
        if client:
            # Get bookings and notes
            bookings = db.get_client_bookings(client_id)
            notes = db.get_client_notes(client_id)
            client['bookings'] = bookings
            client['notes'] = notes
            return jsonify(client)
        return jsonify({"error": "Client not found"}), 404
    
    elif request.method == "PUT":
        # Verify client belongs to this company before updating
        client = db.get_client(client_id)
        if not client or (client.get('company_id') and client.get('company_id') != company_id):
            return jsonify({"error": "Client not found"}), 404
        data = request.json
        db.update_client(client_id, **data)
        return jsonify({"message": "Client updated"})


@app.route("/api/clients/<int:client_id>/notes", methods=["POST"])
@login_required
def add_note_api(client_id):
    """Add a note to a client"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify client belongs to this company
    client = db.get_client(client_id)
    if client and client.get('company_id') and client.get('company_id') != company_id:
        return jsonify({"error": "Client not found"}), 404
    
    data = request.json
    
    note_id = db.add_note(
        client_id=client_id,
        note=data['note'],
        created_by=data.get('created_by', 'user')
    )
    return jsonify({"id": note_id, "message": "Note added"}), 201


@app.route("/api/bookings/<int:booking_id>/notes", methods=["GET", "POST"])
@login_required
def appointment_notes_api(booking_id):
    """Get or add notes for a specific appointment"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id)
    if booking and booking.get('company_id') and booking.get('company_id') != company_id:
        return jsonify({"error": "Booking not found"}), 404
    
    if request.method == "GET":
        notes = db.get_appointment_notes(booking_id)
        return jsonify(notes)
    
    elif request.method == "POST":
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
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
            success = update_client_description(client_id)
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
def appointment_note_api(booking_id, note_id):
    """Update or delete a specific appointment note"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id)
    if booking and booking.get('company_id') and booking.get('company_id') != company_id:
        return jsonify({"error": "Booking not found"}), 404
    
    # Get client_id for description update
    booking = db.get_booking(booking_id)
    client_id = booking['client_id'] if booking else None
    
    if request.method == "PUT":
        data = request.json
        success = db.update_appointment_note(note_id, data['note'])
        if success:
            # Update client description after editing note
            if client_id:
                print(f"\n[UPDATE] Updating client description for client_id: {client_id} after editing note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id)
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
        success = db.delete_appointment_note(note_id)
        if success:
            # Update client description after deleting note
            if client_id:
                print(f"\n[UPDATE] Updating client description for client_id: {client_id} after deleting note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id)
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
@rate_limit(max_requests=30, window_seconds=60)
def bookings_api():
    """Get all bookings or create a new booking"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        bookings = db.get_all_bookings(company_id=company_id)
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
        
        # Required fields
        client_id = data.get('client_id')
        appointment_time = data.get('appointment_time')
        service_type = data.get('service_type')
        
        if not all([client_id, appointment_time, service_type]):
            return jsonify({"error": "Missing required fields: client_id, appointment_time, service_type"}), 400
        
        try:
            # Parse appointment time
            from datetime import datetime, timedelta
            if isinstance(appointment_time, str):
                appointment_dt = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
            else:
                appointment_dt = appointment_time
            
            # Check for time conflicts (same time or overlapping within 1 hour)
            # Check for bookings within 1 hour of the requested time
            time_buffer_before = appointment_dt - timedelta(minutes=59)
            time_buffer_after = appointment_dt + timedelta(minutes=59)
            
            conflicting_bookings = db.get_conflicting_bookings(
                start_time=time_buffer_before.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=time_buffer_after.strftime('%Y-%m-%d %H:%M:%S'),
                company_id=company_id
            )
            
            if conflicting_bookings:
                conflict = conflicting_bookings[0]
                conflict_time = datetime.fromisoformat(str(conflict['appointment_time']))
                
                # Get client name for the conflicting booking
                conflict_client = db.get_client(conflict['client_id'])
                conflict_client_name = conflict_client['name'] if conflict_client else 'Unknown'
                
                return jsonify({
                    "error": f"Time conflict: There is already a booking at {conflict_time.strftime('%I:%M %p')} for {conflict_client_name} ({conflict['service_type']}). Please choose a different time.",
                    "conflict": True,
                    "conflicting_time": conflict_time.isoformat(),
                    "conflicting_client": conflict_client_name
                }), 409  # 409 Conflict status code
            
            # Google Calendar integration disabled (USE_GOOGLE_CALENDAR = False)
            calendar_event_id = None
            
            # Get client info
            client = db.get_client(client_id)
            
            # Use client's most recent booking address if not provided in job data
            # Accept both 'job_address' (from frontend) and 'address' (legacy)
            job_address = data.get('job_address') or data.get('address')
            job_eircode = data.get('eircode')
            job_property_type = data.get('property_type')
            
            # If address not provided, try to get from client's previous bookings
            if not job_address or not job_eircode or not job_property_type:
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
            
            # Create booking - accept both 'charge' and 'estimated_charge' from frontend
            job_charge = data.get('charge') or data.get('estimated_charge')
            
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
                company_id=company_id
            )
            
            # Add initial note if provided
            if data.get('notes'):
                db.add_appointment_note(
                    booking_id=booking_id,
                    note=data['notes'],
                    created_by="user"
                )
            
            # Update client description
            try:
                from src.services.client_description_generator import update_client_description
                update_client_description(client_id)
            except Exception as e:
                print(f"[WARNING] Could not update client description: {e}")
            
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


@app.route("/api/bookings/<int:booking_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def booking_detail_api(booking_id):
    """Get, update or delete a specific booking"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        # Get booking details using database method
        booking = db.get_booking(booking_id)
        
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
        # Verify booking belongs to this company
        if booking.get('company_id') and booking.get('company_id') != company_id:
            return jsonify({"error": "Booking not found"}), 404
        
        # Get notes for this booking
        appointment_notes = db.get_appointment_notes(booking_id)
        notes_text = appointment_notes[0]['note'] if appointment_notes else ''
        
        # Get client details if client_id exists
        if booking.get('client_id'):
            client = db.get_client(booking['client_id'])
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
            'email': booking.get('email') or booking.get('client_email'),
            'created_at': booking.get('created_at'),
            'charge': booking.get('charge'),
            'estimated_charge': booking.get('charge'),
            'payment_status': booking.get('payment_status'),
            'payment_method': booking.get('payment_method'),
            'urgency': booking.get('urgency'),
            'address': booking.get('address'),
            'job_address': booking.get('address'),
            'eircode': booking.get('eircode'),
            'property_type': booking.get('property_type'),
            'customer_name': booking.get('customer_name') or booking.get('client_name'),
            'client_name': booking.get('client_name') or booking.get('customer_name'),
            'notes': notes_text
        }
        
        return jsonify(response_booking)
    
    elif request.method == "PUT":
        # Verify booking belongs to this company before updating
        booking = db.get_booking(booking_id)
        if booking and booking.get('company_id') and booking.get('company_id') != company_id:
            return jsonify({"error": "Booking not found"}), 404
        
        # Update booking
        data = request.json
        
        # Handle notes separately (stored in appointment_notes table)
        notes = data.pop('notes', None)
        
        # Handle job_address mapping - frontend sends 'job_address', DB expects 'address'
        if 'job_address' in data:
            data['address'] = data.pop('job_address')
        
        success = db.update_booking(booking_id, **data)
        
        # Update notes if provided
        if notes is not None:
            # Clear existing notes and add the new note
            db.delete_appointment_notes_by_booking(booking_id)
            
            if notes.strip():
                db.add_appointment_note(booking_id, notes, created_by="user")
            success = True
        
        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Failed to update booking"}), 400
    
    elif request.method == "DELETE":
        # Verify booking belongs to this company before deleting
        booking = db.get_booking(booking_id)
        if booking and booking.get('company_id') and booking.get('company_id') != company_id:
            return jsonify({"error": "Booking not found"}), 404
        
        success = db.delete_booking(booking_id)
        if success:
            return jsonify({"success": True, "message": "Booking deleted"})
        return jsonify({"error": "Failed to delete booking"}), 400


@app.route("/api/bookings/<int:booking_id>/complete", methods=["POST"])
@login_required
def complete_booking_api(booking_id):
    """Mark appointment as complete and update client description using AI"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Get the booking to find the client
    booking = db.get_booking(booking_id)
    
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    
    # Verify booking belongs to this company
    if booking.get('company_id') and booking.get('company_id') != company_id:
        return jsonify({"error": "Booking not found"}), 404
    
    client_id = booking['client_id']
    current_status = booking['status']
    
    # Update booking status to completed
    db.update_booking(booking_id, status='completed')
    
    # Generate/update client description using AI based on all appointments and notes
    try:
        from src.services.client_description_generator import update_client_description
        success = update_client_description(client_id)
        
        if success:
            # Get the updated client info with new description
            client = db.get_client(client_id)
            return jsonify({
                "success": True,
                "message": "Appointment completed and description updated",
                "description": client.get('description')
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


@app.route("/api/bookings/<int:booking_id>/send-invoice", methods=["POST"])
@login_required
def send_invoice_api(booking_id):
    """Send invoice email for a booking with Stripe payment link"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Check subscription for sending invoices
    company = db.get_company(company_id)
    subscription_info = get_subscription_info(company)
    if not subscription_info['is_active']:
        return jsonify({
            "error": "Active subscription required to send invoices",
            "subscription_status": "inactive"
        }), 403
    
    try:
        # Get the booking details using database method
        booking = db.get_booking(booking_id)
        
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
        # Verify booking belongs to this company
        if booking.get('company_id') and booking.get('company_id') != company_id:
            return jsonify({"error": "Booking not found"}), 404
        
        # Get client details if client_id exists
        if booking.get('client_id'):
            client = db.get_client(booking['client_id'])
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
            'email': booking.get('email') or booking.get('client_email'),
            'created_at': booking.get('created_at'),
            'charge': booking.get('charge'),
            'estimated_charge': booking.get('charge'),
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
        
        safe_print(f"[INVOICE] Invoice: Using charge amount EUR{booking_dict['charge']} from database for booking {booking_id}")
        
        # Use customer's actual email
        to_email = booking_dict['email']
        
        if not to_email:
            return jsonify({"error": "Customer email not found. Please add an email address to the customer profile."}), 400
        
        if not booking_dict['client_name']:
            return jsonify({"error": "Customer name not found"}), 400
        
        # Get charge amount - use charge or estimated_charge, default to None if not set
        charge_amount = booking_dict.get('charge') or booking_dict.get('estimated_charge')
        
        if not charge_amount or charge_amount <= 0:
            return jsonify({"error": "Invalid charge amount"}), 400
        
        charge_amount = float(charge_amount)
        safe_print(f"[INVOICE] Invoice: Final charge amount = EUR{charge_amount}")
        
        # Generate Stripe payment link
        from src.utils.config import config
        from src.services.email_reminder import get_email_service
        from datetime import datetime
        stripe_payment_link = None
        
        # Get the user's company to check for Stripe Connect account
        company = db.get_company(session['company_id'])
        connected_account_id = company.get('stripe_connect_account_id') if company else None
        
        # Try to create Stripe payment link if configured
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
                print("[ERROR] STRIPE_SECRET_KEY not found in config or environment!")
        
        # Only create Stripe payment link if the user has their own Connect account
        # We never charge to the platform account - payments go directly to the user
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
                
                # Calculate platform fee if configured
                platform_fee_percent = float(os.getenv('STRIPE_PLATFORM_FEE_PERCENT', '0'))
                if platform_fee_percent > 0:
                    application_fee = int(amount_cents * (platform_fee_percent / 100))
                    checkout_params['payment_intent_data'] = {
                        'application_fee_amount': application_fee,
                    }
                
                checkout_session = stripe.checkout.Session.create(
                    **checkout_params,
                    stripe_account=connected_account_id  # Payment goes to user's account
                )
                
                stripe_payment_link = checkout_session.url
                print(f"[SUCCESS] Stripe payment link created: {stripe_payment_link}")
            except Exception as stripe_error:
                print(f"[WARNING] Could not create Stripe payment link: {stripe_error}")
                import traceback
                traceback.print_exc()
                # Continue without Stripe link - invoice will still be sent
        elif not connected_account_id:
            print("ℹ️ No Stripe Connect account - invoice will be sent without payment link")
        else:
            print("ℹ️ Stripe not configured - sending invoice without payment link")
        
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
        
        email_service = get_email_service()
        
        # Parse appointment time
        appointment_time = None
        if booking_dict.get('appointment_time'):
            try:
                appointment_time = datetime.fromisoformat(booking_dict['appointment_time'].replace('Z', '+00:00'))
            except:
                pass
        
        # Generate invoice number
        invoice_number = f"INV-{booking_id}-{datetime.now().strftime('%Y%m%d')}"
        
        # Get job address
        job_address = booking_dict.get('address') or booking_dict.get('job_address') or ''
        
        # Get business name from the company record
        company_business_name = company.get('business_name') or company.get('name') or None if company else None
        
        success = email_service.send_invoice(
            to_email=to_email,
            customer_name=booking_dict['client_name'],
            service_type=booking_dict.get('service_type') or 'Service',
            charge=charge_amount,
            appointment_time=appointment_time,
            stripe_payment_link=stripe_payment_link,
            job_address=job_address,
            invoice_number=invoice_number,
            bank_details=bank_details,
            revolut_phone=revolut_phone,
            add_bank_details=bool(bank_details and bank_details.get('iban')),
            add_revolut_phone=bool(revolut_phone),
            company_name=company_business_name
        )
        
        if success:
            # Update payment status to 'invoiced' so we know an invoice was sent
            try:
                db.update_booking(booking_id, payment_status='invoiced')
            except Exception:
                pass  # Non-critical, don't fail the response
            
            return jsonify({
                "success": True,
                "message": f"Invoice sent to {to_email}",
                "sent_to": to_email,
                "invoice_number": invoice_number,
                "has_payment_link": stripe_payment_link is not None
            })
        else:
            return jsonify({"error": "Failed to send invoice email"}), 500
            
    except Exception as e:
        safe_print(f"[ERROR] Error sending invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/appointments/auto-complete", methods=["POST"])
@login_required
def auto_complete_appointments():
    """Manually trigger auto-completion of overdue appointments"""
    try:
        from src.services.appointment_auto_complete import auto_complete_overdue_appointments
        count = auto_complete_overdue_appointments()
        return jsonify({
            "success": True,
            "message": f"Auto-completed {count} appointment(s)",
            "count": count
        })
    except Exception as e:
        print(f"[ERROR] Error in auto-complete: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


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


@app.route("/api/workers", methods=["GET", "POST"])
@login_required
@rate_limit(max_requests=30, window_seconds=60)
def workers_api():
    """Get all workers or create a new worker"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        workers = db.get_all_workers(company_id=company_id)
        return jsonify(workers)
    
    elif request.method == "POST":
        # Check subscription for creating workers
        company = db.get_company(company_id)
        subscription_info = get_subscription_info(company)
        if not subscription_info['is_active']:
            return jsonify({
                "error": "Active subscription required to create workers",
                "subscription_status": "inactive"
            }), 403
        
        data = request.json
        
        # Upload image to R2 if it's base64
        image_url = data.get('image_url', '')
        if image_url and image_url.startswith('data:image/'):
            image_url = upload_base64_image_to_r2(image_url, company_id, 'workers')
        
        worker_id = db.add_worker(
            name=data['name'],
            phone=data.get('phone'),
            email=data.get('email'),
            trade_specialty=data.get('trade_specialty'),
            image_url=image_url,
            weekly_hours_expected=data.get('weekly_hours_expected', 40.0),
            company_id=company_id
        )
        return jsonify({"id": worker_id, "message": "Worker added"}), 201


@app.route("/api/workers/<int:worker_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def worker_api(worker_id):
    """Get, update or delete a specific worker"""
    db = get_database()
    company_id = session.get('company_id')
    
    if request.method == "GET":
        worker = db.get_worker(worker_id)
        # Verify worker belongs to this company
        if worker and worker.get('company_id') and worker.get('company_id') != company_id:
            return jsonify({"error": "Worker not found"}), 404
        if worker:
            return jsonify(worker)
        return jsonify({"error": "Worker not found"}), 404
    
    elif request.method == "PUT":
        # Verify worker belongs to this company before updating
        worker = db.get_worker(worker_id)
        if not worker or (worker.get('company_id') and worker.get('company_id') != company_id):
            return jsonify({"error": "Worker not found"}), 404
        
        data = request.json
        
        # Upload image to R2 if it's base64
        if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
            data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'workers')
        
        db.update_worker(worker_id, **data)
        return jsonify({"message": "Worker updated"})
    
    elif request.method == "DELETE":
        # Verify worker belongs to this company before deleting
        worker = db.get_worker(worker_id)
        if not worker or (worker.get('company_id') and worker.get('company_id') != company_id):
            return jsonify({"error": "Worker not found"}), 404
        
        success = db.delete_worker(worker_id)
        if success:
            return jsonify({"message": "Worker deleted"})
        return jsonify({"error": "Worker not found"}), 404


@app.route("/api/bookings/<int:booking_id>/assign-worker", methods=["POST"])
@login_required
def assign_worker_to_job_api(booking_id):
    """Assign a worker to a job"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.json
    worker_id = data.get('worker_id')
    
    if not worker_id:
        return jsonify({"error": "worker_id is required"}), 400
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id)
    if booking and booking.get('company_id') and booking.get('company_id') != company_id:
        return jsonify({"error": "Booking not found"}), 404
    
    # Verify worker belongs to this company
    worker = db.get_worker(worker_id)
    if worker and worker.get('company_id') and worker.get('company_id') != company_id:
        return jsonify({"error": "Worker not found"}), 404
    
    result = db.assign_worker_to_job(booking_id, worker_id)
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@app.route("/api/bookings/<int:booking_id>/remove-worker", methods=["POST"])
@login_required
def remove_worker_from_job_api(booking_id):
    """Remove a worker from a job"""
    db = get_database()
    company_id = session.get('company_id')
    data = request.json
    worker_id = data.get('worker_id')
    
    if not worker_id:
        return jsonify({"error": "worker_id is required"}), 400
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id)
    if booking and booking.get('company_id') and booking.get('company_id') != company_id:
        return jsonify({"error": "Booking not found"}), 404
    
    success = db.remove_worker_from_job(booking_id, worker_id)
    
    if success:
        return jsonify({"success": True, "message": "Worker removed from job"})
    else:
        return jsonify({"error": "Worker assignment not found"}), 404


@app.route("/api/bookings/<int:booking_id>/workers", methods=["GET"])
@login_required
def get_job_workers_api(booking_id):
    """Get all workers assigned to a job"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify booking belongs to this company
    booking = db.get_booking(booking_id)
    if booking and booking.get('company_id') and booking.get('company_id') != company_id:
        return jsonify({"error": "Booking not found"}), 404
    
    workers = db.get_job_workers(booking_id)
    return jsonify(workers)


@app.route("/api/workers/<int:worker_id>/jobs", methods=["GET"])
@login_required
def get_worker_jobs_api(worker_id):
    """Get all jobs assigned to a worker"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify worker belongs to this company
    worker = db.get_worker(worker_id)
    if worker and worker.get('company_id') and worker.get('company_id') != company_id:
        return jsonify({"error": "Worker not found"}), 404
    
    include_completed = request.args.get('include_completed', 'false').lower() == 'true'
    jobs = db.get_worker_jobs(worker_id, include_completed)
    
    # Ensure customer_name is set for frontend consistency
    for job in jobs:
        if not job.get('customer_name') and job.get('client_name'):
            job['customer_name'] = job['client_name']
    
    return jsonify(jobs)


@app.route("/api/workers/<int:worker_id>/schedule", methods=["GET"])
@login_required
def get_worker_schedule_api(worker_id):
    """Get worker's schedule"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify worker belongs to this company
    worker = db.get_worker(worker_id)
    if worker and worker.get('company_id') and worker.get('company_id') != company_id:
        return jsonify({"error": "Worker not found"}), 404
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    schedule = db.get_worker_schedule(worker_id, start_date, end_date)
    return jsonify(schedule)


@app.route("/api/workers/<int:worker_id>/hours-this-week", methods=["GET"])
@login_required
def get_worker_hours_this_week_api(worker_id):
    """Get hours worked by worker this week"""
    db = get_database()
    company_id = session.get('company_id')
    
    # Verify worker belongs to this company
    worker = db.get_worker(worker_id)
    if worker and worker.get('company_id') and worker.get('company_id') != company_id:
        return jsonify({"error": "Worker not found"}), 404
    
    hours = db.get_worker_hours_this_week(worker_id)
    return jsonify({"hours_worked": hours})


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
        
        # Get email configuration from environment
        from_email = os.getenv('FROM_EMAIL', 'j.p.enterprisehq@gmail.com')
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
    from src.services.llm_stream import stream_llm, process_appointment_with_calendar, SYSTEM_PROMPT
    
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
            # Don't pass caller_phone since this is web chat
            async for token in stream_llm(conversation, process_appointment_with_calendar, caller_phone=None):
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
    from src.services.llm_stream import reset_appointment_state
    reset_appointment_state()
    return jsonify({"message": "Chat state reset"})


@app.route("/api/finances", methods=["GET"])
@login_required
def get_finances():
    """Get financial overview and stats"""
    try:
        db = get_database()
        company_id = session.get('company_id')
        bookings = db.get_all_bookings(company_id=company_id)
        
        # Calculate revenue metrics
        paid_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings 
                          if b.get('status') == 'completed' or b.get('payment_status') == 'paid')
        unpaid_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings 
                            if b.get('status') not in ['completed', 'cancelled'] 
                            and b.get('payment_status') != 'paid')
        total_revenue = paid_revenue + unpaid_revenue
        
        # Build transactions list for detailed view
        transactions = []
        for booking in bookings:
            if booking.get('charge') and float(booking.get('charge', 0)) > 0:
                # Get customer name from client
                customer_name = booking.get('customer_name') or booking.get('client_name')
                if not customer_name and booking.get('client_id'):
                    client = db.get_client(booking['client_id'])
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
                    'date': booking.get('appointment_time'),
                    'payment_method': booking.get('payment_method')
                })
        
        # Group by month for chart
        from collections import defaultdict
        from datetime import datetime
        monthly = defaultdict(float)
        for booking in bookings:
            if (booking.get('status') == 'completed' or booking.get('payment_status') == 'paid') and booking.get('appointment_time'):
                try:
                    date = datetime.fromisoformat(booking['appointment_time'].replace('Z', '+00:00'))
                    month_key = date.strftime('%b %Y')  # e.g., "Jan 2024"
                    monthly[month_key] += float(booking.get('charge', 0) or 0)
                except:
                    pass
        
        # Get last 6 months of data, sorted chronologically
        monthly_revenue = [{"month": k, "revenue": v} for k, v in sorted(monthly.items(), 
                          key=lambda x: datetime.strptime(x[0], '%b %Y'))][-6:]
        
        return jsonify({
            "total_revenue": total_revenue,
            "paid_revenue": paid_revenue,
            "unpaid_revenue": unpaid_revenue,
            "pending_revenue": unpaid_revenue,  # For backwards compatibility
            "completed_revenue": paid_revenue,  # For backwards compatibility
            "monthly_revenue": monthly_revenue,
            "transactions": transactions
        })
    except Exception as e:
        print(f"Finances error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/calendar/events", methods=["GET"])
def get_calendar_events():
    """Get calendar events (disabled - USE_GOOGLE_CALENDAR = False)"""
    # Google Calendar integration disabled
    return jsonify([])


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

