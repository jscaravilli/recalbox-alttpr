#!/usr/bin/env python3
"""Download, extract, and normalize the selected ALTTPR MSU-1 music packs.

The Custom Seed menu's "MSU Pack" row offers "Default" (original ALTTP music =
no pack) plus each installed pack. This script reads the curated selection in
``bin/msu-packs.json``, downloads each pack from its host (Google Drive,
Dropbox, MediaFire, or a direct URL), extracts it, finds the ``.msu`` marker and
``-N.pcm`` tracks, and stores them under ``msu/<slug>/``. It then writes the
runtime manifest ``msu/packs.json`` (name, author, dir, basename, track count)
that the menu and the generator read.

RAR archives are NOT handled here (the Pi has no unrar): pack it on a machine
that can extract RAR and drop the ``.msu``/``.pcm`` files into ``msu/<slug>/``,
then re-run with ``--manifest-only`` to register it.

    usage:
      alttpr-msu.py                 # download + install every pending pack
      alttpr-msu.py --only "Maple Story"
      alttpr-msu.py --manifest-only # just rebuild msu/packs.json from disk
      alttpr-msu.py --list          # show selection + install status

Idempotent: a pack whose msu/<slug>/ already has tracks is skipped unless
``--force``. Large downloads; run with plenty of disk + time.
"""
import argparse
import html as htmlmod
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import http.cookiejar
import zipfile
import tarfile

ENGINE = "/recalbox/share/alttpr"
SELECTION = ENGINE + "/bin/data/msu-packs.json"
MSU_DIR = ENGINE + "/msu"
MANIFEST = MSU_DIR + "/packs.json"
USER_METADATA = MSU_DIR + "/user-packs.json"
DL_DIR = ENGINE + "/_msu_dl"
SEVENZR = ENGINE + "/bin/7zz"
SEVENZZ_URL = "https://www.7-zip.org/a/7z2602-linux-arm64.tar.xz"
SEVENZZ_SHA256 = "70ea6cc737ae1495ea2d7eb20ef3120fe579bd3f1a83a9d2362b62ec5bde2bba"


# --- helpers -----------------------------------------------------------------
def slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
    return s or "pack"


def opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent",
                      "Mozilla/5.0 (X11; Linux aarch64) Firefox/120.0")]
    return op


def stream(op, url, dst, data=None):
    r = op.open(urllib.request.Request(url, data=data), timeout=900)
    total = 0
    with open(dst, "wb") as f:
        while True:
            c = r.read(1 << 16)
            if not c:
                break
            f.write(c)
            total += len(c)
    return total, r.headers.get("Content-Type", "")


def ensure_7zz():
    """Install the pinned official ARM64 7-Zip standalone binary.

    Recalbox's bundled 7zr handles 7z only; 7zz also extracts RAR archives.
    """
    if os.path.isfile(SEVENZR) and os.access(SEVENZR, os.X_OK):
        return
    archive = os.path.join(DL_DIR, "7zz-arm64.tar.xz")
    os.makedirs(DL_DIR, exist_ok=True)
    op = opener()
    stream(op, SEVENZZ_URL, archive)
    digest = hashlib.sha256(open(archive, "rb").read()).hexdigest()
    if digest != SEVENZZ_SHA256:
        raise RuntimeError("7zz archive checksum mismatch")
    try:
        with tarfile.open(archive, "r:xz") as tf:
            member = next((m for m in tf.getmembers()
                           if os.path.basename(m.name) == "7zz" and m.isfile()),
                          None)
            if member is None:
                raise RuntimeError("7zz missing from official archive")
            src = tf.extractfile(member)
            with open(SEVENZR, "wb") as dst:
                shutil.copyfileobj(src, dst)
    except (ImportError, tarfile.ReadError, tarfile.CompressionError):
        # Recalbox Python omits lzma, but BusyBox tar + /usr/bin/xz support -J.
        rc = subprocess.call(["tar", "-xJf", archive, "-C", DL_DIR, "7zz"])
        staged = os.path.join(DL_DIR, "7zz")
        if rc != 0 or not os.path.isfile(staged):
            raise RuntimeError("could not extract official 7zz archive")
        shutil.move(staged, SEVENZR)
    os.chmod(SEVENZR, 0o755)


# --- per-host download -------------------------------------------------------
def dl_gdrive(op, url, dst):
    m = re.search(r"/d/([^/]+)", url) or re.search(r"id=([^&]+)", url)
    fid = m.group(1)
    r = op.open("https://drive.google.com/uc?export=download&id=%s" % fid,
                timeout=120)
    ct = r.headers.get("Content-Type", "")
    body = r.read()
    if "text/html" not in ct:
        open(dst, "wb").write(body)
        return len(body)
    h = body.decode("utf-8", "replace")
    fm = re.search(r'<form[^>]+action="([^"]+)"', h)
    if not fm:
        raise RuntimeError("no gdrive form (quota/permission?)")
    action = htmlmod.unescape(fm.group(1))
    n, _ = stream(op, action, dst, data=b"")
    return n


