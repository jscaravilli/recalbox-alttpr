#!/usr/bin/env python3
"""ALTTPR tracker web server for the Pi.

Serves the browser autotracker (static files) AND a small /seedinfo JSON endpoint
so the tracker page can show the running seed's friendly nickname. /seedinfo asks
RetroArch (UDP GET_STATUS on 127.0.0.1:55355) what content is loaded and parses
the nickname/goal out of the seed filename:

    alttpr_<glitch>_<state>_<goal>_<Nick>_<MMDDYYYY>.sfc

No spoiler log is used or needed — the autotracker reads live game memory.

Usage: alttpr-tracker-serve.py [--dir <trackerdir>] [--port 8080] [--ra-port 55355]
"""
import argparse
import json
import os
import re
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RA_HOST = "127.0.0.1"
RA_PORT = 55355

# ROM offsets for the seed's crystal requirements (0-7 each). Verified against
# real seeds: these are the same bytes the Custom Seed menu writes.
OFF_GT_CRYSTALS = 0x18019A     # crystals required to enter Ganon's Tower
OFF_GANON_CRYSTALS = 0x1801A6  # crystals required to make Ganon vulnerable
OFF_TIMER_STYLE = 0x180190      # 2 = Stopwatch
OFF_SEED_HASH = 0x180215        # five Hash Alphabet item IDs
WRAM_NMI_FRAMES = 0xF43E
WRAM_CHALLENGE_TIMER = 0xF454

# Where generated seeds live; the running content name (no extension) is resolved
# to a .sfc here so we can read its crystal bytes.
SEEDS_DIRS = [
    "/recalbox/share/roms/alttpr/SEEDS",
    "/recalbox/share/roms/alttpr",
]

_DATE_RE = re.compile(r"^\d{8}$")


def read_crystals(content):
    """Locate the seed ROM for `content` and read its GT/Ganon crystal reqs.
    Returns (gt, ganon) or (None, None) if the ROM can't be found/read."""
    if not content:
        return (None, None)
    fname = content if content.lower().endswith((".sfc", ".smc")) else content + ".sfc"
    for d in SEEDS_DIRS:
        path = os.path.join(d, fname)
        if os.path.isfile(path):
            try:
                with open(path, "rb") as f:
                    f.seek(OFF_GT_CRYSTALS); gt = f.read(1)[0]
                    f.seek(OFF_GANON_CRYSTALS); ga = f.read(1)[0]
                # sanity: valid seeds use 0-7
                if 0 <= gt <= 7 and 0 <= ga <= 7:
                    return (gt, ga)
            except (OSError, IndexError):
                return (None, None)
    return (None, None)


