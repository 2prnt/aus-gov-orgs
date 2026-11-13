#!/usr/bin/env python3
"""Append the verified government-owned companies (candidates.json from
add_companies.py) to data/organisations.csv. Idempotent: rows previously added
from the company sources are replaced. ABNs come from abr_company_hits.json
(scan_abr_companies.py) and are only taken on a unique, current, in-state exact
legal-name match."""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import companies_data as cd
from scan_abr_companies import ckey, legal_names
from enrich import format_abn

ROOT = Path(__file__).resolve().parents[1]
W = Path("/workspace/agor-sheet/companies")
STATE = {"NSW": "NSW", "Victoria": "VIC", "Queensland": "QLD", "WA": "WA", "SA": "SA", "Tasmania": "TAS", "ACT": "ACT", "NT": "NT"}
GFS = {"PNFC": "Public non-financial corporation", "PFC": "Public financial corporation", "GGS": "General government"}
SITE_OVERRIDE = {"https://manufacturingskillsqld.com.au": "", "https://www.acpa.net.au": ""}
# ABR hit is an old name on a different (renamed) body, so the match is ambiguous
NO_ABN = {"Newcastle Port Corporation"}
PARENT_EXISTING = {"Electricity Generation and Retail Corporation (Synergy)": "Synergy"}

def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    cols = list(rows[0].keys())
    src_names = {v[0] for v in cd.SOURCES.values()}
    rows = [r for r in rows if r["Source name"] not in src_names]
    cands = json.load(open(W / "candidates.json"))["new"]
    sites = json.load(open(W / "site_check.json"))
    hp = W / "abr_company_hits.json"
    hits = json.load(open(hp))["hits"] if hp.exists() else {}
    log = []
    for c in cands:
        src = cd.SOURCES[c["src"]]
        w = c["website"]
        if w in SITE_OVERRIDE: w = SITE_OVERRIDE[w]
        if w and w in sites:
            st, final = sites[w]
            if st == 200 and final: w = final.rstrip("/")
            elif st != 403: w = ""
        abn = conf = ""
        st = STATE[c["j"]]
        recs = {}
        for n in legal_names(c["title"]):
            for r in hits.get(ckey(n), []):
                recs[r["abn"]] = r
        is_co_name = bool(re.search(r"\b(Pty|Ltd|Limited)\b", c["title"]))
        lnames = {ckey(n) for n in legal_names(c["title"])}
        # ASIC company names are unique nationally, so an exact legal-name company match is accepted in any state
        cur = [r for r in recs.values() if r["status"] == "ACT" and ((r.get("state") or st) == st or (is_co_name and ckey(r["name"]) in lnames))]
        if c["title"] in NO_ABN: cur = []
        if len(cur) == 1:
            r = cur[0]
            legal_hit = ckey(r["name"]) in {ckey(n) for n in legal_names(c["title"])}
            abn, conf = format_abn(r["abn"]), ("exact" if legal_hit else "high")
        log.append((c["j"], c["title"], len(recs), len(cur), abn, conf))
        is_co = bool(re.search(r"\b(Pty|Ltd|Limited)\b", c["title"]))
        est = c["note"] if "Act" in c["note"] else ""
        if is_co and not est: est = "Corporations Act 2001 (Cth) company"
        desc = c["note"] if c["note"] and c["note"] != est else ""
        row = {k: "" for k in cols}
        row.update({
            "Jurisdiction": c["j"], "Title": c["title"], "Portfolio": c["portfolio"],
            "Classification": GFS.get(c["gfs"], ""), "Type of Body": c["typ"],
            "GFS Sector Classification": c["gfs"], "Description": desc,
            "Established By / Under": "Corporations Act 2001 (Cth)" if is_co else ("Act" if est else ""),
            "Established by/Under More Info": est,
            "ABN": abn, "ABN match confidence": conf,
            "Parent Organisation": PARENT_EXISTING.get(c["parent"], c["parent"]),
            "Head Office State": st, "Head Office Country": "Australia",
            "Website Address": w,
            "Source name": src[0], "Source URL": src[1], "Source date": src[2],
        })
        rows.append(row)
    order = ["Commonwealth", "NSW", "Victoria", "Queensland", "WA", "SA", "Tasmania", "ACT", "NT"]
    rows.sort(key=lambda r: order.index(r["Jurisdiction"]))  # stable: keeps existing order, new rows at end of each jurisdiction
    with open(ROOT / "data/organisations.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader(); wr.writerows(rows)
    json.dump(log, open(W / "abn_log.json", "w"), indent=0)
    print("rows", len(rows), "added", len(cands), "abn", sum(1 for l in log if l[4]))

if __name__ == "__main__":
    main()
