"""Install / remove a login-time service that runs `heurebleue start`.

  macOS   -> ~/Library/LaunchAgents/com.heurebleue.wall.plist   (launchd)
  Windows -> Task Scheduler task "HeureBleue" at logon           (schtasks)
  Linux   -> ~/.config/systemd/user/heure-bleue.service           (systemd --user)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import config

LABEL = "com.heurebleue.wall"


def _python() -> str:
    return sys.executable


def install() -> str:
    s = config.system()
    if s == "macos":
        return _launchd_install()
    if s == "windows":
        return _schtasks_install()
    if s == "linux":
        return _systemd_install()
    return "no service installer for this platform; run `heurebleue start` yourself"


def remove() -> str:
    s = config.system()
    if s == "macos":
        return _launchd_remove()
    if s == "windows":
        return _run(["schtasks", "/Delete", "/TN", "HeureBleue", "/F"])
    if s == "linux":
        _run(["systemctl", "--user", "disable", "--now", "heure-bleue.service"])
        (Path.home() / ".config/systemd/user/heure-bleue.service").unlink(missing_ok=True)
        return "removed heure-bleue.service"
    return "nothing to remove"


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return (r.stdout or r.stderr).strip() or " ".join(cmd)


# --- macOS ---------------------------------------------------------------------

def _plist_path() -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"


def _launchd_install() -> str:
    logs = config.ROOT / "logs"
    logs.mkdir(exist_ok=True)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array>
    <string>{_python()}</string><string>-m</string><string>heurebleue</string><string>start</string>
  </array>
  <key>WorkingDirectory</key><string>{config.ROOT}</string>
  <key>EnvironmentVariables</key><dict><key>HEURE_BLEUE_HOME</key><string>{config.ROOT}</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{logs}/wall.log</string>
  <key>StandardErrorPath</key><string>{logs}/wall.log</string>
</dict></plist>
"""
    p = _plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(plist)
    _run(["launchctl", "unload", str(p)])
    out = _run(["launchctl", "load", str(p)])
    return f"installed {p}\n{out}".strip()


def _launchd_remove() -> str:
    p = _plist_path()
    out = _run(["launchctl", "unload", str(p)]) if p.exists() else ""
    p.unlink(missing_ok=True)
    return f"removed {p}\n{out}".strip()


# --- Windows -------------------------------------------------------------------

def _schtasks_install() -> str:
    pyw = Path(_python()).with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else _python())
    cmd = f'"{exe}" -m heurebleue start'
    return _run(["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", "HeureBleue", "/TR", cmd, "/RL", "LIMITED"]) + \
        f"\nrun now with: schtasks /Run /TN HeureBleue  (working dir: set HEURE_BLEUE_HOME={config.ROOT} in your user env)"


# --- Linux ---------------------------------------------------------------------

def _systemd_install() -> str:
    unit = f"""[Unit]
Description=heure bleue gallery wall
After=graphical-session.target

[Service]
ExecStart={_python()} -m heurebleue start
WorkingDirectory={config.ROOT}
Environment=HEURE_BLEUE_HOME={config.ROOT}
Restart=on-failure

[Install]
WantedBy=default.target
"""
    p = Path.home() / ".config/systemd/user/heure-bleue.service"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(unit)
    _run(["systemctl", "--user", "daemon-reload"])
    return f"installed {p}\n" + _run(["systemctl", "--user", "enable", "--now", "heure-bleue.service"])
