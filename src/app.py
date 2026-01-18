"""
Flask application for Twilio voice webhook
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, Response, request, jsonify, send_from_directory
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
from src.utils.config import config
from src.services.database import get_database
from src.services.google_calendar import GoogleCalendarService

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))

# Start auto-complete scheduler on app startup
print("\\n🚀 Starting appointment auto-complete scheduler...")
try:
    from src.services.appointment_auto_complete import start_auto_complete_scheduler
    start_auto_complete_scheduler(interval_minutes=60)  # Check every hour
    print("✅ Auto-complete scheduler started successfully\\n")
except Exception as e:
    print(f"⚠️  Warning: Could not start auto-complete scheduler: {e}\\n")


@app.route("/twilio/voice", methods=["POST"])
def twilio_voice():
    """
    Twilio voice webhook endpoint
    Returns TwiML to connect call to media stream
    """
    ws_url = config.WS_PUBLIC_URL
    
    # Extract caller phone number from Twilio request
    caller_phone = request.form.get("From", "")

    twiml = VoiceResponse()
    with twiml.connect() as connect:
        stream = connect.stream(url=ws_url)
        # Pass caller phone as custom parameter
        if caller_phone:
            stream.parameter(name="From", value=caller_phone)

    print("=" * 60)
    print("📞 Incoming Twilio Call")
    print(f"📱 Caller: {caller_phone}")
    print(f"WS_PUBLIC_URL: {ws_url}")
    print("=" * 60)
    
    return Response(str(twiml), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "AI Receptionist"}


@app.route("/twilio/sms", methods=["POST"])
def twilio_sms():
    """
    Handle incoming SMS messages (for appointment confirmations/cancellations)
    Only active if REMINDER_METHOD=sms in .env
    """
    try:
        # Check if SMS reminders are enabled
        if config.REMINDER_METHOD.lower() != "sms":
            print("⚠️ SMS webhook called but REMINDER_METHOD is not 'sms'. Ignoring.")
            resp = MessagingResponse()
            resp.message("Please contact us by phone for appointment inquiries.")
            return Response(str(resp), mimetype="text/xml")
        
        # Get message details
        from_number = request.form.get('From', '')
        message_body = request.form.get('Body', '').strip().upper()
        
        print(f"\n📱 SMS received from {from_number}: {message_body}")
        
        # Create response
        resp = MessagingResponse()
        
        if 'YES' in message_body or 'CONFIRM' in message_body:
            # User confirmed the appointment
            reply = "Thank you! Your appointment is confirmed. We look forward to seeing you!"
            resp.message(reply)
            print(f"✅ Appointment confirmed by {from_number}")
            
        elif 'CANCEL' in message_body:
            # User wants to cancel - we would need event ID to actually cancel
            # For now, just acknowledge and ask them to call
            reply = "We received your cancellation request. Please call us to confirm the cancellation and reschedule if needed."
            resp.message(reply)
            print(f"⚠️ Cancellation request from {from_number}")
            
        else:
            # Unknown response
            reply = "Thank you for your message. Please reply YES to confirm or CANCEL to cancel your appointment."
            resp.message(reply)
        
        return Response(str(resp), mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ Error handling SMS: {e}")
        resp = MessagingResponse()
        resp.message("Sorry, we encountered an error processing your message. Please call us directly.")
        return Response(str(resp), mimetype="text/xml")


# Dashboard and API endpoints
from flask import redirect
@app.route("/")
def dashboard():
    """Serve the dashboard"""
    return send_from_directory('static', 'dashboard.html')


# Redirect /dashboard to /
@app.route("/dashboard")
def dashboard_redirect():
    return redirect("/", code=302)


@app.route("/settings")
def settings_page():
    """Serve the business settings page"""
    return send_from_directory('static', 'settings.html')


@app.route("/settings/developer")
def developer_settings_page():
    """Serve the developer settings page"""
    return send_from_directory('static', 'settings_developer.html')


@app.route("/api/settings/business", methods=["GET", "POST"])
def business_settings_api():
    """Get or update business settings"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    
    if request.method == "GET":
        settings = settings_mgr.get_business_settings()
        return jsonify(settings)
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_business_settings(data, user_id=None)
        if success:
            return jsonify({"message": "Business settings updated successfully"})
        return jsonify({"error": "Failed to update settings"}), 500


