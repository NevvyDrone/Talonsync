"""The desktop database: rich records on the PC, projected onto the PDA's 15-character lines."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import protocol as pr


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@dataclass
class Contact:
    id: str = field(default_factory=new_id)
    first: str = ""
    last: str = ""
    company: str = ""
    job: str = ""
    mobile: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    birthday: str = ""          # YYYY-MM-DD
    notes: str = ""
    category: str = "Unfiled"
    favorite: bool = False
    on_pda: bool = True         # allowed on the handheld
    modified: str = field(default_factory=now_iso)

    @property
    def name(self) -> str:
        return " ".join(x for x in (self.first, self.last) if x).strip() or self.company

    def pda_lines(self) -> List[str]:
        second = self.mobile or self.phone or self.email or self.company
        return [pr.clean(self.name), pr.clean(second)]

    def sort_key(self):
        return (not self.favorite, (self.last or self.first or self.company).lower(), self.first.lower())


@dataclass
class Event:
    id: str = field(default_factory=new_id)
    title: str = ""
    start: str = ""             # local ISO datetime, or YYYY-MM-DD for all-day
    end: str = ""
    all_day: bool = False
    location: str = ""
    notes: str = ""
    category: str = "Unfiled"
    alarm_min: int = -1
    on_pda: bool = True
    modified: str = field(default_factory=now_iso)

    def start_dt(self) -> Optional[datetime]:
        return parse_dt(self.start)

    def end_dt(self) -> Optional[datetime]:
        e = parse_dt(self.end)
        if e:
            return e
        s = self.start_dt()
        if not s:
            return None
        return s + (timedelta(days=1) if self.all_day else timedelta(hours=1))

    def when_line(self, today: Optional[date] = None) -> str:
        s = self.start_dt()
        if not s:
            return pr.clean(self.location)
        today = today or date.today()
        days = (s.date() - today).days
        day = s.strftime("%a") if 0 <= days < 7 else f"{s.month:02d}/{s.day:02d}"
        when = day if self.all_day else f"{day} {s.hour:02d}:{s.minute:02d}"
        return pr.clean(f"{when} {self.location}".strip())

    def pda_lines(self, today: Optional[date] = None) -> List[str]:
        return [pr.clean(self.title), self.when_line(today)]


@dataclass
class Task:
    id: str = field(default_factory=new_id)
    title: str = ""
    done: bool = False
    due: str = ""               # YYYY-MM-DD
    priority: int = 3           # 1 (highest) .. 5
    notes: str = ""
    category: str = "Unfiled"
    on_pda: bool = True
    modified: str = field(default_factory=now_iso)

    def pda_lines(self) -> List[str]:
        return [pr.clean(self.title)]

    def sort_key(self):
        return (self.done, self.priority, self.due or "9999", self.title.lower())


@dataclass
class Memo:
    id: str = field(default_factory=new_id)
    title: str = ""
    body: str = ""
    category: str = "Unfiled"
    pinned: bool = False
    on_pda: bool = True
    modified: str = field(default_factory=now_iso)

    def pda_lines(self) -> List[str]:
        body = wrap(self.body, pr.BUS_CHARS)
        return [pr.clean(self.title), body[0] if body else "", body[1] if len(body) > 1 else ""]


def wrap(text: str, width: int) -> List[str]:
    """Word-wrap into ASCII lines of at most `width` characters."""
    out: List[str] = []
    for para in pr.to_ascii(text or "").replace("\r", "").split("\n"):
        line = ""
        for word in para.split(" "):
            while len(word) > width:
                if line:
                    out.append(line); line = ""
                out.append(word[:width]); word = word[width:]
            if not line:
                line = word
            elif len(line) + 1 + len(word) <= width:
                line += " " + word
            else:
                out.append(line); line = word
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return [pr.clean(x) for x in out]


def parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


@dataclass
class NotePad:
    rows: int = 32
    cols: int = 24
    bits: List[int] = field(default_factory=lambda: [0] * (32 * 24))   # fine resolution, row-major
    modified: str = field(default_factory=now_iso)

    def get(self, r, c) -> bool:
        return bool(self.bits[r * self.cols + c])

    def at_scale(self, scale: int) -> List[List[bool]]:
        """Rows of bits at the PDA's resolution (scale 2: a block is on if any fine pixel is)."""
        R, C = self.rows // scale, self.cols // scale
        return [[any(self.get(r * scale + dr, c * scale + dc) for dr in range(scale) for dc in range(scale))
                 for c in range(C)] for r in range(R)]

    def set_from_scale(self, rows: List[List[bool]], scale: int):
        bits = [0] * (self.rows * self.cols)
        for r, row in enumerate(rows):
            for c, on in enumerate(row):
                if on:
                    for dr in range(scale):
                        for dc in range(scale):
                            bits[(r * scale + dr) * self.cols + c * scale + dc] = 1
        self.bits = bits
        self.modified = now_iso()

    def empty(self) -> bool:
        return not any(self.bits)


