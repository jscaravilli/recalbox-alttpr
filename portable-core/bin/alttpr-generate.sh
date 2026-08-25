#!/bin/bash
# ALTTPR seed generator for Recalbox 10, powered by the Python Door Randomizer
# (codemann8/ALttPDoorRandomizer). Replaces the old static-PHP + box64 chain.
#   usage: alttpr-generate.sh <mode>
# Prints "SEED:<abs path to .sfc>" on the last line for the configgen generator.
#
# Modes map to DR CLI flags. "custom" reads /tmp/alttpr_choices.env written by the
# interactive menu; named presets are self-contained.
set -uo pipefail

ENGINE=/recalbox/share/alttpr
DR="$ENGINE/ALttPDoorRandomizer-OverworldShuffle"
DEPS="$ENGINE/pydeps/site"
BASE=/recalbox/share/system/.alttpr-private/base/alttp-jp10.sfc
BIN="$ENGINE/bin"

ROOT=/recalbox/share/roms/alttpr
DEST="$ROOT/SEEDS"
mkdir -p "$DEST"

export PYTHONPATH="$DEPS"

MODE="${1:-open}"

# --- preset -> DR flags -------------------------------------------------------
# Every flag here is a real DR CLI option (see docs/DR-cli-help.txt).
EXTRA="--create_rom --spoiler full --quickswap"
case "$MODE" in
  open)          FLAGS="--mode open --goal ganon --swords random --difficulty normal --logic noglitches --accessibility items" ;;
  standard)      FLAGS="--mode standard --goal ganon --swords random --difficulty normal --logic noglitches --accessibility items" ;;
  fast_ganon)    FLAGS="--mode open --goal crystals --crystals_ganon 7 --crystals_gt 7 --swords random --difficulty normal --logic noglitches" ;;
  keysanity)     FLAGS="--mode open --goal ganon --swords random --difficulty normal --logic noglitches --keyshuffle wild --bigkeyshuffle wild --mapshuffle wild --compassshuffle wild" ;;
  pedestal)      FLAGS="--mode open --goal pedestal --swords random --difficulty normal --logic noglitches --accessibility locations" ;;
  triforce_hunt) FLAGS="--mode open --goal triforcehunt --swords random --difficulty normal --logic noglitches" ;;
  inverted)      FLAGS="--mode inverted --goal ganon --swords random --difficulty normal --logic noglitches" ;;
  hard)          FLAGS="--mode open --goal ganon --swords random --difficulty hard --item_functionality hard --logic noglitches" ;;
  custom)
    CHOICES=/tmp/alttpr_choices.env
    # defaults (align with DR valid values)
    MODE_V=open GOAL=ganon SWORDS=random DIFFICULTY=normal ITEM_FUNCTIONALITY=normal
    LOGIC=noglitches ACCESSIBILITY=items PROGRESSIVE=on ALGORITHM=balanced
    SHUFFLEBOSSES=none SHUFFLEENEMIES=none ENEMY_HEALTH=default ENEMY_DAMAGE=default
    KEYSHUFFLE=none BIGKEYSHUFFLE=none MAPSHUFFLE=none COMPASSSHUFFLE=none
    CRYSTALS_GANON=7 CRYSTALS_GT=7 SPRITE="(default)" HEARTCOLOR=red
    OW_SHUFFLE=vanilla OW_LAYOUT=vanilla OW_FLUTESHUFFLE=vanilla DOOR_SHUFFLE=vanilla
    SHUFFLE=vanilla NICKNAME="" TIMER=stopwatch POTTERY=none
    HINTS=on QUICKSWAP=true SPOILER=on MSU=Default
    # shellcheck disable=SC1090
    [ -f "$CHOICES" ] && . "$CHOICES"
    FLAGS="--mode $MODE_V --goal $GOAL --swords $SWORDS --difficulty $DIFFICULTY \
--item_functionality $ITEM_FUNCTIONALITY --logic $LOGIC --accessibility $ACCESSIBILITY \
--progressive $PROGRESSIVE --algorithm $ALGORITHM \
--shufflebosses $SHUFFLEBOSSES --shuffleenemies $SHUFFLEENEMIES \
--enemy_health $ENEMY_HEALTH --enemy_damage $ENEMY_DAMAGE \
--keyshuffle $KEYSHUFFLE --bigkeyshuffle $BIGKEYSHUFFLE \
--mapshuffle $MAPSHUFFLE --compassshuffle $COMPASSSHUFFLE \
--crystals_ganon $CRYSTALS_GANON --crystals_gt $CRYSTALS_GT \
--ow_shuffle $OW_SHUFFLE --ow_layout $OW_LAYOUT --ow_fluteshuffle $OW_FLUTESHUFFLE \
--door_shuffle $DOOR_SHUFFLE --shuffle $SHUFFLE --pottery $POTTERY"
    EXTRA="--create_rom"
    [ "$HINTS" = "on" ] && FLAGS="$FLAGS --hints"
    [ "$QUICKSWAP" = "true" ] && EXTRA="$EXTRA --quickswap"
    if [ "$SPOILER" = "on" ]; then
      EXTRA="$EXTRA --spoiler full"
    else
      EXTRA="$EXTRA --spoiler none"
    fi
    [ "$TIMER" = "stopwatch" ] && EXTRA="$EXTRA --timer display"
    [ -n "$HEARTCOLOR" ] && [ "$HEARTCOLOR" != "red" ] && EXTRA="$EXTRA --heartcolor $HEARTCOLOR"
    if [ -n "$SPRITE" ] && [ "$SPRITE" != "(default)" ]; then
      SPR="$ENGINE/sprites/$SPRITE.zspr"
      [ -f "$SPR" ] && EXTRA="$EXTRA --sprite $SPR"
    fi
    ;;
  *) MODE=open; FLAGS="--mode open --goal ganon --swords random --difficulty normal --logic noglitches --accessibility items" ;;
