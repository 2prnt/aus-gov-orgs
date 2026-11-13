#!/usr/bin/env python3
"""Enrich the combined organisations list with AGOR-aligned columns, source
fields, and conservative ABN / website lookups.

Reads the 7-column data/organisations.csv produced by build.py, official
source files under SRC, and the compact ABR government-entity extract, then
rewrites data/organisations.csv, data/by-jurisdiction/*.csv, data/sources.csv
and an XLSX workbook for the Google Sheet.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/agor-sheet/sources")
ABR_JSONL = Path("/workspace/agor-sheet/abr/gov_entities.jsonl")
DATA = ROOT / "data"
REPORT = ROOT / "data" / "enrichment_report.json"

AGOR_COLS = [
    "Id",
    "Portfolio Dept?",
    "Title",
    "Portfolio",
    "Classification",
    "Type of Body",
    "GFS Sector Classification",
    "Materiality",
    "Description",
    "Established By / Under",
    "Established by/Under More Info",
    "Creation Date",
    "GFS Function / Sector Reported",
    "PS Act Body",
    "Average Staffing Level (ASL)",
    "Max Number of Board / Committee Members",
    "Paid Members?",
    "Board / Committee Appointed by",
    "Board / Committee Appointed More Info",
    "Annual Report Prepared and Tabled?",
    "Auditor",
    "Auditor Other",
    "ABN",
    "Parent Organisation",
    "Parent Board / Non-Board Title",
    "Total Appropriations ($000)",
    "Total Departmental Expenses ($000)",
    "Head Office Street Address",
    "Head Office Suburb",
    "Head Office State",
    "Head Office Postcode",
    "Head Office Country",
    "Website Address",
    "Strategic/Corporate/Organisational Plan",
    "Annual Reports",
    "Budget Documentation",
]

EXTRA_COLS = [
    "Accountable Authority",
    "Contact telephone",
    "Generic agency email",
]

OUT_COLS = (
    ["Jurisdiction"]
    + AGOR_COLS
    + ["Source name", "Source URL", "Source date"]
    + EXTRA_COLS
    + ["ABN match confidence"]
)

JURIS_STATE = {
    "Commonwealth": "CTH",
    "NSW": "NSW",
    "Victoria": "VIC",
    "Queensland": "QLD",
    "WA": "WA",
    "SA": "SA",
    "Tasmania": "TAS",
    "ACT": "ACT",
    "NT": "NT",
}

GOV_PREFIXES = ("CG", "SG", "TG", "LG")
GOV_EXACT = {"GOV", "SSA", "STA", "TER", "LOC"}
ALLIED_TYPES = {"OIE", "UIE"}

PUNCT_RE = re.compile(r"[^A-Z0-9& ]+")
SPACE_RE = re.compile(r"\s+")
THE_RE = re.compile(r"^THE\s+")
TRADING_RE = re.compile(
    r"\s*[\(\[]\s*(TRADING AS|T/?AS?|T/A)\s+[^\)\]]+[\)\]]\s*$",
    re.I,
)
TRADING_TAIL_RE = re.compile(r"\s+(TRADING AS|T/?AS)\s+.+$", re.I)
DEPT_HEAD_RE = re.compile(r"^(DEPARTMENT (?:OF|FOR)\s+)(.+)$")
DEPT_TAIL_RE = re.compile(r"^(.+?)\s+DEPARTMENT$")
OFFICE_HEAD_RE = re.compile(r"^(OFFICE OF (?:THE\s+)?)(.+)$")


def is_gov_type(ind: str) -> bool:
    if not ind:
        return False
    return ind in GOV_EXACT or ind.startswith(GOV_PREFIXES)


def norm_name(value: str) -> str:
    s = (value or "").upper().replace("\xa0", " ")
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", " ").replace("\u201d", " ")
    s = s.replace("&", " AND ")
    # Attorney-General's -> ATTORNEY GENERALS (keep possessive S attached)
    s = re.sub(r"'S\b", "S", s)
    s = s.replace("'", " ")
    s = TRADING_RE.sub("", s)
    s = TRADING_TAIL_RE.sub("", s)
    s = PUNCT_RE.sub(" ", s)
    s = SPACE_RE.sub(" ", s).strip()
    s = THE_RE.sub("", s)
    return s


def name_variants(value: str) -> list[str]:
    base = norm_name(value)
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        x = SPACE_RE.sub(" ", x).strip()
        x = THE_RE.sub("", x)
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(base)
    # jurisdiction shorthand
    replacements = [
        ("NEW SOUTH WALES", "NSW"),
        ("NSW", "NEW SOUTH WALES"),
        ("SOUTH AUSTRALIA", "SA"),
        ("SOUTH AUSTRALIAN", "SA"),
        ("WESTERN AUSTRALIA", "WA"),
        ("WESTERN AUSTRALIAN", "WA"),
        ("NORTHERN TERRITORY", "NT"),
        ("AUSTRALIAN CAPITAL TERRITORY", "ACT"),
        ("VICTORIAN", "VICTORIA"),
        ("TASMANIAN", "TASMANIA"),
    ]
    for src, dst in replacements:
        if src in base:
            add(base.replace(src, dst))
    m = DEPT_HEAD_RE.match(base)
    if m:
        add(m.group(2) + " DEPARTMENT")
        # Do not add the bare remainder (e.g. "HEALTH") — too short / ambiguous.
    m = DEPT_TAIL_RE.match(base)
    if m:
        add("DEPARTMENT OF " + m.group(1))
        add("DEPARTMENT FOR " + m.group(1))
    m = OFFICE_HEAD_RE.match(base)
    if m:
        rest = m.group(2)
        add(rest)
        add(rest + " OFFICE")
        add("THE " + rest + " OFFICE")
    # "Ombudsman's Office" <-> "Office of the Ombudsman"
    if base.endswith(" OFFICE") and not base.startswith("OFFICE OF "):
        rest = base[: -len(" OFFICE")].strip()
        if rest.startswith("THE "):
            rest = rest[4:]
        if rest:
            add("OFFICE OF THE " + rest)
            add("OFFICE OF " + rest)
            # Ombudsman's Office -> OFFICE OF THE OMBUDSMAN (not OMBUDSMANS)
            if rest.endswith("S") and len(rest) > 4:
                add("OFFICE OF THE " + rest[:-1])
                add("OFFICE OF " + rest[:-1])
    # drop leading jurisdiction qualifiers
    for head in (
        "NSW ",
        "NEW SOUTH WALES ",
        "VIC ",
        "VICTORIAN ",
        "VICTORIA ",
        "QLD ",
        "QUEENSLAND ",
        "WA ",
        "WESTERN AUSTRALIAN ",
        "WESTERN AUSTRALIA ",
        "SA ",
        "SOUTH AUSTRALIAN ",
        "SOUTH AUSTRALIA ",
        "TAS ",
        "TASMANIAN ",
        "TASMANIA ",
        "ACT ",
        "NT ",
        "NORTHERN TERRITORY ",
    ):
        if base.startswith(head) and len(base) - len(head) >= 8:
            add(base[len(head):])
    # drop trailing state names for distinctive bodies
    for tail in (
        " OF SOUTH AUSTRALIA",
        " SOUTH AUSTRALIA",
        " OF NEW SOUTH WALES",
        " OF WESTERN AUSTRALIA",
        " WESTERN AUSTRALIA",
        " WESTERN AUSTRALIAN",
        " OF VICTORIA",
        " OF TASMANIA",
        " OF THE NORTHERN TERRITORY",
        " OF THE AUSTRALIAN CAPITAL TERRITORY",
        " FOR WESTERN AUSTRALIA",
        " FOR SOUTH AUSTRALIA",
        " FOR NEW SOUTH WALES",
        " FOR VICTORIA",
        " FOR TASMANIA",
        " FOR QUEENSLAND",
        " FOR THE NORTHERN TERRITORY",
        " FOR THE AUSTRALIAN CAPITAL TERRITORY",
        " FOR WA",
        " FOR NSW",
        " FOR VIC",
        " FOR QLD",
        " FOR SA",
        " FOR TAS",
        " FOR ACT",
        " FOR NT",
        " NSW",
        " VIC",
        " QLD",
        " WA",
        " SA",
        " TAS",
        " ACT",
        " NT",
    ):
        if base.endswith(tail) and len(base) - len(tail) >= 8:
            add(base[: -len(tail)])
    return out


def format_abn(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 11:
        return (value or "").strip()
    return f"{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:11]}"


def digits_abn(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalise_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = u.replace(" ", "")
    if u.startswith("www."):
        u = "https://" + u
    elif not re.match(r"^https?://", u, re.I):
        if "." in u:
            u = "https://" + u
        else:
            return ""
    # reject obvious non-sites
    low = u.lower()
    if any(x in low for x in ("javascript:", "mailto:", "tel:")):
        return ""
    return u.rstrip("/") if u.count("/") > 2 or u.endswith("/") else u


def load_base_rows() -> list[dict]:
    path = DATA / "organisations.csv"
    # During this enrichment we may already have overwritten organisations.csv.
    # Prefer the 7-column snapshot if present.
    snapshot = DATA / "organisations_base.csv"
    if snapshot.exists():
        path = snapshot
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if "Entity name" not in (rows[0] if rows else {}):
        # already enriched; Title is the name
        return rows
    return rows


def ensure_base_snapshot() -> None:
    src = DATA / "organisations.csv"
    snap = DATA / "organisations_base.csv"
    if not snap.exists() and src.exists():
        with src.open(encoding="utf-8", newline="") as f:
            header = f.readline()
        if header.startswith("Jurisdiction,Entity name,"):
            snap.write_bytes(src.read_bytes())


def load_agor() -> list[dict]:
    path = SRC / "agor-2026-09-30.csv"
    with path.open(encoding="cp1252", newline="") as f:
        return list(csv.DictReader(f))


def load_abr() -> tuple[dict[str, dict], dict[str, dict[str, list]], dict[str, list]]:
    """Return (by_abn, by_state_norm, by_norm_all_states). Only Active records."""
    by_abn: dict[str, dict] = {}
    by_state: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    by_all: dict[str, list] = defaultdict(list)
    if not ABR_JSONL.exists():
        raise SystemExit(f"Missing ABR extract: {ABR_JSONL}")
    with ABR_JSONL.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("status") != "ACT":
                continue
            abn = digits_abn(rec.get("abn", ""))
            if not abn:
                continue
            # Prefer first (should be unique)
            by_abn.setdefault(abn, rec)
            names = [rec.get("name") or ""] + list(rec.get("other_names") or [])
            state = (rec.get("state") or "").upper().strip()
            for n in names:
                for v in name_variants(n):
                    by_state[state][v].append(rec)
                    by_all[v].append(rec)
    return by_abn, by_state, by_all


STATE_JURISDICTIONS = {"NSW", "Victoria", "Queensland", "WA", "SA", "Tasmania"}
TERRITORY_JURISDICTIONS = {"ACT", "NT"}


def eligible_type(typ: str, jurisdiction: str) -> bool:
    """State/territory rows may only match government types for that level.

    Commonwealth government types (CG*) are never used for sub-national
    rows — many Cth bodies have an ACT (or other) business address and
    would otherwise collide with territory agencies of the same name.
    """
    typ = typ or ""
    if typ.startswith("CG"):
        return False
    if jurisdiction in TERRITORY_JURISDICTIONS:
        return typ.startswith("TG") or typ.startswith("LG") or typ in {"TER", "GOV", "LOC"}
    if jurisdiction in STATE_JURISDICTIONS:
        return typ.startswith("SG") or typ.startswith("LG") or typ in {"GOV", "SSA", "STA", "LOC"}
    return False


def unique_recs(recs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for r in recs:
        a = digits_abn(r.get("abn", ""))
        if a and a not in seen:
            seen.add(a)
            out.append(r)
    return out


def legal_name_matches(entity_name: str, rec: dict) -> bool:
    ev = set(name_variants(entity_name))
    return bool(ev & set(name_variants(rec.get("name") or "")))


def match_abn(
    name: str,
    jurisdiction: str,
    by_state,
    by_all,
    *,
    allow_allied: bool = False,
) -> tuple[str, str, dict | None]:
    """Return (formatted_abn, confidence, rec). confidence is exact|high|''."""
    state = JURIS_STATE.get(jurisdiction, "")
    if jurisdiction == "Commonwealth":
        return "", "", None

    def filter_types(recs):
        out = []
        for r in unique_recs(recs):
            typ = r.get("type") or ""
            if not eligible_type(typ, jurisdiction):
                continue
            rec_state = (r.get("state") or "").upper()
            # Require the recorded state to agree when it is present.
            if rec_state and rec_state != state:
                continue
            if is_gov_type(typ) or (allow_allied and typ in ALLIED_TYPES):
                out.append(r)
        return out

    variants = name_variants(name)
    # 1) unique eligible gov-type match in the right state
    for i, v in enumerate(variants):
        recs = filter_types(by_state.get(state, {}).get(v, []))
        if len(recs) == 1:
            rec = recs[0]
            conf = "exact" if legal_name_matches(name, rec) and i == 0 else "high"
            # If the primary normalised name equals the legal name, exact.
            if legal_name_matches(name, rec):
                conf = "exact"
            return format_abn(rec["abn"]), conf, rec
        if len(recs) > 1:
            # ambiguous in-state
            return "", "", None

    # 2) unique match on the primary normalised name among eligible
    #    records that have no recorded state (rare). Never accept a
    #    different state — many governments share department titles.
    primary = variants[0] if variants else ""
    if primary and len(primary) >= 12:
        recs = filter_types(by_all.get(primary, []))
        if len(recs) == 1:
            rec = recs[0]
            conf = "exact" if legal_name_matches(name, rec) else "high"
            return format_abn(rec["abn"]), conf, rec
    return "", "", None


def load_wa_details() -> dict[str, dict]:
    path = SRC / "wa-government-sector-mailing-list.xlsx"
    wb = load_workbook(path, data_only=True)
    by_name: dict[str, dict] = {}

    def colmap(header):
        m = {}
        for i, c in enumerate(header):
            key = (str(c).strip() if c is not None else "") or f"__{i}"
            if key in m and key not in {"Suburb", "State", "Postcode"}:
                key = f"{key}_{i}"
            # first occurrence wins for address fields; website via name or blank header
            m.setdefault(key, i)
            if key.lower() in {"website", "internetaddress"}:
                m["website"] = i
        # unnamed website-ish column often index 16
        if "website" not in m:
            for i, c in enumerate(header):
                if c is None or str(c).strip() in {"", " "}:
                    m["website"] = i
                    break
        return m

    def val(row, idx):
        if idx is None or idx >= len(row) or row[idx] is None:
            return ""
        return str(row[idx]).strip()

    for sheet in wb.sheetnames:
        rows = list(wb[sheet].iter_rows(values_only=True))
        if not rows:
            continue
        cmap = colmap(rows[0])
        name_i = cmap.get("Agency name")
        if name_i is None:
            continue
        for row in rows[1:]:
            name = val(row, name_i)
            if not name:
                continue
            key = norm_name(name)
            if key in by_name:
                # fill any blanks from later rows of the same agency
                rec = by_name[key]
            else:
                rec = {
                    "name": name,
                    "street": "",
                    "suburb": "",
                    "state": "",
                    "postcode": "",
                    "website": "",
                    "phone": "",
                    "email": "",
                    "ceo_email": "",
                    "ceo_title": "",
                    "ceo_name": "",
                }
                by_name[key] = rec
            street_i = cmap.get("Street address")
            suburb_i = cmap.get("Suburb")
            state_i = cmap.get("State")
            post_i = cmap.get("Postcode")
            if not rec["street"]:
                rec["street"] = val(row, street_i)
                rec["suburb"] = val(row, suburb_i)
                rec["state"] = val(row, state_i)
                rec["postcode"] = val(row, post_i)
            if not rec["website"]:
                rec["website"] = normalise_url(val(row, cmap.get("website")))
            if not rec["phone"]:
                rec["phone"] = val(row, cmap.get("Telephone"))
            if not rec["email"]:
                rec["email"] = val(row, cmap.get("Generic agency email")).strip()
            if not rec["ceo_email"]:
                rec["ceo_email"] = val(row, cmap.get("Generic CEO email")).strip()
            if not rec["ceo_title"]:
                rec["ceo_title"] = val(row, cmap.get("Job title"))
    return by_name


def load_nsw_details() -> dict[str, dict]:
    path = SRC / "nsw-treasury-gsf-agency-list.xlsx"
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(c).strip() if c else "" for c in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    out = {}
    for row in rows[1:]:
        name = str(row[idx["GSF Agency"]]).strip() if row[idx["GSF Agency"]] else ""
        if not name:
            continue
        legis = row[idx.get("Relevant legislation of entity", 3)]
        legis = str(legis).strip() if legis else ""
        legis = re.sub(r"\s+", " ", legis)
        auth = row[idx.get("Accountable Authority", 4)]
        auth = str(auth).strip() if auth else ""
        out[norm_name(name)] = {
            "legislation": legis,
            "accountable_authority": auth,
            "classification": str(row[idx.get("GSF Act Classification", 2)] or "").strip(),
        }
    return out


def load_vic_details() -> dict[str, dict]:
    path = SRC / "vic-vpsc-employers-2026-10-19.csv"
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("Agency") or "").strip()
            if not name:
                continue
            out[norm_name(name)] = {
                "body_type": (row.get("Public Sector Body Type") or "").strip(),
                "employer_type": (row.get("Employer type") or "").strip(),
                "industry": (row.get("Industry") or "").strip(),
                "subsector": (row.get("Sub-Sector") or "").strip(),
            }
    return out


def load_sa_einvoice() -> dict[str, dict]:
    path = SRC / "sa-einvoice-abns.xlsx"
    if not path.exists():
        path = Path("/tmp/sa_abn.xlsx")
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    out = {}
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        name = str(row[0]).strip()
        abn = format_abn(str(row[1] or ""))
        notes = str(row[2]).strip() if len(row) > 2 and row[2] else ""
        out[norm_name(name)] = {"name": name, "abn": abn, "notes": notes}
    return out


def parse_named_links(html_path: Path, name_to_url_only_govau: bool = False) -> dict[str, str]:
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    # Prefer main content
    root = soup.find("main") or soup
    out: dict[str, str] = {}
    for a in root.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        href = a.get("href") or ""
        if not text or not href:
            continue
        url = href.strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            continue
        host = urlparse(url).netloc.lower()
        # Official body sites only — skip in-page nav and social
        if any(
            x in url.lower()
            for x in (
                "facebook.com",
                "twitter.com",
                "x.com",
                "linkedin.com",
                "instagram.com",
                "youtube.com",
                "javascript:",
            )
        ):
            continue
        # Reject generic portal pages that are not the entity site
        if "tas.gov.au/jobs/" in url.lower():
            continue
        key = norm_name(text)
        if not key:
            continue
        # Keep first official-looking URL
        if key not in out:
            out[key] = normalise_url(url)
        # also key without parenthetical
        bare = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
        if bare and norm_name(bare) not in out:
            out[norm_name(bare)] = normalise_url(url)
    return out


def load_qld_websites() -> dict[str, str]:
    d = parse_named_links(SRC / "qld-ministers-departments.html")
    # Official page labels the service "Queensland Police" but the AAO
    # administrative unit is "Queensland Police Service".
    if "QUEENSLAND POLICE" in d and "QUEENSLAND POLICE SERVICE" not in d:
        d["QUEENSLAND POLICE SERVICE"] = d["QUEENSLAND POLICE"]
    return d


def load_act_websites() -> dict[str, str]:
    return parse_named_links(SRC / "act-directorates.html")


def website_is_confident(url: str) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower().lstrip("www.")
    if not host:
        return False
    # official Australian government / education / known territory-owned
    if host.endswith(".gov.au") or host.endswith(".edu.au"):
        return True
    # A few official ACT/NT/Icon sites use .com.au and are taken from the
    # official directory page itself — allow only when already sourced.
    return False


def pick_website(name: str, jurisdiction: str, source_url: str, directory: dict[str, str]) -> str:
    if source_url:
        # WA / AGOR already-provided
        return source_url
    if not directory:
        return ""
    for v in name_variants(name):
        url = directory.get(v, "")
        if url and (website_is_confident(url) or jurisdiction in {"ACT", "Queensland"}):
            # ACT directory includes a handful of official .com.au sites
            # listed on act.gov.au/directorates-and-agencies; accept those
            # only on an exact/high name match against that page.
            if jurisdiction == "ACT" and not website_is_confident(url):
                if v == norm_name(name) or v in {norm_name(k) for k in [name]}:
                    return url
            else:
                return url
        if url and website_is_confident(url):
            return url
    # exact only
    url = directory.get(norm_name(name), "")
    if url and (website_is_confident(url) or jurisdiction in {"ACT"}):
        return url
    return ""


def attach_agor_to_commonwealth(base_rows: list[dict], agor_rows: list[dict]) -> dict[int, dict]:
    """Map each Commonwealth base row index to its AGOR record.

    Titles are unique except four bodies that appear twice (primary body and
    statutory office-holder). Match leftover rows on Title + Classification +
    Type of Body, then Title alone in file order.
    """
    unused = list(agor_rows)
    mapping: dict[int, dict] = {}

    def take(pred):
        for i, rec in enumerate(unused):
            if pred(rec):
                return unused.pop(i)
        return None

    def class_key(classification: str, typ: str) -> str:
        a = (classification or "").strip()
        b = (typ or "").strip()
        if a and b:
            return f"{a} - {b}"
        return a or b

    for i, row in enumerate(base_rows):
        if row["Jurisdiction"] != "Commonwealth":
            continue
        title = row["Entity name"].strip()
        want = (row.get("Entity type/classification") or "").strip()
        rec = take(
            lambda r, t=title, w=want: (r.get("Title") or "").strip() == t
            and class_key(r.get("Classification"), r.get("Type of Body")) == w
        )
        if rec is None:
            rec = take(lambda r, t=title: (r.get("Title") or "").strip() == t)
        if rec is None:
            continue
        mapping[i] = rec
    if unused:
        print(f"WARNING: {len(unused)} unmatched AGOR rows", file=sys.stderr)
    return mapping


def names_compatible(entity_name: str, abr_rec: dict) -> bool:
    ev = set(name_variants(entity_name))
    names = [abr_rec.get("name") or ""] + list(abr_rec.get("other_names") or [])
    av = set()
    for n in names:
        av.update(name_variants(n))
    if ev & av:
        return True
    # token overlap: all significant tokens of the shorter name appear in the longer
    def tokens(s: str) -> set[str]:
        stop = {"AND", "OF", "THE", "FOR", "IN", "A", "AN", "INC", "INCORPORATED"}
        return {t for t in norm_name(s).split() if t not in stop and len(t) > 1}

    et = tokens(entity_name)
    for n in names:
        at = tokens(n)
        if not et or not at:
            continue
        shorter, longer = (et, at) if len(et) <= len(at) else (at, et)
        if shorter <= longer and len(shorter) >= 2:
            return True
    return False


def enrich_row(
    row: dict,
    agor_rec: dict | None,
    wa: dict,
    nsw: dict,
    vic: dict,
    sa_abn: dict,
    qld_web: dict,
    act_web: dict,
    by_abn: dict,
    by_state,
    by_all,
) -> dict:
    out = {c: "" for c in OUT_COLS}
    juris = row["Jurisdiction"]
    name = row["Entity name"].strip()
    out["Jurisdiction"] = juris
    out["Source name"] = row["Source name"]
    out["Source URL"] = row["Source URL"]
    out["Source date"] = row["Source date"]

    if juris == "Commonwealth" and agor_rec:
        for c in AGOR_COLS:
            val = agor_rec.get(c, "")
            if val is None:
                val = ""
            out[c] = str(val).strip()
        if out["ABN"]:
            out["ABN"] = format_abn(out["ABN"])
            out["ABN match confidence"] = "exact"
        if out["Website Address"]:
            out["Website Address"] = normalise_url(out["Website Address"])
        return out

    # State / territory
    out["Title"] = name
    out["Portfolio"] = (row.get("Portfolio/Department") or "").strip()
    classification = (row.get("Entity type/classification") or "").strip()
    out["Classification"] = classification

    key = norm_name(name)

    if juris == "WA":
        rec = wa.get(key)
        if rec:
            out["Head Office Street Address"] = rec["street"]
            out["Head Office Suburb"] = rec["suburb"]
            out["Head Office State"] = rec["state"]
            out["Head Office Postcode"] = str(rec["postcode"] or "").replace(".0", "")
            if rec["street"] or rec["suburb"]:
                out["Head Office Country"] = "Australia"
            out["Website Address"] = rec["website"]
            out["Contact telephone"] = rec["phone"]
            out["Generic agency email"] = rec["email"] or rec["ceo_email"]

    if juris == "NSW":
        rec = nsw.get(key)
        if rec:
            if rec["legislation"]:
                # NSW source gives the instrument, not a yes/no established-by code
                out["Established by/Under More Info"] = rec["legislation"]
                if re.search(r"\bAct\b|\bRegulation\b|\bOrdinance\b", rec["legislation"], re.I):
                    out["Established By / Under"] = "Act / Regulation"
            if rec["accountable_authority"]:
                out["Accountable Authority"] = rec["accountable_authority"]

    if juris == "Victoria":
        rec = vic.get(key)
        if rec and rec["body_type"]:
            out["Type of Body"] = rec["body_type"]

    # SA / TAS / NT / QLD classifications already sit in Classification.
    # Where the value is clearly a GFS sector, also copy to the GFS column.
    gfs_map = {
        "general government": "General Government Sector",
        "general government sector": "General Government Sector",
        "public non-financial corporations": "Public Non-Financial Corporation",
        "public non-financial corporation": "Public Non-Financial Corporation",
        "public financial corporations": "Public Financial Corporation",
        "public financial corporation": "Public Financial Corporation",
    }
    if classification.lower() in gfs_map:
        out["GFS Sector Classification"] = gfs_map[classification.lower()]

    # ABN: prefer a source-provided ABN if it verifies against ABR
    if juris == "SA":
        src = sa_abn.get(key)
        # also try variants
        if not src:
            for v in name_variants(name):
                if v in sa_abn:
                    src = sa_abn[v]
                    break
        if src and src["abn"]:
            rec = by_abn.get(digits_abn(src["abn"]))
            if rec and is_gov_type(rec.get("type") or "") and names_compatible(name, rec):
                rec_state = (rec.get("state") or "").upper()
                if rec_state in {"", "SA"}:
                    out["ABN"] = format_abn(rec["abn"])
                    out["ABN match confidence"] = "exact"

    if not out["ABN"]:
        abn, conf, rec = match_abn(name, juris, by_state, by_all, allow_allied=False)
        if abn:
            out["ABN"] = abn
            out["ABN match confidence"] = conf

    # Website from official directory pages if the source didn't supply one
    directory = {}
    if juris == "Queensland":
        directory = qld_web
    elif juris == "ACT":
        directory = act_web
    if not out["Website Address"]:
        out["Website Address"] = pick_website(name, juris, "", directory)
    elif out["Website Address"]:
        out["Website Address"] = normalise_url(out["Website Address"])

    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in OUT_COLS})


def fill_rates(rows: list[dict]) -> dict:
    juris_order = [
        "Commonwealth",
        "NSW",
        "Victoria",
        "Queensland",
        "WA",
        "SA",
        "Tasmania",
        "ACT",
        "NT",
        "All",
    ]
    cols_of_interest = [
        "ABN",
        "Website Address",
        "Portfolio",
        "Classification",
        "Type of Body",
        "GFS Sector Classification",
        "Established By / Under",
        "Established by/Under More Info",
        "Head Office Street Address",
        "Head Office Suburb",
        "Head Office State",
        "Head Office Postcode",
        "Accountable Authority",
        "Contact telephone",
        "Generic agency email",
        "Description",
        "Creation Date",
        "Established By / Under",
        "Annual Report Prepared and Tabled?",
        "Annual Reports",
        "Max Number of Board / Committee Members",
        "Board / Committee Appointed by",
        "Paid Members?",
    ]
    out: dict[str, dict] = {}
    groups = {"All": rows}
    for r in rows:
        groups.setdefault(r["Jurisdiction"], []).append(r)
    for j in juris_order:
        chunk = groups.get(j, [])
        rec = {"rows": len(chunk)}
        for c in cols_of_interest:
            n = sum(1 for r in chunk if (r.get(c) or "").strip())
            rec[c] = {"n": n, "pct": round(100.0 * n / len(chunk), 1) if chunk else 0.0}
        # ABN confidence breakdown
        confs = Counter_safe(chunk)
        rec["ABN confidence"] = confs
        out[j] = rec
    return out


def Counter_safe(chunk):
    counts = {"exact": 0, "high": 0, "blank": 0}
    for r in chunk:
        c = (r.get("ABN match confidence") or "").strip()
        if c in counts:
            counts[c] += 1
        else:
            counts["blank"] += 1
    return counts


SOURCES_OUT = [
    {
        "Jurisdiction": "Commonwealth",
        "Source name": "Australian Government Organisations Register (AGOR) 2026-09-30",
        "URL": "https://data.gov.au/data/dataset/c77cface-69aa-4dd0-b99f-b065dc33c8e6/resource/6d58f54c-8f24-4b2c-a819-c22f71c39ca1/download/agor-2026-09-30.csv",
        "Date": "30 September 2026",
        "Format": "CSV",
        "Coverage notes": "All 1,372 Commonwealth bodies on the Department of Finance AGOR snapshot (departments, agencies, boards and other AGOR classifications). Landing page: https://data.gov.au/data/dataset/australian-government-organisations-register. AGOR columns are copied through in full.",
        "Row count": "1372",
    },
    {
        "Jurisdiction": "NSW",
        "Source name": "NSW Treasury GSF Agency List",
        "URL": "https://www.nsw.gov.au/sites/default/files/noindex/2026-06/nsw-treasury-gsf-agency-list_1.xlsx",
        "Date": "March 2026",
        "Format": "XLSX",
        "Coverage notes": "Entities treated as GSF agencies under the Government Sector Finance Act 2018, including departments, statutory bodies, state-owned corporations, integrity agencies, universities and controlled entities. Treasury describes the list as indicative and not real-time. Used for portfolio, GSF classification, relevant legislation (Established by/Under More Info) and Accountable Authority. Guide: https://www.nsw.gov.au/departments-and-agencies/nsw-treasury/documents-library/gsf-agency-list-guide (publication date 31 March 2026; file is in a June 2026 folder).",
        "Row count": "404",
    },
    {
        "Jurisdiction": "Victoria",
        "Source name": "VPSC list of public sector employers (19 October 2026)",
        "URL": "https://www.vpsc.vic.gov.au/files/2026-10/Spreadsheet%20-%20list%20of%20employers%2019%20October%202026.csv",
        "Date": "19 October 2026",
        "Format": "CSV",
        "Coverage notes": "Victorian public sector employers (public service and public entities, including health services and TAFEs), with portfolio and body type (mapped to Type of Body). Not every public entity (non-employer bodies are out of scope). Live list: https://www.vpsc.vic.gov.au/about-public-sector/list-public-sector-employers",
        "Row count": "258",
    },
    {
        "Jurisdiction": "Queensland",
        "Source name": "Administrative Arrangements Order (No. 1) 2026",
        "URL": "https://www.qld.gov.au/__data/assets/word_doc/0025/908413/administrative-arrangements-order-no.-1-2026.docx",
        "Date": "3 July 2026",
        "Format": "DOCX",
        "Coverage notes": "Administrative units listed in the Order (departments and a number of other units such as Queensland Health, Queensland Police Service, Public Sector Commission). Gazetted 3 July 2026; made 2 July 2026. This is not a full statutory-bodies register. PDF: https://www.qld.gov.au/__data/assets/pdf_file/0023/908411/administrative-arrangements-order-no.-1-2026.pdf",
        "Row count": "26",
    },
    {
        "Jurisdiction": "Queensland",
        "Source name": "Queensland ministers and departments page",
        "URL": "https://www.qld.gov.au/government/premier-ministers-departments/ministers-departments",
        "Date": "24 October 2026",
        "Format": "HTML",
        "Coverage notes": "Agencies named on the official ministers-and-departments page (including some bodies that sit beside departments, e.g. Trade and Investment Queensland and Arts Queensland). Used to supplement the AAO administrative-units list and to fill official Website Address values where the page links the agency name to its site. Not a comprehensive register of all statutory bodies.",
        "Row count": "2",
    },
    {
        "Jurisdiction": "WA",
        "Source name": "WA Public Sector Commission government sector mailing list",
        "URL": "https://www.wa.gov.au/system/files/2026-11/government-sector-mailing-list.xlsx",
        "Date": "11 November 2026",
        "Format": "XLSX",
        "Coverage notes": "Public sector agencies (departments, SES and non-SES organisations) and Public Sector Management Act 1994 Schedule 1 entities, including public universities, government trading enterprises, local governments and other Schedule 1 bodies. Used for head-office address, Website Address, contact telephone and generic agency/CEO email. Local governments are included because they appear in the source list (they have telephone and CEO email but no website or street address in this file). Page: https://www.wa.gov.au/government/publications/government-sector-mailing-list",
        "Row count": "290",
    },
    {
        "Jurisdiction": "SA",
        "Source name": "SA 2026-27 Budget Statement, Appendix D – South Australian state public sector organisations",
        "URL": "https://www.treasury.sa.gov.au/__data/assets/pdf_file/0006/1419036/2026-27-Budget-Statement.pdf",
        "Date": "4 June 2026",
        "Format": "PDF (pp. 168–169)",
        "Coverage notes": "Government-controlled entities grouped as general government, public non-financial corporations and public financial corporations, as at the 2026-27 Budget. Parsed from a two-column PDF layout. GFS grouping is copied to Classification and GFS Sector Classification. Budget page: https://www.treasury.sa.gov.au/budget/current-budget",
        "Row count": "114",
    },
    {
        "Jurisdiction": "SA",
        "Source name": "Administrative units of the Public Service of South Australia",
        "URL": "https://www.legislation.sa.gov.au/__data/assets/pdf_file/0011/1398611/2026.03.25-Administrative-Units.pdf",
        "Date": "25 March 2026",
        "Format": "PDF",
        "Coverage notes": "Current public service administrative units (departments and attached offices) only. The PDF's historical/abolished units section was excluded. Entities already listed in Budget Appendix D were deduplicated, preferring Appendix D as the source. Index: https://www.legislation.sa.gov.au/lists-and-index-to-sa-legislation/administrative-units",
        "Row count": "1",
    },
    {
        "Jurisdiction": "SA",
        "Source name": "Shared Services SA eInvoicing ABN list (v8.0)",
        "URL": "https://www.sharedservices.sa.gov.au/documents/financial-services/eInvoice_ABNsv8.0.xlsx",
        "Date": "Accessed 13 November 2026",
        "Format": "XLSX",
        "Coverage notes": "Name and ABN for SA government agencies that use eInvoicing. Used only as a candidate ABN: the number is accepted only when the ABR bulk extract confirms an Active government-entity record in South Australia whose name matches the catalogue entity. Older or renamed entries are left unmatched rather than forced.",
        "Row count": "",
    },
    {
        "Jurisdiction": "Tasmania",
        "Source name": "Financial Management Act 2016, Schedule 1 – General Government Sector Agencies",
        "URL": "https://www.legislation.tas.gov.au/view/whole/html/inforce/current/act-2016-042",
        "Date": "8 October 2026",
        "Format": "HTML (in-force)",
        "Coverage notes": "Statutory general government sector agencies in Schedule 1 Part 1 (government agencies) and Part 2 (legislative agencies), current as at the last applied amendment (No. 30 of 2025, 8 October 2026).",
        "Row count": "27",
    },
    {
        "Jurisdiction": "Tasmania",
        "Source name": "Tasmanian State Service Careers – Our agencies",
        "URL": "https://www.tas.gov.au/jobs/work-with-us/about-us/our-agencies",
        "Date": "7 May 2026",
        "Format": "HTML",
        "Coverage notes": "Named State Service departments and state authorities on the careers 'Our agencies' page. Used because the DPAC 'About the Tasmanian State Service' page (https://www.dpac.tas.gov.au/working-in-the-state-service/about-the-tasmanian-state-service, modified 10 November 2026) states there are 18 agencies (nine departments and nine state authorities) but does not name them. Entity names were used; career-page URLs were not treated as official websites. Entities already in FMA Schedule 1 were deduplicated, preferring the FMA as the source. The page names 17 agencies (plus Service Tasmania, which was treated as a service brand and omitted).",
        "Row count": "4",
    },
    {
        "Jurisdiction": "ACT",
        "Source name": "ACT Government – Directorates and agencies",
        "URL": "https://www.act.gov.au/directorates-and-agencies",
        "Date": "23 April 2026",
        "Format": "HTML",
        "Coverage notes": "Eight directorates, listed public sector bodies and statutory authorities, and Icon Water (territory-owned corporation). Official Website Address values are taken from the agency links on this page (including a small number of official .com.au / .edu.au sites listed there). The ACT Directory (directory.act.gov.au) was not used because that site warns it still reflects pre-1 July 2025 structures.",
        "Row count": "35",
    },
    {
        "Jurisdiction": "NT",
        "Source name": "Administrative Arrangements Order 2026, Schedule 1 – Nomination of Agencies",
        "URL": "https://legislation.nt.gov.au/api/sitecore/Act/PDF?id=11575",
        "Date": "1 June 2026",
        "Format": "PDF",
        "Coverage notes": "Agencies nominated in Schedule 1: Part 1 (Financial Management Act and Public Sector Employment and Management Act), Part 2 (Financial Management Act only) and Part 3 (Public Sector Employment and Management Act only). Made 27 May 2026; commenced and gazetted S41 on 1 June 2026. Does not attempt to list every non-agency body mentioned in Schedule 2. The Order does not publish ABNs or websites.",
        "Row count": "27",
    },
    {
        "Jurisdiction": "All",
        "Source name": "ABR ABN Bulk Extract (11 November 2026)",
        "URL": "https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e",
        "Date": "11 November 2026",
        "Format": "XML (ZIP, two parts)",
        "Coverage notes": "Australian Business Register public bulk extract on data.gov.au (CC BY 3.0 AU), files public_split_1_10.zip and public_split_11_20.zip dated 11 November 2026. Used to look up ABNs for non-Commonwealth entities. Only Active (ABN status ACT) records whose EntityTypeInd is a government type (CG*, SG*, TG*, LG*, plus GOV, SSA, STA, TER, LOC) were eligible. A match is accepted only when the entity name matches confidently and the recorded state agrees with the jurisdiction (or, for a long distinctive name, the match is unique nationally). Confidence is 'exact' for a unique in-state match on the normalised legal/trading name, or 'high' for a unique match after light name-variant normalisation. Ambiguous or weak hits are left blank. Other entity types (for example Australian Public Company, Other Incorporated Entity) are not used, so universities and some state-owned corporations may have no ABN even when one exists. Websites are not present in the extract. Resource parts: https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/0ae4d427-6fa8-4d40-8e76-c6909b5a071b and https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/635fcb95-7864-4509-9fa7-a62a6e32b62d",
        "Row count": "",
    },
    {
        "Jurisdiction": "All",
        "Source name": "Combined Organisations tab (after intra-jurisdiction deduplication and enrichment)",
        "URL": "",
        "Date": "",
        "Format": "",
        "Coverage notes": "",
        "Row count": "2560",
    },
]


# Fix the typo in WA URL — the previously used URL was /government_sector_mailing_list.xlsx
# Keep the working URL from the earlier dataset (underscores, 2026-11 folder).
SOURCES_OUT[5]["URL"] = "https://www.wa.gov.au/system/files/2026-11/government_sector_mailing_list.xlsx"


def write_sources(path: Path, rows: list[dict]) -> None:
    # update combined row count just in case
    sources = [dict(s) for s in SOURCES_OUT]
    sources[-1]["Row count"] = str(len(rows))
    cols = ["Jurisdiction", "Source name", "URL", "Date", "Format", "Coverage notes", "Row count"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for s in sources:
            w.writerow(s)


def write_xlsx(path: Path, org_rows: list[dict], fill: dict) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Organisations"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    thin = Border(
        left=Side(style="thin", color="D0D0D0"),
        right=Side(style="thin", color="D0D0D0"),
        top=Side(style="thin", color="D0D0D0"),
        bottom=Side(style="thin", color="D0D0D0"),
    )
    wrap = Alignment(vertical="center", wrap_text=True)
    for col, name in enumerate(OUT_COLS, 1):
        cell = ws.cell(1, col, name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = thin
    for r_i, row in enumerate(org_rows, 2):
        for c_i, name in enumerate(OUT_COLS, 1):
            cell = ws.cell(r_i, c_i, row.get(name, ""))
            cell.alignment = wrap
            cell.border = thin
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(OUT_COLS))}{len(org_rows)+1}"
    # reasonable widths
    widths = {
        "Jurisdiction": 16,
        "Title": 46,
        "Portfolio": 36,
        "Classification": 32,
        "Type of Body": 28,
        "ABN": 16,
        "Website Address": 40,
        "Source name": 40,
        "Source URL": 36,
        "Head Office Street Address": 36,
        "Established by/Under More Info": 36,
        "Accountable Authority": 28,
        "Description": 40,
    }
    for i, name in enumerate(OUT_COLS, 1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(name, 18)
    ws.row_dimensions[1].height = 30
    ws.auto_filter.ref = f"A1:{get_column_letter(len(OUT_COLS))}{max(2, len(org_rows)+1)}"

    # Sources tab
    ws2 = wb.create_sheet("Sources")
    src_cols = ["Jurisdiction", "Source name", "URL", "Date", "Format", "Coverage notes", "Row count"]
    for col, name in enumerate(src_cols, 1):
        cell = ws2.cell(1, col, name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    sources = [dict(s) for s in SOURCES_OUT]
    sources[-1]["Row count"] = str(len(org_rows))
    for r_i, s in enumerate(sources, 2):
        for c_i, name in enumerate(src_cols, 1):
            ws2.cell(r_i, c_i, s.get(name, "")).alignment = wrap
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:G{len(sources)+1}"
    for i, w in enumerate([16, 50, 50, 20, 18, 70, 12], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # Fill rates tab (useful in the Sheet; also documented in the README)
    ws3 = wb.create_sheet("Fill rates")
    interest = [
        "ABN",
        "Website Address",
        "Portfolio",
        "Classification",
        "Type of Body",
        "Established by/Under More Info",
        "Head Office Street Address",
        "Accountable Authority",
        "Contact telephone",
        "Generic agency email",
        "Description",
        "Head Office State",
        "Head Office Postcode",
        "Creation Date",
        "Established By / Under",
        "Annual Report Prepared and Tabled?",
        "Annual Reports",
        "Max Number of Board / Committee Members",
        "Board / Committee Appointed by",
        "Paid Members?",
    ]
    headers = ["Jurisdiction", "Rows"] + [f"{c} %" for c in interest] + ["ABN exact", "ABN high", "ABN blank"]
    for col, name in enumerate(headers, 1):
        cell = ws3.cell(1, col, name)
        cell.font = header_font
        cell.fill = header_fill
    order = [
        "Commonwealth",
        "NSW",
        "Victoria",
        "Queensland",
        "WA",
        "SA",
        "Tasmania",
        "ACT",
        "NT",
        "All",
    ]
    for r_i, j in enumerate(order, 2):
        rec = fill[j]
        ws3.cell(r_i, 1, j)
        ws3.cell(r_i, 2, rec["rows"])
        for c_i, c in enumerate(interest, 3):
            ws3.cell(r_i, c_i, rec[c]["pct"])
        conf = rec["ABN confidence"]
        ws3.cell(r_i, 3 + len(interest), conf["exact"])
        ws3.cell(r_i, 4 + len(interest), conf["high"])
        ws3.cell(r_i, 5 + len(interest), conf["blank"])
    ba = globals().get("BEFORE_AFTER")
    if ba:
        r0 = len(order) + 4
        ws3.cell(r0, 1, ba["title"]).font = header_font
        hdr = ["Column", "Filled before", "Filled after", "Before %", "After %", "Added"]
        for c_i, name in enumerate(hdr, 1):
            cell = ws3.cell(r0 + 1, c_i, name); cell.font = header_font; cell.fill = header_fill
        for k, (col, b, a, n) in enumerate(ba["rows"], r0 + 2):
            for c_i, v in enumerate([col, b, a, round(100 * b / n, 1), round(100 * a / n, 1), a - b], 1):
                ws3.cell(k, c_i, v)
    ws3.freeze_panes = "A2"
    for i in range(1, len(headers) + 1):
        ws3.column_dimensions[get_column_letter(i)].width = 16
    ws3.column_dimensions["A"].width = 16

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


BY_JURIS_FILES = {
    "Commonwealth": "commonwealth",
    "NSW": "nsw",
    "Victoria": "victoria",
    "Queensland": "queensland",
    "WA": "wa",
    "SA": "sa",
    "Tasmania": "tasmania",
    "ACT": "act",
    "NT": "nt",
}


def main() -> None:
    ensure_base_snapshot()
    print("Loading base rows...", flush=True)
    base = load_base_rows()
    if "Entity name" not in base[0]:
        raise SystemExit("organisations.csv is already enriched and no organisations_base.csv snapshot was found")
    print(f"  {len(base)} rows", flush=True)
    print("Loading AGOR...", flush=True)
    agor_rows = load_agor()
    agor_map = attach_agor_to_commonwealth(base, agor_rows)
    print(f"  {len(agor_rows)} AGOR rows, {len(agor_map)} mapped", flush=True)
    print("Loading source detail overlays...", flush=True)
    wa = load_wa_details()
    nsw = load_nsw_details()
    vic = load_vic_details()
    sa_abn = load_sa_einvoice()
    qld_web = load_qld_websites()
    act_web = load_act_websites()
    print(f"  WA={len(wa)} NSW={len(nsw)} VIC={len(vic)} SA eInvoice={len(sa_abn)} QLD web={len(qld_web)} ACT web={len(act_web)}", flush=True)
    print("Loading ABR government-entity index...", flush=True)
    by_abn, by_state, by_all = load_abr()
    print(f"  {len(by_abn):,} active gov/allied ABNs", flush=True)

    enriched = []
    for i, row in enumerate(base):
        rec = enrich_row(
            row,
            agor_map.get(i),
            wa,
            nsw,
            vic,
            sa_abn,
            qld_web,
            act_web,
            by_abn,
            by_state,
            by_all,
        )
        enriched.append(rec)
        if (i + 1) % 500 == 0:
            print(f"  enriched {i+1}/{len(base)}", flush=True)

    print("Writing outputs...", flush=True)
    write_csv(DATA / "organisations.csv", enriched)
    for juris, fname in BY_JURIS_FILES.items():
        chunk = [r for r in enriched if r["Jurisdiction"] == juris]
        write_csv(DATA / "by-jurisdiction" / f"{fname}.csv", chunk)
    write_sources(DATA / "sources.csv", enriched)
    rates = fill_rates(enriched)
    REPORT.write_text(json.dumps(rates, indent=2))
    xlsx_path = Path("/workspace/agor-sheet/Australian_Government_Organisations_All_Jurisdictions_Nov_2026.xlsx")
    write_xlsx(xlsx_path, enriched, rates)
    # also copy into the repo
    write_xlsx(ROOT / "data" / "Australian_Government_Organisations_All_Jurisdictions_Nov_2026.xlsx", enriched, rates)

    print("\nFill rates (ABN %, Website %):", flush=True)
    for j, rec in rates.items():
        print(
            f"  {j:15} n={rec['rows']:5}  ABN {rec['ABN']['n']:5} ({rec['ABN']['pct']:5.1f}%)  "
            f"web {rec['Website Address']['n']:5} ({rec['Website Address']['pct']:5.1f}%)  "
            f"conf={rec['ABN confidence']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
