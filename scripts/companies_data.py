"""Curated state/territory government-owned companies, GOCs, GBEs/GTEs and
subsidiaries (added November 2026). Each entry cites the official source it
was taken from. Websites are candidates; add_companies.py keeps one only when
it loads.
"""

SOURCES = {
 "QLD_TSY": ("Queensland Treasury – Government-owned corporations (list of GOCs)", "https://www.treasury.qld.gov.au/policies-and-programs/economy/government-owned-corporations/", "2026", "HTML",
             "Queensland's 11 GOCs declared under the Government Owned Corporations Regulation 2024, Schedule 1, with shareholding ministers."),
 "QLD_QAO": ("Queensland Audit Office – State entities 2025 (Report 11: 2025–26), Appendices F and I", "https://www.parliament.qld.gov.au/Work-of-the-Assembly/Tabled-Papers/docs/5826T0321/5826t321.pdf", "2026", "PDF",
             "Companies listed as controlled public sector entities: Appendix F (entities preparing financial reports, with their controlled entities) and Appendix I (controlled entities not preparing financial reports, by parent, plus entities managed by QIC Limited). Trusts, funds, projects, insurance cells, 'as trustee' entries and entities footnoted as managed but not controlled were excluded."),
 "TAS_TSY": ("Treasury and Finance Tasmania – Tasmanian Government Businesses", "https://www.treasury.tas.gov.au/government-businesses/tasmanian-government-businesses", "2026", "HTML",
             "Tasmania's Government Business Enterprises and State-owned Companies."),
 "TAS_HYDRO": ("Hydro Tasmania Annual Report 2024-25, Note 29 Controlled entities", "https://www.hydro.com.au/sites/default/files/2026-01/hydro-tasmania-annual-report-2025.pdf", "2025", "PDF",
               "Controlled entities of the Hydro-Electric Corporation, including second-tier subsidiaries named in the note's footnotes."),
 "TAS_PORTS": ("TasPorts Annual Report 2024–25, controlled entities", "https://tasports.com.au/volumes/documents/Annual-Reports/TasPorts-Annual-Report-2024-2025.pdf", "2025", "PDF",
               "Bass Island Line Pty Ltd, the wholly owned TasPorts subsidiary operating the King Island shipping service."),
 "WA_GTE": ("WA Department of Treasury and Finance – GTE governance (GTEs covered by the Government Trading Enterprises Act 2023)", "https://www.wa.gov.au/organisation/department-of-treasury-and-finance/gte-governance", "2026", "HTML",
            "The 12 in-scope GTEs and the 4 second-tranche GTEs."),
 "WA_OAG": ("WA Office of the Auditor General – State Government 2025 Financial Audit Results (Report 6), Appendix 1", "https://audit.wa.gov.au/wp-content/uploads/2025/12/Report-6-State-Government-2025-Financial-Audit-Results.pdf", "December 2025", "PDF",
            "State government entities audited for 2024-25; used for the companies and government trading bodies on the list."),
 "VIC_FR": ("Victoria 2024-25 Financial Report, Note 8.8 Controlled entities", "https://www.dtf.vic.gov.au/sites/default/files/2025-10/2024-25-Financial-Report.pdf", "October 2025", "PDF",
            "Significant controlled entities of the State of Victoria; used for the public non-financial and public financial corporation sectors and the general government companies."),
 "NSW_TSSA": ("NSW Report on the State Finances 2024-25, Total State Sector Accounts Note 36 Controlled Entities", "https://www.nsw.gov.au/sites/default/files/noindex/2025-11/report-on-the-state-finances-2024-25.pdf", "November 2025", "PDF",
              "Controlled entities of the State of NSW by ABS sector; used for public non-financial and public financial corporations (excluding investment trusts and funds) and general government companies and ministerial holding corporations."),
 "SA_BS": ("SA 2025-26 Budget Statement, Appendix D – Public Non-Financial and Public Financial Corporations sectors", "https://www.treasury.sa.gov.au/__data/assets/pdf_file/0003/1159383/2025-26-Budget-Statement.pdf", "June 2025", "PDF",
           "South Australia's government businesses (PNFC and PFC sectors)."),
 "ACT_ICON": ("Icon Water – Who are we", "https://www.iconwater.com.au/about-us/who-are-we", "2026", "HTML",
              "Icon Water Limited's wholly owned subsidiaries and the ActewAGL joint venture partnerships."),
 "NT_PWC": ("Power and Water Corporation – About us; Territory Generation and Jacana Energy annual reports", "https://www.powerwater.com.au/about", "2026", "HTML",
            "Northern Territory government owned corporations and Power and Water's subsidiary Indigenous Essential Services Pty Ltd."),
}

