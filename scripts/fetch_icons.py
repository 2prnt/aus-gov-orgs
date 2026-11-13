"""Stage 1: fetch each website's own icon (per host) into a cache.

Input: hosts collected from data/organisations.csv Website Address, Wikidata-found
sites (/workspace/icons_work/wikidata_sites.json) and fallback domains.
Output: /workspace/icons_work/cache/<host>.png|.svg and hosts.json
"""
import csv, hashlib, io, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests, urllib3
from bs4 import BeautifulSoup
from PIL import Image
import cairosvg

urllib3.disable_warnings()
ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/workspace/icons_work"); CACHE = WORK / "cache"; CACHE.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MAX = 128
# Normalised-PNG hashes of placeholder icons to reject: GovCMS platform default
# /favicon.ico (served when a site's own icon is not reachable) and a Google
# letter placeholder.
BAD = ['0af58fdd88d7b0e8d0d5c6c62db26b6e4a5a7e1d638ba1e449c763e93f5b3910', 'ed9915075ef775c63f5cdd958df264f6b82f64598aadc3c51b7a802c9e37f430']

def session():
    s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept-Language": "en-AU,en;q=0.9"}); return s

def get(s, url, **kw):
    for i in range(2):
        try:
            return s.get(url, timeout=15, allow_redirects=True, verify=False, **kw)
        except Exception:
            time.sleep(1 + i)
    return None

def decode(data, ctype=""):
    """Return (PIL RGBA image, svg_bytes|None) or (None, None)."""
    head = data[:500].lstrip().lower()
    if b"<svg" in head or (b"<?xml" in head and b"<svg" in data[:3000].lower()) or "svg" in ctype:
        try:
            png = cairosvg.svg2png(bytestring=data, output_width=256, output_height=256)
            return Image.open(io.BytesIO(png)).convert("RGBA"), data
        except Exception:
            return None, None
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        return None, None
    try:
        im = Image.open(io.BytesIO(data))
        if im.format == "ICO":
            sizes = sorted(im.ico.sizes(), key=lambda x: x[0] * x[1])
            if sizes: im.size = sizes[-1]
        im.load()
        return im.convert("RGBA"), None
    except Exception:
        return None, None

def norm_png(im):
    w, h = im.size
    if max(w, h) > MAX:
        f = MAX / max(w, h); im = im.resize((max(1, round(w * f)), max(1, round(h * f))), Image.LANCZOS); w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0)); canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)
    b = io.BytesIO(); canvas.save(b, "PNG", optimize=True); return b.getvalue(), side

def candidates(s, base_url):
    r = get(s, base_url)
    cands = []; final = base_url
    if r is not None and r.ok and "html" in r.headers.get("content-type", "html"):
        final = r.url
        soup = BeautifulSoup(r.text[:400000], "html.parser")
        base = soup.find("base", href=True); bhref = urljoin(final, base["href"]) if base else final
        for l in soup.find_all("link", href=True):
            rel = " ".join(l.get("rel") or []).lower()
            if "icon" not in rel or "mask-icon" in rel: continue
            href = urljoin(bhref, l["href"].strip()); sizes = l.get("sizes", "") or ""; typ = (l.get("type") or "").lower()
            m = re.findall(r"(\d+)x(\d+)", sizes); sz = max([int(a) for a, b in m], default=0)
            if "apple-touch" in rel and not sz: sz = 180
            if "svg" in typ or href.lower().split("?")[0].endswith(".svg"): sz = max(sz, 255)
            cands.append((sz, href))
        mf = soup.find("link", rel=lambda v: v and "manifest" in [x.lower() for x in (v if isinstance(v, list) else [v])], href=True)
        if mf:
            mr = get(s, urljoin(bhref, mf["href"]))
            try:
                for ic in (mr.json().get("icons") or [])[:10]:
                    m = re.findall(r"(\d+)x(\d+)", ic.get("sizes", "")); cands.append((max([int(a) for a, b in m], default=0), urljoin(mr.url, ic["src"])))
            except Exception:
                pass
    p = urlparse(final)
    cands.append((1, f"{p.scheme or 'https'}://{p.netloc}/favicon.ico"))
    if final != base_url:
        q = urlparse(base_url); cands.append((1, f"{q.scheme}://{q.netloc}/favicon.ico"))
    seen = set(); out = []
    for sz, u in sorted(cands, key=lambda x: -x[0]):
        if u not in seen and not u.startswith("data:"): seen.add(u); out.append((sz, u))
    return out, final

