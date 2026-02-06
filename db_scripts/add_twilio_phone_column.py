"""
Add twilio_phone_number column to companies table if it doesn't exist
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper

def add_phone_column():
    """Add twilio_phone_number column to companies table"""
    db = PostgreSQLDatabaseWrapper(os.getenv('DATABASE_URL'))
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'companies' 
            AND column_name = 'twilio_phone_number'
        """)
        
        if cursor.fetchone():
            print("✅ Column 'twilio_phone_number' already exists")
        else:
            print("📝 Adding 'twilio_phone_number' column to companies table...")
            cursor.execute("""
                ALTER TABLE companies 
                ADD COLUMN twilio_phone_number TEXT UNIQUE
            """)
            conn.commit()
            print("✅ Column 'twilio_phone_number' added successfully")
        
        # Show current phone columns
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'companies' 
            AND column_name LIKE '%phone%'
            ORDER BY ordinal_position
        """)
        
        print("\n📋 Phone-related columns in companies table:")
        for row in cursor.fetchall():
            print(f"  - {row[0]} ({row[1]}, nullable: {row[2]})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        db.return_connection(conn)

if __name__ == "__main__":
    add_phone_column()
