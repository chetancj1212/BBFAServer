#!/bin/bash
# ============================================================
# BBFA Server — Setup Script
# ============================================================
# Run this on any Linux/macOS system to get the server running.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/chetancj1212/BBFAServer/main/setup.sh | bash
#   — or —
#   chmod +x setup.sh && ./setup.sh
# ============================================================

set -e

echo "=============================================="
echo "  BBFA Server — Setup"
echo "=============================================="
echo ""

# ── Check Docker ──
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    echo "   Install it from: https://docs.docker.com/get-docker/"
    exit 1
fi
echo "✅ Docker found: $(docker --version)"

# ── Check Git ──
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed."
    echo "   Install it from: https://git-scm.com/downloads"
    exit 1
fi
echo "✅ Git found: $(git --version)"

echo ""

# ── Clone repo ──
REPO_URL="https://github.com/chetancj1212/BBFAServer.git"
INSTALL_DIR="BBFAServer"

if [ -d "$INSTALL_DIR" ]; then
    echo "📁 Directory '$INSTALL_DIR' already exists. Pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "📥 Cloning repository..."
    git clone "$REPO_URL"
    cd "$INSTALL_DIR"
fi

echo ""

# ── Build Docker image ──
echo "🐳 Building Docker image (this may take a few minutes)..."
docker build -t bbfa-server ./server

echo ""

# ── Run container ──
echo "🚀 Starting BBFA Server..."
docker run -d \
    --name bbfa-server \
    -p 8700:8700 \
    -v bbfa-data:/app/data \
    -v bbfa-weights:/app/weights \
    --restart unless-stopped \
    bbfa-server

echo ""
echo "=============================================="
echo "  ✅ BBFA Server is running!"
echo "=============================================="
echo ""
echo "  API:         http://localhost:8700"
echo "  Health:      http://localhost:8700/"
echo "  Models:      http://localhost:8700/models"
echo ""
echo "  View logs:   docker logs -f bbfa-server"
echo "  Stop:        docker stop bbfa-server"
echo "  Restart:     docker start bbfa-server"
echo "  Remove:      docker rm -f bbfa-server"
echo ""
echo "  ⚠️  First startup downloads ~185 MB of AI models."
echo "     This may take a few minutes. Check logs to monitor."
echo "=============================================="
