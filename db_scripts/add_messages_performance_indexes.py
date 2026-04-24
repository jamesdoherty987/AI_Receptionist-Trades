"""
Add performance indexes to messages table for faster conversation loading.
- Composite index on (company_id, employee_id, created_at DESC) for conversation queries
- Partial index on unread messages for faster unread count aggregation
"""
import os
import sys
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def migrate():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Composite index for conversation queries (ORDER BY created_at DESC with company+employee filter)
    cursor.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_conv_lookup
        ON messages(company_id, employee_id, created_at DESC)
    """)
    print("Created idx_messages_conv_lookup")

    # Partial index for unread count queries (only unread rows, much smaller)
    cursor.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_unread_sender
        ON messages(company_id, sender_type, employee_id)
        WHERE read = FALSE
    """)
    print("Created idx_messages_unread_sender")

    conn.commit()
    cursor.close()
    conn.close()
    print("Done — messages performance indexes added")


if __name__ == '__main__':
    migrate()
