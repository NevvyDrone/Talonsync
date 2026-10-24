"""Minimal, dependency-free OSC 1.0 over UDP, tuned for VRChat.

VRChat listens on UDP 9000 and sends avatar parameter changes to UDP 9001 as
/avatar/parameters/<name>. Only parameters on the avatar's expression list can be
reached. VRChat only reports values when they CHANGE, so OscLink keeps a cache of
every value it has seen.
"""
from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

PARAM_PREFIX = "/avatar/parameters/"


# ---------------------------------------------------------------- encoding
def _pad(b: bytes) -> bytes:
    return b + b"\0" * (4 - len(b) % 4)


def _osc_string(s: str) -> bytes:
    return _pad(s.encode("utf-8"))


def encode_message(address: str, *args: Any) -> bytes:
    tags = ","
    data = b""
    for a in args:
        if isinstance(a, bool):
            tags += "T" if a else "F"
        elif isinstance(a, int):
            tags += "i"
            data += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            data += struct.pack(">f", a)
        elif isinstance(a, str):
            tags += "s"
            data += _osc_string(a)
        elif a is None:
            tags += "N"
        else:
            raise TypeError(f"can't send {type(a).__name__} over OSC")
    return _osc_string(address) + _osc_string(tags) + data


def _read_string(data: bytes, i: int) -> Tuple[str, int]:
    end = data.index(b"\0", i)
    s = data[i:end].decode("utf-8", "replace")
    i = end + 1
    i += (-i) % 4
    return s, i


def decode_packet(data: bytes) -> List[Tuple[str, List[Any]]]:
    """Returns [(address, args)] for a message or a (nested) bundle."""
    if data.startswith(b"#bundle\0"):
        out = []
        i = 16  # "#bundle\0" + 8-byte timetag
        while i + 4 <= len(data):
            (n,) = struct.unpack(">i", data[i:i + 4])
            i += 4
            out += decode_packet(data[i:i + n])
            i += n
        return out
    addr, i = _read_string(data, 0)
    if i >= len(data):
        return [(addr, [])]
    tags, i = _read_string(data, i)
    args: List[Any] = []
    for t in tags[1:]:
        if t == "i":
            args.append(struct.unpack(">i", data[i:i + 4])[0]); i += 4
        elif t == "f":
            args.append(struct.unpack(">f", data[i:i + 4])[0]); i += 4
        elif t == "d":
            args.append(struct.unpack(">d", data[i:i + 8])[0]); i += 8
        elif t == "h":
            args.append(struct.unpack(">q", data[i:i + 8])[0]); i += 8
        elif t == "s":
            s, i = _read_string(data, i); args.append(s)
        elif t == "b":
            (n,) = struct.unpack(">i", data[i:i + 4]); i += 4
            args.append(data[i:i + n]); i += n + (-n) % 4
        elif t == "T":
            args.append(True)
        elif t == "F":
            args.append(False)
        elif t in "NI":
            args.append(None)
    return [(addr, args)]


