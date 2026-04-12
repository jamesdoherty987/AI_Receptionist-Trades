"""
Add source_booking_id to quotes table for bidirectional quote-job linking.
- source_booking_id: the job that this quote was created FROM
- converted_booking_id: the job that this quote was converted TO (already exists)
Also adds quote_id to bookings for reverse lookup.
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Add source_booking_id to quotes
    try:
        cursor.execute("""
            ALTER TABLE quotes ADD COLUMN IF NOT EXISTS source_booking_id INTEGER REFERENCES bookings(id) ON DELETE SET NULL
        """)
        conn.commit()
        print("Added source_booking_id to quotes table")
    except Exception as e:
        conn.rollback()
        print(f"Error adding source_booking_id: {e}")

    # Add quote_id to bookings for reverse lookup
    try:
        cursor.execute("""
            ALTER TABLE bookings ADD COLUMN IF NOT EXISTS quote_id INTEGER REFERENCES quotes(id) ON DELETE SET NULL
        """)
        conn.commit()
        print("Added quote_id to bookings table")
    except Exception as e:
        conn.rollback()
        print(f"Error adding quote_id: {e}")

    cursor.close()
    conn.close()
    print("Done!")


if __name__ == "__main__":
    run()
