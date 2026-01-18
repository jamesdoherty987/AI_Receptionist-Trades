# AI Receptionist Dashboard

## 🎯 Professional Web Interface

A modern, professional dashboard for managing your AI Receptionist system with two main tabs:

### 👥 Client Management Tab
- **Client Database**: View all clients with contact info and appointment history
- **Client Details**: Click any client to see full profile, appointments, and notes
- **Add Notes**: Document interactions, preferences, and important information
- **Search & Filter**: Quickly find clients
- **Recent Bookings**: Track all appointments in one place

### ⚙️ Developer Tools Tab
- **Test Runner**: Run automated tests with one click
- **Chat Interface**: Test receptionist responses via text
- **System Monitoring**: View test results and debug information

## 🚀 Setup

### 1. Initialize the Dashboard

```bash
python scripts/init_dashboard.py
```

This creates:
- SQLite database at `data/receptionist.db`
- Required directories
- Database schema

### 2. Start the Server

```bash
python src/app.py
```

### 3. Open Dashboard

Navigate to: **http://localhost:5000**

## 📊 Features

### Automatic Client Tracking
When someone books an appointment via phone:
1. ✅ System captures their name and phone number
2. ✅ Creates/updates client record in database
3. ✅ Saves booking with all details
4. ✅ Tracks appointment count and visit history
5. ✅ Available immediately in dashboard

### Client Management
- **View all clients** with sorting and filtering
- **Click to see details**:
  - Contact information
  - Complete appointment history
  - Custom notes and interactions
  - First visit & last visit dates
  - Total appointment count

### Add Notes
Document anything about a client:
- Medical history
- Preferences
- Follow-up actions
- Special requirements
- Staff observations

### Developer Tools
- **Run Tests**: Execute test suite with button click
- **View Results**: See detailed test output
- **Chat Simulation**: Test conversation flow via text interface

## 🎨 Design

- Modern, clean interface
- Responsive layout
- Professional color scheme
- Easy navigation with tabs
- Modal dialogs for actions
- Real-time data updates

## 📱 Mobile Friendly

The dashboard is fully responsive and works on:
- Desktop computers
- Tablets
- Mobile phones

## 🔐 Data Storage

### Database Schema

**clients table**:
- id, name, phone, email
- first_visit, last_visit
- total_appointments
- created_at, updated_at

**bookings table**:
- id, client_id, calendar_event_id
- appointment_time, service_type, status
- phone_number, email
- created_at

**notes table**:
- id, client_id, note
- created_by, created_at

**call_logs table**:
- id, phone_number
- duration_seconds, summary
- created_at

### Database Location
`data/receptionist.db` (SQLite)

## 🔌 API Endpoints

### Client Management
- `GET /api/clients` - List all clients
- `POST /api/clients` - Create new client
- `GET /api/clients/:id` - Get client details
- `PUT /api/clients/:id` - Update client
- `POST /api/clients/:id/notes` - Add note

### Bookings
- `GET /api/bookings` - List all bookings

### Statistics
- `GET /api/stats` - Dashboard stats

### Developer Tools
- `POST /api/tests/run` - Run test suite

## 🛠️ File Structure

```
src/
├── app.py                        # Flask server with API endpoints
├── services/
│   └── database.py              # Database models and queries
└── static/
    ├── dashboard.html           # Main dashboard UI
    └── dashboard.js             # Frontend JavaScript

data/
└── receptionist.db              # SQLite database

scripts/
└── init_dashboard.py            # Setup script
```

## 📖 Usage Examples

### View Client History
1. Open dashboard
2. Go to "Client Management" tab
3. Click "View" on any client
4. See complete appointment history and notes

### Add Note to Client
1. Open client details
2. Click "Add Note"
3. Type note and click "Save"
4. Note appears with timestamp and your name

### Run Tests
1. Go to "Developer Tools" tab
2. Click "Run All Tests" or specific test
3. View results in output box

### Manual Client Entry
1. Click "+ Add Client" button
2. Fill in name, phone, email
3. Click "Add Client"
4. Client appears in list

## 🔄 Integration

The dashboard automatically integrates with:
- ✅ Phone booking system (via LLM stream)
- ✅ Google Calendar (synced)
- ✅ Email reminder system
- ✅ Call logging

When someone books via phone, everything is saved automatically!

## 🎯 Use Cases

### For Receptionists
- Quickly lookup client info during calls
- Add notes about preferences
- View appointment history
- Track no-shows and cancellations

### For Managers
- Monitor total clients and bookings
- Track business metrics
- Review appointment patterns
- Analyze client retention

### For Developers
- Test system functionality
- Debug issues
- Simulate conversations
- Run automated tests

## 🚀 Next Steps

Want to enhance the dashboard? Easy additions:

1. **Export Data**: Add CSV export for clients/bookings
2. **Analytics**: Charts showing bookings over time
3. **SMS from Dashboard**: Send manual reminders
4. **Calendar View**: Visual calendar of appointments
5. **Search**: Advanced filtering and search
6. **Reports**: Generate monthly summaries

## 💡 Tips

- Dashboard updates automatically when bookings are made
- Notes support markdown formatting
- Test runner shows real-time output
- Client phone numbers are automatically linked
- Database is backed up with every booking

## 🐛 Troubleshooting

**Dashboard won't load?**
- Check Flask server is running: `python src/app.py`
- Verify port 5000 is not in use

**No clients showing?**
- Make a test booking via phone first
- Or manually add a client via "+ Add Client"

**Tests failing?**
- Check all dependencies installed
- Run: `pip install -r requirements.txt`

**Database errors?**
- Delete `data/receptionist.db`
- Run: `python scripts/init_dashboard.py`

## ✨ Summary

You now have a **professional, production-ready dashboard** that:
- ✅ Tracks all clients automatically
- ✅ Shows complete appointment history
- ✅ Allows custom notes on each client
- ✅ Provides developer tools for testing
- ✅ Modern, responsive design
- ✅ Real-time data sync

**Enjoy your new AI Receptionist Dashboard!** 🎉
