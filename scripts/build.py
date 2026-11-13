#!/usr/bin/env python3
"""Build combined Australian government organisations workbook."""
from __future__ import annotations

import csv
import html
import re
import zipfile
from collections import OrderedDict, Counter
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from bs4 import BeautifulSoup
from lxml import etree

SRC = Path("/workspace/agor-sheet/sources")
OUT = Path("/workspace/agor-sheet/Australian_Government_Organisations_All_Jurisdictions_Nov_2026.xlsx")

COLS = [
    "Jurisdiction",
    "Entity name",
    "Portfolio/Department",
    "Entity type/classification",
    "Source name",
    "Source URL",
    "Source date",
]

# Source metadata used both on entity rows and the Sources tab
SOURCES = {
    "agor": {
        "jurisdiction": "Commonwealth",
        "name": "Australian Government Organisations Register (AGOR) 2026-09-30",
        "url": "https://data.gov.au/data/dataset/c77cface-69aa-4dd0-b99f-b065dc33c8e6/resource/6d58f54c-8f24-4b2c-a819-c22f71c39ca1/download/agor-2026-09-30.csv",
        "date": "30 September 2026",
        "format": "CSV",
        "coverage": "All 1,372 Commonwealth bodies on the Department of Finance AGOR snapshot (departments, agencies, boards and other AGOR classifications). Landing page: https://data.gov.au/data/dataset/australian-government-organisations-register",
    },
    "nsw": {
        "jurisdiction": "NSW",
        "name": "NSW Treasury GSF Agency List",
        "url": "https://www.nsw.gov.au/sites/default/files/noindex/2026-06/nsw-treasury-gsf-agency-list_1.xlsx",
        "date": "March 2026",
        "format": "XLSX",
        "coverage": "Entities treated as GSF agencies under the Government Sector Finance Act 2018, including departments, statutory bodies, state-owned corporations, integrity agencies, universities and controlled entities. Treasury describes the list as indicative and not real-time. Guide: https://www.nsw.gov.au/departments-and-agencies/nsw-treasury/documents-library/gsf-agency-list-guide (publication date 31 March 2026; file is in a June 2026 folder).",
    },
    "vic": {
        "jurisdiction": "Victoria",
        "name": "VPSC list of public sector employers (19 October 2026)",
        "url": "https://www.vpsc.vic.gov.au/files/2026-10/Spreadsheet%20-%20list%20of%20employers%2019%20October%202026.csv",
        "date": "19 October 2026",
        "format": "CSV",
        "coverage": "Victorian public sector employers (public service and public entities, including health services and TAFEs), with portfolio and body type. Not every public entity (non-employer bodies are out of scope). Live list: https://www.vpsc.vic.gov.au/about-public-sector/list-public-sector-employers",
    },
    "qld_aao": {
        "jurisdiction": "Queensland",
        "name": "Administrative Arrangements Order (No. 1) 2026",
        "url": "https://www.qld.gov.au/__data/assets/word_doc/0025/908413/administrative-arrangements-order-no.-1-2026.docx",
        "date": "3 July 2026",
        "format": "DOCX",
        "coverage": "Administrative units listed in the Order (departments and a number of other units such as Queensland Health, Queensland Police Service, Public Sector Commission). Gazetted 3 July 2026; made 2 July 2026. This is not a full statutory-bodies register. PDF: https://www.qld.gov.au/__data/assets/pdf_file/0023/908411/administrative-arrangements-order-no.-1-2026.pdf",
    },
    "qld_html": {
        "jurisdiction": "Queensland",
        "name": "Queensland ministers and departments page",
        "url": "https://www.qld.gov.au/government/premier-ministers-departments/ministers-departments",
        "date": "24 October 2026",
        "format": "HTML",
        "coverage": "Agencies named on the official ministers-and-departments page (including some bodies that sit beside departments, e.g. Trade and Investment Queensland and Arts Queensland). Not a comprehensive register of all statutory bodies. Used to supplement the AAO administrative-units list; duplicates were removed.",
    },
    "wa": {
        "jurisdiction": "WA",
        "name": "WA Public Sector Commission government sector mailing list",
        "url": "https://www.wa.gov.au/system/files/2026-11/government_sector_mailing_list.xlsx",
        "date": "11 November 2026",
        "format": "XLSX",
        "coverage": "Public sector agencies (departments, SES and non-SES organisations) and Public Sector Management Act 1994 Schedule 1 entities, including public universities, government trading enterprises, local governments and other Schedule 1 bodies. Local governments are included because they appear in the source list; filter Entity type/classification to exclude them if not required. Page: https://www.wa.gov.au/government/publications/government-sector-mailing-list",
    },
    "sa_appd": {
        "jurisdiction": "SA",
        "name": "SA 2026-27 Budget Statement, Appendix D – South Australian state public sector organisations",
        "url": "https://www.treasury.sa.gov.au/__data/assets/pdf_file/0006/1419036/2026-27-Budget-Statement.pdf",
        "date": "4 June 2026",
        "format": "PDF (pp. 168–169)",
        "coverage": "Government-controlled entities grouped as general government, public non-financial corporations and public financial corporations, as at the 2026-27 Budget. Parsed from a two-column PDF layout. Budget page: https://www.treasury.sa.gov.au/budget/current-budget",
    },
    "sa_units": {
        "jurisdiction": "SA",
        "name": "Administrative units of the Public Service of South Australia",
        "url": "https://www.legislation.sa.gov.au/__data/assets/pdf_file/0011/1398611/2026.03.25-Administrative-Units.pdf",
        "date": "25 March 2026",
        "format": "PDF",
        "coverage": "Current public service administrative units (departments and attached offices) only. The PDF's historical/abolished units section was excluded. Entities already listed in Budget Appendix D were deduplicated, preferring Appendix D as the source. Index: https://www.legislation.sa.gov.au/lists-and-index-to-sa-legislation/administrative-units",
    },
    "tas_fma": {
        "jurisdiction": "Tasmania",
        "name": "Financial Management Act 2016, Schedule 1 – General Government Sector Agencies",
        "url": "https://www.legislation.tas.gov.au/view/whole/html/inforce/current/act-2016-042",
        "date": "8 October 2026",
        "format": "HTML (in-force)",
        "coverage": "Statutory general government sector agencies in Schedule 1 Part 1 (government agencies) and Part 2 (legislative agencies), current as at the last applied amendment (No. 30 of 2025, 8 October 2026).",
    },
    "tas_agencies": {
        "jurisdiction": "Tasmania",
        "name": "Tasmanian State Service Careers – Our agencies",
        "url": "https://www.tas.gov.au/jobs/work-with-us/about-us/our-agencies",
        "date": "7 May 2026",
        "format": "HTML",
        "coverage": "Named State Service departments and state authorities on the careers 'Our agencies' page. Used because the DPAC 'About the Tasmanian State Service' page (https://www.dpac.tas.gov.au/working-in-the-state-service/about-the-tasmanian-state-service, modified 10 November 2026) states there are 18 agencies (nine departments and nine state authorities) but does not name them. Entities already in FMA Schedule 1 were deduplicated, preferring the FMA as the source. The page names 17 agencies (plus Service Tasmania, which was treated as a service brand and omitted).",
    },
    "act": {
        "jurisdiction": "ACT",
        "name": "ACT Government – Directorates and agencies",
        "url": "https://www.act.gov.au/directorates-and-agencies",
        "date": "23 April 2026",
        "format": "HTML",
        "coverage": "Eight directorates, listed public sector bodies and statutory authorities, and Icon Water (territory-owned corporation). The ACT Directory (directory.act.gov.au) was not used because that site warns it still reflects pre-1 July 2025 structures.",
    },
    "nt": {
        "jurisdiction": "NT",
        "name": "Administrative Arrangements Order 2026, Schedule 1 – Nomination of Agencies",
        "url": "https://legislation.nt.gov.au/api/sitecore/Act/PDF?id=11575",
        "date": "1 June 2026",
        "format": "PDF",
        "coverage": "Agencies nominated in Schedule 1: Part 1 (Financial Management Act and Public Sector Employment and Management Act), Part 2 (Financial Management Act only) and Part 3 (Public Sector Employment and Management Act only). Made 27 May 2026; commenced and gazetted S41 on 1 June 2026. Does not attempt to list every non-agency body mentioned in Schedule 2.",
    },
}