def read_seed_hash(content):
    """Read the five file-select Hash Alphabet item IDs from the seed ROM."""
    if not content:
        return None
    fname = content if content.lower().endswith((".sfc", ".smc")) else content + ".sfc"
    for directory in SEEDS_DIRS:
        path = os.path.join(directory, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as rom:
                rom.seek(OFF_SEED_HASH)
                values = list(rom.read(5))
            if len(values) == 5 and all(value <= 0x1F for value in values):
                return values
        except OSError:
            return None
    return None


def ra_status():
    """Return the RetroArch GET_STATUS string, or None if nothing is running."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1.0)
    try:
        s.sendto(b"GET_STATUS", (RA_HOST, RA_PORT))
        data, _ = s.recvfrom(4096)
        return data.decode("utf-8", "replace").strip()
    except socket.timeout:
        return None
    except OSError:
        return None
    finally:
        s.close()


def ra_read_core_ram(offset, size):
    """Read bytes from RetroArch core RAM, returning None when unavailable."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1.0)
    try:
        command = "READ_CORE_RAM {:x} {}\n".format(offset, size).encode()
        s.sendto(command, (RA_HOST, RA_PORT))
        data, _ = s.recvfrom(4096)
        parts = data.decode("ascii", "strict").strip().split()
        if len(parts) != size + 2 or parts[:2] != ["READ_CORE_RAM", format(offset, "x")]:
            return None
        return bytes(int(value, 16) for value in parts[2:])
    except (OSError, UnicodeError, ValueError):
        return None
    finally:
        s.close()


def read_stopwatch_seconds(content):
    """Return the same elapsed seconds shown by the in-game Stopwatch."""
    if not content:
        return None
    fname = content if content.lower().endswith((".sfc", ".smc")) else content + ".sfc"
    for directory in SEEDS_DIRS:
        path = os.path.join(directory, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as rom:
                rom.seek(OFF_TIMER_STYLE)
                if rom.read(1) != b"\x02":
                    return None
        except OSError:
            return None
        timer_data = ra_read_core_ram(
            WRAM_NMI_FRAMES,
            WRAM_CHALLENGE_TIMER + 4 - WRAM_NMI_FRAMES,
        )
        if timer_data is None:
            return None
        nmi_frames = int.from_bytes(timer_data[:4], "little")
        challenge_offset = WRAM_CHALLENGE_TIMER - WRAM_NMI_FRAMES
        challenge_timer = int.from_bytes(
            timer_data[challenge_offset:challenge_offset + 4],
            "little",
        )
        return ((nmi_frames - challenge_timer) & 0xFFFFFFFF) // 60
    return None


def parse_seed(base):
    """Parse an ALTTPR seed basename into nickname/state/goal/date."""
    base = os.path.basename(base)
    if base.endswith(".sfc") or base.endswith(".smc"):
        base = base[:-4]
    toks = base.split("_")
    if len(toks) < 4 or toks[0] != "alttpr":
        return None
    date = None
    if _DATE_RE.match(toks[-1]):
        date = toks[-1]
        toks = toks[:-1]
    if len(toks) < 3:
        return None
    # Python-DR wrapper format: alttpr_<mode>_<Nickname>_<MMDDYYYY>
    if len(toks) == 3:
        return {
            "glitch": "",
            "state": toks[1],
            "goal": "",
            "nickname": toks[2],
            "date": date,
        }
    # Legacy PHP format:
    # alttpr_<glitch>_<state>_<goal...>_<Nickname>_<MMDDYYYY>
    info = {
        "glitch": toks[1],
        "state": toks[2],
        "goal": " ".join(toks[3:-1]) if len(toks) > 4 else toks[3],
        "nickname": toks[-1],
        "date": date,
    }
    return info


def read_spoiler_metadata(content):
    """Read settings and dungeon prizes from the generated DR text spoiler."""
    base = os.path.basename(content)
    if base.lower().endswith((".sfc", ".smc")):
        base = base[:-4]
    dungeon_names = {
        "Eastern Palace": "ep",
        "Desert Palace": "dp",
        "Tower of Hera": "toh",
        "Palace of Darkness": "pod",
        "Thieves Town": "tt",
        "Skull Woods": "sw",
        "Swamp Palace": "sp",
        "Ice Palace": "ip",
        "Misery Mire": "mm",
        "Turtle Rock": "tr",
    }
    for directory in SEEDS_DIRS:
        path = os.path.join(directory, base + ".spoiler.txt")
        if not os.path.isfile(path):
            continue
        result = {}
        prizes = {}
        try:
            for line in open(path, encoding="utf-8", errors="replace"):
                match = re.match(r"^(Mode|Logic|Goal):\s+(.+?)\s*$", line)
                if match:
                    result[match.group(1).lower()] = match.group(2)
                    continue
                match = re.match(r"^([^:]+):\s+(Crystal \d+|(?:Green|Red|Blue) Pendant)\s*$", line)
                if not match or match.group(1) not in dungeon_names:
                    continue
                prize = match.group(2)
                if prize in ("Crystal 5", "Crystal 6"):
                    prize = "redcrystal"
                elif prize.startswith("Crystal "):
                    prize = "crystal"
                elif prize == "Green Pendant":
                    prize = "greenpendant"
                else:
                    prize = "pendant"
                prizes[dungeon_names[match.group(1)]] = prize
        except OSError:
            pass
        if prizes:
            result["dungeon_prizes"] = prizes
        return result
    return {}


def seedinfo():
    st = ra_status()
    if not st or not st.startswith("GET_STATUS"):
        return {"running": False}
    parts = st.split(" ", 2)
    if len(parts) < 3 or parts[1] not in ("PLAYING", "PAUSED"):
        return {"running": False}
    # "GET_STATUS PLAYING <core>,<contentname>,crc32=..."
    fields = parts[2].split(",")
    core = fields[0] if fields else ""
    content = fields[1] if len(fields) > 1 else ""
    info = parse_seed(content) or {}
    spoiler = read_spoiler_metadata(content)
    if spoiler:
        info["state"] = spoiler.get("mode", info.get("state", ""))
        info["glitch"] = spoiler.get("logic", info.get("glitch", ""))
        info["goal"] = spoiler.get("goal", info.get("goal", ""))
        if "dungeon_prizes" in spoiler:
            info["dungeon_prizes"] = spoiler["dungeon_prizes"]
    info["running"] = True
    info["core"] = core
    info["content"] = content
    gt, ga = read_crystals(content)
    if gt is not None:
        info["gt_crystals"] = gt
        info["ganon_crystals"] = ga
    seed_hash = read_seed_hash(content)
    if seed_hash is not None:
        info["seed_hash"] = seed_hash
    stopwatch_seconds = read_stopwatch_seconds(content)
    if stopwatch_seconds is not None:
        info["stopwatch_seconds"] = stopwatch_seconds
    return info


class Handler(SimpleHTTPRequestHandler):
    # `directory` is bound via functools.partial in main()
    def do_GET(self):
        if self.path.split("?")[0] == "/seedinfo":
            body = json.dumps(seedinfo()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass  # quiet


def main():
    global RA_PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--ra-port", type=int, default=55355)
    args = ap.parse_args()
    RA_PORT = args.ra_port

    import functools
    handler = functools.partial(Handler, directory=args.dir)
    httpd = ThreadingHTTPServer((args.bind, args.port), handler)
    print("tracker: http://%s:%d  (dir=%s)" % (args.bind, args.port, args.dir))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
