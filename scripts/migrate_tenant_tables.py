# scripts/migrate_tenant_tables.py
import os
import sys
import logging
from sqlalchemy import text
from typing import List

"""
Tenant Database Migration Script.
Iterates over all tenants in the Master Database and ensures their individual 
databases are up-to-date with the latest TenantTable models.
Does NOT use Alembic.
"""

# Ensure the app directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_master_db_context, get_engine_for_url
from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant
from app.models.base import TenantBase

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def migrate_tenants():
    logger.info("Starting Tenant Database migrations...")
    
    with get_master_db_context() as master_db:
        # 1. Fetch all tenants
        tenants = master_db.query(Tenant).filter(Tenant.is_deleted == False).all()
        logger.info(f"Found {len(tenants)} active tenants.")
        
        for tenant in tenants:
            logger.info(f"--- Processing Tenant: {tenant.code} ({tenant.name}) ---")
            
            if not tenant.db_connection_string:
                logger.warning(f"Tenant {tenant.code} has no database connection string. Skipping.")
                continue
                
            try:
                # 2. Decrypt connection string and create engine
                db_url = decrypt_string(tenant.db_connection_string)
                tenant_engine = get_engine_for_url(db_url)
                
                # 3. Create missing tables using SQLAlchemy metadata
                # This will only create tables that do not already exist.
                # It will NOT handle column additions/removals (use raw SQL for that).
                logger.info(f"Ensuring tables exist in {tenant.db_name}...")
                TenantBase.metadata.create_all(bind=tenant_engine)
                
                # 4. Handle specific schema updates (if any) via raw SQL
                # Example: Adding a missing column to an existing table
                # with tenant_engine.connect() as conn:
                #     conn.execute(text("ALTER TABLE some_table ADD COLUMN IF NOT EXISTS new_col ..."))
                #     conn.commit()
                
                logger.info(f"Tenant {tenant.code} migration check complete.")
                
            except Exception as e:
                logger.error(f"Failed to migrate tenant {tenant.code}: {str(e)}")
                continue

    logger.info("-" * 40)
    logger.info("All tenant migrations processed.")
    logger.info("-" * 40)

if __name__ == "__main__":
    try:
        migrate_tenants()
    except Exception as global_exc:
        logger.critical(f"Tenant migration script aborted: {global_exc}")
        sys.exit(1)
