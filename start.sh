#!/bin/bash
# Render.com startup script

echo "🚀 Starting AI Receptionist Backend..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL is required"
    exit 1
else
    echo "✅ Using PostgreSQL database"
fi

# Check if R2 is configured
if [ -z "$R2_ACCOUNT_ID" ]; then
    echo "⚠️  R2 storage not configured (optional)"
else
    echo "✅ R2 storage configured"
fi

# Decode Google credentials if provided as base64
if [ ! -z "$GOOGLE_CREDENTIALS_BASE64" ]; then
    echo "📄 Decoding Google credentials..."
    mkdir -p config
    echo "$GOOGLE_CREDENTIALS_BASE64" | base64 -d > config/credentials.json
    echo "✅ Google credentials decoded"
fi

# Run database migrations (tables will be created automatically)
echo "🗄️  Initializing database..."

# Start the Flask application
echo "🎬 Starting Flask server..."
exec python src/app.py
