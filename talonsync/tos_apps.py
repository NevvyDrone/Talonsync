"""TalonOS Enhanced system apps (TalonSync 1.14): Control Panel, My Files (Explorer), Open / Save As, Recycle Bin,
Notepad, Calculator, Date/Time, System Monitor, Task Manager, Run, Help, the BASIC program library, the Games folder
and small dialogs. They use the public API (self.api, see tos_kernel.py) like any third-party app.

Every window is drawn fresh each frame with the toolkit in enhanced.py; the inside of a full window is rows 1-6 and
columns 1-28 (row 7 is the taskbar)."""
from __future__ import annotations

import os
import re
import shutil
import time
from typing import Callable, List, Optional

from . import library
from .enhanced import App, ListState, S, THEMES, THEME_NAMES, UI, nice, wrap
from .tos_fs import FSError, TalonFS, human_size, vbasename, vdirname

DOC_EXT = ".TXT"


def _safe_name(name: str) -> str:
    n = re.sub(r"[^A-Z0-9_]", "", (name or "").upper())[:8]
    return n


# ---------------------------------------------------------------------------------------------------------- dialogs
class MessageBox(App):
    title = "TalonOS"
    icon = "o"
    short = "Note"
    rect = (1, 2, 5, 27)
    single = False

    def __init__(self, os_, title="TalonOS", text="", buttons=("OK",), done: Optional[Callable[[str], None]] = None):
        super().__init__(os_)
        self.title, self.lines, self.buttons, self.done = title, wrap(text, 23)[:5], buttons, done
        if len(self.lines) > 3:                             # a longer message gets a taller box
            self.rect = (0, 2, 6, 27)

    def draw(self, ui: UI, r0, c0, r1, c1):
        for k, line in enumerate(self.lines):
            ui.center(r0 + k, c0, c1, line)
        n = len(self.buttons)
        w = 6
        start = c0 + (c1 - c0 + 1 - (n * w + (n - 1))) // 2
        for k, b in enumerate(self.buttons):
            ui.button(r1, start + k * (w + 1), start + k * (w + 1) + w - 1, b, lambda b=b: self.answer(b))

    def answer(self, b: str):
        self.os.close(self)
        if self.done:
            self.done(b)

    def back(self):
        self.answer(self.buttons[-1])


class Prompt(App):
    """Asks for a short name (8 letters and numbers), like Save As."""
    title = "Save As"
    icon = "D"
    short = "Save"
    rect = (1, 2, 5, 27)
    single = False

    def __init__(self, os_, title="Save As", prompt="File name:", value="", done: Optional[Callable[[str], None]] = None,
                 free: bool = False):
        super().__init__(os_)
        self.title, self.prompt, self.value, self.done, self.free = title, prompt, value, done, free

    def set_value(self, text: str):
        self.value = (text.strip()[:32] if self.free else _safe_name(text)) or self.value

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0 + 1, self.prompt)
        ui.field(r0 + 1, c0 + 1, c1 - 1, self.value, self.set_value, placeholder="type a name")
        ui.label(r0 + 2, c0 + 1, "Up to 32 letters." if self.free else "Letters and numbers, up to 8.")
        ui.button(r1, c0 + 4, c0 + 10, "OK", self.ok)
        ui.button(r1, c1 - 10, c1 - 3, "Cancel", self.back)

    def ok(self):
        if not self.value:
            self.os.beep()
            return
        self.os.close(self)
        if self.done:
            self.done(self.value)


class ShutDown(App):
    title = "Shut Down TalonOS"
    icon = "o"
    short = "Shut"
    rect = (1, 2, 5, 27)

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.icon(r0 + 1, c0 + 1, "o", S.OWL)
        ui.label(r0, c0 + 4, "Shut down TalonOS?")
        ui.label(r0 + 1, c0 + 4, "Your files are saved.")
        ui.button(r1, c0 + 5, c0 + 10, "Yes", self.os.shut_down)
        ui.button(r1, c0 + 13, c0 + 18, "No", self.back)


class About(App):
    title = "About TalonOS"
    icon = "o"
    short = "About"
    rect = (1, 2, 5, 27)

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.icon(r0 + 1, c0 + 1, "o", S.OWL)
        ui.label(r0, c0 + 4, "TalonOS Enhanced", S.FACE_BLUE)
        ui.label(r0 + 1, c0 + 4, f"TalonSync {self.os.version}")
        ui.label(r0 + 2, c0 + 3, "Created by NevvyDrone")
        ui.button(r1, c0 + 9, c0 + 14, "OK", self.back)


