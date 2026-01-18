"""
Initialize the dashboard and database
Run this once to set up the system
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database import get_database

def initialize():
    """Initialize database and create directories"""
    print("🔧 Initializing AI Receptionist Dashboard...")
    
    # Create database
    print("\n1. Setting up database...")
    db = get_database()
    print("   ✅ Database initialized at data/receptionist.db")
    
    # Create static directory if it doesn't exist
    print("\n2. Checking directories...")
    Path("src/static").mkdir(parents=True, exist_ok=True)
    print("   ✅ Static directory ready")
    
    print("\n✅ Initialization complete!")
    print("\n📋 Next steps:")
    print("   1. Start the server: python src/app.py")
    print("   2. Open your browser: http://localhost:5000")
    print("   3. Start making bookings via phone!")
    print("\n💡 The dashboard will track all clients and appointments automatically.")

if __name__ == "__main__":
    initialize()
