"""Windows: the system media session (SMTC), the same source as the volume-key
media overlay. Sees Spotify, Apple Music, iTunes, Groove, browsers.

Requires one of:  pip install winsdk      (Python 3.9-3.12)
                  pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams
Without it, read() returns None and `heurebleue doctor` says what to install.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from . import Track

_mod = None
try:  # winsdk (single package)
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as _Mgr  # type: ignore
    from winsdk.windows.storage.streams import Buffer as _Buffer, DataReader as _DataReader, InputStreamOptions as _Opts  # type: ignore
    _mod = "winsdk"
except Exception:  # noqa: BLE001
    try:  # winrt namespace packages
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as _Mgr  # type: ignore
        from winrt.windows.storage.streams import Buffer as _Buffer, DataReader as _DataReader, InputStreamOptions as _Opts  # type: ignore
        _mod = "winrt"
    except Exception:  # noqa: BLE001
        _mod = None

PLAYING, PAUSED = 4, 5  # GlobalSystemMediaTransportControlsSessionPlaybackStatus


def available() -> bool:
    return _mod is not None


async def _read_stream(ref) -> Optional[bytes]:
    if ref is None:
        return None
    stream = await ref.open_read_async()
    size = stream.size
    if not size:
        return None
    buf = _Buffer(size)
    await stream.read_async(buf, size, _Opts.NONE)
    reader = _DataReader.from_buffer(buf)
    return bytes(reader.read_bytes(buf.length))


_last_id = None
_last_art: Optional[bytes] = None


async def _read_async() -> Optional[Track]:
    global _last_id, _last_art
    mgr = await _Mgr.request_async()
    session = mgr.get_current_session()
    if session is None:
        return None
    info = session.get_playback_info()
    status = int(info.playback_status)
    if status not in (PLAYING, PAUSED):
        return None
    props = await session.try_get_media_properties_async()
    tl = session.get_timeline_properties()
    app = (session.source_app_user_model_id or "player").split("!")[0]
    player = "Spotify" if "spotify" in app.lower() else ("Music" if "apple" in app.lower() or "itunes" in app.lower() else app)
    tid = f"{player}:{props.title}|{props.artist}|{props.album_title}"
    if tid != _last_id:
        try:
            _last_art = await _read_stream(props.thumbnail)
        except Exception:  # noqa: BLE001
            _last_art = None
        _last_id = tid
    return {
        "player": player, "state": "playing" if status == PLAYING else "paused", "id": tid,
        "title": props.title or "", "artist": props.artist or "", "album": props.album_title or "",
        "cover_url": None, "cover_bytes": _last_art,
        "duration_ms": int(tl.end_time.total_seconds() * 1000) if tl.end_time else 0,
        "position_s": tl.position.total_seconds() if tl.position else 0.0,
    }


def read() -> Optional[Track]:
    if not available():
        return None
    try:
        return asyncio.run(_read_async())
    except Exception:  # noqa: BLE001
        return None
