"""Draw the app icon: a dark green-teal square (the forest theme), a thin horizon
line, and a gold sun just below it. First light.

  python3 tools/make_icon.py        writes assets/icon.png, icon.ico and, on macOS, icon.icns
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "assets"
BG, SKY, GOLD = (14, 31, 28), (31, 63, 58), (201, 169, 107)


def draw(size: int = 1024) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(s * 0.22)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=r, fill=BG)

    # a soft glow above the horizon
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((s * 0.18, s * 0.30, s * 0.82, s * 0.94), fill=(*SKY, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(s * 0.09))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=r, fill=255)
    img.paste(Image.alpha_composite(img, glow), (0, 0), mask)
    d = ImageDraw.Draw(img)

    # the sun: a gold disc, its lower third hidden by the horizon
    cx, cy, rad = s * 0.5, s * 0.60, s * 0.17
    d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=GOLD)
    d.rectangle((0, cy + rad * 0.35, s, s), fill=BG)
    # the horizon line
    d.rectangle((s * 0.17, cy + rad * 0.35 - s * 0.008, s * 0.83, cy + rad * 0.35 + s * 0.008), fill=GOLD)
    return img


def main() -> int:
    OUT.mkdir(exist_ok=True)
    img = draw()
    img.save(OUT / "icon.png")
    img.save(OUT / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if sys.platform == "darwin" and shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as tmp:
            iconset = Path(tmp) / "icon.iconset"
            iconset.mkdir()
            for n in (16, 32, 128, 256, 512):
                img.resize((n, n), Image.LANCZOS).save(iconset / f"icon_{n}x{n}.png")
                img.resize((n * 2, n * 2), Image.LANCZOS).save(iconset / f"icon_{n}x{n}@2x.png")
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT / "icon.icns")], check=True)
    print("wrote", ", ".join(p.name for p in sorted(OUT.iterdir())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
