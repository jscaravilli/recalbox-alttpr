# Install ALTTPR on Recalbox

This guide covers clean installation and repair of an existing installation.
Read the whole guide before formatting a card.

## Requirements

- Raspberry Pi 5
- Recalbox **10.0.8** for Raspberry Pi 5 (`rpi5_64`)
- A2/U3/V30 microSD card (256 GB recommended)
- PC with Raspberry Pi Imager, Git, SSH, and SCP
- Network connection shared by the PC and Raspberry Pi
- Legally obtained, unheadered Japanese v1.0 ALTTP ROM

Recalbox 10.0.8 is the only supported release. Earlier versions are
incompatible with the Python 3.11, configgen, and theme integration used by this
build. Newer versions must be validated before use.

The required base-ROM MD5 is:

```text
03a63945398191337e896e5771f77173
```

> [!CAUTION]
> **Destructive step:** the installer converts the file system of the SHARE partition to ext4.
> This erases everything on that partition. Do it only on the new card, immediately after its
> first boot. Run the installer before adding ROMs and BIOS files to the SD CARD.
> If your ROMs and BIOS files are on a USB drive, they should be fine.

## Supported installation scenarios

| Scenario | SHARE requirement | Data impact | Installation flags |
|---|---|---|---|
| Clean Recalbox installation | Recalbox has completed first boot and created SHARE as exFAT | Erases all SHARE data and recreates it as ext4 | `--confirm-install` `--confirm-format` |
| Repair or update existing ALTTPR | SHARE is already ext4 | Preserves SHARE data | `--confirm-install` |
| Install ALTTPR on an existing Recalbox system, which is already loaded with ROMs/BIOS | Unsupported | DELETES SHARE DATA; MOVE SHARE DATA TO EXTERNAL USB BEFORE RUNNING the CLEAN INSTALL mode | N/A |

The installer runs from another computer over SSH while the microSD card remains
in the Raspberry Pi. It does not install directly to a card connected to the PC.

Every scenario requires the verified base ROM on the PC. During a repair, the
installer revalidates that ROM and replaces the private copy while preserving
generated seeds, saves, MSU packs, Recalbox settings, and other SHARE content.

Run the installer without `--confirm-install` first. This is a read-only dry run.
For a clean-install preview, include `--confirm-format`; formatting still cannot
occur unless `--confirm-install` is also supplied.

## 1. Prepare the PC

Install:

- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- Git
- An SSH client (`ssh` and `scp`)

Windows users can run the repository shell scripts from **Git Bash**. macOS and
Linux already provide a compatible shell and SSH client.

Clone this repository:

```sh
git clone https://github.com/jscaravilli/recalbox-alttpr.git
cd recalbox-alttpr
```

## Installer modes

The installer is read-only unless `--confirm-install` is supplied. On an
existing ext4 installation, start with:

```sh
./install.sh --pi 192.168.1.50 --rom /path/to/alttp-jp10.sfc
```

A successful dry run reports the checks and planned actions without changing
the PC, Recalbox settings, or files. To install or repair ALTTPR while preserving
everything already on SHARE:

```sh
./install.sh --confirm-install --pi 192.168.1.50 \
  --rom /path/to/alttp-jp10.sfc
```

Formatting requires a second, explicit confirmation. Preview a clean install
with:

```sh
./install.sh --confirm-format --pi 192.168.1.50 \
  --rom /path/to/alttp-jp10.sfc
```

To perform the clean installation, supply both confirmations:

```sh
./install.sh --confirm-install --confirm-format --pi 192.168.1.50 \
  --rom /path/to/alttp-jp10.sfc
```

`--confirm-install` alone never formats SHARE. A non-formatting installation
requires SHARE to already be ext4. `--skip-format` and `--dry-run` were removed
because preserving SHARE and dry-run are now the respective defaults.

Have your legally obtained, unheadered Japanese v1.0 ROM available on the PC.
This guide calls it `alttp-jp10.sfc`.

