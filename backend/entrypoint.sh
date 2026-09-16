#!/usr/bin/env bash
set -euo pipefail

# Apply migrations, then serve. Gunicorn manages uvicorn workers.
echo "Running database migrations..."
alembic upgrade head

echo "Starting API..."
# Default to a single worker: the API cache is per-process (app/cache.py), so
# >1 worker gives each its own cache and pipeline invalidation only reaches one.
# Raise WEB_CONCURRENCY only alongside a shared cache (e.g. Redis).
exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_CONCURRENCY:-1}" \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --timeout 120
