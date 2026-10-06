"""The moment: hour, sky and season, as a feel the matcher can compare with a palette.

The page already fetches the weather (Open-Meteo) for the top-right corner; it posts
the parts the matcher needs to POST /api/moment: the WMO weather code and the sun
times. The server keeps them here, in memory. The hour and the season need nothing.

    update(code, sunrise_ts, sunset_ts, lat)   from the page, every weather refresh
    current() -> {"feel": {...}, "reasons": ["mo_rain", "mo_night"], "phase": ..., "sky": ..., "season": ...}

The feel is a nudge on the neutral painting (light .55, chroma .45, warm 0): a rainy
night asks for a dark, grey, cool painting; a clear summer noon for a pale vivid warm
one. The reasons are translation keys for the "why this painting" line.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

_STATE = {"code": None, "sunrise": 0.0, "sunset": 0.0, "lat": 48.9, "ts": 0.0}
_LOCK = threading.Lock()

# WMO weather code -> sky class
def sky_of(code: Optional[int]) -> Optional[str]:
    if code is None:
        return None
    if code in (0, 1):
        return "clear"
    if code in (2,):
        return "partly"
    if code == 3:
        return "overcast"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    return None


# nudges: (light, chroma, warm)
PHASE = {"night": (-0.30, -0.10, -0.10), "dawn": (0.05, 0.05, 0.30), "dusk": (-0.10, 0.00, -0.15), "evening": (-0.15, -0.05, 0.10), "day": (0.05, 0.05, 0.00)}
SKY = {"clear": (0.10, 0.15, 0.05), "partly": (0.03, 0.03, 0.00), "overcast": (-0.05, -0.15, -0.05), "fog": (0.05, -0.30, -0.05),
       "rain": (-0.10, -0.20, -0.20), "snow": (0.25, -0.25, -0.15), "storm": (-0.25, -0.10, -0.10)}
SEASON = {"spring": (0.05, 0.10, 0.10), "summer": (0.05, 0.15, 0.20), "autumn": (-0.05, 0.00, 0.35), "winter": (-0.05, -0.10, -0.25)}
# which reasons are worth a word in the why line (plain "day" and "partly cloudy" are not)
NOTABLE_PHASE = {"night", "dawn", "dusk", "evening"}
NOTABLE_SKY = {"clear", "overcast", "fog", "rain", "snow", "storm"}


def update(code: Optional[int], sunrise: Optional[float], sunset: Optional[float], lat: Optional[float]) -> None:
    with _LOCK:
        if code is not None:
            _STATE["code"] = int(code)
        if sunrise:
            _STATE["sunrise"] = float(sunrise)
        if sunset:
            _STATE["sunset"] = float(sunset)
        if lat is not None:
            _STATE["lat"] = float(lat)
        _STATE["ts"] = time.time()


def season_of(month: int, lat: float) -> str:
    s = ("winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn", "autumn", "winter")[month - 1]
    if lat < 0:  # southern hemisphere
        s = {"winter": "summer", "summer": "winter", "spring": "autumn", "autumn": "spring"}[s]
    return s


def phase_of(now: float, sunrise: float, sunset: float, hour: int) -> str:
    if sunrise and sunset and abs(now - sunrise) < 86400 * 1.5:
        # today's sun times (the page refreshes them every 15 min); "dawn"/"dusk" are the blue hours around them
        if abs(now - sunrise) <= 45 * 60:
            return "dawn"
        if abs(now - sunset) <= 45 * 60:
            return "dusk"
        if sunrise + 45 * 60 < now < sunset - 45 * 60:
            return "day"
        if sunset + 45 * 60 <= now < sunset + 4 * 3600:
            return "evening"
        return "night"
    if 6 <= hour < 8:
        return "dawn"
    if 8 <= hour < 18:
        return "day"
    if 18 <= hour < 20:
        return "dusk"
    if 20 <= hour < 23:
        return "evening"
    return "night"


def current(now: Optional[float] = None) -> dict:
    now = now or time.time()
    lt = time.localtime(now)
    with _LOCK:
        st = dict(_STATE)
    fresh = now - st["ts"] < 3 * 3600  # the page stopped reporting: forget the sky, keep the hour and season
    sky = sky_of(st["code"]) if fresh else None
    phase = phase_of(now, st["sunrise"] if fresh else 0, st["sunset"] if fresh else 0, lt.tm_hour)
    season = season_of(lt.tm_mon, st["lat"])
    light, chroma, warm = 0.55, 0.45, 0.0
    for d in (PHASE[phase], SKY.get(sky, (0, 0, 0)), SEASON[season]):
        light += d[0]; chroma += d[1]; warm += d[2]
    reasons = []
    if sky in NOTABLE_SKY:
        reasons.append(f"mo_{sky}")
    if phase in NOTABLE_PHASE:
        reasons.append(f"mo_{phase}")
    if len(reasons) < 2:
        reasons.append(f"mo_{season}")
    return {"feel": {"light": round(min(1, max(0, light)), 3), "chroma": round(min(1, max(0, chroma)), 3), "warm": round(max(-1, min(1, warm)), 3)},
            "reasons": reasons[:2], "phase": phase, "sky": sky, "season": season}
