#!/bin/bash
# Install optional ALTTPR content after install-deps.sh and deploy.sh.
# Idempotent: existing sprites/previews/MSU packs are retained and skipped.
set -euo pipefail

ENGINE=/recalbox/share/alttpr
BIN="$ENGINE/bin"

echo "== official sprite library =="
python3 "$BIN/alttpr-sprites.py"

echo "== curated MSU library =="
python3 "$BIN/alttpr-msu.py"

echo "== installed content =="
python3 "$BIN/alttpr-msu.py" --list
