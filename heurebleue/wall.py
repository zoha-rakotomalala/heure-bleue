"""The wall loop: what is playing, and which painting answers it.

Every poll:
  * read the active player through the platform backend
  * on a new track, extract the cover palette (URL or raw bytes) and queue a change
  * when the dwell allows (or a swap was requested), pick the painting whose palette
    is closest in CIELAB, weighted by taste (favorites) and the artist hour
  * write data/now_playing.json for the page
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
import urllib.request
from typing import Optional

from . import config, nowplaying
from .color import palette_distance, palette_from_bytes

RECENT_MAX = 40          # in-memory floor; the real memory is the viewing history (see recently_shown)
CANDIDATES = 12          # pick among the closest N, weighted toward the closest
UA = {"User-Agent": "heure-bleue/1.0 (https://github.com/zoha-rakotomalala/heure-bleue; personal desk display)"}


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_index() -> list[dict]:
    return _load_json(config.PAINTINGS, []) + _load_json(config.PAINTINGS_LOCAL, [])


def century(date: Optional[str]) -> Optional[str]:
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})", date or "")
    return str(int(m.group(1)) // 100 + 1) if m else None


_TODAY: set = set()
_TODAY_DAY = ""


def refresh_today() -> set:
    global _TODAY, _TODAY_DAY
    day = time.strftime("%m-%d")
    if day != _TODAY_DAY:
        _TODAY, _TODAY_DAY = {e["artist"] for e in painters_of_the_day()}, day
    return _TODAY


def taste_bonus(p: dict, taste: dict, hour_artist: Optional[str]) -> float:
    """Multiplier on the color distance, 0.35..1.0. Lower = preferred.
    Gentle until ~20 favorites, then the weights have real shape."""
    if not taste or not taste.get("n"):
        return 0.8 if p.get("artist") in _TODAY else 1.0
    strength = min(1.0, taste["n"] / 20)
    score = 0.5 * taste.get("artists", {}).get(p.get("artist"), 0)
    score += 0.25 * taste.get("museums", {}).get(p.get("museum"), 0)
    score += 0.25 * taste.get("centuries", {}).get(century(p.get("date")), 0)
    if hour_artist and p.get("artist") == hour_artist:
        score += 0.8
    if p.get("artist") in _TODAY:
        score += 0.4  # the painter's birthday or death day: a small nudge, not a takeover
    return max(0.35, 1.0 - 0.5 * strength * min(score, 1.3))


def painters_of_the_day(when: Optional[time.struct_time] = None) -> list[dict]:
    """Painters in the index born or died on today's month and day, from data/artists.json."""
    when = when or time.localtime()
    md = f"{when.tm_mon:02d}-{when.tm_mday:02d}"
    out = []
    for name, d in _load_json(config.ARTISTS, {}).items():
        if not d:
            continue
        for kind in ("born", "died"):
            v = d.get(kind)
            if v and v[5:] == md:
                out.append({"artist": name, "event": kind, "year": int(v[:4]), "age": time.localtime().tm_year - int(v[:4])})
    return sorted(out, key=lambda e: e["year"])


def artist_hour() -> Optional[str]:
    a = _load_json(config.ARTIST_HOUR, {})
    return a.get("artist") if a.get("until", 0) > time.time() else None


def recently_shown(days: float, wear_days: float = 30) -> tuple[set[str], dict[str, int]]:
    """From history.jsonl: the ids shown in the last `days` (excluded outright),
    and how many times each id was shown in the last `wear_days` (a soft penalty,
    so the whole pool gets its turn instead of the same close matches)."""
    cutoff, wear_cutoff = time.time() - days * 86400, time.time() - wear_days * 86400
    block, shows = set(), {}
    try:
        for line in config.HISTORY.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts, pid = row.get("ts", 0), row.get("id")
            if not pid or ts < wear_cutoff:
                continue
            shows[pid] = shows.get(pid, 0) + 1
            if ts >= cutoff:
                block.add(pid)
    except FileNotFoundError:
        pass
    return block, shows