# ---------------------------------------------------------------- link
class OscLink:
    """Sends to VRChat, listens for VRChat, caches every avatar parameter seen."""

    def __init__(self, send_host: str = "127.0.0.1", send_port: int = 9000,
                 listen_host: str = "127.0.0.1", listen_port: int = 9001, log: Callable[[str], None] = None,
                 fallback_port: int = 0):
        self.send_addr = (send_host, send_port)
        self.listen_addr = (listen_host, listen_port)
        self.log = log or (lambda s: None)
        self.values: Dict[str, Any] = {}
        self.stamp: Dict[str, float] = {}
        self.last_rx = 0.0
        self.rx_count = 0
        self.tx_count = 0
        self.avatar_id: Optional[str] = None
        self._cond = threading.Condition()
        self._listeners: List[Callable[[str, List[Any]], None]] = []
        self._tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._rx: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        # With OSCQuery we listen on a random port that VRChat finds by mDNS. If VRChat doesn't pick it up
        # (it sometimes misses a service that started after it), it still sends to its standard port, so we
        # also listen there when it's free, and use it only while the OSCQuery port is silent.
        self.fallback_port = fallback_port
        self._rx2: Optional[socket.socket] = None
        self._thread2: Optional[threading.Thread] = None
        self.last_rx_primary = 0.0
        self.fallback_used = False
        self._running = False
        self.error: Optional[str] = None

    # -- lifecycle
    def start(self) -> bool:
        self.stop()
        try:
            rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            rx.bind(self.listen_addr)
            rx.settimeout(0.25)
        except OSError as e:
            self.error = (f"Can't listen on UDP {self.listen_addr[1]} ({e.strerror or e}). "
                          "Another OSC app may be using it - close it, change the port, or turn on OSCQuery.")
            self.log(self.error)
            return False
        self.error = None
        self._rx = rx
        self.listen_addr = rx.getsockname()
        self._running = True
        self._thread = threading.Thread(target=self._loop, args=(rx, True), name="osc-rx", daemon=True)
        self._thread.start()
        if self.fallback_port and self.fallback_port != self.listen_addr[1]:
            try:
                rx2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                rx2.bind((self.listen_addr[0], self.fallback_port))       # no SO_REUSEADDR: only if nobody else has it
                rx2.settimeout(0.25)
                self._rx2 = rx2
                self._thread2 = threading.Thread(target=self._loop, args=(rx2, False), name="osc-rx-fallback", daemon=True)
                self._thread2.start()
            except OSError:
                self._rx2 = None
        return True

    def stop(self):
        self._running = False
        for t in (self._thread, self._thread2):
            if t:
                t.join(timeout=1)
        for r in (self._rx, self._rx2):
            if r:
                try:
                    r.close()
                except OSError:
                    pass
        self._rx = self._rx2 = None
        self._thread = self._thread2 = None

    @property
    def listening(self) -> bool:
        return self._running

    def add_listener(self, fn: Callable[[str, List[Any]], None]):
        self._listeners.append(fn)

    def _loop(self, sock=None, primary: bool = True):
        sock = sock or self._rx
        while self._running:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            now = time.monotonic()
            if primary:
                self.last_rx_primary = now
            elif now - self.last_rx_primary < 3.0:
                continue                      # VRChat reaches us on the OSCQuery port: ignore the duplicate copy
            else:
                self.fallback_used = True
            try:
                msgs = decode_packet(data)
            except Exception:
                continue
            with self._cond:
                for addr, args in msgs:
                    self.rx_count += 1
                    self.last_rx = now
                    if addr.startswith(PARAM_PREFIX) and args:
                        name = addr[len(PARAM_PREFIX):]
                        self.values[name] = args[0]
                        self.stamp[name] = now
                    elif addr == "/avatar/change" and args:
                        self.avatar_id = str(args[0])
                self._cond.notify_all()
            for addr, args in msgs:
                for fn in list(self._listeners):
                    try:
                        fn(addr, args)
                    except Exception as e:  # never let a listener kill the socket thread
                        self.log(f"OSC listener error: {e}")

    # -- sending
    def send(self, address: str, *args: Any):
        try:
            self._tx.sendto(encode_message(address, *args), self.send_addr)
            self.tx_count += 1
        except OSError as e:
            self.log(f"OSC send failed: {e}")

    def set(self, name: str, value: Any):
        """Set an avatar parameter (bool, int or float - match the parameter's type)."""
        self.send(PARAM_PREFIX + name, value)

    def chatbox(self, text: str, send_now: bool = True, sound: bool = False):
        self.send("/chatbox/input", text[:144], bool(send_now), bool(sound))

    # -- reading
    def get(self, name: str, default: Any = None) -> Any:
        with self._cond:
            return self.values.get(name, default)

    def forget(self, name: str, value: Any = None):
        """Set our cached value (used for sentinels we wrote ourselves)."""
        with self._cond:
            self.values[name] = value

    def wait_for(self, name: str, pred: Callable[[Any], bool], timeout: float) -> Optional[Any]:
        """Wait until the cached value of `name` satisfies pred. Returns the value or None on timeout."""
        end = time.monotonic() + timeout
        with self._cond:
            while True:
                v = self.values.get(name)
                if v is not None and pred(v):
                    return v
                left = end - time.monotonic()
                if left <= 0:
                    return None
                self._cond.wait(left)

    def seconds_since_rx(self) -> float:
        return 1e9 if not self.last_rx else time.monotonic() - self.last_rx
