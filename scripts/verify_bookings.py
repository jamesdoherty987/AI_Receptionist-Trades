"""
Verify bookings have contact info
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

db = Database()
bookings = db.get_all_bookings()

print("\n📋 Sample Bookings (first 5):\n")
for booking in bookings[:5]:
    print(f"👤 {booking['client_name']}")
    print(f"   📞 Phone: {booking.get('phone_number', 'N/A')}")
    print(f"   ✉️  Email: {booking.get('email', 'N/A')}")
    print(f"   📅 Time: {booking['appointment_time']}")
    print()

# Check for any bookings without contact info
no_contact = [b for b in bookings if not b.get('phone_number') and not b.get('email')]
if no_contact:
    print(f"⚠️  Found {len(no_contact)} bookings without contact info")
else:
    print(f"✅ All {len(bookings)} bookings have contact info!")
