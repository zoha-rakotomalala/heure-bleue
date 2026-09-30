#!/usr/bin/env python3
"""Add a ``story`` (description text) to the Rijksmuseum entries in data/paintings.json.

For every entry whose id starts with ``rijks-`` the Linked Art record is re-read
(https://id.rijksmuseum.nl/<id>, Accept: application/ld+json) and the description
is stored as ``story`` (<= ~600 chars, cut at a sentence end). English is
preferred; when only a Dutch description exists it is stored with
``story_lang: "nl"`` so the display can decide what to do with it. Entries with
no description are left untouched. Writes are periodic and the run is resumable:
entries that already have a story are skipped unless --force is given.

Usage: python3 add_stories.py [--force] [--delay 0.8]
"""
import argparse
import json
import sys
import time
from pathlib import Path

from . import indexer
from .indexer import OUT, get_json, rijks_story, with_story


def main(force=False, argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-fetch entries that already have a story")
    ap.add_argument("--delay", type=float, default=0.8)
    args = ap.parse_args(argv if argv is not None else [])
    if force: args.force = True
    indexer.DELAY = args.delay

    idx = json.loads(OUT.read_text(encoding="utf-8"))
    todo = [p for p in idx if p["id"].startswith("rijks-") and (args.force or "story" not in p)]
    print(f"{len(idx)} entries, {len(todo)} rijks entries to check")
    added = none = failed = 0
    for n, p in enumerate(todo, 1):
        try:
            o = get_json(f"https://id.rijksmuseum.nl/{p['id'][6:]}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  skip   {p['id']}: {exc}", file=sys.stderr)
            if "403" in str(exc) or "429" in str(exc):
                print("  rate-limited, sleeping 90s", file=sys.stderr)
                time.sleep(90)
            continue
        text, lang = rijks_story(o)
        if text:
            with_story(p, text, lang)
            added += 1
            print(f"  story  {p['id']} [{lang}] {text[:60]}")
        else:
            none += 1
        if n % 25 == 0:
            OUT.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
            print(f"  {n}/{len(todo)} checked, {added} stories")
    OUT.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    langs = {}
    for p in idx:
        if "story" in p:
            langs[p.get("story_lang", "en")] = langs.get(p.get("story_lang", "en"), 0) + 1
    print(f"done: {added} stories added, {none} without description, {failed} fetch failures; "
          f"stories in index by language: {langs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
