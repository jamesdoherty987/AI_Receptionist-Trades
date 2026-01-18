# LLM Architecture Analysis & Improvements

## Issue Fixed: "Next Week" Availability Query

### Problem
When users asked "what times are available next week?", the system:
1. Only checked **one day** (incorrectly checking today instead of next week)
2. Returned "no times available" even though 38 slots were available next week
3. Poor separation between date parsing and availability checking

### Solution Implemented
Enhanced the QUERY intent handler to:
- **Detect "next week" queries** explicitly
- **Check ALL weekdays** (Monday-Friday) of next week
- **Aggregate results** from multiple days
- **Format responses** with day names and dates for clarity

**Code changes in** [llm_stream.py](../src/services/llm_stream.py):
- Lines ~2306-2370: Added "next week" detection and multi-day checking
- Lines ~1903-1955: Enhanced LLM system messages to present next week availability clearly

---

## Architecture Recommendations: Function Calling Best Practices

### Current Approach Issues

Your intuition is **absolutely correct**. The current implementation has these problems:

1. **Mixing concerns**: Intent detection, parameter extraction, and action execution are tangled
2. **Complex state management**: `_appointment_state` dict tracks everything manually
3. **Brittle parsing**: Multiple passes of AI parsing for the same information
4. **Indirect function execution**: Callbacks and conditional logic instead of direct function calls
5. **Poor LLM communication**: System messages with instructions instead of structured tool results

### Recommended Architecture: OpenAI Function Calling

Here's how a proper implementation should work:

```python
# DEFINE FUNCTIONS THE LLM CAN CALL
AVAILABLE_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a date or date range",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_type": {
                        "type": "string",
                        "enum": ["specific_date", "next_week", "this_week", "date_range"],
                        "description": "Type of date query"
                    },
                    "specific_date": {
                        "type": "string",
                        "description": "Specific date in YYYY-MM-DD format (if date_type is specific_date)"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date for range queries (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date for range queries (YYYY-MM-DD)"
                    },
                    "time_preference": {
                        "type": "string",
                        "enum": ["morning", "afternoon", "evening", "any"],
                        "description": "Preferred time of day"
                    }
                },
                "required": ["date_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment at a specific time",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "phone": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "time": {"type": "string", "description": "HH:MM in 24h format"},
                    "service_type": {"type": "string"}
                },
                "required": ["patient_name", "phone", "date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_client",
            "description": "Look up existing client information by name and optionally DOB",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "date_of_birth": {"type": "string", "description": "YYYY-MM-DD format"}
                },
                "required": ["name"]
            }
        }
    }
]

# IMPLEMENT THE FUNCTIONS
def check_availability(date_type: str, specific_date: str = None, 
                       start_date: str = None, end_date: str = None,
                       time_preference: str = "any"):
    """
    Clean function that ONLY handles availability checking.
    Returns structured data that LLM can work with.
    """
    calendar = get_calendar_service()
    now = datetime.now()
    
    # Calculate date range based on type
    if date_type == "next_week":
        days_until_monday = (7 - now.weekday()) % 7 or 7
        start = (now + timedelta(days=days_until_monday)).replace(hour=9, minute=0, second=0)
        end = start + timedelta(days=4)  # Monday to Friday
        dates_to_check = [start + timedelta(days=i) for i in range(5)]
    
    elif date_type == "specific_date":
        dates_to_check = [datetime.strptime(specific_date, "%Y-%m-%d")]
    
    # ... handle other date types
    
    # Gather all available slots
    results = {}
    for date in dates_to_check:
        if date.weekday() < 5:  # Weekday only
            slots = calendar.get_available_slots_for_day(date)
            
            # Filter by time preference
            if time_preference == "morning":
                slots = [s for s in slots if s.hour < 12]
            elif time_preference == "afternoon":
                slots = [s for s in slots if 12 <= s.hour < 17]
            
            if slots:
                results[date.date().isoformat()] = [
                    s.strftime("%H:%M") for s in slots
                ]
    
    return {
        "available": bool(results),
        "slots_by_date": results,
        "total_slots": sum(len(slots) for slots in results.values())
    }


# USE IN CHAT LOOP
def chat_stream(user_text: str, conversation_history: list):
    messages = conversation_history + [{"role": "user", "content": user_text}]
    
    # Call OpenAI with tools enabled
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=AVAILABLE_FUNCTIONS,
        tool_choice="auto"  # Let LLM decide when to call functions
    )
    
    # Check if LLM wants to call a function
    if response.choices[0].message.tool_calls:
        # Execute the function(s)
        for tool_call in response.choices[0].message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            # Call the actual function
            if function_name == "check_availability":
                result = check_availability(**arguments)
            elif function_name == "book_appointment":
                result = book_appointment(**arguments)
            elif function_name == "lookup_client":
                result = lookup_client(**arguments)
            
            # Add function result to conversation
            messages.append({
                "role": "function",
                "name": function_name,
                "content": json.dumps(result)
            })
        
        # Get LLM's final response with function results
        final_response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        
        return final_response.choices[0].message.content
    
    # No function call needed, return direct response
    return response.choices[0].message.content
```

