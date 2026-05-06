import os
from app.core.database import engine
from app.models.base import TenantBase, MasterBase
import app.models.all_models

from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from app.seeds.seed_data import seed_demo_data

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_new_tables():
    print("Refreshing test database schema (aggressive drop)...")
    with engine.connect() as conn:
        # Drop all tables in public schema
        conn.execute(text("""
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO postgres;
            GRANT ALL ON SCHEMA public TO public;
        """))
        conn.commit()
        
    print("Creating all tables...")
    with engine.connect() as conn:
        TenantBase.metadata.create_all(bind=conn)
        MasterBase.metadata.create_all(bind=conn)
        conn.commit()
    
    print("Seeding baseline demo data (SDPs, Facilities, etc.)...")
    db = SessionLocal()
    try:
        seed_demo_data(db, seed_security_first=True)
    finally:
        db.close()
        
    print("Done.")

if __name__ == "__main__":
    # Ensure we are hitting the test database
    test_db_url = os.environ.get(
        "CAREPOINT_HMS_TEST_DATABASE_URL", 
        "postgresql+psycopg2://postgres:Admin123@localhost:5432/carepoint_hms_test"
    )
    os.environ["CAREPOINT_HMS_DATABASE_URL"] = test_db_url
    create_new_tables()
