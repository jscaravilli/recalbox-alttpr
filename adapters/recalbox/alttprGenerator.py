#!/usr/bin/env python
# Recalbox 10 configgen generator for the ALTTPR seed generator (Python Door
# Randomizer engine). A ".alttpr" ROM is a tiny text file whose first line is the
# preset/mode name. Selecting it runs alttpr-generate.sh to make a fresh seed,
# then re-launches that seed as a NORMAL "snes" game -- reusing the exact original
# EmulationStation invocation (controller/resolution args intact), only swapping
# -system/-rom/-emulator/-core. Launching under the real "snes" system is required
# so the SNES core plays it correctly and SRAM lands in saves/snes.
from configgen.Command import Command
import os, sys, subprocess


class AlttprGenerator:

    ENGINE = "/recalbox/share/alttpr"
    GENERATE = "/recalbox/share/alttpr/bin/alttpr-generate.sh"
    MENU = "/recalbox/share/alttpr/bin/alttpr-menu.py"
    SPOILER = "/recalbox/share/alttpr/bin/alttpr-spoiler.py"
    CLEANUP = "/recalbox/share/alttpr/bin/alttpr-cleanup.py"
    PRACTICE = "/recalbox/share/alttpr/practice/Practice.sfc"
    SEEDOUT = "/tmp/alttpr_seed"
    CORE = "snes9x"

    def _run_pygame(self, script):
        env = dict(os.environ)
        env["SDL_VIDEODRIVER"] = "KMSDRM"
        env.setdefault("SDL_AUDIODRIVER", "dummy")
        env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        try:
            subprocess.call(["python3", script], env=env)
        except Exception:
            pass

    def _refresh_es(self):
        try:
            os.remove("/tmp/alttpr_refresh")
        except OSError:
            pass
        try:
            subprocess.Popen(
                ["/bin/sh", "-c",
                 "sleep 2; /etc/init.d/S31emulationstation restart >/dev/null 2>&1"],
                start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def generate(self, system, playersControllers, recalboxOptions, args):
        rom = args.rom
        seed = ""

        low = rom.lower()
        if low.endswith(".sfc") or low.endswith(".smc"):
            # a real seed ROM selected directly: just play it under snes
            seed = rom
        else:
            mode = "open"
            try:
                with open(rom, "r") as f:
                    for line in f:
                        s = line.strip()
                        if s and not s.startswith("#"):
                            mode = s
                            break
            except Exception:
                pass

            if mode == "spoiler":
                self._run_pygame(self.SPOILER)
                return Command(videomode=system.VideoMode, array=["/bin/true"])
            elif mode == "cleanup":
                self._run_pygame(self.CLEANUP)
                if os.path.exists("/tmp/alttpr_refresh"):
                    self._refresh_es()
                return Command(videomode=system.VideoMode, array=["/bin/true"])
            elif mode == "practice":
                if os.path.exists(self.PRACTICE):
                    seed = self.PRACTICE
                else:
                    return Command(videomode=system.VideoMode, array=["/bin/true"])
            elif mode == "custom":
                try:
                    os.remove(self.SEEDOUT)
                except OSError:
                    pass
                self._run_pygame(self.MENU)
                try:
                    if os.path.exists(self.SEEDOUT):
                        with open(self.SEEDOUT) as f:
                            seed = f.read().strip()
                except Exception:
                    seed = ""
            else:
                try:
                    out = subprocess.check_output(
                        ["/bin/bash", self.GENERATE, mode],
                        stderr=subprocess.STDOUT, timeout=360).decode("utf-8", "replace")
                    for line in out.splitlines():
                        if line.startswith("SEED:"):
                            seed = line[5:].strip()
                except Exception:
                    seed = ""

        if not seed or not os.path.exists(seed):
            return Command(videomode=system.VideoMode, array=["/bin/true"])

        core = self.CORE

        # Rebuild the original ES argv, swapping to the real snes system + seed.
        argv = list(sys.argv[1:])
        out_args = []
        i = 0
        while i < len(argv):
            a = argv[i]
            if a == "-system":
                out_args += ["-system", "snes"]; i += 2; continue
            if a == "-rom":
                out_args += ["-rom", seed]; i += 2; continue
            if a == "-emulator":
                out_args += ["-emulator", "libretro"]; i += 2; continue
            if a == "-core":
                out_args += ["-core", core]; i += 2; continue
            out_args.append(a); i += 1

        def ensure(flag, val):
            if flag not in out_args:
                out_args.extend([flag, val])
        ensure("-system", "snes"); ensure("-rom", seed)
        ensure("-emulator", "libretro"); ensure("-core", core)

        cmd = ["python", "/usr/bin/emulatorlauncher.pyc"] + out_args
        return Command(videomode=system.VideoMode, array=cmd)
