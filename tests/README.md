# Test Suite

Automated tests for validating AI Receptionist functionality.

## Test Files

### `test_booking_flow.py`
Tests the complete appointment booking flow from intent detection to calendar booking.

**What it tests:**
- Appointment intent detection
- Detail extraction (name, time, service)
- State management across multiple conversation turns
- Calendar booking integration

**Run:**
```bash
python tests/test_booking_flow.py
```

### `test_cancel_reschedule.py`
Tests cancellation and rescheduling functionality.

**What it tests:**
- Finding appointments by name and time
- Rescheduling to new times with availability checking
- Cancellation and verification
- Calendar API integration

**Run:**
```bash
python tests/test_cancel_reschedule.py
```

### `test_business_hours.py`
Validates business hours enforcement and availability checking.

**What it tests:**
- Times outside business hours are auto-adjusted
- Availability checking for multiple time slots
- Same-day slot availability
- Proper overlap detection

**Run:**
```bash
python tests/test_business_hours.py
```

### `test_datetime_parser.py`
Tests natural language date/time parsing.

**What it tests:**
- Various date formats ("tomorrow", "next Friday", "25th of December")
- Time formats ("2pm", "noon", "five thirty", "twelve pm")
- AM/PM handling
- Business hours enforcement

**Run:**
```bash
python tests/test_datetime_parser.py
```

### `test_complete_booking.py`
End-to-end booking test including all steps.

**What it tests:**
- Full booking workflow
- Multiple conversation turns
- Confirmation handling
- Calendar integration

**Run:**
```bash
python tests/test_complete_booking.py
```

## Running Tests

**Run all tests:**
```bash
cd tests
python test_booking_flow.py
python test_cancel_reschedule.py
python test_business_hours.py
python test_datetime_parser.py
```

**Run individual test:**
```bash
python tests/test_booking_flow.py
```

## Test Output

Tests provide detailed console output showing:
- ✅ Successful operations
- ❌ Failed operations
- 📅 Calendar events created/modified
- 🔍 Availability checks
- 📝 Detected intents and details

## Requirements

All tests require:
- Google Calendar authentication (`python scripts/setup_calendar.py`)
- Valid `.env` configuration
- Active internet connection (for OpenAI and Google Calendar APIs)

## Adding New Tests

When adding new functionality:
1. Create a new test file: `test_<feature_name>.py`
2. Import required services
3. Use `asyncio.run()` for async operations
4. Print clear success/failure messages
5. Clean up test data (delete test appointments)

Example structure:
```python
import asyncio
from src.services.google_calendar import get_calendar_service

async def test_new_feature():
    print("Testing new feature...")
    # Test code here
    print("✅ Test passed!")

if __name__ == "__main__":
    asyncio.run(test_new_feature())
```
