"""
Migration: Ensure services table has 'active' column (it already does as INTEGER DEFAULT 1).
This script just verifies it exists and adds it if somehow missing.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.database import get_database

def migrate():
    db = get_database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # The 'active' column already exists in the services table schema (INTEGER DEFAULT 1).
        # This migration is a safety net.
        cursor.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='services' AND column_name='active') THEN
                    ALTER TABLE services ADD COLUMN active INTEGER DEFAULT 1;
                END IF;
            END $$;
        """)
        conn.commit()
        print("[SUCCESS] 'active' column verified on services table")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
    finally:
        db.return_connection(conn)

if __name__ == "__main__":
    migrate()
