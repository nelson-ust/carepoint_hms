"""add_feature_gating_infrastructure

Revision ID: 1e16f88312ba
Revises: c838e419b7bb
Create Date: 2026-05-15 11:35:52.133594

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e16f88312ba'
down_revision: Union[str, Sequence[str], None] = 'c838e419b7bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add MISSING feature flags to subscription_plan
    # (has_clinical, has_inpatient, has_laboratory, has_pharmacy, has_inventory, 
    # has_billing, has_reporting, has_appointments, has_patient_portal, 
    # has_insurance, has_radiology, has_surgical, has_hr already exist in DB)
    op.add_column('subscription_plan', sa.Column('has_dietary', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('subscription_plan', sa.Column('has_ambulance', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('subscription_plan', sa.Column('has_compliance', sa.Boolean(), server_default='false', nullable=False))

    # 2. Create feature_access_audit_log
    op.create_table('feature_access_audit_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('feature_code', sa.String(length=50), nullable=False),
        sa.Column('path', sa.String(length=255), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('is_denied', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_deleted', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feature_access_audit_log_feature_code'), 'feature_access_audit_log', ['feature_code'], unique=False)
    op.create_index(op.f('ix_feature_access_audit_log_is_denied'), 'feature_access_audit_log', ['is_denied'], unique=False)
    op.create_index(op.f('ix_feature_access_audit_log_tenant_id'), 'feature_access_audit_log', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_feature_access_audit_log_user_id'), 'feature_access_audit_log', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_feature_access_audit_log_user_id'), table_name='feature_access_audit_log')
    op.drop_index(op.f('ix_feature_access_audit_log_tenant_id'), table_name='feature_access_audit_log')
    op.drop_index(op.f('ix_feature_access_audit_log_is_denied'), table_name='feature_access_audit_log')
    op.drop_index(op.f('ix_feature_access_audit_log_feature_code'), table_name='feature_access_audit_log')
    op.drop_table('feature_access_audit_log')

    op.drop_column('subscription_plan', 'has_compliance')
    op.drop_column('subscription_plan', 'has_ambulance')
    op.drop_column('subscription_plan', 'has_dietary')
