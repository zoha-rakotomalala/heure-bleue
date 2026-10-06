"""Find, verify and install new releases.

Check: one request a day to the GitHub releases API, in a daemon thread, never on
the request path. GET /api/version serves the result:

  {"version": "0.3.1", "latest": "0.3.2" | null, "url": ..., "newer": true,
   "can_install": true, "install": {"phase": "downloading", "pct": 42} | null}

Install (packaged app, any platform) goes in two steps so each mode can use them:

  stage()  download the asset for this machine + SHA256SUMS.txt + SHA256SUMS.txt.sig,
           check the Ed25519 signature on the sums with the public key below, check
           the asset's sum, unpack the new bundle next to the old one
  apply()  swap the bundles and, if asked, relaunch

  update_mode "click" (default): the wall's gold line reads "new version · install";
                                 one click runs stage + apply + relaunch.
  update_mode "auto":            stage as soon as a newer release is seen; the line
                                 reads "new version ready · restart"; the swap happens
                                 at quit, or at once when the line is clicked.

Trust: the signature proves the sums file came from the release key; the sums
prove the asset is the one that was signed. Both must pass or nothing changes.
The old bundle is parked under <user folder>/updates/previous and removed on the
next start. Paintings and settings live outside the bundle and are never touched.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path
from typing import Callable, Optional

from . import REPO, __version__, config

# Ed25519 public key of the release signing key. The private half signs
# SHA256SUMS.txt in the release workflow (secret HB_SIGNING_KEY).
PUBLIC_KEY_B64 = "YBTVaNQn1GUGI+sqyws/VD6vqkOySqFoQcNgvLlU1kk="

API = os.environ.get("HEURE_BLEUE_RELEASE_API") or f"https://api.github.com/repos/{REPO}/releases/latest"  # the override is for tests
RELEASES = f"https://github.com/{REPO}/releases/latest"
EVERY = 24 * 3600
UA = {"User-Agent": f"heure-bleue/{__version__} (+https://github.com/{REPO})"}
SUMS, SIG = "SHA256SUMS.txt", "SHA256SUMS.txt.sig"

_state: dict = {"version": __version__, "latest": None, "url": RELEASES, "newer": False, "assets": {}, "install": None}
_lock = threading.Lock()
_staged: Optional[Path] = None
_mode = "click"
on_quit: Optional[Callable[[], None]] = None  # set by the app window so a finished install can close it


def _tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def asset_name(tag: str) -> str:
    s = config.system()
    if s == "macos":
        return f"HeureBleue-v{tag}-mac-{'arm64' if platform.machine() == 'arm64' else 'intel'}.dmg"
    if s == "windows":
        return f"HeureBleue-v{tag}-windows-x64.zip"
    return f"HeureBleue-v{tag}-linux-x64.tar.gz"


# --- what is out there ----------------------------------------------------------

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
    """Only the packaged app can replace itself; a checkout updates with git."""
    with _lock:
        newer, latest, assets = _state["newer"], _state["latest"], _state["assets"]
    return bool(config.FROZEN and newer and latest and asset_name(latest) in assets
                and SUMS in assets and SIG in assets and bundle_path() is not None)


def state() -> dict:
    with _lock:
        d = {k: v for k, v in _state.items() if k != "assets"}
    d["can_install"] = bool(d["newer"]) and can_install()
    d["mode"] = _mode
    d["packaged"] = config.FROZEN  # only the packaged app can swap itself; a checkout updates with git
    return d


def open_latest() -> bool:
    return webbrowser.open(state()["url"])


# --- where we live ----------------------------------------------------------------

def bundle_path() -> Optional[Path]:
    """The installed bundle this process runs from.
    macOS: the .app (or /Applications/<name>.app when macOS translocated it).
    Windows, Linux: the folder holding the executable (PyInstaller one-folder build)."""
    exe = Path(sys.executable).resolve()
    if config.system() == "macos":
        for p in exe.parents:
            if p.suffix == ".app":
                if "/AppTranslocation/" in str(p):
                    home = Path("/Applications") / p.name
                    return home if home.exists() else None
                return p
        return None
    return exe.parent if config.FROZEN else None


def _bundle_version(bundle: Path) -> str:
    plist = bundle / "Contents" / "Info.plist"
    if plist.exists():
        with open(plist, "rb") as f:
            return str(plistlib.load(f).get("CFBundleShortVersionString", ""))
    for p in list(bundle.glob("VERSION")) + list(bundle.glob("*/VERSION")) + list(bundle.glob("*/*/VERSION")):
        return p.read_text(encoding="utf-8").strip()
    return ""


# --- download and verify -------------------------------------------------------

def _progress(phase: Optional[str], pct: Optional[int] = None, error: Optional[str] = None) -> None:
    with _lock:
        _state["install"] = None if phase is None else {"phase": phase, "pct": pct, "error": error}


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


def verify_signature(message: bytes, signature: bytes, public_key_b64: str = PUBLIC_KEY_B64) -> None:
    """Raise if `signature` is not a valid Ed25519 signature of `message` by the release key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    try:
        key.verify(signature, message)
    except InvalidSignature:
        raise RuntimeError("the release is not signed by the heure bleue key") from None


