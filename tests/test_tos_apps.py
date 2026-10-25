"""TalonOS Enhanced apps (1.13): every app opens and survives random presses and typing in both themes; every control
can be reached by a fingertip on the PDA's touch grid; the games follow the BASIC versions' rules; Calculator, Notepad,
Files and the Recycle Bin do real work."""
import os, random, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.terminal import Terminal, GUI_X0, GUI_Y0, GUI_RH, INK_COLS
from talonsync.tos_apps import REGISTRY, list_files
from talonsync import tos_games as TG

class Link:
    def __init__(s): s.v = {}
    def set(s, n, v): s.v[n] = v
    def get(s, n, d=0): return s.v.get(n, d)
class App: pass
a = App(); a.link = Link(); a.dir = tempfile.mkdtemp(); a.settings = {"exp_terminal": True}
t = Terminal(a); t.mode = "gui"; t.return_gui = True
g = t.gui; g.splash_until = 0
t.leave_gui = lambda *x, **k: None                                       # keep BASIC out of the fuzzing
random.seed(7)

def problem():
    return any("has a problem" in row for row in g.render().text_rows())

# ---- 1. every app: opens, draws, and random keys / typing never break it (both themes)
apps = [k for k, v in REGISTRY.items() if v["cls"] and k not in ("msg", "prompt", "shutdown")]
for theme in ("classic", "skyglass"):
    g.cfg["theme"] = theme
    for app_id in apps:
        g.boot(); g.splash_until = 0
        app = g.launch(app_id)
        assert app is not None and not problem(), app_id
        for step in range(220):
            k = random.choice(["up", "down", "down", "enter", "enter", "back", "typed"])
            if k == "typed":
                g.typed(random.choice(["5", "42", "R", "hello owl", "", "A", "-3", "BYE", "1+2=", "x"]))
            elif k == "back":
                if random.random() < 0.15: g.key("back")
            else:
                g.key(k)
            if g.window == "safe":
                g.safe = False
            assert not problem(), (theme, app_id, step, g.render().text_rows())
print("fuzz ok:", len(apps), "apps x 2 themes")

