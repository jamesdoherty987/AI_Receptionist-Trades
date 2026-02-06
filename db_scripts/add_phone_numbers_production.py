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
    is_postgres = db.__class__.__name__ == 'PostgreSQLDatabaseWrapper'
    print(f"\n📞 Adding {len(phone_numbers)} phone numbers to database...")
    print(f"Database type: {'PostgreSQL' if is_postgres else 'SQLite'}\n")
    
    added = 0
    skipped = 0
    errors = 0
    
    # Remove duplicates from input list first
    phone_numbers = list(set([p.strip() for p in phone_numbers]))
    
    for phone in phone_numbers:
        phone = phone.strip()
        if not phone or not phone.startswith('+'):
            print(f"   ⚠️  Skipping invalid format: {phone} (must start with +)")
            skipped += 1
            continue
            
        try:
            conn = db.get_connection()
            if is_postgres:
                cursor = conn.cursor()
                # Check if number already exists first
                cursor.execute("""
                    SELECT phone_number FROM twilio_phone_numbers 
                    WHERE phone_number = %s
                """, (phone,))
                existing = cursor.fetchone()
                
                if existing:
                    print(f"   ⏭️  Already exists: {phone}")
                    skipped += 1
                    db.return_connection(conn)
                    continue
                
                # Insert new number
                cursor.execute("""
                    INSERT INTO twilio_phone_numbers (phone_number, status)
                    VALUES (%s, 'available')
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
                # Check if number already exists first
                cursor.execute("""
                    SELECT phone_number FROM twilio_phone_numbers 
                    WHERE phone_number = ?
                """, (phone,))
                existing = cursor.fetchone()
                
                if existing:
                    print(f"   ⏭️  Already exists: {phone}")
                    skipped += 1
                    conn.close()
                    continue
                
                # Insert new number
                cursor.execute("""
                    INSERT INTO twilio_phone_numbers (phone_number, status)
                    VALUES (?, 'available')
                """, (phone,))
                if cursor.rowcount > 0:
                    print(f"   ✅ Added: {phone}")
                    added += 1
                else:
                    print(f"   ⏭️  Skipped: {phone}")
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
    is_postgres = db.__class__.__name__ == 'PostgreSQLDatabaseWrapper'
    conn = db.get_connection()
    
    try:
        if is_postgres:
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
    parser.add_argument('--both', '-b', action='store_true', help='Add to both production and local databases')
    
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
    
    # Check if we should add to both databases
    if args.both and os.getenv('DATABASE_URL'):
        print("\n🔄 Adding to BOTH databases (Production + Local)\n")
        
        # First, add to production
        print("=" * 60)
        print("📡 PRODUCTION DATABASE (PostgreSQL)")
        print("=" * 60)
        success_prod = add_numbers_to_production(phone_numbers)
        
        # Then add to local by clearing DATABASE_URL and reloading modules
        print("\n" + "=" * 60)
        print("💾 LOCAL DATABASE (SQLite)")
        print("=" * 60)
        
        # Save and clear DATABASE_URL
        original_db_url = os.environ.pop('DATABASE_URL', None)
        
        # Clear the loaded modules to force reload without DATABASE_URL
        import sys
        if 'src.services.database' in sys.modules:
            del sys.modules['src.services.database']
        if 'src.services.db_postgres_wrapper' in sys.modules:
            del sys.modules['src.services.db_postgres_wrapper']
        
        success_local = add_numbers_to_production(phone_numbers)
        
        # Restore DATABASE_URL
        if original_db_url:
            os.environ['DATABASE_URL'] = original_db_url
        
        print("\n" + "=" * 60)
        print("✅ COMPLETED - Numbers added to both databases")
        print("=" * 60)
        sys.exit(0)
    
    # Add numbers (single database)
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