# (title, type_of_body, parent, portfolio, gfs, website, source_key, note)
E = []
def add(j, title, typ, parent="", portfolio="", gfs="", website="", src="", note=""):
    E.append(dict(j=j, title=title, typ=typ, parent=parent, portfolio=portfolio, gfs=gfs, website=website, src=src, note=note))

# ---------------- Queensland GOCs (Treasury list) ----------------
QGOC = [("CleanCo Queensland Limited", "https://www.cleancoqld.com.au"), ("CS Energy Limited", "https://www.csenergy.com.au"),
        ("Energy Queensland Limited", "https://www.energyq.com.au"), ("Far North Queensland Ports Corporation Limited (trading as Ports North)", "https://www.portsnorth.com.au"),
        ("Gladstone Ports Corporation Limited", "https://www.gpcl.com.au"), ("North Queensland Bulk Ports Corporation Limited", "https://nqbp.com.au"),
        ("Port of Townsville Limited", "https://www.townsville-port.com.au"), ("QIC Limited", "https://www.qic.com.au"),
        ("Queensland Electricity Transmission Corporation Limited (trading as Powerlink Queensland)", "https://www.powerlink.com.au"),
        ("Stanwell Corporation Limited", "https://www.stanwell.com"), ("Sunwater Limited", "https://www.sunwater.com.au")]
for t, w in QGOC:
    add("Queensland", t, "Government owned corporation", "", "", "PNFC" if "QIC" not in t else "PFC", w, "QLD_TSY", "GOC under the Government Owned Corporations Act 1993 (Qld)")

# Queensland companies from QAO (curated from scripts parse of Appendices F and I)
QSITES = {"Energex Limited": "https://www.energex.com.au", "Ergon Energy Corporation Limited": "https://www.ergon.com.au",
          "Ergon Energy Queensland Pty Ltd": "https://www.ergon.com.au", "Yurika Pty Ltd": "https://www.yurika.com.au",
          "Queensland Rail Limited": "https://www.queenslandrail.com.au", "Screen Queensland Pty Ltd": "https://screenqld.com.au",
          "The Queensland Music Festival Pty Ltd": "https://qmf.org.au", "Aviation Australia Pty Ltd": "https://www.aviationaustralia.aero",
          "Queensland Hydro Pty Ltd": "https://www.qldhydro.com.au", "Transmax Pty Ltd": "https://www.transmax.com.au",
          "Manufacturing Skills Queensland Limited": "https://manufacturingskillsqld.com.au",
          "Aboriginal Centre for the Performing Arts Pty Ltd": "https://www.acpa.net.au",
          "Gold Coast Events Management Ltd (trading as Events Management Queensland)": "",
          "Queensland Lottery Corporation Pty Ltd": ""}
QAO_PARENT_FIX = {"Stanwell": "Stanwell Corporation Limited", "Powerlink": "Queensland Electricity Transmission Corporation Limited (trading as Powerlink Queensland)",
                  "North Queensland Bulk Ports Limited": "North Queensland Bulk Ports Corporation Limited", "Queensland Rail": "Queensland Rail"}

# ---------------- Tasmania ----------------
for t, w in [("Sustainable Timber Tasmania", "https://www.sttas.com.au"), ("Hydro-Electric Corporation (Hydro Tasmania)", "https://www.hydro.com.au"),
             ("Motor Accidents Insurance Board", "https://www.maib.tas.gov.au"), ("Port Arthur Historic Site Management Authority", "https://portarthur.org.au"),
             ("Tasmanian Public Finance Corporation", "https://www.tascorp.com.au"), ("The Public Trustee", "https://www.publictrustee.tas.gov.au")]:
    add("Tasmania", t, "Government Business Enterprise", "", "", "PFC" if t in ("Motor Accidents Insurance Board", "Tasmanian Public Finance Corporation") else "PNFC", w, "TAS_TSY", "GBE under the Government Business Enterprises Act 1995 (Tas)")
