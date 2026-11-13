"""Stage 1c: find >= 128 px logos for sites used as parent/portfolio fallbacks
whose normal icon is smaller (stored in hosts.json as "BIG:<url>")."""
import csv, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from fetch_icons import WORK, CACHE
from fetch_icons_deep import fetch_deep, host_ok
from build_icons import PORTFOLIO, host_root, norm

ROOT = Path(__file__).resolve().parent.parent
def main():
    hosts = json.loads((WORK / "hosts.json").read_text())
    wd = json.loads((WORK / "wikidata_sites.json").read_text())
    rows = list(csv.DictReader(open(ROOT / "data/organisations.csv", encoding="utf-8")))
    parents = {(r["Jurisdiction"], norm(r["Parent Organisation"])) for r in rows if r["Parent Organisation"]}
    urls = {u for lst in PORTFOLIO.values() for _, u in lst} | {"https://www.dva.gov.au/"}
    for r in rows:
        if (r["Jurisdiction"], norm(r["Title"])) in parents:
            site = r["Website Address"].strip() or ((wd.get(r["Id"] + "|" + r["Title"]) or {}).get("website", ""))
            if host_root(site): urls.add(host_root(site))
    todo = []
    for u in sorted(urls):
        v = hosts.get(u)
        if v and host_ok(v) and Image.open(CACHE / v["file"]).size[0] >= 128: continue
        if "BIG:" + u in hosts: continue
        todo.append(u)
    print("big fetch", len(todo), flush=True)
    with ThreadPoolExecutor(6) as ex:
        for u, res in zip(todo, ex.map(lambda u: fetch_deep(u, min_side=128, suffix="-big"), todo)):
            hosts["BIG:" + u] = res
            print(u, res.get("ok"), res.get("src", "")[:100], flush=True)
    (WORK / "hosts.json").write_text(json.dumps(hosts, indent=1))
if __name__ == "__main__": main()
