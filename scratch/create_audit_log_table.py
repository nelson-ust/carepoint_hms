import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import get_master_engine, get_engine_for_url, TenantBase
from app.core.config import settings
from app.models.all_models import Tenant, AuditLog

def create_audit_log_for_all_tenants():
    master_engine = get_master_engine()
    db = Session(master_engine)
    try:
        tenants = db.query(Tenant).all()
        print(f"Found {len(tenants)} tenants.")
        base_url = settings.DATABASE_URL
        
        from sqlalchemy.engine.url import make_url
        
        for tenant in tenants:
            print(f"Creating tables for tenant: {tenant.code} ({tenant.db_name})")
            url_obj = make_url(base_url)
            tenant_url = url_obj.set(database=tenant.db_name)
            engine = get_engine_for_url(str(tenant_url))
            TenantBase.metadata.create_all(bind=engine)
            print(f"Finished creating tables for tenant: {tenant.code}")
    finally:
        db.close()

if __name__ == "__main__":
    create_audit_log_for_all_tenants()
