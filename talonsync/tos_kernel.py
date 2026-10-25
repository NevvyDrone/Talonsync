"""The TalonOS Enhanced kernel (TalonSync 1.14): processes, the event bus, the settings registry, the clipboard,
notifications, file associations and the public API that every app (built-in, BASIC or Python plugin) goes through.

  Kernel        one per desktop. Owns TalonFS, the process table and the system services.
  Process       one running app: PID, name, kind (system / app / basic / plugin), state, CPU time, faults.
  API           what an app sees as self.api: fs, settings, ui, events, clipboard, notify, launch, open, beep.

A crash in an app's draw / key / tick is caught here: the app is closed with "<name> has a problem" and the rest of
the OS keeps going. Everything an app saves goes through TalonFS or the registry, both inside TalonSync's data folder.
"""
from __future__ import annotations

import os
import time
import traceback
from typing import Callable, Dict, List, Optional

from .tos_fs import FSError, TalonFS, vbasename

API_VERSION = 1


class Process:
    def __init__(self, pid: int, name: str, kind: str, app):
        self.pid, self.name, self.kind, self.app = pid, name, kind, app
        self.state = "running"
        self.started = time.time()
        self.cpu = 0.0                                      # seconds spent in this app's code
        self.faults = 0
        self.last_error = ""

    def info(self) -> dict:
        return {"pid": self.pid, "name": self.name, "kind": self.kind, "state": self.state,
                "cpu_ms": int(self.cpu * 1000), "up_s": int(time.time() - self.started)}


class EventBus:
    """publish(topic, data) calls everyone subscribed to that topic (or to '*'). Subscriptions end with the process."""

    def __init__(self, kernel: "Kernel"):
        self.k = kernel
        self.subs: List[tuple] = []                         # (topic, fn, pid)

    def on(self, topic: str, fn: Callable, pid: int = 0):
        self.subs.append((topic, fn, pid))

    def off_pid(self, pid: int):
        self.subs = [s for s in self.subs if s[2] != pid]

    def emit(self, topic: str, data=None):
        for t, fn, pid in list(self.subs):
            if t == topic or t == "*":
                proc = self.k.procs.get(pid)
                try:
                    fn(topic, data) if t == "*" else fn(data)
                except Exception as e:
                    if proc:
                        self.k.fault(proc, e, where="event")


class Registry:
    """Hierarchical settings ('apps.notepad.wrap'), saved with the desktop's settings in talonos.json."""

    def __init__(self, store: dict, save: Callable[[], None]):
        self.store, self._save = store, save

    def get(self, key: str, default=None):
        return self.store.get(key, default)

    def set(self, key: str, value):
        if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
            raise ValueError("settings can be text, numbers, true/false, lists or tables")
        self.store[key] = value
        self._save()

    def delete(self, key: str):
        self.store.pop(key, None)
        self._save()

    def keys(self, prefix: str = "") -> List[str]:
        return sorted(k for k in self.store if k.startswith(prefix))


