# Bugs and fixes

This document separates upstream defects from integration defects introduced by
this project. Addresses are SNES LoROM addresses unless marked as PC/file
offsets.

## BUG-001 — Upstream Stopwatch can freeze

**Origin:** upstream base patch  
**Status:** fixed locally  
**Affected feature:** `--timer display`

### Symptom

The HUD Stopwatch can stop the game during normal play. The trigger is not tied
to one room; it depends on the Data Bank value when the timer update executes.

### Root cause

The timer routine at `$20:D85B` reads WRAM using long addresses but performs
some writes to `$BExx` with absolute addressing. Those writes depend on the
current Data Bank. When DB is not `$7E`, the divide/subtract loop updates the
wrong bank and can fail to terminate.

### Fix

The complete frame-gate sequence at `$20:DB73`:

```text
D0 03 20 5B D8 6B    BNE skip; JSR $D85B; skip: RTL
```

is replaced with:

```text
5C E0 FF 37 EA EA    JML $37:FFE0; NOP; NOP
```

The 32-byte reservation contains a trampoline that first preserves the original
1-in-32-frame update gate. Calculation frames save DB, select `$7E`, push a
controlled return address, and jump long to the original timer routine. Other
frames return directly:

```text
D0 10 8B E2 20 A9 7E 48 AB C2 20 F4 D5 E4 5C 5B D8 20 6B
```

The original routine’s `RTS` lands on an existing, asserted `PLB; RTL` epilogue
at `$20:E4D6`, restoring DB and returning through the caller’s original long
return frame.

### Safety contract

- `STOPWATCH_TRAMPOLINE_SNES = 0x37FFE0`
- `STOPWATCH_TRAMPOLINE_PC = snes_to_pc(STOPWATCH_TRAMPOLINE_SNES)`
- `STOPWATCH_TRAMPOLINE_SIZE = 0x20`
- The room-data allocator grows upward from `$37:8000` but may not advance past
  `$37:FFE0`; therefore its last permitted byte is `$37:FFDF`.
- The pristine reservation must be exactly 32 zero bytes.
- The return epilogue must remain exactly `AB 6B`.
- The patched reservation must exactly equal the payload plus zero padding.
- The five bytes before the replaced frame gate must remain
  `A5 1A 29 1F 00` (`LDA $1A; AND #$001F`).
- The unsafe former `$37:FFF0` patch is recognized and migrated only when both
  its caller and payload match exactly.
- `DataTables.py` must match the pinned pristine or locally patched SHA-256.

Any upstream drift fails generation rather than risking silent ROM corruption.

## BUG-002 — Former custom trampoline caused Dark Cross crashes

**Origin:** this project’s first Stopwatch workaround  
**Status:** fixed in commit `6483de7`  
**Affected builds:** Stopwatch ROMs patched at `$20:E000`

### Symptom

Two independently generated Standard seeds displayed the randomizer’s fatal
error screen when unlocking the Dark Cross small-key door. Other settings,
including boss shuffle and music, differed.

### Root cause

The first workaround placed a DB wrapper at `$20:E000` (PC `0x106000`) because
those bytes were zero in generated ROMs. Deeper analysis showed all of bank
`$20` is owned by the prebuilt `base2current.bps`; zero bytes there are not
proof of free space. The custom wrapper overwrote data consumed during the
key-door path.

This collision was local to this project. It is separate from BUG-001.

### Isolation matrix

All four ROMs loaded the same pre-door Dark Cross savestate and SRAM:

| Take-Any | Stopwatch | Result before fix | Result with `$37` fix |
|---|---:|---|---|
| None | Off | Pass | Pass |
| Random | Off | Pass | Pass |
| None | On | Fatal crash | Pass |
| Random | On | Fatal crash | Pass |

This eliminated Take-Any caves, Standard mode, the door flag itself, the
tracker, and boss shuffle as causes. Stopwatch was the discriminating variable.

### Fix

The `$20:E000` workaround was removed. New Stopwatch ROMs use the guarded
`$37:FFE0-$37:FFFF` reservation described in BUG-001. ROMs carrying the exact
unsafe `$37:FFF0` trampoline signature are migrated automatically.

## BUG-003 — Entrance generation can fail stochastically

**Origin:** upstream layout/fill algorithms  
**Status:** mitigated in commit `eb3c2bb`

Valid entrance modes occasionally fail for a particular random seed with
`Fill.py` or `EntranceShuffle2.py` exceptions. The wrapper retries only those
known stochastic upstream failures with a fresh seed, up to five attempts.
Other errors fail immediately and the final engine message is shown.
