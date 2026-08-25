#!/bin/bash
# Delete ALTTPR seed ROMs older than N hours (default 48) across all mode folders
# and _Latest. Age is measured from the file's CREATION time (filesystem birth
# time via statx; see alttpr-btime.py), not mtime — so playing/saving a seed never
# resets its age. Also removes each seed's matching .spoiler.json and its gamelist
# entry. KEEPS game saves (.srm/.state) — progress is never auto-deleted — and
# always keeps the launcher tiles (*.alttpr).
#
#   usage: alttpr-cleanup.sh [days|all]        (real delete)
#          alttpr-cleanup.sh [days|all] --dry  (list only, no delete)
#
# "days" uses CALENDAR-day boundaries from local midnight: 1 = anything created
# before today (yesterday or earlier), 2 = before yesterday, 7 = 7+ days ago.
# A seed made "yesterday at noon" counts as 1 day old even though <24h elapsed.
#
# Prints "CANDIDATE:<path>" for each seed that qualifies, then "DELETED:<n>".
set -uo pipefail

ROOT=/recalbox/share/roms/alttpr
BTIME=/recalbox/share/alttpr/bin/alttpr-btime.py
DAYS="${1:-1}"
DRY=0
[ "${2:-}" = "--dry" ] && DRY=1
[ "${1:-}" = "--dry" ] && { DRY=1; DAYS=1; }

NOW=$(date +%s)
# local midnight = now minus seconds elapsed since 00:00 local time (portable;
# avoids relying on `date -d` string parsing under busybox). 10# forces base-10
# so a leading-zero hour/min/sec like 08 or 09 is not read as octal.
SPMID=$(( 10#$(date +%H)*3600 + 10#$(date +%M)*60 + 10#$(date +%S) ))
MIDNIGHT=$(( NOW - SPMID ))
# DAYS="all" (or 0) deletes every seed; otherwise use calendar-day boundaries.
case "$DAYS" in
  all|ALL|0) CUTOFF=$(( NOW + 1 )) ;;                  # everything is < now+1
  *)         CUTOFF=$(( MIDNIGHT - (DAYS-1)*86400 )) ;;
esac
count=0

# creation (birth) time of a file as epoch; falls back to mtime inside the helper
btime() { python3 "$BTIME" "$1" 2>/dev/null | cut -f1; }

process() {
  local f="$1"
  local m
  m=$(btime "$f")
  [ -n "$m" ] || return 0
  [ "$m" -lt "$CUTOFF" ] || return 0          # created on/after cutoff -> keep
  echo "CANDIDATE:$f"
  count=$((count+1))
  [ "$DRY" = "1" ] && return 0
  local base dir
  dir=$(dirname "$f")
  base=$(basename "$f" .sfc)
  rm -f "$f" 2>/dev/null
  rm -f "$dir/${base}.spoiler.json" 2>/dev/null
  # remove any attached MSU-1 symlinks for this seed (<base>.msu + <base>-N.pcm)
  rm -f "$dir/${base}.msu" 2>/dev/null
  for pcm in "$dir/${base}"-*.pcm; do
    [ -e "$pcm" ] || [ -L "$pcm" ] || continue
    rm -f "$pcm" 2>/dev/null
  done
  # remove the per-seed tracker QR overlay fragment (named <romfile>.sfc.cfg)
  rm -f "/recalbox/share/overlays/snes/${base}.sfc.cfg" 2>/dev/null
  # prune the gamelist entry for this rom (match by filename)
  local gl="$dir/gamelist.xml"
  if [ -f "$gl" ]; then
    python3 - "$gl" "$base" <<'PY' 2>/dev/null || true
import sys, re
gl, base = sys.argv[1], sys.argv[2]
d = open(gl, encoding="utf-8").read()
d = re.sub(r"\s*<game>(?:(?!</game>).)*?"+re.escape(base)+r".*?</game>", "", d, flags=re.S)
open(gl, "w", encoding="utf-8").write(d)
PY
  fi
}

# all seeds live in the single SEEDS/ folder
for f in "$ROOT"/SEEDS/*.sfc; do
  [ -e "$f" ] || continue
  process "$f"
done

# sweep orphaned tracker QR overlay fragments (seed deleted outside this tool)
OVDIR=/recalbox/share/overlays/snes
if [ -d "$OVDIR" ]; then
  for frag in "$OVDIR"/alttpr_*.sfc.cfg; do
    [ -e "$frag" ] || continue
    seedfile="$(basename "$frag" .cfg)"          # <base>.sfc
    [ -e "$ROOT/SEEDS/$seedfile" ] || rm -f "$frag" 2>/dev/null
  done
fi

[ "$DRY" = "0" ] && sync 2>/dev/null
echo "DELETED:$count"
