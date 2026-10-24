"""What's playing on this PC, for the PDA's Now Playing card (and optionally the VRChat chatbox).

Sources, best first:
  windows        This computer's media controls (the setting keeps its old name):
                   Windows  SMTC: Spotify, browsers/YouTube, Apple Music, foobar2000, VLC, MusicBee...
                            anything in the volume flyout. Needs `winsdk` (the build script installs it).
                   Linux    MPRIS: Spotify, Firefox/Chrome, VLC, mpv, Rhythmbox, Elisa... anything your
                            desktop's media controls show. Uses `playerctl` or `gdbus` (no Python packages).
                   macOS    Spotify and Apple Music, asked through AppleScript.
  spotify_title  Window titles of Spotify / foobar2000 / VLC / Winamp / AIMP (no extra packages).
  manual         Whatever you type in Settings.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Track:
    title: str = ""
    artist: str = ""
    album: str = ""
    playing: bool = False
    position: Optional[float] = None    # 0..1
    source: str = ""
    app: str = ""

    def key(self):
        return (self.title, self.artist, self.playing)


# ---------------------------------------------------------------- Windows media controls
def _smtc_module():
    for name in ("winsdk.windows.media.control", "winrt.windows.media.control"):
        try:
            return __import__(name, fromlist=["GlobalSystemMediaTransportControlsSessionManager"])
        except Exception:
            continue
    return None


_SMTC = None


def windows_media() -> Optional[Track]:
    global _SMTC
    if sys.platform != "win32":
        return None
    if _SMTC is None:
        _SMTC = _smtc_module() or False
    if not _SMTC:
        return None
    import asyncio

    async def get():
        mgr = await _SMTC.GlobalSystemMediaTransportControlsSessionManager.request_async()
        ses = mgr.get_current_session()
        if ses is None:
            return None
        props = await ses.try_get_media_properties_async()
        info = ses.get_playback_info()
        status = int(info.playback_status) if info is not None else 0
        tl = ses.get_timeline_properties()
        pos = None
        try:
            end = tl.end_time.total_seconds() if hasattr(tl.end_time, "total_seconds") else tl.end_time.duration / 1e7
            cur = tl.position.total_seconds() if hasattr(tl.position, "total_seconds") else tl.position.duration / 1e7
            if end > 0:
                # the position is only updated when the player reports it; extrapolate while playing
                upd = tl.last_updated_time
                try:
                    import datetime as _dt
                    age = (_dt.datetime.now(_dt.timezone.utc) - upd).total_seconds()
                    if status == 4 and 0 < age < end:
                        cur += age
                except Exception:
                    pass
                pos = max(0.0, min(1.0, cur / end))
        except Exception:
            pos = None
        return Track(title=props.title or "", artist=props.artist or props.album_artist or "", album=props.album_title or "",
                     playing=status == 4, position=pos, source="windows", app=getattr(ses, "source_app_user_model_id", "") or "")

    try:
        return asyncio.run(get())
    except Exception:
        return None


# ---------------------------------------------------------------- Linux: MPRIS over D-Bus
def _run(cmd, timeout=2.0) -> str:
    import subprocess
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _gv_str(text: str, key: str) -> str:
    """A string (or the first string of a list) for key in gdbus's GVariant text."""
    m = re.search(r"'%s': <(?:\[)?'((?:[^'\\]|\\.)*)'" % re.escape(key), text)
    if not m:
        m = re.search(r"'%s': <(?:\[)?\"((?:[^\"\\]|\\.)*)\"" % re.escape(key), text)
    return m.group(1).encode("utf-8", "backslashreplace").decode("unicode_escape", "ignore") if m else ""


def _gv_int(text: str, key: str) -> Optional[int]:
    m = re.search(r"'%s': <(?:u?int64 |uint64 |int32 )?(-?\d+)>" % re.escape(key), text)
    return int(m.group(1)) if m else None


