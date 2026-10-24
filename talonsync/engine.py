"""The TalonSync engine: talks to the PDA over the bus, merges with the desktop database.

A sync, step by step:
  1. handshake   TP/Sync/State = 2 -> the PDA jumps to its TalonSync screen and spins the arrows
  2. connect     ping + probe what this PDA has (text slots, Note Pad size)
  3. read        every line, flag, setting and the Note Pad ("Reading your PDA")
  4. conduits    settings, tasks, memos, calendar, contacts, Note Pad - each merged three ways
                 (PDA now / PC now / both at the last TalonSync) and written back where needed
  5. backup      the database is saved and a dated backup written ("Backing up")
  6. done        State = 3 (the PDA chirps "TalonSync complete!"), then 0
"""
from __future__ import annotations

import re
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from . import protocol as pr
from .bus import BusError, Nak, NoPda, PdaBus, PdaInfo
from .model import (SLOT_COUNTS, SLOT_LAYOUT, Contact, Database, Event, Memo, Task, now_iso, wrap)

CONDUIT_OF_KIND = {"tasks": "tasks", "memos": "memos", "events": "calendar", "contacts": "contacts"}
STAGE_OF_KIND = {"tasks": pr.STAGE_TASKS, "memos": pr.STAGE_MEMOS, "events": pr.STAGE_CALENDAR, "contacts": pr.STAGE_CONTACTS}
CLASS_OF_KIND = {"tasks": Task, "memos": Memo, "events": Event, "contacts": Contact}


class Cancelled(Exception):
    pass


@dataclass
class SyncStatus:
    running: bool = False
    stage: int = 0
    stage_name: str = ""
    progress: float = 0.0
    message: str = ""
    started: float = 0.0
    result: str = ""          # "", "ok", "failed", "cancelled"
    initiated_by: str = ""


@dataclass
class SyncReport:
    ok: bool = False
    started: str = ""
    seconds: float = 0.0
    initiated_by: str = "pc"
    pda: Dict[str, int] = field(default_factory=dict)
    lines: List[str] = field(default_factory=list)       # the TalonSync Log
    counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    error: str = ""
    transfers: int = 0


