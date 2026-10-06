"""The wall as a desktop app: the server and the player loop in this process,
the page in a native window (pywebview: WKWebView on macOS, WebView2 on
Windows, WebKitGTK or Qt on Linux). No browser, no address bar.

  python -m heurebleue app                 a window on the main screen
  python -m heurebleue app --fullscreen    fill the screen
  python -m heurebleue app --screen 2      put it on the second screen (1 = main)

Closing the window stops everything. The browser pages keep working while the
window is open: http://127.0.0.1:8765/ answers as before.
"""
from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path
import time
import urllib.request

from . import __version__, config


def _wait_for(url: str, seconds: float = 8.0) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1).read(1)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.1)


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex((host, port)) == 0


def _purge_web_cache_on_new_version() -> None:
    """First launch of a new version: drop the web view's HTTP cache.

    The pages name their scripts with the version (i18n.js?v=0.4.2) and the server
    says no-cache, but a cache written by an OLDER version predates both rules, and
    WebKit kept 0.3.2's i18n.js across the 0.4.1 update, so the new page showed raw
    translation keys. The cache is only images and scripts; kept paintings, history
    and the panel choices live elsewhere and are not touched."""
    import shutil
    stamp = config.ROOT / "webview" / "version"
    try:
        if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == __version__:
            return
    except OSError:
        return
    s = config.system()
    if s == "macos":
        caches = [Path.home() / "Library" / "Caches" / "dev.heurebleue.wall" / "WebKit" / "NetworkCache"]
    elif s == "windows":
        caches = [config.ROOT / "webview" / "EBWebView" / "Default" / "Cache", config.ROOT / "webview" / "EBWebView" / "Default" / "Code Cache"]
    else:
        caches = [config.ROOT / "webview" / "cache", Path.home() / ".cache" / "heure-bleue"]
    for c in caches:
        shutil.rmtree(c, ignore_errors=True)
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(__version__ + "\n", encoding="utf-8")
    except OSError:
        pass


def run(fullscreen: bool = False, screen_index: int = 1, debug: bool = False) -> int:
    try:
        import webview
    except ImportError:
        print("the app window needs pywebview:  python3 -m pip install pywebview", file=sys.stderr)
        return 2
    from . import server, updates, wall

    cfg = config.load()
    if not config.PAINTINGS.exists():
        print(f"no painting index at {config.PAINTINGS}", file=sys.stderr)
        return 2
    url = f"http://{cfg['host']}:{cfg['port']}/?v={__version__}"  # a new build gets a fresh cache entry whatever the web view remembers
    _purge_web_cache_on_new_version()

    stop = threading.Event()
    httpd = None
    if _port_in_use(cfg["host"], cfg["port"]):
        # `heurebleue start` or another window is already serving: just open a window on it
        print(f"a wall is already running on {url}, opening a window on it", flush=True)
    else:
        httpd = server.serve(cfg)
        threading.Thread(target=httpd.serve_forever, name="http", daemon=True).start()
        threading.Thread(target=wall.run, args=(stop, cfg), name="wall", daemon=True).start()
        _wait_for(url)

    screens = webview.screens
    screen = screens[screen_index - 1] if 0 < screen_index <= len(screens) else None
    window = webview.create_window(
        "heure bleue", url,  # the version lives in /api/version and the gold line, not in the title bar
        screen=screen, fullscreen=fullscreen,
        width=1280, height=800, min_size=(640, 400),
        background_color="#0f1a17",  # the forest theme's dark, so the first frame is not white
        text_select=False,
    )

    class Api:
        def toggle_fullscreen(self):
            window.toggle_fullscreen()

    window.expose(Api().toggle_fullscreen)
    updates.on_quit = window.destroy  # a finished self-update closes the window; the new app opens itself

    storage = config.ROOT / "webview"  # localStorage: language, place, units chosen in the panel
    storage.mkdir(parents=True, exist_ok=True)
    try:
        webview.start(private_mode=False, storage_path=str(storage), debug=debug)
    finally:
        stop.set()
        updates.apply_if_ready()  # update_mode auto: a staged release is swapped in now, used at the next start
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
    return 0
