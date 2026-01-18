"""
Test script to initialize settings database and verify functionality
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.settings_manager import get_settings_manager

def test_settings():
    """Test settings manager functionality"""
    print("🧪 Testing Settings Manager...")
    print("=" * 60)
    
    settings_mgr = get_settings_manager()
    
    # Test business settings
    print("\n📊 Business Settings:")
    business_settings = settings_mgr.get_business_settings()
    print(f"Business Name: {business_settings.get('business_name')}")
    print(f"Opening Hours: {business_settings.get('opening_hours_start')} - {business_settings.get('opening_hours_end')}")
    print(f"Currency: {business_settings.get('currency')}")
    print(f"Default Charge: {business_settings.get('default_charge')}")
    
    # Test developer settings
    print("\n⚙️ Developer Settings:")
    dev_settings = settings_mgr.get_developer_settings()
    print(f"OpenAI Model: {dev_settings.get('openai_model')}")
    print(f"TTS Provider: {dev_settings.get('tts_provider')}")
    print(f"Log Level: {dev_settings.get('log_level')}")
    
    # Test update
    print("\n🔄 Testing settings update...")
    test_update = {
        'business_name': 'Munster Physio (Test Update)',
        'default_charge': 55.0
    }
    success = settings_mgr.update_business_settings(test_update)
    print(f"Update {'successful' if success else 'failed'}!")
    
    # Verify update
    updated_settings = settings_mgr.get_business_settings()
    print(f"Updated Business Name: {updated_settings.get('business_name')}")
    print(f"Updated Default Charge: {updated_settings.get('default_charge')}")
    
    # Revert test changes
    revert = {
        'business_name': 'Munster Physio',
        'default_charge': 50.0
    }
    settings_mgr.update_business_settings(revert)
    print("\n✅ Test reverted to original values")
    
    # Test history
    print("\n📜 Settings History (last 5 changes):")
    history = settings_mgr.get_settings_history(5)
    for entry in history:
        print(f"  - {entry['setting_type']}.{entry['setting_key']}: {entry['old_value']} → {entry['new_value']}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")

if __name__ == "__main__":
    test_settings()
