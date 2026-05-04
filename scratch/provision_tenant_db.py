import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.tenant_service import TenantService
from app.models.all_models import Tenant

def provision_db():
    master_engine = create_engine(settings.MASTER_DATABASE_URL)
    with Session(master_engine) as db:
        service = TenantService(db)
        tenant = db.query(Tenant).filter(Tenant.code == 'stnicholas').first()
        if tenant:
            if not tenant.is_provisioned:
                print(f"Provisioning tenant {tenant.id}...")
                from app.schemas.tenant_schemas import TenantRegistrationSchema
                admin_payload = TenantRegistrationSchema(
                    tenant_name=tenant.name,
                    tenant_code=tenant.code,
                    domain_url=tenant.domain_url,
                    plan_code="BASIC",
                    admin_email="admin@stnicholas.com",
                    admin_username="admin",
                    admin_password="Password123!",
                    admin_first_name="St",
                    admin_last_name="Nicholas"
                )
                service.provision_tenant(tenant.id, admin_payload)
                print("Provisioned!")
            else:
                print("Already provisioned.")
        else:
            print("Tenant not found.")

if __name__ == "__main__":
    provision_db()
