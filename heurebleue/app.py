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
    url = f"http://{cfg['host']}:{cfg['port']}/"

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
        f"heure bleue {__version__}", url,
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
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
    return 0
