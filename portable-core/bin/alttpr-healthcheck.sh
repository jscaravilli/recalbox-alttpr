#!/bin/bash
# Read-only post-install checks, except for the idempotent engine reservation.
set -u

ENGINE=/recalbox/share/alttpr
DR="$ENGINE/ALttPDoorRandomizer-OverworldShuffle"
BASE=/recalbox/share/system/.alttpr-private/base/alttp-jp10.sfc
EXPECTED_ROM_MD5=03a63945398191337e896e5771f77173
failures=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

if [ "$(id -u)" -eq 0 ]; then pass "running as root"; else fail "run as root"; fi

fstype="$(awk '$2 == "/recalbox/share" { print $3; exit }' /proc/mounts)"
if [ "$fstype" = "ext4" ]; then
  pass "SHARE is ext4"
else
  fail "SHARE is ext4 (found ${fstype:-unknown})"
fi

if [ -f "$BASE" ] && \
   [ "$(md5sum "$BASE" | cut -d' ' -f1)" = "$EXPECTED_ROM_MD5" ]; then
  pass "private JP1.0 base ROM checksum"
else
  fail "private JP1.0 base ROM checksum"
fi

if [ -f "$DR/DungeonRandomizer.py" ]; then
  pass "Door Randomizer source installed"
else
  fail "Door Randomizer source installed"
fi

if python3 "$ENGINE/bin/alttpr-enginepatch.py" "$DR" >/dev/null 2>&1; then
  pass "pinned engine source and bank-\$37 reservation"
else
  fail "pinned engine source and bank-\$37 reservation"
fi

if PYTHONPATH="$ENGINE/pydeps/site" python3 -c \
  'import aenum, aioconsole, bps, colorama, fast_enum, pygame, websockets, yaml' \
  >/dev/null 2>&1; then
  pass "Python runtime dependencies"
else
  fail "Python runtime dependencies"
fi

for path in \
  "$ENGINE/bin/alttpr-menu.py" \
  "$ENGINE/bin/alttpr-generate.sh" \
  "$ENGINE/bin/alttpr-msu-import.py" \
  "$ENGINE/bin/alttpr-msu-manager.py" \
  "$ENGINE/bin/alttpr-timerpatch.py" \
  "$ENGINE/es/alttpr-install.sh" \
  /recalbox/share/system/custom.sh \
  /recalbox/share/userscripts/alttpr-refresh.sh; do
  if [ -x "$path" ]; then
    pass "executable ${path#/recalbox/share/}"
  else
    fail "executable ${path#/recalbox/share/}"
  fi
done

if grep -q '"HEARTBEEP", "Heart Speed"' "$ENGINE/bin/alttpr-menu.py" &&
   grep -q -- '--heartbeep \$HEARTBEEP' "$ENGINE/bin/alttpr-generate.sh"; then
  pass "Heart Speed menu and generator integration"
else
  fail "Heart Speed menu and generator integration"
fi

if [ -d /recalbox/share/import/msu ] &&
   [ -f /recalbox/share/import/msu/README.txt ]; then
  pass "user MSU network drop folder"
else
  fail "user MSU network drop folder"
fi

SYSTEMLIST=/recalbox/share/system/.emulationstation/systemlist.xml
if grep -q 'name="alttpr"' "$SYSTEMLIST" 2>/dev/null; then
  pass "ALTTPR EmulationStation system registration"
else
  fail "ALTTPR EmulationStation system registration"
fi

CG=/usr/lib/python3.11/site-packages/configgen
if grep -q 'configgen.generators.alttpr.alttprGenerator' \
     "$CG/emulatorlauncher.py" 2>/dev/null &&
   PYTHONPATH="$ENGINE/pydeps/site" python3 -c \
     "import sys; sys.path.insert(0, '$CG/..'); import configgen.recalboxFiles as r; from configgen.generators.alttpr.alttprGenerator import AlttprGenerator; assert 'alttpr' in r.recalboxBins" \
     >/dev/null 2>&1; then
  pass "configgen generator dispatch and registration"
else
  fail "configgen generator dispatch and registration"
fi

if [ -f "$ENGINE/tracker/itemtracker.html" ]; then
  pass "live-tracker web application"
else
  fail "live-tracker web application"
fi

wait_for_port() {
  port="$1"
  attempts=0
  while [ "$attempts" -lt 20 ]; do
    netstat -lnt 2>/dev/null | grep -q ":$port " && return 0
    attempts=$((attempts + 1))
    sleep 1
  done
  return 1
}

if wait_for_port 8080; then
  pass "tracker HTTP service on port 8080"
else
  fail "tracker HTTP service on port 8080"
fi

if wait_for_port 23074; then
  pass "tracker bridge on port 23074"
else
  fail "tracker bridge on port 23074"
fi

if wget -qO- http://127.0.0.1:8080/seedinfo 2>/dev/null |
   grep -q '"running"'; then
  pass "tracker seed-information endpoint"
else
  fail "tracker seed-information endpoint"
fi

theme_found=0
for theme in \
  /recalbox/share_init/system/.emulationstation/themes/recalbox-next-v9 \
  /recalbox/share/themes/recalbox-next-v9; do
  [ -f "$theme/alttpr/custom.xml" ] && theme_found=1
done
if [ "$theme_found" -eq 1 ]; then
  pass "recalbox-next-v9 ALTTPR theme"
else
  fail "recalbox-next-v9 ALTTPR theme"
fi

if [ "$failures" -ne 0 ]; then
  printf '\nALTTPR health check failed: %d problem(s).\n' "$failures"
  exit 1
fi

printf '\nALTTPR health check passed.\n'
