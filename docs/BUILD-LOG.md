# Build Log

Staged rebuild of the ALTTPR console onto a single SD card. Times in CDT.

## Diagnosis (root cause of the freeze)

- Symptom: system freezes after quitting a ROM that ran a long time.
- Hardware: Pi 5 (8 GB), WD_BLACK SN850X 1 TB NVMe at PCIe Gen2 x1, swap=0.
- NVMe intermittently drops off the bus at boot despite APST/ASPM already
  disabled on the kernel cmdline:
  `nvme nvme0: controller is down; will reset: CSTS=0xffffffff`.
- During play the NVMe is idle (ROM+save live on the exFAT share). On exit the
  endgame hook ran a **global blocking `sync`** which stalls on the downed NVMe
  in uninterruptible I/O -> frontend freeze. Longer session = colder/more
  marginal drive when the flush finally hits it.

## Fixes

- **Applied to live Pi**: endgame hook `sync` -> `setsid sh -c 'timeout 15 sync' &`
  (detached, time-bounded). Backup: `alttpr-refresh.sh.bak-20260824-184358`.
- **Rebuild** (this repo): retire the NVMe entirely; single 256 GB A2 SD card,
  ext4 share, Python Door Randomizer engine, golden-image capture.

## Storage roles (original system)

| Device            | Mount                         | Role                         |
|-------------------|-------------------------------|------------------------------|
| SD "SR256" 256 GB | /boot, /overlay, externals    | OS / boot                    |
| USB "USB DISK 3.0"| /recalbox/share (exFAT)       | ROMs, saves, BIOS, configs   |
| NVMe SN850X 1 TB  | /recalbox/share/alttpr (ext4) | ALTTPR app (350 MB) + 18.4 GB MSU |

Only ~350 MB (engine binaries) truly needs exec/ext4; the 18.4 GB MSU is just
read-only audio.

## Stages

- [x] Diagnose freeze; apply live hook fix
- [x] Decide: single 256 GB A2 SD, ext4 share, Python DR (repeatability-first)
- [x] Download Recalbox 10.0.8 rpi5_64 (SHA1 verified)
- [x] Flash SD (Raspberry Pi Imager GUI; scripted raw writes blocked by Windows)
- [x] Back up live saves/seeds/config to PC (`live-saves-seeds.tgz`, 30 MB)
- [x] Remove NVMe (user)
- [x] Boot Pi on new card; SSH in (192.168.68.79, Wi-Fi)
- [x] Convert share to ext4 (RAM-share method; DEV <uuid> auto-detect; survives reboot)
- [x] Install DR + deps on ext4 share; VALIDATED seed generation on Python 3.11
- [x] Wire DR into Recalbox 10 configgen (self-healed through `custom.sh`)
- [x] Restore polished menus + curated ES layout; map baseline options to DR
- [ ] Verify seed gen / MSU / tracker / saves end-to-end in ES
- [ ] Capture golden .img

## VALIDATED (engine swap proven)

On Recalbox 10.0.8 / Python 3.11.8, ext4 share:
- DR deps (aenum, fast-enum, python-bps-continued, colorama, aioconsole,
  websockets, pyyaml) pip-installed to `/recalbox/share/alttpr/pydeps/site`
  (pip bootstrapped via get-pip; rootfs site-packages is read-only).
- `DungeonRandomizer.py --rom base --mode open --goal ganon --swords random
  --create_rom --spoiler full` produced a 2 MB patched playable ROM +
  41 KB spoiler in ~12s. Native item/dungeon/boss/enemy/overworld shuffle —
  NO box64, NO PHP, NO EnemizerCLI. Base ROM md5 03a63945... (JAP 1.0).

## ext4 conversion method (what worked)

Live-unmount of the share fails (system holds it; killing holders kills the SSH
session). Reliable method:
1. Set `sharedevice=RAM` in /boot/recalbox-boot.conf; reboot -> share is tmpfs,
   p2 is free (only auto-mounted once as external /externals/mmc0).
