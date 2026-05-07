
from sqlalchemy import create_engine, text
from app.core.config import settings

url = settings.MASTER_DATABASE_URL or settings.DATABASE_URL
print(f"Connecting to: {url}")
engine = create_engine(url)

with engine.connect() as conn:
    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
    tables = [r[0] for r in result.fetchall()]
    print(f"Tables in public schema ({len(tables)}):")
    for t in sorted(tables):
        print(f"  - {t}")

    # Also check other schemas
    result = conn.execute(text("SELECT schema_name FROM information_schema.schemata"))
    schemas = [r[0] for r in result.fetchall()]
    print(f"Schemas: {', '.join(schemas)}")
