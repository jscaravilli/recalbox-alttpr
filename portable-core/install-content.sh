#!/bin/bash
# Install optional ALTTPR content after install-deps.sh and deploy.sh.
# Usage: install-content.sh [all|sprites|refresh-sprites|msu] [exact MSU name]
# Normal sprite installation is offline from the bundled catalog and assets.
set -euo pipefail

ENGINE=/recalbox/share/alttpr
BIN="$ENGINE/bin"
MODE="${1:-all}"

if [ "$MODE" = "all" ] || [ "$MODE" = "sprites" ]; then
  echo "== bundled official sprite library =="
  python3 "$BIN/alttpr-sprites.py" --offline
fi

if [ "$MODE" = "refresh-sprites" ]; then
  echo "== refreshing official sprite library from alttpr.com =="
  python3 "$BIN/alttpr-sprites.py" --refresh-previews
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "msu" ]; then
  echo "== curated MSU library =="
  if [ -n "${2:-}" ]; then
    python3 "$BIN/alttpr-msu.py" --only "$2"
  else
    python3 "$BIN/alttpr-msu.py"
  fi

  echo "== installed content =="
  python3 "$BIN/alttpr-msu.py" --list
fi

case "$MODE" in
  all|sprites|refresh-sprites|msu) ;;
  *) echo "usage: $0 [all|sprites|refresh-sprites|msu] [exact MSU pack name]" >&2; exit 2 ;;
esac
