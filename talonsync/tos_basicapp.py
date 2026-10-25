"""BASIC apps (TalonSync 1.14): a Talon Enhanced BASIC program that uses WINDOW runs as a TalonOS app, in its own
window and process, on its own thread. PRINT and INPUT work inside the window too, so any program can run there.

  10 WINDOW "HELLO"
  20 TEXT 0,0,"WHAT'S YOUR NAME?"
  30 FIELD 1,1,0,20
  40 BUTTON 2,3,0,8,"SAY HI"
  50 WAIT E
  60 IF E=2 THEN NOTIFY "HI "+FIELD$(1)
  70 GOTO 50

Rows 0-5 and columns 0-27 are the inside of the window. WAIT stores the id of the button pressed (or the field
where Done was pressed, or the check box ticked); WAIT E, 2 gives up after two seconds with 0. Closing the window
stops the program.
"""
from __future__ import annotations

import os
import queue
import threading
from typing import Dict, List, Optional

from .basic import Basic, BasicError, Break, ExitBasic
from .enhanced import App, S, UI, wrap
from .tos_fs import FSError

SAMPLES = {
    "HELLO.BAS": '''10 REM HELLO: A FIRST TALONOS APP
20 WINDOW "HELLO"
30 TEXT 0,0,"WHAT'S YOUR NAME?"
40 FIELD 1,1,0,20
50 BUTTON 2,3,0,9,"SAY HI"
60 BUTTON 3,3,11,9,"BEEP"
70 WAIT E
80 IF E=1 OR E=2 THEN TEXT 2,0,"HI "+FIELD$(1)+"! HOO!     ":NOTIFY "HI "+FIELD$(1)
90 IF E=3 THEN BEEP
100 GOTO 70
''',
    "TODO.BAS": '''10 REM TODO: A TO-DO LIST SAVED IN C:\\DOCUMENTS\\TODO.TXT
20 WINDOW "TO-DO"
30 DIM T$(20):N=0
40 IF NOT EXISTS("C:\\DOCUMENTS\\TODO.TXT") THEN 80
50 OPEN #1,"C:\\DOCUMENTS\\TODO.TXT","I"
60 IF EOF(1) OR N=20 THEN CLOSE #1:GOTO 80
70 N=N+1:INPUT #1,T$(N):GOTO 60
80 GOSUB 200
90 WAIT E
100 IF (E=1 OR E=3) AND FIELD$(1)<>"" AND N<20 THEN N=N+1:T$(N)=FIELD$(1):FIELD 1,0,0,20,"":GOSUB 300:GOSUB 200
110 IF E=2 AND N>0 THEN N=N-1:GOSUB 300:GOSUB 200
120 GOTO 90
200 CLS:FIELD 1,0,0,20:BUTTON 3,0,21,7,"ADD"
210 FOR I=1 TO 4:J=N-4+I
220 IF J>0 THEN TEXT I,0,STR$(J)+". "+T$(J)
230 NEXT I
240 BUTTON 2,5,0,13,"DONE LAST":TEXT 5,15,STR$(N)+" TO DO"
250 RETURN
300 OPEN #2,"C:\\DOCUMENTS\\TODO.TXT","O"
310 FOR I=1 TO N:PRINT #2,T$(I):NEXT I
320 CLOSE #2:RETURN
''',
    "COUNTER.BAS": '''10 REM COUNTER: BUTTONS, A CHECK BOX AND A BAR
20 WINDOW "OWL COUNTER"
30 C=0
40 BUTTON 1,4,0,6,"+1":BUTTON 2,4,8,6,"-1":BUTTON 3,4,16,8,"RESET"
50 CHECK 4,3,0,"BEEP AT 10",1
60 TEXT 0,0,"OWLS SPOTTED:"+STR$(C)+"   "
70 BAR 1,0,28,C/10
80 WAIT E
90 IF E=1 THEN C=C+1
100 IF E=2 AND C>0 THEN C=C-1
110 IF E=3 THEN C=0
120 IF C=10 AND CHECKED(4) THEN BEEP:NOTIFY "TEN OWLS!"
130 IF C>10 THEN C=10
140 GOTO 60
''',
}


def install_samples(desktop):
    """The first time, put the sample apps in C:\\Apps (and never again, even if you delete them)."""
    k = desktop.kernel
    if k.registry.get("system.samples", 0) >= 1:
        return
    for name, src in SAMPLES.items():
        try:
            if not k.fs.exists("C:\\Apps\\" + name):
                k.fs.write_text("C:\\Apps\\" + name, src)
        except FSError:
            pass
    try:
        from .tos_plugins import SAMPLE_PLUGIN
        if not k.fs.exists("C:\\Apps\\hello_plugin.py"):
            k.fs.write_text("C:\\Apps\\hello_plugin.py", SAMPLE_PLUGIN)
    except FSError:
        pass
    k.registry.set("system.samples", 1)


