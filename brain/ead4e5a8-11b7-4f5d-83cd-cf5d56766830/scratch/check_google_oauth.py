import json
import sys

db_url = "postgresql://postgres:admin1234@localhost:5432/documents_db"

def query_with_psycopg():
    import psycopg
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id, provider, status, config, created_at, updated_at FROM integration_connections WHERE provider = 'google_oauth';")
            return cur.fetchall()

def query_with_psycopg2():
    import psycopg2
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id, provider, status, config, created_at, updated_at FROM integration_connections WHERE provider = 'google_oauth';")
            return cur.fetchall()
    finally:
        conn.close()

def query_with_sqlalchemy():
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url.replace("postgresql://", "postgresql+psycopg2://"))
    with engine.connect() as conn:
        result = conn.execute(text("SELECT tenant_id, provider, status, config, created_at, updated_at FROM integration_connections WHERE provider = 'google_oauth';"))
        return [list(row) for row in result]

rows = None
for method_name, method in [
    ("psycopg (v3)", query_with_psycopg),
    ("psycopg2", query_with_psycopg2),
    ("sqlalchemy", query_with_sqlalchemy)
]:
    try:
        rows = method()
        print(f"Successfully queried database using {method_name}")
        break
    except Exception as e:
        print(f"Method {method_name} failed: {e}")

if rows is None:
    print("Could not query the database using any method.")
    sys.exit(1)

if not rows:
    print("No google_oauth connections found in integration_connections table.")
else:
    for row in rows:
        print("="*40)
        print(f"Tenant ID: {row[0]}")
        print(f"Provider: {row[1]}")
        print(f"Status: {row[2]}")
        config = row[3]
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except:
                pass
        print(f"Config: {json.dumps(config, indent=2)}")
        print(f"Created At: {row[4]}")
        print(f"Updated At: {row[5]}")
        print("="*40)
