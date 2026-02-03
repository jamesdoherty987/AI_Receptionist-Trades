"""
Database Migration Script
Migrate existing SQLite data to PostgreSQL (Supabase)
Run this BEFORE first deployment if you have existing data
"""
import os
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def migrate_sqlite_to_postgres():
    """
    Migrate data from SQLite to PostgreSQL
    """
    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        return False
    
    # Check for required environment variables
    db_url = os.getenv('DATABASE_URL') or os.getenv('SUPABASE_DB_URL')
    if not db_url:
        print("❌ DATABASE_URL not set. Set it in your .env file")
        return False
    
    sqlite_path = "data/receptionist.db"
    if not os.path.exists(sqlite_path):
        print(f"⚠️  No SQLite database found at {sqlite_path}")
        print("   Nothing to migrate!")
        return True
    
    print("🔄 Starting migration from SQLite to PostgreSQL...")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    
    try:
        pg_conn = psycopg2.connect(db_url)
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        sqlite_conn.close()
        return False
    
    # Tables to migrate (in order due to foreign keys)
    tables = [
        'clients',
        'bookings',
        'notes',
        'appointment_notes',
        'call_logs',
        'workers',
        'worker_assignments',
        'companies'
    ]
    
    try:
        for table in tables:
            print(f"\n📊 Migrating table: {table}")
            
            # Get data from SQLite
            sqlite_cursor = sqlite_conn.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                print(f"   ⚠️  No data in {table}")
                continue
            
            # Get column names
            columns = [description[0] for description in sqlite_cursor.description]
            # Remove 'id' column as it's auto-generated in PostgreSQL
            columns_without_id = [col for col in columns if col != 'id']
            
            # Prepare INSERT query
            placeholders = ','.join(['%s'] * len(columns_without_id))
            column_names = ','.join(columns_without_id)
            insert_query = f"""
                INSERT INTO {table} ({column_names})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            
            # Prepare data (exclude id column)
            data_to_insert = []
            for row in rows:
                row_dict = dict(row)
                row_data = tuple(row_dict[col] for col in columns_without_id)
                data_to_insert.append(row_data)
            
            # Insert data
            execute_values(pg_cursor, insert_query, data_to_insert)
            pg_conn.commit()
            
            print(f"   ✅ Migrated {len(rows)} rows")
        
        print("\n✅ Migration completed successfully!")
        print("   Your data is now in PostgreSQL")
        print("   You can now deploy to production!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        pg_conn.rollback()
        return False
    
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("SQLite → PostgreSQL Migration Script")
    print("=" * 60)
    print("\n⚠️  IMPORTANT:")
    print("   1. Make sure DATABASE_URL is set in your .env")
    print("   2. This will copy data to PostgreSQL")
    print("   3. Your SQLite database will NOT be deleted")
    print("   4. Duplicate entries will be skipped")
    print("\n")
    
    response = input("Continue with migration? (yes/no): ").lower()
    if response == 'yes':
        success = migrate_sqlite_to_postgres()
        if success:
            print("\n🎉 Done! You're ready to deploy!")
        else:
            print("\n❌ Migration failed. Check errors above.")
            sys.exit(1)
    else:
        print("Migration cancelled.")