def _unpack(archive: Path, into: Path, tag: str) -> Path:
    """Unpack the downloaded asset into `into` and return the new bundle inside it."""
    into.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".dmg":
        mount = archive.parent / "mnt"
        mount.mkdir(exist_ok=True)
        subprocess.run(["hdiutil", "attach", str(archive), "-nobrowse", "-quiet", "-mountpoint", str(mount)], check=True, timeout=120)
        try:
            apps = [p for p in mount.iterdir() if p.suffix == ".app"]
            if len(apps) != 1:
                raise RuntimeError("the disk image does not hold exactly one app")
            dest = into / apps[0].name
            subprocess.run(["ditto", str(apps[0]), str(dest)], check=True, timeout=300)
            subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(dest)], capture_output=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount), "-quiet"], capture_output=True, timeout=60)
    elif archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            _safe_extract_names(z.namelist(), into)
            z.extractall(into)
        dest = _single_dir(into)
    else:
        with tarfile.open(archive, "r:gz") as t:
            _safe_extract_names(t.getnames(), into)
            t.extractall(into, filter="data") if hasattr(tarfile, "data_filter") else t.extractall(into)
        dest = _single_dir(into)
    found = _bundle_version(dest)
    if found != tag:
        raise RuntimeError(f"the download says {found or 'nothing'}, the release says {tag}")
    return dest


def _safe_extract_names(names, into: Path) -> None:
    root = into.resolve()
    for n in names:
        if not (root / n).resolve().is_relative_to(root):
            raise RuntimeError(f"archive entry escapes the folder: {n}")


def _single_dir(into: Path) -> Path:
    dirs = [p for p in into.iterdir() if p.is_dir()]
    if len(dirs) != 1:
        raise RuntimeError("the archive does not hold exactly one folder")
    return dirs[0]


def stage(dmg_url: str, sums_url: str, sig_url: str, tag: str) -> Path:
    """Download, verify, unpack. Returns the staged bundle. Raises on any failure."""
    global _staged
    work = config.ROOT / "updates"
    for p in ("staged", "mnt", asset_name(tag), SUMS, SIG):
        q = work / p
        if q.is_dir():
            shutil.rmtree(q, ignore_errors=True)
        elif q.exists():
            q.unlink()
    work.mkdir(parents=True, exist_ok=True)
    name = asset_name(tag)
    archive = work / name
    try:
        _progress("downloading", 0)
        _download(dmg_url, archive, lambda p: _progress("downloading", p))
        _progress("verifying")
        _download(sums_url, work / SUMS)
        _download(sig_url, work / SIG)
        sums_bytes = (work / SUMS).read_bytes()
        verify_signature(sums_bytes, (work / SIG).read_bytes())
        want = _expected_sum(sums_bytes.decode("utf-8"), name)
        if not want:
            raise RuntimeError(f"{name} is not listed in {SUMS}")
        if _sha256(archive) != want:
            raise RuntimeError(f"checksum mismatch for {name}")
        _progress("installing")
        bundle = _unpack(archive, work / "staged", tag)
        _staged = bundle
        _progress("ready", 100)
        return bundle
    except Exception as exc:  # noqa: BLE001
        _progress("error", error=str(exc))
        raise
    finally:
        archive.unlink(missing_ok=True)


# --- swap and relaunch -----------------------------------------------------------

def apply(staged: Path, target: Path, relaunch: bool = True) -> Path:
    """Put the staged bundle where the running one is. Windows cannot replace a running
    program, so there a helper script does the swap after this process exits."""
    global _staged
    previous = config.ROOT / "updates" / "previous"
    if previous.exists():
        shutil.rmtree(previous, ignore_errors=True)
    _progress("restarting", 100)
    if config.system() == "windows":
        _windows_swap_after_exit(staged, target, previous, relaunch)
    else:
        if target.exists():
            os.rename(target, previous)  # the running process keeps its files
        os.rename(staged, target)
        if relaunch:
            _posix_relaunch(target)
    _staged = None
    if relaunch:
        _quit_soon()
    return target


def _exe_in(bundle: Path) -> Path:
    if bundle.suffix == ".app":
        return bundle / "Contents" / "MacOS" / bundle.stem
    return bundle / ("HeureBleue.exe" if config.system() == "windows" else "HeureBleue")


def _passthrough_env() -> list[str]:
    return [k for k in ("HEURE_BLEUE_HOME", "HEURE_BLEUE_RELEASE_API") if k in os.environ]


