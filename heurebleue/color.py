"""Palette extraction and perceptual palette distance (CIELAB)."""
from __future__ import annotations

import io
import math

from PIL import Image


def palette_from_bytes(img_bytes: bytes, colors: int = 5) -> list[dict]:
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return palette_from_image(im, colors)


def palette_from_image(im: Image.Image, colors: int = 5) -> list[dict]:
    q = im.convert("RGB").resize((96, 96)).quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(n for n, _ in counts)
    return [{"hex": "#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]), "w": round(n / total, 3)} for n, i in counts]


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_lab(rgb) -> tuple[float, float, float]:
    r, g, b = [c / 255.0 for c in rgb]

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = lin(r), lin(g), lin(b)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.00000
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def palette_distance(a: list[dict], b: list[dict]) -> float:
    """Weighted, symmetric nearest-color distance between two palettes."""
    la = [(rgb_to_lab(hex_to_rgb(c["hex"])), c["w"]) for c in a]
    lb = [(rgb_to_lab(hex_to_rgb(c["hex"])), c["w"]) for c in b]

    def one_way(src, dst):
        return sum(min(math.dist(l1, l2) for l2, _ in dst) * w1 for l1, w1 in src)

    return one_way(la, lb) + one_way(lb, la)


def has_calibration_strip(im: Image.Image) -> bool:
    """True when the bottom ~3.5% is a vertically uniform grey ramp or block row
    (a photographic colour target left in a museum photo)."""
    g = im.convert("L")
    w, h = g.size
    band = g.crop((0, int(h * 0.965), w, h)).resize((32, 4), Image.Resampling.BOX)
    px = band.load()
    rows = [[px[x, y] for x in range(32)] for y in range(4)]
    vertical = sum(abs(a - b) for a, b in zip(rows[0], rows[3])) / 32
    if vertical > 10:
        return False
    col = [sum(rows[y][x] for y in range(4)) / 4 for x in range(32)]
    steps = [b - a for a, b in zip(col, col[1:])]
    up = sum(1 for s in steps if s >= -2) / len(steps)
    down = sum(1 for s in steps if s <= 2) / len(steps)
    return (max(col) - min(col)) > 80 and max(up, down) > 0.85