for t, w in [("Aurora Energy Pty Ltd", "https://www.auroraenergy.com.au"), ("Metro Tasmania Pty Ltd", "https://www.metrotas.com.au"),
             ("Tasmanian Irrigation Pty Ltd", "https://www.tasmanianirrigation.com.au"), ("Tasmanian Networks Pty Ltd (TasNetworks)", "https://www.tasnetworks.com.au"),
             ("Tasmanian Ports Corporation Pty Ltd (TasPorts)", "https://www.tasports.com.au"), ("Tasmanian Railway Pty Ltd (TasRail)", "https://www.tasrail.com.au"),
             ("Tasracing Pty Ltd", "https://tasracing.com.au"), ("TT-Line Company Pty Ltd", "https://www.spiritoftasmania.com.au")]:
    add("Tasmania", t, "State-owned company", "", "", "PNFC", w, "TAS_TSY", "State-owned company (Corporations Act 2001 company owned by the State of Tasmania)")
HY = "Hydro-Electric Corporation (Hydro Tasmania)"
for t, w in [("Bell Bay Power Pty Ltd", ""), ("Lofty Ranges Power Pty Ltd", ""), ("Bell Bay Three Pty Ltd", ""), ("RE Storage Project Holding Pty Ltd", ""),
             ("Entura Hydro Tasmania Consulting (Holding) Pty Ltd", "https://www.entura.com.au"), ("Momentum Energy Pty Limited", "https://www.momentumenergy.com.au"),
             ("HT Wind Operations Pty Ltd", ""), ("Hydro Tasmania South Africa (Pty) Ltd", ""), ("AETV Pty Ltd", "")]:
    add("Tasmania", t, "Subsidiary of a Government Business Enterprise", HY, "", "PNFC", w, "TAS_HYDRO", "Wholly owned controlled entity of Hydro Tasmania")
for t in ["Tarraleah Village Holdings Pty Ltd", "Woolnorth Studland Bay Holdings Pty Ltd", "Heemskirk Holdings Pty Ltd", "HT Wind Developments Pty Ltd",
          "Hydro Tasmania Retail Pty Ltd", "Heemskirk Windfarm Pty Ltd"]:
    add("Tasmania", t, "Subsidiary of a Government Business Enterprise", "HT Wind Operations Pty Ltd" if t != "Heemskirk Windfarm Pty Ltd" else "Heemskirk Holdings Pty Ltd", "", "PNFC", "", "TAS_HYDRO", "Second-tier wholly owned subsidiary in the Hydro Tasmania group")
add("Tasmania", "Hydro Tasmania Consulting India Private Limited", "Subsidiary of a Government Business Enterprise", "Entura Hydro Tasmania Consulting (Holding) Pty Ltd", "", "PNFC", "", "TAS_HYDRO", "Second-tier subsidiary in the Hydro Tasmania group (Entura)")
add("Tasmania", "Hydro Tasmania Neusberg (Pty) Ltd", "Subsidiary of a Government Business Enterprise", "Hydro Tasmania South Africa (Pty) Ltd", "", "PNFC", "", "TAS_HYDRO", "92% owned by Hydro Tasmania South Africa (Pty) Ltd")
add("Tasmania", "Bass Island Line Pty Ltd", "Subsidiary of a State-owned company", "Tasmanian Ports Corporation Pty Ltd (TasPorts)", "", "PNFC", "", "TAS_PORTS", "Wholly owned TasPorts subsidiary operating the King Island shipping service")

