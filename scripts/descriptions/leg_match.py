#!/usr/bin/env python3
"""Match each row still missing a Description to the Act that establishes it and pull the
functions/objects section. Writes /workspace/agor-sheet/leg/leg_matches.json keyed by row Id."""
import csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
L = Path("/workspace/agor-sheet/leg")
ABBR = {"NSW": "New South Wales", "Qld": "Queensland", "Vic": "Victoria", "WA": "Western Australia", "SA": "South Australia",
        "Tas": "Tasmania", "NT": "Northern Territory", "ACT": "Australian Capital Territory"}
JAB = {"NSW": "NSW", "Victoria": "Vic", "Queensland": "Qld", "WA": "WA", "SA": "SA", "Tasmania": "Tas", "ACT": "ACT", "NT": "NT"}
STOP = {"the", "of", "and", "for", "in", "on", "to", "a", "an", "new", "south", "wales", "queensland", "victoria", "victorian", "western",
        "australia", "australian", "tasmania", "tasmanian", "northern", "territory", "capital", "nsw", "qld", "vic", "wa", "sa", "tas", "nt", "act", "state", "inc", "incorporated"}
COMPANY = re.compile(r"\b(Pty|Ltd|Limited|Proprietary)\b|Corporations Act|Trust Deed", re.I)

HEAD = re.compile(r"^[ \t]*(\d+[A-Z]{0,3})(?:[.—–-][ \t]*|[ \t]+)([A-Z][^\n]{1,140}?)[ \t]*$", re.M)

def variants(title):
    t = re.sub(r"\s*\([^)]*\)", "", title).strip()
    t = re.sub(r",?\s+(Inc\.?|Incorporated)$", "", t)
    m = re.match(r"^(.+?),\s*((?:The\s+)?(?:Department|Office|Commissioner|Board|Commission|Agency|Authority)\b.*)$", t)
    if m: t = m.group(2) + " " + m.group(1)
    t = re.sub(r"^The\s+", "", t, flags=re.I)
    t = re.sub(r",\s*The$", "", t)
    t = re.sub(r"\bQLD\b", "Qld", t)
    out = {t}
    for ab, full in ABBR.items():
        for v in list(out):
            if re.search(rf"\b{ab}\b", v): out.add(re.sub(rf"\b{ab}\b", full, v))
            if re.search(rf"\b{full}\b", v): out.add(re.sub(rf"\b{full}\b", ab, v))
    for v in list(out):
        if "&" in v: out.add(v.replace("&", "and"))
        if " and " in v: out.add(v.replace(" and ", " & "))
    return [v for v in out if len(v) >= 8 and len(v.split()) >= 2]

ROLE_FIRST = re.compile(r"^(?:The\s+)?(?:[A-Z][a-z]+\s+)?(Commissioner|Office|Department|Board|Council|Commission|Trust|Authority|Corporation|Agency|Registrar|Ombudsman|Tribunal|Court|Inspector|Auditor|Director|Fund|Institute|Committee|Foundation|Library|Museum)\s+(?:of|for|on|to)\b")
def head_noun(title):
    t = re.sub(r"\s*\([^)]*\)", "", title).strip()
    t = re.sub(r",?\s+(Inc\.?|Incorporated)$", "", t)
    m = ROLE_FIRST.match(t)
    if m: return m.group(1).lower()
    ws = [w.lower() for w in re.findall(r"[A-Za-z]+", t) if w.lower() not in STOP]
    return ws[-1] if ws else ""

def sing(w):
    w = w.lower()
    return w[:-1] if w.endswith("s") and not w.endswith("ss") else w

def target_head(target):
    t = re.split(r"\s+(?:in relation to|in respect of|under|with|relating to|as|to|for)\s+", target)[0]
    ws = [w for w in re.findall(r"[A-Za-z]+", t)]
    return sing(ws[-1]) if ws else ""

TITLE_VARIANTS = []
def norm_t(x): return re.sub(r"[^a-z0-9]+", " ", re.sub(r"^the\s+", "", x.lower())).strip()

