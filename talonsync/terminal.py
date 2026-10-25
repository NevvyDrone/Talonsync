"""The Talon Pilot terminal (Talon Pilot 2.18+): TalonSync is the CPU, the PDA is the screen and keyboard.

Screen   30 x 8 characters on the PDA. Row r is the PDA's text-window lines 2r (columns 0-14) and 2r+1 (15-29),
         written as TP/Term/L{w}_{k} = code(2k) * 128 + code(2k+1). Only lines that changed are sent, at most ~12 times a
         second, so a busy program never floods VRChat. TP/Term/Cur = row * 32 + column (-1 = no PC).
Keyboard The PDA copies a typed line into TP/Bus/C0-14 (right-aligned, like its edit buffer) and TP/Bus/Len, then sets
         TP/PC/Cmd = 40. 41/42 scroll back and forward, 43 breaks a running program, 44 repeats the last line.
         A full 15-letter line is kept and joined with the next one (old pocket computers had short lines too).
"""
from __future__ import annotations

import os
import re
import queue
import threading
import time
from typing import List, Optional

from . import protocol as pr
from .basic import Basic, BasicError, Break, ExitBasic, VERSION, MEMORY
from . import library
from .enhanced import Desktop

ROWS, COLS = 8, 30
SCROLLBACK = 300

# Line graphics (Talon Pilot 2.18.2+), like a serial terminal's line-drawing set. The PDA draws codes 5-31 as shapes that
# fill the whole cell, so lines join across rows. Box lines are 16 + arms (1 up, 2 down, 4 left, 8 right).
GFX = {"\u2713": 1, "\u25c0": 2, "\u25b6": 3, "\u2022": 4,
       "\u2591": 5, "\u2592": 6, "\u2593": 7, "\u2580": 8, "\u2584": 9, "\u258c": 11, "\u2590": 12, "\u25cf": 13,
       "\u2571": 14, "\u2572": 15, "\u2588": 16,
       "\u2575": 17, "\u2577": 18, "\u2502": 19, "\u2574": 20, "\u2518": 21, "\u2510": 22, "\u2524": 23,
       "\u2576": 24, "\u2514": 25, "\u250c": 26, "\u251c": 27, "\u2500": 28, "\u2534": 29, "\u252c": 30, "\u253c": 31}
GFX_CHAR = {v: k for k, v in GFX.items()}


def is_line(ch: str) -> bool:
    return 17 <= ord(ch) <= 31


def screen_char(ch: str) -> str:
    """What one character becomes on the PDA: printable ASCII, a line-graphics code, or '?'."""
    if ch in GFX:
        return chr(GFX[ch])
    o = ord(ch)
    return ch if (32 <= o < 127 or (1 <= o < 32 and o != 10)) else "?"


def term_param(w: int, k: int) -> str:
    return f"{pr.P}Term/L{w}_{k}"


TERM_CUR, TERM_BEEP = pr.P + "Term/Cur", pr.P + "Term/Beep"
CMD_SEND, CMD_UP, CMD_DOWN, CMD_BREAK, CMD_REPEAT, CMD_ENTER = 40, 41, 42, 43, 44, 45
# the PDA digitizer (TalonOS Enhanced): 32 rows over virtual y 40..440, 24 columns over x 8..312
INK_ROWS, INK_COLS = 32, 24
GUI_X0, GUI_Y0, GUI_CW, GUI_RH = 10.0, 30.0, 10.0, 52.0