def fetch_host(host_url):
    s = session(); host = urlparse(host_url).netloc.lower()
    key = re.sub(r"[^a-z0-9.-]", "_", host)
    res = {"host": host, "url": host_url, "ok": False}
    try:
        cands, final = candidates(s, host_url)
        if (not cands or len(cands) <= 2) and host_url.startswith("http://"):
            c2, f2 = candidates(s, "https://" + host_url[7:])
            if len(c2) > len(cands): cands, final = c2, f2
        best = None; svg = None; svg_src = None
        for sz, u in cands[:8]:
            r = get(s, u)
            if r is None or not r.ok or len(r.content) < 50: continue
            im, sv = decode(r.content, r.headers.get("content-type", ""))
            if im is None: continue
            if hashlib.sha256(norm_png(im)[0]).hexdigest() in BAD: continue
            if sv is not None and svg is None: svg, svg_src = sv, u
            dim = max(im.size)
            if best is None or dim > best[0]: best = (dim, u, im)
            if dim >= MAX: break
        if best:
            png, side = norm_png(best[2])
            (CACHE / f"{key}.png").write_bytes(png)
            if svg: (CACHE / f"{key}.svg").write_bytes(svg)
            res.update(ok=True, src=best[1], orig=best[0], side=side, file=f"{key}.png", svg=f"{key}.svg" if svg else "", svg_src=svg_src or "", final=final, method="own-site")
        else:
            # third-party fallback, recorded as such
            r = get(s, f"https://www.google.com/s2/favicons?domain={host}&sz=128")
            if r is not None and r.ok and r.status_code == 200:
                im, _ = decode(r.content)
                if im is not None and hashlib.sha256(norm_png(im)[0]).hexdigest() not in BAD:
                    png, side = norm_png(im)
                    (CACHE / f"{key}.png").write_bytes(png)
                    res.update(ok=True, src=r.url, orig=max(im.size), side=side, file=f"{key}.png", svg="", method="google-s2", s2_sha=hashlib.sha256(r.content).hexdigest())
    except Exception as e:
        res["error"] = repr(e)[:200]
    return res

def host_root(u):
    u = u.strip()
    if not u: return None
    if "://" not in u: u = "http://" + u
    p = urlparse(u)
    if not p.netloc: return None
    return f"{p.scheme}://{p.netloc.lower()}/"

FALLBACK_URLS = [
 "https://www.defence.gov.au/", "https://www.australia.gov.au/", "https://www.pmc.gov.au/", "https://www.finance.gov.au/",
 "https://www.infrastructure.gov.au/", "https://www.industry.gov.au/", "https://www.agriculture.gov.au/", "https://www.ag.gov.au/",
 "https://www.health.gov.au/", "https://treasury.gov.au/", "https://www.dcceew.gov.au/", "https://www.homeaffairs.gov.au/",
 "https://www.dfat.gov.au/", "https://www.education.gov.au/", "https://www.dva.gov.au/", "https://www.dewr.gov.au/", "https://www.dss.gov.au/",
 "https://www.nsw.gov.au/", "https://www.vic.gov.au/", "https://www.qld.gov.au/", "https://www.wa.gov.au/", "https://www.sa.gov.au/",
 "https://www.tas.gov.au/", "https://www.act.gov.au/", "https://nt.gov.au/",
 "https://www.health.nsw.gov.au/", "https://www.dcj.nsw.gov.au/", "https://www.treasury.nsw.gov.au/", "https://www.dpi.nsw.gov.au/",
 "https://www.planning.nsw.gov.au/", "https://www.transport.nsw.gov.au/", "https://education.nsw.gov.au/", "https://www.energy.nsw.gov.au/",
 "https://www.health.vic.gov.au/", "https://www.deeca.vic.gov.au/", "https://djsir.vic.gov.au/", "https://www.justice.vic.gov.au/",
 "https://www.dtf.vic.gov.au/", "https://www.transport.vic.gov.au/", "https://www.dffh.vic.gov.au/", "https://www.education.vic.gov.au/",
]

def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    wd = json.loads((WORK / "wikidata_sites.json").read_text()) if (WORK / "wikidata_sites.json").exists() else {}
    urls = set(FALLBACK_URLS)
    for r in rows:
        h = host_root(r["Website Address"])
        if h: urls.add(h)
    for v in wd.values():
        if v and host_root(v["website"]): urls.add(host_root(v["website"]))
    out_path = WORK / "hosts.json"
    done = json.loads(out_path.read_text()) if out_path.exists() else {}
    import os
    if os.environ.get("RETRY"):  # retry hosts that failed or only got a third-party icon
        bad_files = {v["file"] for v in done.values() if v.get("ok") and hashlib.sha256((CACHE / v["file"]).read_bytes()).hexdigest() in BAD}
        done = {k: v for k, v in done.items() if v.get("ok") and v.get("method") == "own-site" and v["file"] not in bad_files}
    todo = sorted(u for u in urls if u not in done)
    print("hosts to fetch", len(todo), flush=True)
    with ThreadPoolExecutor(int(__import__('os').environ.get('WORKERS', '12'))) as ex:
        for i, res in enumerate(ex.map(fetch_host, todo)):
            done[todo[i]] = res
            if i % 50 == 0:
                out_path.write_text(json.dumps(done, indent=1)); print(i, sum(1 for v in done.values() if v.get("ok")), flush=True)
    out_path.write_text(json.dumps(done, indent=1))
    print("done", len(done), "ok", sum(1 for v in done.values() if v.get("ok")))

if __name__ == "__main__": main()
