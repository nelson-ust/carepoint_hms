#!/usr/bin/env bash
# =============================================================================
# Carepoint HMS — Backend Server Provisioning (DigitalOcean Ubuntu 22.04 / 24.04)
# =============================================================================
# Run ONCE on a fresh DigitalOcean droplet to:
#   * harden the box (firewall, swap, fail2ban),
#   * install system deps (Python 3.10+, build tools, nginx, certbot),
#   * create a non-root deploy user with key-only SSH,
#   * clone the application repo into /opt/carepoint_hms,
#   * build a Python virtualenv and install requirements,
#   * install the systemd unit + nginx site,
#   * (optionally) issue a Let's Encrypt certificate,
#   * start the service.
#
# After this script finishes, GitHub Actions only needs to SSH in as the
# deploy user and run scripts/deploy.sh (also created by this repo) to
# pull new code and restart the service.
#
# Usage (from your laptop):
#   scp scripts/provision_droplet.sh root@DROPLET_IP:~
#   ssh root@DROPLET_IP "chmod +x provision_droplet.sh && ./provision_droplet.sh"
#
# Re-runnable: every step is idempotent. Safe to re-execute on the same box.
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
# Override any of these on the command line, e.g.:
#   APP_DOMAIN=api.carepoint.example REPO_URL=git@github.com:you/carepoint_hms.git ./provision_droplet.sh

APP_NAME="${APP_NAME:-carepoint_hms}"
APP_USER="${APP_USER:-deploy}"                # non-root account that owns + runs the app
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_DIR:-/opt/${APP_NAME}}"        # where the source lives
VENV_DIR="${APP_DIR}/venv"
REPO_URL="${REPO_URL:-https://github.com/CHANGE_ME/carepoint_hms.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
# Default to Python 3.12 — current stable, ~10–25% faster than 3.10 and
# the version we test the CI pipeline against. Override with
# PYTHON_VERSION=3.11 (Ubuntu 24.04 default) or 3.10 if you have a
# pinned dependency that hasn't shipped 3.12 wheels yet.
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
APP_PORT="${APP_PORT:-8005}"                  # gunicorn binds here; nginx proxies to it
APP_WORKERS="${APP_WORKERS:-3}"               # uvicorn workers (~ 2*cores+1)
APP_DOMAIN="${APP_DOMAIN:-}"                  # e.g. api.carepoint.example. Empty = no nginx vhost / no SSL
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"    # required if APP_DOMAIN is set + HTTPS wanted
ENABLE_HTTPS="${ENABLE_HTTPS:-true}"          # set to false to skip certbot
GITHUB_DEPLOY_PUBKEY="${GITHUB_DEPLOY_PUBKEY:-}"  # paste the pub-half of the SSH key GH Actions will use

# Path on the droplet where the app's runtime .env lives. NOT versioned.
ENV_FILE="${APP_DIR}/.env"

# ─── PRE-FLIGHT ───────────────────────────────────────────────────────────────
if [[ "${EUID}" -ne 0 ]]; then
    echo "✗ Run this script as root (or with sudo)." >&2
    exit 1
fi

if [[ "${REPO_URL}" == *"CHANGE_ME"* ]]; then
    echo "✗ Set REPO_URL to your GitHub repo URL before running." >&2
    echo "  Example: REPO_URL=https://github.com/youruser/carepoint_hms.git ./provision_droplet.sh"
    exit 1
fi

log()  { echo -e "\033[1;34m[$(date +%H:%M:%S)]\033[0m $*"; }
warn() { echo -e "\033[1;33m[warn]\033[0m $*" >&2; }

# ─── 1. SYSTEM PACKAGES ───────────────────────────────────────────────────────
log "1/9  Updating apt + installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

# Base packages (everything except the specific Python version).
apt-get install -y \
    git curl wget unzip ca-certificates gnupg lsb-release \
    software-properties-common \
    build-essential pkg-config \
    libpq-dev libssl-dev libffi-dev \
    nginx \
    ufw fail2ban \
    rsync htop jq

# Resolve the requested Python from the base apt repo first; if that
# fails (Ubuntu 22.04 doesn't ship 3.11/3.12 in the default repo),
# fall back to the deadsnakes PPA which carries every supported
# Python release built against the matching libc.
PY_PKG="python${PYTHON_VERSION}"
PY_VENV="python${PYTHON_VERSION}-venv"
PY_DEV="python${PYTHON_VERSION}-dev"

if ! apt-get install -y --no-install-recommends "${PY_PKG}" "${PY_VENV}" "${PY_DEV}"; then
    warn "Python ${PYTHON_VERSION} not in base apt — adding deadsnakes PPA"
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -y
    apt-get install -y "${PY_PKG}" "${PY_VENV}" "${PY_DEV}"
fi

