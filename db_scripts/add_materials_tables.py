"""
Create materials catalog and job_materials tables.

materials - the catalog of materials a company uses
job_materials - materials used on specific jobs (with denormalized name/price)
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

    # Materials catalog table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                unit_price NUMERIC(10, 2) DEFAULT 0,
                unit VARCHAR(50) DEFAULT 'each',
                category VARCHAR(100),
                supplier VARCHAR(255),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created table: materials")
    except Exception as e:
        conn.rollback()
        print(f"Error creating materials table: {e}")

    # Job materials table (per-job usage)
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_materials (
                id SERIAL PRIMARY KEY,
                booking_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
                name VARCHAR(255) NOT NULL,
                unit_price NUMERIC(10, 2) DEFAULT 0,
                unit VARCHAR(50) DEFAULT 'each',
                quantity NUMERIC(10, 2) DEFAULT 1,
                total_cost NUMERIC(10, 2) DEFAULT 0,
                added_by VARCHAR(100),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Created table: job_materials")
    except Exception as e:
        conn.rollback()
        print(f"Error creating job_materials table: {e}")

    # Indexes
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_materials_company ON materials(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_materials_booking ON job_materials(booking_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_materials_company ON job_materials(company_id)",
    ]:
        try:
            cursor.execute(idx_sql)
            conn.commit()
            print(f"Created index")
        except Exception as e:
            conn.rollback()
            print(f"Index error: {e}")

    cursor.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    run()
