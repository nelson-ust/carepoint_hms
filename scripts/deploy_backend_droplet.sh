#!/usr/bin/env bash
# =============================================================================
# Carepoint HMS — Production Backend Deployment (DigitalOcean Ubuntu 22.04/24.04)
# =============================================================================
#
# MODES:
#   provision  — Full first-time setup (run as root on a fresh droplet)
#   deploy     — Fast CI/CD deploy (run as deploy user from GitHub Actions)
#   rollback   — Roll back to the previous deployment
#
# Usage:
#   # First-time provisioning (as root):
#   REPO_URL=https://github.com/nelson-ust/carepoint_hms.git \
#   DATABASE_URL='postgresql+psycopg2://...' \
#   APP_DOMAIN=api.example.com \
#   bash deploy_backend_droplet.sh provision
#
#   # CI/CD deploy (as deploy user via GitHub Actions):
#   bash deploy_backend_droplet.sh deploy [BRANCH]
#
#   # Rollback to previous release:
#   bash deploy_backend_droplet.sh rollback
#
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ─── COLOURS & LOGGING ───────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BLUE='\033[1;34m'; BOLD='\033[1m'; RESET='\033[0m'

log()     { echo -e "${BLUE}[$(date +%H:%M:%S)]${RESET} $*"; }
info()    { echo -e "${CYAN}[info]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[ ok ]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*" >&2; }
fail()    { echo -e "${RED}[FAIL]${RESET}  $*" >&2; exit 1; }
step()    { echo; echo -e "${BOLD}━━━ $* ━━━${RESET}"; }

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
DEPLOY_MODE="${1:-provision}"
REPO_URL="${REPO_URL:-https://github.com/nelson-ust/carepoint_hms.git}"
DATABASE_URL="${DATABASE_URL:-}"

APP_NAME="${APP_NAME:-carepoint_hms}"
APP_USER="${APP_USER:-deploy}"
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_DIR:-/opt/${APP_NAME}}"
VENV_DIR="${APP_DIR}/venv"
REPO_BRANCH="${2:-${REPO_BRANCH:-main}}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
APP_PORT="${APP_PORT:-8005}"
APP_WORKERS="${APP_WORKERS:-3}"

APP_DOMAIN="${APP_DOMAIN:-}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
ENABLE_HTTPS="${ENABLE_HTTPS:-true}"
GITHUB_DEPLOY_PUBKEY="${GITHUB_DEPLOY_PUBKEY:-}"

MASTER_DATABASE_URL="${MASTER_DATABASE_URL:-${DATABASE_URL}}"
SECRET_KEY="${SECRET_KEY:-}"
DATABASE_ENCRYPTION_KEY="${DATABASE_ENCRYPTION_KEY:-}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

EMAILS_ENABLED="${EMAILS_ENABLED:-false}"
SMTP_HOST="${SMTP_HOST:-}"; SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USERNAME="${SMTP_USERNAME:-}"; SMTP_PASSWORD="${SMTP_PASSWORD:-}"
SMTP_FROM_EMAIL="${SMTP_FROM_EMAIL:-}"; SMTP_FROM_NAME="${SMTP_FROM_NAME:-Carepoint HMS}"
SMTP_USE_TLS="${SMTP_USE_TLS:-true}"; SMTP_USE_SSL="${SMTP_USE_SSL:-false}"

HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:${APP_PORT}/health}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-15}"
ENV_FILE="${APP_DIR}/.env"
DEPLOY_LOG="${APP_DIR}/deployments.log"
DEPLOY_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# ─── SHARED HELPERS ───────────────────────────────────────────────────────────
gen_secret() { openssl rand -hex 32; }

run_app_py() {
    local label="$1"; shift
    info "→ ${label}"
    sudo -u "${APP_USER}" bash -c "set -a; source '${ENV_FILE}'; set +a; cd '${APP_DIR}' && '${VENV_DIR}/bin/python' $*" \
        && ok "${label} done." \
        || fail "${label} failed."
}

health_check() {
    local url="${1:-${HEALTHCHECK_URL}}"
    local retries="${2:-${HEALTHCHECK_RETRIES}}"
    for attempt in $(seq 1 "${retries}"); do
        if curl -fsS --max-time 5 "${url}" >/dev/null 2>&1; then
            ok "Service healthy (attempt ${attempt}/${retries})."
            return 0
        fi
        info "attempt ${attempt}/${retries} — not ready, sleeping 3s"
        sleep 3
    done
    return 1
}

