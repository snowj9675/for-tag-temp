import os,re,json
from urllib.parse import quote
from flask import Flask,render_template,request,abort,make_response,jsonify,url_for
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

app=Flask(__name__)
app.config["SECRET_KEY"]=os.environ.get("SECRET_KEY","not-used-for-session")
DATABASE_URL=os.environ.get("DATABASE_URL","")
DATABASE_URL_2=os.environ.get("DATABASE_URL_2","")
IMAGE_DOMAIN=os.environ.get("IMAGE_DOMAIN","https://thumb-cdn77.xvideos-cdn.com").rstrip("/")
SITE_URL=os.environ.get("SITE_URL","").rstrip("/")
SITE_NAME=os.environ.get("SITE_NAME","XXX World")
BRAND_ASSET_BASE_URL=os.environ.get("BRAND_ASSET_BASE_URL","").rstrip("/")
PAGE_SIZE=max(12,min(int(os.environ.get("PAGE_SIZE","36")),60))
pool=None
metadata_pool=None

def db():
    global pool
    if pool is None:
        if not DATABASE_URL: raise RuntimeError("Missing DATABASE_URL")
        pool=ConnectionPool(conninfo=DATABASE_URL,min_size=0,max_size=3,open=True,
            kwargs={"row_factory":dict_row,"connect_timeout":8},timeout=12)
    return pool

def read_query(sql,params=()):
    with db().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = 8000")
            cur.execute(sql,params)
            return cur.fetchall()

def creator_profile(name):
    """Optional indexed creator description lookup in separate metadata database."""
    global metadata_pool
    if not DATABASE_URL_2 or not name:
        return None
    try:
        if metadata_pool is None:
            metadata_pool=ConnectionPool(conninfo=DATABASE_URL_2,min_size=0,max_size=1,
                open=True,kwargs={"row_factory":dict_row,"connect_timeout":3},timeout=4)
        with metadata_pool.connection() as connection:
            with connection.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = 2000")
                cur.execute("SELECT description,banner_url,avatar_url FROM public.channel_profiles WHERE channel_name=%s",(name,))
                return cur.fetchone()
    except Exception:
        app.logger.warning("Creator profile metadata unavailable",exc_info=False)
        return None

def image_url(value):
    if not value:return ""
    value=str(value).strip()
    if value.startswith(("https://","http://")):return value
    if value.startswith("//"):return "https:"+value
    return IMAGE_DOMAIN+"/"+value.lstrip("/")

def preview_url(value):
    full=image_url(value)
    m=re.search(r"(.*/0/)[^/?#]+(?:\?.*)?$",full)
    return m.group(1)+"preview.mp4" if m else ""

def fmt_views(v):
    try: n=int(v or 0)
    except (ValueError,TypeError):return "0"
    for count,suffix in ((10**9,"B"),(10**6,"M"),(10**3,"K")):
        if n>=count:return f"{n/count:.1f}{suffix}"
    return str(n)

def channel_path(name):return "/channel/"+quote(name or "",safe="")
def video_path(vid):return "/video/"+str(vid)
def brand_asset(filename):
    return BRAND_ASSET_BASE_URL+"/"+filename if BRAND_ASSET_BASE_URL else "/static/"+filename

def canonical(path):
    return (SITE_URL or request.url_root.rstrip("/"))+path

@app.context_processor
def helpers():
    return dict(site_name=SITE_NAME,image_url=image_url,preview_url=preview_url,
       format_views=fmt_views,channel_path=channel_path,video_path=video_path,
       canonical=canonical,brand_asset=brand_asset,has_external_brand=bool(BRAND_ASSET_BASE_URL))
FIELDS="id,title,img,views,duration,rating,rating_percentage,channel_name"

@app.route("/")
def home():
    sort=request.args.get("sort","recent")
    if sort not in ("recent","popular","top"):sort="recent"
    after=request.args.get("after","")
    n=PAGE_SIZE+1
    if sort=="recent":
        pivot=int(after) if after.isdigit() else None
        rows=read_query(f"SELECT {FIELDS} FROM public.channel_videos "
          +("WHERE id < %s " if pivot else "")+"ORDER BY id DESC LIMIT %s",
          (pivot,n) if pivot else (n,))
        encode=lambda row:str(row["id"])
    else:
        col="views" if sort=="popular" else "rating_percentage"
        params=[]
        where=f"WHERE {col} IS NOT NULL"
        try:
            v,ident=after.split(":",1)
            pivot=(float(v),int(ident)) if col=="rating_percentage" else (int(v),int(ident))
            where+=f" AND ({col},id)<(%s,%s)"
            params.extend(pivot)
        except (ValueError,TypeError):pass
        rows=read_query(f"SELECT {FIELDS} FROM public.channel_videos {where} "
              f"ORDER BY {col} DESC NULLS LAST,id DESC LIMIT %s",(*params,n))
        encode=lambda row:f"{row[col]}:{row['id']}"
    more=len(rows)>PAGE_SIZE
    rows=rows[:PAGE_SIZE]
    resp=make_response(render_template("home.html",videos=rows,sort=sort,
       next_cursor=encode(rows[-1]) if more else None))
    resp.headers["Cache-Control"]="public, s-maxage=180, stale-while-revalidate=900"
    return resp

