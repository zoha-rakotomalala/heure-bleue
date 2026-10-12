"""Clean the painting index: drop what is not a painting, repair file-like titles, merge duplicates.

Re-runnable after any indexing pass:  python3 tools/clean_index.py data/paintings.json [data/paintings.local.json]

What it does, in order:
  1. DROP   hand-checked ids: objects that are not paintings (a thangka, a Bodhisattva, ceiling putti, a harpsichord
            lid), copies and sketches, scanned pages and stamps, a photo of an altar, and files whose only title is a
            catalogue number (Monet "W777") that this tool cannot resolve to a real title.
  2. GATES  the indexer's own filters, re-applied to entries indexed before they existed.
  3. FIX    hand-checked titles, painters and dates for files named like "Berthe morisot 1890 Dans le pommier".
  4. DEDUPE the same painting uploaded twice to Commons (same museum, same painter, same title, same proportions):
            keep the entry with the larger image; a series with one title for several panels is kept whole.
  5. TITLES clean_title again (idempotent), so later indexer improvements reach old entries.
"""
import json
import re
import sys

sys.path.insert(0, ".")
from heurebleue.indexer import NON_PAINTING, NOT_A_PAINTER, clean_title  # noqa: E402

DROP = {  # id -> why
    # scans, stamps and photos that are not the painting
    "louvre-118088267": "stamp", "louvre-110184197": "stamp", "louvre-115861510": "stamp", "louvre-169957770": "stamp",
    "louvre-78682932": "stamp", "louvre-78682216": "stamp", "orsay-56360135": "magazine page", "orsay-43960774": "book page",
    "neue-pinakothek-138727998": "catalogue page", "neue-pinakothek-138728217": "catalogue page",
    "national-gallery-42684221": "book page", "mauritshuis-41864206": "book page", "mauritshuis-123095735": "detail (frog)",
    "mauritshuis-66009416": "room photo", "hermitage-158226538": "1967 painting, not public domain",
    "stadel-12353466": "photo of an altar, credited to the photographer",
    "louvre-128678613": "an etching after a miniature, not a painting",
    # objects that are not easel paintings
    "rijks-20024394": "thangka", "rijks-20024354": "Bodhisattva (scroll)", "rijks-200108353": "harpsichord lid",
    "rijks-20025915": "ceiling putti", "mauritshuis-72951531": "ceiling putti", "mauritshuis-76623455": "putti, manner of",
    # copies and sketches
    "rijks-200107938": "copy of the Night Watch", "prado-116431924": "copy (Copia)",
    "louvre-128638595": "copy after Bouts", "louvre-120390700": "copy after Fra Angelico",
    "orsay-110342528": "esquisse", "marmottan-15260661": "study", "stadel-131888297": "nude study (Aktstudie)",
    "ateneum-163939003": "yard study", "van-gogh-7147722": "study for a painting",
    # a Wildenstein number is not a title (W883, Dolceacqua, is resolved in FIX instead)
    "marmottan-130162325": "titled W777 only", "marmottan-135569684": "titled W1875 only", "marmottan-130241472": "titled W847 only",
}

