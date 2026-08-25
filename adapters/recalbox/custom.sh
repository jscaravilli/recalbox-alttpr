#!/bin/bash
# Recalbox 10 user boot hook (run by /etc/init.d/S99custom as: custom.sh start|stop).
#   start: self-heal the ALTTPR EmulationStation integration into the rootfs, and
#          start the phone autotracker services.
#   stop:  flush to disk.
#
# The engine + all scripts live on the persistent ext4 share; the rootfs configgen
# hook is reapplied every boot (rootfs is an overlay whose changes may not survive
# an unclean shutdown), so nothing depends on rootfs persistence.
LOG=/recalbox/share/system/logs/alttpr-custom.log
ENGINE=/recalbox/share/alttpr

start() {
  # self-heal the ES integration each boot
  [ -x "$ENGINE/es/alttpr-install.sh" ] && bash "$ENGINE/es/alttpr-install.sh" >>"$LOG" 2>&1

  # start the phone autotracker services (idempotent). Added in the tracker phase.
  [ -x "$ENGINE/bin/alttpr-tracker.sh" ] && sh "$ENGINE/bin/alttpr-tracker.sh" start >>"$LOG" 2>&1
}

stop() {
  [ -x "$ENGINE/bin/alttpr-tracker.sh" ] && sh "$ENGINE/bin/alttpr-tracker.sh" stop >>"$LOG" 2>&1
  sync
}

case "$1" in
  start) start ;;
  stop)  stop ;;
  *)     start ;;
esac
