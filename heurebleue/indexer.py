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
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

from . import config
from .color import has_calibration_strip, palette_from_image

ROOT = config.ROOT
OUT = config.PAINTINGS
LOCAL = config.PAINTINGS_LOCAL
UA = {"User-Agent": "heure-bleue/1.0 (https://github.com/zoha-rakotomalala/heure-bleue; personal desk display)"}
# Wikimedia's robot policy wants a contact URL in the User-Agent; without one it answers 429 far more often.
DELAY = 0.8
DEADLINE = 75          # seconds; a wall-clock cap per request. urllib's timeout does not cover DNS lookups,
                       # which hung an overnight run for 20 minutes.
ALLOW_CC = False       # accept CC BY / CC BY-SA files into the local-only index (never committed)


def _with_deadline(fn, seconds):
    box = []

    def run():
        try:
            box.append((fn(), None))
        except Exception as exc:  # noqa: BLE001
            box.append((None, exc))

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"no answer after {seconds}s")
    value, exc = box[0]
    if exc is not None:
        raise exc
    return value


def get_json(url, retries=3):
    headers = dict(UA)
    headers["Accept"] = "application/ld+json" if "rijksmuseum.nl" in url else "application/json"
    for attempt in range(retries):
        try:
            time.sleep(DELAY)
            with _with_deadline(lambda: urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30), DEADLINE) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise  # 429 / 403 / 404: the caller decides how long to back off
        except Exception:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def get_bytes(url):
    with _with_deadline(lambda: urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60), DEADLINE) as r:
        return r.read()


def backoff_seconds(exc, hits):
    """How long to sleep after the ``hits``-th consecutive 429/403: 90 s, 180, 360, capped at 600,
    or longer if the server said so in Retry-After."""
    wait = min(90 * 2 ** (hits - 1), 600)
    retry_after = exc.headers.get("Retry-After") if isinstance(exc, urllib.error.HTTPError) else None
    if retry_after and retry_after.isdigit():
        wait = max(wait, int(retry_after))
    return wait


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
# /v1/search was retired on 1 October 2026 (HTTP 410). Its replacement, /v1.1/search, takes the same filters
# and pages with offset/limit (500 max). 11 = European Paintings, 1 = American Wing, 21 = Modern.
MET_SEARCHES = [f"{MET}.1/search?hasImages=true&isPublicDomain=true&departmentId={d}&q=painting" for d in (11, 1, 21)]
MET_PAGE = 500


def met_search(url):
    """Every objectID the paginated v1.1 search returns for `url`."""
    ids, offset = [], 0
    while True:
        d = get_json(f"{url}&offset={offset}&limit={MET_PAGE}")
        page = d.get("objectIDs") or []
        ids.extend(page)
        offset += len(page)
        if not page or offset >= d.get("total", 0):
            return ids
        time.sleep(DELAY)


def met_candidates(seen):
    ids = []
    for url in MET_SEARCHES:
        ids.extend(met_search(url))
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
COMMONS_SKIP_CATS = ("People with paintings", "Framed paintings", "Details of", "Copies after", "Reproductions of",
                     # book scans and printed matter, not photographs of the paintings themselves
                     "La peinture au Louvre", "Books", "Book scans", "Scans from", "Publications", "Catalogues",
                     "Postcards", "Prints after", "Engravings after", "Photographs", "Interior", "Exterior")
