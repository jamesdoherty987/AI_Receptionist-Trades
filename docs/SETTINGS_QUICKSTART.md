# Quick Start: Settings Pages

## Access Settings

1. **From Dashboard:**
   - Click the "⚙️ Settings" button in the header

2. **Direct URLs:**
   - Business: `http://localhost:5000/settings`
   - Developer: `http://localhost:5000/settings/developer`

## Initialize Settings (First Time Only)

```bash
python scripts/init_settings.py
```

## Business Settings - What to Configure

### Must Configure First:
- ✅ Business name and contact info
- ✅ Opening hours and days
- ✅ Appointment pricing
- ✅ Services offered

### Optional But Recommended:
- Timezone (default: Europe/Dublin)
- Payment methods
- Cancellation policy
- Reminder timing

## Developer Settings - What to Configure

### Performance Settings:
- OpenAI model (gpt-4o-mini is recommended for cost/performance)
- Max tokens (150 is good for short responses)
- Temperature (0.7 is balanced)

### Features to Enable:
- ✅ Analytics (track usage)
- Call recording (for quality assurance)
- Debug mode (only when troubleshooting)

### Don't Touch Unless Needed:
- Max concurrent calls
- Rate limiting
- Session timeout

## Common Tasks

### Change Opening Hours
1. Go to Business Settings
2. Scroll to "Operating Hours"
3. Update start/end times (24-hour format)
4. Select days open
5. Save

### Update Pricing
1. Go to Business Settings
2. Scroll to "Services & Pricing"
3. Update default charge
4. Add/edit services
5. Save

### Enable Call Recording
1. Go to Developer Settings
2. Scroll to "Features & Toggles"
3. Check "Enable Call Recording"
4. Save

### Set Maintenance Mode
1. Go to Developer Settings
2. Scroll to "Danger Zone"
3. Check "Enable Maintenance Mode"
4. Enter custom message
5. Save

## Keyboard Shortcuts

- `Tab` - Navigate between fields
- `Enter` - Submit form
- `Esc` - Close notifications

## Tips

- Settings are saved to SQLite database
- Changes take effect immediately
- All changes are logged in settings history
- Use Developer Settings cautiously - they affect core functionality
- Test major changes in development first

## Troubleshooting

**Settings won't save:**
```bash
# Re-initialize database
python scripts/init_settings.py
```

**Can't access settings page:**
```bash
# Make sure Flask is running
python src/app.py
```

**Testing settings:**
```bash
# Run test suite
python scripts/test_settings.py
```

## Navigation

From either settings page:
- **← Back to Dashboard** - Return to main dashboard
- **Business Settings →** - Switch to business settings
- **Developer Settings →** - Switch to developer settings

## Best Practices

1. **Regular Backups:**
   - Settings stored in `data/receptionist.db`
   - Back up before major changes

2. **Test Changes:**
   - Make one change at a time
   - Test thoroughly before production use

3. **Document Changes:**
   - Settings history tracks all changes
   - Add notes for significant updates

4. **Security:**
   - Keep developer settings access restricted
   - Don't share webhook secrets
   - Use maintenance mode during updates
