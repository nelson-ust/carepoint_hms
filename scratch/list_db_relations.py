from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql+psycopg2://postgres:Admin123@localhost:5432/carepoint_hms"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # List all relations (tables, indexes, etc)
    result = conn.execute(text("""
        SELECT n.nspname as schema,
               c.relname as name,
               CASE c.relkind
                 WHEN 'r' THEN 'table'
                 WHEN 'v' THEN 'view'
                 WHEN 'm' THEN 'materialized view'
                 WHEN 'i' THEN 'index'
                 WHEN 'S' THEN 'sequence'
                 WHEN 's' THEN 'special'
                 WHEN 'f' THEN 'foreign table'
                 WHEN 'p' THEN 'partitioned table'
                 WHEN 'I' THEN 'partitioned index'
               END as type
        FROM pg_catalog.pg_class c
        LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname !~ '^pg_toast'
        ORDER BY 1,2;
    """))
    for row in result:
        print(f"{row[0]}.{row[1]} ({row[2]})")
