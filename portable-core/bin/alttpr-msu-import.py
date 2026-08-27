#!/usr/bin/env python3
"""Import user-owned MSU-1 packs from SHARE/import/msu."""
import argparse
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile


ENGINE = "/recalbox/share/alttpr"
DROP_DIR = "/recalbox/share/import/msu"
PROCESSED_DIR = DROP_DIR + "/processed"
MSU_DIR = ENGINE + "/msu"
USER_METADATA = MSU_DIR + "/user-packs.json"
ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar")
FREE_SPACE_MARGIN = 64 << 20


def load_msu_module():
    path = ENGINE + "/bin/alttpr-msu.py"
    spec = importlib.util.spec_from_file_location("alttpr_msu", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_name(path):
    name = os.path.basename(path.rstrip(os.sep))
    for suffix in ARCHIVE_SUFFIXES:
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
            break
    # This display value is eventually written to a shell-sourced choices file.
    # Keep only a deliberately narrow set with no quotes, substitutions, escapes,
    # control characters, or shell metacharacters.
    name = re.sub(r"[^A-Za-z0-9 _().+-]+", " ", name)
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "Imported MSU Pack"


def load_metadata():
    try:
        data = json.load(open(USER_METADATA, encoding="utf-8"))
        return [p for p in data if p.get("slug", "").startswith("user-")]
    except (OSError, ValueError, TypeError):
        return []


def write_metadata(entries):
    os.makedirs(MSU_DIR, exist_ok=True)
    tmp = USER_METADATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as output:
        json.dump(sorted(entries, key=lambda p: p["name"].lower()), output,
                  ensure_ascii=False, indent=1)
        output.write("\n")
    os.replace(tmp, USER_METADATA)


def candidates():
    os.makedirs(DROP_DIR, exist_ok=True)
    result = []
    for name in sorted(os.listdir(DROP_DIR), key=str.lower):
        path = os.path.join(DROP_DIR, name)
        if path == PROCESSED_DIR or name.startswith("."):
            continue
        if os.path.isdir(path) or name.lower().endswith(ARCHIVE_SUFFIXES):
            result.append(path)
    return result


def safe_extract_zip(path, destination):
    root = os.path.realpath(destination) + os.sep
    with zipfile.ZipFile(path) as archive:
        ensure_staging_space(
            sum(item.file_size for item in archive.infolist()), copies=2)
        for item in archive.infolist():
            target = os.path.realpath(
                os.path.join(destination, item.filename))
            if not target.startswith(root):
                raise RuntimeError("archive contains an unsafe path")
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError("archive contains a symbolic link")
        archive.extractall(destination)


def ensure_staging_space(required, copies=1):
    if required * copies + FREE_SPACE_MARGIN > shutil.disk_usage(MSU_DIR).free:
        raise RuntimeError("not enough free disk space to stage this pack")


def directory_size(path):
    if os.path.islink(path):
        raise RuntimeError("input folder is a symbolic link")
    total = 0
    for directory, dirs, files in os.walk(path):
        for name in dirs:
            if os.path.islink(os.path.join(directory, name)):
                raise RuntimeError("input folder contains a symbolic link")
        for name in files:
            item = os.path.join(directory, name)
            if os.path.islink(item):
                raise RuntimeError("input folder contains a symbolic link")
            total += os.path.getsize(item)
    return total


def validate_7zz_archive(path, msu_module):
    msu_module.ensure_7zz()
    output = msu_module.subprocess.check_output(
        [msu_module.SEVENZR, "l", "-slt", path],
        stderr=msu_module.subprocess.STDOUT,
        timeout=120).decode("utf-8", "replace")
    members = output.split("----------", 1)
    if len(members) != 2:
        raise RuntimeError("could not inspect archive members")
    total = 0
    for line in members[1].splitlines():
        if line.startswith("Path = "):
            name = line[7:].replace("\\", "/")
            parts = [part for part in name.split("/") if part]
            if (name.startswith("/") or re.match(r"^[A-Za-z]:", name)
                    or ".." in parts):
                raise RuntimeError("archive contains an unsafe path")
        elif line.startswith(("Symbolic Link = ", "Hard Link = ")):
            raise RuntimeError("archive contains a link")
        elif line.startswith("Attributes = ") and line[13:].startswith("l"):
            raise RuntimeError("archive contains a symbolic link")
        elif line.startswith("Size = "):
            try:
                total += int(line[7:])
            except ValueError:
                raise RuntimeError("archive contains an invalid size")
    ensure_staging_space(total, copies=2)


def stage_source(path, stage, msu_module):
    if os.path.isdir(path):
        ensure_staging_space(directory_size(path), copies=2)
        shutil.copytree(path, stage, dirs_exist_ok=True)
        return
    if path.lower().endswith(".zip"):
        safe_extract_zip(path, stage)
        return
    if path.lower().endswith((".7z", ".rar")):
        validate_7zz_archive(path, msu_module)
        rc = msu_module.subprocess.call(
            [msu_module.SEVENZR, "x", "-y", "-o" + stage, path],
            stdout=msu_module.subprocess.DEVNULL,
            stderr=msu_module.subprocess.DEVNULL)
        if rc != 0:
            raise RuntimeError("archive extraction failed")
        for directory, dirs, files in os.walk(stage):
            for name in dirs + files:
                if os.path.islink(os.path.join(directory, name)):
                    raise RuntimeError("archive contains a symbolic link")
        return
    raise RuntimeError("unsupported input type")


def find_payload(stage):
    groups = {}
    markers = {}
    for directory, _dirs, files in os.walk(stage):
        for filename in files:
            path = os.path.join(directory, filename)
            match = re.fullmatch(r"(.+)-([0-9]+)\.pcm", filename, re.I)
            if match:
                key = (directory, match.group(1).lower())
                groups.setdefault(key, []).append(
                    (int(match.group(2)), path, match.group(1)))
            elif filename.lower().endswith(".msu"):
                markers[(directory, filename[:-4].lower())] = path
    if not groups:
        raise RuntimeError("no numbered PCM tracks were found")
    if len(groups) != 1:
        raise RuntimeError(
            "multiple PCM filename sets found; keep one pack per input")
    key, tracks = max(groups.items(), key=lambda item: len(item[1]))
    numbers = [number for number, _path, _base in tracks]
    if len(numbers) != len(set(numbers)):
        raise RuntimeError("duplicate PCM track numbers")
    if min(numbers) < 1:
        raise RuntimeError("PCM track numbers must start at 1 or higher")
    for _number, path, _base in tracks:
        size = os.path.getsize(path)
        with open(path, "rb") as track:
            signature = track.read(4)
        if signature != b"MSU1" or size <= 8 or (size - 8) % 4:
            raise RuntimeError("empty or invalid PCM track: " +
                               os.path.basename(path))
    tracks.sort()
    return markers.get(key), tracks, tracks[0][2]


def install(path, replace=False):
    msu_module = load_msu_module()
    name = safe_name(path)
    display_name = "User: " + name
    slug = "user-" + msu_module.slug(name).lower()
    destination = os.path.join(MSU_DIR, slug)
    if os.path.exists(destination) and not replace:
        raise RuntimeError("a user pack with this name is already installed")

    os.makedirs(MSU_DIR, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".user-msu-", dir=MSU_DIR)
    incoming = stage + "-ready"
    backup = os.path.join(MSU_DIR, ".user-backup-" + slug)
    old_entries = load_metadata()
    try:
        stage_source(path, stage, msu_module)
        marker, tracks, _source_base = find_payload(stage)
        base = slug
        required = sum(os.path.getsize(track) for _n, track, _b in tracks)
        required += os.path.getsize(marker) if marker else 0
        free = shutil.disk_usage(MSU_DIR).free
        if required + FREE_SPACE_MARGIN > free:
            raise RuntimeError("not enough free disk space")

        os.makedirs(incoming)
        marker_out = os.path.join(incoming, base + ".msu")
        if marker:
            shutil.copy2(marker, marker_out)
        else:
            open(marker_out, "wb").close()
        for number, track, _source_base in tracks:
            shutil.copy2(track, os.path.join(
                incoming, "%s-%d.pcm" % (base, number)))

        shutil.rmtree(backup, ignore_errors=True)
        if os.path.exists(destination):
            os.replace(destination, backup)
        try:
            os.replace(incoming, destination)
            entries = [entry for entry in old_entries
                       if entry.get("slug") != slug]
            entries.append({"name": display_name, "slug": slug, "author": "",
                            "user": True})
            existing_names = {
                entry.get("name") for entry in
                json.load(open(msu_module.MANIFEST, encoding="utf-8"))
                if entry.get("slug") != slug
            } if os.path.isfile(msu_module.MANIFEST) else set()
            if display_name in existing_names:
                raise RuntimeError("pack display name conflicts with an "
                                   "installed pack")
            write_metadata(entries)
            shutil.rmtree(stage)
            msu_module.build_manifest()
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            if os.path.exists(backup):
                os.replace(backup, destination)
            write_metadata(old_entries)
            msu_module.build_manifest()
            raise
        shutil.rmtree(backup, ignore_errors=True)
        return {"name": display_name, "slug": slug, "tracks": len(tracks),
                "bytes": required}
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(incoming, ignore_errors=True)


def delete(slug):
    if not slug.startswith("user-"):
        raise RuntimeError("only user-imported packs can be deleted")
    entries = load_metadata()
    if not any(entry.get("slug") == slug for entry in entries):
        raise RuntimeError("user pack is not registered")
    destination = os.path.join(MSU_DIR, slug)
    deleting = os.path.join(MSU_DIR, ".user-deleting-" + slug)
    if not os.path.isdir(destination):
        raise RuntimeError("user pack directory is missing")
    shutil.rmtree(deleting, ignore_errors=True)
    os.replace(destination, deleting)
    msu_module = load_msu_module()
    try:
        write_metadata([entry for entry in entries
                        if entry.get("slug") != slug])
        msu_module.build_manifest()
    except Exception:
        os.replace(deleting, destination)
        write_metadata(entries)
        msu_module.build_manifest()
        raise
    shutil.rmtree(deleting)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--import-all", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--delete", metavar="SLUG")
    parser.add_argument("--list-user", action="store_true")
    args = parser.parse_args()
    try:
        if args.scan:
            for path in candidates():
                print(path)
        elif args.import_all:
            found = candidates()
            if not found:
                print("No packs found in " + DROP_DIR)
                return 0
            failures = []
            for path in found:
                try:
                    result = install(path, args.replace)
                    print("IMPORTED:%s:%d:%s" % (
                        result["name"], result["tracks"], path))
                    os.makedirs(PROCESSED_DIR, exist_ok=True)
                    processed = os.path.join(PROCESSED_DIR,
                                             os.path.basename(path))
                    if os.path.exists(processed):
                        suffix = 2
                        while os.path.exists(processed + ".%d" % suffix):
                            suffix += 1
                        processed += ".%d" % suffix
                    os.replace(path, processed)
                except Exception as error:
                    failures.append(path)
                    print("FAILED:%s:%s" % (path, error))
            return 1 if failures else 0
        elif args.delete:
            delete(args.delete)
            print("DELETED:" + args.delete)
        elif args.list_user:
            for entry in load_metadata():
                print("%s\t%s" % (entry["slug"], entry["name"]))
        else:
            parser.error("choose an operation")
    except Exception as error:
        print("ERROR:" + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
