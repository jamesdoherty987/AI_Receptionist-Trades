"""
Simulate the exact scenario from the user's transcript
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.date_parser import parse_datetime


def simulate_transcript_scenario():
    """
    Simulate the exact conversation flow from the user's transcript:
    User: "can i do janary 5th"
    Agent asks for time
    User: "1pm please"
    """
    print("\n" + "="*70)
    print("SIMULATING EXACT TRANSCRIPT SCENARIO")
    print("="*70)
    
    print("\n👤 User: 'can i do janary 5th'")
    print("🤖 Agent extracts date: 'janary 5th'")
    
    # First, try parsing just the date (what the agent extracts)
    date_str = "janary 5th"
    print(f"\n🔍 Attempting to parse: '{date_str}'")
    result1 = parse_datetime(date_str)
    
    if result1 is None:
        print("✅ Correctly detected date-only (no time) - will prompt for time")
    else:
        print(f"⚠️ Unexpected: Got {result1}")
    
    print("\n🤖 Agent: 'What time works best for you on January 5th?'")
    print("👤 User: '1pm please'")
    
    # Now simulate combining the date with the new time
    time_str = "1pm"
    combined = f"{date_str} {time_str}"
    print(f"\n🔍 Combining previous date with new time: '{combined}'")
    result2 = parse_datetime(combined)
    
    if result2:
        print(f"✅ SUCCESS! Parsed as: {result2.strftime('%B %d, %Y at %I:%M %p')}")
        print("\n🤖 Agent can now proceed with booking!")
    else:
        print("❌ FAILED - would still be stuck in loop")
    
    # Also test the variations the user tried
    print("\n" + "="*70)
    print("Testing other variations user tried:")
    print("="*70)
    
    variations = ["1", "1pm"]
    for var in variations:
        combined_var = f"{date_str} {var}"
        print(f"\nUser says: '{var}'")
        print(f"Combined with date: '{combined_var}'")
        result = parse_datetime(combined_var)
        if result:
            print(f"✅ SUCCESS: {result.strftime('%B %d, %Y at %I:%M %p')}")
        else:
            print(f"❌ FAILED: Unable to parse")


if __name__ == "__main__":
    simulate_transcript_scenario()
    
    print("\n" + "="*70)
    print("SIMULATION COMPLETE")
    print("="*70)
