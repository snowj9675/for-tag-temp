#!/usr/bin/env python3
"""Import video->categories mappings to Neon database 2 from CSV/JSONL/JSON.
Never modifies DATABASE_URL catalog. Re-running is idempotent (upsert).
Input objects must contain video_id/id and categories/category.
"""
import argparse,csv,json,os,re,sys,time
from pathlib import Path
import psycopg

def clean_categories(value):
    if value is None:return []
    if isinstance(value,str):
        value=value.strip()
        if value.startswith("["):
            try:value=json.loads(value)
            except json.JSONDecodeError:pass
        if isinstance(value,str):value=re.split(r"[,|]",value)
    if not isinstance(value,(list,tuple,set)):return []
    result={}
    for entry in value:
        if not isinstance(entry,str):continue
        s=" ".join(entry.strip().split())
        if not 0<len(s)<=100:continue
        result.setdefault(s.casefold(),s)
    return list(result.values())[:64]

def parse_row(obj):
    if not isinstance(obj,dict):return None
    raw_id=obj.get("video_id",obj.get("id"))
    try:
        if isinstance(raw_id,bool):return None
        vid=int(raw_id)
        if vid<=0 or vid>=2**63:return None
    except (TypeError,ValueError,OverflowError):return None
    cats=clean_categories(obj.get("categories",obj.get("category")))
    return (vid,cats) if cats else None

def iter_input(path):
    suffix=path.suffix.lower()
    if suffix==".csv":
        with path.open(encoding="utf-8-sig",newline="") as f:
            yield from csv.DictReader(f)
    elif suffix==".jsonl":
        with path.open(encoding="utf-8-sig") as f:
            for line in f:
                if line.strip():yield json.loads(line)
    elif suffix==".json":
        # Intended for smaller JSON arrays; JSONL recommended for large files.
        with path.open(encoding="utf-8-sig") as f:data=json.load(f)
        if not isinstance(data,list):raise ValueError("JSON must be an array of records")
        yield from data
    else:raise ValueError("Use .csv, .jsonl or .json input")

def write_batch(conn,batch):
    # Deduplicate IDs within each chunk to keep ON CONFLICT deterministic.
    items={vid:cats for vid,cats in batch}
    with conn.cursor() as c:
        c.executemany("""
          INSERT INTO public.video_categories(video_id,categories)
          VALUES (%s,%s)
          ON CONFLICT(video_id) DO UPDATE SET
            categories=EXCLUDED.categories
          WHERE public.video_categories.categories IS DISTINCT FROM EXCLUDED.categories
        """,list(items.items()))
    conn.commit()
    return len(items)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True,help="CSV, JSONL or JSON mapping file")
    parser.add_argument("--batch",type=int,default=2000)
    parser.add_argument("--limit",type=int,default=None)
    args=parser.parse_args()
    if args.batch<1 or args.batch>10000:parser.error("batch must be 1..10000")
    path=Path(args.input)
    if not path.is_file():parser.error(f"Missing file: {path}")
    dsn=os.environ.get("DATABASE_URL_2")
    if not dsn:sys.exit("DATABASE_URL_2 missing; nothing was written")
    processed=invalid=committed=0
    start=time.monotonic()
    batch=[]
    with psycopg.connect(dsn,connect_timeout=20) as conn:
        # This script never creates a table implicitly; set up schema via Action first.
        with conn.cursor() as c:
            c.execute("SELECT to_regclass('public.video_categories')")
            if c.fetchone()[0] is None:sys.exit("Run setup-secondary-db Action first")
        conn.commit()
        try:
            for raw in iter_input(path):
                if args.limit is not None and processed>=args.limit:break
                processed+=1
                item=parse_row(raw)
                if item is None:
                    invalid+=1
                    continue
                batch.append(item)
                if len(batch)>=args.batch:
                    committed+=write_batch(conn,batch)
                    batch.clear()
                    print(f"scanned={processed:,} accepted={committed:,} invalid={invalid:,}",flush=True)
            if batch:committed+=write_batch(conn,batch)
        except Exception:
            conn.rollback()
            raise
        with conn.cursor() as c:
            c.execute("SELECT count(*) FROM public.video_categories")
            total=c.fetchone()[0]
    print(json.dumps({"rows_scanned":processed,"accepted_this_run":committed,
       "invalid_or_empty":invalid,"secondary_total":total,
       "seconds":round(time.monotonic()-start,1)},indent=2))
    print("Source data was not deleted or modified.")

if __name__=="__main__":main()
