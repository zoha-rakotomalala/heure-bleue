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


def palette_feel(pal: list[dict]) -> dict:
    """What a palette feels like, three numbers the matcher can compare with a target:
    light 0..1 (dark to pale), chroma 0..1 (grey to vivid), warm -1..1 (blue to orange)."""
    if not pal:
        return {"light": 0.5, "chroma": 0.4, "warm": 0.0}
    total = sum(c.get("w", 1) for c in pal) or 1
    light = chroma = warm = 0.0
    for c in pal:
        w = c.get("w", 1) / total
        L, a, b = rgb_to_lab(hex_to_rgb(c["hex"]))
        C = math.hypot(a, b)
        light += w * L / 100
        chroma += w * min(1.0, C / 60)
        warm += w * ((0.5 * a + b) / (C + 1e-6)) * min(1.0, C / 25)  # grey has no temperature
    return {"light": round(light, 3), "chroma": round(chroma, 3), "warm": round(max(-1.0, min(1.0, warm)), 3)}


def color_name(hex_: str) -> str:
    """A plain name key for a colour (col_red, col_blue, ...), for the 'why this painting' line."""
    L, a, b = rgb_to_lab(hex_to_rgb(hex_))
    C = math.hypot(a, b)
    if L < 14:
        return "col_black"
    if L > 90 and C < 10:
        return "col_white"
    if C < 9:
        return "col_grey"
    h = math.degrees(math.atan2(b, a)) % 360  # CIELAB hue: red ~35, orange ~60, yellow ~90, green ~150, blue ~290, violet ~320
    if 45 <= h < 100 and L < 50 and C < 45:
        return "col_brown"
    if 45 <= h < 110 and L > 75 and C < 30:
        return "col_beige"
    if h < 48 or h >= 340:
        return "col_pink" if L > 60 and C < 70 else "col_red"
    if h < 75:
        return "col_orange"
    if h < 112:
        return "col_yellow"
    if h < 180:
        return "col_green"
    if h < 240:
        return "col_teal"
    if h < 305:
        return "col_blue"
    return "col_violet"


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
