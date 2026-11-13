#!/usr/bin/env python3
"""Fill AGOR-style Description (plus other blank AGOR columns) from official sources.

Inputs (fetched by the scripts in scripts/descriptions/, cached in /workspace/agor-sheet/desc):
  qld_register.json   Queensland Register of Appointees to Government Bodies (BodyDisplay pages)
  cache_nswdir.json   NSW Government Directory (service.nsw.gov.au/nswgovdirectory)
  cache_wa.json       WA.gov.au organisation pages (www.wa.gov.au/organisation/<slug>)
  cache_nsw.json      NSW.gov.au departments-and-agencies pages
  cache_sites.json    official websites (home page and about page meta descriptions)
  cache_wd.json       Wikidata (description; official website P856)
  abr_addr.json       ABR business-address state/postcode for each ABN

Description priority: existing AGOR (Commonwealth) / source list > official directory
(Qld register, NSW directory, WA.gov.au, NSW.gov.au) > official site > Wikidata.
Text is condensed to at most three sentences and first-person wording ("We ...")
is put into the third person; nothing else is added.
"""
import csv, json, re, html, sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
D = Path("/workspace/agor-sheet/desc")
ABR_SRC = "ABR ABN Bulk Extract (11 November 2026) –"
NEW_COLS = ["Description source URL", "Description method", "ABR note", "Other fields source"]
STATES = r"NSW|VIC|QLD|WA|SA|TAS|ACT|NT"

def J(n):
    p = D / n
    return json.loads(p.read_text()) if p.exists() else {}

def norm(s):
    s = html.unescape(s).lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"\bformerly\b.*", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"^the ", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()

ABBR = [("new south wales", "nsw"), ("queensland", "qld"), ("victoria", "vic"), ("western australia", "wa"), ("south australia", "sa"),
        ("tasmania", "tas"), ("northern territory", "nt"), ("australian capital territory", "act")]
def keys(t):
    out = {norm(t), norm(re.sub(r"\s*\([^)]*\)", "", t))}
    m = re.match(r"^(.+?),\s*(.+)$", t)
    if m: out.add(norm(m.group(2) + " " + m.group(1)))
    more = set()
    for k in out:
        k2 = k
        for full, ab in ABBR: k2 = re.sub(rf"\b{full}\b", ab, k2)
        more.add(k2)
        k3 = re.sub(r"\s+(of|for)?\s*(nsw|qld|vic|wa|sa|tas|nt|act)$", "", k2)
        k3 = re.sub(r"^(nsw|qld|vic|wa|sa|tas|nt|act)\s+", "", k3)
        if len(k3.split()) >= 2: more.add(k3)
    return {k for k in out | more if len(k) > 3}

# ---------- text cleaning ----------
BAD = re.compile(r"cookie|javascript|skip to|\blog ?in\b|sign ?in|subscribe|click|this website|our website|this site|official website|"
                 r"welcome to|home ?page|newsletter|©|copyright|\byou\b|\byour\b|you'll|learn more|find out|read more|browser|"
                 r"\bwebsite\b|this section|this page|\bgo to\b|\bvisit\b|view a list|to contact|\bFind [A-Z]|learn what|here\.|phone|call us|email us|opening hours|covid|we acknowledge|traditional (owners|custodians)|^menu|search", re.I)
VERB_IRREG = {"are": "is", "have": "has", "do": "does", "go": "goes", "were": "was", "be": "is"}
MODALS = {"will", "can", "may", "must", "should", "would", "could", "also", "now", "currently", "proudly", "work", "aim", "strive", "seek"}

def conj(v):
    lv = v.lower()
    if lv in VERB_IRREG: return VERB_IRREG[lv]
    if lv in {"will", "can", "may", "must", "should", "would", "could"}: return v
    if re.search(r"[^aeiou]y$", lv): return v[:-1] + "ies"
    if re.search(r"(s|sh|ch|x|z|o)$", lv): return v + "es"
    return v + "s"