Verify it before continuing:

```sh
# Linux
md5sum alttp-jp10.sfc

# macOS
md5 alttp-jp10.sfc

# Windows PowerShell
Get-FileHash .\alttp-jp10.sfc -Algorithm MD5
```

The result must be:

```text
03a63945398191337e896e5771f77173
```

## 2. Flash and boot Recalbox

1. In Raspberry Pi Imager, select **Recalbox 10.0.8 for Raspberry Pi 5
   (`rpi5_64`)**.
2. Write it to the new microSD card.
3. Insert the card, connect the Pi to Ethernet or Wi-Fi, and power it on.
4. Wait for the first-boot expansion and automatic reboot to finish.
5. In Recalbox, enable SSH and note the IP address.

The default SSH credentials are:

```text
user: root
password: recalboxroot
```

The validated image filename is `recalbox-rpi5_64.img.xz`; its SHA-1 is
`1eb7892530927cc868b08b07e68ca006f8c0e8b2`.

Set a shell variable on the PC for the remaining examples:

```sh
PI=192.168.1.50       # replace with the Pi's actual address
ssh root@$PI
```

Accept the SSH host key when prompted, then exit back to the PC:

```sh
exit
```

## 3. Convert only SHARE to ext4

**On the PC**, connect over SSH:

```sh
ssh root@$PI
```

**On the Pi**, run:

```sh
mount -o remount,rw /boot
sed -i 's/^;*sharedevice=.*/sharedevice=RAM/' /boot/recalbox-boot.conf
sync
reboot -f
```

Wait for the Pi to return. **On the PC**, remove the old host key if SSH reports
that it changed, then reconnect:

```sh
ssh-keygen -R "$PI"
ssh root@$PI
```

**On the Pi**, verify the target and format it as one guarded operation:

```sh
set -eu
PART=/dev/mmcblk0p2
test -b "$PART"
test "$(blkid "$PART" | sed -n 's/.* LABEL="\([^"]*\)".*/\1/p')" = "SHARE"
MOUNTPOINT=$(awk -v part="$PART" '$1 == part { print $2; exit }' /proc/mounts)
if [ -n "$MOUNTPOINT" ]; then
  umount "$MOUNTPOINT" || {
    echo "ERROR: normal unmount failed; refusing to format." >&2
    exit 1
  }
fi
if awk -v part="$PART" '$1 == part { found=1 } END { exit !found }' /proc/mounts
then
  echo "ERROR: $PART is still mounted; refusing to format." >&2
  exit 1
fi
mkfs.ext4 -F -L SHARE "$PART"
U=$(blkid "$PART" | sed -n 's/.* UUID="\([^"]*\)".*/\1/p')
test -n "$U"
mount -o remount,rw /boot
sed -i '/^sharedevice=/d' /boot/recalbox-boot.conf
echo "sharedevice=DEV $U" >> /boot/recalbox-boot.conf
sync
reboot -f
```

Wait for the Pi to return. **On the PC**, clear the old key again if SSH reports
a change, reconnect, and verify:

```sh
ssh-keygen -R "$PI"
ssh root@$PI
```

**On the Pi**, run:

```sh
awk '$2 == "/recalbox/share" { print $3 }' /proc/mounts
```

Expected output:

```text
ext4
```

## 4. Install the pinned randomizer engine

From the repository root on the PC:

```sh
scp portable-core/install-deps.sh portable-core/requirements-recalbox.txt \
  root@$PI:/tmp/
ssh root@$PI "sed -i 's/\r$//' /tmp/install-deps.sh &&
  chmod +x /tmp/install-deps.sh &&
  /tmp/install-deps.sh"
```

This installs upstream commit
`7e14fddab00b847d6eccf0931b365a5774c5476a` and Python dependencies under
`/recalbox/share/alttpr`.

## 5. Install the private base ROM

Upload the verified ROM:

```sh
scp alttp-jp10.sfc root@$PI:/tmp/alttp-jp10.sfc
```

