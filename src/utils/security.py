"""
Security utilities for AI Receptionist
Provides cryptographic functions, rate limiting, input validation, and security headers
Addresses OWASP Top 10 vulnerabilities
"""
import os
import re
import hmac
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from collections import defaultdict
import threading

# Try to import bcrypt for password hashing
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("⚠️ bcrypt not installed. Using PBKDF2 as fallback. Run: pip install bcrypt")


# =============================================================================
# PASSWORD HASHING (OWASP A02 - Cryptographic Failures)
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt (preferred) or PBKDF2 (fallback).
    Returns a secure hash suitable for storage.
    
    Args:
        password: Plain text password
        
    Returns:
        Secure password hash string
    """
    if BCRYPT_AVAILABLE:
        # bcrypt automatically handles salt and is resistant to timing attacks
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)  # Cost factor of 12 (recommended)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return f"bcrypt:{hashed.decode('utf-8')}"
    else:
        # Fallback to PBKDF2 with SHA-256 (still secure, but bcrypt preferred)
        salt = secrets.token_hex(32)
        iterations = 600000  # OWASP recommended minimum for PBKDF2-SHA256
        hash_bytes = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        return f"pbkdf2:{salt}:{iterations}:{hash_bytes.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.
    Supports bcrypt, PBKDF2, and legacy SHA-256 hashes.
    
    Args:
        password: Plain text password to verify
        stored_hash: Previously stored password hash
        
    Returns:
        True if password matches, False otherwise
    """
    if not stored_hash or not password:
        return False
    
    try:
        if stored_hash.startswith('bcrypt:'):
            if not BCRYPT_AVAILABLE:
                print("❌ bcrypt hash found but bcrypt not installed")
                return False
            hash_value = stored_hash[7:]  # Remove 'bcrypt:' prefix
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hash_value.encode('utf-8')
            )
        
        elif stored_hash.startswith('pbkdf2:'):
            parts = stored_hash.split(':')
            if len(parts) != 4:
                return False
            _, salt, iterations, hash_hex = parts
            computed_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                int(iterations)
            )
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(computed_hash.hex(), hash_hex)
        
        else:
            # Legacy SHA-256 hash (salt:hash format) - migrate users on next login
            if ':' in stored_hash:
                salt, password_hash = stored_hash.split(':', 1)
                computed = hashlib.sha256((password + salt).encode()).hexdigest()
                # Use constant-time comparison
                return hmac.compare_digest(computed, password_hash)
            return False
            
    except Exception as e:
        print(f"⚠️ Password verification error: {e}")
        return False


def needs_rehash(stored_hash: str) -> bool:
    """
    Check if a password hash needs to be upgraded to a stronger algorithm.
    
    Args:
        stored_hash: The stored password hash
        
    Returns:
        True if the hash should be upgraded
    """
    if not stored_hash:
        return True
    
    # Legacy SHA-256 hashes need upgrade
    if not stored_hash.startswith(('bcrypt:', 'pbkdf2:')):
        return True
    
    # PBKDF2 should be upgraded to bcrypt if available
    if stored_hash.startswith('pbkdf2:') and BCRYPT_AVAILABLE:
        return True
    
    return False


# =============================================================================
# RATE LIMITING (OWASP A07 - Authentication Failures)
# =============================================================================