# ---- 2. every control can be tapped with a real fingertip
xs = [8.0 + (304.0 / INK_COLS) * (i + 0.5) for i in range(INK_COLS)]
xs += [(xs[i] + xs[i + 1]) / 2 for i in range(INK_COLS - 1)]            # a fingertip often covers two contacts
def reachable(sc, idx):
    r0, c0, r1, c1, act = sc.spots[idx]
    for r in range(r0, r1 + 1):
        for x in xs:
            c = int((x - GUI_X0) // 10)
            if 0 <= c < 30 and sc.hit(r, c, (x - GUI_X0) / 10) is act:
                return True
    return False
def visible(sc, idx):                                                   # not hidden under a window or menu
    r0, c0, r1, c1, act = sc.spots[idx]
    return any(sc._hit(r, c) == idx for r in range(r0, r1 + 1) for c in range(c0, c1 + 1))
g.cfg["theme"] = "classic"
unreachable = []
for app_id in apps + ["msg", "shutdown"]:
    g.boot(); g.splash_until = 0
    g.launch(app_id) if app_id != "msg" else g.launch("msg", title="Delete", text="Move OWL.TXT to the bin?", buttons=("Yes", "No"))
    sc = g.render()
    for i in range(len(sc.spots)):
        if i not in sc.background and visible(sc, i) and not reachable(sc, i):
            unreachable.append((app_id, sc.spots[i][:4]))
g.boot(); g.splash_until = 0; g.menu_open = True; g.menu_pick(2); sc = g.render()
for i in range(len(sc.spots)):
    if i not in sc.background and visible(sc, i) and not reachable(sc, i):
        unreachable.append(("start menu", sc.spots[i][:4]))
assert not unreachable, unreachable
print("touch ok")

# ---- 2b. no text runs onto or past a window's right edge
for app_id in apps + ["msg", "shutdown"]:
    g.boot(); g.splash_until = 0
    app = g.launch(app_id) if app_id != "msg" else g.launch("msg", title="Delete", text="Move OWL.TXT to the Recycle Bin?", buttons=("Yes", "No"))
    sc = g.render(); r0, c0, r1, c1 = app.rect
    for r in range(r0 + 1, r1 + 1):
        assert not sc.cells[r][c1][0].strip(), (app_id, r, sc.text_rows()[r])

# ---- 3. Calculator
g.boot(); calc = g.launch("calc")
def calc_run(keys):
    calc.clear()
    for k in keys: calc.press(k)
    return calc.shown
assert calc_run("12*3=") == "36"
assert calc_run("7-10=") == "-3"
assert calc_run("1/4=") == "0.25"
assert calc_run("2+3*4=") == "20"                                       # a pocket calculator works left to right
assert calc_run("9/0=") == "Error"
assert calc_run("50+10%") == "5"
assert calc_run("5~") == "-5"
assert calc_run("123<") == "12"
assert calc_run("0.1+0.2=") == "0.3"
calc.clear(); g.typed("6x7="); assert calc.shown == "42", calc.shown

# ---- 4. Notepad, Files, Recycle Bin (real files); the fuzzing above may have binned a few, so start empty
import shutil; shutil.rmtree(os.path.join(a.dir, "Recycled"), ignore_errors=True)
g.boot(); np = g.launch("notepad")
for line in ["A very long line that will wrap around the window edge", "short"]: np.typed(line)
assert all(len(l) <= 28 for l in np.lines) and "short" in np.lines, np.lines
np.save()                                                               # no name yet: asks
assert g.window == "prompt"; g.typed("my note!"); assert g.top.value == "MYNOTE"; g.top.ok()
assert os.path.exists(os.path.join(a.dir, "Documents", "mynote.txt"))
os.makedirs(t.basic.folder, exist_ok=True)
open(os.path.join(t.basic.folder, "HELLO.bas"), "w").write('10 PRINT "HI"\n')
names = [n for n, k, p in list_files(g)]
assert "MYNOTE.TXT" in names and "HELLO.BAS" in names, names
g.boot(); f = g.launch("files"); g.render()
f.list.sel = names.index("MYNOTE.TXT"); f.delete(); assert g.window == "msg"; g.top.answer("Yes")
assert "MYNOTE.TXT" not in [n for n, k, p in list_files(g)]
b = g.launch("bin"); assert b.items() == ["mynote.txt"], b.items(); b.restore()
assert "MYNOTE.TXT" in [n for n, k, p in list_files(g)] and not b.items()
f.refresh(); f.list.sel = [n for n, k, p in f.items].index("HELLO.BAS"); f.delete(); g.top.answer("Yes")
b.empty(); g.top.answer("Yes"); assert not b.items()
assert not os.path.exists(os.path.join(t.basic.folder, "HELLO.bas"))
# closing an edited note asks first
g.boot(); np = g.launch("notepad"); np.typed("unsaved"); np.back(); assert g.window == "msg"; g.top.answer("No"); assert not g.apps

# ---- 5. the games follow their rules
g.boot()
gs = g.launch("guess"); gs.n = 37
for v in (50, 25, 37): gs.setg(v); gs.guess()
assert gs.done and gs.tries == 3 and g.scores["guess_best"] == 3
rpt = g.launch("rpt")
for h, c, res in [(0, 2, "win"), (2, 1, "win"), (1, 0, "win"), (2, 0, "lose"), (1, 1, "tie")]:
    w, l = rpt.w, rpt.l
    random.seed(0); TG.random.randrange = lambda n, c=c: c
    rpt.play(h)
    assert (rpt.w - w, rpt.l - l) == {"win": (1, 0), "lose": (0, 1), "tie": (0, 0)}[res], (h, c, rpt.msg)
TG.random.randrange = random.randrange
pile = g.launch("pile"); pile.take(4); assert pile.f == 21                # only 1-3
while not pile.over: pile.take(min(3, pile.f))
assert pile.over and pile.f == 0
ld = g.launch("lander")
for _ in range(40):
    if ld.over: break
    ld.setb(30 if ld.v > 8 else 10); ld.step()
assert ld.over and ld.fuel >= 0
ttt = g.launch("tictac"); ttt.move(0); ttt.move(1)                       # X X _ : the owl must block square 3
assert ttt.b[2] == 2, ttt.b
word = g.launch("word"); word.word = "OWL"
for ch in "OWL": word.guess(ch)
assert word.over and "got it" in word.msg.lower()
word.new(); word.word = "OWL"
for ch in "ABCDEF": word.guess(ch)
assert word.over and word.miss == 6
ae = g.launch("aerie")
for _ in range(12):
    if ae.over: break
    ae.setfeed(ae.n * 20); ae.end_year()
assert ae.over and len(ae.report) >= 3
dice = g.launch("dice")
for _ in range(200):
    if dice.over: break
    dice.roll() if dice.turn < 12 else dice.hold()
assert dice.over and (dice.you >= 50 or dice.me >= 50)
mouse = g.launch("mouse"); mouse.x, mouse.y = 4, 2
mouse.swoop(0, 0); assert mouse.hints[(0, 0)] == "SE"                     # south (down) and east (right)
mouse.swoop(8, 4); assert mouse.hints[(8, 4)] == "NW"
mouse.swoop(4, 2); assert mouse.over and "Got it" in mouse.msg
po = g.launch("ponder"); g.typed("I feel sad today"); assert po.log[-1] == "Ponder: Why do you feel sad?"
g.typed("bye"); assert po not in g.apps
m = g.launch("math")
for _ in range(10):
    m.answer = str(m.c); m.check()
assert m.over and m.right == 10 and g.scores["math_best"] == 10
# the high scores and settings are saved
data = __import__("json").load(open(os.path.join(a.dir, "talonos.json")))
assert data["scores"]["math_best"] == 10 and data["scores"]["guess_best"] == 3
t.stop()
print("TOS APPS OK")
