"""Run several indexer phases in sequence, detached from the calling shell.

Usage: python3 tools/run_phases.py SLUG:TARGET [SLUG:TARGET ...]
Each phase runs `python -m heurebleue index --source SLUG --target TARGET`
and logs to logs/index-SLUG.log. Targets are absolute index sizes, so list
them in increasing order. The wall service is restarted at the end (macOS).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"


def run_phase(slug: str, target: str, flags: list[str]) -> int:
    log = LOGS / f"index-{slug}.log"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n=== phase {slug} -> {target} {' '.join(flags)} at {time.strftime('%H:%M:%S')}\n")
        fh.flush()
        proc = subprocess.run(
            [sys.executable, "-m", "heurebleue", "index", "--source", slug, "--target", target, *flags],
            cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
        )
        fh.write(f"=== phase {slug} exit {proc.returncode}\n")
    return proc.returncode


def main() -> int:
    flags = [a for a in sys.argv[1:] if a.startswith("--")]  # passed to every phase, e.g. --allow-cc
    phases = [a.split(":", 1) for a in sys.argv[1:] if not a.startswith("--")]
    if not phases:
        print(__doc__)
        return 2
    if os.environ.get("RUN_PHASES_CHILD") != "1":
        env = dict(os.environ, RUN_PHASES_CHILD="1")
        child = subprocess.Popen(
            [sys.executable, __file__, *sys.argv[1:]], cwd=ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        (LOGS / "run_phases.pid").write_text(str(child.pid), encoding="utf-8")
        print(f"detached pid {child.pid}; phases: {' '.join(sys.argv[1:])}")
        return 0
    LOGS.mkdir(exist_ok=True)
    summary = LOGS / "run_phases.log"
    for slug, target in phases:
        code = run_phase(slug, target, flags)
        with summary.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {slug} -> {target} exit {code}\n")
    if sys.platform == "darwin":
        uid = os.getuid()
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/com.heurebleue.wall"], check=False)
    with summary.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} all phases done\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
