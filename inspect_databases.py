"""Read-only catalog audit for migration planning. Does not print credentials or personal data."""
import os,json
import psycopg
from psycopg.rows import dict_row

def inspect(dsn,label):
    with psycopg.connect(dsn,connect_timeout=20,row_factory=dict_row) as db:
        with db.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute("SET LOCAL statement_timeout='20s'")
            cur.execute("""
                SELECT table_schema,table_name,column_name,data_type,udt_name
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY table_schema,table_name,ordinal_position
            """)
            schema=cur.fetchall()
            cur.execute("""
                SELECT relname AS name,pg_size_pretty(pg_total_relation_size(oid)) AS total_size
                FROM pg_class WHERE relnamespace='public'::regnamespace
                  AND relkind IN ('r','p')
                ORDER BY pg_total_relation_size(oid) DESC LIMIT 20
            """)
            sizes=cur.fetchall()
            cur.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size,
                       current_database() AS database_name
            """)
            info=cur.fetchone()
    print(f"\n=== {label} ===")
    print(json.dumps({"db":dict(info),"tables":[dict(r) for r in sizes],
        "schema":[dict(r) for r in schema]},indent=2))

if __name__=="__main__":
    for key,label in [("DATABASE_URL","catalog"),("DATABASE_URL_2","metadata")]:
        value=os.environ.get(key)
        if not value:
            print(f"{label}: secret {key} missing")
            continue
        try:
            inspect(value,label)
        except Exception as exc:
            print(f"{label}: ERROR {type(exc).__name__}: {exc}")