NSW_PORTFOLIOS = {
    "CCEEW": "Climate Change, Energy, the Environment and Water",
    "CJ": "Communities and Justice",
    "CITHS": "Creative Industries, Tourism, Hospitality and Sport",
    "CS": "Customer Service",
    "Education": "Education",
    "PHI": "Planning, Housing and Infrastructure",
    "PIRD": "Primary Industries and Regional Development",
    "Health": "Health (Ministry of Health)",
    "Integrity": "Integrity Agency",
    "PD": "Premier's Department",
    "SOC": "State Owned Corporations",
    "TCO": "The Cabinet Office",
    "Transport": "Transport",
    "Treasury": "Treasury",
    "Universities": "Universities and their controlled entities",
}

WA_SHEET_TYPE = {
    "Public Sector Leadership Counci": "Department (Public Sector Leadership Council)",
    "Other departments": "Department",
    "SES organisations": "SES organisation",
    "Non-SES organisations": "Non-SES organisation",
    "Schedule 1 -Public universities": "Schedule 1 – Public university",
    "Schedule 1 - GTEs": "Schedule 1 – Government trading enterprise",
    "Schedule 1 - Local government": "Schedule 1 – Local government",
    "Schedule 1 - Others": "Schedule 1 – Other",
}


def clean_ws(s: str | None) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\u00a0", " ").replace("\u202f", " ")
    s = s.replace("\u2011", "-").replace("\u2010", "-").replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\ufeff", "")
    s = re.sub(r"[ \t\r\n]+", " ", s).strip()
    return s


