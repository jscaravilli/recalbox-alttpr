# Install ALTTPR on a New Recalbox SD Card

This runbook installs ALTTPR on a clean Raspberry Pi 5 running Recalbox
10.0.8. The supported path uses `install.sh` from another computer. The script
validates the target before making changes, converts only the new card's SHARE
partition to ext4, installs the pinned randomizer, copies the private base ROM,
deploys the offline sprite bundle, runs the health check, and reboots.

Read the entire guide before starting. Do not add ROMs, BIOS files, saves, or
other content to the new card until installation is complete.

## Installation summary

| Phase | Where | Result |
|---|---|---|
| Flash | PC | Recalbox 10.0.8 is written to the new card |
| First boot | Raspberry Pi | Recalbox expands the card and joins the network |
| Dry run | PC | Hardware, software, ROM, and SHARE are validated read-only |
| Install | PC controlling Pi over SSH | SHARE is reformatted as ext4 and ALTTPR is installed |
| Validate | Pi, TV, and browser | Health check, seed generation, sprites, gameplay, and tracker pass |

The clean installation normally takes two commands after Recalbox has completed
its first boot:

```sh
./install.sh --confirm-format --pi "$PI" --rom "$ROM"
./install.sh --confirm-install --confirm-format --pi "$PI" --rom "$ROM"
```

The first command is a read-only preview. The second performs the installation.

## Requirements

### Hardware

- Raspberry Pi 5
- Raspberry Pi power supply suitable for the Pi 5
- A2/U3/V30 microSD card; 256 GB is recommended and tested
- Display, controller, and network connection
- Another computer on the same network

Use Ethernet for the first installation when possible. Wi-Fi works, but the Pi
reboots twice while SHARE is converted and must reconnect each time.

### Software and files

- Recalbox **10.0.8** for Raspberry Pi 5 (`rpi5_64`)
- Raspberry Pi Imager
- Git
- Git Bash on Windows, or a POSIX-compatible terminal on macOS/Linux
- `ssh`, `scp`, and an MD5 utility
- A legally obtained, unheadered Japanese v1.0 ALTTP ROM

Recalbox 10.0.8 is the only supported release. The installer requires:

| Component | Required value |
|---|---|
| Recalbox | `10.0.8` |
| Architecture | `aarch64` |
| Python | `Python 3.11.8` |
| SHARE partition | `/dev/mmcblk0p2`, label `SHARE` |
| Base-ROM MD5 | `03a63945398191337e896e5771f77173` |

The base ROM is not included, downloaded, or distributed by this project.

> [!CAUTION]
> A clean installation erases **only the SHARE partition on the target
> microSD card** and recreates it as ext4. Use a new or expendable card.
> Confirm the Pi is booting from that card and do not use clean-install mode on
> a Recalbox card containing data you need.

## 1. Prepare the PC

Install Raspberry Pi Imager, Git, and an SSH client.

### Windows

