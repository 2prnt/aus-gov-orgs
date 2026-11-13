#!/usr/bin/env python3
"""Collect ABR main business address state/postcode for every ABN in organisations.csv
(abr_addr.json). Used to fill blank Head Office State/Postcode."""
import csv, json, re, sys, zipfile
from pathlib import Path
from lxml import etree
sys.path.insert(0, str(Path(__file__).parent))
from extract_abr import ZIPS
ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/workspace/agor-sheet/abr/abr_addr.json")
want = {re.sub(r"\D", "", r["ABN"]) for r in csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")) if r["ABN"].strip()}
res = {}
for zp in ZIPS:
    with zipfile.ZipFile(zp) as zf:
        for info in zf.infolist():
            print(info.filename, len(res), flush=True)
            with zf.open(info.filename) as f:
                for ev, el in etree.iterparse(f, events=("end",), tag="ABR", recover=True):
                    a = el.find("ABN")
                    if a is not None and a.text in want:
                        ad = el.find(".//BusinessAddress/AddressDetails")
                        if ad is not None:
                            res[a.text] = {"state": (ad.findtext("State") or "").strip(), "postcode": (ad.findtext("Postcode") or "").strip(), "status": a.get("status")}
                    el.clear()
                    while el.getprevious() is not None: del el.getparent()[0]
OUT.write_text(json.dumps(res))
print("DONE", len(res), flush=True)
