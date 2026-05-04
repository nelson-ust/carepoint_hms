import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.init_db import run_tenant_initialization
from app.core.config import settings

def init_tenant_db():
    db_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/hms_tenant_stnicholas"
    run_tenant_initialization(db_url, create_default_admin=False)
    print("Initialized tenant DB schema successfully.")

if __name__ == "__main__":
    init_tenant_db()
