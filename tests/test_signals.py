"""The three signals, the matcher and the year summary, without network or a window.
    python3 tests/test_signals.py
Also: every translation key the SERVER can put in a "why" (mo_*, col_*, why_*) must exist in web/i18n.js."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
HOME = Path(tempfile.mkdtemp(prefix="hb-signals-"))
os.environ["HEURE_BLEUE_HOME"] = str(HOME)
(HOME / "data").mkdir()
(HOME / "data" / "paintings.json").write_text(json.dumps([
    {"id": f"p{i}", "title": f"P{i}", "artist": a, "museum": "M", "date": d, "w": 3, "h": 4, "image": "x",
     "palette": [{"hex": h, "w": 0.6}, {"hex": "#808080", "w": 0.4}]}
    for i, (a, d, h) in enumerate([("Rembrandt", "1640", "#1a120a"), ("Dufy", "1925", "#f2c14e"), ("Monet", "1890", "#9fc5e8"),
                                    ("Vermeer", "1660", "#d9c7a0"), ("Rothko", "1958", "#8b1a1a"), ("Turner", "1840", "#c9c9c9")] * 8)
]), encoding="utf-8")

from heurebleue import color, moment, music, wall, year  # noqa: E402

# palette feel: dark is dark, pale is pale, orange is warm, blue is cool
f = color.palette_feel([{"hex": "#1a120a", "w": 1}]); assert f["light"] < 0.15, f
f = color.palette_feel([{"hex": "#f2f2f2", "w": 1}]); assert f["light"] > 0.9 and f["chroma"] < 0.1, f
assert color.palette_feel([{"hex": "#e07020", "w": 1}])["warm"] > 0.5
assert color.palette_feel([{"hex": "#2050c0", "w": 1}])["warm"] < -0.4
for hx, name in [("#000000", "col_black"), ("#ffffff", "col_white"), ("#808080", "col_grey"), ("#c0392b", "col_red"), ("#e67e22", "col_orange"),
                 ("#f1c40f", "col_yellow"), ("#27ae60", "col_green"), ("#1f8a8a", "col_teal"), ("#2c5fd8", "col_blue"), ("#7d3c98", "col_violet"),
                 ("#6b4423", "col_brown"), ("#f4a6c0", "col_pink"), ("#e8dcc4", "col_beige")]:
    got = color.color_name(hx); assert got == name, (hx, got, name)

# music feel from tags, no network
feel = music.feel_from_tags([{"name": "doom metal", "count": 5}, {"name": "seen live", "count": 3}])
assert feel and feel["feel"]["light"] < 0.35 and feel["top"] == "doom metal", feel
feel = music.feel_from_tags([{"name": "bossa nova", "count": 4}, {"name": "jazz", "count": 2}])
assert feel["feel"]["warm"] > 0.2 and feel["feel"].get("century") == 20, feel
assert music.feel_from_tags([{"name": "swedish", "count": 2}]) is None
assert music.first_artist("Nina Simone feat. Someone, Other") == "Nina Simone"
assert music.first_artist("Simon & Garfunkel") == "Simon"
assert music.feel_for({"artist": "Domingo", "title": "a stream", "album": "", "player": "Chrome"}) is None  # a channel is not a band

# the moment: a rainy night asks for dark and grey; a clear summer noon for pale and vivid
noon = time.mktime((2026, 7, 10, 13, 0, 0, 0, 0, -1)); night = time.mktime((2026, 11, 10, 1, 0, 0, 0, 0, -1))
def at(code, rise, down, lat, when):  # update() stamps the real clock; the tests ask about other days
    moment.update(code, rise, down, lat); moment._STATE["ts"] = when
at(63, noon - 7 * 3600, noon + 7 * 3600, 48.8, noon)
m = moment.current(noon); assert m["sky"] == "rain" and m["phase"] == "day" and m["season"] == "summer" and "mo_rain" in m["reasons"], m
at(0, night + 7 * 3600, night - 8 * 3600, 48.8, night)
m = moment.current(night); assert m["phase"] == "night" and m["feel"]["light"] < 0.35 and m["reasons"] == ["mo_clear", "mo_night"], m
at(None, None, None, -33.9, night)  # Sydney: November is spring
assert moment.current(night)["season"] == "spring"
at(3, noon - 7 * 3600, noon + 7 * 3600, 48.8, noon)
assert "mo_overcast" in moment.current(noon)["reasons"]

# the matcher: a dark cover + music off + moment off picks the dark painting; moment alone still answers; all off = random with a reason-free why
cover = [{"hex": "#14100a", "w": 0.8}, {"hex": "#302010", "w": 0.2}]
hits = {wall.choose_painting(cover, [], 0, False, {"cover": True, "music": False, "moment": False})[0]["artist"] for _ in range(12)}
assert "Rembrandt" in hits and "Dufy" not in hits, hits
p, why = wall.choose_painting(cover, [], 0, False, {"cover": True, "music": False, "moment": False})
assert why and why[0]["k"] == "why_cover" and why[0]["c"] in ("col_black", "col_brown"), why
p, why = wall.choose_painting(None, [], 0, False, {"cover": True, "music": True, "moment": True})
assert p and any(w["k"].startswith("mo_") for w in why), why
p, why = wall.choose_painting(None, [], 0, False, {"cover": False, "music": False, "moment": False})
assert p and why == [], why
mf = music.feel_from_tags([{"name": "black metal", "count": 9}])
p, why = wall.choose_painting(None, [], 0, False, {"cover": False, "music": True, "moment": False}, mf)
assert why == [{"k": "why_music", "t": "black metal"}], why

# every key the server can emit is translated
i18n = (ROOT / "web" / "i18n.js").read_text(encoding="utf-8")
en = re.search(r"\n    en: \{(.*?)\n    \},", i18n, re.S).group(1)
keys = set(re.findall(r"\b([a-z_0-9]+): \"", en))
need = {f"mo_{x}" for x in list(moment.NOTABLE_SKY) + list(moment.NOTABLE_PHASE) + list(moment.SEASON)}
need |= {"col_black", "col_white", "col_grey", "col_brown", "col_beige", "col_pink", "col_red", "col_orange", "col_yellow", "col_green", "col_teal", "col_blue", "col_violet"}
need |= {"why_cover", "why_music", "why_hour", "why_today", "why_taste", "why_lead", "and"}
missing = need - keys; assert not missing, missing

# the year: numbers from two synthetic files
favs = [{"id": "p1", "title": "P1", "artist": "Dufy", "museum": "M", "saved_at": "2026-03-04 10:00", "image": "x", "track": {"artist": "Nina Simone"}},
        {"id": "p2", "title": "P2", "artist": "Dufy", "museum": "M", "saved_at": "2026-03-20 10:00", "image": "x", "track": None},
        {"id": "p3", "title": "P3", "artist": "Monet", "museum": "N", "saved_at": "2025-12-31 10:00", "image": "x", "track": None}]
t0 = time.mktime((2026, 5, 1, 21, 0, 0, 0, 0, -1))
hist = [{"id": "p1", "artist": "Dufy", "ts": t0 + i * 600, "dwell_s": 600, "mode": "music", "track_artist": "Nina Simone"} for i in range(6)]
hist += [{"id": "p4", "artist": "Monet", "ts": t0 + 5000, "dwell_s": 7200, "mode": "rotation"}]
s = year.summary(2026, favs, hist)
assert s["kept"] == 2 and s["per_month"][2] == 2 and s["quiet_months"][:2] == [0, 1] and s["tiles"][2]["id"] == "p1", s
assert s["top_artist"] == ("Dufy", 2) and s["top_song_artist"] == ("Nina Simone", 1) and s["shown"] == 7 and s["hours"] == 3.0, s
assert s["top_painter"] == {"name": "Monet", "hours": 2.0} and s["busiest_hour"] == 21, s
assert year.summary(2025, favs, hist)["kept"] == 1
img = year.render(s, {}, None)  # no network: tiles stay dark squares, the card still renders
assert img.size == (1080, 1350)
print("signals ok: feel, names, tags, moment, matcher, year; all server keys translated")
