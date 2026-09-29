"""macOS: Spotify and Apple Music (the Music app) via AppleScript.

Spotify gives an artwork URL. Music gives raw artwork bytes, which we pull as a
hex blob through osascript. Both are polled only when the app is running, so we
never launch a player by accident.
"""
from __future__ import annotations

import re
import subprocess
from typing import Optional

from . import Track

RUNNING = 'tell application "System Events" to (name of processes)'

SPOTIFY = '''
tell application "Spotify"
  set pstate to (player state as string)
  if pstate is "stopped" then return "stopped"
  set trk to current track
  return pstate & "\\t" & (id of trk) & "\\t" & (name of trk) & "\\t" & (artist of trk) & "\\t" & (album of trk) & "\\t" & (artwork url of trk) & "\\t" & (duration of trk) & "\\t" & (player position)
end tell
'''

MUSIC = '''
tell application "Music"
  set pstate to (player state as string)
  if pstate is "stopped" then return "stopped"
  set trk to current track
  return pstate & "\\t" & (persistent ID of trk) & "\\t" & (name of trk) & "\\t" & (artist of trk) & "\\t" & (album of trk) & "\\t" & "" & "\\t" & ((duration of trk) * 1000) & "\\t" & (player position)
end tell
'''

MUSIC_ART = '''
tell application "Music"
  try
    return (raw data of artwork 1 of current track)
  on error
    return ""
  end try
end tell
'''


def _osa(script: str, timeout: int = 10) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


def _running() -> set[str]:
    return {p.strip() for p in _osa(RUNNING).split(",")}


def _num(s: str) -> float:
    return float(s.strip().replace(",", "."))  # French locale prints 2,275


def _parse(line: str, player: str) -> Optional[Track]:
    if not line or line == "stopped":
        return None
    parts = line.split("\t")
    if len(parts) < 8:
        return None
    state, tid, name, artist, album, art, dur, pos = parts[:8]
    return {
        "player": player, "state": state, "id": f"{player}:{tid}", "title": name, "artist": artist,
        "album": album, "cover_url": art or None, "cover_bytes": None,
        "duration_ms": int(_num(dur)), "position_s": _num(pos),
    }


def _music_artwork() -> Optional[bytes]:
    out = _osa(MUSIC_ART, timeout=20)
    m = re.search(r"«data \w{4}([0-9A-Fa-f]+)»", out)
    if not m:
        return None
    try:
        return bytes.fromhex(m.group(1))
    except ValueError:
        return None


_last_music_id = None
_last_music_art: Optional[bytes] = None


def read() -> Optional[Track]:
    global _last_music_id, _last_music_art
    procs = _running()
    if "Spotify" in procs:
        t = _parse(_osa(SPOTIFY), "Spotify")
        if t and t["state"] in ("playing", "paused"):
            return t
    if "Music" in procs:
        t = _parse(_osa(MUSIC), "Music")
        if t and t["state"] in ("playing", "paused"):
            if t["id"] != _last_music_id:  # artwork is heavy; fetch once per track
                _last_music_art = _music_artwork()
                _last_music_id = t["id"]
            t["cover_bytes"] = _last_music_art
            return t
    return None
