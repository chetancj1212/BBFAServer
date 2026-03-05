@echo off
echo ==========================================
echo Starting Face Attended Backend Server...
echo ==========================================

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

echo [INFO] Starting the server...
python main.py

echo.
echo Server has stopped.
pause
