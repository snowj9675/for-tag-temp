import os
import psycopg

sql=open("secondary_schema.sql",encoding="utf-8").read()
url=os.environ.get("DATABASE_URL_2")
if not url:
    raise RuntimeError("Missing DATABASE_URL_2 GitHub Actions secret")
with psycopg.connect(url,connect_timeout=20) as connection:
    connection.execute(sql)
print("Secondary metadata tables created or already present.")