class SyncEngine:
    def __init__(self, db: Database, settings, bus: PdaBus, log: Callable[[str], None] = None,
                 on_backup: Callable[[], Optional[str]] = None, on_after: Callable[[SyncReport], None] = None):
        self.db = db
        self.s = settings
        self.bus = bus
        self.log = log or (lambda m: None)
        self.on_backup = on_backup
        self.on_after = on_after
        self.status = SyncStatus()
        self.reports: List[SyncReport] = []
        self.lock = threading.Lock()
        self._cancel = False
        self._report: Optional[SyncReport] = None

    # ------------------------------------------------------------ control
    @property
    def busy(self) -> bool:
        return self.status.running

    def cancel(self):
        self._cancel = True

    def start(self, initiated_by: str = "pc") -> bool:
        if not self.lock.acquire(blocking=False):
            return False
        self._cancel = False
        self.status = SyncStatus(running=True, started=time.time(), initiated_by=initiated_by, stage_name="Connecting",
                                 message="Connecting with the handheld...")
        threading.Thread(target=self._run_thread, args=(initiated_by,), name="talonsync", daemon=True).start()
        return True

    def run_blocking(self, initiated_by: str = "pc") -> SyncReport:
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("a TalonSync is already running")
        self._cancel = False
        self.status = SyncStatus(running=True, started=time.time(), initiated_by=initiated_by)
        return self._run_thread(initiated_by)

    def _run_thread(self, initiated_by: str) -> SyncReport:
        rep = SyncReport(started=now_iso(), initiated_by=initiated_by)
        self._report = rep
        t0 = time.time()
        try:
            self._run(rep)
            rep.ok = True
            self.status.result = "ok"
            name = (self.db.device.owner or "").strip()
            self._note(f"TalonSync complete. Nice work, {name}!" if name else "TalonSync complete!")
        except Cancelled:
            rep.error = "Cancelled"
            self.status.result = "cancelled"
            self._note("TalonSync cancelled.")
            self._finish_pda(False)
        except NoPda as e:
            rep.error = ("The PDA didn't answer. Is VRChat running with OSC enabled, the Talon Pilot avatar loaded "
                         "(2.3+ with PC link on) and nothing else using the OSC port?")
            self.status.result = "failed"
            self._note("Couldn't reach the PDA: " + str(e))
            self._finish_pda(False)
        except Exception as e:
            rep.error = f"{type(e).__name__}: {e}"
            self.status.result = "failed"
            self._note("TalonSync failed: " + rep.error)
            self.log(traceback.format_exc())
            self._finish_pda(False)
        finally:
            rep.seconds = round(time.time() - t0, 1)
            rep.transfers = self.bus.transfers
            self.reports.insert(0, rep)
            del self.reports[50:]
            self.status.running = False
            self.status.progress = 1.0 if rep.ok else self.status.progress
            self.lock.release()
            if self.on_after:
                try:
                    self.on_after(rep)
                except Exception as e:
                    self.log(f"after-sync hook failed: {e}")
        return rep

    # ------------------------------------------------------------ helpers
    def _note(self, msg: str):
        self.status.message = msg
        if self._report is not None:
            self._report.lines.append(f"{datetime.now():%H:%M:%S}  {msg}")
        self.log(msg)

    def _stage(self, stage: int, progress: float, msg: str = None):
        if self._cancel:
            raise Cancelled()
        self.status.stage = stage
        self.status.stage_name = pr.STAGE_NAMES[stage]
        self.status.progress = progress
        if msg:
            self._note(msg)
        try:
            self.bus.set_stage(stage, progress)
        except Exception:
            pass

    def _count(self, conduit: str, what: str, n: int = 1):
        c = self._report.counts.setdefault(conduit, {})
        c[what] = c.get(what, 0) + n

    def _finish_pda(self, ok: bool):
        try:
            self.bus.set_state(pr.STATE_DONE if ok else pr.STATE_FAIL)
            time.sleep(float(self.s.get("done_hold_seconds", 2.5)))
            self.bus.set_state(pr.STATE_IDLE)
            self.bus.link.set(pr.SYNC_REQ, False)
        except Exception:
            pass

    def action(self, conduit: str) -> str:
        return (self.s.get("conduits") or {}).get(conduit, "sync")

    # ------------------------------------------------------------ the TalonSync
    def _run(self, rep: SyncReport):
        db, bus = self.db, self.bus
        bus.transfers = 0
        self._note("Connecting with the handheld...")
        bus.set_state(pr.STATE_XFER)
        self._stage(pr.STAGE_CONNECT, 0.0)
        bus.release()
        bus.set_state(pr.STATE_XFER)
        # the PDA may still be booting: keep pinging for a while
        deadline = time.time() + float(self.s.get("connect_timeout", 10))
        while True:
            if self._cancel:
                raise Cancelled()
            try:
                info = bus.probe()
                break
            except NoPda:
                if time.time() > deadline:
                    raise
        rep.pda = {"version": info.version, "slots": info.slots, "ink_rows": info.ink_rows, "ink_cols": info.ink_cols}
        db.device.pda_info = dict(rep.pda)
        if info.version < pr.PROTOCOL_VERSION:
            self._note("This PDA has an older link (update Talon Pilot to 2.5 for exact settings and Now Playing).")
        self._note(f"Connected: {info.slots} text lines, "
                   + (f"Note Pad {info.ink_cols} x {info.ink_rows}" if info.ink_rows else "no Note Pad"))

        # ---------------- read everything
        reads_total = info.slots + 8 + 26 + 5 + info.ink_rows
        done = [0]

        def tick():
            done[0] += 1
            self._stage(pr.STAGE_READ, 0.45 * done[0] / reads_total)

        self._stage(pr.STAGE_READ, 0.0, "Reading your PDA...")
        pda_lines: Dict[int, str] = {}
        for s in range(info.slots):
            pda_lines[s] = bus.read_text(s); tick()
        flags = []
        for i in range(8):
            v = bus.read_value(pr.VALUE_INDEX[f"T{i}"]); tick()
            flags.append(bool(v and v > 0.5))
        pda_prefs: Dict[str, float] = {}
        for v in pr.PREFS + pr.APP_SETTINGS:
            x = bus.read_value(pr.VALUE_INDEX[v.key]); tick()
            if x is not None:
                pda_prefs[v.key] = float(x)
        pet = {}
        for v in pr.PET:
            try:
                x = bus.read_value(pr.VALUE_INDEX[v.key])
            except Nak:                                  # Hoot-agotchi left out in the Install Wizard (2.14)
                x = None
            tick()
            if x is not None:
                pet[v.key] = round(float(x), 3)
        if pet:
            db.device.pet = pet
            db.device.pet_read = now_iso()
        pda_ink: Optional[List[List[bool]]] = None
        if info.ink_rows:
            pda_ink = []
            for r in range(info.ink_rows):
                pda_ink.append(bus.read_ink_row(r, info.ink_cols)); tick()

        # ---------------- conduits
        written = [0]
        self._reset_queue()
        with db.lock:
            self._settings_conduit(pda_prefs)
            self._hypno_conduit(pda_lines, info)
            for kind in ("tasks", "memos", "events", "contacts"):
                first, per = SLOT_LAYOUT[kind]
                if first + SLOT_COUNTS[kind] * per > info.slots:
                    continue                      # this PDA doesn't store these records
                self._records_conduit(kind, pda_lines, flags if kind == "tasks" else None)
            if pda_ink is not None:
                self._ink_conduit(pda_ink, info)
            db.base.last_sync = now_iso()
            db.base.count += 1
            db.touch()
        # the writes collected above go out now, stage by stage
        for stage, ops in self._writes:
            for op in ops:
                self._stage(stage, 0.45 + 0.45 * written[0] / max(1, self._n_writes))
                op()
                written[0] += 1
        if self._prefs_written:
            bus.reload()

        # ---------------- backup
        self._stage(pr.STAGE_BACKUP, 0.93, "Backing up...")
        db.save()
        if self.on_backup and self.s.get("backup_on_sync", True):
            where = self.on_backup()
            if where:
                self._note(f"Backup saved: {where}")
        self._stage(pr.STAGE_BACKUP, 1.0)
        summary = ", ".join(f"{k}: " + " ".join(f"{n} {w}" for w, n in v.items()) for k, v in rep.counts.items()) or "everything already matched"
        self._note(f"Summary - {summary}")
        bus.set_state(pr.STATE_DONE)
        time.sleep(float(self.s.get("done_hold_seconds", 2.5)))
        bus.set_state(pr.STATE_IDLE)
        bus.link.set(pr.SYNC_REQ, False)

    # ------------------------------------------------------------ write queue
    _writes: List = []
    _n_writes = 0
    _prefs_written = False

    def _queue(self, stage: int, op: Callable[[], None]):
        if not self._writes or self._writes[-1][0] != stage:
            self._writes.append((stage, []))
        self._writes[-1][1].append(op)
        self._n_writes += 1

    def _reset_queue(self):
        self._writes = []
        self._n_writes = 0
        self._prefs_written = False

    # ------------------------------------------------------------ settings
    def _settings_conduit(self, pda_prefs: Dict[str, float]):
        act = self.action("settings")
        if act == "nothing" or not pda_prefs:
            return
        dev, base = self.db.device, self.db.base
        for v in pr.PREFS + pr.APP_SETTINGS:
            if v.key not in pda_prefs:
                continue
            pda = pda_prefs[v.key]
            pc = float(dev.prefs.get(v.key, pda))
            b = base.prefs.get(v.key)
            same = lambda a, c: c is not None and abs(a - c) < (0.01 if v.kind == "float" else 0.5)
            if same(pda, pc):
                base.prefs[v.key] = pda
                continue
            pda_changed = not same(pda, b) if b is not None else True
            pc_changed = not same(pc, b) if b is not None else False
            take_pda = act == "pda_overwrites" or (act == "sync" and pda_changed and (not pc_changed or self.s.get("conflict") == "pda"))
            if take_pda:
                dev.prefs[v.key] = pda
                base.prefs[v.key] = pda
                self._count("settings", "from PDA")
            else:
                k = pr.VALUE_INDEX[v.key]
                val = pc
                self._queue(pr.STAGE_SETTINGS, lambda k=k, val=val: self.bus.write_value(k, val))
                self._prefs_written = True
                base.prefs[v.key] = pc
                self._count("settings", "to PDA")

    def _hypno_conduit(self, pda_lines: Dict[int, str], info: PdaInfo):
        act = self.action("hypno")
        if act == "nothing" or pr.SLOT_HYPNO >= info.slots:
            return
        dev, base = self.db.device, self.db.base
        key = str(pr.SLOT_HYPNO)
        pda, pc, b = pda_lines.get(pr.SLOT_HYPNO, ""), pr.clean(dev.hypno_caption), base.lines.get(key)
        if pda == pc:
            base.lines[key] = pda
            return
        pda_changed = pda != b if b is not None else bool(pda)
        pc_changed = pc != b if b is not None else True
        if act == "pda_overwrites" or (act == "sync" and pda_changed and (not pc_changed or self.s.get("conflict") == "pda")):
            dev.hypno_caption = pda
            base.lines[key] = pda
            self._count("hypno", "from PDA")
        elif act in ("sync", "pc_overwrites"):
            self._queue(pr.STAGE_SETTINGS, lambda: self.bus.write_text(pr.SLOT_HYPNO, pc))
            base.lines[key] = pc
            self._count("hypno", "to PDA")

    # ------------------------------------------------------------ records (tasks, memos, calendar, contacts)
    def _records_conduit(self, kind: str, pda_lines: Dict[int, str], flags: Optional[List[bool]]):
        conduit = CONDUIT_OF_KIND[kind]
        act = self.action(conduit)
        if act == "nothing":
            return
        db, base = self.db, self.db.base
        first, per = SLOT_LAYOUT[kind]
        count = SLOT_COUNTS[kind]
        today = date.today()
        conflict = self.s.get("conflict", "pc")

        def lines_of(rec) -> List[str]:
            if rec is None:
                return [""] * per
            return rec.pda_lines(today) if kind == "events" else rec.pda_lines()

        def slot(i, j=0) -> int:
            return first + i * per + j

        # ---- 1. pull: what changed on the PDA since the last TalonSync
        if act in ("sync", "pda_overwrites"):
            for i in range(count):
                pda = [pda_lines.get(slot(i, j), "") for j in range(per)]
                has_base = str(slot(i)) in base.lines
                b = [base.lines.get(str(slot(i, j)), "") for j in range(per)]
                owner = db.find(kind, base.owners.get(str(slot(i)), "")) if has_base else None
                pda_flag = flags[i] if flags is not None else None
                b_flag = base.flags.get(str(slot(i)))
                if has_base:
                    changed = pda != b
                    flag_changed = flags is not None and b_flag is not None and pda_flag != b_flag
                else:
                    # first TalonSync: PDA content the PC hasn't seen becomes new records
                    changed = any(pda) and pda != lines_of(db.find(kind, (db.pda_choice(kind, count)[i] or "")))
                    flag_changed = False
                if not changed and not flag_changed:
                    continue
                pc_changed = owner is not None and has_base and (lines_of(owner) != b or (flags is not None and b_flag is not None and owner.done != b_flag))
                if owner is not None and pc_changed and act == "sync" and conflict == "pc":
                    self._note(f"{conduit}: '{pda[0] or b[0]}' changed on both - kept the PC version")
                    self._count(conduit, "conflicts")
                    continue
                if not any(pda):
                    if owner is not None:
                        if self.s.get("pda_blank_removes"):
                            db.delete(kind, owner.id)
                            self._count(conduit, "deleted")
                        else:
                            owner.on_pda = False
                            self._count(conduit, "removed from PDA")
                    continue
                if owner is not None and pc_changed and conflict == "duplicate" and act == "sync":
                    rec = CLASS_OF_KIND[kind]()
                    apply_lines(kind, rec, [""] * per, pda, today, pda_flag)
                    db.kind(kind).append(rec)
                    self._count(conduit, "duplicated")
                    continue
                if owner is not None:
                    if changed:
                        apply_lines(kind, owner, b, pda, today, None)
                    if flag_changed:
                        owner.done = bool(pda_flag)
                    owner.modified = now_iso()
                    self._count(conduit, "from PDA")
                else:
                    rec = CLASS_OF_KIND[kind]()
                    apply_lines(kind, rec, [""] * per, pda, today, pda_flag)
                    db.kind(kind).append(rec)
                    base.owners[str(slot(i))] = rec.id          # it stays where it was made
                    self._count(conduit, "new from PDA")

        # ---- 2. push: what the PDA should show now
        choice = db.pda_choice(kind, count, today)
        stage = STAGE_OF_KIND[kind]
        for i in range(count):
            rec = db.find(kind, choice[i]) if choice[i] else None
            want = lines_of(rec)
            pda = [pda_lines.get(slot(i, j), "") for j in range(per)]
            if act == "pda_overwrites":
                want = pda
            elif want != pda:
                for j in range(per):
                    if want[j] != pda[j]:
                        s_, text = slot(i, j), want[j]
                        self._queue(stage, lambda s_=s_, text=text: self.bus.write_text(s_, text))
                self._count(conduit, "to PDA")
            for j in range(per):
                base.lines[str(slot(i, j))] = want[j]
            if rec is not None:
                base.owners[str(slot(i))] = rec.id
            else:
                base.owners.pop(str(slot(i)), None)
            if flags is not None:
                want_flag = bool(rec.done) if (rec is not None and act != "pda_overwrites") else (flags[i] if act == "pda_overwrites" else False)
                if want_flag != flags[i] and act != "pda_overwrites":
                    k = pr.VALUE_INDEX[f"T{i}"]
                    self._queue(stage, lambda k=k, f=want_flag: self.bus.write_value(k, 1.0 if f else 0.0))
                base.flags[str(slot(i))] = want_flag

    # ------------------------------------------------------------ Note Pad
    def _ink_conduit(self, pda_ink: List[List[bool]], info: PdaInfo):
        act = self.action("notepad")
        if act == "nothing":
            return
        db, base = self.db, self.db.base
        scale = info.ink_scale
        pc = db.notepad.at_scale(scale)
        b = None
        if base.ink and len(base.ink) == db.notepad.rows * db.notepad.cols:
            from .model import NotePad
            tmp = NotePad(bits=list(base.ink))
            b = tmp.at_scale(scale)
        if pda_ink == pc:
            base.ink = list(db.notepad.bits)
            return
        pda_changed = pda_ink != b if b is not None else any(any(r) for r in pda_ink)
        pc_changed = pc != b if b is not None else not db.notepad.empty()
        take_pda = act == "pda_overwrites" or (act == "sync" and pda_changed and (not pc_changed or self.s.get("conflict") in ("pda", "duplicate")))
        if take_pda:
            db.notepad.set_from_scale(pda_ink, scale)
            self._count("notepad", "from PDA")
        elif act in ("sync", "pc_overwrites"):
            for r in range(len(pc)):
                if pc[r] != pda_ink[r]:
                    self._queue(pr.STAGE_NOTEPAD, lambda r=r, bits=pc[r]: self.bus.write_ink_row(r, bits))
            self._count("notepad", "to PDA")
        base.ink = list(db.notepad.bits)


