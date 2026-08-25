#!/usr/bin/env python3
"""On-TV ALTTPR spoiler-log viewer (pygame / KMSDRM).

Launched by the configgen alttpr generator when the "Spoiler Logs" tile is
selected (the .alttpr file's first line is "spoiler"). Scans the ALTTPR ROM tree
for <seed>.spoiler.json files, lets the user pick one with the controller, and
renders a human-readable, scrollable view (regions/dungeons -> location: item,
shops, bosses, and the step-by-step playthrough).

Controls:  Up/Down scroll  *  L/R or PgUp/PgDn page  *  A select  *  B back/exit
"""
import os
import re
import sys
import glob
import json

os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

ROMROOT = "/recalbox/share/roms/alttpr"

BG = (24, 20, 37)
FG = (235, 232, 245)
DIM = (150, 145, 170)
ACCENT = (240, 190, 70)
HEAD = (130, 200, 240)
HILITE = (58, 48, 88)
ITEMCOL = (170, 230, 175)


# --- humanize helpers --------------------------------------------------------
_CAMEL = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[a-zA-Z])(?=[0-9])')


def humanize_item(raw):
    """'MoonPearl:1' -> 'Moon Pearl'; 'TwentyRupees:1' -> 'Twenty Rupees'."""
    if raw is None:
        return ""
    s = str(raw)
    count = 1
    if ":" in s:
        s, _, c = s.rpartition(":")
        try:
            count = int(c)
        except ValueError:
            count = 1
    # common sword/shield/mail progression tokens
    s = re.sub(r'^L(\d)Sword$', r'Level \1 Sword', s)
    s = re.sub(r'^L(\d)Shield$', r'Level \1 Shield', s)
    s = _CAMEL.sub(" ", s).replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s)
    if count > 1:
        s += "  x%d" % count
    return s


def humanize_loc(raw):
    """Strip the trailing world id (':1') from a location name."""
    s = str(raw)
    if ":" in s:
        s = s.rpartition(":")[0]
    return s


def seed_label(path):
    base = os.path.basename(path)
    base = base[:-len(".spoiler.json")] if base.endswith(".spoiler.json") else base
    # alttpr_none_open_ganon_<hash>_<date>
    parts = base.split("_")
    hash_ = parts[-2] if len(parts) >= 2 else base
    date = parts[-1] if parts else ""
    mode = " ".join(parts[2:-2]).strip() if len(parts) > 4 else "seed"
    if len(date) == 8:
        date = "%s/%s/%s" % (date[0:2], date[2:4], date[4:8])
    return "%s  \u2014  %s  (%s)" % (mode.title() or "Seed", hash_, date)


DUNGEON_ORDER = [
    "Light World", "Hyrule Castle", "Eastern Palace", "Desert Palace",
    "Death Mountain", "Tower Of Hera", "Castle Tower", "Dark World",
    "Dark Palace", "Swamp Palace", "Skull Woods", "Thieves Town",
    "Ice Palace", "Misery Mire", "Turtle Rock", "Ganons Tower", "Special",
]


