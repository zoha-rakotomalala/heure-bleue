"""Linux: MPRIS through `playerctl` (apt/dnf/pacman install playerctl).
Any MPRIS player works: Spotify, Rhythmbox, VLC, browsers."""
from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from . import Track

FMT = "{{status}}\t{{playerName}}\t{{mpris:trackid}}\t{{title}}\t{{artist}}\t{{album}}\t{{mpris:artUrl}}\t{{mpris:length}}\t{{position}}"


def read() -> Optional[Track]:
    if not shutil.which("playerctl"):
        return None
    try:
        r = subprocess.run(["playerctl", "metadata", "--format", FMT], capture_output=True, text=True, timeout=5)
    except Exception:  # noqa: BLE001
        return None
    line = r.stdout.strip()
    if r.returncode != 0 or not line:
        return None
    parts = line.split("\t")
    if len(parts) < 9:
        return None
    status, player, tid, title, artist, album, art, length, pos = parts[:9]
    if status not in ("Playing", "Paused"):
        return None
    cover_url, cover_bytes = None, None
    if art.startswith("file://"):
        try:
            cover_bytes = open(art[7:], "rb").read()
        except OSError:
            pass
    elif art.startswith("http"):
        cover_url = art
    return {
        "player": player.capitalize(), "state": status.lower(), "id": f"{player}:{tid or title + '|' + artist}",
        "title": title, "artist": artist, "album": album, "cover_url": cover_url, "cover_bytes": cover_bytes,
        "duration_ms": int(int(length or 0) / 1000), "position_s": int(pos or 0) / 1_000_000,
    }
