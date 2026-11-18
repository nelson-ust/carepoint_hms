"""add tenant.facility_profile (standalone vertical: hospital/dental/eye/pharmacy)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-11-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing tenants have NULL, which the service treats as the
    # full "HOSPITAL" profile, so the current integrated arrangement is
    # preserved until an admin opts a tenant into a standalone vertical.
    op.add_column(
        "tenant",
        sa.Column("facility_profile", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant", "facility_profile")
