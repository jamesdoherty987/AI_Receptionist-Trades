"""
Client Description Generator - Creates AI-generated summaries of client history
"""
from datetime import datetime
from typing import Dict, List, Optional
from openai import OpenAI
from src.utils.config import config

# Lazy initialization of OpenAI client
_client = None

def get_openai_client():
    """Get or create OpenAI client instance with timeout"""
    global _client
    if _client is None:
        import httpx
        _client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=httpx.Timeout(20.0, connect=5.0)  # 5s connect, 20s total for description generation
        )
    return _client


def format_date_short(date_str: str) -> str:
    """Format date as d/m/yy (e.g., 12/1/23)"""
    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        else:
            dt = date_str
        return dt.strftime("%d/%m/%y").lstrip("0").replace("/0", "/")
    except:
        return str(date_str)


def generate_client_description_from_notes(client_id: int, use_ai: bool = True, company_id: int = None) -> Optional[str]:
    """
    Generate a client description using AI based on appointment notes and history
    
    This is the preferred method as it uses actual appointment notes to create
    a more accurate and personalized description.
    
    Args:
        client_id: The ID of the client
        use_ai: Whether to use AI generation (True) or template-based (False)
        company_id: Optional company ID for multi-tenant data isolation
        
    Returns:
        Generated description string or None if no bookings
    """
    from src.services.database import get_database
    db = get_database()
    
    # Get client info - filter by company_id for data isolation
    client = db.get_client(client_id, company_id=company_id)
    if not client:
        return None
    
    # Get booking history with notes - filter by company_id for data isolation
    bookings = db.get_client_bookings(client_id, company_id=company_id)
    
    if not bookings or len(bookings) == 0:
        return None
    
    # If AI generation is enabled and we have OpenAI configured
    if use_ai:
        try:
            return _generate_ai_description(client, bookings)
        except Exception as e:
            print(f"⚠️ AI generation failed, falling back to template: {e}")
            # Fall back to template-based generation
    
    # Template-based fallback
    return _generate_template_description(client, bookings)


