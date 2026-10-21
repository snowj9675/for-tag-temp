"""SEO endpoints: stable ID-range sitemap shards and image references.

Video sitemap extensions require a real playable URL; ordinary URL+image
sitemaps are used until playback integration exists.
"""
import math
from datetime import datetime,timezone
from flask import Blueprint, Response, request, current_app
from xml.sax.saxutils import escape
from urllib.parse import quote

seo=Blueprint("seo",__name__)
SHARD_SPAN=40000
MAX_SITEMAPS=50000

def origin():
    from app import SITE_URL
    return SITE_URL or request.url_root.rstrip("/")

def xml_response(text,ttl=3600):
    response=Response(text,mimetype="application/xml; charset=utf-8")
    response.headers["Cache-Control"]=f"public, s-maxage={ttl}, stale-while-revalidate=86400"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response

def highest_id():
    from app import read_query
    rows=read_query("SELECT id FROM public.channel_videos ORDER BY id DESC LIMIT 1")
    return int(rows[0]["id"]) if rows else 0

def shard_count():
    return (highest_id() // SHARD_SPAN) + 1

@seo.route("/sitemap.xml")
def index():
    site=escape(origin())
    count=shard_count()
    if count>MAX_SITEMAPS:
        return Response("Sitemap exceeds configured bounds",status=503)
    entries=[f"<sitemap><loc>{site}/sitemaps/videos-{i}.xml</loc></sitemap>" for i in range(count)]
    entries.append(f"<sitemap><loc>{site}/sitemaps/pages.xml</loc></sitemap>")
    entries.append(f"<sitemap><loc>{site}/sitemaps/channels.xml</loc></sitemap>")
    return xml_response('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(entries)+'</sitemapindex>',ttl=21600)

@seo.route("/sitemaps/videos-<int:shard>.xml")
def videos(shard):
    if shard<0 or shard>=shard_count():
        return Response(status=404)
    from app import read_query,image_url
    lo=shard*SHARD_SPAN
    hi=lo+SHARD_SPAN
    rows=read_query("SELECT id,img FROM public.channel_videos WHERE id >= %s AND id < %s ORDER BY id LIMIT %s",(lo,hi,SHARD_SPAN))
    base=escape(origin())
    parts=['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for row in rows:
        parts.append(f'<url><loc>{base}/video/{row["id"]}</loc>')
        img=image_url(row["img"])
        if img and img.startswith(("https://","http://")):
            parts.append(f'<image:image><image:loc>{escape(img)}</image:loc></image:image>')
        parts.append('</url>')
    parts.append('</urlset>')
    return xml_response(''.join(parts),ttl=86400)

@seo.route("/sitemaps/pages.xml")
def pages():
    base=escape(origin())
    paths=('/', '/channels')
    return xml_response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f"<url><loc>{base}{p}</loc></url>" for p in paths)+'</urlset>',ttl=86400)

@seo.route("/sitemaps/channels.xml")
def channels():
    from channels import get_snapshot
    base=escape(origin())
    all_channels=get_snapshot()
    xml=['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for c in all_channels[:45000]:
        path=quote(c["name"],safe="")
        xml.append(f'<url><loc>{base}/channel/{escape(path)}</loc></url>')
    xml.append('</urlset>')
    return xml_response(''.join(xml),ttl=86400)
