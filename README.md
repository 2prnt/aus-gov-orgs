# Australian Government Organisations

A combined list of Australian government departments, agencies and related entities across the Commonwealth, all six states and both territories, compiled in November 2026 and enriched with AGOR-aligned fields (ABN, website, head office, legislation and so on) where those details can be taken from an official source or a conservative Australian Business Register match.

This repository is a UTF-8 CSV snapshot of the same dataset published as a Google Sheet:

[Australian Government Organisations - All Jurisdictions (Nov 2026)](https://docs.google.com/spreadsheets/d/1C_L4zpS6PShxzaRiUycv_dgLkm8rcShLNUI7rXNnv7k/edit)

The aim is a single, source-cited table analogous to the Commonwealth Department of Finance [Australian Government Organisations Register (AGOR)](https://data.gov.au/data/dataset/australian-government-organisations-register). No state or territory publishes an AGOR-equivalent CSV covering every public body. Where a downloadable register existed it was used in full; otherwise the best official structured source (administrative arrangements order, budget entity list, or government directory page) was parsed. Values were not invented: if a field could not be filled confidently it was left blank.

## Files

- `data/organisations.csv` — all 2,772 entity rows (the Organisations tab)
- `data/sources.csv` — one row per source, plus the ABR bulk extract and a combined total row (the Sources tab)
- `data/by-jurisdiction/` — the same entities split into one CSV per jurisdiction
- `data/enrichment_report.json` — machine-readable fill rates per column per jurisdiction
- `scripts/build.py` — parse the official jurisdiction sources into the base entity list
- `scripts/enrich.py` — map the AGOR schema, attach source-provided fields, match ABNs from the ABR bulk extract, and rewrite the published CSVs
- `icons/` — one icon per organisation (see [Icons](#icons))
- `scripts/wikidata_sites.py`, `fetch_icons.py`, `fetch_icons_deep.py`, `fetch_big_fallbacks.py`, `build_icons.py` — collect the icons
- `scripts/companies_data.py`, `add_companies.py`, `scan_abr_companies.py`, `apply_companies.py`, `finalize_companies.py` — add state/territory government-owned companies and subsidiaries (see [Government-owned companies](#government-owned-companies))
- `scripts/extract_abr.py` — stream the data.gov.au ABN Bulk Extract ZIPs into a compact government-entity JSONL used by `enrich.py`

## Schema

The published table uses the 36 AGOR columns as the unified schema, plus jurisdiction, source citation, three source-native contact fields that have no AGOR equivalent, and an ABN match-confidence flag. The entity name is in AGOR's `Title` column. `Portfolio/Department` from the earlier combined sheet is in `Portfolio`. `Entity type/classification` is in `Classification`.

| Column | Contents |
| --- | --- |
| Jurisdiction | Commonwealth, NSW, Victoria, Queensland, WA, SA, Tasmania, ACT, or NT |
| Id | AGOR identifier (Commonwealth rows only) |
| Portfolio Dept? | AGOR flag (Commonwealth rows only) |
| Title | Entity name as given in the source, lightly normalised (whitespace and typography only) |
| Portfolio | Portfolio, parent department or responsible minister where the source provides one |
| Classification | Classification from the source (AGOR classification, GSF class, VPSC employer type / sheet group, GFS sector, AAO administrative unit, and so on) |
| Type of Body | AGOR type of body (Commonwealth), VPSC Public Sector Body Type (Victoria), or for the government-owned companies added in November 2026 a label such as `Government owned corporation`, `State-owned company`, `Government Business Enterprise`, `Government Trading Enterprise` or `Subsidiary of …` |
| GFS Sector Classification | AGOR GFS class, or SA Budget Appendix D / similar GFS grouping where the source uses those terms |
| Materiality … Budget Documentation | Remaining AGOR columns, populated for Commonwealth rows from the AGOR CSV; otherwise blank unless a state/territory source provides a clear equivalent |
| Established By / Under | AGOR established-by code; set to `Act / Regulation` for NSW GSF agencies whose source legislation field names an Act or Regulation |
| Established by/Under More Info | AGOR instrument text, or the NSW GSF “Relevant legislation of entity” field |
| ABN | Australian Business Number, formatted `XX XXX XXX XXX`. Commonwealth: copied from AGOR. Other jurisdictions: official source ABN only after ABR verification, or a conservative ABR name match (see Methods) |
| Head Office Street Address, Suburb, State, Postcode, Country | AGOR head office (Commonwealth) or WA Public Sector Commission mailing-list street address |
| Website Address | Official website when provided by the source or confidently identified from an official directory page. Normalised to include an `https://` scheme where the source omitted one |
| Source name, Source URL, Source date | Official source of the *entity row* (the register, AAO, budget list or directory the body was taken from) |
| Accountable Authority | NSW GSF accountable authority (no AGOR equivalent) |
| Contact telephone | WA mailing-list telephone (no AGOR equivalent) |
| Generic agency email | WA mailing-list generic agency or CEO email (no AGOR equivalent) |
| ABN match confidence | `exact`, `high`, or blank. Commonwealth ABNs supplied by AGOR are `exact`. ABR matches: `exact` when the normalised legal name is unique in the right state; `high` after conservative name variants, or when the match is an official ABR “other name” of a parent government ABN (see Methods) |

Blank cells mean the source or lookup did not provide a confident value. Values were not invented.

Within a jurisdiction, duplicate names from overlapping sources were collapsed, preferring the more authoritative source (for example the Queensland AAO over the ministers page, SA Budget Appendix D over the Administrative Units PDF, and the Tasmanian FMA Schedule 1 over the agencies page). The exception is the Commonwealth: all 1,372 AGOR rows are kept, including four titles that appear twice because AGOR lists both a primary body and a statutory office-holder under the same name (Fair Work Commission, Safe Work Australia, Australian Human Rights Commission, and Seafarers Safety, Rehabilitation and Compensation Authority).

## Row counts

| Jurisdiction | Rows |
| --- | ---: |
| Commonwealth | 1,372 |
| NSW | 406 |
| Victoria | 270 |
| Queensland | 182 |
| WA | 296 |
| SA | 115 |
| Tasmania | 61 |
| ACT | 39 |
| NT | 31 |
| **Total** | **2,772** |

WA includes **146 local governments** listed in Schedule 1 of the Public Sector Management Act 1994, because they appear in the Public Sector Commission mailing list. Filter `Classification` to `Schedule 1 – Local government` to exclude them. Those councils have telephone and CEO email in the source file but no website or street address, which is why WA website and head-office fill rates are about 49%.

## Fill rates

Percentages are the share of rows in that jurisdiction with a non-blank value. ABN and website are the headline enrichment fields; the other columns show what was available from AGOR or from the state/territory source files.

| Jurisdiction | Rows | ABN | Website | Portfolio | Classification | Type of Body | Legislation / established under | Head office address | Accountable authority | Telephone | Agency email |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Commonwealth | 1,372 | 35.6% | 59.3% | 100.0% | 100.0% | 100.0% | 50.6% | 64.9% | 0.0% | 0.0% | 0.0% |
| NSW | 406 | 34.7% | 0.0% | 99.5% | 100.0% | 0.5% | 99.5% | 0.0% | 99.5% | 0.0% | 0.0% |
| Victoria | 270 | 62.2% | 1.9% | 100.0% | 100.0% | 100.0% | 1.9% | 0.0% | 0.0% | 0.0% | 0.0% |
| Queensland | 182 | 82.4% | 25.3% | 15.4% | 47.3% | 84.6% | 84.6% | 0.0% | 0.0% | 0.0% | 0.0% |
| WA | 296 | 80.7% | 48.6% | 0.0% | 100.0% | 2.0% | 1.7% | 48.3% | 0.0% | 97.3% | 97.6% |
| SA | 115 | 67.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| Tasmania | 61 | 70.5% | 23.0% | 0.0% | 100.0% | 49.2% | 49.2% | 0.0% | 0.0% | 0.0% | 0.0% |
| ACT | 39 | 51.3% | 94.9% | 0.0% | 100.0% | 10.3% | 5.1% | 0.0% | 0.0% | 0.0% | 0.0% |
| NT | 31 | 96.8% | 9.7% | 0.0% | 100.0% | 12.9% | 12.9% | 0.0% | 0.0% | 0.0% | 0.0% |
| **All** | **2,772** | **48.9%** | **38.3%** | **74.8%** | **96.5%** | **66.5%** | **46.8%** | **37.3%** | **14.6%** | **10.4%** | **10.4%** |

| Jurisdiction | ABN exact | ABN high | ABN blank |
| --- | ---: | ---: | ---: |
| Commonwealth | 488 | 0 | 884 |
| NSW | 135 | 6 | 265 |
| Victoria | 147 | 21 | 102 |
| Queensland | 147 | 3 | 32 |
| WA | 225 | 14 | 57 |
| SA | 73 | 4 | 38 |
| Tasmania | 42 | 1 | 18 |
| ACT | 18 | 2 | 19 |
| NT | 8 | 22 | 1 |
| **All** | 1,283 | 73 | 1,416 |

Commonwealth ABN (35.6%) and website (59.3%) fill rates are exactly those of the AGOR 30 September 2026 CSV — they were copied through, not re-looked-up.

## Methods

### Source field mapping

- **Commonwealth.** All 36 AGOR columns are copied from the official CSV, matched on Title plus Classification and Type of Body so the four duplicated titles stay aligned with the correct AGOR row.
- **NSW.** GSF classification stays in `Classification`. Relevant legislation is written to `Established by/Under More Info`, and `Established By / Under` is set to `Act / Regulation` when that field names an Act or Regulation. Accountable Authority is kept in its own column (it is not forced into the AGOR “Board / Committee Appointed by” field).
- **Victoria.** VPSC Public Sector Body Type is written to `Type of Body`. Portfolio and employer-style classification come from the VPSC file.
- **WA.** Street address, suburb, state and postcode map to the AGOR Head Office columns (`Country` is `Australia` where an address is present). Website, telephone and generic email come from the mailing list. The unnamed website column on some sheets is treated as a website only when the cell looks like a URL. Local government rows have telephone and CEO email only.
- **SA.** Budget Appendix D GFS groupings (general government, public non-financial corporations, public financial corporations) are copied to both `Classification` and `GFS Sector Classification`. Candidate ABNs from the Shared Services SA eInvoicing list are used only after ABR verification (see below).
- **Queensland, ACT.** Official website URLs are taken from the agency-name links on the Queensland ministers-and-departments page and the ACT directorates-and-agencies page. Career-page URLs on tas.gov.au/jobs/ were not treated as official websites.

ABN Lookup JSON web services were not used: they require a GUID issued after signup at abr.business.gov.au/webservices.aspx, which was not obtained. The public HTML search was not used either. ABNs for non-Commonwealth entities come from the [ABN Bulk Extract](https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e) on data.gov.au (11 November 2026, CC BY 3.0 AU), which is the more robust option.

Only **Active** (`ACT`) ABR records whose entity type is a government type were eligible:

- State: `SG*` (State Government Entity, Statutory Authority, and related), plus `LG*` for local government, and `GOV` / `SSA` / `STA` / `LOC`
- Territory: `TG*` / `TER` (and `LG*` / `GOV` / `LOC` where applicable)
- **Commonwealth types (`CG*`) are never used to fill a state or territory row.** Many Commonwealth bodies have an ACT (or other) business address and would otherwise collide with similarly named territory agencies (for example the Commonwealth DPP versus the ACT DPP).

Other ABR types such as Australian Public Company (`PUB`) and Other Incorporated Entity (`OIE`) are **not** used, even on an exact name match. Universities, some state-owned corporations and some trustees therefore have a blank ABN in this snapshot even when an ABN exists under a non-government type.

A match is accepted only when:

1. the name matches confidently (normalised legal name, official trading / other name, or a conservative variant such as `Office of the X` / `X Office`, `Department of X` / `X Department`, `&` / `AND`, possessives, and jurisdiction qualifiers), and
2. the recorded state agrees with the jurisdiction (cross-state matches are never accepted — many governments share titles such as “Department of Health” or “Attorney-General’s Department”).

Confidence:

- `exact` — unique eligible match in the right state on the normalised legal name
- `high` — unique eligible match after light name-variant normalisation, or a unique in-state match on an official ABR other-name of a parent body
- blank — no unique confident match

Several bodies legitimately share a parent ABN because the ABR lists them as other names of a department or of a whole-of-government entity. The most prominent case is the Northern Territory: 22 of 27 NT agencies are registered as other names of **Northern Territory of Australia** (ABN 84 085 734 992) and are marked `high`. The same pattern appears for some Victorian and South Australian statutory offices that are other names of their parent department, and for The Perth Mint under Gold Corporation. Shared ABNs were checked so that none are assigned across jurisdictions.

The Shared Services SA eInvoicing workbook is only a candidate list: an eInvoice ABN is kept only when the ABR has an Active government-entity record in South Australia whose name matches the catalogue entity.

### Websites

Websites are taken from:

- the AGOR `Website Address` column (Commonwealth)
- the WA mailing-list Website / InternetAddress columns (and the equivalent unnamed column on some sheets)
- official name-to-URL links on the Queensland ministers-and-departments page and the ACT directorates-and-agencies page (including a small number of official `.com.au` / `.edu.au` sites that the ACT page itself lists for those bodies)

Websites were **not** guessed from email domains, web search, or unofficial directories. NSW, Victoria, SA, Tasmania and the NT sources used here do not publish a website column, so those rows have a blank `Website Address` unless a future official directory can be matched confidently. Tasmanian “Our agencies” links point at tas.gov.au job pages and were not used as websites.

### What could not be filled

- **ABN.** 1,367 of 2,560 rows have no ABN (884 of those are Commonwealth rows that AGOR itself leaves blank). Typical reasons for a blank state/territory ABN: the body is not in the ABR as a government entity type (universities, some SOCs, some trustees); the name is ambiguous (Queensland Health is an other-name on many Hospital and Health Service ABNs, so it was left blank); the ABR has no record under a matching name in that state (Queensland Public Trust Office; the Police Civil Employment Unit Agency in the NT; several recently renamed ACT directorates and statutory offices); or more than one eligible record matched.
- **Website.** 1,544 rows have no website, including all NSW, Victorian, SA, Tasmanian and NT rows and the 146 WA local governments. Queensland Reconstruction Authority, Resources Safety and Health Queensland, and the Public Trust Office have no official link on the ministers page used as the website source.
- **AGOR-only fields** such as staffing, appropriations, auditors, board composition, annual reports and budget documentation are blank for state and territory rows because those sources do not publish them.

## Sources

| Jurisdiction | Source | Date | Format | Rows in this dataset |
| --- | --- | --- | --- | ---: |
| Commonwealth | [AGOR 30 September 2026 CSV](https://data.gov.au/data/dataset/c77cface-69aa-4dd0-b99f-b065dc33c8e6/resource/6d58f54c-8f24-4b2c-a819-c22f71c39ca1/download/agor-2026-09-30.csv) on [data.gov.au](https://data.gov.au/data/dataset/australian-government-organisations-register) | 30 September 2026 | CSV | 1,372 |
| NSW | [NSW Treasury GSF Agency List](https://www.nsw.gov.au/sites/default/files/noindex/2026-06/nsw-treasury-gsf-agency-list_1.xlsx) ([guide](https://www.nsw.gov.au/departments-and-agencies/nsw-treasury/documents-library/gsf-agency-list-guide)) | March 2026 | XLSX | 404 |
| Victoria | [VPSC list of public sector employers, 19 October 2026](https://www.vpsc.vic.gov.au/files/2026-10/Spreadsheet%20-%20list%20of%20employers%2019%20October%202026.csv) ([live list](https://www.vpsc.vic.gov.au/about-public-sector/list-public-sector-employers)) | 19 October 2026 | CSV | 258 |
| Queensland | [Administrative Arrangements Order (No. 1) 2026](https://www.qld.gov.au/__data/assets/word_doc/0025/908413/administrative-arrangements-order-no.-1-2026.docx) (gazetted 3 July 2026; [PDF](https://www.qld.gov.au/__data/assets/pdf_file/0023/908411/administrative-arrangements-order-no.-1-2026.pdf)) | 3 July 2026 | DOCX | 26 |
| Queensland | [Ministers and departments](https://www.qld.gov.au/government/premier-ministers-departments/ministers-departments) page | 24 October 2026 | HTML | 2 |
| WA | [Public Sector Commission government sector mailing list](https://www.wa.gov.au/system/files/2026-11/government_sector_mailing_list.xlsx) ([page](https://www.wa.gov.au/government/publications/government-sector-mailing-list)) | 11 November 2026 | XLSX | 290 |
| SA | [2026–27 Budget Statement, Appendix D](https://www.treasury.sa.gov.au/__data/assets/pdf_file/0006/1419036/2026-27-Budget-Statement.pdf) (pp. 168–169; [budget page](https://www.treasury.sa.gov.au/budget/current-budget)) | 4 June 2026 | PDF | 114 |
| SA | [Administrative units of the Public Service of South Australia](https://www.legislation.sa.gov.au/__data/assets/pdf_file/0011/1398611/2026.03.25-Administrative-Units.pdf) ([index](https://www.legislation.sa.gov.au/lists-and-index-to-sa-legislation/administrative-units)) | 25 March 2026 | PDF | 1 |
| SA | [Shared Services SA eInvoicing ABN list (v8.0)](https://www.sharedservices.sa.gov.au/documents/financial-services/eInvoice_ABNsv8.0.xlsx) | Accessed 13 November 2026 | XLSX | (ABN candidates; verified against the ABR before use) |
| Tasmania | [Financial Management Act 2016, Schedule 1](https://www.legislation.tas.gov.au/view/whole/html/inforce/current/act-2016-042) (last applied amendment 8 October 2026) | 8 October 2026 | HTML | 27 |
| Tasmania | [Tasmanian State Service Careers – Our agencies](https://www.tas.gov.au/jobs/work-with-us/about-us/our-agencies) | 7 May 2026 | HTML | 4 |
| ACT | [Directorates and agencies](https://www.act.gov.au/directorates-and-agencies) | 23 April 2026 | HTML | 35 |
| NT | [Administrative Arrangements Order 2026, Schedule 1](https://legislation.nt.gov.au/api/sitecore/Act/PDF?id=11575) (commenced and gazetted S41 on 1 June 2026) | 1 June 2026 | PDF | 27 |
| NSW | [NSW Report on the State Finances 2024-25, Total State Sector Accounts Note 36 Controlled Entities](https://www.nsw.gov.au/sites/default/files/noindex/2025-11/report-on-the-state-finances-2024-25.pdf) (government-owned companies, added November 2026) | November 2025 | PDF | 2 |
| Victoria | [Victoria 2024-25 Financial Report, Note 8.8 Controlled entities](https://www.dtf.vic.gov.au/sites/default/files/2025-10/2024-25-Financial-Report.pdf) (government-owned companies, added November 2026) | October 2025 | PDF | 12 |
| Queensland | [Queensland Treasury – Government-owned corporations (list of GOCs)](https://www.treasury.qld.gov.au/policies-and-programs/economy/government-owned-corporations/) (government-owned companies, added November 2026) | 2026 | HTML | 11 |
| Queensland | [Queensland Audit Office – State entities 2025 (Report 11: 2025–26), Appendices F and I](https://www.parliament.qld.gov.au/Work-of-the-Assembly/Tabled-Papers/docs/5826T0321/5826t321.pdf) (government-owned companies, added November 2026) | 2026 | PDF | 143 |
| WA | [WA Office of the Auditor General – State Government 2025 Financial Audit Results (Report 6), Appendix 1](https://audit.wa.gov.au/wp-content/uploads/2025/12/Report-6-State-Government-2025-Financial-Audit-Results.pdf) (government-owned companies, added November 2026) | December 2025 | PDF | 6 |
| Tasmania | [Treasury and Finance Tasmania – Tasmanian Government Businesses](https://www.treasury.tas.gov.au/government-businesses/tasmanian-government-businesses) (government-owned companies, added November 2026) | 2026 | HTML | 12 |
| Tasmania | [Hydro Tasmania Annual Report 2024-25, Note 29 Controlled entities](https://www.hydro.com.au/sites/default/files/2026-01/hydro-tasmania-annual-report-2025.pdf) (government-owned companies, added November 2026) | 2025 | PDF | 16 |
| Tasmania | [TasPorts Annual Report 2024–25, controlled entities](https://tasports.com.au/volumes/documents/Annual-Reports/TasPorts-Annual-Report-2024-2025.pdf) (government-owned companies, added November 2026) | 2025 | PDF | 1 |
| ACT | [Icon Water – Who are we](https://www.iconwater.com.au/about-us/who-are-we) (government-owned companies, added November 2026) | 2026 | HTML | 4 |
| NT | [Power and Water Corporation – About us; Territory Generation and Jacana Energy annual reports](https://www.powerwater.com.au/about) (government-owned companies, added November 2026) | 2026 | HTML | 4 |
| All | [ABR ABN Bulk Extract](https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e) (11 November 2026; parts [1–10](https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/0ae4d427-6fa8-4d40-8e76-c6909b5a071b) and [11–20](https://data.gov.au/data/dataset/5bd7fcab-e315-42cb-8daf-50b7efc2027e/resource/635fcb95-7864-4509-9fa7-a62a6e32b62d)) | 11 November 2026 | XML (ZIP) | (ABN lookup only; not a row source) |

Row counts in the table above are rows remaining in `organisations.csv` after deduplication, attributed to the source that was kept.

## Government-owned companies

In November 2026, 212 state and territory government-owned companies, GOCs, state-owned corporations, GBEs/GTEs and their controlled subsidiaries (including Pty Ltd companies) were added from official lists. They were deduplicated against the existing rows using normalised names (case, punctuation, `Pty`/`Ltd`/`Limited`, `trading as` and bracketed short names), plus a hand check of near-matches. Most NSW, Victorian and SA statutory corporations and SOCs were already present from the GSF list, the VPSC list and SA Budget Appendix D, so only the missing ones were added.

| Jurisdiction | Added | Examples |
| --- | ---: | --- |
| NSW | 2 | Newcastle Port Corporation, Residual Transport Corporation |
| Victoria | 12 | SEC Infrastructure Pty Ltd, SEC Energy Pty Ltd, Breakthrough Victoria Pty Ltd, Launch Victoria Ltd, Melbourne Port Lessor Pty Ltd, Homes Victoria |
| Queensland | 154 | CS Energy Limited, Stanwell Corporation Limited, Energy Queensland Limited (Energex Limited, Ergon Energy Corporation Limited, Yurika Pty Ltd), QIC Limited and its controlled companies, Queensland Rail Limited, Screen Queensland Pty Ltd |
| WA | 6 | Flat Rocks Wind Farm Stage 2 Pty Ltd (Synergy), Hedland Maritime Initiative Pty Ltd (Pilbara Ports), Edith Cowan Accommodation Holdings Pty Ltd, Perth International Arts Festival Ltd |
| SA | 0 | none (all SA government businesses were already present from Budget Appendix D) |
| Tasmania | 30 | Hydro-Electric Corporation (Hydro Tasmania), Momentum Energy Pty Limited, Aurora Energy Pty Ltd, TasNetworks, TasPorts, TasRail, TT-Line Company Pty Ltd, Bass Island Line Pty Ltd |
| ACT | 4 | Icon Distribution Investments Limited, Icon Retail Investments Limited, the ActewAGL Distribution (Evoenergy) and Retail partnerships |
| NT | 4 | Power and Water Corporation, Territory Generation, Jacana Energy, Indigenous Essential Services Pty Ltd |

Rules used:

- `Source name`, `Source URL` and `Source date` cite the list each company came from (see [Sources](#sources)). `Parent Organisation` names the owning GOC, GBE, department or statutory body where the source gives it. `Portfolio` is filled where the source groups entities by department (Victoria). `GFS Sector Classification` is PNFC, PFC or GGS where the source gives the sector.
- Queensland: the 11 GOCs come from Queensland Treasury's GOC list. Their companies and other controlled companies come from Queensland Audit Office *State entities 2025*, Appendices F and I. These were excluded: trusts, funds, unincorporated projects, insurance cells, "as trustee" entries, and the two entities the QAO footnotes as managed but not controlled (Queensland Titles Registry Pty Ltd, Registry Finance Pty Ltd). Companies in the "Entities managed by QIC Limited" block have the type `Company managed and controlled by QIC Limited`.
- ABN: the ABR bulk extract was re-scanned across all entity types, because the earlier government-only extract skips Australian Private and Public Companies. An ABN is filled only from a single current (status ACT) ABR record whose legal or other name equals the company name, after normalising Pty/Proprietary and Ltd/Limited. Company names are unique nationally, so for a `Pty Ltd`/`Limited` name the record may be registered in another state. Some QIC and other subsidiaries have only a cancelled ABN, so they are left blank.
- Website: filled only for a well-known official domain that loaded during the check. Redirects were followed, so for example Dairy Food Safety Victoria and PrimeSafe now point to safefood.vic.gov.au. Subsidiaries mostly have no website and use the parent's icon.

Gaps: WA and NT do not publish a consolidated list of GTE/GOC subsidiaries. WA is limited to the GTE Act list and the companies the Auditor General audits directly. NT is limited to the three GOCs and Indigenous Essential Services. Subsidiaries of WA GTEs that the Auditor General does not audit separately, and minority joint ventures, are not included. Universities' controlled companies are only included where the source lists them (ECU in WA). Hydro Tasmania's South African and Indian subsidiaries are included because they are controlled entities in its annual report.

## Known coverage gaps

- **Queensland and NT** are limited to agencies named in the current Administrative Arrangements Order (plus, for Queensland, two extra agencies from the ministers-and-departments page: Arts Queensland and Trade and Investment Queensland). Neither jurisdiction publishes a downloadable register of all statutory bodies. Queensland’s [Government Bodies](https://governmentbodies.premiers.qld.gov.au/) register has no export. NT Schedule 2 bodies that are not nominated as agencies in Schedule 1 are not included.
- **Tasmania:** the Department of Premier and Cabinet page *About the Tasmanian State Service* states there are 18 agencies (nine departments and nine state authorities) but does not name them. Names come from FMA Schedule 1 (general government sector and legislative agencies) plus the tas.gov.au “Our agencies” page, which names 17 State Service bodies. Four of those are not in the FMA list: Homes Tasmania, Macquarie Point Development Corporation, Port Arthur Historic Site Management Authority, and The Public Trustee. The 18th State Service agency is not named on either page.
- **WA** includes 146 local governments from Schedule 1 of the Public Sector Management Act, as well as universities and government trading enterprises, because they appear in the PSC mailing list.
- **SA** Budget Appendix D (the most complete official entity inventory) was reconstructed from a two-column PDF layout in the 2026–27 Budget Statement, pages 168–169. The Administrative Units PDF was used only for current public service units; its historical/abolished section was excluded. After deduplication, only Office of Venue Management was unique to that PDF.
- **Victoria** is the VPSC list of *public sector employers*, not every public entity (non-employer bodies such as some cemetery trusts are out of scope).
- **NSW** is the Treasury GSF agency list, which Treasury describes as indicative and not real-time, and not itself determinative of GSF status. It is broader than the public-facing departments directory (it includes universities and controlled entities). The GSF list has no website column.
- The **ACT Directory** (directory.act.gov.au) was not used, because that site warns it still reflects pre-1 July 2025 structures.

## Icons

Every organisation has a small square PNG icon for use on profile pages, named after the organisation:
`icons/png/<slug>.png`, where the slug is a jurisdiction prefix (`cth`, `nsw`, `vic`, `qld`, `wa`, `sa`, `tas`, `act`, `nt`) plus the kebab-case title, for example `icons/png/cth-australian-taxation-office.png`. Slugs are unique (a `-2` suffix is added for the few repeated titles).

- `icons/png/` — one PNG per organisation (2,772 files, 699 distinct images), padded with transparency to a square. Own-site icons are scaled down to at most 128 px; fallback logos are 128–256 px.
- `icons/svg/` — an SVG copy where the site publishes an SVG icon or logo (136 files). Defence-fallback rows get the "Australian Government | Defence" crest SVG from defence.gov.au.
- `icons/manifest.csv` — slug, title, jurisdiction, website, icon file, SVG file, icon source URL, method, notes, width, height, original size and SHA-256.
- `icons/aus-gov-orgs-icons-png.zip` — all PNGs plus the manifest in one download.
- `data/organisations.csv` and `data/by-jurisdiction/*.csv` include `Icon file`, `Icon source URL` and `Icon method`.

Quality bar: every PNG is at least 1,000 bytes (smallest is 1,011 bytes), at least 32 px from a source of at least 32 px (nothing is upscaled), not blank, not all-white, and not a hosting-platform placeholder. Every fallback logo (parent, portfolio, Defence, jurisdiction) is at least 128 px. Icons that missed the bar were re-searched on the organisation's site (apple-touch and manifest icons, `/apple-touch-icon.png`, the header home-link logo, square `og:image`, SVGs rasterised) and then Google's favicon service at 128 px before falling back.

Method, in order of preference:

| Method | Meaning |
|---|---|
| `own-site` | Icon or logo from the organisation's listed website (subpage URLs use the host's site icon, so committees hosted on a department site share its icon). |
| `own-site-wikidata` | The row had no website; an official website was found on Wikidata (exact title match, Australian item) and its icon fetched. The website is recorded in the manifest only, not added to the dataset. |
| `google-s2` | The site blocked or failed direct icon requests, so its favicon was taken from Google's favicon service. Recorded as third-party. |
| `defence-fallback` | No usable own icon for a Defence-portfolio body: the "Australian Government — Defence" crest from defence.gov.au. |
| `parent` | No usable own icon: the parent organisation's (from `Parent Organisation`) or portfolio department's icon or logo, at least 128 px. Veterans' Affairs bodies use the DVA icon. |
| `fallback-jurisdiction` | No usable own or parent icon: the government's logo. Commonwealth: Australian Government coat of arms (agriculture.gov.au). NSW: nsw.gov.au waratah. Victoria: Victoria State Government logo (vic.gov.au). Queensland: Queensland Government crest (qld.gov.au). WA: wa.gov.au. SA: Government of South Australia logo (sa.gov.au). Tasmania: Tasmanian Government logo (service.tas.gov.au). ACT: ACT Government logo (act.gov.au). NT: nt.gov.au. |

| Jurisdiction | `own-site` | `own-site-wikidata` | `google-s2` | `defence-fallback` | `parent` | `fallback-jurisdiction` | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Commonwealth | 670 | 2 | 30 | 27 | 548 | 95 | 1,372 |
| NSW | 0 | 46 | 5 | 0 | 160 | 195 | 406 |
| Victoria | 5 | 44 | 1 | 0 | 138 | 82 | 270 |
| Queensland | 39 | 1 | 4 | 0 | 69 | 69 | 182 |
| WA | 126 | 116 | 13 | 0 | 3 | 38 | 296 |
| SA | 0 | 16 | 1 | 0 | 0 | 98 | 115 |
| Tasmania | 14 | 7 | 0 | 0 | 16 | 24 | 61 |
| ACT | 34 | 0 | 0 | 0 | 2 | 3 | 39 |
| NT | 3 | 8 | 1 | 0 | 0 | 19 | 31 |
| **All** | 891 | 240 | 55 | 27 | 936 | 623 | 2,772 |

No logo was drawn or generated; every file comes from an official website (or Google's cache of one, where marked). The jurisdiction and Defence logos were rasterised or trimmed from the official artwork only. Icons and logos remain the property of the respective organisations and governments.

To rebuild the icons:

```text
python3 scripts/wikidata_sites.py        # find official sites for rows without a website
python3 scripts/fetch_icons.py           # fetch each host's icon into a local cache
python3 scripts/fetch_icons_deep.py      # deeper search for icons that miss the quality bar
python3 scripts/fetch_big_fallbacks.py   # >= 128 px logos for parent/portfolio fallbacks
python3 scripts/build_icons.py           # assign icons, write icons/ and the icon CSV columns
```

## Rebuilding

The official source files used by `build.py` and `enrich.py` are not stored in this repository (several are large PDFs or spreadsheets). The ABN Bulk Extract is two ~500 MB ZIP files and is also not stored here.

```text
# 1. Place source files where scripts/build.py expects them, then:
python3 scripts/build.py

# 2. Download the ABN Bulk Extract ZIPs from data.gov.au and stream government
#    entities to a JSONL index (see scripts/extract_abr.py for paths).
python3 scripts/extract_abr.py

# 3. Write the published CSVs (expects the 7-column base list in
#    data/organisations_base.csv, or a 7-column data/organisations.csv).
python3 scripts/enrich.py
```

## Licence and use

The compiled table is a convenience extract from official public sources. Each source retains its own copyright and licence (AGOR and the ABR bulk extract are CC BY 3.0 Australia; check the originating agency for the others). This snapshot is not an official government register and will go out of date as machinery-of-government changes occur. ABN assignments for non-Commonwealth entities are a conservative reading of the public ABR extract, not an Australian Business Register information brokerage product.
