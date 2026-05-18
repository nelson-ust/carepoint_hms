"""
Notification Worker for Carepoint HMS.

This worker polls for PENDING or FAILED notifications across all tenants
and processes them using the NotificationDispatcher. It also handles
platform-level SaaSNotifications for administrators.

Execution:
    python -m app.workers.notification_worker
"""
import time
import signal
import logging
import sys
from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import MASTER_DATABASE_URL, get_engine_for_url
from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant, NotificationStatus, SaaSNotification
from app.services.notification_dispatcher import NotificationDispatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("notification_worker")

# Global flag for graceful shutdown
keep_running = True

def signal_handler(sig, frame):
    global keep_running
    logger.info("Shutdown signal received. Finishing current batch...")
    keep_running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_active_tenants() -> List[Tuple[str, str]]:
    """Fetch active and provisioned tenants from master DB."""
    if not MASTER_DATABASE_URL:
        logger.error("MASTER_DATABASE_URL not set")
        return []
        
    master_engine = create_engine(MASTER_DATABASE_URL)
    tenants_data = []
    try:
        with Session(master_engine) as session:
            tenants = (
                session.query(Tenant)
                .filter(
                    Tenant.is_active.is_(True),
                    Tenant.is_provisioned.is_(True),
                    Tenant.is_deleted.is_(False)
                )
                .all()
            )
            for t in tenants:
                try:
                    url = decrypt_string(t.db_connection_string) if t.db_connection_string else None
                    if url:
                        tenants_data.append((t.code, url))
                except Exception as e:
                    logger.error(f"Failed to decrypt connection string for tenant {t.code}: {e}")
    except Exception as e:
        logger.error(f"Error fetching tenants from master: {e}")
    finally:
        master_engine.dispose()
    return tenants_data

def process_saas_notifications():
    """Process pending platform-level notifications for SaaS admins."""
    if not MASTER_DATABASE_URL:
        return
        
    master_engine = create_engine(MASTER_DATABASE_URL)
    try:
        with Session(master_engine) as session:
            pending = (
                session.query(SaaSNotification)
                .filter(SaaSNotification.status == NotificationStatus.PENDING)
                .limit(100)
                .all()
            )
            
            if not pending:
                return
                
            logger.info(f"Processing {len(pending)} SaaS-level notifications")
            for notif in pending:
                # Currently SaaSNotifications are primarily in-app, 
                # so we just mark them as SENT.
                notif.status = NotificationStatus.SENT
                # If we add Email/SMS for SaaS admins, we'd add the logic here.
                
            session.commit()
    except Exception as e:
        logger.error(f"Error processing SaaS notifications: {e}")
    finally:
        master_engine.dispose()

def run_worker_loop():
    """Main worker loop."""
    logger.info("Notification worker started.")
    poll_interval = getattr(settings, "NOTIFICATION_WORKER_POLL_INTERVAL", 10)
    
    while keep_running:
        start_time = time.time()
        
        # 1. Process SaaS-level notifications
        process_saas_notifications()
        
        # 2. Process Tenant-level notifications
        tenants = get_active_tenants()
        for tenant_code, db_url in tenants:
            if not keep_running:
                break
                
            try:
                engine = get_engine_for_url(db_url)
                with Session(engine) as tenant_db:
                    dispatcher = NotificationDispatcher(tenant_db)
                    stats = dispatcher.process_pending(max_batch=50)
                    
                    if stats["total"] > 0:
                        logger.info(
                            f"Tenant {tenant_code}: Processed {stats['total']} notifications "
                            f"(Sent: {stats['sent']}, Failed: {stats['failed']})"
                        )
            except Exception as e:
                logger.error(f"Error processing notifications for tenant {tenant_code}: {e}")
        
        # Calculate sleep time
        elapsed = time.time() - start_time
        sleep_time = max(0.1, poll_interval - elapsed)
        
        if keep_running:
            time.sleep(sleep_time)

    logger.info("Notification worker shut down gracefully.")

if __name__ == "__main__":
    run_worker_loop()