def third_person(text, subject):
    first = [True]
    def subj():
        if first[0]:
            first[0] = False; return subject
        return "It"
    def repl_we(m):
        words = m.group(2)
        toks = re.findall(r"[A-Za-z'-]+|,|\s+|[^A-Za-z,\s]+", words)
        out, i, chain = [], 0, True
        # conjugate leading adverbs then verb chain "examine, register and investigate"
        state = "verb"
        while i < len(toks):
            t = toks[i]
            if state == "verb" and re.match(r"[a-z]", t or ""):
                if t in {"also", "now", "currently", "proudly", "actively", "independently", "directly", "jointly", "primarily", "mainly", "collectively", "together"}:
                    out.append(t); i += 1; continue
                out.append(conj(t)); i += 1
                # continue chain only for ", word" or " and word" / " or word"
                rest = "".join(toks[i:i+4])
                m2 = re.match(r"(,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+)([a-z]+)\b", rest)
                if m2 and m2.group(2) not in {"the", "a", "an", "to", "in", "on", "for", "with"} and toks[i] in (",", " ") and (toks[i] == "," or toks[i+1:i+2] in (["and"], ["or"])):
                    # consume separator tokens up to the next verb
                    sep = m2.group(1)
                    consumed = ""
                    while consumed.strip() != sep.strip() and i < len(toks):
                        consumed += toks[i]; out.append(toks[i]); i += 1
                    continue
                state = "done"
            else:
                out.append(t); i += 1
        return m.group(1) + subj() + " " + "".join(out)
    sents = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        s = re.sub(r"^(\W*)We're\b", lambda m: m.group(1) + "We are", s)
        s = re.sub(r"^(\W*)We've\b", lambda m: m.group(1) + "We have", s)
        if re.match(r"^\W*We\s", s):
            s = re.sub(r"^(\W*)We\s+([^.;:]*)", repl_we, s, count=1)
            s = re.sub(r"\b(and|but) (lead|work|help|deliver|provide|support|manage|ensure|promote|develop|oversee|administer|advise|regulate|operate|maintain|protect|coordinate|connect|champion|drive|partner|offer|invest|build|plan)\b",
                       lambda m: m.group(1) + " " + conj(m.group(2)), s)
            s = re.sub(r"\b(and|but) are\b", r"\1 is", s); s = re.sub(r"\b(and|but) have\b", r"\1 has", s)
        elif re.match(r"^\W*Our\s", s):
            s = re.sub(r"^(\W*)Our\s", lambda m: m.group(1) + (subject + "'s " if first[0] else "Its "), s, count=1); first[0] = False
        else:
            first[0] = False
        s = re.sub(r"\bwe are\b", "it is", s); s = re.sub(r"\bwe have\b", "it has", s)
        s = re.sub(r"\bwe ((?:also|now|currently|jointly|independently)\s+)?([a-z]+)\b",
                   lambda m: "it " + (m.group(1) or "") + (m.group(2) if m.group(2) in {"will", "can", "may", "must", "should", "would", "could"} else conj(m.group(2))), s)
        s = re.sub(r"\b[Oo]ur (state|community|communities|region|city|shire|nation|country|people)\b", r"the \1", s)
        s = re.sub(r"\b[Oo]ur\b", "its", s); s = re.sub(r"\bourselves\b", "itself", s); s = re.sub(r"\bus\b", "it", s)
        s = re.sub(r"\bwe\b", "it", s)
        sents.append(s)
    return " ".join(sents)

def subject_of(title):
    t = re.sub(r"\s*\([^)]*\)$", "", title).strip()
    if t.lower().startswith("the "): return "The " + t[4:]
    if re.search(r"\b(Department|Office|Commission|Board|Authority|Council|Trust|Tribunal|Committee|Corporation|Agency|Service|Centre|"
                 r"Institute|Commissioner|Court|Registry|Fund|Foundation|Library|Museum|Gallery|Network|Panel|Ombudsman|Regulator|Secretariat)\b", t) \
            and not re.search(r",\s*(NSW\s+)?(Department|Office|Commissioner|Minister)\b", t):
        return "The " + t
    return t

