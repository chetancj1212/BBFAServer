@echo off
:: ============================================================
:: BBFA Server — Setup Script (Windows)
:: ============================================================
:: Run this on any Windows system with Docker Desktop installed.
:: ============================================================

echo ==============================================
echo   BBFA Server — Setup
echo ==============================================
echo.

:: ── Check Docker ──
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker is not installed.
    echo    Install it from: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)
echo [OK] Docker found.

:: ── Check Git ──
git --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git is not installed.
    echo    Install it from: https://git-scm.com/downloads
    pause
    exit /b 1
)
echo [OK] Git found.

echo.

:: ── Clone repo ──
set REPO_URL=https://github.com/chetancj1212/BBFAServer.git
set INSTALL_DIR=BBFAServer

if exist "%INSTALL_DIR%" (
    echo Directory '%INSTALL_DIR%' already exists. Pulling latest...
    cd /d "%INSTALL_DIR%"
    git pull origin main
) else (
    echo Cloning repository...
    git clone %REPO_URL%
    cd /d "%INSTALL_DIR%"
)

echo.

:: ── Build Docker image ──
echo Building Docker image (this may take a few minutes)...
docker build -t bbfa-server ./server

echo.

:: ── Stop old container if running ──
docker stop bbfa-server >nul 2>&1
docker rm bbfa-server >nul 2>&1

:: ── Run container ──
echo Starting BBFA Server...
docker run -d ^
    --name bbfa-server ^
    -p 8700:8700 ^
    -v bbfa-data:/app/data ^
    -v bbfa-weights:/app/weights ^
    --restart unless-stopped ^
    bbfa-server

echo.
echo ==============================================
echo   BBFA Server is running!
echo ==============================================
echo.
echo   API:         http://localhost:8700
echo   Health:      http://localhost:8700/
echo   Models:      http://localhost:8700/models
echo.
echo   View logs:   docker logs -f bbfa-server
echo   Stop:        docker stop bbfa-server
echo   Restart:     docker start bbfa-server
echo   Remove:      docker rm -f bbfa-server
echo.
echo   First startup downloads ~185 MB of AI models.
echo   This may take a few minutes. Check logs to monitor.
echo ==============================================
pause
