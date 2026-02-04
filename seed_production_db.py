"""
Production Database Seeder
Run this ONCE to populate your PostgreSQL database with sample data
Usage: python seed_production_db.py
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Set DATABASE_URL environment variable BEFORE importing database
# Replace with your actual Render PostgreSQL URL
DATABASE_URL = os.getenv('DATABASE_URL') or input("Enter your PostgreSQL DATABASE_URL: ")
os.environ['DATABASE_URL'] = DATABASE_URL

from src.services.database import get_database

def seed_database():
    """Seed the production database with sample data"""
    print("\n" + "="*60)
    print("🌱 SEEDING PRODUCTION DATABASE")
    print("="*60)
    
    db = get_database()
    
    # Check if database already has data
    existing_clients = db.get_all_clients()
    if len(existing_clients) > 0:
        response = input(f"\n⚠️  Database already has {len(existing_clients)} clients. Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Seeding cancelled")
            return
    
    print("\n📝 Creating sample clients...")
    
    # Sample clients
    clients = [
        {"name": "John Smith", "phone": "+353871234567", "email": "john@example.com"},
        {"name": "Mary O'Connor", "phone": "+353872345678", "email": "mary@example.com"},
        {"name": "Patrick Murphy", "phone": "+353873456789", "email": "patrick@example.com"},
        {"name": "Sarah Kelly", "phone": "+353874567890", "email": "sarah@example.com"},
        {"name": "Michael Ryan", "phone": "+353875678901", "email": "michael@example.com"},
    ]
    
    client_ids = []
    for client in clients:
        try:
            client_id = db.add_client(**client)
            client_ids.append(client_id)
            print(f"   ✅ Created: {client['name']}")
        except Exception as e:
            print(f"   ⚠️  Skipped {client['name']}: {e}")
    
    print(f"\n📅 Creating sample bookings...")
    
    # Sample bookings (upcoming and past)
    now = datetime.now()
    bookings = [
        {
            "appointment_time": now + timedelta(days=1, hours=10),
            "service_type": "Leak Repairs",
            "urgency": "urgent",
            "address": "123 Main Street, Dublin",
            "eircode": "D01 X123",
            "charge": 85.0
        },
        {
            "appointment_time": now + timedelta(days=2, hours=14),
            "service_type": "Plumbing Installation",
            "urgency": "scheduled",
            "address": "456 Oak Road, Cork",
            "eircode": "T12 Y456",
            "charge": 120.0
        },
        {
            "appointment_time": now + timedelta(days=5, hours=9),
            "service_type": "Drain Cleaning",
            "urgency": "scheduled",
            "address": "789 Park Lane, Galway",
            "eircode": "H91 Z789",
            "charge": 65.0
        },
        {
            "appointment_time": now - timedelta(days=7),
            "service_type": "Boiler Servicing",
            "urgency": "scheduled",
            "address": "321 High Street, Limerick",
            "eircode": "V94 A321",
            "charge": 95.0,
            "status": "completed"
        },
    ]
    
    for i, booking in enumerate(bookings):
        if client_ids:
            client_id = client_ids[i % len(client_ids)]
            try:
                booking_id = db.add_booking(
                    client_id=client_id,
                    calendar_event_id=f"sample_{i}_{int(datetime.now().timestamp())}",
                    appointment_time=booking["appointment_time"],
                    service_type=booking["service_type"],
                    urgency=booking.get("urgency", "scheduled"),
                    address=booking.get("address"),
                    eircode=booking.get("eircode"),
                    charge=booking.get("charge", 50.0)
                )
                
                # Update status if needed
                if booking.get("status"):
                    db.update_booking(booking_id, status=booking["status"])
                
                print(f"   ✅ Created: {booking['service_type']} on {booking['appointment_time'].strftime('%Y-%m-%d')}")
            except Exception as e:
                print(f"   ⚠️  Failed to create booking: {e}")
    
    print(f"\n👷 Creating sample workers...")
    
    # Sample workers
    workers = [
        {"name": "Tom Anderson", "phone": "+353871111111", "email": "tom@company.com", "trade_specialty": "Plumbing"},
        {"name": "Lisa Brown", "phone": "+353872222222", "email": "lisa@company.com", "trade_specialty": "Electrical"},
    ]
    
    for worker in workers:
        try:
            db.add_worker(**worker)
            print(f"   ✅ Created: {worker['name']} ({worker['trade_specialty']})")
        except Exception as e:
            print(f"   ⚠️  Failed to create worker: {e}")
    
    # Final stats
    print("\n" + "="*60)
    print("📊 FINAL DATABASE STATS")
    print("="*60)
    final_clients = db.get_all_clients()
    final_bookings = db.get_all_bookings()
    final_workers = db.get_all_workers()
    
    print(f"   Clients: {len(final_clients)}")
    print(f"   Bookings: {len(final_bookings)}")
    print(f"   Workers: {len(final_workers)}")
    print("\n✅ Database seeding complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        seed_database()
    except Exception as e:
        print(f"\n❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
