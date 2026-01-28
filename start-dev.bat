@echo off
echo Starting Development Servers...
echo.

REM Start Flask backend in a new window
start "Flask Backend" cmd /k "cd /d %~dp0 && venv\Scripts\activate && python src/app.py"

REM Wait a moment for Flask to start
timeout /t 2 /nobreak >nul

REM Start Vite frontend in a new window
start "Vite Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Development servers are starting...
echo.
echo Flask Backend: http://localhost:5000
echo Vite Frontend: http://localhost:3000
echo.
echo Press any key to stop all servers...
pause >nul

REM Kill the processes
taskkill /FI "WINDOWTITLE eq Flask Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Vite Frontend*" /F >nul 2>&1

echo.
echo All servers stopped.
