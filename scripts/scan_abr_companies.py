#!/usr/bin/env python3
"""Rescan the ABR bulk extract for exact legal-name matches of the candidate
companies (any entity type, incl. PRV/PUB), writing abr_company_hits.json."""
from __future__ import annotations
import json, re, sys, zipfile
from pathlib import Path
from lxml import etree
sys.path.insert(0, str(Path(__file__).parent))
from enrich import norm_name
from extract_abr import ZIPS, local, parse_abr

CAND = Path("/workspace/agor-sheet/companies/candidates.json")
OUT = Path("/workspace/agor-sheet/companies/abr_company_hits.json")

def ckey(name: str) -> str:
    s = norm_name(name)
    s = re.sub(r"\bPROPRIETARY\b", "PTY", s)
    s = re.sub(r"\bLIMITED\b", "LTD", s)
    s = re.sub(r"\bCOMPANY\b", "CO", s)
    s = re.sub(r"\bCORP\b", "CORPORATION", s)
    return re.sub(r"\s+", " ", s).strip()

def legal_names(title: str) -> list[str]:
    t = re.sub(r"\s*\((trading as|t/as)[^)]*\)", "", title, flags=re.I)
    out = [t]
    if not re.search(r"\b(Pty|Ltd|Limited)\b", t, re.I):
        out.append(re.sub(r"\s*\([^)]*\)", "", t))
    m = re.match(r"(.*?)\s*\(([^)]*Pty Ltd)\)$", t)   # 'BCWF 2 Pty Ltd (Boulder Creek Wind Farm 2 Pty Ltd)'
    if m:
        out += [m.group(1), m.group(2)]
    if t.startswith("Entura "):
        out.append(t[len("Entura "):])
    return out

def main():
    cands = json.load(open(CAND))["new"]
    targets: dict[str, list[str]] = {}
    for c in cands:
        for n in legal_names(c["title"]):
            targets.setdefault(ckey(n), []).append(c["title"])
    hits: dict[str, list] = {}
    scanned = 0
    for zp in ZIPS:
        with zipfile.ZipFile(zp) as zf:
            for info in zf.infolist():
                print(info.filename, flush=True)
                with zf.open(info.filename) as f:
                    for ev, elem in etree.iterparse(f, events=("end",), tag="ABR", recover=True):
                        scanned += 1
                        rec = parse_abr(elem)
                        if rec:
                            names = [rec["name"]] + rec["other_names"]
                            for n in names:
                                k = ckey(n)
                                if k in targets:
                                    rec["matched_name"] = n
                                    hits.setdefault(k, []).append(rec)
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        if scanned % 1000000 == 0:
                            print(f"scanned {scanned:,} hits {len(hits)}", flush=True)
    json.dump({"targets": targets, "hits": hits}, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("DONE", scanned, len(hits), flush=True)

if __name__ == "__main__":
    main()
