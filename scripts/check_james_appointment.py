"""Check James Doherty's appointment status"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

db = Database()
bookings = db.get_all_bookings()

print("\nJames Doherty's appointments:\n")
for b in bookings:
    if 'james' in b['client_name'].lower() and 'doherty' in b['client_name'].lower():
        print(f"ID: {b['id']}")
        print(f"Date: {b['appointment_time']}")
        print(f"Status: {b['status']}")
        print(f"Service: {b['service_type']}")
        print(f"Phone: {b['phone_number']}")
        print("-" * 40)