def expand_department_order(name: str) -> str:
    """Turn 'Treasury and Finance, Department of' into 'Department of Treasury and Finance' for matching."""
    n = clean_ws(name)
    m = re.match(r"^(?P<body>.+),\s*(?P<label>Department(?:s)? (?:of|for|the)|Office of the|Office for)\s*$", n, re.I)
    if m:
        label = m.group("label")
        body = m.group("body")
        # 'Premier and Cabinet, Department of the' -> 'Department of the Premier and Cabinet'
        if re.search(r"\bthe$", label, re.I):
            return f"{label} {body}"
        return f"{label} {body}"
    m = re.match(r"^(?P<body>.+),\s*Department of the$", n, re.I)
    if m:
        return f"Department of the {m.group('body')}"
    return n


# Known equivalent names for intra-jurisdiction dedupe only
ALIASES = {
    "audit tasmania": "tasmanian audit office",
    "tasmanian audit office": "tasmanian audit office",
    "queensland police": "queensland police service",
    "queensland police service": "queensland police service",
    "south australia police (south australian police department, sapol)": "south australia police",
    "south australia police south australian police department sapol": "south australia police",
    "south australian police department": "south australia police",
    "green industries sa": "office of green industries sa",
    "office of green industries sa": "office of green industries sa",
}