record_deployment() {
    local sha="$1" status="$2"
    local line="${DEPLOY_TIMESTAMP} | sha=${sha} | branch=${REPO_BRANCH} | mode=${DEPLOY_MODE} | status=${status}"
    echo "${line}" >> "${DEPLOY_LOG}" 2>/dev/null || true
}

get_current_sha() {
    git -C "${APP_DIR}" rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

# =============================================================================
# MODE: PROVISION (full first-time setup, must run as root)
# =============================================================================
do_provision() {
    step "0. Pre-flight checks"
    [[ "${EUID}" -ne 0 ]] && fail "Provision mode must run as root."
    [[ "${REPO_URL}" == *"CHANGE_ME"* ]] && \
        fail "Set REPO_URL before running."
    [[ -z "${DATABASE_URL}" ]] && \
        fail "DATABASE_URL is required."
    [[ ! "${DATABASE_URL}" =~ ^postgresql ]] && \
        fail "DATABASE_URL must start with 'postgresql'."

    info "App: ${APP_NAME} | User: ${APP_USER} | Port: ${APP_PORT}"
    info "Repo: ${REPO_URL} @ ${REPO_BRANCH}"
    info "Domain: ${APP_DOMAIN:-<none>} | HTTPS: ${ENABLE_HTTPS}"

    # ─── 1. SYSTEM PACKAGES ──────────────────────────────────────────────
    step "1. System packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get upgrade -y
    apt-get install -y \
        git curl wget unzip ca-certificates gnupg lsb-release \
        software-properties-common build-essential pkg-config \
        libpq-dev libssl-dev libffi-dev \
        nginx ufw fail2ban \
        rsync htop jq openssl postgresql-client

    PY_PKG="python${PYTHON_VERSION}"
    if ! apt-get install -y --no-install-recommends \
        "${PY_PKG}" "${PY_PKG}-venv" "${PY_PKG}-dev" 2>/dev/null; then
        warn "Adding deadsnakes PPA for Python ${PYTHON_VERSION}"
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -y
        apt-get install -y "${PY_PKG}" "${PY_PKG}-venv" "${PY_PKG}-dev"
    fi
    apt-get install -y python3-pip

    PYTHON_BIN="$(command -v "python${PYTHON_VERSION}" || true)"
    [[ -z "${PYTHON_BIN}" ]] && fail "python${PYTHON_VERSION} not found."
    ok "Python: ${PYTHON_BIN} ($(${PYTHON_BIN} --version))"

    # ─── 2. SWAP ─────────────────────────────────────────────────────────
    step "2. Swap"
    if ! swapon --show | grep -q '/swapfile'; then
        fallocate -l 2G /swapfile && chmod 600 /swapfile
        mkswap /swapfile && swapon /swapfile
        grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
        ok "2G swap enabled."
    else
        info "Swap already active."
    fi

    # ─── 3. FIREWALL + SECURITY ──────────────────────────────────────────
    step "3. Firewall + security hardening"
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    yes | ufw enable >/dev/null 2>&1 || true
    systemctl enable --now fail2ban

    # Harden sshd
    if ! grep -q "^PermitRootLogin no" /etc/ssh/sshd_config 2>/dev/null; then
        sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
        sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
        systemctl reload sshd 2>/dev/null || systemctl reload ssh 2>/dev/null || true
        ok "SSH hardened (key-only, root login restricted)."
    fi

    # Kernel security tweaks
    cat >/etc/sysctl.d/99-carepoint-hardening.conf <<SYSCTL
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.tcp_syncookies = 1
SYSCTL
    sysctl --system >/dev/null 2>&1
    ok "Firewall + kernel hardening applied."

    # ─── 4. APP USER ─────────────────────────────────────────────────────
    step "4. Application user"
    if ! id "${APP_USER}" &>/dev/null; then
        adduser --disabled-password --gecos "" "${APP_USER}"
        usermod -aG sudo "${APP_USER}"
    fi
    cat >/etc/sudoers.d/${APP_USER}-deploy <<SUDOERS
${APP_USER} ALL=(root) NOPASSWD: /bin/systemctl restart ${APP_NAME}, /bin/systemctl reload ${APP_NAME}, /bin/systemctl status ${APP_NAME}, /usr/bin/systemctl restart ${APP_NAME}, /usr/bin/systemctl reload ${APP_NAME}, /usr/bin/systemctl status ${APP_NAME}
SUDOERS
    chmod 440 /etc/sudoers.d/${APP_USER}-deploy

    mkdir -p "${APP_HOME}/.ssh"
    chmod 700 "${APP_HOME}/.ssh"
    touch "${APP_HOME}/.ssh/authorized_keys"
    chmod 600 "${APP_HOME}/.ssh/authorized_keys"
    if [[ -n "${GITHUB_DEPLOY_PUBKEY}" ]] && \
       ! grep -qF "${GITHUB_DEPLOY_PUBKEY}" "${APP_HOME}/.ssh/authorized_keys" 2>/dev/null; then
        echo "${GITHUB_DEPLOY_PUBKEY}" >> "${APP_HOME}/.ssh/authorized_keys"
        ok "CI deploy key installed."
    fi
    chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/.ssh"
    ok "User ${APP_USER} ready."

    # ─── 5. REPO CLONE ───────────────────────────────────────────────────
    step "5. Source checkout"
    mkdir -p "${APP_DIR}"
    chown "${APP_USER}:${APP_USER}" "${APP_DIR}"
    if [[ ! -d "${APP_DIR}/.git" ]]; then
        sudo -u "${APP_USER}" git clone --branch "${REPO_BRANCH}" "${REPO_URL}" "${APP_DIR}"
        ok "Cloned ${REPO_URL} @ ${REPO_BRANCH}."
    else
        sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch --all --prune
        sudo -u "${APP_USER}" git -C "${APP_DIR}" checkout "${REPO_BRANCH}"
        sudo -u "${APP_USER}" git -C "${APP_DIR}" reset --hard "origin/${REPO_BRANCH}"
        ok "Updated to origin/${REPO_BRANCH} ($(get_current_sha))."
    fi

    # ─── 6. VIRTUALENV ───────────────────────────────────────────────────
    step "6. Python virtualenv + dependencies"
    if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
        sudo -u "${APP_USER}" "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    fi
    sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel setuptools >/dev/null
    sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
    sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install gunicorn 'uvicorn[standard]' >/dev/null
    ok "Dependencies installed."

    # ─── 7. .env ─────────────────────────────────────────────────────────
    step "7. Environment file"
    SECRET_KEY="${SECRET_KEY:-$(gen_secret)}"
    DATABASE_ENCRYPTION_KEY="${DATABASE_ENCRYPTION_KEY:-$(gen_secret)}"

    if [[ ! -f "${ENV_FILE}" ]]; then
        cat >"${ENV_FILE}" <<ENVEOF
# Generated by deploy_backend_droplet.sh on ${DEPLOY_TIMESTAMP}
CAREPOINT_HMS_ENVIRONMENT=production
CAREPOINT_HMS_DEBUG=false
CAREPOINT_HMS_HOST=0.0.0.0
CAREPOINT_HMS_PORT=${APP_PORT}
CAREPOINT_HMS_DATABASE_URL=${DATABASE_URL}
CAREPOINT_HMS_MASTER_DATABASE_URL=${MASTER_DATABASE_URL}
CAREPOINT_HMS_SECRET_KEY=${SECRET_KEY}
CAREPOINT_HMS_DATABASE_ENCRYPTION_KEY=${DATABASE_ENCRYPTION_KEY}
CAREPOINT_HMS_FRONTEND_URL=${FRONTEND_URL}
CAREPOINT_HMS_EMAILS_ENABLED=${EMAILS_ENABLED}
CAREPOINT_HMS_SMTP_HOST=${SMTP_HOST}
CAREPOINT_HMS_SMTP_PORT=${SMTP_PORT}
CAREPOINT_HMS_SMTP_USERNAME=${SMTP_USERNAME}
CAREPOINT_HMS_SMTP_PASSWORD=${SMTP_PASSWORD}
CAREPOINT_HMS_SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL}
CAREPOINT_HMS_SMTP_FROM_NAME=${SMTP_FROM_NAME}
CAREPOINT_HMS_SMTP_USE_TLS=${SMTP_USE_TLS}
CAREPOINT_HMS_SMTP_USE_SSL=${SMTP_USE_SSL}
CAREPOINT_HMS_SMS_ENABLED=false
CAREPOINT_HMS_S3_ENABLED=false
CAREPOINT_HMS_RATE_LIMIT_ENABLED=true
ENVEOF
        chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
        chmod 600 "${ENV_FILE}"
        ok ".env created. Keys auto-generated."
        warn "SAVE THESE — they are NOT recoverable:"
        echo "    SECRET_KEY=${SECRET_KEY}"
        echo "    DATABASE_ENCRYPTION_KEY=${DATABASE_ENCRYPTION_KEY}"
    else
        info ".env exists — not overwriting."
    fi

    # ─── 8. SYSTEMD + LOGROTATE ──────────────────────────────────────────
    step "8. systemd service"
    cat >/etc/systemd/system/${APP_NAME}.service <<UNITEOF
[Unit]
Description=Carepoint HMS FastAPI Backend
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn app.main:app \\
    --workers ${APP_WORKERS} \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --bind 127.0.0.1:${APP_PORT} \\
    --timeout 120 \\
    --graceful-timeout 30 \\
    --keep-alive 5 \\
    --max-requests 1000 \\
    --max-requests-jitter 50 \\
    --access-logfile /var/log/${APP_NAME}/access.log \\
    --error-logfile /var/log/${APP_NAME}/error.log \\
    --log-level info
Restart=on-failure
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${APP_DIR} /var/log/${APP_NAME}

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
UNITEOF

    mkdir -p /var/log/${APP_NAME}
    chown -R "${APP_USER}:${APP_USER}" /var/log/${APP_NAME}

    cat >/etc/logrotate.d/${APP_NAME} <<LOGEOF
/var/log/${APP_NAME}/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ${APP_USER} ${APP_USER}
    sharedscripts
    postrotate
        systemctl reload ${APP_NAME} >/dev/null 2>&1 || true
    endscript
}
LOGEOF

    systemctl daemon-reload
    systemctl enable ${APP_NAME}.service >/dev/null
    ok "systemd unit installed."

    # ─── 9. NGINX ────────────────────────────────────────────────────────
    step "9. Nginx reverse proxy"
    if [[ -n "${APP_DOMAIN}" ]]; then
        cat >/etc/nginx/sites-available/${APP_NAME} <<NGXEOF
