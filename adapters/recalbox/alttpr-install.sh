#!/bin/bash
# Install/repair the ALTTPR EmulationStation integration on Recalbox 10.
# Idempotent + self-healing: called every boot by custom.sh so the configgen
# hook is reapplied into the (overlay/tmpfs-backed) rootfs regardless of whether
# overlay changes persisted.
set -uo pipefail

ENGINE=/recalbox/share/alttpr
ROOT=/recalbox/share/roms/alttpr
CG=/usr/lib/python3.11/site-packages/configgen
ESDIR=/recalbox/share/system/.emulationstation
BASELIST=/recalbox/share_init/system/.emulationstation/systemlist.xml
USERLIST="$ESDIR/systemlist.xml"
LOG=/recalbox/share/system/logs/alttpr-install.log
say(){ echo "$(date) $*" >>"$LOG"; echo "$*"; }

mkdir -p "$(dirname "$LOG")"
rm -f /tmp/alttpr_refresh /tmp/alttpr_gamelist_pending
rm -f "$ENGINE/bin/alttpr-refresh-worker.sh"

# --- 1. make rootfs writable so we can drop the generator into configgen ------
mount -o remount,rw / 2>/dev/null || true

# --- 2. install the custom generator + register the emulator ------------------
mkdir -p "$CG/generators/alttpr"
cp "$ENGINE/es/alttprGenerator.py" "$CG/generators/alttpr/alttprGenerator.py"
touch "$CG/generators/alttpr/__init__.py"

# register in emulatorlauncher.getGenerator (add an elif for 'alttpr')
EL="$CG/emulatorlauncher.py"
if ! grep -q '"alttpr"' "$EL" 2>/dev/null; then
  python3 - "$EL" <<'PY'
import sys
p = sys.argv[1]
src = open(p).read()
# insert our branch just before the first existing "elif emulator ==" or "if emulator =="
marker = '    if emulator == "advancemame":'
block = (
'    if emulator == "alttpr":\n'
'        module = __import__("configgen.generators.alttpr.alttprGenerator", fromlist=["AlttprGenerator"])\n'
'        generatorClass = getattr(module, "AlttprGenerator")\n'
'        return generatorClass()\n'
)
if '"alttpr"' not in src and marker in src:
    src = src.replace(marker, block + marker, 1)
    open(p, "w").write(src)
    print("patched emulatorlauncher")
else:
    print("marker missing or already patched")
PY
  rm -f "$CG/emulatorlauncher.pyc" "$CG/__pycache__/emulatorlauncher."*.pyc 2>/dev/null || true
  say "registered alttpr generator dispatch"
fi

# register 'alttpr' in recalboxBins so the "known emulator" check passes
RF="$CG/recalboxFiles.py"
BINS_OK=$(python3 -c "import sys; sys.path.insert(0,'$CG/..'); import configgen.recalboxFiles as r; print('yes' if 'alttpr' in r.recalboxBins else 'no')" 2>/dev/null)
if [ "$BINS_OK" != "yes" ]; then
  python3 - "$RF" <<'PY'
import sys, re
p = sys.argv[1]
src = open(p).read()
if "'alttpr'" not in src:
    # recalboxBins is a dict literal starting with "recalboxBins =\{...}" or similar
    m = re.search(r"recalboxBins\s*=\\\s*\n\{", src)
    if m:
        src = src[:m.end()] + "\n    'alttpr'      : '/bin/true'," + src[m.end():]
        open(p, "w").write(src)
        print("registered alttpr in recalboxBins")
    else:
        print("recalboxBins marker not found")
PY
  rm -f "$CG/__pycache__/recalboxFiles."*.pyc 2>/dev/null || true
  say "registered alttpr in recalboxBins"
fi

# --- 3. build the systemlist.xml with an ALTTPR system ------------------------
mkdir -p "$ESDIR"
[ -f "$USERLIST" ] || cp "$BASELIST" "$USERLIST"

if ! grep -q 'name="alttpr"' "$USERLIST"; then
  python3 - "$USERLIST" <<'PY'
import sys
p = sys.argv[1]
xml = open(p, encoding="utf-8").read()
entry = '''  <system uuid="a17e0000-0000-4000-8000-000000000001" name="alttpr" fullname="ALTTPR - Link to the Past Randomizer">
    <descriptor path="%ROOT%/alttpr" theme="alttpr" extensions=".alttpr .sfc .smc" icon="" downloader="0"/>
    <scraper screenscraper="4"/>
    <properties type="console" pad="mandatory" keyboard="no" mouse="no" lightgun="no" releasedate="1991-11" manufacturer="Nintendo" retroachievements="0" crt.multiresolution="0" crt.multiregion="1" ignoredfiles=""/>
    <emulatorList>
      <emulator name="alttpr">
        <core name="alttpr" priority="1" extensions=".alttpr .sfc .smc" netplay="0" softpatching="0" compatibility="high" speed="high" crt.available="0"/>
      </emulator>
    </emulatorList>
  </system>
'''
if 'name="alttpr"' not in xml:
    xml = xml.replace("</systemList>", entry + "</systemList>")
    open(p, "w", encoding="utf-8").write(xml)
    print("added alttpr system to systemlist")
