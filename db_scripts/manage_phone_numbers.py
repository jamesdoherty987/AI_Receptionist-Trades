"""
Twilio Phone Number Pool Management
Manages assignment of Twilio phone numbers from a pool to companies
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database import get_database

def add_phone_numbers_to_pool(phone_numbers: list):
    """Add phone numbers to the pool"""
    db = get_database()
    
    print(f"\n📞 Adding {len(phone_numbers)} phone numbers to pool...")
    
    for phone in phone_numbers:
        try:
            conn = db.get_connection()
            if hasattr(db, 'use_postgres') and db.use_postgres:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO twilio_phone_numbers (phone_number, status)
                    VALUES (%s, 'available')
                    ON CONFLICT (phone_number) DO NOTHING
                """, (phone,))
                conn.commit()
                db.return_connection(conn)
            else:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO twilio_phone_numbers (phone_number, status)
                    VALUES (?, 'available')
                """, (phone,))
                conn.commit()
                conn.close()
            print(f"   ✅ Added: {phone}")
        except Exception as e:
            print(f"   ⚠️  Failed to add {phone}: {e}")

def get_available_phone_numbers():
    """Get list of available phone numbers"""
    db = get_database()
    conn = db.get_connection()
    
    try:
        if hasattr(db, 'use_postgres') and db.use_postgres:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM twilio_phone_numbers 
                WHERE status = 'available'
                ORDER BY created_at
            """)
            numbers = cursor.fetchall()
            db.return_connection(conn)
        else:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM twilio_phone_numbers 
                WHERE status = 'available'
                ORDER BY created_at
            """)
            rows = cursor.fetchall()
            cursor.execute("PRAGMA table_info(twilio_phone_numbers)")
            columns = [col[1] for col in cursor.fetchall()]
            numbers = [dict(zip(columns, row)) for row in rows]
            conn.close()
        
        return numbers
    except Exception as e:
        print(f"Error getting available numbers: {e}")
        if hasattr(db, 'use_postgres') and db.use_postgres:
            db.return_connection(conn)
        else:
            conn.close()
        return []

def assign_phone_number(company_id: int):
    """Assign an available phone number to a company"""
    db = get_database()
    
    # Get first available number
    available = get_available_phone_numbers()
    if not available:
        raise Exception("No available phone numbers in pool")
    
    phone_number = available[0]['phone_number']
    
    conn = db.get_connection()
    try:
        if hasattr(db, 'use_postgres') and db.use_postgres:
            cursor = conn.cursor()
            # Update phone number status
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = %s, 
                    assigned_at = CURRENT_TIMESTAMP,
                    status = 'assigned'
                WHERE phone_number = %s
            """, (company_id, phone_number))
            
            # Update company with phone number
            cursor.execute("""
                UPDATE companies 
                SET twilio_phone_number = %s
                WHERE id = %s
            """, (phone_number, company_id))
            
            conn.commit()
            db.return_connection(conn)
        else:
            cursor = conn.cursor()
            # Update phone number status
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = ?, 
                    assigned_at = CURRENT_TIMESTAMP,
                    status = 'assigned'
                WHERE phone_number = ?
            """, (company_id, phone_number))
            
            # Update company with phone number
            cursor.execute("""
                UPDATE companies 
                SET twilio_phone_number = ?
                WHERE id = ?
            """, (phone_number, company_id))
            
            conn.commit()
            conn.close()
        
        print(f"✅ Assigned {phone_number} to company {company_id}")
        return phone_number
    except Exception as e:
        print(f"❌ Error assigning phone number: {e}")
        if hasattr(db, 'use_postgres') and db.use_postgres:
            db.return_connection(conn)
        else:
            conn.close()
        raise

def get_company_phone_number(company_id: int):
    """Get phone number assigned to a company"""
    db = get_database()
    company = db.get_company(company_id)
    return company.get('twilio_phone_number') if company else None

def list_all_phone_numbers():
    """List all phone numbers and their status"""
    db = get_database()
    conn = db.get_connection()
    
    try:
        if hasattr(db, 'use_postgres') and db.use_postgres:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT 
                    p.*,
                    c.company_name,
                    c.email
                FROM twilio_phone_numbers p
                LEFT JOIN companies c ON p.assigned_to_company_id = c.id
                ORDER BY p.status, p.created_at
            """)
            numbers = cursor.fetchall()
            db.return_connection(conn)
        else:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    p.*,
                    c.company_name,
                    c.email
                FROM twilio_phone_numbers p
                LEFT JOIN companies c ON p.assigned_to_company_id = c.id
                ORDER BY p.status, p.created_at
            """)
            rows = cursor.fetchall()
            cursor.execute("PRAGMA table_info(twilio_phone_numbers)")
            phone_cols = [col[1] for col in cursor.fetchall()]
            # Add company columns
            columns = phone_cols + ['company_name', 'email']
            numbers = [dict(zip(columns, row)) for row in rows]
            conn.close()
        
        return numbers
    except Exception as e:
        print(f"Error listing numbers: {e}")
        if hasattr(db, 'use_postgres') and db.use_postgres:
            db.return_connection(conn)
        else:
            conn.close()
        return []

if __name__ == "__main__":
    print("\n" + "="*60)
    print("📞 TWILIO PHONE NUMBER POOL MANAGER")
    print("="*60)
    
    # Example: Add your current Twilio number to the pool
    # Replace with your actual Twilio phone number
    current_number = os.getenv('TWILIO_PHONE_NUMBER', '+353123456789')
    
    print(f"\n1️⃣ Adding current Twilio number to pool...")
    add_phone_numbers_to_pool([current_number])
    
    print(f"\n2️⃣ Listing all phone numbers...")
    all_numbers = list_all_phone_numbers()
    for num in all_numbers:
        status_emoji = "✅" if num['status'] == 'assigned' else "⭕"
        company_info = f" → {num['company_name']}" if num.get('company_name') else ""
        print(f"   {status_emoji} {num['phone_number']} ({num['status']}){company_info}")
    
    print(f"\n3️⃣ Available numbers: {len(get_available_phone_numbers())}")
    
    print("\n" + "="*60)
    print("✅ Phone number pool ready!")
    print("="*60)
