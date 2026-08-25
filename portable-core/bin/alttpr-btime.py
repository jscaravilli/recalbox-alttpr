#!/usr/bin/env python3
"""Print the filesystem CREATION time (birth time) of each path as an epoch int.

Uses the Linux statx() syscall (STATX_BTIME) via ctypes, since busybox `stat` and
Python's os.stat do not expose birth time on Linux. exFAT (the USB share where
ALTTPR seeds live) stores creation time, so this returns the true "when the seed
was generated" timestamp. Falls back to mtime if btime is unavailable.

Usage:  alttpr-btime.py <file> [<file> ...]
Output: one line per file:  <epoch>\t<path>
"""
import ctypes
import os
import struct
import sys

AT_FDCWD = -100
STATX_BTIME = 0x00000800
# statx fixed header is 64 bytes; timestamps (16 bytes each) follow in the order
# atime, btime, ctime, mtime. So btime.tv_sec is at offset 64 + 16 = 80.
_BTIME_OFF = 80
_MTIME_OFF = 64 + 16 * 3

try:
    _libc = ctypes.CDLL("libc.so.6", use_errno=True)
    _HAVE_STATX = hasattr(_libc, "statx")
except Exception:
    _libc = None
    _HAVE_STATX = False


def birth_epoch(path):
    if _HAVE_STATX:
        buf = ctypes.create_string_buffer(256)
        try:
            r = _libc.statx(AT_FDCWD, path.encode(), 0, STATX_BTIME, buf)
        except Exception:
            r = -1
        if r == 0:
            raw = buf.raw
            mask = struct.unpack_from("<I", raw, 0)[0]
            if mask & STATX_BTIME:
                sec = struct.unpack_from("<q", raw, _BTIME_OFF)[0]
                if sec > 0:
                    return sec
    # fallback: mtime
    try:
        return int(os.stat(path).st_mtime)
    except OSError:
        return 0


def main():
    for p in sys.argv[1:]:
        print("%d\t%s" % (birth_epoch(p), p))


if __name__ == "__main__":
    main()
