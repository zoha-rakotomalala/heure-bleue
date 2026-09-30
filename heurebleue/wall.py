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

RECENT_MAX = 40
UA = {"User-Agent": "heure-bleue/1.0 (personal desk display)"}


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_index() -> list[dict]:
    return _load_json(config.PAINTINGS, [])


def century(date: Optional[str]) -> Optional[str]:
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})", date or "")
    return str(int(m.group(1)) // 100 + 1) if m else None


def taste_bonus(p: dict, taste: dict, hour_artist: Optional[str]) -> float:
    """Multiplier on the color distance, 0.35..1.0. Lower = preferred.
    Gentle until ~20 favorites, then the weights have real shape."""
    if not taste or not taste.get("n"):
        return 1.0
    strength = min(1.0, taste["n"] / 20)
    score = 0.5 * taste.get("artists", {}).get(p.get("artist"), 0)
    score += 0.25 * taste.get("museums", {}).get(p.get("museum"), 0)
    score += 0.25 * taste.get("centuries", {}).get(century(p.get("date")), 0)
    if hour_artist and p.get("artist") == hour_artist:
        score += 0.8
    return max(0.35, 1.0 - 0.5 * strength * min(score, 1.3))


def artist_hour() -> Optional[str]:
    a = _load_json(config.ARTIST_HOUR, {})
    return a.get("artist") if a.get("until", 0) > time.time() else None


def choose_painting(cover_palette: list[dict], recent: list[str]) -> Optional[dict]:
    paintings = [p for p in load_index() if p["id"] not in recent]
    if not paintings:
        return None
    taste, hour = _load_json(config.TASTE, {}), artist_hour()
    upright = [p for p in paintings if p.get("h", 1) >= p.get("w", 1) * 0.9]
    if len(upright) >= 40:  # the screen is portrait; prefer upright when the pool allows
        paintings = upright
    scored = sorted(((palette_distance(cover_palette, p["palette"]) * taste_bonus(p, taste, hour), p) for p in paintings), key=lambda t: t[0])
    return random.choice([p for _, p in scored[:5]])


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


def run(stop: threading.Event, cfg: dict) -> None:
    config.DATA.mkdir(parents=True, exist_ok=True)
    backend, read = nowplaying.detect()
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
            if cover_palette and (swap or (pending and now - last_change >= dwell)):
                chosen = choose_painting(cover_palette, recent)
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
        stop.wait(cfg["poll_seconds"])
