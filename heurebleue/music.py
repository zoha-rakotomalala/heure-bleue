"""What the music feels like, from its genre tags.

The players on the Mac, Windows and Linux tell us title, artist and album, nothing
about the sound. Spotify closed its audio-features endpoint to new apps in 2024 and
Apple Music never had one for what plays on the desktop, so the one signal we can
get without a key or a login is the artist's genre tags from MusicBrainz (CC0).
"jazz", "doom metal", "bossa nova" each carry a feel: how light, how vivid, how
warm a painting should be, and roughly which century. That feel is compared with
each painting's palette in wall.choose_painting.

    feel_for(track) -> {"tags": ["jazz", "soul"], "feel": {...}, "top": "jazz"} | None

Answers are cached in data/music_tags.json (per artist, 90 days; a miss 14 days),
so each artist costs MusicBrainz one request in its life. MusicBrainz asks for one
request per second and a User-Agent with a contact; both are respected.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Optional

from . import config

UA = {"User-Agent": "heure-bleue/1.0 (https://github.com/zoha-rakotomalala/heure-bleue; personal desk display)"}
CACHE = config.DATA / "music_tags.json"
HIT_DAYS, MISS_DAYS = 90, 14
_LOCK = threading.Lock()
_LAST_CALL = 0.0

# tag keyword -> (light, chroma, warm, century). Each is a nudge from the neutral
# painting (light .55, chroma .45, warm 0); None leaves the century free.
# Keywords match as substrings of the lower-cased tag ("doom metal" hits "doom" and "metal").
FEEL = {
    # dark and slow
    "ambient": (-0.20, -0.20, -0.20, None), "drone": (-0.30, -0.25, -0.10, None), "doom": (-0.35, -0.15, 0.00, None),
    "black metal": (-0.40, -0.20, -0.20, None), "gothic": (-0.30, -0.10, -0.10, 19), "darkwave": (-0.30, -0.10, -0.25, None),
    "post-rock": (-0.15, -0.15, -0.10, None), "shoegaze": (-0.10, -0.15, -0.20, None), "slowcore": (-0.20, -0.25, -0.10, None),
    "sadcore": (-0.20, -0.25, 0.00, None), "melanchol": (-0.20, -0.20, -0.10, None), "trip hop": (-0.20, -0.10, 0.00, None),
    "downtempo": (-0.15, -0.15, 0.00, None), "industrial": (-0.30, -0.20, -0.20, None), "dark": (-0.25, -0.15, -0.10, None),
    "noise": (-0.20, -0.10, -0.20, None), "post-punk": (-0.20, -0.15, -0.20, 20), "grunge": (-0.20, -0.15, 0.00, 20),
    # warm and human
    "jazz": (-0.05, -0.05, 0.30, 20), "blues": (-0.10, -0.05, 0.30, 20), "soul": (0.00, 0.05, 0.35, 20),
    "r&b": (0.00, 0.05, 0.25, 20), "funk": (0.05, 0.20, 0.30, 20), "gospel": (0.05, 0.00, 0.30, 20),
    "folk": (0.00, -0.10, 0.25, 19), "country": (0.05, -0.05, 0.30, 19), "americana": (0.00, -0.05, 0.30, 19),
    "singer-songwriter": (0.00, -0.10, 0.15, None), "acoustic": (0.05, -0.10, 0.20, None), "chanson": (0.00, -0.05, 0.15, 20),
    "flamenco": (-0.05, 0.10, 0.40, 19), "tango": (-0.10, 0.05, 0.30, 20), "fado": (-0.15, -0.10, 0.20, 19),
    # bright and vivid
    "pop": (0.15, 0.20, 0.10, 20), "dance": (0.10, 0.30, 0.10, 21), "disco": (0.10, 0.30, 0.25, 20),
    "house": (0.10, 0.25, 0.05, 21), "electro": (0.05, 0.20, -0.10, 21), "synth": (0.00, 0.20, -0.15, 20),
    "techno": (-0.05, 0.15, -0.20, 21), "edm": (0.10, 0.30, 0.00, 21), "latin": (0.10, 0.30, 0.35, None),
    "salsa": (0.10, 0.30, 0.40, 20), "reggae": (0.10, 0.25, 0.30, 20), "ska": (0.10, 0.25, 0.20, 20),
    "afro": (0.10, 0.30, 0.35, None), "bossa": (0.10, 0.05, 0.30, 20), "samba": (0.10, 0.25, 0.35, 20),
    "k-pop": (0.15, 0.30, 0.10, 21), "j-pop": (0.15, 0.30, 0.10, 21), "tropical": (0.15, 0.30, 0.30, 21),
    "indie pop": (0.10, 0.10, 0.10, 21), "dream pop": (0.05, 0.00, -0.10, 21),
    # loud
    "metal": (-0.25, 0.00, -0.05, None), "punk": (-0.05, 0.15, 0.00, 20), "hardcore": (-0.15, 0.10, 0.00, 21),
    "rock": (-0.05, 0.05, 0.05, 20), "hip hop": (-0.05, 0.10, 0.05, 21), "hip-hop": (-0.05, 0.10, 0.05, 21),
    "rap": (-0.05, 0.10, 0.05, 21), "trap": (-0.15, 0.10, -0.05, 21), "drum and bass": (-0.10, 0.20, -0.15, 21),
    "grime": (-0.15, 0.10, -0.10, 21),
    # old
    "classical": (0.00, -0.15, 0.10, 18), "baroque": (-0.05, -0.10, 0.20, 17), "opera": (-0.05, 0.00, 0.15, 19),
    "romantic": (0.00, -0.05, 0.15, 19), "chamber": (0.00, -0.15, 0.10, 18), "piano": (0.05, -0.15, 0.05, 19),
    "orchestral": (0.00, -0.10, 0.10, 19), "choral": (0.05, -0.15, 0.05, 17), "medieval": (-0.10, -0.10, 0.10, 15),
    "renaissance": (0.00, -0.05, 0.15, 16), "early music": (-0.05, -0.10, 0.15, 16), "symphon": (0.00, -0.10, 0.10, 19),
    "soundtrack": (-0.05, -0.05, 0.00, None), "new age": (0.10, -0.15, 0.00, None), "lo-fi": (0.00, -0.15, 0.10, None),
    "indie": (0.00, -0.05, 0.05, 21), "alternative": (-0.05, -0.05, 0.00, 20), "experimental": (-0.10, -0.05, -0.10, 21),
}
SKIP_TAGS = {"seen live", "favorites", "favourites", "american", "british", "french", "german", "english", "usa", "uk",
             "male vocalists", "female vocalists", "singer", "band", "duo", "producer", "dj", "composer"}


def _load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(cache: dict) -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE)
    except OSError:
        pass


def first_artist(name: str) -> str:
    """'A, B & C' or 'A feat. B' -> 'A'."""
    name = re.split(r"\s+(?:feat\.?|ft\.?|featuring|x|with|&|and|vs\.?)\s+|,|;|/", name or "", 1, flags=re.I)[0]
    return name.strip()


def fetch_tags(artist: str, timeout: float = 8) -> Optional[list[dict]]:
    """Ask MusicBrainz for the artist's tags; None when it did not answer, [] when it knows no tags."""
    global _LAST_CALL
    with _LOCK:
        wait = 1.1 - (time.time() - _LAST_CALL)
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL = time.time()
    q = urllib.parse.quote(f'artist:"{artist}"')
    url = f"https://musicbrainz.org/ws/2/artist/?query={q}&fmt=json&limit=3"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001  offline or throttled: try again another day
        return None
    hits = [a for a in data.get("artists", []) if int(a.get("score", 0)) >= 85]
    if not hits:
        return []
    best = max(hits, key=lambda a: (int(a.get("score", 0)), len(a.get("tags") or [])))
    tags = sorted(({"name": t["name"].lower(), "count": int(t.get("count", 1))} for t in best.get("tags") or []
                   if t.get("name") and t["name"].lower() not in SKIP_TAGS), key=lambda t: -t["count"])
    return tags[:12]


