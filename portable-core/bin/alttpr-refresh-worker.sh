#!/bin/sh
# Detached worker that refreshes the ALTTPR gamelist after a new seed is played.
# Launched by the endgame userscript (alttpr-refresh.sh) via setsid so it survives
# ES tearing down the game-launch process group.
#
# Sequence: STOP ES (so it can't rewrite/clobber gamelist.xml from its stale
# in-memory model) -> MERGE the pending seed entries into gamelist.xml -> START ES,
# which now boots with the seed(s) already present (nickname + art intact).
PENDING=/tmp/alttpr_gamelist_pending
GL=/recalbox/share/roms/alttpr/gamelist.xml
MERGE=/recalbox/share/alttpr/bin/alttpr-gamelist-merge.py
INIT=/etc/init.d/S31emulationstation
LOG=/recalbox/share/system/logs/alttpr-refresh.log

log() { echo "$(date '+%F %T') worker: $*" >> "$LOG" 2>/dev/null; }

# stop ES and wait for it to actually exit
"$INIT" stop >/dev/null 2>&1
i=0
while "$INIT" status >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -ge 50 ] && break
  sleep 0.1
done
log "ES stopped (waited ${i}x100ms)"

# merge pending seed entries into the now-quiescent gamelist
if [ -f "$PENDING" ]; then
  python3 "$MERGE" "$GL" "$PENDING" >> "$LOG" 2>&1
  rm -f "$PENDING" 2>/dev/null
fi
sync

# bring ES back — it loads gamelist.xml with the seed(s) present
"$INIT" start >/dev/null 2>&1
log "ES restarted"