@app.route("/api/settings/developer", methods=["GET", "POST"])
def developer_settings_api():
    """Get or update developer settings"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    
    if request.method == "GET":
        settings = settings_mgr.get_developer_settings()
        return jsonify(settings)
    
    elif request.method == "POST":
        data = request.json
        success = settings_mgr.update_developer_settings(data, user_id=None)
        if success:
            return jsonify({"message": "Developer settings updated successfully"})
        return jsonify({"error": "Failed to update settings"}), 500


@app.route("/api/settings/history", methods=["GET"])
def settings_history_api():
    """Get settings change history"""
    from src.services.settings_manager import get_settings_manager
    settings_mgr = get_settings_manager()
    
    limit = request.args.get('limit', 50, type=int)
    history = settings_mgr.get_settings_history(limit)
    return jsonify(history)


@app.route("/api/clients", methods=["GET", "POST"])
def clients_api():
    """Get all clients or create a new client"""
    db = get_database()
    
    if request.method == "GET":
        clients = db.get_all_clients()
        return jsonify(clients)
    
    elif request.method == "POST":
        data = request.json
        client_id = db.add_client(
            name=data['name'],
            phone=data.get('phone'),
            email=data.get('email')
        )
        return jsonify({"id": client_id, "message": "Client created"}), 201


@app.route("/api/clients/<int:client_id>", methods=["GET", "PUT"])
def client_api(client_id):
    """Get or update a specific client"""
    db = get_database()
    
    if request.method == "GET":
        client = db.get_client(client_id)
        if client:
            # Get bookings and notes
            bookings = db.get_client_bookings(client_id)
            notes = db.get_client_notes(client_id)
            client['bookings'] = bookings
            client['notes'] = notes
            return jsonify(client)
        return jsonify({"error": "Client not found"}), 404
    
    elif request.method == "PUT":
        data = request.json
        db.update_client(client_id, **data)
        return jsonify({"message": "Client updated"})


@app.route("/api/clients/<int:client_id>/notes", methods=["POST"])
def add_note_api(client_id):
    """Add a note to a client"""
    db = get_database()
    data = request.json
    
    note_id = db.add_note(
        client_id=client_id,
        note=data['note'],
        created_by=data.get('created_by', 'user')
    )
    return jsonify({"id": note_id, "message": "Note added"}), 201


@app.route("/api/bookings/<int:booking_id>/notes", methods=["GET", "POST"])
def appointment_notes_api(booking_id):
    """Get or add notes for a specific appointment"""
    db = get_database()
    
    if request.method == "GET":
        notes = db.get_appointment_notes(booking_id)
        return jsonify(notes)
    
    elif request.method == "POST":
        # Get booking to find client_id for description update
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT client_id FROM bookings WHERE id = ?", (booking_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"error": "Booking not found"}), 404
        
        client_id = row[0]
        
        data = request.json
        note_id = db.add_appointment_note(
            booking_id=booking_id,
            note=data['note'],
            created_by=data.get('created_by', 'user')
        )
        
        # Update client description after adding note
        print(f"\n🔄 Updating client description for client_id: {client_id} after adding note...")
        try:
            from src.services.client_description_generator import update_client_description
            success = update_client_description(client_id)
            if success:
                print(f"✅ Successfully updated description for client {client_id}")
            else:
                print(f"⚠️ Description update returned False for client {client_id}")
        except Exception as e:
            print(f"❌ ERROR updating description for client {client_id}: {e}")
            import traceback
            traceback.print_exc()
        
        return jsonify({"id": note_id, "message": "Appointment note added"}), 201


@app.route("/api/bookings/<int:booking_id>/notes/<int:note_id>", methods=["PUT", "DELETE"])
def appointment_note_api(booking_id, note_id):
    """Update or delete a specific appointment note"""
    db = get_database()
    
    # Get client_id for description update
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT client_id FROM bookings WHERE id = ?", (booking_id,))
    result = cursor.fetchone()
    conn.close()
    client_id = result[0] if result else None
    
    if request.method == "PUT":
        data = request.json
        success = db.update_appointment_note(note_id, data['note'])
        if success:
            # Update client description after editing note
            if client_id:
                print(f"\n🔄 Updating client description for client_id: {client_id} after editing note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id)
                    if success:
                        print(f"✅ Successfully updated description for client {client_id}")
                    else:
                        print(f"⚠️ Description update returned False for client {client_id}")
                except Exception as e:
                    print(f"❌ ERROR updating description: {e}")
                    import traceback
                    traceback.print_exc()
            return jsonify({"message": "Note updated"})
        return jsonify({"error": "Note not found"}), 404
    
    elif request.method == "DELETE":
        success = db.delete_appointment_note(note_id)
        if success:
            # Update client description after deleting note
            if client_id:
                print(f"\n🔄 Updating client description for client_id: {client_id} after deleting note...")
                try:
                    from src.services.client_description_generator import update_client_description
                    success = update_client_description(client_id)
                    if success:
                        print(f"✅ Successfully updated description for client {client_id}")
                    else:
                        print(f"⚠️ Description update returned False for client {client_id}")
                except Exception as e:
                    print(f"❌ ERROR updating description: {e}")
                    import traceback
                    traceback.print_exc()
            return jsonify({"message": "Note deleted"})
        return jsonify({"error": "Note not found"}), 404


@app.route("/api/bookings", methods=["GET"])
def bookings_api():
    """Get all bookings"""
    db = get_database()
    bookings = db.get_all_bookings()
    return jsonify(bookings)


@app.route("/api/bookings/<int:booking_id>", methods=["PUT"])
def update_booking_api(booking_id):
    """Update booking (including charge and payment info)"""
    db = get_database()
    data = request.json
    success = db.update_booking(booking_id, **data)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to update booking"}), 400


@app.route("/api/bookings/<int:booking_id>/complete", methods=["POST"])
def complete_booking_api(booking_id):
    """Mark appointment as complete and update client description using AI"""
    db = get_database()
    
    # Get the booking to find the client
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT client_id, status FROM bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Booking not found"}), 404
    
    client_id, current_status = row
    
    # Update booking status to completed
    db.update_booking(booking_id, status='completed')
    
    # Generate/update client description using AI based on all appointments and notes
    try:
        from src.services.client_description_generator import update_client_description
        success = update_client_description(client_id)
        
        if success:
            # Get the updated client info with new description
            client = db.get_client(client_id)
            return jsonify({
                "success": True,
                "message": "Appointment completed and description updated",
                "description": client.get('description')
            })
        else:
            return jsonify({
                "success": True,
                "message": "Appointment completed (no description generated)",
                "description": None
            })
    except Exception as e:
        print(f"❌ Error updating description: {e}")
        return jsonify({
            "success": True,
            "message": "Appointment completed but description update failed",
            "error": str(e)
        }), 500


@app.route("/api/appointments/auto-complete", methods=["POST"])
def auto_complete_appointments():
    """Manually trigger auto-completion of overdue appointments"""
    try:
        from src.services.appointment_auto_complete import auto_complete_overdue_appointments
        count = auto_complete_overdue_appointments()
        return jsonify({
            "success": True,
            "message": f"Auto-completed {count} appointment(s)",
            "count": count
        })
    except Exception as e:
        print(f"❌ Error in auto-complete: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/finances/stats", methods=["GET"])
def financial_stats_api():
    """Get financial statistics"""
    db = get_database()
    stats = db.get_financial_stats()
    return jsonify(stats)


@app.route("/api/stats", methods=["GET"])
def stats_api():
    """Get dashboard statistics"""
    db = get_database()
    calendar = GoogleCalendarService()
    
    clients = db.get_all_clients()
    bookings = db.get_all_bookings()
    upcoming = calendar.get_upcoming_appointments(days_ahead=7)
    
    stats = {
        "total_clients": len(clients),
        "total_bookings": len(bookings),
        "upcoming_appointments": len(upcoming),
        "recent_clients": clients[:5] if clients else []
    }
    
    return jsonify(stats)


@app.route("/api/config", methods=["GET"])
def config_api():
    """Get application configuration for frontend"""
    return jsonify({
        "default_charge": config.DEFAULT_APPOINTMENT_CHARGE,
        "currency": "EUR",
        "business_hours": {
            "start": config.BUSINESS_HOURS_START,
            "end": config.BUSINESS_HOURS_END
        },
        "timezone": config.CALENDAR_TIMEZONE,
        "notification_poll_interval": config.NOTIFICATION_POLL_INTERVAL,
        "max_booking_days_ahead": config.MAX_BOOKING_DAYS_AHEAD,
        "appointment_slot_duration": config.APPOINTMENT_SLOT_DURATION
    })


@app.route("/api/workers", methods=["GET", "POST"])
def workers_api():
    """Get all workers or create a new worker"""
    db = get_database()
    
    if request.method == "GET":
        workers = db.get_all_workers()
        return jsonify(workers)
    
    elif request.method == "POST":
        data = request.json
        worker_id = db.add_worker(
            name=data['name'],
            phone=data.get('phone'),
            email=data.get('email'),
            trade_specialty=data.get('trade_specialty')
        )
        return jsonify({"id": worker_id, "message": "Worker added"}), 201


@app.route("/api/workers/<int:worker_id>", methods=["GET", "PUT", "DELETE"])
def worker_api(worker_id):
    """Get, update or delete a specific worker"""
    db = get_database()
    
    if request.method == "GET":
        worker = db.get_worker(worker_id)
        if worker:
            return jsonify(worker)
        return jsonify({"error": "Worker not found"}), 404
    
    elif request.method == "PUT":
        data = request.json
        db.update_worker(worker_id, **data)
        return jsonify({"message": "Worker updated"})
    
    elif request.method == "DELETE":
        success = db.delete_worker(worker_id)
        if success:
            return jsonify({"message": "Worker deleted"})
        return jsonify({"error": "Worker not found"}), 404


@app.route("/api/email/test", methods=["POST"])
def send_test_email():
    """Send a test email"""
    try:
        # This is a placeholder for email functionality
        # You can integrate with services like SendGrid, AWS SES, or SMTP
        return jsonify({
            "success": True,
            "message": "Test email sent successfully (placeholder)"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/config/business_info.json", methods=["GET"])
def business_info_api():
    """Serve business info configuration"""
    import os
    import json
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'business_info.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    return jsonify(config)


@app.route("/api/tests/run", methods=["POST"])
def run_tests():
    """Run test suite"""
    import subprocess
    data = request.json
    test_type = data.get('test_type', 'all')
    
    try:
        # Set environment variable to use UTF-8 encoding for subprocess
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        if test_type == 'datetime':
            result = subprocess.run(
                [sys.executable, 'tests/test_datetime_parser.py'], 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                timeout=10,
                env=env
            )
        else:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/', '-v'], 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                timeout=30,
                env=env
            )
        
        return jsonify({
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr
        })
    except Exception as e:
        return jsonify({"success": False, "output": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat with the AI receptionist"""
    import asyncio
    from src.services.llm_stream import stream_llm, process_appointment_with_calendar
    
    data = request.json
    user_message = data.get('message', '')
    conversation = data.get('conversation', [])
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    # Add user message to conversation
    conversation.append({"role": "user", "content": user_message})
    
    # Add web chat context to first message (minimal differences from phone mode)
    if len(conversation) == 1:
        # Use the same system prompt as phone calls, just add web-specific notes
        web_instructions = {
            "role": "system",
            "content": """[WEB CHAT MODE NOTES:
- You are handling a web chat, NOT a phone call
- DO NOT say things like "calling number" or "I have your number from the call"
- Use slightly longer responses (2-3 sentences OK for web chat)
- Phone number is OPTIONAL for web chat - can book without it if they provide name, date/time, and reason
- All other rules from the main system prompt apply exactly the same]"""
        }
        conversation.insert(0, web_instructions)
    
    # Get response from LLM
    async def get_response():
        response_text = ""
        try:
            # Don't pass caller_phone since this is web chat
            async for token in stream_llm(conversation, process_appointment_with_calendar, caller_phone=None):
                response_text += token
            return response_text
        except Exception as e:
            return f"Error: {str(e)}"
    
    # Run async function
    try:
        response = asyncio.run(get_response())
        conversation.append({"role": "assistant", "content": response})
        return jsonify({
            "response": response,
            "conversation": conversation
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/reset", methods=["POST"])
def chat_reset():
    """Reset chat conversation state"""
    from src.services.llm_stream import reset_appointment_state
    reset_appointment_state()
    return jsonify({"message": "Chat state reset"})


if __name__ == "__main__":
    try:
        config.validate()
        print("✅ Configuration validated")
        print(f"🚀 Starting Flask server on port {config.PORT}")
        app.run(port=config.PORT, debug=(config.FLASK_ENV == "development"), use_reloader=False)
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        exit(1)
