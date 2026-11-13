"""Stage 2: assign an icon to every organisation and write icons/ + CSV columns.

Order: own website icon (listed Website Address, or official site from Wikidata)
-> Defence logo for Defence-portfolio bodies -> parent organisation / portfolio
department icon -> jurisdiction government icon. Every row gets a file.
"""
import csv, hashlib, json, re, shutil, unicodedata, zipfile
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
import sys
sys.path.insert(0, str(Path(__file__).parent))
from fetch_icons_deep import quality

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/workspace/icons_work"); CACHE = WORK / "cache"
ICONS = ROOT / "icons"
PREFIX = {"Commonwealth": "cth", "NSW": "nsw", "Victoria": "vic", "Queensland": "qld", "WA": "wa", "SA": "sa", "Tasmania": "tas", "ACT": "act", "NT": "nt"}
JURIS = {"Commonwealth": "COA", "NSW": "https://www.nsw.gov.au/", "Victoria": "VIC",
         "Queensland": "https://www.qld.gov.au/", "WA": "https://www.wa.gov.au/", "SA": "SA",
         "Tasmania": "TAS", "ACT": "ACT", "NT": "https://nt.gov.au/"}
DEFENCE = "https://www.defence.gov.au/"
PORTFOLIO = {
 "Commonwealth": [("Veterans", "https://www.dva.gov.au/"), ("Finance", "https://www.finance.gov.au/"), ("Infrastructure", "https://www.infrastructure.gov.au/"),
   ("Industry", "https://www.industry.gov.au/"), ("Agriculture", "https://www.agriculture.gov.au/"),
   ("Attorney", "https://www.ag.gov.au/"), ("Health", "https://www.health.gov.au/"), ("Treasury", "https://treasury.gov.au/"),
   ("Climate", "https://www.dcceew.gov.au/"), ("Home Affairs", "https://www.homeaffairs.gov.au/"), ("Foreign Affairs", "https://www.dfat.gov.au/"),
   ("Education", "https://www.education.gov.au/"), ("Employment", "https://www.dewr.gov.au/"), ("Social Services", "https://www.dss.gov.au/")],
 "NSW": [("Health", "https://www.health.nsw.gov.au/"), ("Climate", "https://www.energy.nsw.gov.au/"), ("Communities and Justice", "https://www.dcj.nsw.gov.au/"),
   ("Treasury", "https://www.treasury.nsw.gov.au/"), ("Primary Industries", "https://www.dpi.nsw.gov.au/"), ("Planning", "https://www.planning.nsw.gov.au/"),
   ("Transport", "https://www.transport.nsw.gov.au/"), ("Education", "https://education.nsw.gov.au/")],
 "Victoria": [("Health", "https://www.health.vic.gov.au/"), ("Energy, Environment", "https://www.deeca.vic.gov.au/"), ("Jobs, Skills", "https://djsir.vic.gov.au/"),
   ("Justice", "https://www.justice.vic.gov.au/"), ("Treasury", "https://www.dtf.vic.gov.au/"), ("Transport", "https://www.transport.vic.gov.au/"),
   ("Families", "https://www.dffh.vic.gov.au/"), ("Education", "https://www.education.vic.gov.au/")],
}
DEF_RE = re.compile(r"\b(Defence|Army|Navy|Air Force|ADF|RAAF|RAN|Military)\b")

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace("&", " and ").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:90].rstrip("-")

def host_root(u):
    u = (u or "").strip()
    if not u: return None
    if "://" not in u: u = "http://" + u
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc.lower()}/" if p.netloc else None

def norm(s): return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).replace(" the ", " ").strip()

