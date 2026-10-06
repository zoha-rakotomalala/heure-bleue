"""The wall loop: what is playing, and which painting answers it.

Every poll:
  * read the active player through the platform backend
  * on a new track, extract the cover palette (URL or raw bytes) and queue a change
  * on a new track, look up the artist's genre tags (MusicBrainz, cached) for the music feel
  * when the dwell allows (or a swap was requested), pick the painting that answers the
    signals switched on in config.json "match": the cover's colours (CIELAB), the music
    feel, the moment (hour, sky, season); taste (favorites) and wear scale the result
  * write data/now_playing.json for the page, with the reasons for the choice ("why")
"""
from __future__ import annotations

import json
import math
import random
import re
import threading
import time
import urllib.request
from typing import Optional

from . import config, moment, music, nowplaying
from .color import color_name, hex_to_rgb, palette_distance, palette_feel, palette_from_bytes, rgb_to_lab

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


_FEEL: dict[str, dict] = {}  # painting id -> palette feel, computed once


def feel_of(p: dict) -> dict:
    f = _FEEL.get(p["id"])
    if f is None:
        f = _FEEL[p["id"]] = palette_feel(p.get("palette") or [])
    return f


def feel_distance(a: dict, b: dict, cent: Optional[str] = None) -> float:
    """0 (same feel) .. 1 (opposite). b may ask for a century too."""
    d = abs(a["light"] - b["light"]) + 0.8 * abs(a["chroma"] - b["chroma"]) + 0.35 * abs(a["warm"] - b["warm"])
    if b.get("century") and cent:
        d += 0.08 * min(3, abs(int(cent) - int(b["century"])))
    return min(1.0, d / 1.6)


MATCH_DEFAULT = {"cover": True, "music": True, "moment": True}
WEIGHTS = {"cover": 1.0, "music": 0.6, "moment": 0.5}  # the cover is the picture itself; the others are inferred


def explain(p: dict, cover_palette, music_feel, mom, taste, hour, signals) -> list[dict]:
    """The reasons behind a choice, as translation keys with their values, for the why line."""
    why = []
    if "cover" in signals and cover_palette and p.get("palette"):
        # the cover colour nearest to the painting's dominant one
        lab = rgb_to_lab(hex_to_rgb(p["palette"][0]["hex"]))
        near = min(cover_palette, key=lambda c: math.dist(lab, rgb_to_lab(hex_to_rgb(c["hex"]))))
        why.append({"k": "why_cover", "c": color_name(near["hex"]), "hex": near["hex"]})
    if "music" in signals and music_feel:
        why.append({"k": "why_music", "t": music_feel["top"]})
    if "moment" in signals and mom:
        why += [{"k": r} for r in mom["reasons"]]
    if hour and p.get("artist") == hour:
        why.append({"k": "why_hour", "a": hour})
    elif p.get("artist") in _TODAY:
        why.append({"k": "why_today", "a": p["artist"]})
    elif taste and taste.get("n", 0) >= 3 and taste.get("artists", {}).get(p.get("artist"), 0) >= 0.5:
        why.append({"k": "why_taste", "a": p["artist"]})
    return why[:4]


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


