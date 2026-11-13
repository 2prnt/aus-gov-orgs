# Australian Government Organisations

A combined list of Australian government departments, agencies and related entities across the Commonwealth, all six states and both territories, compiled in November 2026.

This repository is a UTF-8 CSV snapshot of the same dataset published as a Google Sheet:

[Australian Government Organisations - All Jurisdictions (Nov 2026)](https://docs.google.com/spreadsheets/d/1TSvIt88EbW7GlT24kTlaGZWDgBBOXZMmCFN3VWKHAKg/edit)

The aim is a single, source-cited table analogous to the Commonwealth Department of Finance [Australian Government Organisations Register (AGOR)](https://data.gov.au/data/dataset/australian-government-organisations-register). No state or territory publishes an AGOR-equivalent CSV covering every public body. Where a downloadable register existed it was used in full; otherwise the best official structured source (administrative arrangements order, budget entity list, or government directory page) was parsed.

## Files

- `data/organisations.csv` — all 2,560 entity rows (the Organisations tab)
- `data/sources.csv` — one row per source, plus a combined total row (the Sources tab)
- `data/by-jurisdiction/` — the same entities split into one CSV per jurisdiction
- `scripts/build.py` — the Python script used to parse the official sources and build the workbook

## Columns

`organisations.csv` and the per-jurisdiction files use:

| Column | Contents |
| --- | --- |
| Jurisdiction | Commonwealth, NSW, Victoria, Queensland, WA, SA, Tasmania, ACT, or NT |
| Entity name | Name as given in the source, lightly normalised (whitespace and typography only) |
| Portfolio/Department | Portfolio, parent department or responsible minister where the source provides one; otherwise blank |
| Entity type/classification | Classification from the source (for example AGOR body type, GSF class, VPSC public-sector body type, GFS sector, or AAO administrative unit) |
| Source name | Official name of the source dataset or document |
| Source URL | Direct link to the file or page used |
| Source date | Date of the source snapshot, gazette, or page update |

Blank cells mean the source did not provide that field. Values were not invented.

Within a jurisdiction, duplicate names from overlapping sources were collapsed, preferring the more authoritative source (for example the Queensland AAO over the ministers page, SA Budget Appendix D over the Administrative Units PDF, and the Tasmanian FMA Schedule 1 over the agencies page). The exception is the Commonwealth: all 1,372 AGOR rows are kept, including four titles that appear twice because AGOR lists both a primary body and a statutory office-holder under the same name.

## Row counts

| Jurisdiction | Rows |
| --- | ---: |
| Commonwealth | 1,372 |
| NSW | 404 |
| Victoria | 258 |
| Queensland | 28 |
| WA | 290 |
| SA | 115 |
| Tasmania | 31 |
| ACT | 35 |
| NT | 27 |
| **Total** | **2,560** |

WA includes **146 local governments** listed in Schedule 1 of the Public Sector Management Act 1994, because they appear in the Public Sector Commission mailing list. Filter `Entity type/classification` to `Schedule 1 – Local government` to exclude them.

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
| Tasmania | [Financial Management Act 2016, Schedule 1](https://www.legislation.tas.gov.au/view/whole/html/inforce/current/act-2016-042) (last applied amendment 8 October 2026) | 8 October 2026 | HTML | 27 |
| Tasmania | [Tasmanian State Service Careers – Our agencies](https://www.tas.gov.au/jobs/work-with-us/about-us/our-agencies) | 7 May 2026 | HTML | 4 |
| ACT | [Directorates and agencies](https://www.act.gov.au/directorates-and-agencies) | 23 April 2026 | HTML | 35 |
| NT | [Administrative Arrangements Order 2026, Schedule 1](https://legislation.nt.gov.au/api/sitecore/Act/PDF?id=11575) (commenced and gazetted S41 on 1 June 2026) | 1 June 2026 | PDF | 27 |

Row counts in the table above are rows remaining in `organisations.csv` after deduplication, attributed to the source that was kept.

## Known coverage gaps

- **Queensland and NT** are limited to agencies named in the current Administrative Arrangements Order (plus, for Queensland, two extra agencies from the ministers-and-departments page: Arts Queensland and Trade and Investment Queensland). Neither jurisdiction publishes a downloadable register of all statutory bodies. Queensland’s [Government Bodies](https://governmentbodies.premiers.qld.gov.au/) register has no export. NT Schedule 2 bodies that are not nominated as agencies in Schedule 1 are not included.
- **Tasmania:** the Department of Premier and Cabinet page *About the Tasmanian State Service* states there are 18 agencies (nine departments and nine state authorities) but does not name them. Names come from FMA Schedule 1 (general government sector and legislative agencies) plus the tas.gov.au “Our agencies” page, which names 17 State Service bodies. Four of those are not in the FMA list: Homes Tasmania, Macquarie Point Development Corporation, Port Arthur Historic Site Management Authority, and The Public Trustee. The 18th State Service agency is not named on either page.
- **WA** includes 146 local governments from Schedule 1 of the Public Sector Management Act, as well as universities and government trading enterprises, because they appear in the PSC mailing list.
- **SA** Budget Appendix D (the most complete official entity inventory) was reconstructed from a two-column PDF layout in the 2026–27 Budget Statement, pages 168–169. The Administrative Units PDF was used only for current public service units; its historical/abolished section was excluded. After deduplication, only Office of Venue Management was unique to that PDF.
- **Victoria** is the VPSC list of *public sector employers*, not every public entity (non-employer bodies such as some cemetery trusts are out of scope).
- **NSW** is the Treasury GSF agency list, which Treasury describes as indicative and not real-time, and not itself determinative of GSF status. It is broader than the public-facing departments directory (it includes universities and controlled entities).
- The **ACT Directory** (directory.act.gov.au) was not used, because that site warns it still reflects pre-1 July 2025 structures.

## Licence and use

The compiled table is a convenience extract from official public sources. Each source retains its own copyright and licence (AGOR is CC BY 3.0 Australia; check the originating agency for the others). This snapshot is not an official government register and will go out of date as machinery-of-government changes occur.
