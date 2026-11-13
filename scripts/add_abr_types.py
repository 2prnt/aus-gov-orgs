#!/usr/bin/env python3
"""Add government entities registered on the ABR with a Commonwealth, State or
Territory government entity type (CG*, SG*, TG*; local government LG* is out of
scope) that are not already in data/organisations.csv.

Rules (in order; counts are written to abr_types_report.json):
 1. ABN status must be ACT (active).
 2. Name-pattern exclusions from abr_types_classify.RULES (schools, Crown-land
    reserve committees, Defence messes/units/funds, clubs, funds/accounts/
    payroll/divisions, emergency-service brigades/units, historical inquiries...).
 3. Dormant: ABR record not updated since DORMANT_BEFORE and no active GST
    registration (scan_abr_dates.py).
 4. Already present: ABN equal to an existing row's ABN (any jurisdiction).
 5. Already present: normalised name (legal or ABR other name) equal to an
    existing title in the same jurisdiction, or a near-duplicate (one name's
    significant words contained in the other's, at least two words).
 6. Sub-registration: 'X - Y' / 'X (Y)' where X is an existing body.
 7. Duplicate within the ABR set (same normalised name and jurisdiction): keep
    the most recently updated record.
"""
from __future__ import annotations
import csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from abr_types_classify import load, classify, jurisdiction
from add_companies import keys
from enrich import format_abn

ROOT = Path(__file__).resolve().parents[1]
DATES = Path("/workspace/agor-sheet/abr/abr_gov_dates.json")
REPORT = Path("/workspace/agor-sheet/abrtypes/abr_types_report.json")
SOURCE = ("ABR ABN Bulk Extract (11 November 2026) – government entity types",
          "https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e", "11 November 2026")
DORMANT_BEFORE = "20100101"
# Bodies abolished, renamed or merged whose ABNs are still active (checked by hand)
KNOWN_DEFUNCT = [r"^WORKPLACE AUTHORITY$", r"^NATIONAL WATER COMMISSION$", r"^HEALTH WORKFORCE AUSTRALIA$", r"^NATIONAL HEALTH PERFORMANCE AUTHORITY$",
    r"ROADS & TRAFFIC AUTHORITY", r"ROADS AND TRAFFIC AUTHORITY", r"^STATE RAIL AUTHORITY", r"^TAFE NSW ?- ?", r"RURAL LANDS PROTECTION BOARD",
    r"^MARITIME AUTHORITY OF NSW", r"^NSW COMMISSION FOR CHILDREN AND YOUNG PEOPLE$", r"^OFFICE OF POLICE INTEGRITY$", r"^MERIT PROTECTION BOARDS$",
    r"^GROWTH AREAS AUTHORITY$", r"^DEPARTMENT OF FAMILY AND COMMUNITY SERVICES", r"^DEPARTMENT OF CLIMATE CHANGE AND ENERGY EFFICIENCY$",
    r"^DEPARTMENT OF NATURAL RESOURCES$", r"^DEPARTMENT OF JUSTICE$", r"^RESILIENCE NSW$", r"^SYDNEY PORTS CORPORATION$", r"^PORT KEMBLA PORT CORPORATION$",
    r"^PUBLIC TRANSPORT DEVELOPMENT AUTHORITY$", r"^QUEENSLAND FLOODS COMMISSION", r"^DEPARTMENT OF ENVIRONMENT AND RESOURCE MANAGEMENT",
    r"^DEPARTMENT OF EMPLOYMENT AND INDUSTRIAL RELATIONS$", r"^COMMISSION FOR CHILDREN AND YOUNG PEOPLE AND CHILD GUARDIAN$", r"^HERITAGE OFFICE$",
    r"^METROPOLITAN REDEVELOPMENT AUTHORITY$", r"WASTE AND RESOURCE RECOVERY GROUP$", r"ALPINE RESORT MANAGEMENT BOARD$", r"^MT BAW BAW ALPINE RESORT$",
    r"^SOUTH EAST QUEENSLAND WATER GRID MANAGER$", r"^QUEENSLAND BULK WATER TRANSPORT AUTHORITY$", r"^QUEENSLAND MANUFACTURED WATER AUTHORITY$",
    r"^GIPPSLAND INSTITUTE OF TECHNICAL", r"^OFFICE OF THE COMMISSIONER FOR PUBLIC EMPLOYMENT$", r"^DEPARTMENT OF DEFENCE ARMY$", r"^DEPT\. OF HOME AFFAIRS$",
    r"^AUSTRALIAN GOVERNMENT INFORMATION MANAGEMENT OFFICE$", r"^VICTORIAN PORTS CORPORATION", r"^NATURAL GAS AUTHORITY OF SOUTH AUSTRALIA$",
    r"^SOUTH SYDNEY DEVELOPMENT CORPORATION$", r"^NATIONAL OCCUPATIONAL LICENSING", r"^WORKERS COMPENSATION COMMISSION$",
    r"^QUEENSLAND AGRICULTURAL TRAINING COLLEGES$", r"^QUEENSLAND OPEN LEARNING NETWORK$", r"^SKILLS QUEENSLAND$", r"^VOCATIONAL TRAINING QUEENSLAND$",
    r"^QUEENSLAND RACING DIRECTORATE$", r"^RACING QUEENSLAND BOARD$", r"^FORESTRY PLANTATIONS QUEENSLAND OFFICE$", r"^DARLING DOWNS-MORETON RABBIT BOARD$",
    r"^CENTENARY OF FEDERATION VICTORIA$", r"^COVID-19 QUARANTINE VICTORIA$", r"^QUEENSLAND NURSING COUNCIL$", r"^BRISBANE FOREST PARK ADMINISTRATION AUTHORITY$",
    r"^TASMANIA DEVELOPMENT AND RESOURCES$", r"^TRANSPORT SA$", r"^ARTS SA$", r"^HEALTH PURCHASING VICTORIA$", r"^BUILDING PROFESSIONALS BOARD$",
    r"^ABORIGINAL AFFAIRS PLANNING AUTHORITY$", r"^DEPARTMENT OF THE STATE HERITAGE OFFICE$"]