### Benefits of Function Calling Approach

✅ **Clean separation of concerns**
- LLM handles: conversation flow, parameter extraction, natural responses
- Functions handle: business logic, data access, validation

✅ **Automatic parameter extraction**
- LLM fills function parameters based on conversation context
- No manual parsing or regex needed
- Built-in type validation

✅ **Stateless functions**
- Each function is independent and testable
- No complex state management
- Easier to debug and maintain

✅ **Better error handling**
- Function returns structured data
- LLM can naturally communicate errors to users

✅ **Scalable**
- Easy to add new capabilities (just add new functions)
- Functions can be versioned independently
- Can optimize/cache individual functions

### Migration Path

**Phase 1: Extract Pure Functions** (Start Here)
```python
# Create clean, testable functions
def get_available_slots_for_week(start_date: datetime) -> dict:
    """Pure function - no side effects, no state"""
    ...

def find_client_by_name_and_dob(name: str, dob: str) -> dict:
    """Returns structured data, no conversation logic"""
    ...
```

**Phase 2: Define Function Schemas**
```python
# Define OpenAI function schemas
AVAILABILITY_FUNCTION = {
    "name": "check_availability",
    "description": "...",
    "parameters": {...}
}
```

**Phase 3: Implement Function Calling**
```python
# Update chat_stream to use tool_calls
response = client.chat.completions.create(
    ...,
    tools=[AVAILABILITY_FUNCTION, BOOKING_FUNCTION],
    tool_choice="auto"
)
```

**Phase 4: Remove Legacy Code**
- Remove manual intent detection
- Remove _appointment_state dict
- Remove callback system
- Simplify system prompts

### Example: Current vs Improved

**Current (Complex):**
```
User: "what times are available next week"
→ Intent detection (AI call #1)
→ Parse "next week" (AI call #2)
→ Manual date calculation
→ State updates
→ Callback execution
→ System message injection
→ LLM response (AI call #3)
```

**Improved (Simple):**
```
User: "what times are available next week"
→ LLM decides to call check_availability()
   Parameters: {date_type: "next_week"}
→ Function executes, returns slots
→ LLM generates natural response with results
```

**Result:** 3 AI calls → 1 AI call, cleaner code, fewer bugs

---

## Specific Recommendations for Your System

### 1. Create Core Functions Module

```python
# src/services/appointment_functions.py

def check_availability(date_type, **kwargs):
    """Clean availability checker"""
    ...

def book_appointment(patient_name, phone, date, time, **kwargs):
    """Clean booking function"""
    ...

def find_client(name, dob=None, phone=None):
    """Clean client lookup"""
    ...

def reschedule_appointment(old_datetime, new_datetime, client_id):
    """Clean reschedule function"""
    ...
```

### 2. Define Function Schemas

Create `src/services/function_schemas.py` with OpenAI function definitions

### 3. Simplify LLM Stream

Replace complex intent detection + callbacks with:
```python
def chat_stream(user_text, history):
    response = call_openai_with_tools(user_text, history)
    
    if needs_function_call(response):
        result = execute_function(response.tool_calls[0])
        return call_openai_with_result(history, result)
    
    return response.content
```

### 4. Keep State Minimal

Only store:
- `conversation_history` (messages array)
- `current_booking` (when actively booking)

LLM maintains context through conversation history, not complex state dict.

---

## Summary

**Your instinct is correct** - a cleaner architecture with dedicated functions that the LLM calls directly is the better approach. This is exactly what OpenAI's function calling feature is designed for.

**Next Steps:**
1. ✅ Test the "next week" fix (implemented above)
2. Consider migrating to function calling architecture gradually
3. Start with `check_availability` as it's now well-defined
4. Extract other operations into clean functions
5. Add OpenAI function schemas
6. Simplify the main chat loop

The current system works but is hard to maintain. Function calling would make it **cleaner, more reliable, and easier to extend**.
