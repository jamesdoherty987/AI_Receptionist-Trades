# Settings Pages Documentation

## Overview

The AI Receptionist now includes two comprehensive settings pages:

1. **Business Settings** (`/settings`) - For clinic/practice managers, physiotherapists, and doctors
2. **Developer Settings** (`/settings/developer`) - For technical administrators and developers

## Features

### Business Settings Page

Configure operational aspects of your clinic:

#### 🏢 Business Information
- Business name, type, phone, email, website
- Physical address and location details
- Contact information

#### 🕐 Operating Hours
- Timezone selection
- Business hours (24-hour format)
- Days of operation selector
- Appointment duration (minutes)
- Maximum booking days ahead
- Weekend booking toggle

#### 💰 Services & Pricing
- Currency selection (EUR, GBP, USD)
- Default appointment charge
- Services offered (dynamically add/remove)
- Payment methods accepted

#### 📅 Booking Settings
- Reminder timing (hours before appointment)
- Auto-confirm bookings toggle
- Weekend booking permissions
- Cancellation policy text

### Developer Settings Page

Configure technical and AI-related settings:

#### 🤖 AI Model Configuration
- OpenAI model selection (GPT-4o Mini, GPT-4o, etc.)
- Max tokens per response
- Temperature slider (creativity vs. determinism)

#### 🎤 Speech Services
- Deepgram ASR model selection
- TTS provider (Deepgram/ElevenLabs)
- ElevenLabs voice ID

#### 🔗 Webhooks & Integrations
- Webhook URL for external notifications
- Webhook secret for verification

#### ⚙️ System Configuration
- Log level (DEBUG, INFO, WARNING, ERROR)
- Max concurrent calls
- Session timeout (minutes)
- Rate limiting (requests per minute)

#### 🎛️ Features & Toggles
- Call recording enable/disable
- Analytics tracking
- Debug mode

#### 🚨 Danger Zone
- Maintenance mode toggle
- Custom maintenance message

## Database Schema

### Tables Created

#### `business_settings`
Stores all business operational settings including hours, pricing, services, and policies.

#### `developer_settings`
Stores technical configuration including AI models, system limits, and feature toggles.

#### `users`
User accounts for access control (future authentication support).

#### `settings_log`
Complete audit trail of all settings changes with timestamps and user tracking.

## API Endpoints

### Business Settings

**GET** `/api/settings/business`
- Returns current business settings as JSON

**POST** `/api/settings/business`
- Updates business settings
- Request body: JSON object with settings to update

### Developer Settings

**GET** `/api/settings/developer`
- Returns current developer settings as JSON

**POST** `/api/settings/developer`
- Updates developer settings
- Request body: JSON object with settings to update

### Settings History

**GET** `/api/settings/history?limit=50`
- Returns change history for all settings
- Query parameter: `limit` (default: 50)

## Usage

### Initial Setup

Run the initialization script:
```bash
python scripts/init_settings.py
```

This creates the database tables and populates default values.

### Accessing Settings Pages

1. Start the Flask server:
   ```bash
   python src/app.py
   ```

2. Open your browser:
   - Dashboard: `http://localhost:5000/`
   - Business Settings: `http://localhost:5000/settings`
   - Developer Settings: `http://localhost:5000/settings/developer`

3. Click the "⚙️ Settings" button in the dashboard header

### Making Changes

1. **Business Settings:**
   - Navigate to `/settings`
   - Update any fields
   - Click "💾 Save Settings"
   - Changes are immediately saved to database

2. **Developer Settings:**
   - Navigate to `/settings/developer`
   - Adjust technical parameters
   - Use sliders for numeric ranges
   - Click "💾 Save Developer Settings"

### Viewing Change History

All settings changes are logged in the `settings_log` table:
- Who made the change (when user system is implemented)
- What setting was changed
- Old and new values
- Timestamp of change