@app.route("/channel/<path:name>")
def channel(name):
    if not name or len(name)>250:abort(404)
    after=request.args.get("after","")
    pivot=int(after) if after.isdigit() else None
    where="channel_name=%s"
    params=[name]
    if pivot:where+=" AND id<%s";params.append(pivot)
    rows=read_query(f"SELECT {FIELDS} FROM public.channel_videos WHERE {where} ORDER BY id DESC LIMIT %s",(*params,PAGE_SIZE+1))
    more=len(rows)>PAGE_SIZE
    rows=rows[:PAGE_SIZE]
    if not rows and not pivot:abort(404)
    resp=make_response(render_template("channel.html",name=name,profile=creator_profile(name),videos=rows,
           next_cursor=str(rows[-1]["id"]) if more else None))
    resp.headers["Cache-Control"]="public, s-maxage=300, stale-while-revalidate=3600"
    return resp

@app.route("/video/<int:vid>")
def video(vid):
    data=read_query("SELECT id,url,title,img,rating,rating_percentage,views,duration,channel_name FROM public.channel_videos WHERE id=%s",(vid,))
    if not data:abort(404)
    item=data[0]
    related=[]
    if item.get("channel_name"):
        related=read_query(f"SELECT {FIELDS} FROM public.channel_videos WHERE channel_name=%s AND id<>%s ORDER BY id DESC LIMIT 12",(item["channel_name"],vid))
    description=f"Explore {item['title']} on {SITE_NAME}."
    if item.get("channel_name"):description+=f" Creator: {item['channel_name']}."
    # Honest JSON-LD: metadata for the web page, not fake playable video data.
    structured={"@context":"https://schema.org","@type":"WebPage",
      "name":item["title"],"description":description,"url":canonical(video_path(vid)),
      "primaryImageOfPage":image_url(item["img"])}
    resp=make_response(render_template("video.html",video=item,related=related,
        description_text=description,structured=structured))
    resp.headers["Cache-Control"]="public, s-maxage=300, stale-while-revalidate=1800"
    return resp

@app.route("/search")
def search():
    term=" ".join(request.args.get("q","").split())[:100]
    after=request.args.get("after","")
    pivot=int(after) if after.isdigit() else None
    rows=[]
    if len(term)>=2:
        params=[term]
        where="to_tsvector('simple',coalesce(title,'')) @@ plainto_tsquery('simple',%s)"
        if pivot:where+=" AND id<%s";params.append(pivot)
        rows=read_query(f"SELECT {FIELDS} FROM public.channel_videos WHERE {where} ORDER BY id DESC LIMIT %s",(*params,PAGE_SIZE+1))
    more=len(rows)>PAGE_SIZE
    rows=rows[:PAGE_SIZE]
    resp=make_response(render_template("search.html",term=term,videos=rows,
         next_cursor=str(rows[-1]["id"]) if more else None))
    resp.headers["Cache-Control"]="public, s-maxage=90"
    resp.headers["X-Robots-Tag"]="noindex, follow"
    return resp

@app.route("/robots.txt")
def robots():
    txt="User-agent: *\nAllow: /\nDisallow: /search\nSitemap: "+canonical("/sitemap.xml")+"\n"
    resp=app.response_class(txt,mimetype="text/plain")
    resp.headers["Cache-Control"]="public, s-maxage=86400"
    return resp

@app.route("/health")
def health():return jsonify(status="ok")

@app.errorhandler(404)
def missing(_):return render_template("404.html"),404
@app.errorhandler(500)
def failure(_):return render_template("500.html"),500

from seo_routes import seo
from channels import channels_bp
app.register_blueprint(seo)
app.register_blueprint(channels_bp)

if __name__=="__main__":app.run(debug=True,port=5000)
