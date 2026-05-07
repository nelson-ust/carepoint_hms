#!/usr/bin/env bash
# =============================================================================
# Carepoint HMS — Production PostgreSQL Setup (DigitalOcean Ubuntu 22.04/24.04)
# =============================================================================
# Usage (from your local machine):
#   scp scripts/setup_postgres_do.sh root@DROPLET_IP:~
#   ssh root@DROPLET_IP "chmod +x setup_postgres_do.sh && ./setup_postgres_do.sh"
#
# Re-runnable: safe to execute multiple times on the same server.
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
# REQUIRED: change DB_PASSWORD before running — script aborts if left as default.
DB_SUPERUSER="carepoint_admin"        # Postgres owner / CREATEDB user
DB_APP_USER="carepoint_app"           # Lower-privilege app connection user
DB_PASSWORD="Jaiden@oct2019"   # ← MUST CHANGE — will abort if not changed
DB_APP_PASSWORD="Jaiden@oct2019"  # ← MUST CHANGE
DB_NAME="carepoint_hms_master"
PG_VERSION="16"

# OS user that will own the backup scripts and cron jobs (non-root)
OS_DBA_USER="pgdba"

# Lock PostgreSQL access to a specific CIDR (your Render IP / app server IP).
# "0.0.0.0/0" permits all — acceptable during initial setup only.
ALLOWED_CLIENT_CIDR="0.0.0.0/0"

# Automated daily backup directory on the Droplet.
BACKUP_DIR="/var/backups/carepoint_pg"

# ─── COLOURS ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}══════════════════════════════════════════${RESET}"; \
            echo -e "${BOLD} $*${RESET}"; \
            echo -e "${BOLD}══════════════════════════════════════════${RESET}"; }

# ─── PRE-FLIGHT CHECKS ────────────────────────────────────────────────────────
step "Pre-flight checks"

[[ $EUID -ne 0 ]] && error "Run as root: sudo bash $0"

# Abort on default/unchanged passwords
[[ "$DB_PASSWORD"     == "CHANGE_ME_STRONG_PWD" ]] && \
    error "Set DB_PASSWORD to a strong secret before running."
[[ "$DB_APP_PASSWORD" == "CHANGE_ME_APP_PWD" ]] && \
    error "Set DB_APP_PASSWORD to a strong secret before running."

