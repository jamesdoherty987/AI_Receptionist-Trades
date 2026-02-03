# Render.com startup script for Windows-style line endings

Write-Host "🚀 Starting AI Receptionist Backend..."

# Check if DATABASE_URL is set
if (-not $env:DATABASE_URL) {
    Write-Host "⚠️  WARNING: DATABASE_URL not set, using SQLite"
} else {
    Write-Host "✅ Using PostgreSQL database"
}

# Check if R2 is configured
if (-not $env:R2_ACCOUNT_ID) {
    Write-Host "⚠️  R2 storage not configured (optional)"
} else {
    Write-Host "✅ R2 storage configured"
}

# Decode Google credentials if provided as base64
if ($env:GOOGLE_CREDENTIALS_BASE64) {
    Write-Host "📄 Decoding Google credentials..."
    New-Item -ItemType Directory -Force -Path config | Out-Null
    $bytes = [System.Convert]::FromBase64String($env:GOOGLE_CREDENTIALS_BASE64)
    [System.IO.File]::WriteAllBytes("config/credentials.json", $bytes)
    Write-Host "✅ Google credentials decoded"
}

# Start the Flask application
Write-Host "🎬 Starting Flask server..."
python src/app.py
