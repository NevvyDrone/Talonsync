"""TalonOS Enhanced (TalonSync 1.11+, Talon Pilot 2.19+): a classic grey-bevel desktop on the PDA's Terminal.

TalonSync is the CPU and draws the screen as 30 x 8 cells, each a character plus a style (see STYLE below and
Talon_Term.cginc). The PDA turns styles into title bars, bevelled buttons, fields, the taskbar and icons.

Input: the PDA's arrows arrive as terminal commands (Up/Down move, Center opens, Left goes back, Right opens the Start
menu), typed lines as shortcuts, and taps on the screen as cells (the digitizer's contact grid, reported over OSC).
Programs, BASIC and the terminal run full screen in text mode and come back here when they finish.
"""
from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

from . import library

ROWS, COLS = 8, 30


class STYLE:
    DESK, FACE, TITLE, TITLE_OFF, SEL, BUTTON, PRESSED, FIELD, TASKBAR, START = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
    DISABLED, TIP, BLUE, FACE_U, BUTTON_U, TRAY, CONSOLE, BANNER, MENU_SEL = 11, 12, 13, 14, 15, 16, 17, 18, 19
    ICON, ICON_SEL, LABEL_SEL, PROGRESS, ORANGE, FACE_BLUE, PLAIN, CAPTION, OWL, MINI_OWL, BLACK = \
        20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30


S = STYLE
Cell = List  # [char, style]


class Screen:
    def __init__(self, style=S.DESK):
        self.cells = [[[" ", style] for _ in range(COLS)] for _ in range(ROWS)]
        self.spots: List[Tuple[int, int, int, int, Callable]] = []      # (row0, col0, row1, col1, action): tap targets

    def fill(self, r0, c0, r1, c1, style, ch=" "):
        for r in range(max(0, r0), min(ROWS - 1, r1) + 1):
            for c in range(max(0, c0), min(COLS - 1, c1) + 1):
                self.cells[r][c] = [ch, style]

    def text(self, r, c, s, style=None, underline: int = -1, ustyle=None):
        for i, ch in enumerate(s):
            if 0 <= r < ROWS and 0 <= c + i < COLS:
                st = style if style is not None else self.cells[r][c + i][1]
                if i == underline and ustyle is not None:
                    st = ustyle
                self.cells[r][c + i] = [ch, st]

    def style(self, r, c, style):
        if 0 <= r < ROWS and 0 <= c < COLS:
            self.cells[r][c][1] = style

    def spot(self, r0, c0, r1, c1, action):
        self.spots.append((r0, c0, r1, c1, action))

    def hit(self, r, c) -> Optional[Callable]:
        for r0, c0, r1, c1, action in reversed(self.spots):          # the topmost (last drawn) wins
            if r0 <= r <= r1 and c0 <= c <= c1:
                return action
        return None

    def rows(self) -> List[List[Tuple[str, int]]]:
        return [[(ch, st) for ch, st in row] for row in self.cells]


def nice(title: str) -> str:
    """'GUESS MY NUMBER' -> 'Guess My Number' (and BASIC stays BASIC)."""
    t = " ".join(w.capitalize() if "-" not in w else "-".join(p.capitalize() for p in w.split("-")) for w in title.split())
    return t.replace("Basic", "BASIC")


