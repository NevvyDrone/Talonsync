"""TalonOS Enhanced (TalonSync 1.11+, Talon Pilot 2.19+): a small windowed OS on the PDA's Terminal.

TalonSync is the CPU and draws the screen as 30 x 8 cells, each a character plus a style (see STYLE below and
Talon_Term.cginc). The PDA turns styles into title bars, bevelled buttons, fields, the taskbar and icons, in the
Classic or the Skyglass theme.

1.13: a real window manager. Apps (tos_apps.py, tos_games.py) draw their window every frame with a tiny
immediate-mode toolkit (UI below): labels, buttons, fields, check boxes, radio buttons, lists and progress bars.
Input: taps on the screen (the digitizer's contact grid over OSC), the PDA's arrows (Up/Down move between controls,
Center presses, Left goes back or closes, Right opens the Start menu) and typed lines (into the focused field).
BASIC, the terminal and the BASIC programs still run full screen in text mode and come back here.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

ROWS, COLS = 8, 30


class STYLE:
    DESK, FACE, TITLE, TITLE_OFF, SEL, BUTTON, PRESSED, FIELD, TASKBAR, START = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
    DISABLED, TIP, BLUE, FACE_U, BUTTON_U, TRAY, CONSOLE, BANNER, MENU_SEL = 11, 12, 13, 14, 15, 16, 17, 18, 19
    ICON, ICON_SEL, LABEL_SEL, PROGRESS, ORANGE, FACE_BLUE, PLAIN, CAPTION, OWL, MINI_OWL, BLACK = \
        20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30


S = STYLE
Cell = List  # [char, style]
THEMES = ("classic", "skyglass")
THEME_NAMES = {"classic": "Classic", "skyglass": "Skyglass"}


class Screen:
    def __init__(self, style=S.DESK):
        self.cells = [[[" ", style] for _ in range(COLS)] for _ in range(ROWS)]
        self.spots: List[Tuple[int, int, int, int, Callable]] = []      # (row0, col0, row1, col1, action): tap targets
        self.background: set = set()                                     # spots that are only a window's body or title

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

    def spot(self, r0, c0, r1, c1, action, background=False):
        if background:
            self.background.add(len(self.spots))
        self.spots.append((r0, c0, r1, c1, action))

    def _hit(self, r, c) -> int:
        for i in range(len(self.spots) - 1, -1, -1):                 # the topmost (last drawn) wins
            r0, c0, r1, c1, action = self.spots[i]
            if r0 <= r <= r1 and c0 <= c <= c1:
                return i
        return -1

    def hit(self, r, c, cx: Optional[float] = None) -> Optional[Callable]:
        """The control under a tap. The PDA's touch grid is coarser than the screen (24 contacts across 30 cells), so
        when the cell itself is only window background, the nearest control within reach of the fingertip wins."""
        i = self._hit(r, c)
        if cx is not None and (i < 0 or i in self.background):
            best = i
            for cc in sorted({int(cx - 0.65), int(cx + 0.65)}, key=lambda k: abs(k + 0.5 - cx)):
                j = self._hit(r, cc) if cc != c and 0 <= cc < COLS else -1
                if j >= 0 and j not in self.background and (best < 0 or best in self.background):
                    best = j
            i = best
        return self.spots[i][4] if i >= 0 else None

    def rows(self) -> List[List[Tuple[str, int]]]:
        return [[(ch, st) for ch, st in row] for row in self.cells]

    def text_rows(self) -> List[str]:
        return ["".join(ch for ch, st in row) for row in self.cells]


def nice(title: str) -> str:
    """'GUESS MY NUMBER' -> 'Guess My Number' (and BASIC stays BASIC)."""
    t = " ".join(w.capitalize() if "-" not in w else "-".join(p.capitalize() for p in w.split("-")) for w in title.split())
    return t.replace("Basic", "BASIC")


def wrap(text: str, width: int) -> List[str]:
    out: List[str] = []
    for para in text.split("\n"):
        line = ""
        for w in para.split():
            while len(w) > width:
                if line:
                    out.append(line)
                    line = ""
                out.append(w[:width])
                w = w[width:]
            if len(line) + len(w) + (1 if line else 0) > width:
                out.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        out.append(line)
    return out


# ---------------------------------------------------------------------------------------------------------- toolkit
class ListState:
    """Selection and scroll position of a list box (kept by the app between frames)."""
    def __init__(self):
        self.sel = 0
        self.top = 0


class UI:
    """Draws one app's window contents for one frame and remembers what can be focused and tapped.

    Controls are focusable in the order they are drawn. The app's `focus` is an index into that order."""

    def __init__(self, sc: Screen, app: "App", active: bool, bounds=(0, 0, ROWS - 1, COLS - 1)):
        self.sc, self.app, self.active = sc, app, active
        self.bounds = bounds                                         # the window's inside: text never runs past it
        self.focusables: List[Tuple[str, Callable, object]] = []     # (kind, action, data)

    # -- focus
    def _take(self, kind: str, action: Callable, data=None) -> bool:
        i = len(self.focusables)
        self.focusables.append((kind, action, data))
        return self.active and i == self.app.focus

    def _tap(self, i: int, action: Callable) -> Callable:
        def go():
            self.app.focus = i
            action()
        return go

    # -- controls
    def label(self, r, c, text, style=S.FACE, width: int = 0):
        if width:
            text = text[:width].ljust(width)
        self.sc.text(r, c, text[:max(0, self.bounds[3] - c + 1)], style)

    def center(self, r, c0, c1, text, style=S.FACE):
        w = c1 - c0 + 1
        self.sc.text(r, c0 + max(0, (w - len(text)) // 2), text[:w], style)

    def button(self, r, c0, c1, label, action: Callable, enabled=True, pressed=False):
        if not enabled:
            self.sc.fill(r, c0, r, c1, S.BUTTON)
            self.center(r, c0, c1, label, S.DISABLED)
            return
        i = len(self.focusables)
        focus = self._take("button", action)
        st = S.PRESSED if pressed else S.BUTTON
        self.sc.fill(r, c0, r, c1, st)
        self.center(r, c0, c1, label, S.BUTTON_U if focus and not pressed else st)
        self.sc.spot(r, c0, r, c1, self._tap(i, action))

    def field(self, r, c0, c1, text: str, on_text: Optional[Callable[[str], None]] = None, placeholder=""):
        """A text box. Typing goes into it when it has the focus; tapping it gives it the focus."""
        i = len(self.focusables)
        focus = self._take("field", lambda: None, on_text)
        self.sc.fill(r, c0, r, c1, S.FIELD)
        w = c1 - c0 + 1
        shown = text[-(w - 1):] if focus else text[:w]
        if not text and placeholder and not focus:
            self.sc.text(r, c0, placeholder[:w], S.FIELD)
            self.sc.fill(r, c0, r, c0 + min(w, len(placeholder)) - 1, S.FIELD)
        else:
            self.sc.text(r, c0, shown, S.FIELD)
        if focus and len(shown) < w:
            self.sc.text(r, c0 + len(shown), "_", S.FIELD)
        self.sc.spot(r, c0, r, c1, self._tap(i, lambda: None))

    def check(self, r, c, label, value: bool, on_toggle: Callable[[bool], None]):
        i = len(self.focusables)
        act = lambda: on_toggle(not value)
        focus = self._take("button", act)
        self.sc.text(r, c, "[✓]" if value else "[ ]", S.FACE)
        self.sc.text(r, c + 4, label, S.FACE_U if focus else S.FACE)
        self.sc.spot(r, c, r, c + 3 + len(label), self._tap(i, act))

    def radio(self, r, c, label, on: bool, choose: Callable[[], None]):
        i = len(self.focusables)
        focus = self._take("button", choose)
        self.sc.text(r, c, "(•)" if on else "( )", S.FACE)
        self.sc.text(r, c + 4, label, S.FACE_U if focus else S.FACE)
        self.sc.spot(r, c, r, c + 3 + len(label), self._tap(i, choose))

    def listbox(self, r0, r1, c0, c1, items: List[str], state: ListState, on_open: Callable[[int], None],
                on_select: Optional[Callable[[int], None]] = None):
        """A sunken list. Up/Down move inside it while it has the focus; Center or a second tap opens the item."""
        n = len(items)
        h = r1 - r0 + 1
        i = len(self.focusables)
        state.sel = max(0, min(state.sel, n - 1)) if n else 0

        def move(d: int) -> bool:
            if not n or not (0 <= state.sel + d < n):
                return False
            state.sel += d
            if on_select:
                on_select(state.sel)
            return True

        focus = self._take("list", lambda: n and on_open(state.sel), move)
        if state.sel < state.top:
            state.top = state.sel
        if state.sel >= state.top + h:
            state.top = state.sel - h + 1
        state.top = max(0, min(state.top, max(0, n - h)))
        self.sc.fill(r0, c0, r1, c1, S.FIELD)
        w = c1 - c0 + 1
        for k in range(h):
            j = state.top + k
            if j >= n:
                break
            st = S.SEL if j == state.sel else S.FIELD
            self.sc.fill(r0 + k, c0, r0 + k, c1, st)
            self.sc.text(r0 + k, c0, items[j][:w - 1], st)

            def pick(j=j):
                self.app.focus = i
                if state.sel == j:
                    on_open(j)
                else:
                    state.sel = j
                    if on_select:
                        on_select(j)
            self.sc.spot(r0 + k, c0, r0 + k, c1, pick)
        if state.top > 0:
            self.sc.text(r0, c1, "^", S.FIELD if state.sel != state.top else S.SEL)
        if state.top + h < n:
            self.sc.text(r1, c1, "v", S.FIELD if state.sel != state.top + h - 1 else S.SEL)
        if not n:
            self.sc.text(r0, c0, "(empty)"[:w], S.FIELD)

    def progress(self, r, c0, c1, frac: float):
        w = c1 - c0 + 1
        self.sc.fill(r, c0, r, c1, S.FIELD)
        filled = int(round(max(0.0, min(1.0, frac)) * w))
        for k in range(filled):
            self.sc.cells[r][c0 + k] = [" ", S.PROGRESS]

    def icon(self, r, c, pic: str, style=S.ICON):
        self.sc.cells[r][c] = [pic, style]

    def spot(self, r0, c0, r1, c1, action):
        self.sc.spot(r0, c0, r1, c1, action)


# ---------------------------------------------------------------------------------------------------------- apps
class App:
    """One program on the desktop. Subclasses set `title`, `icon` and draw their window in `draw`."""
    title = "Program"
    icon = "D"
    short = ""                          # taskbar label (5 letters)
    rect = (0, 0, 6, 29)                # window: row0, col0, row1, col1 (rows 0-6; row 7 is the taskbar)
    single = True                       # opening it again brings the open one to the front

    def __init__(self, os_: "Desktop", **kw):
        self.os = os_
        self.focus = 0
        self.minimized = False
        self.status = ""

    # drawing
    def draw(self, ui: UI, r0: int, c0: int, r1: int, c1: int):
        pass

    # input: return True when handled
    def key(self, k: str) -> bool:
        return False

    def typed(self, text: str) -> bool:
        return False

    def back(self):
        self.os.close(self)

    def tick(self) -> bool:
        """About once a second while open. True = draw again."""
        return False

    def closing(self):
        pass

    # helpers
    def beep(self):
        self.os.beep()


# ---------------------------------------------------------------------------------------------------------- desktop
class Desktop:
    """The window manager: desktop icons, windows, the Start menu and the taskbar."""

    # label, picture (A-P = the PDA's icons, f folder, p prompt, r bin), app id, anchor row, anchor column
    ICONS = [
        ("Files", "f", "files", 0, 4), ("Settings", "G", "control", 0, 13), ("Games", "M", "games", 0, 24),
        ("Notepad", "D", "notepad", 2, 4), ("Calculator", "E", "calc", 2, 13), ("BASIC", "I", "basic", 2, 24),
        ("Terminal", "p", "terminal", 4, 4), ("Programs", "f", "library", 4, 13), ("Recycle Bin", "r", "bin", 4, 24),
    ]

    def __init__(self, term, version: str):
        self.term, self.version = term, version
        self.lock = threading.RLock()
        self.apps: List[App] = []                     # open windows, back to front
        self.menu_open = False
        self.menu_sel = 0
        self.sub_open: Optional[int] = None           # which Start menu entry's submenu is open
        self.sub_sel = 0
        self.sub_top = 0
        self.icon = 0
        self.splash_until = 0.0
        self.safe_until = 0.0
        self.safe = False
        self.screen = Screen()
        self.last_ui: Optional[UI] = None
        self.cfg = {"theme": "classic", "clock24": False, "seconds": False, "sounds": True, "splash": True,
                    "resume": True}
        self.scores: Dict[str, object] = {}
        self._load()

    # ------------------------------------------------------------------ settings (talonos.json in TalonSync's folder)
    @property
    def folder(self) -> str:
        return getattr(self.term.app, "dir", None) or os.path.dirname(self.term.basic.folder)

    def _path(self):
        return os.path.join(self.folder, "talonos.json")

    def _load(self):
        try:
            with open(self._path(), encoding="utf-8") as f:
                data = json.load(f)
            self.cfg.update({k: v for k, v in data.get("settings", {}).items() if k in self.cfg})
            self.scores = data.get("scores", {}) or {}
        except Exception:
            pass
        if self.cfg.get("theme") not in THEMES:
            self.cfg["theme"] = "classic"

    def save(self):
        try:
            os.makedirs(self.folder, exist_ok=True)
            tmp = self._path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"settings": self.cfg, "scores": self.scores}, f, indent=1)
            os.replace(tmp, self._path())
        except Exception:
            pass

    def set(self, key: str, value):
        self.cfg[key] = value
        self.save()

    def beep(self):
        if self.cfg.get("sounds", True):
            self.term._beep()

    # ------------------------------------------------------------------ state
    def boot(self):
        with self.lock:
            self.menu_open, self.sub_open, self.icon, self.safe = False, None, 0, False
            for a in list(self.apps):
                a.closing()
            self.apps = []
            self.splash_until = time.time() + (2.6 if self.cfg.get("splash", True) else 0.0)

    def cursor_value(self) -> float:
        """TP/Term/Cur for the PDA: 1000 Classic desktop, 1500 Skyglass, 2000-2100 the start-up screen."""
        now = time.time()
        if now < self.splash_until:
            return 2000.0 + min(100, int(100 * (1 - (self.splash_until - now) / 2.6)))
        return 1500.0 if self.cfg.get("theme") == "skyglass" else 1000.0

    @property
    def top(self) -> Optional[App]:
        for a in reversed(self.apps):
            if not a.minimized:
                return a
        return None

    # compatibility with the 1.11 desktop (tests and the terminal look at these)
    @property
    def window(self) -> Optional[str]:
        if self.safe:
            return "safe"
        t = self.top
        return getattr(t, "app_id", None) if t else None

    # ------------------------------------------------------------------ windows
    def launch(self, app_id: str, **kw) -> Optional[App]:
        from .tos_apps import REGISTRY
        with self.lock:
            self.menu_open, self.sub_open = False, None
            if app_id in ("basic", "terminal"):
                self.term.leave_gui(app_id)
                return None
            spec = REGISTRY.get(app_id)
            if not spec:
                return None
            cls = spec["cls"]
            if getattr(cls, "single", True) and not kw:
                for a in self.apps:
                    if getattr(a, "app_id", None) == app_id:
                        self.raise_(a)
                        return a
            a = cls(self, **kw)
            a.app_id = app_id
            self.apps.append(a)
            return a

    def raise_(self, a: App):
        if a in self.apps:
            self.apps.remove(a)
            self.apps.append(a)
            a.minimized = False

    def close(self, a: App):
        with self.lock:
            if a in self.apps:
                a.closing()
                self.apps.remove(a)

    def minimize(self, a: App):
        a.minimized = True

    def task_click(self, a: App):
        if self.top is a:
            a.minimized = True
        else:
            self.raise_(a)

    # ------------------------------------------------------------------ drawing
    def render(self) -> Screen:
        with self.lock:
            sc = Screen(S.DESK)
            self.last_ui = None
            if self.safe:
                sc.fill(0, 0, 7, 29, S.BLACK)
                sc.text(3, 4, "It's now safe to close", S.ORANGE)
                sc.text(4, 8, "the Terminal.", S.ORANGE)
                self.screen = sc
                return sc
            self._desktop(sc)
            top = self.top
            for a in self.apps:
                if a.minimized:
                    continue
                active = a is top and not self.menu_open
                ui = self._frame(sc, a, active)
                if a is top:
                    self.last_ui = ui
            if self.menu_open:
                self._menu(sc)
            self._taskbar(sc)
            self._hide_covered_icons(sc)
            self.screen = sc
            return sc

    def _hide_covered_icons(self, sc: Screen):
        """A desktop icon's picture spreads into the cells beside it; hide it when a window or menu covers those."""
        for label, pic, app_id, r, c in self.ICONS:
            if sc.cells[r][c][1] not in (S.ICON, S.ICON_SEL):
                continue
            if any(0 <= c + d < 30 and sc.cells[r][c + d][1] not in (S.DESK, S.ICON, S.ICON_SEL) for d in (-1, 1)):
                sc.cells[r][c] = [" ", S.DESK]

    def _desktop(self, sc: Screen):
        for i, (label, pic, app_id, r, c) in enumerate(self.ICONS):
            sel = i == self.icon and self.top is None and not self.menu_open
            sc.cells[r][c] = [pic, S.ICON_SEL if sel else S.ICON]
            c0 = c - (len(label) - 1) // 2
            sc.text(r + 1, c0, label, S.LABEL_SEL if sel else S.DESK)
            sc.spot(r, min(c - 2, c0), r + 1, max(c + 2, c0 + len(label) - 1), lambda i=i: self.open_icon(i))

    def _frame(self, sc: Screen, a: App, active: bool) -> UI:
        r0, c0, r1, c1 = a.rect
        sc.fill(r0, c0, r1, c1, S.FACE)
        ts = S.TITLE if active else S.TITLE_OFF
        sc.fill(r0, c0, r0, c1, ts)
        sc.text(r0, c0 + 1, a.title[:max(0, c1 - c0 - 4)], ts)
        sc.cells[r0][c1 - 2] = ["_", S.CAPTION]
        sc.cells[r0][c1 - 1] = ["x", S.CAPTION]
        sc.spot(r0, c0, r1, c1, lambda: None, background=True)        # taps inside a window never reach the desktop
        sc.spot(r0, c0, r0, c1 - 3, lambda a=a: self.raise_(a), background=True)
        sc.spot(r0, c1 - 2, r0, c1 - 2, lambda a=a: self.minimize(a))
        sc.spot(r0, c1 - 1, r0, c1 - 1, lambda a=a: a.back())
        ui = UI(sc, a, active, (r0 + 1, c0 + 1, r1, c1 - 1))
        try:
            a.draw(ui, r0 + 1, c0 + 1, r1, c1 - 1)
        except Exception as e:                                       # a broken app never takes the desktop down
            sc.fill(r0 + 1, c0 + 1, r1, c1 - 1, S.FACE)
            sc.text(r0 + 2, c0 + 1, "This program has a problem:"[:c1 - c0 - 1], S.FACE)
            sc.text(r0 + 3, c0 + 1, str(e)[:c1 - c0 - 1], S.FACE)
        if not active:                                               # a tap on a window behind brings it forward
            sc.spot(r0 + 1, c0, r1, c1, lambda a=a: self.raise_(a), background=True)
        if ui.focusables:
            a.focus = max(0, min(a.focus, len(ui.focusables) - 1))
        return ui

    def _taskbar(self, sc: Screen):
        sc.fill(7, 0, 7, 29, S.TASKBAR)
        st = S.PRESSED if self.menu_open else S.START
        sc.fill(7, 0, 7, 7, st)
        sc.cells[7][1] = ["o", S.MINI_OWL]
        sc.text(7, 3, "Start", st)
        sc.spot(7, 0, 7, 7, self.toggle_menu)
        shown = self.apps[-2:]
        top = self.top
        for k, a in enumerate(shown):
            c0 = 9 + k * 6
            bst = S.PRESSED if a is top and not self.menu_open else S.BUTTON
            sc.fill(7, c0, 7, c0 + 4, bst)
            sc.text(7, c0, (a.short or a.title)[:5], bst)
            sc.spot(7, c0, 7, c0 + 4, lambda a=a: self.task_click(a))
        if len(self.apps) > 2:
            sc.text(7, 20, "+", S.TASKBAR)
            sc.spot(7, 20, 7, 20, lambda: self.raise_(self.apps[0]))
        t = self.clock_text(short=True)
        sc.fill(7, 21, 7, 29, S.TRAY)
        sc.text(7, 29 - len(t), t, S.TRAY)
        sc.spot(7, 21, 7, 29, lambda: self.launch("clock"))

    def clock_text(self, short=False) -> str:
        secs = self.cfg.get("seconds") and not short
        if self.cfg.get("clock24"):
            return time.strftime("%H:%M:%S" if secs else "%H:%M")
        return time.strftime("%I:%M:%S %p" if secs else "%I:%M %p").lstrip("0")

    # ------------------------------------------------------------------ Start menu
    def menu_items(self):
        from .tos_apps import START_MENU
        return START_MENU

    def _menu(self, sc: Screen):
        items = self.menu_items()
        sc.fill(0, 0, 6, 12, S.FACE)
        sc.fill(0, 0, 6, 0, S.BANNER)
        for i, (label, accel, target) in enumerate(items[:7]):
            st = S.MENU_SEL if i == self.menu_sel else S.FACE
            sc.fill(i, 1, i, 12, st)
            sc.text(i, 1, label, st, underline=accel, ustyle=None if st == S.MENU_SEL else S.FACE_U)
            if isinstance(target, list):
                sc.text(i, 12, "▶", st)
            sc.spot(i, 1, i, 12, lambda i=i: self.menu_pick(i))
        if self.sub_open is not None:
            self._submenu(sc, items[self.sub_open][2], self.sub_open)

    def _submenu(self, sc: Screen, sub, row):
        from .tos_apps import REGISTRY
        n = len(sub)
        h = min(n, 7)
        r0 = max(0, min(row, 7 - h))
        if self.sub_sel < self.sub_top:
            self.sub_top = self.sub_sel
        if self.sub_sel >= self.sub_top + h:
            self.sub_top = self.sub_sel - h + 1
        sc.fill(r0, 13, r0 + h - 1, 29, S.FACE)
        for k in range(h):
            sc.text(r0 + k, 13, "\u2502", S.FACE)                    # a line between the menu and its submenu
            j = self.sub_top + k
            app_id = sub[j]
            label = REGISTRY[app_id].get("menu", REGISTRY[app_id]["name"]) if app_id in REGISTRY else app_id
            st = S.MENU_SEL if j == self.sub_sel else S.FACE
            sc.fill(r0 + k, 14, r0 + k, 29, st)
            sc.text(r0 + k, 14, label[:16], st)
            sc.spot(r0 + k, 14, r0 + k, 29, lambda a=app_id: self.launch(a))
        if self.sub_top > 0:
            sc.text(r0, 29, "^", S.MENU_SEL if self.sub_sel == self.sub_top else S.FACE)
        if self.sub_top + h < n:
            sc.text(r0 + h - 1, 29, "v", S.MENU_SEL if self.sub_sel == self.sub_top + h - 1 else S.FACE)

    def menu_pick(self, i: int):
        items = self.menu_items()
        label, accel, target = items[i]
        self.menu_sel = i
        if isinstance(target, list):
            if self.sub_open == i:
                self.sub_open = None
            else:
                self.sub_open, self.sub_sel, self.sub_top = i, 0, 0
            return
        self.menu_open, self.sub_open = False, None
        if target == "shutdown":
            self.launch("shutdown")
        else:
            self.launch(target)

    def toggle_menu(self):
        self.menu_open = not self.menu_open
        self.menu_sel, self.sub_open = 0, None

    # ------------------------------------------------------------------ input
    def open_icon(self, i: int):
        self.icon = i
        self.launch(self.ICONS[i][2])

    def tick(self) -> bool:
        """Called about once a second. True when the screen must be drawn again."""
        with self.lock:
            if self.safe and time.time() >= self.safe_until:
                self.safe = False
                self.boot()
                self.splash_until = 0.0
                self.term.leave_gui("menu")
                return False
            for a in list(self.apps):
                try:
                    a.tick()
                except Exception:
                    pass
            return True

    def shut_down(self):
        self.safe = True
        self.safe_until = time.time() + 3.0
        self.menu_open = False

    def key(self, k: str):
        with self.lock:
            if self.safe:
                return
            if self.menu_open:
                self._menu_key(k)
                return
            if k == "start":
                self.toggle_menu()
                return
            a = self.top
            if a is None:
                self._desktop_key(k)
                return
            if a.key(k):
                return
            ui = self.last_ui if self.last_ui and self.last_ui.app is a else None
            if ui is None:
                self.render()
                ui = self.last_ui
            fl = ui.focusables if ui else []
            if k in ("up", "down"):
                d = 1 if k == "down" else -1
                if fl:
                    kind, act, data = fl[min(a.focus, len(fl) - 1)]
                    if kind == "list" and data(d):
                        return
                    a.focus = (a.focus + d) % len(fl)
            elif k == "enter":
                if fl:
                    kind, act, data = fl[min(a.focus, len(fl) - 1)]
                    act()
            elif k == "back":
                a.back()

    def _menu_key(self, k: str):
        items = self.menu_items()
        if self.sub_open is not None:
            sub = items[self.sub_open][2]
            if k in ("up", "down"):
                self.sub_sel = (self.sub_sel + (1 if k == "down" else -1)) % len(sub)
            elif k in ("enter", "start"):
                self.launch(sub[self.sub_sel])
            elif k == "back":
                self.sub_open = None
            return
        if k in ("up", "down"):
            self.menu_sel = (self.menu_sel + (1 if k == "down" else -1)) % len(items)
        elif k == "enter":
            self.menu_pick(self.menu_sel)
        elif k == "start":                                # Right: into a submenu, or close the menu
            if isinstance(items[self.menu_sel][2], list):
                self.menu_pick(self.menu_sel)
            else:
                self.menu_open = False
        elif k == "back":
            self.menu_open = False

    def _desktop_key(self, k: str):
        n = len(self.ICONS)
        if k in ("up", "down"):
            self.icon = (self.icon + (1 if k == "down" else -1)) % n
        elif k == "enter":
            self.open_icon(self.icon)
        elif k == "back":
            self.menu_open = True                         # Left on the desktop opens the Start menu too
            self.menu_sel, self.sub_open = 0, None

    def typed(self, text: str):
        with self.lock:
            if self.safe:
                return
            t = text.strip()
            a = self.top
            if self.menu_open or a is None:
                if not t:
                    self.key("enter")
                    return
                if self.menu_open and len(t) == 1:            # a menu letter: P(rograms), A(ccessories), G(ames)...
                    for i, (label, accel, target) in enumerate(self.menu_items()):
                        if label[accel].upper() == t.upper():
                            self.menu_pick(i)
                            return
                self._shortcut(t)
                return
            ui = self.last_ui if self.last_ui and self.last_ui.app is a else None
            if ui is None:                                     # a window that opened since the last frame
                self.render()
                ui = self.last_ui
            fl = ui.focusables if ui else []
            if fl:
                kind, act, data = fl[min(a.focus, len(fl) - 1)]
                if kind == "field" and data:
                    data(text)
                    return
            if a.typed(text):
                return
            if not t:
                self.key("enter")

    def _shortcut(self, t: str):
        """On the desktop or in the Start menu, a typed word opens a program: NOTEPAD, CALC, FILES, CONTROL..."""
        from .tos_apps import REGISTRY
        w = t.upper().replace(" ", "")
        self.menu_open, self.sub_open = False, None
        for app_id, spec in REGISTRY.items():
            if spec.get("hidden"):
                continue
            names = [spec["name"].upper().replace(" ", ""), app_id.upper()] + [x.upper() for x in spec.get("words", [])]
            if any(w == n or (len(w) >= 3 and n.startswith(w)) for n in names):
                self.launch(app_id)
                return
        if w in ("BASIC", "TERMINAL", "CMD", "PROMPT"):
            self.launch("basic" if w == "BASIC" else "terminal")

    def tap(self, r: int, c: int, cx: Optional[float] = None):
        with self.lock:
            if self.safe:
                return
            if self.menu_open:
                in_menu = r <= 6 and c <= 12
                in_sub = self.sub_open is not None and c >= 13 and r <= 6
                if not in_menu and not in_sub and not (r == 7 and c <= 7):
                    self.menu_open, self.sub_open = False, None   # a tap outside the menu closes it
                    return
            action = self.screen.hit(r, c, cx)
            if action:
                action()
