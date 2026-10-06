"""The share card: one PNG of what the wall is doing right now.

Black, gold and cream, the way Palette (Zoha's museum app) frames things: the
painting on a dark wall with a hairline gold frame, a museum label under it, the
song that chose it, and along the bottom a strip of the day's other paintings as
small 1:1.3 tiles, Palette's grid idiom. 1080x1350 (4:5), ready for a phone.

    card.render(now, history_today, index_by_id) -> PIL.Image
    card.save(image) -> Path   (Desktop, or the user folder when there is none)
"""
from __future__ import annotations

import io
import os
import platform
import time
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from . import config

W, H = 1080, 1350
BLACK, GOLD, CREAM, MUTED = (26, 26, 26), (212, 175, 55), (245, 245, 220), (150, 146, 130)
UA = {"User-Agent": "heure-bleue/1.0 (https://github.com/zoha-rakotomalala/heure-bleue; personal desk display)"}

_FONTS = {
    "serif_i": ["/System/Library/Fonts/Supplemental/Georgia Italic.ttf", "C:/Windows/Fonts/georgiai.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"],
    "serif": ["/System/Library/Fonts/Supplemental/Georgia.ttf", "C:/Windows/Fonts/georgia.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    "sans": ["/System/Library/Fonts/Helvetica.ttc", "C:/Windows/Fonts/arial.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for p in _FONTS[kind]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default(size)  # Pillow 10.1+: a scalable fallback


def fetch(url: str, timeout: float = 20) -> Optional[Image.Image]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGB")
    except Exception:  # noqa: BLE001  a missing tile is a dark square, not a failed card
        return None


def fit(im: Image.Image, w: int, h: int) -> Image.Image:
    r = min(w / im.width, h / im.height)
    return im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)


def cover_crop(im: Image.Image, w: int, h: int) -> Image.Image:
    r = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def ellipsize(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> str:
    if d.textlength(text, font=f) <= max_w:
        return text
    while text and d.textlength(text + "…", font=f) > max_w:
        text = text[:-1].rstrip()
    return text + "…"


def small_caps(d: ImageDraw.ImageDraw, xy, text: str, f: ImageFont.FreeTypeFont, fill, spacing: float = 3.0, anchor_right: Optional[int] = None):
    """Tracked uppercase, Palette's label style. Draws letter by letter for the tracking."""
    text = text.upper()
    width = sum(d.textlength(c, font=f) + spacing for c in text) - spacing
    x, y = xy
    if anchor_right is not None:
        x = anchor_right - width
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + spacing
    return width


def render(now: dict, today: list[dict], index: dict[str, dict], lang_date: str) -> Image.Image:
    painting, track, palette = now.get("painting") or {}, now.get("track") or {}, now.get("cover_palette") or []
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    d.rectangle((28, 28, W - 29, H - 29), outline=GOLD, width=1)  # the hairline frame

    # header: wordmark and date
    d.text((72, 64), "heure bleue", font=font("serif_i", 44), fill=GOLD)
    small_caps(d, (0, 80), lang_date, font("sans", 18), MUTED, 3.0, anchor_right=W - 72)

    # the painting, on the wall
    top, bottom_of_art = 150, 150 + 700
    art = fetch(painting["image"]) if painting.get("image") else None
    if art:
        art = fit(art, W - 2 * 96, bottom_of_art - top)
        x, y = (W - art.width) // 2, top + (bottom_of_art - top - art.height) // 2
        shadow = Image.new("RGBA", (art.width + 80, art.height + 80), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rectangle((40, 48, art.width + 40, art.height + 56), fill=(0, 0, 0, 140))
        from PIL import ImageFilter
        shadow = shadow.filter(ImageFilter.GaussianBlur(22))
        img.paste(shadow, (x - 40, y - 40), shadow)
        img.paste(art, (x, y))
        d.rectangle((x - 1, y - 1, x + art.width, y + art.height), outline=GOLD, width=1)
    else:
        d.text((W // 2, (top + bottom_of_art) // 2), "·", font=font("serif", 60), fill=MUTED, anchor="mm")

    # the label
    y = bottom_of_art + 48
    d.line((72, y, 72 + 120, y), fill=GOLD, width=1)
    y += 22
    title_f = font("serif_i", 40)
    d.text((72, y), ellipsize(d, painting.get("title") or "", title_f, W - 144), font=title_f, fill=CREAM)
    y += 56
    line2 = " · ".join(s for s in (painting.get("artist"), painting.get("date")) if s)
    d.text((72, y), ellipsize(d, line2, font("sans", 24), W - 144), font=font("sans", 24), fill=MUTED)
    y += 40
    small_caps(d, (72, y), painting.get("museum") or "", font("sans", 15), GOLD, 3.2)

    # the song that chose it (right column of the label)
    if track.get("title"):
        cx, cy = W - 72, bottom_of_art + 70
        cover = fetch(track["cover_url"]) if track.get("cover_url") else None
        if not cover and now.get("cover_file") and Path(now["cover_file"]).exists():
            cover = Image.open(now["cover_file"]).convert("RGB")
        box = 112
        if cover:
            cover = cover_crop(cover, box, box)
            img.paste(cover, (cx - box, cy))
            d.rectangle((cx - box - 1, cy - 1, cx, cy + box), outline=(60, 60, 60), width=1)
        tx = cx - box - 24
        f1, f2 = font("sans", 22), font("sans", 18)
        t1 = ellipsize(d, track["title"], f1, 360)
        t2 = ellipsize(d, " · ".join(s for s in (track.get("artist"), track.get("album")) if s), f2, 360)
        d.text((tx, cy + 10), t1, font=f1, fill=CREAM, anchor="ra")
        d.text((tx, cy + 44), t2, font=f2, fill=MUTED, anchor="ra")
        # the five colours of the cover, the reason this painting is here
        px = tx
        for c in reversed(palette[:5]):
            rgb = tuple(int(c["hex"][i:i + 2], 16) for i in (1, 3, 5))
            d.ellipse((px - 18, cy + 82, px, cy + 100), fill=rgb, outline=(70, 70, 70))
            px -= 26
        small_caps(d, (0, cy + 86), "matched to the cover", font("sans", 11), MUTED, 2.0, anchor_right=px - 10)

    # today's paintings, Palette's tiles: 1:1.3, dark overlay, tiny label
    strip_top = H - 236
    d.line((72, strip_top - 30, W - 72, strip_top - 30), fill=(50, 50, 50), width=1)
    small_caps(d, (72, strip_top - 20), "today on the wall", font("sans", 12), MUTED, 2.6)
    tiles = [p for p in today if p.get("id") != painting.get("id")][-8:]
    n = max(1, len(tiles))
    gap, tw = 14, 0
    tw = (W - 144 - gap * 7) // 8
    th = round(tw * 1.3)
    ty = strip_top + 2
    for i, p in enumerate(tiles):
        tx = 72 + i * (tw + gap)
        full = index.get(p.get("id"), {})
        im = fetch(full.get("image")) if full.get("image") else None
        if im:
            img.paste(cover_crop(im, tw, th), (tx, ty))
        else:
            d.rectangle((tx, ty, tx + tw, ty + th), fill=(34, 34, 34))
        ov = Image.new("RGBA", (tw, 34), (0, 0, 0, 180))
        img.paste(ov, (tx, ty + th - 34), ov)
        f = font("sans", 11)
        d.text((tx + 6, ty + th - 30), ellipsize(d, full.get("title") or p.get("title") or "", f, tw - 12), font=f, fill=CREAM)
        d.text((tx + 6, ty + th - 16), ellipsize(d, full.get("artist") or p.get("artist") or "", f, tw - 12), font=f, fill=(170, 170, 170))
        d.rectangle((tx, ty, tx + tw - 1, ty + th - 1), outline=(60, 60, 60), width=1)
    for i in range(len(tiles), 8):  # empty slots stay as faint outlines, like an unfinished palette
        tx = 72 + i * (tw + gap)
        d.rectangle((tx, ty, tx + tw - 1, ty + th - 1), outline=(48, 48, 48), width=1)

    # footer
    small_caps(d, (72, H - 58), "zoha-rakotomalala.github.io/heure-bleue", font("sans", 12), MUTED, 2.4)
    small_caps(d, (0, H - 58), f"{len(today)} paintings today", font("sans", 12), GOLD, 2.4, anchor_right=W - 72)
    return img


def desktop() -> Path:
    s = platform.system()
    if s == "Darwin":
        return Path.home() / "Desktop"
    if s == "Windows":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    xdg = Path.home() / ".config" / "user-dirs.dirs"
    if xdg.exists():
        for line in xdg.read_text(encoding="utf-8").splitlines():
            if line.startswith("XDG_DESKTOP_DIR="):
                return Path(os.path.expandvars(line.split("=", 1)[1].strip('"')))
    return Path.home() / "Desktop"


def save(img: Image.Image) -> Path:
    folder = desktop()
    if not folder.exists():
        folder = config.DATA.parent / "cards"
        folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("heure bleue %Y-%m-%d %H.%M.png")
    img.save(path, "PNG", optimize=True)
    return path


def reveal(path: Path) -> None:
    """Show the file in the system's file manager; best effort."""
    import subprocess
    s = platform.system()
    try:
        if s == "Darwin":
            subprocess.Popen(["open", "-R", str(path)])
        elif s == "Windows":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass
