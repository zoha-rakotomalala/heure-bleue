"""Local HTTP server. Serves web/ and data/ and a small JSON API.

  GET  /api/config                -> city, locale, language, units, theme, rotate_minutes (the page reads this)
  GET  /api/favorites             -> kept paintings
  GET  /api/taste                 -> weights derived from favorites
  GET  /api/history?limit=N       -> last N rows of history.jsonl (for the stats page)
  POST /api/favorite {painting, track?} -> toggle; remembers the song playing; rebuilds taste; starts the artist hour
  POST /api/swap                  -> ask the wall loop for another painting now
  POST /api/next                  -> skip the player to the next song; the wall follows at once
  POST /api/seen {...}            -> append one line to history.jsonl
  GET  /api/version               -> this version, the latest GitHub release, whether it is newer
  POST /api/update/open           -> open that release page in the system browser
  POST /api/update/install        -> packaged app: download, verify, swap, relaunch (progress in /api/version)
  POST /api/config {update_mode | taste} -> write a setting to config.json (the ⚙ panel's toggles)
  POST /api/open {url}            -> open one of our own pages (credits, source) in the system browser
  POST /api/card                  -> render the share card (PNG) to the Desktop and reveal it
  GET  /api/favorites.csv|.md     -> the Kept list as a download; POST the same path saves it to the Desktop
  GET  /api/today                 -> painters in the index born or died on this day

Binds to 127.0.0.1 by default. Nothing here needs or holds a credential.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import config, updates
from .wall import load_index, painters_of_the_day

OPEN_ALLOWED = ("https://zoha-rakotomalala.github.io/", "https://github.com/zoha-rakotomalala/heure-bleue")
PUBLIC_CFG_KEYS = ("city", "locale", "language", "units", "theme", "rotate_minutes", "paused_rotate_minutes", "repeat_days", "taste")
SEEN_DEDUPE_S = 15  # a second window reporting the same painting within this window is an echo
_LAST_SEEN: dict = {}
_SEEN_LOCK = threading.Lock()


def today_paintings() -> list[dict]:
    """Distinct paintings shown since local midnight, oldest first, from history.jsonl."""
    start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    seen, out = set(), []
    try:
        for line in config.HISTORY.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("ts", 0) >= start and row.get("id") and row.get("title") and row["id"] not in seen:
                seen.add(row["id"]); out.append(row)
    except FileNotFoundError:
        pass
    return out


def export_favorites(favs: list[dict], fmt: str) -> tuple[str, bytes, str]:
    """The Kept list as a file of the user's own: CSV for a spreadsheet, Markdown for notes."""
    stamp = time.strftime("%Y-%m-%d")
    if fmt == "csv":
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["kept", "title", "artist", "date", "museum", "song", "song_artist", "album", "url", "image"])
        for f in favs:
            t = f.get("track") or {}
            w.writerow([f.get("saved_at"), f.get("title"), f.get("artist"), f.get("date"), f.get("museum"), t.get("title"), t.get("artist"), t.get("album"), f.get("url"), f.get("image")])
        return f"heure bleue kept {stamp}.csv", buf.getvalue().encode("utf-8-sig"), "text/csv"
    lines = [f"# Kept paintings · heure bleue · {stamp}", "", f"{len(favs)} paintings, newest first.", ""]
    for f in reversed(favs):
        t = f.get("track") or {}
        who = " · ".join(s for s in (f.get("artist"), f.get("date")) if s)
        lines.append(f"- **[{f.get('title')}]({f.get('url') or f.get('image')})** — {who}  ")
        lines.append(f"  {f.get('museum') or ''}" + (f" · while playing *{t['title']}* by {t.get('artist')}" if t.get("title") else "") + f" · kept {f.get('saved_at')}")
    return f"heure bleue kept {stamp}.md", ("\n".join(lines) + "\n").encode("utf-8"), "text/markdown"


