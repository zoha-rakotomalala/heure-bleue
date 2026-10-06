"""Paths and settings for heure bleue.

From a checkout, everything lives under one root (the repo, or HEURE_BLEUE_HOME):
  web/    the three pages and i18n.js
  data/   paintings.json (shipped), plus files written at runtime
  config.json  optional user settings, merged over DEFAULTS

From the packaged app (PyInstaller sets sys.frozen), the shipped files are
read-only inside the bundle, so the files the wall writes go to the user's
application folder instead:
  macOS    ~/Library/Application Support/heure bleue
  Windows  %APPDATA%\\heure bleue
  Linux    $XDG_DATA_HOME/heure-bleue  (default ~/.local/share/heure-bleue)
HEURE_BLEUE_HOME still wins when set, in both modes.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))


def system() -> str:
    """'macos' | 'windows' | 'linux' | 'other'"""
    s = platform.system()
    return {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(s, "other")


def user_dir() -> Path:
    s = system()
    if s == "macos":
        return Path.home() / "Library" / "Application Support" / "heure bleue"
    if s == "windows":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "heure bleue"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "heure-bleue"


_HOME = os.environ.get("HEURE_BLEUE_HOME")
BUNDLE = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parent.parent
ROOT = Path(_HOME) if _HOME else (user_dir() if FROZEN else BUNDLE)
WEB = BUNDLE / "web"
DATA = ROOT / "data"
CONFIG_FILE = ROOT / "config.json"

if FROZEN and "SSL_CERT_FILE" not in os.environ:
    # The bundled OpenSSL remembers the certificate folder of the machine that BUILT the app
    # (python.org's Python: /Library/Frameworks/Python.framework/.../etc/openssl), which does
    # not exist on the user's machine, so every https fetch fails. certifi ships its own file.
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass

DEFAULTS = {
    "port": 8765,
    "host": "127.0.0.1",
    "poll_seconds": 5,
    "min_dwell_seconds": 45,
    "rotate_minutes": 4,
    "paused_rotate_minutes": 20,
    "repeat_days": 3,
    "theme": "forest",
    "city": {"name": "Paris", "lat": 48.8566, "lon": 2.3522, "timezone": "Europe/Paris"},
    "locale": "",        # date format (fr-FR, en-GB, ...); empty = the system language
    "language": "",       # ui language (en, fr, nl, de, es, it, pt, fi, sv, da, pl, ru, ja); empty = follow locale
    "units": "celsius",   # or fahrenheit
    "players": "auto",     # "none": a wall without music; the hour, the sky and the season choose
    "match": {"cover": True, "music": True, "moment": True},  # the three signals behind a choice; each has a switch in the ⚙ panel
    "taste": True,         # let kept paintings tilt the choice toward their artists, museums and centuries; False = pure colour match, more discovery
    "update_check": True,  # ask GitHub once a day whether a newer release exists; the wall shows a small link
    "update_mode": "click",  # click: the line installs when clicked. auto: download now, install at quit (packaged app)
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



def save_keys(**keys) -> dict:
    """Merge a few settings into the user's config.json (the ⚙ panel writes update_mode this way).
    Only the keys given are touched; the rest of the file, comments aside, stays as the user wrote it."""
    current = {}
    if CONFIG_FILE.exists():
        try:
            current = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = {}
    current.update(keys)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return current

# runtime files (all under data/, all git-ignored except paintings.json)
# The shipped index is read from the bundle; the app never writes it.
PAINTINGS = (BUNDLE if FROZEN else ROOT) / "data" / "paintings.json"
ARTISTS = (BUNDLE if FROZEN else ROOT) / "data" / "artists.json"  # painters' birth and death days (tools/artist_dates.py), shipped
PAINTINGS_LOCAL = DATA / "paintings.local.json"  # CC BY-licensed extras for this machine; git-ignored, never in the demo
NOW = DATA / "now_playing.json"
FAVORITES = DATA / "favorites.json"
HISTORY = DATA / "history.jsonl"
TASTE = DATA / "taste.json"
SWAP = DATA / "swap_request.json"
ARTIST_HOUR = DATA / "artist_hour.json"
COVER = DATA / "cover.jpg"
