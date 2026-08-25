#!/usr/bin/env python3
"""Build MSU-1 PCM tracks from an msupcm++ JSON recipe using ffmpeg.

Recalbox includes ffmpeg but cannot execute the Windows msupcm.exe bundled by
source-audio packs. The recipe's trim/loop offsets are PCM sample frames.
"""
import argparse
import json
import os
import struct
import subprocess
import tempfile


def build(recipe_path):
    recipe_path = os.path.abspath(recipe_path)
    root = os.path.dirname(recipe_path)
    recipe = json.load(open(recipe_path, encoding="utf-8"))
    prefix = recipe.get("output_prefix") or os.path.splitext(
        os.path.basename(recipe_path))[0]
    rate = int(recipe.get("sample_rate") or 44100)
    target_lufs = recipe.get("normalization")
    built = 0

    open(os.path.join(root, prefix + ".msu"), "ab").close()
    for track in recipe.get("tracks", []):
        number = int(track["track_number"])
        source = os.path.join(root, track["file"])
        if not os.path.isfile(source):
            print("missing source:", source)
            continue
        output = os.path.join(root, "%s-%d.pcm" % (prefix, number))
        fd, raw_path = tempfile.mkstemp(prefix="msupcm-", suffix=".raw")
        os.close(fd)
        try:
            cmd = ["ffmpeg", "-v", "error", "-y", "-i", source]
            if target_lufs is not None:
                cmd += ["-af", "loudnorm=I=%s:TP=-1.5:LRA=11" % target_lufs]
            cmd += ["-ar", str(rate), "-ac", "2", "-f", "s16le", raw_path]
            subprocess.check_call(cmd)
            raw = open(raw_path, "rb").read()
            frame_count = len(raw) // 4  # stereo signed 16-bit
            start = max(0, int(track.get("trim_start") or 0))
            end = min(frame_count, int(track.get("trim_end") or frame_count))
            if end <= start:
                raise RuntimeError("invalid trim range for track %d" % number)
            loop = max(0, int(track.get("loop") or start) - start)
            loop = min(loop, end - start - 1)
            with open(output, "wb") as f:
                f.write(b"MSU1")
                f.write(struct.pack("<I", loop))
                f.write(raw[start * 4:end * 4])
            built += 1
            print("built %s (%d frames, loop %d)" %
                  (os.path.basename(output), end - start, loop))
        finally:
            try:
                os.remove(raw_path)
            except OSError:
                pass
    return built


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe")
    args = ap.parse_args()
    count = build(args.recipe)
    print("built tracks:", count)
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
