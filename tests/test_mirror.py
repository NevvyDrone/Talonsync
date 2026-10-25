"""Live backup (1.15): the copy follows OSC, survives an avatar reload, spots a wiped PDA and writes it back."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync import mirror as M

M.time.sleep = lambda s: None                      # skip the 4 s wait for the avatar to load
class Link:
    def __init__(self): self.sent = []
    def set(self, n, v): self.sent.append((n, v))
settings = {"live_backup": True, "auto_restore": False}
logs, link, query = [], Link(), {"v": {}}
m = M.PdaMirror(tempfile.mkdtemp(), settings, logs.append, lambda: link, lambda: False, lambda: query["v"])

# first load of the avatar: values from OSCQuery start the copy
query["v"] = {"TP/Tx/0_0": 72.0, "TP/Tx/0_1": 111.0, "TP/XL/0": 2, "TP/S/Theme": 1, "TP/In/Ok": True, "TP/Foil": True}
m._avatar_loaded("avtr_1")
assert m.avatar == "avtr_1" and "TP/In/Ok" not in m.values and m.values["TP/XL/0"] == 2, m.values

# typing on the PDA arrives over OSC; the copy is written once things settle
for i, ch in enumerate("Hoot at nine"):
    m.on_osc(f"/avatar/parameters/TP/Tx/1_{i}", [float(ord(ch))])
m.on_osc("/avatar/parameters/TP/T3", [1.0])
m.changed_at -= 5; m.tick()
assert os.path.exists(m._path("avtr_1")) and M.text_cells(m._load("avtr_1")["values"]) == 14, m._load("avtr_1")
assert m.snapshots(), "a first snapshot"

# a world later the PDA loads wiped: the copy isn't overwritten, an offer appears
query["v"] = {"TP/Tx/0_0": 0.0, "TP/Tx/0_1": 0.0, "TP/XL/0": 0, "TP/S/Theme": 1}
m._avatar_loaded("avtr_1")
assert m.offer and m.offer["cells_saved"] == 14 and M.text_cells(m.values) == 14, (m.offer, m.values)

# restore writes every saved value back with its own type, then clears the offer
r = m.restore()
sent = dict(link.sent)
assert sent["TP/Tx/1_0"] == 72.0 and sent["TP/XL/0"] == 2 and sent["TP/Foil"] is True and "TP/In/Ok" not in sent, sent
assert m.offer is None and "Restored" in r, r

# a normal reload (nothing wiped) keeps what the PDA has now
query["v"] = {"TP/Tx/0_0": 74.0, "TP/Tx/0_1": 111.0, "TP/XL/0": 2}
m._avatar_loaded("avtr_1")
assert m.offer is None and m.values["TP/Tx/0_0"] == 74.0

# auto-restore puts a wiped PDA back without asking
settings["auto_restore"] = True; link.sent.clear()
query["v"] = {"TP/Tx/0_0": 0.0, "TP/Tx/0_1": 0.0}
m.values["TP/Tx/2_0"] = 65.0; m._save()
m._avatar_loaded("avtr_1")
assert link.sent and m.offer is None, (link.sent, m.offer)
print("MIRROR OK")
