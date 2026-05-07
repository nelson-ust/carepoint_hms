import os
os.environ["PYTHONPATH"] = "/Users/nelsonattah/Projects/carepoint_hms"
from sqlalchemy import create_engine, text
from app.init_db import _build_postgres_admin_uri
from app.core.database import MASTER_DATABASE_URL

admin_uri = _build_postgres_admin_uri(MASTER_DATABASE_URL)
engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT", future=True)
try:
    with engine.connect() as conn:
        conn.execute(text("CREATE DATABASE test_create_py"))
        print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