def clean_desc(raw, title):
    if not raw: return ""
    t = re.sub(r"\s+", " ", html.unescape(raw)).strip()
    t = re.sub(r"^NSW Government Directory listing for [^.]*\.\s*", "", t)
    truncated = t.endswith("…") or t.endswith("...")
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", t) if s.strip()]
    if truncated and sents: sents = sents[:-1]
    sents = [s for s in sents if not BAD.search(s) and len(s.split()) >= 4]
    if not sents: return ""
    out = []
    for s in sents:
        if len(" ".join(out + [s])) > 600: break
        out.append(s)
        if len(out) == 3: break
    if not out:
        cut = sents[0][:600]
        if "; " not in cut: return ""
        out = [cut[:cut.rfind("; ")] + "."]
    d = third_person(" ".join(out), subject_of(title))
    d = re.sub(r"\s+([.,;:])", r"\1", d).replace(";.", ".")
    d = d[0].upper() + d[1:]
    if not re.search(r"[.!?]$", d): d += "."
    if len(d) < 40 or len(d.split()) < 6: return ""
    if norm(d) == norm(title): return ""
    return d

ROLE = re.compile(r"\b(provid|responsib|manag|deliver|regulat|support|promot|administ|overse|advis|operat|develop|protect|ensur|govern|represent|"
                  r"statutory|registr|investigat|fund|maintain|"
                  r"conserv|research|educat|train|supply|supplies|insur|invest|plan|coordinat|establish|led|lead|leads|role|purpose|function|"
                  r"is (?:a|an|the|australia's|[A-Z][\w'’]+'s)\b|are the)", re.I)
IMPERATIVE = re.compile(r"^(Charge|Find|Discover|Explore|Study|Visit|Join|Apply|Book|Get|Stay|Check|See|Browse|Search|Access|Read|Learn|View|Download|Contact|Report|Register|Make|Start|Enjoy|Experience|Inspiring|Connecting|Creating|Building|Welcome)\b")

def site_ok(d, title):
    first = d.split(". ")[0]
    core = re.sub(r"\s*\([^)]*\)", "", title)
    d = d.replace(core, "").replace(subject_of(title), "")
    if IMPERATIVE.match(first): return False
    if not ROLE.search(d): return False
    return True

def wd_desc(desc):
    if not desc or len(desc) < 20: return ""
    if re.match(r"^(government |public )?organi[sz]ation (in|based|of)\b", desc, re.I): return ""
    if re.search(r"wikimedia|disambiguation|human|person", desc, re.I): return ""
    d = desc[0].upper() + desc[1:]
    return d if d.endswith(".") else d + "."

STATE_RX = {"NSW": r"New South Wales|\bNSW\b|Sydney|Newcastle|Wollongong", "Victoria": r"Victoria|\bVic\b|Melbourne|Geelong|Ballarat|Bendigo",
            "Queensland": r"Queensland|\bQld\b|Brisbane|Townsville|Cairns|Gold Coast", "WA": r"Western Australia|\bWA\b|Perth|Fremantle",
            "SA": r"South Australia|\bSA\b|Adelaide", "Tasmania": r"Tasmania|\bTas\b|Hobart|Launceston",
            "ACT": r"Australian Capital Territory|\bACT\b|Canberra", "NT": r"Northern Territory|\bNT\b|Darwin|Alice Springs"}
def wd_conflict(desc, j):
    """True when a Wikidata description names another jurisdiction (or the federal government)."""
    if j == "Commonwealth": return False
    if re.search(r"federal|Commonwealth|(?<!South )(?<!Western )Australian Government", desc, re.I): return True
    for jj, rx in STATE_RX.items():
        if jj == j: continue
        if jj == "SA" and j == "WA" or jj == "WA" and j == "SA":
            if re.search({"SA": r"South Australia|Adelaide", "WA": r"Western Australia|Perth"}[jj], desc): return True
            continue
        if jj in ("SA", "WA", "ACT", "NT"):
            if re.search({"SA": r"South Australia|Adelaide", "WA": r"Western Australia|Perth", "ACT": r"Capital Territory|Canberra", "NT": r"Northern Territory|Darwin"}[jj], desc): return True
            continue
        if re.search(rx, desc, re.I): return True
    return False

def wd_ok(desc, r):
    j = r["Jurisdiction"]
    if j == "Commonwealth": return True
    own = re.search(STATE_RX[j], desc, re.I)
    other = any(re.search(rx, desc, re.I) for jj, rx in STATE_RX.items() if jj != j and not (j == "WA" and jj == "SA") and not (j == "SA" and jj == "WA")) \
        or re.search(r"federal|Commonwealth|(?<!South )(?<!Western )Australian Government", desc, re.I)
    if j == "SA" and re.search(r"Western Australia", desc): other = True
    if j == "WA" and re.search(r"South Australia", desc): other = True
    if j == "SA" and not re.search(r"South Australia|Adelaide|\bSA\b", desc): own = None
    if j == "WA" and not re.search(r"Western Australia|Perth|Fremantle|\bWA\b", desc): own = None
    if own and not other: return True
    if not other and re.search(STATE_RX[j], r["Title"], re.I): return True
    return False

