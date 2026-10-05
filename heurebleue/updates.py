"""Ask GitHub whether a newer release exists.

One request a day, in a daemon thread, never on the request path. The result
is kept in memory and served by GET /api/version:

  {"version": "0.2.0", "latest": "0.3.0" | null, "url": "https://github.com/.../releases/latest", "newer": true}

POST /api/update/open opens that release page in the system browser. The page
can only open the URL this module fetched, never one it sends.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
import webbrowser

from . import REPO, __version__

API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES = f"https://github.com/{REPO}/releases/latest"
EVERY = 24 * 3600

_state = {"version": __version__, "latest": None, "url": RELEASES, "newer": False}
_lock = threading.Lock()


def _tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def check_once(timeout: float = 8.0) -> dict:
    req = urllib.request.Request(API, headers={"User-Agent": f"heure-bleue/{__version__} (+https://github.com/{REPO})",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rel = json.load(r)
    tag = str(rel.get("tag_name") or "").lstrip("v")
    url = rel.get("html_url") or RELEASES
    with _lock:
        _state.update(latest=tag or None, url=url, newer=bool(tag) and _tuple(tag) > _tuple(__version__))
        return dict(_state)


def state() -> dict:
    with _lock:
        return dict(_state)


def open_latest() -> bool:
    return webbrowser.open(state()["url"])


def start(cfg: dict) -> None:
    """Begin the daily check in the background. No-op when config.json says update_check: false."""
    if not cfg.get("update_check", True):
        return

    def loop():
        time.sleep(20)  # let the wall come up first
        while True:
            try:
                check_once()
            except Exception:  # noqa: BLE001  offline, rate-limited, GitHub down: try again tomorrow
                pass
            time.sleep(EVERY)

    threading.Thread(target=loop, name="update-check", daemon=True).start()
