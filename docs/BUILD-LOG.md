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
- [ ] Wire DR into Recalbox 10 configgen (rootfs is READ-ONLY — needs overlay path)
- [ ] Port KEEP scripts: menu, MSU attach, tracker, gamelist glue; rewrite generate.sh for DR
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

- **Art assets recovered from the removed NVMe** (ext4) using a pure-python ext4
  reader on Windows (WSL had no distro; `wsl --mount` unavailable). Raw device
  reads must be 512-byte aligned. Recovered logo, sprites, overlays, sprites.json,
  msu-packs.json, full tracker app, and all KEEP scripts — now committed to the
  repo (were never in git before). Deployed the art PNGs to the Pi.
- **Recalbox 10 theme system differs from v9**: `recalbox-next` uses unified
  `_views/_partials/systems/<sys>.xml` + `data/arts/<sys>` instead of per-system
  folders. The old `build_theme.sh` (clone the `snes` folder) does NOT apply.
- **Carousel strip logo for a NEW custom system**: verified via themes.log that
  the carousel strip logo is drawn from ES's *internal* `${system.logo}`, which is
  populated only for systems ES knows (Favorites/Ports get their strip logo this
  way despite an empty theme-partial include). A brand-new system name ("alttpr")
  has no internal logo mapping, so the strip shows the fullname as TEXT — and no
  theme file overrides the strip for an unknown system. Options: (a) accept the
  text label (functional), (b) patch ES's internal system/logo table (binary/
  source-level, involved), (c) rename the system to a known one (wrong identity).
  Logo assets are sized correctly (254x90) and installed; the detail-view logo
  partial is valid. Carousel-strip logo deferred as an ES-internals limitation.

- Recalbox only serves the *latest* image per board; 9.2.3-Pulstar (live Pi)
  isn't downloadable, so the rebuild targets 10.0.8.
- Recalbox 10 uses a newer EmulationStation — validate the ES restart +
  userscript event names before trusting the refresh worker.
- Python DR supports Python 3.7-3.10; Recalbox ships 3.11 -> reconcile at engine step.
- Windows won't natively write the ext4 partitions; provisioning is done over SSH
  on the running Pi, not by editing the card offline.