@dataclass
class Device:
    owner: str = ""                     # asked on first run: what TalonSync and the PDA call you
    sync_id: str = ""
    hypno_caption: str = ""             # empty = the PDA's built-in "Just relax..."
    prefs: Dict[str, float] = field(default_factory=lambda: {
        "Hour": 12, "Minute": 0, "Clock24": 0, "Bright": 0.75, "Theme": 1, "Wall": 1, "FX": 0, "Sound": 1, "Vol": 1,
        "TapBeep": 1, "GameSnd": 1, "Btn1": 1, "Btn2": 2, "Btn3": 3, "Btn4": 4, "Saver": 1, "SaverTime": 1,
        "AutoOff": 0, "BootLock": 0, "ClockSrc": 0,
        "model3D": 2, "look3D": 2, "spin3D": 1, "hypSpeed": 2, "hypStyle": 0, "scopeMode": 0})
    pet: Dict[str, float] = field(default_factory=dict)       # last values read from the PDA
    pet_read: str = ""
    pda_info: Dict[str, int] = field(default_factory=dict)


@dataclass
class SyncBase:
    """What the PDA looked like after the last successful TalonSync (for three-way merges)."""
    lines: Dict[str, str] = field(default_factory=dict)       # slot -> text
    owners: Dict[str, str] = field(default_factory=dict)      # slot -> record id
    flags: Dict[str, bool] = field(default_factory=dict)      # task done flags by slot
    prefs: Dict[str, float] = field(default_factory=dict)
    ink: List[int] = field(default_factory=list)
    last_sync: str = ""
    count: int = 0


KINDS = {"contacts": Contact, "events": Event, "tasks": Task, "memos": Memo}


