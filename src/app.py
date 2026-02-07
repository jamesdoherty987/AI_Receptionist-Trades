"""
Flask application for Twilio voice webhook
Secured against OWASP Top 10 vulnerabilities
"""
import os
import sys
import secrets
from pathlib import Path
from functools import wraps

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, Response, request, jsonify, send_from_directory, session, g
from flask_cors import CORS
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
from src.utils.config import config
from src.services.database import get_database
from src.utils.security import (
    hash_password, verify_password, needs_rehash,
    get_rate_limiter, get_security_logger,
    sanitize_string, validate_email, validate_id,
    apply_security_headers, configure_secure_session,
    generate_csrf_token, verify_csrf_token,
    validate_field_names, ALLOWED_COMPANY_FIELDS
)
# Google Calendar disabled - USE_GOOGLE_CALENDAR = False

# Set up Flask to serve React build or development files
static_folder = Path(__file__).parent / "static" / "dist"
if not static_folder.exists():
    # Fallback to regular static folder during development
    static_folder = Path(__file__).parent / "static"

app = Flask(__name__, 
            static_folder=str(static_folder),
            static_url_path='')

# Configure CORS - allow specific origins for production
allowed_origins = [
    "https://www.bookedforyou.info",
    "https://bookedforyou.info",
    "http://localhost:5173",  # Vite dev server
    "http://localhost:5000",  # Flask dev server
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5000"
]

# Add ngrok URLs from environment if present
public_url = os.getenv('PUBLIC_URL')
if public_url:
    allowed_origins.append(public_url)
    # Also add without https:// prefix variations
    if public_url.startswith('https://'):
        allowed_origins.append(public_url.replace('https://', 'http://'))

CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

# Configure secure session
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
configure_secure_session(app)

# Security: Add security headers to all responses
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    return apply_security_headers(response)

# Security: Log request details for security monitoring
@app.before_request
def log_request():
    """Log request for security monitoring"""
    g.request_start_time = __import__('time').time()
    g.client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if g.client_ip and ',' in g.client_ip:
        g.client_ip = g.client_ip.split(',')[0].strip()


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