# Rate limiting zone
limit_req_zone \$binary_remote_addr zone=api:10m rate=30r/s;

server {
    listen 80;
    listen [::]:80;
    server_name ${APP_DOMAIN};

    client_max_body_size 25m;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Health endpoint (no rate limit, no logging)
    location /health {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        access_log off;
    }

    # API
    location / {
        limit_req zone=api burst=60 nodelay;
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120;
        proxy_send_timeout 120;
        proxy_buffering on;
        proxy_buffer_size 16k;
        proxy_buffers 4 32k;
    }

    # Static assets
    location /static/ {
        alias ${APP_DIR}/app/static/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Block common attack paths
    location ~ /\.(git|env|svn) { deny all; return 404; }
}
NGXEOF
        ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/${APP_NAME}
        rm -f /etc/nginx/sites-enabled/default
        nginx -t && systemctl reload nginx
        ok "Nginx vhost for ${APP_DOMAIN} installed."
    else
        warn "APP_DOMAIN not set — skipping nginx."
    fi

    # ─── 10. SSL ─────────────────────────────────────────────────────────
    step "10. SSL certificate"
    if [[ -n "${APP_DOMAIN}" && "${ENABLE_HTTPS}" == "true" && -n "${LETSENCRYPT_EMAIL}" ]]; then
        apt-get install -y certbot python3-certbot-nginx
        certbot --nginx --non-interactive --agree-tos \
            --email "${LETSENCRYPT_EMAIL}" \
            --domains "${APP_DOMAIN}" \
            --redirect \
            || warn "certbot failed — DNS may not point here yet."
        systemctl enable --now certbot.timer
        ok "SSL provisioned."
    else
        info "SSL skipped."
    fi

    # ─── 11. DB MIGRATIONS ───────────────────────────────────────────────
    step "11. Database migrations"
    run_app_py "Master schema sync"  "-m app.init_db --sync-master"
    run_app_py "Tenant schemas sync" "-m app.init_db --sync-tenants"

    for migration in \
        migrate_tenant_backups.py \
        migrate_performance_indexes.py \
        migrate_meal_tables.py \
        migrate_feature_gating.py \
        migrate_tenant_tables.py \
        migrate_password_reset_fields.py
    do
        script="${APP_DIR}/scripts/${migration}"
        [[ -f "${script}" ]] && run_app_py "Migration: ${migration}" "${script}"
    done

    # ─── 12. START ───────────────────────────────────────────────────────
    step "12. Start service"
    systemctl restart ${APP_NAME}.service
    sleep 3

    step "13. Health check"
    if health_check; then
        record_deployment "$(get_current_sha)" "SUCCESS"
    else
        record_deployment "$(get_current_sha)" "UNHEALTHY"
        warn "Service did not become healthy. Check: journalctl -u ${APP_NAME} -n 200"
        exit 1
    fi

    # ─── DONE ────────────────────────────────────────────────────────────
    echo
    echo -e "${GREEN}${BOLD}✓ Provisioning complete.${RESET}"
    echo
    echo "  Service:    systemctl status ${APP_NAME}"
    echo "  Logs:       journalctl -u ${APP_NAME} -f"
    echo "  Env:        ${ENV_FILE}"
    echo "  Deploys:    cat ${DEPLOY_LOG}"
    [[ -n "${APP_DOMAIN}" ]] && echo "  URL:        https://${APP_DOMAIN}"
    echo
    echo "  GitHub Actions secrets needed:"
    echo "    DROPLET_HOST       = <this-droplet-ip>"
    echo "    DROPLET_USER       = ${APP_USER}"
    echo "    DROPLET_SSH_KEY    = <private key matching the deploy pubkey>"
    echo "    DROPLET_DOMAIN     = ${APP_DOMAIN:-<your-domain>}"
}

