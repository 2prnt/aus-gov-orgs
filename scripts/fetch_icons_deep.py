"""Stage 1b: deeper icon search for hosts whose icon failed the quality bar.

Quality bar: normalised PNG >= 1,000 bytes, at least 32 px, not blank. Looks at
link icons, web-app manifest icons, /apple-touch-icon.png, header <img> logos
(src/alt/class/id containing "logo" or "crest"), og:image / twitter:image when
square-ish, and SVGs (rasterised). Then Google's favicon service at 128 px.
Small sources are never upscaled.
"""
import hashlib, io, json, re, sys, os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from fetch_icons import session, get, decode, norm_png, CACHE, WORK, BAD

MIN_BYTES = 1000

def is_blank(im):
    a = im.getchannel("A"); hist = a.histogram(); n = im.size[0] * im.size[1]
    if sum(hist[30:]) / n < 0.03: return True
    lo, hi = im.convert("L").getextrema()
    if hi - lo < 8 and a.getextrema()[0] > 200: return True  # solid opaque square
    # all-white artwork on transparency (invisible on a light page)
    from PIL import ImageStat
    mask = a.point(lambda v: 255 if v > 128 else 0)
    if mask.getbbox() and ImageStat.Stat(im.convert("L"), mask).mean[0] > 235: return True
    return False

def quality(png_bytes):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    return len(png_bytes) >= MIN_BYTES and im.size[0] >= 32 and not is_blank(im) and hashlib.sha256(png_bytes).hexdigest() not in BAD

def deep_candidates(s, url):
    out = []
    r = get(s, url)
    if r is None or not r.ok: return out, url
    final = r.url
    soup = BeautifulSoup(r.text[:600000], "html.parser")
    for l in soup.find_all("link", href=True):
        rel = " ".join(l.get("rel") or []).lower()
        if "icon" in rel and "mask" not in rel:
            out.append(("icon", urljoin(final, l["href"].strip())))
        if "manifest" in rel:
            mr = get(s, urljoin(final, l["href"]))
            try:
                for ic in (mr.json().get("icons") or [])[:10]: out.append(("icon", urljoin(mr.url, ic["src"])))
            except Exception: pass
    p = urlparse(final)
    for path in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
        out.append(("icon", f"{p.scheme}://{p.netloc}{path}"))
    for img in soup.find_all("img")[:80]:
        src = img.get("src") or img.get("data-src") or ""
        meta = " ".join([src, img.get("alt", ""), " ".join(img.get("class") or []), img.get("id", "") or ""] +
                        [" ".join(par.get("class") or []) + " " + (par.get("id") or "") for par in img.parents if par.name in ("a", "div", "header", "span")][:3]).lower()
        a = img.find_parent("a")
        home = a is not None and urlparse(urljoin(final, a.get("href") or "x")).path.rstrip("/") in ("", "/index.html", "/home") and urlparse(urljoin(final, a.get("href") or "x")).netloc.lower().replace("www.", "") == urlparse(final).netloc.lower().replace("www.", "")
        in_header = img.find_parent("header") is not None
        if src and not src.startswith("data:") and re.search(r"logo|crest|brand|coat", meta) and (home or in_header) \
                and not re.search(r"budget|campaign|banner|promo|award|partner|sponsor|footer|social|facebook|twitter|linkedin|youtube|instagram", meta):
            out.append(("logo", urljoin(final, src)))
    for m in soup.find_all("meta"):
        if (m.get("property") or m.get("name") or "").lower() in ("og:image", "twitter:image", "msapplication-tileimage") and m.get("content"):
            out.append(("og", urljoin(final, m["content"])))
    seen = set(); res = []
    for k, u in out:
        if u not in seen: seen.add(u); res.append((k, u))
    return res, final

def fetch_deep(url, min_side=32, suffix=""):
    s = session(); host = urlparse(url).netloc.lower(); key = re.sub(r"[^a-z0-9.-]", "_", host) + suffix
    res = {"host": host, "url": url, "ok": False}
    try:
        cands, final = deep_candidates(s, url)
        if not cands and url.startswith("http://"):
            cands, final = deep_candidates(s, "https://" + url[7:])
        scored = []
        for kind, u in cands[:25]:
            r = get(s, u)
            if r is None or not r.ok or len(r.content) < 50: continue
            im, svg = decode(r.content, r.headers.get("content-type", ""))
            if im is None: continue
            w, h = im.size; ar = max(w, h) / max(1, min(w, h))
            if kind == "og" and ar > 1.3: continue
            if kind == "logo" and ar > 4: continue
            if max(w, h) < min_side: continue
            png, side = norm_png(im)
            if not quality(png): continue
            # prefer square icons, then size; header logos next; og last
            rank = (0 if kind == "icon" else 1 if kind == "logo" else 2, 0 if ar <= 1.3 else 1, -min(max(w, h), 256))
            scored.append((rank, u, png, side, max(w, h), svg))
        if scored:
            scored.sort(key=lambda x: x[0]); _, u, png, side, orig, svg = scored[0]
            (CACHE / f"{key}.png").write_bytes(png)
            if svg: (CACHE / f"{key}.svg").write_bytes(svg)
            res.update(ok=True, src=u, orig=orig, side=side, file=f"{key}.png", svg=f"{key}.svg" if svg else "", method="own-site", deep=True)
            return res
        r = get(s, f"https://www.google.com/s2/favicons?domain={host}&sz=128")
        if r is not None and r.ok:
            im, _ = decode(r.content)
            if im is not None and max(im.size) >= min_side:
                png, side = norm_png(im)
                if quality(png):
                    (CACHE / f"{key}.png").write_bytes(png)
                    res.update(ok=True, src=r.url, orig=max(im.size), side=side, file=f"{key}.png", svg="", method="google-s2", s2_sha=hashlib.sha256(r.content).hexdigest(), deep=True)
    except Exception as e:
        res["error"] = repr(e)[:200]
    return res

def host_ok(v):
    if not v.get("ok"): return False
    try: return quality((CACHE / v["file"]).read_bytes())
    except Exception: return False

def main():
    hosts = json.loads((WORK / "hosts.json").read_text())
    todo = [u for u, v in hosts.items() if not host_ok(v) and u.startswith("http") and not v.get("deep_tried")]
    print("deep fetch", len(todo), flush=True)
    with ThreadPoolExecutor(6) as ex:
        for i, res in enumerate(ex.map(fetch_deep, todo)):
            u = todo[i]
            if res.get("ok"): hosts[u] = res
            else: hosts[u]["deep_tried"] = True
            if i % 25 == 0: (WORK / "hosts.json").write_text(json.dumps(hosts, indent=1)); print(i, flush=True)
    (WORK / "hosts.json").write_text(json.dumps(hosts, indent=1))
    print("now ok", sum(1 for v in hosts.values() if host_ok(v)), "of", len(hosts))

if __name__ == "__main__": main()
