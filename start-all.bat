@echo off
echo Starting Face Attended - Unified System Control
echo ==================================================
echo.

:: Start backend server
echo [1/4] Starting Backend Server (port 8700)...
start "Backend Server" cmd /k "cd /d %~dp0server && python main.py"

:: Wait a moment for backend to start
timeout /t 3 /nobreak > nul

:: Start Cloudflare named tunnel
echo [2/4] Starting Cloudflare Tunnel for API...
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel run bbfa-backend"

:: Start BBFA Panel
echo [3/4] Starting BBFA Panel (port 3002)...
start "BBFA Panel" cmd /k "cd /d %~dp0panel && pnpm dev"

:: Start Superadmin Panel
echo [4/4] Starting Superadmin Panel (port 3003)...
start "Superadmin Panel" cmd /k "cd /d %~dp0superadmin && npm run dev"

echo.
echo ==================================================
echo All services started!
echo.
echo BBFA Class Panel:        http://localhost:3002
echo Superadmin Dashboard:    http://localhost:3003
echo Backend API (Local):     http://localhost:8700
echo.
echo *** PUBLIC ACCESS ***
echo Backend API: https://api.chetancj.in
echo ==================================================
pause
