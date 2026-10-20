#!/usr/bin/env python3
"""Read-only Neon -> public page tag extraction smoke test."""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit, urlunsplit

import psycopg
import requests
from bs4 import BeautifulSoup

SITE_ORIGIN = "https://www.xvideos.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8",
}


def normalize_url(raw):
    """Accept relative paths, full URLs, and Markdown-wrapped URLs."""
    raw = (raw or "").strip()
    m = re.fullmatch(r"\[[^\]]+\]\((https?://[^)]+)\)", raw)
    if m:
        raw = m.group(1)
    raw = raw.replace("\\/", "/")
    if raw.startswith("/"):
        raw = SITE_ORIGIN + raw
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in (
        "www.xvideos.com", "xvideos.com"
    ):
        raise ValueError("URL has an unexpected host or scheme")
    return urlunsplit(("https", "www.xvideos.com", parsed.path, parsed.query, ""))


def extract_tags(html):
    soup = BeautifulSoup(html, "html.parser")
    tags = {}
    for meta in soup.select('meta[property="video:tag"], meta[name="keywords"]'):
        content = meta.get("content") or ""
        for item in content.split(","):
            tag = " ".join(item.split()).strip()
            if tag and tag.casefold() not in tags:
                tags[tag.casefold()] = tag
    return sorted(tags.values(), key=str.casefold)


def sample_videos(database_url, count):
    # The test never alters tables or data.
    with psycopg.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                "SELECT id, url FROM public.channel_videos "
                "WHERE url IS NOT NULL AND url <> '' "
                "ORDER BY id DESC LIMIT %s", (count,)
            )
            return cur.fetchall()


def fetch_one(video_id, raw_url):
    url = normalize_url(raw_url)
    try:
        response = requests.get(url, headers=HEADERS, timeout=(10, 25),
                                allow_redirects=True)
        response.raise_for_status()
        if urlsplit(response.url).hostname not in ("www.xvideos.com", "xvideos.com"):
            raise RuntimeError("Redirected to an unexpected host")
        tags = extract_tags(response.text)
        return {"id": video_id, "url": url, "http_status": response.status_code,
                "tags": tags, "tag_count": len(tags), "error": None}
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        return {"id": video_id, "url": url, "http_status": None,
                "tags": [], "tag_count": 0, "error": str(exc)[:300]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=5)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.sample <= 20 or not 1 <= args.workers <= 5:
        parser.error("sample must be 1..20 and workers 1..5")
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("Missing GitHub Actions secret DATABASE_URL")

    videos = sample_videos(url, args.sample)
    if not videos:
        sys.exit("No eligible video rows in public.channel_videos")
    print(f"Read {len(videos)} records. Running read-only tag extraction.", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks = [pool.submit(fetch_one, video_id, raw_url)
                 for video_id, raw_url in videos]
        for fut in as_completed(tasks):
            result = fut.result()
            results.append(result)
            print(f"id={result['id']} status={result['http_status']} "
                  f"tags={result['tag_count']} error={result['error']}", flush=True)
            if result["tags"]:
                print("  sample tags:", ", ".join(result["tags"][:12]), flush=True)

    successes = sum(bool(r["tags"]) for r in results)
    failures = sum(bool(r["error"]) for r in results)
    report = {
        "tested": len(results), "with_tags": successes, "request_errors": failures,
        "results": sorted(results, key=lambda r: r["id"])
    }
    with open("tag_test_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"RESULT: {successes}/{len(results)} pages yielded tags; "
          f"{failures} request failures.", flush=True)
    if not successes:
        sys.exit("No keywords extracted. Inspect logs/results before full-scale work.")


if __name__ == "__main__":
    main()
