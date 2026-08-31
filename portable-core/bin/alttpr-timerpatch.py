#!/usr/bin/env python3
"""Fix the Python-DR HUD Stopwatch using an explicitly reserved ROM slot.

The timer routine was relocated by the current base patch, but retains the old
DB bug: it reads WRAM with long addressing and writes $BExx with absolute
addressing. If DB is not $7E, the divide/subtract loop never updates WRAM.

The original frame gate is patched as one six-byte control-flow unit so its
branch can never land inside a replacement instruction. The wrapper lives in
the guarded final 32 bytes of bank $37 and retains the 1-in-32-frame update.
"""
import sys


def snes_to_pc(value):
    return ((value & 0x7f0000) >> 1) | (value & 0x7fff)


STOPWATCH_TRAMPOLINE_SNES = 0x37FFE0
STOPWATCH_TRAMPOLINE_PC = snes_to_pc(STOPWATCH_TRAMPOLINE_SNES)
STOPWATCH_TRAMPOLINE_SIZE = 0x20
EXPECTED_BASE_BYTES = bytes(STOPWATCH_TRAMPOLINE_SIZE)

FRAME_GATE_PREFIX = snes_to_pc(0x20DB6E)
FRAME_GATE_PREFIX_BYTES = bytes((0xa5, 0x1a, 0x29, 0x1f, 0x00))
CALLER = snes_to_pc(0x20DB73)
CALLER_ORIG = bytes((0xd0, 0x03, 0x20, 0x5b, 0xd8, 0x6b))
CALLER_NEW = bytes((0x5c, 0xe0, 0xff, 0x37, 0xea, 0xea))

# Unsafe implementation used before this patch. Accept it only for an exact,
# fail-closed migration of already-generated ROMs.
LEGACY_CALLER = bytes((0xd0, 0x03, 0x5c, 0xf0, 0xff, 0x37))
LEGACY_TRAMPOLINE_SNES = 0x37FFF0
LEGACY_TRAMPOLINE_PC = snes_to_pc(LEGACY_TRAMPOLINE_SNES)
LEGACY_TRAMPOLINE = bytes((
    0x8b, 0xe2, 0x20, 0xa9, 0x7e, 0x48, 0xab, 0xc2,
    0x20, 0xf4, 0xd5, 0xe4, 0x5c, 0x5b, 0xd8, 0x20,
))
# $20:E4D6 is an existing PLB; RTL epilogue in the pinned base patch. The
# timer routine returns there via RTS, restoring the DB saved below before
# returning through the original caller's untouched long-return stack frame.
RETURN_EPILOGUE_SNES = 0x20E4D6
RETURN_EPILOGUE_PC = snes_to_pc(RETURN_EPILOGUE_SNES)
EXPECTED_RETURN_EPILOGUE = bytes((0xab, 0x6b))  # PLB; RTL
TRAMP_CODE = bytes((
    0xd0, 0x10,       # BNE skip; flags come from the original AND #$001F
    0x8b,             # PHB
    0xe2, 0x20,       # SEP #$20
    0xa9, 0x7e,       # LDA #$7E
    0x48,             # PHA
    0xab,             # PLB
    0xc2, 0x20,       # REP #$20
    0xf4, 0xd5, 0xe4, # PEA $E4D5; timer RTS advances to $20:E4D6
    0x5c, 0x5b, 0xd8, 0x20, # JML $20:D85B
    0x6b,             # skip: RTL
))
if TRAMP_CODE[2 + TRAMP_CODE[1]] != 0x6b:
    raise RuntimeError("Stopwatch skip branch does not land on RTL.")
TRAMPOLINE_BYTES = TRAMP_CODE + bytes(
    STOPWATCH_TRAMPOLINE_SIZE - len(TRAMP_CODE)
)
assert len(TRAMPOLINE_BYTES) == STOPWATCH_TRAMPOLINE_SIZE
TIMER_FLAG = 0x180190


def patch_rom(rom):
    reservation_end = STOPWATCH_TRAMPOLINE_PC + STOPWATCH_TRAMPOLINE_SIZE
    if len(rom) < reservation_end:
        raise RuntimeError("ROM too small")
    if rom[TIMER_FLAG] == 0:
        return "timer disabled"
    if bytes(rom[
            FRAME_GATE_PREFIX:FRAME_GATE_PREFIX + len(FRAME_GATE_PREFIX_BYTES)
            ]) != FRAME_GATE_PREFIX_BYTES:
        raise RuntimeError("Stopwatch frame-gate prefix changed.")
    caller = bytes(rom[CALLER:CALLER + len(CALLER_NEW)])
    if caller == CALLER_NEW:
        existing = bytes(rom[STOPWATCH_TRAMPOLINE_PC:reservation_end])
        if existing == TRAMPOLINE_BYTES:
            if bytes(rom[RETURN_EPILOGUE_PC:RETURN_EPILOGUE_PC + 2]) != \
                    EXPECTED_RETURN_EPILOGUE:
                raise RuntimeError("Stopwatch return epilogue changed.")
            return "already patched"
        raise RuntimeError("timer caller patched but trampoline differs")
    legacy = caller == LEGACY_CALLER
    if not legacy and caller != CALLER_ORIG:
        raise RuntimeError("unexpected timer caller bytes: " +
                           caller.hex(" "))
    reservation = bytes(rom[STOPWATCH_TRAMPOLINE_PC:reservation_end])
    if legacy:
        expected_legacy = (
            bytes(LEGACY_TRAMPOLINE_PC - STOPWATCH_TRAMPOLINE_PC)
            + LEGACY_TRAMPOLINE
        )
        if reservation != expected_legacy:
            raise RuntimeError(
                "legacy Stopwatch caller found but reservation differs")
    elif reservation != EXPECTED_BASE_BYTES:
        raise RuntimeError(
            "Stopwatch trampoline reservation no longer matches expected "
            "base ROM.")
    if bytes(rom[RETURN_EPILOGUE_PC:RETURN_EPILOGUE_PC + 2]) != \
            EXPECTED_RETURN_EPILOGUE:
        raise RuntimeError("Stopwatch return epilogue changed.")
    rom[STOPWATCH_TRAMPOLINE_PC:reservation_end] = TRAMPOLINE_BYTES
    rom[CALLER:CALLER + len(CALLER_NEW)] = CALLER_NEW
    if bytes(rom[STOPWATCH_TRAMPOLINE_PC:reservation_end]) != \
            TRAMPOLINE_BYTES:
        raise RuntimeError("Stopwatch trampoline post-patch validation failed.")
    if bytes(rom[CALLER:CALLER + len(CALLER_NEW)]) != CALLER_NEW:
        raise RuntimeError("Stopwatch caller post-patch validation failed.")
    return "repaired legacy trampoline" if legacy else "applied safe trampoline"


def main():
    if len(sys.argv) != 2:
        print("usage: alttpr-timerpatch.py <seed.sfc>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    rom = bytearray(open(path, "rb").read())
    result = patch_rom(rom)
    if result in ("timer disabled", "already patched"):
        print("timerpatch: " + result)
        return 0
    with open(path, "wb") as output:
        output.write(rom)
    print("timerpatch: " + result + " at $37:FFE0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
