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

# --- 4. create the ROM tiles (launcher .alttpr files) -------------------------
mkdir -p "$ROOT/SEEDS"
make_tile() { # <filename> <mode-line>
  local f="$ROOT/$1" mode="$2"
  [ -f "$f" ] || printf '%s\n' "$mode" > "$f"
}
make_tile "Generate Custom Seed.alttpr" "custom"
make_tile "Open Ganon.alttpr"           "open"
make_tile "Standard Ganon.alttpr"       "standard"
make_tile "Fast Ganon.alttpr"           "fast_ganon"
make_tile "Keysanity.alttpr"            "keysanity"
make_tile "Pedestal.alttpr"             "pedestal"
make_tile "Inverted.alttpr"             "inverted"
make_tile "Clean Old Seeds.alttpr"      "cleanup"
make_tile "View Spoiler.alttpr"         "spoiler"

# --- 5. retroarch: flush SRAM during play; no savestate autoload --------------
RACFG=/recalbox/share/system/configs/retroarch/retroarchcustom.cfg
if [ -f "$RACFG" ]; then
  grep -qE '^autosave_interval = "10"' "$RACFG" || sed -i 's/^autosave_interval.*/autosave_interval = "10"/' "$RACFG" 2>/dev/null || echo 'autosave_interval = "10"' >> "$RACFG"
fi

say "alttpr integration installed/verified"

# --- 6. theme: put the ALTTPR logo on the carousel ----------------------------
# recalbox-next v10 resolves the system carousel logo from
#   data/arts/systems_logos/${system.name}.png  (+ -eu/-jp/-us variants)
# and includes _views/_partials/systems/${system.name}.xml. The theme lives on
# the overlay rootfs (may not persist an unclean shutdown), so we reapply the art
# every boot from the persistent copy on the share.
LOGO_SRC="$ENGINE/es/alttpr-logo-carousel.png"
for THEME in \
  /recalbox/share_init/system/.emulationstation/themes/recalbox-next \
  /recalbox/share/themes/recalbox-next ; do
  [ -d "$THEME/data/arts/systems_logos" ] || continue
  if [ -f "$LOGO_SRC" ]; then
    for v in "" "-eu" "-jp" "-us"; do
      cp "$LOGO_SRC" "$THEME/data/arts/systems_logos/alttpr${v}.png" 2>/dev/null
    done
    say "installed alttpr carousel logo in $THEME"
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
	</view>
</theme>
XML
  say "wrote alttpr theme partial (explicit logo) in $THEME"
  # side console art: reuse snes consolegame svgs so the detail view isn't blank
  ASSETS="$THEME/data/arts/systems_assets"
  if [ -d "$ASSETS" ]; then
    for suf in consolegame eu-consolegame jp-consolegame us-consolegame \
               controls eu-console jp-console us-console; do
      [ -f "$ASSETS/snes-${suf}.svg" ] && [ ! -f "$ASSETS/alttpr-${suf}.svg" ] && \
        cp "$ASSETS/snes-${suf}.svg" "$ASSETS/alttpr-${suf}.svg" 2>/dev/null
    done
    # iconset (carousel small icon)
    for suf in icon_empty icon_filled; do
      [ -f "$ASSETS/snes-${suf}.svg" ] && [ ! -f "$ASSETS/alttpr-${suf}.svg" ] && \
        cp "$ASSETS/snes-${suf}.svg" "$ASSETS/alttpr-${suf}.svg" 2>/dev/null
    done
  fi
done
