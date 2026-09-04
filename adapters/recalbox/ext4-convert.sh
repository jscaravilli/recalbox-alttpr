#!/bin/bash
# Convert the Recalbox SHARE partition (mmcblk0p2) from exFAT to ext4 and switch
# sharedevice to DEV <uuid> so S11share auto-detects the ext4 filesystem.
set -uo pipefail
LOG=/tmp/ext4-convert.log
exec > >(tee "$LOG") 2>&1
echo "=== ext4 share conversion $(date) ==="

SHARE_PART=/dev/mmcblk0p2
BOOTCONF=/boot/recalbox-boot.conf

echo "--- before ---"
blkid "$SHARE_PART"
mount | grep -E "recalbox/share|mmcblk0p2" || true

# 1. stop everything using the share
echo "--- stopping services ---"
/etc/init.d/S31emulationstation stop >/dev/null 2>&1 || true
for s in S91smb S92recalboxapiserver S31emulationstation; do
  [ -x "/etc/init.d/$s" ] && "/etc/init.d/$s" stop >/dev/null 2>&1 || true
done
sleep 2

# 2. free and unmount the share (kill stragglers holding it)
echo "--- unmounting share ---"
fuser -km /recalbox/share 2>/dev/null || true
sleep 1
# handle both direct mount and /var/recalboxfs indirection
umount -l /recalbox/share 2>/dev/null || true
umount -l /var/recalboxfs 2>/dev/null || true
sleep 1
if mount | grep -q "$SHARE_PART"; then
  echo "STILL MOUNTED — aborting to be safe:"; mount | grep "$SHARE_PART"
  exit 1
fi
echo "share unmounted OK"

# 3. reformat as ext4 (label SHARE preserved)
echo "--- mkfs.ext4 ---"
mkfs.ext4 -F -L SHARE "$SHARE_PART" || { echo "mkfs FAILED"; exit 1; }
NEWUUID=$(blkid "$SHARE_PART" | sed -n 's/.* UUID="\([^"]*\)".*/\1/p')
echo "new ext4 UUID=$NEWUUID"
blkid "$SHARE_PART"

# 4. point sharedevice at the ext4 partition by UUID (DEV mode auto-detects fstype)
echo "--- updating $BOOTCONF ---"
mount -o remount,rw /boot
cp -a "$BOOTCONF" "${BOOTCONF}.bak-$(date +%Y%m%d-%H%M%S)"
if grep -qE '^sharedevice=' "$BOOTCONF"; then
  sed -i "s|^sharedevice=.*|sharedevice=DEV ${NEWUUID}|" "$BOOTCONF"
else
  echo "sharedevice=DEV ${NEWUUID}" >> "$BOOTCONF"
fi
grep '^sharedevice=' "$BOOTCONF"
sync
mount -o remount,ro /boot 2>/dev/null || true

echo "=== DONE. sharedevice set to DEV ${NEWUUID}. Rebooting to mount ext4 share. ==="
sync
sleep 2
reboot