PY
  say "added alttpr system to systemlist.xml"
else
  # ensure the theme attribute is 'alttpr' (align with logo resolution)
  sed -i 's#\(name="alttpr"[^>]*\)\n#\1#' "$USERLIST" 2>/dev/null || true
  python3 - "$USERLIST" <<'PY' 2>/dev/null || true
import sys, re
p = sys.argv[1]
d = open(p, encoding="utf-8").read()
d2 = re.sub(r'(<descriptor path="%ROOT%/alttpr"[^>]*?theme=")snes(")', r'\1alttpr\2', d)
if d2 != d:
    open(p, "w", encoding="utf-8").write(d2)
    print("updated alttpr theme attr -> alttpr")
PY
fi

# --- 4. restore the curated ALTTPR menu --------------------------------------
# Keep the system root intentionally small: three action tiles plus one SEEDS
# folder. Seed configuration belongs in the fullscreen pygame menu, not in a
# wall of raw preset launchers.
PFX="ƒ "
SEEDS="$ROOT/SEEDS"
ART="$ROOT/.art"
mkdir -p "$SEEDS" "$ART"

rm -f "$ROOT"/*.alttpr 2>/dev/null
printf '%s\n' custom  > "$ROOT/${PFX}Generate Custom Seed.alttpr"
printf '%s\n' spoiler > "$ROOT/${PFX}View Spoiler Logs.alttpr"
printf '%s\n' cleanup > "$ROOT/${PFX}Clean Old Seeds.alttpr"

# Original curated artwork recovered from the prior Recalbox installation.
ARTSRC="$ENGINE/es/gamelist-art"
[ -f "$ARTSRC/box.png" ]  && cp -f "$ARTSRC/box.png"  "$ART/box.png"
[ -f "$ARTSRC/seed.png" ] && cp -f "$ARTSRC/seed.png" "$ART/seed.png"
chmod 644 "$ART"/*.png 2>/dev/null || true

# Rebuild only the menu-level records while preserving generated seed records
# (including play count/last-played metadata) from the existing gamelist.
python3 - "$ROOT/gamelist.xml" "$PFX" <<'PY' 2>/dev/null || true
import os, re, sys
gl, pfx = sys.argv[1], sys.argv[2]
try:
    old = open(gl, encoding="utf-8").read()
except OSError:
    old = ""

seed_blocks = []
seed_paths = set()
for block in re.findall(r"\s*<game(?:\s[^>]*)?>.*?</game>", old, re.S):
    match = re.search(r"<path>(?:\./)?(SEEDS/[^<]+\.sfc)</path>", block)
    if match and os.path.isfile(os.path.join(os.path.dirname(gl),
                                             match.group(1))):
        block = re.sub(r"<image>.*?</image>",
                       "<image>./.art/seed.png</image>", block, flags=re.S)
        seed_blocks.append(block.strip() + "\n")
        seed_paths.add(match.group(1))

# Add physical seeds missing from the gamelist; stale rows were dropped above.
seeds_dir = os.path.join(os.path.dirname(gl), "SEEDS")
for filename in sorted(os.listdir(seeds_dir)):
    if not filename.endswith(".sfc"):
        continue
    path = "SEEDS/" + filename
    if path in seed_paths:
        continue
    stem = filename[:-4]
    parts = stem.split("_")
    mode = parts[1] if len(parts) > 1 else "seed"
    date = parts[-1] if len(parts) > 2 else ""
    nickname = parts[-2] if len(parts) > 2 else stem
    nickname = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", nickname)
    seed_blocks.append(
        "  <game>\n"
        f"    <path>{path}</path>\n"
        f"    <name>ALTTPR {mode} - {date} ({nickname})</name>\n"
        "    <image>./.art/seed.png</image>\n"
        "    <desc>Generated A Link to the Past Randomizer seed.</desc>\n"
        "  </game>\n")

entries = [
    (f"{pfx}Generate Custom Seed.alttpr", f"{pfx}Generate Custom Seed",
     "Configure a Python Door Randomizer seed in the controller-driven menu, "
     "then generate and play it immediately."),
    (f"{pfx}View Spoiler Logs.alttpr", f"{pfx}View Spoiler Logs",
     "Browse spoiler logs for generated seeds on the TV."),
    (f"{pfx}Clean Old Seeds.alttpr", f"{pfx}Clean Old Seeds",
     "Delete old generated seeds after an on-screen confirmation. Saves remain."),
]
blocks = []
for path, name, desc in entries:
    blocks.append(
        "  <game>\n"
        f"    <path>{path}</path>\n"
        f"    <name>{name}</name>\n"
        "    <image>./.art/box.png</image>\n"
        f"    <desc>{desc}</desc>\n"
        "  </game>\n")
blocks.append(
    "  <folder>\n"
    "    <path>SEEDS</path>\n"
    "    <name>SEEDS</name>\n"
    "    <image>./.art/box.png</image>\n"
    "    <desc>All generated ALTTPR seeds. Pick one to play.</desc>\n"
    "  </folder>\n")

with open(gl, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0"?>\n<gameList>\n')
    f.writelines(blocks)
    f.writelines(seed_blocks)
    f.write("</gameList>\n")
PY

# Recalbox merges every mounted storage root. The old USB share may still carry
# an obsolete ALTTPR tree, which duplicates the action tiles and seed library.
# The authoritative tree is the new ext4 SHARE; remove only stale external
# ALTTPR trees. This also self-heals if Recalbox recreates the directory later.
for EXT in /recalbox/share/externals/*/recalbox/roms/alttpr \
           /recalbox/share/externals/*/roms/alttpr; do
  [ -e "$EXT" ] || continue
  rm -rf "$EXT" 2>/dev/null && say "removed duplicate external ALTTPR tree: $EXT"
done

# Remove legacy external event hooks too. Recalbox 10 must have exactly one
# ALTTPR endgame hook, and it must never restart EmulationStation.
for EXTUS in /recalbox/share/externals/*/recalbox/userscripts \
             /recalbox/share/externals/*/userscripts; do
  [ -d "$EXTUS" ] || continue
  rm -f "$EXTUS"/alttpr-refresh.sh "$EXTUS"/alttpr-refresh.sh.bak-* \
    2>/dev/null || true
done

# --- 5. retroarch: flush SRAM during play; no savestate autoload --------------
RACFG=/recalbox/share/system/configs/retroarch/retroarchcustom.cfg
if [ -f "$RACFG" ]; then
  grep -qE '^autosave_interval = "10"' "$RACFG" || sed -i 's/^autosave_interval.*/autosave_interval = "10"/' "$RACFG" 2>/dev/null || echo 'autosave_interval = "10"' >> "$RACFG"