# Same body as an existing row under another name (checked by hand)
MANUAL_DUP = {"WESTERN AUSTRALIAN LAND AUTHORITY": "Development WA", "WESTERN AUSTRALIAN MINT": "The Perth Mint", "GOLDCORP AUSTRALIA": "The Perth Mint",
    "LOTTERIES COMMISSION": "Lotterywest/Healthway", "WESTERN AUSTRALIAN HEALTH PROMOTION FOUNDATION": "Lotterywest/Healthway"}

STATE_WORDS = [("Queensland", r"\b(QUEENSLAND|QLD)\b"), ("NSW", r"\b(NEW SOUTH WALES|NSW)\b"), ("Victoria", r"\b(VICTORIA|VICTORIAN)\b"),
               ("WA", r"\bWESTERN AUSTRALIA(N)?\b"), ("SA", r"\bSOUTH AUSTRALIA(N)?\b"), ("Tasmania", r"\b(TASMANIA|TASMANIAN)\b"),
               ("NT", r"\bNORTHERN TERRITORY\b"), ("ACT", r"\bAUSTRALIAN CAPITAL TERRITORY\b")]
STOP = {"OF", "THE", "AND", "FOR", "INC", "INCORPORATED", "LTD", "LIMITED", "PTY", "NSW", "NEW", "SOUTH", "WALES", "VICTORIA", "VICTORIAN",
        "QUEENSLAND", "QLD", "WESTERN", "AUSTRALIA", "AUSTRALIAN", "WA", "SA", "TASMANIA", "TASMANIAN", "NORTHERN", "TERRITORY", "NT",
        "ACT", "CAPITAL", "STATE", "GOVERNMENT", "OFFICE", "DEPARTMENT", "BOARD", "AUTHORITY", "COMMISSION", "COUNCIL", "CORPORATION",
        "SERVICE", "SERVICES", "AGENCY", "TRUST", "COMMITTEE", "IN", "TO", "ON", "A"}
