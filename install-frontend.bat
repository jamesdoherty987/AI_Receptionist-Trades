@echo off
echo Installing React frontend dependencies...
cd frontend
call npm install
cd ..
echo.
echo Frontend dependencies installed successfully!
echo.
echo To start development:
echo   1. Run: npm run dev (in frontend directory)
echo   2. Run: python src/app.py (in root directory)
echo.
pause
