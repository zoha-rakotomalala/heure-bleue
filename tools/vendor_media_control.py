"""Copy media-control into vendor/media-control so the packaged Mac app ships it.

media-control (github.com/ungive/media-control, BSD-3-Clause) reads the macOS
Now Playing feed that Apple closed to third parties in 15.4. It is a Perl script
plus a small native framework; Homebrew builds it for the machine's own chip.
The app runs the copy with the system Perl (/usr/bin/perl), so the user needs
neither Homebrew nor Perl of their own.

Usage:  python tools/vendor_media_control.py [--install]
  --install  run `brew install media-control` first (the release workflow does)

The copy is made by Python, not by `cp -R`, so the framework's symlinks are
resolved into plain files: PyInstaller's datas and a .dmg both prefer that.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "vendor" / "media-control"
PARTS = ("bin", "lib", "Frameworks")

NOTICE = """media-control {version}
https://github.com/ungive/media-control

Copyright (c) 2025 Jonas van den Berg
Licensed under the BSD 3-Clause License.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Bundled unmodified with heure bleue, built from the Homebrew formula on {arch}.
"""


def brew_prefix() -> Path:
    out = subprocess.run(["brew", "--prefix", "media-control"], capture_output=True, text=True, check=True).stdout.strip()
    return Path(out).resolve()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--install", action="store_true", help="brew install media-control first")
    args = ap.parse_args()
    if platform.system() != "Darwin":
        print("media-control is macOS only; nothing to vendor here")
        return 0
    if args.install:
        subprocess.run(["brew", "install", "media-control"], check=True)
    src = brew_prefix()
    version = src.name  # .../Cellar/media-control/<version>
    if DEST.exists():
        shutil.rmtree(DEST)
    for part in PARTS:
        shutil.copytree(src / part, DEST / part, symlinks=False)
    (DEST / "NOTICE").write_text(NOTICE.format(version=version, arch=platform.machine()), encoding="utf-8")
    # prove the copy works on its own: the system perl, a bare PATH, the vendored framework
    r = subprocess.run(["/usr/bin/perl", str(DEST / "bin" / "media-control"), "version"],
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=20)
    if r.returncode != 0 or version not in r.stdout:
        print("vendored copy does not run:", r.stdout, r.stderr, file=sys.stderr)
        return 1
    files = sum(1 for p in DEST.rglob("*") if p.is_file())
    print(f"vendored media-control {version} ({platform.machine()}): {files} files in {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
