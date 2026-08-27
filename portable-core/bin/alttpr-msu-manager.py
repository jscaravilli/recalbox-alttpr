#!/usr/bin/env python3
"""Controller-driven manager for user-imported MSU-1 music packs."""
import json
import os
import subprocess
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "KMSDRM"
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402


ENGINE = "/recalbox/share/alttpr"
IMPORTER = ENGINE + "/bin/alttpr-msu-import.py"
DROP_DIR = "/recalbox/share/import/msu"
USER_METADATA = ENGINE + "/msu/user-packs.json"

BG = (24, 20, 37)
PANEL = (36, 30, 56)
FG = (235, 232, 245)
DIM = (150, 145, 170)
ACCENT = (240, 190, 70)
GREEN = (120, 210, 130)
RED = (220, 110, 110)
HILITE = (58, 48, 88)


def pending():
    try:
        out = subprocess.check_output(
            ["python3", IMPORTER, "--scan"], timeout=20)
        return [line for line in out.decode("utf-8", "replace").splitlines()
                if line.strip()]
    except Exception:
        return []


def user_packs():
    try:
        return json.load(open(USER_METADATA, encoding="utf-8"))
    except Exception:
        return []


class Manager:
    def __init__(self):
        pygame.init()
        pygame.display.init()
        pygame.font.init()
        pygame.joystick.init()
        self.sticks = []
        for index in range(pygame.joystick.get_count()):
            try:
                stick = pygame.joystick.Joystick(index)
                stick.init()
                self.sticks.append(stick)
            except Exception:
                pass
        info = pygame.display.Info()
        width = info.current_w if info.current_w > 0 else 1280
        height = info.current_h if info.current_h > 0 else 720
        self.screen = pygame.display.set_mode(
            (width, height), pygame.FULLSCREEN)
        self.W, self.H = self.screen.get_size()
        pygame.mouse.set_visible(False)
        base = max(16, int(self.H / 26))
        self.font = pygame.font.Font(None, base)
        self.small = pygame.font.Font(None, int(base * 0.8))
        self.large = pygame.font.Font(None, int(base * 1.5))
        self.clock = pygame.time.Clock()
        self.sel = 0
        self.confirm_slug = None
        self.status = ""
        self.status_color = FG
        self.reload()

    def reload(self):
        self.incoming = pending()
        self.packs = user_packs()
        self.rows = [("import", None)] + [
            ("pack", pack) for pack in self.packs
        ] + [("refresh", None), ("exit", None)]
        self.sel = min(self.sel, len(self.rows) - 1)

    def poll(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    return "up"
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    return "down"
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return "select"
                if event.key == pygame.K_ESCAPE:
                    return "exit"
            if event.type == pygame.JOYBUTTONDOWN:
                if event.button in (0, 1):
                    return "select"
            if event.type == pygame.JOYHATMOTION:
                if event.value[1] == 1:
                    return "up"
                if event.value[1] == -1:
                    return "down"
            if event.type == pygame.JOYAXISMOTION and event.axis == 1:
                if event.value < -0.7:
                    return "up"
                if event.value > 0.7:
                    return "down"
        return None

    def message(self, text, color=FG, seconds=2):
        self.status = text
        self.status_color = color
        self.draw()
        time.sleep(seconds)

    def import_all(self):
        if not self.incoming:
            self.message("No packs found in SHARE/import/msu.", DIM)
            return
        self.message("Validating and importing %d pack%s..." % (
            len(self.incoming), "" if len(self.incoming) == 1 else "s"),
            ACCENT, 0.4)
        proc = subprocess.run(
            ["python3", IMPORTER, "--import-all"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=1800)
        lines = proc.stdout.decode("utf-8", "replace").splitlines()
        imported = sum(line.startswith("IMPORTED:") for line in lines)
        failed = sum(line.startswith("FAILED:") for line in lines)
        self.reload()
        if failed:
            failure = next(
                (line.rsplit(":", 1)[-1] for line in lines
                 if line.startswith("FAILED:")), "validation failed")
            self.message("Imported %d; failed: %s" %
                         (imported, failure[:90]), RED, 4)
        else:
            self.message("Imported %d pack%s." % (
                imported, "" if imported == 1 else "s"), GREEN)

    def delete_pack(self, pack):
        slug = pack["slug"]
        if self.confirm_slug != slug:
            self.confirm_slug = slug
            self.message("Press A/B again to delete %s." % pack["name"],
                         RED, 1.5)
            return
        proc = subprocess.run(
            ["python3", IMPORTER, "--delete", slug],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        self.confirm_slug = None
        if proc.returncode:
            self.message("Delete failed: " +
                         proc.stdout.decode("utf-8", "replace")[-100:], RED)
        else:
            self.reload()
            self.message("Deleted user pack: " + pack["name"], GREEN)

    def help_text(self):
        kind, value = self.rows[self.sel]
        if kind == "import":
            return (
                "IMPORT FROM NETWORK DROP FOLDER\n\n"
                "%d candidate%s ready.\n\n"
                "From another computer, copy an extracted pack, ZIP, 7Z, or "
                "RAR into:\n\nSHARE/import/msu\n\n"
                "A pack needs numbered PCM files such as music-1.pcm. "
                "Successful inputs move to the processed subfolder."
                % (len(self.incoming),
                   "" if len(self.incoming) == 1 else "s"))
        if kind == "pack":
            return (
                "USER-IMPORTED PACK\n\n%s\n\n"
                "Press A/B twice to delete this pack. Curated packs cannot "
                "be deleted from this screen." % value["name"])
        if kind == "refresh":
            return ("REFRESH\n\nRescan the network drop folder and reload "
                    "the installed user-pack list.")
        return "EXIT\n\nReturn to the ALTTPR game list."

    def wrap(self, text, font, width):
        lines = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split():
                trial = (current + " " + word).strip()
                if current and font.size(trial)[0] > width:
                    lines.append(current)
                    current = word
                else:
                    current = trial
            lines.append(current)
        return lines

    def draw(self):
        self.screen.fill(BG)
        x = int(self.W * 0.06)
        self.screen.blit(self.large.render(
            "ALTTPR  —  Manage MSU Music", True, ACCENT),
            (x, int(self.H * 0.05)))
        self.screen.blit(self.small.render(
            "D-Pad move  •  A/B select  •  deleting requires two presses",
            True, DIM), (x, int(self.H * 0.12)))

        row_h = int(self.H * 0.07)
        top = int(self.H * 0.21)
        visible = max(6, int(self.H * 0.65 / row_h))
        start = max(0, min(self.sel - visible + 1,
                           len(self.rows) - visible))
        labels = []
        for kind, value in self.rows:
            if kind == "import":
                labels.append("Import Drop Folder  (%d)" % len(self.incoming))
            elif kind == "pack":
                labels.append(value["name"])
            elif kind == "refresh":
                labels.append("Refresh")
            else:
                labels.append("Exit")
        for index in range(start, min(len(self.rows), start + visible)):
            y = top + (index - start) * row_h
            if index == self.sel:
                pygame.draw.rect(
                    self.screen, HILITE,
                    (x - 12, y - 5, int(self.W * 0.47), row_h - 5),
                    border_radius=8)
            label = labels[index]
            while self.font.size(label)[0] > int(self.W * 0.44):
                label = label[:-2] + "…"
            color = (RED if self.rows[index][0] == "pack" and
                     self.confirm_slug == self.rows[index][1]["slug"]
                     else ACCENT if index == self.sel else DIM)
            self.screen.blit(self.font.render(label, True, color), (x, y))

        px, py = int(self.W * 0.56), int(self.H * 0.20)
        pw, ph = int(self.W * 0.38), int(self.H * 0.68)
        pygame.draw.rect(self.screen, PANEL, (px, py, pw, ph),
                         border_radius=10)
        y = py + int(self.H * 0.025)
        for line in self.wrap(self.help_text(), self.small,
                              pw - int(self.W * 0.04)):
            if line:
                self.screen.blit(self.small.render(line, True, FG),
                                 (px + int(self.W * 0.02), y))
            y += int(self.small.get_height() * 1.2)
        if self.status:
            self.screen.blit(self.small.render(
                self.status, True, self.status_color),
                (x, int(self.H * 0.93)))
        pygame.display.flip()

    def run(self):
        last_move = 0
        while True:
            action = self.poll()
            now = time.time()
            if action in ("up", "down") and now - last_move > 0.15:
                self.sel = (self.sel + (-1 if action == "up" else 1)) % \
                           len(self.rows)
                self.confirm_slug = None
                self.status = ""
                last_move = now
            elif action == "exit":
                return 0
            elif action == "select":
                kind, value = self.rows[self.sel]
                if kind == "import":
                    self.import_all()
                elif kind == "pack":
                    self.delete_pack(value)
                elif kind == "refresh":
                    self.reload()
                    self.message("Drop folder refreshed.", GREEN, 1)
                else:
                    return 0
            self.draw()
            self.clock.tick(30)


def teardown():
    for function in (pygame.display.quit, pygame.joystick.quit, pygame.quit):
        try:
            function()
        except Exception:
            pass


def main():
    try:
        return Manager().run()
    except Exception as error:
        print("MSU manager error: %s" % error, file=sys.stderr)
        return 2
    finally:
        teardown()


if __name__ == "__main__":
    raise SystemExit(main())