SUF = {"NSW": "nsw", "Victoria": "vic", "Queensland": "qld", "WA": "wa", "SA": "sa", "Tasmania": "tas", "ACT": "act", "NT": "nt"}
def host_ok(url, j):
    """False when a state/territory row points at another jurisdiction's or a federal gov.au host."""
    if j == "Commonwealth" or not url: return True
    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    if any(re.search(rf"\.{s}\.(gov|edu)\.au$", host) for jj, s in SUF.items() if jj != j): return False
    if host.endswith(".gov.au") and not re.search(r"\.(nsw|vic|qld|wa|sa|tas|act|nt)\.gov\.au$", host): return False
    return True

def phone_fmt(p):
    p = re.sub(r"\s+", " ", p).strip()
    m = re.match(r"^\+?61\s*(\d)\s*(\d{4})\s*(\d{4})$", p.replace("-", " "))
    if m: return f"(0{m.group(1)}) {m.group(2)} {m.group(3)}"
    return p

def parse_addr(lines):
    s = ", ".join(l.strip().strip(",") for l in lines if l.strip())
    s = re.sub(r"\s+", " ", s)
    m = re.match(rf"^(.*?)[, ]+([A-Za-z' .-]+?)[, ]+({STATES})[, ]+(\d{{4}})$", s, re.I)
    if not m: return None
    street, sub, st, pc = m.groups()
    if re.match(r"^(PO|GPO|Locked)\s*Bag|^(PO|GPO)\s*Box", street, re.I): return None
    sub = sub.strip(" ,")
    if sub.isupper(): sub = sub.title()
    return {"Head Office Street Address": street.strip(" ,"), "Head Office Suburb": sub, "Head Office State": st.upper(), "Head Office Postcode": pc}

ACT_RX = re.compile(r"\b(?:established|constituted|created|set up|continued|formed)\b[^.]{0,80}?\b(?:under|by)\s+(?:the\s+|section\s+\S+\s+of\s+the\s+|s\.?\s?\d+\w*\s+of\s+the\s+|Part\s+\S+\s+of\s+the\s+)?"
                    r"((?:[A-Z][A-Za-z'’()\-]*\s+|and\s+|of\s+|for\s+|the\s+|\(\w+\)\s+)*?Act\s+\d{4}(?:\s*\((?:NSW|Vic|Qld|WA|SA|Tas|ACT|NT|Cth)\))?)")