# ---------------------------------------------------------------------------------------------------------- Control Panel
class ControlPanel(App):
    title = "Control Panel"
    icon = "G"
    short = "Panel"
    APPLETS = ["Display", "Date/Time", "Sounds", "Start-up", "Storage", "Plugins", "System", "About"]

    def __init__(self, os_, page: str = ""):
        super().__init__(os_)
        self.list = ListState()
        if page in self.APPLETS:
            self.list.sel = self.APPLETS.index(page)

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.listbox(r0, r1, c0, c0 + 9, self.APPLETS, self.list, on_open=lambda i: self._into_pane())
        pane = self.APPLETS[self.list.sel]
        x = c0 + 11
        getattr(self, "_" + re.sub(r"[^a-z]", "", pane.lower()))(ui, r0, x, r1, c1)

    def _into_pane(self):
        self.focus = 1

    def _display(self, ui, r0, x, r1, c1):
        cfg = self.os.cfg
        ui.label(r0, x, "Theme", S.FACE_BLUE)
        for k, t in enumerate(THEMES):
            ui.radio(r0 + 1 + k, x, THEME_NAMES[t], cfg["theme"] == t, lambda t=t: self.os.set("theme", t))
        ui.check(r0 + 4, x, "Start-up", cfg.get("splash", True), lambda v: self.os.set("splash", v))
        ui.label(r0 + 5, x + 4, "screen")

    def _datetime(self, ui, r0, x, r1, c1):
        cfg = self.os.cfg
        ui.label(r0, x, time.strftime("%a %d %b %Y")[:c1 - x + 1], S.FACE_BLUE)
        ui.label(r0 + 1, x, self.os.clock_text())
        ui.check(r0 + 3, x, "24-hour", cfg.get("clock24", False), lambda v: self.os.set("clock24", v))
        ui.check(r0 + 4, x, "Seconds", cfg.get("seconds", False), lambda v: self.os.set("seconds", v))
        ui.label(r0 + 5, x, "Time comes from your PC"[:c1 - x + 1])

    def _sounds(self, ui, r0, x, r1, c1):
        ui.label(r0, x, "Sounds", S.FACE_BLUE)
        ui.check(r0 + 2, x, "Beeps", self.os.cfg.get("sounds", True), lambda v: self.os.set("sounds", v))
        ui.button(r0 + 4, x, x + 5, "Test", self.os.beep)
        ui.label(r0 + 5, x, "The PDA's speaker")

    def _startup(self, ui, r0, x, r1, c1):
        cfg = self.os.cfg
        ui.label(r0, x, "When the PDA")
        ui.label(r0 + 1, x, "switches on:")
        ui.radio(r0 + 2, x, "TalonOS", cfg.get("resume", True), lambda: self.os.set("resume", True))
        ui.radio(r0 + 3, x, "Start menu", not cfg.get("resume", True), lambda: self.os.set("resume", False))
        ui.label(r0 + 5, x, "(if TalonOS was on)")

    def _storage(self, ui, r0, x, r1, c1):
        from .tos_fs import MAX_DRIVE
        fs = self.os.kernel.fs
        used = fs.used()
        ui.label(r0, x, "Drive C:", S.FACE_BLUE)
        ui.progress(r0 + 1, x, c1, used / MAX_DRIVE)
        ui.label(r0 + 2, x, f"{human_size(used)} of 64M used"[:c1 - x + 1])
        ui.label(r0 + 3, x, f"Bin: {len(fs.bin_items())} items"[:c1 - x + 1])
        ui.button(r1 - 1, x, x + 8, "Open C:", lambda: self.os.launch("explorer", path="C:\\"))
        ui.button(r1, x, x + 10, "Empty bin", lambda: self.os.launch("bin"))

    def _plugins(self, ui, r0, x, r1, c1):
        cfg = self.os.cfg
        ui.check(r0, x, "Allow Python", cfg.get("plugins", False), self._allow)
        ui.label(r0 + 1, x + 4, "plugins")
        from .tos_plugins import list_plugins
        n = len(list_plugins(self.os))
        ui.label(r0 + 2, x, f"{n} in C:\\Apps"[:c1 - x + 1])
        ui.label(r0 + 3, x, "Only run ones")
        ui.label(r0 + 4, x, "you trust!")
        ui.button(r1, x, x + 11, "Forget trust", self._forget)

    def _allow(self, v: bool):
        if not v:
            self.os.set("plugins", False)
            return
        def answer(b):
            if b == "Yes":
                self.os.set("plugins", True)
        self.api.ui.message("Python plugins can run any code on your PC. Allow them?", title="Plugins",
                            buttons=("Yes", "No"), done=answer)

    def _forget(self):
        self.os.kernel.registry.set("system.trusted_plugins", {})
        self.api.notify("Plugins will ask again")

    def _system(self, ui, r0, x, r1, c1):
        w = c1 - x + 1
        ui.label(r0, x, f"TalonSync {self.os.version}"[:w], S.FACE_BLUE)
        try:
            import psutil
            ui.label(r0 + 1, x, f"PC CPU {psutil.cpu_percent(interval=None):.0f}%  RAM {psutil.virtual_memory().percent:.0f}%"[:w])
        except Exception:
            ui.label(r0 + 1, x, "PC load: n/a")
        from .basic import MEMORY
        ui.label(r0 + 2, x, f"BASIC {MEMORY - self.os.term.basic.used()} free"[:w])
        m = int(time.time() - self.os.term.started) // 60
        ui.label(r0 + 3, x, f"Up {m // 60}h {m % 60:02d}m"[:w])
        ui.label(r0 + 4, x, f"Processes {len(self.os.kernel.procs)}"[:w])
        ui.button(r1, x, x + 7, "Tasks", lambda: self.os.launch("taskmgr"))
        ui.button(r1, x + 9, c1, "Monitor", lambda: self.os.launch("sysmon"))

    def _about(self, ui, r0, x, r1, c1):
        ui.icon(r0 + 1, x + 1, "o", S.OWL)
        ui.label(r0, x + 4, "TalonOS")
        ui.label(r0 + 1, x + 4, "Enhanced")
        ui.label(r0 + 3, x, "Created by")
        ui.label(r0 + 4, x, "NevvyDrone")
        ui.label(r0 + 5, x, f"TalonSync {self.os.version}"[:c1 - x + 1])

    def tick(self):
        return True


