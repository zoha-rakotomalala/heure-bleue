"""One-time repair of Commons entries indexed before clean_title and the non-painting gate existed.
Usage: python3 tools/repair_titles.py data/paintings.json [data/paintings.local.json ...]"""
import json
import re
import sys

sys.path.insert(0, ".")
from heurebleue.indexer import NON_PAINTING, NOT_A_PAINTER, clean_title  # noqa: E402

DROP = {  # id -> why
    "louvre-118088267": "stamp", "louvre-110184197": "stamp", "louvre-115861510": "stamp", "louvre-169957770": "stamp",
    "louvre-78682932": "stamp", "louvre-78682216": "stamp", "orsay-56360135": "magazine page", "orsay-43960774": "book page",
    "neue-pinakothek-138727998": "catalogue page", "neue-pinakothek-138728217": "catalogue page",
    "national-gallery-42684221": "book page", "mauritshuis-41864206": "book page", "mauritshuis-123095735": "detail (frog)",
    "mauritshuis-66009416": "room photo", "hermitage-158226538": "1967 painting, not public domain",
}
RECREDIT = {  # id -> (painter, title or None to keep the cleaned one)
    "orsay-114554936": ("Antoine Vollon", "Espagnol"), "orsay-61920600": ("Paul Gauguin", "Autoportrait"),
    "orsay-35062551": ("Alfred Roll", None), "orsay-180821769": ("Johan Barthold Jongkind", "La Seine à Argenteuil"),
    "neue-pinakothek-54572093": ("Willem Maris", "Polder Landscape with Cattle"), "van-gogh-121429123": ("Odilon Redon", "The Boat"),
    "mauritshuis-45782834": ("Rembrandt van Rijn", None), "mauritshuis-86338339": ("Rembrandt van Rijn", None),
    "louvre-70090899": ("Sani al-Molk", "Animal studies"), "mauritshuis-179923660": ("Frans Hals", "Portrait of a man"),
}

for path in sys.argv[1:]:
    doc = json.loads(open(path, encoding="utf-8").read())
    items = doc["paintings"] if isinstance(doc, dict) else doc
    kept, dropped, retitled, recredited = [], [], 0, 0
    for p in items:
        if p["id"] in DROP:
            dropped.append((p["id"], DROP[p["id"]], p["title"][:50])); continue
        if p["id"].startswith(("met-", "rijks-")):
            kept.append(p); continue
        if p["id"] in RECREDIT:
            artist, title = RECREDIT[p["id"]]
            p["artist"] = artist
            if title:
                p["title"] = title
            recredited += 1
        elif NON_PAINTING.search(p["title"]) or NOT_A_PAINTER.search(p["artist"]):
            dropped.append((p["id"], "gate", p["title"][:50])); continue
        new = clean_title(p["title"], p["artist"], p.get("museum", ""))
        if new != p["title"]:
            p["title"] = new; retitled += 1
        kept.append(p)
    if isinstance(doc, dict):
        doc["paintings"] = kept
    else:
        doc = kept
    open(path, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(f"{path}: {len(items)} -> {len(kept)}  dropped={len(dropped)} retitled={retitled} recredited={recredited}")
    for d in dropped:
        print("  drop", *d)
