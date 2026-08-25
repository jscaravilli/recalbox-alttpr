#!/usr/bin/env python3
"""Confirmation dialog for deleting old ALTTPR seeds (pygame / KMSDRM).

Launched by the configgen alttpr generator for the "Clean Old Seeds" tile. Shows
how many seeds are older than the cutoff and a preview list, then requires you to
land on Delete or Cancel and press A or B to execute. On confirm it runs
alttpr-cleanup.sh and drops /tmp/alttpr_refresh so ES refreshes the gamelists
when it resumes.

Controls (shared with the Custom Seed menu):
  Up/Down     move between the age selector, Delete, and Cancel
  Left/Right  change the age selector's value
  L/R         jump the value by 10
  A or B      execute the focused item (Delete / Cancel)
  Esc         cancel (keyboard only)
"""
import os
import sys
import subprocess

os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

CLEANUP = "/recalbox/share/alttpr/bin/alttpr-cleanup.sh"
REFRESH_FLAG = "/tmp/alttpr_refresh"

# Age presets: (label, cleanup-arg). Default focus starts on "2 days".
AGE_OPTIONS = [
    ("All seeds", "all"),
    ("Older than 1 day", "1"),
    ("Older than 2 days", "2"),
    ("Older than 1 week", "7"),
]
AGE_DEFAULT = 2  # index of "Older than 2 days"

BG = (24, 20, 37)
FG = (235, 232, 245)
DIM = (150, 145, 170)
ACCENT = (240, 190, 70)
RED = (220, 110, 110)
GREEN = (120, 210, 130)
HILITE = (58, 48, 88)


def candidates(hours):
    """Dry-run the cleanup to get the list of seeds that would be deleted."""
    out = ""
    try:
        out = subprocess.check_output(
            ["/bin/bash", CLEANUP, str(hours), "--dry"],
            stderr=subprocess.STDOUT, timeout=60).decode("utf-8", "replace")
    except Exception:
        pass
    names = []
    for line in out.splitlines():
        if line.startswith("CANDIDATE:"):
            names.append(os.path.basename(line[10:].strip()))
    return names


