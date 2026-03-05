# ============================================================
# BBFA Server — Dockerfile
# ============================================================
# Multi-stage build for a lean Python image.
# Model weights are auto-downloaded on first startup via
# utils/model_downloader.py (cached in the weights/ volume).
# ============================================================

# ── Stage 1: Build dependencies ──
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system deps needed to build opencv-python wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Production image ──
FROM python:3.12-slim

WORKDIR /app

# Runtime system deps for OpenCV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create directories for runtime data and weights
RUN mkdir -p /app/data /app/weights

# ── Volumes ──
# data/   → SQLite databases (persist across restarts)
# weights/ → ONNX models (auto-downloaded on first run)
VOLUME ["/app/data", "/app/weights"]

# ── Environment ──
ENV HOST=0.0.0.0
ENV WORKERS=1
ENV MAX_INFERENCE_CONCURRENCY=4
ENV PYTHONUNBUFFERED=1

EXPOSE 8700

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8700/')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8700"]