# apply PDA lines onto a record ------------------------------------------------
_DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_WHEN = re.compile(r"^\s*(?:(mon|tue|wed|thu|fri|sat|sun)[a-z]*|(\d{1,2})/(\d{1,2}))(?:\s+(\d{1,2}):(\d{2}))?\s*(.*)$", re.I)

def apply_lines(kind: str, rec, before: List[str], pda: List[str], today: date, flag: Optional[bool]):
    if kind == "tasks":
        if pda[0] != before[0]:
            rec.title = pda[0]
        if flag is not None:
            rec.done = bool(flag)
    elif kind == "memos":
        if pda[0] != before[0]:
            rec.title = pda[0]
        if pda[1:] != before[1:]:
            rest = wrap(rec.body, pr.BUS_CHARS)[2:]
            head = " ".join(x for x in pda[1:] if x).strip()
            rec.body = head + ("\n" + " ".join(rest) if rest else "")
    elif kind == "events":
        if pda[0] != before[0]:
            rec.title = pda[0]
        if pda[1] != before[1]:
            m = _WHEN.match(pda[1])
            if m:
                old = rec.start_dt()
                dur = (rec.end_dt() - old) if old and rec.end_dt() else timedelta(hours=1)
                if m.group(1):
                    want = _DOW.index(m.group(1)[:3].lower())
                    d = today + timedelta(days=(want - today.weekday()) % 7)
                else:
                    mo, dy = int(m.group(2)), int(m.group(3))
                    try:
                        d = date(today.year, mo, dy)
                        if d < today - timedelta(days=60):
                            d = date(today.year + 1, mo, dy)
                    except ValueError:
                        d = today
                if m.group(4):
                    hh, mm = min(23, int(m.group(4))), min(59, int(m.group(5)))
                    start = datetime(d.year, d.month, d.day, hh, mm)
                    rec.all_day = False
                    rec.start = start.isoformat()
                    rec.end = (start + dur).isoformat()
                else:
                    rec.all_day = True
                    rec.start = d.isoformat()
                    rec.end = ""
                rec.location = m.group(6).strip() or rec.location
            else:
                rec.location = pda[1]
        if not rec.start:
            rec.start = datetime.combine(today, datetime.min.time()).replace(hour=12).isoformat()
    elif kind == "contacts":
        if pda[0] != before[0]:
            parts = pda[0].rsplit(" ", 1)
            rec.first, rec.last = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")
        if pda[1] != before[1]:
            v = pda[1]
            if before[1] and before[1] == pr.clean(rec.mobile):
                rec.mobile = v
            elif before[1] and before[1] == pr.clean(rec.phone):
                rec.phone = v
            elif "@" in v:
                rec.email = v
            elif sum(ch.isdigit() for ch in v) >= max(3, len(v) // 2):
                rec.mobile = v
            elif before[1] and before[1] == pr.clean(rec.email):
                rec.email = v
            else:
                rec.company = v
    rec.modified = now_iso()

