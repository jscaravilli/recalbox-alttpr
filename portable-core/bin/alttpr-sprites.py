#!/usr/bin/env python3
"""Fetch the full official ALTTPR sprite set and (re)build the menu manifest.

The Custom Seed menu's sprite picker shows friendly names from
``bin/sprites.json`` (name/file/author/tags). The randomizer app bundles only a
handful of ``.zspr`` sprites; this script pulls the complete official list from
alttpr.com and downloads any missing ``.zspr`` into the app's sprite directory,
then writes the manifest the menu reads.

It is safe to re-run: existing sprites are skipped and the manifest is rebuilt
from whatever is present on disk. Requires internet the first time only.

    usage: alttpr-sprites.py [--sprite-dir DIR] [--manifest OUT] [--list-url URL]

Defaults target the on-Pi engine layout.
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import urllib.request

ENGINE = "/recalbox/share/alttpr"
DEF_DIR = ENGINE + "/sprites"
DEF_MANIFEST = ENGINE + "/bin/data/sprites.json"
DEF_PREVIEW_DIR = ENGINE + "/bin/sprite-previews"
DEF_URL = "https://alttpr.com/sprites"


def basename(url):
    return url.rsplit("/", 1)[-1]


def _download_set(items, workers=16, minbytes=50):
    """items: list of (url, dest_path). Returns (ok_count, failures)."""
    ok = [0]
    fail = []

    def get(item):
        url, dst = item
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) < minbytes:
                raise ValueError("suspiciously small (%d bytes)" % len(data))
            tmp = dst + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dst)
            ok[0] += 1
        except Exception as e:  # noqa: BLE001
            fail.append((os.path.basename(dst), str(e)[:80]))

    if items:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(get, items))
    return ok[0], fail


def download_previews(entries, preview_dir, workers=16):
    """Download each sprite's static preview PNG into preview_dir.

    Named <zspr-basename>.png (e.g. abigail.1.png) so the menu can find it from
    the manifest's ``file`` field. Skips ones already present.
    """
    os.makedirs(preview_dir, exist_ok=True)
    todo = []
    for e in entries:
        url = e.get("preview")
        if not url:
            continue
        fn = basename(e["file"])
        stem = fn[:-5] if fn.endswith(".zspr") else fn
        dst = os.path.join(preview_dir, stem + ".png")
        if not os.path.exists(dst):
            todo.append((url, dst))
    got, fail = _download_set(todo, workers=workers, minbytes=40)
    return got, fail, len(todo)


def fetch_list(url):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    data = urllib.request.urlopen(req, timeout=30).read()
    return json.loads(data.decode("utf-8", "replace"))


def download_missing(entries, sprite_dir, workers=16):
    os.makedirs(sprite_dir, exist_ok=True)
    missing = []
    for e in entries:
        fn = basename(e["file"])
        if not os.path.exists(os.path.join(sprite_dir, fn)):
            missing.append((e["file"], fn))
    ok = [0]
    fail = []

    def get(item):
        url, fn = item
        dst = os.path.join(sprite_dir, fn)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) < 50:
                raise ValueError("suspiciously small (%d bytes)" % len(data))
            tmp = dst + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dst)
            ok[0] += 1
        except Exception as e:  # noqa: BLE001
            fail.append((fn, str(e)[:80]))

    if missing:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(get, missing))
    return ok[0], fail, len(missing)


def build_manifest(entries, sprite_dir, out_path, preview_dir=None):
    try:
        present = set(os.listdir(sprite_dir))
    except OSError:
        present = set()
    previews = set()
    if preview_dir:
        try:
            previews = set(os.listdir(preview_dir))
        except OSError:
            previews = set()
    items = []
    seen = {}
    for e in entries:
        fn = basename(e["file"])
        if present and fn not in present:
            continue
        filebase = fn[:-5] if fn.endswith(".zspr") else fn
        name = (e.get("name") or filebase).strip()
        author = (e.get("author") or "").strip()
        key = name.lower()
        if key in seen:
            name = "%s (%s)" % (name, author or filebase)
        seen[key] = 1
        entry = {"name": name, "file": filebase, "author": author}
        # only advertise a preview when the PNG is actually on disk
        if (filebase + ".png") in previews:
            entry["preview"] = filebase + ".png"
        items.append(entry)
    items.sort(key=lambda d: d["name"].lower())
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=0)
        f.write("\n")
    return len(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprite-dir", default=DEF_DIR)
    ap.add_argument("--manifest", default=DEF_MANIFEST)
    ap.add_argument("--preview-dir", default=DEF_PREVIEW_DIR)
    ap.add_argument("--list-url", default=DEF_URL)
    ap.add_argument("--no-previews", action="store_true",
                    help="skip downloading the static preview PNGs")
    ap.add_argument("--offline", action="store_true",
                    help="skip download; just rebuild the manifest from disk")
    args = ap.parse_args()

    entries = None
    if not args.offline:
        try:
            entries = fetch_list(args.list_url)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write("could not fetch sprite list: %s\n" % e)
    if entries is None:
        # offline / fetch failed: rebuild manifest from any cached list if we
        # have one next to the manifest, else nothing to do.
        cache = args.manifest + ".src"
        if os.path.isfile(cache):
            entries = json.load(open(cache, encoding="utf-8"))
        else:
            sys.stderr.write("no sprite list available; nothing to do\n")
            return 1

    # cache the raw list so a later --offline rebuild works
    try:
        with open(args.manifest + ".src", "w", encoding="utf-8") as f:
            json.dump(entries, f)
    except OSError:
        pass

    if not args.offline:
        got, fail, miss = download_missing(entries, args.sprite_dir)
        print("sprites: %d official, %d missing, %d downloaded, %d failed"
              % (len(entries), miss, got, len(fail)))
        for fn, err in fail[:10]:
            print("  FAIL %s: %s" % (fn, err))
        if not args.no_previews:
            pgot, pfail, pmiss = download_previews(entries, args.preview_dir)
            print("previews: %d missing, %d downloaded, %d failed"
                  % (pmiss, pgot, len(pfail)))
            for fn, err in pfail[:10]:
                print("  PREVIEW FAIL %s: %s" % (fn, err))
    n = build_manifest(entries, args.sprite_dir, args.manifest,
                       preview_dir=args.preview_dir)
    print("manifest: %d entries -> %s" % (n, args.manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