def build_lines(spoiler):
    """Flatten a spoiler dict into a list of (text, style) tuples.
    style: 'title' | 'head' | 'kv' | 'dim' | 'blank'
    """
    lines = []

    def add(t="", s="kv"):
        lines.append((t, s))

    meta = spoiler.get("meta", {}) or {}
    add("SETTINGS", "title")
    # (meta_key, friendly label)
    setting_fields = [
        ("goal", "Goal"), ("mode", "Mode"), ("world_state", "World State"),
        ("weapons", "Weapons"), ("logic", "Glitches Logic"),
        ("item_placement", "Item Placement"), ("item_pool", "Item Pool"),
        ("item_functionality", "Item Function"), ("dungeon_items", "Dungeon Items"),
        ("accessibility", "Accessibility"), ("hints", "Hints"),
        ("crystals_ganon", "Ganon Crystals"), ("crystals_tower", "Tower Crystals"),
        ("enemizer.boss_shuffle", "Boss Shuffle"),
        ("enemizer.enemy_shuffle", "Enemy Shuffle"),
        ("enemizer.enemy_damage", "Enemy Damage"),
        ("enemizer.enemy_health", "Enemy Health"),
        ("enemizer.pot_shuffle", "Pot Shuffle"),
        ("tournament", "Race Seed"), ("allow_quickswap", "Quickswap"),
        ("build", "Build"), ("size", "Seed Size"),
    ]
    for k, label in setting_fields:
        if k in meta and meta[k] not in (None, ""):
            val = meta[k]
            if isinstance(val, bool):
                val = "on" if val else "off"
            lines.append(((label, str(val)), "pair"))
    add("", "blank")

    # Bosses
    bosses = spoiler.get("Bosses")
    if isinstance(bosses, dict) and bosses:
        add("BOSSES", "title")
        for dung, boss in bosses.items():
            lines.append(((humanize_loc(dung), humanize_item(boss)), "pair"))
        add("", "blank")

    # Regions / dungeons: location -> item
    keys = list(DUNGEON_ORDER)
    for k in spoiler.keys():
        if k not in keys and isinstance(spoiler[k], dict) and \
           k not in ("meta", "Bosses", "playthrough", "Equipped", "Shops"):
            keys.append(k)
    for region in keys:
        block = spoiler.get(region)
        if not isinstance(block, dict) or not block:
            continue
        add(region.upper(), "title")
        for loc, item in block.items():
            lines.append(((humanize_loc(loc), humanize_item(item)), "pair"))
        add("", "blank")

    # Equipped / starting gear
    eq = spoiler.get("Equipped")
    if isinstance(eq, dict) and eq:
        add("STARTING EQUIPMENT", "title")
        for slot, item in eq.items():
            lines.append(((humanize_loc(slot), humanize_item(item)), "pair"))
        add("", "blank")

    # Shops
    shops = spoiler.get("Shops")
    if isinstance(shops, list) and shops:
        add("SHOPS", "title")
        for sh in shops:
            if not isinstance(sh, dict):
                continue
            add("  " + str(sh.get("location", "Shop")), "head")
            for i in range(6):
                it = sh.get("item_%d" % i)
                if isinstance(it, dict) and it.get("item"):
                    price = it.get("price")
                    ptxt = ("  (%s)" % price) if price not in (None, "") else ""
                    lines.append((("    " + humanize_item(it["item"]), ptxt.strip()),
                                  "pair"))
        add("", "blank")

    # Playthrough
    pt = spoiler.get("playthrough")
    if isinstance(pt, dict) and pt:
        add("PLAYTHROUGH", "title")
        # numeric spheres in order, skip meta keys
        def sphere_key(x):
            try:
                return (0, int(x))
            except (ValueError, TypeError):
                return (1, str(x))
        for sphere in sorted(pt.keys(), key=sphere_key):
            block = pt[sphere]
            if sphere == "longest_item_chain" or not isinstance(block, dict):
                continue
            add("  Sphere %s" % sphere, "head")
            for region, contents in block.items():
                if isinstance(contents, dict):
                    for loc, item in contents.items():
                        lines.append((("    " + humanize_loc(loc),
                                       humanize_item(item)), "pair"))
                else:
                    lines.append((("    " + humanize_loc(region),
                                   humanize_item(contents)), "pair"))
        add("", "blank")

    if not lines:
        add("(empty spoiler)", "dim")
    return lines


