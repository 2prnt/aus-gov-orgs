#!/usr/bin/env python3
"""Collect record-last-updated date, ABN status-from date and GST status for
active Commonwealth/State/Territory government-type ABNs (abr_gov_dates.json)."""
import json, sys, zipfile
from pathlib import Path
from lxml import etree
sys.path.insert(0, str(Path(__file__).parent))
from extract_abr import ZIPS, local
from abr_types_classify import load
OUT = Path("/workspace/agor-sheet/abr/abr_gov_dates.json")
want = {r["abn"] for r in load() if r["status"] == "ACT"}
res = {}
for zp in ZIPS:
    with zipfile.ZipFile(zp) as zf:
        for info in zf.infolist():
            print(info.filename, len(res), flush=True)
            with zf.open(info.filename) as f:
                for ev, el in etree.iterparse(f, events=("end",), tag="ABR", recover=True):
                    a = el.find("ABN")
                    if a is not None and a.text in want:
                        g = el.find("GST")
                        res[a.text] = {"updated": el.get("recordLastUpdatedDate"), "abn_from": a.get("ABNStatusFromDate"),
                                       "gst": g.get("status") if g is not None else "", "gst_from": g.get("GSTStatusFromDate") if g is not None else "",
                                       "dgr": el.find("DGR") is not None}
                    el.clear()
                    while el.getprevious() is not None: del el.getparent()[0]
OUT.write_text(json.dumps(res))
print("DONE", len(res), flush=True)