def choose_painting(cover_palette: list[dict], recent: list[str], repeat_days: float = 3, use_taste: bool = True) -> Optional[dict]:
    index = load_index()
    block, shows = recently_shown(repeat_days)
    block.update(recent)
    paintings = [p for p in index if p["id"] not in block]
    if len(paintings) < 20:  # the pool is small or the memory long: fall back to the short memory only
        paintings = [p for p in index if p["id"] not in recent] or index
    if not paintings:
        return None
    taste, hour = (_load_json(config.TASTE, {}), artist_hour()) if use_taste else ({}, None)  # taste off: colour and wear only
    refresh_today()
    upright = [p for p in paintings if p.get("h", 1) >= p.get("w", 1) * 0.9]
    if len(upright) >= 40:  # the screen is portrait; prefer upright when the pool allows
        paintings = upright

    def score(p):
        wear = 1 + 0.2 * shows.get(p["id"], 0)  # each showing this month costs 20% of closeness
        return palette_distance(cover_palette, p["palette"]) * taste_bonus(p, taste, hour) * wear

    scored = sorted(((score(p), p) for p in paintings), key=lambda t: t[0])[:CANDIDATES]
    weights = [1 / (i + 1) for i in range(len(scored))]  # closest most likely, never certain
    return random.choices([p for _, p in scored], weights=weights, k=1)[0]


def cover_palette_for(track: dict) -> Optional[list[dict]]:
    data = track.get("cover_bytes")
    if not data and track.get("cover_url"):
        with urllib.request.urlopen(urllib.request.Request(track["cover_url"], headers=UA), timeout=20) as r:
            data = r.read()
    if not data:
        return None
    if not track.get("cover_url"):  # serve raw covers to the page from data/cover.jpg
        config.COVER.write_bytes(data)
    return palette_from_bytes(data)


# set by run(); used by the server's POST /api/next
_WAKE = threading.Event()
_next_track = lambda: False  # noqa: E731
_force_change = 0.0  # deadline: change the painting as soon as the player reports a new track


def request_next() -> bool:
    """Skip the player to the next song and make the wall follow at once."""
    global _force_change
    ok = _next_track()
    if ok:
        _force_change = time.time() + 8  # give the player a few seconds to report the new track
        _WAKE.set()
    return ok


def run(stop: threading.Event, cfg: dict) -> None:
    global _next_track, _force_change
    config.DATA.mkdir(parents=True, exist_ok=True)
    backend, read, _next_track = nowplaying.detect()
    print(f"player backend: {backend}", flush=True)
    prev = _load_json(config.NOW, {})
    last_track = (prev.get("track") or {}).get("id")
    last_change = prev.get("painting_changed_at", 0)
    recent = prev.get("recent", [])
    painting = prev.get("painting")
    painting_for = prev.get("painting_for")
    cover_palette = prev.get("cover_palette")
    pending = False
    dwell = cfg["min_dwell_seconds"]

    while not stop.is_set():
        try:
            track = read()
        except Exception as exc:  # noqa: BLE001
            track = None
            print("player read failed:", exc, flush=True)
        now = time.time()
        if track is None:
            out = {"active": False, "backend": backend, "updated_at": now, "painting": None, "recent": recent}
        else:
            if track["id"] != last_track:
                try:
                    cover_palette = cover_palette_for(track) or cover_palette
                except Exception as exc:  # noqa: BLE001
                    print("cover fetch failed:", exc, flush=True)
                pending = True
                last_track = track["id"]
            swap = config.SWAP.exists()
            if swap:
                config.SWAP.unlink(missing_ok=True)
            forced = pending and now < _force_change  # the new song came from our own skip button
            if forced:
                _force_change = 0.0
            if cover_palette and (swap or forced or (pending and now - last_change >= dwell)):
                chosen = choose_painting(cover_palette, recent, cfg.get("repeat_days", 3), cfg.get("taste", True))
                if chosen:
                    painting, last_change = chosen, now
                    painting_for = f"{track.get('title')}|{track.get('artist')}|{track.get('album')}"
                    recent = (recent + [chosen["id"]])[-RECENT_MAX:]
                pending = False
            public = {k: v for k, v in track.items() if k != "cover_bytes"}
            public["cover"] = track.get("cover_url") or (f"/data/cover.jpg?v={int(last_change)}" if track.get("cover_bytes") else None)
            out = {"active": True, "backend": backend, "updated_at": now, "track": public, "cover_palette": cover_palette,
                   "painting": painting, "painting_for": painting_for, "painting_changed_at": last_change,
                   "pending": pending, "recent": recent}
        tmp = config.NOW.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        tmp.replace(config.NOW)
        # poll fast while a skip is waiting for the player to switch; otherwise the normal cadence
        wait = 0.7 if now < _force_change else cfg["poll_seconds"]
        _WAKE.wait(wait)
        _WAKE.clear()