# ---------------------------------------------------------------------------------------------------------- files
def fs_rows(entries) -> List[str]:
    out = []
    for e in entries:
        tail = "<DIR>" if e.is_dir else human_size(e.size)
        out.append(f"{e.name[:21]:<21}{tail:>6}")
    return out


class Browser:
    """Folder browsing shared by Explorer and the Open / Save dialogs."""

    def __init__(self, app: App, folder: str, types=None):
        self.app, self.types = app, tuple(t.upper() for t in types) if types else None
        self.list = ListState()
        self.folder = app.api.fs.normalize(folder or "C:\\Documents")
        self.entries = []
        self.error = ""
        self.refresh()

    def refresh(self):
        try:
            es = self.app.api.fs.listdir(self.folder)
            self.entries = [e for e in es if e.is_dir or not self.types or e.ext in self.types]
            self.error = ""
        except FSError as e:
            self.entries, self.error = [], str(e)

    def sel(self):
        return self.entries[self.list.sel] if self.entries else None

    def go(self, path: str):
        fs = self.app.api.fs
        vp = fs.normalize(path, cwd=self.folder)
        if not fs.isdir(vp):
            raise FSError(f"{vp} isn't a folder")
        self.folder, self.list = vp, ListState()
        self.refresh()

    def up(self):
        drive, parts = TalonFS.split(self.folder)
        if parts:
            self.go(TalonFS.join(drive, parts[:-1]))
        elif drive == "A":
            self.go("C:\\")
        else:
            self.go("A:\\")


class Explorer(App):
    """My Files: drives, folders and files. Open uses the file's type (Notepad, a BASIC app, a plugin)."""
    title = "My Files"
    icon = "f"
    short = "Files"
    single = False

    def __init__(self, os_, path: str = "C:\\Documents"):
        super().__init__(os_)
        self.b = Browser(self, path)
        self.api.events.on("fs.changed", lambda vp: self.b.refresh())
        self.status = ""

    @property
    def items(self):                                        # (name, kind, path) like the 1.13 My Files
        return [(e.name.upper(), e.kind, e.path) for e in self.b.entries]

    @property
    def list(self):
        return self.b.list

    def refresh(self):
        self.b.refresh()

    @property
    def title(self):
        return f"{self.b.folder} - My Files" if len(self.b.folder) < 14 else self.b.folder

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.button(r0, c0, c0 + 3, "Up", self.up_)
        ui.sc.fill(r0, c0 + 5, r0, c1, S.FIELD)
        ui.label(r0, c0 + 5, (self.status or self.b.error or self.b.folder)[-(c1 - c0 - 4):], S.FIELD)
        ui.listbox(r0 + 1, r1 - 1, c0, c1, fs_rows(self.b.entries), self.b.list, on_open=lambda i: self.open())
        has = bool(self.b.entries)
        clip = self.os.kernel.clipboard.get("kind") == "file"
        ui.button(r1, c0, c0 + 3, "Open", self.open, enabled=has)
        ui.button(r1, c0 + 5, c0 + 7, "New", self.new)
        ui.button(r1, c0 + 9, c0 + 11, "Ren", self.rename, enabled=has)
        ui.button(r1, c0 + 13, c0 + 15, "Del", self.delete, enabled=has)
        ui.button(r1, c0 + 17, c0 + 21, "Paste" if clip else "Copy", self.paste if clip else self.copy, enabled=has or clip)
        ui.button(r1, c0 + 23, c1, "Edit", self.edit, enabled=has and (self.b.sel().ext == ".BAS" if has else False))

    def _try(self, fn, *a):
        try:
            fn(*a)
            self.status = ""
        except FSError as e:
            self.status = str(e)
            self.os.beep()

    def up_(self):
        self._try(self.b.up)

    def open(self):
        e = self.b.sel()
        if not e:
            return
        if e.is_dir:
            self._try(self.b.go, e.path)
        else:
            self._try(self.os.kernel.open, e.path)

    def edit(self):
        e = self.b.sel()
        if e and e.ext == ".BAS":
            self._try(lambda: self.os.kernel.open(e.path, edit=True))

    def run(self):
        e = self.b.sel()
        if e and e.ext == ".BAS":
            src = self.api.fs.read_text(e.path)
            self.os.term.open_source(os.path.splitext(e.name)[0], src, run=True)

    def new(self):
        def made(name):
            self._try(self.api.fs.mkdir, self.b.folder + "\\" + name)
        self.api.ui.prompt("Name for the new folder:", made, title="New Folder", free=True)

    def rename(self):
        e = self.b.sel()
        if not e:
            return
        self.api.ui.prompt(f"New name for {e.name[:14]}:", lambda n: self._try(self.api.fs.rename, e.path, n),
                           title="Rename", value=e.name, free=True)

    def delete(self):
        e = self.b.sel()
        if not e:
            return
        perm = self.b.folder.upper().startswith("C:\\RECYCLED")

        def yes(b):
            if b == "Yes":
                self._try(self.api.fs.delete, e.path)
        self.api.ui.message(f"{'Delete' if perm else 'Move'} {e.name[:16]}{' for good' if perm else ' to the Recycle Bin'}?",
                            title="Delete", buttons=("Yes", "No"), done=yes)

    def copy(self):
        e = self.b.sel()
        if e and not e.is_dir:
            self.os.kernel.clipboard = {"kind": "file", "data": e.path}
            self.status = f"Copied {e.name}"

    def paste(self):
        src = self.os.kernel.clipboard.get("data", "")
        self._try(lambda: self.api.fs.copy(src, self.b.folder))
        self.os.kernel.clipboard = {"kind": "", "data": ""}

    def typed(self, text: str) -> bool:
        t = text.strip()
        if t:
            self._try(self.b.go, t)                         # type a path to go there
        return True


