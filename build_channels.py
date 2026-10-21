"""Generate a static channel directory snapshot WITHOUT writing to Neon."""
import json,os,pathlib,sys
import psycopg
from psycopg.rows import dict_row
from datetime import datetime,timezone

def main():
    dsn=os.environ.get("DATABASE_URL")
    if not dsn: raise RuntimeError("DATABASE_URL secret missing")
    output=pathlib.Path("static/channels-index.json")
    with psycopg.connect(dsn,connect_timeout=20,row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '300s'")
            # Weekly index scan, never a GROUP BY in a visitor request.
            cur.execute("""
                SELECT channel_name AS name, COUNT(*)::integer AS count
                FROM public.channel_videos
                WHERE channel_name IS NOT NULL AND channel_name <> ''
                GROUP BY channel_name
                ORDER BY COUNT(*) DESC, channel_name ASC
            """)
            records=[{"name":r["name"],"count":r["count"]} for r in cur]
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(records,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(f"Saved {len(records)} creator summaries -> {output}")
if __name__=="__main__":main()
