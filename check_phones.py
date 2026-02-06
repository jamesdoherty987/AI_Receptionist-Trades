"""Quick script to check and add test phone numbers"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database import get_database

db = get_database()

# Check for available numbers
try:
    available = db.get_available_phone_numbers()
    print(f"✅ Available phone numbers: {len(available)}")
    for num in available[:5]:
        print(f"   - {num['phone_number']}")
    
    if len(available) == 0:
        print("\n⚠️ No phone numbers in database!")
        print("Adding test numbers...")
        
        # Add some test numbers
        test_numbers = [
            '+353861234567',
            '+353862345678',
            '+353863456789',
            '+353864567890',
            '+353865678901'
        ]
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        for num in test_numbers:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO twilio_phone_numbers (phone_number, status)
                    VALUES (?, 'available')
                """, (num,))
            except:
                pass
        
        conn.commit()
        conn.close()
        
        print(f"✅ Added {len(test_numbers)} test phone numbers")
        
except Exception as e:
    print(f"❌ Error: {e}")
