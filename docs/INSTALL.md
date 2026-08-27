# Install on a fresh Raspberry Pi 5

This procedure starts with a blank microSD card and does not require access to
the original console. Read the whole guide before formatting the card.

> **Destructive step:** converting SHARE to ext4 erases everything Recalbox
> created on that partition. Do it only on the new card, immediately after its
> first boot.

## 1. Prepare the PC

Install:

- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- Git
- An SSH client (`ssh` and `scp`)

Windows users can run the repository shell scripts from **Git Bash**. macOS and
Linux already provide a compatible shell and SSH client.

Clone this repository:

```sh
git clone https://github.com/jscaravilli/recalbox-alttpr-portable.git
cd recalbox-alttpr-portable
```

If the repository is private, the owner must first grant your GitHub account
access or provide a source archive. The installation contains no credentials or
private ROM data.

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
test "$(blkid -s LABEL -o value "$PART")" = "SHARE"
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
U=$(blkid -s UUID -o value "$PART")
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