FIX = {  # id -> {"title"/"artist"/"date": value}; only the keys given change
    "orsay-114554936": {"artist": "Antoine Vollon", "title": "Espagnol"}, "orsay-61920600": {"artist": "Paul Gauguin", "title": "Autoportrait"},
    "orsay-35062551": {"artist": "Alfred Roll"}, "orsay-180821769": {"artist": "Johan Barthold Jongkind", "title": "La Seine à Argenteuil"},
    "neue-pinakothek-54572093": {"artist": "Willem Maris", "title": "Polder Landscape with Cattle"},
    "van-gogh-121429123": {"artist": "Odilon Redon", "title": "The Boat"},
    "mauritshuis-45782834": {"artist": "Rembrandt van Rijn"}, "mauritshuis-86338339": {"artist": "Rembrandt van Rijn"},
    "louvre-70090899": {"artist": "Sani al-Molk", "title": "Animal studies"}, "mauritshuis-179923660": {"artist": "Frans Hals", "title": "Portrait of a man"},
    "orsay-149061627": {"title": "Le Pin parasol, Le Brusc", "date": "1911"},
    "orsay-52033950": {"title": "Vase bleu"},
    "marmottan-120751117": {"title": "Six têtes de garçonnets et fleurs", "date": "1770"},
    "marmottan-120751035": {"title": "La Balançoire"},
    "marmottan-88441536": {"title": "Jeune fille accoudée", "date": "1887"},
    "marmottan-176669471": {"title": "Dans le pommier", "date": "1890"},
    "marmottan-30816196": {"title": "Champ de tulipes en Hollande", "date": "1886"},
    "louvre-139083950": {"title": "Vaisseaux hollandais sur une mer agitée", "date": "vers 1690"},
    "louvre-126640008": {"title": "La Vierge à l'Enfant en gloire avec saint Antoine abbé et sainte Lucie"},
    "louvre-116440736": {"title": "La Vierge de douleur", "artist": "Workshop of Dieric Bouts"},
    "louvre-120390712": {"title": "Le Christ bénissant"},
    "stadel-27300362": {"title": "Landscape by a River", "date": "1889"},
    "national-gallery-39203733": {"title": "Portrait of a Man"},
    "national-gallery-80992311": {"title": "The Adoration of the Kings", "artist": "Workshop of Giovanni Bellini"},
    "van-gogh-186326886": {"title": "Pêcheur sur un bateau", "date": "circa 1885"},
    "van-gogh-186544621": {"title": "Portrait d'une jeune femme", "date": "1887"},
    "orsay-87112585": {"title": "Le Salon aux trois lampes, rue Saint-Florentin", "date": "1899"},
    "orsay-17883630": {"title": "Madeleine au Bois d'Amour", "date": "1888"},
    "orsay-161320315": {"title": "Cuirassiers au cabaret", "date": "1875"},
    "orsay-47347031": {"title": "Femme étendant du linge", "date": "1887"},
    "orsay-83765758": {"title": "L'Enlèvement d'Europe", "date": "vers 1869"},
    "orsay-33466378": {"title": "The Mellerio Family", "date": "1897"},
    "orsay-125751437": {"title": "Descente de croix", "date": "1852-1855"},
    "orsay-83765654": {"title": "L'Apparition", "date": "1876"},
    "orsay-21880419": {"title": "Une rue de Paris en mai 1871"},
    "orsay-114216773": {"title": "Branche de pommier en fleurs", "date": "1872"},
    "orsay-47403472": {"title": "Yvette Guilbert", "date": "vers 1899"},
    "van-gogh-187549666": {"title": "Idyll in Asnières", "date": "1888"},
    "van-gogh-187560310": {"title": "Horseman (Constantinople series)", "date": "1893"},
    "van-gogh-187542633": {"title": "Avenue in Brittany with Figures", "date": "1888"},
    "van-gogh-187561204": {"title": "Woman in a Graveyard (Constantinople series)", "date": "1893"},
    "van-gogh-64196338": {"title": "View of Montigny-sur-Loing", "date": "1864"},
    "van-gogh-187605141": {"title": "Figures by the Riverside", "date": "1888"},
    "van-gogh-187605335": {"title": "Pasture with Figures and Animals", "date": "1888"},
    "van-gogh-187605620": {"title": "Breton Woman with a Parasol", "date": "1888"},
    "van-gogh-186358340": {"title": "Portrait d'Andries et Annie Bonger avec l'artiste", "date": "1908"},
    "van-gogh-187561624": {"title": "Woman with Child on Back in a Graveyard (Constantinople series)", "date": "1893"},
    "van-gogh-187562419": {"title": "Women in a Graveyard (Constantinople series)", "date": "1893"},
    "stadel-102627533": {"title": "Attack on a Woman", "date": "1810-1812"},
    "khm-77744268": {"title": "Auf dem Heimweg von der Weltausstellung im Wiener Prater", "date": "1873"},
    "belvedere-69985253": {"title": "Erste Promotion zum Militär-Maria-Theresien-Orden 1758"},
    "mauritshuis-8172169": {"title": "Portrait of Steven van Herwijck"},
    "marmottan-130470521": {"title": "Le Château de Dolceacqua", "date": "1884"},
    "orsay-147069044": {"title": "A Modern Olympia (after Cézanne)", "date": "before 1909"},
}
SERIES = re.compile(r"\bseries\b|\bone of\b", re.I)  # panels that share one title are different paintings


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def clean(items, favorites=()):
    """favorites: ids the user kept; among duplicates the kept one survives."""
    kept, dropped, fixed, retitled = [], [], 0, 0
    for p in items:
        if p["id"] in DROP:
            dropped.append((p["id"], DROP[p["id"]], p["title"][:50]))
            continue
        if p["id"] in FIX:
            p.update(FIX[p["id"]])
            fixed += 1
        if not p["id"].startswith(("met-", "rijks-")):
            if NON_PAINTING.search(p["title"]) or NOT_A_PAINTER.search(p["artist"]):
                dropped.append((p["id"], "gate", p["title"][:50]))
                continue
            if p["id"] not in FIX:
                new = clean_title(p["title"], p["artist"], p.get("museum", ""))
                if new != p["title"]:
                    p["title"] = new
                    retitled += 1
        kept.append(p)
    # duplicates: same museum, same named painter, same title, same proportions (±4 %)
    groups = {}
    for p in kept:
        if p["artist"].lower() in ("unknown artist", "anonymous", "anoniem") or SERIES.search(p["title"]):
            continue
        groups.setdefault((p["museum"], p["artist"], norm(p["title"])), []).append(p)
    gone = set()
    for g in groups.values():
        g.sort(key=lambda p: (p["id"] not in favorites, -(p.get("w", 0) * p.get("h", 0))))
        for a in g:
            if a["id"] in gone:
                continue
            for b in g:
                if b is a or b["id"] in gone:
                    continue
                ra, rb = a.get("w", 1) / max(1, a.get("h", 1)), b.get("w", 1) / max(1, b.get("h", 1))
                if abs(ra - rb) <= 0.04 * max(ra, rb):
                    gone.add(b["id"])
                    dropped.append((b["id"], f"duplicate of {a['id']}", b["title"][:50]))
    kept = [p for p in kept if p["id"] not in gone]
    return kept, dropped, fixed, retitled


def main(argv):
    favorites = set()
    paths = []
    it = iter(argv)
    for a in it:
        if a == "--favorites":  # the wall's favorites.json: a kept duplicate is the one that survives
            favorites = {f["id"] for f in json.loads(open(next(it), encoding="utf-8").read())}
        else:
            paths.append(a)
    for path in paths or ["data/paintings.json"]:
        doc = json.loads(open(path, encoding="utf-8").read())
        items = doc["paintings"] if isinstance(doc, dict) else doc
        kept, dropped, fixed, retitled = clean(items, favorites)
        if isinstance(doc, dict):
            doc["paintings"] = kept
        else:
            doc = kept
        open(path, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False) + "\n")
        print(f"{path}: {len(items)} -> {len(kept)}  dropped={len(dropped)} fixed={fixed} retitled={retitled}")
        for d in dropped:
            print("  drop", *d)


if __name__ == "__main__":
    main(sys.argv[1:])
