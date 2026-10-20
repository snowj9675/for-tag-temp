import argparse,json,os,time,base64,requests,psycopg
from concurrent.futures import ThreadPoolExecutor,as_completed
from tag_test import fetch_one

API="https://api.github.com"
REPO=os.environ["GITHUB_REPOSITORY"]
TOKEN=os.environ["GH_TOKEN"]
HEAD={"Authorization":"Bearer "+TOKEN,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
PATH="progress.json"

def checkpoint_get():
    r=requests.get(f"{API}/repos/{REPO}/contents/{PATH}",headers=HEAD,timeout=20)
    r.raise_for_status()
    obj=r.json()
    return json.loads(base64.b64decode(obj["content"])),obj["sha"]

def checkpoint_put(state,sha):
    blob=base64.b64encode((json.dumps(state,indent=2)+"\n").encode()).decode()
    r=requests.put(f"{API}/repos/{REPO}/contents/{PATH}",headers=HEAD,
        json={"message":"Checkpoint video tag backfill","content":blob,"sha":sha,"branch":"main"},timeout=30)
    r.raise_for_status()
    return r.json()["content"]["sha"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--seconds",type=int,default=3300)
    ap.add_argument("--workers",type=int,default=5)
    ap.add_argument("--batch",type=int,default=100)
    a=ap.parse_args()
    if a.workers<1 or a.workers>10 or a.batch<1 or a.batch>500:ap.error("Invalid configuration")
    state,sha=checkpoint_get()
    if state.get("complete"):
        print("Already completed. No work required.")
        return
    db=psycopg.connect(os.environ["DATABASE_URL"],connect_timeout=20)
    db.execute("ALTER TABLE public.channel_videos ADD COLUMN IF NOT EXISTS tags TEXT[]")
    db.commit()
    limit=time.monotonic()+a.seconds
    done=good=bad=0
    last=state.get("last_id",0)
    batches=0
    while time.monotonic()<limit-60:
        with db.cursor() as c:
            c.execute("SELECT id,url FROM public.channel_videos WHERE id>%s AND tags IS NULL ORDER BY id LIMIT %s",(last,a.batch))
            rows=c.fetchall()
        if not rows:
            if state.get("pass",1)==1:
                state["pass"]=2
                state["last_id"]=0
                last=0
                sha=checkpoint_put(state,sha)
                print("First sweep finished; retrying previously untagged videos once.",flush=True)
                continue
            state["complete"]=True
            break
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            result=list(pool.map(lambda item:fetch_one(*item),rows))
        with db.cursor() as c:
            for obj in result:
                if obj.get("tags"):
                    c.execute("UPDATE public.channel_videos SET tags=%s WHERE id=%s AND tags IS NULL",
                              (obj["tags"],obj["id"]))
                    good+=1
                else:
                    bad+=1
                    if bad<=10:print("No tags",obj["id"],obj.get("error"),flush=True)
        db.commit()
        done+=len(rows)
        last=rows[-1][0]
        state["last_id"]=last
        state["total_processed"]=state.get("total_processed",0)+len(rows)
        state["total_tagged"]=state.get("total_tagged",0)+sum(bool(x.get("tags")) for x in result)
        state["total_failed"]=state.get("total_failed",0)+sum(not x.get("tags") for x in result)
        batches+=1
        if batches%20==0:
            sha=checkpoint_put(state,sha)
        print(f"processed={done} tagged={good} no_tags={bad} checkpoint={last}",flush=True)
    sha=checkpoint_put(state,sha)
    print(json.dumps(state,indent=2))
    db.close()

if __name__=="__main__":main()
