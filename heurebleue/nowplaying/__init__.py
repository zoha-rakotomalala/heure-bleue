"""Now-playing backends.

Each backend exposes  read() -> Track | None  and  next_track() -> bool
(skip to the next song; False when no player answered). Track is a plain dict:

  {
    "player":      "Spotify" | "Music" | "<app name>",
    "state":       "playing" | "paused",
    "id":          stable id for the track (uri, persistent id, or title|artist),
    "title":       str,
    "artist":      str,
    "album":       str,
    "cover_url":   str | None,   # http(s) URL when the player gives one
    "cover_bytes": bytes | None, # raw image when the player gives data instead
    "duration_ms": int,
    "position_s":  float,
  }

None means nothing is playing or no supported player is running.

  macOS   -> AppleScript (Spotify, Music), then media-control for any other player when installed
  Windows -> system media session (SMTC) via winsdk, any player
  Linux   -> MPRIS via playerctl, any player
"""
from __future__ import annotations

import shutil
from typing import Callable, Optional

from .. import config

Track = dict


def detect() -> tuple[str, Callable[[], Optional[Track]], Callable[[], bool]]:
    """Return (backend name, read function, next_track function) for this machine."""
    sys_ = config.system()
    if sys_ == "macos":
        from . import macos
        return ("macos/applescript+media-control" if macos.MEDIA_CONTROL else "macos/applescript"), macos.read, macos.next_track
    if sys_ == "windows":
        from . import windows
        return ("windows/smtc" if windows.available() else "windows/unavailable"), windows.read, windows.next_track
    if sys_ == "linux":
        from . import linux
        name = "linux/playerctl" if shutil.which("playerctl") else "linux/unavailable (install playerctl)"
        return name, linux.read, linux.next_track
    return "unsupported", lambda: None, lambda: False
