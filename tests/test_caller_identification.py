"""
Test script for caller identification and greeting flow
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.llm_stream import check_caller_in_database, spell_out_name
from src.services.database import Database

def test_caller_identification():
    """Test the caller identification flow"""
    db = Database()
    
    print("\n" + "="*80)
    print("TESTING CALLER IDENTIFICATION FLOW")
    print("="*80)
    
    # Test 1: New caller
    print("\n📋 TEST 1: New Caller (not in database)")
    print("-" * 80)
    result = check_caller_in_database("Jane Doe", "555-9999")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    print(f"Clients found: {len(result['clients'])}")
    
    # Test 2: Existing caller with unique name
    print("\n📋 TEST 2: Returning Caller (unique name)")
    print("-" * 80)
    result = check_caller_in_database("Sarah Johnson", "555-0102")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    if result['clients']:
        client = result['clients'][0]
        print(f"Client found: {client['name']} (ID: {client['id']})")
        print(f"Phone: {client.get('phone', 'N/A')}")
        print(f"Email: {client.get('email', 'N/A')}")
    
    # Test 3: Multiple clients with same name
    print("\n📋 TEST 3: Multiple Clients with Same Name")
    print("-" * 80)
    # First add a duplicate John Smith
    try:
        db.find_or_create_client("john smith", "555-8888", "john.smith2@email.com")
    except:
        pass
    
    result = check_caller_in_database("John Smith", "555-0101")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    print(f"Clients found: {len(result['clients'])}")
    for i, client in enumerate(result['clients'], 1):
        print(f"  {i}. {client['name']} - Phone: {client.get('phone', 'N/A')} - Email: {client.get('email', 'N/A')}")
    
    # Test 4: Case insensitive matching
    print("\n📋 TEST 4: Case Insensitive Matching")
    print("-" * 80)
    result1 = check_caller_in_database("sarah johnson", "555-0102")
    result2 = check_caller_in_database("SARAH JOHNSON", "555-0102")
    result3 = check_caller_in_database("Sarah Johnson", "555-0102")
    print(f"Lowercase: {result1['status']} - {len(result1['clients'])} client(s)")
    print(f"Uppercase: {result2['status']} - {len(result2['clients'])} client(s)")
    print(f"Mixed case: {result3['status']} - {len(result3['clients'])} client(s)")
    print(f"✅ All variations matched: {result1['status'] == result2['status'] == result3['status']}")
    
    # Test 5: Name spelling
    print("\n📋 TEST 5: Name Spelling Function")
    print("-" * 80)
    test_names = [
        "John Smith",
        "James",
        "O'Brien",
        "Mary-Jane",
        "Sarah Johnson"
    ]
    for name in test_names:
        spelled = spell_out_name(name)
        print(f"{name} → {spelled}")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_caller_identification()
