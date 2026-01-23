"""
Clear database and populate with trades company demo data
"""
import sys
import os
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import Database
from src.services.google_calendar import GoogleCalendarService

def clear_database(db: Database):
    """Clear all data from database"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    print("🗑️  Clearing database...")
    
    # Delete in correct order due to foreign keys
    cursor.execute("DELETE FROM appointment_notes")
    cursor.execute("DELETE FROM notes")
    cursor.execute("DELETE FROM call_logs")
    cursor.execute("DELETE FROM bookings")
    cursor.execute("DELETE FROM clients")
    cursor.execute("DELETE FROM workers")
    
    # Reset auto-increment counters
    cursor.execute("DELETE FROM sqlite_sequence")
    
    conn.commit()
    conn.close()
    
    print("✅ Database cleared")

def add_workers(db: Database):
    """Add tradespersons to the database"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    print("👷 Adding workers...")
    
    workers = [
        ("James Doherty", "087-1234567", "james@swifttradeservices.ie", "Plumbing & Heating", "active"),
        ("Michael O'Brien", "086-2345678", "michael@swifttradeservices.ie", "Electrical", "active"),
        ("Sarah Murphy", "085-3456789", "sarah@swifttradeservices.ie", "General Maintenance", "active"),
        ("Tom Walsh", "089-4567890", "tom@swifttradeservices.ie", "Carpentry", "active"),
    ]
    
    for name, phone, email, specialty, status in workers:
        cursor.execute("""
            INSERT INTO workers (name, phone, email, trade_specialty, status)
            VALUES (?, ?, ?, ?, ?)
        """, (name, phone, email, specialty, status))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Added {len(workers)} workers")

def add_past_customers(db: Database):
    """Add realistic past customers with job history"""
    print("👥 Adding past customers...")
    
    customers = [
        {
            "name": "John Murphy",
            "phone": "087-1112222",
            "email": "john.murphy@gmail.com",
            "description": "Regular customer - owns rental properties in Limerick city. Usually needs plumbing work."
        },
        {
            "name": "Mary Fitzgerald",
            "phone": "086-3334444",
            "email": "mary.fitz@hotmail.com",
            "description": "Homeowner in Castletroy. Had boiler serviced last winter, very happy with service."
        },
        {
            "name": "Tom O'Brien",
            "phone": "085-5556666",
            "email": "t.obrien@yahoo.ie",
            "description": "Small business owner - cafe in city centre. Regular maintenance contracts."
        },
        {
            "name": "Sarah Collins",
            "phone": "089-7778888",
            "email": "sarah.collins@email.ie",
            "description": "First-time homeowner. Needed electrical work for extension. Recommended by John Murphy."
        },
        {
            "name": "David Lee",
            "phone": "087-9990000",
            "email": "david.lee@gmail.com",
            "description": "Property manager for apartment complex. Regular customer for emergency callouts."
        },
        {
            "name": "Emma Wilson",
            "phone": "086-1231234",
            "email": "emma.w@email.com",
            "description": "Had kitchen renovation - plumbing and electrical. Very satisfied, left 5-star review."
        },
        {
            "name": "Patrick Kelly",
            "phone": "085-4564567",
            "email": "p.kelly@gmail.com",
            "description": "Elderly customer. Needs occasional help with heating system. Always pays cash."
        },
        {
            "name": "Linda McCarthy",
            "phone": "089-7897890",
            "email": "linda.mccarthy@hotmail.com",
            "description": "Restaurant owner. Emergency burst pipe handled quickly. Now uses us for all plumbing."
        },
        {
            "name": "Sean Brennan",
            "phone": "087-3213210",
            "email": "sean.b@email.ie",
            "description": "Landlord with multiple properties. Prefers quotes before work. Good payer."
        },
        {
            "name": "Catherine Ryan",
            "phone": "086-6546543",
            "email": "catherine.ryan@gmail.com",
            "description": "Had electrical fault fixed. Lives in Raheen. Recommended us to neighbors."
        },
    ]
    
    client_ids = []
    for customer in customers:
        client_id = db.add_client(
            name=customer["name"],
            phone=customer["phone"],
            email=customer["email"],
            description=customer["description"]
        )
        client_ids.append(client_id)
        print(f"  ✅ Added: {customer['name']}")
    
    print(f"✅ Added {len(customers)} customers")
    return client_ids

