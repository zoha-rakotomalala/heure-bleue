#!/usr/bin/env python3
"""Build data/paintings.json from open museum APIs (no keys).

Sources
  met    The Metropolitan Museum of Art  (collectionapi.metmuseum.org)
  rijks  Rijksmuseum Amsterdam            (data.rijksmuseum.nl, Linked Art + IIIF)
  orsay  Musée d'Orsay, Paris             (Wikimedia Commons category walk, PD files only)

Each entry stores display fields, the image URL, size, and a five-color palette
(sRGB hex + weight) so the poller can match a Spotify cover by color. Photos that
include a photographic calibration strip along the bottom edge are skipped.
Entries may carry an optional ``story`` (curator/description text, <= ~600 chars)
and, when that text is not English, a ``story_lang`` ISO code (e.g. "nl").
Resumable: existing entries are kept, new ids are appended.

Usage: python3 build_index.py --target 300 [--source met|rijks|orsay|all] [--delay 0.8]
       ("both" is kept as an alias for "all")
"""
import argparse
import functools
import html
import io
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

from . import config
from .color import has_calibration_strip, palette_from_image

ROOT = config.ROOT
OUT = config.PAINTINGS
UA = {"User-Agent": "heure-bleue/1.0 (personal desk display)"}
DELAY = 0.8


def get_json(url, retries=3):
    headers = dict(UA)
    headers["Accept"] = "application/ld+json" if "rijksmuseum.nl" in url else "application/json"
    for attempt in range(retries):
        try:
            time.sleep(DELAY)
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return json.load(r)
        except Exception:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def get_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


# --- text helpers ----------------------------------------------------------------

