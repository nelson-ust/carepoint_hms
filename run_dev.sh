#!/usr/bin/env bash
#
# Reliable local dev launcher for the CarePoint HMS API.
#
#   ./run_dev.sh          # or:  bash run_dev.sh
#
# Why this exists
# ---------------
# Three recurring dev headaches this solves in one command:
#
#   1. "I restarted but the new endpoint still 404s."
#      That happens when a fresh `uvicorn` can't bind the port (the old
#      server is still holding it) and quietly exits — so the OLD process
#      keeps serving stale code. This script force-frees the port first.
#
#   2. "The new feature 500s: relation ... does not exist."
#      New models add new tables/enums that only appear after a schema
#      sync. This script runs the forward-only tenant sync on start, so a
#      newly added table is created before the server serves a request.
#      (Forward-only: it only ADDS missing tables/columns, never drops.)
#      Set SKIP_DB_SYNC=1 to skip it on a given run.
#
#   3. "I have to restart after every change."
#      It starts uvicorn with autoreload, so saved edits take effect with
#      no manual restart.
#
# Run it from the backend project root with your virtualenv activated.
set -euo pipefail
cd "$(dirname "$0")"

# Resolve the API port: explicit env override → .env (UVICORN_PORT/PORT, with
# or without the CAREPOINT_HMS_ prefix) → default 8000.
PORT="${UVICORN_PORT:-}"
if [ -z "${PORT}" ] && [ -f .env ]; then
  PORT="$(grep -E '^(CAREPOINT_HMS_)?(UVICORN_PORT|PORT)=' .env | tail -1 | cut -d '=' -f2- | tr -d '[:space:]' || true)"
fi
PORT="${PORT:-8000}"

echo "▶ Freeing port ${PORT} (stopping any server still bound to it)…"
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti "tcp:${PORT}" 2>/dev/null || true)"
  if [ -n "${PIDS}" ]; then
    echo "  stopping stale PID(s): ${PIDS}"
    kill -9 ${PIDS} 2>/dev/null || true
    sleep 1
  fi
else
  echo "  (lsof not found — skipping port cleanup)"
fi

# Bring the tenant databases' schema up to date so newly added tables/enums
# (e.g. membership_card_funding_request) exist before the API serves traffic.
# Non-fatal: an unreachable tenant DB logs a warning but never blocks startup.
if [ "${SKIP_DB_SYNC:-0}" != "1" ]; then
  echo "▶ Syncing tenant database schema (forward-only; SKIP_DB_SYNC=1 to skip)…"
  python -m app.init_db --sync-tenants || echo "  ⚠ schema sync reported an issue — continuing to start the server."
fi

export UVICORN_RELOAD=true
export UVICORN_PORT="${PORT}"
echo "▶ Starting API on port ${PORT} with autoreload (UVICORN_RELOAD=true)…"
exec python -m app.main