ORSAY_SKIP_CATS = COMMONS_SKIP_CATS
MAX_CATS = 60  # categories walked per museum; enough for a few hundred files, cheap on the API
IMAGE_EXT = (".jpg", ".jpeg", ".png")
BAD_TITLE = re.compile(r"\b(detail|details|d[ée]tails?|crop|cropped|frame|framed|cadre|encadr[ée]e?|in situ|installation view|exhibition|exposition)\b", re.I)
PD_LICENCE = re.compile(r"public domain|\bCC0\b|\bPDM?\b|no (known )?(copyright )?restrictions", re.I)  # PDM = Public Domain Mark
CC_LICENCE = re.compile(r"\bCC[ -]BY\b", re.I)  # any attribution licence: fine to display at home, not shipped
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
        files, todo, done, hits = {}, [(root, 0)], set(), 0
        while todo and len(done) < MAX_CATS:
            cat, lvl = todo.pop(0)
            if cat in done:
                continue
            done.add(cat)
            try:
                members = commons_members(cat)
                hits = 0
            except Exception as exc:  # noqa: BLE001
                print(f"  skip   category {cat}: {exc}", file=sys.stderr)
                if "429" in str(exc) or "403" in str(exc):
                    hits += 1
                    time.sleep(backoff_seconds(exc, hits))
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


# --- women painters: walk "Paintings by <name>" for each painter in data/women_painters.json ----------
# The museum is not known from the category, so it is read from each file's own categories
# ("Paintings in the Mauritshuis", "Dutch Golden Age paintings in the Rijksmuseum Amsterdam").
# Files that resolve to one of COMMONS_MUSEUMS keep that museum's id prefix, so they
# deduplicate against the museum walks; the others are "commons-<pageid>".

WOMEN = config.DATA / "women_painters.json" if (config.DATA / "women_painters.json").exists() \
    else config.BUNDLE / "data" / "women_painters.json"
WOMEN_MAX_CATS = 12       # categories walked per painter ("by museum", "by year" and their children)
WOMEN_MAX_FILES = None    # no cap: every painting by every woman painter on the list
WOMEN_SKIP_CATS = COMMONS_SKIP_CATS + ("private collection", "unidentified", "Signatures of", "by subject", "by genre")
_PAINTER_OF = {}          # pageid -> painter name, from the category that listed the file
_MUSEUM_CAT = re.compile(r"^Category:.*\b(?:paintings|works|art|portraits|landscapes|still lifes?|drawings|watercolou?rs|"
                         r"pastels|collection)\b.*\bin (?:the )?([^,]+?)$", re.I)
_MUSEUM_WORD = re.compile(r"museum|museo|mus[ée]e|museu|gallery|galerie|galleria|kunsthalle|kunsthaus|pinakothek|"
                          r"collection|sammlung|stiftung|foundation|fondation|institute|palace|palais|palazzo|castle|"
                          r"ch[âa]teau|schloss|academy|akademie|library|biblioth|hall\b|fine arts|beaux-arts|"
                          r"nationalgalerie|belvedere|hermitage|mauritshuis|rijksmuseum|louvre|prado|uffizi|ateneum|"
                          r"nationalmuseum|st[äa]del|albertina|kunstmuseum|konstmuseum|kunstsammlung|landesmuseum|"
                          r"stedelijk|gemeentemuseum|frans hals|boijmans|teylers|lakenhal|skagen|hirschsprung|statens|"
                          r"nasjonal|thorvaldsen|ordrupgaard|glyptotek|rmn|petit palais|carnavalet|cognacq", re.I)
_MUSEUM_SKIP = re.compile(r"private collection|unidentified|unknown|\blost\b|destroyed|art market|auction|exhibition|"
                          r"^\d|century|style|school|dynasty|^(?:the )?(?:Netherlands|France|Germany|Austria|Italy|Spain|"
                          r"Sweden|Norway|Denmark|Finland|Russia|Belgium|Switzerland|Poland|England|United Kingdom|"
                          r"United States|Europe|Paris|London|Amsterdam|Vienna|Berlin|Munich)$", re.I)