class FileDialog(App):
    """Open or Save As: browse folders, pick or type a file name."""
    title = "Open"
    icon = "f"
    short = "Open"
    single = False

    def __init__(self, os_, mode="open", types=(".TXT",), folder="C:\\Documents", name="", done=None):
        super().__init__(os_)
        self.mode, self.done = mode, done
        self.title = "Open" if mode == "open" else "Save As"
        self.short = self.title[:5]
        self.b = Browser(self, folder, types if mode == "open" else None)
        self.types = types
        self.name = name
        self.focus = 2 if mode == "save" else 1             # Save As starts in the name box, Open in the list

    def set_name(self, text: str):
        self.name = text.strip()[:32]

    def typed(self, text: str) -> bool:                    # typing anywhere in the dialog is the file name
        if text.strip():
            self.set_name(text)
            self.ok()
        return True

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.button(r0, c0, c0 + 3, "Up", lambda: self._go_up())
        ui.sc.fill(r0, c0 + 5, r0, c1, S.FIELD)
        ui.label(r0, c0 + 5, (self.b.error or self.b.folder)[-(c1 - c0 - 4):], S.FIELD)
        ui.listbox(r0 + 1, r1 - 2, c0, c1, fs_rows(self.b.entries), self.b.list, on_open=lambda i: self.pick(),
                   on_select=lambda i: self._sync())
        ui.label(r1 - 1, c0, "Name")
        ui.field(r1 - 1, c0 + 5, c1, self.name, self.set_name, placeholder="type a file name")
        ui.button(r1, c0 + 8, c0 + 15, "Open" if self.mode == "open" else "Save", self.ok)
        ui.button(r1, c0 + 17, c0 + 24, "Cancel", self.back)

    def _go_up(self):
        try:
            self.b.up()
        except FSError:
            self.os.beep()

    def _sync(self):
        e = self.b.sel()
        if e and not e.is_dir:
            self.name = e.name

    def pick(self):
        e = self.b.sel()
        if not e:
            return
        if e.is_dir:
            self.b.go(e.path)
        else:
            self.name = e.name
            self.ok()

    def ok(self):
        if not self.name:
            self.os.beep()
            return
        name = self.name
        if self.mode == "save" and self.types and not os.path.splitext(name)[1]:
            name += self.types[0].lower()
        try:
            path = self.api.fs.normalize(name, cwd=self.b.folder)
            if self.mode == "open" and not self.api.fs.exists(path):
                raise FSError(f"{name} isn't here")
            if self.mode == "open" and self.api.fs.isdir(path):
                self.b.go(path)
                return
        except FSError as e:
            self.b.error = str(e)
            self.os.beep()
            return
        if self.mode == "save" and self.api.fs.exists(path):
            def answer(b):
                if b == "Yes":
                    self._finish(path)
            self.api.ui.message(f"{name[:20]} is already there. Replace it?", title="Save As", buttons=("Yes", "No"), done=answer)
            return
        self._finish(path)

    def _finish(self, path):
        self.os.close(self)
        if self.done:
            self.done(path)


class RecycleBin(App):
    title = "Recycle Bin"
    icon = "r"
    short = "Bin"

    def __init__(self, os_):
        super().__init__(os_)
        self.list = ListState()

    def items(self):
        return [n for n, orig in self.os.kernel.fs.bin_items()]

    def draw(self, ui: UI, r0, c0, r1, c1):
        items = self.os.kernel.fs.bin_items()
        if not items:
            ui.icon(r0 + 1, c0 + 3, "r")
            ui.label(r0 + 1, c0 + 7, "The bin is empty. Hoo!")
            ui.button(r1, c0 + 10, c0 + 17, "OK", self.back)
            return
        ui.listbox(r0, r1 - 2, c0, c1, [n for n, o in items], self.list, on_open=lambda i: self.restore())
        orig = items[min(self.list.sel, len(items) - 1)][1]
        ui.label(r1 - 1, c0, ("From " + orig)[:c1 - c0 + 1])
        ui.button(r1, c0, c0 + 8, "Restore", self.restore)
        ui.button(r1, c0 + 10, c0 + 16, "Empty", self.empty)
        ui.button(r1, c0 + 18, c1, "Close", self.back)

    def restore(self):
        items = self.items()
        if items:
            try:
                self.os.kernel.fs.restore(items[min(self.list.sel, len(items) - 1)])
            except FSError:
                self.os.beep()

    def empty(self):
        def yes(b):
            if b == "Yes":
                self.os.kernel.fs.empty_bin()
        self.api.ui.message("Delete everything in the bin for good?", title="Empty Bin", buttons=("Yes", "No"), done=yes)


