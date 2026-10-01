"""heurebleue command line.

  python -m heurebleue start              run the wall (server + player loop) in one process
  python -m heurebleue doctor             check Python, Pillow, player backend, index, port
  python -m heurebleue open               open the wall in the default browser
  python -m heurebleue index --target N   grow data/paintings.json from the museums
  python -m heurebleue stories            add curator texts to Rijksmuseum entries
  python -m heurebleue service install    start at login (launchd / Task Scheduler / systemd)
  python -m heurebleue service remove
  python -m heurebleue demo --out site    build the static web demo (GitHub Pages)
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import webbrowser

from . import config


def cmd_start(args) -> int:
    from . import server, wall
    cfg = config.load()
    if not config.PAINTINGS.exists():
        print("no data/paintings.json yet. Run:  python -m heurebleue index", file=sys.stderr)
        return 2
    stop = threading.Event()
    httpd = server.serve(cfg)
    t = threading.Thread(target=wall.run, args=(stop, cfg), name="wall", daemon=True)
    t.start()
    url = f"http://{cfg['host']}:{cfg['port']}/"
    print(f"heure bleue on {url}   (Ctrl-C to stop)", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        httpd.server_close()
    return 0


def cmd_doctor(_args) -> int:
    from . import nowplaying
    cfg = config.load()
    ok = True

    def line(label, good, detail=""):
        nonlocal ok
        ok &= bool(good)
        print(f"  [{'ok' if good else '!!'}] {label:<18} {detail}")

    print(f"heure bleue doctor ({config.system()}, Python {sys.version.split()[0]})")
    line("python", sys.version_info >= (3, 10), "3.10+ required" if sys.version_info < (3, 10) else "")
    try:
        import PIL  # noqa: F401
        line("pillow", True, PIL.__version__)
    except ImportError:
        line("pillow", False, "pip install pillow")
    name, read, _next = nowplaying.detect()
    line("player backend", "unavailable" not in name and name != "unsupported", name)
    try:
        t = read()
        line("now playing", True, f"{t['player']}: {t['title']} - {t['artist']} ({t['state']})" if t else "nothing playing (that is fine)")
    except Exception as exc:  # noqa: BLE001
        line("now playing", False, f"read failed: {exc}")
    if config.PAINTINGS.exists():
        n = len(json.loads(config.PAINTINGS.read_text(encoding="utf-8")))
        line("index", n > 0, f"{n} paintings")
    else:
        line("index", False, "missing: python -m heurebleue index")
    with socket.socket() as s:
        free = s.connect_ex((cfg["host"], cfg["port"])) != 0
    line("port", True, f"{cfg['port']} {'free' if free else 'in use (already running?)'}")
    line("city", True, f"{cfg['city']['name']} ({cfg['city']['timezone']})")
    return 0 if ok else 1


def cmd_open(_args) -> int:
    cfg = config.load()
    webbrowser.open(f"http://{cfg['host']}:{cfg['port']}/")
    return 0


def cmd_index(args) -> int:
    from . import indexer
    return indexer.main(target=args.target, source=args.source, delay=args.delay,
                        argv=["--allow-cc"] if args.allow_cc else [])


def cmd_stories(args) -> int:
    from . import stories
    return stories.main(force=args.force)


def cmd_service(args) -> int:
    from . import service
    print(service.install() if args.action == "install" else service.remove())
    return 0


def cmd_demo(args) -> int:
    from . import demo
    return demo.main(out=args.out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="heurebleue", description="a gallery wall for a spare screen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start", help="run the wall"); p.add_argument("--open", action="store_true", help="also open the browser"); p.set_defaults(fn=cmd_start)
    sub.add_parser("doctor", help="check the setup").set_defaults(fn=cmd_doctor)
    sub.add_parser("open", help="open the wall in a browser").set_defaults(fn=cmd_open)
    p = sub.add_parser("index", help="grow the painting index")
    p.add_argument("--target", type=int, default=420); p.add_argument("--source", default="all", help="met, rijks, a Commons museum slug, commons, or all"); p.add_argument("--delay", type=float, default=0.8)
    p.add_argument("--allow-cc", action="store_true", help="also keep CC BY files, in data/paintings.local.json (this machine only)")
    p.set_defaults(fn=cmd_index)
    p = sub.add_parser("stories", help="add curator texts to Rijksmuseum entries"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_stories)
    p = sub.add_parser("service", help="start at login"); p.add_argument("action", choices=["install", "remove"]); p.set_defaults(fn=cmd_service)
    p = sub.add_parser("demo", help="build the static web demo (no music)"); p.add_argument("--out", default="site"); p.set_defaults(fn=cmd_demo)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
