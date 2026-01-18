"""
Mark all appointments as paid
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import Database
import random

def mark_all_paid():
    """Mark all bookings as paid with payment methods"""
    
    db = Database()
    bookings = db.get_all_bookings()
    
    print(f"\nFound {len(bookings)} bookings to update...")
    
    payment_methods = ['cash', 'card', 'Apple Pay', 'card', 'cash']  # More card/cash
    
    updated = 0
    
    for booking in bookings:
        booking_id = booking['id']
        payment_method = random.choice(payment_methods)
        
        success = db.update_booking(
            booking_id=booking_id,
            payment_status='paid',
            payment_method=payment_method
        )
        
        if success:
            updated += 1
            print(f"✓ Updated booking {booking_id}: paid ({payment_method})")
        else:
            print(f"✗ Failed to update booking {booking_id}")
    
    print(f"\n{'='*50}")
    print(f"Updated {updated}/{len(bookings)} bookings to paid")
    print(f"{'='*50}")

if __name__ == "__main__":
    print("="*50)
    print("Mark All Appointments as Paid")
    print("="*50)
    print("\nThis will mark all appointments as paid.")
    print("Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
        mark_all_paid()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
