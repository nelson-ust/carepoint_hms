
import os
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.cryptography import decrypt_string

url = settings.MASTER_DATABASE_URL or settings.DATABASE_URL
print(f"Connecting to: {url}")
engine = create_engine(url)

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, code, db_name, db_connection_string, status, is_provisioned FROM tenant"))
    tenants = result.fetchall()
    print(f"Found {len(tenants)} tenants:")
    for t in tenants:
        print(f"ID: {t.id}, Code: {t.code}, DB Name: {t.db_name}, Status: {t.status}, Provisioned: {t.is_provisioned}")
        if t.db_connection_string:
            try:
                decrypted = decrypt_string(t.db_connection_string)
                print(f"  Decrypted URL: {decrypted}")
            except Exception as e:
                print(f"  Decryption failed: {e}")
                print(f"  Raw string: {t.db_connection_string}")
