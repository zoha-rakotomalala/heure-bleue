#!/usr/bin/env python3
"""Titles in a non-Latin script (Cyrillic, CJK, Greek, Arabic...) get an English title; the
original is kept as `title_orig` so nothing is lost and the cartel can show both one day.

    python3 tools/translate_titles.py extract data/paintings.json > logs/titles_nonlatin.json
        -> [{"id", "title", "artist", "museum", "date"}] for every entry whose title is mostly non-Latin

    python3 tools/translate_titles.py apply data/paintings.json logs/titles_en.json
        -> titles_en.json is {"<id>": "<English title>" | "DROP"}. "DROP" removes the entry
           (used for files whose title names a different painter than the one credited).
           Entries not in the file are left alone. Prints what changed.

Translation itself is done by hand (or by whoever edits titles_en.json): the list is short
(tens of titles), and painting titles want a reader, not a machine.
"""
import json
import sys
import unicodedata
from pathlib import Path


def mostly_non_latin(text, threshold=0.4):
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    non_latin = sum(1 for ch in letters if not unicodedata.name(ch, "").startswith("LATIN"))
    return non_latin / len(letters) > threshold


def extract(index_path):
    entries = json.loads(Path(index_path).read_text(encoding="utf-8"))
    out = [{"id": e["id"], "title": e["title"], "artist": e.get("artist"), "museum": e.get("museum"), "date": e.get("date")}
           for e in entries if mostly_non_latin(e.get("title", ""))]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print(file=sys.stdout)
    print(f"{len(out)} non-Latin titles of {len(entries)}", file=sys.stderr)


def apply(index_path, translations_path):
    index_path = Path(index_path)
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    tr = json.loads(Path(translations_path).read_text(encoding="utf-8"))
    kept, changed, dropped = [], 0, 0
    for e in entries:
        new = tr.get(e["id"])
        if new is None:
            kept.append(e)
            continue
        if new == "DROP":
            dropped += 1
            print(f"  drop   {e['id']}  {e['title'][:50]}")
            continue
        if new != e["title"]:
            e.setdefault("title_orig", e["title"])
            print(f"  {e['id']}  {e['title'][:40]!r} -> {new!r}")
            e["title"] = new
            changed += 1
        kept.append(e)
    index_path.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    print(f"{changed} titles translated, {dropped} entries dropped, {len(kept)} remain")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "extract":
        extract(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "apply":
        apply(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        raise SystemExit(2)
