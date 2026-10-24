"""Desktop click: a mouse button (or key) on your PC taps the Talon Pilot where you look.

VRChat desktop players aim at the parked PDA with the dot in the middle of the screen. Holding the chosen
button sets the avatar parameter TP/Desk/Tap over OSC (exactly what Expressions > Desktop > "Tap where I look"
does); releasing it lets go. A second, optional button sets TP/Desk/Here ("Bring PDA in front").

No input hooks: the button is polled with GetAsyncKeyState (~60 times a second), so it can never add mouse
lag or swallow clicks. It only acts while the VRChat window is in front. Windows only.
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Callable, Optional

TAP_PARAM = "TP/Desk/Tap"
HERE_PARAM = "TP/Desk/Here"

# what the settings may name -> Windows virtual-key code
BUTTONS = {
    "middle": 0x04, "side1": 0x05, "side2": 0x06,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    **{ch: ord(ch.upper()) for ch in "abcdefghijklmnopqrstuvwxyz0123456789"},
}
LABELS = {"middle": "Middle mouse button", "side1": "Mouse side button (back)", "side2": "Mouse side button (forward)"}


def label(name: str) -> str:
    if not name:
        return "None"
    return LABELS.get(name, name.upper() + " key")


class DeskClick:
    def __init__(self, settings, send: Callable[[str, bool], None], log: Callable[[str], None] = print):
        self.settings, self.send, self.log = settings, send, log
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.available = sys.platform == "win32"
        self.why = "" if self.available else "the desktop click button only works on Windows"
        self.pressing = {TAP_PARAM: False, HERE_PARAM: False}
        self.vrchat_front = False
        self.taps = 0
        self._user32 = None

    # ------------------------------------------------------------------ platform
    def _setup(self) -> bool:
        if not self.available:
            return False
        try:
            import ctypes
            self._user32 = ctypes.windll.user32            # type: ignore[attr-defined]
            self._buf = ctypes.create_unicode_buffer(256)
            return True
        except Exception as e:                              # pragma: no cover - Windows only
            self.available, self.why = False, f"Windows input isn't available ({e})"
            return False

    def _down(self, vk: int) -> bool:
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def _vrchat_in_front(self) -> bool:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return False
        self._user32.GetWindowTextW(hwnd, self._buf, 256)
        return self._buf.value.strip() == "VRChat"

    # ------------------------------------------------------------------ loop
    def start(self):
        if self._thread or not self._setup():
            return
        self._thread = threading.Thread(target=self._loop, name="deskclick", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._release_all()

    def _set(self, param: str, on: bool):
        if self.pressing.get(param) == on:
            return
        self.pressing[param] = on
        try:
            self.send(param, on)
        except Exception as e:
            self.log(f"Desktop click: couldn't reach VRChat ({e})")
        if on and param == TAP_PARAM:
            self.taps += 1

    def _release_all(self):
        for p in list(self.pressing):
            if self.pressing[p]:
                self._set(p, False)

    def _loop(self):
        last_focus = 0.0
        while not self._stop.wait(1 / 60):
            try:
                if not self.settings.get("desk_click", True):
                    self._release_all()
                    self._stop.wait(0.5)
                    continue
                now = time.time()
                if now - last_focus > 0.25:
                    last_focus = now
                    self.vrchat_front = self._vrchat_in_front()
                if not self.vrchat_front:
                    self._release_all()
                    continue
                for param, key in ((TAP_PARAM, "desk_click_button"), (HERE_PARAM, "desk_here_button")):
                    vk = BUTTONS.get(str(self.settings.get(key, "") or "").lower())
                    self._set(param, bool(vk) and self._down(vk))
            except Exception as e:                          # never let the loop die
                self.log(f"Desktop click: {e}")
                self._stop.wait(1.0)

    def status(self) -> dict:
        return {"available": self.available, "why": self.why, "on": bool(self.settings.get("desk_click", True)),
                "button": label(str(self.settings.get("desk_click_button", "middle") or "")),
                "here": label(str(self.settings.get("desk_here_button", "") or "")),
                "vrchat_front": self.vrchat_front, "taps": self.taps,
                "choices": [{"value": k, "label": label(k)} for k in ["middle", "side1", "side2"] + [f"f{i}" for i in range(1, 13)]]}
