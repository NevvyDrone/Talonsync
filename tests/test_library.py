"""Every Program Library program runs through the real terminal with scripted key presses and no BASIC errors."""
import os, sys, tempfile, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.terminal import Terminal, GFX_CHAR
from talonsync import library

class Link:
    def __init__(s): s.v = {}
    def set(s, n, v): s.v[n] = v
    def get(s, n, d=0): return s.v.get(n, d)
class App: pass

def screen(t):
    return "\n".join("".join(GFX_CHAR.get(ord(ch), ch) for ch in r) for r in t.visible())

random.seed(1)
answers = {
    "TOUR": lambda i: "BIRDY",
    "GUESS": lambda i: str(random.randint(1, 100)) if i < 40 else "N",
    "RPT": lambda i: "RPTXQ"[min(i % 6, 4)] if i < 12 else "Q",
    "FEATHERS": lambda i: str(random.randint(0, 4)) if i < 60 else "N",
    "LANDER": lambda i: str(random.choice([0, 10, 30, 99, -3])) if i < 60 else "N",
    "TICTAC": lambda i: str(random.randint(0, 10)) if i < 80 else "N",
    "WORD": lambda i: random.choice("AEIOUSTRNLMKPQZ1") if i < 60 else "N",
    "AERIE": lambda i: ["", "5", "200", "-3", "999999", "100"][i % 6] if i < 120 else "N",
    "DICE": lambda i: random.choice("RRRH") if i < 150 else "N",
    "MOUSE": lambda i: f"{random.randint(0,9)},{random.randint(0,9)}" if i < 20 else "N",
    "PONDER": lambda i: ["I AM SAD", "hello owl", "what", "my computer", "BYE"][i] if i < 5 else "BYE",
    "MATH": lambda i: ["2", "0"][min(i, 1)] if i < 30 else "N",
    "ART": lambda i: "",
}
fails = 0
for p in library.PROGRAMS:
    a = App(); a.link = Link(); a.dir = tempfile.mkdtemp(); a.settings = {"exp_terminal": True}
    t = Terminal(a)
    t.start_library(splash=False)
    t.line(str(library.PROGRAMS.index(p) + 1)); t.line("R")
    n, start, out = 0, time.time(), []
    orig = t.write
    t.write = lambda s, orig=orig: (out.append(s), orig(s))[1]
    limit = 3.0 if p["name"] in ("SINE", "LAUNCH") else 20.0
    while t.lib_state != "after" and time.time() - start < limit:
        if t.waiting_input:
            t.line(answers.get(p["name"], lambda i: "N")(n)); n += 1
        time.sleep(0.005)
    if t.lib_state != "after":
        t.on_cmd(43)                                   # Left: break the demo
        time.sleep(0.5)
    text = "".join(out)
    ok = "ERROR" not in text and t.lib_state == "after"
    fails += not ok
    print(f"{'OK  ' if ok else 'FAIL'} {p['name']:9} inputs={n:3}  {time.time()-start:4.1f}s")
    if not ok:
        print(screen(t))
    if p["name"] in ("TICTAC", "ART", "TOUR"):
        open(f"/tmp/claude-0/-home-claude/bb170ebd-2469-5e98-ada8-43fc9924e221/scratchpad/scr_{p['name']}.txt", "w").write(screen(t))
    t.stop()
# the library screens themselves
a = App(); a.link = Link(); a.dir = tempfile.mkdtemp(); a.settings = {"exp_terminal": True}
t = Terminal(a); t.menu(); print(screen(t)); t.line("1"); time.sleep(1.6); print(screen(t)); t.line("2"); print(screen(t))
t.line("L"); t.line(""); t.line("E"); print(screen(t)); t.line("LIBRARY"); time.sleep(1.6); t.line("N"); print(screen(t)); t.line("N"); print(screen(t))
assert os.path.exists(os.path.join(a.dir, "Programs", "GUESS.bas"))
for r in t.visible(): assert len(r) <= 30, r
t.stop()
assert fails == 0, fails
print("LIBRARY OK")