class Desktop:
    ICONS = [  # label, picture (A-P = the PDA's icons), style, action, anchor row, anchor column
        ("Programs", "f", S.ICON, "library", 0, 4), ("BASIC", "D", S.ICON, "basic", 2, 4), ("Terminal", "p", S.ICON, "terminal", 4, 4),
        ("About", "o", S.OWL, "about", 0, 13), ("Clock", "F", S.ICON, "clock", 2, 13), ("Recycle", "r", S.ICON, "bin", 4, 13),
    ]
    MENU = [("Programs", 0, "library"), ("BASIC", 0, "basic"), ("Terminal", 0, "terminal"), ("About", 0, "about"),
            ("Help", 0, "help"), ("Shut Down...", 1, "shutdown")]

    def __init__(self, term, version: str):
        self.term, self.version = term, version
        self.window: Optional[str] = None             # library, about, clock, bin, help, shutdown, safe
        self.menu_open = False
        self.icon = 0
        self.menu_sel = 0
        self.lib_sel = 0
        self.lib_top = 0
        self.btn = 0                                    # focused button in a dialog
        self.splash_until = 0.0
        self.safe_until = 0.0
        self.screen = Screen()

    # ------------------------------------------------------------------ state
    def boot(self):
        self.window, self.menu_open, self.icon = None, False, 0
        self.splash_until = time.time() + 2.6

    def cursor_value(self) -> float:
        now = time.time()
        if now < self.splash_until:
            return 2000.0 + min(100, int(100 * (1 - (self.splash_until - now) / 2.6)))
        return 1000.0

    # ------------------------------------------------------------------ drawing
    def render(self) -> Screen:
        sc = Screen(S.DESK)
        if self.window == "safe":
            sc.fill(0, 0, 7, 29, S.BLACK)
            sc.text(3, 4, "It's now safe to close", S.ORANGE)
            sc.text(4, 8, "the Terminal.", S.ORANGE)
            self.screen = sc
            return sc
        self._desktop(sc)
        if self.window == "library":
            self._library(sc)
        elif self.window in ("about", "clock", "bin", "help", "shutdown"):
            getattr(self, "_" + self.window)(sc)
        if self.menu_open:
            self._menu(sc)
        self._taskbar(sc)
        self.screen = sc
        return sc

    def _desktop(self, sc: Screen):
        for i, (label, pic, style, action, r, c) in enumerate(self.ICONS):
            sel = i == self.icon and not self.window and not self.menu_open
            sc.cells[r][c] = [pic, (S.ICON_SEL if style == S.ICON else style) if sel else style]
            c0 = c - (len(label) - 1) // 2
            sc.text(r + 1, c0, label, S.LABEL_SEL if sel else S.DESK)
            sc.spot(r, c - 2, r + 1, c0 + len(label) - 1, lambda i=i: self.open_icon(i))

    def _taskbar(self, sc: Screen):
        sc.fill(7, 0, 7, 29, S.TASKBAR)
        st = S.PRESSED if self.menu_open else S.START
        sc.fill(7, 0, 7, 8, st)
        sc.cells[7][1] = ["o", S.MINI_OWL]
        sc.text(7, 3, "Start", st)
        sc.spot(7, 0, 7, 8, self.toggle_menu)
        if self.window and self.window not in ("safe",):
            name = {"library": "Program Library", "about": "About", "clock": "Date/Time", "bin": "Recycle Bin",
                    "help": "Help", "shutdown": "Shut Down"}[self.window]
            sc.fill(7, 10, 7, 20, S.PRESSED)
            sc.text(7, 11, name[:9], S.PRESSED)
        t = time.strftime("%I:%M %p").lstrip("0")
        sc.fill(7, 21, 7, 29, S.TRAY)
        sc.text(7, 29 - len(t), t, S.TRAY)
        sc.spot(7, 21, 7, 29, lambda: self.open("clock"))

    def _window(self, sc: Screen, r0, c0, r1, c1, title, active=True):
        sc.fill(r0, c0, r1, c1, S.FACE)
        ts = S.TITLE if active else S.TITLE_OFF
        sc.fill(r0, c0, r0, c1, ts)
        sc.text(r0, c0 + 1, title[:c1 - c0 - 3], ts)
        sc.cells[r0][c1 - 1] = ["x", S.CAPTION]
        sc.spot(r0, c1 - 1, r0, c1 - 1, self.close)
        sc.spot(r0 + 1, c0, r1, c1, lambda: None)                  # taps inside a window don't reach the desktop

    def _button(self, sc: Screen, r, c0, c1, label, action, focus=False, accel=0):
        sc.fill(r, c0, r, c1, S.BUTTON)
        start = c0 + (c1 - c0 + 1 - len(label)) // 2
        sc.text(r, start, label, S.BUTTON_U if focus else S.BUTTON, underline=accel, ustyle=S.BUTTON_U)
        sc.spot(r, c0, r, c1, action)

    def _library(self, sc: Screen):
        progs = library.PROGRAMS
        self._window(sc, 0, 0, 6, 29, "Program Library", active=not self.menu_open)
        sc.fill(1, 1, 4, 28, S.FIELD)
        self.lib_sel %= len(progs)
        if self.lib_sel < self.lib_top:
            self.lib_top = self.lib_sel
        if self.lib_sel > self.lib_top + 3:
            self.lib_top = self.lib_sel - 3
        for k in range(4):
            i = self.lib_top + k
            if i >= len(progs):
                break
            p = progs[i]
            st = S.SEL if i == self.lib_sel else S.FIELD
            sc.fill(1 + k, 1, 1 + k, 28, st)
            sc.text(1 + k, 1, f"{i + 1:>2} {nice(p['title'])[:17]:<17}{p['kind'].capitalize():>6}", st)
            sc.spot(1 + k, 1, 1 + k, 28, lambda i=i: self.pick(i))
        if self.lib_top > 0:
            sc.text(1, 28, "^", S.FIELD if self.lib_sel != self.lib_top else S.SEL)
        if self.lib_top + 4 < len(progs):
            sc.text(4, 28, "v", S.FIELD if self.lib_sel != self.lib_top + 3 else S.SEL)
        about, line = progs[self.lib_sel]["about"], ""
        words = about.split()
        for n, w in enumerate(words):                   # as many whole words as fit, then "..."
            if len(line) + len(w) + 1 > (28 if n == len(words) - 1 else 25):
                line += "..."
                break
            line = (line + " " + w).strip()
        sc.text(5, 1, line, S.FACE)
        self._button(sc, 6, 1, 6, "Run", lambda: self.lib_do("R"), accel=0)
        self._button(sc, 6, 8, 13, "List", lambda: self.lib_do("L"), accel=0)
        self._button(sc, 6, 15, 20, "Edit", lambda: self.lib_do("E"), accel=0)
        self._button(sc, 6, 22, 28, "Close", self.close, accel=0)

    def _dialog(self, sc, r0, c0, r1, c1, title):
        self._window(sc, r0, c0, r1, c1, title)

    def _about(self, sc: Screen):
        self._dialog(sc, 1, 3, 5, 26, "About TalonOS")
        sc.cells[2][6] = ["o", S.OWL]
        sc.text(2, 9, "TalonOS Enhanced", S.FACE_BLUE)
        sc.text(3, 9, f"TalonSync {self.version}", S.FACE)
        sc.text(4, 5, "Created by NevvyDrone", S.FACE)
        self._button(sc, 5, 12, 17, "OK", self.close, focus=True)

    def _clock(self, sc: Screen):
        self._dialog(sc, 1, 3, 5, 26, "Date/Time")
        d = time.strftime("%A, %B ") + str(int(time.strftime("%d")))
        t = time.strftime("%I:%M:%S %p").lstrip("0")
        sc.text(2, 3 + (24 - len(d)) // 2, d[:22], S.FACE)
        sc.fill(3, 8, 3, 21, S.FIELD)
        sc.text(3, 8 + (14 - len(t)) // 2, t, S.FIELD)
        sc.text(4, 7, time.strftime("%Y   week %W"), S.FACE)
        self._button(sc, 5, 12, 17, "OK", self.close, focus=True)

    def _bin(self, sc: Screen):
        self._dialog(sc, 2, 2, 5, 27, "Recycle Bin")
        sc.text(3, 4, "The bin is empty. Hoo!", S.FACE)
        self._button(sc, 5, 12, 17, "OK", self.close, focus=True)

    def _help(self, sc: Screen):
        self._dialog(sc, 0, 0, 6, 29, "TalonOS Help")
        for i, line in enumerate(["Tap anything on the screen,", "or Up/Down to choose.",
                                  "Center opens, Left goes back,", "Right opens the Start menu."]):
            sc.text(1 + i, 1, line, S.FACE)
        self._button(sc, 6, 11, 18, "OK", self.close, focus=True)

    def _shutdown(self, sc: Screen):
        self._dialog(sc, 2, 2, 5, 27, "Shut Down TalonOS")
        sc.text(3, 4, "Close TalonOS Enhanced?", S.FACE)
        self._button(sc, 5, 6, 11, "Yes", self.shut_down, focus=self.btn == 0, accel=0)
        self._button(sc, 5, 18, 23, "No", self.close, focus=self.btn == 1, accel=0)

    def _menu(self, sc: Screen):
        sc.fill(1, 0, 6, 13, S.FACE)
        sc.fill(1, 0, 6, 0, S.BANNER)
        for i, (label, accel, action) in enumerate(self.MENU):
            r = 1 + i
            st = S.MENU_SEL if i == self.menu_sel else S.FACE
            sc.fill(r, 1, r, 13, st)
            sc.text(r, 2, label, st, underline=accel, ustyle=None if st == S.MENU_SEL else S.FACE_U)
            sc.spot(r, 1, r, 13, lambda a=action: self.open(a))

    # ------------------------------------------------------------------ input
    def open_icon(self, i: int):
        if self.icon == i or True:
            self.icon = i
            self.open(self.ICONS[i][3])

    def toggle_menu(self):
        self.menu_open = not self.menu_open
        self.menu_sel = 0

    def open(self, what: str):
        self.menu_open = False
        if what in ("basic", "terminal"):
            self.term.leave_gui(what)
            return
        self.window, self.btn = what, 0

    def close(self):
        self.window = None

    def pick(self, i: int):
        if self.lib_sel == i:
            self.lib_do("R")                            # tapping the chosen one again runs it
        self.lib_sel = i

    def lib_do(self, key: str):
        self.term.leave_gui("program", library.PROGRAMS[self.lib_sel], key)

    def shut_down(self):
        self.window = "safe"
        self.safe_until = time.time() + 3.0

    def tick(self) -> bool:
        """Called about once a second. True when the screen must be drawn again."""
        if self.window == "safe" and time.time() >= self.safe_until:
            self.window = None
            self.term.leave_gui("menu")
            return False
        return True

    def key(self, k: str):
        if self.window == "safe":
            return
        if k == "start":
            self.toggle_menu()
            return
        if self.menu_open:
            if k in ("up", "down"):
                self.menu_sel = (self.menu_sel + (1 if k == "down" else -1)) % len(self.MENU)
            elif k == "enter":
                self.open(self.MENU[self.menu_sel][2])
            elif k == "back":
                self.menu_open = False
            return
        if self.window == "library":
            n = len(library.PROGRAMS)
            if k in ("up", "down"):
                self.lib_sel = (self.lib_sel + (1 if k == "down" else -1)) % n
            elif k == "enter":
                self.lib_do("R")
            elif k == "back":
                self.close()
            return
        if self.window == "shutdown":
            if k in ("up", "down"):
                self.btn = 1 - self.btn
            elif k == "enter":
                self.shut_down() if self.btn == 0 else self.close()
            elif k == "back":
                self.close()
            return
        if self.window:                                  # simple dialogs: OK
            if k in ("enter", "back"):
                self.close()
            return
        if k in ("up", "down"):
            self.icon = (self.icon + (1 if k == "down" else -1)) % len(self.ICONS)
        elif k == "enter":
            self.open(self.ICONS[self.icon][3])
        elif k == "back":
            self.menu_open = True                         # Left on the desktop opens the Start menu too

    def typed(self, text: str):
        t = text.strip().upper()
        if not t:
            self.key("enter")
            return
        if self.window == "library":
            if t.isdigit() and library.by_number(int(t)):
                self.lib_sel = int(t) - 1
            elif t[0] in "RLE":
                self.lib_do(t[0])
            elif t[0] in "XQC":
                self.close()
            return
        if self.window == "shutdown":
            self.shut_down() if t[0] == "Y" else self.close()
            return
        if self.window:
            self.close()
            return
        for label, accel, action in self.MENU:
            if t[0] == label[accel].upper() and (self.menu_open or t[0] in "PBTAHU"):
                self.open(action)
                return

    def tap(self, r: int, c: int):
        if self.window == "safe":
            return
        if self.menu_open and not (1 <= r <= 6 and c <= 13) and not (r == 7 and c <= 8):
            self.menu_open = False                        # a tap outside the menu closes it
            return
        action = self.screen.hit(r, c)
        if action:
            action()
