"""
Migration: Add customer_photo_urls column to bookings table.
Stores JSON array of R2 URLs for media uploaded by customers via the portal.
Separate from photo_urls (employee/owner uploads) so they can be displayed distinctly.
"""
import os
import psycopg2

def run():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE bookings
            ADD COLUMN IF NOT EXISTS customer_photo_urls JSONB DEFAULT '[]'::jsonb
        """)
        conn.commit()
        print("[SUCCESS] Added customer_photo_urls column to bookings table")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    run()