class RateLimiter:
    """
    Thread-safe rate limiter to prevent brute force attacks.
    Uses token bucket algorithm with IP-based tracking.
    """
    
    def __init__(self):
        # Use RLock (reentrant lock) to allow nested lock acquisition
        # This prevents deadlock when check_rate_limit calls is_blocked
        self._lock = threading.RLock()
        self._requests: Dict[str, list] = defaultdict(list)
        self._blocked: Dict[str, datetime] = {}
        
        # Configuration
        self.max_requests_per_minute = 60
        self.max_login_attempts = 5
        self.login_window_seconds = 300  # 5 minutes
        self.block_duration_seconds = 900  # 15 minutes
    
    def _cleanup_old_requests(self, key: str, window_seconds: int):
        """Remove requests older than the window"""
        cutoff = time.time() - window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
    
    def is_blocked(self, identifier: str) -> bool:
        """Check if an identifier (IP/email) is currently blocked"""
        with self._lock:
            if identifier in self._blocked:
                if datetime.now() < self._blocked[identifier]:
                    return True
                else:
                    del self._blocked[identifier]
            return False
    
    def check_rate_limit(self, identifier: str, limit: int = None, 
                         window_seconds: int = 60) -> Tuple[bool, int]:
        """
        Check if request should be rate limited.
        
        Args:
            identifier: Unique identifier (IP address, user ID, etc.)
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if limit is None:
            limit = self.max_requests_per_minute
            
        with self._lock:
            if self.is_blocked(identifier):
                return False, 0
            
            self._cleanup_old_requests(identifier, window_seconds)
            
            if len(self._requests[identifier]) >= limit:
                return False, 0
            
            self._requests[identifier].append(time.time())
            remaining = limit - len(self._requests[identifier])
            return True, remaining
    
    def record_failed_login(self, identifier: str) -> bool:
        """
        Record a failed login attempt. Returns True if account should be blocked.
        
        Args:
            identifier: Email or IP address
            
        Returns:
            True if the identifier should now be blocked
        """
        with self._lock:
            self._cleanup_old_requests(f"login:{identifier}", self.login_window_seconds)
            self._requests[f"login:{identifier}"].append(time.time())
            
            if len(self._requests[f"login:{identifier}"]) >= self.max_login_attempts:
                self._blocked[identifier] = datetime.now() + timedelta(
                    seconds=self.block_duration_seconds
                )
                return True
            return False
    
    def clear_failed_logins(self, identifier: str):
        """Clear failed login attempts after successful login"""
        with self._lock:
            key = f"login:{identifier}"
            if key in self._requests:
                del self._requests[key]
            if identifier in self._blocked:
                del self._blocked[identifier]


# Global rate limiter instance
_rate_limiter = None

def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# =============================================================================
# INPUT VALIDATION & SANITIZATION (OWASP A03 - Injection)
# =============================================================================

def sanitize_string(value: str, max_length: int = 1000, 
                    allow_html: bool = False) -> str:
    """
    Sanitize a string input to prevent injection attacks.
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        allow_html: Whether to allow HTML (default False)
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return ""
    
    # Truncate to max length
    value = value[:max_length]
    
    if not allow_html:
        # Escape HTML special characters
        value = (value
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;')
        )
    
    # Remove null bytes and other dangerous characters
    value = value.replace('\x00', '')
    
    return value.strip()


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid email format
    """
    if not email or not isinstance(email, str):
        return False
    
    # RFC 5322 compliant email regex (simplified)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.lower().strip()))


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid phone format
    """
    if not phone or not isinstance(phone, str):
        return False
    
    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
    
    # Check if it's a valid phone number (10-15 digits, optional +)
    pattern = r'^\+?[0-9]{10,15}$'
    return bool(re.match(pattern, cleaned))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for file system operations
    """
    if not filename:
        return "unnamed_file"
    
    # Remove path separators and dangerous characters
    filename = os.path.basename(filename)
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    filename = filename.strip('. ')
    
    if not filename:
        return "unnamed_file"
    
    return filename[:255]  # Max filename length


def validate_id(id_value: Any) -> Optional[int]:
    """
    Validate and convert an ID value to integer.
    
    Args:
        id_value: Value to validate as ID
        
    Returns:
        Integer ID or None if invalid
    """
    try:
        id_int = int(id_value)
        if id_int > 0:
            return id_int
    except (TypeError, ValueError):
        pass
    return None


# =============================================================================
# SECURE TOKEN GENERATION (OWASP A07 - Authentication Failures)
# =============================================================================

def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Length of the token in bytes (output will be 2x in hex)
        
    Returns:
        Secure random token as hex string
    """
    return secrets.token_hex(length)


def generate_csrf_token() -> str:
    """
    Generate a CSRF token for form protection.
    
    Returns:
        CSRF token string
    """
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, stored_token: str) -> bool:
    """
    Verify a CSRF token using constant-time comparison.
    
    Args:
        token: Token from request
        stored_token: Token from session
        
    Returns:
        True if tokens match
    """
    if not token or not stored_token:
        return False
    return hmac.compare_digest(token, stored_token)


# =============================================================================
# SECURITY HEADERS (OWASP A05 - Security Misconfiguration)
# =============================================================================

