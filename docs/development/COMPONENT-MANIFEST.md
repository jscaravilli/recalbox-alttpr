# Component Manifest — KEEP / REWRITE / DROP

Decision list for the single-SD (ext4) + Python Door Randomizer rebuild.
Derived by challenging every script in the original `alttpr-recalbox` repo.

Two changes drive the cuts: the **engine swap** (Python DR replaces PHP + box64)
and the **single ext4 card** (no multi-device storage glue).

## DROP — eliminated by the engine swap
- `patches/Enemizer.php` — PHP app patch (no PHP app)
- `patches/Randomize.php` — PHP CLI option patch (no PHP app)
- `scripts/fetch-box64.py` — box64 fetch (DR is native ARM Python)
- `scripts/fetch-enemizer.sh` + EnemizerCLI — DR does boss/enemy shuffle in Python*
- box64 (~74 MB) + static PHP (~30 MB) + sporchia app (~197 MB) — replaced by DR

\* VERIFY on hardware: confirm the DR fork implements enemizer natively and does
not shell out to an x86 EnemizerCLI for any enemy/boss option.

## DROP — obsoleted by the single ext4 card
- `system/alttpr-storage.sh` — direct/disk/image abstraction; whole card is ext4
  now, engine runs "direct". Dead code.
- Seeds bind-mount logic — seeds live directly on ext4 `roms/alttpr/SEEDS`
- `custom.sh` `remount,sync` hardening — exFAT durability hack; hurts SD IOPS,
  ext4 journaling covers it. Remove.
- `bootstrap.sh` storage chooser — no storage decision left; collapses to a
  plain copy-in installer.

## PHP-CLI workarounds
- `alttpr-hashfix.py` — worked around the PHP CLI stamping identical file-select
  icons; DR emits a proper per-seed hash. Likely unneeded.
- `alttpr-timerpatch.py` — KEEP, reworked for the current Python-DR base patch.
  The same DB bug remains at relocated addresses. The current patch retargets
  complete frame gate at `$20:DB73` to a DB=$7E trampoline in the explicitly
  reserved final 32 bytes of room-data bank `$37` (`$37:FFE0-$37:FFFF`), then
  calls the relocated timer routine at `$20:D85B`. The room allocator is capped
  at `$37:FFE0`; exact pre/post byte assertions fail closed if upstream reclaims
  the reservation.

## KEEP — engine-independent
- `alttpr-menu.py` (pygame UI) — KEEP; remap option flags to DR CLI names
- `alttpr-msu.py` + `msu-packs.json` + MSU attach — KEEP (the 18.4 GB music feature)
- Tracker suite (`alttpr-tracker-*`, `engine/tracker/*`, QR overlay) — KEEP
- `alttpr-spoiler.py` — KEEP (verify spoiler JSON parser vs DR format)
- `alttpr-sprites.py` + `sprites.json` — KEEP (verify DR sprite/.zspr flag)
- `alttpr-cleanup.py` / `.sh` — KEEP (housekeeping)
- `alttpr-name.py` + `words/` — KEEP (nickname UX)
- `alttpr-btime.py` — KEEP (seed birth-time via statx; works on ext4)
- `alttpr-refresh.sh` — KEEP only as a detached/time-bounded durability flush.
  Recalbox 10 owns ROM/gamelist watching and relaunches; the old
  `alttpr-refresh-worker.sh` was removed because force-restarting ES from an
  endgame child caused restart/reboot loops.
- `alttpr-gamelist-merge.py` — retained as a repair utility, not called at exit.

## REWRITE — core engine swap
- `alttpr-generate.sh` — replace `php artisan alttp:randomize` with
  `python3 DungeonRandomizer.py ...`; adapt nickname/MSU/gamelist post-processing
  to DR output filenames + flags.

## MUST RE-FIT for Recalbox 10 (version risk)
- `alttpr-install.sh` + `alttprGenerator.py` — inject the configgen generator into
  the OS Python site-packages. Recalbox 10 (ES-next) may move the path
  (`/usr/lib/python3.11/site-packages/configgen/...`) or change the configgen
  generator API. Validate live before trusting.

## Verify-on-hardware checklist
1. DR enemizer is native Python (no x86 EnemizerCLI dependency).
2. Recalbox 10 configgen generator path + API.
3. DR spoiler JSON + sprite/.zspr flag names (for spoiler/sprites scripts).
4. Python version: DR supports 3.7-3.10; Recalbox ships 3.11 — test + patch or
   bundle a compatible interpreter.
