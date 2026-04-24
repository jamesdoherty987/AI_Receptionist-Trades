"""
Migration: Add photo_urls column to bookings table.
Stores JSON array of R2 URLs for job photos uploaded by employees.
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return False

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'bookings' AND column_name = 'photo_urls'
        """)
        if cursor.fetchone():
            print("photo_urls column already exists, skipping.")
            return True

        cursor.execute("""
            ALTER TABLE bookings 
            ADD COLUMN photo_urls JSONB DEFAULT '[]'::jsonb
        """)
        conn.commit()
        print("SUCCESS: Added photo_urls column to bookings table")
        return True
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    migrate()
