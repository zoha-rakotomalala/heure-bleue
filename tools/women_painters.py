"""Build data/women_painters.json from Wikidata: women painters who died before 1956
(so their work can be public domain) and have a Wikimedia Commons category.

    python3 tools/women_painters.py            # writes data/women_painters.json
    python3 tools/women_painters.py --min-sitelinks 12

The indexer's `women` source walks each painter's "Paintings by <name>" category on
Commons. The list is ordered by how many Wikipedias know the painter, so a bounded run
reaches the best-documented ones first. Painters without a "Paintings by" category
are skipped by the indexer at walk time (their Commons category holds portraits OF
them, not works BY them: Sarah Bernhardt, empresses, queens).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "data" / "women_painters.json"
UA = {"User-Agent": "heure-bleue/1.0 (https://github.com/zoha-rakotomalala/heure-bleue; personal desk display)"}
SPARQL = "https://query.wikidata.org/sparql"

QUERY = """SELECT ?p ?pLabel ?cat ?born ?died ?sites WHERE {
  ?p wdt:P106 wd:Q1028181; wdt:P21 wd:Q6581072; wdt:P373 ?cat; wdt:P570 ?died; wikibase:sitelinks ?sites.
  OPTIONAL { ?p wdt:P569 ?born. }
  FILTER(YEAR(?died) < 1956) FILTER(?sites >= %d)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,de,nl,it,es,sv,fi". }
} ORDER BY DESC(?sites)"""


def fetch(min_sitelinks: int) -> list[dict]:
    url = SPARQL + "?format=json&query=" + urllib.parse.quote(QUERY % min_sitelinks)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                data = json.load(r)
            break
        except Exception as exc:  # noqa: BLE001  the query service times out under load; try again
            print(f"  wikidata: {exc}, retrying", file=sys.stderr)
            time.sleep(20 * (attempt + 1))
    else:
        raise SystemExit("wikidata query service did not answer")
    rows, seen = [], set()
    for b in data["results"]["bindings"]:
        qid = b["p"]["value"].rsplit("/", 1)[-1]
        if qid in seen:
            continue
        seen.add(qid)
        rows.append({
            "qid": qid,
            "name": b["pLabel"]["value"],
            "category": b["cat"]["value"],
            "born": (b.get("born") or {}).get("value", "")[:4] or None,
            "died": b["died"]["value"][:4],
            "sitelinks": int(b["sites"]["value"]),
        })
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-sitelinks", type=int, default=8, help="how many Wikipedias must know the painter")
    args = ap.parse_args(argv)
    rows = fetch(args.min_sitelinks)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(rows)} women painters -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