def get_security_headers() -> Dict[str, str]:
    """
    Get recommended security headers for HTTP responses.
    
    Returns:
        Dictionary of security headers
    """
    return {
        # Prevent clickjacking
        'X-Frame-Options': 'DENY',
        
        # Prevent MIME type sniffing
        'X-Content-Type-Options': 'nosniff',
        
        # Enable XSS filter
        'X-XSS-Protection': '1; mode=block',
        
        # Referrer policy
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        
        # Content Security Policy (adjust based on your needs)
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://js.stripe.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https:; connect-src 'self' https://api.stripe.com https://*.openai.com https://*.deepgram.com; frame-src https://js.stripe.com;",
        
        # Permissions Policy
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
        
        # HSTS (only enable in production with HTTPS)
        # 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    }


def apply_security_headers(response):
    """
    Apply security headers to a Flask response.
    
    Args:
        response: Flask response object
        
    Returns:
        Response with security headers applied
    """
    headers = get_security_headers()
    for header, value in headers.items():
        response.headers[header] = value
    return response


# =============================================================================
# SECURITY LOGGING (OWASP A09 - Security Logging Failures)
# =============================================================================

class SecurityLogger:
    """
    Security event logger for audit trail and intrusion detection.
    """
    
    def __init__(self):
        self._log_file = os.getenv('SECURITY_LOG_FILE', 'logs/security.log')
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """Create log directory if it doesn't exist"""
        log_dir = os.path.dirname(self._log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    def _log(self, event_type: str, details: Dict[str, Any], severity: str = 'INFO'):
        """Write a security log entry"""
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'severity': severity,
            'event_type': event_type,
            'details': details
        }
        
        # Also print to console for development
        print(f"🔐 [{severity}] {event_type}: {details}")
        
        # Write to log file
        try:
            import json
            with open(self._log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"⚠️ Could not write security log: {e}")
    
    def log_login_attempt(self, email: str, ip_address: str, success: bool):
        """Log a login attempt"""
        self._log(
            'LOGIN_ATTEMPT',
            {
                'email': email,
                'ip_address': ip_address,
                'success': success
            },
            severity='INFO' if success else 'WARNING'
        )
    
    def log_failed_auth(self, endpoint: str, ip_address: str, reason: str):
        """Log a failed authentication attempt"""
        self._log(
            'AUTH_FAILURE',
            {
                'endpoint': endpoint,
                'ip_address': ip_address,
                'reason': reason
            },
            severity='WARNING'
        )
    
    def log_rate_limit(self, identifier: str, endpoint: str):
        """Log a rate limit event"""
        self._log(
            'RATE_LIMIT',
            {
                'identifier': identifier,
                'endpoint': endpoint
            },
            severity='WARNING'
        )
    
    def log_suspicious_activity(self, description: str, details: Dict[str, Any]):
        """Log suspicious activity"""
        self._log(
            'SUSPICIOUS_ACTIVITY',
            {
                'description': description,
                **details
            },
            severity='ALERT'
        )
    
    def log_password_change(self, user_id: int, ip_address: str):
        """Log a password change"""
        self._log(
            'PASSWORD_CHANGE',
            {
                'user_id': user_id,
                'ip_address': ip_address
            },
            severity='INFO'
        )


# Global security logger instance
_security_logger = None

def get_security_logger() -> SecurityLogger:
    """Get or create global security logger instance"""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger


# =============================================================================
# SQL INJECTION PREVENTION HELPERS (OWASP A03 - Injection)
# =============================================================================

# Allowed field names for dynamic updates (whitelist approach)
ALLOWED_CLIENT_FIELDS = frozenset([
    'name', 'phone', 'email', 'date_of_birth', 'description', 'address', 'eircode'
])

ALLOWED_BOOKING_FIELDS = frozenset([
    'calendar_event_id', 'appointment_time', 'service_type', 'status',
    'phone_number', 'email', 'charge', 'payment_status', 'payment_method',
    'urgency', 'address', 'eircode', 'property_type'
])

ALLOWED_COMPANY_FIELDS = frozenset([
    'company_name', 'owner_name', 'phone', 'trade_type', 'address',
    'logo_url', 'business_hours', 'ai_enabled'
])

ALLOWED_WORKER_FIELDS = frozenset([
    'name', 'phone', 'email', 'trade_specialty', 'status', 'image_url',
    'weekly_hours_expected'
])


def validate_field_names(fields: Dict[str, Any], allowed: frozenset) -> Dict[str, Any]:
    """
    Filter dictionary to only include allowed field names.
    Prevents SQL injection via dynamic field names.
    
    Args:
        fields: Dictionary of field names and values
        allowed: Set of allowed field names
        
    Returns:
        Filtered dictionary with only allowed fields
    """
    return {k: v for k, v in fields.items() if k in allowed}


# =============================================================================
# SESSION SECURITY (OWASP A07 - Authentication Failures)
# =============================================================================

def configure_secure_session(app):
    """
    Configure Flask session with secure settings.
    
    Args:
        app: Flask application instance
    """
    import os
    
    # Generate a secure secret key if not set
    if not app.secret_key or app.secret_key == 'dev':
        app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
    
    # Session configuration
    app.config.update(
        SESSION_COOKIE_SECURE=os.getenv('FLASK_ENV') == 'production',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',  # 'Strict' for more security, 'Lax' for usability
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_REFRESH_EACH_REQUEST=True,
    )