def _posix_relaunch(target: Path) -> None:
    """Start the new bundle once this process is gone (`open` only activates a running app)."""
    pid = os.getpid()
    wait = f'for i in $(seq 1 60); do kill -0 {pid} 2>/dev/null || break; sleep 0.5; done; '
    if config.system() == "macos":
        env = " ".join(f'--env {k}="{os.environ[k]}"' for k in _passthrough_env())
        run = f'open {env} "{target}"'
    else:
        env = " ".join(f'{k}="{os.environ[k]}"' for k in _passthrough_env())
        run = f'{env} "{_exe_in(target)}" >/dev/null 2>&1 &'
    subprocess.Popen(["/bin/sh", "-c", wait + run], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _windows_swap_after_exit(staged: Path, target: Path, previous: Path, relaunch: bool) -> None:
    script = config.ROOT / "updates" / "swap.ps1"
    env_lines = "".join(f"$env:{k} = '{os.environ[k]}'\n" for k in _passthrough_env())
    start = f"Start-Process -FilePath '{_exe_in(target)}' -WorkingDirectory '{target}'\n" if relaunch else ""
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f"$p = Get-Process -Id {os.getpid()} -ErrorAction SilentlyContinue\n"
        "if ($p) { $p.WaitForExit() }\n"
        "Start-Sleep -Milliseconds 500\n"
        f"if (Test-Path '{target}') {{ Move-Item -LiteralPath '{target}' -Destination '{previous}' -Force }}\n"
        f"Move-Item -LiteralPath '{staged}' -Destination '{target}' -Force\n"
        f"{env_lines}{start}",
        encoding="utf-8")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                      "-ExecutionPolicy", "Bypass", "-File", str(script)], creationflags=flags, close_fds=True)


def _quit_soon() -> None:
    def go():
        time.sleep(1.0)  # let /api/version report "restarting" once
        try:
            if on_quit:
                on_quit()
        finally:
            threading.Timer(4.0, os._exit, [0]).start()
    threading.Thread(target=go, daemon=True).start()


# --- the two modes -------------------------------------------------------------------

def _urls() -> tuple[str, dict]:
    with _lock:
        return _state["latest"], dict(_state["assets"])


def install() -> dict:
    """The gold line was clicked. Stage if needed, then swap and relaunch. Returns the state."""
    s = state()
    if not s["can_install"]:
        raise RuntimeError("this build cannot update itself")
    inst = s["install"]
    if inst and inst["phase"] in ("downloading", "verifying", "installing", "restarting"):
        return s
    tag, assets = _urls()
    target = bundle_path()

    def run():
        try:
            bundle = _staged if (_staged and _staged.exists() and inst and inst["phase"] == "ready") \
                else stage(assets[asset_name(tag)], assets[SUMS], assets[SIG], tag)
            apply(bundle, target, relaunch=True)
        except Exception:  # noqa: BLE001  state already says error
            pass
    _progress("installing" if (inst and inst["phase"] == "ready") else "downloading", 0)
    threading.Thread(target=run, name="update-install", daemon=True).start()
    return state()


def stage_in_background() -> None:
    """update_mode auto: fetch and verify the new release now, swap it in at quit."""
    if not can_install():
        return
    inst = state()["install"]
    if inst and inst["phase"] in ("downloading", "verifying", "installing", "ready", "restarting"):
        return
    tag, assets = _urls()

    def run():
        try:
            stage(assets[asset_name(tag)], assets[SUMS], assets[SIG], tag)
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=run, name="update-stage", daemon=True).start()


def apply_if_ready() -> bool:
    """Called when the app quits: install a staged release without relaunching."""
    target = bundle_path()
    if _staged and _staged.exists() and target is not None:
        try:
            apply(_staged, target, relaunch=False)
            return True
        except Exception:  # noqa: BLE001
            return False
    return False


def clean_previous() -> None:
    """Remove what the last update left behind. Called at start."""
    for name in ("previous", "previous.app", "staged", "swap.ps1"):
        p = config.ROOT / "updates" / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()



def set_mode(mode: str) -> str:
    """Switch between click and auto at runtime and remember it in config.json.
    Going to auto with a newer release already known stages it right away."""
    global _mode
    _mode = "auto" if str(mode).lower() == "auto" else "click"
    config.save_keys(update_mode=_mode)
    if _mode == "auto":
        with _lock:
            newer = _state["newer"]
        if newer:
            stage_in_background()
    return _mode

def start(cfg: dict) -> None:
    """Begin the daily check in the background. No-op when config.json says update_check: false."""
    global _mode
    _mode = "auto" if str(cfg.get("update_mode", "click")).lower() == "auto" else "click"
    if not cfg.get("update_check", True):
        return
    clean_previous()

    def loop():
        time.sleep(3 if "HEURE_BLEUE_RELEASE_API" in os.environ else 20)  # let the wall come up first
        while True:
            try:
                check_once()
                if _mode == "auto":
                    stage_in_background()
            except Exception:  # noqa: BLE001  offline, rate-limited, GitHub down: try again tomorrow
                pass
            time.sleep(EVERY)

    threading.Thread(target=loop, name="update-check", daemon=True).start()
