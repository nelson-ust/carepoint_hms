from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, select, update

from app.core.database import get_master_db_context, get_engine_for_url
from app.core.multitenancy import decrypt_string
from app.models.all_models import Tenant, TenantUsage, User, Invoice, Payment, AuditLog
from app.core.logger import get_logger

logger = get_logger(__name__)

class TenantUsageService:
    @staticmethod
    def get_or_create_usage(master_db: Session, tenant_id: int) -> TenantUsage:
        """
        Get or create the usage record for a tenant.
        """
        usage = master_db.query(TenantUsage).filter(TenantUsage.tenant_id == tenant_id).first()
        if not usage:
            usage = TenantUsage(tenant_id=tenant_id)
            master_db.add(usage)
            master_db.commit()
            master_db.refresh(usage)
        return usage

    @staticmethod
    def increment_api_usage(tenant_id: int) -> None:
        """
        Increment the API call count for a tenant.
        Executed in the background or middleware.
        """
        with get_master_db_context() as master_db:
            master_db.execute(
                update(TenantUsage)
                .where(TenantUsage.tenant_id == tenant_id)
                .values(api_call_count=TenantUsage.api_call_count + 1)
            )
            master_db.commit()

    @staticmethod
    def increment_login_usage(tenant_id: int) -> None:
        """
        Increment the login count for a tenant.
        """
        with get_master_db_context() as master_db:
            master_db.execute(
                update(TenantUsage)
                .where(TenantUsage.tenant_id == tenant_id)
                .values(login_count=TenantUsage.login_count + 1)
            )
            master_db.commit()

    @staticmethod
    def sync_tenant_metrics(tenant_id: int) -> TenantUsage:
        """
        Connect to the tenant database and aggregate usage metrics.
        """
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                raise ValueError(f"Tenant with ID {tenant_id} not found.")

            if not tenant.db_connection_string:
                logger.warning(f"Tenant {tenant.code} has no database connection string. Skipping sync.")
                return TenantUsageService.get_or_create_usage(master_db, tenant_id)

            db_url = decrypt_string(tenant.db_connection_string)
            engine = get_engine_for_url(db_url)
            
            # Aggregate metrics from Tenant DB
            from sqlalchemy.orm import sessionmaker
            TenantSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
            tenant_db = TenantSessionLocal()
            
            try:
                user_count = tenant_db.query(func.count(User.id)).scalar() or 0
                invoice_count = tenant_db.query(func.count(Invoice.id)).scalar() or 0
                payment_count = tenant_db.query(func.count(Payment.id)).scalar() or 0
                # sms/email logs would go here too if those tables exist
                # for now using transactions = invoices + payments
                transaction_count = invoice_count + payment_count
                
                # Update Master DB
                usage = TenantUsageService.get_or_create_usage(master_db, tenant_id)
                usage.user_count = user_count
                usage.transaction_count = transaction_count
                usage.last_sync_at = datetime.now()
                
                master_db.add(usage)
                master_db.commit()
                master_db.refresh(usage)
                return usage
            finally:
                tenant_db.close()
