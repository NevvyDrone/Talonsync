"""A pretend Talon Pilot that speaks the bus protocol over real UDP, like VRChat would.

Used by "Demo PDA" mode (try TalonSync without VRChat) and by the tests. It behaves like
VRChat: listens on the OSC input port, reports parameter CHANGES to the output port, clamps
expression parameters (Int 0..255, Float -1..1), and takes a frame or two per step.
"""
from __future__ import annotations

import random
import socket
import threading
import time
from typing import Dict, List

from . import protocol as pr
from .osc import PARAM_PREFIX, decode_packet, encode_message


class FakePda:
    def __init__(self, listen_port: int = 9000, send_port: int = 9001, host: str = "127.0.0.1",
                 slots: int = 48, ink_rows: int = 0, fps: float = 72.0, version: int = 3):
        self.host = host
        self.listen_port = listen_port
        self.send_port = send_port
        self.fps = fps
        self.version = version
        self.slots = slots
        self.ink_rows, self.ink_cols = ink_rows, (24 if ink_rows == 32 else 12 if ink_rows else 0)
        # --- device memory
        self.text: List[List[int]] = [[0] * 15 for _ in range(slots)]
        self.ink: List[List[bool]] = [[False] * self.ink_cols for _ in range(self.ink_rows)]
        self.values: Dict[str, float] = {v.param: 0.0 for v in pr.VALUES}
        for v in pr.PREFS:
            self.values[v.param] = {"Hour": 12, "Bright": 0.75, "Theme": 1, "Wall": 2, "Sound": 1, "Vol": 1, "TapBeep": 1,
                                    "GameSnd": 1, "Btn1": 1, "Btn2": 2, "Btn3": 3, "Btn4": 4, "Saver": 1, "SaverTime": 1}.get(v.key, 0)
        for v, d in zip(pr.APP_SETTINGS, [2, 2, 1, 2, 0, 0]):
            self.values[v.param] = d
        for v, d in zip(pr.PET, [0.8, 0.7, 0.9, 0.05, 0]):
            self.values[v.param] = d
        self.now_playing = ["", ""]
        self.pc = [pr.PC_NA] * pr.PC_VALUES
        self.pc_message = ["", ""]
        self.alerts = 0
        self.sky = (40.0, None)
        self.np_pos = 0.0
        self.app = 0
        self.weather = {}
        self.jazz = 1
        self.screen = "Launcher"
        self.events: List[str] = []
        # --- the expression parameters (what OSC sees)
        self.params: Dict[str, object] = {}
        for name, kind in pr.link_params(max(self.ink_cols, 12)):
            self.params[name] = False if kind == "bool" else 0 if kind == "int" else 0.0
        self.params[pr.POWER] = False
        self._kinds = {n: k for n, k in pr.link_params(max(self.ink_cols, 12))}
        self._kinds[pr.POWER] = "bool"
        self._clk_prev = False
        self._pending: List = []
        self._hs = "idle"
        self._hs_t = 0.0
        self._rx = None
        self._tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._run = False
        self._lock = threading.Lock()
        self.seed()

    def seed(self):
        """Something to find on the first TalonSync."""
        def put(slot, s):
            self.text[slot] = pr.encode_line(s)
        put(0, "Feed the pet"); put(1, "Draw an owl")
        put(8, "PDA memo"); put(9, "Written on the"); put(10, "Talon Pilot!")
        put(23, "Just relax...")
        for r in range(3, 7):
            for c in range(3, 9):
                if self.ink_rows and (r in (3, 6) or c in (3, 8)):
                    self.ink[r][c] = True

    # ------------------------------------------------------------ lifecycle
    def start(self):
        self._rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._rx.bind((self.host, self.listen_port))
        self._rx.settimeout(0.005)
        self.listen_port = self._rx.getsockname()[1]
        self._run = True
        threading.Thread(target=self._loop, daemon=True, name="fake-pda").start()
        return self

    def stop(self):
        self._run = False
        time.sleep(0.05)
        if self._rx:
            self._rx.close()

    def _send(self, name, value):
        self._tx.sendto(encode_message(PARAM_PREFIX + name, value), (self.host, self.send_port))

    def _setp(self, name, value):
        """Avatar-side change: clamp like VRChat and report it if it changed."""
        kind = self._kinds.get(name)
        if kind == "int":
            value = max(0, min(255, int(value)))
        elif kind == "float":
            value = max(-1.0, min(1.0, float(value)))
        elif kind == "bool":
            value = bool(value)
        if self.params.get(name) != value:
            self.params[name] = value
            self._send(name, value)

    # ------------------------------------------------------------ frame loop
    def _loop(self):
        frame = 1.0 / self.fps
        while self._run:
            t = time.monotonic()
            try:
                while True:
                    data, _ = self._rx.recvfrom(65535)
                    for addr, args in decode_packet(data):
                        if addr.startswith(PARAM_PREFIX) and args:
                            n = addr[len(PARAM_PREFIX):]
                            if n in self._kinds:
                                v = args[0]
                                k = self._kinds[n]
                                v = bool(v) if k == "bool" else max(0, min(255, int(v))) if k == "int" else max(-1.0, min(1.0, float(v)))
                                self.params[n] = v          # OSC input: not echoed back
            except (socket.timeout, BlockingIOError):
                pass
            except OSError:
                break
            with self._lock:
                self._frame()
            time.sleep(max(0.0, frame - (time.monotonic() - t)))

    def _frame(self):
        # finish a transfer one frame after it was latched (like the animator's Port -> Hold states)
        if self._pending:
            ops = self._pending
            self._pending = []
            for n, v in ops:
                self._setp(n, v)
            return
        clk = bool(self.params[pr.BUS_CLK])
        if clk and not self._clk_prev:
            self._latch(int(self.params[pr.BUS_ADDR]))
        if not clk and self._clk_prev:
            self._setp(pr.BUS_ACK, 0)
        self._clk_prev = clk
        self._sync()

    def _latch(self, a: int):
        P = self.params
        out = []
        ok = True
        if self.version >= 3 and not self.ink_rows and a < 20:
            if a < pr.ADDR_PC_MESSAGE:
                self.pc[a] = int(P[pr.BUS_LEN])
            elif a < pr.ADDR_PC_ALERT:
                self.pc_message[a - pr.ADDR_PC_MESSAGE] = pr.decode_line([int(P[pr.BUS_C(i)]) for i in range(15)])
            elif a == pr.ADDR_PC_ALERT:
                self.alerts += 1; self.events.append("alert")
            elif a == pr.ADDR_PC_CLEAR:
                self.pc_message = ["", ""]; self.pc[pr.PC_UNREAD] = 0
            elif a == pr.ADDR_SKY_LAT:
                self.sky = (int(P[pr.BUS_LEN]) - 90.0, self.sky[1])
            elif a == pr.ADDR_SKY_LON:
                self.sky = (self.sky[0], int(P[pr.BUS_LEN]) / 255 * 360 - 180)
            else:
                ok = False
        elif pr.ADDR_INK_WRITE <= a < pr.ADDR_INK_WRITE + 32:
            r = a - pr.ADDR_INK_WRITE
            if r < self.ink_rows:
                self.ink[r] = [bool(P[pr.BUS_B(c)]) for c in range(self.ink_cols)]
            else:
                ok = False
        elif pr.ADDR_INK_READ <= a < pr.ADDR_INK_READ + 32:
            r = a - pr.ADDR_INK_READ
            if r < self.ink_rows:
                out += [(pr.BUS_B(c), self.ink[r][c]) for c in range(self.ink_cols)]
            else:
                ok = False
        elif pr.ADDR_TEXT_WRITE <= a < pr.ADDR_TEXT_WRITE + 48:
            s = a - pr.ADDR_TEXT_WRITE
            if s < self.slots:
                self.text[s] = [int(P[pr.BUS_C(i)]) & 127 for i in range(15)]
            else:
                ok = False
        elif pr.ADDR_TEXT_READ <= a < pr.ADDR_TEXT_READ + 48:
            s = a - pr.ADDR_TEXT_READ
            if s < self.slots:
                out += [(pr.BUS_C(i), self.text[s][i]) for i in range(15)]
                out.append((pr.BUS_LEN, sum(1 for c in self.text[s] if c)))
            else:
                ok = False
        elif pr.ADDR_VALUE_READ <= a < pr.ADDR_VALUE_READ + 40:
            v = pr.VALUES[a - pr.ADDR_VALUE_READ]
            x = self.values.get(v.param, 0)
            out.append((pr.BUS_V, x) if v.kind == "float" else (pr.BUS_N, int(x)))
        elif pr.ADDR_VALUE_WRITE <= a < pr.ADDR_VALUE_WRITE + 40:
            v = pr.VALUES[a - pr.ADDR_VALUE_WRITE]
            n = int(P[pr.BUS_LEN])
            self.values[v.param] = n / 255.0 if v.kind == "float" else n
            self.events.append(f"value {v.key} = {self.values[v.param]}")
        elif a == pr.ADDR_PING:
            if self.version >= 2:
                out.append((pr.BUS_N, 2 if (self.ink_rows or self.version == 2) else pr.PROTOCOL_VERSION))
        elif a == pr.ADDR_RELOAD:
            self.events.append("reload")
        elif a == pr.ADDR_CLEAR_INK and self.ink_rows:
            self.ink = [[False] * self.ink_cols for _ in range(self.ink_rows)]
        elif a in (pr.ADDR_NOW_PLAYING, pr.ADDR_NOW_PLAYING + 1) and self.version >= 2:
            self.now_playing[a - pr.ADDR_NOW_PLAYING] = pr.decode_line([int(P[pr.BUS_C(i)]) for i in range(15)])
        elif a == pr.ADDR_NOW_POS and self.version >= 2:
            self.np_pos = int(P[pr.BUS_LEN]) / 255.0
        elif a == pr.ADDR_NOW_CLEAR and self.version >= 2:
            self.now_playing = ["", ""]; self.np_pos = 0.0
        elif pr.ADDR_WX_TICKER <= a < pr.ADDR_WX_TICKER + 3 and self.version >= 2:
            self.weather[a] = [int(P[pr.BUS_C(i)]) for i in range(15)]
        elif a in (pr.ADDR_WX_CURRENT, pr.ADDR_WX_FORECAST, pr.ADDR_WX_NAME) and self.version >= 2:
            self.weather[a] = [int(P[pr.BUS_C(i)]) for i in range(15)]
        elif a == pr.ADDR_JAZZ and self.version >= 2:
            self.jazz = int(P[pr.BUS_LEN])
            self.events.append(f"jazz {self.jazz}")
        elif a == pr.ADDR_OPEN_APP and self.version >= 2:
            self.app = int(P[pr.BUS_LEN]); self.values[pr.POWER] = 1
            self.events.append(f"open app {self.app}")
        else:
            ok = False
        # data lines change this frame, Ack next frame (as the animator does)
        for n, v in out:
            self._setp(n, v)
        self._pending = [(pr.BUS_ACK, 1 if ok else 2)]

    # ------------------------------------------------------------ the TalonSync screen
    def press_sync(self):
        """Like tapping TalonSync on the PDA."""
        with self._lock:
            self._hs = "waiting"
            self._hs_t = time.monotonic()
            self._setp(pr.SYNC_REQ, True)
            self.screen = "TalonSync: waiting for PC"

    def _sync(self):
        st = int(self.params[pr.SYNC_STATE])
        if self._hs == "waiting":
            if st in (1, 2):
                self._hs = "xfer"; self._setp(pr.SYNC_REQ, False)
            elif time.monotonic() - self._hs_t > 6:
                self._hs = "shown"; self._setp(pr.SYNC_REQ, False); self.screen = "TalonSync: couldn't reach TalonSync"
        elif self._hs in ("idle", "shown") and st in (1, 2):
            self._hs = "xfer"
        if self._hs == "xfer":
            stage = int(round(float(self.params[pr.SYNC_STAGE]) * 8))
            self.screen = f"TalonSync: {pr.STAGE_NAMES[max(0, min(8, stage))]} {int(float(self.params[pr.SYNC_PROG]) * 100)}%"
            if st == 3:
                self._hs = "shown"; self.screen = "TalonSync complete!"; self.events.append("chirp")
            elif st in (0, 4):
                self._hs = "shown"; self.screen = "TalonSync was interrupted."

    # ------------------------------------------------------------ inspection
    def line(self, slot: int) -> str:
        return pr.decode_line(self.text[slot])