# =============================================================================
# MODE: DEPLOY (fast CI/CD path, runs as deploy user)
# =============================================================================
do_deploy() {
    step "CI/CD Deploy"

    [[ -d "${APP_DIR}/.git" ]] || fail "${APP_DIR} is not a git repo. Run 'provision' first."
    [[ -x "${VENV_DIR}/bin/python" ]] || fail "No venv at ${VENV_DIR}. Run 'provision' first."
    [[ -f "${ENV_FILE}" ]] || fail "${ENV_FILE} missing."

    # Concurrency guard: only one deploy at a time on this host. Belt and
    # braces — GitHub Actions also gates with its own ``concurrency:`` block,
    # but a manual deploy could still race with CI without this. The lock
    # auto-releases when this shell exits (success, failure, or signal).
    local lock_file="/var/lock/${APP_NAME}.deploy.lock"
    exec 9>"${lock_file}" 2>/dev/null || true
    if command -v flock >/dev/null 2>&1; then
        if ! flock -n 9; then
            fail "Another deploy is in progress (lock: ${lock_file}). Retry once it finishes."
        fi
    fi

    cd "${APP_DIR}"

    # Save current SHA for rollback
    PREV_SHA="$(get_current_sha)"
    echo "${PREV_SHA}" > "${APP_DIR}/.previous_sha"

    # 1. Pull latest code
    log "Pulling origin/${REPO_BRANCH}"
    git fetch --all --prune
    git checkout "${REPO_BRANCH}"
    git reset --hard "origin/${REPO_BRANCH}"
    NEW_SHA="$(get_current_sha)"
    log "Deploying ${PREV_SHA} → ${NEW_SHA} ($(git log -1 --pretty=%s))"

    if [[ "${PREV_SHA}" == "${NEW_SHA}" ]]; then
        info "No new commits. Restarting service anyway."
    fi

    # 2. Dependencies (only if requirements changed)
    if ! git diff --quiet "${PREV_SHA}..${NEW_SHA}" -- requirements.txt 2>/dev/null; then
        log "requirements.txt changed — syncing deps"
        "${VENV_DIR}/bin/pip" install --upgrade pip wheel >/dev/null
        "${VENV_DIR}/bin/pip" install -r requirements.txt
        "${VENV_DIR}/bin/pip" install gunicorn 'uvicorn[standard]' >/dev/null
        ok "Dependencies updated."
    else
        info "requirements.txt unchanged — skipping pip install."
    fi

    # 3a. Schema migrations: framework-level forward sync (idempotent).
    log "Running forward-only schema sync"
    set -a; source "${ENV_FILE}"; set +a
    "${VENV_DIR}/bin/python" -m app.init_db --sync-master  || fail "Master sync failed"
    "${VENV_DIR}/bin/python" -m app.init_db --sync-tenants || fail "Tenant sync failed"

    # 3b. Standalone migration scripts. Each one is idempotent (ADD COLUMN IF
    # NOT EXISTS / CREATE INDEX IF NOT EXISTS), so re-runs on an up-to-date
    # database are a no-op. New migrations added to scripts/migrate_*.py
    # ship to production the moment the next deploy lands — no separate
    # operator step required.
    for migration in \
        migrate_tenant_backups.py \
        migrate_performance_indexes.py \
        migrate_meal_tables.py \
        migrate_feature_gating.py \
        migrate_tenant_tables.py \
        migrate_password_reset_fields.py
    do
        script="${APP_DIR}/scripts/${migration}"
        if [[ -f "${script}" ]]; then
            log "→ migration: ${migration}"
            "${VENV_DIR}/bin/python" "${script}" || fail "Migration ${migration} failed"
        fi
    done

    # 4. Graceful restart
    log "Restarting ${APP_NAME}.service"
    sudo /bin/systemctl restart "${APP_NAME}"
    sleep 3

    # 5. Health check
    if health_check "${HEALTHCHECK_URL}" 10; then
        record_deployment "${NEW_SHA}" "SUCCESS"
        log "✓ Deployed ${NEW_SHA} successfully."
    else
        warn "Health check failed — attempting automatic rollback to ${PREV_SHA}"
        git reset --hard "${PREV_SHA}"
        sudo /bin/systemctl restart "${APP_NAME}"
        sleep 3
        if health_check "${HEALTHCHECK_URL}" 5; then
            record_deployment "${NEW_SHA}" "ROLLED_BACK"
            fail "Deploy of ${NEW_SHA} failed. Auto-rolled back to ${PREV_SHA}."
        else
            record_deployment "${NEW_SHA}" "FAILED"
            fail "Deploy AND rollback failed. Manual intervention required."
        fi
    fi
}