class Kernel:
    def __init__(self, desktop):
        self.os = desktop                                   # the window manager (enhanced.Desktop)
        term = desktop.term
        from . import library
        rom = {p["name"].upper() + ".BAS": p["source"] + "\n" for p in library.PROGRAMS}
        self.fs = TalonFS(desktop.folder, programs_dir=term.basic.folder, rom=rom)
        self.events = EventBus(self)
        self.registry = Registry(desktop.registry_store, desktop.save)
        self.procs: Dict[int, Process] = {}
        self.next_pid = 1
        self.clipboard: dict = {"kind": "", "data": ""}
        self.notes: List[tuple] = []                        # (text, until)
        self.errors: List[str] = []
        self.fs.listeners.append(lambda vp: self.events.emit("fs.changed", vp))

    # ------------------------------------------------------------------ processes
    def attach(self, app, name: str, kind: str = "system") -> Process:
        pid = self.next_pid
        self.next_pid += 1
        p = Process(pid, name, kind, app)
        self.procs[pid] = p
        app.pid = pid
        app.api = API(self, app)
        self.events.emit("process.started", p.info())
        return p

    def detach(self, app):
        pid = getattr(app, "pid", None)
        p = self.procs.pop(pid, None)
        if p:
            p.state = "ended"
            self.events.off_pid(pid)
            self.events.emit("process.ended", p.info())

    def proc_of(self, app) -> Optional[Process]:
        return self.procs.get(getattr(app, "pid", None))

    def run(self, app, fn: Callable, *args, where: str = ""):
        """Call into an app: time it, and if it fails, close just that app."""
        p = self.proc_of(app)
        t0 = time.perf_counter()
        try:
            return fn(*args)
        except Exception as e:
            if p:
                self.fault(p, e, where=where)
            else:
                raise
            return None
        finally:
            if p:
                p.cpu += time.perf_counter() - t0

    def fault(self, p: Process, e: Exception, where: str = ""):
        p.faults += 1
        p.last_error = f"{type(e).__name__}: {e}"
        line = f"{time.strftime('%H:%M:%S')} {p.name} (PID {p.pid}) {where}: {p.last_error}"
        self.errors.append(line)
        self.errors = self.errors[-50:]
        try:
            self.fs.append_text("C:\\Temp\\errors.log", line + "\n" + "".join(traceback.format_exception_only(type(e), e)))
        except Exception:
            pass
        if p.state != "running":
            return
        p.state = "not responding"
        app = p.app
        self.os.close(app, force=True)
        self.os.launch("msg", title=p.name, text=f"{p.name} has a problem and was closed. {p.last_error}"[:69])

    def kill(self, pid: int) -> bool:
        p = self.procs.get(pid)
        if not p:
            return False
        self.os.close(p.app, force=True)
        return True

    def list(self) -> List[dict]:
        return [p.info() for p in sorted(self.procs.values(), key=lambda p: p.pid)]

    # ------------------------------------------------------------------ services
    def notify(self, text: str, seconds: float = 3.0):
        self.notes.append((text[:40], time.time() + seconds))
        self.notes = self.notes[-4:]
        self.os.beep()

    def current_note(self) -> Optional[str]:
        now = time.time()
        self.notes = [n for n in self.notes if n[1] > now]
        return self.notes[0][0] if self.notes else None

    def add_recent(self, vpath: str):
        rec = [r for r in self.registry.get("system.recent", []) if r.upper() != vpath.upper()]
        self.registry.set("system.recent", ([vpath] + rec)[:6])

    def open(self, vpath: str, cwd: str = "C:\\Documents", edit: bool = False):
        """Open a file with the app its type belongs to (like a double-click)."""
        vp = self.fs.normalize(vpath, cwd)
        if self.fs.isdir(vp):
            return self.os.launch("explorer", path=vp)
        if not self.fs.exists(vp):
            raise FSError(f"{vp} doesn't exist")
        desc, icon, app_id = self.fs.type_of(vp)
        self.add_recent(vp)
        if app_id == "notepad":
            return self.os.launch("notepad", path=vp)
        if app_id == "basicapp":
            source = self.fs.read_text(vp)
            bad = basic_problem(source)
            if bad and not edit:
                self.os.launch("msg", title="BASIC", text=f"{vbasename(vp)[:16]} has a mistake: {bad}. Edit it?",
                               buttons=("Edit", "Cancel"),
                               done=lambda b: b == "Edit" and self.open(vp, edit=True))
                return None
            if edit or not uses_window(source):
                name = os.path.splitext(vbasename(vp))[0]
                self.os.term.open_source(name, source)
                return None
            return self.os.launch("basicapp", path=vp)
        if app_id == "plugin":
            return self.os.launch_plugin(vp)
        return self.os.launch("notepad", path=vp)


def basic_problem(source: str) -> str:
    """'' when every line of a BASIC program is fine, else the first problem like '?SYNTAX ERROR IN 20'."""
    import re
    from .basic import BasicError, tokenize
    for raw in source.replace("\r", "").split("\n"):
        if not raw.strip():
            continue
        m = re.match(r"\s*(\d+)\s?(.*)$", raw)
        if not m:
            return "a line without a number"
        try:
            tokenize(m.group(2))
        except BasicError as e:
            return f"?{e} ERROR IN {m.group(1)}"
    return ""


def uses_window(source: str) -> bool:
    """A BASIC program that opens a WINDOW runs as a TalonOS app; anything else runs in the BASIC terminal."""
    import re
    for line in source.split("\n"):
        body = re.sub(r'"[^"]*"', "", line.upper())
        if re.search(r"(^|[\s:\d])WINDOW\b", body):
            return True
    return False


