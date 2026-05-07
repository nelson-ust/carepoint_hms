from app.core.config import settings
from sqlalchemy import create_engine, text

url = "postgresql+psycopg2://carepoint_admin:Jaiden%40oct2019@139.59.161.246:5432/carepoint_hms_master?sslmode=require"
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text("SELECT datname FROM pg_database")).fetchall()
    print([r[0] for r in result])