def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    hosts = json.loads((WORK / "hosts.json").read_text())
    wd = json.loads((WORK / "wikidata_sites.json").read_text())
    # find google-s2 default-globe hash(es) to reject
    s2_counts = {}
    for v in hosts.values():
        if v.get("method") == "google-s2": s2_counts[v["s2_sha"]] = s2_counts.get(v["s2_sha"], 0) + 1
    s2_default = {h for h, n in s2_counts.items() if n >= 3}
    # Curated fallback logos (all >= 256 px rasters of official artwork, see README)
    CUR = {
     "COA": ("_cth_coat_of_arms.png", "https://www.agriculture.gov.au/themes/custom/awe/images/australian-government-logo-512.png"),
     "DEFENCE": ("_defence_crest.png", "https://www.defence.gov.au/themes/custom/custom/defence8ui/images/gov-crest-horizontal.svg"),
     "VIC": ("_vic_govt.png", "https://www.vic.gov.au/ (footer Victoria State Government logo SVG)"),
     "TAS": ("_tas_govt.png", "https://www.service.tas.gov.au/__data/assets/git_bridge/0021/290190/dist/mysource_files/tasmania-govt-black..svg"),
     "SA": ("_sa_govt.png", "https://www.sa.gov.au/__data/assets/image/0006/591828/og-gosa-colour-on-white.png"),
     "ACT": ("_act_govt.png", "https://www.act.gov.au/__data/assets/image/0019/2541430/ACTGov_inline_black.png"),
    }
    for k, (f, src) in CUR.items():
        hosts[k] = {"ok": True, "method": "own-site", "file": f, "side": Image.open(CACHE / f).size[0], "orig": "", "src": src}
    hosts["DEFENCE"].update(svg="_defence_crest_horizontal.svg", svg_src=CUR["DEFENCE"][1])
    def good(url):
        h = hosts.get(url) if url else None
        ok = lambda x: x and x.get("ok") and quality((CACHE / x["file"]).read_bytes())
        if (not ok(h) or h.get("method") == "google-s2") and url and url.startswith("http"):
            alt = ("https://" + url[7:]) if url.startswith("http://") else ("http://" + url[8:])
            a = hosts.get(alt)
            if ok(a) and (a.get("method") == "own-site" or not ok(h)): h = a
        if not h or not h.get("ok"): return None
        if h.get("method") == "google-s2" and h.get("s2_sha") in s2_default: return None
        if not quality((CACHE / h["file"]).read_bytes()): return None
        return h
    def good_fb(url):  # fallback icons must be decent: >= 128 px
        for k in (url, "BIG:" + str(url)):
            h = good(k)
            if h and Image.open(CACHE / h["file"]).size[0] >= 128: return h
        return None
    for k in list(hosts):
        if not good(k): pass

    from describe import host_ok, wd_conflict
    def wdget(r):
        """Wikidata site for a row; state rows share a title-only key, so check host and description jurisdiction."""
        w = wd.get(r["Id"] + "|" + r["Title"])
        if not w: return None
        if not host_ok(w.get("website", ""), r["Jurisdiction"]): return None
        if wd_conflict(w.get("description", ""), r["Jurisdiction"]): return None
        return w
    # pass 1: own icons
    res = {}
    for i, r in enumerate(rows):
        site = r["Website Address"].strip(); how = "own-site"
        if not site:
            w = wdget(r)
            if w: site, how = w["website"], "own-site-wikidata"
        h = good(host_root(site))
        if h:
            res[i] = dict(site=site, host=h, hkey=host_root(site), method=how if h["method"] == "own-site" else "google-s2", note="")
    own_by_title = {}
    for i, v in res.items():
        own_by_title.setdefault((rows[i]["Jurisdiction"], norm(rows[i]["Title"])), v)

    parent_of = {(r["Jurisdiction"], norm(r["Title"])): r["Parent Organisation"] for r in rows if r["Parent Organisation"]}
    # pass 2: fallbacks
    for i, r in enumerate(rows):
        if i in res: continue
        j = r["Jurisdiction"]; port = r["Portfolio"]; parent = r["Parent Organisation"]
        site = r["Website Address"].strip() or ((wdget(r) or {}).get("website", ""))
        note = "site icon not retrievable" if site else "no website"
        if j == "Commonwealth" and "Veterans" not in port and (DEF_RE.search(port) or DEF_RE.search(parent) or DEF_RE.search(r["Title"])):
            res[i] = dict(site=site, host=good_fb("DEFENCE"), method="defence-fallback", note=note + "; Department of Defence"); continue
        # walk up the parent chain (e.g. second-tier subsidiary -> subsidiary -> GOC)
        ph = None; p = parent; seen = set()
        while p and (j, norm(p)) not in seen and not ph:
            seen.add((j, norm(p)))
            ph = good_fb(own_by_title[(j, norm(p))]["hkey"]) if (j, norm(p)) in own_by_title else None
            if not ph: p = parent_of.get((j, norm(p)), "")
        if ph:
            res[i] = dict(site=site, host=ph, method="parent", note=note + "; parent: " + p); continue
        hit = None
        for key, url in PORTFOLIO.get(j, []):
            if key.lower() in port.lower() and good_fb(url): hit = url; break
        if hit:
            res[i] = dict(site=site, host=good_fb(hit), method="parent", note=note + "; portfolio: " + port); continue
        res[i] = dict(site=site, host=good_fb(JURIS[j]), method="fallback-jurisdiction", note=note); assert res[i]["host"], j

    # write files
    if ICONS.exists(): shutil.rmtree(ICONS)
    (ICONS / "png").mkdir(parents=True); (ICONS / "svg").mkdir()
    used = set(); manifest = []
    for i, r in enumerate(rows):
        base = PREFIX[r["Jurisdiction"]] + "-" + slugify(r["Title"]); slug = base; n = 2
        while slug in used: slug = f"{base}-{n}"; n += 1
        used.add(slug)
        v = res[i]; h = v["host"]
        src_png = CACHE / h["file"]; data = src_png.read_bytes()
        (ICONS / "png" / f"{slug}.png").write_bytes(data)
        svg_rel = ""
        if h.get("svg") and v["method"] in ("own-site", "own-site-wikidata", "defence-fallback"):
            shutil.copyfile(CACHE / h["svg"], ICONS / "svg" / f"{slug}.svg"); svg_rel = f"icons/svg/{slug}.svg"
        r["Icon file"] = f"icons/png/{slug}.png"; r["Icon source URL"] = h["src"]; r["Icon method"] = v["method"]
        manifest.append({"slug": slug, "org title": r["Title"], "jurisdiction": r["Jurisdiction"], "website": v["site"],
                         "icon file": r["Icon file"], "svg file": svg_rel, "icon source URL": h["src"], "method": v["method"],
                         "notes": v["note"], "width": Image.open(CACHE / h["file"]).size[0], "height": Image.open(CACHE / h["file"]).size[1], "original size": h.get("orig", ""),
                         "sha256": hashlib.sha256(data).hexdigest()})
    cols = list(rows[0].keys())
    for p in [ROOT / "data/organisations.csv"]:
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    fname = {"Commonwealth": "commonwealth", "NSW": "nsw", "Victoria": "victoria", "Queensland": "queensland", "WA": "wa", "SA": "sa", "Tasmania": "tasmania", "ACT": "act", "NT": "nt"}
    for j, fn in fname.items():
        with open(ROOT / "data/by-jurisdiction" / f"{fn}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows([r for r in rows if r["Jurisdiction"] == j])
    with open(ICONS / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys())); w.writeheader(); w.writerows(manifest)
    with zipfile.ZipFile(ICONS / "aus-gov-orgs-icons-png.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for m in manifest: z.write(ROOT / m["icon file"], m["icon file"].split("/", 1)[1])
        z.write(ICONS / "manifest.csv", "manifest.csv")
    from collections import Counter
    print(Counter(m["method"] for m in manifest))
    for j in PREFIX: print(j, Counter(m["method"] for m in manifest if m["jurisdiction"] == j))
    print("svg", sum(1 for m in manifest if m["svg file"]), "unique pngs", len({m["sha256"] for m in manifest}))

if __name__ == "__main__": main()
