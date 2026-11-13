#!/usr/bin/env python3
"""Build candidate rows for state/territory government-owned companies and
subsidiaries (scripts/companies_data.py + QAO parse), dedupe against
data/organisations.csv, and write /workspace/agor-sheet/companies/candidates.json.
"""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from enrich import norm_name, name_variants  # noqa
import companies_data as cd

ROOT = Path(__file__).resolve().parents[1]
QAO = Path("/workspace/agor-sheet/companies/qao_raw.json")
OUT = Path("/workspace/agor-sheet/companies/candidates.json")

SUFFIX = re.compile(r"\s+(PTY\.?\s+)?(LTD|LIMITED)$|\s+PTY$")
PAREN = re.compile(r"\s*\(([^)]*)\)")

def keys(name: str, strip: bool = True) -> set[str]:
    out = set()
    alias = [a for a in PAREN.findall(name)] if strip else []
    bare = PAREN.sub("", name) if strip else name
    for n in [name, bare] + [re.sub(r"^(trading as|t/as)\s+", "", a, flags=re.I) for a in alias]:
        for v in name_variants(n):
            out.add(v)
            s = SUFFIX.sub("", v).strip()
            if len(s) >= 4:
                out.add(s)
    return {k for k in out if len(k) >= 4}

QAO_SKIP = re.compile(r"\b(Trust|Fund|Project$|as trustee|Segregated Cell|PCC|LLC|S\.á\.r\.l|Inc$)\b", re.I)
QAO_EXCLUDE = {"Queensland Titles Registry Pty Ltd", "Registry Finance Pty Ltd", "South Bank Corporation",
               "Queensland Theatre Company", "Queensland Treasury Corporation"}
QIC = "QIC Limited"
PARENT_MAP = {"Stanwell": "Stanwell Corporation Limited", "Powerlink": "Queensland Electricity Transmission Corporation Limited (trading as Powerlink Queensland)",
              "North Queensland Bulk Ports Limited": "North Queensland Bulk Ports Corporation Limited",
              "Queensland Rail": "Queensland Rail", "The Council of the Queensland Institute of Medical Research": "The Council of the Queensland Institute of Medical Research"}
GOCS = {t for t, _ in cd.QGOC}

def qld_rows():
    rows = []
    for x in json.load(open(QAO)):
        n = re.sub(r"\*+$", "", x["name"]).strip()
        n = re.sub(r"\s+31\.08\.2025", "", n)
        if n == "Ergon Energy Queensland":
            n = "Ergon Energy Queensland Pty Ltd"
        if not re.search(r"\b(Pty|Ltd|Limited|Co\.)\b", n) or QAO_SKIP.search(n) or n in QAO_EXCLUDE:
            continue
        if x["foot"] == "3":
            continue
        if n.startswith("Queensland Electricity Transmission") or n in GOCS or n.startswith("QIC Limited"):
            continue
        parent = x["parent"]
        line = x["line"]
        if x["app"] == "I" and 4753 <= line <= 4906:
            parent = QIC  # 'Entities managed by QIC Limited' block (parser mislabelled as Stanwell)
        if n == "Queensland Trade and Investment Office Pty Ltd":
            parent = "Trade and Investment Queensland"
        parent = PARENT_MAP.get(parent, parent)
        if n == "Queensland Rail Limited":
            typ = "Government-controlled company"
        elif parent in GOCS or parent == QIC or parent.startswith("Queensland Electricity Transmission"):
            typ = "Subsidiary of a government owned corporation"
        elif parent:
            typ = "Controlled company"
        else:
            typ = "Government-controlled company"
        if parent == QIC and x["app"] == "I":
            typ = "Company managed and controlled by QIC Limited"
        gfs = "PFC" if parent == QIC else ""
        rows.append(dict(j="Queensland", title=n, typ=typ, parent=parent, portfolio="", gfs=gfs,
                         website=cd.QSITES.get(n, ""), src="QLD_QAO", note=""))
    return rows

# Same body already in the dataset under a different form of the name (checked by hand)
MANUAL_DUP = {("WA", "Busselton Water Corporation"): "Busselton Water", ("WA", "Fremantle Port Authority"): "Fremantle Ports",
    ("WA", "Mid West Ports Authority"): "Mid West Ports", ("WA", "Western Australian Land Authority (DevelopmentWA)"): "Development WA",
    ("WA", "Lotteries Commission (Lotterywest)"): "Lotterywest/Healthway", ("WA", "Keystart Loans Limited"): "Keystart",
    ("Victoria", "Phillip Island Nature Parks"): "Phillip Island Nature Park Board of Management",
    ("Victoria", "Remembrance Parks Central Victoria"): "Remembrance Park Central Victoria",
    ("Victoria", "Victorian Rail Track"): "Victorian Rail Track Corporation", ("Victoria", "Dockland Studios Melbourne Pty Ltd"): "Docklands Studios Melbourne",
    ("Victoria", "VITS Language Loop"): "VITS LanguageLoop", ("NSW", "Jenolan Caves Reserves Trust"): "Jenolan Caves Reserve Trust",
    ("NSW", "WaterNSW"): "Water NSW", ("NSW", "Generator Property Management Pty Ltd"): "Generator Property Management Corporation"}

def main():
    added_src = {v[0] for v in cd.SOURCES.values()}
    existing = [r for r in csv.DictReader(open(ROOT / "data/organisations.csv")) if r["Source name"] not in added_src]
    exkeys: dict[tuple, str] = {}
    for r in existing:
        for k in keys(r["Title"]):
            exkeys.setdefault((r["Jurisdiction"], k), r["Title"])
    cands = cd.E + qld_rows()
    seen: dict[tuple, str] = {}
    new, dups = [], []
    for c in cands:
        ks = keys(c["title"])
        hit = MANUAL_DUP.get((c["j"], c["title"])) or next((exkeys[(c["j"], k)] for k in ks if (c["j"], k) in exkeys), None)
        ks = keys(c["title"], strip=False)
        if hit:
            dups.append((c["j"], c["title"], hit)); continue
        if any((c["j"], k) in seen for k in ks):
            dups.append((c["j"], c["title"], "(duplicate candidate)")); continue
        for k in ks:
            seen[(c["j"], k)] = c["title"]
        new.append(c)
    json.dump({"new": new, "dups": dups}, open(OUT, "w"), indent=1, ensure_ascii=False)
    from collections import Counter
    print("candidates", len(cands), "new", len(new), "dups", len(dups))
    print(Counter(c["j"] for c in new))
    for d in dups:
        print("DUP", d)

if __name__ == "__main__":
    main()
