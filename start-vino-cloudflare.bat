@echo off
echo Starting Backend + Cloudflare Tunnel
echo ==================================================
echo.

:: Start backend server
echo [1/2] Starting Backend Server (port 8700)...
start "Backend Server" cmd /k "cd /d %~dp0server-vino && python main.py"

:: Wait for backend to start
timeout /t 3 /nobreak > nul

:: Start Cloudflare named tunnel (permanent URL)
echo [2/2] Starting Cloudflare Tunnel for Backend API...
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel run bbfa-backend"

echo.
echo ==================================================
echo Backend is online via Cloudflare Tunnel!
echo.
echo Local API:  http://localhost:8700
echo Public API: https://api.chetancj.in
echo.
echo Your laptop must stay on for the API to be reachable.
echo ==================================================
pause
