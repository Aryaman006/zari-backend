FROM python:3.12-slim

# ── System Dependencies ───────────────────────────────────────────────────────
# WeasyPrint requires Cairo, Pango, and GDK-Pixbuf for PDF generation.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# ── Environment ───────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Python Dependencies ───────────────────────────────────────────────────────
# Copy requirements first to leverage Docker layer cache.
COPY requirements.txt .
RUN pip install -r requirements.txt

# ── Application Code ──────────────────────────────────────────────────────────
COPY . .

# ── Security ──────────────────────────────────────────────────────────────────
# Run as non-root for security.
RUN addgroup --system appgroup && adduser --system --group appuser
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# ── Start Command ─────────────────────────────────────────────────────────────
# Production: Gunicorn with Uvicorn workers.
# --preload: loads the app once before forking workers (faster cold starts on Render).
# Render sets the PORT env var; default to 8000 for local/Docker testing.
CMD ["sh", "-c", "gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 \
    --preload \
    --access-logfile - \
    --error-logfile -"]
