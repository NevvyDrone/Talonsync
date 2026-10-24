"""PC Link: your computer's vital signs, messages, music controls and a focus timer on the Talon Pilot.

Everything here is optional and degrades quietly: a source that isn't available on this PC just
shows "--" on the PDA. Sources:
  * CPU / RAM            psutil (installed by the build scripts)
  * CPU temperature      psutil on Linux; not available on Windows/macOS without vendor tools
  * GPU load / temp      nvidia-smi (NVIDIA drivers)
  * Headset + controller battery   SteamVR, through the `openvr` package
  * Heart rate           any heart-rate app that sends the avatar parameter HR (or HeartRateInt) to
                         VRChat; VRChat echoes it to TalonSync, which shows it on the PDA
  * Messages             calendar reminders, the "Send a message" box, Twitch chat mentions, other
                         programs over OSC (/talonpilot/message "title" "text"), and on Linux your
                         desktop notifications
  * Media remote         system media keys (Windows), MPRIS (Linux), Spotify/Music (macOS)
Talon Pilot 2.11 (link protocol 3) or newer is needed on the avatar.
"""
from __future__ import annotations

import re
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from . import protocol as pr
from .bus import BusError, Nak
from .nowplaying import media_command

PCLINK_APP = 30          # the PDA app that shows PC values

try:
    import psutil                                                 # type: ignore
except Exception:                                                 # pragma: no cover - optional
    psutil = None

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd: List[str], timeout: float = 3.0) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW).stdout
    except Exception:
        return ""


# ---------------------------------------------------------------- sources
def cpu_ram() -> Dict[int, int]:
    out: Dict[int, int] = {}
    if psutil is None:
        return out
    try:
        out[pr.PC_CPU] = int(round(psutil.cpu_percent(interval=None)))
        out[pr.PC_RAM] = int(round(psutil.virtual_memory().percent))
        temps = getattr(psutil, "sensors_temperatures", lambda: {})() or {}
        for name in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
            if temps.get(name):
                out[pr.PC_CPU_TEMP] = int(round(max(t.current for t in temps[name])))
                break
    except Exception:
        pass
    return out


