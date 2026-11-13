import requests, re, html, json, sys
from concurrent.futures import ThreadPoolExecutor
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (aus-gov-orgs research)"
OUT="/workspace/agor-sheet/desc/qld_register.json"
FIELDS=["Body Name","Body Description","Body Function","Constitution Date","Contact Officer Name","Street Address","Postal Address","Phone Number","Email","Last Updated","Body is Active","Reporting Requirements","Body Region","Approval Process","Website","Legislative Provision","Department","Portfolio"]
def text(s):
    t=re.sub(r'<script.*?</script>|<style.*?</style>','',s,flags=re.S)
    t=html.unescape(re.sub(r'<[^>]+>','\n',t)); return re.sub(r'[ \t\r]+',' ',re.sub(r'\n\s*\n+','\n',t))
def get(i):
    for k in range(3):
        try:
            r=S.get(f"https://governmentbodies.premiers.qld.gov.au/BodyDisplay.aspx?Parameter={i}",timeout=30)
            break
        except Exception: r=None
    if r is None or len(r.text)<16500: return i,None
    t=text(r.text)
    d={}
    labels=re.findall(r'\n ?([A-Z][A-Za-z\' ]{2,40}): ?\n',t)
    parts=re.split(r'\n ?([A-Z][A-Za-z\' ]{2,40}): ?\n',t)
    for a,b in zip(parts[1::2],parts[2::2]):
        if a not in d: d[a]=b.strip().split("\nMembers\n")[0].strip()
    links=re.findall(r'href="(https?://(?!www\.qld\.gov|www\.premiers|www\.smartjobs)[^"]+)"',r.text)
    d["_links"]=links
    return i,d
res={}
with ThreadPoolExecutor(8) as ex:
    for i,d in ex.map(get, range(1,int(sys.argv[1]))):
        if d: res[i]=d
        if i%200==0: print(i,len(res),flush=True)
json.dump(res,open(OUT,"w"),indent=1)
print("done",len(res))