# ---------------------------------------------------------------------------------------------------------- the API
class ProcFS:
    """TalonFS for one app, with its own current folder (cwd)."""

    def __init__(self, fs: TalonFS, cwd: str = "C:\\Documents"):
        self._fs, self.cwd = fs, cwd

    def cd(self, path: str) -> str:
        vp = self._fs.normalize(path, self.cwd)
        if not self._fs.isdir(vp):
            raise FSError(f"{vp} isn't a folder")
        self.cwd = vp
        return vp

    def __getattr__(self, name):
        fn = getattr(self._fs, name)
        if name in ("listdir", "read_text", "write_text", "append_text", "mkdir", "rename", "copy", "move", "delete",
                    "exists", "isdir", "stat", "normalize", "real"):
            return lambda *a, **k: fn(*a, cwd=self.cwd, **k) if "cwd" not in k else fn(*a, **k)
        return fn


class Settings:
    def __init__(self, reg: Registry, ns: str):
        self.reg, self.ns = reg, ns

    def get(self, key: str, default=None):
        return self.reg.get(f"{self.ns}.{key}", default)

    def set(self, key: str, value):
        self.reg.set(f"{self.ns}.{key}", value)

    def system(self, key: str, default=None):
        """Read-only: theme, clock24, seconds, sounds..."""
        return self.reg.os.cfg.get(key, default) if hasattr(self.reg, "os") else default


class UIService:
    def __init__(self, k: Kernel):
        self.k = k

    def message(self, text: str, title: str = "TalonOS", buttons=("OK",), done: Optional[Callable[[str], None]] = None):
        self.k.os.launch("msg", title=title, text=text, buttons=tuple(buttons), done=done)

    def prompt(self, prompt: str, done: Callable[[str], None], title: str = "TalonOS", value: str = "", free: bool = False):
        self.k.os.launch("prompt", title=title, prompt=prompt, value=value, done=done, free=free)

    def open_file(self, done: Callable[[str], None], types=(".TXT",), folder: str = "C:\\Documents"):
        self.k.os.launch("filedlg", mode="open", types=tuple(types), folder=folder, done=done)

    def save_file(self, done: Callable[[str], None], name: str = "", types=(".TXT",), folder: str = "C:\\Documents"):
        self.k.os.launch("filedlg", mode="save", types=tuple(types), folder=folder, name=name, done=done)


class API:
    """self.api inside every app. Stable for plugins: see docs/TalonOS_SDK.md (API_VERSION 1)."""
    version = API_VERSION

    def __init__(self, k: Kernel, app):
        self._k, self._app = k, app
        app_id = getattr(app, "app_id", None) or type(app).__name__.lower()
        self.fs = ProcFS(k.fs)
        self.settings = Settings(k.registry, f"apps.{app_id}")
        self.ui = UIService(k)
        self.events = _Events(k, app)

    @property
    def pid(self) -> int:
        return getattr(self._app, "pid", 0)

    def notify(self, text: str):
        self._k.notify(text)

    def beep(self):
        self._k.os.beep()

    def launch(self, app_id: str, **kw):
        return self._k.os.launch(app_id, **kw)

    def open(self, path: str, edit: bool = False):
        return self._k.open(path, self.fs.cwd, edit=edit)

    def clipboard_get(self) -> str:
        return self._k.clipboard.get("data", "") if self._k.clipboard.get("kind") == "text" else ""

    def clipboard_set(self, text: str):
        self._k.clipboard = {"kind": "text", "data": str(text)[:20000]}
        self._k.events.emit("clipboard.changed", "text")

    def system(self, key: str, default=None):
        """Read a system setting: theme, clock24, seconds, sounds, splash, resume."""
        return self._k.os.cfg.get(key, default)

    def clock(self) -> str:
        return self._k.os.clock_text()

    def processes(self) -> List[dict]:
        return self._k.list()

    def log(self, text: str):
        self._k.fs.append_text("C:\\Temp\\apps.log", f"{time.strftime('%H:%M:%S')} {self.pid} {text}\n")


class _Events:
    def __init__(self, k: Kernel, app):
        self.k, self.app = k, app

    def on(self, topic: str, fn: Callable):
        self.k.events.on(topic, fn, getattr(self.app, "pid", 0))

    def emit(self, topic: str, data=None):
        if not topic.startswith("app."):
            raise ValueError("apps can only send app.* events")
        self.k.events.emit(topic, data)
