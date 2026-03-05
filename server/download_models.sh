#!/bin/bash
# ============================================================
# Download BBFA Model Weights (~185 MB)
# ============================================================
# Run this after cloning the repo to download the ONNX models.
# Usage: chmod +x download_models.sh && ./download_models.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEIGHTS_DIR="$SCRIPT_DIR/weights"

echo "=============================================="
echo "  BBFA — Model Weight Downloader"
echo "=============================================="
echo ""

mkdir -p "$WEIGHTS_DIR"
echo "Downloading models to: $WEIGHTS_DIR"
echo "This will download ~185 MB total."
echo ""

# ── 1. SCRFD-10G Face Detector (~16 MB) ──
if [ -f "$WEIGHTS_DIR/scrfd_10g.onnx" ]; then
    echo "[SKIP] scrfd_10g.onnx already exists"
else
    echo "[1/3] Downloading SCRFD-10G face detector (~16 MB)..."
    curl -L -o "$WEIGHTS_DIR/scrfd_10g.onnx" \
        "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/scrfd_10g_bnkps.onnx"
    echo "[OK] scrfd_10g.onnx downloaded"
fi

echo ""

# ── 2. ArcFace Recognizer (~167 MB) ──
if [ -f "$WEIGHTS_DIR/recognizer.onnx" ]; then
    echo "[SKIP] recognizer.onnx already exists"
else
    echo "[2/3] Downloading ArcFace recognizer (~167 MB)..."
    curl -L -o "$WEIGHTS_DIR/recognizer.onnx" \
        "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/w600k_r50.onnx"
    echo "[OK] recognizer.onnx downloaded"
fi

echo ""

# ── 3. Liveness Detector (~2 MB) ──
if [ -f "$WEIGHTS_DIR/liveness.onnx" ]; then
    echo "[SKIP] liveness.onnx already exists"
else
    echo "[3/3] Downloading MiniFASNetV2 liveness detector (~2 MB)..."
    curl -L -o "$WEIGHTS_DIR/liveness.onnx" \
        "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/minifasnet_v2.onnx"
    echo "[OK] liveness.onnx downloaded"
fi

echo ""
echo "=============================================="
echo "  ✅ Download complete!"
echo "=============================================="
echo ""
echo "  weights/scrfd_10g.onnx   — Face detector"
echo "  weights/recognizer.onnx  — Face recognizer"
echo "  weights/liveness.onnx    — Liveness detector"
echo ""
