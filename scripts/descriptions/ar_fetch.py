#!/usr/bin/env python3
"""Find each state/territory body's annual report from its official website (home page link
whose text or URL says 'annual report'), then the latest annual report PDF on that page.
Caches the AR page URL, the PDF URL and the text of the PDF's first 15 pages in
/workspace/agor-sheet/leg/cache_ar.json."""
import csv, json, re, subprocess, tempfile, html, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
ROOT = Path(__file__).resolve().parents[2]
OUT = Path("/workspace/agor-sheet/leg/cache_ar.json")
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
AR = re.compile(r"annual[\s_%20-]*reports?", re.I)

def links(base, s):
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', s, re.I | re.S):
        txt = html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        txt = re.sub(r"\s+", " ", txt).strip()
        yield urljoin(base, html.unescape(m.group(1))), txt

def year_of(u, t):
    ys = [int(y) for y in re.findall(r"20[12]\d", u + " " + t)]
    return max(ys) if ys else 0

def pdf_text(b):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(b); f.flush()
        return subprocess.run(["pdftotext", "-l", "15", f.name, "-"], capture_output=True, text=True, timeout=120).stdout

def same_site(a, b):
    ha, hb = urlparse(a).netloc.lower().removeprefix("www."), urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha) or ha.endswith(".gov.au")

def work(item):
    key, site = item
    res = {"site": site}
    try:
        r = S.get(site, timeout=25); home = r.url; s = r.text
        cands = [(u, t) for u, t in links(home, s) if (AR.search(t) or AR.search(u)) and same_site(u, home)]
        if not cands:
            for path in ["/annual-reports", "/annual-report", "/about-us/annual-reports", "/about/annual-reports", "/publications/annual-reports"]:
                u = urljoin(home, path)
                try:
                    rr = S.get(u, timeout=20)
                    if rr.status_code == 200 and AR.search(rr.text[:200000]) and "text/html" in rr.headers.get("content-type", ""):
                        cands = [(rr.url, "annual reports")]; break
                except Exception: pass
        if not cands: return key, res
        cands.sort(key=lambda x: (x[0].lower().endswith(".pdf"), year_of(*x)), reverse=False)
        page = sorted(cands, key=lambda x: (not x[0].lower().endswith(".pdf"), year_of(*x)), reverse=True)[0]
        res["ar_link"] = page[0]
        pdf = page[0] if page[0].lower().split("?")[0].endswith(".pdf") else None
        if not pdf:
            rr = S.get(page[0], timeout=25)
            if "pdf" in rr.headers.get("content-type", ""):
                pdf = rr.url; b = rr.content
            else:
                res["ar_page_text"] = re.sub(r"\s+", " ", html.unescape(re.sub(r"<(script|style)\b.*?</\1>|<[^>]+>", " ", rr.text, flags=re.S | re.I)))[:20000]
                ps = [(u, t) for u, t in links(rr.url, rr.text) if u.lower().split("?")[0].endswith(".pdf") and (AR.search(u) or AR.search(t) or year_of(u, t))]
                if ps:
                    ps.sort(key=lambda x: year_of(*x), reverse=True)
                    pdf = ps[0][0]
        if pdf:
            res["pdf"] = pdf
            if "b" not in dir() or not locals().get("b"):
                rb = S.get(pdf, timeout=60)
                b = rb.content if rb.status_code == 200 else b""
            if b[:4] == b"%PDF" and len(b) < 60_000_000:
                res["pdf_text"] = pdf_text(b)[:60000]
    except Exception as e:
        res["error"] = str(e)[:200]
    return key, res

def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    cache = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = []
    for r in rows:
        if r["Jurisdiction"] == "Commonwealth" or not r["Website Address"].strip(): continue
        need = not r["Annual Reports"].strip() or not r["Description"].strip() or r["Description method"] == "wikidata"
        k = r["Jurisdiction"] + "|" + r["Title"]
        if need and k not in cache: todo.append((k, r["Website Address"].strip()))
    print(len(todo), flush=True)
    with ThreadPoolExecutor(16) as ex:
        for i, (k, res) in enumerate(ex.map(work, todo)):
            cache[k] = res
            if i % 50 == 0:
                OUT.write_text(json.dumps(cache)); print(i, flush=True)
    OUT.write_text(json.dumps(cache))
    print("done", sum(1 for v in cache.values() if v.get("ar_link")), sum(1 for v in cache.values() if v.get("pdf_text")))

if __name__ == "__main__":
    main()
