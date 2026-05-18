# scripts/migrate_patient_clinical_records.py
import os
import sys
import logging
from sqlalchemy import create_engine, text
from typing import List

"""
Migration script to update existing tenant databases with new clinical record structures.
Specifically:
1. Ensures the 'patient_allergy' table exists.
2. Adds the 'chronic_conditions' column to the 'patient' table if it doesn't exist.
3. Adds any missing relationships or tables defined in the latest TenantBase.
"""

# Ensure the app directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_master_db_context
from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant
from app.db_sync import sync_tenant_schema

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("tenant_migration.log")
    ]
)
logger = logging.getLogger(__name__)

def migrate_clinical_records():
    logger.info("Starting clinical records migration across all tenants...")
    
    # 1. Fetch all provisioned tenants and close master session immediately
    # to avoid holding the master connection open during long tenant migrations.
    tenant_data = []
    try:
        with get_master_db_context() as master_db:
            tenants = master_db.query(Tenant).filter(
                Tenant.is_deleted == False,
                Tenant.is_provisioned == True
            ).all()
            
            for t in tenants:
                tenant_data.append({
                    "id": t.id,
                    "code": t.code,
                    "name": t.name,
                    "db_name": t.db_name,
                    "db_connection_string": t.db_connection_string
                })
        logger.info(f"Fetched {len(tenant_data)} active, provisioned tenants from master.")
    except Exception as e:
        logger.critical(f"Failed to fetch tenants from master: {e}")
        return

    success_count = 0
    failure_count = 0
    
    for t_info in tenant_data:
        code = t_info["code"]
        name = t_info["name"]
        logger.info(f"--- Processing Tenant: {code} ({name}) ---")
        
        if not t_info["db_connection_string"]:
            logger.warning(f"Tenant {code} has no database connection string. Skipping.")
            continue
            
        # Retry logic for individual tenant migrations using the robust sync_tenant_schema
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                # 2. Decrypt connection string
                db_url = decrypt_string(t_info["db_connection_string"])
                
                logger.info(f"Attempt {attempt}: Synchronizing schema for tenant database '{t_info['db_name']}'...")
                summary = sync_tenant_schema(db_url)
                
                if summary:
                    logger.info(f"Successfully applied schema updates: {summary}")
                else:
                    logger.info("Schema is already fully synchronized. No changes required.")
                
                logger.info(f"Tenant {code} migrated successfully.")
                success_count += 1
                break # Success, exit retry loop
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Attempt {attempt} failed for tenant {code}: {e}. Retrying...")
                    import time
                    time.sleep(2) # Brief pause before retry
                else:
                    logger.error(f"Failed to migrate tenant {code} after {max_retries} attempts: {e}")
                    failure_count += 1

    logger.info("=" * 40)
    logger.info(f"Migration finished. Success: {success_count}, Failures: {failure_count}")
    logger.info("=" * 40)

if __name__ == "__main__":
    # Ensure SQL echo is disabled globally for the migration script to avoid noise
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    try:
        migrate_clinical_records()
    except Exception as global_exc:
        logger.critical(f"Global migration error: {global_exc}")
        sys.exit(1)
