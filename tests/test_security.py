"""
Security module tests
Tests password hashing, rate limiting, and input validation
"""
import pytest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.security import (
    hash_password, verify_password, needs_rehash,
    sanitize_string, validate_email, validate_phone, validate_id,
    RateLimiter, SecurityLogger,
    generate_csrf_token, verify_csrf_token,
    validate_field_names, ALLOWED_COMPANY_FIELDS
)


class TestPasswordHashing:
    """Test password hashing functions"""
    
    def test_hash_password_returns_string(self):
        """Password hash should be a string"""
        hashed = hash_password("TestPassword123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_hash_password_different_each_time(self):
        """Same password should produce different hashes (salt)"""
        hash1 = hash_password("TestPassword123")
        hash2 = hash_password("TestPassword123")
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Correct password should verify"""
        password = "TestPassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Incorrect password should not verify"""
        hashed = hash_password("TestPassword123")
        assert verify_password("WrongPassword", hashed) is False
    
    def test_verify_legacy_sha256(self):
        """Should verify legacy SHA-256 hashes"""
        import hashlib
        password = "TestPassword123"
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        assert verify_password(password, legacy_hash) is True
    
    def test_needs_rehash_sha256(self):
        """SHA-256 hashes need rehashing"""
        import hashlib
        legacy_hash = hashlib.sha256("test".encode()).hexdigest()
        assert needs_rehash(legacy_hash) is True
    
    def test_needs_rehash_bcrypt(self):
        """bcrypt hashes don't need rehashing"""
        hashed = hash_password("TestPassword123")
        if hashed.startswith("bcrypt:"):
            assert needs_rehash(hashed) is False
    
    def test_needs_rehash_pbkdf2(self):
        """PBKDF2 hashes don't need rehashing"""
        hashed = hash_password("TestPassword123")
        if hashed.startswith("pbkdf2:"):
            assert needs_rehash(hashed) is False


class TestInputSanitization:
    """Test input sanitization functions"""
    
    def test_sanitize_string_html(self):
        """Should escape HTML characters"""
        result = sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    def test_sanitize_string_max_length(self):
        """Should truncate to max length"""
        long_string = "a" * 2000
        result = sanitize_string(long_string, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_string_none(self):
        """Should handle None safely"""
        result = sanitize_string(None)
        assert result == ""
    
    def test_validate_email_valid(self):
        """Valid emails should pass"""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.org") is True
    
    def test_validate_email_invalid(self):
        """Invalid emails should fail"""
        assert validate_email("not-an-email") is False
        assert validate_email("@nodomain.com") is False
        assert validate_email("test@.com") is False
        assert validate_email("") is False
        assert validate_email(None) is False
    
    def test_validate_phone_valid(self):
        """Valid phone numbers should pass"""
        assert validate_phone("+12025551234") is True
        assert validate_phone("(202) 555-1234") is True
    
    def test_validate_phone_invalid(self):
        """Invalid phone numbers should fail"""
        assert validate_phone("abc") is False
        assert validate_phone("123") is False  # Too short
    
    def test_validate_id_valid(self):
        """Valid IDs should pass"""
        assert validate_id(1) == 1
        assert validate_id("42") == 42
        assert validate_id(100) == 100
    
    def test_validate_id_invalid(self):
        """Invalid IDs should return None"""
        assert validate_id(-1) is None
        assert validate_id("abc") is None
        assert validate_id(None) is None
        assert validate_id("1; DROP TABLE users") is None


class TestRateLimiter:
    """Test rate limiting functionality"""
    
    def test_rate_limiter_allows_initial_requests(self):
        """Should allow requests within limit"""
        limiter = RateLimiter()
        allowed, remaining = limiter.check_rate_limit("test_key", 5, 60)
        assert allowed is True
        assert remaining == 4
    
    def test_rate_limiter_blocks_excess(self):
        """Should block requests exceeding limit"""
        limiter = RateLimiter()
        for _ in range(5):
            limiter.check_rate_limit("test_key_2", 5, 60)
        
        allowed, remaining = limiter.check_rate_limit("test_key_2", 5, 60)
        assert allowed is False
        assert remaining == 0
    
    def test_rate_limiter_failed_login_blocking(self):
        """Should block after too many failed logins"""
        limiter = RateLimiter()
        for _ in range(10):
            limiter.record_failed_login("user@test.com")
        
        assert limiter.is_blocked("user@test.com") is True


class TestCSRFProtection:
    """Test CSRF token generation and verification"""
    
    def test_generate_csrf_token(self):
        """Should generate valid tokens"""
        token = generate_csrf_token()
        assert isinstance(token, str)
        assert len(token) == 64  # 32 bytes hex = 64 chars
    
    def test_verify_csrf_token_valid(self):
        """Valid token should verify"""
        token = generate_csrf_token()
        assert verify_csrf_token(token, token) is True
    
    def test_verify_csrf_token_invalid(self):
        """Invalid token should not verify"""
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert verify_csrf_token(token1, token2) is False
    
    def test_verify_csrf_token_empty(self):
        """Empty tokens should not verify"""
        assert verify_csrf_token("", "") is False
        assert verify_csrf_token(None, None) is False


class TestFieldValidation:
    """Test field name validation for injection prevention"""
    
    def test_validate_field_names_allowed(self):
        """Allowed fields should pass through"""
        fields = {"company_name": "Test", "owner_name": "John"}
        result = validate_field_names(fields, ALLOWED_COMPANY_FIELDS)
        assert result == fields
    
    def test_validate_field_names_filters_unknown(self):
        """Unknown fields should be filtered out"""
        fields = {"company_name": "Test", "sql_injection": "DROP TABLE"}
        result = validate_field_names(fields, ALLOWED_COMPANY_FIELDS)
        assert "company_name" in result
        assert "sql_injection" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
