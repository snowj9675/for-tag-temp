"""Read-only channel catalog snapshot; no database GROUP BY on web requests."""
import json,os,time
from pathlib import Path
from flask import Blueprint,render_template,request,abort,make_response

channels_bp=Blueprint("channels",__name__)
FILE=Path(__file__).resolve().parent/"static"/"channels-index.json"
_cache={"mtime":None,"data":[]}
def get_snapshot():
    try:
        mtime=FILE.stat().st_mtime_ns
        if mtime!=_cache["mtime"]:
            raw=json.loads(FILE.read_text(encoding="utf-8"))
            _cache["data"]=[c for c in raw if isinstance(c,dict) and c.get("name")]
            _cache["mtime"]=mtime
    except (OSError,ValueError,TypeError):
        return []
    return _cache["data"]

@channels_bp.route("/channels")
def directory():
    all_items=get_snapshot()
    q=" ".join(request.args.get("q","").split()).casefold()[:80]
    # Small offline snapshot (~14k entries): in-process filter, no Neon query.
    filtered=[c for c in all_items if q in c["name"].casefold()] if q else all_items
    try: page=max(1,min(int(request.args.get("page",1)),10000))
    except ValueError: page=1
    size=48
    offset=(page-1)*size
    items=filtered[offset:offset+size]
    resp=make_response(render_template("channels.html",channels=items,q=q,page=page,
         has_next=offset+size<len(filtered),total=len(filtered),
         snapshot_ready=bool(all_items)))
    resp.headers["Cache-Control"]="public, s-maxage=600, stale-while-revalidate=86400"
    return resp
