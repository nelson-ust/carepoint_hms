# scripts/migrate_feature_gating.py
import os
import sys
import logging
from sqlalchemy import text
from typing import List

"""
Feature Gating Migration Script (Master Database).
This script applies schema changes and backfills data for multi-tenant feature gating.
Does NOT use Alembic.
"""

# Ensure the app directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_master_db_context
from app.models.all_models import Tenant, TenantSubscription, TenantModuleAccess
from app.core.enums import SubscriptionStatus

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. Schema Changes SQL
SCHEMA_MIGRATION_SQL = """
-- Add missing feature flags to subscription_plan if they don't exist
DO $$ 
BEGIN 
    BEGIN
        ALTER TABLE subscription_plan ADD COLUMN has_dietary BOOLEAN DEFAULT FALSE;
    EXCEPTION WHEN duplicate_column THEN 
        RAISE NOTICE 'column has_dietary already exists in subscription_plan';
    END;
    
    BEGIN
        ALTER TABLE subscription_plan ADD COLUMN has_ambulance BOOLEAN DEFAULT FALSE;
    EXCEPTION WHEN duplicate_column THEN 
        RAISE NOTICE 'column has_ambulance already exists in subscription_plan';
    END;
    
    BEGIN
        ALTER TABLE subscription_plan ADD COLUMN has_compliance BOOLEAN DEFAULT FALSE;
    EXCEPTION WHEN duplicate_column THEN 
        RAISE NOTICE 'column has_compliance already exists in subscription_plan';
    END;
END $$;

-- Create Feature Access Audit Log table
CREATE TABLE IF NOT EXISTS feature_access_audit_log (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenant(id),
    user_id INTEGER,
    feature_code VARCHAR(50) NOT NULL,
    path VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_denied BOOLEAN DEFAULT FALSE,
    reason TEXT,
    
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    date_created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    date_deleted TIMESTAMPTZ,
    created_by_id INTEGER,
    updated_by_id INTEGER,
    deleted_by_id INTEGER
);

CREATE INDEX IF NOT EXISTS ix_feature_access_audit_log_tenant_id ON feature_access_audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS ix_feature_access_audit_log_feature_code ON feature_access_audit_log(feature_code);
CREATE INDEX IF NOT EXISTS ix_feature_access_audit_log_is_denied ON feature_access_audit_log(is_denied);
"""

# List of all feature flags to backfill
FEATURE_FLAGS = [
    "clinical", "inpatient", "laboratory", "pharmacy", "inventory",
    "billing", "reporting", "appointments", "patient_portal",
    "insurance", "radiology", "surgical", "hr", "dietary",
    "ambulance", "compliance"
]

def run_migration():
    logger.info("Starting Feature Gating migration...")
    
    with get_master_db_context() as db:
        # Phase 1: Schema Updates
        logger.info("Phase 1: Applying schema changes to Master Database...")
        try:
            db.execute(text(SCHEMA_MIGRATION_SQL))
            db.commit()
            logger.info("Schema changes applied successfully.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to apply schema changes: {str(e)}")
            return

        # Phase 2: Data Backfill (TenantModuleAccess)
        logger.info("Phase 2: Backfilling TenantModuleAccess records...")
        tenants = db.query(Tenant).all()
        logger.info(f"Found {len(tenants)} total tenants.")
        
        updated_count = 0
        
        for tenant in tenants:
            # Get active subscription for tenant
            subscription = db.query(TenantSubscription).filter(
                TenantSubscription.tenant_id == tenant.id,
                TenantSubscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
            ).first()
            
            if not subscription or not subscription.plan:
                logger.warning(f"Tenant {tenant.code} has no active subscription. Skipping data backfill.")
                continue
                
            plan = subscription.plan
            
            for feature in FEATURE_FLAGS:
                # Get the value from the plan (using getattr since these are now guaranteed to exist or be in model)
                plan_value = getattr(plan, f"has_{feature}", False)
                
                # Check if override already exists
                existing_override = db.query(TenantModuleAccess).filter(
                    TenantModuleAccess.tenant_id == tenant.id,
                    TenantModuleAccess.module_code == feature
                ).first()
                
                if not existing_override:
                    new_override = TenantModuleAccess(
                        tenant_id=tenant.id,
                        module_code=feature,
                        is_enabled=plan_value,
                        notes=f"Auto-backfilled from plan {plan.code}"
                    )
                    db.add(new_override)
                    updated_count += 1
        
        try:
            db.commit()
            logger.info(f"Data backfill complete. Created {updated_count} records.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit data backfill: {str(e)}")

    logger.info("-" * 40)
    logger.info("Migration finished successfully.")
    logger.info("-" * 40)

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as global_exc:
        logger.critical(f"Migration script aborted due to a critical error: {global_exc}")
        sys.exit(1)
