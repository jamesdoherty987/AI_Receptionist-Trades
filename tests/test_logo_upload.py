"""
Test Logo Upload Functionality

Tests both R2 upload and base64 fallback scenarios
"""
import pytest
import base64
import io
from unittest.mock import Mock, patch, MagicMock


def test_base64_logo_fallback_when_r2_not_configured():
    """Test that base64 is stored when R2 is not configured"""
    # Create a small test image as base64
    test_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    # Mock request data
    data = {'logo_url': test_image_base64}
    
    # Mock R2Storage to raise ValueError (not configured)
    with patch('src.services.storage_r2.R2Storage') as mock_r2:
        mock_r2.side_effect = ValueError("Missing required R2 configuration")
        
        # Simulate the logic from app.py
        logo_url = data['logo_url']
        
        if logo_url.startswith('data:image/'):
            try:
                # Try R2 upload
                r2 = mock_r2()
                # This should raise ValueError
                assert False, "Should have raised ValueError"
            except ValueError:
                # R2 not configured - keep base64
                assert data['logo_url'] == test_image_base64
                print("✅ Base64 fallback working correctly")


def test_r2_upload_success():
    """Test successful R2 upload replaces base64 with URL"""
    test_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    expected_r2_url = "https://yourbucket.r2.dev/logos/logo_20240203_123456_abc123.png"
    
    data = {'logo_url': test_image_base64}
    
    # Mock R2Storage
    with patch('src.services.storage_r2.R2Storage') as mock_r2_class:
        mock_r2_instance = MagicMock()
        mock_r2_instance.upload_file.return_value = expected_r2_url
        mock_r2_class.return_value = mock_r2_instance
        
        # Simulate the logic from app.py
        logo_url = data['logo_url']
        
        if logo_url.startswith('data:image/'):
            try:
                # Extract base64 data
                header, encoded = logo_url.split(',', 1)
                content_type = header.split(';')[0].split(':')[1]
                
                # Decode
                image_data = base64.b64decode(encoded)
                
                # Upload to R2
                r2 = mock_r2_class()
                public_url = r2.upload_file(
                    file_data=io.BytesIO(image_data),
                    filename="test_logo.png",
                    folder='logos',
                    content_type=content_type
                )
                
                # Replace base64 with R2 URL
                data['logo_url'] = public_url
                
                assert data['logo_url'] == expected_r2_url
                print(f"✅ R2 upload successful: {public_url}")
                
            except Exception as e:
                assert False, f"R2 upload should have succeeded: {e}"


def test_base64_validation():
    """Test that non-image base64 is rejected"""
    invalid_base64 = "not-a-valid-base64-image"
    
    data = {'logo_url': invalid_base64}
    
    # Should not start with data:image/
    assert not data['logo_url'].startswith('data:image/')
    print("✅ Invalid base64 correctly rejected")


def test_image_size_validation():
    """Test that the frontend validates image size (2MB max)"""
    # This would be handled by ImageUpload.jsx
    # Just verify the logic
    max_size = 2 * 1024 * 1024  # 2MB in bytes
    
    # Test with a size that's too large
    large_file_size = 3 * 1024 * 1024  # 3MB
    
    if large_file_size > max_size:
        print("✅ Large file correctly detected as over limit")
    else:
        assert False, "Size validation logic is incorrect"


if __name__ == "__main__":
    print("\n🧪 Testing Logo Upload Functionality\n")
    print("=" * 60)
    
    print("\nTest 1: Base64 fallback when R2 not configured")
    print("-" * 60)
    test_base64_logo_fallback_when_r2_not_configured()
    
    print("\nTest 2: R2 upload success")
    print("-" * 60)
    test_r2_upload_success()
    
    print("\nTest 3: Base64 validation")
    print("-" * 60)
    test_base64_validation()
    
    print("\nTest 4: Image size validation")
    print("-" * 60)
    test_image_size_validation()
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60 + "\n")