class Terminal:
    def __init__(self, app, folder: Optional[str] = None):
        self.app = app
        self.lines: List[str] = [""]                       # scrollback; the screen is the last 8 lines
        self.cy, self.cx = 0, 0                            # the cursor: index into lines, column
        self.view = 0                                      # lines scrolled back from the bottom
        self.sent: dict = {}
        self.dirty = threading.Event()
        self.lock = threading.RLock()
        self.partial = ""
        self.last_line = ""
        self.inputs: "queue.Queue[Optional[str]]" = queue.Queue()
        self.waiting_input = False
        self.worker: Optional[threading.Thread] = None
        folder = folder or os.path.join(getattr(app, "dir", "."), "Programs")
        self.basic = Basic(self.write, self._input, beep=self._beep, cls=self.cls, folder=folder,
                           locate=self.locate, plot=self.plot)
        self.libvm = Basic(self.write, self._input, beep=self._beep, cls=self.cls, folder=folder,
                           locate=self.locate, plot=self.plot)      # runs library programs, so yours is left alone
        self.active = self.basic
        self.lib_page, self.lib_pick, self.lib_state = 0, 0, "list"
        from . import __version__
        self.gui = Desktop(self, __version__)              # TalonOS Enhanced
        self.return_gui = False                            # a program / BASIC / terminal started from the desktop
        self.touch_rows, self.touch_cols = set(), set()
        self._touch_timer: Optional[threading.Timer] = None
        self._last_tick = 0.0
        autosave = os.path.join(folder, "_current.bas")
        if os.path.exists(autosave):                       # carry on where you left off
            try:
                for raw in open(autosave, encoding="utf-8", errors="replace"):
                    raw = raw.rstrip("\n")
                    if raw.strip():
                        self.basic.enter(raw)
            except Exception:
                pass
        self.mode = "menu"                                 # menu -> "basic" or "local"; nothing loads until you choose
        self.session = 0                                   # counts starts, so a late power-on reset never wipes one
        self.started = time.time()
        self._stop = threading.Event()
        threading.Thread(target=self._flusher, daemon=True, name="terminal").start()

    # ------------------------------------------------------------ screen
    def banner(self):
        self.write(f"TALON ENHANCED BASIC {VERSION}\nTALONSYNC CPU {MEMORY - self.basic.used()} BYTES FREE\nREADY.\n")

    def menu(self):
        """What the PDA sees when it opens the Terminal and finds the CPU: a choice, nothing loaded yet."""
        from . import __version__
        self.mode = "menu"
        self.return_gui = False
        self.cls()
        self.write(self._frame_top("TALONOS TERMINAL") + "\n" + self._frame_row(f" CPU: TALONSYNC {__version__}") + "\n"
                   + self._frame_bottom() + "\n"
                   " 1 TALONOS ENHANCED\n 2 TALON ENHANCED BASIC\n 3 LOCAL TERMINAL\n\nTYPE 1, 2 OR 3: ")

    def enabled(self) -> bool:
        """Experimental and opt in: TalonSync is only the Terminal's CPU when Experimental > Terminal is switched on."""
        s = getattr(self.app, "settings", None)
        return bool(s and s.get("exp_terminal", False))

    def on_app(self, app: int):
        """VRChat reported the PDA's open app. Opening the Terminal with nothing chosen shows the menu."""
        if not self.enabled():
            return
        if app == 18 and self.mode == "menu":
            self.menu()

    def _newline(self):
        self.cy += 1
        self.cx = 0
        if self.cy >= len(self.lines):
            self.lines.append("")

    def _put(self, ch: str):
        if self.cx >= COLS:
            self._newline()
        line = self.lines[self.cy].ljust(self.cx)
        old = line[self.cx] if self.cx < len(line) else " "
        if is_line(ch) and is_line(old):                   # lines that cross join up: a - over a | makes a +
            ch = chr(16 + ((ord(ch) - 16) | (ord(old) - 16)))
        self.lines[self.cy] = line[:self.cx] + ch + line[self.cx + 1:]
        self.cx += 1

    def write(self, text: str):
        with self.lock:
            for ch in text:
                if ch == "\n":
                    self._newline()
                else:
                    self._put(screen_char(ch))
            extra = len(self.lines) - SCROLLBACK
            if extra > 0:
                del self.lines[:extra]
                self.cy -= extra
            self.view = 0
        self.dirty.set()

    def _top(self) -> int:
        return max(0, len(self.lines) - ROWS)

    def locate(self, row: int, col: int):
        """Move the cursor to a place on the screen (row 0-7, column 0-29), like LOCATE."""
        with self.lock:
            row, col = max(0, min(ROWS - 1, int(row))), max(0, min(COLS - 1, int(col)))
            target = self._top() + row
            while len(self.lines) <= target:
                self.lines.append("")
            self.cy, self.cx = target, col

    def plot(self, row: int, col: int, ch: str):
        """Put one character at a place on the screen without moving the cursor (off-screen places are skipped)."""
        if not (0 <= row < ROWS and 0 <= col < COLS):
            return
        with self.lock:
            cy, cx, top = self.cy, self.cx, self._top()
            self.locate(row, col)
            ch = screen_char(ch)
            line = self.lines[self.cy]
            old = line[self.cx] if self.cx < len(line) else " "
            if ord(ch) in (17, 18, 20, 24) and not is_line(old):   # a line's end on empty ground: draw it full length
                ch = chr(19 if ord(ch) in (17, 18) else 28)
            self._put(ch)
            self.cy, self.cx = cy + (self._top() - top), cx
        self.dirty.set()

    def cls(self):
        with self.lock:
            self.lines = [""]
            self.cy = self.cx = 0
            self.view = 0
        self.dirty.set()

    def visible(self) -> List[str]:
        with self.lock:
            end = len(self.lines) - self.view
            rows = self.lines[max(0, end - ROWS):end]
        return rows + [""] * (ROWS - len(rows))

    def cursor(self) -> int:
        with self.lock:
            if self.view:
                return -2                                  # scrolled back: no cursor (but a PC is here)
            return (self.cy - self._top()) * 32 + min(self.cx, COLS - 1)

    @staticmethod
    def encode_row(text: str):
        codes = [ord(ch) if 0 < ord(ch) < 127 and ord(ch) != 10 else 0 for ch in (screen_char(ch) if ch != "\0" else ch for ch in text[:COLS].ljust(COLS, "\0"))]
        out = []
        for half in (codes[:15], codes[15:]):
            out.append([half[2 * k] * 128 + (half[2 * k + 1] if 2 * k + 1 < 15 else 0) for k in range(8)])
        return out

    @staticmethod
    def encode_cells(cells):
        """A desktop row: (char, style) pairs -> two half-lines of 8 registers, c1*128 + c2 + 16384*(s1 + 32*s2)."""
        def code(ch):
            o = ord(screen_char(ch))
            return o if 0 < o < 127 and o != 10 else 0
        out = []
        for half in (cells[:15], cells[15:30]):
            regs = []
            for k in range(8):
                a = half[2 * k] if 2 * k < len(half) else (" ", 0)
                b = half[2 * k + 1] if 2 * k + 1 < len(half) else ("\0", 0)
                cb = code(b[0]) if b[0] != "\0" else 0
                regs.append(code(a[0]) * 128 + cb + 16384 * ((a[1] & 31) + 32 * (b[1] & 31)))
            out.append(regs)
        return out

    def redraw(self, force=False):
        link = getattr(self.app, "link", None)
        if not link:
            return
        if force:
            self.sent.clear()
        gui = self.mode == "gui"
        rows = self.gui.render().rows() if gui else self.visible()
        for r, text in enumerate(rows):
            for h, regs in enumerate(self.encode_cells(text) if gui else self.encode_row(text)):
                w = 2 * r + h
                for k, v in enumerate(regs):
                    name = term_param(w, k)
                    if self.sent.get(name) != v:
                        link.set(name, float(v))
                        self.sent[name] = v
        cur = self.gui.cursor_value() if gui else float(max(-1, self.cursor()) if self.cursor() != -2 else 255)
        if self.sent.get(TERM_CUR) != cur:
            link.set(TERM_CUR, cur)
            self.sent[TERM_CUR] = cur

    def _flusher(self):
        while not self._stop.is_set():
            if self.mode == "gui" and time.time() - self._last_tick > (0.25 if time.time() < self.gui.splash_until + 0.3 else 1.0):
                self._last_tick = time.time()
                if self.gui.tick():
                    self.dirty.set()
            if self.dirty.wait(0.25 if self.mode == "gui" else 0.5):
                self.dirty.clear()
                if not self.enabled():
                    continue
                try:
                    self.redraw()
                except Exception:
                    pass
                time.sleep(0.08)                           # at most ~12 screens a second

    def attach(self):
        """The PDA powered on (or the avatar loaded, or TalonSync started): a fresh terminal, nothing loaded."""
        ticket = self.session
        def go():
            if self.session != ticket and self.enabled():
                self.redraw(force=True)                    # something was started since: keep it, just resend the screen
                return
            self.libvm.stop_flag.set()
            if not self.enabled():                         # switched off: the PDA keeps saying "No CPU found"
                self.mode = "menu"
                self.basic.stop_flag.set()
                link = getattr(self.app, "link", None)
                if link:
                    link.set(TERM_CUR, -1.0)
                    self.sent.pop(TERM_CUR, None)
                return
            self.basic.stop_flag.set()
            if self.waiting_input:
                self.inputs.put(None)
            if self.return_gui and self.gui.cfg.get("resume", True):   # 1.12.1: you were on TalonOS Enhanced: it comes back
                self.start_gui()                           # (Shut Down or MENU from the desktop goes back to the menu)
            else:
                self.menu()
            self.redraw(force=True)
        threading.Timer(0.6, go).start()

    def stop(self):
        self._stop.set()
        link = getattr(self.app, "link", None)
        if link:
            try:
                link.set(TERM_CUR, -1.0)                   # the PDA shows "no CPU" again
            except Exception:
                pass

    # ------------------------------------------------------------ keyboard
    def on_cmd(self, cmd: int):
        if not self.enabled():
            return
        if self.mode == "gui" and cmd != CMD_SEND:
            k = {CMD_UP: "up", CMD_DOWN: "down", CMD_BREAK: "back", CMD_REPEAT: "start", CMD_ENTER: "enter"}.get(cmd)
            if k:
                self.gui.key(k)
                self.dirty.set()
            return
        if cmd == CMD_BREAK and self.return_gui and not (self.worker and self.worker.is_alive()) and not self.waiting_input \
                and self.mode in ("basic", "local", "library"):
            self.back_to_gui()                             # Left when nothing is running: back to the desktop
            return
        if cmd == CMD_SEND:
            time.sleep(0.15)                               # the characters arrive with (or just after) the command
            link = self.app.link
            n = int(link.get(pr.BUS_LEN, 0) or 0)
            chars = [int(link.get(pr.BUS_C(i), 0) or 0) for i in range(pr.BUS_CHARS)]
            text = "".join(chr(c) for c in chars[pr.BUS_CHARS - n:] if 32 <= c < 127) if n > 0 else ""
            self.line(text, full=(n >= pr.BUS_CHARS))
        elif cmd == CMD_UP:
            with self.lock:
                self.view = min(self.view + 4, max(0, len(self.lines) - ROWS))
            self.dirty.set()
        elif cmd == CMD_DOWN:
            with self.lock:
                self.view = max(0, self.view - 4)
            self.dirty.set()
        elif cmd == CMD_BREAK:
            self.active.stop_flag.set()
            if self.waiting_input:
                self.inputs.put(None)
        elif cmd == CMD_REPEAT and self.last_line:
            self.line(self.last_line)

    def line(self, text: str, full: bool = False):
        """One line from the PDA keyboard (a full 15-letter line waits for the rest)."""
        if self.mode == "gui":                             # the desktop: typed lines are shortcuts
            self.gui.typed(self.partial + text if not full else text)
            self.partial = ""
            self.dirty.set()
            return
        if full:
            self.partial += text
            self.write(text)
            return
        whole = self.partial + text
        self.write(text + "\n")
        self.partial = ""
        if self.waiting_input:
            self.inputs.put(whole)
            return
        if self.worker and self.worker.is_alive():
            return                                         # busy (a program is printing): ignore typing
        if whole.strip():
            self.last_line = whole
        if self.wants_gui(whole) and not (self.mode == "library" and self.lib_state == "running"):
            if self.mode == "basic":
                self._autosave()
            self.start_gui()                               # 1.12.1: TALONOS (or WIN, GUI, DESKTOP) works everywhere
            return
        if self.mode == "menu":
            choice = whole.strip().upper()
            if choice in ("1", "TALONOS", "WIN"):
                self.start_gui()
            elif choice == "LIBRARY":
                self.start_library()
            elif choice in ("2", "BASIC"):
                self.start_basic()
            elif choice in ("3", "LOCAL"):
                self.start_local()
            else:
                self.menu()
            return
        if self.mode == "local":
            self.local(whole)
            return
        if self.mode == "library":
            self.library_key(whole.strip().upper())
            return
        if whole.strip().upper() == "LIBRARY":             # from BASIC straight to the library
            self._autosave()
            self.start_library()
            return
        self.worker = threading.Thread(target=self._run, args=(whole,), daemon=True, name="basic")
        self.worker.start()

    @staticmethod
    def wants_gui(text: str) -> bool:
        """TALONOS, TALON OS, TALONOS ENHANCED, WIN, GUI or DESKTOP, however it's spaced or cased."""
        t = text.strip().upper()
        if not t or any(not (ch.isalpha() or ch == " ") for ch in t):
            return False                                   # a BASIC line like 10 WIN=1 is never the desktop
        return t.replace(" ", "") in ("TALONOS", "TALONOSENHANCED", "ENHANCED", "WIN", "GUI", "DESKTOP")

    # ------------------------------------------------------------ the two choices
    def start_basic(self):
        self.mode = "basic"
        self.cls()
        self.write("LOADING...\n")
        self.banner()

    def start_local(self, clear=True):
        self.mode = "local"
        if clear:
            self.cls()
        self.write("LOCAL TERMINAL. TYPE HELP\n> ")

    def local(self, text: str):
        """The terminal's own commands (like an old serial terminal's local mode)."""
        from . import __version__
        words = text.strip().split(None, 1)
        cmd, arg = (words[0].upper(), words[1] if len(words) > 1 else "") if words else ("", "")
        now = time.localtime()
        if cmd == "HELP":
            self.write("TALONOS  THE DESKTOP\nLIBRARY  PROGRAMS AND GAMES\nBASIC  LOAD TALON ENH. BASIC\nCLS DATE TIME VER CPU UPTIME\nECHO TEXT  FILES  MENU  EXIT\n")
        elif cmd == "LIBRARY":
            self.start_library()
            return
        elif cmd == "BASIC":
            self.start_basic()
            return
        elif cmd == "MENU":
            self.menu()
            return
        elif cmd in ("EXIT", "TALONOS", "WIN"):
            if self.return_gui or cmd != "EXIT":
                self.start_gui() if not self.return_gui else self.back_to_gui()
            else:
                self.menu()
            return
        elif cmd == "CLS":
            self.cls()
        elif cmd == "DATE":
            self.write(time.strftime("%A %d %B %Y", now).upper()[:30] + "\n")
        elif cmd == "TIME":
            self.write(time.strftime("%H:%M:%S", now) + "\n")
        elif cmd == "VER":
            self.write(f"TALONOS TERMINAL\nTALONSYNC {__version__}\nTALON ENH. BASIC {VERSION}\n")
        elif cmd == "UPTIME":
            m = int(time.time() - self.started) // 60
            self.write(f"CPU UP {m // 60}H {m % 60:02d}M\n")
        elif cmd == "CPU":
            line = "CPU: TALONSYNC ON YOUR PC"
            try:
                import psutil
                line += f"\nLOAD {psutil.cpu_percent(interval=0.3):.0f}%  RAM {psutil.virtual_memory().percent:.0f}%"
            except Exception:
                pass
            self.write(line + "\n")
        elif cmd == "ECHO":
            self.write(arg + "\n")
        elif cmd == "FILES":
            names = self.basic.files()
            self.write(("\n".join(names) if names else "NO FILES") + "\n")
        elif cmd:
            self.write("? TYPE HELP\n")
        self.write("> ")

    # ------------------------------------------------------------ TalonOS Enhanced (the desktop)
    def start_gui(self):
        self.mode = "gui"
        self.return_gui = True
        self.gui.boot()
        self._beep()
        self.redraw(force=True)
        self.dirty.set()

    def open_program(self, name: str, run: bool = False):
        """From My Files: put a saved program into BASIC (full screen) and LIST or RUN it; Left comes back."""
        name = self.program_name(name)
        source = self.program_read(name)
        if self.worker and self.worker.is_alive():
            return
        self._keep_old()
        self.return_gui = True
        self.mode = "basic"
        self.cls()
        self._load_into(self.basic, source)
        self._autosave()
        self.write(f"LOADED {name}\n")
        if run:
            self.worker = threading.Thread(target=self._run, args=("RUN",), daemon=True, name="basic")
            self.worker.start()
        else:
            self.write("TYPE RUN OR LIST. LEFT = BACK\nREADY.\n")
        self.dirty.set()

    def _keep_old(self):
        """The program in BASIC is kept as OLDPROG before another one replaces it."""
        b = self.basic
        if b.program:
            try:
                os.makedirs(b.folder, exist_ok=True)
                with open(os.path.join(b.folder, "OLDPROG.bas"), "w", encoding="utf-8") as f:
                    for n in b.lines():
                        f.write(f"{n} {b.program[n]}\n")
            except Exception:
                pass

    def back_to_gui(self):
        self.mode = "gui"
        self.return_gui = True
        self.gui.menu_open = False
        self.dirty.set()

    def leave_gui(self, what: str, prog=None, key: str = ""):
        """The desktop starts something that runs full screen in text mode (and comes back here)."""
        if what == "menu":
            self.menu()
            return
        self.return_gui = True
        if what == "basic":
            self.start_basic()
        elif what == "terminal":
            self.start_local()
        elif what == "program":
            self.mode, self.lib_pick = "library", library.PROGRAMS.index(prog)
            if key == "E":
                self.edit_in_basic(prog)
            elif key == "L":
                self.lib_state = "listing"
                self.cls()
                self.write(prog["source"] + "\n\u25b6 UP/DOWN SCROLL. DONE = BACK")
            else:
                self.lib_state = "running"
                self.cls()
                self.worker = threading.Thread(target=self._run_lib, args=(prog,), daemon=True, name="basic-lib")
                self.worker.start()
        self.dirty.set()

    def on_touch(self, name: str, on: bool):
        """A digitizer contact (TP/In/IR0-31 rows, TP/In/IC0-23 columns) changed. A tap = the first touch after none."""
        try:
            kind, idx = name[:2], int(name[2:])
        except ValueError:
            return
        target = self.touch_rows if kind == "IR" else self.touch_cols if kind == "IC" else None
        if target is None:
            return
        was_empty = not self.touch_rows and not self.touch_cols
        (target.add if on else target.discard)(idx)
        if on and was_empty and self.mode == "gui" and self.enabled():
            if self._touch_timer:
                self._touch_timer.cancel()
            self._touch_timer = threading.Timer(0.09, self._tap_now)   # let the row and the column both arrive
            self._touch_timer.start()

    def touch_cell(self, exact: bool = False):
        if not self.touch_rows or not self.touch_cols:
            return None
        y = 40.0 + 12.5 * (sum(self.touch_rows) / len(self.touch_rows) + 0.5)
        x = 8.0 + (304.0 / INK_COLS) * (sum(self.touch_cols) / len(self.touch_cols) + 0.5)
        r = int(min(ROWS - 1, max(0, (y - GUI_Y0) // GUI_RH)))
        c = int(min(COLS - 1, max(0, (x - GUI_X0) // GUI_CW)))
        return (r, c, (x - GUI_X0) / GUI_CW) if exact else (r, c)

    def _tap_now(self):
        rc = self.touch_cell(exact=True)
        if rc and self.mode == "gui":
            self.gui.tap(*rc)
            self.dirty.set()

    # ------------------------------------------------------------ the TalonSync window (TalonSync 1.12+)
    # The PC can drive the same CPU the PDA uses: see the screen, type, press the PDA's buttons, tap the desktop and
    # write BASIC in a real editor. It works without VRChat too; with a PDA attached, both show the same screen.
    def snapshot(self) -> dict:
        """The screen as the PDA shows it: 8 rows of (text, styles), plus the mode and the cursor."""
        gui = self.mode == "gui"
        if gui:
            rows = self.gui.render().rows()
            text = ["".join(GFX_CHAR.get(ord(screen_char(ch)), ch) if ch != "\0" else " " for ch, st in r) for r in rows]
            styles = [[st for ch, st in r] for r in rows]
            cur = self.gui.cursor_value()
        else:
            vis = self.visible()
            text = ["".join(GFX_CHAR.get(ord(ch), ch) for ch in r).ljust(COLS)[:COLS] for r in vis]
            styles = [[0] * COLS for _ in vis]
            cur = float(self.cursor())
        return {"enabled": self.enabled(), "mode": self.mode, "gui": gui, "splash": gui and cur >= 2000, "cursor": cur,
                "theme": self.gui.cfg.get("theme", "classic"),
                "rows": text, "styles": styles, "running": bool(self.worker and self.worker.is_alive()),
                "waiting_input": self.waiting_input, "program_lines": len(self.basic.program)}

    def pc_key(self, key: str):
        """A PDA button pressed in the TalonSync window: up, down, left, right, center."""
        cmd = {"up": CMD_UP, "down": CMD_DOWN, "left": CMD_BREAK, "right": CMD_REPEAT, "center": CMD_ENTER}.get(key)
        if cmd is None:
            raise ValueError("unknown key")
        if cmd == CMD_ENTER and self.mode != "gui":
            self.line("")                                  # Center in text mode = Done on an empty line
        else:
            self.on_cmd(cmd)

    def pc_line(self, text: str):
        """A line typed in the TalonSync window (no 15-letter limit here)."""
        if not self.enabled():
            return
        self.line(text.replace("\r", "")[:240])

    def pc_tap(self, row: int, col: int):
        if self.enabled() and self.mode == "gui":
            self.gui.tap(int(row), int(col))
            self.dirty.set()

    def pc_start(self, what: str):
        if not self.enabled():
            raise ValueError("Switch on the Terminal CPU first.")
        self.session += 1
        if self.worker and self.worker.is_alive():
            self.active.stop_flag.set()
            if self.waiting_input:
                self.inputs.put(None)
            self.worker.join(1.0)
        {"menu": self.menu, "gui": self.start_gui, "basic": self.start_basic, "local": self.start_local,
         "library": self.start_library}[what]()
        self.dirty.set()

    def pc_load(self, source: str, run: bool = False):
        """Put a program from the editor into BASIC (your old one is kept as OLDPROG), and RUN it if asked."""
        if not self.enabled():
            raise ValueError("Switch on the Terminal CPU first.")
        self.session += 1
        if self.worker and self.worker.is_alive():
            raise ValueError("A program is running. Press Left (break) first.")
        b = self.basic
        lines = [l for l in source.replace("\r", "").split("\n") if l.strip()]
        bad = [l for l in lines if not re.match(r"\s*\d+", l)]
        if bad:
            raise ValueError(f"Every line needs a line number, like 10 PRINT \"HI\". This one doesn't: {bad[0][:40]}")
        test = Basic(lambda t: None, lambda p: None)
        for l in lines:
            try:
                test.enter(l)
            except BasicError as e:
                raise ValueError(f"?{e} ERROR in: {l[:40]}")
        self._keep_old()
        self.return_gui = self.return_gui and self.mode == "gui"
        self.mode = "basic"
        self.cls()
        self._load_into(b, "\n".join(lines))
        self._autosave()
        self.write(f"PROGRAM FROM TALONSYNC: {len(lines)} LINES\n")
        if run:
            self.write("RUN\n")
            self.worker = threading.Thread(target=self._run, args=("RUN",), daemon=True, name="basic")
            self.worker.start()
        else:
            self.write("READY.\n")

    # saved programs (the Programs folder; the same files SAVE, LOAD and FILES use)
    @staticmethod
    def program_name(name: str) -> str:
        n = re.sub(r"[^A-Z0-9_]", "", (name or "").upper())[:8]
        if not n:
            raise ValueError("Give the program a name: letters and numbers, up to 8.")
        return n

    def program_files(self):
        return self.basic.files()

    def program_read(self, name: str) -> str:
        if name.startswith("library:"):
            key = name.split(":", 1)[1]
            for p in library.PROGRAMS:
                if p["name"] == key:
                    return p["source"]
            raise ValueError("No such library program.")
        path = os.path.join(self.basic.folder, self.program_name(name) + ".bas")
        if not os.path.exists(path):
            raise ValueError("No such program.")
        return open(path, encoding="utf-8", errors="replace").read()

    def program_write(self, name: str, source: str) -> str:
        n = self.program_name(name)
        os.makedirs(self.basic.folder, exist_ok=True)
        with open(os.path.join(self.basic.folder, n + ".bas"), "w", encoding="utf-8") as f:
            f.write(source.replace("\r", "").rstrip() + "\n")
        return n

    def program_delete(self, name: str):
        path = os.path.join(self.basic.folder, self.program_name(name) + ".bas")
        if os.path.exists(path):
            os.remove(path)

    # ------------------------------------------------------------ the program library
    PER_PAGE = 5

    @staticmethod
    def _frame_top(title: str, right: str = "") -> str:
        inner = COLS - 2
        t = f"\u2500 {title} "
        r = f" {right} \u2500" if right else ""
        return "\u250c" + t + "\u2500" * max(0, inner - len(t) - len(r)) + r + "\u2510"

    @staticmethod
    def _frame_row(text: str) -> str:
        return "\u2502" + text[:COLS - 2].ljust(COLS - 2) + "\u2502"

    @staticmethod
    def _frame_bottom() -> str:
        return "\u2514" + "\u2500" * (COLS - 2) + "\u2518"

    def _export_library(self):
        """Write the library programs into the Programs folder (once), so LOAD "GUESS" works too."""
        folder = self.basic.folder
        try:
            os.makedirs(folder, exist_ok=True)
            for p in library.PROGRAMS:
                path = os.path.join(folder, p["name"] + ".bas")
                if not os.path.exists(path):
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(p["source"] + "\n")
        except Exception:
            pass

    def start_library(self, splash: bool = True):
        self.mode = "library"
        self.lib_state = "list"
        self._export_library()
        if not splash:
            self.draw_library()
            return
        self.cls()
        art = ["", "   ,___,    TALON SOFTWARE", "   (O,O)    PROGRAM LIBRARY", "   /)__)    VOLUME 1",
               ' ---"-"---  ' + f"{len(library.PROGRAMS)} PROGRAMS", "            BY NEVVYDRONE"]
        self.write(self._frame_top("TALON") + "\n" + "\n".join(self._frame_row(a) for a in art[1:]) + "\n" + self._frame_bottom() + "\n")
        def load():
            for i in range(1, 11):                         # an old-style loading bar
                if self.mode != "library" or self.lib_state != "list":
                    return
                with self.lock:
                    self.lines[-1] = "LOADING " + "\u2593" * (i * 2) + "\u2591" * (20 - i * 2)
                    self.cx = len(self.lines[-1])
                self.dirty.set()
                time.sleep(0.12)
            if self.mode == "library" and self.lib_state == "list":
                self.draw_library()
        threading.Thread(target=load, daemon=True, name="library").start()

    def draw_library(self):
        progs, per = library.PROGRAMS, self.PER_PAGE
        pages = (len(progs) + per - 1) // per
        self.lib_page %= pages
        rows = [self._frame_top("PROGRAM LIBRARY", f"{self.lib_page + 1}/{pages}")]
        for i in range(self.lib_page * per, self.lib_page * per + per):
            if i < len(progs):
                p = progs[i]
                rows.append(self._frame_row(f"{i + 1:>2} {p['title']:<18}{p['kind']:>6} "))
            else:
                rows.append(self._frame_row(""))
        rows.append(self._frame_bottom())
        self.cls()
        self.write("\n".join(rows) + "\n# OPENS  N/P PAGE  Q QUIT: ")

    def draw_card(self):
        import textwrap
        p = library.PROGRAMS[self.lib_pick]
        rows = [self._frame_top(p["title"], p["kind"])]
        body = textwrap.wrap(p["about"].upper(), COLS - 4)[:4]
        rows += [self._frame_row(" " + t) for t in body + [""] * (4 - len(body))]
        rows.append(self._frame_bottom())
        self.cls()
        self.write("\n".join(rows) + "\nR RUN  L LIST  E EDIT  B BACK\n> ")

    def library_key(self, key: str):
        if self.lib_state in ("after", "listing"):          # after a program (or a listing): back to where you were
            if self.return_gui:
                self.back_to_gui()
            elif self.lib_state == "listing":
                self.lib_state = "card"
                self.draw_card()
            else:
                self.lib_state = "list"
                self.draw_library()
            return
        if self.lib_state == "list":
            if key.isdigit() and library.by_number(int(key)):
                self.lib_pick, self.lib_state = int(key) - 1, "card"
                self.draw_card()
            elif key in ("N", ""):
                self.lib_page += 1
                self.draw_library()
            elif key == "P":
                self.lib_page -= 1
                self.draw_library()
            elif key in ("Q", "MENU"):
                self.menu()
            else:
                self.draw_library()
            return
        # a program's card
        p = library.PROGRAMS[self.lib_pick]
        if key == "R":
            self.cls()
            self.worker = threading.Thread(target=self._run_lib, args=(p,), daemon=True, name="basic-lib")
            self.worker.start()
        elif key == "L":
            self.lib_state = "listing"
            self.cls()
            self.write(p["source"] + "\n\u25b6 UP/DOWN SCROLL. DONE = BACK")
        elif key == "E":
            self.edit_in_basic(p)
        elif key in ("B", "Q", ""):
            self.lib_state = "list"
            self.draw_library()
        else:
            self.draw_card()

    def _load_into(self, vm: Basic, source: str):
        vm.program = {}
        for raw in source.splitlines():
            if raw.strip():
                vm.enter(raw)
        vm.clear()

    def _run_lib(self, p):
        vm = self.libvm
        self.active = vm
        try:
            self._load_into(vm, p["source"])
            vm.stop_flag.clear()
            vm.cur_line = None
            vm.run()
        except Break:
            self.write("\nSTOPPED.")
        except BasicError as e:
            where = getattr(vm, "cur_line", None)
            self.write(f"\n?{e} ERROR" + (f" IN {where}" if where is not None else ""))
        except Exception as e:
            self.write("\n?INTERNAL ERROR")
            log = getattr(self.app, "log", None)
            if log:
                log(f"Library {p['name']}: {e!r}")
        finally:
            self.active = self.basic
        if self.cx:
            self.write("\n")
        self.write("\u25b6 DONE = BACK TO TALONOS" if self.return_gui else "\u25b6 DONE = BACK TO THE LIBRARY")
        self.lib_state = "after"

    def edit_in_basic(self, p):
        """Open a library program in BASIC to read and change. Your own program is saved as OLDPROG first."""
        b = self.basic
        if b.program:
            try:
                os.makedirs(b.folder, exist_ok=True)
                with open(os.path.join(b.folder, "OLDPROG.bas"), "w", encoding="utf-8") as f:
                    for n in b.lines():
                        f.write(f"{n} {b.program[n]}\n")
            except Exception:
                pass
        self._load_into(b, p["source"])
        self._autosave()
        self.mode = "basic"
        self.cls()
        self.write(f"{p['title']} IS IN BASIC.\nLIST READS IT, RUN PLAYS IT,\nLIBRARY GOES BACK.\n"
                   + ("(YOUR OLD ONE: LOAD \"OLDPROG\")\n" if os.path.exists(os.path.join(b.folder, "OLDPROG.bas")) else "")
                   + "READY.\n")

    def _run(self, text: str):
        b = self.basic
        try:
            b.stop_flag.clear()
            b.enter(text)
            if not text.strip()[:1].isdigit():
                self.write("READY.\n")
            self._autosave()
        except ExitBasic:
            self._autosave()
            if self.return_gui:
                self.back_to_gui()
                return
            self.write("BASIC CLOSED\n")
            self.start_local(clear=False)
        except Break:
            self.write(f"\nBREAK" + (f" IN {b.cur_line}" if getattr(b, "cur_line", None) is not None else "") + "\nREADY.\n")
        except BasicError as e:
            where = getattr(b, "cur_line", None)                # None for a command typed at the prompt
            self.write(f"?{e} ERROR" + (f" IN {where}" if where is not None else "") + "\nREADY.\n")
        except RecursionError:
            self.write("?OUT OF MEMORY ERROR\nREADY.\n")
        except Exception as e:                             # never take TalonSync down
            self.write(f"?INTERNAL ERROR\nREADY.\n")
            log = getattr(self.app, "log", None)
            if log:
                log(f"Terminal: {e!r}")

    def _input(self, prompt: str) -> Optional[str]:
        self.write(prompt)
        self.waiting_input = True
        try:
            while True:
                try:
                    return self.inputs.get(timeout=0.5)
                except queue.Empty:
                    if self.active.stop_flag.is_set():
                        return None
        finally:
            self.waiting_input = False

    def _beep(self):
        link = getattr(self.app, "link", None)
        if link:
            link.set(TERM_BEEP, True)

    def _autosave(self):
        b = self.basic
        try:
            os.makedirs(b.folder, exist_ok=True)
            with open(os.path.join(b.folder, "_current.bas"), "w", encoding="utf-8", errors="replace") as f:
                for n in b.lines():
                    f.write(f"{n} {b.program[n]}\n")
        except Exception:
            pass
