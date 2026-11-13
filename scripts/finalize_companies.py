#!/usr/bin/env python3
"""After apply_companies.py + build_icons.py: rewrite data/sources.csv, the XLSX
(Organisations incl. icon columns, Sources, Fill rates), enrichment_report.json
and the README count tables."""
from __future__ import annotations
import csv, json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import enrich
import companies_data as cd

ROOT = Path(__file__).resolve().parents[1]
ORDER = ["Commonwealth", "NSW", "Victoria", "Queensland", "WA", "SA", "Tasmania", "ACT", "NT"]
XLSX_NAME = "Australian_Government_Organisations_All_Jurisdictions_Nov_2026.xlsx"

def main(sheet_url: str | None = None):
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    cols = list(rows[0].keys())
    enrich.OUT_COLS = cols  # include the icon columns in the XLSX
    by_src = Counter(r["Source name"] for r in rows)
    # existing per-source row counts may have changed (none removed); add new sources before the ABR row
    new = []
    jmap = {"QLD": "Queensland", "TAS": "Tasmania", "WA_": "WA", "VIC": "Victoria", "NSW": "NSW", "SA_": "SA", "ACT": "ACT", "NT_": "NT"}
    for key, (name, url, date, fmt, notes) in cd.SOURCES.items():
        n = by_src.get(name, 0)
        if not n: continue
        new.append({"Jurisdiction": jmap[key[:3]], "Source name": name, "URL": url, "Date": date, "Format": fmt,
                    "Coverage notes": notes + " Added November 2026 as government-owned companies / GOCs / GBEs / GTEs and subsidiaries; deduplicated against existing rows (normalised names).",
                    "Row count": str(n)})
    base = [s for s in enrich.SOURCES_OUT if s["Source name"] not in {x["Source name"] for x in new}]
    for s in base:
        if s["Source name"] in by_src: s["Row count"] = str(by_src[s["Source name"]])
        if s["Source name"].startswith("ABR ABN Bulk Extract") and "companies added" not in s["Coverage notes"]:
            s["Coverage notes"] += (" For the government-owned companies added in November 2026, the extract was re-scanned for every entity type (including"
                                    " Australian Private/Public Company); an ABN is used only for a single current (status ACT) record in the right state whose"
                                    " legal or other name equals the company name after normalising Pty/Proprietary and Ltd/Limited (confidence 'exact').")
    abr_i = next(i for i, s in enumerate(base) if s["Source name"].startswith("ABR ABN Bulk Extract"))
    new.sort(key=lambda s: ORDER.index(s["Jurisdiction"]))
    enrich.SOURCES_OUT[:] = base[:abr_i] + new + base[abr_i:]
    enrich.write_sources(ROOT / "data/sources.csv", rows)
    fill = enrich.fill_rates(rows)
    (ROOT / "data/enrichment_report.json").write_text(json.dumps(fill, indent=2))
    for p in [Path("/workspace/agor-sheet") / XLSX_NAME, ROOT / "data" / XLSX_NAME]:
        enrich.write_xlsx(p, rows, fill)
    readme(rows, fill, sheet_url)

def fmt(n): return f"{n:,}"

def readme(rows, fill, sheet_url):
    p = ROOT / "README.md"; s = p.read_text()
    tot = len(rows)
    s = re.sub(r"all [\d,]+ entity rows", f"all {fmt(tot)} entity rows", s)
    cnt = Counter(r["Jurisdiction"] for r in rows)
    tbl = "| Jurisdiction | Rows |\n| --- | ---: |\n" + "".join(f"| {j} | {fmt(cnt[j])} |\n" for j in ORDER) + f"| **Total** | **{fmt(tot)}** |\n"
    s = re.sub(r"\| Jurisdiction \| Rows \|\n\| --- \| ---: \|\n(?:\|.*\|\n)+", tbl, s, count=1)
    cols = [("ABN", "ABN"), ("Website Address", "Website"), ("Portfolio", "Portfolio"), ("Classification", "Classification"), ("Type of Body", "Type of Body"),
            ("Established by/Under More Info", "Legislation / established under"), ("Head Office Street Address", "Head office address"),
            ("Accountable Authority", "Accountable authority"), ("Contact telephone", "Telephone"), ("Generic agency email", "Agency email")]
    hdr = "| Jurisdiction | Rows | " + " | ".join(c[1] for c in cols) + " |\n| --- | ---: |" + " ---: |" * len(cols) + "\n"
    body = ""
    for j in ORDER + ["All"]:
        rec = fill[j]
        cells = [f"{rec[c]['pct']:.1f}%" for c, _ in cols]
        if j == "All":
            body += f"| **All** | **{fmt(rec['rows'])}** | " + " | ".join(f"**{c}**" for c in cells) + " |\n"
        else:
            body += f"| {j} | {fmt(rec['rows'])} | " + " | ".join(cells) + " |\n"
    s = re.sub(r"\| Jurisdiction \| Rows \| ABN \| Website \|.*\n\| --- .*\n(?:\|.*\|\n)+", hdr + body, s, count=1)
    ab = "| Jurisdiction | ABN exact | ABN high | ABN blank |\n| --- | ---: | ---: | ---: |\n"
    for j in ORDER + ["All"]:
        c = fill[j]["ABN confidence"]; name = "**All**" if j == "All" else j
        ab += f"| {name} | {fmt(c['exact'])} | {fmt(c['high'])} | {fmt(c['blank'])} |\n"
    s = re.sub(r"\| Jurisdiction \| ABN exact \| ABN high \| ABN blank \|\n.*\n(?:\|.*\|\n)+", ab, s, count=1)
    # icons table
    man = list(csv.DictReader(open(ROOT / "icons/manifest.csv", encoding="utf-8")))
    meth = ["own-site", "own-site-wikidata", "google-s2", "defence-fallback", "parent", "fallback-jurisdiction"]
    it = "| Jurisdiction | `own-site` | `own-site-wikidata` | `google-s2` | `defence-fallback` | `parent` | `fallback-jurisdiction` | Total |\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
    for j in ORDER:
        c = Counter(m["method"] for m in man if m["jurisdiction"] == j)
        it += f"| {j} | " + " | ".join(fmt(c[m]) for m in meth) + f" | {fmt(sum(c.values()))} |\n"
    c = Counter(m["method"] for m in man)
    it += "| **All** | " + " | ".join(fmt(c[m]) for m in meth) + f" | {fmt(len(man))} |\n"
    s = re.sub(r"\| Jurisdiction \| `own-site` .*\n\|---.*\n(?:\|.*\|\n)+", it, s, count=1)
    s = re.sub(r"one PNG per organisation \([\d,]+ files, [\d,]+ distinct images\)",
               f"one PNG per organisation ({fmt(len(man))} files, {fmt(len({m['sha256'] for m in man}))} distinct images)", s)
    s = re.sub(r"\(([\d,]+) files\)\. Defence-fallback", f"({fmt(sum(1 for m in man if m['svg file']))} files). Defence-fallback", s)
    smallest = min((ROOT / m["icon file"]).stat().st_size for m in man)
    s = re.sub(r"smallest is [\d,]+ bytes", f"smallest is {fmt(smallest)} bytes", s)
    if sheet_url:
        s = re.sub(r"https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+/edit", sheet_url, s)
    p.write_text(s)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
