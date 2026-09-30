"""Build the static web demo (what GitHub Pages serves).

  python -m heurebleue demo [--out site]

Copies the three pages and the shipped index into one folder and injects
web/demo.js, which answers the /api/* routes from localStorage. No music match:
there is no player loop in a browser. The wall rotates on its own.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import config

SHIM_TAG = '<script src="demo.js"></script>\n'


def build(out: Path) -> Path:
    out = out.resolve()
    if out == config.ROOT or config.ROOT in out.parents and out.name in ("web", "data", "heurebleue"):
        raise SystemExit(f"refusing to build into {out}")
    shutil.rmtree(out, ignore_errors=True)
    (out / "data").mkdir(parents=True)

    for name in ("index.html", "favorites.html", "stats.html"):
        html = (config.WEB / name).read_text(encoding="utf-8")
        i = html.index("<script>")  # the shim must run before the page's own script
        (out / name).write_text(html[:i] + SHIM_TAG + html[i:], encoding="utf-8")

    shutil.copy2(config.WEB / "demo.js", out / "demo.js")
    shutil.copy2(config.PAINTINGS, out / "data" / "paintings.json")
    (out / ".nojekyll").write_text("", encoding="utf-8")  # Pages must not run Jekyll over the folder
    return out


def main(out: str = "site") -> int:
    p = build(Path(out))
    n = sum(1 for _ in p.rglob("*") if _.is_file())
    size = sum(_.stat().st_size for _ in p.rglob("*") if _.is_file()) // 1024
    print(f"demo built in {p}  ({n} files, {size} KB)")
    print(f"preview:  python3 -m http.server 8766 --bind 127.0.0.1 --directory {p}")
    return 0