def sig_words(title):
    return {w for w in re.findall(r"[a-z]+", title.lower()) if w not in STOP and len(w) > 2}

def sections(text):
    hs = list(HEAD.finditer(text))
    out = []
    for i, m in enumerate(hs):
        end = hs[i + 1].start() if i + 1 < len(hs) else min(len(text), m.end() + 6000)
        body = text[m.end():end]
        if re.search(r"\s\d+$", m.group(2)) or re.search(r"\.{4,}", m.group(2)): continue  # table of contents
        out.append((m.group(1), m.group(2).strip(), body, m.start()))
    return out

EST = re.compile(r"\b(established|constituted|continued|created)\b", re.I)

V = r"(established|constituted|continued|created)"
def find_est(text, vs):
    """Return (variant, pos, verb) for an establishment statement naming the body."""
    for v in vs:
        nm = r"(?:the\s+)?" + re.escape(v).replace(r"\ ", r"\s+")
        pats = [nm + r"(?:\s*\([^)]{0,80}\))?\s*(?:is|are)\s+(?:hereby\s+|by\s+this\s+Act\s+)?" + V + r"\b",
                r"\b(?:There\s+is|is\s+hereby|shall\s+be)\s+" + V + r"\b[^.;]{0,160}?" + nm + r"(?![A-Za-z])",
                r"\b(?:This\s+Act\s+)?(?:establishes|constitutes|continues)\s+" + nm + r"(?![A-Za-z])",
                r"\bThere\s+(?:is|shall\s+be|are)\s+(?:to\s+be\s+)?(?:a|an)\s+[^.;]{0,120}?(?:called|named|entitled|known\s+as|by\s+the\s+name\s+of|with\s+the\s+(?:corporate\s+)?name)\s+[\"“'‘]?" + nm + r"(?![A-Za-z])",
                nm + r"[\"”'’]?\s*(?:\([^)]{0,80}\)\s*)?(?:is|shall\s+be)\s+(?:to\s+be\s+)?a\s+body\s+corporate",
                r"\b" + V + r"\s+(?:as\s+)?(?:a\s+(?:body\s+corporate|corporation|statutory\s+body)[^.;]{0,40}?\s+)?(?:under|by)\s+(?:this\s+Act|section\s+\d+)[^.;]{0,20}?" + nm]
        for k, pt in enumerate(pats):
            m = re.search(pt, text, re.I)
            vm = None
            if not m: continue
            w = text[max(0, m.start() - 120): m.end() + 60]
            if re.search(r"\babolish|\bdissol|\bformer(ly)?\b|\brepeal", w, re.I): continue
            vm = re.search(V, m.group(0), re.I)
            if not vm and k >= 3: vm = None
            return (v, m.start(), vm.group(1).lower() if vm else ("continued" if "continues" in m.group(0).lower() else "constituted" if "constitutes" in m.group(0).lower() else "established"))
    return None

def section_of(text, pos):
    best = None
    for m in HEAD.finditer(text[:pos]): best = m
    if not best or pos - best.end() > 1500: return "", ""
    return best.group(1), best.group(2)

FUNC_H = re.compile(r"^(?!.*\b(?:delegat|chair|deputy|member|minister|secretary|staff|exercise|performance|conferral|additional|other|supplementary|incidental|limit|restrict|ancillary)\w*\b)(?:[A-Za-z ,]*?\b)?(objects?|functions?|purposes?|role|duties)\b(?:\s+(?:and|,)\s+(?:powers|objects?|functions?|purposes?|duties)\b)*(?:\s+of\s+(?:the\s+)?(.+?))?$", re.I)

def clean_item(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\[[^\]]*\]", "", s).strip()
    s = re.sub(r"(;|,|\.)?\s*(and|or)?\s*$", "", s).strip()
    s = re.sub(r"[;,:—–-]+$", "", s).strip()
    return s

