from app.core.config import settings
from sqlalchemy import create_engine, text

url = "postgresql+psycopg2://carepoint_admin:Jaiden%40oct2019@139.59.161.246:5432/carepoint_hms_master?options=-c+search_path%3Dhms_tenant_stnicholas%2Cpublic&sslmode=require"
engine = create_engine(url)
try:
    with engine.connect() as conn:
        print("Connected successfully!")
except Exception as e:
    print("Connection failed:", e)
