@echo off
:: ============================================================
:: BBFA — Docker + Cloudflare Tunnel Start Script
:: ============================================================
:: This script starts the Dockerized BBFA Server and then 
:: tunnels it to api.chetancj.in via Cloudflare.
::
:: Re-Requirement: cloudflared must be installed on this PC.
:: ============================================================

echo ==============================================
echo   BBFA — Docker + Cloudflare Tunnel
echo ==============================================
echo.

:: 1. Check if Docker is running
docker ps >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)

:: 2. Check if cloudflared is installed
cloudflared --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] cloudflared is not installed. 
    echo Please install it from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/install-run/
    pause
    exit /b 1
)

:: 3. Start the Dockerized server
echo [1/2] Starting BBFA Server Container...
:: We assume the container is already built or loaded from .tar
docker start bbfa-server >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Container not found. Attempting to run from image...
    docker run -d --name bbfa-server -p 8700:8700 -v bbfa-data:/app/data bbfa-server
)
echo [OK] Server is starting on port 8700.

:: 4. Wait a few seconds
timeout /t 3 /nobreak > nul

:: 5. Start the Cloudflare Tunnel
echo [2/2] Starting Cloudflare Tunnel (api.chetancj.in)...
echo.
echo Press Ctrl+C to stop the tunnel.
echo.
:: Using the existing tunnel configuration 'bbfa-backend'
cloudflared tunnel run bbfa-backend

echo.
echo ==============================================
echo   Tunnel Stopped.
echo ==============================================
pause