def extract_functions(body, words, short):
    body = re.split(r"\n\s*(?:Note|Example|Examples)\b", body)[0]
    body = re.sub(r"[ \t]+", " ", body)
    # list form
    m = re.search(r"(?:^|\n)\s*(?:\(1\)\s*)?([^\n]{0,200}?(?:functions?|objects?)[^\n]{0,120}?(?:—|–|:|-)\s*)\n", body, re.I)
    items = []
    if m:
        lead = m.group(1)
        rest = body[m.end():]
        for im in re.finditer(r"(?:^|\n)\s*\(([a-z]{1,2})\)\s*([^\n]+)", rest):
            if im.group(1) in ("i", "ii", "iii", "iv", "v") and items and im.group(1) != "i" * 0 and not re.match(r"[a-z]$", im.group(1)): continue
            items.append((im.group(1), im.group(2)))
            nxt = rest[im.end(): im.end() + 30]
            if re.match(r"\s*\n\s*\(\d+\)", nxt) or re.match(r"\s*\n\s*\(2\)", nxt): break
        # stop at first gap back to numbered subsection
        m_of = re.search(r"(?i)(?:functions?|objects?|purposes?)\s+of\s+(?:the\s+)?([A-Za-z][\w -]*?)\s+(?:are|is|include|shall)\b", lead)
        lead_subj = re.search(r"(?i)\b(the|this|a|an|each)\s+((?:[A-Za-z-]+\s+){0,5}?[A-Za-z-]+?)(?:'s|’s)?\s+(?:has|have|is|are|may|must|shall|main|principal|primary|general|functions?|objects?)\b", lead)
        if m_of:
            subj_ok = sing(m_of.group(1).split()[-1]) in {sing(x) for x in short} or norm_t(m_of.group(1)) in {norm_t(x) for x in TITLE_VARIANTS}
        elif lead_subj:
            subj_ok = sing(lead_subj.group(2).split()[-1]) in {sing(x) for x in short} and lead_subj.group(1).lower() in ("the",)
        else:
            subj_ok = bool(re.search(r"^\s*(?:\(1\)\s*)?(?:Its|Without limiting)\b|^\s*(?:\(1\)\s*)?(?:The\s+)?(?:functions?|objects?)\s+(?:are|is)\b", lead, re.I))
        if items and subj_ok:
            kind = "objects" if re.search(r"objects?", lead, re.I) and not re.search(r"functions?", lead, re.I) else "functions"
            its = []
            for lab, txt in items:
                if not re.match(r"^[a-z]{1,2}$", lab) or lab in ("ii", "iii", "iv", "vi", "vii"): continue
                raw = txt.strip()
                if re.search(r"(—|–|:|-|\bof|\bbetween|\bto|\bthe|\bin)\s*$", raw): continue
                c = clean_item(txt)
                if not c or len(c) > 230 or len(c) < 25: continue
                if not re.match(r"^(to\s|[a-z]+ing\b|(?:if|where|when|subject to|in|on|with)\b[^,]{0,90},\s+to\s)", c): continue
                if re.search(r"\b(section|sections|Part|Division|Chapter|Schedule|subsection|paragraph)\s+\d", c): continue
                if re.search(r"\b(this Act|any other Act|the regulations|prescribed|conferred|imposed)\b", c) and len(its) >= 1: continue
                if re.search(r"conferred|imposed|prescribed by the regulations|under any other Act", c, re.I): continue
                its.append(c)
                if len(its) == 3: break
            if its:
                isto = lambda c: c.startswith("to ") or bool(re.match(r"^(?:if|where|when|subject to|in|on|with)\b[^,]{0,90},\s+to\s", c))
                style = "to" if isto(its[0]) else "ing"
                its = [c for c in its if (isto(c) if style == "to" else re.match(r"^[a-z]+ing\b", c) and not c.startswith("to "))]
            if its and style == "ing" and not re.match(r"^(promoting|providing|managing|developing|administering|advising|encouraging|conducting|undertaking|maintaining|regulating|ensuring|supporting|facilitating|establishing|operating|carrying|investigating|monitoring|planning|coordinating|co-ordinating|delivering|making|preparing|assisting|protecting|conserving|registering|collecting|holding|acquiring|fostering|implementing|reviewing|overseeing|representing|enforcing|educating|researching|disseminating|accrediting|licensing|determining|issuing|keeping|reporting)\b", its[0]): its = []
            if its:
                more = len([1 for lab, _ in items if re.match(r"^[a-z]$", lab)]) > len(its)
                return kind, its, more
    # prose form: "The function of the X is to ..."
    m = re.search(r"(?:\(1\)\s*)?((?:The|An?)\s+(?:principal\s+|main\s+)?(?:functions?|objects?|object|purpose|role)\s+of\s+(?:the\s+)?([A-Z][\w ]{2,60}?)\s+(?:is|are)\s+(?:to\s+)?[^\n]{10,400}?\.)", body)
    if m:
        sw = sig_words(m.group(2)) | {m.group(2).lower()}
        if sing(m.group(2).split()[-1]) in {sing(x) for x in short} and not re.search(r"\b(section|Part|Division|referred to)\s*\d*|conferred|imposed", m.group(1)):
            return "prose", [re.sub(r"\s+", " ", m.group(1)).strip()], False
    return None

