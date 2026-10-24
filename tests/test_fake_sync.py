import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.osc import OscLink
from talonsync.bus import PdaBus, Timing
from talonsync.model import Database
from talonsync.settings import Settings
from talonsync.engine import SyncEngine
from talonsync.fakepda import FakePda
from talonsync import protocol as pr

def make(tmp, port_in=19000, port_out=19001, **kw):
    pda = FakePda(listen_port=port_in, send_port=port_out, **kw).start()
    link = OscLink(send_port=port_in, listen_port=port_out); assert link.start()
    s = Settings(os.path.join(tmp, "s.json")); s.update({"done_hold_seconds": 0.2})
    db = Database(os.path.join(tmp, "db.json"))
    bus = PdaBus(link, Timing(ack_timeout=0.5, settle=0.01))
    return pda, link, s, db, SyncEngine(db, s, bus, log=lambda m: None)

def test_roundtrip():
    tmp = tempfile.mkdtemp()
    pda, link, s, db, hs = make(tmp)
    t = time.time(); rep = hs.run_blocking(); dt = time.time() - t
    assert rep.ok, rep.error
    print(f"first sync {dt:.1f}s transfers={rep.transfers}")
    print("\n".join(rep.lines))
    titles = [x.title for x in db.tasks]
    assert "Feed the pet" in titles and "Draw an owl" in titles, titles
    assert any(m.title == "PDA memo" and "Talon Pilot!" in m.body for m in db.memos)
    assert db.notepad.empty()            # Talon Pilot 2.10+ has no Note Pad
    # the PC's records are now on the PDA
    lines = [pda.line(i) for i in range(48)]
    assert "Run a TalonSync" in lines and "Gryphon meetup" in lines and "Archie Barnowl" in lines, lines
    assert pda.screen == "TalonSync complete!", pda.screen
    # edit on PDA, edit on PC, sync again
    slot = lines.index("Run a TalonSync")
    pda.text[slot] = pr.encode_line("Run 2 syncs")
    pda.values["TP/T%d" % slot] = 1.0
    db.upsert("contacts", {"id": db.contacts[0].id, "mobile": "555-9999"})
    pda.values["TP/Theme"] = 3
    rep = hs.run_blocking()
    assert rep.ok, rep.error
    print("\n".join(rep.lines))
    t = next(x for x in db.tasks if x.title == "Run 2 syncs"); assert t.done
    assert "555-9999" in [pda.line(i) for i in range(48)]
    assert db.device.prefs["Theme"] == 3
    # third sync: nothing to do
    n0 = rep.transfers
    rep = hs.run_blocking()
    assert rep.ok and "everything already matched" in rep.lines[-2], rep.lines
    # now playing
    hs.bus.now_playing("Midnight Owls", "The Gryphons", 0.5)
    time.sleep(0.1)
    assert pda.now_playing == ["Midnight Owls", "The Gryphons"] and abs(pda.np_pos - 0.5) < 0.01
    hs.bus.open_app(26); assert pda.app == 26
    from talonsync import weather as W
    hs.bus.weather(W.sample()); hs.bus.jazz_mode(2)
    assert pda.weather[pr.ADDR_WX_CURRENT][14] == 1 and pda.weather[pr.ADDR_WX_CURRENT][0] == 154 and pda.jazz == 2, (pda.weather, pda.jazz)
    assert pr.decode_line(pda.weather[pr.ADDR_WX_NAME]) == "Chicago"
    hs.bus.ticker("Hoot hoot! Stay warm and clever, friend!")
    tk = "".join(chr(c) for l in range(3) for c in pda.weather[pr.ADDR_WX_TICKER + l])
    assert tk.rstrip() == "Hoot hoot! Stay warm and clever, friend!", repr(tk)
    pda.stop(); link.stop()

def test_no_pda():
    tmp = tempfile.mkdtemp()
    link = OscLink(send_port=19100, listen_port=19101); link.start()
    s = Settings(os.path.join(tmp, "s.json")); s.update({"connect_timeout": 1.0, "done_hold_seconds": 0})
    db = Database(os.path.join(tmp, "db.json"))
    hs = SyncEngine(db, s, PdaBus(link, Timing(ack_timeout=0.2, retries=0)))
    rep = hs.run_blocking()
    assert not rep.ok and "didn't answer" in rep.error
    link.stop()

if __name__ == "__main__":
    test_roundtrip(); test_no_pda(); print("ALL OK")