def installed_apps(desktop) -> List[tuple]:
    """Start menu entries for C:\\Apps: (label, action)."""
    out = []
    try:
        for e in desktop.kernel.fs.listdir("C:\\Apps"):
            if e.is_dir or e.ext not in (".BAS", ".PY"):
                continue
            label = os.path.splitext(e.name)[0].replace("_", " ").title()
            out.append((label[:16], (lambda p=e.path: desktop.kernel.open(p))))
    except FSError:
        pass
    return out


class BasicApp(App):
    title = "BASIC app"
    icon = "I"
    short = "App"
    single = False

    def __init__(self, os_, path: str = "", source: Optional[str] = None):
        super().__init__(os_)
        self.path = path
        name = os.path.splitext(os.path.basename(path.replace("\\", "/")))[0] or "PROGRAM"
        self.title, self.short = name.title(), name[:5].title()
        self.lock = threading.RLock()
        self.console: List[str] = [""]
        self.items: Dict[tuple, str] = {}                 # (row, col) -> text
        self.controls: Dict[int, dict] = {}               # id -> control
        self.events: "queue.Queue[Optional[int]]" = queue.Queue()
        self.inputs: "queue.Queue[Optional[str]]" = queue.Queue()
        self.prompt: Optional[str] = None
        self.input_text = ""
        self.modal: Optional[str] = None                  # MSGBOX text
        self.modal_q: "queue.Queue[Optional[int]]" = queue.Queue()
        self.windowed = False
        self.finished = False
        self.error = ""
        self.closed = False
        if source is None:
            source = self.api.fs.read_text(path)
        k = os_.kernel
        self.b = Basic(self._out, self._inp, beep=os_.beep, cls=self.cls, folder=os_.term.basic.folder)
        self.b.fs, self.b.gui = k.fs, self
        self.b.cwd = "C:\\Documents"                       # file names without a folder mean C:\\Documents
        for raw in source.replace("\r", "").split("\n"):
            if raw.strip():
                self.b.enter(raw)                          # a syntax error stops the app before it starts
        self.thread = threading.Thread(target=self._main, daemon=True, name=f"basicapp-{self.pid}")
        self.thread.start()

    # ------------------------------------------------------------------ the program's thread
    def _main(self):
        try:
            self.b.run()
        except Break:
            pass
        except ExitBasic:
            pass
        except BasicError as e:
            line = getattr(self.b, "cur_line", None)
            self.error = f"?{e} ERROR" + (f" IN {line}" if line is not None else "")
            self._out("\n" + self.error + "\n")
        except Exception as e:                            # an interpreter bug: report it, don't crash TalonSync
            self.error = f"?{type(e).__name__.upper()} ERROR"
            self._out("\n" + self.error + "\n")
        finally:
            self.finished = True
            if not self.closed and not self.error and self.windowed and not any(l.strip() for l in self.console):
                self.os.close(self)                       # a windowed app that ENDs closes its window
            self._redraw()

    def _redraw(self):
        try:
            self.os.term.dirty.set()
        except Exception:
            pass

    def _out(self, text: str):
        with self.lock:
            for ch in text:
                if ch == "\n":
                    self.console.append("")
                else:
                    if len(self.console[-1]) >= 28:
                        self.console.append("")
                    self.console[-1] += ch
            self.console = self.console[-60:]
        self._redraw()

    def _inp(self, prompt: str) -> Optional[str]:
        with self.lock:
            self.prompt, self.input_text = prompt, ""
        self._redraw()
        while True:
            if self.b.stop_flag.is_set():
                return None
            try:
                v = self.inputs.get(timeout=0.1)
            except queue.Empty:
                continue
            with self.lock:
                self.prompt = None
            if v is not None:
                self._out(prompt + v + "\n")
            return v

    # ------------------------------------------------------------------ what BASIC calls (the gui hooks)
    def window(self, title: str):
        with self.lock:
            self.title, self.short, self.windowed = title[:24], title[:5], True
        self._redraw()

    def cls(self):
        with self.lock:
            self.console, self.items, self.controls = [""], {}, {}
        self._redraw()

    def text(self, r: int, c: int, s: str):
        with self.lock:
            self.items[(r, c)] = s
        self._redraw()

    def button(self, n, r, c, w, label):
        with self.lock:
            self.controls[n] = {"kind": "button", "r": r, "c": c, "w": max(1, w), "label": label}
        self._redraw()

    def field(self, n, r, c, w, text):
        with self.lock:
            old = self.controls.get(n, {}).get("text", "")
            self.controls[n] = {"kind": "field", "r": r, "c": c, "w": max(1, w), "text": old if text is None else text}
        self._redraw()

    def check(self, n, r, c, label, on):
        with self.lock:
            old = self.controls.get(n, {}).get("on", False)
            self.controls[n] = {"kind": "check", "r": r, "c": c, "label": label, "on": old if on is None else on}
        self._redraw()

    def bar(self, r, c, w, frac):
        with self.lock:
            self.items[(r, c)] = ("\0bar", max(1, w), frac)
        self._redraw()

    def field_text(self, n) -> str:
        with self.lock:
            return self.controls.get(n, {}).get("text", "")

    def checked(self, n) -> bool:
        with self.lock:
            return bool(self.controls.get(n, {}).get("on", False))

    def wait(self, secs: Optional[float], stop) -> Optional[int]:
        import time
        end = None if secs is None else time.time() + max(0.0, secs)
        while True:
            if stop.is_set() or self.closed:
                return None
            try:
                ev = self.events.get(timeout=0.1)
                return ev
            except queue.Empty:
                if end is not None and time.time() >= end:
                    return 0

    def notify(self, s: str):
        self.os.kernel.notify(s)

    def msgbox(self, s: str, stop) -> Optional[int]:
        with self.lock:
            self.modal = s
        self._redraw()
        while True:
            if stop.is_set() or self.closed:
                return None
            try:
                return self.modal_q.get(timeout=0.1)
            except queue.Empty:
                continue

    # ------------------------------------------------------------------ drawing and input (the desktop's thread)
    def _event(self, n: int):
        self.events.put(n)

    def draw(self, ui: UI, r0, c0, r1, c1):
        with self.lock:
            console = list(self.console)
            items = dict(self.items)
            controls = dict(self.controls)
            prompt, modal = self.prompt, self.modal
        h = r1 - r0 + 1
        if modal is not None:
            for k, line in enumerate(wrap(modal, c1 - c0 + 1)[:h - 1]):
                ui.center(r0 + k, c0, c1, line)
            ui.button(r1, c0 + 10, c0 + 17, "OK", self._modal_ok)
            return
        rows = h - (1 if prompt is not None else 0)
        if any(l.strip() for l in console) or not (items or controls):
            shown = console[-rows:] if console[-1] or len(console) == 1 else console[-rows - 1:-1]
            for k, line in enumerate(shown[-rows:]):
                ui.label(r0 + k, c0, line)
        for (r, c), v in sorted(items.items()):
            if not (0 <= r < h and 0 <= c <= c1 - c0):
                continue
            if isinstance(v, tuple):
                ui.progress(r0 + r, c0 + c, min(c1, c0 + c + v[1] - 1), v[2])
            else:
                ui.label(r0 + r, c0 + c, v)
        for n, ctl in sorted(controls.items(), key=lambda kv: (kv[1]["r"], kv[1]["c"])):
            r, c = r0 + ctl["r"], c0 + ctl["c"]
            if not (r0 <= r <= r1 and c0 <= c <= c1):
                continue
            if ctl["kind"] == "button":
                ui.button(r, c, min(c1, c + ctl["w"] - 1), ctl["label"], lambda n=n: self._event(n))
            elif ctl["kind"] == "field":
                ui.field(r, c, min(c1, c + ctl["w"] - 1), ctl["text"], lambda t, n=n: self._field_done(n, t))
            elif ctl["kind"] == "check":
                ui.check(r, c, ctl["label"][:c1 - c - 3], ctl["on"], lambda v, n=n: self._toggle(n, v))
        if prompt is not None:
            p = prompt[:12]
            ui.label(r1, c0, p)
            ui.field(r1, c0 + len(p), c1, self.input_text, self._answer)
            self.focus = len(ui.focusables) - 1
        if self.finished and not self.error and not self.windowed:
            ui.label(r1, c1 - 9, "(finished)")

    def _field_done(self, n: int, text: str):
        with self.lock:
            if n in self.controls:
                self.controls[n]["text"] = text.strip()[:60]
        self._event(n)

    def _toggle(self, n: int, v: bool):
        with self.lock:
            if n in self.controls:
                self.controls[n]["on"] = v
        self._event(n)

    def _answer(self, text: str):
        self.inputs.put(text)

    def _modal_ok(self):
        with self.lock:
            self.modal = None
        self.modal_q.put(1)

    def typed(self, text: str) -> bool:
        if self.prompt is not None:
            self.inputs.put(text)
            return True
        return False

    def back(self):
        self.os.close(self)

    def closing(self):
        self.closed = True
        self.b.stop_flag.set()
        self.inputs.put(None)
        self.events.put(None)
        self.modal_q.put(None)

    def tick(self):
        return True
