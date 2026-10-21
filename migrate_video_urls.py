"""One-off idempotent Neon catalog URL normalization using DATABASE_URL.

Only legacy /prof-video-click/upload/.../<video-code>/<slug> values are updated.
Use --dry-run to inspect without writes. No schema changes.
"""
import argparse
import os
import psycopg

OLD = r'^/prof-video-click/upload/(?:[^/]+/)*[A-Za-z0-9]+/[A-Za-z0-9_-]+/?$'
CAPTURE = r'^/prof-video-click/upload/(?:[^/]+/)*([A-Za-z0-9]+)/([A-Za-z0-9_-]+)/?$'
REPLACEMENT = r'/\1/\2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("Missing DATABASE_URL GitHub Actions secret")
    with psycopg.connect(dsn, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout='120s'")
            cur.execute("SELECT count(*) FROM public.channel_videos WHERE url ~ %s", (OLD,))
            before = cur.fetchone()[0]
            print(f"Matching legacy URLs: {before}")
            cur.execute("""
                SELECT id, url,
                       regexp_replace(url, %s, %s) AS normalized
                FROM public.channel_videos WHERE url ~ %s
                ORDER BY id DESC LIMIT 10
            """, (CAPTURE, REPLACEMENT, OLD))
            for video_id, old, new in cur.fetchall():
                print(f"Sample id={video_id}: {old} -> {new}")
            if args.dry_run:
                print("DRY RUN: no changes committed")
                conn.rollback()
                return
            if not before:
                print("No changes needed (idempotent)")
                return
            cur.execute("""
                UPDATE public.channel_videos
                   SET url = regexp_replace(url, %s, %s)
                 WHERE url ~ %s
            """, (CAPTURE, REPLACEMENT, OLD))
            updated = cur.rowcount
            if updated != before:
                raise RuntimeError(f"Count mismatch expected={before} changed={updated}; rolling back")
            cur.execute("SELECT count(*) FROM public.channel_videos WHERE url ~ %s", (OLD,))
            remaining = cur.fetchone()[0]
            if remaining:
                raise RuntimeError(f"{remaining} matching legacy URLs remain; rolling back")
            conn.commit()
            print(f"COMMITTED: {updated} URL rows normalized. Remaining legacy rows: {remaining}")


if __name__ == "__main__":
    main()