2. `umount` that single point; `mkfs.ext4 -F -L SHARE /dev/mmcblk0p2`.
3. Set `sharedevice=DEV <uuid>` (DEV mode auto-detects ext4 via blkid; INTERNAL
   mode hardcodes an exfat mount and would fail on ext4). New UUID
   754e5c83-88d1-4bd1-a8a7-5482826c290b.
4. Reboot -> `/recalbox/share` mounts ext4 (rw,noatime, NO sync). Symlinks +
   exec confirmed working. `reboot` hangs on this build; use `reboot -f` or a
   hard power cycle (safe after sync).

## Notes / gotchas

- **Menus restored and validated**: recovered the original `box.png`/`seed.png`
  from the old USB share, restored the three-action + `SEEDS` layout, deployed
  the fullscreen custom/cleanup/spoiler pygame tools, and mapped the baseline
  option payload to Python DR. Recalbox 10's SDL driver name is case-sensitive:
  use `KMSDRM`, not v9's lowercase `kmsdrm`. Custom menu default generation
  produced a real 2 MiB ROM + text spoiler. Spoiler browser supports DR
  `.spoiler.txt` and legacy `.spoiler.json`.
- **Both bundled themes polished**: `recalbox-next` and `recalbox-next-v9`
  receive the committed ALTTPR logo, the user-supplied transparent sprite
  montage, and project/game information. The v9 adapter builds a native
  `alttpr/` system folder from its SNES structural baseline; the modern adapter
  installs unified assets/markdown and overrides all regional image paths.
  Framebuffer-verified on both themes. The installer also removes stale external
  `roms/alttpr` trees so Recalbox does not merge duplicate action tiles.
- **Optional content restored**: 513 official sprites are selectable (486 have
  recovered previews). The only HUD timer choice is Stopwatch, mapped to DR's
  `--timer display` / native `clock_mode = stopwatch`. Ten curated MSU packs
  plus Default are installed and alphabetized; generation was validated with a
  selected sprite, stopwatch, and 61 linked MSU files. `Zelda & Chill` is not
  installed because its public archive contains recipes only and explicitly
  requires the separately purchased GameChops albums.
- **Exit loop fixed**: the v9 refresh worker raced Recalbox 10's native file
  watcher by stopping/starting ES from the `endgame` child. Generation and
  cleanup no longer rewrite gamelists, create refresh flags, or restart ES.
  Legacy hooks on external storage are removed. The endgame hook retains only
  `setsid timeout 15 sync`, preserving the original storage-freeze mitigation.
- **Expanded Python DR menu**: 66 rows now include entrance and door shuffle,
  door intensity/types/traps/key logic, overworld shuffle/layout/crossing/
  terrain/mixed-world/whirlpools, flute spots, dungeon item/prize/counter
  placement, shops/followers/key drops, enemy logic, and related options.
  Entrance, door, and overworld/flute modes generated successfully. The upstream
  DR build cannot combine non-vanilla entrance and overworld shuffle; the menu
  now rejects that combination with an explicit error.
- **MSU runtime verified**: Snes9x reported `ROM+RAM+BAT+MSU-1` and opened the
  selected `.msu` plus all PCM files. New MSU seeds also enable DR's
  `msu_resume` patch.
- **Autotracker completion**: the bridge and HTTP services were already running
  on ports 23074 and 8080, but the web root was empty. The committed 154-file
  tracker app is now part of `deploy.sh` and deployed to the Pi.
- **Static live-tracker URL**:
  `http://recalbox.local:8080/itemtracker.html` is shown in both system themes.
  The page connects to the bridge on the serving host and polls `/seedinfo`.
  The server supports the Python-DR filename format and reads mode/logic/goal
  from the active seed's text spoiler. Verified through Recalbox's exact
  RetroArch launch config: it reported Bobbing Hootenanny / standard / ganon.
  Tracker process management now matches exact `/proc` script arguments instead
  of broad `pgrep -f`, which previously confused invoking shells with services.
