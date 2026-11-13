#!/usr/bin/env python3
"""Second description pass (November 2026): enabling legislation and annual reports.

Inputs (built by scripts/descriptions/leg_index.py, leg_match.py, ar_fetch.py):
  /workspace/agor-sheet/leg/leg_matches.json  Act that establishes each body + its functions/objects section
  /workspace/agor-sheet/leg/cache_ar.json     annual report page / PDF found on the body's official website

Only blank cells are filled, except that a Wikidata one-liner (< 120 characters) is replaced by a
legislation description. Description method 'legislation' or 'annual-report'; source URL recorded."""
import csv, json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parent / "descriptions"))
from ar_desc import pick
from leg_match import variants, sig_words

def overlap_ok(title, act):
    t = re.sub(r"\s*\([^)]*\)", "", title)
    return any(v.lower() in act.lower() for v in variants(t)) or len(sig_words(t) & sig_words(act)) >= 2
ROOT = Path(__file__).resolve().parents[1]
L = Path("/workspace/agor-sheet/leg")
JAB = {"NSW": "NSW", "Victoria": "Vic", "Queensland": "Qld", "WA": "WA", "SA": "SA", "Tasmania": "Tas", "ACT": "ACT", "NT": "NT"}

def add_src(r, s):
    cur = r.get("Other fields source", "")
    if s not in cur: r["Other fields source"] = (cur + "; " if cur else "") + s

def main():
    path = ROOT / "data/organisations.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    cols = list(rows[0].keys())
    bp = ROOT / "data/fill_before_pass2.json"
    if not bp.exists():
        bp.write_text(json.dumps({"before": {c: sum(1 for r in rows if (r.get(c) or "").strip()) for c in cols},
                                  "desc_by_jur": dict(Counter(r["Jurisdiction"] for r in rows if r["Description"].strip()))}, indent=1))
    lm = json.loads((L / "leg_matches.json").read_text())
    ar = json.loads((L / "cache_ar.json").read_text())
    st = Counter()
    for r in rows:
        k = r["Jurisdiction"] + "|" + r["Title"]
        m = lm.get(k)
        blank = not r["Description"].strip()
        thin_wd = r["Description method"] == "wikidata" and len(r["Description"]) < 120
        if m:
            ov = overlap_ok(r["Title"], m["act"])
            reliable = "Description" in m or ov
            if "Description" in m and (blank or thin_wd):
                r["Description"] = m["Description"]; r["Description method"] = "legislation"; r["Description source URL"] = m["url"]
                st["desc legislation " + ("upgrade wikidata" if thin_wd else "new")] += 1
                st["new:" + r["Jurisdiction"] + ":legislation"] += 1 if blank else 0
                blank = False
            elif blank and ov:
                name = r["Title"]
                verb = {"continued": "is continued in existence", "constituted": "is constituted"}.get(m["verb"], "is established")
                the = "The " if re.search(r"\b(Trust|Board|Commission|Authority|Council|Corporation|Commissioner|Office|Tribunal|Court|Fund|Agency|Foundation|Institute|Committee|Service|Regulator|Registrar|Inspectorate|Department|Library|Museum|Centre|Panel|Ombudsman|Assembly|Network)\b", name) and not name.startswith("The ") else ""
                sec = f" (section {m['est_section']})" if m.get("est_section") else ""
                r["Description"] = f"{the}{name} {verb} under the {m['act']} ({JAB[r['Jurisdiction']]}){sec}."
                r["Description method"] = "legislation"; r["Description source URL"] = m["url"]
                st["desc legislation establishment-only"] += 1; st["new:" + r["Jurisdiction"] + ":legislation"] += 1
                blank = False
            if reliable:
                if not r["Established By / Under"].strip():
                    r["Established By / Under"] = "Act / Regulation"; st["established by"] += 1
                    add_src(r, "Established By / Under: " + m["url"])
                if not r["Established by/Under More Info"].strip():
                    r["Established by/Under More Info"] = (f"Section {m['est_section']} " if m.get("est_section") else "") + m["act"]
                    st["established more info"] += 1
                    add_src(r, "Established by/Under More Info: " + m["url"])
        c = ar.get(k)
        if c and r["Jurisdiction"] != "Commonwealth":
            o = pick(r, c)
            if o.get("Annual Reports") and not r["Annual Reports"].strip():
                r["Annual Reports"] = o["Annual Reports"]; st["annual report link"] += 1
                add_src(r, "Annual Reports: official website")
            if o.get("Description") and blank:
                r["Description"] = o["Description"]; r["Description method"] = "annual-report"; r["Description source URL"] = o["Description source URL"]
                st["desc annual-report new"] += 1; st["new:" + r["Jurisdiction"] + ":annual-report"] += 1
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    for j in sorted({r["Jurisdiction"] for r in rows}):
        with open(ROOT / f"data/by-jurisdiction/{j.lower().replace(' ', '-')}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows([r for r in rows if r["Jurisdiction"] == j])
    (L / "pass2_stats.json").write_text(json.dumps(st, indent=1))
    print(json.dumps(st, indent=1))

if __name__ == "__main__":
    main()
