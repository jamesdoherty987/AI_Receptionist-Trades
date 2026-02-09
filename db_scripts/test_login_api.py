"""
Test login API endpoint directly
Useful for diagnosing production login issues
"""
import sys
import requests
import json

def test_login(base_url, email, password):
    """Test the login API endpoint"""
    
    print(f"\n{'='*60}")
    print(f"Testing Login API")
    print(f"{'='*60}")
    print(f"Base URL: {base_url}")
    print(f"Email: {email}")
    print(f"Password: {'*' * len(password)}")
    print(f"{'='*60}\n")
    
    # Step 1: Check configuration
    print("Step 1: Checking server configuration...")
    try:
        config_url = f"{base_url}/api/config-check"
        config_response = requests.get(config_url)
        config_data = config_response.json()
        
        print(f"✓ Server responded (Status: {config_response.status_code})")
        print(f"  - Flask ENV: {config_data.get('flask_env', 'unknown')}")
        print(f"  - Production Mode: {config_data.get('is_production_mode', False)}")
        print(f"  - SECRET_KEY Set: {config_data.get('secret_key_env_set', False)}")
        print(f"  - Session Secure: {config_data.get('session_config', {}).get('cookie_secure', False)}")
        print(f"  - Session SameSite: {config_data.get('session_config', {}).get('cookie_samesite', 'unknown')}")
        
        recommendations = config_data.get('recommendations', [])
        if recommendations:
            print(f"\n  Recommendations:")
            for rec in recommendations:
                print(f"    {rec}")
        
        print()
    except requests.exceptions.RequestException as e:
        print(f"✗ Error checking config: {e}\n")
        return False
    
    # Step 2: Test login
    print("Step 2: Attempting login...")
    try:
        login_url = f"{base_url}/api/auth/login"
        headers = {
            'Content-Type': 'application/json',
            'Origin': base_url  # Simulate browser origin
        }
        data = {
            'email': email,
            'password': password
        }
        
        # Create session to handle cookies
        session = requests.Session()
        login_response = session.post(login_url, json=data, headers=headers)
        
        print(f"Response Status: {login_response.status_code}")
        print(f"\nResponse Headers:")
        for header, value in login_response.headers.items():
            if header.lower() in ['set-cookie', 'access-control-allow-origin', 'access-control-allow-credentials']:
                print(f"  {header}: {value}")
        
        print(f"\nResponse Body:")
        try:
            response_data = login_response.json()
            print(json.dumps(response_data, indent=2))
            
            if login_response.status_code == 200 and response_data.get('success'):
                print(f"\n✓ Login SUCCESSFUL!")
                
                # Step 3: Test session persistence
                print(f"\nStep 3: Testing session persistence...")
                me_url = f"{base_url}/api/auth/me"
                me_response = session.get(me_url, headers=headers)
                
                print(f"Auth Check Status: {me_response.status_code}")
                me_data = me_response.json()
                
                if me_data.get('authenticated'):
                    print(f"✓ Session is valid!")
                    print(f"  User: {me_data.get('user', {}).get('email', 'unknown')}")
                else:
                    print(f"✗ Session is NOT valid - cookies not being sent/received")
                    print(f"  This indicates a cookie/session issue")
                
                return True
            else:
                print(f"\n✗ Login FAILED")
                error = response_data.get('error', 'Unknown error')
                code = response_data.get('code', 'N/A')
                print(f"  Error: {error}")
                print(f"  Code: {code}")
                
                if 'debug' in response_data:
                    print(f"  Debug: {response_data['debug']}")
                
                return False
                
        except ValueError:
            print(login_response.text)
            print(f"\n✗ Invalid JSON response")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error during login: {e}")
        return False

def test_cors(base_url, origin):
    """Test CORS configuration"""
    print(f"\n{'='*60}")
    print(f"Testing CORS Configuration")
    print(f"{'='*60}")
    print(f"Origin: {origin}\n")
    
    try:
        # Preflight request
        headers = {
            'Origin': origin,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type'
        }
        
        response = requests.options(f"{base_url}/api/auth/login", headers=headers)
        
        print(f"Preflight Response Status: {response.status_code}")
        print(f"\nCORS Headers:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"  {header}: {value}")
        
        allow_origin = response.headers.get('Access-Control-Allow-Origin')
        allow_creds = response.headers.get('Access-Control-Allow-Credentials')
        
        if allow_origin and allow_creds == 'true':
            print(f"\n✓ CORS is configured correctly for {origin}")
        else:
            print(f"\n✗ CORS issue detected:")
            if not allow_origin:
                print(f"  - Origin '{origin}' is not in allowed_origins list")
            if allow_creds != 'true':
                print(f"  - Credentials not allowed (needed for session cookies)")
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error testing CORS: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python test_login_api.py <base_url> <email> <password> [origin]")
        print("\nExamples:")
        print("  Production:")
        print("    python test_login_api.py https://your-backend.onrender.com jkdoherty123@gmail.com James123 https://www.bookedforyou.info")
        print("\n  Local:")
        print("    python test_login_api.py http://localhost:5000 jkdoherty123@gmail.com James123")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    email = sys.argv[2]
    password = sys.argv[3]
    origin = sys.argv[4] if len(sys.argv) > 4 else base_url
    
    # Test CORS if origin is different from base_url
    if origin != base_url:
        test_cors(base_url, origin)
    
    # Test login
    success = test_login(base_url, email, password)
    
    print(f"\n{'='*60}")
    if success:
        print("✓ All tests PASSED - Login is working!")
    else:
        print("✗ Tests FAILED - Check the errors above")
        print("\nTroubleshooting:")
        print("1. Check that SECRET_KEY is set in production environment")
        print("2. Verify your frontend URL is in allowed_origins list")
        print("3. Check server logs for detailed error messages")
        print("4. Read PRODUCTION_TROUBLESHOOTING.md for more help")
    print(f"{'='*60}\n")
    
    sys.exit(0 if success else 1)
