FROM python:3.12-slim

LABEL org.opencontainers.image.title="Simple Recipes" \
      org.opencontainers.image.description="Recipe sharing service"

# System dependencies (curl for asset download)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# Download vendored frontend assets
RUN mkdir -p /app/static/js /app/static/css \
    && curl -fkSL -o /app/static/js/htmx.min.js \
       https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js \
    && curl -fkSL -o /app/static/css/pico.min.css \
       https://unpkg.com/@picocss/pico@2.0.6/css/pico.min.css

# Copy application code
COPY backend/ .

# Data directory (overridden by bind mount at runtime)
RUN mkdir -p /app/data/db /app/data/recipes

# Entrypoint: chown data dir then drop to appuser
COPY entrypoint.sh /entrypoint.sh
RUN useradd -r -u 1001 -g root appuser \
    && chown -R appuser:root /app \
    && chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/docs || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