fi

say "alttpr integration installed/verified"

# Populate the official sprite library on a fresh install. The catalog snapshot
# is committed for offline manifest rebuilds; online runs fetch missing current
# sprites/previews. Guarded so normal self-healing boots do not hit the network.
SPRITE_COUNT="$(find "$ENGINE/sprites" -maxdepth 1 -type f -name '*.zspr' \
  2>/dev/null | wc -l)"
PREVIEW_COUNT="$(find "$ENGINE/bin/sprite-previews" -maxdepth 1 -type f \
  -name '*.png' 2>/dev/null | wc -l)"
if { [ "${SPRITE_COUNT:-0}" -lt 500 ] || \
     [ "${PREVIEW_COUNT:-0}" -lt 500 ]; } && \
   [ -x "$ENGINE/bin/alttpr-sprites.py" ]; then
  python3 "$ENGINE/bin/alttpr-sprites.py" >>"$LOG" 2>&1 || \
    say "sprite population failed; cached/default sprites remain available"
fi

# --- 6. themes: logo, sprite montage, and project information -----------------
# Both bundled themes live on the overlay rootfs, so reapply their customizations
# every boot from persistent assets on the ext4 share.
LOGO_SRC="$ENGINE/es/alttpr-logo-carousel.png"
MONTAGE_SRC="$ENGINE/es/alttpr-consolegame.png"
INFO_SRC="$ENGINE/es/alttpr-info-en.txt"

