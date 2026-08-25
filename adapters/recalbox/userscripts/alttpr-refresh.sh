#!/bin/bash
# Recalbox EmulationStation event hook.
#
# Recalbox 10 watches ROM/gamelist changes and owns its own safe relaunch cycle.
# Do not stop/start ES from an endgame child: that races the native watcher and
# can create restart/reboot loops. The only endgame job needed is a detached,
# time-bounded durability flush.

action=""
while [ $# -gt 0 ]; do
  case "$1" in
    -action) action="$2"; shift 2 ;;
    *) shift ;;
  esac
done

[ "$action" = "endgame" ] || exit 0

# Never block the frontend on a global sync. This preserves the original freeze
# mitigation even if some future storage device stalls.
setsid sh -c 'timeout 15 sync' </dev/null >/dev/null 2>&1 &
exit 0
