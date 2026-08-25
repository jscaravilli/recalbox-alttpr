#!/bin/sh
# Start/stop the ALTTPR phone autotracker services on the Pi:
#   - HTTP server (port 8080) serving the browser tracker + /seedinfo
#   - usb2snes->RetroArch WebSocket bridge (port 23074)
# Both are dependency-free Python; safe to run always (bridge idles when no game).
# Called from custom.sh at boot and self-heals (idempotent: restarts cleanly).
BIN=/recalbox/share/alttpr/bin
TRACKER=/recalbox/share/alttpr/tracker
LOGDIR=/recalbox/share/system/logs
SERVE_LOG=$LOGDIR/alttpr-tracker-serve.log
BRIDGE_LOG=$LOGDIR/alttpr-tracker-bridge.log
mkdir -p "$LOGDIR"

kill_match() {
  for p in $(pgrep -f "$1"); do kill "$p" 2>/dev/null; done
}

start() {
  # bridge (WebSocket :23074 -> RetroArch UDP :55355)
  if ! pgrep -f "alttpr-tracker-bridge.py" >/dev/null 2>&1; then
    setsid python3 "$BIN/alttpr-tracker-bridge.py" >"$BRIDGE_LOG" 2>&1 < /dev/null &
  fi
  # web server (:8080, serves $TRACKER + /seedinfo)
  if ! pgrep -f "alttpr-tracker-serve.py" >/dev/null 2>&1; then
    setsid python3 "$BIN/alttpr-tracker-serve.py" --dir "$TRACKER" --port 8080 >"$SERVE_LOG" 2>&1 < /dev/null &
  fi
  sleep 1
  status
}

stop() {
  kill_match "alttpr-tracker-serve.py"
  kill_match "alttpr-tracker-bridge.py"
  echo "stopped tracker services"
}

status() {
  b=$(pgrep -f alttpr-tracker-bridge.py | head -1)
  s=$(pgrep -f alttpr-tracker-serve.py | head -1)
  echo "bridge: ${b:-DOWN}   server: ${s:-DOWN}"
}

case "$1" in
  start|"") start ;;
  stop)     stop ;;
  restart)  stop; sleep 1; start ;;
  status)   status ;;
  *) echo "usage: $0 {start|stop|restart|status}" ;;
esac
