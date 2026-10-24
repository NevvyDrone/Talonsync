"""TalonOS Enhanced: the desktop through the real terminal: splash, arrows, Start menu, touch taps, the library window,
running a program full screen and coming back, BASIC and BYE, shut down."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.terminal import Terminal, GUI_X0, GUI_Y0, GUI_RH
from talonsync import library

class Link:
    def __init__(s): s.v = {}
    def set(s, n, v): s.v[n] = v
    def get(s, n, d=0): return s.v.get(n, d)
class App: pass
a = App(); a.link = Link(); a.dir = tempfile.mkdtemp(); a.settings = {"exp_terminal": True}
t = Terminal(a)
cur = lambda: a.link.v.get("TP/Term/Cur")
def wait(cond, s=4.0):
    end = time.time() + s
    while time.time() < end and not cond(): time.sleep(0.02)
    return cond()
def text(r): return "".join(ch for ch, st in t.gui.render().rows()[r])
def tap(r, c):
    """Press the digitizer contacts over cell (r, c) like a fingertip, then lift."""
    y = GUI_Y0 + GUI_RH * r + 26; x = GUI_X0 + 10 * c + 5
    ir = int((y - 40) // 12.5); ic = int((x - 8) // (304 / 24))
    t.on_touch(f"IR{ir}", True); t.on_touch(f"IC{ic}", True); time.sleep(0.2)
    t.on_touch(f"IR{ir}", False); t.on_touch(f"IC{ic}", False); time.sleep(0.05)

t.menu(); t.line("1")
assert t.mode == "gui" and cur() >= 2000, cur()
assert wait(lambda: cur() == 1000.0), cur()
assert "Start" in text(7) and "Programs" in text(1)
# the registers carry styles: the taskbar's style 9 sits above the characters
v = a.link.v["TP/Term/L14_7"]; assert v >= 16384, v
# Right opens the Start menu, Down + Center opens BASIC... Left closes it instead
t.on_cmd(44); assert t.gui.menu_open; t.on_cmd(43); assert not t.gui.menu_open
# tap the Programs icon -> the library window
tap(0, 4); assert t.gui.window == "library", t.gui.window
assert "Program Library" in text(0)
t.on_cmd(42); t.on_cmd(42); assert t.gui.lib_sel == 2
tap(3, 10)                                            # tap the 3rd list row (index 2 again) = run it
assert wait(lambda: t.mode == "library"), t.mode
assert wait(lambda: t.waiting_input)                   # ROCK PAPER TALON asks for R, P or T
t.line("Q"); assert wait(lambda: t.lib_state == "after")
assert "TALONOS" in "".join(t.visible())
t.line(""); assert t.mode == "gui" and t.gui.window == "library"
# Close button by touch, then the Start menu by touch, then BASIC from it
tap(6, 25); assert t.gui.window is None
tap(7, 2); assert t.gui.menu_open
tap(2, 5); assert t.mode == "basic", t.mode
t._run("PRINT 6*7"); assert " 42" in "".join(t.visible())
t._run("BYE"); assert t.mode == "gui"
# the desktop by keys: About opens and closes, then shut down
t.gui.icon = 3; t.on_cmd(45); assert t.gui.window == "about" and "NevvyDrone" in text(4)
t.on_cmd(45); assert t.gui.window is None
t.on_cmd(44); [t.on_cmd(42) for _ in range(5)]; t.on_cmd(45); assert t.gui.window == "shutdown"
t.on_cmd(45); assert t.gui.window == "safe" and "safe" in text(3)
assert wait(lambda: t.mode == "menu", 5)
# taps don't do anything outside the desktop, and nothing breaks when the CPU is switched off
a.settings["exp_terminal"] = False; tap(1, 1); t.stop()
print("ENHANCED OK")
