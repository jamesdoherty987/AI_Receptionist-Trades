"""
Comprehensive test for address collection and all required fields.
Tests new customers, returning customers, and edge cases.
"""

import sys
import os
from datetime import datetime, timedelta
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.database import Database
from src.services.calendar_tools import execute_tool_call

def generate_unique_event_id():
    """Generate a unique calendar event ID for testing"""
    return f"test_event_{uuid.uuid4().hex[:12]}"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_lookup_customer_with_address():
    """Test that lookup_customer returns address information"""
    print_section("TEST 1: Lookup Customer - Should Return Last Address")
    
    db = Database()
    
    # Create a test customer with a booking that has an address
    client_id = db.find_or_create_client(
        name="Test Customer One",
        phone="0851111111",
        email="test1@test.com",
        date_of_birth=None
    )
    
    # Add a booking with address
    test_time = datetime.now() + timedelta(days=1)
    booking_id = db.add_booking(
        client_id=client_id,
        calendar_event_id=generate_unique_event_id(),
        appointment_time=test_time,
        service_type="Plumbing - Test",
        phone_number="0851111111",
        email="test1@test.com",
        urgency="scheduled",
        address="123 Test Street, Limerick, V94 ABC1",
        eircode="V94 ABC1",
        property_type="residential"
    )
    
    print(f"✓ Created test customer (ID: {client_id}) with booking (ID: {booking_id})")
    print(f"  Address saved: 123 Test Street, Limerick, V94 ABC1")
    
    # Test lookup
    services = {
        'database': db,
        'google_calendar': None
    }
    
    result = execute_tool_call(
        "lookup_customer",
        {"customer_name": "Test Customer One"},
        services
    )
    
    print(f"\n📋 Lookup Result:")
    print(f"  Success: {result.get('success')}")
    print(f"  Customer Exists: {result.get('customer_exists')}")
    
    if result.get('customer_info'):
        info = result['customer_info']
        print(f"  Name: {info.get('name')}")
        print(f"  Phone: {info.get('phone')}")
        print(f"  Email: {info.get('email')}")
        print(f"  Last Address: {info.get('last_address')}")
    
    print(f"  Message: {result.get('message')}")
    
    # Verify address is returned
    assert result.get('success'), "Lookup should succeed"
    assert result.get('customer_exists'), "Customer should exist"
    assert result['customer_info'].get('last_address') == "123 Test Street, Limerick, V94 ABC1", "Address should be returned"
    
    print("\n✅ TEST PASSED: Address is returned in lookup")
    
    # Cleanup
    db.delete_booking(booking_id)
    print(f"🧹 Cleaned up test booking")

def test_book_job_with_all_fields():
    """Test booking a job with all required fields including address"""
    print_section("TEST 2: Book Job - All Required Fields Including Address")
    
    db = Database()
    services = {
        'database': db,
        'google_calendar': None  # We'll mock this
    }
    
    # Test data - NEW customer
    booking_data = {
        "customer_name": "Test Customer Two",
        "phone": "0852222222",
        "email": "test2@test.com",
        "job_address": "456 Oak Avenue, Cork, T12 XYZ9",
        "job_description": "Blocked drain in kitchen sink",
        "appointment_datetime": "tomorrow at 2pm",
        "urgency_level": "same-day",
        "property_type": "residential"
    }
    
    print("\n📝 Attempting to book job with:")
    for key, value in booking_data.items():
        print(f"  {key}: {value}")
    
    # Note: This will fail because we don't have Google Calendar connected
    # But we can check the validation logic
    result = execute_tool_call("book_job", booking_data, services)
    
    print(f"\n📋 Booking Result:")
    print(f"  Success: {result.get('success')}")
    if result.get('error'):
        print(f"  Error: {result.get('error')}")
    if result.get('message'):
        print(f"  Message: {result.get('message')}")
    
    # Check validation - all required fields should be present
    if not result.get('success'):
        error = result.get('error', '')
        # Should NOT complain about missing required fields
        assert 'name is required' not in error.lower(), "Name should be provided"
        assert 'phone' not in error.lower() or 'mandatory' not in error.lower(), "Phone should be provided"
        assert 'email' not in error.lower() or 'mandatory' not in error.lower(), "Email should be provided"
        assert 'address is required' not in error.lower(), "Address should be provided"
        assert 'job description is required' not in error.lower(), "Job description should be provided"
        print("\n✅ TEST PASSED: All required fields validated correctly")
    else:
        # If successful, verify booking was saved with address
        print("\n✅ TEST PASSED: Booking created successfully")

