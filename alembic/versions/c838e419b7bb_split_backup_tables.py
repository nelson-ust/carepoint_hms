"""split_backup_tables

Revision ID: c838e419b7bb
Revises: 16b488ed9fcb
Create Date: 2026-05-14 16:42:18.657810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c838e419b7bb'
down_revision: Union[str, Sequence[str], None] = '16b488ed9fcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create master_database_backup
    op.create_table(
        'master_database_backup',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_deleted', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('s3_url', sa.Text(), nullable=True),
        sa.Column('s3_key', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('storage_location', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False),
        sa.Column('encryption_algo', sa.String(length=40), nullable=True),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('backup_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('backup_finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retention_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('triggered_by', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_master_database_backup_retention_until'), 'master_database_backup', ['retention_until'], unique=False)

    # 2. Migrate existing master data from old database_backup if it exists
    # We do this as a raw SQL execute
    op.execute("""
        INSERT INTO master_database_backup (
            filename, s3_url, s3_key, size_bytes, status, storage_location, 
            error_message, is_encrypted, encryption_algo, checksum_sha256,
            backup_started_at, backup_finished_at, retention_until, triggered_by,
            date_created, date_updated, is_active, is_deleted
        )
        SELECT 
            filename, s3_url, s3_key, size_bytes, status, storage_location, 
            error_message, is_encrypted, encryption_algo, checksum_sha256,
            backup_started_at, backup_finished_at, retention_until, triggered_by,
            date_created, date_updated, is_active, is_deleted
        FROM database_backup
        WHERE tenant_id IS NULL;
    """)

    # 3. Drop the old table from Master DB
    op.drop_table('database_backup')


def downgrade() -> None:
    # Re-create the old database_backup table in Master DB
    op.create_table(
        'database_backup',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenant.id'), nullable=True),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('s3_url', sa.Text(), nullable=True),
        sa.Column('s3_key', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('storage_location', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False),
        sa.Column('encryption_algo', sa.String(length=40), nullable=True),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('backup_type', sa.String(length=20), nullable=False),
        sa.Column('pg_dump_format', sa.String(length=20), nullable=False),
        sa.Column('backup_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('backup_finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retention_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('triggered_by', sa.String(length=20), nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_updated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy back from master_database_backup
    op.execute("""
        INSERT INTO database_backup (
            filename, s3_url, s3_key, size_bytes, status, storage_location, 
            error_message, is_encrypted, encryption_algo, checksum_sha256,
            backup_started_at, backup_finished_at, retention_until, triggered_by,
            date_created, date_updated, is_active, is_deleted, backup_type, pg_dump_format
        )
        SELECT 
            filename, s3_url, s3_key, size_bytes, status, storage_location, 
            error_message, is_encrypted, encryption_algo, checksum_sha256,
            backup_started_at, backup_finished_at, retention_until, triggered_by,
            date_created, date_updated, is_active, is_deleted, 'FULL', 'custom'
        FROM master_database_backup;
    """)
    
    op.drop_table('master_database_backup')
