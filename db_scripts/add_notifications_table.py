"""
Create notifications table for owner and worker notifications.
Supports notifications for time-off requests, job assignments, etc.
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

    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'notifications'
        )
    """)
    if cursor.fetchone()[0]:
        print("Table notifications already exists")
        conn.close()
        return

    cursor.execute("""
        CREATE TABLE notifications (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            recipient_type VARCHAR(20) NOT NULL DEFAULT 'owner',
            recipient_id INTEGER,
            type VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("CREATE INDEX idx_notifications_company ON notifications(company_id)")
    cursor.execute("CREATE INDEX idx_notifications_recipient ON notifications(recipient_type, recipient_id)")
    cursor.execute("CREATE INDEX idx_notifications_created ON notifications(created_at DESC)")

    conn.commit()
    cursor.close()
    conn.close()

    print("Created notifications table successfully")


if __name__ == '__main__':
    migrate()
