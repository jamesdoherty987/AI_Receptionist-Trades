"""
Text-based chat interface for testing AI receptionist
Test appointment booking by typing instead of calling
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path so we can import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.llm_stream import stream_llm, process_appointment_with_calendar, reset_appointment_state

async def chat_loop():
    """Interactive chat loop for testing"""
    print("\n" + "="*80)
    print("🤖 AI RECEPTIONIST - TEXT CHAT TEST")
    print("="*80)
    print("\nType 'quit' or 'exit' to end the conversation")
    print("Type 'reset' to clear appointment state and start over")
    print("\n" + "="*80 + "\n")
    
    # Initialize conversation with greeting
    conversation = []
    
    # Add initial greeting
    greeting = "Hi, thank you for calling. How can I help you today?"
    print(f"🤖 Assistant: {greeting}\n")
    conversation.append({"role": "assistant", "content": greeting})
    
    while True:
        # Get user input
        try:
            user_input = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        # Check for special commands
        if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
            print("\n👋 Thank you for calling. Goodbye!\n")
            break
        
        if user_input.lower() == 'reset':
            reset_appointment_state()
            conversation = []
            greeting = "Starting fresh. How can I help you today?"
            print(f"\n🔄 {greeting}\n")
            conversation.append({"role": "assistant", "content": greeting})
            continue
        
        # Add user message to conversation
        conversation.append({"role": "user", "content": user_input})
        
        # Get LLM response with appointment detection
        print("🤖 Assistant: ", end="", flush=True)
        response_text = ""
        
        try:
            async for token in stream_llm(conversation, process_appointment_with_calendar):
                print(token, end="", flush=True)
                response_text += token
            print("\n")  # New line after response
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            continue
        
        # Add assistant response to conversation
        if response_text:
            # Note: stream_llm already adds to conversation, so we don't need to add again
            pass

async def main():
    """Main entry point"""
    try:
        await chat_loop()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
