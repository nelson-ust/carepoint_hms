"""backfill ledger accounts on existing monetary records

Data-only migration (no DDL). Maps every NULL-account reimbursement, salary
advance, payroll run, billing line and payment to an existing account, reusing
``app.scripts.backfill_account_codes.backfill``. It is a no-op on databases that
don't carry the tenant tables (e.g. the master DB) and is idempotent — only
rows whose account is still NULL are touched.

Run per tenant:

    alembic -x db_url="postgresql://…/tenant_db" upgrade head

Revision ID: a1b2c3d4e5f6
Revises: 1e16f88312ba
Create Date: 2026-07-21
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "1e16f88312ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables the backfill touches; skip cleanly when they're absent (master DB).
_REQUIRED_TABLES = ("account", "billing_item", "billing_payment")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not all(inspector.has_table(t) for t in _REQUIRED_TABLES):
        # Not a tenant database — nothing to back-fill here.
        return

    from app.scripts.backfill_account_codes import backfill

    session = Session(bind=bind)
    # commit=False: Alembic owns the surrounding transaction and commits it.
    summary = backfill(session, commit=False)
    session.flush()
    print(f"[backfill_account_codes] {summary}")


def downgrade() -> None:
    # Data back-fill: intentionally irreversible. The account snapshots written
    # here are indistinguishable from those set by normal charge capture, so we
    # do not attempt to null them out on downgrade.
    pass
