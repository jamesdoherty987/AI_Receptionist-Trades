"""Find and fix William Garcia's appointment"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

db = Database()
bookings = db.get_all_bookings()

print("\nWilliam Garcia's appointments:\n")
for b in bookings:
    if 'william' in b['client_name'].lower() and 'garcia' in b['client_name'].lower():
        print(f"ID: {b['id']}")
        print(f"Date: {b['appointment_time']}")
        print(f"Status: {b['status']}")
        print(f"Service: {b['service_type']}")
        print("-" * 40)
        
        # Fix if it's a future appointment marked as completed
        from datetime import datetime
        appt_time = datetime.strptime(b['appointment_time'], "%Y-%m-%d %H:%M:%S")
        if appt_time > datetime.now() and b['status'] == 'completed':
            print(f"FIXING: Setting booking {b['id']} to 'scheduled'")
            db.update_booking(b['id'], status='scheduled')
            print("✅ Fixed!\n")
