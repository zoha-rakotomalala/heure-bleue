"""Assemble the frames from tools/record_demo.js into a demo GIF (and mp4).

    python3 tools/assemble_demo.py <frames dir> <out.gif> [--width 420] [--fps 6]
                                   [--mp4 <out.mp4> --ffmpeg <ffmpeg binary>]

GIF needs only Pillow. mp4 needs an ffmpeg binary; pass its path with --ffmpeg
(Playwright's cached one works: it has libvpx, so the mp4 falls back to webm).
Duplicate consecutive frames are dropped so a still wall does not bloat the file.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=420)
    ap.add_argument("--fps", type=float, default=6)
    ap.add_argument("--step", type=int, default=1, help="keep every Nth frame")
    ap.add_argument("--mp4", default=None)
    ap.add_argument("--ffmpeg", default=None)
    a = ap.parse_args()

    files = sorted(Path(a.frames).glob("f*.png"))[:: max(1, a.step)]
    if not files:
        print("no frames", file=sys.stderr)
        return 1

    frames: list[Image.Image] = []
    last = None
    dropped = 0
    for f in files:
        im = Image.open(f).convert("RGB")
        h = round(im.height * a.width / im.width)
        im = im.resize((a.width, h), Image.LANCZOS)
        sig = hashlib.md5(im.tobytes()).hexdigest()
        if sig == last:
            dropped += 1
            continue
        last = sig
        frames.append(im)

    # One shared adaptive palette keeps colours stable between frames.
    sheet = Image.new("RGB", (frames[0].width, frames[0].height * min(len(frames), 12)))
    step = max(1, len(frames) // 12)
    for i, im in enumerate(frames[::step][:12]):
        sheet.paste(im, (0, i * im.height))
    palette = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    quant = [im.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG) for im in frames]

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    quant[0].save(
        out,
        save_all=True,
        append_images=quant[1:],
        duration=int(1000 / a.fps),
        loop=0,
        optimize=True,
    )
    print(f"GIF {out} {out.stat().st_size // 1024} KB, {len(frames)} frames ({dropped} duplicates dropped)")

    if a.mp4 and a.ffmpeg:
        tmp = out.parent / "_seq"
        tmp.mkdir(exist_ok=True)
        for i, im in enumerate(frames):
            im.save(tmp / f"s{i:04d}.png")
        target = Path(a.mp4)
        cmd = [a.ffmpeg, "-y", "-framerate", str(a.fps), "-i", str(tmp / "s%04d.png"),
               "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
        if target.suffix == ".webm":
            cmd += ["-c:v", "libvpx", "-b:v", "1M"]
        else:
            cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        cmd.append(str(target))
        r = subprocess.run(cmd, capture_output=True, text=True)
        for p in tmp.glob("s*.png"):
            p.unlink()
        tmp.rmdir()
        if r.returncode:
            print("video failed:", r.stderr.strip().splitlines()[-1], file=sys.stderr)
        else:
            print(f"VIDEO {target} {target.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
