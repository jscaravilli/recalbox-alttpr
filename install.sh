#!/usr/bin/env bash
# Install ALTTPR onto a clean, first-booted Recalbox 10.0.8 Raspberry Pi 5.
# Safe by default: without --confirm-install this performs read-only validation.
set -euo pipefail

EXPECTED_RECALBOX=10.0.8
EXPECTED_ARCH=aarch64
EXPECTED_PYTHON="Python 3.11.8"
EXPECTED_ROM_MD5=03a63945398191337e896e5771f77173

PI=recalbox.local
ROM=
CONFIRM=false
SKIP_FORMAT=false
REPO="$(cd "$(dirname "$0")" && pwd)"
TMP=

usage() {
  cat <<'EOF'
Usage:
  ./install.sh --rom /path/to/alttp-jp10.sfc [--pi HOST]
  ./install.sh --confirm-install --rom /path/to/alttp-jp10.sfc [--pi HOST]
               [--skip-format]

Modes:
  default             Read-only dry run. Validates the PC, ROM, Recalbox
                      version, architecture, Python, and SHARE filesystem.
  --confirm-install   Perform the installation.
  --skip-format       Preserve SHARE and skip its ext4 conversion. Installation
                      proceeds only when SHARE is already ext4.

There is intentionally no --dry-run option: dry-run is the default.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --pi)
      [ "$#" -ge 2 ] || die "--pi requires a host or IP"
      PI="$2"
      shift 2
      ;;
    --rom)
      [ "$#" -ge 2 ] || die "--rom requires a file"
      ROM="$2"
      shift 2
      ;;
    --confirm-install)
      CONFIRM=true
      shift
      ;;
    --skip-format)
      SKIP_FORMAT=true
      shift
      ;;
    --dry-run)
      die "--dry-run was removed because dry-run is now the default"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[ -n "$ROM" ] || die "--rom is required"
[ -f "$ROM" ] || die "base ROM not found: $ROM"

for command in ssh scp; do
  command -v "$command" >/dev/null 2>&1 ||
    die "required command not found: $command"
done

if command -v md5sum >/dev/null 2>&1; then
  actual_md5="$(md5sum "$ROM" | awk '{print $1}')"
elif command -v md5 >/dev/null 2>&1; then
  actual_md5="$(md5 -q "$ROM")"
else
  die "required checksum command not found: md5sum or md5"
fi
[ "$actual_md5" = "$EXPECTED_ROM_MD5" ] ||
  die "base ROM MD5 is $actual_md5; expected $EXPECTED_ROM_MD5"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
KNOWN_HOSTS="$TMP/known_hosts"
SSH_CONFIG="$TMP/ssh_config"

write_ssh_config() {
  : > "$KNOWN_HOSTS"
  cat > "$SSH_CONFIG" <<EOF
Host alttpr-target
  HostName $PI
  User root
  UserKnownHostsFile $KNOWN_HOSTS
  StrictHostKeyChecking accept-new
  ConnectTimeout 10
  ServerAliveInterval 10
  ServerAliveCountMax 3
EOF
}

write_ssh_config
SSH=(ssh -F "$SSH_CONFIG" alttpr-target)
SCP=(scp -F "$SSH_CONFIG")

remote() {
  "${SSH[@]}" "$@"
}

