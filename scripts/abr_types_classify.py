#!/usr/bin/env python3
"""Classify active Commonwealth/State/Territory government-type ABR records
(gov_entities.jsonl from extract_abr.py) into include / exclude categories.
Used by add_abr_types.py; run alone to print a category summary."""
from __future__ import annotations
import json, re
from collections import Counter
from pathlib import Path

ABR_JSONL = Path("/workspace/agor-sheet/abr/gov_entities.jsonl")
GOV = ("CG", "SG", "TG")  # LG* (local government) out of scope

# (category, regex on upper-case name). Order matters: first match wins.
RULES = [
 ("payroll/fund/account sub-registration", r"\b(PAYROLL|TRUST ACCOUNT|SPECIAL PURPOSE ACCOUNT|PUBLIC FUND|GIFT FUND|DONATIONS? (FUND|ACCOUNT)|BUILDING FUND|SCHOLARSHIP FUND|LIBRARY FUND|DGR|AMENITIES FUND|WELFARE FUND|BENEVOLENT FUND|PRIZE FUND|BEQUEST|ENDOWMENT|PATIENT(S)? (TRUST|FUND)|RESIDENTS? (TRUST|FUND)|COMFORTS FUND|FUNDS? ACCOUNT)\b"),
 ("defence mess/unit/cadet sub-registration", r"\b(MESS|MESSES|SQUADRON|SQN|HMAS|HMA SHIP|RAAF|RAN|REGIMENT|BATTALION|CADETS?|CORPS|UNIT FUND|UNIT WELFARE|CANTEEN|WARDROOM|SERGEANTS|ALL RANKS|SHIPS FUND)\b"),
 ("government school/kindergarten", r"\b(SCHOOLS?|PRIMARY|COLLEGE|KINDERGARTEN|KINDY|PRESCHOOL|PRE-SCHOOL|PRE SCHOOL|CHILDREN'?S CENTRE|CHILD CARE|CHILDCARE|EARLY (LEARNING|CHILDHOOD)|P-12|P12|K-12|SECONDARY COLLEGE|STATE SCHOOL|SPECIAL SCHOOL|EDUCATION SUPPORT CENTRE|SCHOOL COUNCIL|GOVERNING COUNCIL|PARENTS? AND (CITIZENS|FRIENDS)|P AND C|P&C)\b"),
 ("Crown land reserve / hall / committee of management", r"\b(RESERVE|RECREATION|HALL|MECHANICS|RACECOURSE|SHOWGROUNDS?|COMMITTEE OF MANAGEMENT|PUBLIC PARK|PARK TRUST|PARK COMMITTEE|GARDENS? COMMITTEE|SPORTSGROUND|SPORTS GROUND|OVAL|POOL|STADIUM COMMITTEE|SOLDIERS MEMORIAL|MEMORIAL (HALL|PARK)|COMMONS?|LAND MANAGER|CROWN LAND|TENNIS|GOLF|BOWLS|FOOTBALL|CRICKET|CAMPING|CARAVAN|FORESHORE|JETTY|BOAT RAMP|INSTITUTE HALL)\b"),
 ("club/association/society (non-government body on a government ABN type)", r"\b(CLUB|ASSOCIATION|ASSOC|ASSN|SOCIETY|AUXILIARY|MOTHERS|PARENTS|PROGRESS|SOCIAL|FAMILIES|FRIENDS OF|BALL|STUDENTS?|PHILANTHROPIC|HISTORICAL|PRESERVATION|SPORTING COMPLEX|COMMUNITY CENTRE|COMMUNITY INCORPORATED|NETBALL|HOCKEY|RUGBY|SKIING|GLIDING|TRIATHLON|FISHING|DIVE)\b"),
 ("account/division/branch/staff/employing-office sub-registration", r"\b(ACCOUNT|TERRITORIAL|DEPARTMENTAL|DIVISION|STAFF AGENCY|STAFF|EMPLOYING OFFICE|BRANCH|CAMPUS|BOOKSHOP|SHOP|PROVISION|CONSOLIDATED|PORTFOLIO|RTF|RPA|DETACHMENT|SECRETARIAT|CATERING|PAYMENTS?|HOME LOAN|PROGRAM|PROGRAMME|CONTROLLED|STATE GOVERNMENT|THE LEGISLATURE|EXECUTIVE UNIT|CRESENT CSC|CSC)\b"),
 ("fund/scheme (not an organisation)", r"\b(FUND|FUNDS|FD|SCHEME|PENSIONS|NOMINAL INSURER|LIABILITY)\b"),
 ("education/training/children's centre (school-type site)", r"\b(EDUCATION CENTRE|OUTDOOR EDUCATION|ENVIRONMENTAL EDUCATION|ENVIRNMENTAL EDUCATION|LEARNING CENTRE|LANGUAGE DEVELOPMENT CENTRE|LANGUAGES? CENTRE|ENGLISH LANGUAGE|COMMUNITY EDUCATION|CEC|CEC COUNCIL|EDUCATION SUPPORT|DISTRICT HIGH|SENIOR CAMPUS|CHILDREN'?S SERVICES|CHILDHOOD SERVICES|FAMILY CENTRE|ACADEMY FOR|VIRTUAL ACADEMY|DISTANCE EDUCATION|AVIATION HIGH|TRAINING CENTRE|SENIOR SC|LEADERSHIP EXCELLENCE CENTRE|ORAL AURAL UNIT|EDUCATION RESOURCE CENTRE|SENIOR HIGH|PS|ESCHOOL|LEARNING FEDERATION|CHILDRENS'? (SERVICES|CENTRE)|CHILDRENS'? SERVICES_CENTRE)\b"),
 ("defence unit/social sub-registration", r"\b(FLIGHT|AIRTC|QAIRTC|TROOP|BAND|REGIMENTAL|BARRACKS|NORFORCE|RECCE|SAIL TRAINING|NORTHSAIL|DEFENCE FORCE|ADF|ARMY|NAVY|AIR FORCE|RSAF|PSYCH UNIT|BATTLE|DEFENCE COMMUNITY|DEFENCE INTELLIGENCE TRAINING|DEFENCE CORPORATE SUPPORT|JOINT MOVEMENT|COMMAND ELEMENT|SOLDIERS?|AMENITIES)\b"),
 ("historical inquiry / personal office", r"\b(ROYAL COMMISSION|COMMISSION OF INQUIRY|COMMISSIONERS OF THE INQUIRY|SENATOR|SOCOG)\b"),
 ("minister (corporation sole)", r"^ ?(THE )?MINISTER\b"),
 ("emergency service brigade/unit", r"\b(FIRE BRIGADE|BRIGADE|SES UNIT|RURAL FIRE|FIRE AND RESCUE STATION|STATE EMERGENCY SERVICE (UNITS?|SOUTH|NORTH|EAST|WEST|CENTRAL|MID)|STATE EMERGENCY SERVICE -|CFS GROUP|^ \\d{4,5} [A-Z ]+ GROUP $|VOLUNTEER|RESCUE SQUAD|FIREWISE)\b"),
 ("investment fund/pool", r"\b(FUNDS SA [A-Z ]+|FUND|FUNDS|INVESTMENT TRUST|UNIT TRUST|POOL [A-Z])$|\bTHE TRUSTEE FOR\b"),
]
RULES += [
 ("local-government body (out of scope)", r"\bREGIONAL COUNCIL $|ORGANISATION OF COUNCILS|^ SOUTHERN REGION WASTE RESOURCE AUTHORITY $"),
 ("Crown land reserve / hall / committee of management", r"RAIL TRAIL (MANAGEMENT )?COMMITTEE"),
 ("account/division/branch/staff/employing-office sub-registration", r"\bSUSPENSE\b|^ (SOUTH AUSTRALIAN GOVERNMENT|SOUTH AUSTRALIAN BOARD|BUILDING MAINTENANCE|BUILDING MANAGEMENT|STATE SUPPORT GROUP|SHARED SERVICES) $|^ (DETE|DHS|DIT)\b"),
 ("education/training/children's centre (school-type site)", r"\b(SENIOR HIGH|PS|ESCHOOL|LEARNING FEDERATION|CHILDRENS'? (SERVICES|CENTRE)|CHILDRENS'? SERVICES_CENTRE)\b"),
 ("emergency service brigade/unit", r"^ \d{4,5} [A-Z ]+ GROUP $"),
]
CRE = [(c, re.compile(p)) for c, p in RULES]

def jurisdiction(rec: dict) -> str:
    t, st = rec["type"], (rec.get("state") or "").upper()
    if t.startswith("CG"): return "Commonwealth"
    if t.startswith("TG"): return {"ACT": "ACT", "NT": "NT"}.get(st, "")
    return {"NSW": "NSW", "VIC": "Victoria", "QLD": "Queensland", "WA": "WA", "SA": "SA", "TAS": "Tasmania"}.get(st, "")

def classify(rec: dict) -> str:
    n = " " + re.sub(r"\s+", " ", (rec["name"] or "").upper().replace("&", " AND ")) + " "
    for c, rx in CRE:
        if rx.search(n): return c
    return ""

def load():
    for l in open(ABR_JSONL, encoding="utf-8"):
        r = json.loads(l)
        if r["type"].startswith(GOV): yield r

if __name__ == "__main__":
    recs = [r for r in load() if r["status"] == "ACT"]
    c = Counter(classify(r) or "remaining" for r in recs)
    print(len(recs), c)
    j = Counter(jurisdiction(r) or f"?{r['type']}/{r['state']}" for r in recs if not classify(r))
    print(j)
