"""
Script to add test users and bookings to the database for testing purposes.
Run this script to populate the database with realistic test data.
"""

import sys
import os
from datetime import datetime, timedelta
import random

# Add parent directory to path to import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database

def add_test_users():
    """Add a variety of test users with different booking scenarios"""
    db = Database()
    
    # Test users with realistic data
    test_clients = [
        {"name": "John Smith", "phone": "555-0101", "email": "john.smith@email.com"},
        {"name": "Sarah Johnson", "phone": "555-0102", "email": "sarah.j@email.com"},
        {"name": "Michael Chen", "phone": "555-0103", "email": "m.chen@email.com"},
        {"name": "Emily Davis", "phone": "555-0104", "email": "emily.davis@email.com"},
        {"name": "David Wilson", "phone": "555-0105", "email": "d.wilson@email.com"},
        {"name": "Lisa Anderson", "phone": "555-0106", "email": "lisa.a@email.com"},
        {"name": "James Martinez", "phone": "555-0107", "email": "james.m@email.com"},
        {"name": "Jennifer Brown", "phone": "555-0108", "email": "jen.brown@email.com"},
        {"name": "Robert Taylor", "phone": "555-0109", "email": "rob.taylor@email.com"},
        {"name": "Mary Thomas", "phone": "555-0110", "email": "mary.t@email.com"},
        {"name": "William Garcia", "phone": "555-0111", "email": "will.garcia@email.com"},
        {"name": "Patricia Moore", "phone": "555-0112", "email": "patricia.m@email.com"},
        {"name": "Christopher Lee", "phone": "555-0113", "email": "chris.lee@email.com"},
        {"name": "Linda White", "phone": "555-0114", "email": "linda.white@email.com"},
        {"name": "Daniel Harris", "phone": "555-0115", "email": "dan.harris@email.com"},
        # Some clients with email only (no phone)
        {"name": "Jessica Turner", "email": "jessica.turner@email.com"},
        {"name": "Matthew Clark", "email": "matt.clark@email.com"},
        {"name": "Ashley Rodriguez", "email": "ashley.r@email.com"},
        # Some clients with phone only (no email)
        {"name": "Andrew Lewis", "phone": "555-0119"},
        {"name": "Michelle Walker", "phone": "555-0120"},
    ]
    
    # Appointment types and durations
    appointment_types = [
        ("Initial Consultation", 60),
        ("Follow-up Appointment", 30),
        ("Annual Checkup", 45),
        ("Procedure", 90),
        ("Quick Visit", 15),
        ("Extended Consultation", 120),
    ]
    
    # Booking statuses
    statuses = ["confirmed", "completed", "cancelled", "pending"]
    
    print("🚀 Adding test users to database...\n")
    
    client_ids = []
    
    # Add all clients
    for client in test_clients:
        try:
            client_id = db.find_or_create_client(
                name=client["name"],
                phone=client.get("phone"),
                email=client.get("email")
            )
            client_ids.append((client_id, client["name"]))
            print(f"✅ Added client: {client['name']} (ID: {client_id})")
        except Exception as e:
            print(f"❌ Error adding {client['name']}: {e}")
    
    print(f"\n📊 Successfully added {len(client_ids)} clients\n")
    print("📅 Adding test bookings...\n")
    
    # Add bookings for each client (some clients have multiple bookings)
    booking_count = 0
    base_date = datetime.now()
    
    for client_id, client_name in client_ids:
        # Random number of bookings per client (1-4)
        num_bookings = random.randint(1, 4)
        
        for i in range(num_bookings):
            # Generate booking in the past, present, or future
            days_offset = random.randint(-30, 60)  # 30 days ago to 60 days ahead
            hours_offset = random.randint(8, 17)   # Between 8 AM and 5 PM
            
            booking_datetime = (base_date + timedelta(days=days_offset)).replace(
                hour=hours_offset, 
                minute=random.choice([0, 15, 30, 45]),
                second=0,
                microsecond=0
            )
            
            # Choose appointment type
            apt_type, duration = random.choice(appointment_types)
            
            # Status based on date (past = completed/cancelled, future = confirmed/pending)
            if days_offset < -1:
                status = random.choice(["completed", "cancelled"])
            elif days_offset < 0:
                status = random.choice(["completed", "confirmed"])
            else:
                status = random.choice(["confirmed", "pending", "confirmed", "confirmed"])  # More likely confirmed
            
            try:
                # Generate a fake calendar event ID
                calendar_event_id = f"test_event_{client_id}_{i}_{random.randint(1000, 9999)}"
                
                # Get client info to include their contact details
                client_info = db.get_client(client_id)
                
                booking_id = db.add_booking(
                    client_id=client_id,
                    calendar_event_id=calendar_event_id,
                    appointment_time=booking_datetime,
                    service_type=apt_type,
                    phone_number=client_info.get('phone'),
                    email=client_info.get('email')
                )
                
                # Add some appointment notes
                if random.random() > 0.5:  # 50% chance of having notes
                    notes = [
                        f"Client prefers morning appointments",
                        f"Follow up on previous {apt_type.lower()}",
                        f"Requested {random.choice(['parking', 'wheelchair', 'early arrival'])} assistance",
                        f"Reminder: Bring previous medical records",
                        f"Special requirement: {random.choice(['first-time patient', 'referral from Dr. Smith', 'insurance verification needed'])}",
                    ]
                    db.add_appointment_note(
                        booking_id=booking_id,
                        note=random.choice(notes),
                        created_by="system"
                    )
                
                booking_count += 1
                status_emoji = "✅" if status == "confirmed" else "📝" if status == "pending" else "✔️" if status == "completed" else "❌"
                print(f"{status_emoji} {client_name}: {apt_type} on {booking_datetime.strftime('%Y-%m-%d %H:%M')}")
                
            except Exception as e:
                print(f"❌ Error adding booking for {client_name}: {e}")
    
    print(f"\n📊 Successfully added {booking_count} bookings")
    print(f"\n🎉 Test database populated successfully!")
    print(f"   - {len(client_ids)} clients")
    print(f"   - {booking_count} bookings")
    print(f"\n💡 You can now view these test users in the dashboard at http://localhost:5000")

if __name__ == "__main__":
    try:
        add_test_users()
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
