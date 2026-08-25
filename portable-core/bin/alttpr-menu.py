#!/usr/bin/env python3
"""Interactive ALTTPR seed-generation menu (pygame / KMSDRM).

Launched by EmulationStation (via the configgen alttpr generator) when the user
selects the "Custom Seed" launcher. Presents a controller-driven menu of seed
options, then runs alttpr-generate.sh with the chosen flags while showing a
progress screen. Writes the resulting seed path to /tmp/alttpr_seed.

Exit codes:  0 = seed generated (path in /tmp/alttpr_seed),  2 = cancelled.
"""
import os
import sys
import glob
import time
import subprocess

os.environ["SDL_VIDEODRIVER"] = "KMSDRM"
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

ENGINE = "/recalbox/share/alttpr"
GENERATE = ENGINE + "/bin/alttpr-generate.sh"
NAMEGEN = ENGINE + "/bin/alttpr-name.py"
SPRITE_DIR = ENGINE + "/sprites"
SPRITE_MANIFEST = ENGINE + "/bin/data/sprites.json"
PREVIEW_DIR = ENGINE + "/bin/sprite-previews"
MSU_MANIFEST = ENGINE + "/msu/packs.json"
CHOICES = "/tmp/alttpr_choices.env"
SEEDOUT = "/tmp/alttpr_seed"


def new_nickname():
    """Generate a fresh spaced nickname (e.g. 'Bumpy Pumpkin') for a seed.

    Decided up front — when the menu opens and after each generate — so the
    progress splash can name the seed being made and the SAME nickname ends up
    in the seed filename (the menu passes it to generate.sh).
    """
    try:
        out = subprocess.check_output(["python3", NAMEGEN], timeout=10)
        nick = out.decode("utf-8", "replace").strip()
        if nick:
            return nick
    except Exception:
        pass
    return "Mystery Seed"

# --- colors ------------------------------------------------------------------
BG = (24, 20, 37)
PANEL = (36, 30, 56)
FG = (235, 232, 245)
DIM = (150, 145, 170)
ACCENT = (240, 190, 70)     # triforce gold
HILITE = (58, 48, 88)
GREEN = (120, 210, 130)
RED = (220, 110, 110)


def load_sprite_manifest():
    """Return (names, meta) for the friendly sprite picker.

    names: ["(default)", <friendly names sorted>...]
    meta:  {friendly_name: {"file": <basename w/o .zspr>, "author", "tags"}}

    Reads sprites.json (built from alttpr.com's official list). Falls back to a
    raw filesystem glob (filenames as both label and value) if the manifest is
    missing, so the menu still works on a bare install.
    """
    names = ["(default)"]
    meta = {}
    try:
        import json
        entries = json.load(open(SPRITE_MANIFEST, encoding="utf-8"))
        present = set()
        try:
            present = set(os.listdir(SPRITE_DIR))
        except Exception:
            pass
        for e in entries:
            fn = e.get("file", "")
            if present and (fn + ".zspr") not in present:
                continue  # skip entries whose .zspr isn't on disk
            # only offer sprites that have a preview image on disk (drop the
            # handful with no official preview so every pick shows an image)
            prev = e.get("preview", "")
            if not prev or not os.path.isfile(os.path.join(PREVIEW_DIR, prev)):
                continue
            nm = e.get("name") or fn
            names.append(nm)
            meta[nm] = {"file": fn,
                        "author": e.get("author", ""),
                        "preview": prev}
        if len(names) > 1:
            return names, meta
    except Exception:
        pass
    # fallback: raw glob, filename is both label and value
    try:
        for p in sorted(glob.glob(os.path.join(SPRITE_DIR, "*.zspr"))):
            b = os.path.basename(p)[:-5]
            names.append(b)
            meta[b] = {"file": b, "author": "", "preview": ""}
    except Exception:
        pass
    return names, meta


def sprite_options():
    return load_sprite_manifest()[0]


def load_msu_manifest():
    """Return (names, meta) for the MSU music-pack picker.

    names: ["Default", <pack names sorted>...]   (Default = original ALTTP music)
    meta:  {name: {"author": ..., "slug": ..., "tracks": N}}
    """
    names = ["Default"]
    meta = {}
    try:
        import json
        for p in json.load(open(MSU_MANIFEST, encoding="utf-8")):
            nm = p.get("name") or p.get("slug")
            if not nm:
                continue
            names.append(nm)
            meta[nm] = {"author": p.get("author", ""),
                        "slug": p.get("slug", ""),
                        "tracks": p.get("tracks", 0)}
    except Exception:
        pass
    return names, meta


