#!/usr/bin/env python3
"""usb2snes <-> RetroArch bridge for ALTTPR web autotrackers (e.g. hutchch).

Web trackers speak the QUsb2Snes/SNI WebSocket protocol (DeviceList / Attach /
Name / GetAddress) on TCP :23074. SNI's RetroArch driver uses READ_CORE_MEMORY
(SNES A-bus) which the snes9x libretro core does NOT support ("no memory map
defined"). snes9x DOES support READ_CORE_RAM (WRAM by offset), which is all the
ALTTPR trackers need (they only read WRAM $7EF000 region + game mode $7E0010).

This bridge implements a minimal usb2snes WebSocket server (dependency-free,
hand-rolled RFC6455) and translates each GetAddress into RetroArch's UDP
READ_CORE_RAM on :55355, so the stock snes9x core works with no core change.

    usb2snes GetAddress 0xF5xxxx N   ->   READ_CORE_RAM (xxxx) N   (offset = addr-0xF50000)

Usage: alttpr-tracker-bridge.py [--ws-port 23074] [--ra-host 127.0.0.1] [--ra-port 55355]
"""
import argparse
import base64
import hashlib
import json
import socket
import struct
import sys
import threading

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WRAM_BASE = 0xF50000          # usb2snes WRAM base -> READ_CORE_RAM offset 0
RA_CHUNK = 256                # bytes per READ_CORE_RAM request (UDP-safe)

RA_HOST = "127.0.0.1"
RA_PORT = 55355


