"""TalonSync settings: one JSON file, every option with a default, validated on load."""
from __future__ import annotations

import json
import os
import sys
import threading
from copy import deepcopy

CONDUITS = ["settings", "tasks", "memos", "calendar", "contacts", "notepad", "hypno"]
ACTIONS = ["sync", "pc_overwrites", "pda_overwrites", "nothing"]

DEFAULTS = {
    # ---- connection
    "osc_send_host": "127.0.0.1",
    "osc_send_port": 9000,
    "osc_listen_host": "127.0.0.1",
    "osc_listen_port": 9001,
    "oscquery": True,                 # advertise over OSCQuery (zeroconf) so VRChat finds us even with other OSC apps
    "oscquery_random_port": True,     # with OSCQuery on, listen on a free port instead of 9001
    "ack_timeout": 1.5,
    "bus_settle_ms": 20,
    "bus_gap_ms": 0,
    "bus_retries": 2,
    "connect_timeout": 10.0,
    "demo_pda": False,
    "exp_terminal": False,            # EXPERIMENTAL, opt in: be the CPU for the PDA's Terminal (Talon Enhanced BASIC)                # a built-in pretend PDA, to try TalonSync without VRChat
    # ---- TalonSync
    "answer_pda_requests": True,      # the PDA's own TalonSync button starts a sync
    "auto_sync_minutes": 0,           # 0 = off
    "sync_on_start": False,
    "conflict": "pc",                 # pc | pda | duplicate
    "pda_blank_removes": False,       # a line erased on the PDA deletes the PC record (else just un-pins it)
    "conduits": {c: "sync" for c in CONDUITS},
    "done_hold_seconds": 2.5,
    "sound": True,
    "chirp_on_done": True,
    # ---- backups and files
    "backup_keep": 20,
    "backup_on_sync": True,
    "auto_export": False,
    "auto_export_folder": "",
    "auto_export_formats": ["vcf", "ics", "csv", "md", "png", "json"],
    "watch_import_folder": "",
    # ---- now playing
    "now_playing": True,
    "np_source": "auto",              # auto | windows | spotify_title | manual
    "np_manual_title": "",
    "np_manual_artist": "",
    "np_interval": 2.0,
    "np_position": True,
    "np_swap": False,                 # artist on the first line
    "np_upper": False,
    "np_clear_when_paused": True,
    "np_only_when_connected": True,
    "chatbox_now_playing": False,
    "chatbox_format": "♪ {title} - {artist}",
    "chatbox_interval": 6.0,
    # ---- TalonStar 4000
    "ts_enabled": True,
    "ts_place": {},                   # {name, admin1, country, lat, lon}
    "ts_units": "imperial",           # imperial | metric
    "ts_refresh_minutes": 15,
    "ts_region_count": 7,
    "ts_extra_cities": [],
    "ts_pages": ["current", "observations", "local", "extended", "hourly", "regional", "almanac", "agenda"],
    "ts_page_seconds": 10,
    "ts_theme": "classic",            # classic | owl | gryphon | dusk
    "ts_crt": True,
    "ts_scanlines": 0.35,
    "ts_crawl": True,
    "ts_crawl_text": "Thanks for watching TalonStar 4000, your local forecast from the aerie. Stay warm and stay clever!",
    "ts_crawl_speed": 90,
    "ts_clock24": False,
    "ts_show_seconds": True,
    "ts_music": True,
    "ts_volume": 0.55,
    "ts_animations": "full",          # full | calm | off
    "ts_send_pda": True,              # put the weather on the Talon Pilot's TalonStar app
    "ts_pda_jazz": 1,                 # 0 off, 1 only I hear it, 2 everyone nearby hears it
    "ts_pda_ticker": "auto",          # auto (weather summary) | custom | twitch (your Twitch chat) | off
    "ts_pda_ticker_text": "",         # custom PDA ticker, up to 45 characters
    "ts_demo_weather": True,          # show sample weather when the internet is out
    # ---- PC Link (Talon Pilot 2.11+)
    "pc_link": True,
    "pc_monitor": True,               # CPU / GPU / RAM load and temperatures
    "pc_batteries": True,             # headset and controller battery (SteamVR)
    "pc_heart": True,                 # heart rate from a heart-rate app (avatar parameter HR)
    "pc_messages": True,
    "pc_message_chirp": True,         # the PDA chirps for a new message
    "pc_reminders": True,             # calendar reminders become PDA messages
    "pc_media_remote": True,          # the PDA's media buttons control music on this PC
    "pc_focus_minutes": 25,
    "pc_break_minutes": 5,
    "pc_timer_loop": True,            # focus -> break -> focus ...
    "twitch_channel": "",             # for the Twitch chat ticker / mentions
    "twitch_name": "",                # your Twitch name, for mentions (defaults to the channel)
    "pc_twitch_mentions": False,      # @mentions in that chat become PDA messages
    # ---- Desktop click (Talon Pilot 2.12+, Windows, VRChat desktop mode)
    "desk_click": True,               # a mouse button taps the PDA where you look (TP/Desk/Tap)
    "desk_click_button": "middle",    # middle | side1 | side2 | f1..f12 | a letter
    "desk_here_button": "",           # optional: "Bring PDA in front" (TP/Desk/Here); "" = none
    # ---- app
    "theme": "aerie",                 # aerie | classic | owl | gryphon | light
    "accent": "#4f8cff",
    "animations": True,
    "compact": False,
    "start_minimized": False,
    "close_to_tray": True,
    "start_with_windows": False,
    "confirm_destructive": True,
    "log_level": "info",
    "first_run": True,
    "window": {"w": 1180, "h": 760},
}


def data_dir() -> str:
    exe_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0] or "."))
    if os.path.exists(os.path.join(exe_dir, "portable.txt")):
        return os.path.join(exe_dir, "TalonSync Data")
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "TalonSync")


class Settings:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        self.data = deepcopy(DEFAULTS)
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                self.update(json.load(f), save=False)
        except Exception as e:
            print(f"TalonSync: settings unreadable ({e}), using defaults")

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
            os.replace(tmp, self.path)

    def __getitem__(self, k):
        with self.lock:
            return self.data[k]

    def get(self, k, default=None):
        with self.lock:
            return self.data.get(k, default)

    def update(self, changes: dict, save: bool = True):
        """Apply changes with type checks against the defaults; unknown keys are ignored."""
        with self.lock:
            for k, v in (changes or {}).items():
                if k not in DEFAULTS:
                    continue
                d = DEFAULTS[k]
                try:
                    if isinstance(d, bool):
                        v = bool(v)
                    elif isinstance(d, int):
                        v = int(v)
                    elif isinstance(d, float):
                        v = float(v)
                    elif isinstance(d, str):
                        v = str(v)
                    elif isinstance(d, dict):
                        v = {**self.data.get(k, d), **{kk: vv for kk, vv in dict(v).items()}}
                    elif isinstance(d, list):
                        v = list(v)
                except (TypeError, ValueError):
                    continue
                if k == "conflict" and v not in ("pc", "pda", "duplicate"):
                    continue
                if k == "conduits":
                    v = {c: (v.get(c) if v.get(c) in ACTIONS else "sync") for c in CONDUITS}
                if k.endswith("_port"):
                    v = max(0, min(65535, v))
                self.data[k] = v
        if save:
            self.save()

    def as_dict(self) -> dict:
        with self.lock:
            return deepcopy(self.data)
