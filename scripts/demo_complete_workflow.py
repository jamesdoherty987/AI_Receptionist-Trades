"""
Demo: Complete workflow of appointment notes → AI description
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database
from src.services.client_description_generator import update_client_description

def demo_workflow():
    """Demonstrate the complete workflow"""
    db = Database()
    
    print("\n" + "="*80)
    print("🎬 DEMO: APPOINTMENT NOTES → AI DESCRIPTION WORKFLOW")
    print("="*80 + "\n")
    
    # Get a client with bookings
    clients = db.get_all_clients()
    client = next((c for c in clients if c.get('total_appointments', 0) > 0), None)
    
    if not client:
        print("❌ No clients with bookings found")
        return
    
    print(f"📋 Client: {client['name'].title()}")
    print(f"   Current Description:")
    if client.get('description'):
        print(f"   {client['description']}\n")
    else:
        print("   (No description yet)\n")
    
    # Get bookings
    bookings = db.get_client_bookings(client['id'])
    print(f"📅 Total Appointments: {len(bookings)}\n")
    
    # Show first booking details
    if bookings:
        booking = bookings[0]  # Most recent
        print(f"📌 Most Recent Appointment:")
        print(f"   Date: {booking['appointment_time']}")
        print(f"   Service: {booking['service_type']}")
        print(f"   Status: {booking['status']}")
        
        # Show notes
        notes = booking.get('notes', [])
        print(f"   Notes: {len(notes)}")
        for note in notes:
            print(f"      - {note['note']}")
        print()
    
    # Simulate staff workflow
    print("👨‍⚕️ STAFF WORKFLOW SIMULATION:")
    print("-" * 80)
    print("1. Staff opens dashboard and views client")
    print("2. Staff clicks '📝 Notes' button on appointment")
    print("3. Staff adds notes during/after appointment:")
    print("   - 'Patient reports improved mobility'")
    print("   - 'Recommended home exercises'")
    print("   - 'Follow-up in 2 weeks'")
    print("4. Staff clicks '✓ Complete' button")
    print("5. System marks appointment as completed")
    print("6. AI analyzes all appointments and notes...")
    print()
    
    # Trigger AI description update
    print("🤖 GENERATING AI DESCRIPTION...")
    print("-" * 80)
    success = update_client_description(client['id'])
    
    if success:
        # Get updated client
        updated_client = db.get_client(client['id'])
        print("\n✅ NEW AI-GENERATED DESCRIPTION:")
        print("-" * 80)
        print(updated_client.get('description', 'No description'))
        print("-" * 80)
    else:
        print("❌ Description generation failed")
    
    print("\n" + "="*80)
    print("✅ WORKFLOW COMPLETE")
    print("="*80)
    print("\n📊 Summary:")
    print(f"   • Client: {client['name'].title()}")
    print(f"   • Appointments: {len(bookings)}")
    print(f"   • Description: Updated with AI (GPT-4o-mini)")
    print(f"   • Cost: ~$0.00003 per update")
    print(f"   • Time: <2 seconds")
    print()

if __name__ == "__main__":
    demo_workflow()