# Minimum password length (12 chars)
[[ ${#DB_PASSWORD} -lt 12 ]] && \
    error "DB_PASSWORD must be at least 12 characters."
[[ ${#DB_APP_PASSWORD} -lt 12 ]] && \
    error "DB_APP_PASSWORD must be at least 12 characters."

# Ubuntu only
. /etc/os-release
[[ "$ID" != "ubuntu" ]] && error "This script supports Ubuntu only (got: $ID)."
[[ "${VERSION_ID}" < "22.04" ]] && \
    error "Ubuntu 22.04+ required (got: ${VERSION_ID})."

success "All pre-flight checks passed"

# ─── STEP 1: System Update + Essential Packages ───────────────────────────────
step "Step 1/9 — System update and essential packages"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y \
    curl gnupg lsb-release ufw fail2ban \
    unattended-upgrades apt-listchanges \
    logrotate htop vim-tiny ntp

# Enable automatic security updates
cat > /etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
echo 'APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";' > /etc/apt/apt.conf.d/20auto-upgrades

systemctl enable unattended-upgrades --now
success "System updated and automatic security patching enabled"

# ─── STEP 2: Add Swap Space (prevents OOM on low-memory droplets) ─────────────
step "Step 2/9 — Configuring swap space"

if [[ ! -f /swapfile ]]; then
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    SWAP_SIZE_GB=$(( (TOTAL_RAM_KB / 1024 / 1024) * 2 ))
    [[ $SWAP_SIZE_GB -lt 2 ]] && SWAP_SIZE_GB=2
    [[ $SWAP_SIZE_GB -gt 8 ]] && SWAP_SIZE_GB=8
    fallocate -l "${SWAP_SIZE_GB}G" /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -qxF '/swapfile none swap sw 0 0' /etc/fstab || \
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -w vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.d/99-carepoint.conf
    success "Swap: ${SWAP_SIZE_GB}GB created"
else
    info "Swap already exists — skipping"
fi

# ─── STEP 3: Create Non-Root DBA OS User ──────────────────────────────────────
step "Step 3/9 — Creating OS DBA user '${OS_DBA_USER}'"

if ! id "${OS_DBA_USER}" &>/dev/null; then
    useradd -m -s /bin/bash -G sudo "${OS_DBA_USER}"
    success "OS user '${OS_DBA_USER}' created"
else
    info "OS user '${OS_DBA_USER}' already exists"
fi

# ─── STEP 4: SSH Hardening ────────────────────────────────────────────────────
step "Step 4/9 — Hardening SSH"

SSHD_CONF="/etc/ssh/sshd_config"
cp "${SSHD_CONF}" "${SSHD_CONF}.bak.$(date +%Y%m%d_%H%M%S)"

# Apply production SSH settings
declare -A SSH_SETTINGS=(
    ["PermitRootLogin"]="prohibit-password"
    ["PasswordAuthentication"]="no"
    ["PubkeyAuthentication"]="yes"
    ["PermitEmptyPasswords"]="no"
    ["X11Forwarding"]="no"
    ["MaxAuthTries"]="3"
    ["LoginGraceTime"]="30"
    ["ClientAliveInterval"]="300"
    ["ClientAliveCountMax"]="2"
    ["Protocol"]="2"
)
for key in "${!SSH_SETTINGS[@]}"; do
    val="${SSH_SETTINGS[$key]}"
    if grep -q "^${key}" "${SSHD_CONF}"; then
        sed -i "s/^${key}.*/${key} ${val}/" "${SSHD_CONF}"
    else
        echo "${key} ${val}" >> "${SSHD_CONF}"
    fi
done

sshd -t && systemctl reload sshd
success "SSH hardened (root password login disabled)"

# ─── STEP 5: Install PostgreSQL ───────────────────────────────────────────────
step "Step 5/9 — Installing PostgreSQL ${PG_VERSION}"

if ! command -v psql &>/dev/null; then
    install -d /usr/share/postgresql-common/pgdg
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg

    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] \
https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list

    apt-get update -y
    apt-get install -y "postgresql-${PG_VERSION}" "postgresql-client-${PG_VERSION}"
    success "PostgreSQL ${PG_VERSION} installed"
else
    info "PostgreSQL already installed — skipping"
fi

systemctl enable postgresql --now
success "PostgreSQL running"

# ─── STEP 6: PostgreSQL Configuration ────────────────────────────────────────
step "Step 6/9 — Tuning PostgreSQL for production"

PG_CONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"
PG_HBA="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"

# Detect RAM for tuning
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
SHARED_BUFFERS_MB=$(( TOTAL_RAM_MB / 4 ))
EFFECTIVE_CACHE_MB=$(( TOTAL_RAM_MB * 3 / 4 ))
WORK_MEM_MB=$(( TOTAL_RAM_MB / 50 ))
[[ $WORK_MEM_MB -lt 4 ]] && WORK_MEM_MB=4

apply_pg_setting() {
    local key=$1 val=$2
    if grep -q "^#*${key}" "${PG_CONF}"; then
        sed -i "s|^#*${key}.*|${key} = ${val}|" "${PG_CONF}"
    else
        echo "${key} = ${val}" >> "${PG_CONF}"
    fi
}

apply_pg_setting "listen_addresses"               "'*'"
apply_pg_setting "max_connections"                "200"
apply_pg_setting "shared_buffers"                 "${SHARED_BUFFERS_MB}MB"
apply_pg_setting "effective_cache_size"           "${EFFECTIVE_CACHE_MB}MB"
apply_pg_setting "work_mem"                       "${WORK_MEM_MB}MB"
apply_pg_setting "maintenance_work_mem"           "64MB"
apply_pg_setting "wal_buffers"                    "16MB"
apply_pg_setting "checkpoint_completion_target"   "0.9"
apply_pg_setting "random_page_cost"               "1.1"
apply_pg_setting "effective_io_concurrency"       "200"
apply_pg_setting "ssl"                            "on"
apply_pg_setting "ssl_min_protocol_version"       "'TLSv1.2'"
apply_pg_setting "log_connections"                "on"
apply_pg_setting "log_disconnections"             "on"
apply_pg_setting "log_min_duration_statement"     "1000"
apply_pg_setting "log_line_prefix"                "'%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '"
apply_pg_setting "log_timezone"                   "'UTC'"
apply_pg_setting "timezone"                       "'UTC'"
apply_pg_setting "idle_in_transaction_session_timeout" "30000"
apply_pg_setting "statement_timeout"              "300000"

# pg_hba.conf — tighten auth
cat > "${PG_HBA}" <<HBA
# TYPE  DATABASE        USER                    ADDRESS                 METHOD
# Local connections (Unix socket)
local   all             postgres                                        peer
local   all             ${DB_SUPERUSER}                                 peer
local   all             all                                             md5

# IPv4 localhost
host    all             all                     127.0.0.1/32            scram-sha-256

# IPv6 localhost
host    all             all                     ::1/128                 scram-sha-256

# Remote application server
host    ${DB_NAME}      ${DB_APP_USER}          ${ALLOWED_CLIENT_CIDR}  scram-sha-256
host    all             ${DB_SUPERUSER}         ${ALLOWED_CLIENT_CIDR}  scram-sha-256
HBA

systemctl restart postgresql
success "PostgreSQL tuned (shared_buffers=${SHARED_BUFFERS_MB}MB, work_mem=${WORK_MEM_MB}MB)"

# ─── STEP 7: Create Users and Database ───────────────────────────────────────
step "Step 7/9 — Creating database users and master database"

sudo -u postgres psql <<EOSQL
-- Admin user: owns the master DB, can CREATE DATABASE for tenants
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_SUPERUSER}') THEN
        CREATE USER ${DB_SUPERUSER} WITH PASSWORD '${DB_PASSWORD}' CREATEDB LOGIN;
    ELSE
        ALTER USER ${DB_SUPERUSER} WITH PASSWORD '${DB_PASSWORD}' CREATEDB LOGIN;
    END IF;
END
\$\$;

-- App user: lower-privilege connection user for the running application
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_APP_USER}') THEN
        CREATE USER ${DB_APP_USER} WITH PASSWORD '${DB_APP_PASSWORD}' LOGIN;
    ELSE
        ALTER USER ${DB_APP_USER} WITH PASSWORD '${DB_APP_PASSWORD}' LOGIN;
    END IF;
END
\$\$;

-- Create master database (idempotent)
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_SUPERUSER} ENCODING UTF8 LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec

-- Grant app user access to master DB
GRANT CONNECT ON DATABASE ${DB_NAME} TO ${DB_APP_USER};
EOSQL

# Grant schema-level rights to app user inside the master DB
sudo -u postgres psql -d "${DB_NAME}" <<EOSQL
GRANT USAGE ON SCHEMA public TO ${DB_APP_USER};
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${DB_APP_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${DB_APP_USER};
EOSQL

success "Users '${DB_SUPERUSER}' and '${DB_APP_USER}' created, database '${DB_NAME}' ready"

# ─── STEP 8: Automated Backups ────────────────────────────────────────────────
step "Step 8/9 — Setting up automated daily backups"

mkdir -p "${BACKUP_DIR}"
chown postgres:postgres "${BACKUP_DIR}"
chmod 750 "${BACKUP_DIR}"

# Backup script
cat > /usr/local/bin/carepoint_pg_backup.sh <<BACKUP
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="${BACKUP_DIR}"
TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="\${BACKUP_DIR}/carepoint_hms_master_\${TIMESTAMP}.dump"

pg_dump -Fc -U postgres "${DB_NAME}" > "\${BACKUP_FILE}"
gzip "\${BACKUP_FILE}"

# Keep only last 14 daily backups
find "\${BACKUP_DIR}" -name "*.dump.gz" -mtime +14 -delete

echo "Backup complete: \${BACKUP_FILE}.gz"
BACKUP
chmod +x /usr/local/bin/carepoint_pg_backup.sh

# Schedule daily at 02:00 UTC
CRON_JOB="0 2 * * * postgres /usr/local/bin/carepoint_pg_backup.sh >> /var/log/carepoint_pg_backup.log 2>&1"
( crontab -u postgres -l 2>/dev/null | grep -v carepoint_pg_backup || true; echo "$CRON_JOB" ) \
    | crontab -u postgres -
success "Daily backup scheduled at 02:00 UTC → ${BACKUP_DIR}"

# ─── STEP 9: Firewall + Fail2Ban ──────────────────────────────────────────────
step "Step 9/9 — Firewall and intrusion prevention"

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH

if [[ "${ALLOWED_CLIENT_CIDR}" == "0.0.0.0/0" ]]; then
    ufw allow 5432/tcp
    warn "Port 5432 open to ALL IPs — lock ALLOWED_CLIENT_CIDR down before go-live."
else
    ufw allow from "${ALLOWED_CLIENT_CIDR}" to any port 5432
    info "Port 5432 restricted to ${ALLOWED_CLIENT_CIDR}"
fi
ufw --force enable

# Fail2Ban: SSH + PostgreSQL brute-force protection
cat > /etc/fail2ban/jail.local <<'F2B'
[DEFAULT]
bantime   = 6h
findtime  = 10m
maxretry  = 4
banaction = ufw

[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
backend  = %(syslog_backend)s

[postgresql]
enabled  = true
port     = 5432
filter   = postgresql
logpath  = /var/log/postgresql/postgresql-*.log
maxretry = 5
F2B

cat > /etc/fail2ban/filter.d/postgresql.conf <<'PGF'
[Definition]
failregex = ^.*FATAL:.*password authentication failed for user.*$
            ^.*FATAL:.*pg_hba.conf rejects connection for host.*$
ignoreregex =
PGF

systemctl enable fail2ban --now
systemctl restart fail2ban
success "UFW and Fail2Ban configured"

# ─── LOGROTATE FOR PG BACKUPS ─────────────────────────────────────────────────
cat > /etc/logrotate.d/carepoint_pg_backup <<'LR'
/var/log/carepoint_pg_backup.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
}
LR

# ─── VERIFY ───────────────────────────────────────────────────────────────────
systemctl is-active --quiet postgresql || error "PostgreSQL is not running!"

DROPLET_IP=$(curl -s --connect-timeout 5 http://checkip.amazonaws.com/ 2>/dev/null \
    || hostname -I | awk '{print $1}')

# ─── DONE ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║   Carepoint HMS — PostgreSQL Production Setup ✓        ║${RESET}"
echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}Droplet IP:${RESET}       ${DROPLET_IP}"
echo -e "  ${BOLD}PostgreSQL:${RESET}       ${PG_VERSION}"
echo -e "  ${BOLD}Database:${RESET}         ${DB_NAME}"
echo -e "  ${BOLD}Admin user:${RESET}       ${DB_SUPERUSER}  (CREATEDB — for provisioning)"
echo -e "  ${BOLD}App user:${RESET}         ${DB_APP_USER}   (DML only — for FastAPI)"
echo -e "  ${BOLD}Daily backups:${RESET}    ${BACKUP_DIR}  (14-day retention)"
echo ""
echo -e "${BOLD}─── .env / Render Environment Variables ───────────────────────${RESET}"
echo ""
echo "# Admin connection (used by init_db and tenant provisioning)"
echo "CAREPOINT_HMS_MASTER_DATABASE_URL=postgresql+psycopg2://${DB_SUPERUSER}:${DB_PASSWORD}@${DROPLET_IP}:5432/${DB_NAME}?sslmode=require"
echo "MASTER_DATABASE_URL=postgresql+psycopg2://${DB_SUPERUSER}:${DB_PASSWORD}@${DROPLET_IP}:5432/${DB_NAME}?sslmode=require"
echo ""
echo "# App connection (used by FastAPI at runtime)"
echo "CAREPOINT_HMS_DATABASE_URL=postgresql+psycopg2://${DB_APP_USER}:${DB_APP_PASSWORD}@${DROPLET_IP}:5432/${DB_NAME}?sslmode=require"
echo "DATABASE_URL=postgresql+psycopg2://${DB_APP_USER}:${DB_APP_PASSWORD}@${DROPLET_IP}:5432/${DB_NAME}?sslmode=require"
echo ""
echo "CAREPOINT_HMS_POSTGRES_SERVER=${DROPLET_IP}"
echo "CAREPOINT_HMS_POSTGRES_PORT=5432"
echo "CAREPOINT_HMS_POSTGRES_USER=${DB_SUPERUSER}"
echo "CAREPOINT_HMS_POSTGRES_PASSWORD=${DB_PASSWORD}"
echo "CAREPOINT_HMS_POSTGRES_DB=${DB_NAME}"
echo ""
echo -e "${YELLOW}${BOLD}Post-install checklist:${RESET}"
echo -e "  1. Copy the env vars above into Render environment settings"
echo -e "  2. Lock ALLOWED_CLIENT_CIDR to your Render static outbound IP"
echo -e "  3. Run: python -m app.init_db   (creates master tables + seeds)"
echo -e "  4. Test: psql \"postgresql://${DB_SUPERUSER}:***@${DROPLET_IP}:5432/${DB_NAME}?sslmode=require\""
echo -e "  5. Verify daily backup: /usr/local/bin/carepoint_pg_backup.sh"
echo ""
