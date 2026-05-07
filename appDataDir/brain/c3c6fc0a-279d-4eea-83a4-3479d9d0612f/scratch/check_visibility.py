
from sqlalchemy import create_engine, text
from app.core.config import settings

url = settings.DATABASE_URL # Use the app user URL
print(f"Connecting as: {url}")
engine = create_engine(url)

with engine.connect() as conn:
    result = conn.execute(text("SHOW search_path"))
    print(f"search_path: {result.scalar()}")
    
    result = conn.execute(text("SELECT current_user"))
    print(f"current_user: {result.scalar()}")
    
    # Try to select from tenant
    try:
        result = conn.execute(text("SELECT count(*) FROM tenant"))
        print(f"Tenant count: {result.scalar()}")
    except Exception as e:
        print(f"Failed to query tenant: {e}")
