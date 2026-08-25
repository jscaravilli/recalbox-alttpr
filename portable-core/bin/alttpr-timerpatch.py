#!/usr/bin/env python3
"""Fix the Python-DR HUD stopwatch freeze in a generated ROM.

The timer routine was relocated by the current base patch, but retains the old
DB bug: it reads WRAM with long addressing and writes $BExx with absolute
addressing. If DB is not $7E, the divide/subtract loop never updates WRAM and
freezes. Wrap the routine with DB=$7E, then restore the caller's DB.
"""
import sys


def lorom_off(bank, address):
    return ((bank & 0x7f) * 0x8000) + (address & 0x7fff)


CALLER = lorom_off(0x20, 0xdb75)
CALLER_ORIG = bytes((0x20, 0x5b, 0xd8))  # JSR $D85B
CALLER_NEW = bytes((0x20, 0x00, 0xe0))   # JSR $E000
TRAMP = lorom_off(0x20, 0xe000)
TRAMP_CODE = bytes((
    0x8b,             # PHB
    0xe2, 0x20,       # SEP #$20
    0xa9, 0x7e,       # LDA #$7E
    0x48,             # PHA
    0xab,             # PLB
    0xc2, 0x20,       # REP #$20
    0x20, 0x5b, 0xd8, # JSR $D85B
    0xab,             # PLB
    0x60,             # RTS
))
TIMER_FLAG = 0x180190


def main():
    if len(sys.argv) != 2:
        print("usage: alttpr-timerpatch.py <seed.sfc>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    rom = bytearray(open(path, "rb").read())
    if len(rom) < TRAMP + len(TRAMP_CODE):
        raise RuntimeError("ROM too small")
    if rom[TIMER_FLAG] == 0:
        print("timerpatch: timer disabled")
        return 0
    caller = bytes(rom[CALLER:CALLER + 3])
    if caller == CALLER_NEW:
        if bytes(rom[TRAMP:TRAMP + len(TRAMP_CODE)]) != TRAMP_CODE:
            raise RuntimeError("timer caller patched but trampoline differs")
        print("timerpatch: already patched")
        return 0
    if caller != CALLER_ORIG:
        raise RuntimeError("unexpected timer caller bytes: " +
                           caller.hex(" "))
    if any(rom[TRAMP:TRAMP + len(TRAMP_CODE)]):
        raise RuntimeError("$20:E000 trampoline space is not free")
    rom[TRAMP:TRAMP + len(TRAMP_CODE)] = TRAMP_CODE
    rom[CALLER:CALLER + 3] = CALLER_NEW
    with open(path, "wb") as output:
        output.write(rom)
    print("timerpatch: applied DB=$7E trampoline at $20:E000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