def dedupe_key(name: str) -> str:
    n = expand_department_order(name).lower()
    n = re.sub(r"[^\w\s&'-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"^(the)\s+", "", n)
    n = ALIASES.get(n, n)
    return n


def make_row(jurisdiction, name, portfolio, typ, source_key):
    src = SOURCES[source_key]
    return {
        "Jurisdiction": jurisdiction,
        "Entity name": clean_ws(name),
        "Portfolio/Department": clean_ws(portfolio),
        "Entity type/classification": clean_ws(typ),
        "Source name": src["name"],
        "Source URL": src["url"],
        "Source date": src["date"],
        "_source_key": source_key,
        "_key": dedupe_key(name),
    }


# ---------- parsers ----------

def parse_agor():
    rows = []
    with open(SRC / "agor-2026-09-30.csv", newline="", encoding="cp1252") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            title = clean_ws(rec.get("Title"))
            if not title:
                continue
            classification = clean_ws(rec.get("Classification"))
            typ = clean_ws(rec.get("Type of Body"))
            parts = [p for p in (classification, typ) if p]
            typ_out = " — ".join(parts)
            rows.append(make_row("Commonwealth", title, rec.get("Portfolio"), typ_out, "agor"))
    return rows


def parse_nsw():
    wb = openpyxl.load_workbook(SRC / "nsw-treasury-gsf-agency-list.xlsx", data_only=True)
    ws = wb.active
    rows = []
    for rec in ws.iter_rows(min_row=2, values_only=True):
        name = clean_ws(rec[0] if rec else "")
        if not name:
            continue
        raw_port = clean_ws(rec[1] if len(rec) > 1 else "")
        portfolio = NSW_PORTFOLIOS.get(raw_port, raw_port)
        typ = clean_ws(rec[2] if len(rec) > 2 else "")
        rows.append(make_row("NSW", name, portfolio, typ, "nsw"))
    return rows


def parse_vic():
    rows = []
    with open(SRC / "vic-vpsc-employers-2026-10-19.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            name = clean_ws(rec.get("Agency"))
            if not name:
                continue
            typ_parts = []
            body = clean_ws(rec.get("Public Sector Body Type"))
            emp = clean_ws(rec.get("Employer type"))
            if body:
                typ_parts.append(body)
            if emp:
                typ_parts.append(f"Employer type: {emp}")
            rows.append(make_row("Victoria", name, rec.get("Portfolio"), " — ".join(typ_parts), "vic"))
    return rows


def parse_wa():
    wb = openpyxl.load_workbook(SRC / "wa-government-sector-mailing-list.xlsx", data_only=True)
    rows = []
    for sheet in wb.sheetnames:
        typ = WA_SHEET_TYPE.get(sheet, sheet)
        ws = wb[sheet]
        headers = [clean_ws(c.value).lower() for c in next(ws.iter_rows(min_row=1, max_row=1))]
        # Agency name should be first column
        for rec in ws.iter_rows(min_row=2, values_only=True):
            name = clean_ws(rec[0] if rec else "")
            if not name or name.lower() == "agency name":
                continue
            rows.append(make_row("WA", name, "", typ, "wa"))
    return rows


W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _docx_cell_text(tc) -> str:
    parts = []
    for node in tc.xpath(".//w:t", namespaces=W_NS):
        piece = node.text or ""
        if parts and piece:
            prev = parts[-1]
            if re.search(r"[A-Za-z0-9,;:]$", prev) and re.search(r"^[A-Za-z0-9(']", piece):
                parts.append(" ")
        parts.append(piece)
    return html.unescape("".join(parts))


def parse_qld_aao():
    z = zipfile.ZipFile(SRC / "qld-aao-no1-2026.docx")
    root = etree.fromstring(z.read("word/document.xml"))
    tables = root.xpath("//w:tbl", namespaces=W_NS)
    # Accumulate unique units with ministers
    units: OrderedDict[str, list[str]] = OrderedDict()
    current_minister = ""
    for tbl in tables:
        rows = tbl.xpath("./w:tr", namespaces=W_NS)
        if not rows:
            continue
        header = [_docx_cell_text(tc).strip() for tc in rows[0].xpath("./w:tc", namespaces=W_NS)]
        if not any("Administrative Unit" in h for h in header):
            continue
        idx = next(i for i, h in enumerate(header) if "Administrative Unit" in h)
        for tr in rows[1:]:
            cells = [_docx_cell_text(tc).strip() for tc in tr.xpath("./w:tc", namespaces=W_NS)]
            if not cells:
                continue
            minister = clean_ws(cells[0]) if cells[0] else current_minister
            if cells[0]:
                current_minister = clean_ws(cells[0])
            unit = clean_ws(cells[idx] if len(cells) > idx else "")
            if not unit:
                continue
            units.setdefault(unit, [])
            if minister and minister not in units[unit]:
                units[unit].append(minister)
    out = []
    for unit, ministers in units.items():
        # Classify roughly
        if unit.lower().startswith("department "):
            typ = "Administrative unit (department)"
        else:
            typ = "Administrative unit"
        out.append(make_row("Queensland", unit, "; ".join(ministers), typ, "qld_aao"))
    return out


def parse_qld_html():
    raw = (SRC / "qld-ministers-departments.html").read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    main = soup.find("main") or soup
    text = main.get_text("\n", strip=True)
    lines = [clean_ws(l) for l in text.splitlines() if clean_ws(l)]
    current_minister = ""
    current_dept = ""
    found = OrderedDict()  # name -> (portfolio, typ)
    i = 0
    while i < len(lines):
        line = lines[i]
        # Minister lines often end with MP and are followed by a 'Minister for...' title
        if re.search(r"\bMP$", line) and "website" not in line.lower():
            # could be a minister name
            if i + 1 < len(lines) and lines[i + 1].lower().startswith("minister") or (
                i + 1 < len(lines) and "Premier" in lines[i + 1]
            ):
                current_minister = lines[i + 1] if not line.endswith("Queensland") else line
                # If this line is "David Crisafulli MP" and next is "The Premier of Queensland"
                if "premier" in lines[i + 1].lower():
                    current_minister = "Premier of Queensland"
                else:
                    current_minister = lines[i + 1]
        if line.lower() in {"department website:", "department website"}:
            if i + 1 < len(lines):
                name = lines[i + 1]
                if name.lower() not in {"contact", "minister website:", "department website:"}:
                    found.setdefault(name, (current_minister or current_dept, "Department"))
                    current_dept = name
        elif line.lower().endswith("website:") and "minister" not in line.lower() and "department" not in line.lower():
            # e.g. "Trade and Investment Queensland website:"
            name = re.sub(r"\s*website:\s*$", "", line, flags=re.I)
            portfolio = current_dept or current_minister
            found.setdefault(name, (portfolio, "Agency"))
        i += 1
    return [make_row("Queensland", n, p, t, "qld_html") for n, (p, t) in found.items()]


_SAFE_END = re.compile(
    r"(?:Department(?:s)? of(?: the)?|Department for|Office of(?: the)?|Office for)$",
    re.I,
)
_INCOMPLETE_END = re.compile(r"(?: and| or| of| the| as| to|,)$", re.I)
_WRAP_HEAD = re.compile(
    r"^(Standards Board|Life)\b|Commission \(trading",
    re.I,
)
_ALREADY_COMPLETE = re.compile(
    r"\b(Commission|Corporation|Commissioner|Assembly|Authority|Board|Trust)\s*(\(|$)",
    re.I,
)


def _is_continuation(prev: str, cur: str) -> bool:
    if not prev or not cur:
        return False
    if prev.count("(") > prev.count(")"):
        return True
    if cur[0].islower() or cur.startswith("("):
        return True
    if re.match(r"^(and|or|of|for|the|as|to|&)\b", cur, re.I):
        return True
    if _INCOMPLETE_END.search(prev) and not _SAFE_END.search(prev):
        return True
    if _WRAP_HEAD.match(cur) and not _ALREADY_COMPLETE.search(prev):
        return True
    return False


def _join_wrapped(parts: list[str]) -> list[str]:
    out: list[str] = []
    for p in parts:
        p = clean_ws(p)
        if not p:
            continue
        if out and _is_continuation(out[-1], p):
            prev = out[-1]
            joiner = "" if prev.endswith("-") or p.startswith((")", ",", ".", "-")) else " "
            out[-1] = clean_ws(prev + joiner + p)
        else:
            out.append(p)
    return out


def parse_sa_appendix_d():
    # Use form-feed paginated layout text
    data = Path("/tmp/sa_budget_ff.txt").read_text(encoding="utf-8", errors="replace")
    pages = data.split("\f")
    # Pages 172-173 in 1-based indexing from earlier inspection
    chunks = []
    for i, p in enumerate(pages, start=1):
        if i in (172, 173) or (
            "General Government Sector" in p and "Adelaide Festival Corporation" in p
        ) or (
            "Public Non-Financial Corporations Sector" in p and "Retail Shop Leases Fund" in p
        ):
            chunks.append(p)
    text = "\n".join(chunks)
    # Determine split column from two-column lines
    starts = []
    for line in text.splitlines():
        m = re.search(r"\S.{10,}\s{4,}(\S)", line)
        if m and not line.startswith(" " * 10):
            # start of right column
            starts.append(m.start(1))
    split_col = Counter(starts).most_common(1)[0][0] if starts else 63

    # Stream left/right with sector tags
    events = []  # (col, text) or ('SECTOR', name)
    for raw in text.splitlines():
        line = raw.rstrip()
        if not clean_ws(line):
            continue
        stripped = clean_ws(line)
        if re.fullmatch(r"(General Government Sector|Public Non-Financial Corporations Sector|Public Financial Corporations Sector)", stripped, re.I):
            events.append(("SECTOR", stripped))
            continue
        # skip headers/footers
        if re.search(r"Appendix D|Budget Statement|Changes to controlled|New entities|Effective |The entities listed|The sectors to which|The government's interest|The government’s interest|100 per cent|listed below is|State Development Coordination|Northern Parklands Act", stripped, re.I):
            continue
        if re.search(r"\bAct\s+\d{4}\b", stripped):
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        left = line[:split_col].rstrip()
        right = line[split_col:].strip() if len(line) > split_col else ""
        if clean_ws(left):
            events.append(("L", left))
        if clean_ws(right):
            events.append(("R", right))

    # Rebuild per sector: all L then all R in document order, but they were interleaved line by line.
    # Collect sequences between sector markers, join wraps within each column separately, then concatenate L then R.
    rows = []
    current_sector = ""
    buf_l: list[str] = []
    buf_r: list[str] = []

    def flush():
        nonlocal buf_l, buf_r
        names = _join_wrapped(buf_l) + _join_wrapped(buf_r)
        for n in names:
            typ = current_sector or ""
            rows.append(make_row("SA", n, "", typ, "sa_appd"))
        buf_l, buf_r = [], []

    for kind, val in events:
        if kind == "SECTOR":
            flush()
            current_sector = val
        elif kind == "L":
            buf_l.append(val)
        else:
            buf_r.append(val)
    flush()
    cleaned = []
    for r in rows:
        n = r["Entity name"]
        if re.search(r"\bAct\s+\d{4}\b", n):
            continue
        if re.search(r"100 per cent|listed below|as at \d|^sector organisations$", n, re.I):
            continue
        if n.lower() == "sector organisations":
            continue
        if len(n) < 5:
            continue
        cleaned.append(r)
    return cleaned


def parse_sa_admin_units():
    text = Path("/tmp/sa_units.txt").read_text(encoding="utf-8", errors="replace")
    # Only current units
    if "Historical information" in text:
        text = text.split("Historical information", 1)[0]
    rows = []
    skip_prefixes = (
        "www.",
        "administrative units",
        "disclaimer",
        "information about",
        "form:",
        "minister:",
        "minister for",
        "continued:",
        "formerly",
        "established:",
        "title altered",
        "attached office",
        "this unit",
        "page ",
    )
    for line in text.splitlines():
        if not line.strip():
            continue
        # Headings are at left margin (little indent) and not metadata
        indent = len(line) - len(line.lstrip(" "))
        if indent > 2:
            continue
        name = clean_ws(line)
        low = name.lower()
        if not name or any(low.startswith(p) for p in skip_prefixes):
            continue
        if re.fullmatch(r"\d+", name) or re.match(r"^as at\b", low) or re.search(r"public service of south australia", low):
            continue
        if name.startswith(("Premier ", "Treasurer", "Attorney-General")) and "Department" not in name:
            continue
        # Classify
        if re.search(r",?\s*Department( for| of| of the)?$", name, re.I) or name.lower().startswith("department "):
            typ = "Administrative unit (department)"
        elif name.lower().startswith("office "):
            typ = "Administrative unit (attached office)"
        else:
            typ = "Administrative unit"
        rows.append(make_row("SA", name, "", typ, "sa_units"))
    return rows


def parse_tas_fma():
    raw = (SRC / "tas-fma-whole.html").read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    text = soup.get_text("\n", strip=True)
    # Isolate Schedule 1
    m = re.search(
        r"SCHEDULE 1\s*-\s*General Government Sector Agencies(.*?)SCHEDULE 2\s*-",
        text,
        re.S | re.I,
    )
    if not m:
        raise RuntimeError("Could not find FMA Schedule 1")
    block = m.group(1)
    part1, part2 = block, ""
    m2 = re.search(r"PART 2\s*-\s*Legislative Agencies(.*)", block, re.S | re.I)
    if m2:
        part1 = block[: m2.start()]
        part2 = m2.group(1)

    skip = re.compile(
        r"^(schedule|part |section|column |\[part|the chief|the commissioner|the director|the person|secretary of|auditor-general|both the clerk|a person appointed|the tasmanfe|the tasmanian|the official|applied:)",
        re.I,
    )

    def agencies_from(part: str) -> list[str]:
        names = []
        for line in part.splitlines():
            t = clean_ws(line)
            if not t:
                continue
            if skip.search(t):
                continue
            if t.startswith("section ") or re.match(r"^No\.\s*\d+", t):
                continue
            # Accountable-authority leftover lines
            if t.lower().startswith(("the ", "secretary ", "auditor-general", "both the", "a person")):
                continue
            if re.match(r"^\d+\s*$", t):
                continue
            # Act titles that leaked
            if t.endswith(" Act") or re.search(r"\bAct\s+\d{4}\b", t):
                continue
            # Too long to be an agency name
            if len(t) > 90:
                continue
            names.append(t)
        return names

    rows = []
    for n in agencies_from(part1):
        typ = "General government sector agency (Schedule 1 Part 1)"
        if n.lower().startswith("department ") or n.lower() in {"building tasmania"}:
            typ = "Department — GGS agency (Schedule 1 Part 1)"
        rows.append(make_row("Tasmania", n, "", typ, "tas_fma"))
    for n in agencies_from(part2):
        rows.append(make_row("Tasmania", n, "", "Legislative agency (Schedule 1 Part 2)", "tas_fma"))
    return rows


def parse_tas_our_agencies():
    raw = (SRC / "tas-our-agencies.html").read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    # Prefer list items under the main/h1 Our agencies
    names = []
    seen = set()
    for li in soup.find_all("li"):
        t = clean_ws(li.get_text(" ", strip=True))
        if not t or t in seen or li.find("ul"):
            continue
        if t in {"Moving to Tasmania", "Other jobs in Tasmania", "Service Tasmania"}:
            continue
        if len(t) > 90:
            continue
        # Keep named agencies only
        if any(
            k in t
            for k in (
                "Department",
                "Tasmania",
                "Authority",
                "Commission",
                "Audit",
                "Brand",
                "Homes",
                "Integrity",
                "Macquarie",
                "Port Arthur",
                "Trustee",
                "Tourism",
                "Building",
                "Environment Protection",
            )
        ):
            seen.add(t)
            names.append(t)
    dept_like = ("Department ", "Building Tasmania", "Audit Tasmania")
    rows = []
    for n in names:
        typ = "State Service department" if n.startswith("Department ") or n in {"Building Tasmania", "Audit Tasmania"} else "State Service state authority"
        rows.append(make_row("Tasmania", n, "", typ, "tas_agencies"))
    return rows


def parse_act():
    raw = (SRC / "act-directorates.html").read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")
    main = soup.find("main") or soup
    wanted = {
        "directorates": "Directorate",
        "public sector bodies and statutory authorities": "Public sector body / statutory authority",
        "territory owned corporations": "Territory-owned corporation",
    }
    rows = []
    seen = set()
    for ul in main.find_all("ul"):
        h = ul.find_previous(["h2", "h3", "h4"])
        if not h:
            continue
        key = clean_ws(h.get_text(" ", strip=True)).lower()
        typ = wanted.get(key)
        if not typ:
            continue
        for li in ul.find_all("li", recursive=False):
            name = clean_ws(li.get_text(" ", strip=True))
            if not name or name in {"Yes", "No"} or name in seen:
                continue
            seen.add(name)
            rows.append(make_row("ACT", name, "", typ, "act"))
    return rows


def parse_nt():
    """Parse Schedule 1 of the NT AAO from layout text (two columns, wrapped names)."""
    text = (SRC / "nt-aao-2026.txt").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Schedule 1\s+Nomination of Agencies(.*?)Schedule 2", text, re.S)
    if not m:
        raise RuntimeError("Could not find NT Schedule 1")
    block = m.group(1)
    # Split into parts
    grouped = {}
    matches = list(re.finditer(r"Part\s+(\d+)\b", block))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        grouped[int(m.group(1))] = block[m.end():end]

    part_types = {
        1: "Agency (Financial Management Act and Public Sector Employment and Management Act)",
        2: "Agency (Financial Management Act only)",
        3: "Agency (Public Sector Employment and Management Act only)",
    }

    def parse_part(part_text: str) -> list[str]:
        # Drop the part title lines
        lines = part_text.splitlines()
        # Determine split col from two-column lines
        starts = []
        for line in lines:
            m2 = re.search(r"\S.{8,}\s{3,}(\S)", line)
            if m2 and not line.startswith(" " * 8):
                starts.append(m2.start(1))
        split_col = Counter(starts).most_common(1)[0][0] if starts else 45
        left, right = [], []
        for raw in lines:
            line = raw.rstrip()
            s = clean_ws(line)
            if not s:
                continue
            if re.match(r"Part\s+\d+", s):
                continue
            if s.startswith("Agencies for ") or s.startswith("Agency for "):
                continue
            if "Financial Management Act" in s or "Public Sector Employment" in s:
                continue
            if s.startswith("Page ") or re.fullmatch(r"\d+", s):
                continue
            lft = line[:split_col].rstrip()
            rgt = line[split_col:].strip() if len(line) > split_col else ""
            if clean_ws(lft):
                left.append(lft)
            if clean_ws(rgt):
                right.append(rgt)
        def nt_join(parts: list[str]) -> list[str]:
            # A fragment continues the previous name unless it starts a new agency.
            starters = re.compile(
                r"^(Attorney-General|Auditor-General|Department of|Land Development|Northern Territory|Office of|Aboriginal Areas|NT Home|Police Civil)\b",
                re.I,
            )
            out: list[str] = []
            for p in parts:
                p = clean_ws(p)
                if not p:
                    continue
                if out and not starters.match(p):
                    out[-1] = clean_ws(out[-1] + " " + p)
                else:
                    out.append(p)
            return out

        return nt_join(left) + nt_join(right)

    rows = []
    for num, ptext in grouped.items():
        typ = part_types.get(num, f"Schedule 1 Part {num}")
        for name in parse_part(ptext):
            # Filter leftover heading fragments
            if name.lower().startswith(("agencies for", "agency for", "and public sector", "management act")):
                continue
            rows.append(make_row("NT", name, "", typ, "nt"))
    return rows


def dedupe(rows, prefer_keys=None):
    """Keep first occurrence of each (jurisdiction, key), unless a later row has a preferred source."""
    prefer_keys = prefer_keys or {}
    # Group by jurisdiction+key
    buckets: OrderedDict[tuple, list] = OrderedDict()
    for r in rows:
        # Keep every Commonwealth/AGOR row even when titles coincide
        # (e.g. a primary body and a statutory office with the same name).
        if r["Jurisdiction"] == "Commonwealth":
            k = ("Commonwealth", id(r))
        else:
            k = (r["Jurisdiction"], r["_key"])
        buckets.setdefault(k, []).append(r)
    out = []
    dropped = []
    for k, items in buckets.items():
        if len(items) == 1:
            out.append(items[0])
            continue
        juris = k[0]
        prefer = prefer_keys.get(juris)
        chosen = items[0]
        if prefer:
            for it in items:
                if it["_source_key"] == prefer:
                    chosen = it
                    break
        out.append(chosen)
        for it in items:
            if it is not chosen:
                dropped.append((it["Entity name"], it["_source_key"], "kept", chosen["Entity name"], chosen["_source_key"]))
    return out, dropped


JURIS_ORDER = {
    "Commonwealth": 0,
    "NSW": 1,
    "Victoria": 2,
    "Queensland": 3,
    "WA": 4,
    "SA": 5,
    "Tasmania": 6,
    "ACT": 7,
    "NT": 8,
}


def write_workbook(entity_rows, source_counts, dropped, parse_notes):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Organisations"

    header_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_align = Alignment(vertical="center", wrap_text=True)
    cell_align = Alignment(vertical="center", wrap_text=True)
    thin = Border(
        left=Side(style="thin", color="D0D7DE"),
        right=Side(style="thin", color="D0D7DE"),
        top=Side(style="thin", color="D0D7DE"),
        bottom=Side(style="thin", color="D0D7DE"),
    )
    alt_fill = PatternFill("solid", fgColor="F2F6FA")

    for col, h in enumerate(COLS, start=1):
        cell = ws.cell(1, col, h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{len(entity_rows)+1}"
    ws.row_dimensions[1].height = 22

    entity_rows = sorted(
        entity_rows,
        key=lambda r: (JURIS_ORDER.get(r["Jurisdiction"], 99), r["Entity name"].lower()),
    )

    for i, r in enumerate(entity_rows, start=2):
        for col, h in enumerate(COLS, start=1):
            cell = ws.cell(i, col, r.get(h, ""))
            cell.alignment = cell_align
            cell.border = thin
            cell.font = Font(name="Calibri", size=10)
            if i % 2 == 0:
                cell.fill = alt_fill
            if h == "Source URL" and r.get(h):
                cell.hyperlink = r[h]
                cell.font = Font(name="Calibri", size=10, color="0563C1", underline="single")
                if i % 2 == 0:
                    cell.fill = alt_fill

    widths = {
        "A": 16,
        "B": 55,
        "C": 42,
        "D": 42,
        "E": 55,
        "F": 45,
        "G": 20,
    }
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.auto_filter.ref = f"A1:G{len(entity_rows)+1}"
    ws.sheet_view.showGridLines = False

    # Sources tab
    ws2 = wb.create_sheet("Sources")
    src_cols = [
        "Jurisdiction",
        "Source name",
        "URL",
        "Date",
        "Format",
        "Coverage notes",
        "Row count",
    ]
    for col, h in enumerate(src_cols, start=1):
        cell = ws2.cell(1, col, h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin
    ws2.freeze_panes = "A2"
    ws2.row_dimensions[1].height = 22

    # Preserve source order
    source_order = list(SOURCES.keys())
    for i, key in enumerate(source_order, start=2):
        s = SOURCES[key]
        vals = [
            s["jurisdiction"],
            s["name"],
            s["url"],
            s["date"],
            s["format"],
            s["coverage"],
            source_counts.get(key, 0),
        ]
        for col, v in enumerate(vals, start=1):
            cell = ws2.cell(i, col, v)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = thin
            cell.font = Font(name="Calibri", size=10)
            if col == 3 and v:
                cell.hyperlink = v
                cell.font = Font(name="Calibri", size=10, color="0563C1", underline="single")
            if i % 2 == 0:
                cell.fill = alt_fill
        ws2.row_dimensions[i].height = 75

    # Totals row
    total_row = len(source_order) + 2
    ws2.cell(total_row, 1, "All").font = Font(name="Calibri", size=10, bold=True)
    ws2.cell(total_row, 2, "Combined Organisations tab (after intra-jurisdiction deduplication)").font = Font(name="Calibri", size=10, bold=True)
    ws2.cell(total_row, 7, len(entity_rows)).font = Font(name="Calibri", size=10, bold=True)
    for col in range(1, 8):
        ws2.cell(total_row, col).border = thin
        ws2.cell(total_row, col).alignment = Alignment(vertical="center", wrap_text=True)

    ws2.auto_filter.ref = f"A1:G{len(source_order)+1}"
    for col, w in enumerate([16, 60, 45, 18, 22, 80, 12], start=1):
        ws2.column_dimensions[get_column_letter(col)].width = w
    ws2.sheet_view.showGridLines = False

    wb.save(OUT)
    return OUT


def main():
    print("Parsing sources...")
    blocks = OrderedDict()
    blocks["agor"] = parse_agor()
    blocks["nsw"] = parse_nsw()
    blocks["vic"] = parse_vic()
    blocks["wa"] = parse_wa()
    blocks["qld_aao"] = parse_qld_aao()
    blocks["qld_html"] = parse_qld_html()
    blocks["sa_appd"] = parse_sa_appendix_d()
    blocks["sa_units"] = parse_sa_admin_units()
    blocks["tas_fma"] = parse_tas_fma()
    blocks["tas_agencies"] = parse_tas_our_agencies()
    blocks["act"] = parse_act()
    blocks["nt"] = parse_nt()

    raw_counts = {k: len(v) for k, v in blocks.items()}
    print("Raw counts:", raw_counts)

    # Review prints for tricky parsers
    for key in ("qld_aao", "qld_html", "sa_appd", "sa_units", "tas_fma", "tas_agencies", "act", "nt"):
        print(f"\n===== {key} ({len(blocks[key])}) =====")
        for r in blocks[key]:
            print(f"  - {r['Entity name']} | {r['Portfolio/Department']} | {r['Entity type/classification']}")

    # Prefer more authoritative sources when names collide
    prefer = {
        "Queensland": "qld_aao",
        "SA": "sa_appd",
        "Tasmania": "tas_fma",
    }
    all_rows = []
    for v in blocks.values():
        all_rows.extend(v)

    # Source counts BEFORE dedupe (how many rows that source contributed before collapsing)
    pre_counts = raw_counts.copy()

    merged, dropped = dedupe(all_rows, prefer_keys=prefer)
    print(f"\nDropped {len(dropped)} intra-jurisdiction duplicates:")
    for d in dropped:
        print("  ", d)

    # Post-dedupe counts by source (rows remaining attributed to that source)
    post_counts = Counter(r["_source_key"] for r in merged)
    print("Post-dedupe source counts:", dict(post_counts))
    print("By jurisdiction:", dict(Counter(r["Jurisdiction"] for r in merged)))

    # Sources tab row count = number of entity rows in the combined sheet that still cite that source
    # (after dedupe). Also useful to know pre-dedupe. We'll put post-dedupe counts, and mention
    # pre-dedupe in coverage if different? Better: row count = rows in Organisations tab citing that source.
    write_workbook(merged, post_counts, dropped, None)
    print("Wrote", OUT, "entities", len(merged))


if __name__ == "__main__":
    main()
