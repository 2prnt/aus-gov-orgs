import csv, json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
ROOT=Path("/workspace/aus-gov-orgs"); OUT=Path("/workspace/agor-sheet/desc/cache_wd.json")
S=requests.Session(); S.headers["User-Agent"]="aus-gov-orgs/1.0 (https://github.com/2prnt/aus-gov-orgs)"
API="https://www.wikidata.org/w/api.php"
AUS=re.compile(r"australia|new south wales|victoria|queensland|tasmania|northern territory|capital territory|western australia|south australia|\bnsw\b|\bact\b",re.I)
def norm(s): return re.sub(r"[^a-z0-9]+"," ",s.lower().replace("&","and")).strip()
def get(p):
    for i in range(4):
        try:
            r=S.get(API,params={**p,"format":"json"},timeout=20)
            if r.status_code==429: time.sleep(5*(i+1)); continue
            return r.json()
        except Exception: time.sleep(2*(i+1))
    return {}
def val(cl,p):
    out=[]
    for c in cl.get(p,[]):
        if c.get("rank")=="deprecated": continue
        v=c["mainsnak"].get("datavalue",{}).get("value")
        if isinstance(v,dict) and "id" in v: v=v["id"]
        elif isinstance(v,dict) and "time" in v: v=v["time"]
        if v: out.append(v)
    return out
def lookup(title):
    t=re.sub(r"\s*\([^)]*\)","",title).strip()
    res=get({"action":"wbsearchentities","search":t[:250],"language":"en","limit":7,"type":"item"})
    ids=[h["id"] for h in res.get("search",[]) if norm(h.get("match",{}).get("text",""))==norm(t) or norm(h.get("label",""))==norm(t)]
    if not ids: return None
    ents=get({"action":"wbgetentities","ids":"|".join(ids),"props":"claims|descriptions|labels|sitelinks"}).get("entities",{})
    for q in ids:
        e=ents.get(q,{}); cl=e.get("claims",{}); desc=e.get("descriptions",{}).get("en",{}).get("value","")
        if "Q408" not in val(cl,"P17") and not AUS.search(desc): continue
        if re.search(r"\b(person|politician|human|album|song|film|ship|building|school|street)\b",desc,re.I): continue
        return {"qid":q,"desc":desc,"site":val(cl,"P856"),"inception":val(cl,"P571"),"dissolved":val(cl,"P576"),
                "parent":val(cl,"P749"),"enwiki":e.get("sitelinks",{}).get("enwiki",{}).get("title")}
    return None
rows=list(csv.DictReader(open(ROOT/"data/organisations.csv",encoding="utf-8")))
cache=json.loads(OUT.read_text()) if OUT.exists() else {}
todo=[r for r in rows if r["Jurisdiction"]!="Commonwealth" and r["Jurisdiction"]+"|"+r["Title"] not in cache]
def work(r): return r["Jurisdiction"]+"|"+r["Title"], lookup(r["Title"])
with ThreadPoolExecutor(4) as ex:
    for i,(k,v) in enumerate(ex.map(work,todo)):
        cache[k]=v
        if i%100==0: print(i,len(todo),flush=True); OUT.write_text(json.dumps(cache))
OUT.write_text(json.dumps(cache)); print("done",sum(1 for v in cache.values() if v))