Install [Git for Windows](https://git-scm.com/download/win), which provides Git
Bash, `ssh`, `scp`, and `md5sum`. Run all shell commands in this guide from
**Git Bash**, not PowerShell or Command Prompt.

### macOS or Linux

Use the normal Terminal application. Ensure `git`, `ssh`, and `scp` are
available.

Clone the current repository:

```sh
git clone https://github.com/jscaravilli/recalbox-alttpr.git
cd recalbox-alttpr
git pull --ff-only
```

Confirm that the corrected offline sprite bundle is present:

```sh
git log -1 --oneline
find portable-core/content/sprites -maxdepth 1 -name '*.zspr' | wc -l
find portable-core/content/bin/sprite-previews -maxdepth 1 -name '*.png' | wc -l
```

Both file counts must be `513`. The repository revision should be
`040e29b` or newer.

## 2. Verify the base ROM

Place the legally obtained ROM somewhere accessible from the terminal. This
guide uses `alttp-jp10.sfc` as an example.

```sh
# Windows Git Bash or Linux
md5sum /path/to/alttp-jp10.sfc

# macOS
md5 /path/to/alttp-jp10.sfc
```

The result must be exactly:

```text
03a63945398191337e896e5771f77173
```

Do not continue with a headered ROM, another region, or another revision. The
installer independently verifies the checksum and refuses an incorrect file.

## 3. Flash Recalbox

1. Insert the new microSD card into the PC.
2. Open Raspberry Pi Imager.
3. Select Recalbox 10.0.8 for Raspberry Pi 5 (`rpi5_64`).
4. Select the new microSD card as the target.
5. Verify the target drive carefully.
6. Write the image and allow the imager to verify it.
7. Safely eject the card.

The validated Recalbox image filename is `recalbox-rpi5_64.img.xz`, with SHA-1:

```text
1eb7892530927cc868b08b07e68ca006f8c0e8b2
```

## 4. Complete Recalbox first boot

1. Insert the card into the Raspberry Pi 5.
2. Connect Ethernet if available.
3. Connect the display, controller, and power.
4. Wait for Recalbox to expand the card and complete any automatic reboot.
5. Finish the initial controller and network setup.
6. Enable SSH in the Recalbox network/system settings.
7. Note the Pi's IP address.

Do not start the ALTTPR installation while Recalbox is still expanding the card
or rebooting.

The default SSH credentials are:

```text
user: root
password: recalboxroot
```

## 5. Confirm connectivity

Return to the repository directory on the PC and define variables for the Pi
and ROM. Replace both example values:

```sh
PI=192.168.1.50
ROM=/path/to/alttp-jp10.sfc
```

An IP address is more reliable during installation than `recalbox.local`.

Test SSH:

```sh
ssh root@"$PI"
```

Accept the host key and enter `recalboxroot` when prompted. At the Pi prompt,
check the Recalbox version:

```sh
cat /recalbox/recalbox.version 2>/dev/null || cat /etc/recalbox.version
uname -m
python3 --version
```

Expected output:

```text
10.0.8
aarch64
Python 3.11.8
```

Exit back to the PC:

```sh
exit
```

## 6. Run the clean-install dry run

The installer is read-only unless `--confirm-install` is present. Preview the
clean installation:

```sh
./install.sh --confirm-format --pi "$PI" --rom "$ROM"
```

Enter the Recalbox root password if prompted. A successful dry run prints the
detected facts and ends with:

```text
DRY RUN PASSED
No files or target settings were changed.
```

Review the planned SHARE action. It must say:

```text
ERASE and convert /dev/mmcblk0p2 to ext4
```

The dry run must identify all of these correctly:

- Recalbox `10.0.8`
- Architecture `aarch64`
- Python `3.11.8`
- SHARE label `SHARE`
- The intended Pi address
- The correct base-ROM MD5

Stop if any value is unexpected. Do not bypass an installer check.

## 7. Perform the clean installation

Run the same command with the install confirmation:

```sh
./install.sh --confirm-install --confirm-format --pi "$PI" --rom "$ROM"
```

The command performs these stages:

1. Switches Recalbox temporarily to a RAM-backed SHARE and reboots.
2. Verifies `/dev/mmcblk0p2` is the partition labeled `SHARE`.
3. Unmounts and reformats only that partition as ext4.
4. Configures Recalbox to mount the new ext4 SHARE and reboots.
5. Installs the pinned Python Door/Overworld Randomizer and dependencies.
6. Revalidates and privately installs the base ROM.
7. Deploys the Recalbox menu, theme integration, tracker, and boot repair hook.
8. Validates and installs 513 bundled ZSPR files and 513 bundled previews.
9. Rebuilds the sprite menu manifest locally without downloading sprite art.
10. Runs `/recalbox/share/alttpr/bin/alttpr-healthcheck.sh`.
11. Reboots into the completed installation.

The two intermediate reboots are expected. The installer waits for the required
filesystem after each reboot. Do not power off the Pi or close the terminal.

The complete sprite bundle is about 15 MB, so the deployment may pause briefly
while many small files are copied.

The final successful output includes:

```text
ALTTPR health check passed.
== installation complete; rebooting Recalbox ==
```

## 8. Validate after the final reboot

Wait until the Recalbox interface is responsive, then run the health check again
from the PC:

```sh
ssh root@"$PI" /recalbox/share/alttpr/bin/alttpr-healthcheck.sh
```

Every required check must report `PASS`, ending with:

```text
ALTTPR health check passed.
```

Confirm the installed asset counts:

```sh
ssh root@"$PI" '
  printf "ZSPR files: "
  find /recalbox/share/alttpr/sprites -maxdepth 1 -type f -name "*.zspr" | wc -l
  printf "Preview files: "
  find /recalbox/share/alttpr/bin/sprite-previews \
    -maxdepth 1 -type f -name "*.png" | wc -l
'
```

Both counts must be `513`.

Confirm the deployed bundle checksums:

```sh
ssh root@"$PI" '
  cd /recalbox/share/alttpr
  sha256sum -c sprite-assets.sha256
'
```

All entries must report `OK`.

## 9. Run the functional acceptance test

### Recalbox menu

1. Confirm **ALTTPR - Link to the Past Randomizer** appears as a system.
2. Open it and select **Generate Custom Seed**.
3. Confirm the configuration menu opens and responds to the controller.

### Sprite previews

1. Open the sprite selection.
2. Scroll through several sprites and confirm each preview is transparent,
   centered, and recognizable.
3. Specifically inspect **Bavarian Link**; it must show Link wearing Bavarian
   clothing, not an unrelated purple character.
4. Inspect several other fallback previews, such as Agrias, Axolotl, Isabelle,
   Lugia, Stitch, and Tunic.
5. Select a non-default sprite for the gameplay test.

### Generate and play

1. Leave gameplay settings at their defaults.
2. Choose **Generate & Play**.
3. Wait for generation to complete.
4. Confirm the generated seed launches in Snes9x/RetroArch.
5. Confirm video, controller input, and sound work.
6. Confirm the selected sprite appears in game.
7. Save and exit normally to verify Recalbox returns to the ALTTPR system.

### Live tracker

From a phone, tablet, or computer on the same network, open:

```text
http://recalbox.local:8080/itemtracker.html
```

If mDNS is unavailable, use the Pi address:

```text
http://192.168.1.50:8080/itemtracker.html
```

Confirm the tracker loads and updates while the generated seed is running.

## 10. Capture diagnostics if a test fails

Do not rerun the destructive format for an application-level failure. Capture
the health check and logs first:

```sh
ssh root@"$PI" '
  /recalbox/share/alttpr/bin/alttpr-healthcheck.sh
  echo "===== custom.log ====="
  tail -n 200 /recalbox/share/system/logs/alttpr-custom.log 2>/dev/null || true
  echo "===== filesystem ====="
  awk '"'"'$2 == "/recalbox/share" { print }'"'"' /proc/mounts
  echo "===== disk space ====="
  df -h /recalbox/share
'
```

For a missing ALTTPR system, rerun only the deployment:

```sh
./portable-core/deploy.sh "$PI"
ssh root@"$PI" "sync; reboot"
```

For a sprite-menu issue, rebuild the manifest from the already deployed offline
assets:

```sh
ssh root@"$PI" "/recalbox/share/alttpr/install-content.sh sprites"
```

This command does not download sprite art.

## Installer modes

| Command | SHARE effect | Use |
|---|---|---|
| `./install.sh --rom "$ROM" --pi "$PI"` | None | Validate an existing ext4 installation |
| `./install.sh --confirm-format --rom "$ROM" --pi "$PI"` | None | Preview a clean install |
| `./install.sh --confirm-install --rom "$ROM" --pi "$PI"` | Preserve ext4 SHARE | Install or repair without formatting |
| `./install.sh --confirm-install --confirm-format --rom "$ROM" --pi "$PI"` | Erase and recreate SHARE | Install on a new Recalbox card |

`--confirm-install` alone never formats SHARE. A non-formatting installation
requires SHARE to already be ext4. Dry-run and preservation are defaults;
therefore, the old `--dry-run` and `--skip-format` flags are intentionally
rejected.

## Optional MSU music

MSU music is not required for the initial acceptance test. Test the original
SNES soundtrack first.

After the base installation is stable, install one curated pack:

```sh
ssh root@"$PI" \
  "/recalbox/share/alttpr/install-content.sh msu 'A Link to the Past Enhanced'"
```

Install every curated pack:

```sh
ssh root@"$PI" "/recalbox/share/alttpr/install-content.sh msu"
```

These optional downloads can be large. One unavailable third-party pack does
not affect the original soundtrack or packs already installed. Users can also
import legally obtained packs later; see [MSU-IMPORT.md](MSU-IMPORT.md).

## Secure and preserve the finished console

The default Recalbox SSH password is public knowledge. After validation:

1. Disable SSH in Recalbox settings.
2. Shut down Recalbox cleanly.
3. Remove the card and create a full-card image on the PC.
4. Label the image with the repository commit and test date.

The full-card image is the fastest recovery method. This repository and guide
remain the reproducible clean-build source.

## Updating or repairing later

Enable SSH temporarily, update the repository, run a dry run, then install
without `--confirm-format`:

```sh
git pull --ff-only
./install.sh --pi "$PI" --rom "$ROM"
./install.sh --confirm-install --pi "$PI" --rom "$ROM"
```

This preserves the ext4 SHARE, generated seeds, saves, imported MSU packs,
Recalbox settings, and other content.

Do not replace the pinned randomizer source independently. The safety patches
verify exact upstream source and ROM contracts and intentionally fail closed if
those inputs change.

## Troubleshooting

| Symptom | Action |
|---|---|
| `Permission denied` from SSH | Use user `root` and the current Recalbox root password. |
| `recalbox.local` does not resolve | Use the IP address displayed by Recalbox. |
| SSH host-key warning after a reinstall | Run `ssh-keygen -R "$PI"` on the PC, then reconnect. |
| Installer cannot reconnect after a reboot | Wait for the Recalbox UI and network, verify the IP, then rerun the dry run. |
| Recalbox version, architecture, or Python check fails | Stop; flash the supported Recalbox 10.0.8 Pi 5 image. |
| SHARE label check fails | Stop; confirm the Pi booted from the intended new microSD card. |
| SHARE is exFAT during a repair | Use clean-install mode only if erasing SHARE is acceptable. |
| Base-ROM checksum fails | Use the unheadered Japanese v1.0 ROM; no other revision is accepted. |
| Engine provenance check fails | Remove only `/recalbox/share/alttpr/ALttPDoorRandomizer-OverworldShuffle`, then rerun the non-formatting installer. |
| ALTTPR system is absent | Redeploy, reboot, and rerun the health check. |
| Sprite count or checksum fails | Rerun `portable-core/deploy.sh`; do not fetch replacement art manually. |
| Tracker ports fail | Reboot once, then inspect `/recalbox/share/system/logs/alttpr-custom.log`. |
| Seed generation reports a reservation error | Do not bypass it; the pinned engine or ROM layout requires review. |

After all checks pass, continue with the [user guide](USER-GUIDE.md).