def dl_dropbox(op, url, dst):
    u = url.split("?")[0] + "?dl=1"
    n, _ = stream(op, u, dst)
    return n


def dl_mediafire(op, url, dst):
    h = op.open(url, timeout=120).read().decode("utf-8", "replace")
    # the real link is embedded in the page; it may be http OR https, and short
    # links (no filename) render it only in a script var — match both.
    m = re.search(r'(https?://download[0-9]*\.mediafire\.com[^\s"\'<>\\]+)', h)
    if not m:
        m = re.search(r'data-scrambled-url="([^"]+)"', h)
        if m:
            import base64
            direct = base64.b64decode(m.group(1)).decode("utf-8")
            n, _ = stream(op, direct, dst)
            return n
        raise RuntimeError("mediafire direct link not found")
    n, _ = stream(op, m.group(1), dst)
    return n


def dl_arborelia(op, url, dst):
    h = op.open(url, timeout=120).read().decode("utf-8", "replace")
    m = re.search(r'href="([^"]+\.(?:zip|7z))"', h, re.I)
    if not m:
        raise RuntimeError("no archive link on page")
    link = m.group(1)
    if not link.startswith("http"):
        link = urllib.parse.urljoin(url, link)
    n, _ = stream(op, link, dst)
    return n


def download(pack, dst):
    op = opener()
    host = pack["host"]
    if host == "gdrive":
        return dl_gdrive(op, pack["url"], dst)
    if host == "dropbox":
        return dl_dropbox(op, pack["url"], dst)
    if host == "mediafire":
        return dl_mediafire(op, pack["url"], dst)
    if host == "arborelia":
        return dl_arborelia(op, pack["url"], dst)
    n, _ = stream(op, pack["url"], dst)
    return n