# --- option model ------------------------------------------------------------
# Each option: (key, label, [values], default_index)
#
# These rows map directly to the Python Door Randomizer CLI. New DR-specific
# entrance/door/overworld options are added in a separate menu expansion; this
# first pass restores the proven controller UI with a clean baseline option set.
def build_options(sprite_names=None, msu_names=None):
    # Row order and the default (index 0) for each row are curated in
    # docs/option-help.md; keep this list in sync with that doc's block order
    # and first-listed value. The right-hand help panel text is loaded from
    # option-help.json (generated from the same doc).
    sprites = sprite_names if sprite_names is not None else sprite_options()
    msus = msu_names if msu_names is not None else load_msu_manifest()[0]
    opts = [
        ("MODE_V", "Game State", ["standard", "open", "inverted", "retro"], 0),
        ("GOAL", "Goal", ["ganon", "crystals", "dungeons", "pedestal",
                           "ganonhunt", "triforcehunt", "trinity",
                           "completionist"], 0),
        ("CRYSTALS_GT", "Crystals Required for GT",
         ["7", "6", "5", "4", "3", "2", "1", "0", "random"], 0),
        ("CRYSTALS_GANON", "Ganon Vulnerable",
         ["7", "6", "5", "4", "3", "2", "1", "0", "random"], 0),
        ("SWORDS", "Swords", ["random", "assured", "vanilla", "swordless"], 0),
        ("DIFFICULTY", "Item Pool", ["normal", "hard", "expert"], 0),
        ("ITEM_FUNCTIONALITY", "Item Function", ["normal", "hard", "expert"], 0),
        ("LOGIC", "Glitches Logic", ["noglitches", "minorglitches",
                                      "owglitches", "hybridglitches",
                                      "nologic"], 0),
        ("ALGORITHM", "Item Placement",
         ["balanced", "vanilla_fill", "major_only", "dungeon_only",
          "district"], 0),
        ("ACCESSIBILITY", "Accessibility", ["items", "locations", "none"], 0),
        ("HINTS", "Hints", ["on", "off"], 0),
        ("SHUFFLEBOSSES", "Boss Shuffle",
         ["none", "simple", "unique", "full", "random"], 0),
        ("SHUFFLEENEMIES", "Enemy Shuffle", ["none", "shuffled"], 0),
        ("ENEMY_DAMAGE", "Enemy Damage", ["default", "shuffled", "random"], 0),
        ("ENEMY_HEALTH", "Enemy Health",
         ["default", "easy", "normal", "hard", "expert"], 0),
        ("POTTERY", "Pot Shuffle",
         ["none", "keys", "dungeon", "cave", "cavekeys", "reduced",
          "clustered", "nonempty", "lottery"], 0),
        ("QUICKSWAP", "Quickswap (L/R)", ["true", "false"], 0),
        ("TIMER", "HUD Timer",
         ["none", "display", "timed", "timed-ohko", "ohko",
          "timed-countdown"], 0),
        ("SPRITE", "Link Sprite", sprites, 0),
        ("HEARTCOLOR", "Heart Color", ["red", "blue", "green", "yellow",
                                       "random"], 0),
        ("MSU", "MSU Music Pack", msus, 0),
        ("SPOILER", "Spoiler Log", ["on", "off"], 0),
    ]
    return opts


