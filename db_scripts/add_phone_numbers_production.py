"""
Add Phone Numbers to Production Database
Run this script locally - it automatically loads DATABASE_URL from .env file.

Usage:
    # Add DATABASE_URL to your .env file:
    DATABASE_URL=postgresql://user:password@host.render.com:5432/database_name
    
    # Then run:
    python db_scripts/add_phone_numbers_production.py +353123456789 +353987654321
    
    # Or add from a file (one number per line)
    python db_scripts/add_phone_numbers_production.py --from-file numbers.txt
    
    # View current phone pool
    python db_scripts/add_phone_numbers_production.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def add_numbers_to_production(phone_numbers: list):
    """Add phone numbers to production database"""
    from src.services.database import get_database
    
    db = get_database()
    print(f"\n📞 Adding {len(phone_numbers)} phone numbers to database...")
    print(f"Database type: {'PostgreSQL' if hasattr(db, 'use_postgres') and db.use_postgres else 'SQLite'}\n")
    
    added = 0
    skipped = 0
    errors = 0
    
    for phone in phone_numbers:
        phone = phone.strip()
        if not phone or not phone.startswith('+'):
            print(f"   ⚠️  Skipping invalid format: {phone} (must start with +)")
            skipped += 1
            continue
            
        try:
            conn = db.get_connection()
            if hasattr(db, 'use_postgres') and db.use_postgres:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO twilio_phone_numbers (phone_number, status)
                    VALUES (%s, 'available')
                    ON CONFLICT (phone_number) DO NOTHING
                    RETURNING phone_number
                """, (phone,))
                result = cursor.fetchone()
                conn.commit()
                db.return_connection(conn)
                
                if result:
                    print(f"   ✅ Added: {phone}")
                    added += 1
                else:
                    print(f"   ⏭️  Already exists: {phone}")
                    skipped += 1
            else:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO twilio_phone_numbers (phone_number, status)
                    VALUES (?, 'available')
                """, (phone,))
                if cursor.rowcount > 0:
                    print(f"   ✅ Added: {phone}")
                    added += 1
                else:
                    print(f"   ⏭️  Already exists: {phone}")
                    skipped += 1
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"   ❌ Failed to add {phone}: {e}")
            errors += 1
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  ✅ Added: {added}")
    print(f"  ⏭️  Skipped: {skipped}")
    print(f"  ❌ Errors: {errors}")
    print(f"{'='*60}\n")
    
    return added > 0

def list_all_numbers():
    """List all phone numbers in the database"""
    from src.services.database import get_database
    
    db = get_database()
    conn = db.get_connection()
    
    try:
        if hasattr(db, 'use_postgres') and db.use_postgres:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT 
                    p.phone_number,
                    p.status,
                    p.assigned_at,
                    c.company_name AS company_name,
                    c.email AS email
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
                    p.phone_number,
                    p.status,
                    p.assigned_at,
                    c.company_name AS company_name,
                    c.email AS email
                FROM twilio_phone_numbers p
                LEFT JOIN companies c ON p.assigned_to_company_id = c.id
                ORDER BY p.status, p.created_at
            """)
            rows = cursor.fetchall()
            # Convert to dict
            columns = ['phone_number', 'status', 'assigned_at', 'company_name', 'email']
            numbers = [dict(zip(columns, row)) for row in rows]
            conn.close()
        
        print(f"\n{'='*80}")
        print(f"📞 PHONE NUMBER POOL STATUS")
        print(f"{'='*80}\n")
        
        available = []
        assigned = []
        
        for num in numbers:
            if num['status'] == 'available':
                available.append(num)
            else:
                assigned.append(num)
        
        if available:
            print(f"⭕ AVAILABLE ({len(available)}):")
            for num in available:
                print(f"   {num['phone_number']}")
        
        if assigned:
            print(f"\n✅ ASSIGNED ({len(assigned)}):")
            for num in assigned:
                company_info = f"{num['company_name']} ({num['email']})" if num['company_name'] else "Unknown"
                assigned_date = num['assigned_at'][:10] if num['assigned_at'] else "Unknown"
                print(f"   {num['phone_number']} → {company_info} (since {assigned_date})")
        
        print(f"\n{'='*80}")
        print(f"Total: {len(numbers)} | Available: {len(available)} | Assigned: {len(assigned)}")
        print(f"{'='*80}\n")
        
        return numbers
    except Exception as e:
        print(f"❌ Error listing numbers: {e}")
        if hasattr(db, 'use_postgres') and db.use_postgres:
            db.return_connection(conn)
        else:
            conn.close()
        return []

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Add Twilio phone numbers to production database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Add single number
    python add_phone_numbers_production.py +353123456789
    
    # Add multiple numbers
    python add_phone_numbers_production.py +353123456789 +353987654321 +353555555555
    
    # Add from file
    python add_phone_numbers_production.py --from-file numbers.txt
    
    # List all numbers
    python add_phone_numbers_production.py --list
        """
    )
    parser.add_argument('numbers', nargs='*', help='Phone numbers to add (format: +353...)')
    parser.add_argument('--from-file', '-f', help='Read phone numbers from file (one per line)')
    parser.add_argument('--list', '-l', action='store_true', help='List all phone numbers')
    
    args = parser.parse_args()
    
    # Check DATABASE_URL
    if not os.getenv('DATABASE_URL'):
        print("\n⚠️  WARNING: DATABASE_URL not set!")
        print("This will use local SQLite database.")
        print("\nTo connect to production database:")
        print("  export DATABASE_URL='postgresql://user:password@host:port/database'")
        print("  # or on Windows PowerShell:")
        print("  $env:DATABASE_URL='postgresql://user:password@host:port/database'")
        print()
        
        response = input("Continue with local database? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    else:
        print(f"✅ Using production database")
    
    # List numbers
    if args.list:
        list_all_numbers()
        sys.exit(0)
    
    # Collect phone numbers
    phone_numbers = []
    
    if args.from_file:
        try:
            with open(args.from_file, 'r') as f:
                phone_numbers = [line.strip() for line in f if line.strip()]
            print(f"📄 Read {len(phone_numbers)} numbers from {args.from_file}")
        except FileNotFoundError:
            print(f"❌ File not found: {args.from_file}")
            sys.exit(1)
    
    if args.numbers:
        phone_numbers.extend(args.numbers)
    
    if not phone_numbers:
        print("❌ No phone numbers provided!")
        print("Usage: python add_phone_numbers_production.py +353123456789 [+353...]")
        print("   or: python add_phone_numbers_production.py --from-file numbers.txt")
        print("   or: python add_phone_numbers_production.py --list")
        sys.exit(1)
    
    # Add numbers
    success = add_numbers_to_production(phone_numbers)
    
    # Show summary
    if success:
        print("✅ Done! Phone numbers added to pool.")
        print("\nNext steps:")
        print("  1. Configure webhook URLs in Twilio Console")
        print("  2. Set webhook to: https://your-backend.onrender.com/twilio/voice")
        print("  3. New signups will automatically get assigned a number")
    else:
        print("⚠️  No numbers were added.")
    
    # Offer to list
    print()
    response = input("List all phone numbers now? (y/n): ")
    if response.lower() == 'y':
        list_all_numbers()