class Viewer:
    def __init__(self):
        pygame.init()
        try:
            pygame.display.init()
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
            self.screen = pygame.display.set_mode((1280, 720))
        self.W, self.H = self.screen.get_size()
        pygame.mouse.set_visible(False)
        base = max(15, int(self.H / 32))
        self.font = pygame.font.Font(None, base)
        self.font_hd = pygame.font.Font(None, int(base * 1.15))
        self.font_sm = pygame.font.Font(None, int(base * 0.78))
        self.font_lg = pygame.font.Font(None, int(base * 1.6))
        self.clock = pygame.time.Clock()
        self._held = None
        self._last = 0.0

    def poll(self):
        import time
        act = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "back"
            if e.type == pygame.KEYDOWN:
                act = {pygame.K_UP: "up", pygame.K_w: "up",
                       pygame.K_DOWN: "down", pygame.K_s: "down",
                       pygame.K_RETURN: "select", pygame.K_SPACE: "select",
                       pygame.K_ESCAPE: "back", pygame.K_BACKSPACE: "back",
                       pygame.K_PAGEUP: "pageup", pygame.K_PAGEDOWN: "pagedown",
                       pygame.K_LEFT: "pageup", pygame.K_RIGHT: "pagedown",
                       pygame.K_HOME: "home", pygame.K_END: "end"}.get(e.key)
            if e.type == pygame.JOYBUTTONDOWN:
                if e.button == 0:
                    act = "select"
                elif e.button == 1:
                    act = "back"
                elif e.button in (4, 6):
                    act = "pageup"
                elif e.button in (5, 7):
                    act = "pagedown"
            if e.type == pygame.JOYHATMOTION:
                _, y = e.value
                if y == 1:
                    act = "up"
                elif y == -1:
                    act = "down"
        now = time.time()
        ay = 0.0
        for js in self.sticks:
            try:
                if js.get_numaxes() >= 2:
                    ay = ay or js.get_axis(1)
            except Exception:
                pass
        if not act:
            d = "up" if ay < -0.6 else "down" if ay > 0.6 else None
            if d:
                if d != self._held:
                    self._held = d
                    self._last = now
                    act = d
                elif now - self._last > 0.03:
                    self._last = now
                    act = d
            else:
                self._held = None
        return act

    # --- generic list browser ------------------------------------------------
    def browse(self, title, subtitle, rows):
        """rows = list of (label, sublabel_or_None). Returns index or None (back)."""
        sel = 0
        top = int(self.H * 0.19)
        row_h = int(self.H * 0.075)
        visible = max(5, int((self.H * 0.70) / row_h))
        scroll = 0
        n = len(rows)
        while True:
            act = self.poll()
            if act == "up":
                sel = (sel - 1) % n
            elif act == "down":
                sel = (sel + 1) % n
            elif act == "pageup":
                sel = max(0, sel - visible)
            elif act == "pagedown":
                sel = min(n - 1, sel + visible)
            elif act == "home":
                sel = 0
            elif act == "end":
                sel = n - 1
            elif act == "select":
                return sel
            elif act == "back":
                return None
            if sel < scroll:
                scroll = sel
            elif sel >= scroll + visible:
                scroll = sel - visible + 1
            self.screen.fill(BG)
            self.screen.blit(self.font_lg.render(title, True, ACCENT),
                             (int(self.W * 0.06), int(self.H * 0.05)))
            self.screen.blit(self.font.render(subtitle, True, DIM),
                             (int(self.W * 0.06), int(self.H * 0.12)))
            x = int(self.W * 0.06)
            for i in range(scroll, min(n, scroll + visible)):
                y = top + (i - scroll) * row_h
                if i == sel:
                    pygame.draw.rect(self.screen, HILITE,
                                     (x - 12, y - 4, int(self.W * 0.88),
                                      row_h - 8), border_radius=8)
                label, sub = rows[i]
                self.screen.blit(self.font.render(label, True,
                                 FG if i == sel else DIM), (x, y))
                if sub:
                    self.screen.blit(self.font_sm.render(sub, True, DIM),
                                     (x + 16, y + int(row_h * 0.42)))
            # scrollbar
            if n > visible:
                frac = sel / max(1, n - 1)
                bar = int(self.H * 0.70)
                by = top + int(frac * (bar - 24))
                pygame.draw.rect(self.screen, ACCENT,
                                 (int(self.W * 0.95), by, 6, 24),
                                 border_radius=3)
            pygame.display.flip()
            self.clock.tick(30)

    # --- spoiler renderer ----------------------------------------------------
    def show(self, path):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            data = {"meta": {"error": str(e)}}
        lines = build_lines(data)
        top = int(self.H * 0.13)
        line_h = int(self.H * 0.042)
        visible = max(8, int((self.H - top - int(self.H * 0.04)) / line_h))
        off = 0
        maxoff = max(0, len(lines) - visible)
        while True:
            act = self.poll()
            if act == "up":
                off = max(0, off - 1)
            elif act == "down":
                off = min(maxoff, off + 1)
            elif act == "pageup":
                off = max(0, off - visible)
            elif act == "pagedown":
                off = min(maxoff, off + visible)
            elif act == "home":
                off = 0
            elif act == "end":
                off = maxoff
            elif act == "back":
                return
            self.screen.fill(BG)
            hdr = self.font_hd.render(seed_label(path), True, ACCENT)
            self.screen.blit(hdr, (int(self.W * 0.05), int(self.H * 0.04)))
            self.screen.blit(self.font.render(
                "Up/Down scroll  \u2022  L/R page  \u2022  B back", True, DIM),
                (int(self.W * 0.05), int(self.H * 0.085)))
            x = int(self.W * 0.05)
            x2 = int(self.W * 0.42)
            for idx in range(off, min(len(lines), off + visible)):
                text, style = lines[idx]
                y = top + (idx - off) * line_h
                if style == "pair":
                    loc, item = text
                    self.screen.blit(self.font.render(str(loc), True, FG),
                                     (x, y))
                    self.screen.blit(self.font.render(str(item), True, ITEMCOL),
                                     (x2, y))
                elif style == "title":
                    self.screen.blit(self.font_hd.render(text, True, ACCENT),
                                     (x, y))
                elif style == "head":
                    self.screen.blit(self.font.render(text, True, HEAD), (x, y))
                elif style == "dim":
                    self.screen.blit(self.font.render(text, True, DIM), (x, y))
                elif style == "blank":
                    pass
                else:
                    self.screen.blit(self.font.render(str(text), True, FG),
                                     (x, y))
            # scrollbar
            if maxoff > 0:
                frac = off / maxoff
                bar_area = self.H - top - int(self.H * 0.05)
                by = top + int(frac * (bar_area - 24))
                pygame.draw.rect(self.screen, ACCENT,
                                 (int(self.W * 0.965), by, 6, 24),
                                 border_radius=3)
            pygame.display.flip()
            self.clock.tick(30)

    def message(self, text):
        self.screen.fill(BG)
        m = self.font_hd.render(text, True, FG)
        r = m.get_rect(center=(self.W // 2, self.H // 2))
        self.screen.blit(m, r)
        pygame.display.flip()
        import time
        end = time.time() + 3.0
        while time.time() < end:
            for e in pygame.event.get():
                if e.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.QUIT):
                    return
            self.clock.tick(20)

    def run(self):
        import time
        while True:
            # all spoilers live in the single SEEDS/ folder now; group by the mode
            # parsed from the filename (alttpr_<glitches>_<state>_<goal>_<code>_...)
            paths = glob.glob(os.path.join(ROMROOT, "SEEDS", "*.spoiler.json"))
            if not paths:
                self.message("No spoiler logs yet. Generate a seed with "
                             "Spoiler Log = on.")
                return 0
            folders = {}
            for p in paths:
                parts = os.path.basename(p).split("_")
                mode = parts[2] if len(parts) > 2 else "seeds"  # <state> token
                folders.setdefault(mode, []).append(p)
            names = sorted(folders.keys())

            # Level 1: choose a folder (skip straight to seeds if only one folder)
            if len(names) == 1:
                fsel = 0
            else:
                rows = []
                for nm in names:
                    cnt = len(folders[nm])
                    rows.append((nm.replace("_", " ").title(),
                                 "%d spoiler%s" % (cnt, "" if cnt == 1 else "s")))
                idx = self.browse("ALTTPR  \u2014  Spoiler Logs",
                                  "Pick a folder  \u2022  A open  \u2022  B exit",
                                  rows)
                if idx is None:
                    return 0
                fsel = idx

            # Level 2: choose a seed within the folder
            while True:
                folder = names[fsel]
                seeds = sorted(folders[folder],
                               key=lambda p: os.path.getmtime(p), reverse=True)
                srows = []
                for p in seeds:
                    lbl = seed_label(p)
                    ts = time.strftime("%b %d  %H:%M",
                                       time.localtime(os.path.getmtime(p)))
                    srows.append((lbl, ts))
                sub = ("%s  \u2022  A view  \u2022  B back"
                       % folder.replace("_", " ").title())
                idx = self.browse("ALTTPR  \u2014  Spoiler Logs", sub, srows)
                if idx is None:
                    if len(names) == 1:
                        return 0   # nothing to go back to
                    break          # back to folder list
                self.show(seeds[idx])


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
        v = Viewer()
    except Exception as e:
        sys.stderr.write("spoiler viewer init failed: %s\n" % e)
        _teardown()
        os._exit(2)
    try:
        rc = v.run()
    except Exception as e:
        sys.stderr.write("spoiler viewer error: %s\n" % e)
        rc = 2
    _teardown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    main()
