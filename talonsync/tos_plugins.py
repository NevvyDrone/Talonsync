"""Python plugins for TalonOS Enhanced (TalonSync 1.14).

A plugin is a .py file in C:\\Apps. It is off until you switch on Control Panel > Plugins > Allow Python plugins, and
each plugin asks once before it first runs (and again whenever the file changes). A plugin runs inside TalonSync with
everything Python can do, so only run plugins from people you trust.

A plugin defines NAME (optional), ICON (optional) and a class Main(App) from talonsync.tos_sdk. If it crashes, only
its window closes.
"""
from __future__ import annotations

import hashlib
import os
import types

from .tos_fs import FSError

SAMPLE_PLUGIN = '''"""Hello Plugin: a sample Python plugin for TalonOS Enhanced. Python plugins are off until you switch them on
in Control Panel > Plugins, and each one asks before it runs. See docs/TalonOS_SDK.md in TalonSync."""
from talonsync.tos_sdk import App, S

NAME = "Hello Plugin"
ICON = "K"


class Main(App):
    title = "Hello Plugin"
    short = "Hello"

    def __init__(self, os_):
        super().__init__(os_)
        self.count = self.api.settings.get("count", 0)        # saved between sessions

    def draw(self, ui, r0, c0, r1, c1):
        ui.label(r0, c0, "Hello from Python!", S.FACE_BLUE)
        ui.label(r0 + 1, c0, f"Pressed {self.count} times")
        ui.label(r0 + 2, c0, f"It's {self.api.clock()}")
        ui.button(r0 + 4, c0, c0 + 8, "Press", self.press)
        ui.button(r0 + 4, c0 + 10, c0 + 19, "Notify", lambda: self.api.notify("Hoo from Python!"))
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def press(self):
        self.count += 1
        self.api.settings.set("count", self.count)

    def tick(self):
        return True
'''


def list_plugins(desktop):
    try:
        return [e for e in desktop.kernel.fs.listdir("C:\\Apps") if e.ext == ".PY"]
    except FSError:
        return []


def _key(vpath: str) -> str:
    return os.path.basename(vpath.replace("\\", "/")).lower()


def launch_plugin(desktop, vpath: str):
    k = desktop.kernel
    if not desktop.cfg.get("plugins", False):
        def answer(b):
            if b == "Settings":
                desktop.launch("control", page="Plugins")
        desktop.launch("msg", title="Plugins", text="Python plugins are off. Turn them on in Control Panel.",
                       buttons=("Settings", "OK"), done=answer)
        return None
    try:
        source = k.fs.read_text(vpath)
    except FSError as e:
        desktop.launch("msg", title="Plugins", text=str(e))
        return None
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    trusted = dict(k.registry.get("system.trusted_plugins", {}) or {})
    name = _key(vpath)
    if trusted.get(name) != digest:
        def answer(b):
            if b == "Run":
                trusted[name] = digest
                k.registry.set("system.trusted_plugins", trusted)
                _start(desktop, vpath, source)
        desktop.launch("msg", title="Run plugin?", text=f"{name[:16]} can do anything on your PC. Only run it if you trust who made it.",
                       buttons=("Run", "Cancel"), done=answer)
        return None
    return _start(desktop, vpath, source)


def _start(desktop, vpath: str, source: str):
    name = _key(vpath)
    try:
        real = desktop.kernel.fs.real(vpath)
        mod = types.ModuleType("talonos_plugin_" + "".join(ch if ch.isalnum() else "_" for ch in name[:-3]))
        mod.__file__ = real
        exec(compile(source, real, "exec"), mod.__dict__)
        main = getattr(mod, "Main", None)
        from .enhanced import App
        if not (isinstance(main, type) and issubclass(main, App)):
            raise TypeError("a plugin needs class Main(App)")
    except Exception as e:
        desktop.launch("msg", title="Plugin problem", text=f"{name[:16]} couldn't start: {type(e).__name__}: {e}"[:69])
        return None
    label = str(getattr(mod, "NAME", "") or os.path.splitext(name)[0].replace("_", " ").title())[:24]
    if getattr(mod, "ICON", None):
        main.icon = str(mod.ICON)[:1]
    return desktop.start(main, "plugin:" + name, label, "plugin")
