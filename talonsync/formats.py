"""Import / export in formats other apps open.

  Contacts   vCard (.vcf: Outlook, Google, iCloud, phones), CSV (Outlook / Google headers)
  Calendar   iCalendar (.ics: Outlook, Google Calendar, Apple), CSV
  Tasks      iCalendar VTODO (.ics), CSV, Markdown checklist (.md)
  Memos      Markdown (.md), plain text (.txt), one file or a folder of files
  Note Pad   PNG (export scaled up; import any picture, thresholded)
  Everything TalonSync backup (.json), Unity TalonSync JSON (TalonSyncData)
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import zlib
import struct
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from . import protocol as pr
from .model import Contact, Database, Event, Memo, NotePad, Task, now_iso, parse_dt


# ====================================================================== helpers
def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _unesc(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append("\n" if n in "nN" else n)
            i += 2
        else:
            out.append(c); i += 1
    return "".join(out)


def _fold(line: str) -> str:
    """RFC 5545/6350 line folding at 75 octets."""
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > (75 if not parts else 74):
            parts.append(cur.decode("utf-8")); cur = b""
        cur += e
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def _unfold(text: str) -> List[str]:
    lines: List[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw.strip():
            lines.append(raw)
    # vCard 2.1 quoted-printable soft line breaks
    merged: List[str] = []
    for l in lines:
        if merged and merged[-1].endswith("=") and "QUOTED-PRINTABLE" in merged[-1].upper():
            merged[-1] = merged[-1][:-1] + l
        else:
            merged.append(l)
    return merged


def _prop(line: str) -> Tuple[str, Dict[str, str], str]:
    """NAME;PARAM=x;TYPE=a,b:value -> (NAME, {PARAM: x, TYPE: 'A,B'}, value)."""
    # the first ':' not inside quotes separates the value
    q, idx = False, -1
    for i, ch in enumerate(line):
        if ch == '"':
            q = not q
        elif ch == ":" and not q:
            idx = i; break
    if idx < 0:
        return line.upper(), {}, ""
    head, value = line[:idx], line[idx + 1:]
    bits = head.split(";")
    name = bits[0].upper()
    if "." in name:                       # item1.TEL -> TEL (Apple groups)
        name = name.split(".", 1)[1]
    params: Dict[str, str] = {}
    for b in bits[1:]:
        if "=" in b:
            k, v = b.split("=", 1)
            k = k.upper()
            params[k] = (params[k] + "," if k in params else "") + v.strip('"').upper()
        else:                             # vCard 2.1: TEL;CELL;VOICE:
            params["TYPE"] = (params.get("TYPE", "") + "," if params.get("TYPE") else "") + b.upper()
    if params.get("ENCODING", "").upper() in ("QUOTED-PRINTABLE", "QP"):
        value = _qp_decode(value, params.get("CHARSET", "utf-8"))
    return name, params, value


def _qp_decode(v: str, charset: str) -> str:
    import quopri
    try:
        return quopri.decodestring(v.encode("latin-1", "replace")).decode(charset.lower() or "utf-8", "replace")
    except LookupError:
        return quopri.decodestring(v.encode("latin-1", "replace")).decode("utf-8", "replace")


def read_text_file(path: str) -> str:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            t = raw.decode(enc)
            if enc == "utf-16" and not (raw[:2] in (b"\xff\xfe", b"\xfe\xff")):
                continue
            return t
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ====================================================================== vCard
def contacts_to_vcf(contacts: List[Contact]) -> str:
    out = []
    for c in contacts:
        L = ["BEGIN:VCARD", "VERSION:3.0",
             f"N:{_esc(c.last)};{_esc(c.first)};;;",
             f"FN:{_esc(c.name or c.company or 'No name')}"]
        if c.company:
            L.append(f"ORG:{_esc(c.company)}")
        if c.job:
            L.append(f"TITLE:{_esc(c.job)}")
        if c.mobile:
            L.append(f"TEL;TYPE=CELL:{_esc(c.mobile)}")
        if c.phone:
            L.append(f"TEL;TYPE=VOICE:{_esc(c.phone)}")
        if c.email:
            L.append(f"EMAIL;TYPE=INTERNET:{_esc(c.email)}")
        if c.address:
            L.append(f"ADR;TYPE=HOME:;;{_esc(c.address)};;;;")
        if c.birthday:
            L.append(f"BDAY:{c.birthday}")
        if c.notes:
            L.append(f"NOTE:{_esc(c.notes)}")
        if c.category and c.category != "Unfiled":
            L.append(f"CATEGORIES:{_esc(c.category)}")
        L.append(f"X-TALONSYNC-FAVORITE:{'1' if c.favorite else '0'}")
        L.append(f"UID:talonsync-{c.id}")
        L.append("END:VCARD")
        out += [_fold(l) for l in L]
    return "\r\n".join(out) + "\r\n"


def vcf_to_contacts(text: str) -> List[Contact]:
    out: List[Contact] = []
    cur: Optional[Contact] = None
    for line in _unfold(text):
        name, params, value = _prop(line)
        if name == "BEGIN" and value.upper() == "VCARD":
            cur = Contact(); fn = ""
            continue
        if cur is None:
            continue
        if name == "END":
            if not (cur.first or cur.last) and fn:
                parts = fn.rsplit(" ", 1)
                cur.first, cur.last = (parts[0], parts[1]) if len(parts) == 2 else (fn, "")
            if cur.name or cur.company or cur.mobile or cur.email:
                out.append(cur)
            cur = None
            continue
        types = params.get("TYPE", "")
        if name == "N":
            f = (value.split(";") + [""] * 5)[:5]
            cur.last, cur.first = _unesc(f[0]), " ".join(x for x in (_unesc(f[1]), _unesc(f[2])) if x)
        elif name == "FN":
            fn = _unesc(value)
        elif name == "ORG":
            cur.company = _unesc(value.split(";")[0])
        elif name == "TITLE":
            cur.job = _unesc(value)
        elif name == "TEL":
            v = _unesc(value).replace("tel:", "")
            if ("CELL" in types or "MOBILE" in types or "IPHONE" in types) and not cur.mobile:
                cur.mobile = v
            elif not cur.phone:
                cur.phone = v
            elif not cur.mobile:
                cur.mobile = v
        elif name == "EMAIL" and not cur.email:
            cur.email = _unesc(value)
        elif name == "ADR" and not cur.address:
            f = [_unesc(x) for x in value.split(";")]
            cur.address = ", ".join(x for x in f if x)
        elif name == "BDAY":
            v = value.strip()
            m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", v)
            cur.birthday = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
        elif name == "NOTE":
            cur.notes = _unesc(value)
        elif name == "CATEGORIES":
            cur.category = _unesc(value).split(",")[0] or "Unfiled"
        elif name == "X-TALONSYNC-FAVORITE":
            cur.favorite = value.strip() == "1"
    return out


# ====================================================================== iCalendar
def _ics_dt(s: str, all_day: bool) -> str:
    d = parse_dt(s)
    if not d:
        return ""
    return d.strftime("%Y%m%d") if all_day else d.strftime("%Y%m%dT%H%M%S")


def _parse_ics_dt(value: str, params: Dict[str, str]) -> Tuple[Optional[datetime], bool]:
    v = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
        try:
            return datetime.strptime(v[:8], "%Y%m%d"), True
        except ValueError:
            return None, False
    m = re.match(r"(\d{8})T(\d{6})(Z?)", v)
    if not m:
        return None, False
    d = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    if m.group(3) == "Z":                       # UTC -> local time of this PC
        d = d.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    return d, False                             # TZID: taken as wall-clock time (good enough for a PDA)


def to_ics(events: List[Event], tasks: List[Task], name: str = "TalonSync") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TalonSync//Talon Pilot//EN", "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{_esc(name)}"]
    for e in events:
        L += ["BEGIN:VEVENT", f"UID:talonsync-{e.id}", f"DTSTAMP:{stamp}"]
        if e.all_day:
            L.append(f"DTSTART;VALUE=DATE:{_ics_dt(e.start, True)}")
            end = e.end_dt()
            if end:
                L.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
        else:
            L.append(f"DTSTART:{_ics_dt(e.start, False)}")
            if e.end_dt():
                L.append(f"DTEND:{e.end_dt().strftime('%Y%m%dT%H%M%S')}")
        L.append(f"SUMMARY:{_esc(e.title)}")
        if e.location:
            L.append(f"LOCATION:{_esc(e.location)}")
        if e.notes:
            L.append(f"DESCRIPTION:{_esc(e.notes)}")
        if e.category and e.category != "Unfiled":
            L.append(f"CATEGORIES:{_esc(e.category)}")
        if e.alarm_min >= 0:
            L += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(e.title)}", f"TRIGGER:-PT{e.alarm_min}M", "END:VALARM"]
        L.append("END:VEVENT")
    for t in tasks:
        L += ["BEGIN:VTODO", f"UID:talonsync-{t.id}", f"DTSTAMP:{stamp}", f"SUMMARY:{_esc(t.title)}",
              f"STATUS:{'COMPLETED' if t.done else 'NEEDS-ACTION'}", f"PRIORITY:{min(9, max(1, t.priority * 2 - 1))}"]
        if t.due:
            L.append(f"DUE;VALUE=DATE:{t.due.replace('-', '')}")
        if t.notes:
            L.append(f"DESCRIPTION:{_esc(t.notes)}")
        if t.category and t.category != "Unfiled":
            L.append(f"CATEGORIES:{_esc(t.category)}")
        L.append("END:VTODO")
    L.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in L) + "\r\n"


def ics_to_records(text: str) -> Tuple[List[Event], List[Task]]:
    events: List[Event] = []
    tasks: List[Task] = []
    cur = None
    kind = None
    depth_alarm = False
    for line in _unfold(text):
        name, params, value = _prop(line)
        if name == "BEGIN":
            v = value.upper()
            if v == "VEVENT":
                cur, kind = Event(), "e"
            elif v == "VTODO":
                cur, kind = Task(), "t"
            elif v == "VALARM":
                depth_alarm = True
            continue
        if name == "END":
            v = value.upper()
            if v == "VALARM":
                depth_alarm = False
            elif v in ("VEVENT", "VTODO") and cur is not None:
                if kind == "e" and cur.start:
                    events.append(cur)
                elif kind == "t" and cur.title:
                    tasks.append(cur)
                cur = kind = None
            continue
        if cur is None:
            continue
        if depth_alarm:
            if name == "TRIGGER" and kind == "e":
                m = re.match(r"-?P(?:T)?(?:(\d+)H)?(?:(\d+)M)?", value.replace("T", "T"))
                mm = re.search(r"(\d+)([DHM])", value)
                if mm:
                    n = int(mm.group(1)) * {"D": 1440, "H": 60, "M": 1}[mm.group(2)]
                    cur.alarm_min = n
            continue
        if name == "SUMMARY":
            cur.title = _unesc(value)
        elif name == "LOCATION" and kind == "e":
            cur.location = _unesc(value)
        elif name == "DESCRIPTION":
            cur.notes = _unesc(value)
        elif name == "CATEGORIES":
            cur.category = _unesc(value).split(",")[0] or "Unfiled"
        elif kind == "e" and name in ("DTSTART", "DTEND"):
            d, all_day = _parse_ics_dt(value, params)
            if d:
                if name == "DTSTART":
                    cur.all_day = all_day
                    cur.start = d.date().isoformat() if all_day else d.isoformat()
                else:
                    cur.end = d.date().isoformat() if all_day else d.isoformat()
        elif kind == "e" and name == "DURATION" and cur.start:
            m = re.match(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", value)
            if m:
                dur = timedelta(days=int(m.group(1) or 0), hours=int(m.group(2) or 0), minutes=int(m.group(3) or 0))
                s = parse_dt(cur.start)
                if s:
                    cur.end = (s + dur).isoformat()
        elif kind == "t" and name == "STATUS":
            cur.done = value.upper() == "COMPLETED"
        elif kind == "t" and name == "COMPLETED":
            cur.done = True
        elif kind == "t" and name == "DUE":
            d, _ = _parse_ics_dt(value, params)
            if d:
                cur.due = d.date().isoformat()
        elif kind == "t" and name == "PRIORITY":
            try:
                p = int(value)
                cur.priority = 3 if p == 0 else max(1, min(5, (p + 1) // 2))
            except ValueError:
                pass
    # all-day DTEND is exclusive in iCalendar; we store inclusive-ish "end" only for multi-day
    for e in events:
        if e.all_day and e.end:
            s, en = parse_dt(e.start), parse_dt(e.end)
            if s and en and (en - s).days <= 1:
                e.end = ""
    return events, tasks


# ====================================================================== CSV
CONTACT_CSV = ["First Name", "Last Name", "Company", "Job Title", "Mobile Phone", "Business Phone", "E-mail Address",
               "Home Street", "Birthday", "Notes", "Categories", "Favorite"]
_CONTACT_ALIASES = {
    "first": ["first name", "given name", "first", "firstname"],
    "last": ["last name", "family name", "surname", "last", "lastname"],
    "name": ["name", "full name", "display name", "fn"],
    "company": ["company", "organization 1 - name", "organization", "org"],
    "job": ["job title", "organization 1 - title", "title"],
    "mobile": ["mobile phone", "mobile", "cell", "cell phone", "phone 1 - value", "primary phone"],
    "phone": ["business phone", "home phone", "phone", "phone 2 - value", "other phone"],
    "email": ["e-mail address", "email", "e-mail 1 - value", "email address", "e-mail"],
    "address": ["home street", "address 1 - formatted", "address", "home address"],
    "birthday": ["birthday", "bday"],
    "notes": ["notes", "note"],
    "category": ["categories", "group membership", "category"],
    "favorite": ["favorite", "starred"],
}


def contacts_to_csv(contacts: List[Contact]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(CONTACT_CSV)
    for c in contacts:
        w.writerow([c.first, c.last, c.company, c.job, c.mobile, c.phone, c.email, c.address, c.birthday, c.notes,
                    "" if c.category == "Unfiled" else c.category, "1" if c.favorite else ""])
    return buf.getvalue()


def _dict_rows(text: str) -> List[Dict[str, str]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in rows]


def _pick(row: Dict[str, str], names: List[str]) -> str:
    for n in names:
        if row.get(n):
            return row[n]
    return ""


def csv_to_contacts(text: str) -> List[Contact]:
    out = []
    for r in _dict_rows(text):
        c = Contact()
        for field_, names in _CONTACT_ALIASES.items():
            v = _pick(r, names)
            if field_ == "name":
                if v and not (c.first or c.last):
                    parts = v.rsplit(" ", 1)
                    c.first, c.last = (parts[0], parts[1]) if len(parts) == 2 else (v, "")
            elif field_ == "favorite":
                c.favorite = v.lower() in ("1", "yes", "true", "x", "starred")
            elif field_ == "category":
                c.category = v.split(":::")[0].replace("* ", "").strip() or "Unfiled"
            elif v:
                setattr(c, field_, v)
        if c.name or c.company or c.mobile or c.email:
            out.append(c)
    return out


def events_to_csv(events: List[Event]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Subject", "Start Date", "Start Time", "End Date", "End Time", "All Day Event", "Location", "Description", "Categories"])
    for e in events:
        s, en = e.start_dt(), e.end_dt()
        w.writerow([e.title, s.strftime("%Y-%m-%d") if s else "", "" if e.all_day or not s else s.strftime("%H:%M"),
                    en.strftime("%Y-%m-%d") if en and not e.all_day else "", "" if e.all_day or not en else en.strftime("%H:%M"),
                    "True" if e.all_day else "False", e.location, e.notes, "" if e.category == "Unfiled" else e.category])
    return buf.getvalue()


def _parse_date_time(d: str, t: str) -> Optional[datetime]:
    d, t = (d or "").strip(), (t or "").strip()
    if not d:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            day = datetime.strptime(d, fmt)
            break
        except ValueError:
            day = None
    if day is None:
        return parse_dt(d)
    if t:
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p", "%I %p"):
            try:
                tt = datetime.strptime(t.upper(), fmt)
                return day.replace(hour=tt.hour, minute=tt.minute)
            except ValueError:
                pass
    return day


def csv_to_events(text: str) -> List[Event]:
    out = []
    for r in _dict_rows(text):
        title = _pick(r, ["subject", "title", "summary", "event"])
        s = _parse_date_time(_pick(r, ["start date", "date", "start"]), _pick(r, ["start time", "time"]))
        if not title or not s:
            continue
        en = _parse_date_time(_pick(r, ["end date"]) or _pick(r, ["start date", "date"]), _pick(r, ["end time"]))
        all_day = _pick(r, ["all day event", "all day", "allday"]).lower() in ("true", "yes", "1") or not _pick(r, ["start time", "time"])
        e = Event(title=title, all_day=all_day, location=_pick(r, ["location", "where"]), notes=_pick(r, ["description", "notes"]),
                  category=_pick(r, ["categories", "category"]) or "Unfiled")
        e.start = s.date().isoformat() if all_day else s.isoformat()
        if en and not all_day and en > s:
            e.end = en.isoformat()
        out.append(e)
    return out


def tasks_to_csv(tasks: List[Task]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Subject", "Done", "Due Date", "Priority", "Notes", "Categories"])
    for t in tasks:
        w.writerow([t.title, "True" if t.done else "False", t.due, t.priority, t.notes, "" if t.category == "Unfiled" else t.category])
    return buf.getvalue()


def csv_to_tasks(text: str) -> List[Task]:
    out = []
    for r in _dict_rows(text):
        title = _pick(r, ["subject", "title", "task", "name", "summary"])
        if not title:
            continue
        t = Task(title=title, notes=_pick(r, ["notes", "description"]), category=_pick(r, ["categories", "category"]) or "Unfiled")
        t.done = _pick(r, ["done", "complete", "completed", "status"]).lower() in ("true", "yes", "1", "x", "completed", "done")
        d = _parse_date_time(_pick(r, ["due date", "due"]), "")
        t.due = d.date().isoformat() if d else ""
        try:
            t.priority = max(1, min(5, int(_pick(r, ["priority"]) or 3)))
        except ValueError:
            t.priority = {"high": 1, "normal": 3, "low": 5}.get(_pick(r, ["priority"]).lower(), 3)
        out.append(t)
    return out


def memos_to_csv(memos: List[Memo]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Title", "Body", "Category", "Pinned", "Modified"])
    for m in memos:
        w.writerow([m.title, m.body, "" if m.category == "Unfiled" else m.category, "1" if m.pinned else "", m.modified])
    return buf.getvalue()


def csv_to_memos(text: str) -> List[Memo]:
    out = []
    for r in _dict_rows(text):
        title, body = _pick(r, ["title", "subject", "name"]), _pick(r, ["body", "text", "note", "notes", "content"])
        if title or body:
            out.append(Memo(title=title or body.split("\n")[0][:40], body=body, category=_pick(r, ["category", "categories"]) or "Unfiled",
                            pinned=_pick(r, ["pinned"]).lower() in ("1", "yes", "true")))
    return out


# ====================================================================== Markdown / text
def tasks_to_md(tasks: List[Task]) -> str:
    lines = ["# Tasks", ""]
    for t in sorted(tasks, key=lambda t: t.sort_key()):
        extra = []
        if t.due:
            extra.append(f"due {t.due}")
        if t.priority != 3:
            extra.append(f"!{t.priority}")
        lines.append(f"- [{'x' if t.done else ' '}] {t.title}" + (f"  ({', '.join(extra)})" if extra else ""))
    return "\n".join(lines) + "\n"


_MD_TASK = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]\s+(.*?)(?:\s+\(([^)]*)\))?\s*$")


def md_to_tasks(text: str) -> List[Task]:
    out = []
    for line in text.splitlines():
        m = _MD_TASK.match(line)
        if not m:
            continue
        t = Task(title=m.group(2).strip(), done=m.group(1).lower() == "x")
        for bit in (m.group(3) or "").split(","):
            bit = bit.strip()
            if bit.startswith("due "):
                t.due = bit[4:].strip()
            elif bit.startswith("!") and bit[1:].isdigit():
                t.priority = max(1, min(5, int(bit[1:])))
        out.append(t)
    return out


def memos_to_md(memos: List[Memo]) -> str:
    parts = []
    for m in memos:
        parts.append(f"# {m.title or 'Untitled'}\n\n{m.body.strip()}\n")
    return "\n---\n\n".join(parts)


def memo_to_md(m: Memo) -> str:
    return f"# {m.title or 'Untitled'}\n\n{m.body.strip()}\n"


def md_to_memos(text: str, fallback_title: str = "Imported memo") -> List[Memo]:
    """One memo per '# heading' (or per '---' block); plain text becomes one memo."""
    text = text.replace("\r\n", "\n")
    chunks = re.split(r"\n-{3,}\n", text) if re.search(r"\n-{3,}\n", text) else [text]
    out = []
    for chunk in chunks:
        heads = list(re.finditer(r"^#{1,6}\s+(.*)$", chunk, re.M))
        if not heads:
            body = chunk.strip()
            if body:
                first = body.split("\n", 1)
                out.append(Memo(title=first[0][:60] if len(first) > 1 else fallback_title, body=first[1].strip() if len(first) > 1 else body))
            continue
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(chunk)
            out.append(Memo(title=h.group(1).strip(), body=chunk[h.end():end].strip()))
    return out


# ====================================================================== PNG (pure Python, Pillow optional)
def _png(width: int, height: int, rgb_rows: List[bytes]) -> bytes:
    raw = b"".join(b"\0" + r for r in rgb_rows)
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def notepad_to_png(np_: NotePad, scale_px: int = 16, ink=(28, 32, 48), paper=(236, 240, 228), pda_scale: int = 1) -> bytes:
    rows = np_.at_scale(pda_scale) if pda_scale > 1 else [[np_.get(r, c) for c in range(np_.cols)] for r in range(np_.rows)]
    px = scale_px * pda_scale
    out = []
    for row in rows:
        line = b"".join(bytes(ink if on else paper) * px for on in row)
        out += [line] * px
    return _png(len(rows[0]) * px, len(rows) * px, out)


def png_to_notepad(data: bytes, threshold: float = 0.5, invert: Optional[bool] = None) -> NotePad:
    """Any picture -> 24 x 32 ink (needs Pillow). Dark pixels are ink, unless the picture is mostly dark."""
    from PIL import Image  # bundled with the exe
    im = Image.open(io.BytesIO(data)).convert("L")
    # fit 3:4 without stretching, centered on white
    W, H = 24, 32
    r = min(W * 16 / im.width, H * 16 / im.height)
    big = Image.new("L", (W * 16, H * 16), 255)
    sm = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    big.paste(sm, ((W * 16 - sm.width) // 2, (H * 16 - sm.height) // 2))
    small = big.resize((W, H), Image.BOX)
    vals = list(small.getdata())
    mean = sum(vals) / len(vals) / 255
    if invert is None:
        invert = mean < 0.4
    np_ = NotePad()
    np_.bits = [1 if ((v / 255 > threshold) if invert else (v / 255 < threshold)) else 0 for v in vals]
    np_.modified = now_iso()
    return np_


# ====================================================================== Unity TalonSync JSON (TalonSyncData)
def to_unity_json(db: Database) -> str:
    """The same fields Unity's TalonSync window reads (Tools > Talon Pilot > TalonSync > Import JSON)."""
    lines = [""] * 48
    for kind in ("tasks", "memos", "events", "contacts"):
        from .model import SLOT_COUNTS, SLOT_LAYOUT
        first, per = SLOT_LAYOUT[kind]
        for i, rid in enumerate(db.pda_choice(kind, SLOT_COUNTS[kind])):
            rec = db.find(kind, rid) if rid else None
            if rec:
                for j, l in enumerate(rec.pda_lines()):
                    lines[first + i * per + j] = l
    lines[pr.SLOT_HYPNO] = pr.clean(db.device.hypno_caption)
    task_ids = db.pda_choice("tasks", 8)
    done = [bool(db.find("tasks", t).done) if t else False for t in task_ids]
    p = db.device.prefs
    d = {
        "owner": db.device.owner, "powerOnAtLoad": False,
        "prefs": [float(p.get(v.key, 0)) for v in pr.PREFS],
        "slots": lines, "tasksDone": done,
        "model3D": int(p.get("model3D", 2)), "look3D": int(p.get("look3D", 2)), "spin3D": int(p.get("spin3D", 1)),
        "hypSpeed": int(p.get("hypSpeed", 2)), "hypStyle": int(p.get("hypStyle", 0)), "scopeMode": int(p.get("scopeMode", 0)),
        "ink": [bool(b) for b in db.notepad.bits],
        "pushSettings": True, "pushText": True, "pushDrawing": True, "pushAppearance": True, "pushContent": False,
        "overwriteOnLoad": True, "syncVersion": db.base.count, "lastPush": now_iso(),
    }
    return json.dumps(d, indent=2)


