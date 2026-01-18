"""
Populate existing bookings with financial data (charge, payment status, payment method)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import Database
from datetime import datetime
import random

def populate_finances():
    """Add financial data to all existing bookings"""
    
    db = Database()
    bookings = db.get_all_bookings()
    
    print(f"\nFound {len(bookings)} bookings to update...")
    
    payment_methods = ['cash', 'card', 'Apple Pay', None]
    payment_statuses = ['paid', 'unpaid']
    
    updated = 0
    
    for booking in bookings:
        booking_id = booking['id']
        appointment_time = datetime.fromisoformat(booking['appointment_time'])
        now = datetime.now()
        
        # Past appointments are more likely to be paid
        if appointment_time < now:
            payment_status = random.choices(['paid', 'unpaid'], weights=[0.85, 0.15])[0]
            payment_method = random.choice(payment_methods) if payment_status == 'paid' else None
        else:
            # Future appointments are unpaid
            payment_status = 'unpaid'
            payment_method = None
        
        # Random charges between €40-€60, mostly €50
        charge = random.choices([40.0, 45.0, 50.0, 55.0, 60.0], weights=[0.1, 0.15, 0.5, 0.15, 0.1])[0]
        
        success = db.update_booking(
            booking_id=booking_id,
            charge=charge,
            payment_status=payment_status,
            payment_method=payment_method
        )
        
        if success:
            updated += 1
            status_text = f"{payment_status} ({payment_method})" if payment_method else payment_status
            print(f"✓ Updated booking {booking_id}: €{charge:.2f} - {status_text}")
        else:
            print(f"✗ Failed to update booking {booking_id}")
    
    print(f"\n{'='*50}")
    print(f"Updated {updated}/{len(bookings)} bookings with financial data")
    print(f"{'='*50}")

if __name__ == "__main__":
    print("="*50)
    print("Populate Financial Data")
    print("="*50)
    print("\nThis script will add charges and payment info to all bookings.")
    print("Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
        populate_finances()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
