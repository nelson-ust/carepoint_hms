#!/usr/bin/env bash
# =============================================================================
# Carepoint HMS — Deploy Script (runs on the droplet, invoked by GitHub Actions)
# =============================================================================
# This script lives in the repo and is executed on the droplet by the
# GitHub Actions workflow after it SSHes in. It assumes provision_droplet.sh
# has already been run once.
#
# What it does:
#   1. cd into the app directory,
#   2. fetch + reset to origin/<branch> (no merges, no surprises),
#   3. activate the venv and install / upgrade requirements,
#   4. run the idempotent forward-migrate so new tables/columns appear
#      without dropping data,
#   5. restart the systemd service,
#   6. health-check the running service.
#
# Usage on the droplet (manual):
#   sudo -u deploy /opt/carepoint_hms/scripts/deploy.sh [BRANCH]
#
# In CI:
#   GitHub Actions runs `bash /opt/carepoint_hms/scripts/deploy.sh main`.
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

APP_NAME="${APP_NAME:-carepoint_hms}"
APP_DIR="${APP_DIR:-/opt/${APP_NAME}}"
VENV_DIR="${APP_DIR}/venv"
BRANCH="${1:-${REPO_BRANCH:-main}}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8005/health}"

log()  { echo -e "\033[1;34m[deploy $(date +%H:%M:%S)]\033[0m $*"; }
fail() { echo -e "\033[1;31m[deploy fail]\033[0m $*" >&2; exit 1; }

[[ -d "${APP_DIR}/.git" ]] || fail "${APP_DIR} is not a git checkout. Did provision_droplet.sh run?"
[[ -x "${VENV_DIR}/bin/python" ]] || fail "venv not found at ${VENV_DIR}. Did provision_droplet.sh run?"
[[ -f "${APP_DIR}/.env" ]] || fail "${APP_DIR}/.env missing — create it before deploying."

cd "${APP_DIR}"

# ─── 1. Update source tree ────────────────────────────────────────────────────
log "Pulling latest from origin/${BRANCH}"
git fetch --all --prune
git checkout "${BRANCH}"
git reset --hard "origin/${BRANCH}"
COMMIT_SHA="$(git rev-parse --short HEAD)"
log "Now at ${COMMIT_SHA} ($(git log -1 --pretty=%s))"

# ─── 2. Dependencies ──────────────────────────────────────────────────────────
log "Syncing Python requirements"
"${VENV_DIR}/bin/pip" install --upgrade pip wheel >/dev/null
"${VENV_DIR}/bin/pip" install -r requirements.txt
# Make sure the runtime servers exist (no-op once installed).
"${VENV_DIR}/bin/pip" install gunicorn 'uvicorn[standard]' >/dev/null

# ─── 3. Idempotent schema forward-migrate ─────────────────────────────────────
# We DELIBERATELY do NOT run a destructive reset here. The init_db default
# would DROP SCHEMA public CASCADE on the master DB — that is correct for
# initial setup but would wipe production tenants on every push. Use the
# explicit forward-migrate flags instead so existing data is preserved.
log "Applying master + tenant schema forward-migrate"
"${VENV_DIR}/bin/python" -m app.init_db --sync-master  || fail "master sync failed"
"${VENV_DIR}/bin/python" -m app.init_db --sync-tenants || fail "tenant sync failed"

# ─── 4. Restart the service ───────────────────────────────────────────────────
log "Restarting ${APP_NAME}.service"
sudo /bin/systemctl restart "${APP_NAME}"
sleep 3
sudo /bin/systemctl status "${APP_NAME}" --no-pager | head -n 20

# ─── 5. Health-check ──────────────────────────────────────────────────────────
log "Health-check: ${HEALTHCHECK_URL}"
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS --max-time 5 "${HEALTHCHECK_URL}" >/dev/null; then
        log "✓ Service healthy on attempt ${attempt}. Deployed ${COMMIT_SHA}."
        exit 0
    fi
    log "  attempt ${attempt}/10 — service not ready yet, sleeping 3s"
    sleep 3
done

fail "Service did not become healthy after 30s. Inspect: journalctl -u ${APP_NAME} -n 200"
