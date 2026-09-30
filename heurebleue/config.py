"""Paths and settings for heure bleue.

Everything lives under one root (the repo checkout, or HEURE_BLEUE_HOME if set):
  web/    the two pages
  data/   paintings.json (shipped), plus files written at runtime
  config.json  optional user settings, merged over DEFAULTS
"""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path

ROOT = Path(os.environ.get("HEURE_BLEUE_HOME") or Path(__file__).resolve().parent.parent)
WEB = ROOT / "web"
DATA = ROOT / "data"
CONFIG_FILE = ROOT / "config.json"

DEFAULTS = {
    "port": 8765,
    "host": "127.0.0.1",
    "poll_seconds": 5,
    "min_dwell_seconds": 45,
    "rotate_minutes": 4,
    "paused_rotate_minutes": 20,
    "theme": "forest",
    "city": {"name": "Paris", "lat": 48.8566, "lon": 2.3522, "timezone": "Europe/Paris"},
    "locale": "fr-FR",
    "players": "auto",
}


def load() -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    if CONFIG_FILE.exists():
        try:
            user = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"config.json is not valid JSON: {exc}")
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def system() -> str:
    """'macos' | 'windows' | 'linux' | 'other'"""
    s = platform.system()
    return {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(s, "other")


# runtime files (all under data/, all git-ignored except paintings.json)
PAINTINGS = DATA / "paintings.json"
NOW = DATA / "now_playing.json"
FAVORITES = DATA / "favorites.json"
HISTORY = DATA / "history.jsonl"
TASTE = DATA / "taste.json"
SWAP = DATA / "swap_request.json"
ARTIST_HOUR = DATA / "artist_hour.json"
COVER = DATA / "cover.jpg"
