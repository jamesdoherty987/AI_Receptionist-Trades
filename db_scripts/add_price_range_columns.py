"""
Add price_max column to services table and charge_max column to bookings table.
Supports price ranges (e.g., €100 - €200) for services and jobs.
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_connection():
    return psycopg2.connect(os.getenv('DATABASE_URL'))

def migrate():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Add price_max to services
        cursor.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='services' AND column_name='price_max') THEN
                    ALTER TABLE services ADD COLUMN price_max REAL DEFAULT NULL;
                END IF;
            END $$;
        """)
        print("✅ services.price_max column ready")
        
        # Add charge_max to bookings
        cursor.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='bookings' AND column_name='charge_max') THEN
                    ALTER TABLE bookings ADD COLUMN charge_max REAL DEFAULT NULL;
                END IF;
            END $$;
        """)
        print("✅ bookings.charge_max column ready")
        
        conn.commit()
        print("\n🎉 Migration complete — price ranges are now supported!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    migrate()
