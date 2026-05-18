# Carepoint HMS — Production Deployment Guide

> **Version**: 2.0  
> **Last updated**: 2026-05-16  
> **Audience**: DevOps engineers, backend developers, system administrators

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Phase 1 — Database Preparation](#phase-1--database-preparation)
4. [Phase 2 — SSH Deploy Key](#phase-2--ssh-deploy-key)
5. [Phase 3 — Droplet Provisioning](#phase-3--droplet-provisioning)
6. [Phase 4 — Master Database Initialization](#phase-4--master-database-initialization)
7. [Phase 5 — GitHub CI/CD Configuration](#phase-5--github-cicd-configuration)
8. [Phase 6 — Deploying Code](#phase-6--deploying-code)
9. [Phase 7 — Operations & Maintenance](#phase-7--operations--maintenance)
10. [Security Reference](#security-reference)
11. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The Carepoint HMS backend runs on a single DigitalOcean droplet behind an Nginx
reverse proxy with automatic SSL. GitHub Actions handles the full CI/CD pipeline —
every push to `main` triggers linting, tests against an ephemeral Postgres, and (if
all checks pass) an automated SSH deploy to the production droplet.

```
Developer workstation
        │
        │  git push origin main
        ▼
GitHub Actions Runner (ubuntu-22.04)
   ┌────────────────────────────────────────────────┐
   │  Job 1: LINT                                   │
   │    └── ruff check app/                         │
   │                                                │
   │  Job 2: TEST                                   │
   │    ├── Spin up ephemeral Postgres 16           │
   │    ├── pip install -r requirements.txt         │
   │    └── pytest app/tests/integration            │
   │                                                │
   │  Job 3: DEPLOY (only if lint + test pass)      │
   │    ├── SSH into droplet as 'deploy' user       │
   │    ├── Run deploy_backend_droplet.sh deploy    │
   │    └── Smoke-test https://domain/health        │
   └────────────────────────────────────────────────┘
                        │
                        │  SSH (port 22)
                        ▼
DigitalOcean Droplet (Ubuntu 22.04 / 24.04)
   ┌────────────────────────────────────────────────┐
   │  Nginx (port 80/443)                           │
   │    ├── Let's Encrypt SSL (auto-renewal)        │
   │    ├── Rate limiting (30 req/s per IP)         │
   │    ├── Security headers (HSTS, X-Frame, etc.)  │
   │    └── Reverse proxy → 127.0.0.1:8005         │
   │                                                │
   │  systemd: carepoint_hms.service                │
   │    └── Gunicorn (3 workers)                    │
   │         └── Uvicorn ASGI workers               │
   │              └── FastAPI app (app.main:app)    │
   │                                                │
   │  /opt/carepoint_hms/                           │
   │    ├── .env           (runtime secrets)        │
   │    ├── .git/          (repo checkout)          │
   │    ├── venv/          (Python virtualenv)      │
   │    ├── deployments.log (audit trail)           │
   │    └── scripts/       (deploy + migration)     │
   └────────────────────────────────────────────────┘
                        │
                        │  PostgreSQL (port 25060)
                        ▼
DigitalOcean Managed PostgreSQL 16
   ├── carepoint_hms_master    (master database)
   ├── tenant_<code>_db        (per-tenant databases)
   ├── carepoint_admin user    (DDL / schema owner)
   └── carepoint_app user      (DML / read-write)
```

### Files Involved

| File | Where it runs | Purpose |
|------|---------------|---------|
| `scripts/deploy_backend_droplet.sh` | Droplet | Main script — handles provisioning, deploys, and rollback |
| `.github/workflows/deploy.yml` | GitHub Actions | CI/CD pipeline — lint, test, deploy, smoke test |
| `scripts/setup_postgres_do.sh` | DB Droplet | Self-hosted PostgreSQL setup (optional) |
| `/opt/carepoint_hms/.env` | Droplet (runtime) | Environment variables and secrets — **never committed to git** |

---

## Prerequisites

Before you begin, ensure you have:

| Requirement | Details |
|-------------|---------|
| DigitalOcean account | With a droplet and (optionally) managed Postgres |
| Droplet OS | Ubuntu 22.04 LTS or 24.04 LTS |
| Droplet size | Minimum **2 GB RAM** (4 GB recommended for production) |
| Domain name | Pointed at the droplet's IPv4 via an A record |
| GitHub repository | `https://github.com/nelson-ust/carepoint_hms.git` |
| SSH key for your laptop | Added to the droplet so you can SSH in as root |
| Terminal access | A local terminal (macOS Terminal, iTerm2, etc.) |

---

## Phase 1 — Database Preparation

**Goal**: Set up a PostgreSQL 16 database cluster that the application will connect
to for storing master data (tenants, subscriptions, SaaS admins) and per-tenant
clinical data.

### Option A: DigitalOcean Managed PostgreSQL (Recommended)

Managed Postgres handles automatic backups, failover, and security patching. This
is the recommended approach for production.

1. **Create the cluster**: In the DO console, go to *Databases → Create Database
   Cluster*. Choose PostgreSQL 16 in the same region as your app droplet.

2. **Create the master database**: Name it `carepoint_hms_master`. This is the
   central database where tenant records, subscription plans, SaaS admin accounts,
   and multi-tenant metadata are stored.

3. **Create two database users**:
   - `carepoint_admin` — Granted full owner privileges. Used by the application for
     schema DDL operations (CREATE TABLE, ALTER TABLE) during migrations and tenant
     provisioning. The `MASTER_DATABASE_URL` env var uses this user.
   - `carepoint_app` — Granted read/write (SELECT, INSERT, UPDATE, DELETE) only.
     Used by the application for day-to-day queries. The `DATABASE_URL` env var uses
     this user. This limits the blast radius if the application is compromised.

4. **Restrict trusted sources**: In the cluster settings, add only the droplet's
   **private IP** to the trusted sources list. This ensures the database is not
   reachable from the public internet.

5. **Copy the connection strings**: You'll need them for Phase 3. They look like:
   ```
   postgresql+psycopg2://carepoint_app:PASSWORD@private-db-host:25060/carepoint_hms_master?sslmode=require
   ```

### Option B: Self-Hosted PostgreSQL

If you prefer to manage Postgres yourself (e.g., for cost savings or compliance):

```bash
# From your laptop:
scp scripts/setup_postgres_do.sh root@DB_DROPLET_IP:~
ssh root@DB_DROPLET_IP "chmod +x setup_postgres_do.sh && ./setup_postgres_do.sh"
```

**What this script does:**
- Installs PostgreSQL 16 from the official apt repository
- Creates the `carepoint_admin` and `carepoint_app` users
- Creates the `carepoint_hms_master` database
- Configures `pg_hba.conf` for password authentication
- Sets up automated daily `pg_dump` backups to `/var/backups/postgresql/`
- Tunes `postgresql.conf` for a 2–4 GB RAM server

---

## Phase 2 — SSH Deploy Key

**Goal**: Create a dedicated SSH key pair so GitHub Actions can securely SSH into
the droplet without using your personal credentials.

On your **laptop** (not the droplet):

```bash
ssh-keygen -t ed25519 -C "github-actions-carepoint" -f ~/.ssh/carepoint_deploy -N ''
```

**What this does:**
- Generates a modern Ed25519 SSH key pair (faster and more secure than RSA)
- `-N ''` means no passphrase — required because GitHub Actions runs non-interactively
- `-C "github-actions-carepoint"` adds a comment so you can identify this key later

**Two files are created:**

| File | Contains | Goes where |
|------|----------|-----------|
| `~/.ssh/carepoint_deploy` | **Private** key | GitHub secret `DROPLET_SSH_KEY` (Phase 5) |
| `~/.ssh/carepoint_deploy.pub` | **Public** key | Droplet's `authorized_keys` (Phase 3) |

Before Phase 3, upload the public key to the droplet:

```bash
scp ~/.ssh/carepoint_deploy.pub root@YOUR_DROPLET_IP:~/carepoint_deploy.pub
```

---

## Phase 3 — Droplet Provisioning

**Goal**: Transform a fresh Ubuntu droplet into a fully configured, hardened
production server running the Carepoint HMS backend.

### 3.1 — Copy the script to the droplet

```bash
scp scripts/deploy_backend_droplet.sh root@YOUR_DROPLET_IP:~
```

### 3.2 — Run provisioning

```bash
ssh root@YOUR_DROPLET_IP

# On the droplet, run:
REPO_URL=https://github.com/nelson-ust/carepoint_hms.git \
DATABASE_URL='postgresql+psycopg2://carepoint_app:YOUR_PASS@DB_HOST:25060/carepoint_hms_master?sslmode=require' \
MASTER_DATABASE_URL='postgresql+psycopg2://carepoint_admin:YOUR_PASS@DB_HOST:25060/carepoint_hms_master?sslmode=require' \
APP_DOMAIN=api.carepointhms.com \
LETSENCRYPT_EMAIL=ops@carepointhms.com \
GITHUB_DEPLOY_PUBKEY="$(cat ~/carepoint_deploy.pub)" \
bash deploy_backend_droplet.sh provision
```

### 3.3 — What each provisioning step does

The `provision` mode executes 13 sequential steps. Each is **idempotent** — if the
script fails midway (e.g., DNS not propagated for SSL), you can fix the issue and
re-run safely.

#### Step 1: System Packages
Installs all operating system dependencies using `apt-get`:
- **Python 3.12** (from deadsnakes PPA if not in the default repo)
- **Nginx** — used as a reverse proxy in front of Gunicorn
- **Git** — to clone and pull the application repository
- **Build tools** (`build-essential`, `pkg-config`) — needed to compile Python C extensions like `psycopg2`
- **Database libraries** (`libpq-dev`) — PostgreSQL client libraries
- **Security tools** (`ufw`, `fail2ban`) — firewall and brute-force protection
- **Utilities** (`curl`, `jq`, `htop`, `openssl`, `postgresql-client`)

#### Step 2: Swap
Creates a **2 GB swap file** on disk. This is critical for small droplets (1–2 GB
RAM) because Python dependency installation and Gunicorn workers can temporarily
spike memory usage. Without swap, the OOM killer may terminate the `pip install`
process or a Gunicorn worker. The swap is permanent (added to `/etc/fstab`).

#### Step 3: Firewall + Security Hardening
Three layers of security are applied:

- **UFW Firewall**: Opens only ports 22 (SSH), 80 (HTTP), and 443 (HTTPS). All
  other inbound traffic is dropped.
- **fail2ban**: Monitors SSH login attempts and bans IPs after 5 failed attempts
  for 10 minutes. Prevents brute-force attacks on the SSH port.
- **SSH hardening**: Disables password-based SSH authentication and restricts root
  login to key-based only. This means only users with an authorized SSH key can
  connect.
- **Kernel sysctl tweaks**: Enables SYN cookies (prevents SYN flood attacks),
  disables ICMP redirects (prevents route hijacking), and enables reverse path
  filtering (prevents IP spoofing).

#### Step 4: Application User
Creates a dedicated non-root user called `deploy` that owns and runs the
application. This follows the principle of least privilege:
- The `deploy` user **cannot** install packages, modify system files, or read root-owned secrets
- Passwordless `sudo` is granted **only** for `systemctl restart/reload/status carepoint_hms`
- An SSH `authorized_keys` entry is added for the GitHub Actions deploy key

#### Step 5: Source Checkout
Clones the repository to `/opt/carepoint_hms` and checks out the specified branch
(defaults to `main`). On subsequent runs, it performs a hard reset to `origin/main`
to ensure the working tree matches the remote exactly.

#### Step 6: Python Virtualenv + Dependencies
Creates an isolated Python virtual environment at `/opt/carepoint_hms/venv` and
installs:
- All application dependencies from `requirements.txt`
- **Gunicorn** — the production WSGI/ASGI server
- **Uvicorn** (with `[standard]` extras) — the ASGI worker class that Gunicorn
  delegates to for async FastAPI support

The venv ensures the application's Python packages are isolated from the system
Python and cannot be disrupted by OS updates.

#### Step 7: Environment File (.env)
Generates `/opt/carepoint_hms/.env` with all runtime configuration. This file is:
- **Not in version control** — secrets never appear in the git history
- **Owned by deploy:deploy** with `chmod 600` — only the deploy user can read it
- **Loaded by systemd** via `EnvironmentFile=` — values are injected into the process
  environment without appearing in process listings (`ps aux`)
- **Never overwritten** on subsequent deploys — once created, you edit it manually

Two critical secrets are auto-generated using `openssl rand -hex 32`:
- `SECRET_KEY` — Used for JWT signing. Changing it invalidates all active sessions.
- `DATABASE_ENCRYPTION_KEY` — Used to encrypt/decrypt tenant database connection
  strings stored in the master DB. Changing it makes all existing encrypted strings
  unreadable (requires a re-encryption migration).

#### Step 8: systemd Service + Log Rotation
Installs a systemd service unit that:
- Runs Gunicorn with 3 Uvicorn workers, bound to `127.0.0.1:8005`
- Sets a 120-second request timeout and 30-second graceful shutdown
- Recycles workers after 1000 requests (`--max-requests`) to prevent memory leaks
- Restarts automatically on failure (up to 5 times within 60 seconds)
- Applies security sandboxing: `ProtectSystem=strict`, `ProtectHome=true`,
  `NoNewPrivileges=true`, `PrivateTmp=true`
- Raises file descriptor limits to 65536 (needed for many concurrent connections)

Log rotation is configured to:
- Rotate daily, keep 30 days, compress old logs
- Logs are written to `/var/log/carepoint_hms/access.log` and `error.log`

#### Step 9: Nginx Reverse Proxy
Configures Nginx as a reverse proxy that:
- Listens on ports 80 and 443
- Forwards all requests to `127.0.0.1:8005` (the Gunicorn backend)
- Adds **security headers**: `X-Frame-Options`, `X-Content-Type-Options`,
  `X-XSS-Protection`, `Referrer-Policy`, `Strict-Transport-Security`
- Applies **rate limiting**: 30 requests/second per IP with a burst queue of 60
  (prevents API abuse)
- Serves `/static/` files directly (bypasses Gunicorn for performance)
- Blocks access to sensitive paths (`.git`, `.env`, `.svn`)
- The `/health` endpoint is exempted from rate limiting and access logging so
  monitoring systems can poll frequently

#### Step 10: SSL Certificate
Uses **certbot** with the Nginx plugin to obtain a free Let's Encrypt SSL
certificate. This:
- Automatically modifies the Nginx config to redirect HTTP → HTTPS
- Installs a systemd timer that auto-renews the certificate before it expires
  (Let's Encrypt certs last 90 days; renewal happens at 60 days)
- Requires that DNS for `APP_DOMAIN` already points to the droplet's IP

#### Step 11: Database Migrations
Runs forward-only, non-destructive schema synchronization:
- `--sync-master` — Creates any new tables/columns in the master database without
  dropping existing data
- `--sync-tenants` — Applies the same to every provisioned tenant database
- Then runs all standalone migration scripts (`migrate_*.py`) which are individually
  idempotent (they use `IF NOT EXISTS` guards)

#### Step 12: Start Service
Restarts the systemd service and waits 3 seconds for it to initialize.

#### Step 13: Health Check
Polls `http://127.0.0.1:8005/health` up to 15 times (3-second intervals, 45
seconds total). If the service responds with a 200, the deployment is recorded as
`SUCCESS` in `deployments.log`. If it never becomes healthy, the script exits with
an error.

---

## Phase 4 — Master Database Initialization

**Goal**: Seed the master database with subscription plans, default roles, and the
initial SaaS super-admin account.

> **Only run this once**, on a brand-new database.

```bash
ssh root@YOUR_DROPLET_IP

# Initialize the master DB:
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db
```

**What `app.init_db` does (without flags):**
1. Drops and recreates the `public` schema in the master database
2. Creates all master-level tables (Tenant, SubscriptionPlan, SaaSAdmin, etc.)
3. Seeds default subscription plans (TRIAL, STARTER, PROFESSIONAL, ENTERPRISE)
4. Creates the default SaaS super-admin account

**Verify it worked:**

```bash
systemctl start carepoint_hms
curl -s http://127.0.0.1:8005/health | python3 -m json.tool
```

---

## Phase 5 — GitHub CI/CD Configuration

**Goal**: Configure GitHub so that every push to `main` automatically deploys to
production after passing lint and test checks.

### 5.1 — Repository Secrets

Navigate to: **GitHub → Repository → Settings → Secrets and variables → Actions → Secrets tab → New repository secret**

Add these three secrets:

| Secret Name | Value | Why it's a secret |
|-------------|-------|------------------|
| `DROPLET_HOST` | Your droplet's IPv4 address (e.g., `203.0.113.42`) | Prevents exposing your server IP in logs |
| `DROPLET_USER` | `deploy` | The SSH username |
| `DROPLET_SSH_KEY` | Full contents of `~/.ssh/carepoint_deploy` (the **private** half, including `-----BEGIN...` and `-----END...` lines) | SSH private key — must never be exposed |

### 5.2 — Repository Variables

Navigate to: **Settings → Secrets and variables → Actions → Variables tab → New repository variable**

| Variable Name | Value | Why it's a variable (not secret) |
|---------------|-------|---------------------------------|
| `DROPLET_DOMAIN` | `api.carepointhms.com` | Domain names are not sensitive; using a variable allows it to be referenced in `environment.url` (which doesn't support secrets) |

### 5.3 — Protected Environment (Optional but Recommended)

Navigate to: **Settings → Environments → New environment**

1. Name it `production`
2. Enable **Required reviewers** — adds a manual approval gate before each deploy
3. Optionally restrict deployment to the `main` branch only
4. Move the secrets from repository level to this environment for stricter scoping

This means: push to `main` → lint passes → tests pass → a team member approves →
deploy runs.

### 5.4 — Understanding the CI/CD Pipeline

The `.github/workflows/deploy.yml` file defines three jobs:

**Job 1: Lint**
- Runs `ruff check app/` to catch syntax errors, unused imports, and style issues
- Uses `|| true` so lint warnings don't block the deploy (you can remove this to
  make linting strict)

**Job 2: Test**
- Spins up an ephemeral Postgres 16 container as a GitHub Actions service
- Installs all Python dependencies
- Runs `pytest app/tests/integration -x` (stops at first failure)
- Uploads test results as a downloadable artifact (JUnit XML format)

**Job 3: Deploy** (only runs on push to `main`, after lint + test pass)
- Configures SSH credentials from the repository secrets
- SSHes into the droplet and runs `deploy_backend_droplet.sh deploy main`
- Performs a public smoke test against `https://DOMAIN/health`

---

## Phase 6 — Deploying Code

### Automatic Deployment (Recommended)

Simply push to `main`:

```bash
git add .
git commit -m "feat: add patient discharge summary endpoint"
git push origin main
```

Monitor progress at: **GitHub → Actions tab**

The pipeline takes approximately 2–4 minutes:
- Lint: ~20 seconds
- Test: ~1–2 minutes (depends on test count)
- Deploy: ~30–60 seconds (git pull + optional pip install + migrations + restart)
- Smoke test: ~5–15 seconds

### What the `deploy` mode does

When GitHub Actions (or a manual user) runs `deploy_backend_droplet.sh deploy main`,
it executes these steps:

1. **Save current SHA** — Stores the current commit hash in `.previous_sha` for
   rollback support
2. **Pull latest code** — `git fetch --all && git reset --hard origin/main`
3. **Smart dependency install** — Only runs `pip install` if `requirements.txt`
   changed between the old and new commit (saves ~15 seconds on most deploys)
4. **Schema migrations** — Runs `--sync-master` and `--sync-tenants` (non-destructive)
5. **Graceful restart** — `systemctl restart carepoint_hms`
6. **Health check** — Polls `/health` up to 10 times
7. **Auto-rollback** — If the health check fails, automatically reverts to the
   previous commit and restarts. If even the rollback fails, it exits with an error
   for manual intervention

### Manual Deployment (from the droplet)

```bash
ssh deploy@YOUR_DROPLET_IP
bash /opt/carepoint_hms/scripts/deploy_backend_droplet.sh deploy main
```

### Manual Deployment (from GitHub UI)

1. Go to **Actions → CI / CD Pipeline**
2. Click **Run workflow** (top right)
3. Select branch and environment
4. Click **Run workflow**

### Rollback

If a deploy causes issues that weren't caught by the health check:

```bash
ssh deploy@YOUR_DROPLET_IP
bash /opt/carepoint_hms/scripts/deploy_backend_droplet.sh rollback
```

This reverts to the commit stored in `.previous_sha`, re-installs its dependencies,
restarts the service, and health-checks the result.

---

## Phase 7 — Operations & Maintenance

### Service Management

```bash
# Check if the service is running
systemctl status carepoint_hms

# Restart the service
sudo systemctl restart carepoint_hms

# View live logs (Ctrl+C to stop)
journalctl -u carepoint_hms -f

# View last 200 log lines
journalctl -u carepoint_hms -n 200 --no-pager
```

### Log Files

```bash
# Gunicorn access log (HTTP requests)
tail -f /var/log/carepoint_hms/access.log

# Gunicorn error log (application errors, tracebacks)
tail -f /var/log/carepoint_hms/error.log

# Deployment audit trail
cat /opt/carepoint_hms/deployments.log
```

### Environment Variables

```bash
# Edit runtime configuration
nano /opt/carepoint_hms/.env

# Restart to pick up changes
sudo systemctl restart carepoint_hms
```

### Database Operations

```bash
# Forward-only schema migration (safe — no data loss)
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db --sync-master
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db --sync-tenants

# Destructive reset (CAUTION: drops all data)
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db

# Provision a new tenant manually
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db \
  --provision-tenant DEMO --tenant-name "Demo Hospital" --tenant-domain demo.example.com
```

### SSL Certificate

```bash
# Check renewal timer
systemctl list-timers certbot.timer

# View current certificates
certbot certificates

# Force renewal (if needed)
certbot renew --force-renewal

# Re-issue after DNS change
certbot --nginx -d api.carepointhms.com
```

---

## Security Reference

| Layer | Measure | Details |
|-------|---------|---------|
| **Network** | UFW firewall | Only ports 22, 80, 443 open |
| **Network** | fail2ban | Bans IPs after 5 failed SSH attempts |
| **Network** | Nginx rate limiting | 30 req/s per IP, burst of 60 |
| **SSH** | Key-only auth | Password authentication disabled |
| **SSH** | Root restriction | Root login limited to key-based only |
| **OS** | Kernel hardening | SYN cookies, anti-spoofing, no redirects |
| **App** | Non-root user | Service runs as `deploy`, not root |
| **App** | Scoped sudo | Only `systemctl restart/reload/status` allowed |
| **App** | systemd sandbox | `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true` |
| **App** | Worker recycling | Gunicorn recycles workers every 1000 requests |
| **App** | Secrets isolation | `.env` is `chmod 600`, loaded via `EnvironmentFile=` |
| **Web** | HTTPS only | HTTP redirects to HTTPS via certbot |
| **Web** | Security headers | HSTS, X-Frame-Options, CSP, XSS protection |
| **Web** | Path blocking | `.git`, `.env`, `.svn` return 404 |
| **DB** | Trusted sources | Postgres only accepts connections from the droplet |
| **DB** | Least privilege | `carepoint_app` has DML only, `carepoint_admin` has DDL |
| **CI** | Encrypted secrets | SSH key stored as GitHub encrypted secret |

---

## Troubleshooting

### Service won't start

```bash
# Check the error:
journalctl -u carepoint_hms -n 100 --no-pager

# Common causes:
# 1. .env is missing or malformed
# 2. DATABASE_URL has wrong credentials
# 3. Python dependency failed to install (check venv)
```

### Deploy fails with "Permission denied (publickey)"

The GitHub Actions secret `DROPLET_SSH_KEY` doesn't match the public key on the
droplet. Fix:

```bash
# On your laptop — verify the key pair matches:
ssh-keygen -l -f ~/.ssh/carepoint_deploy      # private
ssh-keygen -l -f ~/.ssh/carepoint_deploy.pub   # public
# Fingerprints must match.

# Re-paste the PRIVATE key contents into the DROPLET_SSH_KEY secret on GitHub.
# Ensure you copy the ENTIRE file including -----BEGIN/END----- lines.
```

### Deploy fails with "sudo: a password is required"

The sudoers file was modified or deleted. Fix (as root on the droplet):

```bash
cat >/etc/sudoers.d/deploy-deploy <<EOF
deploy ALL=(root) NOPASSWD: /bin/systemctl restart carepoint_hms, /bin/systemctl reload carepoint_hms, /bin/systemctl status carepoint_hms, /usr/bin/systemctl restart carepoint_hms, /usr/bin/systemctl reload carepoint_hms, /usr/bin/systemctl status carepoint_hms
EOF
chmod 440 /etc/sudoers.d/deploy-deploy
```

### Health check fails after deploy

The deploy script **automatically rolls back** when this happens. Check what went
wrong:

```bash
# View the error that caused the health check failure:
journalctl -u carepoint_hms -n 200 --no-pager | tail -50

# Check the deployment audit log:
cat /opt/carepoint_hms/deployments.log
# Look for entries with status=ROLLED_BACK or status=FAILED
```

### certbot failed during provisioning

DNS must be pointing at the droplet before certbot can verify domain ownership.

```bash
# Check if DNS resolves to your droplet IP:
dig +short api.carepointhms.com

# Once DNS is correct, re-run certbot:
certbot --nginx -d api.carepointhms.com
```

### Tenant approval hangs or times out

If using managed Postgres, `CREATE DATABASE` may be blocked by the provider. The
application falls back to schema-per-tenant mode. Verify:

```bash
journalctl -u carepoint_hms | grep -i "schema-per-tenant"
```

### High memory usage

```bash
# Check current memory:
free -h

# If swap is heavily used, consider upgrading the droplet or reducing workers:
# Edit /etc/systemd/system/carepoint_hms.service, change --workers 3 to --workers 2
systemctl daemon-reload
systemctl restart carepoint_hms
```