# ---------------- Western Australia ----------------
for t, w, g in [("Electricity Networks Corporation (Western Power)", "https://www.westernpower.com.au", "PNFC"),
                ("Electricity Generation and Retail Corporation (Synergy)", "https://www.synergy.net.au", "PNFC"),
                ("Regional Power Corporation (Horizon Power)", "https://www.horizonpower.com.au", "PNFC"),
                ("Bunbury Water Corporation (Aqwest)", "https://www.aqwest.com.au", "PNFC"),
                ("Busselton Water Corporation", "https://www.busseltonwater.wa.gov.au", "PNFC"),
                ("Water Corporation", "https://www.watercorporation.com.au", "PNFC"),
                ("Fremantle Port Authority", "https://www.fremantleports.com.au", "PNFC"), ("Kimberley Ports Authority", "https://www.kimberleyports.wa.gov.au", "PNFC"),
                ("Mid West Ports Authority", "https://www.midwestports.com.au", "PNFC"), ("Pilbara Ports Authority", "https://www.pilbaraports.com.au", "PNFC"),
                ("Southern Ports Authority", "https://www.southernports.com.au", "PNFC"),
                ("Western Australian Land Authority (DevelopmentWA)", "https://developmentwa.com.au", "PNFC"),
                ("Forest Products Commission", "https://www.fpc.wa.gov.au", "PNFC"), ("Gold Corporation (The Perth Mint)", "https://www.perthmint.com", "PFC"),
                ("Insurance Commission of Western Australia", "https://www.icwa.wa.gov.au", "PFC"),
                ("Western Australian Treasury Corporation", "https://www.watc.wa.gov.au", "PFC")]:
    add("WA", t, "Government Trading Enterprise", "", "", g, w, "WA_GTE", "In-scope or second-tranche GTE under the Government Trading Enterprises Act 2023 (WA)")
for t, typ, parent, w in [("ECU Hold Trust Pty Ltd", "Controlled company", "Edith Cowan University", ""),
                          ("Edith Cowan Accommodation Holdings Pty Ltd", "Controlled company", "Edith Cowan University", ""),
                          ("Flat Rocks Wind Farm Stage 2 Pty Ltd", "Subsidiary of a Government Trading Enterprise", "Electricity Generation and Retail Corporation (Synergy)", ""),
                          ("Hedland Maritime Initiative Pty Ltd", "Subsidiary of a Government Trading Enterprise", "Pilbara Ports Authority", ""),
                          ("Keystart Loans Limited", "Controlled company (dormant from 1 July 2025)", "Housing Authority", "https://www.keystart.com.au"),
                          ("Perth International Arts Festival Ltd", "Controlled company", "", "https://perthfestival.com.au"),
                          ("Racing and Wagering Western Australia", "Government trading body", "", "https://www.rwwa.com.au"),
                          ("Lotteries Commission (Lotterywest)", "Government trading body", "", "https://www.lotterywest.wa.gov.au"),
                          ("Western Australian Coastal Shipping Commission", "Government trading body", "", "")]:
    add("WA", t, typ, parent, "", "PNFC", w, "WA_OAG", "")

