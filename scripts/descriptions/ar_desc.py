#!/usr/bin/env python3
"""Pick an annual-report link and an 'about us / our role' description for each row from cache_ar.json."""
import csv, json, re, sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from describe import clean_desc, norm
from leg_match import variants, sig_words
L = Path("/workspace/agor-sheet/leg")
HUBS = {"nsw.gov.au", "wa.gov.au", "qld.gov.au", "vic.gov.au", "sa.gov.au", "tas.gov.au", "act.gov.au", "nt.gov.au", "dcj.nsw.gov.au",
        "environment.nsw.gov.au", "health.nsw.gov.au", "health.vic.gov.au", "health.qld.gov.au", "health.wa.gov.au", "sahealth.sa.gov.au", "health.tas.gov.au", "cmtedd.act.gov.au"}
BADURL = re.compile(r"news|media|release|response|child-death|tabled|submission|consultation|strategy|plan-|budget|guide|case-study|licensee|licence-annual|announcement", re.I)

def acronyms(title):
    out = set(re.findall(r"\(([A-Z][A-Za-z]{1,8})\)", title))
    caps = "".join(w[0] for w in re.findall(r"[A-Z][a-z]+", re.sub(r"\([^)]*\)", "", title)))
    if len(caps) >= 3: out.add(caps)
    return out

def mentions(text, title):
    t = re.sub(r"\s+", " ", text)
    for v in variants(title) + [re.sub(r"\s*\([^)]*\)", "", title)]:
        if re.search(r"(?<![A-Za-z])" + re.escape(v) + r"(?![A-Za-z])", t, re.I): return True
    return False

def host(u): return urlparse(u).netloc.lower().removeprefix("www.")

def pick(row, c):
    title = row["Title"]
    out = {}
    link = c.get("ar_link")
    if not link or BADURL.search(link): return out
    ys = [int(y) for y in re.findall(r"20[12]\d", link)]
    if ys and max(ys) < 2023: return out
    text = (c.get("pdf_text") or "") + " " + (c.get("ar_page_text") or "")
    if not mentions(text[:80000], title): return out
    h = host(link); sh = host(row["Website Address"])
    path_ok = len(set(re.findall(r"[a-z]+", link.lower())) & sig_words(title)) >= 2 or any(a.lower() in link.lower() for a in acronyms(title))
    if h in HUBS and not path_ok: return out
    if c.get("pdf") and BADURL.search(c["pdf"]): c = dict(c, pdf_text="")
    out["Annual Reports"] = link
    # description: paragraphs in the PDF (first 15 pages) or AR page that say what the body is / does
    src = c.get("pdf_text") or ""
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", src)]
    names = [re.escape(v) for v in variants(title)] + [re.escape(a) for a in acronyms(title)] + [r"We"]
    rx = re.compile(r"^(?:The\s+)?(?:" + "|".join(names) + r")\s*(?:\([^)]{1,15}\)\s*)?(?:is|are|was established|was created|was formed|has been)\b", re.I)
    for p in paras:
        if len(p) < 60 or len(p) > 1500: continue
        if not rx.search(p): continue
        if re.search(r"\b(this|the) (annual )?report\b|financial statements|\$\s?\d|per cent|%|\b20\d\d[–-]\d\d\b|year in review|highlights", p[:250], re.I): continue
        if re.search(r"\b(is|are) (pleased|proud|delighted|committed to (?:continuing|delivering))\b", p, re.I): continue
        first = re.split(r"(?<=[a-z)])\.\s", p)[0]
        if re.search(r"\b(committed|also|fortunate|child safe|setting the standard|proud|honoured|made up of|appointed)\b", first, re.I): continue
        if not re.search(r"\b(is (?:a|an|the)\b|was established|established (?:under|by|in)|statutory|responsible for|role is|purpose is|provides?|delivers?|regulat|administer|manag|government agency)", p[:400], re.I): continue
        if c.get("pdf"):
            ys = [int(y) for y in re.findall(r"20[12]\d", c["pdf"])]
            if ys and max(ys) < 2023: continue
        d = clean_desc(p, title)
        if d and len(d) >= 60:
            out["Description"] = d; out["Description source URL"] = c.get("pdf") or link
            break
    return out

if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[2]
    cache = json.loads((L / "cache_ar.json").read_text())
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    n = 0
    for r in rows:
        c = cache.get(r["Jurisdiction"] + "|" + r["Title"])
        if not c: continue
        o = pick(r, c)
        if o:
            n += 1
            print(r["Jurisdiction"], "|", r["Title"], "|", o.get("Annual Reports"), "|", (o.get("Description") or "")[:300], "|", r["Description method"])
    print(n)
