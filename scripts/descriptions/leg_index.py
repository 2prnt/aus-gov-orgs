#!/usr/bin/env python3
"""Build one index of in-force Acts per jurisdiction from:
  leg.jsonl   - primary legislation rows of the Open Australian Legal Corpus (isaacus, HF), which are
                copies of the official NSW/Qld/WA/SA/Tas legislation sites (official URLs kept)
  vic.jsonl   - legislation.vic.gov.au in-force Acts (latest version DOCX), fetched by vic.py
  actnt.jsonl - legislation.act.gov.au current Acts (DOCX) and legislation.nt.gov.au Acts (Word/PDF), fetched by actnt.py
Writes acts.json: [{jur, title, url, text, date}]"""
import json, re, subprocess, tempfile
from pathlib import Path
L = Path("/workspace/agor-sheet/leg")
JM = {"new_south_wales": "NSW", "queensland": "Queensland", "western_australia": "WA", "south_australia": "SA", "tasmania": "Tasmania"}
def rtf_text(s):
    with tempfile.NamedTemporaryFile("w", suffix=".rtf", delete=False) as f: f.write(s)
    return s
def unlayout(t):
    """Re-join pdftotext -layout output into one logical line per heading / subsection / list item."""
    out = []
    for line in t.replace("\f", "\n").split("\n"):
        st = line.strip()
        if not st: out.append(""); continue
        if re.fullmatch(r"\d+|[ivxlc]+|Page \d+.*", st): continue
        st = re.sub(r"\s{2,}", " ", st)
        if not out or out[-1] == "" or re.match(r"^(\(\w{1,4}\)|\d+[A-Z]{0,3}\s+[A-Z]|Part\s+\d|Division\s+\d|Schedule\s+\d)", st):
            out.append(st)
        else:
            out[-1] += " " + st
    return "\n".join(out)

acts = []
for l in open(L / "leg.jsonl"):
    d = json.loads(l)
    t = re.sub(r"\s*\((NSW|Qld|WA|SA|Tas)\)$", "", d["citation"]).strip()
    if "(Repealed)" in t or "Repeal" in t.split(" Act")[0][-10:]: continue
    u = re.sub(r"/inforce/\d{4}-\d{2}-\d{2}/", "/inforce/current/", d["url"])
    acts.append({"jur": JM[d["jurisdiction"]], "title": t, "url": u, "text": d["text"], "date": d["date"]})
for l in open(L / "vic.jsonl"):
    d = json.loads(l)
    if not d.get("text"): continue
    if d.get("layout"): d["text"] = unlayout(d["text"])
    slug = d["url"].rsplit("/", 1)[1]
    t = re.sub(r"-", " ", slug)
    # take the title from the DOCX: first line ending 'Act YYYY' matching the slug words
    yr = re.search(r"\d{4}$", t)
    for line in d["text"].split("\n")[:80]:
        line = line.replace("\xa0", " ").strip()
        if re.fullmatch(r"[A-Z][^\t]{3,150}\bAct \d{4}", line) and (not yr or line.endswith(yr.group(0))): t = line; break
    else: t = " ".join(w if w in {"and", "of", "the", "for", "to", "in", "on", "by"} and i else w.capitalize() for i, w in enumerate(t.split()))
    d["text"] = re.sub(r"(?m)^(?:S\.|Ss\.|Pt|Div|Sch\.?|Note)\s*[\d\w().\xa0 ,-]*?(?:amended|inserted|substituted|repealed|renumbered|re-numbered)\b[^\n]*\n", "", d["text"])
    acts.append({"jur": "Victoria", "title": t, "url": d["url"], "text": d["text"], "date": d.get("version_url", "")[-3:]})
for l in open(L / "actnt.jsonl"):
    d = json.loads(l)
    if not d.get("text"): continue
    if d.get("layout"): d["text"] = unlayout(d["text"])
    t = re.sub(r"\s*\|.*$", "", d.get("title", "")).strip()
    if d["jur"] == "NT": t = t.title().replace(" And ", " and ").replace(" Of ", " of ").replace(" The ", " the ").replace(" For ", " for ")
    if d["jur"] == "ACT" and not re.search(r"\d{4}$", t):
        m = re.search(re.escape(t) + r"\s+(\d{4})", d["text"][:4000])
        if m: t = f"{t} {m.group(1)}"
    acts.append({"jur": "NT" if d["jur"] == "NT" else "ACT", "title": t, "url": d["url"], "text": d["text"], "date": ""})
for a in acts: a["title"] = re.sub(r"\s+", " ", a["title"].replace("\xa0", " ")).strip()
(L / "acts.json").write_text(json.dumps(acts))
from collections import Counter
print(len(acts), Counter(a["jur"] for a in acts))
