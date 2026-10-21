"""Resume-safe keyset migration: short transactions on primary DATABASE_URL."""
import argparse
import os
import time
import psycopg

PATTERN = r'^/prof-video-click/upload/(?:[^/]+/)*([A-Za-z0-9]+)/([A-Za-z0-9_-]+)/?$'
REPLACE = r'/\1/\2'

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--batch-size", type=int, default=2000)
    opts = p.parse_args()
    if not 1 <= opts.batch_size <= 10000:
        raise ValueError("batch-size must be between 1 and 10000")
    dsn = os.environ["DATABASE_URL"]
    cursor = 0
    total = scanned = 0
    t0 = time.monotonic()
    with psycopg.connect(dsn, connect_timeout=20, autocommit=True) as conn:
        while True:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '30s'")
                    cur.execute("""
                        SELECT id,url FROM public.channel_videos
                        WHERE id > %s
                        ORDER BY id LIMIT %s
                    """, (cursor, opts.batch_size))
                    rows = cur.fetchall()
                    if not rows:
                        break
                    cursor = rows[-1][0]
                    scanned += len(rows)
                    matching = [(rid, raw) for rid, raw in rows
                                if isinstance(raw, str)
                                and raw.startswith("/prof-video-click/upload/")]
                    if matching:
                        ids = [rid for rid, _ in matching]
                        if opts.dry_run:
                            for rid, url in matching[:2]:
                                print(f"sample id={rid}: {url}", flush=True)
                        else:
                            cur.execute("""
                                UPDATE public.channel_videos
                                SET url = regexp_replace(url, %s, %s)
                                WHERE id = ANY(%s) AND url ~ %s
                            """, (PATTERN, REPLACE, ids, PATTERN))
                            total += cur.rowcount
            if scanned % (opts.batch_size * 20) == 0 or len(rows) < opts.batch_size:
                print(f"scanned={scanned} updated={total} last_id={cursor}", flush=True)
            if len(rows) < opts.batch_size:
                break
    print(f"DONE scanned={scanned} updated={total} seconds={time.monotonic()-t0:.1f}", flush=True)

if __name__ == "__main__":
    main()