# ── RetroArch UDP network-command client ─────────────────────────────────────
def ra_cmd(cmd, timeout=1.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(cmd.encode(), (RA_HOST, RA_PORT))
        data, _ = s.recvfrom(65535)
        return data.decode("utf-8", "replace").strip()
    except socket.timeout:
        return None
    finally:
        s.close()


def ra_status():
    """Return (running, name) — name like 'Snes9x'."""
    r = ra_cmd("GET_STATUS")
    if not r or not r.startswith("GET_STATUS"):
        return (False, None)
    # "GET_STATUS PLAYING Snes9x,<rom>,crc32=..."
    parts = r.split(" ", 2)
    if len(parts) >= 3 and parts[1] in ("PLAYING", "PAUSED"):
        core = parts[2].split(",")[0]
        return (True, core)
    return (False, None)


def ra_read_wram(offset, size):
    """Read `size` bytes of WRAM starting at `offset` via READ_CORE_RAM,
    chunked to stay UDP-safe. Returns a bytes object of length `size`
    (zero-filled on any per-chunk error so the tracker still gets fixed sizes)."""
    out = bytearray()
    pos = 0
    while pos < size:
        n = min(RA_CHUNK, size - pos)
        resp = ra_cmd("READ_CORE_RAM %x %d" % (offset + pos, n))
        chunk = bytearray(n)  # default zero
        if resp and resp.startswith("READ_CORE_RAM"):
            toks = resp.split()
            # "READ_CORE_RAM <addr> <b0> <b1> ..."  or "... -1" on error
            if len(toks) >= 3 and toks[2] != "-1":
                hexes = toks[2:]
                for i in range(min(n, len(hexes))):
                    try:
                        chunk[i] = int(hexes[i], 16)
                    except ValueError:
                        chunk[i] = 0
        out += chunk
        pos += n
    return bytes(out)


# ── minimal RFC6455 WebSocket framing (server side, unmasked out) ────────────
def ws_handshake(conn):
    req = b""
    while b"\r\n\r\n" not in req:
        d = conn.recv(4096)
        if not d:
            return False
        req += d
    key = None
    for line in req.split(b"\r\n"):
        if line.lower().startswith(b"sec-websocket-key:"):
            key = line.split(b":", 1)[1].strip()
            break
    if not key:
        return False
    accept = base64.b64encode(
        hashlib.sha1(key + WS_GUID.encode()).digest()).decode()
    resp = ("HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: %s\r\n\r\n" % accept)
    conn.sendall(resp.encode())
    return True


def ws_recv(conn):
    """Return (opcode, payload_bytes) or (None, None) on close."""
    hdr = _recvn(conn, 2)
    if not hdr:
        return (None, None)
    b0, b1 = hdr[0], hdr[1]
    opcode = b0 & 0x0F
    masked = b1 & 0x80
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack(">H", _recvn(conn, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recvn(conn, 8))[0]
    mask = _recvn(conn, 4) if masked else b"\x00\x00\x00\x00"
    payload = _recvn(conn, length) if length else b""
    if masked and payload:
        payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
    return (opcode, payload)


def _recvn(conn, n):
    buf = b""
    while len(buf) < n:
        d = conn.recv(n - len(buf))
        if not d:
            return None
        buf += d
    return buf


def ws_send(conn, data, opcode):
    b0 = 0x80 | opcode
    n = len(data)
    if n < 126:
        header = struct.pack("!BB", b0, n)
    elif n < 65536:
        header = struct.pack("!BBH", b0, 126, n)
    else:
        header = struct.pack("!BBQ", b0, 127, n)
    conn.sendall(header + data)


def ws_send_text(conn, obj):
    ws_send(conn, json.dumps(obj).encode(), 0x1)


def ws_send_binary(conn, data):
    ws_send(conn, data, 0x2)


# ── usb2snes protocol handling per connection ────────────────────────────────
def handle_conn(conn, addr):
    try:
        if not ws_handshake(conn):
            return
        while True:
            opcode, payload = ws_recv(conn)
            if opcode is None or opcode == 0x8:   # close
                return
            if opcode == 0x9:                      # ping -> pong
                ws_send(conn, payload, 0xA)
                continue
            if opcode != 0x1:                      # only text control frames
                continue
            try:
                msg = json.loads(payload.decode("utf-8", "replace"))
            except Exception:
                continue
            op = msg.get("Opcode")
            operands = msg.get("Operands") or []

            if op == "DeviceList":
                running, core = ra_status()
                results = ["RetroArch %s" % (core or "snes9x")] if running else []
                ws_send_text(conn, {"Results": results})
            elif op in ("Attach", "Name", "Register"):
                pass  # accepted; no response expected
            elif op == "Info":
                running, core = ra_status()
                ws_send_text(conn, {"Results": [
                    core or "snes9x", "1.0", "RetroArch",
                    "no info" if running else "no game"]})
            elif op == "GetAddress":
                # Operands: [hexAddr, hexSize]
                try:
                    addr_i = int(operands[0], 16)
                    size_i = int(operands[1], 16)
                except (IndexError, ValueError):
                    ws_send_binary(conn, b"")
                    continue
                offset = addr_i - WRAM_BASE
                if offset < 0:
                    # not WRAM (e.g. ROM/SRAM) — trackers we target don't do
                    # this; return zeros of the requested size.
                    ws_send_binary(conn, bytes(size_i))
                else:
                    ws_send_binary(conn, ra_read_wram(offset, size_i))
            else:
                pass
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def main():
    global RA_HOST, RA_PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws-port", type=int, default=23074)
    ap.add_argument("--ra-host", default="127.0.0.1")
    ap.add_argument("--ra-port", type=int, default=55355)
    ap.add_argument("--bind", default="0.0.0.0")
    args = ap.parse_args()
    RA_HOST, RA_PORT = args.ra_host, args.ra_port

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.bind, args.ws_port))
    srv.listen(8)
    sys.stdout.write("bridge: usb2snes ws://%s:%d -> RetroArch %s:%d\n"
                     % (args.bind, args.ws_port, RA_HOST, RA_PORT))
    sys.stdout.flush()
    while True:
        try:
            conn, addr = srv.accept()
        except KeyboardInterrupt:
            break
        t = threading.Thread(target=handle_conn, args=(conn, addr), daemon=True)
        t.start()


if __name__ == "__main__":
    main()