Install it outside both visible ROM and engine directories:

```sh
ssh root@$PI '
  set -e
  PRIVATE=/recalbox/share/system/.alttpr-private
  DEST=$PRIVATE/base/alttp-jp10.sfc
  mkdir -p "$PRIVATE/base"
  chmod 700 "$PRIVATE" "$PRIVATE/base"
  test "$(md5sum /tmp/alttp-jp10.sfc | cut -d" " -f1)" = \
    "03a63945398191337e896e5771f77173"
  install -o root -g root -m 0400 /tmp/alttp-jp10.sfc "$DEST"
  rm -f /tmp/alttp-jp10.sfc
  chattr +i "$DEST"
'
```

## 6. Deploy the console integration

From the repository root on the PC:

```sh
chmod +x portable-core/deploy.sh
./portable-core/deploy.sh "$PI"
```

Install the official sprite library:

```sh
ssh root@$PI "/recalbox/share/alttpr/install-content.sh sprites"
```

MSU downloads are optional and can be large. Install one named pack:

```sh
ssh root@$PI \
  "/recalbox/share/alttpr/install-content.sh msu 'A Link to the Past Enhanced'"
```

Or install every curated pack:

```sh
ssh root@$PI "/recalbox/share/alttpr/install-content.sh msu"
```

One unavailable third-party pack does not affect the original SNES soundtrack
or packs already installed.

Users can later add their own legally obtained packs over the network without
SSH. See [MSU-IMPORT.md](MSU-IMPORT.md).

Reboot:

```sh
ssh root@$PI "sync; reboot"
```

## 7. Validate the installation

After the Pi returns:

```sh
ssh root@$PI /recalbox/share/alttpr/bin/alttpr-healthcheck.sh
```

Every required check must report `PASS`, ending with:

```text
ALTTPR health check passed.
```

Continue with the [user guide](USER-GUIDE.md).

On the television:

1. Confirm **ALTTPR - Link to the Past Randomizer** appears as a system.
2. Open **Generate Custom Seed**.
3. Leave the defaults and choose **Generate & Play**.
4. Confirm the generated seed launches with sound.
5. On another device, open
   `http://recalbox.local:8080/itemtracker.html`.

## 8. Secure the finished console

The default SSH password is public knowledge. After validation, disable SSH in
the Recalbox network/system settings. The tracker does not require SSH.

For a later update, temporarily enable SSH, deploy the update, verify it, and
disable SSH again. Do not leave a finished console listening with the default
root password.

## Updating this installation

Temporarily enable SSH in Recalbox. Pull the new repository version on the PC
and deploy it:

```sh
git pull --ff-only
./portable-core/deploy.sh "$PI"
ssh root@$PI "sync; reboot"
```

After validation, disable SSH again.

Do not replace the pinned randomizer source independently. The Stopwatch safety
patch verifies exact upstream source and ROM contracts and intentionally fails
closed if they change.

## Troubleshooting

| Symptom | Action |
|---|---|
| SSH host-key warning after formatting | Run `ssh-keygen -R "$PI"` once, then reconnect. |
| Health check says SHARE is not ext4 | Repeat step 3; do not continue on exFAT. |
| Base-ROM checksum fails | Verify the ROM is unheadered Japanese v1.0. No other revision is accepted. |
| Engine provenance check fails | Remove only `/recalbox/share/alttpr/ALttPDoorRandomizer-OverworldShuffle`, then repeat steps 4 and 6. |
| ALTTPR system is absent | Run `./portable-core/deploy.sh "$PI"`, reboot, then rerun the health check. |
| Tracker ports fail | Reboot once; inspect `/recalbox/share/system/logs/alttpr-custom.log`. |
| Seed generation reports a reservation error | Do not bypass it. The pinned engine or ROM layout changed and requires code review. |

## Recovery

Once installation and gameplay are confirmed, shut down Recalbox and image the
entire microSD card. A full-card image is the fastest recovery path; this guide
remains the source-controlled clean-build path.
