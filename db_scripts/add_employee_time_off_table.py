"""
Create employee_time_off table for the employee portal HR features.
Employees can request time off, owners can approve/deny.
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
            WHERE table_name = 'employee_time_off'
        )
    """)
    if cursor.fetchone()[0]:
        print("Table employee_time_off already exists")
        conn.close()
        return

    cursor.execute("""
        CREATE TABLE employee_time_off (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            reason VARCHAR(500),
            type VARCHAR(50) DEFAULT 'vacation',
            status VARCHAR(20) DEFAULT 'pending',
            reviewed_at TIMESTAMP,
            reviewer_note VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("CREATE INDEX idx_employee_time_off_employee ON employee_time_off(employee_id)")
    cursor.execute("CREATE INDEX idx_employee_time_off_company ON employee_time_off(company_id)")
    cursor.execute("CREATE INDEX idx_employee_time_off_dates ON employee_time_off(start_date, end_date)")

    conn.commit()
    cursor.close()
    conn.close()

    print("Created employee_time_off table successfully")


if __name__ == '__main__':
    migrate()
