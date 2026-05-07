
from app.core.config import settings
from app.core.database import DATABASE_URL, MASTER_DATABASE_URL

print(f"settings.DATABASE_URL: {settings.DATABASE_URL}")
print(f"settings.MASTER_DATABASE_URL: {settings.MASTER_DATABASE_URL}")
print(f"database.DATABASE_URL: {DATABASE_URL}")
print(f"database.MASTER_DATABASE_URL: {MASTER_DATABASE_URL}")
print(f"settings.POSTGRES_SERVER: {settings.POSTGRES_SERVER}")
