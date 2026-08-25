#!/bin/bash
# EmulationStation endgame event hook (Recalbox userscripts).
#
# Recalbox invokes userscripts as:
#   sh <script> -action <event> -systemName <sys> -gamePath <path> ...
#
# Jobs on 'endgame' (fired right after a game/tile is exited):
#   1. Flush saves/metadata to disk — but DETACHED and TIME-BOUNDED so a downed
#      storage device can never freeze the frontend (see NOTE below).
#   2. If the generator dropped /tmp/alttpr_refresh (a NEW seed was generated this
#      launch), launch the detached refresh worker to re-merge the seed's gamelist
#      entry and restart ES so the seed shows with its nickname/art.
FLAG=/tmp/alttpr_refresh
WORKER=/recalbox/share/alttpr/bin/alttpr-refresh-worker.sh
LOG=/recalbox/share/system/logs/alttpr-refresh.log

action=""
while [ $# -gt 0 ]; do
  case "$1" in
    -action) action="$2"; shift 2 ;;
    *) shift ;;
  esac
done

[ "$action" = "endgame" ] || exit 0

# 1. flush saves/metadata to disk after every game.
# NOTE: run the flush DETACHED and TIME-BOUNDED. A bare, blocking `sync` flushes
# every filesystem system-wide. If a storage device has dropped off the bus
# (the original WD SN850X NVMe did this on the Pi 5), a blocking sync hangs in
# uninterruptible I/O through the ~30s controller reset and freezes ES at the
# moment you quit a game. setsid+timeout guarantees the hook returns immediately.
setsid sh -c 'timeout 15 sync' </dev/null >/dev/null 2>&1 &

# 2. refresh gamelists only when a new seed was generated this launch
[ -f "$FLAG" ] || exit 0
rm -f "$FLAG" 2>/dev/null

echo "$(date '+%F %T') new seed -> launching refresh worker" >> "$LOG" 2>/dev/null

if [ -x "$WORKER" ]; then
  setsid sh "$WORKER" </dev/null >/dev/null 2>&1 &
else
  setsid sh -c 'sleep 1; /etc/init.d/S31emulationstation restart >/dev/null 2>&1' </dev/null >/dev/null 2>&1 &
fi

exit 0