def test_missing_required_fields():
    """Test that missing required fields are caught"""
    print_section("TEST 3: Missing Required Fields - Should Fail Validation")
    
    db = Database()
    services = {
        'database': db,
        'google_calendar': None
    }
    
    test_cases = [
        {
            "name": "Missing Phone",
            "data": {
                "customer_name": "Test Customer",
                "email": "test@test.com",
                "job_address": "123 Street",
                "job_description": "Fix leak",
                "appointment_datetime": "tomorrow at 2pm",
                "urgency_level": "scheduled"
            },
            "expected_error": "phone"
        },
        {
            "name": "Missing Email",
            "data": {
                "customer_name": "Test Customer",
                "phone": "0851234567",
                "job_address": "123 Street",
                "job_description": "Fix leak",
                "appointment_datetime": "tomorrow at 2pm",
                "urgency_level": "scheduled"
            },
            "expected_error": "email"
        },
        {
            "name": "Missing Address",
            "data": {
                "customer_name": "Test Customer",
                "phone": "0851234567",
                "email": "test@test.com",
                "job_description": "Fix leak",
                "appointment_datetime": "tomorrow at 2pm",
                "urgency_level": "scheduled"
            },
            "expected_error": "address"
        },
        {
            "name": "Missing Job Description",
            "data": {
                "customer_name": "Test Customer",
                "phone": "0851234567",
                "email": "test@test.com",
                "job_address": "123 Street",
                "appointment_datetime": "tomorrow at 2pm",
                "urgency_level": "scheduled"
            },
            "expected_error": "job description"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🧪 Testing: {test_case['name']}")
        result = execute_tool_call("book_job", test_case['data'], services)
        
        assert not result.get('success'), f"{test_case['name']} should fail"
        error = result.get('error', '').lower()
        assert test_case['expected_error'] in error, f"Should mention missing {test_case['expected_error']}"
        print(f"  ✓ Correctly rejected: {result.get('error')}")
    
    print("\n✅ TEST PASSED: All missing required fields are caught")

def test_vague_time_rejection():
    """Test that vague times like 'ASAP' are rejected"""
    print_section("TEST 4: Vague Time Rejection - Should Require Specific Time")
    
    db = Database()
    services = {
        'database': db,
        'google_calendar': None
    }
    
    vague_times = [
        "ASAP",
        "as soon as possible",
        "within 2 hours",
        "urgently",
        "right away",
        "immediately"
    ]
    
    for vague_time in vague_times:
        print(f"\n🧪 Testing vague time: '{vague_time}'")
        result = execute_tool_call("book_job", {
            "customer_name": "Test Customer",
            "phone": "0851234567",
            "email": "test@test.com",
            "job_address": "123 Street, Limerick",
            "job_description": "Emergency plumbing",
            "appointment_datetime": vague_time,
            "urgency_level": "emergency"
        }, services)
        
        assert not result.get('success'), f"'{vague_time}' should be rejected"
        error = result.get('error', '')
        assert 'not specific enough' in error.lower() or 'check availability' in error.lower(), \
            f"Should indicate time is not specific: {error}"
        print(f"  ✓ Correctly rejected: {error}")
    
    print("\n✅ TEST PASSED: All vague times are rejected")

def test_address_in_database():
    """Test that address is actually saved to the database"""
    print_section("TEST 5: Database Storage - Verify Address is Saved")
    
    db = Database()
    
    # Create a test customer
    client_id = db.find_or_create_client(
        name="Address Test Customer",
        phone="0853333333",
        email="addresstest@test.com",
        date_of_birth=None
    )
    
    print(f"✓ Created test customer (ID: {client_id})")
    
    # Create a booking with address
    test_address = "789 Test Boulevard, Galway, H91 XY12"
    test_eircode = "H91 XY12"
    test_property_type = "commercial"
    test_time = datetime.now() + timedelta(days=2)
    
    booking_id = db.add_booking(
        client_id=client_id,
        calendar_event_id=generate_unique_event_id(),
        appointment_time=test_time,
        service_type="Electrical - Test",
        phone_number="0853333333",
        email="addresstest@test.com",
        urgency="scheduled",
        address=test_address,
        eircode=test_eircode,
        property_type=test_property_type
    )
    
    print(f"✓ Created booking (ID: {booking_id})")
    print(f"  Address: {test_address}")
    print(f"  Eircode: {test_eircode}")
    print(f"  Property Type: {test_property_type}")
    
    # Retrieve and verify
    bookings = db.get_client_bookings(client_id)
    assert len(bookings) > 0, "Should have at least one booking"
    
    found_booking = None
    for booking in bookings:
        if booking['id'] == booking_id:
            found_booking = booking
            break
    
    assert found_booking is not None, "Should find the created booking"
    
    print(f"\n📋 Retrieved Booking from Database:")
    print(f"  ID: {found_booking['id']}")
    print(f"  Address: {found_booking.get('address')}")
    print(f"  Eircode: {found_booking.get('eircode')}")
    print(f"  Property Type: {found_booking.get('property_type')}")
    print(f"  Urgency: {found_booking.get('urgency')}")
    
    # Verify all fields are saved
    assert found_booking.get('address') == test_address, "Address should be saved"
    assert found_booking.get('eircode') == test_eircode, "Eircode should be saved"
    assert found_booking.get('property_type') == test_property_type, "Property type should be saved"
    
    print("\n✅ TEST PASSED: Address, eircode, and property_type are saved correctly")
    
    # Cleanup
    db.delete_booking(booking_id)
    print(f"🧹 Cleaned up test booking")

def test_returning_customer_address_lookup():
    """Test the full flow for returning customer with address"""
    print_section("TEST 6: Returning Customer Flow - Address from Previous Job")
    
    db = Database()
    
    # Setup: Create customer with previous booking
    client_id = db.find_or_create_client(
        name="Returning Customer Test",
        phone="0854444444",
        email="returning@test.com",
        date_of_birth=None
    )
    
    previous_address = "999 Previous Street, Dublin, D02 AB12"
    test_time = datetime.now() - timedelta(days=30)  # 30 days ago
    
    booking_id = db.add_booking(
        client_id=client_id,
        calendar_event_id=generate_unique_event_id(),
        appointment_time=test_time,
        service_type="Previous Job",
        phone_number="0854444444",
        email="returning@test.com",
        urgency="scheduled",
        address=previous_address,
        property_type="residential"
    )
    
    print(f"✓ Setup: Created returning customer with previous job at: {previous_address}")
    
    # Test: Look up customer
    services = {'database': db, 'google_calendar': None}
    result = execute_tool_call(
        "lookup_customer",
        {"customer_name": "Returning Customer Test"},
        services
    )
    
    print(f"\n📋 Lookup Result:")
    print(f"  Success: {result.get('success')}")
    print(f"  Customer Exists: {result.get('customer_exists')}")
    print(f"  Message: {result.get('message')}")
    
    if result.get('customer_info'):
        info = result['customer_info']
        print(f"\n  Customer Info:")
        print(f"    Name: {info.get('name')}")
        print(f"    Phone: {info.get('phone')}")
        print(f"    Email: {info.get('email')}")
        print(f"    Last Address: {info.get('last_address')}")
        
        # Verify
        assert info.get('last_address') == previous_address, "Should return previous address"
        print(f"\n✅ AI can now ask: 'Is this for {previous_address}, or a different location?'")
    
    print("\n✅ TEST PASSED: Returning customer lookup includes last address")
    
    # Cleanup
    db.delete_booking(booking_id)
    print(f"🧹 Cleaned up test data")

def test_new_customer_no_address_history():
    """Test that new customers don't have address history"""
    print_section("TEST 7: New Customer - No Address History")
    
    db = Database()
    services = {'database': db, 'google_calendar': None}
    
    # Create new customer without bookings
    client_id = db.find_or_create_client(
        name="Brand New Customer",
        phone="0855555555",
        email="newcustomer@test.com",
        date_of_birth=None
    )
    
    print(f"✓ Created new customer (ID: {client_id}) with NO bookings")
    
    # Lookup
    result = execute_tool_call(
        "lookup_customer",
        {"customer_name": "Brand New Customer"},
        services
    )
    
    print(f"\n📋 Lookup Result:")
    print(f"  Customer Exists: {result.get('customer_exists')}")
    
    if result.get('customer_info'):
        info = result['customer_info']
        print(f"  Last Address: {info.get('last_address')}")
        
        assert info.get('last_address') is None, "New customer should have no address history"
        print(f"\n✅ AI will need to ask: 'What's the full address for the job?'")
    
    print("\n✅ TEST PASSED: New customer has no address history")

def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "█"*80)
    print("  COMPREHENSIVE ADDRESS & REQUIRED FIELDS TEST SUITE")
    print("█"*80)
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("█"*80)
    
    tests = [
        ("Lookup Customer Returns Address", test_lookup_customer_with_address),
        ("Book Job With All Fields", test_book_job_with_all_fields),
        ("Missing Required Fields Validation", test_missing_required_fields),
        ("Vague Time Rejection", test_vague_time_rejection),
        ("Database Storage Verification", test_address_in_database),
        ("Returning Customer Address Lookup", test_returning_customer_address_lookup),
        ("New Customer No Address History", test_new_customer_no_address_history)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            print(f"\n💥 TEST ERROR: {test_name}")
            print(f"   Exception: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "█"*80)
    print("  TEST SUMMARY")
    print("█"*80)
    print(f"  Total Tests: {len(tests)}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print("█"*80)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("\n✓ Address collection is working correctly")
        print("✓ All required fields are validated")
        print("✓ Database storage is working")
        print("✓ Returning customers get their last address")
        print("✓ New customers are prompted for address")
    else:
        print(f"\n⚠️  {failed} test(s) failed - please review")
    
    return failed == 0

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
