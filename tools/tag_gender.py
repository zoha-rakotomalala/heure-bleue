"""Tag every painting with its painter's gender, read from Wikidata (P21).

    python3 tools/tag_gender.py                  # data/paintings.json (+ paintings.local.json if present)
    python3 tools/tag_gender.py --refresh        # ignore the cache and ask Wikidata again

Each distinct painter name is searched once (wbsearchentities, then the entity's P21 and
P106). Results are cached in data/painters.json as {name: {"qid", "gender"}} so a rerun
costs nothing for names already known. A painting gets "gender": "f" or "m" when the
match is a painter (P106 includes painter/artist); unknown names get no field. The
women indexing pass sets "f" itself; this tool never overwrites an existing "f".
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
PAINTINGS = HERE / "data" / "paintings.json"
LOCAL = HERE / "data" / "paintings.local.json"
CACHE = HERE / "data" / "painters.json"
UA = {"User-Agent": "heure-bleue/1.0 (https://github.com/zoha-rakotomalala/heure-bleue; personal desk display)"}
API = "https://www.wikidata.org/w/api.php"
FEMALE, MALE = "Q6581072", "Q6581097"
PAINTER_LIKE = {"Q1028181", "Q483501", "Q15296811", "Q3391743", "Q1281618", "Q644687", "Q10732476", "Q329439"}  # painter, artist, drawer, visual artist, sculptor, illustrator, watercolourist, engraver
SKIP = ("unknown", "anonym", "anoniem", "manner of", "circle of", "workshop of", "attributed to", "follower of", "after ", "school of", "master of", "copy ")
DELAY = 0.6


def api(params):
    params.update(action=params.get("action", "query"), format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(10 * (attempt + 1) if "429" in str(exc) else 2)


def lookup(name: str) -> dict:
    """{"qid", "gender"} for a painter name, or {} when Wikidata has no painter by that name."""
    d = api({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": "5"})
    hits = d.get("search", [])
    if not hits:
        return {}
    ids = "|".join(h["id"] for h in hits)
    time.sleep(DELAY)
    ents = api({"action": "wbgetentities", "ids": ids, "props": "claims"}).get("entities", {})
    for h in hits:  # first hit that is a painter wins
        claims = ents.get(h["id"], {}).get("claims", {})
        occ = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P106", [])}
        if not occ & PAINTER_LIKE:
            continue
        g = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P21", [])]
        gender = "f" if FEMALE in g else "m" if MALE in g else None
        return {"qid": h["id"], "gender": gender}
    return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)
    cache = {} if args.refresh or not CACHE.exists() else json.loads(CACHE.read_text(encoding="utf-8"))
    files = [p for p in (PAINTINGS, LOCAL) if p.exists()]
    sets = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in files]
    names = sorted({e.get("artist") or "" for _, es in sets for e in es})
    names = [n for n in names if n and not n.lower().startswith(SKIP)]
    todo = [n for n in names if n not in cache]
    print(f"{len(names)} painters, {len(todo)} to look up")
    for i, n in enumerate(todo):
        try:
            cache[n] = lookup(n)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {n}: {exc}", file=sys.stderr)
            continue
        time.sleep(DELAY)
        if (i + 1) % 50 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
            print(f"  {i + 1}/{len(todo)}")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    tagged = {"f": 0, "m": 0, None: 0}
    for path, entries in sets:
        for e in entries:
            if e.get("gender") == "f":
                tagged["f"] += 1
                continue
            g = (cache.get(e.get("artist") or "") or {}).get("gender")
            if g:
                e["gender"] = g
            else:
                e.pop("gender", None)
            tagged[g] += 1
        path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    print(f"tagged: {tagged['f']} by women, {tagged['m']} by men, {tagged[None]} unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
