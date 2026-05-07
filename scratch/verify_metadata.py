
from app.models.base import MasterBase, TenantBase
import app.models.all_models

print("--- MasterBase Metadata Tables ---")
for table in MasterBase.metadata.tables:
    print(table)

print("\n--- TenantBase Metadata Tables ---")
for table in TenantBase.metadata.tables:
    print(table)
