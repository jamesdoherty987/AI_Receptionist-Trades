"""
Test script to verify DOB and description functionality
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.database import Database
from src.services.llm_stream import check_caller_in_database

def test_dob_and_descriptions():
    """Test DOB verification and description display"""
    db = Database()
    
    print("\n" + "="*80)
    print("🧪 TESTING DOB AND DESCRIPTION FUNCTIONALITY")
    print("="*80 + "\n")
    
    # Test 1: Get a client with description
    print("📋 TEST 1: Retrieve client with description")
    print("-" * 80)
    clients = db.get_all_clients()
    
    if clients:
        client = clients[0]
        print(f"👤 Name: {client['name'].title()}")
        print(f"🎂 DOB: {client.get('date_of_birth', 'Not set')}")
        print(f"📝 Description:")
        if client.get('description'):
            print(f"   {client['description']}")
        else:
            print("   No description available")
        print()
    
    # Test 2: Check caller identification (single match)
    print("\n📋 TEST 2: Single client match")
    print("-" * 80)
    if clients:
        test_client = clients[0]
        result = check_caller_in_database(test_client['name'])
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        if result.get('clients'):
            print(f"Clients found: {len(result['clients'])}")
        print()
    
    # Test 3: Check for multiple James Doherty entries (if they exist)
    print("\n📋 TEST 3: Multiple clients with same name (DOB verification)")
    print("-" * 80)
    james_clients = [c for c in clients if 'james' in c['name'].lower() and 'doherty' in c['name'].lower()]
    
    if len(james_clients) > 1:
        print(f"Found {len(james_clients)} clients named James Doherty")
        result = check_caller_in_database("james doherty")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        print(f"Needs DOB: {result.get('needs_dob', False)}")
        print()
        
        # Test DOB verification
        if james_clients[0].get('date_of_birth'):
            print("Testing DOB verification...")
            result_with_dob = check_caller_in_database(
                "james doherty", 
                caller_dob=james_clients[0]['date_of_birth']
            )
            print(f"Status with DOB: {result_with_dob['status']}")
            print(f"Matched by DOB: {result_with_dob.get('matched_by_dob', False)}")
    else:
        print("Only 1 James Doherty found, cannot test multiple match scenario")
    print()
    
    # Test 4: Display all clients with DOB
    print("\n📋 TEST 4: All clients with DOB")
    print("-" * 80)
    for i, client in enumerate(clients[:5], 1):  # Show first 5
        print(f"{i}. {client['name'].title()}")
        print(f"   DOB: {client.get('date_of_birth', 'Not set')}")
        print(f"   Bookings: {client.get('total_appointments', 0)}")
        if client.get('description'):
            desc_preview = client['description'][:100] + "..." if len(client['description']) > 100 else client['description']
            print(f"   Preview: {desc_preview}")
        print()
    
    print("="*80)
    print("✅ TESTS COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_dob_and_descriptions()
