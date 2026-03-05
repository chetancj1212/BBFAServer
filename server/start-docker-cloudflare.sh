#!/bin/bash
# ============================================================
# BBFA — Docker + Cloudflare Tunnel Start Script (Linux/macOS)
# ============================================================

echo "=============================================="
echo "  BBFA — Docker + Cloudflare Tunnel"
echo "=============================================="
echo ""

# 1. Check Docker
if ! docker ps >/dev/null 2>&1; then
    echo "[ERROR] Docker is not running."
    exit 1
fi

# 2. Check cloudflared
if ! command -v cloudflared >/dev/null 2>&1; then
    echo "[ERROR] cloudflared is not installed."
    exit 1
fi

# 3. Start Server
echo "[1/2] Starting BBFA Server Container..."
if ! docker start bbfa-server >/dev/null 2>&1; then
    echo "[INFO] Container not found. Attempting to run from image..."
    docker run -d --name bbfa-server -p 8700:8700 -v bbfa-data:/app/data bbfa-server
fi

# 4. Wait
sleep 3

# 5. Start Tunnel
echo "[2/2] Starting Cloudflare Tunnel (api.chetancj.in)..."
cloudflared tunnel run bbfa-backend