ACRONYMS = {"NSW", "ACT", "NT", "SA", "WA", "QLD", "TAFE", "ACFE", "ABC", "CSIRO", "ADF", "RAAF", "SES", "CFA", "CFS", "AHPRA", "TGA", "NHVR",
            "TIO", "VCAT", "NCAT", "QBCC", "PFAS", "ICT", "IT", "II", "III", "IV", "RSL", "CBD", "UNSW", "CSI", "QFLEET", "CITEC", "SA", "NCN", "CMTEDD", "HCSD", "CED", "LPI", "RAAOC", "ACT", "TEGS", "CSC", "NHVR", "SAFA", "QIMR", "STAR", "VITS", "ICAC", "OPI"}
SMALL = {"of", "the", "and", "for", "in", "on", "at", "to", "a", "an", "by", "with", "&"}

def tokens(s: str) -> set[str]:
    t = re.sub(r"[^A-Z0-9 ]", " ", s.upper().replace("&", " AND ")).split()
    out = set()
    for w in t:
        if w in STOP: continue
        w = {"TRUSTEE": "TRUST", "TRUSTEES": "TRUST"}.get(w, w)
        if len(w) > 4 and w.endswith("S") and not w.endswith("SS"): w = w[:-1]
        out.add(w)
    return out

def nice(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    letters = [c for c in name if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return name  # already mixed case
    words = []
    for i, w in enumerate(name.split(" ")):
        core = re.sub(r"[^A-Za-z]", "", w).upper()
        if core in ACRONYMS: words.append(w.upper()); continue
        lw = w.lower()
        if i and lw in SMALL: words.append(lw); continue
        words.append("-".join(p[:1].upper() + p[1:] for p in lw.split("-")))
    s = " ".join(words)
    s = re.sub(r"'S\b", "'s", s)
    s = re.sub(r"(\w)\(", r"\1 (", s); s = re.sub(r"\)(\w)", r") \1", s)
    return re.sub(r"\(([a-z])", lambda m: "(" + m.group(1).upper(), s)

def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    cols = list(rows[0].keys())
    rows = [r for r in rows if r["Source name"] != SOURCE[0]]  # idempotent
    abns = {re.sub(r"\D", "", r["ABN"]) for r in rows if r["ABN"]}
    exk, extok = {}, defaultdict(list)
    for r in rows:
        t = r["Title"]
        # inverted titles such as "Education, Department for" (SA Budget Appendix D)
        m = re.match(r"^(.+?),\s*((Department|Office|Commissioner|Minister|Board|Commission|Agency|Authority)\b.*)$", t)
        for tt in [t] + ([m.group(2) + " " + m.group(1)] if m else []):
            for k in keys(tt): exk.setdefault((r["Jurisdiction"], k), t)
        for nm in [r["Title"]] + re.findall(r"\(([^)]*)\)", r["Title"]):
            tk = tokens(re.sub(r"\([^)]*\)", "", nm) if nm == r["Title"] else nm)
            if len(tk) >= 2: extok[r["Jurisdiction"]].append((tk, r["Title"]))
    dates = json.loads(DATES.read_text()) if DATES.exists() else {}
    cnt, ex_samples = Counter(), defaultdict(list)
    def drop(rule, rec):
        cnt[rule] += 1
        if len(ex_samples[rule]) < 15: ex_samples[rule].append(rec["name"])
    cands = []
    for rec in load():
        if rec["status"] != "ACT": cnt["cancelled ABN"] += 1; continue
        cat = classify(rec)
        if cat: drop(cat, rec); continue
        d = dates.get(rec["abn"], {})
        if d.get("gst") == "CAN":
            drop("historical/dormant: GST registration cancelled", rec); continue
        if d and d.get("updated", "99999999") < DORMANT_BEFORE and d.get("gst") != "ACT":
            drop(f"dormant: ABR record not updated since before {DORMANT_BEFORE[:4]} and never GST-registered", rec); continue
        if any(re.search(p, rec["name"].upper()) for p in KNOWN_DEFUNCT):
            drop("known abolished/merged body (manual list)", rec); continue
        if rec["abn"] in abns: drop("already present (same ABN)", rec); continue
        if rec["name"].upper().strip() in MANUAL_DUP: drop("near-duplicate of an existing body", rec); continue
        j = jurisdiction(rec)
        U = rec["name"].upper()
        named = [jj for jj, rx in STATE_WORDS if re.search(rx, U)]
        if len(named) == 1 and named[0] != j and not rec["type"].startswith("CG"):
            j = named[0]
        if not j: drop("jurisdiction unclear (type/state mismatch)", rec); continue
        names = [rec["name"]] + rec.get("other_names", [])
        if any((j, k) in exk for n in names for k in keys(n)): drop("already present (same normalised name)", rec); continue
        tk = tokens(rec["name"])
        near = None
        if len(tk) >= 2:
            for et, title in extok[j]:
                if tk <= et or et <= tk: near = title; break
        if near: drop("near-duplicate of an existing body", rec); continue
        m = re.match(r"^(.+?)\s*(?:-|–)\s*.+$|^(.+?)\s*\(.+\)$", rec["name"])
        if m:
            head = (m.group(1) or m.group(2)).strip()
            if any((j, k) in exk for k in keys(head)) or re.match(r"^(DEPARTMENT|DEPT|NSW HEALTH SERVICE|HCSD|CED|CMTEDD|SA HEALTH)\b", head.upper()):
                drop("sub-registration of an existing body ('X - Y')", rec); continue
        cands.append((j, rec, d))
    # within-set dedupe
    best = {}
    for j, rec, d in cands:
        key = (j, min(keys(rec["name"]) or {rec["name"].upper()}, key=len), frozenset(tokens(rec["name"])))
        key = (j, frozenset(tokens(rec["name"])) or rec["name"].upper())
        if key in best:
            cnt["duplicate within ABR set"] += 1
            if (d.get("updated") or "") > (best[key][2].get("updated") or ""): best[key] = (j, rec, d)
        else:
            best[key] = (j, rec, d)
    added = []
    for j, rec, d in best.values():
        row = {k: "" for k in cols}
        upd = d.get("updated", "")
        row.update({"Jurisdiction": j, "Title": nice(rec["name"]), "Classification": rec["type_text"],
                    "ABN": format_abn(rec["abn"]), "ABN match confidence": "exact",
                    "Head Office State": rec.get("state", ""), "Head Office Postcode": rec.get("postcode", ""),
                    "Head Office Country": "Australia" if rec.get("state") else "",
                    "Description": "Added from the ABR government entity types (" + rec["type"] + "); ABR record last updated "
                                   + (f"{upd[6:8]}/{upd[4:6]}/{upd[:4]}" if upd else "unknown")
                                   + ("; GST registered" if d.get("gst") == "ACT" else "")
                                   + ". Current status not confirmed by an official agency list.",
                    "Source name": SOURCE[0], "Source URL": SOURCE[1], "Source date": SOURCE[2]})
        added.append(row)
    order = ["Commonwealth", "NSW", "Victoria", "Queensland", "WA", "SA", "Tasmania", "ACT", "NT"]
    rows += added
    rows.sort(key=lambda r: order.index(r["Jurisdiction"]))
    with open(ROOT / "data/organisations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    rep = {"added": len(added), "by_jurisdiction": Counter(r["Jurisdiction"] for r in added),
           "by_type": Counter(r["Classification"] for r in added),
           "by_jurisdiction_type": Counter(f'{r["Jurisdiction"]} | {r["Classification"]}' for r in added),
           "excluded": cnt, "samples": ex_samples}
    REPORT.write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: rep[k] for k in ("added", "by_jurisdiction", "by_type", "excluded")}, indent=1))

if __name__ == "__main__":
    main()