# ---------------------------------------------------------------------------------------------------------- Notepad
class Notepad(App):
    title = "Notepad"
    icon = "D"
    short = "Notes"
    single = False
    WIDTH = 28

    def __init__(self, os_, path: str = ""):
        super().__init__(os_)
        self.path = ""
        self.lines: List[str] = [""]
        self.cur = 0
        self.top = 0
        self.changed = False
        if path:
            self.load(path)
        self._title()

    def load(self, path: str):
        try:
            text = self.api.fs.read_text(path)
            self.path = self.api.fs.normalize(path)
            self.lines = text.split("\n") or [""]
            if len(self.lines) > 1 and self.lines[-1] == "":
                self.lines.pop()
            self.cur, self.changed = len(self.lines) - 1, False
            if self.path.upper().startswith("A:"):
                self.path = ""                               # the ROM disk is read only: Save asks for a name
        except FSError as e:
            self.api.ui.message(str(e), title="Notepad")
        self._title()

    def _title(self):
        name = os.path.basename(self.path.replace("\\", "/")) if self.path else "Untitled"
        self.title = f"{name}{'*' if self.changed else ''} - Notepad"

    def draw(self, ui: UI, r0, c0, r1, c1):
        h = r1 - r0                                           # text rows (the last row has the buttons)
        i = len(ui.focusables)
        focus = ui._take("text", lambda: self.new_line())
        self.cur = max(0, min(self.cur, len(self.lines) - 1))
        if self.cur < self.top:
            self.top = self.cur
        if self.cur >= self.top + h:
            self.top = self.cur - h + 1
        ui.sc.fill(r0, c0, r1 - 1, c1, S.FIELD)
        for k in range(h):
            j = self.top + k
            if j >= len(self.lines):
                break
            line = self.lines[j][:c1 - c0 + 1]
            ui.sc.text(r0 + k, c0, line, S.FIELD)
            if j == self.cur and focus and len(line) <= c1 - c0:
                ui.sc.text(r0 + k, c0 + len(line), "_", S.FIELD)

            def tap(j=j):
                self.focus = i
                self.cur = j
            ui.spot(r0 + k, c0, r0 + k, c1, tap)
        ui.button(r1, c0, c0 + 3, "New", self.new)
        ui.button(r1, c0 + 5, c0 + 8, "Open", self.open)
        ui.button(r1, c0 + 10, c0 + 13, "Save", self.save)
        ui.button(r1, c0 + 15, c0 + 18, "Cut", self.cut)
        ui.button(r1, c0 + 20, c1, "Paste", self.paste, enabled=bool(self.api.clipboard_get()))

    def key(self, k: str) -> bool:
        if self.focus != 0 or k not in ("up", "down"):
            return False
        d = 1 if k == "down" else -1
        if 0 <= self.cur + d < len(self.lines):
            self.cur += d
            return True
        return False

    def typed(self, text: str) -> bool:
        if self.focus != 0:
            return False
        if not text:
            self.new_line()
            return True
        line = self.lines[self.cur] + text
        parts = wrap(line, self.WIDTH) if len(line) > self.WIDTH else [line]
        self.lines[self.cur:self.cur + 1] = parts
        self.cur += len(parts) - 1
        self.lines.insert(self.cur + 1, "")
        self.cur += 1
        self._dirty()
        return True

    def _dirty(self):
        self.changed = True
        self._title()

    def new_line(self):
        self.lines.insert(self.cur + 1, "")
        self.cur += 1
        self._dirty()

    def cut(self):
        self.api.clipboard_set(self.lines[self.cur])
        if len(self.lines) > 1:
            del self.lines[self.cur]
            self.cur = min(self.cur, len(self.lines) - 1)
        else:
            self.lines = [""]
        self._dirty()

    def paste(self):
        text = self.api.clipboard_get()
        if text:
            for k, line in enumerate(text.split("\n")):
                self.lines.insert(self.cur + 1 + k, line[:120])
            self.cur += 1
            self._dirty()

    def del_line(self):
        if len(self.lines) > 1:
            del self.lines[self.cur]
            self.cur = min(self.cur, len(self.lines) - 1)
        else:
            self.lines = [""]
        self._dirty()

    def new(self):
        self.os.launch("notepad", path="")

    def open(self):
        self.api.ui.open_file(lambda p: self.load(p), types=(".TXT", ".LOG", ".INI", ".BAS"),
                              folder=vdirname(self.path) if self.path else "C:\\Documents")

    def save(self, then: Optional[Callable] = None):
        if not self.path:
            def named(p):
                self.path = p
                self.save(then)
            self.api.ui.save_file(named, types=(".TXT",))
            return
        try:
            lines = list(self.lines)
            while len(lines) > 1 and lines[-1] == "":
                lines.pop()
            self.path = self.api.fs.write_text(self.path, "\n".join(lines) + "\n")
            self.os.kernel.add_recent(self.path)
            self.changed = False
            self._title()
            if then:
                then()
        except FSError as e:
            self.api.ui.message(str(e), title="Notepad")

    def back(self):
        if not self.changed or not any(l.strip() for l in self.lines):
            self.os.close(self)
            return

        def answer(b):
            if b == "Yes":
                self.save(then=lambda: self.os.close(self))
            elif b == "No":
                self.os.close(self)
        self.api.ui.message("Save your changes first?", title="Notepad", buttons=("Yes", "No", "Back"), done=answer)


