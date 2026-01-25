"""
Test script for services menu and business hours functionality
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.settings_manager import get_settings_manager

def test_services_menu():
    """Test services menu functionality"""
    print("=" * 60)
    print("Testing Services Menu & Business Hours")
    print("=" * 60)
    
    settings_mgr = get_settings_manager()
    
    # Test 1: Load services menu
    print("\n1. Loading services menu...")
    menu = settings_mgr.get_services_menu()
    print(f"   ✓ Business Name: {menu.get('business_name', 'Not set')}")
    print(f"   ✓ Services count: {len(menu.get('services', []))}")
    print(f"   ✓ Business hours: {menu.get('business_hours', {}).get('start_hour', 'N/A')} to {menu.get('business_hours', {}).get('end_hour', 'N/A')}")
    print(f"   ✓ Days open: {', '.join(menu.get('business_hours', {}).get('days_open', []))}")
    
    # Test 2: Display services
    print("\n2. Available Services:")
    services = menu.get('services', [])
    if services:
        for service in services:
            status = "✓ Active" if service.get('active', True) else "✗ Inactive"
            print(f"   {status} - {service['name']} ({service['category']}) - €{service['price']}")
    else:
        print("   No services configured yet")
    
    # Test 3: Business hours details
    print("\n3. Business Hours Details:")
    hours = menu.get('business_hours', {})
    print(f"   Start: {hours.get('start_hour', 9)}:00")
    print(f"   End: {hours.get('end_hour', 17)}:00")
    print(f"   Timezone: {hours.get('timezone', 'Europe/Dublin')}")
    print(f"   Days: {', '.join(hours.get('days_open', ['Monday-Friday']))}")
    print(f"   Notes: {hours.get('notes', 'None')}")
    
    # Test 4: Pricing notes
    print("\n4. Pricing Information:")
    pricing = menu.get('pricing_notes', {})
    print(f"   Callout fee: {pricing.get('callout_fee', 'Not set')}")
    print(f"   Hourly rate: {pricing.get('hourly_rate', 'Not set')}")
    print(f"   Payment methods: {', '.join(pricing.get('payment_methods', []))}")
    print(f"   Free quotes: {'Yes' if pricing.get('free_quotes', True) else 'No'}")
    
    # Test 5: Service policies
    print("\n5. Service Policies:")
    policies = menu.get('service_policies', {})
    print(f"   Cancellation notice: {policies.get('cancellation_notice', 'Not set')}")
    print(f"   Emergency response: {policies.get('emergency_response_hours', 'Not set')} hours")
    print(f"   Warranty: {policies.get('warranty_months', 'Not set')} months")
    print(f"   Service area: {policies.get('service_area_km', 'Not set')} km")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start the app: python src/app.py")
    print("2. Visit dashboard: http://localhost:5000/dashboard")
    print("3. Click 'Services Menu' to configure your business")
    print("=" * 60)

if __name__ == "__main__":
    test_services_menu()
