"""
Test DOB extraction with informal input (e.g., 'the first on january 2000')
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.llm_stream import _appointment_state, reset_appointment_state, stream_llm

async def test_dob_informal():
    print("\n" + "="*60)
    print("🧪 TESTING DOB EXTRACTION WITH INFORMAL INPUT")
    print("="*60 + "\n")
    
    reset_appointment_state()
    messages = [
        {"role": "assistant", "content": "Can I get your date of birth, please?"},
        {"role": "user", "content": "the first on january 2000"}
    ]
    async for _ in stream_llm(messages):
        pass
    print(f"Full appointment state: {_appointment_state}")
    dob = _appointment_state.get("date_of_birth")
    print(f"Extracted DOB: {dob}")
    assert dob == "2000-01-01", f"DOB extraction failed, got: {dob}"
    print("✅ Informal DOB extraction test passed!\n")

if __name__ == "__main__":
    asyncio.run(test_dob_informal())
