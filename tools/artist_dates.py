"""Painters' birth and death dates from Wikidata -> data/artists.json

    python3 tools/artist_dates.py            # all artists in the index, skipping those already known
    python3 tools/artist_dates.py --refresh  # ask again for everyone

Uses the MediaWiki API (no key): wbsearchentities to find the painter, then
wbgetentities for P569 (born) and P570 (died). Only humans whose occupation
(P106) includes a visual-arts profession are accepted, so 'Raphael' finds the
painter and not the archangel. Names like 'Raphael (Raffaello Sanzio or Santi)'
are searched by the part before the parenthesis.

Output: { "Claude Monet": {"born": "1840-11-14", "died": "1926-12-05", "qid": "Q296"}, ... }
Unknown or anonymous painters are skipped. ~1 request per second; 600 artists ≈ 20 min.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "paintings.json"
OUT = ROOT / "data" / "artists.json"
API = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "heure-bleue/1.0 (https://github.com/zoha-rakotomalala/heure-bleue; personal desk display)"}
ARTIST_OCCUPATIONS = {  # P106 values that make a hit a painter and not a namesake
    "Q1028181", "Q3391743", "Q1281618", "Q644687", "Q15296811", "Q483501", "Q10732476", "Q1925963",
}  # painter, visual artist, sculptor, illustrator, drawer, artist, graphic artist, miniaturist
SKIP = re.compile(r"unknown|anonymous|painter \(|workshop|circle of|follower|attributed|school|master of|^\w+ painter$", re.I)


def get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as exc:  # noqa: BLE001  429s and hiccups: back off and retry
            time.sleep(5 * (attempt + 1))
            last = exc
    raise last


def date_of(claims: dict, prop: str) -> str | None:
    for c in claims.get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        t, prec = v.get("time", ""), v.get("precision", 0)
        m = re.match(r"\+(\d{4})-(\d{2})-(\d{2})", t)
        if m and prec >= 11:  # day precision; a year-only date is useless for "today"
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _try(q: str) -> dict | None:
    hits = get({"action": "wbsearchentities", "search": q, "language": "en", "type": "item", "limit": 10}).get("search", [])
    if not hits:
        return None
    ids = "|".join(h["id"] for h in hits)
    ents = get({"action": "wbgetentities", "ids": ids, "props": "claims", "languages": "en"}).get("entities", {})
    for h in hits:  # first hit that is a human with an artist occupation
        claims = ents.get(h["id"], {}).get("claims", {})
        occ = {c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P106", [])}
        human = any(c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5" for c in claims.get("P31", []))
        if human and occ & ARTIST_OCCUPATIONS:
            born, died = date_of(claims, "P569"), date_of(claims, "P570")
            return {"born": born, "died": died, "qid": h["id"]} if (born or died) else None
    return None


def lookup(name: str) -> dict | None:
    q = re.sub(r"\s*\(.*\)\s*$", "", name).strip()  # 'Raphael (Raffaello Sanzio or Santi)' -> 'Raphael'
    q = re.sub(r"^(Sir|Lord)\s+", "", q)
    r = _try(q)
    if r is None:  # a bare first name ('Raphael', 'Titian') is crowded out by namesakes; say what we mean
        time.sleep(0.5)
        r = _try(q + " painter")
    return r


def main() -> int:
    refresh = "--refresh" in sys.argv
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    known = {} if refresh or not OUT.exists() else json.loads(OUT.read_text(encoding="utf-8"))
    artists = sorted({p["artist"] for p in index if p.get("artist") and not SKIP.search(p["artist"])})
    todo = [a for a in artists if a not in known]
    print(f"{len(artists)} painters, {len(todo)} to look up")
    found = 0
    for i, a in enumerate(todo, 1):
        try:
            r = lookup(a)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {a}: {exc}", file=sys.stderr)
            r = None
        known[a] = r or {}
        found += bool(r)
        if i % 25 == 0 or i == len(todo):
            OUT.write_text(json.dumps(dict(sorted(known.items())), ensure_ascii=False, indent=0), encoding="utf-8")
            print(f"  {i}/{len(todo)} · {found} with dates")
        time.sleep(1.0)
    dated = sum(1 for v in known.values() if v)
    print(f"done: {dated}/{len(known)} painters with a birth or death day -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