# Recalbox 10's unified recalbox-next theme.
for THEME in \
  /recalbox/share_init/system/.emulationstation/themes/recalbox-next \
  /recalbox/share/themes/recalbox-next ; do
  [ -d "$THEME/data/arts/systems_logos" ] || continue
  if [ -f "$LOGO_SRC" ]; then
    for v in "" "-eu" "-jp" "-us"; do
      cp "$LOGO_SRC" "$THEME/data/arts/systems_logos/alttpr${v}.png" 2>/dev/null
      chmod 644 "$THEME/data/arts/systems_logos/alttpr${v}.png" 2>/dev/null
    done
    say "installed alttpr carousel logo in $THEME"
  fi
  ASSETS="$THEME/data/arts/systems_assets"
  if [ -f "$MONTAGE_SRC" ] && [ -d "$ASSETS" ]; then
    cp "$MONTAGE_SRC" "$ASSETS/alttpr-consolegame.png"
    chmod 644 "$ASSETS/alttpr-consolegame.png"
  fi
  if [ -f "$INFO_SRC" ] && [ -d "$THEME/data/txt" ]; then
    cp "$INFO_SRC" "$THEME/data/txt/alttpr-en.txt"
    cp "$INFO_SRC" "$THEME/data/txt/alttpr-fr.txt"
    chmod 644 "$THEME/data/txt/alttpr-en.txt" \
              "$THEME/data/txt/alttpr-fr.txt"
  fi
  # Define the system logo explicitly. Included theme paths are resolved relative
  # to the included XML file, so use ${root}; "./data/..." incorrectly resolves
  # under _views/_partials/systems and makes SystemView fall back to fullname text.
  SPART="$THEME/_views/_partials/systems/alttpr.xml"
  cat > "$SPART" <<'XML'
<theme>
	<view name="system">
		<image name="logo"
			path="${root}/data/arts/systems_logos/alttpr.png"
			path.EU="${root}/data/arts/systems_logos/alttpr-eu.png"
			path.JP="${root}/data/arts/systems_logos/alttpr-jp.png"
			path.US="${root}/data/arts/systems_logos/alttpr-us.png"
		/>
		<markdown name="info100" extra="true" color="ffffff" />
		<image name="consolegame" extra="true">
			<path>${root}/data/arts/systems_assets/alttpr-consolegame.png</path>
			<path.EU>${root}/data/arts/systems_assets/alttpr-consolegame.png</path.EU>
			<path.JP>${root}/data/arts/systems_assets/alttpr-consolegame.png</path.JP>
			<path.US>${root}/data/arts/systems_assets/alttpr-consolegame.png</path.US>
		</image>
		<image name="consolegamecontroller" extra="true">
			<pos>2 2</pos>
		</image>
		<image name="controller" extra="true">
			<pos>2 2</pos>
		</image>
	</view>
</theme>
XML
  say "wrote alttpr theme partial (explicit logo) in $THEME"
done

# Recalbox-next-v9 uses one folder per system. Clone SNES as the structural
# baseline, then replace its logo/console art and metadata with ALTTPR content.
for THEME in \
  /recalbox/share_init/system/.emulationstation/themes/recalbox-next-v9 \
  /recalbox/share/themes/recalbox-next-v9 ; do
  [ -d "$THEME/snes" ] || continue
  if [ -x "$ENGINE/es/build_theme.sh" ] && [ -f "$LOGO_SRC" ] && \
     [ -f "$MONTAGE_SRC" ]; then
    bash "$ENGINE/es/build_theme.sh" "$THEME" "$LOGO_SRC" "$MONTAGE_SRC" \
      >>"$LOG" 2>&1
  fi
  CUSTOM="$THEME/alttpr/custom.xml"
  [ -f "$CUSTOM" ] || continue
  python3 - "$CUSTOM" <<'PY' >>"$LOG" 2>&1
import sys
import xml.etree.ElementTree as ET
p = sys.argv[1]
info = [
    "A LINK TO THE PAST RANDOMIZER",
    "Original: A Link to the Past | SNES | 1991",
    "Create a unique seed from the interactive menu.",
    "Shuffle items, enemies, bosses, and entrances.",
    "Choose world, difficulty, and win conditions.",
    "Explore Hyrule with the equipment you find.",
    "LIVE ITEM AUTO-TRACKER",
    "Tracks collected items and dungeon chests.",
    "Scan the QR code or visit:",
    "recalbox.local:8080/itemtracker.html",
]
tree = ET.parse(p)
root = tree.getroot()
for index, line in enumerate(info, 1):
    name = "info%d" % index
    fixed = [element for element in root.iter("text")
             if element.get("name") == name]
    if len(fixed) != 1:
        raise RuntimeError("ALTTPR theme text element is missing: " + name)
    content = fixed[0].find("text")
    if content is None:
        content = ET.SubElement(fixed[0], "text")
    content.text = line
tree.write(p, encoding="unicode")
PY
  if [ $? -ne 0 ]; then
    say "failed to write fixed ALTTPR text in $CUSTOM"
    continue
  fi
  say "built ALTTPR system view in recalbox-next-v9"
done