_HIDDEN = re.compile(r"<[^>]+display:\s*none[^>]*>.*?</[^>]+>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def strip_html(s):
    """Plain text from a Commons/extmetadata HTML fragment (hidden spans dropped)."""
    if not s:
        return ""
    s = _HIDDEN.sub(" ", s)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = html.unescape(_TAG.sub(" ", s))
    return re.sub(r"\s+", " ", s).strip()


STORY_MAX = 600


def trim_story(text, limit=STORY_MAX):
    """Trim to <= limit chars, cutting at the last sentence end when possible."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    ends = [cut.rfind(p) for p in (". ", "! ", "? ", ".\u201d ", ".\u2019 ")]
    end = max(ends)
    if end < limit // 3:  # no usable sentence boundary; fall back to a word boundary
        return cut[: cut.rfind(" ")].rstrip(",;:") + "\u2026"
    return cut[: end + 1].strip()


# --- image analysis ------------------------------------------------------------



def analyse(img_bytes):
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    if has_calibration_strip(im):
        return None
    w, h = im.size
    return w, h, palette_from_image(im)


# --- Met ---------------------------------------------------------------------

MET = "https://collectionapi.metmuseum.org/public/collection/v1"
MET_SEARCHES = [
    f"{MET}/search?hasImages=true&isPublicDomain=true&departmentId=11&q=painting",
    f"{MET}/search?hasImages=true&isPublicDomain=true&departmentId=1&q=painting",
    f"{MET}/search?hasImages=true&isPublicDomain=true&departmentId=21&q=painting",
]


def met_candidates(seen):
    ids = []
    for url in MET_SEARCHES:
        ids.extend(get_json(url).get("objectIDs") or [])
    ids = [i for i in dict.fromkeys(ids) if f"met-{i}" not in seen]
    random.shuffle(ids)
    return ids


def met_fetch(oid):
    o = get_json(f"{MET}/objects/{oid}")
    if not o.get("isPublicDomain") or not o.get("primaryImageSmall"):
        return None
    if "Painting" not in (o.get("classification") or ""):
        return None
    res = analyse(get_bytes(o["primaryImageSmall"]))
    if not res:
        print(f"  strip  met-{oid} {o.get('title', '')[:40]}")
        return None
    w, h, pal = res
    return {
        "id": f"met-{oid}", "title": o.get("title") or "Untitled",
        "artist": o.get("artistDisplayName") or "Unknown artist", "date": o.get("objectDate") or "",
        "museum": "The Metropolitan Museum of Art", "url": o.get("objectURL"),
        "image": o["primaryImageSmall"], "w": w, "h": h, "palette": pal,
    }


# --- Rijksmuseum ---------------------------------------------------------------

RIJKS_SEARCH = "https://data.rijksmuseum.nl/search/collection?type=painting&imageAvailable=true"


def rijks_candidates(seen, pages=8):
    """Walk a few random-depth pages of the search (100 ids per page)."""
    ids, url = [], RIJKS_SEARCH
    skip = random.randint(0, 12)
    for n in range(skip + pages):
        d = get_json(url)
        if n >= skip:
            ids.extend(i["id"] for i in d.get("orderedItems", []))
        url = (d.get("next") or {}).get("id")
        if not url:
            break
    ids = [i for i in dict.fromkeys(ids) if f"rijks-{i.rsplit('/', 1)[-1]}" not in seen]
    random.shuffle(ids)
    return ids


def _en(notations):
    for n in notations or []:
        if n.get("@language") == "en":
            return n.get("@value")
    return (notations or [{}])[0].get("@value")


ENGLISH = "http://vocab.getty.edu/aat/300388277"
DUTCH = "http://vocab.getty.edu/aat/300388256"
DESCRIPTION_TYPES = {
    "http://vocab.getty.edu/aat/300048722",  # description (document genre)
    "http://vocab.getty.edu/aat/300404670",  # description (Rijksmuseum's curator text)
    "http://vocab.getty.edu/aat/300411780",  # description (Linked Art default)
}
LANG_CODES = {ENGLISH: "en", DUTCH: "nl"}


def rijks_title(o):
    names = [n for n in o.get("identified_by", []) if n.get("type") == "Name" and n.get("content")]
    for n in names:
        if any(l.get("id") == ENGLISH for l in n.get("language", [])):
            return n["content"]
    return names[0]["content"] if names else "Untitled"


def _linguistic_objects(o):
    """Yield every LinguisticObject that may hold prose: subject_of parts + referred_to_by."""
    for s in o.get("subject_of", []) or []:
        for p in [s] + (s.get("part", []) or []):
            if p.get("type") == "LinguisticObject" and p.get("content"):
                yield p
    for r in o.get("referred_to_by", []) or []:
        if r.get("type") == "LinguisticObject" and r.get("content"):
            yield r


def rijks_story(o):
    """(text, lang) of the object's description, preferring English.

    The Linked Art records classify the curator description as aat/300404670
    (or 300048722 / 300411780). As of 2026-09 the API only carries these in Dutch
    for nearly every painting, so the Dutch text is returned with lang "nl" when
    no English one exists. Returns (None, None) when there is no description.
    """
    best, best_rank = None, 99
    for lo in _linguistic_objects(o):
        types = {c.get("id") for c in lo.get("classified_as", []) or []}
        if not types & DESCRIPTION_TYPES:
            continue
        langs = {l.get("id") for l in lo.get("language", []) or []}
        text = strip_html(lo["content"])
        if len(text) < 40:
            continue
        rank = 0 if ENGLISH in langs else 1 if DUTCH in langs else 2
        if rank < best_rank:
            best, best_rank = (trim_story(text), next((LANG_CODES[l] for l in langs if l in LANG_CODES), "und")), rank
    return best or (None, None)


def with_story(entry, text, lang):
    if text:
        entry["story"] = text
        if lang and lang != "en":
            entry["story_lang"] = lang
    return entry


def rijks_fetch(obj_url):
    o = get_json(obj_url)
    oid = obj_url.rsplit("/", 1)[-1]
    title = rijks_title(o)
    pb = o.get("produced_by") or {}
    artists = []
    for part in [pb] + pb.get("part", []):
        for a in part.get("carried_out_by", []) or []:
            name = _en(a.get("notation"))
            if name and name not in artists:
                artists.append(name)
    ts = (pb.get("timespan") or {}).get("identified_by", [{}])
    date = ts[0].get("content", "") if ts else ""
    shows = o.get("shows") or []
    if not shows:
        return None
    vis = get_json(shows[0]["id"])
    dig = (vis.get("digitally_shown_by") or [{}])[0].get("id")
    if not dig:
        return None
    d = get_json(dig)
    ap = (d.get("access_point") or [{}])[0].get("id", "")
    if "/full/" not in ap:
        return None
    base = ap.split("/full/")[0]
    image = f"{base}/full/!1400,1400/0/default.jpg"
    res = analyse(get_bytes(f"{base}/full/!600,600/0/default.jpg"))
    if not res:
        print(f"  strip  rijks-{oid} {title[:40]}")
        return None
    w, h, pal = res
    handle = next((e["id"] for e in o.get("equivalent", []) if "hdl.handle.net" in e.get("id", "")), obj_url)
    entry = {
        "id": f"rijks-{oid}", "title": title, "artist": ", ".join(artists) or "Unknown artist",
        "date": date, "museum": "Rijksmuseum, Amsterdam", "url": handle,
        "image": image, "w": w, "h": h, "palette": pal,
    }
    return with_story(entry, *rijks_story(o))


# --- Museums via Wikimedia Commons -----------------------------------------------
# One category per museum; the Orsay code below walks any of them. Slug = id prefix.

COMMONS = "https://commons.wikimedia.org/w/api.php"
COMMONS_MUSEUMS = {
    "orsay": ("Category:Paintings in the Musée d'Orsay", "Musée d'Orsay, Paris"),
    "orangerie": ("Category:Paintings in the Musée de l'Orangerie", "Musée de l'Orangerie, Paris"),
    "marmottan": ("Category:Paintings in the Musée Marmottan Monet", "Musée Marmottan Monet, Paris"),
    "petit-palais": ("Category:Paintings in the Petit Palais", "Petit Palais, Paris"),
    "louvre": ("Category:Paintings in the Louvre", "Musée du Louvre, Paris"),
    "lyon": ("Category:Paintings in the Musée des Beaux Arts de Lyon", "Musée des Beaux-Arts de Lyon"),
    "national-gallery": ("Category:Paintings in the National Gallery, London", "National Gallery, London"),
    "prado": ("Category:Paintings in the Museo del Prado", "Museo del Prado, Madrid"),
    "mauritshuis": ("Category:Paintings in the Mauritshuis", "Mauritshuis, The Hague"),
    "van-gogh": ("Category:Paintings in the Van Gogh Museum", "Van Gogh Museum, Amsterdam"),
    "kroller-muller": ("Category:Paintings in the Kröller-Müller Museum", "Kröller-Müller Museum, Otterlo"),
    "khm": ("Category:Paintings in the Kunsthistorisches Museum", "Kunsthistorisches Museum, Vienna"),
    "belvedere": ("Category:Paintings in the Österreichische Galerie Belvedere", "Belvedere, Vienna"),
    "alte-nationalgalerie": ("Category:Paintings in the Alte Nationalgalerie", "Alte Nationalgalerie, Berlin"),
    "gemaldegalerie": ("Category:Paintings in the Gemäldegalerie, Berlin", "Gemäldegalerie, Berlin"),
    "neue-pinakothek": ("Category:Paintings in the Neue Pinakothek", "Neue Pinakothek, Munich"),
    "stadel": ("Category:Paintings in the Städel", "Städel Museum, Frankfurt"),
    "nationalmuseum": ("Category:Paintings in the Nationalmuseum Stockholm", "Nationalmuseum, Stockholm"),
    "ateneum": ("Category:Paintings in the Ateneum", "Ateneum, Helsinki"),
    "hermitage": ("Category:Paintings in the Hermitage", "Hermitage Museum, Saint Petersburg"),
    "nga": ("Category:Paintings in the National Gallery of Art (Washington, D.C.)", "National Gallery of Art, Washington"),
}
ORSAY_ROOT, ORSAY_MUSEUM = COMMONS_MUSEUMS["orsay"]
COMMONS_SKIP_CATS = ("People with paintings", "Framed paintings", "Details of", "Copies after", "Reproductions of")
ORSAY_SKIP_CATS = COMMONS_SKIP_CATS
MAX_CATS = 60  # categories walked per museum; enough for a few hundred files, cheap on the API
IMAGE_EXT = (".jpg", ".jpeg", ".png")
BAD_TITLE = re.compile(r"\b(detail|details|d[ée]tails?|crop|cropped|frame|framed|cadre|encadr[ée]e?|in situ|installation view|exhibition|exposition)\b", re.I)
PD_LICENCE = re.compile(r"public domain|\bCC0\b|\bPD\b|no (known )?(copyright )?restrictions", re.I)
MIN_ORIGINAL_WIDTH = 700
# Wikimedia only serves standard thumbnail widths (https://w.wiki/GHai: 20 40 60 120 250 330 500
# 960 1280 1920 3840). Any other width is rejected (400) or throttled (429), so hotlinked thumbs
# MUST use one of these. 1280 for display, 500 for palette/strip analysis.
IMAGE_WIDTH = 1280
THUMB_WIDTH = 500


def commons(params):
    q = dict(params, format="json", formatversion="2")
    return get_json(f"{COMMONS}?{urllib.parse.urlencode(q)}")


def commons_members(cat):
    out, params = [], {"action": "query", "list": "categorymembers", "cmtitle": cat,
                       "cmlimit": "500", "cmtype": "subcat|file"}
    while True:
        d = commons(params)
        out.extend(d.get("query", {}).get("categorymembers", []))
        if "continue" not in d:
            return out
        params.update(d["continue"])


def commons_candidates(seen, slug="orsay", depth=2, cache_hours=72):
    """Walk one museum's Commons category and its subcategories (default two levels down).

    Returns Commons file pageids of jpg/png files not yet indexed, shuffled. The
    walk costs up to MAX_CATS API calls, so its result is cached in logs/ for a few days.
    """
    root, _ = COMMONS_MUSEUMS[slug]
    cache = ROOT / "logs" / f"{slug}_candidates.json"
    files = None
    if cache.exists() and time.time() - cache.stat().st_mtime < cache_hours * 3600:
        files = {int(k): v for k, v in json.loads(cache.read_text(encoding="utf-8")).items()}
        print(f"  {slug}: {len(files)} image files from cache {cache.name}")
    if files is None:
        files, todo, done = {}, [(root, 0)], set()
        while todo and len(done) < MAX_CATS:
            cat, lvl = todo.pop(0)
            if cat in done:
                continue
            done.add(cat)
            try:
                members = commons_members(cat)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip   category {cat}: {exc}", file=sys.stderr)
                if "429" in str(exc) or "403" in str(exc):
                    time.sleep(60)
                continue
            time.sleep(DELAY)
            for m in members:
                if m.get("ns") == 6 and m["title"].lower().endswith(IMAGE_EXT):
                    files[m["pageid"]] = m["title"]
                elif m.get("ns") == 14 and lvl < depth and not any(s in m["title"] for s in COMMONS_SKIP_CATS):
                    todo.append((m["title"], lvl + 1))
        print(f"  {slug}: {len(done)} categories walked, {len(files)} image files", flush=True)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(files, ensure_ascii=False), encoding="utf-8")
    ids = [pid for pid in files if f"{slug}-{pid}" not in seen]
    random.shuffle(ids)
    _QUEUES[slug] = ids  # same list object main() pops from, so the fetcher can prefetch the next batch
    return ids


def orsay_candidates(seen, depth=2, cache_hours=72):
    return commons_candidates(seen, "orsay", depth, cache_hours)


_QUEUES = {}               # slug -> remaining candidate pageids (shared with main's queue order)
_META = {}                 # pageid -> (page, imageinfo)
ORSAY_BATCH = 25


def _imageinfo_batch(pageids):
    """Metadata for up to 50 files in ONE API call. No iiurlwidth on purpose: asking the
    API to render two thumbnail sizes for 25 files at once trips Wikimedia's 429 throttle;
    thumbnails are instead requested one at a time from upload.wikimedia.org (thumb_url)."""
    d = commons({"action": "query", "prop": "imageinfo|categories", "pageids": "|".join(map(str, pageids)),
                 "iiprop": "url|size|extmetadata", "clshow": "!hidden", "cllimit": "500"})
    return {p["pageid"]: p for p in d.get("query", {}).get("pages", []) if "imageinfo" in p}


def _imageinfo(pageid, slug="orsay"):
    """(page, imageinfo) for a file; fetched ORSAY_BATCH files per API call, from this museum's queue."""
    if pageid not in _META:
        queue = _QUEUES.get(slug, [])
        batch = [pageid] + [p for p in reversed(queue) if p != pageid and p not in _META][: ORSAY_BATCH - 1]
        pages = _imageinfo_batch(batch)
        for pid in batch:
            pg = pages.get(pid)
            _META[pid] = (pg, pg["imageinfo"][0]) if pg else (None, None)
    return _META.pop(pageid)


def thumb_url(original, orig_width, width):
    """Standard-bucket Commons thumbnail URL (…/thumb/a/ab/Name.jpg/1280px-Name.jpg).

    Returns the original URL when the file is not wider than the requested size.
    """
    original = _clean_url(original)
    if orig_width <= width or "/wikipedia/commons/" not in original:
        return original
    head, rest = original.split("/wikipedia/commons/", 1)
    name = rest.rsplit("/", 1)[-1]
    thumb = f"{width}px-{name}"
    if not thumb.lower().endswith((".jpg", ".jpeg", ".png")):
        thumb += ".png"  # tiff/gif/svg thumbs are rendered as png
    return f"{head}/wikipedia/commons/thumb/{rest}/{thumb}"


def _clean_url(u):
    return u.split("?", 1)[0] if u else u


def _meta(ii, key):
    return strip_html(((ii.get("extmetadata") or {}).get(key) or {}).get("value", ""))


LANG_LABEL = re.compile(r"\b(English|French|Français|Italian|Italiano|German|Deutsch|Dutch|Nederlands|Spanish|Español|Portuguese|Russian|Polish|Swedish|Danish|Catalan)\s*:\s*", re.I)
USERNAME_LIKE = re.compile(r"^[A-Za-z0-9_.-]+$")  # a single token such as "Sailko" is the photographer, not the painter
PAINTER_CATS = [  # Commons category patterns that name the painter, most specific first
    re.compile(r"^Category:(?:\d{4}s? )?(?:paintings|works|portraits|landscapes|gardens|drawings) by (.+?)(?: in (?:the )?[^|]+| by .+)?$", re.I),
    re.compile(r"^Category:.+ (?:-|by) ([A-ZÀ-Ý][\wÀ-ÿ'.-]+(?: [\wÀ-ÿ'.-]+){1,4})$"),  # '<Title> - <Painter>' single-painting cats
]
FRAME_CATS = re.compile(r"framed paintings|painting frames|frames \(", re.I)
PHOTO_DATE = re.compile(r"\b(19[3-9]\d|20\d\d)\b")  # public-domain painting pools end before 1930: a later year is the photo's date


def pick_language(text):
    """From 'French: X English: Y' style multilingual text pick the English part, else the first."""
    text = re.sub(r'\s*"\s*"\s*', " ", text).strip()  # stray empty quote pairs left by templates
    parts = LANG_LABEL.split(text)
    if len(parts) < 3:
        return text
    lead, langs, bodies = parts[0].strip(), parts[1::2], [b.strip() for b in parts[2::2]]
    for lang, body in zip(langs, bodies):
        if lang.lower() == "english" and body:
            return body
    return next((b for b in bodies if b), lead)


_QS_LABEL_EN = re.compile(r'label QS:Len,"([^"]+)"')
_LANG_BLOCK = re.compile(r'<(?:div|span)[^>]*\blang="([a-zA-Z-]+)"[^>]*>(.*?)</(?:div|span)>', re.S)


def multilingual_pick(raw_html):
    """English text from a Commons {{title}}/{{LangSwitch}} HTML fragment, else its first language."""
    m = _QS_LABEL_EN.search(raw_html or "")
    if m and strip_html(m.group(1).split("<", 1)[0]):
        return strip_html(m.group(1).split("<", 1)[0])  # the label may run into an inline edit-icon span
    blocks = [(lang.lower(), strip_html(inner)) for lang, inner in _LANG_BLOCK.findall(raw_html or "")]
    blocks = [(lang, t) for lang, t in blocks if t]
    for lang, t in blocks:
        if lang.startswith("en"):
            return t
    if blocks:
        return blocks[0][1]
    return pick_language(strip_html(raw_html))


def orsay_title(page, ii):
    for key in ("ObjectName", "ImageDescription"):
        raw = ((ii.get("extmetadata") or {}).get(key) or {}).get("value", "")
        t = multilingual_pick(raw)
        if 2 < len(t) <= 160:
            return t
    t = page["title"].split(":", 1)[-1]
    return re.sub(r"\.[a-z]+$", "", t, flags=re.I).replace("_", " ")


def orsay_artist(page, ii):
    """Painter name: extmetadata Artist unless it is an uploader handle, then the 'Paintings by X' category."""
    artist = pick_language(_meta(ii, "Artist"))
    artist = re.sub(r"\s*\(.*?\)\s*$", "", artist).strip()[:120]
    if artist and not USERNAME_LIKE.match(artist) and not artist.lower().startswith(("unknown", "anonym")):
        return artist
    cats = [c.get("title", "") for c in page.get("categories", []) or []]
    for pat in PAINTER_CATS:
        for c in cats:
            m = pat.match(c)
            if m and not USERNAME_LIKE.match(m.group(1)):
                return m.group(1)
    return artist or "Unknown artist"


def orsay_date(ii):
    d = _meta(ii, "DateTimeOriginal")
    d = re.split(r"\bdate QS:", d)[0].strip()
    return "" if PHOTO_DATE.search(d) else d[:60]


def commons_fetch(pageid, slug="orsay"):
    museum = COMMONS_MUSEUMS[slug][1]
    page, ii = _imageinfo(pageid, slug)
    if not ii:
        return None
    lic = _meta(ii, "LicenseShortName")
    if not PD_LICENCE.search(lic):
        print(f"  licence {slug}-{pageid} {lic[:40]!r}")
        return None
    w0, h0 = ii.get("width", 0), ii.get("height", 0)
    if w0 < MIN_ORIGINAL_WIDTH:
        return None
    title = orsay_title(page, ii)
    desc = multilingual_pick(((ii.get("extmetadata") or {}).get("ImageDescription") or {}).get("value", ""))
    cats = " ".join(c.get("title", "") for c in page.get("categories", []) or [])
    if BAD_TITLE.search(title) or BAD_TITLE.search(page["title"]) or BAD_TITLE.search(desc[:300]) or FRAME_CATS.search(cats):
        return None  # detail/crop/frame, or a photo taken in a gallery rather than a reproduction
    artist = orsay_artist(page, ii)
    image = thumb_url(ii["url"], w0, IMAGE_WIDTH)
    thumb = thumb_url(ii["url"], w0, THUMB_WIDTH)
    time.sleep(DELAY)  # be polite to upload.wikimedia.org too
    res = analyse(get_bytes(thumb))
    if not res:
        print(f"  strip  {slug}-{pageid} {title[:40]}")
        return None
    w, h, pal = res
    entry = {
        "id": f"{slug}-{pageid}", "title": title, "artist": artist, "date": orsay_date(ii),
        "museum": museum, "url": ii.get("descriptionurl") or f"https://commons.wikimedia.org/?curid={pageid}",
        "image": image, "w": w0 or w, "h": h0 or h, "palette": pal,
    }
    if len(desc) > 60 and desc.lower() != title.lower() and " " in desc:
        entry["story"] = trim_story(desc)
    return entry


def orsay_fetch(pageid):
    return commons_fetch(pageid, "orsay")


# --- main ------------------------------------------------------------------------

def main(target=None, source=None, delay=None, argv=None):
    global DELAY
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up in a redirected log
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=300, help="stop when the index holds this many paintings")
    ap.add_argument("--source", default="all",
                    help="met, rijks, a Commons museum slug (" + ", ".join(COMMONS_MUSEUMS) + "), "
                         "'commons' for all Commons museums, or 'all' (default, round-robin over everything)")
    ap.add_argument("--delay", type=float, default=0.8)
    args = ap.parse_args(argv if argv is not None else [])
    if target is not None: args.target = target
    if source is not None: args.source = source
    if delay is not None: args.delay = delay
    DELAY = args.delay
    source = "all" if args.source == "both" else args.source.lower()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    seen = {e["id"] for e in existing}
    print(f"existing: {len(existing)}  target: {args.target}")

    queues = []
    if source in ("met", "all"):
        queues.append(("met", met_candidates(seen), met_fetch))
    if source in ("rijks", "all"):
        queues.append(("rijks", rijks_candidates(seen), rijks_fetch))
    for slug in COMMONS_MUSEUMS:
        if source in (slug, "commons", "all"):
            queues.append((slug, commons_candidates(seen, slug), functools.partial(commons_fetch, slug=slug)))
    if not queues:
        ap.error(f"unknown source {source!r}")
    print("candidates: " + ", ".join(f"{n}={len(q)}" for n, q, _ in queues))

    processed = added = 0
    while len(existing) < args.target and any(q for _, q, _ in queues):
        for name, q, fetch in queues:  # round-robin so the museums grow together
            if not q or len(existing) >= args.target:
                continue
            cid = q.pop()
            processed += 1
            try:
                entry = fetch(cid)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip   {name} {cid}: {exc}", file=sys.stderr)
                if "403" in str(exc) or "429" in str(exc):
                    print("  rate-limited, sleeping 90s", file=sys.stderr)
                    time.sleep(90)
                continue
            if entry:
                existing.append(entry)
                seen.add(entry["id"])
                added += 1
            if processed % 20 == 0:
                OUT.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
                print(f"  {processed} processed, {added} added, index={len(existing)}")
    OUT.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    print(f"done: {len(existing)} paintings in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