# ---------------- Victoria (Financial Report Note 8.8) ----------------
VPNFC = {
 "Department of Energy, Environment and Climate Action": [("Agriculture Victoria Services Pty Ltd", ""), ("Alpine Resorts Victoria", "https://www.alpineresorts.vic.gov.au"),
     ("Dairy Food Safety Victoria", "https://www.dairysafe.vic.gov.au"), ("Great Ocean Road Coast and Parks Authority", "https://www.marinecoastalparks.vic.gov.au"),
     ("Melbourne Market Authority", "https://www.melbournemarket.com.au"), ("Murray Valley Wine Grape Industry Development Committee", ""),
     ("Phillip Island Nature Parks", "https://www.penguins.org.au"), ("PrimeSafe", "https://www.primesafe.vic.gov.au"),
     ("SEC Victoria Pty Ltd", "https://www.secvictoria.com.au"), ("Victorian Strawberry Industry Development Committee", ""),
     ("Barwon Region Water Corporation", "https://www.barwonwater.vic.gov.au"), ("Central Gippsland Region Water Corporation", "https://www.gippswater.com.au"),
     ("Central Highlands Region Water Corporation", "https://www.chw.net.au"), ("Coliban Region Water Corporation", "https://coliban.com.au"),
     ("East Gippsland Region Water Corporation", "https://www.egwater.vic.gov.au"), ("Gippsland and Southern Rural Water Corporation", "https://www.srw.com.au"),
     ("Goulburn Murray Rural Water Corporation", "https://www.g-mwater.com.au"), ("Goulburn Valley Region Water Corporation", "https://www.gvwater.vic.gov.au"),
     ("Grampians Wimmera Mallee Water Corporation", "https://www.gwmwater.org.au"), ("Greater Western Water", "https://www.gww.com.au"),
     ("Lower Murray Urban and Rural Water Corporation", "https://www.lmw.vic.gov.au"), ("Melbourne Water Corporation", "https://www.melbournewater.com.au"),
     ("North East Region Water Corporation", "https://www.newater.com.au"), ("South East Water Corporation", "https://southeastwater.com.au"),
     ("South Gippsland Region Water Corporation", "https://sgwater.com.au"), ("Wannon Region Water Corporation", "https://www.wannonwater.com.au"),
     ("Westernport Region Water Corporation", "https://www.westernportwater.com.au"), ("Yarra Valley Water Corporation", "https://www.yvw.com.au"),
     ("Zoological Parks and Gardens Board", "https://www.zoo.org.au")],
 "Department of Families, Fairness and Housing": [("Homes Victoria", "https://www.homes.vic.gov.au"), ("Queen Victoria Women's Centre Trust", "https://qvwc.org.au")],
 "Department of Health": [("Ballarat General Cemeteries Trust", ""), ("Geelong Cemeteries Trust", ""), ("The Greater Metropolitan Cemeteries Trust", "https://www.gmct.com.au"),
     ("Southern Metropolitan Cemeteries Trust", "https://www.smct.org.au"), ("The Mildura Cemetery Trust", ""), ("Remembrance Parks Central Victoria", "")],
 "Department of Jobs, Skills, Industry and Regions": [("Australian Grand Prix Corporation", "https://www.grandprix.com.au"), ("Geelong Performing Arts Centre Trust", "https://www.gpac.org.au"),
     ("Kardinia Park Stadium Trust", ""), ("Launch Victoria Ltd", "https://launchvic.org"), ("Melbourne and Olympic Parks Trust", "https://www.mopt.com.au"),
     ("Melbourne Arts Precinct Corporation", ""), ("Puffing Billy Railway Board", "https://puffingbilly.com.au"), ("State Sport Centres Trust", ""),
     ("Victorian Arts Centre Trust", "https://www.artscentremelbourne.com.au"), ("Victorian Convention and Event Trust", "https://mcec.com.au")],
 "Department of Justice and Community Safety": [("Greyhound Racing Victoria", "https://grv.org.au"), ("Harness Racing Victoria", "https://www.thetrots.com.au")],
 "Department of Premier and Cabinet": [("VITS Language Loop", "https://www.languageloop.com.au")],
 "Department of Transport and Planning": [("Development Victoria", "https://www.development.vic.gov.au"), ("North East Link State Tolling Corporation", ""),
     ("Melbourne Port Lessor Pty Ltd", ""), ("Port of Hastings Corporation", ""), ("Ports Victoria", "https://ports.vic.gov.au"),
     ("V/Line Corporation", "https://www.vline.com.au"), ("Victorian Rail Track", "")],
 "Department of Treasury and Finance": [("Victorian Plantations Corporation", ""), ("Workplace Injury Commission", "")],
}
for port, items in VPNFC.items():
    for t, w in items:
        add("Victoria", t, "Public non-financial corporation", "", port, "PNFC", w, "VIC_FR", "")
add("Victoria", "SEC Infrastructure Pty Ltd", "Subsidiary of a state-owned company", "SEC Victoria Pty Ltd", "Department of Energy, Environment and Climate Action", "PNFC", "", "VIC_FR", "Declared a state-owned company under the State Owned Enterprises Act 1992 (Vic)")
add("Victoria", "SEC Energy Pty Ltd", "Subsidiary of a state-owned company", "SEC Victoria Pty Ltd", "Department of Energy, Environment and Climate Action", "PNFC", "", "VIC_FR", "Declared a state-owned company under the State Owned Enterprises Act 1992 (Vic)")
for port, t, w in [("Department of Jobs, Skills, Industry and Regions", "Breakthrough Victoria Pty Ltd", "https://breakthroughvictoria.com"),
                   ("Department of Treasury and Finance", "State Trustees Limited", "https://www.statetrustees.com.au"),
                   ("Department of Treasury and Finance", "Transport Accident Commission", "https://www.tac.vic.gov.au"),
                   ("Department of Treasury and Finance", "Treasury Corporation of Victoria", "https://www.tcv.vic.gov.au"),
                   ("Department of Treasury and Finance", "Victorian Funds Management Corporation", "https://www.vfmc.vic.gov.au")]:
    add("Victoria", t, "Public financial corporation", "", port, "PFC", w, "VIC_FR", "")