def add_past_jobs(db: Database, client_ids: list):
    """Add past completed jobs for customers"""
    print("📋 Adding past jobs...")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Define realistic past jobs
    jobs = [
        # John Murphy - rental property owner
        {
            "client_id": client_ids[0],
            "service_type": "Plumbing - Leaking tap repair",
            "address": "45 O'Connell Street, Limerick",
            "eircode": "V94 E8N6",
            "property_type": "Commercial",
            "urgency": "same-day",
            "charge": 95.00,
            "payment_status": "paid",
            "payment_method": "card",
            "status": "completed",
            "days_ago": 45
        },
        {
            "client_id": client_ids[0],
            "service_type": "Plumbing - Toilet cistern replacement",
            "address": "12 Henry Street, Limerick",
            "eircode": "V94 T2C9",
            "property_type": "Residential",
            "urgency": "scheduled",
            "charge": 180.00,
            "payment_status": "paid",
            "payment_method": "bank transfer",
            "status": "completed",
            "days_ago": 120
        },
        # Mary Fitzgerald - homeowner
        {
            "client_id": client_ids[1],
            "service_type": "Heating - Boiler annual service",
            "address": "78 Castletroy Park, Castletroy",
            "eircode": "V94 N6P3",
            "property_type": "Residential",
            "urgency": "scheduled",
            "charge": 120.00,
            "payment_status": "paid",
            "payment_method": "card",
            "status": "completed",
            "days_ago": 90
        },
        # Tom O'Brien - cafe owner
        {
            "client_id": client_ids[2],
            "service_type": "Electrical - Kitchen socket installation",
            "address": "23 William Street, Limerick",
            "eircode": "V94 X2E1",
            "property_type": "Commercial",
            "urgency": "scheduled",
            "charge": 250.00,
            "payment_status": "paid",
            "payment_method": "bank transfer",
            "status": "completed",
            "days_ago": 60
        },
        {
            "client_id": client_ids[2],
            "service_type": "Electrical - Fault finding & repair",
            "address": "23 William Street, Limerick",
            "eircode": "V94 X2E1",
            "property_type": "Commercial",
            "urgency": "emergency",
            "charge": 280.00,
            "payment_status": "paid",
            "payment_method": "cash",
            "status": "completed",
            "days_ago": 180
        },
        # Sarah Collins - extension work
        {
            "client_id": client_ids[3],
            "service_type": "Electrical - Extension wiring",
            "address": "56 Dooradoyle Road, Limerick",
            "eircode": "V94 H2K9",
            "property_type": "Residential",
            "urgency": "scheduled",
            "charge": 950.00,
            "payment_status": "paid",
            "payment_method": "bank transfer",
            "status": "completed",
            "days_ago": 150
        },
        # David Lee - property manager
        {
            "client_id": client_ids[4],
            "service_type": "Plumbing - Emergency burst pipe",
            "address": "Riverpoint Apartments, Limerick",
            "eircode": "V94 C7T2",
            "property_type": "Commercial",
            "urgency": "emergency",
            "charge": 320.00,
            "payment_status": "paid",
            "payment_method": "card",
            "status": "completed",
            "days_ago": 30
        },
        {
            "client_id": client_ids[4],
            "service_type": "General Maintenance - Blocked drain",
            "address": "Riverpoint Apartments, Limerick",
            "eircode": "V94 C7T2",
            "property_type": "Commercial",
            "urgency": "same-day",
            "charge": 140.00,
            "payment_status": "paid",
            "payment_method": "card",
            "status": "completed",
            "days_ago": 75
        },
        # Emma Wilson - kitchen renovation
        {
            "client_id": client_ids[5],
            "service_type": "Plumbing - Kitchen sink installation",
            "address": "34 Elm Park, Corbally",
            "eircode": "V94 P8F5",
            "property_type": "Residential",
            "urgency": "scheduled",
            "charge": 280.00,
            "payment_status": "paid",
            "payment_method": "bank transfer",
            "status": "completed",
            "days_ago": 100
        },
        {
            "client_id": client_ids[5],
            "service_type": "Electrical - Kitchen lighting installation",
            "address": "34 Elm Park, Corbally",
            "eircode": "V94 P8F5",
            "property_type": "Residential",
            "urgency": "scheduled",
            "charge": 320.00,
            "payment_status": "paid",
            "payment_method": "bank transfer",
            "status": "completed",
            "days_ago": 95
        },
        # Patrick Kelly - elderly customer
        {
            "client_id": client_ids[6],
            "service_type": "Heating - Radiator repair",
            "address": "89 Clare Street, Limerick",
            "eircode": "V94 R3W1",
            "property_type": "Residential",
            "urgency": "same-day",
            "charge": 110.00,
            "payment_status": "paid",
            "payment_method": "cash",
            "status": "completed",
            "days_ago": 200
        },
        # Linda McCarthy - restaurant
        {
            "client_id": client_ids[7],
            "service_type": "Plumbing - Emergency burst pipe",
            "address": "The Green Cafe, 67 O'Connell Avenue",
            "eircode": "V94 A9B2",
            "property_type": "Commercial",
            "urgency": "emergency",
            "charge": 420.00,
            "payment_status": "paid",
            "payment_method": "card",
            "status": "completed",
            "days_ago": 250
        },
        # Sean Brennan - landlord
        {
            "client_id": client_ids[8],
            "service_type": "Quote - Bathroom renovation",
            "address": "15 Park Avenue, Limerick",
            "eircode": "V94 K5L8",
            "property_type": "Residential",
            "urgency": "quote",
            "charge": 0.00,
            "payment_status": "n/a",
            "payment_method": None,
            "status": "completed",
            "days_ago": 35
        },
        # Catherine Ryan - electrical fault
        {
            "client_id": client_ids[9],
            "service_type": "Electrical - Fault finding & repair",
            "address": "42 Raheen Park, Raheen",
            "eircode": "V94 W7X3",
            "property_type": "Residential",
            "urgency": "same-day",
            "charge": 160.00,
            "payment_status": "paid",
            "payment_method": "card",
            "status": "completed",
            "days_ago": 80
        },
    ]
    
    for job in jobs:
        # Calculate appointment time in the past
        appointment_time = datetime.now() - timedelta(days=job["days_ago"])
        
        cursor.execute("""
            INSERT INTO bookings (
                client_id, appointment_time, service_type, status, urgency,
                address, eircode, property_type, charge, payment_status, payment_method,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job["client_id"],
            appointment_time,
            job["service_type"],
            job["status"],
            job["urgency"],
            job["address"],
            job["eircode"],
            job["property_type"],
            job["charge"],
            job["payment_status"],
            job["payment_method"],
            appointment_time - timedelta(days=2)  # Created 2 days before appointment
        ))
        
        booking_id = cursor.lastrowid
        
        # Add some notes for selected jobs
        if random.random() < 0.3:  # 30% of jobs get notes
            note_templates = [
                "Customer very happy with service",
                "Work completed on time",
                "Recommended to friends",
                "May need follow-up in 6 months",
                "Additional work identified - sent quote",
            ]
            cursor.execute("""
                INSERT INTO appointment_notes (booking_id, note, created_by)
                VALUES (?, ?, ?)
            """, (booking_id, random.choice(note_templates), "system"))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Added {len(jobs)} past jobs")

def add_upcoming_jobs(db: Database, client_ids: list):
    """Add some upcoming jobs for demonstration"""
    print("📅 Adding upcoming jobs...")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    upcoming_jobs = [
        {
            "client_id": client_ids[0],  # John Murphy
            "service_type": "Plumbing - Radiator installation",
            "address": "45 O'Connell Street, Limerick",
            "eircode": "V94 E8N6",
            "property_type": "Commercial",
            "urgency": "scheduled",
            "charge": 250.00,
            "payment_status": "unpaid",
            "days_ahead": 3
        },
        {
            "client_id": client_ids[1],  # Mary Fitzgerald
            "service_type": "Heating - Boiler check",
            "address": "78 Castletroy Park, Castletroy",
            "eircode": "V94 N6P3",
            "property_type": "Residential",
            "urgency": "scheduled",
            "charge": 80.00,
            "payment_status": "unpaid",
            "days_ahead": 7
        },
        {
            "client_id": client_ids[4],  # David Lee
            "service_type": "General Maintenance - Tap repair",
            "address": "Riverpoint Apartments, Limerick",
            "eircode": "V94 C7T2",
            "property_type": "Commercial",
            "urgency": "scheduled",
            "charge": 95.00,
            "payment_status": "unpaid",
            "days_ahead": 5
        },
    ]
    
    for job in upcoming_jobs:
        # Calculate future appointment time
        appointment_time = datetime.now() + timedelta(days=job["days_ahead"])
        # Set time to business hours (9 AM - 5 PM)
        appointment_time = appointment_time.replace(hour=random.choice([9, 10, 11, 14, 15, 16]), minute=0, second=0)
        
        cursor.execute("""
            INSERT INTO bookings (
                client_id, appointment_time, service_type, status, urgency,
                address, eircode, property_type, charge, payment_status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job["client_id"],
            appointment_time,
            job["service_type"],
            "scheduled",
            job["urgency"],
            job["address"],
            job["eircode"],
            job["property_type"],
            job["charge"],
            job["payment_status"],
            datetime.now() - timedelta(hours=random.randint(1, 48))
        ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Added {len(upcoming_jobs)} upcoming jobs")

def update_client_stats(db: Database):
    """Update client statistics based on bookings"""
    print("📊 Updating client statistics...")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Update total_appointments and last_visit for each client
    cursor.execute("""
        UPDATE clients
        SET total_appointments = (
            SELECT COUNT(*) FROM bookings WHERE bookings.client_id = clients.id
        ),
        last_visit = (
            SELECT MAX(appointment_time) FROM bookings 
            WHERE bookings.client_id = clients.id AND bookings.status = 'completed'
        ),
        first_visit = (
            SELECT MIN(appointment_time) FROM bookings 
            WHERE bookings.client_id = clients.id
        )
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ Client statistics updated")

def main():
    """Main function to reset and populate database"""
    print("\n" + "="*60)
    print("🔧 TRADES DATABASE RESET & POPULATE")
    print("="*60 + "\n")
    
    db = Database()
    
    # Step 1: Clear existing data
    clear_database(db)
    
    # Step 2: Add workers
    add_workers(db)
    
    # Step 3: Add past customers
    client_ids = add_past_customers(db)
    
    # Step 4: Add past jobs
    add_past_jobs(db, client_ids)
    
    # Step 5: Add upcoming jobs
    add_upcoming_jobs(db, client_ids)
    
    # Step 6: Update statistics
    update_client_stats(db)
    
    print("\n" + "="*60)
    print("✅ DATABASE RESET COMPLETE")
    print("="*60)
    print(f"\n📊 Summary:")
    print(f"   • {len(client_ids)} customers added")
    print(f"   • 14 past jobs added")
    print(f"   • 3 upcoming jobs added")
    print(f"   • 4 workers added")
    print("\n🎯 Ready for trades company demo!\n")

if __name__ == "__main__":
    main()