def choose_painting(cover_palette: Optional[list[dict]], recent: list[str], repeat_days: float = 3, use_taste: bool = True,
                    match: Optional[dict] = None, music_feel: Optional[dict] = None, use_moment: bool = True,
                    portrait: bool = True) -> tuple[Optional[dict], list[dict]]:
    """The painting for this moment, and why.

    Three signals, each with its own switch in config.json "match": the cover's colours
    (the strongest, when a song plays), the music's genre tags, and the moment (hour, sky,
    season). Each gives a 0..1 distance per painting; they are averaged by weight, then
    taste and wear scale the result. With no signal on or available (nothing playing and
    "moment" off), the choice is a weighted draw over the whole pool: taste and wear only.
    """
    index = load_index()
    block, shows = recently_shown(repeat_days)
    block.update(recent)
    paintings = [p for p in index if p["id"] not in block]
    if len(paintings) < 20:  # the pool is small or the memory long: fall back to the short memory only
        paintings = [p for p in index if p["id"] not in recent] or index
    if not paintings:
        return None, []
    taste, hour = (_load_json(config.TASTE, {}), artist_hour()) if use_taste else ({}, None)  # taste off: colour and wear only
    refresh_today()
    if portrait:
        upright = [p for p in paintings if p.get("h", 1) >= p.get("w", 1) * 0.9]
        if len(upright) >= 40:  # the screen is portrait; prefer upright when the pool allows
            paintings = upright
    match = {**MATCH_DEFAULT, **(match or {})}
    mom = moment.current() if (match.get("moment") and use_moment) else None
    signals = {}
    if match.get("cover") and cover_palette:
        signals["cover"] = lambda p: min(1.0, palette_distance(cover_palette, p["palette"]) / 110)
    if match.get("music") and music_feel:
        signals["music"] = lambda p: feel_distance(feel_of(p), music_feel["feel"], century(p.get("date")))
    if mom:
        signals["moment"] = lambda p: feel_distance(feel_of(p), mom["feel"])
    wsum = sum(WEIGHTS[s] for s in signals)

    def score(p):
        wear = 1 + 0.2 * shows.get(p["id"], 0)  # each showing this month costs 20% of closeness
        base = sum(WEIGHTS[s] * f(p) for s, f in signals.items()) / wsum if signals else 1.0
        return base * taste_bonus(p, taste, hour) * wear

    if signals:
        scored = sorted(((score(p), p) for p in paintings), key=lambda t: t[0])[:CANDIDATES]
        weights = [1 / (i + 1) for i in range(len(scored))]  # closest most likely, never certain
        chosen = random.choices([p for _, p in scored], weights=weights, k=1)[0]
    else:
        chosen = random.choices(paintings, weights=[1 / score(p) for p in paintings], k=1)[0]
    return chosen, explain(chosen, cover_palette, music_feel, mom, taste, hour, signals)


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
    if cfg.get("players") == "none":  # a wall without music: the page rotates on the moment alone
        backend, read, _next_track = "none", (lambda: None), (lambda: False)
    else:
        backend, read, _next_track = nowplaying.detect()
    print(f"player backend: {backend}", flush=True)
    prev = _load_json(config.NOW, {})
    last_track = (prev.get("track") or {}).get("id")
    last_change = prev.get("painting_changed_at", 0)
    recent = prev.get("recent", [])
    painting = prev.get("painting")
    painting_for = prev.get("painting_for")
    cover_palette = prev.get("cover_palette")
    music_feel = prev.get("music")
    why = prev.get("why") or []
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
                try:
                    music_feel = music.feel_for(track) if (cfg.get("match") or MATCH_DEFAULT).get("music", True) else None
                except Exception as exc:  # noqa: BLE001
                    music_feel = None
                    print("music tags failed:", exc, flush=True)
                pending = True
                last_track = track["id"]
            swap = config.SWAP.exists()
            if swap:
                config.SWAP.unlink(missing_ok=True)
            forced = pending and now < _force_change  # the new song came from our own skip button
            if forced:
                _force_change = 0.0
            if swap or forced or (pending and now - last_change >= dwell):  # no cover and no tags: the moment and taste still choose
                chosen, why = choose_painting(cover_palette, recent, cfg.get("repeat_days", 3), cfg.get("taste", True),
                                              cfg.get("match"), music_feel)
                if chosen:
                    painting, last_change = chosen, now
                    painting_for = f"{track.get('title')}|{track.get('artist')}|{track.get('album')}"
                    recent = (recent + [chosen["id"]])[-RECENT_MAX:]
                pending = False
            public = {k: v for k, v in track.items() if k != "cover_bytes"}
            public["cover"] = track.get("cover_url") or (f"/data/cover.jpg?v={int(last_change)}" if track.get("cover_bytes") else None)
            out = {"active": True, "backend": backend, "updated_at": now, "track": public, "cover_palette": cover_palette,
                   "music": music_feel, "why": why,
                   "painting": painting, "painting_for": painting_for, "painting_changed_at": last_change,
                   "pending": pending, "recent": recent}
        tmp = config.NOW.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        tmp.replace(config.NOW)
        # poll fast while a skip is waiting for the player to switch; otherwise the normal cadence
        wait = 0.7 if now < _force_change else cfg["poll_seconds"]
        _WAKE.wait(wait)
        _WAKE.clear()