def load_help():
    """Load option-help.json (key -> {value: text, or "_row": text})."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "option-help.json")
    try:
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class Menu:
    def __init__(self):
        pygame.init()
        try:
            pygame.display.init()
        except Exception:
            pass
        try:
            pygame.font.init()
        except Exception:
            pass
        pygame.joystick.init()
        self.sticks = []
        for i in range(pygame.joystick.get_count()):
            try:
                js = pygame.joystick.Joystick(i)
                js.init()
                self.sticks.append(js)
            except Exception:
                pass

        try:
            info = pygame.display.Info()
            w = info.current_w if info.current_w > 0 else 1280
            h = info.current_h if info.current_h > 0 else 720
        except Exception:
            w, h = 1280, 720
        try:
            self.screen = pygame.display.set_mode((w, h), pygame.FULLSCREEN)
        except Exception:
            try:
                self.screen = pygame.display.set_mode((1280, 720))
            except Exception:
                if os.environ.get("ALTTPR_MENU_HEADLESS"):
                    self.screen = None
                else:
                    raise
        if self.screen is not None:
            self.W, self.H = self.screen.get_size()
            pygame.mouse.set_visible(False)
        else:
            self.W, self.H = w, h

        base = max(16, int(self.H / 26))
        self.font = pygame.font.Font(None, base)
        self.font_sm = pygame.font.Font(None, int(base * 0.8))
        self.font_lg = pygame.font.Font(None, int(base * 1.6))
        self.clock = pygame.time.Clock()

        self.sprite_names, self.sprite_meta = load_sprite_manifest()
        self.msu_names, self.msu_meta = load_msu_manifest()
        self.options = build_options(self.sprite_names, self.msu_names)
        self.values = [o[3] for o in self.options]
        self.sel = 0                 # start focused on the top option row
        # two virtual action rows follow the options: Generate & Play, Cancel
        self.n = len(self.options)
        self.scroll = 0
        # input repeat
        self._last_move = 0.0
        self._held = None
        self._hat = (0, 0)          # last joystick hat (d-pad) state
        try:
            pygame.key.set_repeat(280, 90)   # keyboard auto-repeat for scrubbing
        except Exception:
            pass
        # right-hand help panel
        self.help = load_help()
        self._help_id = None        # identity of currently shown text
        self._help_t0 = time.time()  # scroll animation anchor
        self._wrap_cache = {}        # (id, width) -> wrapped lines
        self._preview_cache = {}     # (file, scale) -> scaled Surface (or None)
        # pick the seed's nickname up front so the progress splash can name it and
        # the same nickname lands in the seed filename (passed to generate.sh).
        self.nickname = new_nickname()

    # --- input helpers -------------------------------------------------------
    def _edge_move(self, direction, now):
        """Debounced continuous movement while a dir is held."""
        if direction is None:
            self._held = None
            return False
        if direction != self._held:
            self._held = direction
            self._last_move = now
            return True
        # repeat after initial delay
        if now - self._last_move > 0.16:
            self._last_move = now
            return True
        return False

    def poll(self):
        """Return a logical action string or None."""
        action = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "cancel"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w):
                    action = "up"
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    action = "down"
                elif e.key in (pygame.K_LEFT, pygame.K_a):
                    action = "left"
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    action = "right"
                elif e.key in (pygame.K_LEFTBRACKET,):
                    action = "fastleft"
                elif e.key in (pygame.K_RIGHTBRACKET,):
                    action = "fastright"
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    action = "activate"
                elif e.key in (pygame.K_ESCAPE,):
                    action = "cancel"
                elif e.key == pygame.K_PAGEUP:
                    action = "pageup"
                elif e.key == pygame.K_PAGEDOWN:
                    action = "pagedown"
            if e.type == pygame.JOYBUTTONDOWN:
                # Unified control model (shared with Clean Old Seeds):
                #   L/R shoulders  -> jump the focused value by 10 (horizontal
                #                     only; never moves the row cursor)
                #   A or B (0/1)   -> execute the focused row (Generate / Cancel)
                # Every other button is ignored, so a stray press can't fire an
                # action — you deliberately land on Generate or Cancel and press
                # A or B.
                if e.button in (4, 6):
                    action = "fastleft"    # L shoulder: jump values by 10
                elif e.button in (5, 7):
                    action = "fastright"   # R shoulder: jump values by 10
                elif e.button in (0, 1):
                    action = "activate"    # A or B: execute the focused row
            if e.type == pygame.JOYHATMOTION:
                # Track held hat state; the repeat logic below turns a held
                # direction into auto-repeating moves (a hat only emits one event
                # per change, so without this a 500+ item list is unnavigable).
                self._hat = e.value
        if action:
            # a discrete key/button press: reset repeat anchor so a following
            # held direction still gets its own initial delay
            if action in ("up", "down", "left", "right"):
                self._held = action
                self._last_move = time.time()
            return action
        # held direction (hat or analog) -> auto-repeat via _edge_move
        now = time.time()
        ax = ay = 0.0
        for js in self.sticks:
            try:
                if js.get_numaxes() >= 2:
                    ax = ax or js.get_axis(0)
                    ay = ay or js.get_axis(1)
            except Exception:
                pass
        hx, hy = self._hat
        d = None
        if hy == 1 or ay < -0.6:
            d = "up"
        elif hy == -1 or ay > 0.6:
            d = "down"
        elif hx == -1 or ax < -0.6:
            d = "left"
        elif hx == 1 or ax > 0.6:
            d = "right"
        if self._edge_move(d, now):
            action = d
        return action

    # --- state changes -------------------------------------------------------
    def apply(self, action):
        rows = self.n + 2   # option rows + Generate & Play + Cancel
        if action == "up":
            self.sel = (self.sel - 1) % rows
        elif action == "down":
            self.sel = (self.sel + 1) % rows
        elif action == "pageup":
            self.sel = max(0, self.sel - 6)
        elif action == "pagedown":
            self.sel = min(rows - 1, self.sel + 6)
        elif action in ("left", "right") and self.sel < self.n:
            key, label, vals, _ = self.options[self.sel]
            step = -1 if action == "left" else 1
            self.values[self.sel] = (self.values[self.sel] + step) % len(vals)
        elif action in ("fastleft", "fastright") and self.sel < self.n:
            # jump by 10 for fast scrubbing of long lists (e.g. 500+ sprites)
            key, label, vals, _ = self.options[self.sel]
            step = -10 if action == "fastleft" else 10
            self.values[self.sel] = (self.values[self.sel] + step) % len(vals)
        elif action == "activate":
            if self.sel == self.n:
                return "generate"
            if self.sel == self.n + 1:
                return "cancel"
            # activate on an option row advances its value (handy shortcut)
            key, label, vals, _ = self.options[self.sel]
            self.values[self.sel] = (self.values[self.sel] + 1) % len(vals)
        elif action == "cancel":       # keyboard Esc hard-escape only
            return "cancel"
        return None

    # --- help panel ----------------------------------------------------------
    def _current_help(self):
        """(identity, title, text) for the row/value under the cursor."""
        if self.sel == self.n:
            return ("__generate__", "Generate & Play",
                    "Create the seed using the options on the left and boot "
                    "straight into it. Native Python generation usually "
                    "finishes in 10–30 seconds.")
        if self.sel >= self.n + 1:
            return ("__cancel__", "Cancel",
                    "Exit without generating a seed and return to the game "
                    "list. Nothing is created.")
        key, label, vals, _ = self.options[self.sel]
        val = vals[self.values[self.sel]]
        # Sprite rows: build help from the manifest (author + tags) instead of
        # the static option-help.json, so every sprite gets a useful blurb.
        if key == "SPRITE":
            if val == "(default)":
                text = ("Default Link sprite (original game graphics).\n\n"
                        "Purely cosmetic — no effect on logic or gameplay.")
            else:
                m = self.sprite_meta.get(val, {})
                bits = []
                if m.get("author"):
                    bits.append("by %s" % m["author"])
                if bits:
                    bits.append("")
                bits.append("Purely cosmetic — no effect on logic or gameplay.")
                text = "\n".join(bits)
            return ("SPRITE=%s" % val, "%s: %s" % (label, val), text)
        # MSU music-pack rows: help from the pack manifest (author + track count).
        if key == "MSU":
            if val == "Default":
                text = ("Original A Link to the Past soundtrack (no MSU-1 pack).\n\n"
                        "Cosmetic audio only — no effect on logic or gameplay.")
            else:
                m = self.msu_meta.get(val, {})
                bits = []
                if m.get("author"):
                    bits.append("by %s" % m["author"])
                if m.get("tracks"):
                    bits.append("%d tracks" % m["tracks"])
                if bits:
                    bits.append("")
                bits.append("Replaces the in-game music via MSU-1.")
                bits.append("Cosmetic audio only — no effect on logic or gameplay.")
                text = "\n".join(bits)
            return ("MSU=%s" % val, "%s: %s" % (label, val), text)
        # Reuse the curated old help copy after renaming PHP-era keys to their
        # Python DR equivalents.
        aliases = {
            "MODE_V": ("STATE", {}),
            "CRYSTALS_GT": ("CRYSTALS_TOWER", {}),
            "SWORDS": ("WEAPONS", {"random": "randomized"}),
            "DIFFICULTY": ("ITEM_POOL", {}),
            "LOGIC": ("GLITCHES", {
                "noglitches": "none",
                "minorglitches": "none",
                "owglitches": "overworld_glitches",
                "hybridglitches": "hybrid_major_glitches",
                "nologic": "no_logic",
            }),
            "ALGORITHM": ("ITEM_PLACEMENT", {
                "balanced": "advanced",
                "vanilla_fill": "basic",
            }),
            "SHUFFLEBOSSES": ("BOSS_SHUFFLE", {}),
            "SHUFFLEENEMIES": ("ENEMY_SHUFFLE", {}),
            "POTTERY": ("POT_SHUFFLE", {
                "none": "off",
                "keys": "on", "dungeon": "on", "cave": "on",
                "cavekeys": "on", "reduced": "on", "clustered": "on",
                "nonempty": "on", "lottery": "on",
            }),
            "HEARTCOLOR": ("HEART_COLOR", {}),
        }
        help_key, value_aliases = aliases.get(key, (key, {}))
        help_val = value_aliases.get(val, val)
        block = self.help.get(help_key, {})
        text = block.get(help_val)
        if text is None:
            text = block.get("_row", "")
        if not text:
            text = ("Python Door Randomizer option. Use Left/Right to choose "
                    "a value; the selected value is passed directly to DR.")
        title = "%s: %s" % (label, val)
        return ("%s=%s" % (key, val), title, text)

    def _wrap(self, text, font, maxw):
        out = []
        for para in text.split("\n"):
            if not para.strip():
                out.append("")
                continue
            bullet = para.lstrip().startswith("- ")
            indent = "    " if bullet else ""
            cur = ""
            for w in para.split(" "):
                trial = (cur + " " + w) if cur else w
                if font.size(trial)[0] <= maxw or not cur:
                    cur = trial
                else:
                    out.append(cur)
                    cur = indent + w
            if cur:
                out.append(cur)
        return out

    def _scroll_offset(self, nlines, visible, line_h, now):
        """Auto-scroll: pause at top, glide down, pause at bottom, loop."""
        if nlines <= visible:
            return 0
        scroll_px = (nlines - visible) * line_h
        speed = max(14.0, line_h * 0.8)   # px/sec
        pause = 2.2
        down = scroll_px / speed
        cycle = pause + down + pause
        t = (now - self._help_t0) % cycle
        if t < pause:
            return 0
        t -= pause
        if t < down:
            return int(t * speed)
        return scroll_px

    def _load_preview(self, prev_file, target_w):
        """Load + nearest-neighbor scale a sprite preview PNG. Cached; None-safe."""
        if not prev_file:
            return None
        # choose an integer scale that fits target_w (sprites are 16px wide)
        key = (prev_file, target_w)
        if key in self._preview_cache:
            return self._preview_cache[key]
        surf = None
        try:
            path = os.path.join(PREVIEW_DIR, prev_file)
            raw = pygame.image.load(path)
            try:
                raw = raw.convert_alpha()
            except Exception:
                pass  # no display yet (e.g. headless) — use unconverted surface
            sw = raw.get_width() or 16
            scale = max(1, int(target_w // sw))
            surf = pygame.transform.scale(
                raw, (sw * scale, raw.get_height() * scale))
        except Exception:
            surf = None
        self._preview_cache[key] = surf
        return surf

    def draw_help_panel(self):
        ident, title, text = self._current_help()
        if ident != self._help_id:
            self._help_id = ident
            self._help_t0 = time.time()   # restart scroll for the new text
        px0 = int(self.W * 0.60)
        px1 = int(self.W * 0.965)
        py0 = int(self.H * 0.17)
        py1 = int(self.H * 0.92)
        pad = int(self.W * 0.012)
        # panel background
        pygame.draw.rect(self.screen, PANEL,
                         (px0, py0, px1 - px0, py1 - py0), border_radius=10)
        # title
        tsurf = self.font_sm.render(title, True, ACCENT)
        self.screen.blit(tsurf, (px0 + pad, py0 + pad))
        tl_y = py0 + pad + int(self.font_sm.get_height() * 1.4)
        pygame.draw.line(self.screen, HILITE,
                         (px0 + pad, tl_y - 4), (px1 - pad, tl_y - 4), 1)
        body_top = tl_y + 4
        # sprite preview image (drawn above the text, centered) when available
        if ident.startswith("SPRITE="):
            val = ident[len("SPRITE="):]
            prev = self.sprite_meta.get(val, {}).get("preview", "")
            target_w = int((px1 - px0) * 0.105)
            img = self._load_preview(prev, target_w)
            if img is not None:
                ix = px0 + (px1 - px0 - img.get_width()) // 2
                self.screen.blit(img, (ix, body_top + pad))
                body_top = body_top + pad + img.get_height() + pad
        # body (clipped, auto-scrolling)
        maxw = px1 - px0 - 2 * pad
        line_h = int(self.font_sm.get_height() * 1.12)
        cache_key = (ident, maxw)
        lines = self._wrap_cache.get(cache_key)
        if lines is None:
            lines = self._wrap(text or "(no description)", self.font_sm, maxw)
            self._wrap_cache[cache_key] = lines
        body_h = py1 - pad - body_top
        visible = max(1, body_h // line_h)
        off = self._scroll_offset(len(lines), visible, line_h, time.time())
        clip = pygame.Rect(px0 + pad, body_top, maxw, visible * line_h)
        self.screen.set_clip(clip)
        y = body_top - off
        for ln in lines:
            if y + line_h >= body_top and y <= body_top + visible * line_h:
                if ln:
                    self.screen.blit(self.font_sm.render(ln, True, FG),
                                     (px0 + pad, y))
            y += line_h
        self.screen.set_clip(None)

    # --- rendering -----------------------------------------------------------
    def draw(self):
        if self.screen is None:
            return
        self.screen.fill(BG)
        # header
        title = self.font_lg.render("ALTTPR  \u2014  Custom Seed", True, ACCENT)
        self.screen.blit(title, (int(self.W * 0.06), int(self.H * 0.04)))
        hint = self.font_sm.render(
            "D-Pad move  \u2022  Left/Right change  \u2022  L/R jump \u00b110  \u2022  A/B = select",
            True, DIM)
        self.screen.blit(hint, (int(self.W * 0.06), int(self.H * 0.11)))

        top = int(self.H * 0.17)
        row_h = int(self.H * 0.066)
        visible = max(6, int((self.H * 0.72) / row_h))
        # keep selection in view
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + visible:
            self.scroll = self.sel - visible + 1

        x = int(self.W * 0.04)
        vx = int(self.W * 0.34)
        val_maxw = int(self.W * 0.21)   # keep values clear of the help panel
        list_w = int(self.W * 0.52)
        total_rows = self.n + 2
        for i in range(self.scroll, min(total_rows, self.scroll + visible)):
            y = top + (i - self.scroll) * row_h
            selected = (i == self.sel)
            if i >= self.n:
                # action rows: Generate & Play (n) and Cancel (n+1)
                if i == self.n:
                    label = "  >>  GENERATE  &  PLAY  <<"
                    col = GREEN if selected else FG
                else:
                    label = "  \u00d7   CANCEL"
                    col = RED if selected else FG
                if selected:
                    pygame.draw.rect(self.screen, HILITE,
                                     (x - 12, y - 4, list_w, row_h - 6),
                                     border_radius=8)
                self.screen.blit(self.font.render(label, True, col), (x, y))
                continue
            key, lbl, vals, _ = self.options[i]
            val = vals[self.values[i]]
            if selected:
                pygame.draw.rect(self.screen, HILITE,
                                 (x - 12, y - 4, list_w, row_h - 6),
                                 border_radius=8)
            self.screen.blit(self.font.render(lbl, True,
                             FG if selected else DIM), (x, y))
            vcol = ACCENT if selected else FG
            arrow_l = "\u2039 " if selected else "  "
            arrow_r = " \u203a" if selected else ""
            # truncate over-long values (e.g. sprite names) to fit the column
            vstr = str(val)
            while vstr and self.font.size(arrow_l + vstr + arrow_r)[0] > val_maxw:
                vstr = vstr[:-1]
            if vstr != str(val):
                vstr = vstr[:-1] + "\u2026"
            vtxt = arrow_l + vstr + arrow_r
            self.screen.blit(self.font.render(vtxt, True, vcol), (vx, y))

        # scroll indicator (between the list and the help panel)
        if total_rows > visible:
            frac = self.sel / max(1, total_rows - 1)
            bar_h = int(self.H * 0.72)
            by = top + int(frac * (bar_h - 20))
            pygame.draw.rect(self.screen, ACCENT,
                             (int(self.W * 0.565), by, 6, 20), border_radius=3)

        # right-hand help panel
        self.draw_help_panel()
        pygame.display.flip()

    def progress(self, msg, t):
        if self.screen is None:
            return
        self.screen.fill(BG)
        title = self.font_lg.render(
            'Generating seed \u201c%s\u201d\u2026' % self.nickname, True, ACCENT)
        r = title.get_rect(center=(self.W // 2, int(self.H * 0.40)))
        self.screen.blit(title, r)
        sub = self.font.render(msg, True, FG)
        rs = sub.get_rect(center=(self.W // 2, int(self.H * 0.50)))
        self.screen.blit(sub, rs)
        # spinner dots
        dots = "." * (1 + int(t * 3) % 4)
        d = self.font_lg.render(dots, True, DIM)
        rd = d.get_rect(center=(self.W // 2, int(self.H * 0.60)))
        self.screen.blit(d, rd)
        pygame.display.flip()

    def message(self, text, color):
        if self.screen is None:
            return
        self.screen.fill(BG)
        m = self.font.render(text, True, color)
        r = m.get_rect(center=(self.W // 2, self.H // 2))
        self.screen.blit(m, r)
        pygame.display.flip()

    # --- generation ----------------------------------------------------------
    def write_choices(self):
        lines = []
        for i, (key, lbl, vals, _) in enumerate(self.options):
            val = vals[self.values[i]]
            # Sprite: write the .zspr basename generate.sh expects, not the
            # friendly display name. "(default)" passes through unchanged.
            if key == "SPRITE" and val != "(default)":
                val = self.sprite_meta.get(val, {}).get("file", val)
            lines.append('%s="%s"' % (key, val))
        # pass the pre-chosen nickname so generate.sh names the seed with the
        # exact name shown on the progress splash (instead of rolling its own).
        lines.append('NICKNAME="%s"' % self.nickname)
        with open(CHOICES, "w") as f:
            f.write("\n".join(lines) + "\n")

    def generate(self):
        self.write_choices()
        try:
            os.remove(SEEDOUT)
        except OSError:
            pass
        # run generator in background, animate progress
        proc = subprocess.Popen(["/bin/bash", GENERATE, "custom"],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        start = time.time()
        seed = ""
        out_lines = []
        while proc.poll() is None:
            self.progress("Generating with Python Door Randomizer",
                          time.time() - start)
            # keep SDL responsive
            pygame.event.pump()
            self.clock.tick(12)
        try:
            out = proc.stdout.read().decode("utf-8", "replace")
            out_lines = out.splitlines()
        except Exception:
            out = ""
        for ln in out_lines:
            if ln.startswith("SEED:"):
                seed = ln[5:].strip()
        # flush the splash nickname so a new one is minted for the next attempt
        # (whether this one succeeds or we fall back into the menu).
        self.nickname = new_nickname()
        if seed and os.path.isfile(seed):
            with open(SEEDOUT, "w") as f:
                f.write(seed + "\n")
            self.message("Seed ready \u2014 launching\u2026", GREEN)
            time.sleep(1.0)
            return 0
        self.message("Generation failed. Returning to menu.", RED)
        time.sleep(2.0)
        return None  # back to menu

    def run(self):
        while True:
            action = self.poll()
            result = self.apply(action) if action else None
            if result == "cancel":
                return 2
            if result == "generate":
                rc = self.generate()
                if rc == 0:
                    return 0
                # else fall back into the menu loop
            self.draw()
            self.clock.tick(30)


def _teardown():
    # Release the KMSDRM display + input devices cleanly, then hard-exit so no
    # lingering fd (DRM master / /dev/input) blocks EmulationStation's resume.
    try:
        pygame.display.quit()
    except Exception:
        pass
    try:
        pygame.joystick.quit()
    except Exception:
        pass
    try:
        pygame.quit()
    except Exception:
        pass


def main():
    rc = 0
    try:
        m = Menu()
    except Exception as e:
        sys.stderr.write("menu init failed: %s\n" % e)
        _teardown()
        os._exit(2)
    try:
        rc = m.run()
    except Exception as e:
        sys.stderr.write("menu error: %s\n" % e)
        rc = 2
    _teardown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    main()