def upload_base64_image_to_r2(base64_data: str, company_id: int, file_type: str = 'images') -> str:
    """
    Upload a base64 image to R2 storage
    
    Args:
        base64_data: Base64 encoded image data (e.g., 'data:image/png;base64,...')
        company_id: Company ID for folder separation
        file_type: Type of file (logos, workers, services, etc.)
    
    Returns:
        R2 public URL if successful, or original base64 if R2 fails/not configured
    """
    # Skip if not base64 data
    if not base64_data or not base64_data.startswith('data:image/'):
        return base64_data or ''
    
    try:
        from src.services.storage_r2 import upload_company_file, is_r2_enabled
        import base64
        import io
        from datetime import datetime
        
        # Only proceed if R2 is configured
        if not is_r2_enabled():
            print("⚠️ R2 not configured, image will be stored as base64 in database")
            return base64_data
        
        # Extract base64 data and content type
        header, encoded = base64_data.split(',', 1)
        content_type = header.split(';')[0].split(':')[1]
        extension = content_type.split('/')[-1]
        
        # Decode base64
        image_data = base64.b64decode(encoded)
        
        # Generate unique filename with company separation
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{file_type}_{timestamp}_{secrets.token_hex(4)}.{extension}"
        
        # Upload to R2 with company-specific folder
        public_url = upload_company_file(
            company_id=company_id,
            file_data=io.BytesIO(image_data),
            filename=filename,
            file_type=file_type,
            content_type=content_type
        )
        
        if public_url:
            print(f"✅ Image uploaded to R2: {public_url}")
            return public_url
        else:
            print("⚠️ R2 upload returned None, storing as base64")
            return base64_data
            
    except Exception as e:
        print(f"⚠️ R2 upload failed, storing as base64: {e}")
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
        print(f"⚠️  Warning: Could not start auto-complete scheduler: {e}\\n")


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
        if hasattr(db, 'use_postgres') and db.use_postgres:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM companies WHERE twilio_phone_number = %s", (to_number,))
            company = cursor.fetchone()
            db.return_connection(conn)
            company = dict(company) if company else None
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE twilio_phone_number = ?", (to_number,))
            row = cursor.fetchone()
            if row:
                cursor.execute("PRAGMA table_info(companies)")
                columns = [col[1] for col in cursor.fetchall()]
                company = dict(zip(columns, row))
            else:
                company = None
            conn.close()
    except Exception as e:
        print(f"⚠️ Error fetching company by phone {to_number}: {e}")
        company = None
    
    if not company:
        # No company found for this number - return error
        twiml = VoiceResponse()
        twiml.say("This phone number is not configured. Please contact support.")
        print(f"❌ No company found for Twilio number: {to_number}")
        return Response(str(twiml), mimetype="text/xml")
    
    # Check if AI receptionist is enabled
    ai_enabled = company.get('ai_enabled', True)
    
    twiml = VoiceResponse()
    
    if not ai_enabled:
        # AI is disabled - forward to business phone number
        business_phone = company.get('phone') if company else None
        
        print("=" * 60)
        print("📞 Incoming Twilio Call - AI DISABLED")
        print(f"📱 Caller: {caller_phone}")
        print(f"📲 Forwarding to business phone: {business_phone or 'No phone number set!'}")
        print("=" * 60)
        
        if business_phone:
            twiml.say("Please hold while we connect you.")
            # Create Dial verb with proper nested Number noun
            dial = twiml.dial(timeout=60, action='/twilio/dial-status', method='POST')
            dial.number(business_phone)
            print(f"📋 Generated TwiML for forwarding:")
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

        print("=" * 60)
        print("📞 Incoming Twilio Call - AI ENABLED")
        print(f"📱 Caller: {caller_phone}")
        print(f"🤖 Connecting to AI at: {ws_url}")
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
        print(f"⚠️  ERROR {error_code}: {error_message}")
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
    print(f"📲 Transferring to: {transfer_number}")
    print("=" * 60)
    
    # Create TwiML to transfer the call
    response = VoiceResponse()
    response.say("Transferring you now. Please hold.")
    dial = response.dial(timeout=60, action='/twilio/dial-status', method='POST')
    dial.number(transfer_number)
    
    print(f"📋 Generated transfer TwiML:\n{str(response)}")
    
    return Response(str(response), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "AI Receptionist"}


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
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if len(password) > 128:
        return jsonify({"error": "Password is too long"}), 400
    
    # Additional password complexity checks
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_upper and has_lower and has_digit):
        return jsonify({
            "error": "Password must contain at least one uppercase letter, one lowercase letter, and one number"
        }), 400
    
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
        # Log the user in (phone number will be configured separately)
        session['company_id'] = company_id
        session['email'] = email
        
        company = db.get_company(company_id)
        return jsonify({
            "success": True,
            "message": "Account created successfully",
            "user": {
                "id": company_id,
                "company_name": company['company_name'],
                "owner_name": company['owner_name'],
                "email": company['email'],
                "subscription_tier": company['subscription_tier'],
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
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    
    # Check if this IP/email is blocked due to too many failed attempts
    if rate_limiter.is_blocked(email) or rate_limiter.is_blocked(client_ip):
        security_logger.log_failed_auth(
            '/api/auth/login',
            client_ip,
            'Account temporarily blocked'
        )
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
        return jsonify({"error": "Invalid email or password"}), 401
    
    if not verify_password(password, company['password_hash']):
        # Record failed attempt
        should_block = rate_limiter.record_failed_login(email)
        rate_limiter.record_failed_login(client_ip)
        security_logger.log_login_attempt(email, client_ip, False)
        
        if should_block:
            return jsonify({
                "error": "Too many failed attempts. Account temporarily locked."
            }), 429
        
        return jsonify({"error": "Invalid email or password"}), 401
    
    # Successful login - clear failed attempts
    rate_limiter.clear_failed_logins(email)
    rate_limiter.clear_failed_logins(client_ip)
    security_logger.log_login_attempt(email, client_ip, True)
    
    # Check if password hash needs upgrade (migrate from weak hash)
    if needs_rehash(company['password_hash']):
        new_hash = hash_password(password)
        db.update_company_password(company['id'], new_hash)
        print(f"✅ Upgraded password hash for user {company['id']}")
    
    # Update last login
    db.update_last_login(company['id'])
    
    # Create session
    session['company_id'] = company['id']
    session['email'] = company['email']
    
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
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    """Get the currently logged in user"""
    if 'company_id' not in session:
        return jsonify({"authenticated": False}), 200
    
    db = get_database()
    company = db.get_company(session['company_id'])
    
    if not company:
        session.clear()
        return jsonify({"authenticated": False}), 200
    
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
        }
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
        
        # Get all data in parallel operations (within same DB connection context)
        bookings = db.get_all_bookings()
        clients = db.get_all_clients()
        workers = db.get_all_workers()
        
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
        print(f"❌ Dashboard data error: {e}")
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
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    if len(new_password) > 128:
        return jsonify({"error": "Password is too long"}), 400
    
    has_upper = any(c.isupper() for c in new_password)
    has_lower = any(c.islower() for c in new_password)
    has_digit = any(c.isdigit() for c in new_password)
    if not (has_upper and has_lower and has_digit):
        return jsonify({
            "error": "Password must contain at least one uppercase letter, one lowercase letter, and one number"
        }), 400
    
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
        print(f"⚠️ Method not found: {e}")
        return jsonify({
            "success": False,
            "error": "Phone number management not configured",
            "numbers": []
        }), 500
    except Exception as e:
        print(f"❌ Error getting phone numbers: {e}")
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
        print(f"❌ Phone assignment failed for company {company_id}: {error_msg}")
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
        
        print(f"\n📱 SMS received from {from_number}: {message_body}")
        
        # Create response
        resp = MessagingResponse()
        
        if 'YES' in message_body or 'CONFIRM' in message_body:
            # User confirmed the appointment
            reply = "Thank you! Your appointment is confirmed. We look forward to seeing you!"
            resp.message(reply)
            print(f"✅ Appointment confirmed by {from_number}")
            
        elif 'CANCEL' in message_body:
            # User wants to cancel - we would need event ID to actually cancel
            # For now, just acknowledge and ask them to call
            reply = "We received your cancellation request. Please call us to confirm the cancellation and reschedule if needed."
            resp.message(reply)
            print(f"⚠️ Cancellation request from {from_number}")
            
        else:
            # Unknown response
            reply = "Thank you for your message. Please reply YES to confirm or CANCEL to cancel your appointment."
            resp.message(reply)
        
        return Response(str(resp), mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ Error handling SMS: {e}")
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
    return redirect("/", code=302)


@app.route("/settings")
def settings_page():
    """Redirect to React app"""
    return redirect("/settings", code=302)


@app.route("/settings/menu")
def settings_menu_page():
    """Redirect to React app"""
    return redirect("/settings/menu", code=302)


@app.route("/settings/developer")
def developer_settings_page():
    """Redirect to React app"""
    return redirect("/settings/developer", code=302)


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
            'ai_enabled': company.get('ai_enabled', True)
        }
        return jsonify(settings)
    
    elif request.method == "POST":
        data = request.json
        
        # Handle logo upload to R2 if logo_url is base64
        if 'logo_url' in data and data['logo_url'] and data['logo_url'].startswith('data:image/'):
            data['logo_url'] = upload_base64_image_to_r2(data['logo_url'], company_id, 'logos')
        
        # Map frontend field names to database column names
        # Only basic business info - no API keys or Twilio credentials
        update_data = {}
        field_mapping = {
            'business_name': 'company_name',
            'business_phone': 'phone',
            'business_email': 'email',
            'business_address': 'address',
            'logo_url': 'logo_url',
            'business_hours': 'business_hours',
            'ai_enabled': 'ai_enabled'
        }
        
        for frontend_field, db_field in field_mapping.items():
            if frontend_field in data:
                update_data[db_field] = data[frontend_field]
        
        if update_data:
            success = db.update_company(company_id, **update_data)
            if success:
                return jsonify({"message": "Settings updated successfully"})
        
        return jsonify({"error": "Failed to update settings"}), 500


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
    
    if request.method == "GET":
        menu = settings_mgr.get_services_menu()
        return jsonify(menu)
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_services_menu(data)
        if success:
            return jsonify({"message": "Services menu updated successfully"})
        return jsonify({"error": "Failed to update services menu"}), 500


@app.route("/api/services/menu/service", methods=["POST"])
@login_required
def add_service_api():
    """Add a new service"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    
    data = request.json
    
    # Upload image to R2 if it's base64
    if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
        company_id = session.get('company_id', 0)
        data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'services')
    
    success = settings_mgr.add_service(data)
    if success:
        return jsonify({"message": "Service added successfully"})
    return jsonify({"error": "Failed to add service"}), 500


@app.route("/api/services/menu/service/<service_id>", methods=["PUT", "DELETE"])
@login_required
def manage_service_api(service_id):
    """Update or delete a service"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    
    if request.method == "PUT":
        data = request.json
        
        # Upload image to R2 if it's base64
        if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
            company_id = session.get('company_id', 0)
            data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'services')
        
        success = settings_mgr.update_service(service_id, data)
        if success:
            return jsonify({"message": "Service updated successfully"})
        return jsonify({"error": "Service not found"}), 404
    
    elif request.method == "DELETE":
        success = settings_mgr.delete_service(service_id)
        if success:
            return jsonify({"message": "Service deleted successfully"})
        return jsonify({"error": "Service not found"}), 404


@app.route("/api/services/business-hours", methods=["GET", "POST"])
@login_required
def business_hours_api():
    """Get or update business hours"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    
    if request.method == "GET":
        menu = settings_mgr.get_services_menu()
        return jsonify(menu.get('business_hours', {}))
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_business_hours(data)
        if success:
            return jsonify({"message": "Business hours updated successfully"})
        return jsonify({"error": "Failed to update business hours"}), 500


@app.route("/api/clients", methods=["GET", "POST"])
@login_required
def clients_api():
    """Get all clients or create a new client"""
    db = get_database()
    
    if request.method == "GET":
        clients = db.get_all_clients()
        return jsonify(clients)
    
    elif request.method == "POST":
        data = request.json
        client_id = db.add_client(
            name=data['name'],
            phone=data.get('phone'),
            email=data.get('email')
        )
        return jsonify({"id": client_id, "message": "Client created"}), 201


@app.route("/api/clients/<int:client_id>", methods=["GET", "PUT"])
@login_required
def client_api(client_id):
    """Get or update a specific client"""
    db = get_database()
    
    if request.method == "GET":
        client = db.get_client(client_id)
        if client:
            # Get bookings and notes
            bookings = db.get_client_bookings(client_id)
            notes = db.get_client_notes(client_id)
            client['bookings'] = bookings
            client['notes'] = notes
            return jsonify(client)
        return jsonify({"error": "Client not found"}), 404
    
    elif request.method == "PUT":
        data = request.json
        db.update_client(client_id, **data)
        return jsonify({"message": "Client updated"})


@app.route("/api/clients/<int:client_id>/notes", methods=["POST"])
@login_required
def add_note_api(client_id):
    """Add a note to a client"""
    db = get_database()
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
    
    if request.method == "GET":
        notes = db.get_appointment_notes(booking_id)
        return jsonify(notes)
    
    elif request.method == "POST":
        # Get booking to find client_id for description update
        booking = db.get_booking(booking_id)
        
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
        print(f"\n🔄 Updating client description for client_id: {client_id} after adding note...")
        try:
            from src.services.client_description_generator import update_client_description
            success = update_client_description(client_id)
            if success:
                print(f"✅ Successfully updated description for client {client_id}")
            else:
                print(f"⚠️ Description update returned False for client {client_id}")
        except Exception as e:
            print(f"❌ ERROR updating description for client {client_id}: {e}")
            import traceback
            traceback.print_exc()
        
        return jsonify({"id": note_id, "message": "Appointment note added"}), 201


@app.route("/api/bookings/<int:booking_id>/notes/<int:note_id>", methods=["PUT", "DELETE"])
@login_required
def appointment_note_api(booking_id, note_id):
    """Update or delete a specific appointment note"""
    db = get_database()
    
    # Get client_id for description update
    booking = db.get_booking(booking_id)
    client_id = booking['client_id'] if booking else None
    
    if request.method == "PUT":
        data = request.json
        success = db.update_appointment_note(note_id, data['note'])
        if success:
            # Update client description after editing note
            if client_id:
                print(f"\n🔄 Updating client description for client_id: {client_id} after editing note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id)
                    if success:
                        print(f"✅ Successfully updated description for client {client_id}")
                    else:
                        print(f"⚠️ Description update returned False for client {client_id}")
                except Exception as e:
                    print(f"❌ ERROR updating description: {e}")
                    import traceback
                    traceback.print_exc()
            return jsonify({"message": "Note updated"})
        return jsonify({"error": "Note not found"}), 404
    
    elif request.method == "DELETE":
        success = db.delete_appointment_note(note_id)
        if success:
            # Update client description after deleting note
            if client_id:
                print(f"\n🔄 Updating client description for client_id: {client_id} after deleting note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id)
                    if success:
                        print(f"✅ Successfully updated description for client {client_id}")
                    else:
                        print(f"⚠️ Description update returned False for client {client_id}")
                except Exception as e:
                    print(f"❌ ERROR updating description: {e}")
                    import traceback
                    traceback.print_exc()
            return jsonify({"message": "Note deleted"})
        return jsonify({"error": "Note not found"}), 404


@app.route("/api/bookings", methods=["GET", "POST"])
@login_required
def bookings_api():
    """Get all bookings or create a new booking"""
    db = get_database()
    
    if request.method == "GET":
        bookings = db.get_all_bookings()
        return jsonify(bookings)
    
    elif request.method == "POST":
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
                end_time=time_buffer_after.strftime('%Y-%m-%d %H:%M:%S')
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
                        print(f"📍 Using address from previous booking: {job_address}")
                    
                    if not job_eircode and previous_booking['eircode']:
                        job_eircode = previous_booking['eircode']
                        print(f"📮 Using eircode from previous booking: {job_eircode}")
                    
                    if not job_property_type and previous_booking.get('property_type'):
                        job_property_type = previous_booking['property_type']
                        print(f"🏠 Using property type from previous booking: {job_property_type}")
            
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
                charge=job_charge
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
                print(f"⚠️ Could not update client description: {e}")
            
            return jsonify({
                "success": True,
                "booking_id": booking_id,
                "message": "Job created successfully"
            }), 201
            
        except Exception as e:
            print(f"❌ Error creating booking: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


@app.route("/api/bookings/<int:booking_id>", methods=["GET", "PUT"])
@login_required
def booking_detail_api(booking_id):
    """Get or update a specific booking"""
    db = get_database()
    
    if request.method == "GET":
        # Get booking details using database method
        booking = db.get_booking(booking_id)
        
        if not booking:
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


@app.route("/api/bookings/<int:booking_id>/complete", methods=["POST"])
@login_required
def complete_booking_api(booking_id):
    """Mark appointment as complete and update client description using AI"""
    db = get_database()
    
    # Get the booking to find the client
    booking = db.get_booking(booking_id)
    
    if not booking:
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
        print(f"❌ Error updating description: {e}")
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
    
    try:
        # Get the booking details using database method
        booking = db.get_booking(booking_id)
        
        if not booking:
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
        
        print(f"💰 Invoice: Using charge amount €{booking_dict['charge']} from database for booking {booking_id}")
        
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
        print(f"💰 Invoice: Final charge amount = €{charge_amount}")
        
        # Generate Stripe payment link
        from src.utils.config import config
        from src.services.email_reminder import get_email_service
        from datetime import datetime
        stripe_payment_link = None
        
        # Try to create Stripe payment link if configured
        stripe_secret_key = getattr(config, 'STRIPE_SECRET_KEY', None)
        
        # Debug: Check if key is loaded
        if stripe_secret_key:
            print(f"🔑 Stripe key found: {stripe_secret_key[:12]}...{stripe_secret_key[-4:]}")
        else:
            # Try loading directly from environment as fallback
            stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
            if stripe_secret_key:
                print(f"🔑 Stripe key loaded from env: {stripe_secret_key[:12]}...{stripe_secret_key[-4:]}")
            else:
                print("❌ STRIPE_SECRET_KEY not found in config or environment!")
        
        if stripe_secret_key:
            try:
                import stripe
                stripe.api_key = stripe_secret_key
                
                # Create a payment link using Stripe Checkout
                # Amount must be in cents
                amount_cents = int(charge_amount * 100)
                
                print(f"💳 Creating Stripe checkout session for €{charge_amount} ({amount_cents} cents)...")
                
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
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
                    mode='payment',
                    success_url=f"{os.getenv('PUBLIC_URL', 'http://localhost:5000')}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{os.getenv('PUBLIC_URL', 'http://localhost:5000')}/payment-cancelled",
                    metadata={
                        'booking_id': str(booking_id),
                        'customer_name': booking_dict['client_name'],
                    }
                )
                stripe_payment_link = checkout_session.url
                print(f"✅ Stripe payment link created: {stripe_payment_link}")
            except Exception as stripe_error:
                print(f"⚠️ Could not create Stripe payment link: {stripe_error}")
                import traceback
                traceback.print_exc()
                # Continue without Stripe link - invoice will still be sent
        else:
            print("ℹ️ Stripe not configured - sending invoice without payment link")
        
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
        
        success = email_service.send_invoice(
            to_email=to_email,
            customer_name=booking_dict['client_name'],
            service_type=booking_dict.get('service_type') or 'Service',
            charge=charge_amount,
            appointment_time=appointment_time,
            stripe_payment_link=stripe_payment_link,
            job_address=job_address,
            invoice_number=invoice_number
        )
        
        if success:
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
        print(f"❌ Error sending invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/appointments/auto-complete", methods=["POST"])
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
        print(f"❌ Error in auto-complete: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/finances/stats", methods=["GET"])
@login_required
def financial_stats_api():
    """Get financial statistics"""
    db = get_database()
    stats = db.get_financial_stats()
    return jsonify(stats)


@app.route("/api/stats", methods=["GET"])
@login_required
def stats_api():
    """Get dashboard statistics"""
    db = get_database()
    # Google Calendar disabled (USE_GOOGLE_CALENDAR = False)
    
    clients = db.get_all_clients()
    bookings = db.get_all_bookings()
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
def workers_api():
    """Get all workers or create a new worker"""
    db = get_database()
    
    if request.method == "GET":
        workers = db.get_all_workers()
        return jsonify(workers)
    
    elif request.method == "POST":
        data = request.json
        
        # Upload image to R2 if it's base64
        image_url = data.get('image_url', '')
        if image_url and image_url.startswith('data:image/'):
            company_id = session.get('company_id', 0)
            image_url = upload_base64_image_to_r2(image_url, company_id, 'workers')
        
        worker_id = db.add_worker(
            name=data['name'],
            phone=data.get('phone'),
            email=data.get('email'),
            trade_specialty=data.get('trade_specialty'),
            image_url=image_url,
            weekly_hours_expected=data.get('weekly_hours_expected', 40.0)
        )
        return jsonify({"id": worker_id, "message": "Worker added"}), 201


@app.route("/api/workers/<int:worker_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def worker_api(worker_id):
    """Get, update or delete a specific worker"""
    db = get_database()
    
    if request.method == "GET":
        worker = db.get_worker(worker_id)
        if worker:
            return jsonify(worker)
        return jsonify({"error": "Worker not found"}), 404
    
    elif request.method == "PUT":
        data = request.json
        
        # Upload image to R2 if it's base64
        if 'image_url' in data and data['image_url'] and data['image_url'].startswith('data:image/'):
            company_id = session.get('company_id', 0)
            data['image_url'] = upload_base64_image_to_r2(data['image_url'], company_id, 'workers')
        
        db.update_worker(worker_id, **data)
        return jsonify({"message": "Worker updated"})
    
    elif request.method == "DELETE":
        success = db.delete_worker(worker_id)
        if success:
            return jsonify({"message": "Worker deleted"})
        return jsonify({"error": "Worker not found"}), 404


@app.route("/api/bookings/<int:booking_id>/assign-worker", methods=["POST"])
@login_required
def assign_worker_to_job_api(booking_id):
    """Assign a worker to a job"""
    db = get_database()
    data = request.json
    worker_id = data.get('worker_id')
    
    if not worker_id:
        return jsonify({"error": "worker_id is required"}), 400
    
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
    data = request.json
    worker_id = data.get('worker_id')
    
    if not worker_id:
        return jsonify({"error": "worker_id is required"}), 400
    
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
    workers = db.get_job_workers(booking_id)
    return jsonify(workers)


@app.route("/api/workers/<int:worker_id>/jobs", methods=["GET"])
@login_required
def get_worker_jobs_api(worker_id):
    """Get all jobs assigned to a worker"""
    db = get_database()
    include_completed = request.args.get('include_completed', 'false').lower() == 'true'
    jobs = db.get_worker_jobs(worker_id, include_completed)
    return jsonify(jobs)


@app.route("/api/workers/<int:worker_id>/schedule", methods=["GET"])
@login_required
def get_worker_schedule_api(worker_id):
    """Get worker's schedule"""
    db = get_database()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    schedule = db.get_worker_schedule(worker_id, start_date, end_date)
    return jsonify(schedule)


@app.route("/api/workers/<int:worker_id>/hours-this-week", methods=["GET"])
@login_required
def get_worker_hours_this_week_api(worker_id):
    """Get hours worked by worker this week"""
    db = get_database()
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
        
        print(f"✅ Email sent successfully to {to_email}")
        
        return jsonify({
            "success": True,
            "message": f"Email sent successfully to {client_name}"
        })
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/tests/run", methods=["POST"])
def run_tests():
    """Run test suite"""
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
            print(f"📝 Chat response generated ({len(response_text)} chars): {response_text[:100]}...")
            
            # If response is empty or suspiciously short, add fallback
            if not response_text or len(response_text.strip()) < 5:
                print("⚠️ WARNING: Chat response is empty or too short, using fallback")
                response_text = "I'm here to help. What can I do for you today?"
            
            return response_text
        except Exception as e:
            print(f"❌ Chat error in get_response: {e}")
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
        bookings = db.get_all_bookings()
        
        total_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings if b.get('status') == 'completed')
        pending_revenue = sum(float(b.get('charge', 0) or 0) for b in bookings if b.get('status') in ['pending', 'scheduled'])
        completed_revenue = total_revenue
        
        # Build transactions list for detailed view
        transactions = []
        for booking in bookings:
            if booking.get('charge') and float(booking.get('charge', 0)) > 0:
                transactions.append({
                    'id': booking.get('id'),
                    'customer_name': booking.get('customer_name') or booking.get('client_name') or 'Unknown',
                    'description': booking.get('service_type') or booking.get('service') or 'Service',
                    'amount': float(booking.get('charge', 0)),
                    'status': booking.get('status'),
                    'payment_status': booking.get('payment_status'),
                    'date': booking.get('appointment_time'),
                    'payment_method': booking.get('payment_method')
                })
        
        # Group by month
        from collections import defaultdict
        from datetime import datetime
        monthly = defaultdict(float)
        for booking in bookings:
            if booking.get('status') == 'completed' and booking.get('appointment_time'):
                try:
                    date = datetime.fromisoformat(booking['appointment_time'].replace('Z', '+00:00'))
                    month_key = date.strftime('%Y-%m')
                    monthly[month_key] += float(booking.get('charge', 0) or 0)
                except:
                    pass
        
        monthly_revenue = [{"month": k, "revenue": v} for k, v in sorted(monthly.items())]
        
        return jsonify({
            "total_revenue": total_revenue,
            "pending_revenue": pending_revenue,
            "completed_revenue": completed_revenue,
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
    print(f"Internal server error: {e}")
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all uncaught exceptions"""
    print(f"Unhandled exception: {e}")
    return jsonify({"error": "An unexpected error occurred"}), 500


if __name__ == "__main__":
    try:
        config.validate()
        print("✅ Configuration validated")
        print(f"🚀 Starting Flask server on port {config.PORT}")
        # Bind to 0.0.0.0 for production (Render/cloud), 127.0.0.1 for local dev
        host = "0.0.0.0" if config.FLASK_ENV == "production" else "127.0.0.1"
        app.run(host=host, port=config.PORT, debug=(config.FLASK_ENV == "development"), use_reloader=False)
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        exit(1)