def _generate_ai_description(client: Dict, bookings: List[Dict]) -> str:
    """
    Use GPT-4o-mini to generate a natural description from appointment history
    """
    client_openai = get_openai_client()
    
    # Extract name
    name_parts = client['name'].split()
    first_name = name_parts[0].capitalize()
    
    # Prepare booking information with notes
    booking_summaries = []
    for booking in reversed(bookings):  # Oldest first
        date_str = format_date_short(booking['appointment_time'])
        service = booking.get('service_type', 'general appointment')
        
        # Get notes for this appointment
        notes_text = ""
        if booking.get('notes'):
            notes_list = [note['note'] for note in booking['notes']]
            notes_text = " Notes: " + " | ".join(notes_list)
        
        booking_summaries.append(f"- {date_str}: {service}{notes_text}")
    
    # Create prompt for AI
    prompt = f"""Create a brief, natural-sounding summary of this client's history with our trades business.

Client name: {first_name}
Total jobs: {len(bookings)}

Job history (oldest to newest):
{chr(10).join(booking_summaries)}

Write a 2-3 sentence summary. Mention the APPOINTMENT DATE (not today's date) for each job.
Keep it concise and natural. Use "they/their" pronouns. Focus on what work was done and when."""

    response = client_openai.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[
            {
                "role": "system", 
                "content": "You are a receptionist writing brief client history summaries for a trades business. Write naturally and conversationally. Use the appointment dates from the job history, NOT today's date."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        **config.max_tokens_param(value=150)
    )
    
    description = response.choices[0].message.content.strip()
    print(f"✅ AI-generated description for {first_name}")
    return description


def _generate_template_description(client: Dict, bookings: List[Dict]) -> str:
    """
    Template-based description generation (fallback when AI is unavailable)
    """
    # Get first and last visits
    first_booking = bookings[-1]  # Oldest (last in the list)
    last_booking = bookings[0]    # Most recent (first in the list)
    total_visits = len(bookings)
    
    # Extract name parts
    name_parts = client['name'].split()
    first_name = name_parts[0].capitalize()
    
    # Get service types (reasons for visits)
    service_types = []
    for booking in bookings:
        service = booking.get('service_type', 'general appointment')
        if service and service.lower() not in ['general', 'appointment', 'n/a']:
            service_types.append(service.lower())
    
    # Remove duplicates while preserving order
    unique_services = []
    seen = set()
    for service in service_types:
        if service not in seen:
            unique_services.append(service)
            seen.add(service)
    
    # Format dates
    first_visit_date = format_date_short(first_booking['appointment_time'])
    last_visit_date = format_date_short(last_booking['appointment_time'])
    
    # Build description
    description_parts = []
    
    # First visit information
    first_service = unique_services[0] if unique_services else "general appointment"
    resolution_status = "that is now resolved" if total_visits > 5 else "which has improved significantly"
    
    description_parts.append(
        f"When {first_name} first came in on {first_visit_date}, they had a {first_service}, {resolution_status}."
    )
    
    # Middle visits summary
    if total_visits > 1:
        other_services = unique_services[1:] if len(unique_services) > 1 else []
        
        if other_services:
            if len(other_services) == 1:
                services_text = f"a {other_services[0]}"
            elif len(other_services) == 2:
                services_text = f"a {other_services[0]} and a {other_services[1]}"
            else:
                services_text = f"{', '.join(['a ' + s for s in other_services[:-1]])} and a {other_services[-1]}"
            
            description_parts.append(
                f"Since then, they have been in {total_visits} times with {services_text}."
            )
        else:
            description_parts.append(
                f"Since then, they have been in {total_visits} times."
            )
    
    # Last visit information
    last_service = unique_services[-1] if unique_services else "general issue"
    last_service_clean = last_service.replace("injury", "").replace("pain", "").strip()
    if last_service_clean:
        description_parts.append(
            f"Their last visit on {last_visit_date}, their {last_service_clean} was hurting."
        )
    else:
        description_parts.append(
            f"Their last visit was on {last_visit_date}."
        )
    
    return " ".join(description_parts)


# Keep the old function for backward compatibility
def generate_client_description(client_id: int, company_id: int = None) -> Optional[str]:
    """
    Generate an AI-style description for a client based on their booking history
    
    This now uses AI generation by default (GPT-4o-mini).
    Falls back to template-based generation if AI fails.
    
    Args:
        client_id: The ID of the client
        company_id: Optional company ID for multi-tenant data isolation
        
    Returns:
        Generated description string or None if no bookings
    """
    return generate_client_description_from_notes(client_id, use_ai=True, company_id=company_id)


def update_client_description(client_id: int, company_id: int = None) -> bool:
    """
    Generate and update a client's description using AI
    
    Args:
        client_id: The ID of the client
        company_id: Optional company ID for multi-tenant data isolation
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\\n{'='*60}")
        print(f"🤖 Starting description update for client {client_id}" + (f" (company_id: {company_id})" if company_id else ""))
        print(f"{'='*60}")
        
        description = generate_client_description(client_id, company_id=company_id)
        if description:
            print(f"✅ Generated description ({len(description)} chars)")
            print(f"📝 Preview: {description[:100]}...")
            
            from src.services.database import get_database
            db = get_database()
            db.update_client_description(client_id, description, company_id=company_id)
            print(f"💾 Saved to database for client {client_id}")
            print(f"{'='*60}\\n")
            return True
        else:
            print(f"⚠️ No description generated (possibly no bookings)")
            print(f"{'='*60}\\n")
            return False
    except Exception as e:
        print(f"❌ Error updating description for client {client_id}: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\\n")
        return False


def update_all_client_descriptions(company_id: int = None) -> int:
    """
    Update descriptions for all clients who have bookings
    
    Args:
        company_id: Optional company ID to filter clients (for multi-tenant isolation)
    
    Returns:
        Number of descriptions updated
    """
    from src.services.database import get_database
    db = get_database()
    # MUST filter by company_id for proper multi-tenant data isolation
    all_clients = db.get_all_clients(company_id=company_id)
    
    updated_count = 0
    for client in all_clients:
        if update_client_description(client['id'], company_id=company_id):
            updated_count += 1
    
    print(f"\n✅ Updated {updated_count} client descriptions" + (f" for company {company_id}" if company_id else ""))
    return updated_count

