"""Local HTTP server for the TalonSync window: static UI + a small JSON API.
Bound to 127.0.0.1 with a random token, so web pages in your browser can't poke it."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import secrets
import sys
import tempfile
import threading
import traceback
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import formats, protocol as pr
from .core import TalonSyncApp
from .settings import ACTIONS, CONDUITS, DEFAULTS


def web_dir() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "talonsync", "web") if hasattr(sys, "_MEIPASS") else os.path.join(base, "web")
    return p


EXPORTS = {
    "contacts.vcf": ("TalonSync Contacts.vcf", "text/vcard", lambda db: formats.contacts_to_vcf(db.contacts)),
    "contacts.csv": ("TalonSync Contacts.csv", "text/csv", lambda db: formats.contacts_to_csv(db.contacts)),
    "calendar.ics": ("TalonSync Calendar.ics", "text/calendar", lambda db: formats.to_ics(db.events, [])),
    "calendar.csv": ("TalonSync Calendar.csv", "text/csv", lambda db: formats.events_to_csv(db.events)),
    "tasks.ics": ("TalonSync Tasks.ics", "text/calendar", lambda db: formats.to_ics([], db.tasks)),
    "tasks.csv": ("TalonSync Tasks.csv", "text/csv", lambda db: formats.tasks_to_csv(db.tasks)),
    "tasks.md": ("TalonSync Tasks.md", "text/markdown", lambda db: formats.tasks_to_md(db.tasks)),
    "memos.md": ("TalonSync Memos.md", "text/markdown", lambda db: formats.memos_to_md(db.memos)),
    "memos.csv": ("TalonSync Memos.csv", "text/csv", lambda db: formats.memos_to_csv(db.memos)),
    "notepad.png": ("TalonSync Note Pad.png", "image/png", lambda db: formats.notepad_to_png(db.notepad)),
    "unity.json": ("TalonSync for Unity.json", "application/json", lambda db: formats.to_unity_json(db)),
    "backup.json": ("TalonSync Backup.json", "application/json", lambda db: json.dumps(db.to_dict(), indent=1)),
}


class Server:
    def __init__(self, app: TalonSyncApp, port: int = 0):
        self.app = app
        self.token = secrets.token_urlsafe(16)
        handler = type("H", (_Handler,), {"srv": self})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="ui-server").start()
        return self

    def stop(self):
        self.httpd.shutdown()


class _Handler(BaseHTTPRequestHandler):
    srv: Server = None
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    # ------------------------------------------------------------ plumbing
    def _send(self, code: int, body: bytes, ctype: str = "application/json", extra: dict = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, default=str).encode("utf-8"))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _authed(self, q) -> bool:
        tok = self.headers.get("X-Token") or (q.get("t") or [""])[0]
        return secrets.compare_digest(tok, self.srv.token)

    # ------------------------------------------------------------ routes
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not u.path.startswith("/api/"):
            return self._static(u.path)
        if not self._authed(q):
            return self._json({"error": "forbidden"}, 403)
        try:
            self._get(u.path[5:], q)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authed(q):
            return self._json({"error": "forbidden"}, 403)
        try:
            self._post(u.path[5:], self._body())
        except ValueError as e:                             # a plain "can't do that" for the window to show
            self._json({"error": str(e)}, 400)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        root = web_dir()
        full = os.path.normpath(os.path.join(root, path.lstrip("/")))
        if not full.startswith(os.path.normpath(root)) or not os.path.isfile(full):
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".js"):
            ctype = "text/javascript"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))

    def _get(self, route, q):
        app = self.srv.app
        db = app.db
        if route == "state":
            return self._json(app.state())
        # ---- Experimental: the Terminal CPU, TalonOS Enhanced and BASIC (TalonSync 1.12)
        if route == "terminal":
            return self._json(app.terminal.snapshot())
        if route == "programs":
            from . import library
            return self._json({"files": app.terminal.program_files(),
                               "library": [{"name": p["name"], "title": p["title"], "kind": p["kind"], "about": p["about"]} for p in library.PROGRAMS]})
        if route == "program":
            name = (q.get("name") or [""])[0]
            try:
                return self._json({"name": name, "source": app.terminal.program_read(name)})
            except ValueError as e:
                return self._json({"error": str(e)}, 404)
        if route == "meta":
            return self._json({
                "values": [asdict(v) for v in pr.VALUES], "apps": pr.APPS, "conduits": CONDUITS, "actions": ACTIONS,
                "defaults": DEFAULTS, "data_dir": app.dir, "exports": {k: v[0] for k, v in EXPORTS.items()},
            })
        if route in ("contacts", "events", "tasks", "memos"):
            with db.lock:
                recs = [asdict(r) for r in db.kind(route)]
                choice = db.pda_choice(route, {"contacts": 6, "events": 6, "tasks": 8, "memos": 5}[route])
                for r, rec in zip(recs, db.kind(route)):
                    r["pda_lines"] = rec.pda_lines()
                    r["pda_pos"] = choice.index(rec.id) if rec.id in choice else -1
            return self._json(recs)
        if route == "notepad":
            return self._json(asdict(db.notepad))
        if route == "device":
            return self._json(asdict(db.device))
        if route == "settings":
            return self._json(app.settings.as_dict())
        if route == "reports":
            return self._json([asdict(r) for r in app.syncer.reports])
        if route == "backups":
            return self._json(app.backups())
        if route == "mirror":
            return self._json({**app.mirror.state(), "snapshots": app.mirror.snapshots()})
        if route == "doctor":
            return self._json(app.doctor())
        if route == "support":
            from .support import build_report
            return self._json({"text": build_report(app)})
        if route == "weather":
            return self._json({"weather": app.weather_data(), "extras": app.agenda_extras(), "pda_sent": app.wx_pda})
        if route == "locate":
            from . import weather as wx
            p = wx.locate_by_ip()
            return self._json({"place": p} if p else {"error": "Couldn't work out where this PC is - search for your city instead."})
        if route == "geocode":
            from . import weather as wx
            try:
                return self._json({"results": wx.geocode((q.get("q") or [""])[0])})
            except Exception as e:
                return self._json({"results": [], "error": f"Couldn't search ({e})"})
        if route == "log":
            return self._json(list(app.log_lines))
        if route.startswith("export/"):
            key = route[7:]
            if key not in EXPORTS:
                return self._json({"error": "unknown export"}, 404)
            name, ctype, fn = EXPORTS[key]
            data = fn(db)
            if isinstance(data, str):
                data = data.encode("utf-8")
            return self._send(200, data, ctype, {"Content-Disposition": f'attachment; filename="{name}"'})
        return self._json({"error": "not found"}, 404)

    def _post(self, route, b):
        app = self.srv.app
        db = app.db
        t = app.terminal
        if route == "terminal/key":
            t.pc_key(str(b.get("key", ""))); return self._json(t.snapshot())
        if route == "terminal/line":
            t.pc_line(str(b.get("text", ""))); return self._json(t.snapshot())
        if route == "terminal/tap":
            t.pc_tap(int(b.get("row", 0)), int(b.get("col", 0))); return self._json(t.snapshot())
        if route == "terminal/start":
            what = str(b.get("what", ""))
            if what not in ("menu", "gui", "basic", "local", "library"):
                raise ValueError("Unknown choice.")
            t.pc_start(what); return self._json(t.snapshot())
        if route == "terminal/load":
            t.pc_load(str(b.get("source", "")), bool(b.get("run"))); return self._json(t.snapshot())
        if route == "program/save":
            return self._json({"name": t.program_write(str(b.get("name", "")), str(b.get("source", "")))})
        if route == "program/delete":
            t.program_delete(str(b.get("name", ""))); return self._json({"ok": True})
        if route == "sync":
            ok = app.start_sync("pc")
            return self._json({"started": ok})
        if route == "sync/cancel":
            app.syncer.cancel()
            return self._json({"ok": True})
        if route in ("contacts", "events", "tasks", "memos"):
            rec = db.upsert(route, b)
            return self._json(asdict(rec))
        if route.startswith("delete/"):
            kind = route[7:]
            return self._json({"ok": db.delete(kind, b.get("id", ""))})
        if route == "notepad":
            with db.lock:
                bits = [1 if x else 0 for x in b.get("bits", [])]
                if len(bits) == db.notepad.rows * db.notepad.cols:
                    db.notepad.bits = bits
                    db.notepad.modified = __import__("talonsync.model", fromlist=["now_iso"]).now_iso()
                    db.touch()
            return self._json({"ok": True})
        if route == "device":
            with db.lock:
                for k in ("owner", "sync_id", "hypno_caption"):
                    if k in b:
                        setattr(db.device, k, str(b[k]))
                if "prefs" in b:
                    db.device.prefs.update({k: float(v) for k, v in b["prefs"].items()})
                db.touch()
            return self._json({"ok": True})
        if route == "settings":
            before = app.settings.as_dict()
            app.settings.update(b)
            after = app.settings.as_dict()
            conn_keys = ("osc_send_host", "osc_send_port", "osc_listen_host", "osc_listen_port", "oscquery",
                         "oscquery_random_port", "demo_pda", "ack_timeout", "bus_settle_ms", "bus_gap_ms", "bus_retries")
            if any(before.get(k) != after.get(k) for k in conn_keys):
                if not app.syncer.busy:
                    app.connect()
            if before.get("exp_terminal") != after.get("exp_terminal"):
                app.terminal.attach()                      # turned on: the PDA finds the CPU; off: "No CPU found"
            if any(before.get(k) != after.get(k) for k in ("ts_place", "ts_units", "ts_region_count", "ts_extra_cities")):
                app.weather.refresh_now()
            elif any(before.get(k) != after.get(k) for k in ("ts_pda_ticker", "ts_pda_ticker_text")):
                threading.Thread(target=app.push_weather, daemon=True).start()
            if any(before.get(k) != after.get(k) for k in ("ts_pda_ticker", "twitch_channel", "pc_twitch_mentions")):
                app.pc.apply_settings()
            if before.get("ts_pda_jazz") != after.get("ts_pda_jazz") and app.bus:
                threading.Thread(target=lambda: _quiet(lambda: app.bus.jazz_mode(after["ts_pda_jazz"])), daemon=True).start()
            if before.get("start_with_windows") != after.get("start_with_windows"):
                set_autostart(after["start_with_windows"])
            return self._json(after)
        if route == "settings/reset":
            from copy import deepcopy
            app.settings.data = deepcopy(DEFAULTS)
            app.settings.data["first_run"] = False
            app.settings.save()
            app.connect()
            return self._json(app.settings.as_dict())
        if route == "remote":
            action = b.pop("action", "")
            return self._json({"message": app.remote(action, **b)})
        if route == "doctor/fix":
            return self._json({"message": app.doctor_fix(b.get("what", ""))})
        if route == "weather/refresh":
            threading.Thread(target=app.weather.update, daemon=True).start()
            return self._json({"ok": True})
        if route == "hypno":
            msg = app.save_hypno(b.get("caption"), b.get("speed"), b.get("style"), bool(b.get("send", True)), bool(b.get("open", False)))
            return self._json({"message": msg})
        if route == "pclink/message":
            app.pc.message(str(b.get("title", "")), str(b.get("text", "")), alert=bool(b.get("chirp", True)))
            return self._json({"message": "Sent to the PDA's PC Link"})
        if route == "pclink/clear":
            threading.Thread(target=app.pc.clear_messages, daemon=True).start()
            return self._json({"ok": True})
        if route == "pclink/timer":
            act = b.get("action", "toggle")
            if act == "start_focus": app.pc._timer_phase(1)
            elif act == "start_break": app.pc._timer_phase(2)
            elif act == "stop": app.pc.timer_stop()
            else: app.pc.timer_toggle()
            return self._json(app.pc.state()["timer"])
        if route == "pclink/media":
            from .nowplaying import media_command
            return self._json({"ok": media_command(b.get("action", "play_pause"))})
        if route == "weather/push":
            return self._json({"message": app.push_weather()})
        if route == "reconnect":
            app.connect()
            return self._json({"ok": True})
        if route == "import":
            tmp = tempfile.mkdtemp(prefix="talonsync-import-")
            paths = []
            for f in b.get("files", []):
                name = os.path.basename(f.get("name") or "import.txt")
                p = os.path.join(tmp, name)
                with open(p, "wb") as fh:
                    fh.write(base64.b64decode(f.get("data", "")))
                paths.append(p)
            res = app.import_files(paths, b.get("target", "auto"))
            return self._json(res)
        if route == "export_all":
            folder = b.get("folder") or os.path.join(os.path.expanduser("~"), "Documents", "TalonSync Export")
            files = formats.export_all(db, folder, b.get("formats") or ["vcf", "ics", "csv", "md", "png", "json"])
            return self._json({"folder": folder, "files": [os.path.basename(f) for f in files]})
        if route == "backups/create":
            return self._json({"name": app.backup(b.get("label", ""))})
        if route == "mirror/restore":
            return self._json({"message": app.mirror.restore(b.get("snapshot", ""))})
        if route == "mirror/dismiss":
            app.mirror.dismiss()
            return self._json({"ok": True})
        if route == "mirror/snapshot":
            return self._json({"name": app.mirror.snapshot("manual")})
        if route == "backups/restore":
            app.restore(b.get("name", ""))
            return self._json({"ok": True})
        if route == "open_folder":
            open_folder(b.get("path") or app.dir)
            return self._json({"ok": True})
        if route == "wipe":
            what = b.get("what")
            app.backup(f"before clearing {what}")
            with db.lock:
                if what in ("contacts", "events", "tasks", "memos"):
                    db.kind(what).clear()
                elif what == "sync_history":
                    from .model import SyncBase
                    db.base = SyncBase()
                db.touch()
            return self._json({"ok": True})
        return self._json({"error": "not found"}, 404)


def _quiet(fn):
    try:
        fn()
    except Exception:
        pass


def open_folder(path: str):
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess; subprocess.Popen(["open", path])
        else:
            import subprocess; subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def _launch_cmd(minimized=True):
    """How to start this TalonSync again: the exe, or this Python with this script."""
    if getattr(sys, "frozen", False):
        return [sys.executable] + (["--minimized"] if minimized else [])
    return [sys.executable, os.path.abspath(sys.argv[0])] + (["--minimized"] if minimized else [])


def set_autostart(on: bool):
    """Start TalonSync when you log in, minimized to the tray.
    Windows: the HKCU Run key.  Linux: ~/.config/autostart/talonsync.desktop.
    macOS: a LaunchAgent (~/Library/LaunchAgents/com.talonsync.app.plist)."""
    try:
        cmd = _launch_cmd()
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if on:
                winreg.SetValueEx(key, "TalonSync", 0, winreg.REG_SZ, " ".join(f'"{c}"' if " " in c else c for c in cmd))
            else:
                try:
                    winreg.DeleteValue(key, "TalonSync")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        elif sys.platform == "darwin":
            path = os.path.expanduser("~/Library/LaunchAgents/com.talonsync.app.plist")
            if on:
                import plistlib
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    plistlib.dump({"Label": "com.talonsync.app", "ProgramArguments": cmd, "RunAtLoad": True,
                                   "WorkingDirectory": os.path.dirname(os.path.abspath(sys.argv[0]))}, f)
            elif os.path.exists(path):
                os.remove(path)
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
            path = os.path.join(base, "autostart", "talonsync.desktop")
            if on:
                import shlex
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write("[Desktop Entry]\nType=Application\nName=TalonSync\nComment=Sync your Talon Pilot PDA\n"
                            f"Exec={' '.join(shlex.quote(c) for c in cmd)}\n"
                            f"Path={os.path.dirname(os.path.abspath(sys.argv[0]))}\n"
                            "X-GNOME-Autostart-enabled=true\nTerminal=false\n")
            elif os.path.exists(path):
                os.remove(path)
    except Exception:
        pass
