@echo off
echo Building React frontend for production...
cd frontend
call npm run build
cd ..
echo.
echo Frontend built successfully!
echo Build files are in: src/static/dist/
echo.
pause
