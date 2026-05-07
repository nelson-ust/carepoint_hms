from app.core.config import settings
from sqlalchemy import create_engine, text
from app.core.cryptography import encrypt_string

url = settings.MASTER_DATABASE_URL
engine = create_engine(url)

# The correct URL for stnicholas
correct_url = "postgresql+psycopg2://carepoint_admin:Jaiden%40oct2019@139.59.161.246:5432/carepoint_hms_master?options=-c+search_path%3Dhms_tenant_stnicholas%2Cpublic&sslmode=require"

encrypted_url = encrypt_string(correct_url)

with engine.begin() as conn:
    conn.execute(
        text("UPDATE tenant SET db_connection_string = :url WHERE code = 'stnicholas'"),
        {"url": encrypted_url}
    )
print("Updated stnicholas db_connection_string!")
