"""add tenant.deployment_mode (per-hospital cloud/onprem/hybrid opt-in)

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-11-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing tenants fall back to the global default mode, so
    # current behaviour is preserved until an admin opts a hospital in.
    op.add_column("tenant", sa.Column("deployment_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant", "deployment_mode")
