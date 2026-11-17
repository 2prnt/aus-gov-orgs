#!/usr/bin/env python3
"""Find genuinely large logos and write icons/png-512 plus extra SVGs.

A source counts as large only if it is a vector (SVG) or a raster whose
longest side is at least 256 px. Tiny favicons are never upscaled and
passed off as large. Eligible sources are fitted into a 512x512 square
with transparent padding.

Sources, in order:
  1. The organisation's own site (apple-touch, web manifest, large .ico
     sizes, SVG favicons or logos).
  2. Wikimedia Commons / Wikidata logo (P154) for that organisation.
  3. Official SVG or large logos for the fallback parent (Commonwealth
     Coat of Arms / Australian Government logo, state government logos,
     Defence, DVA, portfolio departments).

The existing icons/png set is left untouched. New columns on
icons/manifest.csv: large_source_url, large_original_px, large_is_fallback.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import cairosvg
import requests
import urllib3
from bs4 import BeautifulSoup
from PIL import Image, ImageStat

sys.path.insert(0, str(Path(__file__).parent))
from build_icons import (  # noqa: E402
    DEF_RE,
    DEFENCE,
    PORTFOLIO,
    PREFIX,
    host_root,
    norm,
    slugify,
)
from fetch_icons import BAD  # noqa: E402

urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/workspace/icons_work")
LARGE = WORK / "large"
CACHE = LARGE / "cache"
FBDIR = LARGE / "fallbacks"
HOSTS_OUT = LARGE / "hosts.json"
WD_P154 = LARGE / "wikidata_p154.json"
CACHE.mkdir(parents=True, exist_ok=True)
FBDIR.mkdir(parents=True, exist_ok=True)

UA_SITE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
UA_WMF = "aus-gov-orgs-icons/1.0 (https://github.com/2prnt/aus-gov-orgs)"
MIN_RASTER = 256
OUT_SIDE = 512
MIN_BYTES = 1000
WORKERS = int(os.environ.get("WORKERS", "14"))

# Official fallback artwork: prefer an official-site SVG or >=256 px logo
# already used by this project; otherwise a Wikimedia Commons coat-of-arms SVG.
OFFICIAL = {
    "COA": {
        "cite": "https://www.agriculture.gov.au/themes/custom/awe/images/australian-government-logo-512.png",
        "name": "Australian Government logo / Commonwealth Coat of Arms",
        "urls": [
            # Already downloaded during the first icon pass.
            "file:/workspace/icons_work/coa512.png",
            "https://www.agriculture.gov.au/themes/custom/awe/images/australian-government-logo-512.png",
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_arms_of_the_Commonwealth_of_Australia.svg",
        ],
        "svg_urls": [
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_arms_of_the_Commonwealth_of_Australia.svg",
        ],
    },
    "DEFENCE": {
        "cite": "https://www.defence.gov.au/themes/custom/custom/defence8ui/images/gov-crest-horizontal.svg",
        "name": "Australian Government — Defence crest",
        "urls": [
            "file:/workspace/icons_work/cache/_defence_crest_horizontal.svg",
            "https://www.defence.gov.au/themes/custom/custom/defence8ui/images/gov-crest-horizontal.svg",
        ],
        "svg_urls": [
            "file:/workspace/icons_work/cache/_defence_crest_horizontal.svg",
            "https://www.defence.gov.au/themes/custom/custom/defence8ui/images/gov-crest-horizontal.svg",
        ],
    },
    "NSW": {
        "cite": "https://www.nsw.gov.au/themes/custom/dcs_theme/favicons/sets/standard/android-chrome-512x512.png",
        "name": "NSW Government",
        "urls": [
            "https://www.nsw.gov.au/themes/custom/dcs_theme/favicons/sets/standard/android-chrome-512x512.png",
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_New_South_Wales.svg",
        ],
        "svg_urls": [
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_New_South_Wales.svg",
        ],
    },
    "VIC": {
        "cite": "https://www.vic.gov.au/ (footer Victoria State Government logo SVG)",
        "name": "Victoria State Government",
        "urls": [
            "file:/workspace/icons_work/vicgov.svg",
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_Victoria.svg",
        ],
        "svg_urls": [
            "file:/workspace/icons_work/vicgov.svg",
        ],
    },
    "QLD": {
        "cite": "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_Queensland.svg",
        "name": "Queensland Government",
        "urls": [
            # Existing site icon is only 192 px, so use the official CoA SVG.
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_Queensland.svg",
        ],
        "svg_urls": [
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_Queensland.svg",
        ],
    },
    "WA": {
        "cite": "https://www.wa.gov.au/themes/custom/wagov/images/logo.svg",
        "name": "Government of Western Australia",
        "urls": [
            "https://www.wa.gov.au/themes/custom/wagov/images/logo.svg",
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_Western_Australia.svg",
        ],
        "svg_urls": [
            "https://www.wa.gov.au/themes/custom/wagov/images/logo.svg",
        ],
    },
    "SA": {
        "cite": "https://www.sa.gov.au/__data/assets/image/0006/591828/og-gosa-colour-on-white.png",
        "name": "Government of South Australia",
        "urls": [
            "file:/workspace/icons_work/saog.png",
            "https://www.sa.gov.au/__data/assets/image/0006/591828/og-gosa-colour-on-white.png",
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_arms_of_South_Australia.svg",
        ],
        "svg_urls": [
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_arms_of_South_Australia.svg",
        ],
    },
    "TAS": {
        "cite": "https://www.service.tas.gov.au/__data/assets/git_bridge/0021/290190/dist/mysource_files/tasmania-govt-black..svg",
        "name": "Tasmanian Government",
        "urls": [
            "file:/workspace/icons_work/tasgovt.svg",
            "https://www.service.tas.gov.au/__data/assets/git_bridge/0021/290190/dist/mysource_files/tasmania-govt-black..svg",
        ],
        "svg_urls": [
            "file:/workspace/icons_work/tasgovt.svg",
        ],
    },
    "ACT": {
        "cite": "https://www.act.gov.au/__data/assets/image/0019/2541430/ACTGov_inline_black.png",
        "name": "ACT Government",
        "urls": [
            "file:/workspace/icons_work/actlogo.png",
            "https://www.act.gov.au/__data/assets/image/0019/2541430/ACTGov_inline_black.png",
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_the_Australian_Capital_Territory.svg",
        ],
        "svg_urls": [
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_Arms_of_the_Australian_Capital_Territory.svg",
        ],
    },
    "NT": {
        "cite": "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_arms_of_the_Northern_Territory.svg",
        "name": "Northern Territory Government",
        "urls": [
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_arms_of_the_Northern_Territory.svg",
        ],
        "svg_urls": [
            "https://commons.wikimedia.org/wiki/Special:FilePath/Coat_of_arms_of_the_Northern_Territory.svg",
        ],
    },
}

JURIS_KEY = {
    "Commonwealth": "COA",
    "NSW": "NSW",
    "Victoria": "VIC",
    "Queensland": "QLD",
    "WA": "WA",
    "SA": "SA",
    "Tasmania": "TAS",
    "ACT": "ACT",
    "NT": "NT",
}


def site_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA_SITE, "Accept-Language": "en-AU,en;q=0.9"})
    return s


def wmf_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA_WMF, "Accept-Language": "en"})
    return s


def http_get(sess, url, timeout=12, max_bytes=8_000_000):
    last = None
    for i in range(2):
        try:
            r = sess.get(url, timeout=timeout, allow_redirects=True, verify=False, stream=True)
            # Cap body so a random PDF/video can't blow the box.
            data = b""
            for chunk in r.iter_content(65536):
                data += chunk
                if len(data) > max_bytes:
                    break
            r._content = data
            r.close()
            return r
        except Exception as e:
            last = e
            time.sleep(1 + i)
    return last


def looks_svg(data, ctype=""):
    if not data:
        return False
    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except Exception:
            return False
    head = data[:800].lstrip().lower()
    if b"<svg" in head or (b"<?xml" in head and b"<svg" in data[:4000].lower()):
        return True
    return "svg" in (ctype or "").lower() and b"<" in data[:200]


def as_svg_bytes(data):
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def rasterise_svg(data, side=OUT_SIDE):
    """Render an SVG so the long side is 2x the output size, preserving aspect."""
    data = as_svg_bytes(data)
    png = cairosvg.svg2png(bytestring=data, output_width=side * 2)
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    # cairosvg sometimes leaves transparent margins; drop them so we can centre later.
    a = im.getchannel("A")
    bbox = a.getbbox()
    if bbox:
        im = im.crop(bbox)
    if max(im.size) > side * 2:
        f = (side * 2) / max(im.size)
        im = im.resize((max(1, round(im.size[0] * f)), max(1, round(im.size[1] * f))), Image.Resampling.LANCZOS)
    return im


def decode_raster(data, ctype=""):
    """Return (PIL RGBA, orig_max_side) or (None, 0). Never upscales."""
    head = data[:200].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html") or head.startswith(b"{") or head.startswith(b"%pdf"):
        return None, 0
    try:
        im = Image.open(io.BytesIO(data))
        if im.format == "ICO":
            sizes = []
            try:
                sizes = list(im.ico.sizes())
            except Exception:
                sizes = [im.size]
            if sizes:
                best = max(sizes, key=lambda s: s[0] * s[1])
                try:
                    im.seek(0)
                    # Pillow: assign size so the largest layer is loaded.
                    im.size = best
                except Exception:
                    pass
                try:
                    im = im.ico.getimage(best)
                except Exception:
                    im.load()
            else:
                im.load()
        else:
            im.load()
        im = im.convert("RGBA")
        return im, max(im.size)
    except Exception:
        return None, 0


def is_blank(im):
    a = im.getchannel("A")
    hist = a.histogram()
    n = im.size[0] * im.size[1]
    if n == 0 or sum(hist[30:]) / n < 0.03:
        return True
    lo, hi = im.convert("L").getextrema()
    if hi - lo < 8 and a.getextrema()[0] > 200:
        return True
    mask = a.point(lambda v: 255 if v > 128 else 0)
    if mask.getbbox() and ImageStat.Stat(im.convert("L"), mask).mean[0] > 235:
        return True
    return False



def _is_white_css_color(c):
    c = (c or "").strip().lower()
    if c in ("white", "#fff", "#ffff", "#ffffff", "#ffffffff", "rgb(255,255,255)", "rgb(255, 255, 255)"):
        return True
    return bool(re.fullmatch(r"#f{3}([f]{3,5})?", c))


def darken_white_svg(svg_bytes):
    """If an SVG is a white-only mark (header logos), recolour it dark so it reads on a light background."""
    try:
        text = svg_bytes.decode("utf-8")
    except Exception:
        return svg_bytes
    colors = set(re.findall(r"(?:fill|stroke)\s*[:=]\s*[\'\"]?([^;\'\")\s]+)", text, re.I))
    meaningful = {c for c in colors if c.lower() not in ("none", "transparent", "inherit", "currentcolor") and not c.lower().startswith("url")}
    if not meaningful or not all(_is_white_css_color(c) for c in meaningful):
        return svg_bytes
    text = re.sub(r"#fff(f{0,5})\b", "#111111", text, flags=re.I)
    text = re.sub(r"\bwhite\b", "#111111", text, flags=re.I)
    text = re.sub(r"rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)", "#111111", text, flags=re.I)
    return text.encode("utf-8")


def recolor_light_mono(im):
    """Paint near-white monochrome artwork black, keeping anti-aliased alpha.

    Only runs on images that use transparency. A fully opaque wordmark on a
    white canvas must not be flattened to a black square.
    """
    im = im.convert("RGBA")
    a = im.getchannel("A")
    if a.getextrema()[0] > 200:
        return im
    mask = a.point(lambda v: 255 if v > 16 else 0)
    if not mask.getbbox():
        return im
    mean = ImageStat.Stat(im.convert("RGB"), mask).mean
    mx, mn = max(mean), min(mean)
    if sum(mean) / 3 > 200 and (mx - mn) < 30:
        black = Image.new("L", im.size, 17)
        r, g, b, al = im.split()
        return Image.merge("RGBA", (black, black, black, al))
    return im


def quality_ok(im, from_svg=False):
    if im is None:
        return False
    w, h = im.size
    if min(w, h) < 1:
        return False
    if not from_svg and max(w, h) < MIN_RASTER:
        return False
    if is_blank(im):
        return False
    buf = io.BytesIO()
    # Hash a normalised copy so placeholder detection still works.
    tmp = im.copy()
    if max(tmp.size) > 128:
        f = 128 / max(tmp.size)
        tmp = tmp.resize((max(1, round(tmp.size[0] * f)), max(1, round(tmp.size[1] * f))), Image.Resampling.LANCZOS)
    side = max(tmp.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(tmp, ((side - tmp.size[0]) // 2, (side - tmp.size[1]) // 2), tmp)
    canvas.save(buf, "PNG")
    if hashlib.sha256(buf.getvalue()).hexdigest() in BAD:
        return False
    return True


def trim_whitespace(im, bg_thresh=245):
    """Trim nearly-white / transparent margins so a logo in an OG image fills the square."""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    def empty(x, y):
        r, g, b, a = px[x, y]
        return a < 8 or (r >= bg_thresh and g >= bg_thresh and b >= bg_thresh)
    top = 0
    while top < h and all(empty(x, top) for x in range(w)):
        top += 1
    bot = h - 1
    while bot > top and all(empty(x, bot) for x in range(w)):
        bot -= 1
    left = 0
    while left < w and all(empty(left, y) for y in range(top, bot + 1)):
        left += 1
    right = w - 1
    while right > left and all(empty(right, y) for y in range(top, bot + 1)):
        right -= 1
    if right - left < 32 or bot - top < 16:
        return im
    return im.crop((left, top, right + 1, bot + 1))


def to_square_512(im):
    im = im.convert("RGBA")
    w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)
    if side != OUT_SIDE:
        canvas = canvas.resize((OUT_SIDE, OUT_SIDE), Image.Resampling.LANCZOS)
    return canvas


def png_bytes(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def host_key(url):
    host = urlparse(url).netloc.lower() or re.sub(r"[^a-z0-9.-]", "_", url)[:80]
    return re.sub(r"[^a-z0-9.-]", "_", host)


def load_file_or_url(sess, url):
    if url.startswith("file:"):
        p = Path(url[5:])
        return p.read_bytes(), "image/svg+xml" if p.suffix.lower() == ".svg" else "", url
    r = http_get(sess if "wikimedia" in url or "wikidata" in url else sess, url)
    if r is None or isinstance(r, Exception) or not getattr(r, "ok", False):
        return None, "", url
    return r.content, r.headers.get("content-type", ""), r.url


def decode_source(data, ctype, url, trim=False):
    """Return dict with im, svg, orig, from_svg or None."""
    if not data or len(data) < 40:
        return None
    path = (url or "").lower().split("?")[0]
    if looks_svg(data, ctype) or path.endswith(".svg") or path.endswith(".svgz"):
        try:
            svg = darken_white_svg(as_svg_bytes(data))
            im = rasterise_svg(svg, side=OUT_SIDE)
            im = recolor_light_mono(im)
            if trim:
                im = trim_whitespace(im)
            if not quality_ok(im, from_svg=True):
                return None
            return {"im": im, "svg": svg, "orig": OUT_SIDE, "from_svg": True}
        except Exception:
            return None
    im, orig = decode_raster(data, ctype)
    if im is None:
        return None
    im = recolor_light_mono(im)
    if trim:
        im = trim_whitespace(im)
        orig = max(im.size)
    if orig < MIN_RASTER or not quality_ok(im, from_svg=False):
        return None
    ar = max(im.size) / max(1, min(im.size))
    if ar > 6:
        return None
    return {"im": im, "svg": None, "orig": orig, "from_svg": False}


# ---------------------------------------------------------------------------
# Site crawl
# ---------------------------------------------------------------------------
def parse_candidates(sess, page_url):
    r = http_get(sess, page_url, timeout=20, max_bytes=2_000_000)
    cands = []
    final = page_url
    if r is None or isinstance(r, Exception) or not getattr(r, "ok", False):
        return cands, final
    final = r.url
    ctype = r.headers.get("content-type", "html")
    if "html" not in ctype and "xml" not in ctype:
        return cands, final
    soup = BeautifulSoup(r.content[:600000], "html.parser")
    base = soup.find("base", href=True)
    bhref = urljoin(final, base["href"]) if base else final

    def add(kind, href, sz=0, typ=""):
        if not href or href.startswith("data:"):
            return
        u = urljoin(bhref, href.strip())
        path = u.lower().split("?")[0]
        if "svg" in (typ or "") or path.endswith(".svg") or path.endswith(".svgz"):
            sz = max(sz, 512)
        cands.append((kind, sz, u))

    for l in soup.find_all("link", href=True):
        rel = " ".join(l.get("rel") or []).lower()
        typ = (l.get("type") or "").lower()
        if "icon" in rel and "mask-icon" not in rel:
            m = re.findall(r"(\d+)x(\d+)", l.get("sizes") or "")
            sz = max([int(a) for a, b in m], default=0)
            if "apple-touch" in rel and not sz:
                sz = 180
            add("icon", l["href"], sz, typ)
        if "manifest" in rel:
            mr = http_get(sess, urljoin(bhref, l["href"]), timeout=15, max_bytes=500_000)
            try:
                if mr is not None and getattr(mr, "ok", False):
                    for ic in (mr.json().get("icons") or [])[:15]:
                        m = re.findall(r"(\d+)x(\d+)", ic.get("sizes") or "")
                        add("icon", urljoin(mr.url, ic.get("src") or ""), max([int(a) for a, b in m], default=0), ic.get("type") or "")
            except Exception:
                pass

    p = urlparse(final)
    root = f"{p.scheme}://{p.netloc}"
    for path, sz in (
        ("/apple-touch-icon.png", 180),
        ("/apple-touch-icon-precomposed.png", 180),
        ("/android-chrome-512x512.png", 512),
        ("/android-icon-512x512.png", 512),
        ("/favicon-512x512.png", 512),
        ("/icon-512x512.png", 512),
        ("/mstile-310x310.png", 310),
        ("/favicon.ico", 1),
    ):
        add("icon", root + path, sz)

    for img in soup.find_all("img")[:100]:
        src = img.get("src") or img.get("data-src") or ""
        typ = (img.get("type") or "")
        meta = " ".join(
            [
                src,
                img.get("alt", ""),
                " ".join(img.get("class") or []),
                img.get("id") or "",
            ]
            + [
                " ".join(par.get("class") or []) + " " + (par.get("id") or "")
                for par in img.parents
                if par.name in ("a", "div", "header", "span", "picture")
            ][:4]
        ).lower()
        a = img.find_parent("a")
        home = False
        if a is not None:
            href = urljoin(final, a.get("href") or "x")
            pu, pf = urlparse(href), urlparse(final)
            home = pu.path.rstrip("/") in ("", "/index.html", "/home") and pu.netloc.lower().replace("www.", "") == pf.netloc.lower().replace("www.", "")
        in_header = img.find_parent("header") is not None
        if src and not src.startswith("data:") and re.search(r"logo|crest|brand|coat|wordmark", meta) and (home or in_header) \
                and not re.search(r"budget|campaign|banner|promo|award|partner|sponsor|footer|social|facebook|twitter|linkedin|youtube|instagram", meta):
            add("logo", src, 0, typ)

    # Linked / inline SVGs in the header that look like the brand mark.
    for el in soup.select("header svg, a[href='/'] svg, a[href='./'] svg, .logo svg, .brand svg, [class*='logo'] svg, [class*='brand'] svg"):
        try:
            raw = str(el).encode()
            if b"<svg" in raw and len(raw) > 80:
                cands.append(("logo-inline-svg", 512, "inline-svg:" + hashlib.sha1(raw).hexdigest()[:16]))
                # stash bytes on the tuple via a side channel after
        except Exception:
            pass

    for m in soup.find_all("meta"):
        name = (m.get("property") or m.get("name") or "").lower()
        if name in ("og:image", "og:image:url", "twitter:image", "msapplication-tileimage") and m.get("content"):
            add("og", m["content"], 0)

    # Dedup, keep highest declared size.
    best = {}
    for kind, sz, u in cands:
        if u not in best or sz > best[u][1]:
            best[u] = (kind, sz, u)
    # Sort: declared size desc, icons first
    kind_rank = {"icon": 0, "logo": 1, "logo-inline-svg": 1, "og": 2}
    out = sorted(best.values(), key=lambda t: (kind_rank.get(t[0], 9), -t[1]))
    return out, final


def fetch_host_large(page_url, known_src=None):
    """Return a result dict stored in hosts.json (ok, src, orig, from_svg, file, svg, method)."""
    key = host_key(page_url)
    sess = site_session()
    scored = []
    svg_stash = {}

    def consider(kind, u, data, ctype, final_url):
        trim = kind in ("og", "logo")
        got = decode_source(data, ctype, final_url or u, trim=trim)
        if not got:
            return
        im, orig, svg, from_svg = got["im"], got["orig"], got["svg"], got["from_svg"]
        w, h = im.size
        ar = max(w, h) / max(1, min(w, h))
        if kind == "og" and not from_svg:
            # Social-card photos / default thumbnails are not logos.
            if ar > 1.45:
                return
        if kind == "logo" and ar > 5:
            return
        # Prefer vector, then bigger original, then squarer, then icon over og.
        rank = (
            0 if from_svg else 1,
            0 if kind == "icon" else 1 if kind == "logo" else 2,
            -min(orig if not from_svg else 10_000, 2048),
            0 if ar <= 1.25 else 1 if ar <= 2 else 2,
        )
        scored.append((rank, u, im, orig, svg, from_svg, kind))

    if known_src:
        r = http_get(sess, known_src)
        if r is not None and getattr(r, "ok", False) and not isinstance(r, Exception):
            consider("icon", known_src, r.content, r.headers.get("content-type", ""), r.url)

    try:
        cands, final = parse_candidates(sess, page_url)
    except Exception:
        cands, final = [], page_url

    # If http failed, try https.
    if not cands and page_url.startswith("http://"):
        try:
            parsed = parse_candidates(sess, "https://" + page_url[7:])
            cands, final = parsed[0], parsed[1]
        except Exception:
            pass

    for kind, sz, u in cands[:16]:
        if u.startswith("inline-svg:"):
            continue
        # Skip obvious tiny declarations when we already have a vector or 512.
        r = http_get(sess, u)
        if r is None or isinstance(r, Exception) or not getattr(r, "ok", False) or len(getattr(r, "content", b"")) < 50:
            continue
        consider(kind, u, r.content, r.headers.get("content-type", ""), r.url)
        if any(item[5] or item[3] >= 512 for item in scored):
            break

    if not scored:
        return {"ok": False, "url": page_url, "host": urlparse(page_url).netloc.lower()}

    scored.sort(key=lambda x: x[0])
    _, u, im, orig, svg, from_svg, kind = scored[0]
    out_im = to_square_512(im)
    png = png_bytes(out_im)
    # Only accept if the 512 file is a real image
    if len(png) < MIN_BYTES:
        return {"ok": False, "url": page_url, "host": urlparse(page_url).netloc.lower(), "reason": "tiny-output"}
    (CACHE / f"{key}.png").write_bytes(png)
    svg_name = ""
    if svg:
        (CACHE / f"{key}.svg").write_bytes(svg)
        svg_name = f"{key}.svg"
    return {
        "ok": True,
        "url": page_url,
        "host": urlparse(page_url).netloc.lower(),
        "src": u,
        "orig": orig,
        "from_svg": from_svg,
        "file": f"{key}.png",
        "svg": svg_name,
        "method": "own-site",
        "kind": kind,
    }


# ---------------------------------------------------------------------------
# Official fallbacks
# ---------------------------------------------------------------------------
def prepare_official():
    """Download / rasterise official parent logos into FBDIR and return map."""
    out = {}
    site, wmf = site_session(), wmf_session()
    for key, meta in OFFICIAL.items():
        picked = None
        svg_bytes, svg_src = None, ""
        # Prefer an official-site source that decodes as large or vector; the
        # list is already in preference order. For SA's OG image, trim margins.
        for url in meta["urls"]:
            sess = wmf if "wikimedia" in url or "wikidata" in url else site
            try:
                data, ctype, final = load_file_or_url(sess, url)
            except Exception:
                continue
            if not data:
                continue
            trim = key == "SA" or "og-" in url
            got = decode_source(data, ctype, final or url, trim=trim)
            if not got:
                continue
            picked = (url if not url.startswith("file:") else final or url, got, final or url)
            if got["from_svg"]:
                svg_bytes, svg_src = got["svg"], (url if not url.startswith("file:") else meta.get("urls", [url])[-1])
            break
        # Only keep an SVG when it is the artwork we actually used for the PNG.
        # Do not attach a coat-of-arms SVG to a different government wordmark.
        if picked is None:
            for url in meta.get("svg_urls") or []:
                sess = wmf if "wikimedia" in url or "wikidata" in url else site
                try:
                    data, ctype, final = load_file_or_url(sess, url)
                except Exception:
                    continue
                if data and looks_svg(data, ctype):
                    try:
                        svg_bytes = as_svg_bytes(data)
                        svg_src = url if not url.startswith("file:") else final
                        im = rasterise_svg(svg_bytes, side=OUT_SIDE)
                        if quality_ok(im, from_svg=True):
                            picked = (svg_src, {"im": im, "svg": svg_bytes, "orig": OUT_SIDE, "from_svg": True}, svg_src)
                            break
                    except Exception:
                        svg_bytes, svg_src = None, ""
        # If the listed URLs missed or were only last-resort Commons arms,
        # try the government's own homepage for a large brand logo first.
        HOMEPAGE = {
            "NSW": "https://www.nsw.gov.au/",
            "VIC": "https://www.vic.gov.au/",
            "QLD": "https://www.qld.gov.au/",
            "WA": "https://www.wa.gov.au/",
            "SA": "https://www.sa.gov.au/",
            "TAS": "https://www.tas.gov.au/",
            "ACT": "https://www.act.gov.au/",
            "NT": "https://nt.gov.au/",
            "DEFENCE": "https://www.defence.gov.au/",
            "COA": "https://www.agriculture.gov.au/",
        }
        homepage = HOMEPAGE.get(key)
        prefer_site = key in ("QLD", "WA", "NT") or picked is None
        if homepage and prefer_site:
            try:
                site_rec = fetch_host_large(homepage)
            except Exception as e:
                site_rec = {"ok": False, "error": repr(e)}
            if site_rec.get("ok") and (site_rec.get("from_svg") or site_rec.get("kind") in ("icon", "logo")):
                from_commons = bool(picked and "wikimedia.org" in (picked[0] or ""))
                if picked is None or from_commons:
                    sp = resolve_png(site_rec)
                    if sp:
                        im = Image.open(sp).convert("RGBA")
                        svg_data = None
                        if site_rec.get("from_svg") and site_rec.get("svg"):
                            sp_svg = CACHE / site_rec["svg"]
                            if sp_svg.exists():
                                svg_data = sp_svg.read_bytes()
                        picked = (site_rec["src"], {"im": im, "svg": svg_data, "orig": site_rec.get("orig") or OUT_SIDE, "from_svg": bool(site_rec.get("from_svg"))}, site_rec["src"])
                        if svg_data:
                            svg_bytes, svg_src = svg_data, site_rec["src"]
                        print("official homepage used for", key, site_rec.get("src", "")[:100], "orig", site_rec.get("orig"), flush=True)
        if not picked:
            print("WARN no official logo for", key, flush=True)
            continue
        src, got, final = picked
        im512 = to_square_512(got["im"])
        (FBDIR / f"{key}.png").write_bytes(png_bytes(im512))
        if svg_bytes:
            (FBDIR / f"{key}.svg").write_bytes(svg_bytes)
        # Record a public URL, not a file: path. Never attribute a local extract
        # to a different Wikimedia file.
        public = src
        if public.startswith("file:"):
            public = meta.get("cite") or next(
                (u for u in meta["urls"] + meta.get("svg_urls", []) if u.startswith("http") and "wikimedia.org" not in u),
                meta.get("cite") or public,
            )
        out[key] = {
            "ok": True,
            "src": public,
            "orig": got["orig"],
            "from_svg": bool(got["from_svg"] or svg_bytes),
            "file": str(FBDIR / f"{key}.png"),
            "svg": str(FBDIR / f"{key}.svg") if svg_bytes else "",
            "svg_src": svg_src if svg_bytes else "",
            "name": meta["name"],
            "method": "fallback-official",
        }
        print("official", key, "orig", got["orig"], "svg" if out[key]["svg"] else "raster", public[:90], flush=True)
    return out


# ---------------------------------------------------------------------------
# Wikidata P154
# ---------------------------------------------------------------------------
def load_p154():
    if not WD_P154.exists() or WD_P154.stat().st_size < 1000:
        sess = wmf_session()
        q = """SELECT ?item ?itemLabel ?logo ?website WHERE {
          ?item wdt:P17 wd:Q408.
          ?item wdt:P154 ?logo.
          OPTIONAL { ?item wdt:P856 ?website }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }"""
        r = sess.get(
            "https://query.wikidata.org/sparql",
            params={"query": q},
            headers={"Accept": "application/sparql-results+json"},
            timeout=120,
        )
        r.raise_for_status()
        WD_P154.write_bytes(r.content)
    data = json.loads(WD_P154.read_text())
    by_title = defaultdict(list)
    by_host = defaultdict(list)
    for row in data["results"]["bindings"]:
        rec = {
            "qid": row["item"]["value"].rsplit("/", 1)[-1],
            "label": row.get("itemLabel", {}).get("value", ""),
            "logo": row["logo"]["value"],
            "website": row.get("website", {}).get("value", ""),
        }
        if rec["label"]:
            by_title[norm(rec["label"])].append(rec)
        if rec["website"]:
            h = urlparse(rec["website"]).netloc.lower().removeprefix("www.")
            if h:
                by_host[h].append(rec)
    return by_title, by_host


def _p154_looks_like_logo(url):
    """Drop Wikidata P154 files that are photographs or other non-logos."""
    from urllib.parse import unquote
    name = unquote((url or "").split("?")[0].rsplit("/", 1)[-1]).lower()
    if any(w in name for w in ("building", "station", "photograph", "photo", "museum", "cast iron", "power-station", "power_station")):
        return False
    if name.endswith(".svg"):
        return True
    return bool(re.search(r"logo|coat|crest|arms|badge|seal|wordmark|brand", name))


def pick_p154(recs):
    """Prefer an SVG logo if several claims exist. Skip photographs."""
    recs = [r for r in recs if r.get("logo") and _p154_looks_like_logo(r["logo"])]
    svgs = [r for r in recs if r["logo"].lower().split("?")[0].endswith(".svg")]
    return (svgs or recs)[0] if recs else None


def fetch_commons(url):
    """Download a Wikidata/Commons logo and cache it under large/cache."""
    if url.startswith("http://"):
        url = "https://" + url[7:]
    key = "wd_" + hashlib.sha1(url.encode()).hexdigest()[:16]
    png_path = CACHE / f"{key}.png"
    meta_path = CACHE / f"{key}.json"
    if meta_path.exists() and png_path.exists():
        return json.loads(meta_path.read_text())
    sess = wmf_session()
    # FilePath URLs sometimes need a follow-through; also try Special:Redirect.
    r = http_get(sess, url, timeout=40, max_bytes=12_000_000)
    if r is None or isinstance(r, Exception) or not getattr(r, "ok", False):
        return {"ok": False, "src": url, "reason": "download"}
    got = decode_source(r.content, r.headers.get("content-type", ""), r.url, trim=True)
    if not got:
        return {"ok": False, "src": url, "reason": "not-large"}
    im512 = to_square_512(got["im"])
    png = png_bytes(im512)
    if len(png) < MIN_BYTES:
        return {"ok": False, "src": url, "reason": "tiny-output"}
    png_path.write_bytes(png)
    svg_name = ""
    if got["svg"]:
        (CACHE / f"{key}.svg").write_bytes(got["svg"])
        svg_name = f"{key}.svg"
    rec = {
        "ok": True,
        "src": url,
        "orig": got["orig"],
        "from_svg": got["from_svg"],
        "file": f"{key}.png",
        "svg": svg_name,
        "method": "wikidata-p154",
    }
    meta_path.write_text(json.dumps(rec))
    return rec


# ---------------------------------------------------------------------------
# Assignment helpers
# ---------------------------------------------------------------------------
def good_host(hosts, url):
    if not url:
        return None
    h = hosts.get(url)
    if h and h.get("ok"):
        return h
    if url.startswith("http://"):
        h = hosts.get("https://" + url[7:])
        if h and h.get("ok"):
            return h
    elif url.startswith("https://"):
        h = hosts.get("http://" + url[8:])
        if h and h.get("ok"):
            return h
    return None


def resolve_png(rec):
    if not rec:
        return None
    f = rec.get("file") or ""
    for p in (Path(f), CACHE / f, FBDIR / f):
        if f and p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    manifest = list(csv.DictReader(open(ROOT / "icons/manifest.csv", encoding="utf-8")))
    assert len(rows) == len(manifest), (len(rows), len(manifest))
    old_hosts = json.loads((WORK / "hosts.json").read_text()) if (WORK / "hosts.json").exists() else {}
    wd_sites = json.loads((WORK / "wikidata_sites.json").read_text()) if (WORK / "wikidata_sites.json").exists() else {}

    from describe import host_ok, wd_conflict

    def wdget(r):
        w = wd_sites.get(r["Id"] + "|" + r["Title"])
        if not w:
            return None
        if not host_ok(w.get("website", ""), r["Jurisdiction"]):
            return None
        if wd_conflict(w.get("description", ""), r["Jurisdiction"]):
            return None
        return w

    official = prepare_official()
    by_title, by_host = load_p154()
    print("wikidata p154 titles", len(by_title), "hosts", len(by_host), flush=True)

    # Map each org to a site we should crawl for an *own* large logo.
    org_site = []
    crawl_urls = {}  # url -> known large src (if any)
    for i, (r, m) in enumerate(zip(rows, manifest)):
        site = (r.get("Website Address") or "").strip()
        how = "own-site"
        if not site:
            w = wdget(r)
            if w:
                site, how = w["website"], "own-site-wikidata"
        org_site.append((site, how))
        h = host_root(site) if site else None
        if not h:
            continue
        # Hint: previously recorded source, if it looked large or was SVG.
        prev = m.get("icon source URL") or ""
        prev_orig = 0
        try:
            prev_orig = int(m.get("original size") or 0)
        except Exception:
            prev_orig = 0
        is_svg = prev.lower().split("?")[0].endswith(".svg") or prev.lower().split("?")[0].endswith(".svgz") or bool(m.get("svg file"))
        if h not in crawl_urls:
            crawl_urls[h] = prev if (is_svg or prev_orig >= MIN_RASTER) and not prev.startswith("https://www.google.com/s2/") else None
        elif crawl_urls[h] is None and (is_svg or prev_orig >= MIN_RASTER) and not prev.startswith("https://www.google.com/s2/"):
            crawl_urls[h] = prev

    # Previously discovered large parent logos (BIG:) are strong hints.
    for k, v in old_hosts.items():
        src = (v or {}).get("src") or ""
        if not v or not v.get("ok") or not src or src.startswith("https://www.google.com/s2/"):
            continue
        orig = v.get("orig") or 0
        try:
            orig = int(orig)
        except Exception:
            orig = 0
        if not (v.get("svg") or orig >= MIN_RASTER or v.get("from_svg")):
            continue
        u = k[4:] if k.startswith("BIG:") else k
        if u.startswith("http") and (u not in crawl_urls or crawl_urls.get(u) is None):
            crawl_urls[u if u.endswith("/") or "BIG:" in k else u] = src
            # Normalise to host root when possible
            root = host_root(u)
            if root:
                if root not in crawl_urls or crawl_urls.get(root) is None:
                    crawl_urls[root] = src

    # Also crawl parent / portfolio department sites so fallbacks can be large
    # *own* logos of the parent, not just the jurisdiction mark.
    parent_urls = set()
    for lst in PORTFOLIO.values():
        for _, u in lst:
            parent_urls.add(u)
    parent_urls.add("https://www.dva.gov.au/")
    parent_urls.add(DEFENCE)
    parents_needed = {(r["Jurisdiction"], norm(r["Parent Organisation"])) for r in rows if r.get("Parent Organisation")}
    for r in rows:
        if (r["Jurisdiction"], norm(r["Title"])) in parents_needed:
            site = (r.get("Website Address") or "").strip() or ((wdget(r) or {}).get("website") or "")
            if host_root(site):
                parent_urls.add(host_root(site))
    for u in parent_urls:
        crawl_urls.setdefault(u, None)

    hosts = json.loads(HOSTS_OUT.read_text()) if HOSTS_OUT.exists() else {}
    # Re-fetch earlier failures when requested; otherwise skip ok hosts.
    todo = []
    for u, hint in sorted(crawl_urls.items()):
        rec = hosts.get(u)
        if rec and rec.get("ok") and resolve_png(rec):
            continue
        todo.append((u, hint))
    if os.environ.get("ASSIGN_ONLY"):
        todo = []
        print("ASSIGN_ONLY: skip crawl", flush=True)
    print("hosts to crawl", len(todo), "already ok", sum(1 for u in crawl_urls if hosts.get(u, {}).get("ok")), flush=True)

    def work(item):
        u, hint = item
        try:
            return u, fetch_host_large(u, known_src=hint)
        except Exception as e:
            return u, {"ok": False, "url": u, "error": repr(e)[:200]}

    if todo:
        done = 0
        with ThreadPoolExecutor(WORKERS) as ex:
            futs = [ex.submit(work, it) for it in todo]
            for fut in as_completed(futs):
                u, rec = fut.result()
                hosts[u] = rec
                done += 1
                if done % 25 == 0 or done == len(todo):
                    HOSTS_OUT.write_text(json.dumps(hosts, indent=1))
                    ok = sum(1 for v in hosts.values() if v.get("ok"))
                    print(f"crawl {done}/{len(todo)} ok={ok}", flush=True)
        HOSTS_OUT.write_text(json.dumps(hosts, indent=1))
    print("crawl done ok", sum(1 for v in hosts.values() if v.get("ok")), "of", len(hosts), flush=True)

    # Pull Wikidata P154 logos for orgs that still lack an own large icon.
    def own_large(i):
        site, _ = org_site[i]
        return good_host(hosts, host_root(site) if site else None)

    p154_jobs = {}  # logo url -> list of org indexes that want it
    for i, (r, m) in enumerate(zip(rows, manifest)):
        if own_large(i):
            continue
        recs = list(by_title.get(norm(r["Title"])) or [])
        picked = pick_p154(recs)
        if picked:
            p154_jobs.setdefault(picked["logo"], []).append(i)

    print("wikidata logos to fetch", len(p154_jobs), flush=True)
    p154_cache = {}
    logos = list(p154_jobs)
    if logos:
        with ThreadPoolExecutor(6) as ex:
            for url, rec in zip(logos, ex.map(fetch_commons, logos)):
                p154_cache[url] = rec
                if rec.get("ok"):
                    pass
        print("wikidata logos ok", sum(1 for v in p154_cache.values() if v.get("ok")), flush=True)

    # Index parent own-large icons by (jurisdiction, normalised title).
    own_by_title = {}
    for i, r in enumerate(rows):
        h = own_large(i)
        if h:
            own_by_title[(r["Jurisdiction"], norm(r["Title"]))] = (host_root(org_site[i][0]), h)
    parent_of = {(r["Jurisdiction"], norm(r["Title"])): r.get("Parent Organisation") or "" for r in rows if r.get("Parent Organisation")}

    def p154_for(i):
        recs = list(by_title.get(norm(rows[i]["Title"])) or [])
        picked = pick_p154(recs)
        if not picked:
            return None
        rec = p154_cache.get(picked["logo"]) or p154_cache.get(picked["logo"].replace("http://", "https://"))
        return rec if rec and rec.get("ok") else None

    def fallback_parent(i):
        r = rows[i]
        j, port, parent = r["Jurisdiction"], r.get("Portfolio") or "", r.get("Parent Organisation") or ""
        # Defence portfolio bodies.
        if j == "Commonwealth" and "Veterans" not in port and (DEF_RE.search(port) or DEF_RE.search(parent) or DEF_RE.search(r["Title"])):
            rec = official.get("DEFENCE")
            if rec:
                return rec, "defence-fallback", "Department of Defence"
        # Walk parent chain; use a parent's *own* large logo if we have one.
        p = parent
        seen = set()
        while p and (j, norm(p)) not in seen:
            seen.add((j, norm(p)))
            hit = own_by_title.get((j, norm(p)))
            if hit:
                return hit[1], "parent", "parent: " + p
            p = parent_of.get((j, norm(p)), "")
        # Portfolio department site.
        for key, url in PORTFOLIO.get(j, []):
            if key.lower() in port.lower():
                h = good_host(hosts, url)
                if h:
                    return h, "parent", "portfolio: " + port
        # Veterans' Affairs.
        if j == "Commonwealth" and "Veterans" in port:
            h = good_host(hosts, "https://www.dva.gov.au/")
            if h:
                return h, "parent", "portfolio: " + port
        rec = official.get(JURIS_KEY[j])
        assert rec, j
        return rec, "fallback-jurisdiction", rec["name"]

    # Write outputs. Never touch icons/png.
    png_dir = ROOT / "icons" / "png-512"
    svg_dir = ROOT / "icons" / "svg"
    if png_dir.exists():
        shutil.rmtree(png_dir)
    png_dir.mkdir(parents=True)
    # Shared official SVGs (not copied per organisation — CoA files are huge).
    shared_svg_dir = ROOT / "icons" / "svg-fallback"
    if shared_svg_dir.exists():
        shutil.rmtree(shared_svg_dir)
    shared_svg_dir.mkdir()
    shared_copied = {}

    counts = Counter()
    origs = []
    new_manifest = []
    new_own_svg = 0
    for i, (r, m) in enumerate(zip(rows, manifest)):
        slug = m["slug"]
        own = own_large(i)
        p154 = None if own else p154_for(i)
        is_fb = False
        method_large = ""
        note_extra = ""
        if own:
            rec = own
            method_large = "own-site"
            is_fb = False
        elif p154:
            rec = p154
            method_large = "wikidata-p154"
            is_fb = False
        else:
            rec, method_large, note_extra = fallback_parent(i)
            is_fb = True
        src_png = resolve_png(rec)
        if src_png is None:
            # Last resort: official jurisdiction logo.
            rec, method_large, note_extra = official[JURIS_KEY[r["Jurisdiction"]]], "fallback-jurisdiction", "last-resort"
            is_fb = True
            src_png = resolve_png(rec)
        data = src_png.read_bytes()
        # All cache/fallback files are already 512; copy as-is.
        (png_dir / f"{slug}.png").write_bytes(data)

        svg_rel = m.get("svg file") or ""
        # Own / P154 vectors get a per-slug SVG (skip huge files already stored shared).
        rec_svg = rec.get("svg") or ""
        rec_from_svg = rec.get("from_svg")
        if not is_fb and rec_svg:
            sp = Path(rec_svg) if "/" in rec_svg else (CACHE / rec_svg)
            if sp.exists() and sp.stat().st_size <= 400_000:
                dest = svg_dir / f"{slug}.svg"
                shutil.copyfile(sp, dest)
                svg_rel = f"icons/svg/{slug}.svg"
                new_own_svg += 1
        elif is_fb and rec.get("svg"):
            # Shared official / parent SVG.
            sp = Path(rec["svg"]) if "/" in str(rec["svg"]) else (CACHE / rec["svg"] if (CACHE / rec["svg"]).exists() else FBDIR / rec["svg"])
            if not sp.exists() and rec_svg:
                for cand in (CACHE / rec_svg, FBDIR / rec_svg, Path(rec_svg)):
                    if cand.exists():
                        sp = cand
                        break
            if sp.exists():
                # Name shared file by official key or hash.
                shared_name = None
                for k, v in official.items():
                    if v is rec or v.get("src") == rec.get("src"):
                        shared_name = f"_{k.lower()}.svg"
                        break
                if not shared_name:
                    shared_name = "_parent_" + hashlib.sha1((rec.get("src") or "").encode()).hexdigest()[:12] + ".svg"
                dest = shared_svg_dir / shared_name
                if shared_name not in shared_copied:
                    shutil.copyfile(sp, dest)
                    shared_copied[shared_name] = dest
                svg_rel = f"icons/svg-fallback/{shared_name}"

        # Defence already has per-slug SVGs in icons/svg from the small set;
        # keep pointing at them when we still use the Defence crest.
        if is_fb and method_large == "defence-fallback" and (m.get("svg file") or "").startswith("icons/svg/"):
            svg_rel = m["svg file"]

        orig_px = rec.get("orig") or ""
        row = dict(m)
        row["svg file"] = svg_rel
        row["large_source_url"] = rec.get("src") or rec.get("svg_src") or ""
        row["large_original_px"] = orig_px
        row["large_is_fallback"] = "true" if is_fb else "false"
        if note_extra and not row.get("notes"):
            row["notes"] = note_extra
        new_manifest.append(row)
        counts["fallback" if is_fb else "own"] += 1
        counts[method_large] += 1
        if rec_from_svg or (svg_rel and Path(ROOT / svg_rel).exists() if svg_rel else False):
            counts["has_svg"] += 1
        try:
            origs.append(int(orig_px))
        except Exception:
            pass

    # Write manifest with the new columns after the existing ones.
    cols = list(manifest[0].keys())
    for c in ("large_source_url", "large_original_px", "large_is_fallback"):
        if c not in cols:
            cols.append(c)
    with open(ROOT / "icons/manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(new_manifest)

    # Zip of the large set only (do not replace the small zip).
    zpath = ROOT / "icons" / "aus-gov-orgs-icons-png-512.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for m in new_manifest:
            slug = m["slug"]
            z.write(png_dir / f"{slug}.png", f"png-512/{slug}.png")
        z.write(ROOT / "icons/manifest.csv", "manifest.csv")
        if shared_svg_dir.exists():
            for p in sorted(shared_svg_dir.glob("*.svg")):
                z.write(p, f"svg-fallback/{p.name}")

    # Sanity: every file is 512x512.
    bad_sz = 0
    for p in png_dir.glob("*.png"):
        im = Image.open(p)
        if im.size != (512, 512):
            bad_sz += 1
    print("wrote", len(new_manifest), "png-512; bad sizes", bad_sz)
    print("own vs fallback", counts["own"], counts["fallback"])
    print("methods", {k: v for k, v in counts.items() if k not in ("own", "fallback", "has_svg")})
    print("has svg (own or shared)", counts["has_svg"], "new per-slug own svgs written this pass (not unique total)")
    print("svg-fallback files", len(list(shared_svg_dir.glob('*.svg'))))
    print("svg per-slug now", len(list(svg_dir.glob('*.svg'))))
    if origs:
        origs.sort()
        print("orig px: min", origs[0], "median", origs[len(origs)//2], "p90", origs[int(len(origs)*0.9)], "max", origs[-1])
        print("orig distribution", Counter(origs).most_common(15))
    print("zip", zpath, "bytes", zpath.stat().st_size)


if __name__ == "__main__":
    main()
