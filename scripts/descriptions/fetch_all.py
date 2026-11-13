"""Fetch description/contact candidates for non-Commonwealth rows (and Cth gaps).
Caches raw page extracts to /workspace/agor-sheet/desc/cache_*.json"""
import csv, json, re, html, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
D = Path("/workspace/agor-sheet/desc"); ROOT = Path("/workspace/aus-gov-orgs")
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) aus-gov-orgs/1.0"
def load(n):
    p = D / f"cache_{n}.json"; return json.loads(p.read_text()) if p.exists() else {}
def save(n, d): (D / f"cache_{n}.json").write_text(json.dumps(d, indent=0))
def fetch(url, timeout=20):
    for k in range(2):
        try:
            r = S.get(url, timeout=timeout, allow_redirects=True)
            return r.status_code, r.url, r.text if "html" in r.headers.get("content-type", "") else ""
        except Exception as e:
            err = str(e)[:80]
    return 0, url, ""
def clean(s): return re.sub(r"\s+", " ", html.unescape(s or "")).strip()
def metas(s):
    out = {}
    for m in re.finditer(r"<meta\b[^>]*>", s, re.I):
        tag = m.group(0)
        k = re.search(r'(?:name|property)\s*=\s*["\']([^"\']+)', tag, re.I); c = re.search(r'content\s*=\s*"([^"]*)"|content\s*=\s*\'([^\']*)\'', tag, re.I)
        if k and c: out.setdefault(k.group(1).lower(), clean(c.group(1) or c.group(2)))
    t = re.search(r"<title[^>]*>(.*?)</title>", s, re.I | re.S)
    out["_title"] = clean(t.group(1)) if t else ""
    return out
def text(s):
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<nav.*?</nav>|<header.*?</header>|<select.*?</select>", "", s, flags=re.S | re.I)
    return re.sub(r"\n\s*\n+", "\n", html.unescape(re.sub(r"<[^>]+>", "\n", t)))
def slugs(title):
    t = title
    m = re.match(r"^(.+?),\s*((?:Department|Office|Commissioner|Minister)\b.*)$", t)
    cands = [t] + ([m.group(2) + " " + m.group(1)] if m else [])
    cands += [re.sub(r"\s*\([^)]*\)", "", c) for c in cands]
    cands += [p for c in cands for p in re.findall(r"\(([^)]+)\)", c)]
    out = []
    for c in cands:
        s = c.lower().replace("&", "and").replace("’", "").replace("'", "")
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
        for v in (s, re.sub(r"^the-", "", s)):
            if v and v not in out: out.append(v)
    return out
rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
man = {m["slug"]: m for m in csv.DictReader(open(ROOT / "icons/manifest.csv", encoding="utf-8"))}
def key(r): return r["Jurisdiction"] + "|" + r["Title"]

def portal(stage, base, juris):
    cache = load(stage)
    todo = [r for r in rows if r["Jurisdiction"] == juris and key(r) not in cache]
    def work(r):
        for s in slugs(r["Title"])[:4]:
            code, url, body = fetch(base + s)
            if code == 200 and body:
                mt = metas(body); tx = text(body)
                return key(r), {"url": url, "meta": mt, "text": tx[:20000],
                                "links": re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', body, re.S)[:400]}
        return key(r), None
    with ThreadPoolExecutor(8) as ex:
        for i, (k, v) in enumerate(ex.map(work, todo)):
            cache[k] = v
            if i % 50 == 0: print(stage, i, len(todo), flush=True); save(stage, cache)
    save(stage, cache); print(stage, "found", sum(1 for v in cache.values() if v))

def sites():
    cache = load("sites")
    urls = {}
    for r in rows:
        w = r["Website Address"].strip()
        slug = (r.get("Icon file") or "").split("/")[-1][:-4]
        if not w and slug in man: w = man[slug]["website"]
        if w:
            if not w.startswith("http"): w = "https://" + w
            urls[key(r)] = w
    ex = D / "extra_sites.json"
    if ex.exists():
        for k, u in json.loads(ex.read_text()).items(): urls.setdefault(k, u)
    todo = [(k, u) for k, u in urls.items() if k not in cache and not k.startswith("Commonwealth|")]
    def work(ku):
        k, u = ku
        res = []
        code, final, body = fetch(u)
        if code == 200 and body:
            res.append({"url": final, "meta": metas(body), "text": text(body)[:6000]})
            about = [urljoin(final, h) for h, t in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', body, re.S)
                     if re.search(r"\babout\b|who we are|our role|what we do", clean(re.sub("<[^>]+>", "", t)), re.I)]
            about = [a for a in about if urlparse(a).netloc == urlparse(final).netloc][:2]
            for a in about:
                c2, f2, b2 = fetch(a)
                if c2 == 200 and b2: res.append({"url": f2, "meta": metas(b2), "text": text(b2)[:6000]})
        return k, {"site": u, "pages": res}
    with ThreadPoolExecutor(12) as ex:
        for i, (k, v) in enumerate(ex.map(work, todo)):
            cache[k] = v
            if i % 50 == 0: print("sites", i, len(todo), flush=True); save("sites", cache)
    save("sites", cache); print("sites done", len(cache))

if __name__ == "__main__":
    st = sys.argv[1]
    if st == "wa": portal("wa", "https://www.wa.gov.au/organisation/", "WA")
    if st == "nsw": portal("nsw", "https://www.nsw.gov.au/departments-and-agencies/", "NSW")
    if st == "sites": sites()