- **System helper refresh**: both themes now present a concise “What is ALTTPR?”
  explanation instead of build metadata. A committed off-white/near-black QR for
  the permanent tracker URL is composed beside the sprite montage. The source QR
  and composition script are committed so the URL/art can be regenerated.
- **Timer and preview follow-up**: Stopwatch remains the default with Disabled
  second. Deterministic fixed-seed tests prove Stopwatch changes ROM bytes.
  All 513 sprites now have previews; the 27 forbidden upstream preview URLs are
  rendered locally from their ZSPR standing frame using the stdlib PNG writer.
- **Stopwatch freeze root cause restored**: Python DR relocated but retained the
  old base-patch Data Bank bug. Current Stopwatch ROMs mixed long WRAM reads with
  absolute `$BExx` writes in the routine at `$20:D85B`; with a non-$7E DB, its
  divide/subtract loop never updates WRAM and freezes. `alttpr-timerpatch.py`
  retargets caller `$20:DB75` to a DB=$7E trampoline at `$37:FFF0`. The final
  16 bytes of bank `$37` are reserved by a hard room-allocator bound, and exact
  pre/post byte assertions prevent upstream changes from silently reclaiming it.
- **Custom menu organization/help**: nine nonselectable sections organize Seed
  Rules, Items & Progression, Entrances, Dungeon Doors, Overworld/Flute, Dungeon
  Items, Enemies/Bosses, Advanced Gameplay, and Cosmetics/Output. Navigation
  skips section headers. All 66 rows and 757 row/value combinations resolve to
  curated help; generic fallback text was removed.
- **Game audio fix**: the custom ALTTPR generator launched the nested SNES
  configgen without `XDG_RUNTIME_DIR`, so RetroArch could not find the running
  PulseAudio socket and continued silently. `alttprGenerator.py` now passes and
  embeds `/run/user/0` plus `unix:/run/user/0/pulse/native`. Verified with an
  actual nested SNES launch: RetroArch created a live Pulse sink-input on the
  HDMI sink.

- **Art assets recovered from the removed NVMe** (ext4) using a pure-python ext4
  reader on Windows (WSL had no distro; `wsl --mount` unavailable). Raw device
  reads must be 512-byte aligned. Recovered logo, sprites, overlays, sprites.json,
  msu-packs.json, full tracker app, and all KEEP scripts — now committed to the
  repo (were never in git before). Deployed the art PNGs to the Pi.
- **Recalbox 10 theme system differs from v9**: `recalbox-next` uses unified
  `_views/_partials/systems/<sys>.xml` + `data/arts/<sys>` instead of per-system
  folders. The old `build_theme.sh` (clone the `snes` folder) does NOT apply.
- **Carousel logo root cause and fix**: Recalbox ES `SystemView::addSystem()`
  uses the theme's `system/logo` image when its path resolves, otherwise it falls
  back to fullname text. Our first `alttpr.xml` used `./data/...`; because it is
  included from `_views/_partials/systems/`, that resolved under the partial
  directory and the file did not exist. Use
  `${root}/data/arts/systems_logos/alttpr.png`. With the recovered logo resized
  to 254x90, the ALTTPR logo renders correctly in the carousel (framebuffer
  verified).

- Recalbox only serves the *latest* image per board; 9.2.3-Pulstar (live Pi)
  isn't downloadable, so the rebuild targets 10.0.8.
- Recalbox 10 uses a newer EmulationStation — validate the ES restart +
  userscript event names before trusting the refresh worker.
- Python DR supports Python 3.7-3.10; Recalbox ships 3.11 -> reconcile at engine step.
- Windows won't natively write the ext4 partitions; provisioning is done over SSH
  on the running Pi, not by editing the card offline.
