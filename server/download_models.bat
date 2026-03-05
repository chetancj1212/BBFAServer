@echo off
:: ============================================================
:: Download BBFA Model Weights (~185 MB)
:: ============================================================
:: Run this after cloning the repo to download the ONNX models.
:: Models are saved to the server/weights/ directory.
:: ============================================================

echo ==============================================
echo   BBFA — Model Weight Downloader
echo ==============================================
echo.

cd /d "%~dp0"

:: Create weights directory
if not exist "weights" mkdir weights

echo Downloading models to: %cd%\weights
echo This will download ~185 MB total.
echo.

:: ── 1. SCRFD-10G Face Detector (~16 MB) ──
if exist "weights\scrfd_10g.onnx" (
    echo [SKIP] scrfd_10g.onnx already exists
) else (
    echo [1/3] Downloading SCRFD-10G face detector (~16 MB)...
    curl -L -o "weights\scrfd_10g.onnx" "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/scrfd_10g_bnkps.onnx"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to download scrfd_10g.onnx
    ) else (
        echo [OK] scrfd_10g.onnx downloaded
    )
)

echo.

:: ── 2. ArcFace Recognizer (~167 MB) ──
if exist "weights\recognizer.onnx" (
    echo [SKIP] recognizer.onnx already exists
) else (
    echo [2/3] Downloading ArcFace recognizer (~167 MB)...
    curl -L -o "weights\recognizer.onnx" "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/w600k_r50.onnx"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to download recognizer.onnx
    ) else (
        echo [OK] recognizer.onnx downloaded
    )
)

echo.

:: ── 3. Liveness Detector (~2 MB) ──
if exist "weights\liveness.onnx" (
    echo [SKIP] liveness.onnx already exists
) else (
    echo [3/3] Downloading MiniFASNetV2 liveness detector (~2 MB)...
    curl -L -o "weights\liveness.onnx" "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/minifasnet_v2.onnx"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to download liveness.onnx
    ) else (
        echo [OK] liveness.onnx downloaded
    )
)

echo.
echo ==============================================
echo   Download complete!
echo ==============================================
echo.
echo   weights\scrfd_10g.onnx   — Face detector
echo   weights\recognizer.onnx  — Face recognizer
echo   weights\liveness.onnx    — Liveness detector
echo.
pause