def from_unity_json(text: str) -> Dict:
    """Unity TalonSyncData JSON -> records + prefs (as if read from a PDA)."""
    from .engine import apply_lines
    from .model import SLOT_LAYOUT, SLOT_COUNTS
    d = json.loads(text)
    slots = (d.get("slots") or []) + [""] * 48
    done = (d.get("tasksDone") or []) + [False] * 8
    today = date.today()
    recs: Dict[str, List] = {"tasks": [], "memos": [], "events": [], "contacts": []}
    cls = {"tasks": Task, "memos": Memo, "events": Event, "contacts": Contact}
    for kind in recs:
        first, per = SLOT_LAYOUT[kind]
        for i in range(SLOT_COUNTS[kind]):
            lines = [pr.clean(slots[first + i * per + j] or "") for j in range(per)]
            if any(lines):
                r = cls[kind]()
                apply_lines(kind, r, [""] * per, lines, today, done[i] if kind == "tasks" else None)
                recs[kind].append(r)
    prefs = {}
    for v, x in zip(pr.PREFS, d.get("prefs") or []):
        prefs[v.key] = float(x)
    for k in ("model3D", "look3D", "spin3D", "hypSpeed", "hypStyle", "scopeMode"):
        if k in d:
            prefs[k] = float(d[k])
    ink = d.get("ink") or []
    np_ = None
    if len(ink) == 32 * 24 and any(ink):
        np_ = NotePad(bits=[1 if b else 0 for b in ink])
    return {"records": recs, "prefs": prefs, "owner": d.get("owner", ""), "hypno": pr.clean(slots[pr.SLOT_HYPNO] or ""), "notepad": np_}


