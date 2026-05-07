# Carepoint HMS — Deployment Runbook (DigitalOcean + GitHub Actions)

This guide gets you from "fresh DigitalOcean droplet" to "every push to `main` auto-deploys to production". Reading time: ~5 minutes. Setup time: ~20 minutes.

## What you get

```
GitHub Actions on push to main
        │
        │ 1. run pytest against an ephemeral Postgres in CI
        │ 2. SSH into the droplet as `deploy`
        │ 3. run scripts/deploy.sh (pull, sync schema, restart)
        │ 4. smoke-test https://your-domain/health
        ▼
DigitalOcean Droplet (Ubuntu 22.04)
  ├── /opt/carepoint_hms/                  ← git checkout
  │     ├── venv/                          ← Python virtualenv
  │     ├── .env                           ← runtime secrets (NOT in git)
  │     └── scripts/deploy.sh              ← invoked by GH Actions
  ├── systemd: carepoint_hms.service       ← gunicorn + uvicorn workers
  └── nginx: api.your-domain.com           ← reverse proxy + Let's Encrypt SSL
        │
        ▼
DigitalOcean Managed Postgres
  └── carepoint_hms_master  (schema-per-tenant)
```

## Files involved

| File | Where it runs | Purpose |
|------|---------------|---------|
| `scripts/provision_droplet.sh` | once on a fresh droplet, as root | installs system deps, creates `deploy` user, clones repo, sets up systemd + nginx |
| `scripts/setup_postgres_do.sh` | once on the Postgres droplet (or skip if using DO Managed Postgres) | installs PostgreSQL 16, creates `carepoint_admin` + `carepoint_app` users + `carepoint_hms_master` DB |
| `scripts/deploy.sh` | every CI deploy, as `deploy` user | `git pull` → `pip install -r requirements.txt` → schema sync → `systemctl restart` → health-check |
| `.github/workflows/deploy.yml` | GitHub Actions | runs tests on every PR, deploys on push to `main` |

---

## 1. Provision the Postgres host

You have two paths. Pick one.

**1a. Use DigitalOcean Managed PostgreSQL (recommended for production):**
1. Create a Managed Postgres cluster (`postgres:16`) in the same region as your app droplet.
2. In the DO console, create the database `carepoint_hms_master`.
3. Create two users: `carepoint_admin` (owner) and `carepoint_app` (read/write).
4. Restrict the cluster's "Trusted Sources" to the app droplet's private IP.
5. Note the connection string — you'll paste it into `.env` later.

**1b. Self-host Postgres on a separate droplet:**

```bash
scp scripts/setup_postgres_do.sh root@DB_DROPLET_IP:~
ssh root@DB_DROPLET_IP "chmod +x setup_postgres_do.sh && ./setup_postgres_do.sh"
```

That script (already in this repo) installs PostgreSQL 16, creates the users and the master DB, and sets up automated daily backups.

---

## 2. Create the GitHub Actions deploy SSH key

On your laptop:

```bash
ssh-keygen -t ed25519 -C "github-actions-carepoint" -f ~/.ssh/carepoint_deploy -N ''
```

Two files appear:
- `~/.ssh/carepoint_deploy`        — **private** half. Copy its contents into the GitHub secret `DROPLET_SSH_KEY` (Step 5).
- `~/.ssh/carepoint_deploy.pub`    — **public** half. Pass it to `provision_droplet.sh` as `GITHUB_DEPLOY_PUBKEY` so the droplet trusts GH Actions.

---

## 3. Provision the application droplet

1. Spin up a DigitalOcean Ubuntu 22.04 or 24.04 droplet (Basic, 2 GB RAM is enough to start).
2. Add your laptop's SSH key to the droplet (DO console → Settings → Security → SSH keys).
3. From your laptop:

> **Python version**
> The provisioning script defaults to **Python 3.12** — the current stable release, ~10–25% faster than 3.10 and what CI tests against. On Ubuntu 22.04 it auto-adds the `deadsnakes` PPA to fetch 3.12 (3.10 is the base repo). On Ubuntu 24.04, 3.12 is in the base repo and no PPA is needed. Override with `PYTHON_VERSION=3.11` (Ubuntu 24.04 default) or `PYTHON_VERSION=3.10` if you have a pinned dependency that lacks 3.12 wheels — keep `.github/workflows/deploy.yml` in sync if you do.

```bash
scp scripts/provision_droplet.sh root@APP_DROPLET_IP:~

# Required env vars:
#   REPO_URL            — your GitHub repo URL (HTTPS or SSH)
#   APP_DOMAIN          — e.g. api.yourdomain.com  (skip for ip-only access)
#   LETSENCRYPT_EMAIL   — your email (for SSL cert renewals)
#   GITHUB_DEPLOY_PUBKEY — contents of ~/.ssh/carepoint_deploy.pub from step 2
#
# Optional:
#   APP_USER            — defaults to "deploy"
#   APP_PORT            — defaults to 8005
#   APP_WORKERS         — defaults to 3
#   ENABLE_HTTPS        — defaults to true; set to false to skip certbot

ssh root@APP_DROPLET_IP "chmod +x provision_droplet.sh && \
  REPO_URL=https://github.com/YOURUSER/carepoint_hms.git \
  APP_DOMAIN=api.yourdomain.com \
  LETSENCRYPT_EMAIL=ops@yourdomain.com \
  GITHUB_DEPLOY_PUBKEY='$(cat ~/.ssh/carepoint_deploy.pub)' \
  ./provision_droplet.sh"
```

The script is idempotent — if it fails part-way (DNS not propagated, missing arg, etc.) just re-run it after fixing the issue.

---

## 4. Fill in `.env` and bootstrap the master DB