_MUSEUM_ALIAS = [  # a known museum's words in a category -> its slug (so ids deduplicate with the museum walks)
    (re.compile(r"Mus[ée]e d'Orsay", re.I), "orsay"), (re.compile(r"Orangerie", re.I), "orangerie"),
    (re.compile(r"Marmottan", re.I), "marmottan"), (re.compile(r"Petit Palais", re.I), "petit-palais"),
    (re.compile(r"\bLouvre\b", re.I), "louvre"), (re.compile(r"Beaux[- ]Arts de Lyon", re.I), "lyon"),
    (re.compile(r"National Gallery, London|National Gallery \(London\)", re.I), "national-gallery"),
    (re.compile(r"\bPrado\b", re.I), "prado"), (re.compile(r"Mauritshuis", re.I), "mauritshuis"),
    (re.compile(r"Van Gogh Museum", re.I), "van-gogh"), (re.compile(r"Kr[öo]ller-M[üu]ller", re.I), "kroller-muller"),
    (re.compile(r"Kunsthistorisches Museum", re.I), "khm"), (re.compile(r"Belvedere", re.I), "belvedere"),
    (re.compile(r"Alte Nationalgalerie", re.I), "alte-nationalgalerie"),
    (re.compile(r"Gem[äa]ldegalerie, Berlin|Gem[äa]ldegalerie \(Berlin\)|Gem[äa]ldegalerie Berlin", re.I), "gemaldegalerie"),
    (re.compile(r"Neue Pinakothek", re.I), "neue-pinakothek"), (re.compile(r"St[äa]del", re.I), "stadel"),
    (re.compile(r"Nationalmuseum(?: Stockholm)?", re.I), "nationalmuseum"), (re.compile(r"Ateneum", re.I), "ateneum"),
    (re.compile(r"\bHermitage\b", re.I), "hermitage"),
    (re.compile(r"National Gallery of Art(?: \(Washington|, Washington)", re.I), "nga"),
    (re.compile(r"Rijksmuseum(?: Amsterdam)?$", re.I), "rijks"), (re.compile(r"Metropolitan Museum of Art", re.I), "met"),
]
_RIJKS_MET_NAMES = {"rijks": "Rijksmuseum, Amsterdam", "met": "The Metropolitan Museum of Art"}


def resolve_museum(cats):
    """(slug, museum name) from a file's categories, or (None, None) when no collection is named."""
    best = None
    for c in cats:
        for pat, slug in _MUSEUM_ALIAS:
            if pat.search(c):
                return slug, (COMMONS_MUSEUMS.get(slug) or (None, _RIJKS_MET_NAMES.get(slug)))[1]
        m = _MUSEUM_CAT.match(c)
        if m:
            name = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(1)).strip()  # "Galleria Palatina (Florence)" -> "Galleria Palatina"
            if _MUSEUM_WORD.search(name) and not _MUSEUM_SKIP.search(name) and 4 <= len(name) <= 70:
                if best is None or len(name) < len(best):  # "Mauritshuis" over "Mauritshuis in The Hague"
                    best = name
    return (None, best) if best else (None, None)


_INSTITUTION = re.compile(r"\|\s*(?:institution|gallery|museum|collection)\s*=\s*(.+)", re.I)
_TEMPLATE_INST = re.compile(r"\{\{\s*Institution:([^}|]+)")
_LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")


