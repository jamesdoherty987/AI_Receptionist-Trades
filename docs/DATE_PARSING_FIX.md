# Date Parsing Fix - January 1, 2026

## Issue
The receptionist was calculating weekday dates incorrectly. When users said "next Monday" on Thursday, January 1, 2026, the system calculated:
- ❌ **Incorrect**: January 4, 2026 (Saturday) - off by 1 day
- ✅ **Correct**: January 5, 2026 (Monday)

This caused the system to:
1. Look for appointments on the wrong day
2. Not find existing appointments (e.g., Patrick Walsh's Monday 10am appointment)
3. Offer weekend times when weekends are excluded from business hours

## Root Cause
The AI date parser (using GPT-4o-mini) was returning `relative_days: 3` for "next Monday" instead of returning `day_of_week: 'monday'`. 

When the AI returned `relative_days: 3`:
- Thursday, Jan 1 + 3 days = Saturday, Jan 4 ❌

When using `day_of_week: 'monday'` (correct approach):
- Calculate: (0 - 3) % 7 = 4 days ahead
- Thursday, Jan 1 + 4 days = Monday, Jan 5 ✅

## Solution
Updated `src/utils/date_parser.py` to:

1. **Function schema improvements** (lines 51-60):
   - Clarified that `relative_days` should ONLY be used for "today", "tomorrow", "day after tomorrow"
   - Emphasized that `day_of_week` should ALWAYS be used for weekday names (Monday, Tuesday, etc.)

2. **System prompt enhancement** (line 107):
   - Added explicit instruction: "When user mentions a weekday name, ALWAYS use the 'day_of_week' field, NOT 'relative_days'"
   - Reinforced: "Use 'relative_days' ONLY for 'today', 'tomorrow', 'day after tomorrow'"

## Testing
```bash
python test_monday_fix.py
```

Results:
- ✅ "next Monday at 10am" → Monday, January 5, 2026 10:00
- ✅ "Friday at 11am" → Friday, January 2, 2026 11:00
- ✅ "next Tuesday at 3pm" → Tuesday, January 6, 2026 15:00
- ✅ Found Patrick Walsh's appointment on Monday Jan 5 at 10am

## Impact
- Fixes reschedule flow for weekday appointments
- Ensures appointments are found at correct times
- Prevents weekend days from being offered when business hours are Monday-Friday
- Users in Dublin, Ireland timezone will now see correct calendar calculations