SSH to the droplet:

```bash
ssh root@APP_DROPLET_IP

# Edit the runtime config
nano /opt/carepoint_hms/.env
```

Set at minimum:

```dotenv
CAREPOINT_HMS_ENVIRONMENT=production
CAREPOINT_HMS_DATABASE_URL=postgresql+psycopg2://carepoint_app:PASSWORD@DB_HOST:5432/carepoint_hms_master?sslmode=require
CAREPOINT_HMS_MASTER_DATABASE_URL=postgresql+psycopg2://carepoint_admin:PASSWORD@DB_HOST:5432/carepoint_hms_master?sslmode=require
CAREPOINT_HMS_SECRET_KEY=$(openssl rand -hex 32)
CAREPOINT_HMS_DATABASE_ENCRYPTION_KEY=$(openssl rand -hex 32)
```

Initialise the master DB (drops + recreates the public schema, seeds plans + the default SaaS admin):

```bash
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db
```

Start the service:

```bash
systemctl start carepoint_hms
systemctl status carepoint_hms        # should be "active (running)"
journalctl -u carepoint_hms -f        # tail logs
curl -s http://127.0.0.1:8005/health  # should return JSON
```

If you set `APP_DOMAIN`, the public URL is now live:

```bash
curl -s https://api.yourdomain.com/health
```

---

## 5. Add GitHub repo secrets

In your repo on GitHub, go to **Settings → Secrets and variables → Actions → New repository secret** and create:

| Secret | Value |
|--------|-------|
| `DROPLET_HOST` | the droplet's IPv4 address or DNS hostname (e.g. `203.0.113.10`) |
| `DROPLET_USER` | `deploy` (or whatever you set as `APP_USER` during provisioning) |
| `DROPLET_SSH_KEY` | contents of `~/.ssh/carepoint_deploy` (the **private** half) |
| `DROPLET_DOMAIN` | `api.yourdomain.com` (used by the post-deploy smoke test) |

Optional — only needed if you also want to set per-environment things via Actions UI:
- Create an environment named `production` under **Settings → Environments**, attach the secrets there, and require manual approvals if you want a gate before each deploy.

---

## 6. Push to `main`

```bash
git push origin main
```

GitHub Actions will:

1. Spin up an Ubuntu runner with a throwaway Postgres.
2. Run `pytest app/tests/integration -x` against it.
3. SSH into your droplet and run `bash /opt/carepoint_hms/scripts/deploy.sh main`.
4. Smoke-test `https://api.yourdomain.com/health`.

The whole pipeline takes 2–4 minutes. Watch it in the **Actions** tab.

---

## Operations cheatsheet

```bash
# Status / logs
systemctl status carepoint_hms
journalctl -u carepoint_hms -f
tail -f /var/log/carepoint_hms/error.log

# Manual deploy from the droplet (skip CI)
sudo -u deploy /opt/carepoint_hms/scripts/deploy.sh main

# Forward-migrate schema only (no data loss)
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db --sync-master
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db --sync-tenants

# Wipe + reinitialise the master DB (DESTRUCTIVE — data loss!)
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db

# Provision a tenant out of band (rare; normally done via /api/v1/tenants/{id}/approve)
sudo -u deploy /opt/carepoint_hms/venv/bin/python -m app.init_db \
  --provision-tenant DEMO --tenant-name "Demo Hospital" --tenant-domain demo.example.com

# Roll back to a previous commit
cd /opt/carepoint_hms
sudo -u deploy git checkout <SHA>
sudo /bin/systemctl restart carepoint_hms
```

---

## Troubleshooting

**`systemctl status carepoint_hms` shows "failed"**
- Check `journalctl -u carepoint_hms -n 100`.
- 9/10 times it's a missing or malformed `.env` — `CAREPOINT_HMS_DATABASE_URL` not set, or contains an unescaped `%` etc.

**Deploy step fails with `Permission denied (publickey)`**
- The GH Actions secret `DROPLET_SSH_KEY` doesn't match the public key in `/home/deploy/.ssh/authorized_keys`. Re-paste the *private* half of the key into the secret.

**Deploy step fails with `sudo: a password is required`**
- The sudoers file `/etc/sudoers.d/deploy-deploy` may have been edited. The provisioning script writes a tightly scoped rule that allows only `systemctl restart carepoint_hms`. Re-run `provision_droplet.sh` to restore it.

**Tenant `/approve` endpoint hangs or times out**
- If you're on managed Postgres, the `CREATE DATABASE` step inside `provision_tenant` will fail and fall back to schema-per-tenant. That fallback is silent in normal logs — confirm it via `journalctl -u carepoint_hms` and look for `Falling back to schema-per-tenant`.
- Check the `connect_timeout` is not being hit: `tail -f /var/log/carepoint_hms/error.log` while you re-trigger the approval.

**`certbot` failed during provisioning**
- Make sure DNS for `APP_DOMAIN` is already pointing at the droplet. Once it is, re-run: `certbot --nginx -d api.yourdomain.com`.

---

## Security notes

- The `deploy` user has passwordless sudo only for `systemctl restart carepoint_hms` and `systemctl status carepoint_hms`. It cannot install packages or read root files.
- The runtime `.env` lives at `/opt/carepoint_hms/.env`, owned `deploy:deploy`, mode `600`. It is loaded by systemd via `EnvironmentFile=` so its values never appear in process lists.
- UFW is enabled by `provision_droplet.sh` and only allows ports 22, 80, 443.
- `fail2ban` is running with default jails (SSH bans after 5 failed auth attempts).
- All secrets used by GitHub Actions are stored as encrypted repo secrets and only decrypted on the runner mid-job.
