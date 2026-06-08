#!/bin/sh
set -e

# Start haveged to prevent entropy starvation (mainly for bcrypt / getrandom in cloud containers)
haveged -w 1024 || true

# Start Celery worker in background
uv run --project /app/backend celery -A backend.app.tasks:celery_app worker --loglevel=info &
CELERY_PID=$!

# Kill Celery when uvicorn exits
cleanup() {
    kill "$CELERY_PID" 2>/dev/null || true
    wait "$CELERY_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start uvicorn in foreground (keeps container alive)
exec uv run --project /app/backend uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
