#!/usr/bin/env python3
"""Reserve the final 32 bytes of DR's bank-$37 room-data allocator."""
import hashlib
import pathlib
import py_compile
import sys


STOPWATCH_TRAMPOLINE_SNES = 0x37FFE0
STOPWATCH_TRAMPOLINE_PC = (
    ((STOPWATCH_TRAMPOLINE_SNES & 0x7F0000) >> 1)
    | (STOPWATCH_TRAMPOLINE_SNES & 0x7FFF)
)
STOPWATCH_TRAMPOLINE_SIZE = 0x20
PINNED_DR_COMMIT = "7e14fddab00b847d6eccf0931b365a5774c5476a"
PRISTINE_SHA256 = "e9d6c6914896bb7eb387298e20a806fb90f2a1051176b66f0dacfa6ed5ab8295"
LEGACY_PATCHED_SHA256 = "5866dac0f24b89abb35ddd84db37081a3a092aa264d67a5f79eba266156d8941"
PATCHED_16_SHA256 = "a4affa17b8d1e4c7ae4f816871f21f2e6b71a4a9364fe3cd5815d27f25348db6"
PATCHED_SHA256 = "b86387eaf2bb435c9bb4a4e7e2d833417e4f690d28ef75273ca54591959ed476"
LEGACY_COMMENT = (
    "# Reserved by recalbox-alttpr-portable for the HUD Stopwatch DB wrapper."
)
CURRENT_COMMENT = (
    "# Reserved by recalbox-alttpr for the HUD Stopwatch DB wrapper."
)

CONSTANTS = """\
# Reserved by recalbox-alttpr for the HUD Stopwatch DB wrapper.
STOPWATCH_TRAMPOLINE_SNES = 0x37FFE0
STOPWATCH_TRAMPOLINE_PC = snes_to_pc(STOPWATCH_TRAMPOLINE_SNES)
STOPWATCH_TRAMPOLINE_SIZE = 0x20
assert STOPWATCH_TRAMPOLINE_SNES + STOPWATCH_TRAMPOLINE_SIZE == 0x380000

"""
IMPORT_ANCHOR = (
    "from source.classes.GFX import init_gfx_data\n\n\n"
)
OLD_GUARD = "if room_start_address > 0x380000:"
NEW_GUARD = "if room_start_address > STOPWATCH_TRAMPOLINE_SNES:"


def main():
    if len(sys.argv) != 2:
        print("usage: alttpr-enginepatch.py <door-randomizer-dir>",
              file=sys.stderr)
        return 2
    source = pathlib.Path(sys.argv[1]) / "source" / "rom" / "DataTables.py"
    text = source.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest not in (
            PRISTINE_SHA256, LEGACY_PATCHED_SHA256, PATCHED_16_SHA256,
            PATCHED_SHA256):
        raise RuntimeError(
            "pinned DataTables.py provenance check failed; expected DR commit "
            + PINNED_DR_COMMIT)

    if digest == PRISTINE_SHA256:
        if IMPORT_ANCHOR not in text:
            raise RuntimeError("DataTables import anchor changed")
        text = text.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + CONSTANTS, 1)
        text = text.replace(OLD_GUARD, NEW_GUARD, 1)
    elif digest in (LEGACY_PATCHED_SHA256, PATCHED_16_SHA256):
        text = text.replace(LEGACY_COMMENT, CURRENT_COMMENT, 1)
        text = text.replace(
            "STOPWATCH_TRAMPOLINE_SNES = 0x37FFF0",
            "STOPWATCH_TRAMPOLINE_SNES = 0x37FFE0",
            1,
        )
        text = text.replace(
            "STOPWATCH_TRAMPOLINE_SIZE = 0x10",
            "STOPWATCH_TRAMPOLINE_SIZE = 0x20",
            1,
        )
    if text.count(NEW_GUARD) != 1:
        raise RuntimeError("room allocator guard changed")
    if text.count("STOPWATCH_TRAMPOLINE_SNES = 0x37FFE0") != 1:
        raise RuntimeError("Stopwatch reservation declaration changed")

    source.write_text(text, encoding="utf-8")
    patched_digest = hashlib.sha256(
        source.read_bytes()).hexdigest()
    if patched_digest != PATCHED_SHA256:
        raise RuntimeError("patched DataTables.py hash does not match contract")
    py_compile.compile(str(source), doraise=True)
    print("enginepatch: reserved $37:FFE0-$37:FFFF from room allocator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