def join_items(items):
    if len(items) == 1: return items[0]
    return "; ".join(items[:-1]) + "; and " + items[-1]

def describe(row, act, est):
    v, pos, verb = est
    title = row["Title"]
    text = act["text"]
    words = sig_words(title)
    # short names the Act uses for the body: title head noun, acronym in brackets after first mention
    short = set()
    tw = [w.lower() for w in re.findall(r"[A-Za-z]+", re.sub(r"\s*\([^)]*\)", "", title))]
    short.add(head_noun(title))
    near = text[pos: pos + 400]
    for m in re.finditer(r"\((?:the\s+|called\s+(?:the\s+)?|in this Act called\s+(?:the\s+)?)?[\"“']?([A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)[\"”']?\)", near):
        short.add(m.group(1).lower())
    for m in re.finditer(r"[\"“]([A-Z][A-Za-z]+)[\"”]\s+means\s+(?:the\s+)?" + re.escape(v.split()[0]), text, re.I):
        short.add(m.group(1).lower())
    TITLE_VARIANTS[:] = variants(title) + [title]
    secs = sections(text)
    cand = []
    for num, head, body, start in secs:
        fm = FUNC_H.match(head)
        if not fm: continue
        target = (fm.group(2) or "").strip()
        if target:
            tl = target.lower()
            tw2 = sig_words(target) | {re.sub(r"^the\s+", "", tl)}
            if re.match(r"(this\s+)?act\b|part\b|division\b", tl): continue
            if re.search(r"\b(in relation to|in respect of|relating to)\b", target): continue
            th = target_head(target)
            if norm_t(target) in {norm_t(x) for x in TITLE_VARIANTS}: th = next(iter(short))
            if th not in {sing(x) for x in short} and not (len(target.split()) >= 3 and sig_words(target) <= words): continue
            score = 3 if sig_words(target) & words else 2
        else:
            score = 1
        if fm.group(1).lower().startswith("function"): score += 1
        cand.append((score, num, head, body))
    cand.sort(key=lambda x: -x[0])
    for score, num, head, body in cand[:4]:
        r = extract_functions(body, words, short)
        if not r: continue
        kind, items, more = r
        GEN = {"trust", "board", "commission", "authority", "council", "corporation", "commissioner", "office", "tribunal", "court", "fund", "agency", "foundation", "institute", "committee", "service", "regulator", "registrar", "inspectorate", "department", "library", "museum", "centre", "panel", "directorate", "unit", "ombudsman", "company", "society", "assembly", "network", "secretary", "director", "trustee", "trustees"}
        bare = re.sub(r"\s*\([^)]*\)", "", title).strip()
        bw = bare.split()
        the = "The " if not re.match(r"^The\s", title) and any(w.lower() in GEN for w in bw) else ""
        name = re.sub(r"\s*\([^)]*\)$", "", title) if len(title) > 70 else title
        verbw = {"continued": "continued", "constituted": "constituted", "created": "established", "established": "established"}[verb]
        s1 = f"{the}{name} is {verbw} under the {act['title']} ({JAB[row['Jurisdiction']]})."
        if verbw == "continued": s1 = f"{the}{name} is continued in existence under the {act['title']} ({JAB[row['Jurisdiction']]})."
        d = None
        for n in (3, 2, 1):
            if kind == "prose":
                s2 = items[0][0].upper() + items[0][1:]
            else:
                its = items[:n]
                PERSON = {"commissioner", "director", "registrar", "secretary", "ombudsman", "inspector", "auditor", "trustee", "officer", "coordinator", "head", "advocate", "guardian", "custodian", "chief"}
                hn = head_noun(title)
                its_w = f"The {hn.capitalize()}'s" if hn in PERSON else "Its"
                lead = ("Its objects include" if kind == "objects" else "Its functions include") if (more or len(items) > n) else ("Its objects are" if kind == "objects" else "Its functions are")
                lead = lead.replace("Its", its_w, 1)
                s2 = f"{lead}: {join_items(its)}."
            d = (s1 + " " + s2).replace("..", ".")
            if len(d) <= 560: break
        if len(d) > 640: continue
        return {"Description": d, "section": num, "heading": head}
    return None