def linux_media() -> Optional[Track]:
    if not sys.platform.startswith("linux"):
        return None
    import shutil
    if shutil.which("playerctl"):
        out = _run(["playerctl", "metadata", "--format", "{{status}}\t{{artist}}\t{{title}}\t{{album}}\t{{position}}\t{{mpris:length}}\t{{playerName}}"])
        if out.strip():
            st, ar, ti, al, pos, ln, app = (out.rstrip("\n").split("\t") + [""] * 7)[:7]
            p = None
            try:
                if ln and float(ln) > 0: p = max(0.0, min(1.0, float(pos) / float(ln)))
            except ValueError:
                p = None
            return Track(title=ti, artist=ar, album=al, playing=st == "Playing", position=p, source="windows", app=app)
    if not shutil.which("gdbus"):
        return None
    names = re.findall(r"'(org\.mpris\.MediaPlayer2\.[^']+)'", _run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus",
                                                                   "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames"]))
    best = None
    for name in names:
        out = _run(["gdbus", "call", "--session", "--dest", name, "--object-path", "/org/mpris/MediaPlayer2",
                    "--method", "org.freedesktop.DBus.Properties.GetAll", "org.mpris.MediaPlayer2.Player"])
        if not out:
            continue
        status = _gv_str(out, "PlaybackStatus")
        title, artist = _gv_str(out, "xesam:title"), _gv_str(out, "xesam:artist")
        if not (title or artist):
            continue
        ln, pos = _gv_int(out, "mpris:length"), _gv_int(out, "Position")
        p = max(0.0, min(1.0, pos / ln)) if ln and pos is not None and ln > 0 else None
        t = Track(title=title, artist=artist, album=_gv_str(out, "xesam:album"), playing=status == "Playing", position=p,
                  source="windows", app=name.split(".")[3] if name.count(".") >= 3 else name)
        if t.playing:
            return t
        best = best or t
    return best


# ---------------------------------------------------------------- macOS: Spotify / Music via AppleScript
def _mac_script(app: str) -> str:
    return (f'tell application "{app}"\n'
            '  if player state is playing then\n    set st to "Playing"\n  else\n    set st to "Paused"\n  end if\n'
            '  set t to current track\n'
            f'  return st & tab & (artist of t) & tab & (name of t) & tab & (album of t) & tab & (player position as text) & tab & ((duration of t) as text) & tab & "{app}"\n'
            'end tell')


def mac_media() -> Optional[Track]:
    if sys.platform != "darwin":
        return None
    out = ""
    for app in ("Spotify", "Music"):
        # ask "is it running" first: talking to an app that isn't running would launch it
        if _run(["osascript", "-e", f'application "{app}" is running']).strip() == "true":
            out = _run(["osascript", "-e", _mac_script(app)], timeout=3.0).strip()
            if out:
                break
    if not out:
        return None
    st, ar, ti, al, pos, ln, app = (out.split("\t") + [""] * 7)[:7]
    p = None
    try:
        dur = float(ln.replace(",", "."))
        if dur > 1000: dur /= 1000.0                      # Spotify reports milliseconds, Music seconds
        if dur > 0: p = max(0.0, min(1.0, float(pos.replace(",", ".")) / dur))
    except ValueError:
        p = None
    return Track(title=ti, artist=ar, album=al, playing=st == "Playing", position=p, source="windows", app=app)


def system_media() -> Optional[Track]:
    if sys.platform == "win32":
        return windows_media()
    if sys.platform == "darwin":
        return mac_media()
    return linux_media()


# ---------------------------------------------------------------- media remote (PC Link)
def media_command(action: str) -> bool:
    """action: "play_pause" | "next" | "previous". Sends the system media key (Windows), MPRIS (Linux)
    or AppleScript (macOS). Returns True if something was sent."""
    if action not in ("play_pause", "next", "previous"):
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            vk = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1}[action]
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)          # key down
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)          # key up
            return True
        except Exception:
            return False
    if sys.platform == "darwin":
        verb = {"play_pause": "playpause", "next": "next track", "previous": "previous track"}[action]
        for app in ("Spotify", "Music"):
            if _run(["osascript", "-e", f'application "{app}" is running']).strip() == "true":
                _run(["osascript", "-e", f'tell application "{app}" to {verb}'])
                return True
        return False
    import shutil
    if shutil.which("playerctl"):
        _run(["playerctl", {"play_pause": "play-pause", "next": "next", "previous": "previous"}[action]])
        return True
    if shutil.which("gdbus"):
        names = re.findall(r"'(org\.mpris\.MediaPlayer2\.[^']+)'", _run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus",
                                                                       "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames"]))
        method = {"play_pause": "PlayPause", "next": "Next", "previous": "Previous"}[action]
        for name in names[:1]:
            _run(["gdbus", "call", "--session", "--dest", name, "--object-path", "/org/mpris/MediaPlayer2",
                  "--method", "org.mpris.MediaPlayer2.Player." + method])
            return True
    return False


