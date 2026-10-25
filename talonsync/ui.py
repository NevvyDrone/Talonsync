"""The window and the tray icon. pywebview (Edge WebView2) gives a real app window; without it,
TalonSync opens as an app-mode Edge/Chrome window or in your default browser."""
from __future__ import annotations

import base64
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from . import APP_NAME

_lock_sock = None


def single_instance() -> bool:
    """Only one TalonSync at a time (two would fight over the OSC port)."""
    global _lock_sock
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.CreateMutexW(None, False, "TalonSync.SingleInstance")
        if k32.GetLastError() != 183:                             # ERROR_ALREADY_EXISTS
            return True
        # Another TalonSync is running - often an OLDER one hiding in the tray after an update.
        # Offer to swap it for this copy instead of silently showing the old app.
        try:
            ans = ctypes.windll.user32.MessageBoxW(None, "TalonSync is already running (look for the owl in your system tray).\n\n"
                                                   "Close that one and start this copy instead?\n(Pick Yes after updating TalonSync.)", APP_NAME, 0x04 | 0x20)
        except Exception:
            ans = 7
        if ans != 6:                                              # IDYES
            return False
        _close_other_copies()
        k32.CloseHandle(h)
        for _ in range(40):
            time.sleep(0.25)
            h = k32.CreateMutexW(None, False, "TalonSync.SingleInstance")
            if k32.GetLastError() != 183:
                return True
            k32.CloseHandle(h)
        ctypes.windll.user32.MessageBoxW(None, "The other TalonSync didn't close. Quit it from the tray owl and try again.", APP_NAME, 0x30)
        return False
    try:
        _lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_sock.bind(("127.0.0.1", 47924))
        return True
    except OSError:
        print("TalonSync is already running.")
        return False


def _close_other_copies():
    """Ends other TalonSync processes (the exe, or python running talonsync_main)."""
    me = os.getpid()
    try:
        flags = 0x08000000                                        # CREATE_NO_WINDOW
        out = subprocess.run(["wmic", "process", "get", "ProcessId,Name,CommandLine", "/format:csv"],
                             capture_output=True, text=True, creationflags=flags, timeout=10).stdout
    except Exception:
        out = ""
    pids = set()
    for line in out.splitlines():
        low = line.lower()
        if "talonsync.exe" in low or "talonsync_main" in low:
            try:
                pid = int(line.rsplit(",", 1)[-1])
            except ValueError:
                continue
            if pid != me and pid != os.getppid():
                pids.add(pid)
    if not out:   # no wmic (newer Windows): by image name
        subprocess.run(["taskkill", "/F", "/IM", "TalonSync.exe", "/FI", f"PID ne {me}"], capture_output=True, creationflags=0x08000000)
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, creationflags=0x08000000)


def icon_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for p in (os.path.join(base, "assets", "talonsync.ico"), os.path.join(base, "talonsync.ico")):
        if os.path.exists(p):
            return p
    return ""


class JsApi:
    """Called from the page as window.pywebview.api.*

    pywebview exposes every PUBLIC attribute of this object to the page, walking into it
    recursively. Anything that isn't a plain API method must start with an underscore, or the
    walk crawls through it (a Window object made the app freeze on load)."""

    def __init__(self):
        self._window = None

    def save_file(self, name, b64):
        import webview
        try:
            res = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename=name)
        except Exception:
            return ""
        if not res:
            return ""
        path = res if isinstance(res, str) else res[0]
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return path


