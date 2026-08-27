set -uo pipefail
# Build a real 'alttpr' theme folder in recalbox-next that clones snes but uses
# the ALTTPR PNG logo + ALTTPR sprite sheet as the console/side graphic.
TROOT="$1"
LOGO="$2"
SPRITES="${3:-}"

[ -d "$TROOT/snes" ] || exit 0

rm -rf "$TROOT/alttpr"
mkdir -p "$TROOT/alttpr/data"
cp -r "$TROOT/snes/." "$TROOT/alttpr/" 2>/dev/null

# logo (PNG renders in ES; embedded-in-SVG does not)
cp "$LOGO" "$TROOT/alttpr/data/logo.png"
for r in us eu jp; do [ -d "$TROOT/alttpr/data/$r" ] && cp "$LOGO" "$TROOT/alttpr/data/$r/logo.png"; done
rm -f "$TROOT/alttpr/data/logo.svg" "$TROOT/alttpr/data/us/logo.svg" "$TROOT/alttpr/data/eu/logo.svg" "$TROOT/alttpr/data/jp/logo.svg" 2>/dev/null

# side graphic: replace the SNES console+cartridge (consolegame) with the sprites
HAVE_SPR=0
if [ -n "$SPRITES" ] && [ -f "$SPRITES" ]; then
  HAVE_SPR=1
  cp "$SPRITES" "$TROOT/alttpr/data/consolegame.png"
  for r in us eu jp; do [ -d "$TROOT/alttpr/data/$r" ] && cp "$SPRITES" "$TROOT/alttpr/data/$r/consolegame.png"; done
  rm -f "$TROOT/alttpr/data/consolegame.svg" "$TROOT/alttpr/data/us/consolegame.svg" "$TROOT/alttpr/data/eu/consolegame.svg" "$TROOT/alttpr/data/jp/consolegame.svg" 2>/dev/null
fi

CX="$TROOT/alttpr/custom.xml"
if [ -f "$CX" ] && ! grep -q "data/logo.png" "$CX"; then
  python3 - "$CX" "$HAVE_SPR" <<'PY'
import sys, re
p=sys.argv[1]; have_spr=sys.argv[2]=="1"
d=open(p,encoding="utf-8").read()
imgs='<image name="logo"><path>./data/logo.png</path></image>'
imgs+='<image name="logo" region="us"><path>./data/logo.png</path></image>'
imgs+='<image name="logo" region="eu"><path>./data/logo.png</path></image>'
imgs+='<image name="logo" region="jp"><path>./data/logo.png</path></image>'
if have_spr:
    for reg in ('','us','eu','jp'):
        r=(' region="%s"'%reg) if reg else ''
        path='./data/%sconsolegame.png'%((reg+'/') if reg else '')
        imgs+='<image name="consolegame" extra="true"%s><path>%s</path></image>'%(r,path)
# ALTTPR uses the sprite montage as its right-hand identity art; hide the
# inherited SNES controller so it does not compete with the montage.
hidden=''
for reg in ('','us','eu','jp'):
    r=(' region="%s"'%reg) if reg else ''
    hidden+='<image name="controller" extra="true"%s><pos>2 2</pos></image>'%r
info_names=', '.join('info%d'%i for i in range(1, 13))
# Hide the inherited single-line metadata rows and replace them with one fixed
# multiline field. A normal text element wraps but never marquee-scrolls.
fixed=('<text name="%s" extra="true"><pos>2 2</pos></text>'
       '<text name="alttpr_info" extra="true">'
       '<pos>0.33 0.055</pos><size>0.39 0.56</size>'
       '<fontPath>./data/arts/Exo2-SemiBoldCondensed.otf</fontPath>'
       '<fontSize>0.014</fontSize><lineSpacing>1.08</lineSpacing>'
       '<alignment>left</alignment><color>ffffff</color>'
       '</text>')%info_names
override='<view name="system, basic, detailed, gameclip">%s%s%s</view>'%(imgs,hidden,fixed)
m=re.search(r"</formatVersion>", d)
if m:
    d=d[:m.end()]+override+d[m.end():]
    open(p,"w",encoding="utf-8").write(d)
    print("logo + consolegame override injected")
PY
fi
echo "alttpr theme built at $TROOT/alttpr (sprites=$HAVE_SPR)"