# ---------------------------------------------------------------- window titles (no packages)
_TITLE_RULES = [
    # (process name, regex on the window title, title group, artist group)
    ("spotify.exe", re.compile(r"^(?P<a>.+?) - (?P<t>.+)$"), "t", "a"),
    ("foobar2000.exe", re.compile(r"^(?P<a>.+?) - (?:\[.*?\] )?(?P<t>.+?)(?:\s+\[foobar2000.*\])?$"), "t", "a"),
    ("vlc.exe", re.compile(r"^(?P<t>.+?) - VLC media player$"), "t", None),
    ("winamp.exe", re.compile(r"^(?:\d+\. )?(?P<a>.+?) - (?P<t>.+?) - Winamp"), "t", "a"),
    ("aimp.exe", re.compile(r"^(?P<a>.+?) - (?P<t>.+)$"), "t", "a"),
    ("musicbee.exe", re.compile(r"^(?P<a>.+?) - (?P<t>.+?) - MusicBee$"), "t", "a"),
]


def window_titles() -> Optional[Track]:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    found = []

    def proc_name(hwnd):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = kernel32.OpenProcess(0x1000, False, pid.value)       # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(520)
            n = wintypes.DWORD(520)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                return buf.value.rsplit("\\", 1)[-1].lower()
        finally:
            kernel32.CloseHandle(h)
        return ""

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    for hwnd, title in found:
        pname = None
        for proc, rx, tg, ag in _TITLE_RULES:
            if " - " not in title:
                break
            if pname is None:
                pname = proc_name(hwnd)
            if pname != proc:
                continue
            m = rx.match(title)
            if m:
                return Track(title=m.group(tg).strip(), artist=(m.group(ag).strip() if ag else ""), playing=True,
                             source="window", app=proc)
    return None


# ---------------------------------------------------------------- service
class NowPlaying:
    """Polls the chosen source and calls on_change(track) when the song (or play state) changes,
    and on_position(track) when only the position moved."""

    def __init__(self, settings, on_change: Callable[[Track], None], on_position: Callable[[Track], None] = None,
                 log: Callable[[str], None] = None):
        self.s = settings
        self.on_change = on_change
        self.on_position = on_position
        self.log = log or (lambda m: None)
        self.track = Track()
        import shutil
        self.available = {"windows": (_smtc_module() is not None) if sys.platform == "win32" else
                                     (sys.platform == "darwin" or bool(shutil.which("playerctl") or shutil.which("gdbus"))),
                          "spotify_title": sys.platform == "win32", "manual": True}
        self._run = False
        self._last_pos = -1.0

    def read(self) -> Track:
        src = self.s.get("np_source", "auto")
        if src == "manual":
            t, a = self.s.get("np_manual_title", ""), self.s.get("np_manual_artist", "")
            return Track(title=t, artist=a, playing=bool(t or a), source="manual")
        if src in ("auto", "windows"):
            t = system_media()
            if t and (t.title or t.artist):
                return t
            if src == "windows":
                return Track()
        if src in ("auto", "spotify_title"):
            t = window_titles()
            if t:
                return t
        return Track()

    def start(self):
        if self._run:
            return
        self._run = True
        threading.Thread(target=self._loop, name="now-playing", daemon=True).start()

    def stop(self):
        self._run = False

    def _loop(self):
        while self._run:
            try:
                if self.s.get("now_playing", True):
                    t = self.read()
                    if t.key() != self.track.key():
                        self.track = t
                        self._last_pos = t.position if t.position is not None else -1
                        self.on_change(t)
                    else:
                        self.track.position = t.position
                        if (self.on_position and t.position is not None and self.s.get("np_position", True)
                                and abs(t.position - self._last_pos) >= 1.5 / 255):
                            self._last_pos = t.position
                            self.on_position(t)
            except Exception as e:
                self.log(f"now playing: {e}")
            time.sleep(max(0.5, float(self.s.get("np_interval", 2.0))))