def feel_from_tags(tags: list[dict]) -> Optional[dict]:
    """Combine the known tags, weighted by their votes, into one feel. None if none is known."""
    light = chroma = warm = 0.0
    cents, total, matched = [], 0.0, []
    for t in tags:
        w = max(1, t.get("count", 1))
        for kw, (dl, dc, dw, cen) in FEEL.items():
            if kw in t["name"]:
                light += w * dl; chroma += w * dc; warm += w * dw; total += w
                if cen:
                    cents.append((cen, w))
                matched.append((w, t["name"]))
                break
    if not total:
        return None
    feel = {"light": round(min(1, max(0, 0.55 + light / total)), 3), "chroma": round(min(1, max(0, 0.45 + chroma / total)), 3),
            "warm": round(max(-1, min(1, warm / total)), 3)}
    if cents:
        feel["century"] = round(sum(c * w for c, w in cents) / sum(w for _, w in cents))
    return {"feel": feel, "top": max(matched)[1], "tags": [n for _, n in sorted(matched, reverse=True)][:4]}


BROWSERS = {"chrome", "google chrome", "firefox", "safari", "arc", "brave", "edge", "microsoft edge", "opera", "vivaldi"}


def feel_for(track: dict) -> Optional[dict]:
    """The music feel for this track's artist, from the cache or MusicBrainz."""
    artist = first_artist(track.get("artist") or "")
    if not artist or artist.lower() in ("various artists", "unknown artist", "unknown"):
        return None
    # a browser tab with no album is a video or a stream, and its "artist" is a channel name:
    # a streamer called Domingo must not turn the wall to opera
    if not track.get("album") and (track.get("player") or "").lower() in BROWSERS:
        return None
    cache = _load()
    key = artist.lower()
    row = cache.get(key)
    now = time.time()
    if row and now - row.get("ts", 0) < (HIT_DAYS if row.get("tags") else MISS_DAYS) * 86400:
        tags = row.get("tags") or []
    else:
        tags = fetch_tags(artist)
        if tags is None:  # no answer: keep whatever we had, do not cache the failure for long
            tags = (row or {}).get("tags") or []
            if not row:
                cache[key] = {"ts": now - (MISS_DAYS - 1) * 86400, "tags": []}
                _save(cache)
        else:
            cache[key] = {"ts": now, "tags": tags}
            _save(cache)
    return feel_from_tags(tags) if tags else None
