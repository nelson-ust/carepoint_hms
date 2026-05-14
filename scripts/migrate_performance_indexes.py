# scripts/migrate_performance_indexes.py
import os
import sys
import logging

# Ensure the app directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, create_engine
from app.core.database import get_master_db_context
from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MASTER_SQL = """
-- MASTER DATABASE OPTIMIZATIONS
BEGIN;

-- Indexing for tenant and platform-level audit tables
CREATE INDEX IF NOT EXISTS ix_tenant_date_created ON tenant (date_created);
CREATE INDEX IF NOT EXISTS ix_saas_user_date_created ON "user" (date_created);
CREATE INDEX IF NOT EXISTS ix_audit_log_date_created ON audit_log (date_created);

COMMIT;
"""

TENANT_SQL = """
-- TENANT DATABASE OPTIMIZATIONS
BEGIN;

-- 1. Global Audit Performance (Applies to all business tables)
CREATE INDEX IF NOT EXISTS ix_patient_date_created ON patient (date_created);
CREATE INDEX IF NOT EXISTS ix_visit_date_created ON visit (date_created);
CREATE INDEX IF NOT EXISTS ix_user_date_created ON "user" (date_created);

-- 2. Membership Card & Transaction Performance
CREATE INDEX IF NOT EXISTS ix_membership_card_issuing_facility_id ON membership_card (issuing_facility_id);
CREATE INDEX IF NOT EXISTS ix_membership_card_date_issued ON membership_card (date_issued);
CREATE INDEX IF NOT EXISTS ix_membership_card_expiry_date ON membership_card (expiry_date);

CREATE INDEX IF NOT EXISTS ix_membership_card_transaction_facility_id ON membership_card_transaction (facility_id);
CREATE INDEX IF NOT EXISTS ix_membership_card_transaction_transaction_date ON membership_card_transaction (transaction_date);
CREATE INDEX IF NOT EXISTS ix_membership_card_transaction_invoice_id ON membership_card_transaction (invoice_id);

-- Composite Index for high-performance history lookup
CREATE INDEX IF NOT EXISTS ix_membership_card_transaction_lookup 
ON membership_card_transaction (membership_card_id, transaction_date);

-- 3. Notifications & Messaging Performance
CREATE INDEX IF NOT EXISTS ix_notification_template_id ON notification (template_id);
CREATE INDEX IF NOT EXISTS ix_notification_scheduled_at ON notification (scheduled_at);
CREATE INDEX IF NOT EXISTS ix_notification_date_created ON notification (date_created);
CREATE INDEX IF NOT EXISTS ix_message_date_created ON message (date_created);

-- Partial index for the notification worker/scheduler
CREATE INDEX IF NOT EXISTS ix_notification_pending_worker_lookup 
ON notification (scheduled_at) 
WHERE status = 'PENDING';

COMMIT;
"""

def migrate_master():
    logger.info("Starting Master Database migration...")
    with get_master_db_context() as db:
        try:
            db.execute(text(MASTER_SQL))
            db.commit()
            logger.info("Successfully applied indexes to Master Database.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to apply indexes to Master Database: {e}")

def migrate_tenants():
    logger.info("Starting Tenant Databases migration...")
    with get_master_db_context() as db:
        tenants = db.query(Tenant).filter(
            Tenant.is_provisioned.is_(True)
        ).all()
        
        logger.info(f"Found {len(tenants)} provisioned tenants.")
        
        for tenant in tenants:
            logger.info(f"Migrating tenant: {tenant.name} ({tenant.code})")
            try:
                db_url = decrypt_string(tenant.db_connection_string)
                engine = create_engine(db_url, future=True, connect_args={"connect_timeout": 10})
                with engine.connect() as conn:
                    conn.execute(text(TENANT_SQL))
                    conn.commit()
                engine.dispose()
                logger.info(f"Successfully applied indexes to tenant {tenant.code}.")
            except Exception as e:
                logger.error(f"Failed to migrate tenant {tenant.code}: {e}")

if __name__ == "__main__":
    migrate_master()
    migrate_tenants()
    logger.info("Migration process completed.")