esac

# Ensure seeds play on snes9x (HD off) so the phone autotracker can read memory.
SEEDSCONF="$DEST/.recalbox.conf"
grep -q '^snes.hdmode=0' "$SEEDSCONF" 2>/dev/null || \
  printf 'snes.hdmode=0\nsnes.widescreenmode=0\n' > "$SEEDSCONF" 2>/dev/null || true

STAMP="$(date +%m%d%Y)"
RELEASEDATE="$(date +%Y%m%dT%H%M%S)"
STAGE="$(mktemp -d)"
TOKEN="gen$$"

cd "$DR" || { echo "SEED:"; exit 1; }
# shellcheck disable=SC2086
timeout 300 python3 DungeonRandomizer.py --rom "$BASE" $FLAGS $EXTRA \
  --outputpath "$STAGE" --outputname "$TOKEN" >/dev/null 2>&1

NEW="$(ls -1t "$STAGE"/*.sfc 2>/dev/null | head -1)"
if [ -z "$NEW" ]; then rm -rf "$STAGE"; echo "SEED:"; exit 1; fi

# --- friendly nickname in the filename ---------------------------------------
NICK_SPACED="${NICKNAME:-}"
[ -z "$NICK_SPACED" ] && NICK_SPACED="$(python3 "$BIN/alttpr-name.py" 2>/dev/null)"
[ -z "$NICK_SPACED" ] && NICK_SPACED="Mystery Seed"
NICK="$(printf '%s' "$NICK_SPACED" | tr -cd 'A-Za-z0-9')"
[ -z "$NICK" ] && NICK="Seed"
NEWBASE="alttpr_${MODE}_${NICK}"
FINAL="$DEST/${NEWBASE}_${STAMP}.sfc"
n=2
while [ -e "$FINAL" ]; do
  NEWBASE="alttpr_${MODE}_${NICK}${n}"
  FINAL="$DEST/${NEWBASE}_${STAMP}.sfc"
  n=$((n+1))
