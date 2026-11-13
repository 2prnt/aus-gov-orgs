import re, json, html
from concurrent.futures import ThreadPoolExecutor
import requests
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 aus-gov-orgs/1.0"
sm=S.get("https://www.service.nsw.gov.au/sitemap.xml",timeout=30).text
urls=sorted(set(u for u in re.findall(r"<loc>([^<]*nswgovdirectory/[^<]+)</loc>",sm)))
def text(s):
    t=re.sub(r'<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<nav.*?</nav>|<header.*?</header>|<footer.*?</footer>','',s,flags=re.S)
    return re.sub(r'\n\s*\n+','\n',html.unescape(re.sub(r'<[^>]+>','\n',t)))
def work(u):
    try: s=S.get(u,timeout=30).text
    except Exception: return u,None
    t=text(s)
    h1=re.search(r"<h1[^>]*>(.*?)</h1>",s,re.S)
    name=re.sub(r"\s+"," ",html.unescape(re.sub("<[^>]+>","",h1.group(1)))).strip() if h1 else ""
    i=t.find(name+"\n") if name else -1
    return u,{"name":name,"text":t,"mailto":re.findall(r'href="mailto:([^"]+)"',s),"tel":re.findall(r'href="tel:([^"]+)"',s)}
res={}
with ThreadPoolExecutor(8) as ex:
    for u,d in ex.map(work,urls): res[u]=d
json.dump(res,open("/workspace/agor-sheet/desc/cache_nswdir.json","w"))
print(len(urls),sum(1 for v in res.values() if v))