# =============================================================================
# MODE: ROLLBACK
# =============================================================================
do_rollback() {
    step "Rollback"

    [[ -d "${APP_DIR}/.git" ]] || fail "Not a git repo."
    cd "${APP_DIR}"

    CURRENT_SHA="$(get_current_sha)"

    if [[ -f "${APP_DIR}/.previous_sha" ]]; then
        PREV_SHA="$(cat "${APP_DIR}/.previous_sha")"
    else
        # Fall back to the commit before HEAD
        PREV_SHA="$(git rev-parse --short HEAD~1 2>/dev/null || true)"
    fi

    [[ -z "${PREV_SHA}" ]] && fail "No previous SHA to roll back to."
    [[ "${PREV_SHA}" == "${CURRENT_SHA}" ]] && fail "Already at ${PREV_SHA}."

    log "Rolling back: ${CURRENT_SHA} → ${PREV_SHA}"
    git reset --hard "${PREV_SHA}"

    # Re-sync deps
    "${VENV_DIR}/bin/pip" install -r requirements.txt >/dev/null 2>&1

    sudo /bin/systemctl restart "${APP_NAME}"
    sleep 3

    if health_check "${HEALTHCHECK_URL}" 10; then
        record_deployment "${PREV_SHA}" "ROLLBACK_SUCCESS"
        ok "Rolled back to ${PREV_SHA} successfully."
    else
        record_deployment "${PREV_SHA}" "ROLLBACK_FAILED"
        fail "Rollback to ${PREV_SHA} failed. Service unhealthy."
    fi
}

# =============================================================================
# DISPATCH
# =============================================================================
case "${DEPLOY_MODE}" in
    provision) do_provision ;;
    deploy)    do_deploy ;;
    rollback)  do_rollback ;;
    *)
        echo "Usage: $0 {provision|deploy|rollback} [BRANCH]"
        echo
        echo "  provision  — Full server setup (run as root)"
        echo "  deploy     — CI/CD deploy (pull, migrate, restart)"
        echo "  rollback   — Revert to previous deployment"
        exit 1
        ;;
esac
