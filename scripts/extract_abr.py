#!/usr/bin/env python3
"""Stream the ABR bulk extract ZIPs and write government (and allied) entities to JSONL.

Usage: download public_split_1_10.zip and public_split_11_20.zip from
https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e into
ABR_DIR (default /workspace/agor-sheet/abr/), then run this script.
Output: gov_entities.jsonl plus entity_type_counts.json.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from lxml import etree

GOV_PREFIXES = ("CG", "SG", "TG", "LG")
GOV_EXACT = {"GOV", "SSA", "STA", "TER", "LOC"}
ALLIED = {"OIE", "UIE"}  # other incorporated/unincorporated; some public bodies use these

OUT = Path("/workspace/agor-sheet/abr/gov_entities.jsonl")
TYPE_COUNTS = Path("/workspace/agor-sheet/abr/entity_type_counts.json")
ZIPS = [
    Path("/workspace/agor-sheet/abr/public_split_1_10.zip"),
    Path("/workspace/agor-sheet/abr/public_split_11_20.zip"),
]


def keep_type(ind: str) -> bool:
    if not ind:
        return False
    return ind in GOV_EXACT or ind.startswith(GOV_PREFIXES) or ind in ALLIED


def local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_abr(elem) -> dict | None:
    typ_ind = typ_text = ""
    abn = status = state = postcode = legal = ""
    others: list[str] = []
    for child in elem:
        t = local(child.tag)
        if t == "ABN":
            abn = (child.text or "").strip()
            status = child.get("status") or ""
        elif t == "EntityType":
            typ_ind = (child.findtext("EntityTypeInd") or child.findtext(f".//{child.tag.split('}')[0]}}}EntityTypeInd") or "")
            # safer: iterate
            for s in child:
                st = local(s.tag)
                if st == "EntityTypeInd":
                    typ_ind = (s.text or "").strip()
                elif st == "EntityTypeText":
                    typ_text = (s.text or "").strip()
        elif t in {"MainEntity", "LegalEntity"}:
            for s in child:
                st = local(s.tag)
                if st == "NonIndividualName":
                    legal = (s.findtext("NonIndividualNameText") or "")
                    if not legal:
                        for n in s:
                            if local(n.tag) == "NonIndividualNameText":
                                legal = n.text or ""
                    legal = legal.strip()
                elif st == "BusinessAddress":
                    # AddressDetails/State, Postcode
                    for ad in s.iter():
                        at = local(ad.tag)
                        if at == "State" and ad.text:
                            state = ad.text.strip()
                        elif at == "Postcode" and ad.text:
                            postcode = ad.text.strip()
        elif t == "OtherEntity":
            for s in child:
                if local(s.tag) == "NonIndividualName":
                    for n in s:
                        if local(n.tag) == "NonIndividualNameText" and n.text:
                            others.append(n.text.strip())
    if not abn:
        return None
    return {
        "abn": abn,
        "status": status,
        "type": typ_ind,
        "type_text": typ_text,
        "state": state,
        "postcode": postcode,
        "name": legal,
        "other_names": others,
    }


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    type_counts: dict[str, list] = {}
    kept = scanned = 0
    with OUT.open("w", encoding="utf-8") as out:
        for zp in ZIPS:
            print(f"Opening {zp.name}", flush=True)
            with zipfile.ZipFile(zp) as zf:
                for info in zf.infolist():
                    print(f"  {info.filename} ...", flush=True)
                    with zf.open(info.filename) as f:
                        context = etree.iterparse(f, events=("end",), tag="ABR", recover=True)
                        for ev, elem in context:
                            typ = ""
                            # cheap type read
                            for child in elem:
                                if local(child.tag) == "EntityType":
                                    for s in child:
                                        if local(s.tag) == "EntityTypeInd":
                                            typ = (s.text or "").strip()
                                            break
                                    break
                            rec_text = ""
                            # count all types lightly: get text too only if new
                            if typ not in type_counts:
                                typ_text = ""
                                for child in elem:
                                    if local(child.tag) == "EntityType":
                                        for s in child:
                                            if local(s.tag) == "EntityTypeText":
                                                typ_text = (s.text or "").strip()
                                type_counts[typ] = [typ_text, 0]
                            type_counts[typ][1] += 1
                            scanned += 1
                            if keep_type(typ):
                                rec = parse_abr(elem)
                                if rec:
                                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                                    kept += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            if scanned % 200000 == 0:
                                print(f"    scanned={scanned:,} kept={kept:,}", flush=True)
                    print(f"    done scanned={scanned:,} kept={kept:,}", flush=True)
    TYPE_COUNTS.write_text(json.dumps({k: {"text": v[0], "count": v[1]} for k, v in sorted(type_counts.items(), key=lambda x: -x[1][1])}, indent=2))
    print(f"FINISHED scanned={scanned:,} kept={kept:,} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
