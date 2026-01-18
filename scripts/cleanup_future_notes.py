"""
Remove notes from future/upcoming appointments
Notes should only exist for past appointments
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

def cleanup_future_notes():
    """Remove notes from appointments that haven't happened yet"""
    db = Database()
    
    print("\n" + "="*80)
    print("🧹 CLEANING UP NOTES FROM FUTURE APPOINTMENTS")
    print("="*80 + "\n")
    
    # Get all bookings
    all_bookings = db.get_all_bookings()
    
    # Filter to future appointments
    now = datetime.now()
    future_bookings = []
    
    for booking in all_bookings:
        try:
            appt_time = datetime.strptime(booking['appointment_time'], "%Y-%m-%d %H:%M:%S")
            if appt_time >= now:
                future_bookings.append(booking)
        except:
            continue
    
    print(f"Found {len(future_bookings)} upcoming appointments\n")
    
    if not future_bookings:
        print("✅ No upcoming appointments to clean")
        return
    
    deleted_count = 0
    
    for booking in future_bookings:
        booking_id = booking['id']
        client_name = booking['client_name']
        appt_time = booking['appointment_time']
        
        # Get existing notes
        existing_notes = db.get_appointment_notes(booking_id)
        
        if len(existing_notes) > 0:
            print(f"📅 {appt_time} - {client_name}")
            print(f"   Removing {len(existing_notes)} note(s)...")
            
            # Delete all notes for this booking
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM appointment_notes WHERE booking_id = ?", (booking_id,))
            conn.commit()
            conn.close()
            
            deleted_count += len(existing_notes)
            print(f"   ✅ Deleted")
            print()
    
    print("="*80)
    print(f"✅ Deleted {deleted_count} notes from {len([b for b in future_bookings if db.get_appointment_notes(b['id'])])} upcoming appointments")
    print("="*80 + "\n")

if __name__ == "__main__":
    cleanup_future_notes()
