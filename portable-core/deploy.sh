#!/usr/bin/env bash
# Deploy the ALTTPR integration from this repo onto a running Recalbox 10 Pi.
# Usage:  ./deploy.sh <pi-ip> [ssh-pass]
# Requires: ssh/scp (or run the scp/ssh lines by hand). Assumes steps 1-3 of
# docs/REPRODUCE.md are done (ext4 share + engine + base ROM already in place).
set -euo pipefail
PI="${1:?usage: deploy.sh <pi-ip> [pass]}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH="ssh root@${PI}"
SCP="scp"

echo "== creating target dirs =="
$SSH "mkdir -p /recalbox/share/alttpr/bin/words /recalbox/share/alttpr/es/gamelist-art \
      /recalbox/share/roms/alttpr/SEEDS /recalbox/share/userscripts"

echo "== copying engine bin =="
$SCP -r "$REPO"/portable-core/bin/* "root@${PI}:/recalbox/share/alttpr/bin/"

echo "== copying es integration =="
$SCP "$REPO"/adapters/recalbox/alttprGenerator.py "root@${PI}:/recalbox/share/alttpr/es/"
$SCP "$REPO"/adapters/recalbox/alttpr-install.sh  "root@${PI}:/recalbox/share/alttpr/es/"
$SCP "$REPO"/adapters/recalbox/assets/gamelist/box.png \
     "$REPO"/adapters/recalbox/assets/gamelist/seed.png \
     "root@${PI}:/recalbox/share/alttpr/es/gamelist-art/"

echo "== copying boot hook + endgame userscript =="
$SCP "$REPO"/adapters/recalbox/custom.sh "root@${PI}:/recalbox/share/system/custom.sh"
$SCP "$REPO"/adapters/recalbox/userscripts/alttpr-refresh.sh "root@${PI}:/recalbox/share/userscripts/"

echo "== normalize line endings + perms, then install =="
$SSH "cd /recalbox/share/alttpr; \
      find bin es -type f \( -name '*.sh' -o -name '*.py' \) -exec sed -i 's/\r\$//' {} +; \
      sed -i 's/\r\$//' /recalbox/share/system/custom.sh /recalbox/share/userscripts/alttpr-refresh.sh; \
      chmod +x bin/*.sh bin/*.py es/*.sh es/*.py /recalbox/share/system/custom.sh /recalbox/share/userscripts/alttpr-refresh.sh; \
      bash /recalbox/share/alttpr/es/alttpr-install.sh"

echo "== done. Restart EmulationStation on the Pi to see the ALTTPR system. =="
