"""
Create messages table for owner-worker messaging.
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
            WHERE table_name = 'messages'
        )
    """)
    if cursor.fetchone()[0]:
        print("Table messages already exists")
        conn.close()
        return

    cursor.execute("""
        CREATE TABLE messages (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            sender_type VARCHAR(10) NOT NULL CHECK (sender_type IN ('owner', 'worker')),
            content TEXT NOT NULL,
            read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("CREATE INDEX idx_messages_company_worker ON messages(company_id, worker_id)")
    cursor.execute("CREATE INDEX idx_messages_created ON messages(created_at DESC)")
    cursor.execute("CREATE INDEX idx_messages_unread ON messages(company_id, worker_id, read) WHERE read = FALSE")

    conn.commit()
    cursor.close()
    conn.close()
    print("Created messages table successfully")


if __name__ == '__main__':
    migrate()
