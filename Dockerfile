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

# Download vendored frontend assets.
# TLS verification stays on and every file is checked against a pinned digest,
# so a tampered CDN response fails the build instead of shipping in the image.
ARG HTMX_SHA256=491955cd1810747d7d7b9ccb936400afb760e06d25d53e4572b64b6563b2784e
ARG PICO_SHA256=dd5fd5591afd81ee21dcc117ad85c014dc3f1f19dc2d7b7d101ea0acc29274c2
RUN mkdir -p /app/static/js /app/static/css \
    && curl -fsSL -o /app/static/js/htmx.min.js \
       https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js \
    && echo "${HTMX_SHA256}  /app/static/js/htmx.min.js" | sha256sum -c - \
    && curl -fsSL -o /app/static/css/pico.min.css \
       https://unpkg.com/@picocss/pico@2.0.6/css/pico.min.css \
    && echo "${PICO_SHA256}  /app/static/css/pico.min.css" | sha256sum -c -

# Copy application code
COPY backend/ .

# Data directory (overridden by bind mount at runtime)
RUN mkdir -p /app/data/db /app/data/recipes

# Entrypoint: chown data dir then drop to appuser.
# The application code stays owned by root and read-only for appuser; only the
# data directory is writable, so a file-write bug cannot rewrite the app itself.
COPY entrypoint.sh /entrypoint.sh
RUN useradd -r -u 1001 -g root appuser \
    && chown -R root:root /app \
    && chmod -R go-w /app \
    && chown -R appuser:root /app/data \
    && chmod -R u+rwX /app/data \
    && chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["/entrypoint.sh"]
# --proxy-headers makes the rate limiter see the real client IP instead of the
# reverse proxy's. FORWARDED_ALLOW_IPS must list the proxy only, never "*".
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-172.16.0.0/12}\""]