done
mv "$NEW" "$FINAL"
FINALBASE="$(basename "$FINAL" .sfc)"

# preserve the spoiler next to the seed, renamed to match
SPOILERSRC="$(ls -1 "$STAGE"/*_Spoiler.txt 2>/dev/null | head -1)"
[ -f "$SPOILERSRC" ] && mv "$SPOILERSRC" "$DEST/${FINALBASE}.spoiler.txt"
rm -rf "$STAGE"

# --- attach selected MSU-1 pack ----------------------------------------------
# Packs are normalized under msu/<slug>/ with a runtime manifest. Since the
# share is ext4, attach tracks as symlinks instead of copying ~1 GiB per seed.
MSU="${MSU:-Default}"
if [ -n "$MSU" ] && [ "$MSU" != "Default" ]; then
  MANIFEST="$ENGINE/msu/packs.json"
  if [ -f "$MANIFEST" ]; then
    PACKINFO="$(python3 - "$MANIFEST" "$MSU" <<'PY' 2>/dev/null
import json, sys
for p in json.load(open(sys.argv[1], encoding="utf-8")):
    if p.get("name") == sys.argv[2]:
        print(p.get("dir", ""))
        print(p.get("basename", ""))
        break
PY
)"
    PACKDIR="$(printf '%s\n' "$PACKINFO" | sed -n 1p)"
    PACKBASE="$(printf '%s\n' "$PACKINFO" | sed -n 2p)"
    if [ -d "$PACKDIR" ] && [ -n "$PACKBASE" ]; then
      for SRC in "$PACKDIR/$PACKBASE".msu "$PACKDIR/$PACKBASE"-*.pcm; do
        [ -e "$SRC" ] || continue
        SUFFIX="$(basename "$SRC")"
        SUFFIX="${SUFFIX#$PACKBASE}"
        ln -sf "$SRC" "$DEST/${FINALBASE}${SUFFIX}"
      done
    fi
  fi
fi

# --- register the seed for the ES gamelist (root gamelist + durable pending) --
GL="$ROOT/gamelist.xml"
PENDING=/tmp/alttpr_gamelist_pending
IMG="./.art/seed.png"
RELPATH="SEEDS/$(basename "$FINAL")"
NAME="ALTTPR ${MODE} - ${STAMP} (${NICK_SPACED})"
[ -f "$GL" ] || printf '<?xml version="1.0"?>\n<gameList>\n</gameList>\n' > "$GL"
python3 - "$GL" "$RELPATH" "$NAME" "$IMG" "$MODE" "$STAMP" "$RELEASEDATE" "$PENDING" <<'PY' 2>/dev/null || true
import sys, re
gl, path, name, img, mode, stamp, releasedate, pending = sys.argv[1:9]
entry = (f"  <game>\n    <path>{path}</path>\n    <name>{name}</name>\n"
         f"    <image>{img}</image>\n"
         f"    <releasedate>{releasedate}</releasedate>\n"
         f"    <desc>A Link to the Past Randomizer seed ({mode}). Generated {stamp}.</desc>\n  </game>\n")
data = open(gl, encoding="utf-8").read()
pat = r"\s*<game(?:\s[^>]*)?>(?:(?!</game>).)*?<path>" + re.escape(path) + r"</path>.*?</game>"
data = re.sub(pat, "", data, flags=re.S)
open(gl, "w", encoding="utf-8").write(data.replace("</gameList>", entry + "</gameList>"))
with open(pending, "a", encoding="utf-8") as f:
    f.write(entry)
PY

# --- signal the ES event hook to refresh gamelists after this game exits ------
touch /tmp/alttpr_refresh 2>/dev/null || true
sync 2>/dev/null || true

echo "generated: $FINAL"
echo "SEED:$FINAL"
