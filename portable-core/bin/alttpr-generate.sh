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
    MODE_V=open GOAL=ganon SWORDS=random FLUTE_MODE=normal BOW_MODE=progressive
    DIFFICULTY=normal ITEM_FUNCTIONALITY=normal
    LOGIC=noglitches ACCESSIBILITY=items PROGRESSIVE=on ALGORITHM=balanced
    SHUFFLEBOSSES=none SHUFFLEENEMIES=none ENEMY_HEALTH=default ENEMY_DAMAGE=default
    SHUFFLE_FOLLOWERS=off SHOPSANITY=off KEYDROPSHUFFLE=off DROPSHUFFLE=none
    MIXED_TRAVEL=prevent
    KEYSHUFFLE=none BIGKEYSHUFFLE=none MAPSHUFFLE=none COMPASSSHUFFLE=none
    PRIZESHUFFLE=none DUNGEON_COUNTERS=default RESTRICT_BOSS_ITEMS=none
    CRYSTALS_GANON=7 CRYSTALS_GT=7 SPRITE="(default)" HEARTCOLOR=red
    OW_SHUFFLE=vanilla OW_LAYOUT=vanilla OW_CROSSED=none
    OW_FLUTESHUFFLE=vanilla OW_UNPARALLEL=off OW_TERRAIN=off
    OW_KEEPSIMILAR=off OW_MIXED=off OW_WHIRLPOOL=off
    DOOR_SHUFFLE=vanilla INTENSITY=1 DOOR_TYPE_MODE=original
    TRAP_DOOR_MODE=vanilla KEY_LOGIC_ALGORITHM=strict
    DECOUPLEDOORS=off DOOR_SELF_LOOPS=off
    ENTRANCE_SHUFFLE=vanilla NICKNAME="" TIMER=stopwatch POTTERY=none
    ANY_ENEMY_LOGIC=none SKULLWOODS=original LINKED_DROPS=unset
    OVERWORLD_MAP=default SHUFFLELINKS=off SHUFFLETAVERN=off
    PSEUDOBOOTS=off MIRRORSCROLL=off BOMBBAG=off TAKE_ANY=none
    REDUCE_FLASHING=off SHUFFLE_SFX=off
    HINTS=on QUICKSWAP=true SPOILER=on MSU=Default
    # shellcheck disable=SC1090
    [ -f "$CHOICES" ] && . "$CHOICES"
    if [ "$ENTRANCE_SHUFFLE" != "vanilla" ] && \
       [ "$OW_SHUFFLE" != "vanilla" ]; then
      echo "ERROR: Entrance Shuffle and Overworld Shuffle cannot be combined in this DR build."
      echo "SEED:"
      exit 2
    fi
    FLAGS="--mode $MODE_V --goal $GOAL --swords $SWORDS \
--flute_mode $FLUTE_MODE --bow_mode $BOW_MODE --difficulty $DIFFICULTY \
--item_functionality $ITEM_FUNCTIONALITY --logic $LOGIC --accessibility $ACCESSIBILITY \
--progressive $PROGRESSIVE --algorithm $ALGORITHM \
--dropshuffle $DROPSHUFFLE --mixed_travel $MIXED_TRAVEL \
--shufflebosses $SHUFFLEBOSSES --shuffleenemies $SHUFFLEENEMIES \
--enemy_health $ENEMY_HEALTH --enemy_damage $ENEMY_DAMAGE \
--any_enemy_logic $ANY_ENEMY_LOGIC \
--keyshuffle $KEYSHUFFLE --bigkeyshuffle $BIGKEYSHUFFLE \
--mapshuffle $MAPSHUFFLE --compassshuffle $COMPASSSHUFFLE \
--prizeshuffle $PRIZESHUFFLE --dungeon_counters $DUNGEON_COUNTERS \
--restrict_boss_items $RESTRICT_BOSS_ITEMS \
--crystals_ganon $CRYSTALS_GANON --crystals_gt $CRYSTALS_GT \
--ow_shuffle $OW_SHUFFLE --ow_layout $OW_LAYOUT --ow_crossed $OW_CROSSED \
--ow_fluteshuffle $OW_FLUTESHUFFLE \
--door_shuffle $DOOR_SHUFFLE --shuffle $ENTRANCE_SHUFFLE \
--intensity $INTENSITY --door_type_mode $DOOR_TYPE_MODE \
--trap_door_mode $TRAP_DOOR_MODE --key_logic_algorithm $KEY_LOGIC_ALGORITHM \
--pottery $POTTERY --skullwoods $SKULLWOODS \
--linked_drops $LINKED_DROPS --overworld_map $OVERWORLD_MAP \
--take_any $TAKE_ANY"
    EXTRA="--create_rom"
    [ "$HINTS" = "on" ] && FLAGS="$FLAGS --hints"
    [ "$QUICKSWAP" = "true" ] && EXTRA="$EXTRA --quickswap"
    [ "$SHUFFLE_FOLLOWERS" = "on" ] && EXTRA="$EXTRA --shuffle_followers"
    [ "$SHOPSANITY" = "on" ] && EXTRA="$EXTRA --shopsanity"
    [ "$KEYDROPSHUFFLE" = "on" ] && EXTRA="$EXTRA --keydropshuffle"
    [ "$DECOUPLEDOORS" = "on" ] && EXTRA="$EXTRA --decoupledoors"
    [ "$DOOR_SELF_LOOPS" = "on" ] && EXTRA="$EXTRA --door_self_loops"
    [ "$OW_UNPARALLEL" = "on" ] && EXTRA="$EXTRA --ow_unparallel"
    [ "$OW_TERRAIN" = "on" ] && EXTRA="$EXTRA --ow_terrain"
    [ "$OW_KEEPSIMILAR" = "on" ] && EXTRA="$EXTRA --ow_keepsimilar"
    [ "$OW_MIXED" = "on" ] && EXTRA="$EXTRA --ow_mixed"
    [ "$OW_WHIRLPOOL" = "on" ] && EXTRA="$EXTRA --ow_whirlpool"
    [ "$SHUFFLELINKS" = "on" ] && EXTRA="$EXTRA --shufflelinks"
    [ "$SHUFFLETAVERN" = "on" ] && EXTRA="$EXTRA --shuffletavern"
    [ "$PSEUDOBOOTS" = "on" ] && EXTRA="$EXTRA --pseudoboots"
    [ "$MIRRORSCROLL" = "on" ] && EXTRA="$EXTRA --mirrorscroll"
    [ "$BOMBBAG" = "on" ] && EXTRA="$EXTRA --bombbag"
    [ "$REDUCE_FLASHING" = "on" ] && EXTRA="$EXTRA --reduce_flashing"
    [ "$SHUFFLE_SFX" = "on" ] && EXTRA="$EXTRA --shuffle_sfx"
    [ "$MSU" != "Default" ] && EXTRA="$EXTRA --msu_resume"
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
python3 "$BIN/alttpr-enginepatch.py" "$DR" >/dev/null || {
  echo "ERROR: Stopwatch room-data reservation could not be enforced."
  echo "SEED:"
  exit 1
}
DR_LOG="$STAGE/engine.log"
ATTEMPT=1
MAX_ATTEMPTS=1
# Entrance layouts can occasionally produce an impossible dungeon-item fill.
# That failure depends on the random seed, not the selected settings, so retry
# only this known FillError with a fresh seed instead of rejecting a valid mode.
[ "${ENTRANCE_SHUFFLE:-vanilla}" != "vanilla" ] && MAX_ATTEMPTS=5
while :; do
  # shellcheck disable=SC2086
  timeout 300 python3 DungeonRandomizer.py --rom "$BASE" $FLAGS $EXTRA \
    --outputpath "$STAGE" --outputname "$TOKEN" >"$DR_LOG" 2>&1
  DR_RC=$?
  [ "$DR_RC" -eq 0 ] && break
  if grep -qE '/Fill\.py|source/overworld/EntranceShuffle2\.py' "$DR_LOG" && \
     [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; then
    ATTEMPT=$((ATTEMPT + 1))
    rm -f "$STAGE"/*.sfc "$STAGE"/*_Spoiler.txt
    continue
  fi
  DETAIL="$(grep 'FillError:' "$DR_LOG" | tail -1)"
  [ -z "$DETAIL" ] && DETAIL="$(tail -1 "$DR_LOG")"
  [ "$DR_RC" -eq 124 ] && DETAIL="Door Randomizer timed out after 300 seconds."
  rm -rf "$STAGE"
  echo "ERROR: ${DETAIL:-Door Randomizer failed.}"
  echo "SEED:"
  exit 1
done

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

# The current DR base patch retains the HUD timer Data Bank bug from the old
# engine at relocated addresses. Install the verified DB=$7E trampoline whenever
# Stopwatch is selected; Disabled seeds are a no-op.
python3 "$BIN/alttpr-timerpatch.py" "$FINAL" || {
  rm -f "$FINAL"
  echo "ERROR: Stopwatch safety patch failed."
  echo "SEED:"
  exit 1
}

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

# Recalbox 10's native file watcher discovers the new ROM. Do not rewrite the
# gamelist or restart ES from the game-launch process; doing so races its safe
# relaunch lifecycle. The boot self-heal adds friendly metadata deterministically.

echo "generated: $FINAL"
echo "SEED:$FINAL"