# --- extraction --------------------------------------------------------------
def sniff(path):
    with open(path, "rb") as f:
        sig = f.read(8)
    if sig[:2] == b"PK":
        return "zip"
    if sig[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"
    if sig[:4] == b"Rar!":
        return "rar"
    return "unknown"


def extract(path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    kind = sniff(path)
    if kind == "zip":
        with zipfile.ZipFile(path) as z:
            z.extractall(out_dir)
        return True
    if kind in ("7z", "rar"):
        ensure_7zz()
        rc = subprocess.call([SEVENZR, "x", "-y", "-o" + out_dir, path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        return rc == 0
    return False


# --- normalize into msu/<slug>/ ----------------------------------------------
def find_msu_tree(root):
    """Return (msu_path, pcm_paths). Picks the .msu whose basename has the most
    matching -N.pcm siblings."""
    msus = []
    pcms = []
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            low = fn.lower()
            if low.endswith(".msu"):
                msus.append(os.path.join(dp, fn))
            elif low.endswith(".pcm"):
                pcms.append(os.path.join(dp, fn))
    if not pcms:
        return None, [], None
    best = None
    best_n = -1
    for m in msus:
        base = os.path.basename(m)[:-4].lower()
        cnt = sum(1 for p in pcms
                  if os.path.basename(p).lower().startswith(base + "-"))
        if cnt > best_n:
            best_n, best = cnt, m
    if best is None:
        # no .msu: derive base from the most common pcm prefix
        from collections import Counter
        bases = Counter()
        for p in pcms:
            mm = re.match(r"(.+)-\d+", os.path.basename(p)[:-4])
            if mm:
                bases[mm.group(1).lower()] += 1
        if not bases:
            return None, [], None
        base = bases.most_common(1)[0][0]
        best = None
    else:
        base = os.path.basename(best)[:-4].lower()
    keep = [p for p in pcms
            if os.path.basename(p).lower().startswith(base + "-")]
    return best, keep, base


def install_pack(pack, force=False):
    name = pack["name"]
    dest = os.path.join(MSU_DIR, slug(name))
    if (not force and os.path.isdir(dest)
            and any(f.lower().endswith(".pcm") for f in os.listdir(dest))):
        return "already"
    os.makedirs(DL_DIR, exist_ok=True)
    arc = os.path.join(DL_DIR, slug(name) + ".arc")
    n = download(pack, arc)
    if n < 1000:
        raise RuntimeError("download too small (%d bytes)" % n)
    ex = os.path.join(DL_DIR, slug(name) + "_x")
    shutil.rmtree(ex, ignore_errors=True)
    if not extract(arc, ex):
        raise RuntimeError("extract failed (format %s)" % sniff(arc))
    found = find_msu_tree(ex)
    if not found or not found[1]:
        # Source-audio packs ship MP3/FLAC + an msupcm++ recipe. Build the PCM
        # payload natively because their included converter is a Windows exe.
        recipes = []
        for dp, _dn, fns in os.walk(ex):
            for fn in fns:
                if fn.lower().endswith(".json"):
                    recipes.append(os.path.join(dp, fn))
        builder = ENGINE + "/bin/alttpr-build-msupcm.py"
        for recipe in recipes:
            try:
                data = json.load(open(recipe, encoding="utf-8"))
            except Exception:
                continue
            if not data.get("tracks") or not data.get("output_prefix"):
                continue
            subprocess.call(["python3", builder, recipe])
        found = find_msu_tree(ex)
    if not found or not found[1]:
        raise RuntimeError("no .pcm tracks found after extract")
    msu_path, pcms, base = found
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    # copy the .msu (create an empty one if the pack lacks it) + all tracks
    msu_dst = os.path.join(dest, base + ".msu")
    if msu_path:
        shutil.copy2(msu_path, msu_dst)
    else:
        open(msu_dst, "wb").close()
    for p in pcms:
        shutil.copy2(p, os.path.join(dest, os.path.basename(p)))
    # cleanup the staging
    shutil.rmtree(ex, ignore_errors=True)
    try:
        os.remove(arc)
    except OSError:
        pass
    return "installed"


# --- manifest ----------------------------------------------------------------
def build_manifest():
    packs = []
    if os.path.isdir(MSU_DIR):
        for d in sorted(os.listdir(MSU_DIR)):
            if d.startswith("."):
                continue
            pd = os.path.join(MSU_DIR, d)
            if not os.path.isdir(pd):
                continue
            pcms = [f for f in os.listdir(pd) if f.lower().endswith(".pcm")]
            msu = [f for f in os.listdir(pd) if f.lower().endswith(".msu")]
            if not pcms or not msu:
                continue
            base = msu[0][:-4]
            packs.append({"slug": d, "dir": pd, "basename": base,
                          "tracks": len(pcms)})
    # merge display metadata from the selection file
    meta = {}
    try:
        for p in json.load(open(SELECTION, encoding="utf-8")):
            meta[slug(p["name"])] = p
    except Exception:
        pass
    try:
        for p in json.load(open(USER_METADATA, encoding="utf-8")):
            meta[p["slug"]] = p
    except Exception:
        pass
    out = []
    for p in packs:
        m = meta.get(p["slug"], {})
        out.append({"name": m.get("name", p["slug"]),
                    "author": m.get("author", ""),
                    "slug": p["slug"], "dir": p["dir"],
                    "basename": p["basename"], "tracks": p["tracks"],
                    "user": bool(m.get("user", False))})
    out.sort(key=lambda d: d["name"].lower())
    os.makedirs(MSU_DIR, exist_ok=True)
    manifest_tmp = MANIFEST + ".tmp"
    with open(manifest_tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(manifest_tmp, MANIFEST)
    return out


# --- main --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="install just the pack with this exact name")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    try:
        selection = json.load(open(SELECTION, encoding="utf-8"))
    except Exception as e:
        sys.stderr.write("cannot read selection %s: %s\n" % (SELECTION, e))
        return 2

    if args.list:
        for p in selection:
            d = os.path.join(MSU_DIR, slug(p["name"]))
            has = (os.path.isdir(d)
                   and any(f.lower().endswith(".pcm") for f in os.listdir(d)))
            status = "x" if has else ("!" if p.get("requires_album") else " ")
            print("[%s] %-45s %s" % (status, p["name"], p["host"]))
        return 0

    if args.manifest_only:
        out = build_manifest()
        print("manifest: %d installed packs -> %s" % (len(out), MANIFEST))
        return 0

    targets = selection
    if args.only:
        targets = [p for p in selection if p["name"] == args.only]
        if not targets:
            sys.stderr.write("no pack named %r\n" % args.only)
            return 2

    ok = 0
    fail = []
    for p in targets:
        if p.get("requires_album"):
            print("%-45s manual: %s" %
                  (p["name"], p.get("note", "source audio required")))
            continue
        try:
            res = install_pack(p, force=args.force)
            print("%-45s %s" % (p["name"], res))
            if res in ("installed", "already"):
                ok += 1
        except Exception as e:  # noqa: BLE001
            print("%-45s FAILED: %s" % (p["name"], str(e)[:80]))
            fail.append((p["name"], str(e)[:120]))
    out = build_manifest()
    print("---")
    print("ok=%d failed=%d installed-manifest=%d" % (ok, len(fail), len(out)))
    for n, e in fail:
        print("  FAIL %s: %s" % (n, e))
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
