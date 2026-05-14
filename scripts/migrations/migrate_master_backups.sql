-- Migration Script for Master Database
-- Purpose: Split DatabaseBackup into Tenant and Master levels with standardized field names.
-- This script runs on the Master Database.

BEGIN;

-- 1. Create the new Master Backup table
CREATE TABLE IF NOT EXISTS master_database_backup (
    id SERIAL PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    date_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    date_deleted TIMESTAMP WITH TIME ZONE,
    created_by_id INTEGER,
    updated_by_id INTEGER,
    deleted_by_id INTEGER,
    
    file_name TEXT NOT NULL,
    s3_url TEXT,
    s3_key TEXT,
    size_bytes BIGINT,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    storage_location VARCHAR(50) NOT NULL DEFAULT 'LOCAL',
    error_message TEXT,
    is_encrypted BOOLEAN NOT NULL DEFAULT false,
    encryption_algo VARCHAR(40),
    checksum_sha256 VARCHAR(64),
    
    format VARCHAR(16) NOT NULL DEFAULT 'custom',
    schema_only BOOLEAN NOT NULL DEFAULT false,
    note VARCHAR(255),
    
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    
    triggered_by VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    retention_until TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_master_database_backup_retention_until ON master_database_backup (retention_until);

-- 2. Migrate existing master-level records (where tenant_id was NULL)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'database_backup') THEN
        INSERT INTO master_database_backup (
            file_name, s3_url, s3_key, size_bytes, status, storage_location, 
            error_message, is_encrypted, encryption_algo, checksum_sha256,
            started_at, completed_at, retention_until, triggered_by,
            date_created, date_updated, is_active, is_deleted
        )
        SELECT 
            COALESCE(file_name, filename), s3_url, s3_key, size_bytes, status, 
            COALESCE(storage_location, 'LOCAL'),
            error_message, is_encrypted, encryption_algo, checksum_sha256,
            COALESCE(started_at, backup_started_at), 
            COALESCE(completed_at, backup_finished_at), 
            retention_until, triggered_by,
            date_created, date_updated, is_active, is_deleted
        FROM database_backup
        WHERE tenant_id IS NULL;
        
        -- 3. Drop the old table from Master DB
        DROP TABLE database_backup;
    END IF;
END $$;

COMMIT;
