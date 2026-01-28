# 🚀 Quick Start Guide - React Version

Your application has been converted to React! Follow these simple steps to get started.

## Step 1: Install Frontend Dependencies

Open PowerShell/Command Prompt in the project root and run:

```bash
.\install-frontend.bat
```

Or manually:
```bash
cd frontend
npm install
cd ..
```

## Step 2: Install Backend Dependencies

If you haven't already:

```bash
pip install -r requirements.txt
```

New dependency added: `flask-cors` for development support.

## Step 3: Start Development

### Option A: Automatic (Recommended)

Double-click or run:
```bash
.\start-dev.bat
```

This opens two windows:
- **Flask Backend** → http://localhost:5000
- **Vite Frontend** → http://localhost:3000

### Option B: Manual

**Terminal 1 - Backend:**
```bash
venv\Scripts\activate
python src/app.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## Step 4: Open Your Browser

Visit: **http://localhost:3000**

You'll see your AI Receptionist dashboard with the modern React interface!

## Step 5: Build for Production (When Ready)

```bash
.\build-frontend.bat
```

Or manually:
```bash
cd frontend
npm run build
cd ..
```

Then start Flask normally:
```bash
python src/app.py
```

Flask will automatically serve the built React app from http://localhost:5000

---

## 📁 What Changed?

**Before:**
- HTML files in `src/static/`
- Vanilla JavaScript

**After:**
- React components in `frontend/src/`
- Modern component-based architecture
- All features enhanced and improved

## 🎯 All Your Features Still Work!

✅ Dashboard with jobs, customers, workers
✅ Business settings
✅ Services menu configuration
✅ Developer settings
✅ AI receptionist toggle
✅ Calendar integration
✅ AI chat assistant
✅ All Twilio webhooks
✅ All API endpoints

## 💡 Tips

- **Development:** Use http://localhost:3000 for instant hot reload
- **Production:** Use http://localhost:5000 after building
- **Debugging:** Check both terminal windows for errors
- **Changes:** Edit files in `frontend/src/` and see instant updates

## 🆘 Troubleshooting

**"npm: command not found"**
→ Install Node.js from https://nodejs.org/

**"Port 3000 already in use"**
→ Close other apps using port 3000, or edit `frontend/vite.config.js`

**"CORS errors"**
→ Make sure both servers are running and flask-cors is installed

**"Module not found"**
→ Run `cd frontend && npm install`

## 📖 Learn More

- Read `REACT_MIGRATION.md` for full details
- Read `MIGRATION_SUMMARY.md` for what changed
- Read `frontend/README.md` for frontend docs

---

**That's it! You're ready to go! 🎉**

Questions? Check the documentation files or the code comments.
