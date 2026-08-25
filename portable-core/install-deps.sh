#!/bin/bash
# Install the Python Door Randomizer (codemann8/ALttPDoorRandomizer) and its
# Python dependencies onto a Recalbox 10 (Pi 5) system, entirely on the ext4
# share so nothing touches the read-only rootfs.
#
# VALIDATED on Recalbox 10.0.8 / Python 3.11.8: DR generates a real playable
# seed in ~12s. All engine work (item/dungeon/boss/enemy/overworld shuffle) is
# native Python — no PHP, no box64, no EnemizerCLI.
set -euo pipefail

ENGINE=/recalbox/share/alttpr
DEPS="$ENGINE/pydeps/site"
DR_ZIP_URL="https://github.com/codemann8/ALttPDoorRandomizer/archive/refs/heads/OverworldShuffle.zip"

mkdir -p "$ENGINE" "$DEPS"

# 1. Door Randomizer source
python3 -c "import urllib.request; urllib.request.urlretrieve('$DR_ZIP_URL','/tmp/dr.zip')"
python3 -c "import zipfile; zipfile.ZipFile('/tmp/dr.zip').extractall('$ENGINE')"

# 2. pip (Recalbox ships none) — bootstrap to the user base on the share
export PYTHONUSERBASE="$ENGINE/pydeps"
python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py','/tmp/get-pip.py')"
python3 /tmp/get-pip.py --user

# 3. DR runtime deps -> installed into a target dir on the ext4 share
python3 -m pip install --target="$DEPS" \
  aenum fast-enum python-bps-continued colorama aioconsole websockets pyyaml

echo "Done. Run DR with:"
echo "  PYTHONPATH=$DEPS python3 $ENGINE/ALttPDoorRandomizer-OverworldShuffle/DungeonRandomizer.py --help"
