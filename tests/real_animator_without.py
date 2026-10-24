"""TalonSync against the REAL animator built WITHOUT Hoot Pet, TalonStar and PC Link (TP_WITHOUT=26,27,30 bridge.ps1)."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.osc import OscLink
from talonsync.bus import PdaBus, Timing, Nak
from talonsync.model import Database
from talonsync.settings import Settings
from talonsync.engine import SyncEngine
from talonsync import protocol as pr

tmp = tempfile.mkdtemp()
link = OscLink(send_port=19200, listen_port=19201); assert link.start()
s = Settings(os.path.join(tmp, "s.json")); s.update({"done_hold_seconds": 1.0, "connect_timeout": 15})
db = Database(os.path.join(tmp, "db.json"))
db.device.prefs["Theme"] = 3
bus = PdaBus(link, Timing(ack_timeout=1.0, settle=0.02), log=print)
hs = SyncEngine(db, s, bus, log=print)
rep = hs.run_blocking(); print(f"sync: ok={rep.ok} transfers={rep.transfers} {rep.error}")
assert rep.ok, rep.error
assert not db.device.pet, db.device.pet
print("theme on PDA:", bus.read_value(pr.VALUE_INDEX["Theme"]))
bus.pc_value(5, 77)                                   # the headset battery still works
for call in (lambda: bus.pc_value(0, 10), lambda: bus.weather({"ok": True})):
    try: call(); raise SystemExit("expected a NAK")
    except Nak: pass
    except (KeyError, TypeError): pass
print("WITHOUT-APPS OK")