for t, w in [("Dockland Studios Melbourne Pty Ltd", "https://www.docklandsstudios.com.au"), ("Melbourne Recital Centre Limited", "https://www.melbournerecital.com.au"),
             ("Victorian Institute of Sport Limited", "https://www.vis.org.au")]:
    add("Victoria", t, "Government-controlled company", "", "Department of Jobs, Skills, Industry and Regions", "GGS", w, "VIC_FR", "")

# ---------------- NSW (TSSA Note 36) ----------------
for t, w, typ in [("Cobar Water Board", "", "Public non-financial corporation"), ("Essential Energy", "https://www.essentialenergy.com.au", "State-owned corporation"),
                  ("Intium Pty Limited", "", "Subsidiary of a state-owned corporation"), ("Forestry Corporation of New South Wales", "https://www.forestcorporation.com.au", "State-owned corporation"),
                  ("Hunter Water Corporation", "https://www.hunterwater.com.au", "State-owned corporation"), ("Hunter Water Ministerial Corporation", "", "Public non-financial corporation"),
                  ("Jenolan Caves Reserves Trust", "https://www.jenolancaves.org.au", "Public non-financial corporation"), ("Landcom", "https://www.landcom.com.au", "State-owned corporation"),
                  ("Newcastle Port Corporation", "", "Public non-financial corporation"), ("New South Wales Land and Housing Corporation", "", "Public non-financial corporation"),
                  ("NSW Trains", "", "Public non-financial corporation"), ("Place Management NSW", "", "Public non-financial corporation"),
                  ("Residual Transport Corporation", "", "Public non-financial corporation"), ("State Sporting Venues Authority", "", "Public non-financial corporation"),
                  ("State Transit Authority of New South Wales", "", "Public non-financial corporation"), ("Sydney Ferries", "", "Public non-financial corporation"),
                  ("Sydney Opera House Trust", "https://www.sydneyoperahouse.com", "Public non-financial corporation"), ("Sydney Trains", "", "Public non-financial corporation"),
                  ("Sydney Water Corporation", "https://www.sydneywater.com.au", "State-owned corporation"), ("Teacher Housing Authority of New South Wales", "", "Public non-financial corporation"),
                  ("Transport Asset Manager of New South Wales", "", "State-owned corporation"), ("Venues NSW", "https://www.venuesnsw.com", "Public non-financial corporation"),
                  ("Viral Vector Manufacturing Facility Pty Ltd", "", "Government-controlled company"), ("Waste Assets Management Corporation", "", "Public non-financial corporation"),
                  ("WaterNSW", "https://www.waternsw.com.au", "State-owned corporation"), ("WaterNSW Infrastructure Pty Ltd", "", "Subsidiary of a state-owned corporation"),
                  ("Zoological Parks Board of New South Wales", "https://taronga.org.au", "Public non-financial corporation")]:
    parent = {"Intium Pty Limited": "Essential Energy", "WaterNSW Infrastructure Pty Ltd": "WaterNSW"}.get(t, "")
    add("NSW", t, typ, parent, "", "PNFC", w, "NSW_TSSA", "")
for t, w in [("Insurance and Care NSW", "https://www.icare.nsw.gov.au"), ("Lifetime Care and Support Authority of New South Wales", ""),
             ("NSW Treasury Corporation", "https://www.tcorp.nsw.gov.au"), ("SAS Trustee Corporation", "https://www.aware.com.au")]:
    add("NSW", t, "Public financial corporation", "", "", "PFC", w if t != "SAS Trustee Corporation" else "", "NSW_TSSA", "")
for t in ["ERIC Alpha Holdings Pty Ltd", "ERIC Epsilon Holdings", "Generator Property Management Pty Ltd", "NSW Rent Buy Pty Ltd",
          "Alpha Distribution Ministerial Holding Corporation", "Electricity Transmission Ministerial Holding Corporation", "Epsilon Distribution Ministerial Holding Corporation",
          "Electricity Assets Ministerial Holding Corporation", "Port of Newcastle Lessor Ministerial Holding Corporation",
          "Port Botany Lessor Ministerial Holding Corporation", "Port Kembla Lessor Ministerial Holding Corporation"]:
    add("NSW", t, "Government-controlled company" if "Corporation" not in t else "Ministerial holding corporation", "", "", "GGS", "", "NSW_TSSA", "")