# ---------------------------------------------------------------------------------------------------------- Calculator
class Calculator(App):
    title = "Calculator"
    icon = "E"
    short = "Calc"
    rect = (0, 5, 6, 24)
    KEYS = [["7", "8", "9", "/"], ["4", "5", "6", "*"], ["1", "2", "3", "-"], ["0", ".", "=", "+"]]

    def __init__(self, os_):
        super().__init__(os_)
        self.shown = "0"
        self.acc: Optional[float] = None
        self.op = ""
        self.fresh = True

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.sc.fill(r0, c0, r0, c1 - 4, S.FIELD)
        ui.sc.text(r0, c1 - 4 - len(self.shown[-13:]) + 1, self.shown[-13:], S.FIELD)
        ui.button(r0, c1 - 2, c1, "C", self.clear)
        for rr, row in enumerate(self.KEYS):
            for k, key in enumerate(row):
                x = c0 + k * 5
                ui.button(r0 + 1 + rr, x, x + 2, key, lambda key=key: self.press(key))
        ui.button(r1, c0, c0 + 5, "Back", lambda: self.press("<"))
        ui.button(r1, c0 + 7, c0 + 10, "+-", lambda: self.press("~"))
        ui.button(r1, c0 + 12, c0 + 14, "%", lambda: self.press("%"))

    @staticmethod
    def fmt(v: float) -> str:
        if v != v or abs(v) == float("inf"):
            return "Error"
        if abs(v) >= 1e12:
            return f"{v:.6g}"
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s

    def clear(self):
        self.shown, self.acc, self.op, self.fresh = "0", None, "", True

    def _val(self) -> float:
        try:
            return float(self.shown)
        except ValueError:
            return 0.0

    def press(self, key: str):
        if self.shown == "Error" and key not in "0123456789":
            self.clear()
            return
        if key.isdigit() or key == ".":
            if self.fresh or self.shown == "0":
                self.shown = "0." if key == "." else key
                self.fresh = False
            elif not (key == "." and "." in self.shown) and len(self.shown) < 13:
                self.shown += key
        elif key in "+-*/":
            self._apply()
            self.op, self.fresh = key, True
        elif key == "=":
            if self.op:
                self._apply()
            self.op, self.fresh = "", True
        elif key == "<":
            self.shown = self.shown[:-1] if len(self.shown) > 1 and not self.fresh else "0"
        elif key == "~":
            self.shown = self.fmt(-self._val())
        elif key == "%":
            base = self.acc if self.acc is not None else 0.0
            self.shown = self.fmt(base * self._val() / 100.0)

    def _apply(self):
        """Finish the pending sum with the number on display (a second operator in a row just replaces the first)."""
        v = self._val()
        if not self.op or self.acc is None:
            self.acc = v
            return
        if self.fresh:
            return
        a = self.acc
        try:
            r = {"+": a + v, "-": a - v, "*": a * v, "/": a / v if v else float("nan")}[self.op]
        except Exception:
            r = float("nan")
        self.acc = r
        self.shown = self.fmt(r)
        if self.shown == "Error":
            self.acc, self.op = None, ""

    def typed(self, text: str) -> bool:
        for ch in text.replace("x", "*").replace("X", "*").replace(" ", ""):
            if ch in "0123456789.+-*/=%":
                self.press(ch)
            elif ch.upper() == "C":
                self.clear()
        return True


# ---------------------------------------------------------------------------------------------------------- Date/Time
class Clock(App):
    title = "Date/Time"
    icon = "F"
    short = "Clock"
    rect = (1, 3, 5, 26)

    def draw(self, ui: UI, r0, c0, r1, c1):
        d = time.strftime("%A, %B ") + str(int(time.strftime("%d"))) + time.strftime(", %Y")
        ui.center(r0, c0, c1, d[:c1 - c0 + 1])
        t = self.os.clock_text()
        ui.sc.fill(r0 + 1, c0 + 4, r0 + 1, c1 - 4, S.FIELD)
        ui.center(r0 + 1, c0 + 4, c1 - 4, t, S.FIELD)
        ui.center(r0 + 2, c0, c1, time.strftime("Week %W, day %j"))
        ui.button(r1, c0 + 2, c0 + 10, "Settings", lambda: self.os.launch("control", page="Date/Time"))
        ui.button(r1, c1 - 7, c1 - 2, "OK", self.back)

    def tick(self):
        return True


# ---------------------------------------------------------------------------------------------------------- System Monitor
class SysMon(App):
    title = "System Monitor"
    icon = "K"
    short = "Mon"

    def __init__(self, os_):
        super().__init__(os_)
        self.cpu, self.ram = 0.0, 0.0
        self.tick()

    def tick(self):
        try:
            import psutil
            self.cpu = psutil.cpu_percent(interval=None)
            self.ram = psutil.virtual_memory().percent
        except Exception:
            pass
        return True

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, "PC CPU")
        ui.progress(r0, c0 + 8, c1 - 5, self.cpu / 100.0)
        ui.label(r0, c1 - 3, f"{self.cpu:3.0f}%"[-4:])
        ui.label(r0 + 1, c0, "PC RAM")
        ui.progress(r0 + 1, c0 + 8, c1 - 5, self.ram / 100.0)
        ui.label(r0 + 1, c1 - 3, f"{self.ram:3.0f}%"[-4:])
        m = int(time.time() - self.os.term.started) // 60
        ui.label(r0 + 2, c0, f"TalonSync up {m // 60}h {m % 60:02d}m")
        link = getattr(self.os.term.app, "link", None)
        ui.label(r0 + 3, c0, "PDA link: " + ("on" if link else "none (PC only)"))
        ui.label(r0 + 4, c0, f"Windows open: {len(self.os.apps)}")
        ui.button(r1, c0 + 10, c0 + 17, "OK", self.back)


