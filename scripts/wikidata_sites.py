"""Find official websites (Wikidata P856) for organisations with no Website Address.

Accepts a match only when the Wikidata label or alias equals the organisation title
(case-insensitive) and the item is Australian (P17 = Q408, or its description names
Australia or a state/territory). Output: data/icon_work/wikidata_sites.json
"""
import csv, json, re, time, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = Path("/workspace/icons_work/wikidata_sites.json")
UA = "aus-gov-orgs-icons/1.0 (https://github.com/2prnt/aus-gov-orgs)"
API = "https://www.wikidata.org/w/api.php"
AUS_WORDS = re.compile(r"australia|new south wales|victoria|queensland|tasmania|northern territory|capital territory|\bnsw\b|\bact\b", re.I)
S = requests.Session(); S.headers["User-Agent"] = UA

def norm(s): return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def get(params):
    for i in range(4):
        try:
            r = S.get(API, params={**params, "format": "json"}, timeout=20)
            if r.status_code == 429: time.sleep(5 * (i + 1)); continue
            return r.json()
        except Exception:
            time.sleep(2 * (i + 1))
    return {}

def lookup(title):
    res = get({"action": "wbsearchentities", "search": title[:250], "language": "en", "limit": 7, "type": "item"})
    ids = [h["id"] for h in res.get("search", []) if norm(h.get("match", {}).get("text", "")) == norm(title) or norm(h.get("label", "")) == norm(title)]
    if not ids: return None
    ents = get({"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|descriptions|labels"}).get("entities", {})
    for qid in ids:
        e = ents.get(qid, {}); cl = e.get("claims", {})
        sites = [c["mainsnak"].get("datavalue", {}).get("value") for c in cl.get("P856", []) if c.get("rank") != "deprecated"]
        sites = [s for s in sites if isinstance(s, str)]
        if not sites: continue
        countries = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in cl.get("P17", [])]
        desc = e.get("descriptions", {}).get("en", {}).get("value", "")
        if "Q408" in countries or AUS_WORDS.search(desc) or (not countries and re.search(r"\.au(/|$)", sites[0])):
            return {"qid": qid, "website": sites[0], "description": desc}
    return None

def main():
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    todo = [r for r in rows if not r["Website Address"].strip()]
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = [r for r in todo if r["Id"] + "|" + r["Title"] not in out]
    def work(r):
        return r["Id"] + "|" + r["Title"], lookup(r["Title"])
    with ThreadPoolExecutor(6) as ex:
        for i, (k, v) in enumerate(ex.map(work, todo)):
            out[k] = v
            if i % 100 == 0:
                OUT.write_text(json.dumps(out, indent=1)); print(i, len(todo), sum(1 for x in out.values() if x), flush=True)
    OUT.write_text(json.dumps(out, indent=1))
    print("done", sum(1 for x in out.values() if x), "found of", len(out))

if __name__ == "__main__": main()
