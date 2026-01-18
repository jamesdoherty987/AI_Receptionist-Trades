"""
Initialize settings database with default values
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.settings_manager import get_settings_manager

def init_settings():
    """Initialize settings with defaults"""
    print("🚀 Initializing Settings Database...")
    print("=" * 60)
    
    settings_mgr = get_settings_manager()
    
    print("\n✅ Settings tables created successfully!")
    print("\n📊 Current Business Settings:")
    business = settings_mgr.get_business_settings()
    for key, value in business.items():
        if key not in ['id', 'created_at', 'updated_at']:
            print(f"  {key}: {value}")
    
    print("\n⚙️ Current Developer Settings:")
    dev = settings_mgr.get_developer_settings()
    for key, value in dev.items():
        if key not in ['id', 'created_at', 'updated_at']:
            print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("✅ Settings initialized! Access them at:")
    print("  📊 Business Settings: http://localhost:5000/settings")
    print("  ⚙️ Developer Settings: http://localhost:5000/settings/developer")

if __name__ == "__main__":
    init_settings()