def gpu() -> Dict[int, int]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {}
    line = _run([exe, "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]).strip().splitlines()
    try:
        load, temp = [int(float(x)) for x in line[0].split(",")[:2]]
        return {pr.PC_GPU: load, pr.PC_GPU_TEMP: temp}
    except Exception:
        return {}


class SteamVrBatteries:
    """Headset and controller charge from SteamVR (needs the `openvr` package and SteamVR running)."""
    def __init__(self):
        self.vr = None
        self.ok = None              # None = not tried, False = not available
        self.why = ""
        self._next_try = 0.0

    def read(self) -> Dict[int, int]:
        try:
            import openvr                                         # type: ignore
        except Exception:
            self.ok, self.why = False, "openvr isn't installed"
            return {}
        if self.vr is None:
            if time.time() < self._next_try:
                return {}
            try:
                self.vr = openvr.init(openvr.VRApplication_Background)
                self.ok, self.why = True, ""
            except Exception as e:                                # SteamVR not running
                self.vr, self.ok, self.why = None, False, "SteamVR isn't running"
                self._next_try = time.time() + 30
                return {}
        out: Dict[int, int] = {}
        try:
            for i in range(openvr.k_unMaxTrackedDeviceCount):
                cls = self.vr.getTrackedDeviceClass(i)
                if cls == openvr.TrackedDeviceClass_Invalid:
                    continue
                try:
                    pct = self.vr.getFloatTrackedDeviceProperty(i, openvr.Prop_DeviceBatteryPercentage_Float)
                except Exception:
                    continue
                v = int(round(max(0.0, min(1.0, pct)) * 100))
                if cls == openvr.TrackedDeviceClass_HMD:
                    out[pr.PC_HMD] = v
                elif cls == openvr.TrackedDeviceClass_Controller:
                    role = self.vr.getControllerRoleForTrackedDeviceIndex(i)
                    if role == openvr.TrackedControllerRole_LeftHand:
                        out[pr.PC_LEFT] = v
                    elif role == openvr.TrackedControllerRole_RightHand:
                        out[pr.PC_RIGHT] = v
        except Exception:
            try:
                openvr.shutdown()
            except Exception:
                pass
            self.vr, self.ok, self.why = None, False, "SteamVR closed"
        return out


class LinuxNotifications(threading.Thread):
    """Desktop notifications on Linux, read from the session bus with dbus-monitor."""
    def __init__(self, on_message: Callable[[str, str], None]):
        super().__init__(daemon=True, name="notifications")
        self.on_message = on_message
        self.proc = None
        self.ok = sys.platform.startswith("linux") and bool(shutil.which("dbus-monitor"))

    def run(self):
        if not self.ok:
            return
        try:
            self.proc = subprocess.Popen(["dbus-monitor", "--session", "interface='org.freedesktop.Notifications',member='Notify'"],
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except Exception:
            self.ok = False
            return
        strings: List[str] = []
        collecting = False
        for line in self.proc.stdout:
            if "member=Notify" in line:
                collecting, strings = True, []
                continue
            if collecting:
                m = re.match(r'\s*string "(.*)"\s*$', line)
                if m:
                    strings.append(m.group(1))
                    if len(strings) == 4:                         # app name, icon, summary, body
                        collecting = False
                        app, _, summary, body = strings
                        self.on_message(summary or app, body or summary)

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass


def twitch_channel_name(text: str) -> str:
    """'MyName', '#myname', '@MyName' or 'https://www.twitch.tv/myname' -> 'myname'."""
    t = (text or "").strip()
    m = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", t)
    if m:
        t = m.group(1)
    return re.sub(r"[^A-Za-z0-9_]", "", t).lower()


class TwitchChat(threading.Thread):
    """Read-only, anonymous Twitch chat (no account needed). TLS on 6697, plain 6667 as a fallback."""
    HOST = "irc.chat.twitch.tv"

    def __init__(self, channel: str, on_line: Callable[[str, str], None], log=print, host: str = None, ports=((6697, True), (6667, False))):
        super().__init__(daemon=True, name="twitch")
        self.channel = twitch_channel_name(channel)
        self.on_line = on_line
        self.log = log
        self.host = host or self.HOST
        self.ports = ports
        self._stop = threading.Event()
        self.connected = False
        self.error = ""
        self.last = ""
        self.count = 0

    def _open(self):
        last_err = None
        for port, tls in self.ports:
            try:
                s = socket.create_connection((self.host, port), timeout=10)
                if tls:
                    s = ssl.create_default_context().wrap_socket(s, server_hostname=self.host)
                return s
            except Exception as e:
                last_err = e
        raise last_err or OSError("no connection")

    def run(self):
        while not self._stop.is_set() and self.channel:
            s = None
            try:
                s = self._open()
                s.settimeout(360)
                nick = "justinfan%d" % (int(time.time()) % 90000 + 10000)
                s.sendall(f"PASS SCHMOOPIIE\r\nNICK {nick}\r\nJOIN #{self.channel}\r\n".encode())
                buf = b""
                while not self._stop.is_set():
                    data = s.recv(4096)
                    if not data:
                        raise OSError("Twitch closed the connection")
                    buf += data
                    while b"\r\n" in buf:
                        raw, buf = buf.split(b"\r\n", 1)
                        line = raw.decode("utf-8", "replace")
                        if line.startswith("PING"):
                            s.sendall(b"PONG :tmi.twitch.tv\r\n")
                            continue
                        if " 366 " in line or " JOIN #" in line:
                            if not self.connected:
                                self.connected, self.error = True, ""
                                self.log(f"Twitch chat: connected to #{self.channel}")
                            continue
                        if " NOTICE " in line and not self.connected:
                            self.error = line.split(" :", 1)[-1]
                        m = re.match(r"(?:@\S+ )?:(\w+)!\S+ PRIVMSG #\S+ :(.*)", line)
                        if m:
                            self.connected = True
                            self.last = f"{m.group(1)}: {m.group(2)}"
                            self.count += 1
                            try:
                                self.on_line(m.group(1), m.group(2))
                            except Exception as e:
                                self.log(f"Twitch chat: {e}")
            except Exception as e:
                if not self._stop.is_set():
                    self.error = str(e) or e.__class__.__name__
                    self.log(f"Twitch chat: {self.error} (retrying in 15 s)")
            finally:
                if s is not None:
                    try:
                        s.close()
                    except Exception:
                        pass
            self.connected = False
            self._stop.wait(15)

    def stop(self):
        self._stop.set()


# ---------------------------------------------------------------- the service
class PcLink:
    def __init__(self, app, log=print):
        self.app = app
        self.log = log
        self.vr = SteamVrBatteries()
        self.notes = LinuxNotifications(self.message)
        self.twitch: Optional[TwitchChat] = None
        self.values: Dict[int, int] = {}          # what we'd like the PDA to show
        self.sent: Dict[int, int] = {}            # what it shows
        self.heart = (0, 0.0)                     # (bpm, when)
        self.messages: List[Dict] = []            # newest first
        self.unread = 0
        self.timer = {"state": 0, "end": 0.0, "length": 0.0}     # 0 off, 1 focus, 2 break
        self.protocol = 0
        self._proto_checked = 0.0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._reminded: set = set()
        self._sent_loc = None
        self._pending_message = None
        self._last_full = 0.0
        # 2.12 (TalonSync 1.7): which app the PDA shows (VRChat reports TP/App over OSC). CPU/GPU are only
        # measured while PC Link is open - the GPU check runs nvidia-smi, which can cause small hitches.
        self.pda_app: Optional[int] = None
        self._last_monitor = 0.0
        self._last_battery = 0.0
        self.chat_line = ""

    # ---------------------------------------------------------- lifecycle
    def start(self):
        if self.notes.ok:
            self.notes.start()
        self.apply_settings()
        threading.Thread(target=self._loop, daemon=True, name="pclink").start()

    def stop(self):
        self._stop.set()
        self.notes.stop()
        if self.twitch:
            self.twitch.stop()

    def apply_settings(self):
        s = self.app.settings
        want = twitch_channel_name(s.get("twitch_channel") or "")
        if self.twitch and (not want or self.twitch.channel != want):
            self.twitch.stop(); self.twitch = None
        if want and not self.twitch:
            self.twitch = TwitchChat(want, self._chat, log=self.log)
            self.twitch.start()

    def forget_pda(self):
        """New avatar or reconnect: resend everything and re-check the protocol."""
        with self._lock:
            self.sent.clear()
            self.protocol = 0
            self._proto_checked = 0.0
            self._sent_loc = None

    # ---------------------------------------------------------- inputs from OSC
    def on_osc(self, addr: str, args) -> bool:
        if not addr.startswith("/avatar/parameters/") and not addr.startswith("/talonpilot/"):
            return False
        name = addr[len("/avatar/parameters/"):] if addr.startswith("/avatar/parameters/") else ""
        if name.startswith("TP/In/I") and args:                       # the digitizer: TalonOS Enhanced taps
            term = getattr(self.app, "terminal", None)
            if term:
                term.on_touch(name[len("TP/In/"):], bool(args[0]))
            return False
        if name == "TP/App" and args:
            try:
                self.pda_app = int(round(float(args[0])))
                term = getattr(self.app, "terminal", None)
                if term:
                    term.on_app(self.pda_app)                         # the Terminal opened: offer the menu
            except (TypeError, ValueError):
                pass
            return False                  # others may want it too
        if name in pr.HEART_PARAMS and args:
            try:
                bpm = int(round(float(args[0])))
                if 20 <= bpm <= 250:
                    self.heart = (bpm, time.time())
            except (TypeError, ValueError):
                pass
            return True
        if name == pr.PC_CMD and args:
            try:
                cmd = int(args[0])
            except (TypeError, ValueError):
                return True
            if cmd:
                threading.Thread(target=self.command, args=(cmd,), daemon=True).start()
            return True
        if addr == "/talonpilot/message":
            a = [str(x) for x in (args or [])]
            if a:
                self.message(a[0], a[1] if len(a) > 1 else "")
            return True
        return False

    def command(self, cmd: int):
        s = self.app.settings
        try:
            self.app.link.set(pr.PC_CMD, 0)                            # ready for the next press
        except Exception:
            pass
        if 40 <= cmd <= 45 and getattr(self.app, "terminal", None):    # the terminal (Talon Pilot 2.18)
            self.app.terminal.on_cmd(cmd)
            return
        if cmd in (pr.CMD_PLAY, pr.CMD_NEXT, pr.CMD_PREV):
            if s.get("pc_media_remote", True):
                act = {pr.CMD_PLAY: "play_pause", pr.CMD_NEXT: "next", pr.CMD_PREV: "previous"}[cmd]
                ok = media_command(act)
                self.log(f"PDA: {act.replace('_', '/')}" + ("" if ok else " (no media player answered)"))
        elif cmd == pr.CMD_TIMER:
            self.timer_toggle()
        elif cmd == pr.CMD_TIMER_RESET:
            self.timer_stop()
        elif cmd == pr.CMD_CLEAR:
            self.clear_messages()

    # ---------------------------------------------------------- messages
    def message(self, title: str, text: str, alert: Optional[bool] = None):
        if not self.app.settings.get("pc_messages", True):
            return
        title, text = pr.to_ascii(title or "").strip(), pr.to_ascii(text or "").strip()
        with self._lock:
            self.messages.insert(0, {"title": title, "text": text, "time": datetime.now().isoformat(timespec="seconds")})
            del self.messages[30:]
            self.unread = min(250, self.unread + 1)
            self._pending_message = (title, text)
        if alert is None:
            alert = self.app.settings.get("pc_message_chirp", True)
        self._push_message(alert)

    def clear_messages(self):
        with self._lock:
            self.unread = 0
            self._pending_message = None
        try:
            if self.protocol >= 3:
                self.app.bus.pc_clear()
                self.sent[pr.PC_UNREAD] = 0
        except BusError:
            pass

    def _push_message(self, alert: bool):
        if self.protocol < 3 or not self.app.bus:
            return
        with self._lock:
            pm = self._pending_message
            self._pending_message = None
        if not pm:
            return
        title, text = pm
        # 15 letters per line: the sender/title on line 1, the start of the text on line 2
        line1 = pr.clean(title, 15)
        line2 = pr.clean(text, 15) if text else ""
        try:
            self.app.bus.pc_message(line1, line2)
            self.app.bus.pc_value(pr.PC_UNREAD, self.unread)
            self.sent[pr.PC_UNREAD] = self.unread
            if alert:
                self.app.bus.pc_alert()
        except BusError:
            with self._lock:
                self._pending_message = pm

    def _chat(self, user: str, text: str):
        self.chat_line = f"{user}: {text}"
        s = self.app.settings
        if s.get("ts_pda_ticker") == "twitch":
            self.app.push_ticker(pr.clean(self.chat_line, 45))
        me = twitch_channel_name(s.get("twitch_name") or s.get("twitch_channel") or "")
        if s.get("pc_twitch_mentions") and me and ("@" + me) in text.lower():
            self.message("Twitch: " + user, text)

    # ---------------------------------------------------------- focus timer
    def timer_toggle(self):
        if self.timer["state"]:
            self.timer_stop()
        else:
            self._timer_phase(1)

    def timer_stop(self):
        self.timer = {"state": 0, "end": 0.0, "length": 0.0}
        self.log("Focus timer stopped")

    def _timer_phase(self, state: int):
        mins = float(self.app.settings.get("pc_focus_minutes" if state == 1 else "pc_break_minutes", 25 if state == 1 else 5))
        self.timer = {"state": state, "end": time.time() + mins * 60, "length": mins * 60}
        self.log(("Focus" if state == 1 else "Break") + f" timer: {mins:g} minutes")

    def _timer_tick(self):
        t = self.timer
        if t["state"] and time.time() >= t["end"]:
            nxt = 2 if t["state"] == 1 else 1
            self.message("Focus timer", "Break time!" if nxt == 2 else "Back to it!", alert=True)
            if self.app.settings.get("pc_timer_loop", True):
                self._timer_phase(nxt)
            else:
                self.timer_stop()

    def timer_values(self) -> Dict[int, int]:
        t = self.timer
        if not t["state"]:
            return {pr.PC_TIMER_STATE: 0, pr.PC_TIMER_MIN: 0, pr.PC_TIMER_FRAC: 0}
        left = max(0.0, t["end"] - time.time())
        return {pr.PC_TIMER_STATE: t["state"], pr.PC_TIMER_MIN: int(left // 60 + (1 if left % 60 else 0)),
                pr.PC_TIMER_FRAC: int(round(left / max(1.0, t["length"]) * 255))}

    # ---------------------------------------------------------- calendar reminders
    def _reminders(self):
        if not self.app.settings.get("pc_reminders", True):
            return
        now = datetime.now()
        for e in self.app.db.events:
            if e.alarm_min is None or e.alarm_min < 0:
                continue
            st = e.start_dt()
            if not st:
                continue
            due = st - timedelta(minutes=e.alarm_min)
            key = (e.id, e.start, e.alarm_min)
            if due <= now <= due + timedelta(minutes=10) and key not in self._reminded:
                self._reminded.add(key)
                self.message(e.title or "Reminder", f"{st:%H:%M} {e.location}".strip(), alert=True)

    # ---------------------------------------------------------- the loop
    def _check_protocol(self):
        bus = self.app.bus
        if not bus or (self.app.syncer and self.app.syncer.busy):
            return
        if self.protocol >= 3 or time.time() - self._proto_checked < 30:
            return
        if not self.app._vrchat_alive() and not self.app.demo:
            return
        self._proto_checked = time.time()
        try:
            self.protocol = bus.ping()
            if self.protocol >= 3:
                self.log("PC Link: the PDA is ready")
        except BusError:
            self.protocol = 0

    def pclink_open(self) -> bool:
        return self.pda_app == PCLINK_APP

    def gather(self, monitor: bool = True, batteries: bool = True) -> Dict[int, int]:
        """monitor / batteries False = keep the last values for those (not measured this time)."""
        s = self.app.settings
        v: Dict[int, int] = {k: pr.PC_NA for k in range(13)}
        keep = (pr.PC_CPU, pr.PC_GPU, pr.PC_CPU_TEMP, pr.PC_GPU_TEMP, pr.PC_RAM) if not monitor else ()
        keep += (pr.PC_HMD, pr.PC_LEFT, pr.PC_RIGHT) if not batteries else ()
        for k in keep:
            if k in self.values:
                v[k] = self.values[k]
        if s.get("pc_monitor", True) and monitor:
            v.update(cpu_ram())
            v.update(gpu())
        if s.get("pc_batteries", True) and batteries:
            v.update(self.vr.read())
        bpm, when = self.heart
        if s.get("pc_heart", True) and bpm and time.time() - when < 20:
            v[pr.PC_HEART] = bpm
        v.update(self.timer_values())
        v[pr.PC_UNREAD] = self.unread
        return {k: max(0, min(255, int(x))) for k, x in v.items()}

    def _loop(self):
        last_slow = 0.0
        while not self._stop.wait(2.0):
            try:
                if not self.app.settings.get("pc_link", True) or not self.app.bus:
                    continue
                self._timer_tick()
                self._reminders()
                self._check_protocol()
                if self.protocol < 3 or (self.app.syncer and self.app.syncer.busy):
                    continue
                now = time.time()
                if now - last_slow >= 5.0:
                    last_slow = now
                    # PC Link open: everything every 5 s. Otherwise: no CPU/GPU at all (the PDA can't show it),
                    # batteries once a minute for the title bar. Unknown app (no OSC output): every 30 s.
                    open_ = self.pclink_open()
                    unknown = self.pda_app is None
                    monitor = open_ or (unknown and now - self._last_monitor >= 30)
                    batteries = open_ or now - self._last_battery >= (30 if unknown else 60)
                    if monitor:
                        self._last_monitor = now
                    if batteries:
                        self._last_battery = now
                    with self._lock:
                        self.values = self.gather(monitor, batteries)
                else:
                    with self._lock:
                        self.values.update(self.timer_values())
                        self.values[pr.PC_UNREAD] = self.unread
                full = time.time() - self._last_full > 60
                if full:
                    self._last_full = time.time()
                for k, x in list(self.values.items()):
                    if full or self.sent.get(k) != x:
                        self.app.bus.pc_value(k, x)
                        self.sent[k] = x
                self._push_message(False)
                self._send_location()
            except Nak:
                self.protocol = 0
            except BusError:
                pass
            except Exception as e:
                self.log(f"PC Link: {e}")

    def _send_location(self):
        place = self.app.weather.place() if self.app.weather else None
        if not place or place.get("lat") is None:
            return
        loc = (round(float(place["lat"]), 1), round(float(place["lon"]), 1))
        if loc != self._sent_loc:
            self.app.bus.sky_location(*loc)
            self._sent_loc = loc

    # ---------------------------------------------------------- for the GUI
    def state(self) -> Dict:
        v = dict(self.values)
        bpm, when = self.heart
        return {
            "pda_ready": self.protocol >= 3, "protocol": self.protocol,
            "pclink_open": self.pclink_open(), "pda_app": self.pda_app,
            "values": {str(k): x for k, x in v.items()},
            "sources": {
                "monitor": psutil is not None, "gpu": bool(shutil.which("nvidia-smi")),
                "batteries": bool(self.vr.ok), "batteries_why": self.vr.why or ("" if self.vr.ok else "not checked yet"),
                "heart": bool(bpm and time.time() - when < 20),
                "notifications": self.notes.ok, "twitch": bool(self.twitch and self.twitch.connected),
                "twitch_channel": self.twitch.channel if self.twitch else "", "twitch_error": self.twitch.error if self.twitch else "",
                "twitch_count": self.twitch.count if self.twitch else 0,
            },
            "messages": self.messages[:10], "unread": self.unread,
            "timer": {"state": self.timer["state"], "left": max(0, int(self.timer["end"] - time.time())) if self.timer["state"] else 0},
            "chat": self.chat_line,
        }