# ====================================================================== import dispatcher
def detect(path: str, text_head: str = "") -> str:
    ext = os.path.splitext(path)[1].lower()
    head = text_head.lstrip()[:200].upper()
    if ext in (".vcf", ".vcard") or head.startswith("BEGIN:VCARD"):
        return "vcf"
    if ext in (".ics", ".ical", ".ifb") or head.startswith("BEGIN:VCALENDAR"):
        return "ics"
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
        return "image"
    if ext == ".json":
        return "json"
    if ext in (".csv", ".tsv"):
        return "csv"
    if ext in (".md", ".markdown"):
        return "md"
    return "txt"


def import_file(db: Database, path: str, target: str = "auto", dedupe: bool = True) -> Dict[str, int]:
    """Import one file into the database. target: auto | contacts | events | tasks | memos | notepad."""
    fmt = detect(path)
    added = {"contacts": 0, "events": 0, "tasks": 0, "memos": 0, "notepad": 0, "settings": 0, "skipped": 0}
    new: Dict[str, List] = {"contacts": [], "events": [], "tasks": [], "memos": []}
    if fmt == "image":
        with db.lock:
            db.notepad = png_to_notepad(open(path, "rb").read())
            db.touch()
        added["notepad"] = 1
        return added
    text = read_text_file(path)
    fmt = detect(path, text)
    name = os.path.splitext(os.path.basename(path))[0]
    if fmt == "vcf":
        new["contacts"] = vcf_to_contacts(text)
    elif fmt == "ics":
        new["events"], new["tasks"] = ics_to_records(text)
    elif fmt == "json":
        d = json.loads(text)
        if d.get("format") == "talonsync-db":
            raise ValueError("That's a TalonSync backup - use Backups > Restore to load it.")
        u = from_unity_json(text)
        new.update(u["records"])
        with db.lock:
            if u["prefs"]:
                db.device.prefs.update(u["prefs"]); added["settings"] = len(u["prefs"])
            if u["notepad"] is not None:
                db.notepad = u["notepad"]; added["notepad"] = 1
            if u["owner"]:
                db.device.owner = u["owner"]
    elif fmt == "csv":
        head = text.split("\n", 1)[0].lower()
        if target == "auto":
            if any(k in head for k in ("first name", "given name", "e-mail", "email", "phone", "family name")):
                target = "contacts"
            elif "start date" in head or "start time" in head or "all day" in head:
                target = "events"
            elif "due" in head or "done" in head or "priority" in head:
                target = "tasks"
            elif "body" in head:
                target = "memos"
            else:
                target = "contacts"
        new[target] = {"contacts": csv_to_contacts, "events": csv_to_events, "tasks": csv_to_tasks, "memos": csv_to_memos}[target](text)
    elif fmt in ("md", "txt"):
        tasks = md_to_tasks(text)
        if target == "tasks" or (target == "auto" and tasks and len(tasks) >= max(1, len([l for l in text.splitlines() if l.strip() and not l.startswith("#")]) // 2)):
            new["tasks"] = tasks
        else:
            new["memos"] = md_to_memos(text, fallback_title=name)
    with db.lock:
        for kind, items in new.items():
            existing = {_key(kind, r) for r in db.kind(kind)} if dedupe else set()
            for r in items:
                k = _key(kind, r)
                if k in existing:
                    added["skipped"] += 1
                    continue
                existing.add(k)
                db.kind(kind).append(r)
                added[kind] += 1
        db.touch()
    return added


def _key(kind: str, r) -> tuple:
    if kind == "contacts":
        return (r.name.lower(), (r.mobile or r.phone or r.email).lower())
    if kind == "events":
        return (r.title.lower(), r.start[:16])
    if kind == "tasks":
        return (r.title.lower(),)
    return (r.title.lower(), r.body.strip()[:80].lower())


# ====================================================================== export everything
def export_all(db: Database, folder: str, formats: List[str]) -> List[str]:
    os.makedirs(folder, exist_ok=True)
    written = []

    def w(name, data, binary=False):
        p = os.path.join(folder, name)
        with open(p, "wb" if binary else "w", encoding=None if binary else "utf-8", newline="" if not binary else None) as f:
            f.write(data)
        written.append(p)

    with db.lock:
        if "vcf" in formats:
            w("TalonSync Contacts.vcf", contacts_to_vcf(db.contacts))
        if "ics" in formats:
            w("TalonSync Calendar.ics", to_ics(db.events, db.tasks))
        if "csv" in formats:
            w("TalonSync Contacts.csv", contacts_to_csv(db.contacts))
            w("TalonSync Calendar.csv", events_to_csv(db.events))
            w("TalonSync Tasks.csv", tasks_to_csv(db.tasks))
            w("TalonSync Memos.csv", memos_to_csv(db.memos))
        if "md" in formats:
            w("TalonSync Tasks.md", tasks_to_md(db.tasks))
            w("TalonSync Memos.md", memos_to_md(db.memos))
        if "png" in formats:
            w("TalonSync Note Pad.png", notepad_to_png(db.notepad), binary=True)
        if "json" in formats:
            w("TalonSync for Unity.json", to_unity_json(db))
    return written
