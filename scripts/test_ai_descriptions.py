"""
Test AI-powered description generation
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.client_description_generator import generate_client_description_from_notes
from src.services.database import Database

def test_ai_descriptions():
    """Test AI description generation for clients with bookings"""
    db = Database()
    
    print("\n" + "="*80)
    print("🤖 TESTING AI-POWERED DESCRIPTION GENERATION")
    print("="*80 + "\n")
    
    # Get all clients with bookings
    all_clients = db.get_all_clients()
    clients_with_bookings = [c for c in all_clients if c.get('total_appointments', 0) > 0]
    
    if not clients_with_bookings:
        print("❌ No clients with bookings found")
        return
    
    print(f"Found {len(clients_with_bookings)} clients with bookings\n")
    
    # Test on first 3 clients
    for i, client in enumerate(clients_with_bookings[:3], 1):
        print(f"📋 Test {i}: {client['name'].title()}")
        print("-" * 80)
        
        # Get bookings
        bookings = db.get_client_bookings(client['id'])
        print(f"   Appointments: {len(bookings)}")
        
        # Show booking details
        for booking in bookings[:3]:  # Show first 3
            service = booking.get('service_type', 'N/A')
            date = booking.get('appointment_time', 'N/A')
            notes_count = len(booking.get('notes', []))
            print(f"   - {date}: {service} ({notes_count} notes)")
        
        # Generate AI description
        print("\n   🤖 Generating AI description...")
        try:
            description = generate_client_description_from_notes(client['id'], use_ai=True)
            
            if description:
                print(f"   ✅ AI Description:")
                print(f"   {description}")
            else:
                print("   ⚠️  No description generated (no bookings)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()
    
    print("="*80)
    print("✅ TESTS COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_ai_descriptions()