# ---------------------------------------------------------------------------------------------------------- Help
HELP_PAGES = [
    ("Welcome", "TalonOS Enhanced runs on your PC through TalonSync; your PDA is its screen. Tap anything to use it."),
    ("Buttons", "Up/Down move between controls. Center presses. Left goes back or closes. Right opens Start."),
    ("Typing", "Type on the PDA keyboard and press Done: the text goes into the box with the cursor."),
    ("Windows", "The _ button hides a window; its taskbar button brings it back. x closes it."),
    ("Programs", "Games and tools are in Start. BASIC and the Terminal run full screen; Left comes back."),
    ("Settings", "Control Panel changes the theme, the clock and sounds. Skyglass is glossy; Classic is grey."),
    ("Shortcuts", "On the desktop type a program's name, like NOTEPAD or CALC. TALONOS comes back here anywhere."),
]


class Help(App):
    title = "TalonOS Help"
    icon = "C"
    short = "Help"

    def __init__(self, os_):
        super().__init__(os_)
        self.page = 0

    def draw(self, ui: UI, r0, c0, r1, c1):
        name, text = HELP_PAGES[self.page]
        ui.label(r0, c0, f"{name}"[:20], S.FACE_BLUE)
        ui.label(r0, c1 - 4, f"{self.page + 1}/{len(HELP_PAGES)}")
        for k, line in enumerate(wrap(text, c1 - c0 + 1)[:4]):
            ui.label(r0 + 1 + k, c0, line)
        ui.button(r1, c0, c0 + 7, "< Back", lambda: self.turn(-1), enabled=self.page > 0)
        ui.button(r1, c0 + 9, c0 + 16, "Next >", lambda: self.turn(1), enabled=self.page < len(HELP_PAGES) - 1)
        ui.button(r1, c0 + 18, c0 + 21, "OK", self.os_close)
        ui.button(r1, c0 + 23, c1, "About", lambda: self.os.launch("about"))

    def os_close(self):
        self.os.close(self)

    def turn(self, d):
        self.page = max(0, min(len(HELP_PAGES) - 1, self.page + d))


# ---------------------------------------------------------------------------------------------------------- BASIC library
class ProgramLibrary(App):
    """The BASIC programs (games, demos and the BASIC tour). They run full screen in BASIC and come back here."""
    title = "BASIC Programs"
    icon = "f"
    short = "Progs"

    def __init__(self, os_):
        super().__init__(os_)
        self.list = ListState()
        os_.term._export_library()                         # so LOAD "GUESS" works in BASIC too

    @property
    def lib_sel(self):
        return self.list.sel

    def draw(self, ui: UI, r0, c0, r1, c1):
        progs = library.PROGRAMS
        rows = [f"{i + 1:>2} {nice(p['title'])[:16]:<16}{p['kind'].capitalize():>6}" for i, p in enumerate(progs)]
        ui.listbox(r0, r1 - 2, c0, c1, rows, self.list, on_open=lambda i: self.do("R"))
        about = progs[self.list.sel]["about"]
        line = wrap(about, c1 - c0 + 1)[0]
        if len(about) > len(line):
            line = line[:c1 - c0 - 2].rstrip() + "..."
        ui.label(r1 - 1, c0, line)
        ui.button(r1, c0, c0 + 5, "Run", lambda: self.do("R"))
        ui.button(r1, c0 + 7, c0 + 12, "List", lambda: self.do("L"))
        ui.button(r1, c0 + 14, c0 + 19, "Edit", lambda: self.do("E"))
        ui.button(r1, c0 + 21, c1, "Close", self.back)

    def do(self, key: str):
        self.os.term.leave_gui("program", library.PROGRAMS[self.list.sel], key)

    def typed(self, text: str) -> bool:
        t = text.strip().upper()
        if t.isdigit() and library.by_number(int(t)):
            self.list.sel = int(t) - 1
        elif t and t[0] in "RLE":
            self.do(t[0])
        elif t and t[0] in "XQC":
            self.back()
        return True


# ---------------------------------------------------------------------------------------------------------- Games folder
class GamesFolder(App):
    title = "Games"
    icon = "M"
    short = "Games"

    def __init__(self, os_):
        super().__init__(os_)
        self.list = ListState()

    def draw(self, ui: UI, r0, c0, r1, c1):
        ids = START_GAMES
        rows = [f"{REGISTRY[g]['name']:<16}{REGISTRY[g].get('best', '')}" for g in ids]
        ui.listbox(r0, r1 - 2, c0, c1, rows, self.list, on_open=lambda i: self.play())
        ui.label(r1 - 1, c0, REGISTRY[ids[self.list.sel]].get("blurb", "")[:c1 - c0 + 1])
        ui.button(r1, c0, c0 + 6, "Play", self.play)
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def play(self):
        self.os.launch(START_GAMES[self.list.sel])


# ---------------------------------------------------------------------------------------------------------- Task Manager
class TaskManager(App):
    title = "Task Manager"
    icon = "K"
    short = "Tasks"

    def __init__(self, os_):
        super().__init__(os_)
        self.list = ListState()
        self.rows: List[dict] = []

    def tick(self):
        return True

    def draw(self, ui: UI, r0, c0, r1, c1):
        self.rows = self.os.kernel.list()
        ui.label(r0, c0, "PID Name            CPU ms")
        rows = [f"{p['pid']:>3} {p['name'][:15]:<15}{p['cpu_ms']:>8}" for p in self.rows]
        ui.listbox(r0 + 1, r1 - 1, c0, c1, rows, self.list, on_open=lambda i: self.end())
        ui.button(r1, c0, c0 + 8, "End task", self.end, enabled=bool(self.rows))
        ui.label(r1, c0 + 10, f"{len(self.rows)} running")
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def end(self):
        if not self.rows:
            return
        p = self.rows[min(self.list.sel, len(self.rows) - 1)]
        if p["pid"] == self.pid:
            self.back()
            return
        self.os.kernel.kill(p["pid"])
        self.api.notify(f"Ended {p['name'][:20]}")