# ---------------- South Australia (Budget Statement Appendix D) ----------------
for t, w, g in [("Adelaide Cemeteries Authority", "https://www.aca.sa.gov.au", "PNFC"), ("Adelaide Festival Centre Trust", "https://www.adelaidefestivalcentre.com.au", "PNFC"),
                ("Adelaide Venue Management Corporation", "https://www.avmc.com.au", "PNFC"), ("Distribution Lessor Corporation", "", "PNFC"),
                ("Generation Lessor Corporation", "", "PNFC"), ("Public Trustee", "https://www.publictrustee.sa.gov.au", "PNFC"),
                ("South Australian Forestry Corporation (trading as ForestrySA)", "https://www.forestrysa.sa.gov.au", "PNFC"),
                ("South Australian Housing Trust", "https://www.housing.sa.gov.au", "PNFC"), ("South Australian Motor Sport Board", "", "PNFC"),
                ("South Australian Water Corporation (trading as SA Water)", "https://www.sawater.com.au", "PNFC"),
                ("State Owned Generators Leasing Co Pty Ltd", "", "PNFC"), ("Transmission Lessor Corporation", "", "PNFC"),
                ("Urban Renewal Authority (trading as Renewal SA)", "https://renewalsa.sa.gov.au", "PNFC"),
                ("West Beach Trust (trading as West Beach Parks)", "https://www.westbeachparks.com.au", "PNFC"),
                ("HomeStart Finance", "https://www.homestart.com.au", "PFC"), ("Lifetime Support Authority", "https://lifetimesupport.sa.gov.au", "PFC"),
                ("Motor Accident Commission", "", "PFC"), ("Return to Work Corporation of South Australia (trading as ReturnToWorkSA)", "https://www.rtwsa.com", "PFC"),
                ("South Australian Government Financing Authority (trading as SAFA)", "https://www.safa.sa.gov.au", "PFC"),
                ("Superannuation Funds Management Corporation of South Australia (trading as Funds SA)", "https://www.funds.sa.gov.au", "PFC")]:
    add("SA", t, "Public non-financial corporation" if g == "PNFC" else "Public financial corporation", "", "", g, w, "SA_BS", "")

# ---------------- ACT ----------------
add("ACT", "Icon Distribution Investments Limited", "Subsidiary of a territory-owned corporation", "Icon Water Limited", "", "PNFC", "", "ACT_ICON", "50% partner in the ActewAGL Distribution Partnership (Evoenergy)")
add("ACT", "Icon Retail Investments Limited", "Subsidiary of a territory-owned corporation", "Icon Water Limited", "", "PNFC", "", "ACT_ICON", "50% partner in the ActewAGL Retail Partnership")
add("ACT", "ActewAGL Distribution Partnership (Evoenergy)", "Joint venture partnership (50% territory-owned)", "Icon Distribution Investments Limited", "", "PNFC", "https://www.evoenergy.com.au", "ACT_ICON", "Joint venture between Icon Water and Jemena")
add("ACT", "ActewAGL Retail Partnership", "Joint venture partnership (50% territory-owned)", "Icon Retail Investments Limited", "", "PNFC", "https://www.actewagl.com.au", "ACT_ICON", "Joint venture between Icon Water and AGL Energy")

# ---------------- NT ----------------
add("NT", "Power and Water Corporation", "Government owned corporation", "", "", "PNFC", "https://www.powerwater.com.au", "NT_PWC", "GOC under the Government Owned Corporations Act 2001 (NT)")
add("NT", "Power Generation Corporation (trading as Territory Generation)", "Government owned corporation", "", "", "PNFC", "https://territorygeneration.com.au", "NT_PWC", "GOC under the Government Owned Corporations Act 2001 (NT)")
add("NT", "Power Retail Corporation (trading as Jacana Energy)", "Government owned corporation", "", "", "PNFC", "https://jacanaenergy.com.au", "NT_PWC", "GOC under the Government Owned Corporations Act 2001 (NT)")
add("NT", "Indigenous Essential Services Pty Ltd", "Subsidiary of a government owned corporation", "Power and Water Corporation", "", "PNFC", "", "NT_PWC", "Not-for-profit wholly owned subsidiary providing essential services to remote communities")
