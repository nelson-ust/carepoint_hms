from app.services.tenant_service import TenantService
from app.core.config import settings

print("MASTER_DATABASE_URL:", settings.MASTER_DATABASE_URL)
url = TenantService._build_tenant_db_url("hms_tenant_stnicholas")
print("Constructed URL:", url)
