# recalbox-alttpr-portable

Reproducible build of an **A Link to the Past Randomizer (ALTTPR)** console on
Recalbox / Raspberry Pi 5, using the **Python Door Randomizer**
([codemann8/ALttPDoorRandomizer](https://github.com/codemann8/ALttPDoorRandomizer),
`OverworldShuffle` branch) instead of the legacy PHP + box64 generator chain.

## Why this repo exists

The original system ran on a 3-device storage split (SD boot + USB share + NVMe
app). A flaky WD_BLACK SN850X NVMe intermittently dropped off the PCIe bus,
freezing EmulationStation on game exit (a global `sync` in the endgame hook
blocked on the downed drive). This rebuild consolidates everything onto a single
256 GB A2 SD card with an **ext4 share**, swaps in a reproducible Python engine,
and captures a **golden image** so the whole console can be re-flashed in minutes.

## Target hardware

- Raspberry Pi 5 (8 GB), aarch64
- 256 GB A2 / U3 / V30 microSD (Samsung PRO Plus / SanDisk Extreme Pro)
- Base ROM: *Zelda no Densetsu - Kamigami no Triforce (Japan) v1.0* (not stored here)

## Layout

```
adapters/recalbox/    Recalbox-specific integration (ES event hooks, storage layer)
  userscripts/        EmulationStation event-driver scripts (endgame hook, etc.)
portable-core/        Distro-agnostic logic (engine driver, gamelist merge)
docs/                 Build notes, portability audit, reproduction steps
build/                Flashing + provisioning scripts (Windows-side)
```

## Base image

- Recalbox **10.0.8** for rpi5_64 (`recalbox-rpi5_64.img.xz`, SHA1
  `1eb7892530927cc868b08b07e68ca006f8c0e8b2`). The image itself is not committed.

## Status

See `docs/BUILD-LOG.md` for the staged build progress.
