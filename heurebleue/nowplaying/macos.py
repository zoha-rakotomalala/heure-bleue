"""macOS: Spotify and Apple Music (the Music app) via AppleScript, then any other
player through the system Now Playing feed.

Spotify gives an artwork URL. Music gives raw artwork bytes, which we pull as a
hex blob through osascript. Both are polled only when the app is running, so we
never launch a player by accident.

Everything else (YouTube Music, Deezer, Tidal, a browser tab) is read with
`media-control` (github.com/ungive/media-control, BSD-3), which opens the
MediaRemote feed Apple closed to third parties in macOS 15.4. The packaged app
ships its own copy under vendor/media-control and runs it with the system Perl;
a source checkout uses the Homebrew install when there is one. It is a community
tool, not an Apple door; when it is missing or stops working the wall simply
falls back to Spotify and Music.
"""
from __future__ import annotations

import base64
import calendar
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .. import config
from . import Track


def _find_media_control() -> Optional[list]:
    """The command prefix for media-control, or None. Bundled copy first, then Homebrew."""
    bundled = config.BUNDLE / "vendor" / "media-control" / "bin" / "media-control"
    if bundled.exists() and Path("/usr/bin/perl").exists():
        return ["/usr/bin/perl", str(bundled)]  # the bundle is not on PATH and may carry a quarantine flag; perl does not care
    found = shutil.which("media-control") or next(
        (p for p in ("/opt/homebrew/bin/media-control", "/usr/local/bin/media-control") if Path(p).exists()), None)
    # an app opened from Finder has a bare PATH, so the Homebrew locations are tried by hand
    return [found] if found else None


MEDIA_CONTROL = _find_media_control()

APP_NAMES = {
    "com.spotify.client": "Spotify", "com.apple.Music": "Music", "com.google.Chrome": "Chrome",
    "com.apple.Safari": "Safari", "org.mozilla.firefox": "Firefox", "com.brave.Browser": "Brave",
    "com.microsoft.edgemac": "Edge", "company.thebrowser.Browser": "Arc", "com.github.th-ch.youtube-music": "YouTube Music",
    "com.tidal.desktop": "TIDAL", "com.deezer.deezer-desktop": "Deezer", "org.videolan.vlc": "VLC",
}

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
        "album": album, "cover_url": art if art and art != "missing value" else None, "cover_bytes": None,
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


def _system_now_playing() -> Optional[Track]:
    """Whatever macOS itself shows in the Now Playing widget, via media-control."""
    if not MEDIA_CONTROL:
        return None
    try:
        r = subprocess.run([*MEDIA_CONTROL, "get"], capture_output=True, text=True, timeout=10)
        d = json.loads(r.stdout or "null")
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return None
    if not d or not d.get("title"):
        return None
    bundle = d.get("bundleIdentifier") or ""
    player = APP_NAMES.get(bundle) or bundle.rsplit(".", 1)[-1] or "player"
    playing = bool(d.get("playing"))
    pos = float(d.get("elapsedTime") or 0)
    if playing and d.get("timestamp"):  # elapsedTime is the position at `timestamp`; advance it to now
        try:
            ts = calendar.timegm(time.strptime(d["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))  # the feed stamps in UTC
            pos += max(0.0, time.time() - ts)
        except ValueError:
            pass
    art = d.get("artworkData")
    try:
        cover = base64.b64decode(art) if art else None
    except ValueError:
        cover = None
    title, artist = d.get("title") or "", d.get("artist") or ""
    return {
        "player": player, "state": "playing" if playing else "paused",
        "id": f"{player}:{d.get('contentItemIdentifier') or title + '|' + artist}",
        "title": title, "artist": artist, "album": d.get("album") or "",
        "cover_url": None, "cover_bytes": cover,
        "duration_ms": int(float(d.get("duration") or 0) * 1000), "position_s": pos,
    }


def read() -> Optional[Track]:
    """Spotify, then Music, by AppleScript; then the system feed. A player that is
    playing beats one that is paused, so a Firefox tab wins over a paused Spotify."""
    global _last_music_id, _last_music_art
    procs = _running()
    direct: Optional[Track] = None
    if "Spotify" in procs:
        t = _parse(_osa(SPOTIFY), "Spotify")
        if t and t["state"] in ("playing", "paused"):
            direct = t
    if "Music" in procs and (direct is None or direct["state"] == "paused"):
        t = _parse(_osa(MUSIC), "Music")
        if t and t["state"] in ("playing", "paused") and (direct is None or t["state"] == "playing"):
            if t["id"] != _last_music_id:  # artwork is heavy; fetch once per track
                _last_music_art = _music_artwork()
                _last_music_id = t["id"]
            t["cover_bytes"] = _last_music_art
            direct = t
    if direct is not None and direct["state"] == "playing":
        return direct
    other = _system_now_playing()
    if other and other["state"] == "playing" and other["player"] not in ("Spotify", "Music"):
        return other
    return direct or other


def next_track() -> bool:
    """Skip to the next song in whichever player is active. Never launches an app."""
    procs = _running()
    for app in ("Spotify", "Music"):
        if app in procs:
            state = _osa(f'tell application "{app}" to (player state as string)')
            if state in ("playing", "paused"):
                _osa(f'tell application "{app}" to next track')
                return True
    if MEDIA_CONTROL and _system_now_playing():
        try:
            subprocess.run([*MEDIA_CONTROL, "next-track"], capture_output=True, timeout=10)
            return True
        except (subprocess.SubprocessError, OSError):
            return False
    return False
