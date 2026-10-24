"""PdaBus: the PC end of the Talon Pilot pseudo-serial bus (see protocol.py)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import protocol as pr
from .osc import OscLink


class BusError(Exception):
    pass


class NoPda(BusError):
    """The PDA never acknowledged: VRChat isn't running, OSC is off, or the avatar has no PC link."""


class Nak(BusError):
    """The PDA doesn't know this address (feature not installed on this avatar)."""


@dataclass
class Timing:
    ack_timeout: float = 1.5     # seconds to wait for the PDA to acknowledge a clock
    settle: float = 0.02         # after Ack, wait this long for the data lines to arrive
    gap: float = 0.0             # extra pause between transfers (slow PCs / busy instances)
    retries: int = 2


@dataclass
class PdaInfo:
    version: int = 0
    slots: int = 0               # 24 or 48 text slots
    ink_rows: int = 0            # 0 (no Note Pad), 16 (standard) or 32 (fine)
    ink_cols: int = 0            # 0, 12 or 24

    @property
    def ink_scale(self) -> int:
        return 0 if not self.ink_rows else 32 // self.ink_rows


SENTINEL_INT = 255
SENTINEL_FLOAT = -1.0


class PdaBus:
    def __init__(self, link: OscLink, timing: Optional[Timing] = None, log=None):
        self.link = link
        self.t = timing or Timing()
        self.log = log or (lambda s: None)
        self.transfers = 0
        self.info = PdaInfo()
        self.lock = threading.RLock()          # one transfer at a time (TalonSync, Now Playing and remote share the bus)
        self.last_ok = 0.0

    # ------------------------------------------------------------ one transfer
    def _clock(self, addr: int, ints: Dict[str, int] = None, bools: Dict[str, bool] = None,
               floats: Dict[str, float] = None, read_ints=(), read_bools=(), read_floats=()):
        L = self.link
        # sentinels for everything we want to read, so the PDA's answer is always a CHANGE (VRChat only reports changes)
        for n in read_ints:
            L.set(n, SENTINEL_INT); L.forget(n, SENTINEL_INT)
        for n in read_bools:
            L.set(n, False); L.forget(n, False)
        for n in read_floats:
            L.set(n, SENTINEL_FLOAT); L.forget(n, SENTINEL_FLOAT)
        for n, v in (ints or {}).items():
            L.set(n, int(v))
        for n, v in (bools or {}).items():
            L.set(n, bool(v))
        for n, v in (floats or {}).items():
            L.set(n, float(v))
        L.set(pr.BUS_ADDR, int(addr))
        L.forget(pr.BUS_ACK, 0)
        L.set(pr.BUS_CLK, True)
        ack = L.wait_for(pr.BUS_ACK, lambda a: a in (1, 2), self.t.ack_timeout)
        if ack is None:
            L.set(pr.BUS_CLK, False)
            raise NoPda(f"no answer at address {addr}")
        if self.t.settle:
            time.sleep(self.t.settle)
        out = {}
        for n in list(read_ints) + list(read_bools) + list(read_floats):
            out[n] = L.get(n)
        L.set(pr.BUS_CLK, False)
        L.wait_for(pr.BUS_ACK, lambda a: a == 0, self.t.ack_timeout)
        L.forget(pr.BUS_ACK, 0)
        self.transfers += 1
        if self.t.gap:
            time.sleep(self.t.gap)
        if ack == 2:
            raise Nak(f"address {addr} not supported by this PDA")
        return out

    def clock(self, addr: int, **kw):
        last = None
        with self.lock:
            for attempt in range(self.t.retries + 1):
                try:
                    r = self._clock(addr, **kw)
                    self.last_ok = time.monotonic()
                    return r
                except NoPda as e:
                    last = e
                    self.log(f"bus: no ack at {addr}, retry {attempt + 1}")
            raise last

    @property
    def connected_recently(self) -> bool:
        return self.last_ok and time.monotonic() - self.last_ok < 30

    # ------------------------------------------------------------ connection
    def release(self):
        """Lower the clock (recovers a PDA left mid-transfer by a crashed session)."""
        self.link.set(pr.BUS_CLK, False)
        time.sleep(0.15)
        self.link.forget(pr.BUS_ACK, 0)

    def ping(self) -> int:
        """Returns the PDA's protocol version (1 = PDA from before version 2.5)."""
        r = self.clock(pr.ADDR_PING, read_ints=[pr.BUS_N])
        n = r[pr.BUS_N]
        return 1 if n in (None, SENTINEL_INT) else int(n)

    def probe(self) -> PdaInfo:
        info = PdaInfo(version=self.ping())
        try:
            self.clock(pr.ADDR_TEXT_READ + pr.SLOTS_BASIC, read_ints=[pr.BUS_LEN])
            info.slots = pr.SLOTS_ALL
        except Nak:
            info.slots = pr.SLOTS_BASIC
        try:
            self.clock(pr.ADDR_INK_READ + 0, read_bools=[])
            try:
                self.clock(pr.ADDR_INK_READ + 16, read_bools=[])
                info.ink_rows, info.ink_cols = 32, 24
            except Nak:
                info.ink_rows, info.ink_cols = 16, 12
        except Nak:
            info.ink_rows = info.ink_cols = 0
        self.info = info
        return info

    # ------------------------------------------------------------ text
    def read_text(self, slot: int) -> str:
        names = [pr.BUS_C(i) for i in range(pr.BUS_CHARS)]
        r = self.clock(pr.ADDR_TEXT_READ + slot, read_ints=names + [pr.BUS_LEN])
        codes = [int(r[n]) if r[n] is not None else 0 for n in names]
        return pr.decode_line(codes)

    def write_text(self, slot: int, text: str):
        codes = pr.encode_line(text)
        ints = {pr.BUS_C(i): c for i, c in enumerate(codes)}
        ints[pr.BUS_LEN] = len(pr.clean(text))
        self.clock(pr.ADDR_TEXT_WRITE + slot, ints=ints)

    # ------------------------------------------------------------ ink
    def read_ink_row(self, row: int, cols: int) -> List[bool]:
        names = [pr.BUS_B(i) for i in range(cols)]
        r = self.clock(pr.ADDR_INK_READ + row, read_bools=names)
        return [bool(r[n]) for n in names]

    def write_ink_row(self, row: int, bits: List[bool]):
        self.clock(pr.ADDR_INK_WRITE + row, bools={pr.BUS_B(i): bool(b) for i, b in enumerate(bits)})

    def clear_ink(self):
        self.clock(pr.ADDR_CLEAR_INK)

    # ------------------------------------------------------------ values
    def read_value(self, k: int):
        v = pr.VALUES[k]
        if v.kind == "float":
            r = self.clock(pr.ADDR_VALUE_READ + k, read_floats=[pr.BUS_V])
            x = r[pr.BUS_V]
            return None if x is None or x == SENTINEL_FLOAT else float(x)
        r = self.clock(pr.ADDR_VALUE_READ + k, read_ints=[pr.BUS_N])
        x = r[pr.BUS_N]
        if x is None or x == SENTINEL_INT:
            return None
        return bool(x) if v.kind == "bool" else int(x)

    def write_value(self, k: int, value):
        v = pr.VALUES[k]
        n = int(round(max(0.0, min(1.0, float(value))) * 255)) if v.kind == "float" else int(value)
        self.clock(pr.ADDR_VALUE_WRITE + k, ints={pr.BUS_LEN: max(0, min(255, n))})

    def reload(self):
        self.clock(pr.ADDR_RELOAD)

    # ------------------------------------------------------------ now playing / remote
    def now_playing(self, title: str, artist: str, position: Optional[float] = None):
        for line, text in ((0, title), (1, artist)):
            # left-justified on screen either way; send right-aligned like every other line
            codes = pr.encode_line(text)
            self.clock(pr.ADDR_NOW_PLAYING + line, ints={pr.BUS_C(i): c for i, c in enumerate(codes)})
        if position is not None:
            self.now_position(position)

    def now_position(self, position: float):
        self.clock(pr.ADDR_NOW_POS, ints={pr.BUS_LEN: int(round(max(0.0, min(1.0, position)) * 255))})

    def now_clear(self):
        self.clock(pr.ADDR_NOW_CLEAR)

    def open_app(self, app: int):
        self.clock(pr.ADDR_OPEN_APP, ints={pr.BUS_LEN: int(app)})

    # ------------------------------------------------------------ TalonStar weather
    def weather(self, w: dict):
        """Send current conditions, a 3-day forecast and the city name to the PDA's TalonStar app."""
        from datetime import datetime
        c = w["current"]
        t8 = lambda v: max(0, min(255, int(round(v)) + 100)) if v is not None else 0
        dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        days = (w.get("daily") or [])[1:4]
        now = datetime.now()
        dow1 = (datetime.fromisoformat(days[0]["date"]).weekday() + 1) % 7 if days else 0      # 0 = Sunday
        today = (w.get("daily") or [{}])[0]
        cur = [t8(c.get("temp")), c.get("pda_icon", 2), c.get("humidity") or 0, min(255, c.get("wind") or 0),
               dirs.index(c["wind_dir"]) if c.get("wind_dir") in dirs else 0, int(c.get("is_day", 1)),
               1 if w.get("metric") else 0, {"S": 0, "R": 1, "F": 2}.get(c.get("trend") or "S", 0), t8(c.get("feels")),
               dow1, now.hour, now.minute, today.get("pop") or 0, t8(today.get("hi")), 1]
        self.clock(pr.ADDR_WX_CURRENT, ints={pr.BUS_C(i): int(v) for i, v in enumerate(cur)})
        fc = []
        for d in days:
            fc += [d.get("pda_icon", 2), t8(d.get("hi")), t8(d.get("lo"))]
        fc += [0] * (15 - len(fc))
        fc[9] = t8(today.get("lo"))
        self.clock(pr.ADDR_WX_FORECAST, ints={pr.BUS_C(i): int(v) for i, v in enumerate(fc[:15])})
        name = pr.encode_line(pr.to_ascii((w.get("place") or {}).get("name", "")))
        self.clock(pr.ADDR_WX_NAME, ints={pr.BUS_C(i): c_ for i, c_ in enumerate(name)})

    def ticker(self, text: str):
        """Up to 45 characters for the TalonStar ticker (3 lines of 15, drawn side by side). Empty clears it."""
        t = pr.clean(text, 45)
        for l in range(3):
            chunk = t[l * 15:(l + 1) * 15]
            codes = [ord(ch) for ch in chunk.ljust(15)] if t else [0] * 15
            if t and l * 15 >= len(t):
                codes = [32] * 15            # keep the gap even after the text ends
            self.clock(pr.ADDR_WX_TICKER + l, ints={pr.BUS_C(i): c for i, c in enumerate(codes)})

    def jazz_mode(self, mode: int):
        """0 off, 1 only you hear it, 2 everyone nearby hears it."""
        self.clock(pr.ADDR_JAZZ, ints={pr.BUS_LEN: max(0, min(2, int(mode)))})

    # ------------------------------------------------------------ PC Link (protocol 3)
    def pc_value(self, k: int, raw: int):
        """Raw 0-255 (255 = not available) for value k (pr.PC_*)."""
        self.clock(pr.ADDR_PC_VALUE + k, ints={pr.BUS_LEN: max(0, min(255, int(round(raw))))})

    def pc_message(self, title: str, text: str):
        for line, t in ((0, title), (1, text)):
            codes = pr.encode_line(t)
            self.clock(pr.ADDR_PC_MESSAGE + line, ints={pr.BUS_C(i): c for i, c in enumerate(codes)})

    def pc_alert(self):
        self.clock(pr.ADDR_PC_ALERT)

    def pc_clear(self):
        self.clock(pr.ADDR_PC_CLEAR)

    def sky_location(self, lat: float, lon: float):
        self.clock(pr.ADDR_SKY_LAT, ints={pr.BUS_LEN: int(round(max(-90.0, min(90.0, lat)) + 90))})
        self.clock(pr.ADDR_SKY_LON, ints={pr.BUS_LEN: int(round((max(-180.0, min(180.0, lon)) + 180) / 360 * 255))})

    # ------------------------------------------------------------ handshake lines
    def set_state(self, state: int):
        self.link.set(pr.SYNC_STATE, int(state))

    def set_stage(self, stage: int, progress: float):
        self.link.set(pr.SYNC_STAGE, stage / 8.0)
        self.link.set(pr.SYNC_PROG, float(max(0.0, min(1.0, progress))))