class Database:
    """All desktop data, saved as JSON. Thread-safe enough: one lock around edits and saves."""

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        self.contacts: List[Contact] = []
        self.events: List[Event] = []
        self.tasks: List[Task] = []
        self.memos: List[Memo] = []
        self.notepad = NotePad()
        self.device = Device()
        self.base = SyncBase()
        self.revision = 0
        self.load()

    # ------------------------------------------------------------ records
    def kind(self, name: str) -> List:
        return getattr(self, name)

    def find(self, kind: str, rid: str):
        return next((r for r in self.kind(kind) if r.id == rid), None)

    def upsert(self, kind: str, data: dict):
        cls = KINDS[kind]
        names = {f.name for f in fields(cls)}
        with self.lock:
            rec = self.find(kind, data.get("id", "")) if data.get("id") else None
            if rec is None:
                rec = cls()
                self.kind(kind).append(rec)
            for k, v in data.items():
                if k in names and k != "id":
                    cur = getattr(rec, k)
                    if isinstance(cur, bool):
                        v = bool(v)
                    elif isinstance(cur, int) and not isinstance(cur, bool):
                        v = int(v or 0)
                    elif isinstance(cur, str):
                        v = "" if v is None else str(v)
                    setattr(rec, k, v)
            rec.modified = now_iso()
            self.touch()
            return rec

    def delete(self, kind: str, rid: str) -> bool:
        with self.lock:
            lst = self.kind(kind)
            n = len(lst)
            lst[:] = [r for r in lst if r.id != rid]
            if len(lst) != n:
                self.touch()
                return True
            return False

    def touch(self):
        self.revision += 1

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        with self.lock:
            return {
                "format": "talonsync-db", "version": 1,
                "contacts": [asdict(x) for x in self.contacts], "events": [asdict(x) for x in self.events],
                "tasks": [asdict(x) for x in self.tasks], "memos": [asdict(x) for x in self.memos],
                "notepad": asdict(self.notepad), "device": asdict(self.device), "base": asdict(self.base),
            }

    def from_dict(self, d: dict):
        def load(cls, items):
            names = {f.name for f in fields(cls)}
            return [cls(**{k: v for k, v in it.items() if k in names}) for it in items or []]
        with self.lock:
            self.contacts = load(Contact, d.get("contacts"))
            self.events = load(Event, d.get("events"))
            self.tasks = load(Task, d.get("tasks"))
            self.memos = load(Memo, d.get("memos"))
            np_ = d.get("notepad") or {}
            self.notepad = NotePad(**{k: v for k, v in np_.items() if k in {f.name for f in fields(NotePad)}})
            if len(self.notepad.bits) != self.notepad.rows * self.notepad.cols:
                self.notepad = NotePad()
            dv = d.get("device") or {}
            dev = Device()
            for k, v in dv.items():
                if hasattr(dev, k):
                    if k == "prefs":
                        dev.prefs.update(v)
                    else:
                        setattr(dev, k, v)
            self.device = dev
            b = d.get("base") or {}
            self.base = SyncBase(**{k: v for k, v in b.items() if k in {f.name for f in fields(SyncBase)}})
            self.touch()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.from_dict(json.load(f))
                return
            except Exception as e:  # keep the broken file, start clean
                broken = self.path + f".broken-{int(time.time())}"
                try:
                    os.replace(self.path, broken)
                except OSError:
                    pass
                print(f"TalonSync: database unreadable ({e}); moved to {broken}")
        self.seed()

    def save(self):
        with self.lock:
            data = json.dumps(self.to_dict(), indent=1)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, self.path)

    def snapshot(self) -> dict:
        return copy.deepcopy(self.to_dict())

    def seed(self):
        """First run: a few friendly records so every screen has something in it."""
        today = date.today()
        def at(days, h, m=0):
            return datetime.combine(today + timedelta(days=days), datetime.min.time()).replace(hour=h, minute=m).isoformat()
        self.contacts = [
            Contact(first="Archie", last="Barnowl", company="Aerie Worlds", job="World Builder", mobile="555-0142", email="archie@aerie.net", notes="Udon wizard. Owes you a mouse.", favorite=True),
            Contact(first="Gryff", last="Talonsson", job="Avatar Artist", mobile="555-0177", email="gryff@talon.net", notes="Great at feather shaders."),
            Contact(first="Wren", last="Snowy", company="Owl Post", mobile="555-0119", email="wren@owl.post"),
        ]
        self.events = [
            Event(title="Gryphon meetup", start=at(1, 20), end=at(1, 23), location="Aerie Lounge", notes="Show off the Talon Pilot!"),
            Event(title="World launch party", start=at(3, 21), end=at(3, 23, 30), location="New world"),
        ]
        self.tasks = [Task(title="Install TalonSync", done=True, priority=1), Task(title="Run a TalonSync", priority=1),
                      Task(title="Stretch your wings", priority=2)]
        self.memos = [Memo(title="Welcome", body="TalonSync keeps your PDA and PC in step. Press TalonSync!", pinned=True)]
        self.touch()

    # ------------------------------------------------------------ PDA projection
    def pda_choice(self, kind: str, count: int, today: Optional[date] = None) -> List[Optional[str]]:
        """Which record goes in which PDA record position. Keeps records where they were last time."""
        today = today or date.today()
        recs = [r for r in self.kind(kind) if r.on_pda]
        if kind == "events":
            recs = [e for e in recs if (e.end_dt() or datetime.max) >= datetime.combine(today, datetime.min.time())]
            recs.sort(key=lambda e: e.start_dt() or datetime.max)
        elif kind == "contacts":
            recs.sort(key=lambda c: c.sort_key())
        elif kind == "tasks":
            recs.sort(key=lambda t: t.sort_key())
        elif kind == "memos":
            recs.sort(key=lambda m: (m.pinned, m.modified), reverse=True)
        allowed = {r.id for r in recs}
        first, per = SLOT_LAYOUT[kind]
        slots: List[Optional[str]] = [None] * count
        # records stay where they were last synced (a sync never shuffles your PDA), as long as
        # they still exist, are allowed on the PDA and (events) haven't ended
        for i in range(count):
            owner = self.base.owners.get(str(first + i * per))
            if owner in allowed and owner not in slots:
                slots[i] = owner
        rest = [r.id for r in recs if r.id not in slots]
        for i in range(count):
            if slots[i] is None and rest:
                slots[i] = rest.pop(0)
        return slots


# kind -> (first slot, lines per record)
SLOT_LAYOUT = {"tasks": (pr.SLOT_TASKS, 1), "memos": (pr.SLOT_MEMOS, pr.MEMO_LINES),
               "events": (pr.SLOT_CALENDAR, pr.RECORD_LINES), "contacts": (pr.SLOT_CONTACTS, pr.RECORD_LINES)}
SLOT_COUNTS = {"tasks": pr.N_TASKS, "memos": pr.N_MEMOS, "events": pr.N_EVENTS, "contacts": pr.N_CONTACTS}