class Dialog:
    def __init__(self):
        pygame.init()
        try:
            pygame.display.init(); pygame.font.init()
        except Exception:
            pass
        pygame.joystick.init()
        self.sticks = []
        for i in range(pygame.joystick.get_count()):
            try:
                js = pygame.joystick.Joystick(i); js.init(); self.sticks.append(js)
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
        base = max(16, int(self.H / 26))
        self.font = pygame.font.Font(None, base)
        self.font_sm = pygame.font.Font(None, int(base * 0.8))
        self.font_lg = pygame.font.Font(None, int(base * 1.5))
        self.clock = pygame.time.Clock()
        self.scroll = 0

    def poll(self):
        """Return one of: up, down, left, right, activate, cancel, None.
        'activate' fires on ANY joypad button (controller-agnostic) or Enter/Space.
        'cancel' is a hard escape (keyboard Esc only) so a stray button never
        cancels unexpectedly — on a controller you navigate to Cancel + activate.
        """
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "cancel"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return "activate"
                if e.key in (pygame.K_ESCAPE,):
                    return "cancel"
                if e.key in (pygame.K_UP, pygame.K_w):
                    return "up"
                if e.key in (pygame.K_DOWN, pygame.K_s):
                    return "down"
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    return "left"
                if e.key in (pygame.K_RIGHT, pygame.K_d):
                    return "right"
                if e.key in (pygame.K_LEFTBRACKET,):
                    return "fastleft"
                if e.key in (pygame.K_RIGHTBRACKET,):
                    return "fastright"
            if e.type == pygame.JOYBUTTONDOWN:
                # Unified control model (shared with the Custom Seed menu):
                #   L/R shoulders -> jump the focused value by 10 (horizontal)
                #   A or B (0/1)  -> execute the focused item (Delete / Cancel)
                # Other buttons are ignored so a stray press can't delete.
                if e.button in (4, 6):
                    return "fastleft"
                if e.button in (5, 7):
                    return "fastright"
                if e.button in (0, 1):
                    return "activate"
                # any other button: ignore
            if e.type == pygame.JOYHATMOTION:
                x, y = e.value
                if y == 1:
                    return "up"
                if y == -1:
                    return "down"
                if x == -1:
                    return "left"
                if x == 1:
                    return "right"
            if e.type == pygame.JOYAXISMOTION:
                if e.axis in (0,) and abs(e.value) > 0.6:
                    return "right" if e.value > 0 else "left"
                if e.axis in (1,) and abs(e.value) > 0.6:
                    return "down" if e.value > 0 else "up"
        return None

    def draw(self, age_idx, names, focus, visible):
        """focus: 0=age selector, 1=Delete, 2=Cancel"""
        self.screen.fill(BG)
        self.screen.blit(self.font_lg.render("Clean Old Seeds", True, ACCENT),
                         (int(self.W * 0.06), int(self.H * 0.05)))
        self.screen.blit(self.font_sm.render(
            "Up/Down move  \u2022  Left/Right change  \u2022  A/B = select",
            True, DIM), (int(self.W * 0.06), int(self.H * 0.12)))

        # --- age selector row ---
        ay = int(self.H * 0.22)
        x = int(self.W * 0.06)
        if focus == 0:
            pygame.draw.rect(self.screen, HILITE,
                             (x - 12, ay - 6, int(self.W * 0.88), int(self.H * 0.075)),
                             border_radius=8)
        self.screen.blit(self.font.render("Delete:", True, FG), (x, ay))
        label = AGE_OPTIONS[age_idx][0]
        arrow = ("\u2039 " + label + " \u203a") if focus == 0 else label
        self.screen.blit(self.font.render(arrow, True, ACCENT),
                         (int(self.W * 0.30), ay))

        # --- count + note ---
        cy = int(self.H * 0.34)
        n = len(names)
        cmsg = "%d seed%s will be deleted" % (n, "" if n == 1 else "s")
        self.screen.blit(self.font.render(cmsg, True,
                         RED if n else DIM), (x, cy))
        self.screen.blit(self.font_sm.render(
            "Game saves are kept. Launcher tiles are kept.", True, DIM),
            (x, cy + int(self.H * 0.06)))

        # --- preview list ---
        top = int(self.H * 0.48)
        row_h = int(self.H * 0.045)
        lx = int(self.W * 0.08)
        for i in range(self.scroll, min(n, self.scroll + visible)):
            y = top + (i - self.scroll) * row_h
            self.screen.blit(self.font_sm.render(names[i], True, DIM), (lx, y))
        if n > self.scroll + visible:
            self.screen.blit(self.font_sm.render(
                "... %d more" % (n - self.scroll - visible), True, DIM),
                (lx, top + visible * row_h))

        # --- buttons (navigable, stacked vertically: Delete above Cancel) ---
        bx = int(self.W * 0.06)
        bw = int(self.W * 0.24)
        bh = int(self.H * 0.075)
        for idx, (text, col, by) in enumerate([
                ("Delete", RED,   int(self.H * 0.82)),
                ("Cancel", GREEN, int(self.H * 0.90))], start=1):
            if focus == idx:
                pygame.draw.rect(self.screen, HILITE,
                                 (bx - 14, by - 8, bw, bh), border_radius=8)
                pygame.draw.rect(self.screen, col,
                                 (bx - 14, by - 8, bw, bh), width=3, border_radius=8)
            self.screen.blit(self.font.render(text, True, col), (bx, by))
        pygame.display.flip()

    def message(self, text, color):
        self.screen.fill(BG)
        m = self.font.render(text, True, color)
        self.screen.blit(m, m.get_rect(center=(self.W // 2, self.H // 2)))
        pygame.display.flip()

    def run(self):
        age_idx = AGE_DEFAULT
        names = candidates(AGE_OPTIONS[age_idx][1])
        focus = 2  # default on Cancel (safe)
        row_h = int(self.H * 0.045)
        visible = max(3, int((self.H * 0.28) / row_h))   # leave room for the two stacked buttons
        import time
        while True:
            act = self.poll()
            if act == "cancel":
                return 2
            elif act == "up":
                focus = max(0, focus - 1); self.scroll = 0
            elif act == "down":
                focus = min(2, focus + 1); self.scroll = 0
            elif act in ("left", "right") and focus == 0:
                age_idx = (age_idx + (1 if act == "right" else -1)) % len(AGE_OPTIONS)
                names = candidates(AGE_OPTIONS[age_idx][1])
                self.scroll = 0
            elif act in ("fastleft", "fastright") and focus == 0:
                # L/R shoulders jump the value by 10 (wraps within the short list)
                age_idx = (age_idx + (10 if act == "fastright" else -10)) % len(AGE_OPTIONS)
                names = candidates(AGE_OPTIONS[age_idx][1])
                self.scroll = 0
            elif act == "activate":
                if focus == 2:                 # Cancel
                    return 2
                if focus == 1:                 # Delete
                    if not names:
                        self.message("Nothing to delete for that range.", FG)
                        time.sleep(1.5)
                    else:
                        self.message("Deleting %d seed%s..."
                                     % (len(names), "" if len(names) == 1 else "s"),
                                     ACCENT)
                        try:
                            subprocess.call(
                                ["/bin/bash", CLEANUP, AGE_OPTIONS[age_idx][1]],
                                timeout=180)
                        except Exception:
                            pass
                        try:
                            open(REFRESH_FLAG, "w").close()  # ES refresh on resume
                        except Exception:
                            pass
                        self.message("Deleted %d seed%s."
                                     % (len(names), "" if len(names) == 1 else "s"),
                                     GREEN)
                        time.sleep(2)
                        return 0
                # focus == 0 (age selector) activate -> no-op
            self.draw(age_idx, names, focus, visible)
            self.clock.tick(30)


def _teardown():
    for fn in (pygame.display.quit, pygame.joystick.quit, pygame.quit):
        try:
            fn()
        except Exception:
            pass


def main():
    rc = 0
    try:
        d = Dialog()
    except Exception as e:
        sys.stderr.write("cleanup dialog init failed: %s\n" % e)
        _teardown(); os._exit(2)
    try:
        rc = d.run()
    except Exception as e:
        sys.stderr.write("cleanup dialog error: %s\n" % e)
        rc = 2
    _teardown()
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    main()