class RunDialog(App):
    """Start > Run: a program name, a file path or a folder."""
    title = "Run"
    icon = "p"
    short = "Run"
    rect = (1, 2, 5, 27)

    def __init__(self, os_):
        super().__init__(os_)
        self.value = ""
        self.error = ""

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, "Type a program, file or folder:")
        ui.field(r0 + 1, c0, c1, self.value, self.set_value, placeholder="NOTEPAD or C:\\Apps\\X.BAS")
        ui.label(r0 + 2, c0, self.error[:c1 - c0 + 1])
        ui.button(r1, c0 + 4, c0 + 9, "OK", self.ok)
        ui.button(r1, c0 + 12, c0 + 19, "Cancel", self.back)

    def set_value(self, text: str):
        self.value = text.strip()
        self.ok()

    def ok(self):
        v = self.value.strip()
        if not v:
            return
        if ":" in v or "\\" in v or "." in v:
            try:
                self.os.close(self)
                self.os.kernel.open(v)
            except FSError as e:
                self.os.launch("msg", title="Run", text=str(e))
            return
        before = len(self.os.apps)
        self.os.close(self)
        self.os._shortcut(v)
        if len(self.os.apps) < before and self.os.term.mode == "gui":
            self.os.launch("msg", title="Run", text=f"TalonOS can't find {v[:20]}.")


# ---------------------------------------------------------------------------------------------------------- registry
from . import tos_games  # noqa: E402  (games use the toolkit above)

REGISTRY = {
    "control": {"cls": ControlPanel, "name": "Control Panel", "words": ["SETTINGS", "PANEL", "CONTROL"]},
    "explorer": {"cls": Explorer, "name": "My Files", "words": ["FILES", "EXPLORER", "COMPUTER"]},
    "files": {"cls": Explorer, "name": "My Files", "words": ["DOCUMENTS"], "hidden": True},
    "filedlg": {"cls": FileDialog, "name": "Open", "words": [], "hidden": True},
    "taskmgr": {"cls": TaskManager, "name": "Task Manager", "words": ["TASKMGR", "TASKS", "PROCESSES"]},
    "run": {"cls": RunDialog, "name": "Run...", "words": ["RUN"]},
    "bin": {"cls": RecycleBin, "name": "Recycle Bin", "words": ["BIN", "TRASH"]},
    "notepad": {"cls": Notepad, "name": "Notepad", "words": ["NOTES", "EDIT"]},
    "calc": {"cls": Calculator, "name": "Calculator", "words": ["CALC"]},
    "clock": {"cls": Clock, "name": "Date/Time", "words": ["CLOCK", "TIME", "DATE"]},
    "sysmon": {"cls": SysMon, "name": "System Monitor", "words": ["MONITOR", "SYSMON"]},
    "help": {"cls": Help, "name": "Help", "words": ["HELP"]},
    "about": {"cls": About, "name": "About TalonOS", "words": ["ABOUT", "VER"]},
    "library": {"cls": ProgramLibrary, "name": "BASIC Programs", "words": ["PROGRAMS", "LIBRARY"]},
    "games": {"cls": GamesFolder, "name": "Games", "words": ["GAMES"]},
    "shutdown": {"cls": ShutDown, "name": "Shut Down", "words": ["SHUTDOWN"]},
    "msg": {"cls": MessageBox, "name": "Message", "words": [], "hidden": True},
    "basicapp": {"cls": None, "name": "BASIC app", "words": [], "hidden": True, "kind": "basic"},
    "prompt": {"cls": Prompt, "name": "Prompt", "words": [], "hidden": True},
}
REGISTRY.update(tos_games.GAMES)
from .tos_basicapp import BasicApp  # noqa: E402
REGISTRY["basicapp"]["cls"] = BasicApp
START_GAMES = list(tos_games.GAMES.keys())

def start_menu(desktop):
    """The Start menu, built each time it opens: installed apps and recent documents change."""
    from .tos_basicapp import installed_apps
    apps = installed_apps(desktop)
    recent = desktop.kernel.registry.get("system.recent", [])

    def opener(p):
        return lambda: desktop.kernel.open(p)
    docs = [(os.path.basename(p.replace("\\", "/"))[:16], opener(p)) for p in recent]
    docs.append(("My Documents", lambda: desktop.launch("explorer", path="C:\\Documents")))
    return [                     # like the classic Start menu: label, underlined letter, app or submenu
        ("Programs", 0, ["library", "basic", "terminal", "explorer", "taskmgr"] + apps),
        ("Accessories", 0, ["notepad", "calc", "clock", "sysmon"]),
        ("Games", 0, START_GAMES),
        ("Documents", 0, docs),
        ("Settings", 0, ["control", "help", "about"]),
        ("Run...", 0, "run"),
        ("Shut Down...", 2, "shutdown"),
    ]


START_MENU = []                  # kept for older imports; the menu is start_menu(desktop) now
REGISTRY["basic"] = {"cls": None, "name": "BASIC", "words": ["CODE"]}
REGISTRY["terminal"] = {"cls": None, "name": "Terminal", "words": ["CMD", "PROMPT", "DOS"]}
