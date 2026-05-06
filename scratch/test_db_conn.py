from sqlalchemy import create_engine, text
engine = create_engine("postgresql+psycopg2://postgres:Admin123@localhost:5432/carepoint_hms_test")
with engine.connect() as conn:
    print("Connected!")
    conn.execute(text("CREATE TABLE IF NOT EXISTS test_table (id serial primary key, name text)"))
    conn.execute(text("INSERT INTO test_table (name) VALUES ('test')"))
    res = conn.execute(text("SELECT name FROM test_table")).fetchone()
    print(f"Found: {res[0]}")
    conn.commit()
print("Success!")
