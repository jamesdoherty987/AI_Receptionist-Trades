"""
Appointment Auto-Complete Service
Automatically completes appointments that are more than 24 hours past their scheduled time
"""
from datetime import datetime, timedelta
from typing import List, Dict
from src.services.client_description_generator import update_client_description


def auto_complete_overdue_appointments() -> int:
    """
    Find and auto-complete appointments that are more than 24 hours past
    their scheduled time and haven't been manually completed.
    
    Returns:
        Number of appointments auto-completed
    """
    from src.services.database import get_database
    db = get_database()
    
    # Calculate cutoff time (24 hours ago)
    cutoff_time = datetime.now() - timedelta(hours=24)
    cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n{'='*60}")
    print(f"🔄 Checking for overdue appointments...")
    print(f"⏰ Cutoff time: {cutoff_str}")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Find appointments that:
    # 1. Are not already completed
    # 2. Are more than 24 hours past their scheduled time
    cursor.execute("""
        SELECT id, client_id, appointment_time, service_type 
        FROM bookings 
        WHERE status != 'completed' 
        AND appointment_time < ?
        ORDER BY appointment_time ASC
    """, (cutoff_str,))
    
    overdue_bookings = cursor.fetchall()
    conn.close()
    
    if not overdue_bookings:
        print(f"✅ No overdue appointments found")
        print(f"{'='*60}\n")
        return 0
    
    print(f"📋 Found {len(overdue_bookings)} overdue appointment(s)")
    
    completed_count = 0
    
    for booking in overdue_bookings:
        booking_id, client_id, appt_time, service_type = booking
        
        try:
            print(f"\n  📌 Booking {booking_id}: {appt_time} ({service_type or 'General'})")
            
            # Check if appointment has notes
            notes = db.get_appointment_notes(booking_id)
            
            if not notes or len(notes) == 0:
                print(f"  ⚠️  Skipping (no notes) - adding auto-note")
                # Add a system note indicating it was auto-completed
                db.add_appointment_note(
                    booking_id=booking_id,
                    note="Auto-completed by system after 24 hours. No notes were added during the appointment.",
                    created_by="system"
                )
            
            # Update booking status to completed
            db.update_booking(booking_id, status='completed')
            print(f"  ✅ Marked as completed")
            
            # Update client description
            try:
                success = update_client_description(client_id)
                if success:
                    print(f"  🤖 Updated AI description for client {client_id}")
                else:
                    print(f"  ⚠️  Description update failed for client {client_id}")
            except Exception as desc_error:
                print(f"  ⚠️  Description update error: {desc_error}")
            
            completed_count += 1
            
        except Exception as e:
            print(f"  ❌ Error auto-completing booking {booking_id}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"✅ Auto-completed {completed_count} appointment(s)")
    print(f"{'='*60}\n")
    
    return completed_count


def start_auto_complete_scheduler(interval_minutes: int = 60):
    """
    Start a background scheduler that checks for overdue appointments
    
    Args:
        interval_minutes: How often to check (default: 60 minutes)
    """
    import threading
    import time
    
    def scheduler_loop():
        print(f"🚀 Auto-complete scheduler started (checking every {interval_minutes} minutes)")
        
        while True:
            try:
                auto_complete_overdue_appointments()
            except Exception as e:
                print(f"❌ Error in auto-complete scheduler: {e}")
            
            # Wait for next check
            time.sleep(interval_minutes * 60)
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    return scheduler_thread


if __name__ == "__main__":
    # For testing: run once
    auto_complete_overdue_appointments()
