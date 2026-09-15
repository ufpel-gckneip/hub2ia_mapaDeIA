#!/usr/bin/env bash
set -euo pipefail

# Apply migrations, then serve. Gunicorn manages uvicorn workers.
echo "Running database migrations..."
alembic upgrade head

echo "Starting API..."
exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_CONCURRENCY:-2}" \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --timeout 120
