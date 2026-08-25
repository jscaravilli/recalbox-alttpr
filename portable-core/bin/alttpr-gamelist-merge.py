#!/usr/bin/env python3
"""Merge pending ALTTPR seed <game> entries into the alttpr gamelist.xml.

EmulationStation rewrites gamelist.xml from its in-memory model on quit, wiping
<game> entries the generator appended while ES was already running. The generator
records each new seed's <game> block in a pending file; this script (run while ES
is stopped) re-inserts any pending block whose <path> is not already present, so
ES boots with the seed's nickname + art intact.

    usage: alttpr-gamelist-merge.py <gamelist.xml> <pending-file>

Prints "merged N/M" and exits 0 (best-effort; never fails the caller).
"""
import re
import sys

EMPTY = '<?xml version="1.0"?>\n<gameList>\n</gameList>\n'


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: alttpr-gamelist-merge.py <gamelist.xml> <pending>\n")
        return 0
    gl, pending = sys.argv[1], sys.argv[2]
    try:
        data = open(gl, encoding="utf-8").read()
    except OSError:
        data = EMPTY
    if "</gameList>" not in data:
        data = EMPTY
    try:
        pend = open(pending, encoding="utf-8").read()
    except OSError:
        print("no pending file")
        return 0
    blocks = re.findall(r"  <game>.*?</game>\n", pend, re.S)
    added = 0
    for b in blocks:
        m = re.search(r"<path>(.*?)</path>", b)
        if not m:
            continue
        path = m.group(1)
        # Replace any existing entry for this exact path — ES's folder scan leaves
        # a raw-filename <game> for the seed; swapping in the pending block makes
        # our friendly nickname win without leaving a duplicate. If none exists,
        # this simply inserts it.
        pat = (r"\s*<game(?:\s[^>]*)?>(?:(?!</game>).)*?<path>"
               + re.escape(path) + r"</path>.*?</game>")
        data = re.sub(pat, "", data, flags=re.S)
        data = data.replace("</gameList>", b + "</gameList>")
        added += 1
    try:
        open(gl, "w", encoding="utf-8").write(data)
    except OSError as e:
        sys.stderr.write("merge: cannot write %s: %s\n" % (gl, e))
        return 0
    print("merged %d/%d pending gamelist entries" % (added, len(blocks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
