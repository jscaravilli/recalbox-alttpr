#!/usr/bin/env bash
# Deploy the ALTTPR integration from this repo onto a running Recalbox 10 Pi.
# Usage:  ./deploy.sh <pi-ip>
# Requires: ssh/scp (or run the scp/ssh lines by hand). Assumes steps 1-3 of
# docs/INSTALL.md are done (ext4 share + engine + base ROM already in place).
set -euo pipefail
PI="${1:?usage: deploy.sh <pi-ip-or-ssh-host>}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH=(ssh)
SCP=(scp)
if [ -n "${ALTTPR_SSH_CONFIG:-}" ]; then
  SSH+=(-F "$ALTTPR_SSH_CONFIG")
  SCP+=(-F "$ALTTPR_SSH_CONFIG")
fi
TARGET="root@${PI}"
[ -n "${ALTTPR_SSH_CONFIG:-}" ] && TARGET="$PI"

echo "== creating target dirs =="
"${SSH[@]}" "$TARGET" "mkdir -p /recalbox/share/alttpr/bin/words /recalbox/share/alttpr/es/gamelist-art \
      /recalbox/share/alttpr/tracker /recalbox/share/import/msu/processed \
      /recalbox/share/roms/alttpr/SEEDS /recalbox/share/userscripts"

echo "== copying engine bin =="
"${SCP[@]}" -r "$REPO"/portable-core/bin/* "$TARGET:/recalbox/share/alttpr/bin/"

echo "== copying phone autotracker web app =="
"${SCP[@]}" -r "$REPO"/portable-core/tracker/* "$TARGET:/recalbox/share/alttpr/tracker/"

echo "== copying es integration =="
"${SCP[@]}" "$REPO"/adapters/recalbox/alttprGenerator.py "$TARGET:/recalbox/share/alttpr/es/"
"${SCP[@]}" "$REPO"/adapters/recalbox/alttpr-install.sh  "$TARGET:/recalbox/share/alttpr/es/"
"${SCP[@]}" "$REPO"/adapters/recalbox/build_theme.sh \
     "$REPO"/adapters/recalbox/assets/alttpr-logo.png \
     "$REPO"/adapters/recalbox/assets/alttpr-logo-carousel.png \
     "$REPO"/adapters/recalbox/assets/alttpr-consolegame.png \
     "$REPO"/adapters/recalbox/assets/alttpr-info-en.txt \
     "$TARGET:/recalbox/share/alttpr/es/"
"${SCP[@]}" "$REPO"/adapters/recalbox/assets/gamelist/box.png \
     "$REPO"/adapters/recalbox/assets/gamelist/seed.png \
     "$TARGET:/recalbox/share/alttpr/es/gamelist-art/"

echo "== copying boot hook + endgame userscript =="
"${SCP[@]}" "$REPO"/adapters/recalbox/custom.sh "$TARGET:/recalbox/share/system/custom.sh"
"${SCP[@]}" "$REPO"/adapters/recalbox/userscripts/alttpr-refresh.sh "$TARGET:/recalbox/share/userscripts/"
"${SCP[@]}" "$REPO"/portable-core/install-content.sh "$TARGET:/recalbox/share/alttpr/install-content.sh"

echo "== normalize line endings + perms, then install =="
"${SSH[@]}" "$TARGET" "cd /recalbox/share/alttpr; \
      find bin es -type f \( -name '*.sh' -o -name '*.py' \) -exec sed -i 's/\r\$//' {} +; \
      sed -i 's/\r\$//' install-content.sh /recalbox/share/system/custom.sh /recalbox/share/userscripts/alttpr-refresh.sh; \
      chmod +x bin/*.sh bin/*.py es/*.sh es/*.py /recalbox/share/system/custom.sh /recalbox/share/userscripts/alttpr-refresh.sh; \
      chmod +x /recalbox/share/alttpr/install-content.sh; \
      bash /recalbox/share/alttpr/es/alttpr-install.sh"

echo "== done. Restart EmulationStation on the Pi to see the ALTTPR system. =="
