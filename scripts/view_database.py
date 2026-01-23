"""
View database contents for trades company
"""
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import Database

def view_customers(db: Database):
    """Display all customers"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, phone, email, total_appointments, description
        FROM clients
        ORDER BY total_appointments DESC
    """)
    
    customers = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*80)
    print("👥 CUSTOMERS")
    print("="*80)
    
    for customer in customers:
        id, name, phone, email, total, desc = customer
        print(f"\n🔹 {name} (ID: {id})")
        print(f"   📱 Phone: {phone}")
        print(f"   ✉️  Email: {email}")
        print(f"   📊 Total Jobs: {total}")
        if desc:
            print(f"   💬 Notes: {desc}")

def view_workers(db: Database):
    """Display all workers"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, phone, email, trade_specialty, status
        FROM workers
        ORDER BY name
    """)
    
    workers = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*80)
    print("👷 WORKERS / TRADESPEOPLE")
    print("="*80)
    
    for worker in workers:
        name, phone, email, specialty, status = worker
        status_icon = "✅" if status == "active" else "❌"
        print(f"\n{status_icon} {name}")
        print(f"   🔧 Specialty: {specialty}")
        print(f"   📱 Phone: {phone}")
        print(f"   ✉️  Email: {email}")

def view_past_jobs(db: Database):
    """Display past completed jobs"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.name,
            b.service_type,
            b.address,
            b.urgency,
            b.charge,
            b.payment_status,
            b.appointment_time
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        WHERE b.status = 'completed'
        ORDER BY b.appointment_time DESC
        LIMIT 10
    """)
    
    jobs = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*80)
    print("📋 PAST JOBS (Most Recent 10)")
    print("="*80)
    
    total_revenue = 0
    for job in jobs:
        name, service, address, urgency, charge, payment, appt_time = job
        
        # Parse datetime
        if isinstance(appt_time, str):
            dt = datetime.fromisoformat(appt_time.replace('Z', '+00:00'))
        else:
            dt = appt_time
        
        urgency_icons = {
            'emergency': '🚨',
            'same-day': '⚡',
            'scheduled': '📅',
            'quote': '💰'
        }
        urgency_icon = urgency_icons.get(urgency, '📋')
        
        payment_icon = "✅" if payment == "paid" else "❌"
        
        print(f"\n{urgency_icon} {service}")
        print(f"   👤 Customer: {name}")
        print(f"   📍 Address: {address}")
        print(f"   📅 Date: {dt.strftime('%d %b %Y %H:%M')}")
        print(f"   💶 Charge: €{charge:.2f} {payment_icon} {payment}")
        
        if payment == "paid":
            total_revenue += charge
    
    print(f"\n💰 Total Revenue (from shown jobs): €{total_revenue:.2f}")

def view_upcoming_jobs(db: Database):
    """Display upcoming scheduled jobs"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.name,
            c.phone,
            b.service_type,
            b.address,
            b.urgency,
            b.charge,
            b.appointment_time
        FROM bookings b
        JOIN clients c ON b.client_id = c.id
        WHERE b.status = 'scheduled'
        ORDER BY b.appointment_time ASC
    """)
    
    jobs = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*80)
    print("📅 UPCOMING JOBS")
    print("="*80)
    
    if not jobs:
        print("\n   No upcoming jobs scheduled")
    else:
        for job in jobs:
            name, phone, service, address, urgency, charge, appt_time = job
            
            # Parse datetime
            if isinstance(appt_time, str):
                dt = datetime.fromisoformat(appt_time.replace('Z', '+00:00'))
            else:
                dt = appt_time
            
            days_until = (dt.date() - datetime.now().date()).days
            
            print(f"\n📋 {service}")
            print(f"   👤 Customer: {name} ({phone})")
            print(f"   📍 Address: {address}")
            print(f"   📅 Scheduled: {dt.strftime('%d %b %Y %H:%M')} ({days_until} days)")
            print(f"   💶 Charge: €{charge:.2f}")

def view_stats(db: Database):
    """Display database statistics"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Count customers
    cursor.execute("SELECT COUNT(*) FROM clients")
    customer_count = cursor.fetchone()[0]
    
    # Count workers
    cursor.execute("SELECT COUNT(*) FROM workers")
    worker_count = cursor.fetchone()[0]
    
    # Count total jobs
    cursor.execute("SELECT COUNT(*) FROM bookings")
    total_jobs = cursor.fetchone()[0]
    
    # Count completed jobs
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE status = 'completed'")
    completed_jobs = cursor.fetchone()[0]
    
    # Count upcoming jobs
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE status = 'scheduled'")
    upcoming_jobs = cursor.fetchone()[0]
    
    # Total revenue
    cursor.execute("SELECT SUM(charge) FROM bookings WHERE payment_status = 'paid'")
    total_revenue = cursor.fetchone()[0] or 0
    
    # Emergency jobs
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE urgency = 'emergency'")
    emergency_jobs = cursor.fetchone()[0]
    
    conn.close()
    
    print("\n" + "="*80)
    print("📊 DATABASE STATISTICS")
    print("="*80)
    print(f"\n👥 Total Customers: {customer_count}")
    print(f"👷 Total Workers: {worker_count}")
    print(f"📋 Total Jobs: {total_jobs}")
    print(f"   ✅ Completed: {completed_jobs}")
    print(f"   📅 Upcoming: {upcoming_jobs}")
    print(f"   🚨 Emergency Jobs: {emergency_jobs}")
    print(f"💰 Total Revenue (Paid): €{total_revenue:.2f}")

def main():
    """Main function to display database contents"""
    db = Database()
    
    print("\n" + "="*80)
    print("🔧 SWIFT TRADE SERVICES - DATABASE VIEWER")
    print("="*80)
    
    view_stats(db)
    view_customers(db)
    view_workers(db)
    view_upcoming_jobs(db)
    view_past_jobs(db)
    
    print("\n" + "="*80)
    print("✅ END OF REPORT")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
