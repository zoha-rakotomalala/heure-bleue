"""Your year on the wall: numbers and a card, from favorites.json and history.jsonl.

    summary(year, favs, history) -> dict      what the Stats page shows and the card draws
    render(summary, index, labels) -> Image   1080x1350, the share card's idiom (see card.py)

The wall never phones home, so this is the only "Wrapped" there is: computed on the
user's machine, from the two files they own, drawn into one PNG for the Desktop.
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from typing import Optional

from PIL import Image, ImageDraw

from .card import BLACK, CREAM, GOLD, H, MUTED, W, cover_crop, ellipsize, fetch, font, small_caps

LABELS = {  # English defaults; the page sends its own language
    "title": "your year on the wall", "shown": "paintings shown", "hours": "hours on the wall", "kept": "kept",
    "most_kept": "most kept", "museum": "your museum", "song": "the music behind the hearts", "painter": "the painter you lived with",
    "quiet": "quiet months", "none_quiet": "a painting kept every month", "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "first": "first kept", "hour": "your hour", "in_months": "paintings kept in {n} of 12 months",
}


UNNAMED = {"unknown artist", "anonymous", "anoniem", "anonyme", "unknown"}


def named(a: Optional[str]) -> bool:
    return bool(a) and a.strip().lower() not in UNNAMED


def _year_of(s: Optional[str]) -> Optional[int]:
    try:
        return int((s or "")[:4])
    except ValueError:
        return None


def tiles(kept: list[dict], first_of_month: list) -> list:
    """Twelve tiles: the first painting kept in each month (with its month), then, where months are
    empty, the other kept paintings newest first, so a year that began in September still fills the grid."""
    out = []
    used = {f["id"] for f in first_of_month if f}
    others = [f for f in sorted(kept, key=lambda f: f.get("saved_at") or "", reverse=True) if f["id"] not in used]
    for i, f in enumerate(first_of_month):
        if f is None and others:
            f, month = others.pop(0), None
        else:
            month = i if f else None
        out.append({"id": f["id"], "title": f.get("title"), "artist": f.get("artist"), "image": f.get("image"), "month": month} if f else None)
    return out


def summary(year: int, favs: list[dict], history: list[dict]) -> dict:
    kept = [f for f in favs if _year_of(f.get("saved_at")) == year]
    per_month = [0] * 12
    first_of_month: list[Optional[dict]] = [None] * 12
    for f in sorted(kept, key=lambda f: f.get("saved_at") or ""):
        m = int(f["saved_at"][5:7]) - 1
        per_month[m] += 1
        if first_of_month[m] is None:
            first_of_month[m] = f
    artists = Counter(f["artist"] for f in kept if named(f.get("artist")))
    museums = Counter(f["museum"] for f in kept if f.get("museum"))
    songs = Counter((f.get("track") or {}).get("artist") for f in kept if (f.get("track") or {}).get("artist"))

    start = time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1)); end = time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1))
    rows = [r for r in history if start <= r.get("ts", 0) < end and r.get("id")]
    dwell = defaultdict(float); shown = Counter(); by_hour = Counter(); by_month = Counter()
    painter_dwell = defaultdict(float); music_dwell = defaultdict(float); music_rows = 0; total_dwell = 0.0
    for r in rows:
        d = float(r.get("dwell_s") or 0)
        total_dwell += d; dwell[r["id"]] += d; shown[r["id"]] += 1
        lt = time.localtime(r["ts"]); by_hour[lt.tm_hour] += 1; by_month[lt.tm_mon - 1] += 1
        if named(r.get("artist")):
            painter_dwell[r["artist"]] += d
        if r.get("mode") == "music":
            music_rows += 1
            if r.get("track_artist"):
                music_dwell[r["track_artist"]] += d
    most_shown = shown.most_common(1)
    top_painter = max(painter_dwell.items(), key=lambda kv: kv[1], default=(None, 0))
    top_music = max(music_dwell.items(), key=lambda kv: kv[1], default=(None, 0))
    return {
        "year": year, "kept": len(kept), "per_month": per_month, "quiet_months": [i for i, n in enumerate(per_month) if n == 0],
        "tiles": tiles(kept, first_of_month),
        "top_artist": artists.most_common(1)[0] if artists else None, "top_museum": museums.most_common(1)[0] if museums else None,
        "top_song_artist": songs.most_common(1)[0] if songs else None,
        "shown": len(rows), "works": len(shown), "hours": round(total_dwell / 3600, 1), "music_share": round(music_rows / len(rows), 2) if rows else 0,
        "most_shown": {"id": most_shown[0][0], "n": most_shown[0][1]} if most_shown else None,
        "top_painter": {"name": top_painter[0], "hours": round(top_painter[1] / 3600, 1)} if top_painter[0] else None,
        "top_music": {"name": top_music[0], "hours": round(top_music[1] / 3600, 1)} if top_music[0] else None,
        "busiest_hour": by_hour.most_common(1)[0][0] if by_hour else None, "busiest_month": by_month.most_common(1)[0][0] if by_month else None,
        "first_kept": kept[0].get("saved_at")[:10] if kept else None,
    }


def render(s: dict, index: dict[str, dict], labels: Optional[dict] = None) -> Image.Image:
    L = {**LABELS, **(labels or {})}
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    d.rectangle((28, 28, W - 29, H - 29), outline=GOLD, width=1)

    d.text((72, 64), "heure bleue", font=font("serif_i", 44), fill=GOLD)
    small_caps(d, (0, 80), L["title"], font("sans", 16), MUTED, 3.0, anchor_right=W - 72)
    d.text((W - 72, 150), str(s["year"]), font=font("serif", 150), fill=CREAM, anchor="ra")
    d.line((72, 318, W - 72, 318), fill=(50, 50, 50), width=1)

    # three numbers
    y = 346
    cols = [(s["shown"], L["shown"]), (s["hours"], L["hours"]), (s["kept"], L["kept"])]
    for i, (n, lab) in enumerate(cols):
        x = 72 + i * ((W - 144) // 3)
        txt = f"{n:g}" if isinstance(n, float) else str(n)
        d.text((x, y), txt, font=font("serif", 72), fill=GOLD if i == 2 else CREAM)
        small_caps(d, (x + 2, y + 92), lab, font("sans", 13), MUTED, 2.6)

    # twelve months, Palette's tiles; one kept painting per month, the month's first
    gap, cols_n = 14, 6
    tw = (W - 144 - gap * (cols_n - 1)) // cols_n
    th = round(tw * 1.3)
    gy = 500
    for i, t in enumerate(s["tiles"]):
        r, c = divmod(i, cols_n)
        tx, ty = 72 + c * (tw + gap), gy + r * (th + gap)
        im = fetch(t["image"]) if t and t.get("image") else None
        if im:
            img.paste(cover_crop(im, tw, th), (tx, ty))
            ov = Image.new("RGBA", (tw, 34), (0, 0, 0, 180))
            img.paste(ov, (tx, ty + th - 34), ov)
            f = font("sans", 11)
            d.text((tx + 6, ty + th - 30), ellipsize(d, t.get("title") or "", f, tw - 12), font=f, fill=CREAM)
            d.text((tx + 6, ty + th - 16), ellipsize(d, t.get("artist") or "", f, tw - 12), font=f, fill=(170, 170, 170))
            d.rectangle((tx, ty, tx + tw - 1, ty + th - 1), outline=(60, 60, 60), width=1)
            if t.get("month") is not None:
                name = L["months"][t["month"]]
                bw = int(sum(d.textlength(c, font=font("sans", 10)) + 1.6 for c in name.upper())) + 12
                badge = Image.new("RGBA", (bw, 22), (20, 20, 20, 170)); img.paste(badge, (tx + 6, ty + 6), badge)
                small_caps(d, (tx + 12, ty + 11), name, font("sans", 10), GOLD, 1.6)
        else:
            d.rectangle((tx, ty, tx + tw - 1, ty + th - 1), outline=(48, 48, 48), width=1)
            d.text((tx + tw // 2, ty + th // 2), L["months"][i], font=font("serif_i", 24), fill=(75, 75, 75), anchor="mm")
    y = gy + 2 * (th + gap) + 30
    d.line((72, y, 72 + 120, y), fill=GOLD, width=1)
    y += 24

    # four facts, two columns
    def fact(x, yy, label, value):
        small_caps(d, (x, yy), label, font("sans", 12), MUTED, 2.6)
        f = font("serif_i", 28)
        d.text((x, yy + 20), ellipsize(d, value or "—", f, (W - 144) // 2 - 16), font=f, fill=CREAM)

    ta, tm, ts_, tp = s.get("top_artist"), s.get("top_museum"), s.get("top_song_artist"), s.get("top_painter")
    half = (W - 144) // 2
    fact(72, y, L["most_kept"], f"{ta[0]} · {ta[1]}" if ta else None)
    fact(72 + half, y, L["museum"], tm[0] if tm else None)
    fact(72, y + 100, L["song"], ts_[0] if ts_ else ((s.get("top_music") or {}).get("name")))
    fact(72 + half, y + 100, L["painter"], f"{tp['name']} · {tp['hours']:g} h" if tp else None)

    # footer
    small_caps(d, (72, H - 58), "zoha-rakotomalala.github.io/heure-bleue", font("sans", 12), MUTED, 2.4)
    q = s.get("quiet_months") or []
    if not q:
        right = L["none_quiet"]
    elif len(q) <= 4:
        right = f"{L['quiet']}: " + " · ".join(L["months"][i] for i in q)
    else:
        right = L["in_months"].replace("{n}", str(12 - len(q)))
    small_caps(d, (0, H - 58), right, font("sans", 12), GOLD, 2.4, anchor_right=W - 72)
    return img
