"""
Release Twilio Phone Numbers from Companies
Interactive script to detach phone numbers from accounts
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database import get_database


def get_companies_with_phones():
    """Get all companies that have a phone number assigned"""
    db = get_database()
    conn = db.get_connection()
    
    try:
        if hasattr(db, 'use_postgres') and db.use_postgres:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, company_name, email, twilio_phone_number
                FROM companies
                WHERE twilio_phone_number IS NOT NULL
                ORDER BY id
            """)
            companies = cursor.fetchall()
            db.return_connection(conn)
        else:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, company_name, email, twilio_phone_number
                FROM companies
                WHERE twilio_phone_number IS NOT NULL
                ORDER BY id
            """)
            rows = cursor.fetchall()
            companies = [{'id': r[0], 'company_name': r[1], 'email': r[2], 'twilio_phone_number': r[3]} for r in rows]
            conn.close()
        return companies
    except Exception as e:
        print(f"Error: {e}")
        return []


def release_phone_number(company_id: int):
    """Release phone number from a specific company"""
    db = get_database()
    conn = db.get_connection()
    
    try:
        if hasattr(db, 'use_postgres') and db.use_postgres:
            cursor = conn.cursor()
            # Release from phone pool
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = NULL, status = 'available', assigned_at = NULL
                WHERE assigned_to_company_id = %s
            """, (company_id,))
            # Clear from company
            cursor.execute("""
                UPDATE companies SET twilio_phone_number = NULL WHERE id = %s
            """, (company_id,))
            conn.commit()
            db.return_connection(conn)
        else:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = NULL, status = 'available', assigned_at = NULL
                WHERE assigned_to_company_id = ?
            """, (company_id,))
            cursor.execute("""
                UPDATE companies SET twilio_phone_number = NULL WHERE id = ?
            """, (company_id,))
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"Error releasing phone: {e}")
        return False


def release_all_phones():
    """Release all phone numbers from all companies"""
    db = get_database()
    conn = db.get_connection()
    
    try:
        if hasattr(db, 'use_postgres') and db.use_postgres:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = NULL, status = 'available', assigned_at = NULL
                WHERE status = 'assigned'
            """)
            cursor.execute("UPDATE companies SET twilio_phone_number = NULL")
            conn.commit()
            db.return_connection(conn)
        else:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE twilio_phone_numbers 
                SET assigned_to_company_id = NULL, status = 'available', assigned_at = NULL
                WHERE status = 'assigned'
            """)
            cursor.execute("UPDATE companies SET twilio_phone_number = NULL")
            conn.commit()
            conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("📞 RELEASE PHONE NUMBERS FROM COMPANIES")
    print("="*60)
    
    companies = get_companies_with_phones()
    
    if not companies:
        print("\n✅ No companies have phone numbers assigned.")
        return
    
    print(f"\nCompanies with assigned phone numbers:\n")
    for i, c in enumerate(companies, 1):
        print(f"  {i}. [{c['id']}] {c['company_name']} - {c['twilio_phone_number']}")
    
    print(f"\n  A. Release ALL phone numbers")
    print(f"  Q. Quit\n")
    
    choice = input("Enter number to release (1-{}) or A/Q: ".format(len(companies))).strip().upper()
    
    if choice == 'Q':
        print("Cancelled.")
        return
    
    if choice == 'A':
        confirm = input(f"\n⚠️  Release ALL {len(companies)} phone numbers? (yes/no): ").strip().lower()
        if confirm == 'yes':
            if release_all_phones():
                print(f"\n✅ Released all phone numbers!")
            else:
                print(f"\n❌ Failed to release phone numbers")
        else:
            print("Cancelled.")
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(companies):
            company = companies[idx]
            confirm = input(f"\nRelease {company['twilio_phone_number']} from {company['company_name']}? (yes/no): ").strip().lower()
            if confirm == 'yes':
                if release_phone_number(company['id']):
                    print(f"\n✅ Released {company['twilio_phone_number']} from {company['company_name']}")
                else:
                    print(f"\n❌ Failed to release phone number")
            else:
                print("Cancelled.")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")


if __name__ == "__main__":
    main()
