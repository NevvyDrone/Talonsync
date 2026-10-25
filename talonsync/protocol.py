"""The TalonSync link protocol - must match Editor/TalonPilotAnimatorBus.cs in the Unity package.

Everything is an avatar parameter reached over OSC:
  TalonSync handshake
    TP/Sync/Req    Bool   PDA -> PC   the PDA's TalonSync button is waiting for the PC
    TP/Sync/State  Int    PC -> PDA   0 idle, 1 PC wants to sync, 2 transferring, 3 done, 4 failed
    TP/Sync/Stage  Float  PC -> PDA   stage / 8 (0 connecting ... 8 backing up)
    TP/Sync/Prog   Float  PC -> PDA   progress bar 0..1
  Bus (one acknowledged transfer per clock)
    PC sets data lines + TP/Bus/Addr, raises TP/Bus/Clk; PDA latches and sets TP/Bus/Ack = 1
    (2 = unknown address); PC lowers Clk; PDA sets Ack = 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

P = "TP/"
BUS_ADDR, BUS_CLK, BUS_ACK = P + "Bus/Addr", P + "Bus/Clk", P + "Bus/Ack"
BUS_LEN, BUS_V, BUS_N = P + "Bus/Len", P + "Bus/V", P + "Bus/N"
SYNC_REQ, SYNC_STATE, SYNC_STAGE, SYNC_PROG = P + "Sync/Req", P + "Sync/State", P + "Sync/Stage", P + "Sync/Prog"
PC_HELLO = P + "PC/Hello"          # 2.17: answered at power-on so the PDA's self-test can report the link (int: our version digits, capped at 255)
POWER = P + "On"


def BUS_B(i: int) -> str:
    return f"{P}Bus/B{i}"


def BUS_C(i: int) -> str:
    return f"{P}Bus/C{i}"


BUS_CHARS = 15            # characters per text line
INK_BITS_MAX = 24         # B lines on a fine canvas (12 on standard)

# addresses
ADDR_INK_WRITE, ADDR_INK_READ = 0, 32
ADDR_TEXT_WRITE, ADDR_TEXT_READ = 64, 112
ADDR_VALUE_READ = 160
ADDR_PING, ADDR_RELOAD, ADDR_CLEAR_INK = 200, 201, 202
ADDR_NOW_PLAYING, ADDR_NOW_POS, ADDR_NOW_CLEAR = 203, 205, 206
ADDR_VALUE_WRITE, ADDR_OPEN_APP = 207, 247
ADDR_WX_CURRENT, ADDR_WX_FORECAST, ADDR_WX_NAME, ADDR_JAZZ, ADDR_WX_TICKER = 248, 249, 250, 251, 252   # ticker: 252-254
PROTOCOL_VERSION = 3          # 3: Talon Pilot 2.11+ (no Note Pad): PC Link ports at 0-19
# PC Link (protocol 3). Values are raw 0-255 (255 = not available), stored by the PDA as Len/255.
ADDR_PC_VALUE, ADDR_PC_MESSAGE, ADDR_PC_ALERT, ADDR_PC_CLEAR, ADDR_SKY_LAT, ADDR_SKY_LON = 0, 14, 16, 17, 18, 19
PC_CPU, PC_GPU, PC_CPU_TEMP, PC_GPU_TEMP, PC_RAM, PC_HMD, PC_LEFT, PC_RIGHT, PC_HEART, PC_TIMER_MIN, PC_TIMER_FRAC, PC_TIMER_STATE, PC_UNREAD = range(13)
PC_VALUES = 14
PC_NA = 255
PC_CMD = P + "PC/Cmd"         # PDA -> PC: 1 play/pause, 2 next, 3 previous, 4 focus timer, 5 timer reset, 6 clear messages,
                              # 40-44 terminal: send line, scroll back, scroll forward, break, repeat (Talon Pilot 2.18)
CMD_PLAY, CMD_NEXT, CMD_PREV, CMD_TIMER, CMD_TIMER_RESET, CMD_CLEAR = 1, 2, 3, 4, 5, 6
HEART_PARAMS = ("HR", "HeartRateInt", "HeartRate", "Heartrate")

# sync states and stages
STATE_IDLE, STATE_WANT, STATE_XFER, STATE_DONE, STATE_FAIL = 0, 1, 2, 3, 4
STAGE_CONNECT, STAGE_SETTINGS, STAGE_TASKS, STAGE_MEMOS, STAGE_CALENDAR, STAGE_CONTACTS, STAGE_NOTEPAD, STAGE_READ, STAGE_BACKUP = range(9)
STAGE_NAMES = ["Connecting", "Settings", "Tasks", "Memos", "Calendar", "Contacts", "Note Pad", "Reading your PDA", "Backing up"]

# text slot map (15-character lines)
SLOT_TASKS, N_TASKS = 0, 8
SLOT_MEMOS, N_MEMOS, MEMO_LINES = 8, 5, 3
SLOT_HYPNO = 23
SLOT_CALENDAR, N_EVENTS = 24, 6
SLOT_CONTACTS, N_CONTACTS = 36, 6
RECORD_LINES = 2
SLOTS_BASIC, SLOTS_ALL = 24, 48

# apps (for remote launch)
APPS = {0: "Launcher", 1: "Calendar", 2: "Contacts", 3: "Tasks", 4: "Memos", 5: "Calc", 6: "Clock", 7: "Prefs",
        8: "TalonSync", 10: "Expense", 11: "Card Info", 12: "Security",
        20: "Talon 3D", 23: "Hypno", 24: "Compass", 25: "Scope", 26: "Hoot Pet", 27: "TalonCast",
        28: "Owl Oracle", 29: "Moon & Stars", 30: "PC Link", 31: "Beam", 21: "TalonPop", 22: "Snow Globe", 19: "Aquarium", 18: "Terminal"}


@dataclass
class Value:
    key: str
    param: str
    kind: str              # "int", "float", "bool"
    label: str
    lo: float = 0
    hi: float = 1
    labels: List[str] = None
    group: str = "prefs"


def _pref(key, param, kind, label, lo, hi, labels=None):
    return Value(key, param, kind, label, lo, hi, labels, "prefs")


# Value read/write table: index k <-> addresses ADDR_VALUE_READ + k / ADDR_VALUE_WRITE + k.
# Order = TalonPilotAnimator.BusValues(): 20 prefs, 6 app settings, 8 task flags, power, 5 pet stats.
PREFS = [
    _pref("Hour", "TP/Hour", "int", "Clock hour", 0, 23),
    _pref("Minute", "TP/Min", "int", "Clock minute", 0, 59),
    _pref("Clock24", "TP/S/Clock24", "int", "Time format", 0, 1, ["12-hour", "24-hour"]),
    _pref("Bright", "TP/Bright", "float", "Brightness", 0.1, 1.0),
    _pref("Theme", "TP/Theme", "int", "Theme", 0, 7, ["Classic LCD", "Mint Owl", "Owl Night", "Feather Gray", "Gryphon Gold", "Custom 1", "Custom 2", "Custom 3"]),
    _pref("Wall", "TP/S/Wall", "int", "Wallpaper", 0, 2, ["Plain", "Aurora", "Morning mist"]),
    _pref("FX", "TP/S/FX", "int", "Screen effect", 0, 2, ["None", "LCD grid", "Scanlines"]),
    _pref("Sound", "TP/Sound", "float", "System sound", 0, 1, ["Off", "On"]),
    _pref("Vol", "TP/S/Vol", "int", "Volume", 0, 2, ["Low", "Medium", "High"]),
    _pref("TapBeep", "TP/S/TapBeep", "int", "Tap beep", 0, 1, ["Off", "On"]),
    _pref("GameSnd", "TP/S/GameSnd", "int", "Game sound", 0, 1, ["Off", "On"]),
    _pref("Btn1", "TP/S/Btn1", "int", "Button 1 app", 1, 13),
    _pref("Btn2", "TP/S/Btn2", "int", "Button 2 app", 1, 13),
    _pref("Btn3", "TP/S/Btn3", "int", "Button 3 app", 1, 13),
    _pref("Btn4", "TP/S/Btn4", "int", "Button 4 app", 1, 13),
    _pref("Saver", "TP/S/Saver", "int", "Screensaver", 0, 3, ["Off", "Mystify", "3D Pipes", "Hypnospiral"]),
    _pref("SaverTime", "TP/S/SaverT", "int", "Screensaver after", 0, 3, ["1 min", "2 min", "5 min", "10 min"]),
    _pref("AutoOff", "TP/S/AutoOff", "int", "Auto-off", 0, 3, ["Never", "5 min", "15 min", "30 min"]),
    _pref("BootLock", "TP/S/BootLock", "int", "Lock at power on", 0, 1, ["Off", "On"]),
    _pref("ClockSrc", "TP/S/ClockSrc", "int", "Set time", 0, 1, ["Automatic", "Manual"]),
]
APP_SETTINGS = [
    Value("model3D", "TP/3D/Model", "int", "Talon 3D model", 0, 8, group="apps"),
    Value("look3D", "TP/3D/Look", "int", "Talon 3D look", 0, 2, ["Solid", "Hologram", "CAD"], group="apps"),
    Value("spin3D", "TP/3D/Spin", "int", "Talon 3D spin", 0, 1, ["Off", "On"], group="apps"),
    Value("hypSpeed", "TP/Hyp/Speed", "int", "Hypno speed", 1, 5, group="apps"),
    Value("hypStyle", "TP/Hyp/Style", "int", "Hypno style", 0, 2, ["Rainbow spiral", "Black & white spiral", "Rainbow rings"], group="apps"),
    Value("scopeMode", "TP/Scope/Mode", "int", "Scope mode", 0, 8, ["Spectrum", "Waveform", "Voice", "LED bars", "Mirror bars", "Sunburst", "Plasma", "Warp tunnel", "Band history"], group="apps"),
]
TASK_FLAGS = [Value(f"T{i}", f"TP/T{i}", "float", f"Task {i + 1} done", group="tasks") for i in range(8)]
POWER_VALUE = Value("On", POWER, "bool", "Power", group="device")
PET = [
    Value("petFood", "TP/Pet/Food", "float", "Food", group="pet"),
    Value("petJoy", "TP/Pet/Joy", "float", "Joy", group="pet"),
    Value("petEnergy", "TP/Pet/Energy", "float", "Energy", group="pet"),
    Value("petAge", "TP/Pet/Age", "float", "Age", group="pet"),
    Value("petSleep", "TP/Pet/Sleep", "float", "Asleep", group="pet"),
]
VALUES: List[Value] = PREFS + APP_SETTINGS + TASK_FLAGS + [POWER_VALUE] + PET
VALUE_INDEX = {v.key: i for i, v in enumerate(VALUES)}
assert len(VALUES) == 40

# Every OSC-facing parameter: (name, kind). Used by the doctor and the OSCQuery namespace.
def link_params(ink_bits: int = 12):
    out = [(BUS_ADDR, "int"), (BUS_CLK, "bool"), (BUS_ACK, "int"), (BUS_LEN, "int"), (BUS_V, "float"), (BUS_N, "int")]
    out += [(BUS_B(i), "bool") for i in range(ink_bits)]
    out += [(BUS_C(i), "int") for i in range(BUS_CHARS)]
    out += [(SYNC_REQ, "bool"), (SYNC_STATE, "int"), (SYNC_STAGE, "float"), (SYNC_PROG, "float"), (PC_CMD, "int")]
    return out


# ---------------------------------------------------------------- text encoding (same as TalonSync.cs)
def clean(text: str, max_len: int = BUS_CHARS) -> str:
    text = (text or "").translate(_ASCII_FOLD)
    out = "".join(ch for ch in text if 32 <= ord(ch) < 127)
    return out[:max_len]


def encode_line(text: str) -> List[int]:
    """15 ASCII codes, right-aligned (the PDA keyboard shifts characters in from the right)."""
    t = clean(text)
    codes = [0] * BUS_CHARS
    start = BUS_CHARS - len(t)
    for i, ch in enumerate(t):
        codes[start + i] = ord(ch)
    return codes


def decode_line(codes) -> str:
    return "".join(chr(c) for c in codes if 32 <= c < 127)


# fold common typographic characters and accents to ASCII so song titles survive
_FOLD = {
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
    " ": " ", "×": "x", "•": "*", "·": "*",
}
try:
    import unicodedata

    def _fold_char(c):
        if c in _FOLD:
            return _FOLD[c]
        d = unicodedata.normalize("NFKD", c)
        d = "".join(x for x in d if not unicodedata.combining(x))
        return d if all(32 <= ord(x) < 127 for x in d) else ""
except ImportError:  # pragma: no cover
    def _fold_char(c):
        return _FOLD.get(c, "")


class _Folder(dict):
    def __missing__(self, code):
        c = chr(code)
        r = c if 32 <= code < 127 else _fold_char(c)
        self[code] = r
        return r


_ASCII_FOLD = _Folder()


def to_ascii(text: str) -> str:
    return (text or "").translate(_ASCII_FOLD)
