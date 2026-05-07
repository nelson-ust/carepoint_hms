from app.core.config import settings
from sqlalchemy import create_engine, text
from app.core.cryptography import decrypt_string

url = settings.MASTER_DATABASE_URL
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text("SELECT code, db_connection_string FROM tenant")).fetchall()
    for row in result:
        print(f"Tenant {row[0]}: {decrypt_string(row[1])}")