# python3-pip from apt is a separate package and works for any Python
# version because the venv we'll create has its own pip.
apt-get install -y python3-pip

# Pick the python binary we just installed (must be the requested
# major.minor — never silently fall back to whatever python3 points
# at, otherwise the venv ends up on the wrong interpreter).
PYTHON_BIN="$(command -v "python${PYTHON_VERSION}" || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
    fail() { echo -e "\033[1;31m[fail]\033[0m $*" >&2; exit 1; }
    fail "Could not locate python${PYTHON_VERSION} after install. Set PYTHON_VERSION to a value the OS supports (e.g. 3.10 on Ubuntu 22.04, 3.11 on 24.04, or use deadsnakes for 3.12)."
fi
log "      Using Python at ${PYTHON_BIN} ($("${PYTHON_BIN}" --version))"

# ─── 2. SWAP (helpful on 1–2 GB droplets) ─────────────────────────────────────
if ! swapon --show | grep -q '/swapfile'; then
    log "2/9  Adding 2G swapfile"
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
else
    log "2/9  Swap already configured — skipping"
fi

# ─── 3. FIREWALL ──────────────────────────────────────────────────────────────
log "3/9  Configuring UFW (ssh + http + https)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
yes | ufw enable >/dev/null 2>&1 || true
systemctl enable --now fail2ban

# ─── 4. APPLICATION USER ──────────────────────────────────────────────────────
if ! id "${APP_USER}" &>/dev/null; then
    log "4/9  Creating ${APP_USER} user"
    adduser --disabled-password --gecos "" "${APP_USER}"
    usermod -aG sudo "${APP_USER}"
    # Allow passwordless sudo for the systemd service-restart commands the
    # deploy script needs.
    cat >/etc/sudoers.d/${APP_USER}-deploy <<EOF
${APP_USER} ALL=(root) NOPASSWD: /bin/systemctl restart ${APP_NAME}, /bin/systemctl status ${APP_NAME}, /usr/bin/systemctl restart ${APP_NAME}, /usr/bin/systemctl status ${APP_NAME}
EOF
    chmod 440 /etc/sudoers.d/${APP_USER}-deploy
else
    log "4/9  User ${APP_USER} already exists — skipping"
fi

# Authorised SSH key for GitHub Actions
mkdir -p "${APP_HOME}/.ssh"
chmod 700 "${APP_HOME}/.ssh"
touch "${APP_HOME}/.ssh/authorized_keys"
chmod 600 "${APP_HOME}/.ssh/authorized_keys"

if [[ -n "${GITHUB_DEPLOY_PUBKEY}" ]]; then
    if ! grep -qF "${GITHUB_DEPLOY_PUBKEY}" "${APP_HOME}/.ssh/authorized_keys" 2>/dev/null; then
        log "      Installing GitHub Actions deploy public key"
        echo "${GITHUB_DEPLOY_PUBKEY}" >> "${APP_HOME}/.ssh/authorized_keys"
    fi
else
    warn "GITHUB_DEPLOY_PUBKEY not set — paste the pub key into ${APP_HOME}/.ssh/authorized_keys before triggering the GH Actions deploy."
fi
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/.ssh"

# ─── 5. CLONE REPO ────────────────────────────────────────────────────────────
log "5/9  Cloning / updating the application repository"
mkdir -p "${APP_DIR}"
chown "${APP_USER}:${APP_USER}" "${APP_DIR}"

if [[ ! -d "${APP_DIR}/.git" ]]; then
    sudo -u "${APP_USER}" git clone --branch "${REPO_BRANCH}" "${REPO_URL}" "${APP_DIR}"
else
    sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch --all --prune
    sudo -u "${APP_USER}" git -C "${APP_DIR}" checkout "${REPO_BRANCH}"
    sudo -u "${APP_USER}" git -C "${APP_DIR}" reset --hard "origin/${REPO_BRANCH}"
fi

# ─── 6. PYTHON VENV + DEPENDENCIES ────────────────────────────────────────────
log "6/9  Building Python virtualenv + installing requirements"
sudo -u "${APP_USER}" "${PYTHON_BIN}" -m venv "${VENV_DIR}"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel setuptools
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
# Production WSGI/ASGI runner — gunicorn driving uvicorn workers.
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install gunicorn uvicorn[standard]

# ─── 7. .env BOOTSTRAP ────────────────────────────────────────────────────────
if [[ ! -f "${ENV_FILE}" ]]; then
    log "7/9  Writing initial .env (you MUST edit it before first start)"
    cat >"${ENV_FILE}" <<EOF
# Carepoint HMS runtime configuration — fill these in before starting the service.
CAREPOINT_HMS_ENVIRONMENT=production
CAREPOINT_HMS_DEBUG=false
CAREPOINT_HMS_HOST=0.0.0.0
CAREPOINT_HMS_PORT=${APP_PORT}

