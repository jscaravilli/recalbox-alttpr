#!/bin/bash
# Install optional ALTTPR content after install-deps.sh and deploy.sh.
# Usage: install-content.sh [all|sprites|msu] [exact MSU pack name]
# Idempotent: existing sprites/previews/MSU packs are retained and skipped.
set -euo pipefail

ENGINE=/recalbox/share/alttpr
BIN="$ENGINE/bin"
MODE="${1:-all}"

if [ "$MODE" = "all" ] || [ "$MODE" = "sprites" ]; then
  echo "== official sprite library =="
  python3 "$BIN/alttpr-sprites.py"
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
  all|sprites|msu) ;;
  *) echo "usage: $0 [all|sprites|msu] [exact MSU pack name]" >&2; exit 2 ;;
esac