def _tray(app, srv, show, quit_):
    if sys.platform == "darwin":
        return None          # macOS only allows a tray icon on the main thread, which the window owns
    try:
        import pystray
        from PIL import Image
    except Exception:
        return None
    ico = icon_path()
    try:
        if ico:
            # read the icon into memory and close the file at once: an open icon (Pillow maps it) stops
            # Windows from replacing it, so unzipping an update over a running TalonSync failed (0x800704C8)
            import io
            with open(ico, "rb") as f:
                img = Image.open(io.BytesIO(f.read()))
                img.load()
        else:
            img = Image.new("RGBA", (64, 64), (79, 140, 255, 255))
    except Exception:
        img = Image.new("RGBA", (64, 64), (79, 140, 255, 255))
    menu = pystray.Menu(
        pystray.MenuItem("Open TalonSync", lambda: show(), default=True),
        pystray.MenuItem("TalonSync now", lambda: app.start_sync("pc")),
        pystray.MenuItem("TalonCast", lambda: show("talonstar")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda: quit_()),
    )
    tray = pystray.Icon("TalonSync", img, "TalonSync", menu)
    threading.Thread(target=tray.run, daemon=True, name="tray").start()
    return tray


def run(app, srv, minimized=False, browser=False):
    stop = threading.Event()
    if not browser:
        try:
            import webview
        except Exception:
            webview = None
        if webview is not None:
            try:
                return _run_webview(webview, app, srv, minimized)
            except Exception as e:                  # no WebView2, broken install...: use a browser window
                app.log(f"App window failed ({e}) - opening in a browser window instead")
    # ---- browser fallback
    url = srv.url
    def show(view=None):
        _open_browser(url + (f"&view={view}" if view else ""))
    tray = _tray(app, srv, show, stop.set)
    if not minimized:
        show()
    print(f"TalonSync is running at {url}  (Ctrl+C to quit)")
    try:
        while not stop.wait(1):
            pass
    finally:
        if tray:
            tray.stop()


def _open_browser(url):
    """An app-style window (no tabs or address bar) from a Chromium browser if there is one,
    otherwise a normal browser tab."""
    if sys.platform == "win32":
        cands = [shutil.which(e) or _find_win_browser(e) for e in ("msedge", "chrome")]
    elif sys.platform == "darwin":
        cands = [p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                             "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                             "/Applications/Chromium.app/Contents/MacOS/Chromium") if os.path.exists(p)]
    else:
        cands = [shutil.which(e) for e in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                                           "microsoft-edge", "microsoft-edge-stable", "brave-browser")]
    for path in cands:
        if path:
            try:
                subprocess.Popen([path, f"--app={url}", "--window-size=1180,780"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                continue
    webbrowser.open(url)


def _find_win_browser(name):
    roots = [os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""), os.environ.get("LOCALAPPDATA", "")]
    rel = {"msedge": r"Microsoft\Edge\Application\msedge.exe", "chrome": r"Google\Chrome\Application\chrome.exe"}[name]
    for r in roots:
        p = os.path.join(r, rel)
        if r and os.path.exists(p):
            return p
    return None


def _run_webview(webview, app, srv, minimized):
    api = JsApi()
    s = app.settings
    size = s.get("window") or {}
    win = webview.create_window(APP_NAME, srv.url, js_api=api, width=size.get("w", 1180), height=size.get("h", 760),
                                min_size=(900, 600), background_color="#0f2119", hidden=bool(minimized), text_select=True)
    api._window = win
    state = {"quitting": False, "tray": None}

    def show(view=None):
        try:
            win.show(); win.restore()
            if view:
                win.evaluate_js(f"go('{view}')")
        except Exception:
            pass

    def quit_():
        state["quitting"] = True
        try:
            win.destroy()
        except Exception:
            pass

    state["tray"] = _tray(app, srv, show, quit_)

    def on_closing():
        if not state["quitting"] and s.get("close_to_tray") and state["tray"] is not None:
            win.hide()
            return False                      # keep running in the tray
        return True

    def on_resized(w, h):
        s.data["window"] = {"w": int(w), "h": int(h)}

    win.events.closing += on_closing
    try:
        win.events.resized += on_resized
    except Exception:
        pass
    webview.start(private_mode=False, storage_path=os.path.join(app.dir, "webview"))
    if state["tray"]:
        state["tray"].stop()
    s.save()
