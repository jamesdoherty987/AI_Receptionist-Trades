import os
import psycopg2

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise Exception('DATABASE_URL environment variable is not set.')

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Check columns in business_settings table
cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'business_settings'")
bs_columns = cursor.fetchall()
print('business_settings table columns:')
for col in bs_columns:
    print(f"  {col[0]} ({col[1]})")

# Check columns in companies table
cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'companies'")
co_columns = cursor.fetchall()
print('\ncompanies table columns:')
for col in co_columns:
    print(f"  {col[0]} ({col[1]})")

cursor.close()
conn.close()
