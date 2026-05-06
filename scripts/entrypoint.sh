#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting Carepoint HMS Entrypoint Script..."

# 1. Run database initialization/sync
# This handles schema creation and seeding in an idempotent way
echo "Running database initialization..."
python -m app.init_db

# 2. Start the application
# We use Gunicorn with Uvicorn workers for production performance and stability
echo "Starting FastAPI application with Gunicorn..."
exec gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logformat '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"' \
    --access-logfile -
