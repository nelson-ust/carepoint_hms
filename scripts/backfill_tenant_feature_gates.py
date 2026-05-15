# scripts/backfill_tenant_feature_gates.py
import os
import sys
import logging

"""
Backfill script for TenantModuleAccess.
Ensures all existing tenants have explicit module access records in the Master Database
based on their current subscription plan features.
"""

# Ensure the app directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import get_master_db_context
from app.models.all_models import Tenant, TenantSubscription, SubscriptionPlan, TenantModuleAccess
from app.core.enums import SubscriptionStatus

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# List of all feature flags from SubscriptionPlan
FEATURE_FLAGS = [
    "clinical", "inpatient", "laboratory", "pharmacy", "inventory",
    "billing", "reporting", "appointments", "patient_portal",
    "insurance", "radiology", "surgical", "hr", "dietary",
    "ambulance", "compliance"
]

def backfill_feature_access():
    logger.info("Starting backfill of TenantModuleAccess records...")
    
    with get_master_db_context() as db:
        # 1. Fetch all tenants
        tenants = db.query(Tenant).all()
        logger.info(f"Found {len(tenants)} total tenants.")
        
        updated_count = 0
        skipped_count = 0
        
        for tenant in tenants:
            # 2. Get active subscription for tenant
            subscription = db.query(TenantSubscription).filter(
                TenantSubscription.tenant_id == tenant.id,
                TenantSubscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
            ).first()
            
            if not subscription or not subscription.plan:
                logger.warning(f"Tenant {tenant.code} has no active subscription. Skipping.")
                skipped_count += 1
                continue
                
            plan = subscription.plan
            logger.info(f"Processing tenant {tenant.code} on plan {plan.code}...")
            
            # 3. Ensure TenantModuleAccess records exist for each feature flag
            for feature in FEATURE_FLAGS:
                plan_value = getattr(plan, f"has_{feature}", False)
                
                # Check if override already exists
                existing_override = db.query(TenantModuleAccess).filter(
                    TenantModuleAccess.tenant_id == tenant.id,
                    TenantModuleAccess.module_code == feature
                ).first()
                
                if not existing_override:
                    # Create explicit override matching plan default
                    new_override = TenantModuleAccess(
                        tenant_id=tenant.id,
                        module_code=feature,
                        is_enabled=plan_value,
                        notes=f"Auto-backfilled from plan {plan.code}"
                    )
                    db.add(new_override)
                    updated_count += 1
                else:
                    # Record exists, skip to preserve manual overrides
                    continue
        
        # 4. Commit changes
        try:
            db.commit()
            logger.info("Successfully committed changes to Master Database.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit backfill: {str(e)}")
            raise

    logger.info("-" * 40)
    logger.info("Backfill completed.")
    logger.info(f"Records created: {updated_count}")
    logger.info(f"Tenants skipped: {skipped_count}")
    logger.info("-" * 40)

if __name__ == "__main__":
    try:
        backfill_feature_access()
    except Exception as global_exc:
        logger.critical(f"Backfill script aborted: {global_exc}")
        sys.exit(1)