read_facts() {
  remote '
    version="$(cat /recalbox/recalbox.version 2>/dev/null ||
      cat /etc/recalbox.version 2>/dev/null || true)"
    printf "version=%s\n" "$version"
    printf "arch=%s\n" "$(uname -m)"
    printf "python=%s\n" "$(python3 --version 2>&1)"
    printf "sharefs=%s\n" "$(awk '"'"'$2 == "/recalbox/share" { print $3; exit }'"'"' /proc/mounts)"
    printf "sharelabel=%s\n" "$(blkid /dev/mmcblk0p2 2>/dev/null |
      sed -n '"'"'s/.* LABEL="\([^"]*\)".*/\1/p'"'"')"
  '
}

wait_for_share_fs() {
  expected="$1"
  attempts=0
  while [ "$attempts" -lt 120 ]; do
    if remote "awk '\$2 == \"/recalbox/share\" && \$3 == \"$expected\" { found=1 } END { exit !found }' /proc/mounts" \
        >/dev/null 2>&1; then
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 5
  done
  die "timed out waiting for Recalbox to mount SHARE as $expected"
}

printf '== validating Recalbox target %s ==\n' "$PI"
facts="$(read_facts)" || die "cannot reach $PI over SSH"
printf '%s\n' "$facts"

fact() {
  printf '%s\n' "$facts" | sed -n "s/^$1=//p" | head -1
}

[ "$(fact version)" = "$EXPECTED_RECALBOX" ] ||
  die "Recalbox $(fact version) is unsupported; required $EXPECTED_RECALBOX"
[ "$(fact arch)" = "$EXPECTED_ARCH" ] ||
  die "target architecture $(fact arch) is unsupported; required $EXPECTED_ARCH"
[ "$(fact python)" = "$EXPECTED_PYTHON" ] ||
  die "target Python $(fact python) is unsupported; required $EXPECTED_PYTHON"
[ "$(fact sharelabel)" = "SHARE" ] ||
  die "/dev/mmcblk0p2 is not labeled SHARE; refusing to continue"

sharefs="$(fact sharefs)"
if $SKIP_FORMAT && [ "$sharefs" != "ext4" ]; then
  die "--skip-format requires SHARE to already be ext4 (found $sharefs)"
fi
if ! $SKIP_FORMAT && [ "$sharefs" = "ext4" ]; then
  die "SHARE is already ext4; use --skip-format to preserve it"
fi

if ! $CONFIRM; then
  cat <<EOF

DRY RUN PASSED
No files or target settings were changed.

Planned actions:
  SHARE: $([ "$SKIP_FORMAT" = true ] && printf 'preserve existing ext4 filesystem' ||
    printf 'erase and convert /dev/mmcblk0p2 to ext4')
  Engine: install pinned Python Door Randomizer and hashed dependencies
  ROM: validate and install privately
  Content: deploy ALTTPR integration and official sprite library
  Validation: run the ALTTPR health check

Run the same command with --confirm-install to perform these actions.
EOF
  exit 0
fi

if ! $SKIP_FORMAT; then
  echo "== switching Recalbox to a temporary RAM share =="
  remote '
    set -eu
    mount -o remount,rw /boot
    sed -i "s/^;*sharedevice=.*/sharedevice=RAM/" /boot/recalbox-boot.conf
    sync
  '
  remote 'reboot -f' || true

  echo "== waiting for RAM-share boot =="
  sleep 10
  write_ssh_config
  wait_for_share_fs tmpfs

  echo "== formatting only /dev/mmcblk0p2 as ext4 =="
  remote '
    set -eu
    PART=/dev/mmcblk0p2
    test -b "$PART"
    label="$(blkid "$PART" | sed -n '"'"'s/.* LABEL="\([^"]*\)".*/\1/p'"'"')"
    test "$label" = "SHARE"
    mountpoint="$(awk -v part="$PART" '"'"'$1 == part { print $2; exit }'"'"' /proc/mounts)"
    if [ -n "$mountpoint" ]; then
      umount "$mountpoint"
    fi
    if awk -v part="$PART" '"'"'$1 == part { found=1 } END { exit !found }'"'"' /proc/mounts; then
      echo "SHARE partition remains mounted; refusing to format." >&2
      exit 1
    fi
    mkfs.ext4 -F -L SHARE "$PART"
    uuid="$(blkid "$PART" | sed -n '"'"'s/.* UUID="\([^"]*\)".*/\1/p'"'"')"
    test -n "$uuid"
    mount -o remount,rw /boot
    sed -i "/^sharedevice=/d" /boot/recalbox-boot.conf
    printf "sharedevice=DEV %s\n" "$uuid" >> /boot/recalbox-boot.conf
    sync
  '
  remote 'reboot -f' || true

  echo "== waiting for ext4 SHARE boot =="
  sleep 10
  write_ssh_config
  wait_for_share_fs ext4
fi

echo "== installing pinned randomizer engine =="
"${SCP[@]}" "$REPO/portable-core/install-deps.sh" \
  "$REPO/portable-core/requirements-recalbox.txt" alttpr-target:/tmp/
remote '
  set -eu
  sed -i "s/\r$//" /tmp/install-deps.sh
  chmod +x /tmp/install-deps.sh
  /tmp/install-deps.sh
'

echo "== installing private base ROM =="
"${SCP[@]}" "$ROM" alttpr-target:/tmp/alttp-jp10.sfc
remote "
  set -eu
  expected='$EXPECTED_ROM_MD5'
  actual=\"\$(md5sum /tmp/alttp-jp10.sfc | awk '{print \$1}')\"
  [ \"\$actual\" = \"\$expected\" ]
  private=/recalbox/share/system/.alttpr-private
  dest=\$private/base/alttp-jp10.sfc
  mkdir -p \"\$private/base\"
  chmod 700 \"\$private\" \"\$private/base\"
  chattr -i \"\$dest\" 2>/dev/null || true
  install -o root -g root -m 0400 /tmp/alttp-jp10.sfc \"\$dest\"
  rm -f /tmp/alttp-jp10.sfc
  chattr +i \"\$dest\"
"

echo "== deploying ALTTPR integration =="
ALTTPR_SSH_CONFIG="$SSH_CONFIG" "$REPO/portable-core/deploy.sh" alttpr-target

echo "== installing official sprite library =="
remote '/recalbox/share/alttpr/install-content.sh sprites'

echo "== validating installation =="
remote '/recalbox/share/alttpr/bin/alttpr-healthcheck.sh'

echo "== installation complete; rebooting Recalbox =="
remote 'sync; reboot' || true
