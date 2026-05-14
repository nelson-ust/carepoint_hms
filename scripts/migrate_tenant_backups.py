import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from app.models.all_models import Tenant
from app.core.cryptography import decrypt_string

def migrate_master_backup(master_engine):
    """
    Migrates the Master Database backup schema.
    """
    print("Migrating Master Database...")
    with master_engine.connect() as conn:
        sql = """
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
        """
        conn.execute(text(sql))
    print("Master Database migration complete.")

def migrate_tenant_backups():
    """
    Creates or updates the database_backup table in every provisioned tenant database.
    Standardizes field names (file_name, started_at, etc.)
    """
    print("Starting Multi-Tenant Backup Migration...")
    
    # 1. Connect to Master DB
    master_db_url = settings.MASTER_DATABASE_URL or settings.DATABASE_URL
    master_engine = create_engine(master_db_url)
    
    # 2. Migrate Master DB itself first
    try:
        migrate_master_backup(master_engine)
    except Exception as e:
        print(f"Failed to migrate Master Database: {e}")
        # We continue to tenants even if master failed, or we could exit.
    
    # 3. Get all tenants
    with Session(master_engine) as master_db:
        tenants = master_db.query(Tenant).filter(Tenant.is_provisioned == True).all()
        print(f"Found {len(tenants)} provisioned tenants.")

        for tenant in tenants:
            print(f"Migrating tenant: {tenant.name} ({tenant.code})...")
            try:
                db_url = decrypt_string(tenant.db_connection_string)
                tenant_engine = create_engine(db_url)
                
                with tenant_engine.connect() as conn:
                    # SQL for creation and incremental update
                    sql = """
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
                        -- Rename filename if it exists
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
                    """
                    conn.execute(text(sql))
                print(f"  Successfully migrated {tenant.code}.")
            except Exception as e:
                print(f"  Failed to migrate {tenant.code}: {e}")
            finally:
                tenant_engine.dispose()

    master_engine.dispose()
    print("Multi-tenant migration complete.")

if __name__ == "__main__":
    migrate_tenant_backups()
