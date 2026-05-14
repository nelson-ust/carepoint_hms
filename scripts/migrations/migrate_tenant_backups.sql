-- Migration Script for Tenant Databases
-- Purpose: Create or update the isolated DatabaseBackup table in each tenant database.
-- Standardizes field names (file_name, started_at, etc.)

BEGIN;

-- 1. Create the table if it doesn't exist
CREATE TABLE IF NOT EXISTS database_backup (
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
    retention_days INTEGER,
    note VARCHAR(255),
    
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    
    backup_type VARCHAR(20) NOT NULL DEFAULT 'FULL',
    triggered_by VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    retention_until TIMESTAMP WITH TIME ZONE
);

-- 2. Handle Schema Updates (for existing tables)
DO $$ 
BEGIN
    -- Add file_name if filename exists
    IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'filename') THEN
        ALTER TABLE database_backup RENAME COLUMN filename TO file_name;
    END IF;

    -- Add storage_location if missing
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'storage_location') THEN
        ALTER TABLE database_backup ADD COLUMN storage_location VARCHAR(50) NOT NULL DEFAULT 'LOCAL';
    END IF;

    -- Rename started_at/completed_at
    IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'backup_started_at') THEN
        ALTER TABLE database_backup RENAME COLUMN backup_started_at TO started_at;
    END IF;
    IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'backup_finished_at') THEN
        ALTER TABLE database_backup RENAME COLUMN backup_finished_at TO completed_at;
    END IF;
    IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'pg_dump_format') THEN
        ALTER TABLE database_backup RENAME COLUMN pg_dump_format TO format;
    END IF;

    -- Add missing metadata columns
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'duration_ms') THEN
        ALTER TABLE database_backup ADD COLUMN duration_ms INTEGER;
    END IF;
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'note') THEN
        ALTER TABLE database_backup ADD COLUMN note VARCHAR(255);
    END IF;
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'schema_only') THEN
        ALTER TABLE database_backup ADD COLUMN schema_only BOOLEAN DEFAULT false;
    END IF;
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'retention_days') THEN
        ALTER TABLE database_backup ADD COLUMN retention_days INTEGER;
    END IF;

    -- Drop legacy columns
    IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'database_backup' AND column_name = 'pitr_lsn') THEN
        ALTER TABLE database_backup DROP COLUMN pitr_lsn;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_database_backup_retention_until ON database_backup (retention_until);

COMMIT;
