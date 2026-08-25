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
- [ ] Boot Pi on new card; SSH in
- [ ] Convert share to ext4; restore saves/seeds
- [ ] Install app; swap PHP/box64 -> DungeonRandomizer.py (Python 3.7-3.10 vs Pi 3.11)
- [ ] Adapt ES integration hooks to Recalbox 10 (ES-next); validate
- [ ] Verify seed gen / MSU / tracker / saves end-to-end
- [ ] Capture golden .img

## Notes / gotchas

- Recalbox only serves the *latest* image per board; 9.2.3-Pulstar (live Pi)
  isn't downloadable, so the rebuild targets 10.0.8.
- Recalbox 10 uses a newer EmulationStation — validate the ES restart +
  userscript event names before trusting the refresh worker.
- Python DR supports Python 3.7-3.10; Recalbox ships 3.11 -> reconcile at engine step.
- Windows won't natively write the ext4 partitions; provisioning is done over SSH
  on the running Pi, not by editing the card offline.