def load_favs() -> list[dict]:
    try:
        return json.loads(config.FAVORITES.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_history(limit: int = 20000) -> list[dict]:
    """Last `limit` rows of history.jsonl. Bad lines are skipped, never fatal."""
    try:
        lines = config.HISTORY.read_text(encoding="utf-8").splitlines()[-limit:]
    except FileNotFoundError:
        return []
    rows = []
    for ln in lines:
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows


TRACK_KEYS = ("title", "artist", "album", "cover", "player")


def century(date):
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})", date or "")
    return str(int(m.group(1)) // 100 + 1) if m else None


def rebuild_taste(favs: list[dict]) -> dict:
    artists, museums, centuries, colors = Counter(), Counter(), Counter(), []
    for f in favs:
        if f.get("artist") and f["artist"] != "Unknown artist":
            artists[f["artist"]] += 1
        if f.get("museum"):
            museums[f["museum"]] += 1
        if (c := century(f.get("date"))):
            centuries[c] += 1
        colors += [col["hex"] for col in (f.get("palette") or [])[:2]]

    def norm(cnt):
        top = max(cnt.values(), default=1)
        return {k: round(v / top, 3) for k, v in cnt.items()}

    taste = {"n": len(favs), "artists": norm(artists), "museums": norm(museums), "centuries": norm(centuries),
             "colors": colors[-20:], "updated_at": time.time()}
    config.TASTE.write_text(json.dumps(taste, ensure_ascii=False, indent=1), encoding="utf-8")
    return taste


class Handler(SimpleHTTPRequestHandler):
    cfg: dict = {}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(config.WEB), **kw)

    def log_message(self, fmt, *args):  # quiet
        pass

    def translate_path(self, path: str) -> str:
        p = urlsplit(path).path
        if p.startswith("/data/"):
            return str((config.DATA / p[6:]).resolve())
        return super().translate_path(path)

    def end_headers(self):
        if self.path.startswith(("/data/", "/api/")):
            self.send_header("Cache-Control", "no-store")
        else:
            # the page and its scripts: ask again every load, so an updated app never shows the old page
            # (WebKit kept a stale index.html across the 0.3.1 -> 0.3.2 update; the server is loopback, so this costs nothing)
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _file_download(self, name: str, data: bytes, mime: str):
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlsplit(self.path).path
        if p == "/api/config":
            return self._json({k: self.cfg[k] for k in PUBLIC_CFG_KEYS})
        if p == "/api/favorites":
            return self._json(load_favs())
        if p == "/api/version":
            return self._json(updates.state())
        if p == "/api/today":
            return self._json(painters_of_the_day())
        if p in ("/api/favorites.csv", "/api/favorites.md"):
            return self._file_download(*export_favorites(load_favs(), p.rsplit(".", 1)[1]))
        if p == "/api/taste":
            try:
                return self._json(json.loads(config.TASTE.read_text(encoding="utf-8")))
            except (FileNotFoundError, json.JSONDecodeError):
                return self._json(rebuild_taste(load_favs()))
        if p == "/api/history":
            q = dict(x.split("=", 1) for x in urlsplit(self.path).query.split("&") if "=" in x)
            try:
                limit = max(1, min(int(q.get("limit", 20000)), 100000))
            except ValueError:
                limit = 20000
            return self._json(load_history(limit))
        if p == "/data/paintings.json":  # shipped index + this machine's local extras
            return self._json(load_index())
        if p.startswith("/data/") and not (config.DATA / p[6:]).exists():
            return self._json({"error": "not found"}, 404)
        return super().do_GET()

    def do_POST(self):
        p = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except json.JSONDecodeError:
            return self._json({"error": "bad json"}, 400)

        if p == "/api/update/open":
            return self._json({"ok": updates.open_latest()})

        if p == "/api/open":
            # the credits links: only our own pages, opened in the system browser (the app window has no address bar)
            url = str(body.get("url") or "")
            if not url.startswith(OPEN_ALLOWED):
                return self._json({"error": "not one of ours"}, 403)
            import webbrowser
            return self._json({"ok": webbrowser.open(url)})

        if p == "/api/update/install":
            try:
                return self._json(updates.install())
            except Exception as exc:  # noqa: BLE001
                return self._json({"error": str(exc)}, 409)

        if p == "/api/config":
            # the ⚙ panel: settings that live in config.json rather than the browser (shared by every window)
            out = {}
            if "update_mode" in body:
                out["update_mode"] = updates.set_mode(body["update_mode"])
                self.cfg["update_mode"] = out["update_mode"]
            if "rotate_minutes" in body:
                try:
                    m = max(1, min(60, int(body["rotate_minutes"])))
                except (TypeError, ValueError):
                    return self._json({"error": "rotate_minutes must be a number"}, 400)
                out["rotate_minutes"] = self.cfg["rotate_minutes"] = m
                config.save_keys(rotate_minutes=m)
            if "taste" in body:
                out["taste"] = self.cfg["taste"] = bool(body["taste"])  # the wall loop shares this dict, so the next choice sees it
                config.save_keys(taste=out["taste"])
            if not out:
                return self._json({"error": "nothing to set"}, 400)
            return self._json(out)

        if p == "/api/card":
            # the share card: a PNG of the wall right now, saved to the Desktop and shown in the file manager
            from . import card
            try:
                now = json.loads(config.NOW.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                now = {}
            if not (now.get("painting") or {}).get("image"):
                return self._json({"error": "no painting on the wall yet"}, 409)
            now["cover_file"] = str(config.COVER)
            index = {q["id"]: q for q in load_index()}
            img = card.render(now, today_paintings(), index, time.strftime("%A %d %B %Y"))
            path = card.save(img)
            card.reveal(path)
            return self._json({"ok": True, "path": str(path)})

        if p == "/api/favorites.csv" or p == "/api/favorites.md":
            name, data, mime = export_favorites(load_favs(), p.rsplit(".", 1)[1])
            from . import card
            folder = card.desktop()
            if not folder.exists():
                folder = config.DATA.parent
            path = folder / name
            path.write_bytes(data)
            card.reveal(path)
            return self._json({"ok": True, "path": str(path), "count": len(load_favs())})

        if p == "/api/swap":
            config.SWAP.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")
            return self._json({"ok": True})

        if p == "/api/next":
            from . import wall
            ok = wall.request_next()
            return self._json({"ok": ok} if ok else {"ok": False, "error": "no player answered"}, 200 if ok else 409)

        if p == "/api/seen":
            row = {k: body.get(k) for k in ("id", "title", "artist", "museum", "mode", "track", "track_artist", "dwell_s", "swapped")}
            row["ts"] = time.time()
            # two windows showing the wall report the same change a few seconds apart: keep one
            key = (row["id"], row["track"])
            with _SEEN_LOCK:
                last = _LAST_SEEN.get("row")
                if last and (last["id"], last["track"]) == key and row["ts"] - last["ts"] < SEEN_DEDUPE_S:
                    return self._json({"ok": True, "deduped": True})
                _LAST_SEEN["row"] = row
                with config.HISTORY.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            return self._json({"ok": True})

        if p == "/api/favorite":
            painting = body.get("painting") or {}
            if not painting.get("id"):
                return self._json({"error": "painting.id required"}, 400)
            favs = load_favs()
            if any(f["id"] == painting["id"] for f in favs):
                favs = [f for f in favs if f["id"] != painting["id"]]
                state = False
            else:
                keep = {k: painting.get(k) for k in ("id", "title", "artist", "date", "museum", "url", "image", "palette")}
                keep["saved_at"] = time.strftime("%Y-%m-%d %H:%M")
                track = body.get("track")
                keep["track"] = {k: track.get(k) for k in TRACK_KEYS} if isinstance(track, dict) and track.get("title") else None
                favs.append(keep)
                state = True
            config.FAVORITES.write_text(json.dumps(favs, ensure_ascii=False, indent=1), encoding="utf-8")
            taste = rebuild_taste(favs)
            if state:
                config.ARTIST_HOUR.write_text(json.dumps({"artist": painting.get("artist"), "until": time.time() + 3600}), encoding="utf-8")
            return self._json({"favorite": state, "count": len(favs), "taste_n": taste["n"]})

        return self._json({"error": "unknown endpoint"}, 404)


def serve(cfg: dict) -> ThreadingHTTPServer:
    config.DATA.mkdir(parents=True, exist_ok=True)
    Handler.cfg = cfg
    updates.start(cfg)
    ThreadingHTTPServer.allow_reuse_address = True
    return ThreadingHTTPServer((cfg["host"], cfg["port"]), Handler)
