#!/usr/bin/env python3
"""Fix the Python-DR HUD Stopwatch using an explicitly reserved ROM slot.

The timer routine was relocated by the current base patch, but retains the old
DB bug: it reads WRAM with long addressing and writes $BExx with absolute
addressing. If DB is not $7E, the divide/subtract loop never updates WRAM and
freezes. The wrapper lives in the guarded final 16 bytes of bank $37.
"""
import sys


def snes_to_pc(value):
    return ((value & 0x7f0000) >> 1) | (value & 0x7fff)


STOPWATCH_TRAMPOLINE_SNES = 0x37FFF0
STOPWATCH_TRAMPOLINE_PC = snes_to_pc(STOPWATCH_TRAMPOLINE_SNES)
STOPWATCH_TRAMPOLINE_SIZE = 0x10
EXPECTED_BASE_BYTES = bytes(STOPWATCH_TRAMPOLINE_SIZE)

CALLER = snes_to_pc(0x20DB75)
CALLER_ORIG = bytes((0x20, 0x5b, 0xd8, 0x6b))  # JSR $D85B; RTL
CALLER_NEW = bytes((0x5c, 0xf0, 0xff, 0x37))   # JML $37:FFF0
# $20:E4D6 is an existing PLB; RTL epilogue in the pinned base patch. The
# timer routine returns there via RTS, restoring the DB saved below before
# returning through the original caller's untouched long-return stack frame.
RETURN_EPILOGUE_SNES = 0x20E4D6
RETURN_EPILOGUE_PC = snes_to_pc(RETURN_EPILOGUE_SNES)
EXPECTED_RETURN_EPILOGUE = bytes((0xab, 0x6b))  # PLB; RTL
TRAMP_CODE = bytes((
    0x8b,             # PHB
    0xe2, 0x20,       # SEP #$20
    0xa9, 0x7e,       # LDA #$7E
    0x48,             # PHA
    0xab,             # PLB
    0xc2, 0x20,       # REP #$20
    0xf4, 0xd5, 0xe4, # PEA $E4D5; timer RTS advances to $20:E4D6
    0x5c, 0x5b, 0xd8, 0x20, # JML $20:D85B
))
assert len(TRAMP_CODE) == STOPWATCH_TRAMPOLINE_SIZE
TRAMPOLINE_BYTES = TRAMP_CODE
TIMER_FLAG = 0x180190


def main():
    if len(sys.argv) != 2:
        print("usage: alttpr-timerpatch.py <seed.sfc>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    rom = bytearray(open(path, "rb").read())
    reservation_end = STOPWATCH_TRAMPOLINE_PC + STOPWATCH_TRAMPOLINE_SIZE
    if len(rom) < reservation_end:
        raise RuntimeError("ROM too small")
    if rom[TIMER_FLAG] == 0:
        print("timerpatch: timer disabled")
        return 0
    caller = bytes(rom[CALLER:CALLER + len(CALLER_NEW)])
    if caller == CALLER_NEW:
        existing = bytes(rom[STOPWATCH_TRAMPOLINE_PC:reservation_end])
        if existing == TRAMPOLINE_BYTES:
            if bytes(rom[RETURN_EPILOGUE_PC:RETURN_EPILOGUE_PC + 2]) != \
                    EXPECTED_RETURN_EPILOGUE:
                raise RuntimeError("Stopwatch return epilogue changed.")
            print("timerpatch: already patched")
            return 0
        raise RuntimeError("timer caller patched but trampoline differs")
    if caller != CALLER_ORIG:
        raise RuntimeError("unexpected timer caller bytes: " +
                           caller.hex(" "))
    if bytes(rom[STOPWATCH_TRAMPOLINE_PC:reservation_end]) != \
            EXPECTED_BASE_BYTES:
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
    with open(path, "wb") as output:
        output.write(rom)
    print("timerpatch: applied DB=$7E trampoline at $37:FFF0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
