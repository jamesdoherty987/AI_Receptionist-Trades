"""
Check if a user exists in the database and verify password
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.services.database import get_database
from src.utils.security import verify_password

def check_user(email: str):
    """Check if user exists and show their info"""
    db = get_database()
    
    print(f"\n🔍 Checking for user: {email}")
    print(f"   (case-insensitive)")
    print("-" * 60)
    
    # Try exact match
    company = db.get_company_by_email(email.lower().strip())
    
    if company:
        print("✅ USER FOUND!")
        print(f"   ID: {company['id']}")
        print(f"   Email: {company['email']}")
        print(f"   Company: {company['company_name']}")
        print(f"   Owner: {company['owner_name']}")
        print(f"   Password Hash: {company['password_hash'][:50]}...")
        print(f"   Subscription: {company.get('subscription_tier', 'N/A')}")
        
        # Test password if provided
        if len(sys.argv) > 2:
            test_password = sys.argv[2]
            print(f"\n🔐 Testing password...")
            if verify_password(test_password, company['password_hash']):
                print("✅ PASSWORD MATCHES!")
            else:
                print("❌ PASSWORD DOES NOT MATCH")
                print("   The password hash in database may be incorrect")
    else:
        print("❌ USER NOT FOUND")
        print("\n🔍 Searching for similar emails...")
        
        # Search for similar emails
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = db.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT id, email, company_name, owner_name 
                FROM companies 
                WHERE email ILIKE %s
                LIMIT 10
            """, (f"%{email.split('@')[0]}%",))
            
            similar = cursor.fetchall()
            if similar:
                print(f"\n📧 Found {len(similar)} similar email(s):")
                for row in similar:
                    print(f"   - {row['email']} (ID: {row['id']}, {row['company_name']})")
            else:
                print("   No similar emails found")
                
            # Show total user count
            cursor.execute("SELECT COUNT(*) as count FROM companies")
            total = cursor.fetchone()['count']
            print(f"\n📊 Total users in database: {total}")
            
        finally:
            cursor.close()
            db.return_connection(conn)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_user.py <email> [password]")
        print("Example: python check_user.py jkdoherty123@gmail.com James123")
        sys.exit(1)
    
    email = sys.argv[1]
    check_user(email)
