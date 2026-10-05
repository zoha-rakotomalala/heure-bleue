"""Ask GitHub whether a newer release exists, and install it on request.

One request a day, in a daemon thread, never on the request path. The result
is kept in memory and served by GET /api/version:

  {"version": "0.2.0", "latest": "0.3.0" | null, "url": ..., "newer": true,
   "can_install": true, "install": {"phase": "downloading", "pct": 42} | null}

POST /api/update/open   opens the release page in the system browser.
POST /api/update/install (packaged macOS app only) downloads the matching .dmg,
checks its SHA-256 against the SHA256SUMS.txt published with the release, mounts
it, swaps the bundle in place and relaunches. Nothing outside the .app is touched;
paintings and settings live in the user folder. The old bundle is parked under
<user folder>/updates/previous.app and removed on the next start.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, Optional

from . import REPO, __version__, config

API = os.environ.get("HEURE_BLEUE_RELEASE_API") or f"https://api.github.com/repos/{REPO}/releases/latest"  # the override is for tests
RELEASES = f"https://github.com/{REPO}/releases/latest"
EVERY = 24 * 3600
UA = {"User-Agent": f"heure-bleue/{__version__} (+https://github.com/{REPO})"}

_state: dict = {"version": __version__, "latest": None, "url": RELEASES, "newer": False, "assets": {}, "install": None}
_lock = threading.Lock()
on_quit: Optional[Callable[[], None]] = None  # set by the app window so a finished install can close it


def _tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def _arch() -> str:
    return "arm64" if platform.machine() == "arm64" else "intel"


def _asset_name(tag: str) -> str:
    return f"HeureBleue-v{tag}-mac-{_arch()}.dmg"


def check_once(timeout: float = 8.0) -> dict:
    req = urllib.request.Request(API, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rel = json.load(r)
    tag = str(rel.get("tag_name") or "").lstrip("v")
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", []) if a.get("browser_download_url")}
    with _lock:
        _state.update(latest=tag or None, url=rel.get("html_url") or RELEASES, assets=assets,
                      newer=bool(tag) and _tuple(tag) > _tuple(__version__))
        return dict(_state)


def can_install() -> bool:
    """Only the packaged macOS app can replace itself; a checkout updates with git."""
    with _lock:
        newer, latest, assets = _state["newer"], _state["latest"], _state["assets"]
    return bool(config.FROZEN and config.system() == "macos" and newer and latest
                and _asset_name(latest) in assets and "SHA256SUMS.txt" in assets
                and bundle_path() is not None)


def state() -> dict:
    with _lock:
        d = {k: v for k, v in _state.items() if k != "assets"}
    d["can_install"] = False
    try:
        d["can_install"] = can_install() if d["newer"] else False
    except Exception:  # noqa: BLE001
        pass
    return d


def open_latest() -> bool:
    return webbrowser.open(state()["url"])


def bundle_path() -> Optional[Path]:
    """The .app this process runs from; /Applications/HeureBleue.app when macOS translocated it."""
    exe = Path(sys.executable).resolve()
    for p in exe.parents:
        if p.suffix == ".app":
            if "/AppTranslocation/" in str(p):
                home = Path("/Applications") / p.name
                return home if home.exists() else None
            return p
    return None


def _progress(phase: str, pct: Optional[int] = None, error: Optional[str] = None) -> None:
    with _lock:
        _state["install"] = {"phase": phase, "pct": pct, "error": error}


def _download(url: str, dest: Path, on_pct: Optional[Callable[[int], None]] = None) -> None:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 18)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if on_pct and total:
                on_pct(min(99, done * 100 // total))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _expected_sum(sums_text: str, name: str) -> Optional[str]:
    for line in sums_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*").split("/")[-1] == name:
            return parts[0].lower()
    return None


def _bundle_version(app: Path) -> str:
    with open(app / "Contents" / "Info.plist", "rb") as f:
        return str(plistlib.load(f).get("CFBundleShortVersionString", ""))


def install_from(dmg_url: str, sums_url: str, tag: str, target: Path, relaunch: bool = True) -> Path:
    """Download, verify, mount, swap. Returns the path of the installed bundle. Raises on any failure."""
    work = config.ROOT / "updates"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    name = _asset_name(tag)
    dmg, mount = work / name, work / "mnt"
    try:
        _progress("downloading", 0)
        _download(dmg_url, dmg, lambda p: _progress("downloading", p))
        _progress("verifying")
        sums = work / "SHA256SUMS.txt"
        _download(sums_url, sums)
        want = _expected_sum(sums.read_text(encoding="utf-8"), name)
        if not want:
            raise RuntimeError(f"{name} is not listed in SHA256SUMS.txt")
        got = _sha256(dmg)
        if got != want:
            raise RuntimeError(f"checksum mismatch for {name}")

        _progress("installing")
        mount.mkdir(exist_ok=True)
        subprocess.run(["hdiutil", "attach", str(dmg), "-nobrowse", "-quiet", "-mountpoint", str(mount)], check=True, timeout=120)
        try:
            apps = [p for p in mount.iterdir() if p.suffix == ".app"]
            if len(apps) != 1:
                raise RuntimeError("the disk image does not hold exactly one app")
            if _bundle_version(apps[0]) != tag:
                raise RuntimeError(f"the image says {_bundle_version(apps[0])}, the release says {tag}")
            staged = target.with_name(target.stem + ".new.app")
            if staged.exists():
                shutil.rmtree(staged)
            subprocess.run(["ditto", str(apps[0]), str(staged)], check=True, timeout=300)
            subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(staged)], capture_output=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount), "-quiet"], capture_output=True, timeout=60)
        previous = work / "previous.app"
        if target.exists():
            os.rename(target, previous)  # the running process keeps its files; the folder is cleaned next start
        os.rename(staged, target)
        _progress("restarting", 100)
    except Exception as exc:  # noqa: BLE001
        _progress("error", error=str(exc))
        raise
    finally:
        dmg.unlink(missing_ok=True)
    if relaunch:
        _relaunch(target)
    return target


def _relaunch(target: Path) -> None:
    """Start the new bundle once this process has gone, then close this one."""
    env = " ".join(f'--env {k}="{os.environ[k]}"' for k in ("HEURE_BLEUE_HOME", "HEURE_BLEUE_RELEASE_API") if k in os.environ)
    # wait for THIS process to be gone (open only activates an app that still runs), then start the new bundle
    script = (f'for i in $(seq 1 60); do kill -0 {os.getpid()} 2>/dev/null || break; sleep 0.5; done; '
              f'open {env} "{target}"')
    subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def quit_soon():
        time.sleep(1.0)  # let /api/version report "restarting" once
        try:
            if on_quit:
                on_quit()
        finally:
            threading.Timer(4.0, os._exit, [0]).start()
    threading.Thread(target=quit_soon, daemon=True).start()


def install() -> dict:
    """Begin the self-update in the background. Returns the state; raises if it cannot start."""
    s = state()
    if not s["can_install"]:
        raise RuntimeError("this build cannot update itself")
    if s["install"] and s["install"]["phase"] not in (None, "error"):
        return s
    with _lock:
        tag, assets = _state["latest"], dict(_state["assets"])
    target = bundle_path()

    def run():
        try:
            install_from(assets[_asset_name(tag)], assets["SHA256SUMS.txt"], tag, target)
        except Exception:  # noqa: BLE001  state already says error
            pass
    _progress("downloading", 0)
    threading.Thread(target=run, name="update-install", daemon=True).start()
    return state()


def clean_previous() -> None:
    """Remove the bundle parked by the last update. Called at start."""
    prev = config.ROOT / "updates" / "previous.app"
    if prev.exists():
        shutil.rmtree(prev, ignore_errors=True)


def start(cfg: dict) -> None:
    """Begin the daily check in the background. No-op when config.json says update_check: false."""
    if not cfg.get("update_check", True):
        return
    clean_previous()

    def loop():
        time.sleep(3 if "HEURE_BLEUE_RELEASE_API" in os.environ else 20)  # let the wall come up first
        while True:
            try:
                check_once()
            except Exception:  # noqa: BLE001  offline, rate-limited, GitHub down: try again tomorrow
                pass
            time.sleep(EVERY)

    threading.Thread(target=loop, name="update-check", daemon=True).start()
