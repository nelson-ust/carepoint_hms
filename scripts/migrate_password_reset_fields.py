"""
Migration: add password-reset token columns.

Adds the following nullable columns used by the forgot-password / reset-password
flow:

    * password_reset_token              VARCHAR(255)              (indexed)
    * password_reset_token_expires_at   TIMESTAMP WITH TIME ZONE

They are applied to:
    * the ``saas_admin`` table in the Master database, and
    * the ``"user"`` table in every provisioned Tenant database.

The script is idempotent — it uses ``ADD COLUMN IF NOT EXISTS`` and
``CREATE INDEX IF NOT EXISTS``, so it is safe to re-run. Each database is
migrated inside its own transaction; a failure on one tenant does not abort
the others.

Usage
-----
    python scripts/migrate_password_reset_fields.py
"""

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add project root to path so ``app`` package imports resolve.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant


# ``user`` is a reserved word in PostgreSQL, so it must be quoted.
TENANT_STATEMENTS = (
    'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255)',
    'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password_reset_token_expires_at TIMESTAMP WITH TIME ZONE',
    'CREATE INDEX IF NOT EXISTS ix_user_password_reset_token ON "user" (password_reset_token)',
)

MASTER_STATEMENTS = (
    "ALTER TABLE saas_admin ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255)",
    "ALTER TABLE saas_admin ADD COLUMN IF NOT EXISTS password_reset_token_expires_at TIMESTAMP WITH TIME ZONE",
    "CREATE INDEX IF NOT EXISTS ix_saas_admin_password_reset_token ON saas_admin (password_reset_token)",
)


def _apply(engine, statements) -> None:
    """Run a sequence of DDL statements inside a single transaction."""
    # ``engine.begin()`` opens a transactional connection that commits on
    # success and rolls back if any statement raises.
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def migrate_master(master_engine) -> None:
    """Add the password-reset columns to the Master database (saas_admin)."""
    print("Migrating Master Database (saas_admin)...")
    _apply(master_engine, MASTER_STATEMENTS)
    print("  Master Database migration complete.")


def migrate_password_reset_fields() -> None:
    """Apply the migration to the Master DB and every provisioned tenant DB."""
    print("Starting password-reset fields migration...")

    master_db_url = settings.MASTER_DATABASE_URL or settings.DATABASE_URL
    master_engine = create_engine(master_db_url)

    # 1. Master database first.
    try:
        migrate_master(master_engine)
    except Exception as exc:  # noqa: BLE001 - we want to continue to tenants
        print(f"  Failed to migrate Master Database: {exc}")

    # 2. Every provisioned tenant database.
    succeeded = 0
    failed = 0
    with Session(master_engine) as master_db:
        tenants = (
            master_db.query(Tenant)
            .filter(Tenant.is_provisioned == True)  # noqa: E712
            .all()
        )
        print(f"Found {len(tenants)} provisioned tenant(s).")

        for tenant in tenants:
            print(f"Migrating tenant: {tenant.name} ({tenant.code})...")
            tenant_engine = None
            try:
                if not tenant.db_connection_string:
                    raise ValueError("tenant has no db_connection_string set")

                db_url = decrypt_string(tenant.db_connection_string)
                tenant_engine = create_engine(db_url)
                _apply(tenant_engine, TENANT_STATEMENTS)

                print(f"  Successfully migrated {tenant.code}.")
                succeeded += 1
            except Exception as exc:  # noqa: BLE001 - isolate per-tenant failures
                print(f"  Failed to migrate {tenant.code}: {exc}")
                failed += 1
            finally:
                if tenant_engine is not None:
                    tenant_engine.dispose()

    master_engine.dispose()

    print(
        "Password-reset fields migration complete. "
        f"Tenants: {succeeded} succeeded, {failed} failed."
    )

    if failed:
        # Non-zero exit so CI / deploy pipelines notice partial failures.
        sys.exit(1)


if __name__ == "__main__":
    migrate_password_reset_fields()
