@echo off
echo ========================================
echo   Asset Lifecycle Management System
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python...
python --version
if errorlevel 1 (
    echo Python not found! Please install Python first.
    pause
    exit /b 1
)

echo.
echo Installing dependencies (first time only)...
python -m pip install -r requirements.txt --quiet

echo.
echo Starting the application...
echo.
echo The app will open in your browser at: http://localhost:8501
echo Press Ctrl+C in this window to stop the app.
echo.

streamlit run app.py --server.headless=true

pause
