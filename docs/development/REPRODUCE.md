# Reproduce this build from scratch

End-to-end steps to rebuild the ALTTPR console on a fresh card. Every command
and file needed is in this repo. Two profiles are covered:

- **Clean build** — a blank card, whole SHARE partition converted to ext4 (what
  this repo was validated with).
- **Overlay install** — an existing Recalbox you don't want to wipe; the engine
  runs from a loopback ext4 image on the existing exFAT share (see the note at
  the end).

## 0. Prerequisites

- Raspberry Pi 5 (aarch64), 256 GB A2 microSD.
- A legal base ROM: *A Link to the Past (Japan) v1.0*, unheadered, renamed
  `alttp-jp10.sfc`. **md5 `03a63945398191337e896e5771f77173`.** Never committed.
- A PC to flash the card and SSH to the Pi.

## 1. Flash Recalbox 10 (Pi 5)

- Image: `recalbox-rpi5_64.img.xz` from https://www.recalbox.com/download/
  (validated: 10.0.8, SHA1 `1eb7892530927cc868b08b07e68ca006f8c0e8b2`).
- Flash with Raspberry Pi Imager (GUI is most reliable on Windows; scripted raw
  writes are blocked by the OS auto-mounting the new partitions mid-write).
- Boot the Pi once (first boot expands the filesystem and self-reboots). If a
  reboot ever hangs on this build, hard power-cycle — it's safe after a `sync`.
- Connect it to the network and note its IP. Default SSH login: `root` /
  `recalboxroot`.

## 2. Convert the SHARE partition to ext4

Only `mmcblk0p2` (LABEL=SHARE) changes. p1 (FAT boot) and p3 (ext4 overlay) are
left alone. ext4 is required for **symlinks** (MSU music attach), journaling
(durability without the IOPS-killing `sync` remount), and exec.

`adapters/recalbox/ext4-convert.sh` does the live-unmount version, but the
reliable method is the RAM-share dance (a live share can't be cleanly unmounted;
killing the holders kills your SSH session):

```sh
# On the Pi:
mount -o remount,rw /boot
sed -i 's/^;*sharedevice=.*/sharedevice=RAM/' /boot/recalbox-boot.conf
sync; reboot -f            # share now tmpfs; p2 is free

# after reboot:
umount /recalbox/share/externals/mmc0 2>/dev/null || umount -l /recalbox/share/externals/mmc0
mkfs.ext4 -F -L SHARE /dev/mmcblk0p2
U=$(blkid /dev/mmcblk0p2 | sed -n 's/.* UUID="\([^"]*\)".*/\1/p')
mount -o remount,rw /boot
sed -i '/^sharedevice=/d' /boot/recalbox-boot.conf
echo "sharedevice=DEV $U" >> /boot/recalbox-boot.conf   # DEV mode auto-detects ext4
sync; reboot -f
```

After reboot, `/recalbox/share` mounts ext4 (rw,noatime). Verify symlinks work.
NOTE: reformatting the share regenerates the SSH host keys (they live on the
share), so your SSH client will see a changed host key — expected.

## 3. Install the engine (Python Door Randomizer)

`portable-core/install-deps.sh` — run it on the Pi. It:
1. downloads pinned codemann8/ALttPDoorRandomizer commit
   `7e14fddab00b847d6eccf0931b365a5774c5476a` from the OverworldShuffle
   branch to `/recalbox/share/alttpr/`,
2. bootstraps pip (Recalbox ships none) to `/recalbox/share/alttpr/pydeps`,
3. installs DR's deps (`aenum fast-enum python-bps-continued colorama aioconsole
   websockets pyyaml`) into `/recalbox/share/alttpr/pydeps/site`.

Install the base ROM in a hidden, root-only location on the ext4 share:

```sh
PRIVATE=/recalbox/share/system/.alttpr-private
DEST=$PRIVATE/base/alttp-jp10.sfc
mkdir -p "$PRIVATE/base"
chmod 700 "$PRIVATE" "$PRIVATE/base"
install -o root -g root -m 0400 alttp-jp10.sfc "$DEST"
md5sum "$DEST"  # must be 03a63945398191337e896e5771f77173
chattr +i "$DEST"
```

The ROM is intentionally outside the engine and ROM-browser trees, visible only
through an SSH/root session. It is never committed.

Smoke test:
```sh
PYTHONPATH=/recalbox/share/alttpr/pydeps/site \
  python3 /recalbox/share/alttpr/ALttPDoorRandomizer-OverworldShuffle/DungeonRandomizer.py \
  --rom /recalbox/share/system/.alttpr-private/base/alttp-jp10.sfc --mode open --goal ganon \
  --swords random --create_rom --spoiler full --outputpath /tmp/t --outputname test
```

## 4. Deploy the integration scripts

Copy onto the Pi (strip CRLF, chmod +x):

| Repo file | Pi path |
|-----------|---------|
| `portable-core/bin/*` (incl. `words/`) | `/recalbox/share/alttpr/bin/` |
| `adapters/recalbox/alttprGenerator.py` | `/recalbox/share/alttpr/es/` |
| `adapters/recalbox/alttpr-install.sh`  | `/recalbox/share/alttpr/es/` |
| `adapters/recalbox/custom.sh`          | `/recalbox/share/system/custom.sh` |
| `adapters/recalbox/userscripts/alttpr-refresh.sh` | `/recalbox/share/userscripts/` |

Then run `bash /recalbox/share/alttpr/es/alttpr-install.sh` once. It:
- installs a fail-closed `$37:FFE0-$37:FFFF` room-allocator reservation for the
  Stopwatch trampoline,
- remounts `/` rw and installs the configgen generator at
  `configgen/generators/alttpr/`,
- patches `emulatorlauncher.py` getGenerator dispatch + `recalboxFiles.py`
  recalboxBins,
- adds the `alttpr` system to `systemlist.xml`,
- creates the `.alttpr` launcher tiles under `roms/alttpr/`.

`custom.sh` (run every boot by `/etc/init.d/S99custom`) re-runs the installer, so
the rootfs hook self-heals even though rootfs overlay changes may not survive an
unclean shutdown.

## 5. Install sprites and curated MSU packs

Run `portable-core/install-content.sh` on the Pi after deployment. It downloads
the current official `.zspr` library from `alttpr.com/sprites`, uses the committed
catalog snapshot if the API is unavailable, and installs only the curated MSU
selection in `portable-core/bin/data/msu-packs.json`. The pinned official ARM64
`7zz` extractor supports ZIP, 7Z, and RAR packs.

## 6. Endgame hook (freeze fix)

`adapters/recalbox/userscripts/alttpr-refresh.sh` runs on ES `endgame`: a
DETACHED, time-bounded `sync` (never a bare blocking `sync` — that froze the
frontend when the old NVMe dropped off the bus). Recalbox 10's native file
watcher owns library refreshes; this hook never restarts EmulationStation.

## 7. Golden image

Once verified, power off and image the whole card (all 3 partitions) to a `.img`
for one-step re-flash / cloning. See `BUILD-LOG.md`.

## Overlay-install profile (existing Pi, no reformat)

Instead of step 2, create a loopback ext4 image on the existing exFAT share and
mount it at `/recalbox/share/alttpr`. MSU packs (large) stay on the exFAT share
as plain files; only the ~engine + seeds need the ext4 image (symlinks/exec).
This is non-destructive and reversible (delete the image file to uninstall).
