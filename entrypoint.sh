#!/bin/sh
# Ensure the data directory is owned by the app user (handles host bind-mounts)
chown -R appuser:root /app/data 2>/dev/null || true
exec runuser -u appuser -- "$@"