Access via API:
```bash
curl http://localhost:5000/api/settings/history?limit=20
```

## Security Considerations

### Current State
- No authentication required (local development)
- All settings are visible and editable

### Future Enhancements
- User authentication and authorization
- Role-based access control (RBAC):
  - **Admin**: Full access to both pages
  - **Manager**: Business settings only
  - **Developer**: Developer settings only
  - **Staff**: View-only access
- API key protection for settings endpoints
- HTTPS enforcement in production

## Testing

Test the settings system:
```bash
# Initialize settings
python scripts/init_settings.py

# Run comprehensive tests
python scripts/test_settings.py
```

## Integration with Existing System

The settings manager integrates seamlessly:

1. **Config Integration:**
   - Settings supplement existing `config.py` and `business_info.json`
   - Database settings take precedence when available
   - Fallback to environment variables if settings not found

2. **Dashboard Integration:**
   - Settings button added to dashboard header
   - Easy navigation between settings pages
   - Consistent UI/UX with existing dashboard

3. **API Consistency:**
   - Follows existing API patterns in `app.py`
   - RESTful endpoint structure
   - JSON request/response format

## Customization

### Adding New Settings

1. **Add Database Column:**
   ```python
   # In settings_manager.py, update init_settings_tables()
   cursor.execute("""
       ALTER TABLE business_settings 
       ADD COLUMN new_setting TEXT DEFAULT 'default_value'
   """)
   ```

2. **Add to HTML Form:**
   ```html
   <!-- In settings.html or settings_developer.html -->
   <div class="form-group">
       <label for="new_setting">New Setting</label>
       <input type="text" id="new_setting" name="new_setting">
   </div>
   ```

3. **Handle in JavaScript:**
   ```javascript
   // Settings will automatically be included in form submission
   ```

### Styling Customization

Both pages use CSS custom properties for easy theming:

**Business Settings:**
- Modern gradient design
- Light theme
- Consistent with main dashboard

**Developer Settings:**
- Dark terminal theme
- Monospace fonts
- Tech-focused aesthetic

## Troubleshooting

### Settings Not Saving
- Check browser console for errors
- Verify Flask server is running
- Check database file permissions

### Settings Not Loading
- Run `python scripts/init_settings.py` to recreate tables
- Check database file exists in `data/` folder
- Verify no database schema errors in console

### UI Issues
- Clear browser cache
- Check browser console for JavaScript errors
- Verify all CSS is loading correctly

## Future Enhancements

Planned improvements:

1. **Authentication System**
   - Login/logout functionality
   - Password hashing (bcrypt)
   - Session management

2. **Advanced Features**
   - Settings export/import (JSON/YAML)
   - Settings templates/presets
   - Bulk settings updates via API
   - Settings validation and constraints

3. **UI Improvements**
   - Real-time validation
   - Unsaved changes warning
   - Settings search/filter
   - Keyboard shortcuts

4. **Integration**
   - Sync settings to `.env` file
   - Update `business_info.json` automatically
   - Reload configuration without restart
   - Settings version control

5. **Notifications**
   - Email notifications on critical changes
   - Webhook triggers for settings updates
   - Slack/Discord integration

## Files Added/Modified

### New Files
- `src/services/settings_manager.py` - Core settings management
- `src/static/settings.html` - Business settings page
- `src/static/settings_developer.html` - Developer settings page
- `scripts/init_settings.py` - Database initialization
- `scripts/test_settings.py` - Testing utilities
- `docs/SETTINGS.md` - This documentation

### Modified Files
- `src/app.py` - Added settings routes and API endpoints
- `src/static/dashboard.html` - Added settings button in header
- `.gitignore` - Updated with additional exclusions

## Support

For issues or questions:
1. Check this documentation
2. Review test scripts for examples
3. Examine browser console for errors
4. Check Flask server logs
5. Verify database integrity with SQLite browser

## License

Same as parent project.
