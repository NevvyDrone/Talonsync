import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.model import Database
from talonsync import formats as F

def test_all():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "db.json"))
    db.contacts[0].notes = "Line one\nLine two, with; punctuation"
    db.contacts[0].birthday = "1990-04-01"
    db.notepad.bits[5] = 1
    files = F.export_all(db, os.path.join(tmp, "out"), ["vcf", "ics", "csv", "md", "png", "json"])
    print("\n".join(os.path.basename(f) for f in files))
    db2 = Database(os.path.join(tmp, "db2.json"))
    for k in ("contacts", "events", "tasks", "memos"): db2.kind(k).clear()
    for f in files:
        if f.endswith("Unity.json") or f.endswith(".png"): continue
        print(os.path.basename(f), F.import_file(db2, f))
    c = next(c for c in db2.contacts if c.first == "Archie")
    assert c.notes == db.contacts[0].notes and c.mobile == "555-0142" and c.favorite and c.birthday == "1990-04-01", c
    assert len(db2.contacts) == 3 and len(db2.events) == 2 and len(db2.tasks) == 3 and len(db2.memos) == 1, (len(db2.contacts), len(db2.events), len(db2.tasks), len(db2.memos))
    e = db2.events[0]; e0 = next(x for x in db.events if x.title == e.title)
    assert e.start[:16] == e0.start[:16] and e.end[:16] == e0.end[:16] and e.location == e0.location, (e, e0)
    assert any(t.done for t in db2.tasks)
    # unity json
    u = F.from_unity_json(F.to_unity_json(db))
    print({k: [getattr(r, 'title', None) or r.name for r in v] for k, v in u["records"].items()})
    assert u["notepad"] is not None and u["prefs"]["Theme"] == 1
    # outside formats
    google = 'Name,Given Name,Family Name,Phone 1 - Type,Phone 1 - Value,E-mail 1 - Value\nOwl Person,Owl,Person,Mobile,555-1234,owl@example.com\n'
    p = os.path.join(tmp, "google.csv"); open(p, "w").write(google)
    r = F.import_file(db2, p); assert r["contacts"] == 1, r
    v21 = "BEGIN:VCARD\r\nVERSION:2.1\r\nN:Hoot;Barney\r\nTEL;CELL;VOICE:555-7777\r\nNOTE;ENCODING=QUOTED-PRINTABLE:Caf=C3=A9 =\r\nowl\r\nEND:VCARD\r\n"
    cs = F.vcf_to_contacts(v21); assert cs[0].first == "Barney" and cs[0].mobile == "555-7777" and cs[0].notes == "Café owl", cs
    ics = "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:20261031T200000Z\r\nDURATION:PT2H\r\nSUMMARY:Halloween\\, owls\r\nBEGIN:VALARM\r\nTRIGGER:-PT15M\r\nEND:VALARM\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20261225\r\nDTEND;VALUE=DATE:20261226\r\nSUMMARY:Xmas\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ev, ts = F.ics_to_records(ics)
    assert ev[0].title == "Halloween, owls" and ev[0].alarm_min == 15 and ev[0].end and ev[1].all_day and ev[1].start == "2026-12-25", ev
    md = "# Tasks\n- [ ] fly home\n- [x] eat mouse (due 2026-10-30, !1)\n"
    t = F.md_to_tasks(md); assert t[1].done and t[1].due == "2026-10-30" and t[1].priority == 1
    png = F.notepad_to_png(db.notepad)
    np2 = F.png_to_notepad(png); assert np2.bits == db.notepad.bits, sum(np2.bits)
    print("FORMATS OK")

if __name__ == "__main__":
    test_all()
