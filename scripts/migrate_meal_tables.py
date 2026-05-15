# scripts/migrate_meal_tables.py
import os
import sys
import logging

"""
Multi-Tenant Migration Script for Meal Management.
Applies the new meal_type and meal_order tables across all provisioned tenant databases.
"""

# Ensure the app directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, create_engine
from app.core.database import get_master_db_context
from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# SQL to be executed on each tenant
TENANT_MIGRATION_SQL = """
-- 1. Meal Type Catalog
CREATE TABLE IF NOT EXISTS meal_type (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    billable_service_id INTEGER REFERENCES billable_service(id),
    name VARCHAR(150) NOT NULL,
    code VARCHAR(100) NOT NULL,
    description TEXT,
    base_price NUMERIC(14, 2) NOT NULL DEFAULT 0,
    
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    date_created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_deleted TIMESTAMPTZ,
    created_by_id INTEGER,
    updated_by_id INTEGER,
    deleted_by_id INTEGER
);

CREATE INDEX IF NOT EXISTS ix_meal_type_code ON meal_type(code);
CREATE INDEX IF NOT EXISTS ix_meal_type_tenant_id ON meal_type(tenant_id);

-- 2. Meal Orders
CREATE TABLE IF NOT EXISTS meal_order (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    visit_id INTEGER NOT NULL REFERENCES visit(id),
    patient_id INTEGER NOT NULL REFERENCES patient(id),
    meal_type_id INTEGER NOT NULL REFERENCES meal_type(id),
    invoice_item_id INTEGER REFERENCES invoice_item(id),
    
    recipient_type VARCHAR(50) NOT NULL DEFAULT 'PATIENT',
    caregiver_name VARCHAR(200),
    status VARCHAR(50) NOT NULL DEFAULT 'ORDERED',
    
    unit_price NUMERIC(14, 2) NOT NULL DEFAULT 0,
    quantity NUMERIC(14, 2) NOT NULL DEFAULT 1,
    total_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    
    ordered_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    served_at TIMESTAMPTZ,
    
    ordered_by_staff_id INTEGER,
    served_by_staff_id INTEGER,
    
    notes TEXT,
    
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    date_created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_deleted TIMESTAMPTZ,
    created_by_id INTEGER,
    updated_by_id INTEGER,
    deleted_by_id INTEGER
);

CREATE INDEX IF NOT EXISTS ix_meal_order_visit_id ON meal_order(visit_id);
CREATE INDEX IF NOT EXISTS ix_meal_order_patient_id ON meal_order(patient_id);
CREATE INDEX IF NOT EXISTS ix_meal_order_status ON meal_order(status);
CREATE INDEX IF NOT EXISTS ix_meal_order_tenant_id ON meal_order(tenant_id);
"""

def migrate_tenants():
    logger.info("Starting Meal Management migration across all tenants...")
    
    with get_master_db_context() as db:
        # Fetch all active and provisioned tenants
        tenants = db.query(Tenant).filter(
            Tenant.is_provisioned.is_(True),
            Tenant.is_active.is_(True)
        ).all()
        
        logger.info(f"Found {len(tenants)} active tenants to migrate.")
        
        success_count = 0
        failure_count = 0
        
        for tenant in tenants:
            logger.info(f"Migrating tenant: {tenant.name} (Code: {tenant.code})")
            try:
                # Decrypt the tenant-specific connection string
                db_url = decrypt_string(tenant.db_connection_string)
                
                # Create a temporary engine for the tenant
                engine = create_engine(
                    db_url, 
                    future=True, 
                    connect_args={"connect_timeout": 10}
                )
                
                with engine.connect() as conn:
                    # Execute migration in a transaction
                    with conn.begin():
                        conn.execute(text(TENANT_MIGRATION_SQL))
                
                engine.dispose()
                logger.info(f"Successfully migrated tenant {tenant.code}.")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate tenant {tenant.code}: {str(e)}")
                failure_count += 1
        
        logger.info("-" * 40)
        logger.info(f"Migration finished.")
        logger.info(f"Successfully migrated: {success_count}")
        logger.info(f"Failed: {failure_count}")
        logger.info("-" * 40)

if __name__ == "__main__":
    try:
        migrate_tenants()
    except Exception as global_exc:
        logger.critical(f"Migration script aborted due to a critical error: {global_exc}")
        sys.exit(1)
