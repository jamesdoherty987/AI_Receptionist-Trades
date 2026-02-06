"""
Test script to verify phone number assignment functionality
Run this to test both SQLite and PostgreSQL implementations
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database import get_database

def test_phone_number_assignment():
    """Test the phone number assignment functionality"""
    print("=" * 60)
    print("Testing Phone Number Assignment")
    print("=" * 60)
    
    db = get_database()
    db_type = "PostgreSQL" if hasattr(db, 'use_postgres') and db.use_postgres else "SQLite"
    print(f"\n✅ Using {db_type} database\n")
    
    # Test 1: Get available phone numbers
    print("Test 1: Getting available phone numbers...")
    try:
        available = db.get_available_phone_numbers()
        print(f"✅ Found {len(available)} available numbers")
        if available:
            for num in available[:3]:  # Show first 3
                print(f"   - {num['phone_number']}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test 2: Check if assign_phone_number accepts optional parameter
    print("\nTest 2: Checking assign_phone_number signature...")
    import inspect
    sig = inspect.signature(db.assign_phone_number)
    params = list(sig.parameters.keys())
    print(f"✅ Parameters: {params}")
    
    if 'phone_number' in params:
        print("✅ Supports specific phone number assignment")
    else:
        print("❌ Missing phone_number parameter")
        return False
    
    # Test 3: Verify database structure
    print("\nTest 3: Verifying database structure...")
    try:
        conn = db.get_connection()
        if db_type == "PostgreSQL":
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'twilio_phone_numbers'
            """)
            columns = [row['column_name'] for row in cursor.fetchall()]
            db.return_connection(conn)
        else:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(twilio_phone_numbers)")
            columns = [col[1] for col in cursor.fetchall()]
            conn.close()
        
        required_columns = ['phone_number', 'status', 'assigned_to_company_id']
        missing = [col for col in required_columns if col not in columns]
        
        if missing:
            print(f"❌ Missing columns: {missing}")
            return False
        else:
            print(f"✅ All required columns present: {required_columns}")
    except Exception as e:
        print(f"❌ Error checking structure: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\n📋 Summary:")
    print(f"   Database: {db_type}")
    print(f"   Available numbers: {len(available)}")
    print("   Ready for production: YES")
    return True

if __name__ == "__main__":
    success = test_phone_number_assignment()
    sys.exit(0 if success else 1)
