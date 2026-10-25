"""The TalonSync window's Experimental page: snapshot, keys, typing, taps, start buttons, the BASIC editor's files and
loading / running a program, through the real HTTP API."""
import json, os, sys, tempfile, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.core import TalonSyncApp
from talonsync.server import Server

d = tempfile.mkdtemp()
app = TalonSyncApp(d)
app.settings.update({"demo_pda": True})
app.start()
srv = Server(app, 0).start()
base = srv.url.split("?")[0].rstrip("/")
tok = srv.url.split("t=")[1]
def call(path, body=None):
    req = urllib.request.Request(base + "/api/" + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-Token": tok, "Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
def wait(cond, s=5):
    end = time.time() + s
    while time.time() < end:
        if cond(): return True
        time.sleep(0.05)
    return False
try:
    # off: the page says so, and starting is refused politely
    code, t = call("terminal"); assert code == 200 and t["enabled"] is False
    code, r = call("terminal/start", {"what": "basic"}); assert code == 400 and "Terminal CPU" in r["error"], r
    call("settings", {"exp_terminal": True})
    # BASIC by typing from the PC
    code, t = call("terminal/start", {"what": "basic"}); assert t["mode"] == "basic" and "READY." in "".join(t["rows"])
    code, t = call("terminal/line", {"text": "PRINT 6*7; \"OWLS\""}); assert wait(lambda: " 42 OWLS" in "".join(call("terminal")[1]["rows"]))
    # the editor: save, list, read back, load + run with input
    src = '10 INPUT "NAME";N$\n20 PRINT "HI ";N$\n'
    code, r = call("program/save", {"name": "hi there!", "source": src}); assert r["name"] == "HITHERE", r
    code, r = call("programs"); assert "HITHERE" in r["files"] and any(p["name"] == "GUESS" for p in r["library"])
    code, r = call("program?name=HITHERE"); assert r["source"].startswith("10 INPUT")
    code, r = call("program?name=library:TOUR"); assert "LEARN BASIC" in r["source"]
    code, r = call("terminal/load", {"source": "PRINT 1\n"}); assert code == 400 and "line number" in r["error"]
    code, t = call("terminal/load", {"source": src, "run": True}); assert code == 200
    assert wait(lambda: call("terminal")[1]["waiting_input"])
    call("terminal/line", {"text": "ROBIN"})
    assert wait(lambda: "HI ROBIN" in "".join(call("terminal")[1]["rows"]))
    # Left breaks a running program
    call("terminal/load", {"source": '10 GOTO 10\n', "run": True}); assert wait(lambda: call("terminal")[1]["running"])
    call("terminal/key", {"key": "left"}); assert wait(lambda: not call("terminal")[1]["running"]) and "BREAK" in "".join(call("terminal")[1]["rows"])
    # TalonOS Enhanced: desktop, keys and a tap on the Programs icon open the library window
    code, t = call("terminal/start", {"what": "gui"}); assert t["gui"] is True
    assert wait(lambda: not call("terminal")[1]["splash"], 6)
    t = call("terminal")[1]; assert "Start" in t["rows"][7] and t["styles"][7][0] in (9, 10, 7), (t["mode"], t["rows"][7], t["styles"][7][:4])
    call("terminal/tap", {"row": 4, "col": 13}); assert app.terminal.gui.window == "library"
    call("terminal/key", {"key": "down"}); assert app.terminal.gui.top.list.sel == 1
    call("terminal/key", {"key": "left"}); assert app.terminal.gui.window is None
    call("terminal/key", {"key": "right"}); assert app.terminal.gui.menu_open
    code, r = call("program/delete", {"name": "HITHERE"}); assert "HITHERE" not in call("programs")[1]["files"]
    code, r = call("terminal/key", {"key": "sideways"}); assert code == 400
    print("PC TERMINAL OK")
finally:
    app.stop(); srv.stop()