def institution_from_wikitext(pageid):
    """The Artwork template's institution field, read from the file page's wikitext, or None.
    One extra API call, used only when the file's categories name no collection."""
    d = commons({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "pageids": str(pageid)})
    pages = d.get("query", {}).get("pages", [])
    text = ((pages[0].get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content", "")) if pages else ""
    for m in _INSTITUTION.finditer(text):
        raw = m.group(1).split("\n")[0].strip()
        t = _TEMPLATE_INST.search(raw)
        name = t.group(1).strip() if t else _LINK.sub(r"\1", raw)
        name = re.sub(r"\{\{[^}]*\}\}|<[^>]+>|\|.*$", "", name).strip(" .,;")
        if name and _MUSEUM_WORD.search(name) and not _MUSEUM_SKIP.search(name) and 4 <= len(name) <= 70:
            slug = next((s for pat, s in _MUSEUM_ALIAS if pat.search(name)), None)
            return slug, ((COMMONS_MUSEUMS.get(slug) or (None, _RIJKS_MET_NAMES.get(slug)))[1] if slug else name)
    return None, None


PAINTERS = config.DATA / "painters.txt" if (config.DATA / "painters.txt").exists() \
    else config.BUNDLE / "data" / "painters.txt"   # one painter per line; "# ..." comments; walked without a cap


def painter_candidates(seen, slug, names, cap, cache_hours=72, max_cats=None):
    """Walk each painter's "Paintings by <name>" category (plus its "by museum" / "by year"
    children). `cap` bounds the files taken per painter (None = everything). Returns shuffled
    file pageids and remembers which painter each file belongs to."""
    cache = ROOT / "logs" / f"{slug}_candidates.json"
    files = None
    if cache.exists() and time.time() - cache.stat().st_mtime < cache_hours * 3600:
        files = {int(k): v for k, v in json.loads(cache.read_text(encoding="utf-8")).items()}
        print(f"  {slug}: {len(files)} image files from cache {cache.name}")
    if files is None:
        painters = list(names)
        files, hits, named = {}, 0, 0
        for i, name in enumerate(painters):
            root = f"Category:Paintings by {name}"
            todo, done, mine = [(root, 0)], set(), 0
            while todo and len(done) < (max_cats or WOMEN_MAX_CATS) and (cap is None or mine < cap):
                cat, lvl = todo.pop(0)
                if cat in done:
                    continue
                done.add(cat)
                try:
                    members = commons_members(cat)
                    hits = 0
                except Exception as exc:  # noqa: BLE001
                    if "429" in str(exc) or "403" in str(exc):
                        hits += 1
                        time.sleep(backoff_seconds(exc, hits))
                    continue
                time.sleep(DELAY)
                for m in members:
                    if m.get("ns") == 6 and m["title"].lower().endswith(IMAGE_EXT) and (cap is None or mine < cap):
                        files[m["pageid"]] = [m["title"], name]
                        mine += 1
                    elif m.get("ns") == 14 and lvl < 3 and not any(x.lower() in m["title"].lower() for x in WOMEN_SKIP_CATS):
                        todo.append((m["title"], lvl + 1))
            if mine:
                named += 1
            if (i + 1) % 25 == 0:
                print(f"  {slug}: {i + 1}/{len(painters)} painters walked, {named} with paintings, {len(files)} files", flush=True)
        print(f"  {slug}: {len(painters)} painters, {named} with a 'Paintings by' category, {len(files)} image files", flush=True)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(files, ensure_ascii=False), encoding="utf-8")
    _PAINTER_OF.update({pid: v[1] for pid, v in files.items()})
    seen_pids = {sid.rsplit("-", 1)[-1] for sid in seen}
    ids = [pid for pid in files if str(pid) not in seen_pids]
    random.shuffle(ids)
    _QUEUES[slug] = ids
    return ids


_PRIVATE = re.compile(r"private collection|collection particuli|privatsammlung|privébezit|particuliere collectie|colección particular|collezione privata", re.I)


def home_from_wikitext_fallback(pageid):
    """When no museum is named: 'Private collection' if the file says so, else None. One extra call
    at most, and the result is only a label line."""
    try:
        d = commons({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "pageids": str(pageid)})
        pages = d.get("query", {}).get("pages", [])
        text = ((pages[0].get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content", "")) if pages else ""
    except Exception:  # noqa: BLE001
        return None
    for m in _INSTITUTION.finditer(text):
        raw = m.group(1).split("\n")[0]
        if _PRIVATE.search(raw):
            return "Private collection"
    return None


def women_candidates(seen, cache_hours=72, max_painters=None):
    painters = json.loads(WOMEN.read_text(encoding="utf-8")) if WOMEN.exists() else []
    if max_painters:
        painters = painters[:max_painters]
    return painter_candidates(seen, "women", [p["name"] for p in painters], WOMEN_MAX_FILES, cache_hours, max_cats=40)


def requested_painters():
    """Names from data/painters.txt: one per line, blank lines and # comments ignored."""
    if not PAINTERS.exists():
        return []
    return [ln.strip() for ln in PAINTERS.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def painters_candidates(seen, cache_hours=72):
    return painter_candidates(seen, "painters", requested_painters(), None, cache_hours, max_cats=40)


def women_fetch(pageid):
    return commons_fetch(pageid, "women")


def painters_fetch(pageid):
    return commons_fetch(pageid, "painters")


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
TITLE_PAINTER = re.compile(r"\s+[–-]\s+([A-ZÀ-Ý][\wÀ-ÿ'.-]+(?: (?:d[aeiu]|van|der|den|von|le|la|du|de la)?\s?[A-ZÀ-Ý][\wÀ-ÿ'.-]+){1,3})\s*$")
PAINTER_CATS = [  # Commons category patterns that name the painter, most specific first
    re.compile(r"^Category:(?:\d{4}s? )?(?:paintings|works|portraits|landscapes|gardens|drawings) by (.+?)(?: in (?:the )?[^|]+| by .+)?$", re.I),
    re.compile(r"^Category:.+ (?:-|by) ([A-ZÀ-Ý][\wÀ-ÿ'.-]+(?: [\wÀ-ÿ'.-]+){1,4})$"),  # '<Title> - <Painter>' single-painting cats
]
FRAME_CATS = re.compile(r"framed paintings|painting frames|frames \(", re.I)
BOOK_SCAN = re.compile(r"\b(book scans?|scans? from|la peinture au louvre|publications?|catalogu|postcards?|plates? from|illustrations? from|\bp\.\s?\d+)\b", re.I)
PHOTO_DATE = re.compile(r"\b(19[3-9]\d|20\d\d)\b")  # public-domain painting pools end before 1930: a later year is the photo's date
# Files that live in a museum's Commons category without being a painting: stamps reproducing one, scanned
# catalogues and magazines, room photos, a frog cropped from a bull. Matched on title, artist and categories.
NON_PAINTING = re.compile(r"\b(stamps?|MiNr\s?\d|katalog|catalogue|catalog\b|magazine|обозр[еѣ]н|internet archive|book images|"
                          r"hidden treasures|carpets?, runners|interior \d+$|the \w+ from [A-Z][\w.' -]+ -)", re.I)
# Artist strings that name a photographer, a postal administration or a collection, never a painter.
NOT_A_PAINTER = re.compile(r"\bon stamps\b|postal administration|internet archive|unknown author|^room \d|^painting by |"
                           r" in the (?:mauritshuis|louvre|rijksmuseum|museum)\b|^[A-Z]\.\s?[A-Z][a-z]+ / ", re.I)  # 'G.Blot / H. Lewandowski' are photographers
_INVENTORY = re.compile(r"[,\s-]*\b(?:(?:RF|MI|INV\.?|MO RF|MAO|MNH)\s?\d[\d\s.-]*[a-z]?|SK-[A-Z]-?\d+|[sd]\d{4}[A-Z]\d{4}[a-z]?)(?=[\s,.-]|$)", re.I)
# A museum or city name is dropped only when it sits at an edge: start, end, or against a separator or a number.
_MUSEUM_NAMES = (r"Mus[ée]e d'Orsay(?: Parijs| Paris)?|Mus[ée]e Marmottan Monet|Van Gogh Museum|Mauritshuis|Louvre(?: museum)?|"
                 r"National Gallery|Neue Pinakothek|Hermitage(?: Museum)?(?: Saint Petersburg)?")
_MUSEUM_WORDS = re.compile(r"(?<![\w'])(?:%s)(?=\s*(?:[-–,.;]|\d+\b|$))" % _MUSEUM_NAMES, re.I)
_CITY_WORDS = re.compile(r"(?:^|[-–,;]\s*)(?:Paris|Parijs|Den Haag|The Hague|Saint Petersburg|MN)(?=\s*(?:[-–,.;]|$))", re.I)
_PHOTO_STAMP = re.compile(r"\b\d{1,2}-\d{1,2}-20\d\d(?:\s\d{1,2}-\d{2}-\d{2})?\b|\b(?:January|February|March|April|May|June|July|"
                          r"August|September|October|November|December) 20\d\d\b", re.I)
_LIFE_DATES = re.compile(r"\s*\(\s*\d{4}\s*[–-]\s*\d{4}\s*\)\)?")
_TRAILING_COUNTER = re.compile(r"(?:[\s,]+\d{1,3}|\s+\(\d{1,3}\)|\s+\(\d{5,}\))$")
_APRES = re.compile(r"[,\s-]*\bD'apr[èe]s\b[,\s-]*", re.I)


def clean_title(title, artist="", museum=""):
    """Turn a Commons file name into a label. Removes the painter (leading 'Vallotton - ', trailing ' - Félix Vallotton',
    ', par X', ' by X'), the museum and city at the edges, inventory numbers (RF 2012 19, MI 734, s0275V1962r), photo dates
    and life dates, trailing counters, and 'D'après' (kept as '(after X)'). Shouting titles are lowered. Never empty."""
    t = title
    after = bool(_APRES.search(t))
    t = _APRES.sub(" ", t)
    t = _LIFE_DATES.sub("", t)
    t = re.sub(r"\s*\((?:1[0-9]{3}|20\d\d)\)\s*$", "", t)  # 'Isaac Israëls (1925)'
    t = _PHOTO_STAMP.sub(" ", t)
    t = _INVENTORY.sub(" ", t)
    t = _MUSEUM_WORDS.sub(" ", t)
    t = _CITY_WORDS.sub(" ", t)
    t = re.sub(r",\s*(?:19[3-9]\d|20\d\d)\s*$", "", t)  # 'Attack on a Woman, 1810 – 1812, 1980': the last is the inventory year
    t = re.sub(r"\s+(?:[3-9]\d{3}|2[1-9]\d\d)\s*$", "", t)  # 'Japanese Bridge 5077': a bare number that cannot be a year
    t = _TRAILING_COUNTER.sub("", t)
    if artist and artist != "Unknown artist":
        parts = [p for p in re.split(r"[\s,.]+", artist) if len(p) > 2 and p[0].isupper()]
        surname = parts[-1] if parts else ""
        full = re.escape(artist)
        names = [full]
        for sn in {surname, surname.split("-")[-1]} - {""}:  # 'Bastien-Lepage' and 'Lepage'
            names.append(re.escape(sn) + r"(?:,\s*[A-Z][\w-]+)?")  # 'Bouts' or 'Bouts, Dirck'
            names.append(r"[A-Z][\w-]+[- ]" + re.escape(sn))  # 'Jules-Bastien Lepage', 'Toulouse-Lautrec'
        alt = "|".join(names)
        t = re.sub(r"^\s*(?:%s)\s*[.:,]?\s*(?:[–-]\s*)?(?=[A-Z])" % alt, "", t, flags=re.I)  # 'Vallotton - Verdun', 'Jan steen, la visita'
        t = re.sub(r"^\s*(?:%s)\s*,\s*" % alt, "", t, flags=re.I)  # 'Jan steen, la visita del dottore'
        t = re.sub(r",?\s+(?:par|by|door)\s+(?:%s)\b[,.]?" % alt, "", t)  # 'L'Avocat, par Paul Cézanne'
        t = re.sub(r"\s*[–-]\s*(?:%s)\s*(?=[–-]|$)" % alt, " ", t)  # 'The Boat - Odilon Redon - 1898'
        t = re.sub(r",?\s+(?:de|von|van)\s+%s\b[,.]?" % full, "", t)  # 'Arbre en fleurs de Gustave Caillebotte' (full name only)
        t = re.sub(r"\s*[.:,]\s*(?:%s)\s*$" % alt, "", t)  # 'Play Lyra. Louis de Boullogne', 'Bonger, Isaac Israëls'
        t = re.sub(r"^\s*(?:%s)\s+(?=[A-Z])" % alt, "", t)  # 'Champaigne Translation des reliques'
    t = re.sub(r"\s*[–-]\s*(?:[–-]\s*)+", " - ", t)
    t = _TRAILING_COUNTER.sub("", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–,.:;")
    if t.count(")") > t.count("("):
        t = t.rstrip(")").rstrip()
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) > 0.8 * len(letters):
        t = ". ".join(s.strip().capitalize() for s in t.split(".") if s.strip())
    elif t and t[0].islower():
        t = t[0].upper() + t[1:]
    if after and artist:
        t = f"{t} (after {artist})"
    return t or title.strip()


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


def orsay_artist(page, ii, trust_artist_field=True):
    """Painter name. Order: a curated 'paintings by X' category, then extmetadata Artist (unless it is an
    uploader handle, or the file is a CC photo where Artist names the photographer), then looser categories,
    then a '<Title> - <Painter>' file name."""
    cats = [c.get("title", "") for c in page.get("categories", []) or []]
    for c in cats:
        m = PAINTER_CATS[0].match(c)
        if m and not USERNAME_LIKE.match(m.group(1)):
            return m.group(1)
    artist = pick_language(_meta(ii, "Artist")) if trust_artist_field else ""
    artist = re.split(r"\s+[–-]\s+(?:Painter|Peintre|Maler)\b|\bDetails on\b|\(\d{4}\s*[–-]\s*\d{4}\)", artist)[0]
    artist = re.sub(r"\s*\(.*?\)\s*$", "", artist).strip(" -–,")[:120]
    if NOT_A_PAINTER.search(artist):
        artist = re.sub(r"^painting by\s+| in the \w+$", "", artist, flags=re.I) if artist.lower().startswith("painting by") else ""
    if artist and not USERNAME_LIKE.match(artist) and not artist.lower().startswith(("unknown", "anonym")):
        return artist
    for pat in PAINTER_CATS[1:]:
        for c in cats:
            m = pat.match(c)
            if m and not USERNAME_LIKE.match(m.group(1)):
                return m.group(1)
    if artist.lower().startswith(("unknown", "anonym")):
        return "Unknown artist"
    m = TITLE_PAINTER.search(orsay_title(page, ii))  # 'Girl Carrying Water - Jean-François Millet'
    if m:
        return m.group(1)
    return None  # a bare handle or a Wikidata id and no painter category: we cannot name the painter


def orsay_date(ii):
    d = _meta(ii, "DateTimeOriginal")
    d = re.split(r"\bdate QS:", d)[0].strip()
    return "" if PHOTO_DATE.search(d) else d[:60]


def commons_fetch(pageid, slug="orsay"):
    women = slug == "women"
    by_painter = slug in ("women", "painters")
    museum = None if by_painter else COMMONS_MUSEUMS[slug][1]
    page, ii = _imageinfo(pageid, slug)
    if not ii:
        return None
    if by_painter:
        cat_titles = [c.get("title", "") for c in page.get("categories", []) or []]
        mslug, museum = resolve_museum(cat_titles)
        if not museum:
            time.sleep(DELAY)
            mslug, museum = institution_from_wikitext(pageid)
        if not museum:
            museum = home_from_wikitext_fallback(pageid)  # "Private collection", a city, or None: the label line stays empty
        slug = mslug or "commons"
    lic = _meta(ii, "LicenseShortName")
    cc_only = not PD_LICENCE.search(lic) and bool(CC_LICENCE.search(lic))
    if not PD_LICENCE.search(lic) and not (ALLOW_CC and cc_only):
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
    if title.rstrip().endswith(("...", "…")) or BOOK_SCAN.search(cats) or BOOK_SCAN.search(page["title"]):
        return None  # a scan from a book or album, not the painting
    raw_artist = pick_language(_meta(ii, "Artist"))
    if NON_PAINTING.search(title) or NON_PAINTING.search(cats) or NON_PAINTING.search(raw_artist) \
            or re.search(r"\((?:19[3-9]\d|20\d\d)\)\s*$", title):
        print(f"  notart {slug}-{pageid} {title[:40]}")
        return None  # a stamp, a catalogue page, a room photo, or a painting too recent to be public domain
    artist = _PAINTER_OF.get(pageid) if women else None  # the category that listed the file names the painter
    artist = artist or orsay_artist(page, ii, trust_artist_field=not cc_only)
    if artist is None or NOT_A_PAINTER.search(artist):
        print(f"  noname {slug}-{pageid} {title[:40]}")
        return None
    title = re.sub(r"^WLANL\s+-\s+[^-]+-\s+", "", title)  # Wiki Loves Art NL files start with the photographer
    title = clean_title(title, artist, museum)
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
    if women:
        entry["gender"] = "f"
    if len(desc) > 60 and desc.lower() != title.lower() and " " in desc:
        entry["story"] = trim_story(desc)
    if cc_only:  # kept on this machine only: data/paintings.local.json, never committed
        entry["local"] = True
        entry["licence"] = lic
        entry["credit"] = _meta(ii, "Attribution") or pick_language(_meta(ii, "Artist")) or _meta(ii, "Credit")
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
                         "'commons' for all Commons museums, 'women' (paintings by women painters, data/women_painters.json), "
                         "'all' (default, round-robin over everything), or a comma list")
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--allow-cc", action="store_true",
                    help="also keep CC BY-licensed files, in data/paintings.local.json (git-ignored, this machine only)")
    args = ap.parse_args(argv if argv is not None else [])
    if target is not None: args.target = target
    if source is not None: args.source = source
    if delay is not None: args.delay = delay
    DELAY = args.delay
    global ALLOW_CC
    ALLOW_CC = args.allow_cc
    source = "all" if args.source == "both" else args.source.lower()
    wanted = set(source.split(","))  # "met,orsay,prado": several sources, round-robin
    def want(*names):
        return bool(wanted & {*names, "all"})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    existing += json.loads(LOCAL.read_text(encoding="utf-8")) if LOCAL.exists() else []
    seen = {e["id"] for e in existing}
    print(f"existing: {len(existing)}  target: {args.target}" + ("  (CC BY allowed, local only)" if ALLOW_CC else ""))

    def save():
        OUT.write_text(json.dumps([e for e in existing if not e.get("local")], ensure_ascii=False), encoding="utf-8")
        local = [e for e in existing if e.get("local")]
        if local:
            LOCAL.write_text(json.dumps(local, ensure_ascii=False), encoding="utf-8")

    queues = []
    if want("met"):
        queues.append(("met", met_candidates(seen), met_fetch))
    if want("rijks"):
        queues.append(("rijks", rijks_candidates(seen), rijks_fetch))
    for slug in COMMONS_MUSEUMS:
        if want(slug, "commons"):
            queues.append((slug, commons_candidates(seen, slug), functools.partial(commons_fetch, slug=slug)))
    if want("women") and WOMEN.exists():
        queues.append(("women", women_candidates(seen), women_fetch))
    if want("painters") and requested_painters():
        queues.append(("painters", painters_candidates(seen), painters_fetch))
    if not queues:
        ap.error(f"unknown source {source!r}")
    print("candidates: " + ", ".join(f"{n}={len(q)}" for n, q, _ in queues))

    processed = added = hits = 0
    while len(existing) < args.target and any(q for _, q, _ in queues):
        for name, q, fetch in queues:  # round-robin so the museums grow together
            if not q or len(existing) >= args.target:
                continue
            cid = q.pop()
            processed += 1
            try:
                entry = fetch(cid)
                hits = 0
            except Exception as exc:  # noqa: BLE001
                print(f"  skip   {name} {cid}: {exc}", file=sys.stderr)
                if "403" in str(exc) or "429" in str(exc):
                    hits += 1
                    wait = backoff_seconds(exc, hits)
                    print(f"  rate-limited ({hits} in a row), sleeping {wait}s", file=sys.stderr)
                    time.sleep(wait)
                continue
            if entry:
                existing.append(entry)
                seen.add(entry["id"])
                added += 1
            if processed % 20 == 0:
                save()
                print(f"  {processed} processed, {added} added, index={len(existing)}")
    save()
    print(f"done: {len(existing)} paintings in {OUT}" + (f" + {LOCAL.name}" if LOCAL.exists() else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