# Database (managed Postgres recommended)
CAREPOINT_HMS_DATABASE_URL=postgresql+psycopg2://carepoint_app:CHANGE_ME@DB_HOST:5432/carepoint_hms_master?sslmode=require
CAREPOINT_HMS_MASTER_DATABASE_URL=postgresql+psycopg2://carepoint_admin:CHANGE_ME@DB_HOST:5432/carepoint_hms_master?sslmode=require

# Secrets — generate with:  openssl rand -hex 32
CAREPOINT_HMS_SECRET_KEY=CHANGE_ME_WITH_openssl_rand_-hex_32
CAREPOINT_HMS_DATABASE_ENCRYPTION_KEY=CHANGE_ME_WITH_openssl_rand_-hex_32

# Email / SMS / S3 — set to true and fill in once the integrations are ready
CAREPOINT_HMS_EMAILS_ENABLED=false
CAREPOINT_HMS_SMS_ENABLED=false
CAREPOINT_HMS_S3_ENABLED=false
EOF
    chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    warn "Edit ${ENV_FILE} now — set the database URL + secrets, then re-run: systemctl restart ${APP_NAME}"
else
    log "7/9  ${ENV_FILE} already exists — leaving untouched"
fi

# ─── 8. SYSTEMD SERVICE + NGINX SITE ──────────────────────────────────────────
log "8/9  Installing systemd unit + nginx vhost"

# systemd unit — runs gunicorn + uvicorn workers as the deploy user.
cat >/etc/systemd/system/${APP_NAME}.service <<EOF
[Unit]
Description=Carepoint HMS FastAPI backend
After=network.target

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
    --access-logfile /var/log/${APP_NAME}/access.log \\
    --error-logfile /var/log/${APP_NAME}/error.log \\
    --log-level info
Restart=on-failure
RestartSec=5
# Hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /var/log/${APP_NAME}
chown -R "${APP_USER}:${APP_USER}" /var/log/${APP_NAME}

# Log rotation for the gunicorn logs.
cat >/etc/logrotate.d/${APP_NAME} <<EOF
/var/log/${APP_NAME}/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 ${APP_USER} ${APP_USER}
    sharedscripts
    postrotate
        systemctl reload ${APP_NAME} >/dev/null 2>&1 || true
    endscript
}
EOF

# nginx vhost (only when a domain is configured).
if [[ -n "${APP_DOMAIN}" ]]; then
    cat >/etc/nginx/sites-available/${APP_NAME} <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${APP_DOMAIN};

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120;
        proxy_send_timeout 120;
    }

    location /static/ {
        alias ${APP_DIR}/app/static/;
        access_log off;
        expires 7d;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/${APP_NAME}
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl reload nginx
else
    warn "APP_DOMAIN not set — skipped nginx vhost. Set APP_DOMAIN=api.example.com and rerun for a public endpoint."
fi

systemctl daemon-reload
systemctl enable ${APP_NAME}.service

# ─── 9. SSL (Let's Encrypt) ───────────────────────────────────────────────────
if [[ -n "${APP_DOMAIN}" && "${ENABLE_HTTPS}" == "true" ]]; then
    if [[ -z "${LETSENCRYPT_EMAIL}" ]]; then
        warn "9/9  ENABLE_HTTPS=true but LETSENCRYPT_EMAIL is empty — skipping certbot."
    else
        log "9/9  Issuing Let's Encrypt certificate for ${APP_DOMAIN}"
        apt-get install -y certbot python3-certbot-nginx
        certbot --nginx --non-interactive --agree-tos \
            --email "${LETSENCRYPT_EMAIL}" \
            --domains "${APP_DOMAIN}" \
            --redirect || warn "certbot failed — DNS may not yet point to this droplet. Re-run after DNS propagates: certbot --nginx -d ${APP_DOMAIN}"
        systemctl enable --now certbot.timer
    fi
else
    log "9/9  HTTPS provisioning skipped (no domain or ENABLE_HTTPS=false)"
fi

log "✓ Provisioning complete."
echo
echo "Next steps:"
echo "  1. Edit ${ENV_FILE} — set DATABASE_URL, MASTER_DATABASE_URL, SECRET_KEY, DATABASE_ENCRYPTION_KEY."
echo "  2. Initialise the master DB:   sudo -u ${APP_USER} ${VENV_DIR}/bin/python -m app.init_db"
echo "  3. Start the service:          systemctl start ${APP_NAME}"
echo "  4. Check status / logs:        systemctl status ${APP_NAME} ; journalctl -u ${APP_NAME} -f"
echo "  5. Add the GitHub Actions deploy key to ${APP_HOME}/.ssh/authorized_keys (if not already)."
echo "  6. Add repo secrets in GitHub: DROPLET_HOST, DROPLET_USER=${APP_USER}, DROPLET_SSH_KEY (private half)."
