"""Reset phone number pool for testing
Make sure DATABASE_URL is set in your .env file
Usage: python db_scripts/reset_phone_pool.py
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database import get_database

db = get_database()
conn = db.get_connection()

# Reset all phone numbers to available
conn.execute("""
    UPDATE twilio_phone_numbers 
    SET assigned_to_company_id = NULL, 
        status = 'available', 
        assigned_at = NULL
""")
conn.commit()
conn.close()

print("✅ All phone numbers reset to available status")
