"""TalonSyncApp: wires OSC, the PDA bus, TalonSync, Now Playing, backups and the doctor together.
The GUI talks to this through server.py; nothing here knows about windows or HTML."""
from __future__ import annotations

import collections
import glob
import json
import os
import shutil
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional

from . import __version__, formats, protocol as pr
from .bus import BusError, Nak, NoPda, PdaBus, Timing
from .engine import SyncEngine, SyncReport
from .model import Database, NotePad
from .nowplaying import NowPlaying, Track
from .osc import OscLink
from . import weather as wx
from .oscquery import HAVE_ZEROCONF, OscQueryService, free_udp_port
from .settings import Settings, data_dir


class TalonSyncApp:
    def __init__(self, folder: Optional[str] = None):
        self.dir = folder or data_dir()
        os.makedirs(self.dir, exist_ok=True)
        self.backup_dir = os.path.join(self.dir, "Backups")
        self.log_lines = collections.deque(maxlen=800)
        self.settings = Settings(os.path.join(self.dir, "settings.json"))
        self.db = Database(os.path.join(self.dir, "talonsync_db.json"))
        self.link: Optional[OscLink] = None
        self.bus: Optional[PdaBus] = None
        self.syncer: Optional[SyncEngine] = None
        self.oscq: Optional[OscQueryService] = None
        self.demo = None
        self.weather = wx.WeatherService(self.settings, log=self.log, on_update=self._weather_updated)
        self.wx_pda = ""
        self.np = NowPlaying(self.settings, self._np_changed, self._np_position, log=self.log)
        self.np_sent = Track()
        self.np_error = ""
        from .pclink import PcLink
        self.pc = PcLink(self, log=self.log)
        from .terminal import Terminal
        self.terminal = Terminal(self)                  # 2.18: Talon Enhanced BASIC on the PDA's terminal
        from .deskclick import DeskClick
        self.desk = DeskClick(self.settings, self._desk_send, log=self.log)
        self._last_chat = 0.0
        self._req_prev = False
        self._on_prev = False
        self._stop = threading.Event()
        self._watch_seen: Dict[str, float] = {}
        self.started = time.time()
        from .mirror import PdaMirror                   # 1.15: live backup of the PDA's saved memory
        self.mirror = PdaMirror(self.dir, self.settings, self.log, lambda: self.link,
                                lambda: bool(self.syncer and self.syncer.busy),
                                lambda: self.oscq.vrchat_values() if self.oscq else {})

    # ------------------------------------------------------------ logging
    def log(self, msg: str, level: str = "info"):
        line = f"{datetime.now():%H:%M:%S}  {msg}"
        self.log_lines.append(line)
        try:
            with open(os.path.join(self.dir, "talonsync.log"), "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d} {line}\n")
        except OSError:
            pass

    # ------------------------------------------------------------ start / stop
    def start(self):
        self.log(f"TalonSync {__version__} starting (data in {self.dir})")
        self.connect()
        self.np.start()
        self.weather.start()
        self.pc.start()
        self.desk.start()
        threading.Thread(target=self._housekeeping, daemon=True, name="housekeeping").start()
        if self.settings.get("sync_on_start"):
            threading.Timer(3.0, lambda: self.start_sync("startup")).start()

    def _desk_send(self, param: str, on: bool):
        """Desktop click -> the avatar parameter (and the demo PDA, so it can be tried without VRChat)."""
        if self.link:
            self.link.set(param, bool(on))
        if self.demo and hasattr(self.demo, "desk"):
            self.demo.desk[param] = bool(on)

    def stop(self):
        try:
            self.terminal.stop()
        except Exception:
            pass
        self._stop.set()
        self.pc.stop()
        self.desk.stop()
        self.np.stop()
        self.weather.stop()
        self._clear_now_playing()
        if self.oscq:
            self.oscq.stop()
        if self.link:
            self.link.stop()
        if self.demo:
            self.demo.stop()
        try:
            self.db.save()
        except Exception:
            pass

    def connect(self):
        """(Re)open the OSC link with the current settings."""
        if self.oscq:
            self.oscq.stop(); self.oscq = None
        if self.link:
            self.link.stop()
        if self.demo:
            self.demo.stop(); self.demo = None
        s = self.settings
        listen_port = int(s["osc_listen_port"])
        send_port = int(s["osc_send_port"])
        use_q = bool(s["oscquery"]) and HAVE_ZEROCONF and not s["demo_pda"]
        if use_q and s["oscquery_random_port"]:
            listen_port = free_udp_port()
        if s["demo_pda"]:
            from .fakepda import FakePda
            send_port = free_udp_port()
            listen_port = free_udp_port()
            self.demo = FakePda(listen_port=send_port, send_port=listen_port).start()
            self.log("Demo PDA running (a pretend Talon Pilot - turn it off in Settings to use VRChat)")
        fallback = int(s["osc_listen_port"]) if (use_q and s["oscquery_random_port"]) else 0
        self.link = OscLink(s["osc_send_host"], send_port, s["osc_listen_host"], listen_port, log=self.log, fallback_port=fallback)
        if not self.link.start() and use_q:
            pass
        self.link.add_listener(self._on_osc)
        if getattr(self, "terminal", None):
            self.terminal.attach()                      # the PDA's Terminal finds the CPU (menu, nothing loaded)
        if use_q:
            self.oscq = OscQueryService(self.link.listen_addr[1], log=self.log)
            if not self.oscq.start():
                self.oscq = None
        t = Timing(ack_timeout=float(s["ack_timeout"]), settle=s["bus_settle_ms"] / 1000.0,
                   gap=s["bus_gap_ms"] / 1000.0, retries=int(s["bus_retries"]))
        self.bus = PdaBus(self.link, t, log=lambda m: None)
        old_reports = self.syncer.reports if self.syncer else []
        self.syncer = SyncEngine(self.db, s, self.bus, log=self.log, on_backup=self.backup_after_sync, on_after=self._after_sync)
        self.syncer.reports = old_reports or self._load_reports()
        self.pc.forget_pda()
        self.log(f"OSC: sending to {s['osc_send_host']}:{send_port}, listening on {self.link.listen_addr[1]}"
                 + (" (OSCQuery)" if self.oscq else ""))

    # ------------------------------------------------------------ OSC events
    def _on_osc(self, addr: str, args):
        try:
            self.mirror.on_osc(addr, args)
        except Exception as e:
            self.log(f"live backup: {e}")
        if self.pc.on_osc(addr, args):
            return
        if addr == "/avatar/parameters/" + pr.SYNC_REQ:
            req = bool(args and args[0])
            if req and not self._req_prev and self.settings.get("answer_pda_requests", True):
                self.log("The PDA asked for a TalonSync")
                self.start_sync("pda")
            self._req_prev = req
        elif addr == "/avatar/parameters/" + pr.P + "On":
            on = bool(args and args[0])
            if on and not self._on_prev:
                self._hello()                  # the PDA is booting: its self-test waits up to 1.5 s for us
            self._on_prev = on
        elif addr == "/avatar/change":
            self._on_prev = False
            self._hello(delays=(0.5, 1.0, 1.4))  # a saved "on" PDA boots as the avatar loads
            self.log(f"Avatar changed ({args[0] if args else '?'})")
            self.np_sent = Track()            # resend now playing to the new avatar
            self.pc.forget_pda()
            threading.Timer(4.0, lambda: self._np_changed(self.np.track)).start()

    def _hello(self, delays=(0.1, 0.5, 0.9)):
        """Answer the PDA's power-on self-test: TP/PC/Hello = our version (187 for 1.8.7). Sent three times inside
        its 1.5 s window so one lost UDP packet doesn't matter; three tiny OSC messages per boot, nothing else."""
        from . import __version__
        try:
            code = int("".join(__version__.split(".")[:3]))
        except ValueError:
            code = 1
        code = max(1, min(255, code))
        def send():
            if self.link:
                self.link.set(pr.PC_HELLO, code)
        for d in delays:
            t = threading.Timer(d, send); t.daemon = True; t.start()
        if getattr(self, "terminal", None):
            self.terminal.attach()                      # and put the terminal screen back

    # ------------------------------------------------------------ TalonSync
    def start_sync(self, who: str = "pc") -> bool:
        if not self.syncer or self.syncer.busy:
            return False
        if who == "pc":
            self.log("TalonSync started from the PC")
        return self.syncer.start(who)

    def _after_sync(self, rep: SyncReport):
        self._save_reports()
        if rep.ok and self.settings.get("sound") and self.settings.get("chirp_on_done"):
            play_chirp()
        if rep.ok and self.settings.get("auto_export") and self.settings.get("auto_export_folder"):
            try:
                files = formats.export_all(self.db, self.settings["auto_export_folder"], self.settings["auto_export_formats"])
                self.log(f"Auto-export: {len(files)} files to {self.settings['auto_export_folder']}")
            except Exception as e:
                self.log(f"Auto-export failed: {e}")
        if rep.ok and self.settings.get("ts_send_pda", True):
            threading.Thread(target=self.push_weather, daemon=True).start()
        if rep.ok:
            self.np_sent = Track()            # make sure the card is current
            self._np_changed(self.np.track)

    def _reports_path(self):
        new = os.path.join(self.dir, "sync_log.json")
        old = os.path.join(self.dir, "hotsync_log.json")    # renamed in 1.7.0: carry the old log over once
        if not os.path.exists(new) and os.path.exists(old):
            try:
                os.replace(old, new)
            except OSError:
                pass
        return new

    def _save_reports(self):
        try:
            with open(self._reports_path(), "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in self.syncer.reports[:50]], f, indent=1)
        except Exception:
            pass

    def _load_reports(self) -> List[SyncReport]:
        try:
            with open(self._reports_path(), encoding="utf-8") as f:
                return [SyncReport(**r) for r in json.load(f)]
        except Exception:
            return []

    # ------------------------------------------------------------ backups
    def backup(self, label: str = "") -> str:
        os.makedirs(self.backup_dir, exist_ok=True)
        name = f"TalonSync {datetime.now():%Y-%m-%d %H%M%S}{(' ' + label) if label else ''}.json"
        path = os.path.join(self.backup_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.db.to_dict(), f, indent=1)
        keep = max(1, int(self.settings.get("backup_keep", 20)))
        files = sorted(glob.glob(os.path.join(self.backup_dir, "TalonSync *.json")))
        for old in files[:-keep]:
            try:
                os.remove(old)
            except OSError:
                pass
        return name

    def backup_after_sync(self) -> str:
        return self.backup()

    def backups(self) -> List[Dict]:
        out = []
        for p in sorted(glob.glob(os.path.join(self.backup_dir, "TalonSync *.json")), reverse=True):
            st = os.stat(p)
            out.append({"name": os.path.basename(p), "size": st.st_size, "time": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
        return out

    def restore(self, name: str):
        p = os.path.join(self.backup_dir, os.path.basename(name))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("format") != "talonsync-db":
            raise ValueError("not a TalonSync backup")
        self.backup("before restore")
        self.db.from_dict(data)
        self.db.save()
        self.log(f"Restored {name}")

    # ------------------------------------------------------------ Now Playing
    def _fmt(self, t: Track):
        title, artist = t.title, t.artist
        if self.settings.get("np_swap"):
            title, artist = artist, title
        if self.settings.get("np_upper"):
            title, artist = title.upper(), artist.upper()
        return pr.to_ascii(title), pr.to_ascii(artist)

    def _np_changed(self, t: Track):
        if not self.settings.get("now_playing", True) or not self.bus:
            return
        if self.settings.get("np_only_when_connected") and not self.bus.connected_recently and not self._vrchat_alive():
            return
        try:
            show = t.playing or not self.settings.get("np_clear_when_paused", True)
            if show and (t.title or t.artist):
                title, artist = self._fmt(t)
                self.bus.now_playing(title, artist, t.position if self.settings.get("np_position") else 0.0)
                self.log(f"Now playing on the PDA: {title} - {artist}")
            else:
                self.bus.now_clear()
            self.np_sent = t
            self.np_error = ""
        except Nak:
            self.np_error = "This PDA has no Now Playing card yet (update Talon Pilot to 2.5)."
        except BusError:
            self.np_error = "PDA not reachable"
        self._chatbox(t)

    def _np_position(self, t: Track):
        if self.bus and self.np_sent.key() == t.key() and t.playing and t.position is not None and self.settings.get("np_position"):
            try:
                self.bus.now_position(t.position)
            except BusError:
                pass
        self._chatbox(t)

    def _chatbox(self, t: Track):
        if not self.settings.get("chatbox_now_playing") or not self.link:
            return
        if time.time() - self._last_chat < max(2.0, float(self.settings.get("chatbox_interval", 6))):
            return
        if not (t.playing and (t.title or t.artist)):
            return
        self._last_chat = time.time()
        try:
            text = self.settings.get("chatbox_format", "{title} - {artist}").format(title=t.title, artist=t.artist, album=t.album)
        except Exception:
            text = f"{t.title} - {t.artist}"
        self.link.chatbox(text, True, False)

    def _clear_now_playing(self):
        try:
            if self.bus and self.bus.connected_recently:
                self.bus.t.retries = 0
                self.bus.now_clear()
        except Exception:
            pass

    def _vrchat_alive(self) -> bool:
        return bool(self.link and self.link.seconds_since_rx() < 60)

    # ------------------------------------------------------------ TalonCast
    def weather_data(self) -> Dict:
        d = self.weather.data
        if not d.get("ok") and self.settings.get("ts_demo_weather", True):
            place = self.weather.place()
            demo = wx.sample(place, self.settings.get("ts_units") == "metric")
            demo["error"] = d.get("error", "")
            return demo
        return d

    def _weather_updated(self, d: Dict):
        if d.get("ok") and self.settings.get("ts_send_pda", True):
            self.push_weather()

    def push_weather(self) -> str:
        d = self.weather_data()
        if not d.get("ok") or not self.bus:
            return "No weather to send yet"
        if self.syncer and self.syncer.busy:
            return "TalonSync is running"
        try:
            self.bus.weather(d)
            self.bus.jazz_mode(int(self.settings.get("ts_pda_jazz", 1)))
            try:
                self.bus.ticker(self.pda_ticker_text(d))
            except Nak:
                pass                                   # PDA from before 2.5.3: no ticker
            self.wx_pda = datetime.now().isoformat(timespec="seconds")
            return f"Weather for {d['place'].get('name', '')} sent to the PDA"
        except Nak:
            return "This PDA has no TalonCast app (it was left out in the Install Wizard, or Talon Pilot is older than 2.5)."
        except BusError:
            return "PDA not reachable"

    def pda_ticker_text(self, d: Dict = None) -> str:
        mode = self.settings.get("ts_pda_ticker", "auto")
        if mode == "off":
            return ""
        if mode == "custom":
            return pr.clean(self.settings.get("ts_pda_ticker_text", ""), 45)
        if mode == "twitch":
            return pr.clean(self.pc.chat_line, 45)
        d = d or self.weather_data()
        if not d.get("ok"):
            return ""
        c, u = d["current"], d["units"]
        day = (d.get("daily") or [{}])[0]
        parts = [f"Now {c.get('temp')}{u['temp']} {c.get('short', '')}", f"Hi {day.get('hi')} Lo {day.get('lo')}"]
        if c.get("wind"):
            parts.append(f"Wind {c.get('wind_dir', '')} {c['wind']}")
        return pr.clean("  ".join(parts), 45)

    def push_ticker(self, text: str):
        """Put text on the PDA's TalonCast ticker right away (Twitch chat), unless a TalonSync is running."""
        if not self.bus or (self.syncer and self.syncer.busy):
            return
        try:
            self.bus.ticker(text)
        except BusError:
            pass

    def save_hypno(self, caption: str = None, speed: int = None, style: int = None, send: bool = True, open_app: bool = False) -> str:
        """Hypnospiral options from the TalonSync window: stored here, and sent straight to the PDA."""
        dev, base = self.db.device, self.db.base
        with self.db.lock:
            if caption is not None:
                dev.hypno_caption = pr.clean(caption)
            if speed is not None:
                dev.prefs["hypSpeed"] = float(max(1, min(5, int(speed))))
            if style is not None:
                dev.prefs["hypStyle"] = float(max(0, min(2, int(style))))
            self.db.touch()
        if not send:
            return "Saved. It goes to the PDA at the next TalonSync."
        if self.syncer and self.syncer.busy:
            return "Saved. TalonSync is running, so it'll go across with it."
        try:
            if caption is not None:
                self.bus.write_text(pr.SLOT_HYPNO, dev.hypno_caption)
                base.lines[str(pr.SLOT_HYPNO)] = dev.hypno_caption        # the PDA now matches: no TalonSync conflict
            for key in ("hypSpeed", "hypStyle"):
                if (key == "hypSpeed" and speed is not None) or (key == "hypStyle" and style is not None):
                    self.bus.write_value(pr.VALUE_INDEX[key], dev.prefs[key])
                    base.prefs[key] = dev.prefs[key]
            self.bus.reload()
            if open_app:
                self.bus.open_app(23)
            return "Sent to your PDA. Hoot!"
        except Nak:
            return "Saved, but this PDA doesn't understand that yet (update Talon Pilot)."
        except BusError:
            return "Saved. The PDA isn't reachable right now, so it'll go across at the next TalonSync."

    def agenda_extras(self) -> Dict:
        from .model import parse_dt
        now = datetime.now()
        evs = []
        for e in sorted(self.db.events, key=lambda e: e.start_dt() or datetime.max):
            s = e.start_dt()
            if s and (e.end_dt() or s) >= now:
                when = s.strftime("%a %b %d") if e.all_day else s.strftime("%a %I:%M %p").replace(" 0", " ")
                evs.append({"title": e.title, "when": when})
            if len(evs) >= 4:
                break
        tasks = [t.title for t in sorted(self.db.tasks, key=lambda t: t.sort_key()) if not t.done][:5]
        np_ = f"{self.np.track.title} by {self.np.track.artist}" if self.np.track.playing and self.np.track.title else ""
        return {"owner": self.db.device.owner, "events": evs, "tasks": tasks, "pet": self.db.device.pet, "np": np_}

    # ------------------------------------------------------------ remote control
    def remote(self, action: str, **kw) -> str:
        if self.syncer and self.syncer.busy:
            return "TalonSync is running - try again in a moment."
        b = self.bus
        try:
            if action == "ping":
                info = b.probe()
                self.db.device.pda_info = {"version": info.version, "slots": info.slots, "ink_rows": info.ink_rows, "ink_cols": info.ink_cols}
                return f"PDA answered: link v{info.version}, {info.slots} text lines, " + (f"Note Pad {info.ink_cols}x{info.ink_rows}" if info.ink_rows else "no Note Pad")
            if action == "open_app":
                b.open_app(int(kw.get("app", 0)))
                return f"Opened {pr.APPS.get(int(kw.get('app', 0)), 'app')} on the PDA"
            if action == "power":
                self.link.set(pr.POWER, bool(kw.get("on", True)))
                return "Power " + ("on" if kw.get("on", True) else "off")
            if action == "message":
                text = str(kw.get("text", ""))
                b.now_playing(pr.to_ascii(kw.get("title", "Message from PC")), pr.to_ascii(text), 0.0)
                self.np_sent = Track(title="(message)")
                return "Message sent to the PDA's Now Playing card"
            if action == "pet":
                what = kw.get("what")
                key = {"feed": "petFood", "play": "petJoy"}.get(what)
                if not key:
                    return "?"
                k = pr.VALUE_INDEX[key]
                cur = b.read_value(k) or 0.0
                b.write_value(k, min(1.0, cur + 0.35))
                return f"{'Fed' if what == 'feed' else 'Played with'} your Hoot-agotchi from the PC."
            if action == "read_pet":
                pet = {}
                for v in pr.PET:
                    x = b.read_value(pr.VALUE_INDEX[v.key])
                    if x is not None:
                        pet[v.key] = round(float(x), 3)
                self.db.device.pet = pet
                self.db.device.pet_read = datetime.now().isoformat(timespec="seconds")
                return "Pet stats read"
            if action == "set_pref":
                key, val = kw["key"], float(kw["value"])
                b.write_value(pr.VALUE_INDEX[key], val)
                b.reload()
                self.db.device.prefs[key] = val
                self.db.base.prefs[key] = val
                return f"{key} set on the PDA"
            if action == "clear_ink":
                b.clear_ink()
                return "Note Pad cleared on the PDA"
            if action == "demo_press" and self.demo:
                self.demo.press_sync()
                return "Pressed TalonSync on the demo PDA"
        except Nak:
            return "This PDA doesn't have that (the app may have been left out in the Install Wizard, or Talon Pilot needs an update)."
        except NoPda:
            return "The PDA didn't answer. Is VRChat running with OSC on and your Talon Pilot avatar loaded?"
        except Exception as e:
            return f"Failed: {e}"
        return "Unknown action"

    # ------------------------------------------------------------ doctor
    def doctor(self) -> List[Dict]:
        """Connection checks, each {name, ok, detail, fix}."""
        out = []
        L = self.link
        out.append({"name": "OSC listening", "ok": bool(L and L.listening),
                    "detail": f"UDP {L.listen_addr[1]}" if L and L.listening else (L.error if L else "not started"), "fix": ""})
        out.append({"name": "OSCQuery", "ok": bool(self.oscq), "detail": ("advertising, " + ("VRChat found" if self.oscq.vrchat else "VRChat not seen yet")) if self.oscq
                    else ("zeroconf missing" if not HAVE_ZEROCONF else "off"), "fix": ""})
        alive = self._vrchat_alive()
        out.append({"name": "VRChat sending OSC", "ok": alive,
                    "detail": (f"last message {L.seconds_since_rx():.0f} s ago" + (" (on the standard port: VRChat didn't use OSCQuery)" if L.fallback_used else "")) if L and L.last_rx else "nothing received yet - turn on OSC in VRChat's Action Menu (Options > OSC > Enabled)",
                    "fix": ""})
        cfg = self.vrchat_osc_configs()
        stale = [c for c in cfg if not c["has_link"]]
        out.append({"name": "Avatar OSC config", "ok": not stale,
                    "detail": (f"{len(cfg)} avatar configs, {len(stale)} without the Talon Pilot link (old)" if cfg else "no VRChat OSC configs found on this PC"),
                    "fix": "delete_stale_configs" if stale else ""})
        try:
            msg = self.remote("ping")
            ok = msg.startswith("PDA answered")
        except Exception as e:
            ok, msg = False, str(e)
        out.append({"name": "Talon Pilot answers", "ok": ok, "detail": msg, "fix": ""})
        np_ok = self.np.available.get("windows") or self.np.available.get("spotify_title")
        out.append({"name": "Now Playing source", "ok": bool(np_ok),
                    "detail": "Windows media controls" if self.np.available.get("windows") else ("window titles" if np_ok else "not on Windows"), "fix": ""})
        return out

    @staticmethod
    def vrchat_osc_root() -> str:
        return os.path.join(os.path.expanduser("~"), "AppData", "LocalLow", "VRChat", "VRChat", "OSC")

    def vrchat_osc_configs(self) -> List[Dict]:
        out = []
        for p in glob.glob(os.path.join(self.vrchat_osc_root(), "usr_*", "Avatars", "avtr_*.json")):
            try:
                txt = open(p, encoding="utf-8-sig", errors="replace").read()
            except OSError:
                continue
            if "TP/" not in txt:
                continue                                     # not a Talon Pilot avatar
            out.append({"path": p, "has_link": "TP/Bus/Clk" in txt})
        return out

    def doctor_fix(self, what: str) -> str:
        if what == "delete_stale_configs":
            n = 0
            for c in self.vrchat_osc_configs():
                if not c["has_link"]:
                    try:
                        shutil.move(c["path"], c["path"] + ".old"); n += 1
                    except OSError:
                        pass
            return f"Moved {n} old avatar OSC config(s) aside. Change avatar (or reload yours) in VRChat so it writes fresh ones."
        return "?"

    # ------------------------------------------------------------ files
    def import_files(self, paths: List[str], target: str = "auto") -> Dict[str, int]:
        total: Dict[str, int] = {}
        self.backup("before import")
        for p in paths:
            r = formats.import_file(self.db, p, target)
            for k, v in r.items():
                total[k] = total.get(k, 0) + v
            self.log(f"Imported {os.path.basename(p)}: " + ", ".join(f"{v} {k}" for k, v in r.items() if v))
        self.db.save()
        return total

    # ------------------------------------------------------------ background chores
    def _housekeeping(self):
        last_auto = time.time()
        last_save_rev = self.db.revision
        while not self._stop.wait(2.0):
            try:
                self.mirror.tick()
                # autosave edits
                if self.db.revision != last_save_rev and not (self.syncer and self.syncer.busy):
                    self.db.save()
                    last_save_rev = self.db.revision
                # scheduled TalonSync
                m = int(self.settings.get("auto_sync_minutes", 0))
                if m > 0 and time.time() - last_auto > m * 60:
                    last_auto = time.time()
                    if self._vrchat_alive():
                        self.start_sync("schedule")
                # import folder
                folder = self.settings.get("watch_import_folder")
                if folder and os.path.isdir(folder):
                    for p in glob.glob(os.path.join(folder, "*")):
                        if not os.path.isfile(p) or p.endswith((".imported", ".failed")):
                            continue
                        mt = os.path.getmtime(p)
                        if time.time() - mt < 3 or self._watch_seen.get(p) == mt:
                            continue
                        self._watch_seen[p] = mt
                        try:
                            self.import_files([p])
                            os.replace(p, p + ".imported")
                        except Exception as e:
                            self.log(f"Import of {os.path.basename(p)} failed: {e}")
                            try:
                                os.replace(p, p + ".failed")
                            except OSError:
                                pass
            except Exception as e:
                self.log(f"housekeeping: {e}")

    # ------------------------------------------------------------ state for the GUI
    def state(self) -> Dict:
        L, hs = self.link, self.syncer
        st = asdict(hs.status) if hs else {}
        alive = self._vrchat_alive()
        pda_seen = bool(self.bus and self.bus.connected_recently)
        req = bool(L and L.get(pr.SYNC_REQ))
        return {
            "version": __version__, "stale_exe": _stale_exe(),
            "connection": {
                "listening": bool(L and L.listening), "error": L.error if L else "", "port": L.listen_addr[1] if L else 0,
                "send": f"{L.send_addr[0]}:{L.send_addr[1]}" if L else "", "vrchat": alive, "pda": pda_seen,
                "oscquery": bool(self.oscq), "demo": bool(self.demo), "avatar": L.avatar_id if L else None,
                "rx": L.rx_count if L else 0, "tx": L.tx_count if L else 0, "pda_waiting": req,
            },
            "sync": st,
            "last_sync": self.db.base.last_sync, "sync_count": self.db.base.count,
            "reports": [asdict(r) for r in (hs.reports[:1] if hs else [])],
            "now_playing": {**asdict(self.np.track), "sent": self.np_sent.title, "error": self.np_error,
                            "sources": self.np.available},
            "counts": {k: len(self.db.kind(k)) for k in ("contacts", "events", "tasks", "memos")},
            "device": {"owner": self.db.device.owner, "pet": self.db.device.pet, "pet_read": self.db.device.pet_read,
                       "pda_info": self.db.device.pda_info},
            "demo_screen": self.demo.screen if self.demo else "",
            "pclink": self.pc.state(),
            "mirror": self.mirror.state(),
            "revision": self.db.revision,
            "log": list(self.log_lines)[-60:],
        }


def play_chirp():
    """The TalonSync 'done' chirp (two rising beeps), Windows only."""
    if sys.platform != "win32":
        return
    def go():
        try:
            import winsound
            for f, d in ((1568, 70), (2093, 110)):
                winsound.Beep(f, d)
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()


_STALE = None


def _stale_exe():
    """Built exe only: the version of the source files next to it, when that's not the version
    baked into this exe (someone unzipped an update but didn't rebuild). Else ""."""
    global _STALE
    if _STALE is None:
        _STALE = ""
        try:
            if getattr(sys, "frozen", False):
                import re as _re
                src = os.path.join(os.path.dirname(sys.executable), "talonsync", "__init__.py")
                if os.path.exists(src):
                    m = _re.search(r'__version__\s*=\s*"([^"]+)"', open(src, encoding="utf-8").read())
                    if m and m.group(1) != __version__:
                        _STALE = m.group(1)
        except Exception:
            pass
    return _STALE