NOACT = []
def main():
    acts = json.loads((L / "acts.json").read_text())
    byj = defaultdict(list)
    for a in acts:
        a["low"] = re.sub(r"\s+", " ", a["text"].lower())
        byj[a["jur"]].append(a)
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    only = set(sys.argv[1:])
    res = {}; stats = Counter()
    for r in rows:
        if r["Description"].strip() and r["Description method"] != "wikidata": continue
        if r["Jurisdiction"] == "Commonwealth": continue
        if only and r["Jurisdiction"] not in only: continue
        if COMPANY.search(r["Title"]) or COMPANY.search(r["Established by/Under More Info"]) and "Act" not in r["Established by/Under More Info"].replace("Corporations Act", ""): stats["company"] += 1; continue
        vs = variants(r["Title"])
        if not vs: stats["short title"] += 1; continue
        pool = byj.get(r["Jurisdiction"], [])
        # preferred Acts: those named in More Info
        named = [a for a in pool if a["title"] and a["title"].lower() in r["Established by/Under More Info"].lower()]
        hits = []
        for a in named + [a for a in pool if a not in named]:
            if not any(v.lower() in a["low"] for v in vs): continue
            est = find_est(a["text"], vs)
            if not est: continue
            score = (a in named) * 5 + (len(sig_words(a["title"]) & sig_words(r["Title"])) >= max(1, len(sig_words(r["Title"])) - 1)) * 3 - ("Amendment" in a["title"] or "Repeal" in a["title"]) * 4
            hits.append((score, a, est))
        if not hits: stats["no act"] += 1; NOACT.append((r["Jurisdiction"], r["Title"], r["Source name"][:40])); continue
        hits.sort(key=lambda x: -x[0])
        if hits[0][0] < 0: stats["only amending acts"] += 1; continue
        a, est = hits[0][1], hits[0][2]
        sec, sec_head = section_of(a["text"], est[1])
        if not re.search(r"establish|constitut|continu|incorporat|creat|corporation|body corporate|\b" + re.escape(head_noun(r["Title"])) + r"\b", sec_head, re.I): sec = ""
        out = {"title": r["Title"], "jur": r["Jurisdiction"], "act": a["title"], "url": a["url"], "est_section": sec, "verb": est[2],
               "had_wikidata": r["Description method"] == "wikidata"}
        out["act_title_overlap"] = bool(sig_words(a["title"]) & sig_words(r["Title"]))
        dd = describe(r, a, est)
        if dd: out.update(dd); stats["described"] += 1
        else: stats["act only"] += 1
        res[r["Jurisdiction"] + "|" + r["Title"]] = out
    (L / "leg_matches.json").write_text(json.dumps(res, indent=1))
    print(stats)
    json.dump(NOACT, open(L / "noact.json", "w"), indent=0)

if __name__ == "__main__":
    main()
