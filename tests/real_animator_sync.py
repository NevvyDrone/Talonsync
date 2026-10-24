"""TalonSync against the REAL generated animator (run gen/cscheck/bridge.ps1 first)."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.osc import OscLink
from talonsync.bus import PdaBus, Timing
from talonsync.model import Database
from talonsync.settings import Settings
from talonsync.engine import SyncEngine
from talonsync import protocol as pr

tmp = tempfile.mkdtemp()
link = OscLink(send_port=19200, listen_port=19201); assert link.start()
s = Settings(os.path.join(tmp, "s.json")); s.update({"done_hold_seconds": 1.0, "connect_timeout": 15})
db = Database(os.path.join(tmp, "db.json"))
db.memos[0].body = "Hoot! ~ {owls} [are] 100% cool & clever; |pipes| `ticks` ^caret^"
db.device.prefs["Theme"] = 4
bus = PdaBus(link, Timing(ack_timeout=1.0, settle=0.02), log=print)
hs = SyncEngine(db, s, bus, log=print)
t = time.time(); rep = hs.run_blocking(); print(f"sync 1: ok={rep.ok} {time.time()-t:.1f}s transfers={rep.transfers} {rep.error}")
assert rep.ok
# read back every slot and compare with what the PC wanted (exact text round trip through Tx = code/127)
bad = []
for slot, want in db.base.lines.items():
    got = bus.read_text(int(slot))
    if got != want: bad.append((slot, want, got))
print("readback mismatches:", bad)
print("theme on PDA:", bus.read_value(pr.VALUE_INDEX["Theme"]), " bright:", bus.read_value(pr.VALUE_INDEX["Bright"]))
print("pet:", db.device.pet)
rep = hs.run_blocking(); print(f"sync 2: ok={rep.ok} {rep.seconds}s transfers={rep.transfers}", rep.lines[-2])
bus.now_playing("Midnight Owls", "The Gryphons", 0.42)
print("probe:", bus.probe())
assert bus.ping() == 3, "PDA should speak link protocol 3"
for k, v in enumerate([23, 41, 58, 64, 47, 82, 64, 71, 72, 18, 140, 1, 2]): bus.pc_value(k, v)
bus.pc_message("Discord", "Wren: on my way"); bus.pc_alert(); bus.sky_location(41.9, -87.6); bus.pc_clear()
print("PC Link ports OK")
bus.open_app(26)
assert not bad
print("REAL ANIMATOR OK")