def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    cols = list(rows[0].keys())
    for c in NEW_COLS:
        if c not in cols:
            if c in ("Description source URL", "Description method"):
                cols.insert(cols.index("Description") + 1 + (c == "Description method"), c)
            else:
                cols.insert(cols.index("Icon file"), c)
    before = {c: sum(1 for r in rows if (r.get(c) or "").strip()) for c in cols}
    before_j = defaultdict(Counter)
    for r in rows:
        for c in cols:
            if (r.get(c) or "").strip(): before_j[r["Jurisdiction"]][c] += 1

    qreg = {}
    for i, d in J("qld_register.json").items():
        def f(k):
            v = (d.get(k) or "").strip()
            return "" if re.match(r"^[A-Z][A-Za-z' ]+:\s*", v) else v
        rec = {k: f(k) for k in d if not k.startswith("_")}
        if "No" in (d.get("Body is Active") or "") or "Body is Active: \nNo" in (d.get("Completion Date") or ""): continue
        rec["_url"] = f"https://governmentbodies.premiers.qld.gov.au/BodyDisplay.aspx?Parameter={i}"
        for k in keys(rec.get("Body Name", "")): qreg.setdefault(k, []).append(rec)
    nswdir = {}
    for u, d in J("cache_nswdir.json").items():
        if not d or not d.get("name"): continue
        d["_url"] = u
        for k in keys(d["name"]): nswdir.setdefault(k, []).append(d)
    wa, nswp, sites, wd = J("cache_wa.json"), J("cache_nsw.json"), J("cache_sites.json"), J("cache_wd.json")
    addr = J("../abr/abr_addr.json") if (D / "../abr/abr_addr.json").exists() else {}

    # site meta descriptions shared by several rows are generic -> ignore
    site_desc_count = Counter()
    def site_cands(k):
        v = sites.get(k)
        if not v or not host_ok(v.get("site", ""), k.split("|")[0]): return []
        out = []
        for pg in v.get("pages", [])[::-1]:  # about pages first
            m = pg.get("meta", {})
            for f in ("description", "og:description"):
                if m.get(f): out.append((m[f], pg["url"])); break
        # first substantial paragraph of an "about" page
        for pg in v.get("pages", [])[1:]:
            if not re.search(r"about|who-we-are|what-we-do|our-role", pg["url"], re.I): continue
            for line in pg.get("text", "").split("\n"):
                line = line.strip()
                if len(line.split()) >= 18 and not BAD.search(line) and re.search(r"[.]$", line):
                    out.append((line, pg["url"])); break
        return out
    for r in rows:
        for txt, u in site_cands(r["Jurisdiction"] + "|" + r["Title"]):
            site_desc_count[norm(txt)] += 1

    meth = Counter(); filled = Counter(); extra_sites = {}
    for r in rows:
        k = r["Jurisdiction"] + "|" + r["Title"]
        other = []
        def setf(col, val, src):
            val = (val or "").strip()
            if val and not (r.get(col) or "").strip():
                r[col] = val; filled[col] += 1; other.append((col, src))
        # ABR note
        if r["Source name"].startswith(ABR_SRC) and r["Description"].startswith("Added from the ABR"):
            r["ABR note"] = r["Description"]; r["Description"] = ""
        r.setdefault("Description source URL", ""); r.setdefault("Description method", "")
        r.setdefault("ABR note", r.get("ABR note", "")); r.setdefault("Other fields source", "")
        if r["Jurisdiction"] == "Commonwealth" and r["Description"].strip():
            r["Description method"] = "existing-AGOR"; r["Description source URL"] = r["Source URL"]
        elif r["Description"].strip() and not r["Description method"]:
            r["Description method"] = "source-list"; r["Description source URL"] = r["Source URL"]

        cands = []  # (method, text, url)
        q = [x for kk in keys(r["Title"]) for x in qreg.get(kk, [])] if r["Jurisdiction"] == "Queensland" else []
        q = q[0] if q and len({x["_url"] for x in q}) == 1 else None
        nd = [x for kk in keys(r["Title"]) for x in nswdir.get(kk, [])] if r["Jurisdiction"] == "NSW" else []
        nd = nd[0] if nd and len({x["_url"] for x in nd}) == 1 else None
        w = wa.get(k) if r["Jurisdiction"] == "WA" else None
        np_ = nswp.get(k) if r["Jurisdiction"] == "NSW" else None
        if q and q.get("Body Description"): cands.append(("official-directory", q["Body Description"], q["_url"]))
        if nd:
            t = nd["text"]; desc = ""
            m = re.search(r"\n(?:More information|About [^\n]{2,60})\n(.*?)\n(?:Related agencies|Related department|Featured services|Back to top)", t, re.S)
            if m:
                parts, buf, listing = [], [], False
                for line in [x.strip() for x in m.group(1).split("\n") if x.strip()]:
                    if listing and not re.search(r"[.]$", line): buf.append(line.rstrip(";,")); continue
                    if listing and buf is not None and line.endswith(".") and not line.endswith(":"):
                        buf.append(line.rstrip(".")); parts.append("; ".join(buf) + "."); buf = []; listing = False; continue
                    if buf: parts.append("; ".join(buf) + "."); buf = []
                    listing = line.endswith(":")
                    if listing: parts.append(line); buf = []
                    else: parts.append(line)
                if buf: parts.append("; ".join(buf) + ".")
                desc = " ".join(parts).replace(": ;", ":")
                desc = re.sub(r":\s+(?=\S)", ": ", desc)
            else:
                m = re.search(r"\nListen\n(.*?)\n(?:Website:|Street address:|Postal address:|Phone:|Email:|Related)", t, re.S)
                if m and len(m.group(1)) > 40: desc = m.group(1)
            if desc: cands.append(("official-directory", desc.replace("\n", " "), nd["_url"]))
        if w and w.get("meta", {}).get("description"): cands.append(("official-directory", w["meta"]["description"], w["url"]))
        if np_ and np_.get("meta", {}).get("description"): cands.append(("official-directory", np_["meta"]["description"], np_["url"]))
        for txt, u in site_cands(k):
            if site_desc_count[norm(txt)] == 1: cands.append(("official-site", txt, u))
        wdv = wd.get(k)
        if wdv and not wd_ok(wdv.get("desc", ""), r): wdv = None
        if wdv and not wdv.get("dissolved"): cands.append(("wikidata", wdv.get("desc", ""), f"https://www.wikidata.org/wiki/{wdv['qid']}"))

        if not r["Description"].strip():
            for mth, txt, u in cands:
                d = wd_desc(txt) if mth == "wikidata" else clean_desc(txt, r["Title"])
                if d and mth == "official-site" and not site_ok(d, r["Title"]): d = ""
                if d:
                    r["Description"] = d; r["Description method"] = mth; r["Description source URL"] = u; break
        if r["Description method"]: meth[(r["Jurisdiction"], r["Description method"])] += 1

        # ----- other columns from official directories -----
        if q:
            u = q["_url"]
            cd = q.get("Constitution Date", "")
            if re.match(r"^\d{2}/\d{2}/\d{4}$", cd): setf("Creation Date", re.sub(r"^0", "", cd[:2]) + cd[2:3] + re.sub(r"^0", "", cd[3:5]) + cd[5:], u)
            setf("Contact telephone", q.get("Phone Number", ""), u)
            em = q.get("Email", "")
            if re.match(r"^[^@\s]+@[^@\s]+$", em) and not re.match(r"^[a-z]+\.[a-z]+\d*@", em, re.I): setf("Generic agency email", em, u)
            a = parse_addr(q.get("Street Address", "").split("\n"))
            if a and not r["Head Office Street Address"]:
                for c, v in a.items(): setf(c, v, u)
            ma = q.get("Max Appointees", "")
            if ma.isdigit(): setf("Max Number of Board / Committee Members", ma, u)
            ap = q.get("Approval Process", "")
            if ap: setf("Board / Committee Appointed by", "Governor in Council" if "Governor in Council" in ap else ("Ministerial" if "Minist" in ap else "Other"), u)
            mr = (q.get("Members Remuneration Rate", "") + " " + q.get("Chairperson Remuneration Rate", "")).strip()
            if mr: setf("Paid Members?", "No" if re.fullmatch(r"(No Remuneration|Not applicable|\s)+", mr) else "Yes", u)
            if q.get("Reporting Requirements") == "Annual Report": setf("Annual Report Prepared and Tabled?", "Yes", u)
            links = [l for l in J("qld_register.json").get(u.split("=")[-1], {}).get("_links", []) if "premiers.qld" not in l]
        if nd:
            t, u = nd["text"], nd["_url"]
            m = re.search(r"\nWebsite:\n(https?://\S+)", t)
            if m: setf("Website Address", m.group(1).rstrip("/") + "/", u)
            m = re.search(r"\nPhone:\n([^\n]+)", t)
            if m: setf("Contact telephone", m.group(1).strip(), u)
            mails = [x for x in nd.get("mailto", []) if not re.match(r"^[a-z]+\.[a-z]+\d*@", x, re.I)]
            if mails: setf("Generic agency email", mails[0].split("?")[0], u)
            m = re.search(r"\nStreet address:\n(.*?)\n(?:Postal address|Phone|Email|Fax|Related|More information|Website)", t, re.S)
            if m and not r["Head Office Street Address"]:
                a = parse_addr(m.group(1).split("\n"))
                if a:
                    for c, v in a.items(): setf(c, v, u)
            m = re.search(r"\nRelated department\n([^\n]+)", t)
            if m and not r["Portfolio"]:
                dep = m.group(1).strip()
                mm = re.match(r"^(.+?),\s*(NSW\s+)?(Department|Office)\s+(of|for)(\s+the)?$", dep)
                setf("Portfolio", (f"{mm.group(3)} {mm.group(4)}{mm.group(5) or ''} {mm.group(1)}" if mm else dep), u)
        if w:
            t, u = w["text"], w["url"]
            for href, lt in w.get("links", []):
                lt2 = re.sub(r"<[^>]+>", "", html.unescape(lt)).strip()
                if lt2.lower().endswith("website") and "wa.gov.au/organisation" not in href:
                    setf("Website Address", href, u); break
            m = re.search(r"\nContact\n(?:Head office\n)?Address:\n([^\n]+)", t)
            if m and not r["Head Office Street Address"]:
                a = parse_addr([m.group(1)])
                if a:
                    for c, v in a.items(): setf(c, v, u)
            m = re.search(r"\nTelephone:\n([^\n]+)", t)
            if m: setf("Contact telephone", phone_fmt(m.group(1)), u)
            m = re.search(r"\nEmail:\n([^\s@]+@[^\s]+)", t)
            if m and not re.match(r"^[a-z]+\.[a-z]+\d*@", m.group(1), re.I): setf("Generic agency email", m.group(1), u)
            m = re.search(r"\nMinisterial reporting\n(.*?)\n(?:Corporate executive|Contact|Share)\n", t, re.S)
            if m:
                mins = re.findall(r"\n\s*Minister for ([^\n]+)", "\n" + m.group(1))
                if len(mins) == 1: setf("Portfolio", re.split(r";\s*Minister Assisting", mins[0])[0].strip(), u)
            ar = [href for href, lt in w.get("links", []) if re.search(r"annual report", re.sub(r"<[^>]+>", "", lt), re.I)]
            if ar: setf("Annual Reports", ar[0], u)
        # legislation from official text
        if not r["Established by/Under More Info"].strip() and r["Description method"] in ("official-directory", "official-site", "source-list"):
            m = ACT_RX.search(r["Description"])
            if m:
                act = re.sub(r"^(?:the|The)\s+", "", m.group(1)).strip()
                setf("Established by/Under More Info", act, r["Description source URL"])
                setf("Established By / Under", "Act / Regulation", r["Description source URL"])
        # wikidata website, used only if the site answered (checked by the site fetch)
        if wdv and wdv.get("site") and not r["Website Address"].strip() and host_ok(wdv["site"][0], r["Jurisdiction"]):
            s0 = wdv["site"][0]
            sv = sites.get(k)
            if sv and sv.get("site") == s0 and sv.get("pages"):
                setf("Website Address", s0, f"https://www.wikidata.org/wiki/{wdv['qid']} (P856; site checked)")
            else:
                extra_sites[k] = s0
        if not r["Website Address"].strip() and r["Jurisdiction"] != "Commonwealth":
            pass
        # ABR state / postcode
        abn = re.sub(r"\D", "", r["ABN"])
        if abn and abn in addr and addr[abn].get("state") and r["ABN match confidence"] in ("exact", "high"):
            if not r["Head Office State"].strip() and not r["Head Office Postcode"].strip():
                setf("Head Office State", addr[abn]["state"], "ABR ABN Bulk Extract (11 November 2026)")
                setf("Head Office Postcode", addr[abn]["postcode"], "ABR ABN Bulk Extract (11 November 2026)")
        if r["Head Office State"].strip() in STATES.split("|") and not r["Head Office Country"].strip() and any(c.startswith("Head Office") for c, _ in other):
            setf("Head Office Country", "Australia", next(src for c, src in other if c.startswith("Head Office")))
        if other:
            fams = defaultdict(list)
            for c, s in other: fams[s].append(c)
            add = "; ".join(f"{', '.join(cs)}: {s}" for s, cs in fams.items())
            r["Other fields source"] = (r["Other fields source"] + "; " if r["Other fields source"] else "") + add
    (D / "extra_sites.json").write_text(json.dumps(extra_sites))
    with open(ROOT / "data/organisations.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=cols, lineterminator="\n"); wr.writeheader()
        for r in rows: wr.writerow({c: r.get(c, "") for c in cols})
    after = {c: sum(1 for r in rows if (r.get(c) or "").strip()) for c in cols}
    rep = {"methods": {f"{a}|{b}": n for (a, b), n in sorted(meth.items())}, "filled": dict(filled),
           "before": before, "after": after, "extra_sites": len(extra_sites),
           "before_by_j": {j: dict(c) for j, c in before_j.items()}}
    (D / "describe_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({"filled": dict(filled), "extra_sites": len(extra_sites)}, indent=1))
    print(Counter(r["Description method"] for r in rows))

if __name__ == "__main__":
    main()
