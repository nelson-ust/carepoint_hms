import os
os.environ["PYTHONPATH"] = "/Users/nelsonattah/Projects/carepoint_hms"

from app.init_db import create_new_database
from app.services.tenant_service import TenantService

print("Testing create_new_database...")
create_new_database("hms_tenant_stnicholas")

print("Testing _build_tenant_db_url...")
url = TenantService._build_tenant_db_url("hms_tenant_stnicholas")
print(f"Resulting URL: {url}")
