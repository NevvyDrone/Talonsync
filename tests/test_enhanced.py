"""TalonOS Enhanced (1.13): the desktop through the real terminal: splash, icons, the Start menu and submenus, windows,
the taskbar, touch taps, keys, typing, BASIC and back, shut down, TALONOS from anywhere and the desktop coming back."""
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
g = t.gui
cur = lambda: a.link.v.get("TP/Term/Cur")
def wait(cond, s=4.0):
    end = time.time() + s
    while time.time() < end and not cond(): time.sleep(0.02)
    return cond()
def text(r): return g.render().text_rows()[r]
def tap(r, c):
    """Press the digitizer contacts over cell (r, c) like a fingertip, then lift."""
    y = GUI_Y0 + GUI_RH * r + 26; x = GUI_X0 + 10 * c + 5
    ir = int((y - 40) // 12.5); ic = int((x - 8) // (304 / 24))
    t.on_touch(f"IR{ir}", True); t.on_touch(f"IC{ic}", True); time.sleep(0.2)
    t.on_touch(f"IR{ir}", False); t.on_touch(f"IC{ic}", False); time.sleep(0.05)

t.menu(); t.line("1")
assert t.mode == "gui" and cur() >= 2000, cur()
assert wait(lambda: cur() == 1000.0), cur()
assert "Start" in text(7) and "Files" in text(1) and "Settings" in text(1) and "Recycle Bin" in text(5)
v = a.link.v["TP/Term/L14_7"]; assert v >= 16384, v                   # the taskbar's style rides above the characters

# desktop icons by touch: Calculator, then use it by touch
tap(2, 13); assert g.window == "calc", g.window
calc = g.top
for key, (r, c) in {"1": (4, 6), "2": (4, 11), "*": (3, 21), "3": (4, 16), "=": (5, 16)}.items():
    tap(r, c)
assert calc.shown == "36", calc.shown
assert "Calc" in text(7)                                              # its taskbar button
# minimise with the caption button, then bring it back from the taskbar
r0, c0, r1, c1 = calc.rect
tap(r0, c1 - 2); assert g.top is None and g.window is None
tap(7, 10); assert g.top is calc
tap(r0, c1 - 1); assert not g.apps                                    # x closes it

# the Start menu: Right opens it, Games submenu by keys, launch Tic-Tac-Talon
t.on_cmd(44); assert g.menu_open
t.on_cmd(42); t.on_cmd(42); assert g.menu_sel == 2
t.on_cmd(44); assert g.sub_open == 2                                  # Right goes into the submenu
t.on_cmd(42); t.on_cmd(42); t.on_cmd(42); t.on_cmd(42); t.on_cmd(45)
assert g.window == "tictac", g.window
ttt = g.top
tap(1, 2)                                                             # square 1 by touch
assert ttt.b[0] == 1 and sum(1 for q in ttt.b if q == 2) == 1, ttt.b
t.on_cmd(43); assert not g.apps                                       # Left closes the game
# menu by touch, and a tap outside closes it
tap(7, 2); assert g.menu_open
tap(5, 25); assert not g.menu_open
# Settings > Control Panel by touch, switch to Skyglass by touch
tap(7, 2); tap(4, 3); assert g.sub_open == 4
tap(4, 18); assert g.window == "control", g.window
cp = g.top
tap(3, 13)                                                            # ( ) Skyglass
assert g.cfg["theme"] == "skyglass" and wait(lambda: cur() == 1500.0), cur()
assert t.snapshot()["theme"] == "skyglass"
tap(2, 13); assert g.cfg["theme"] == "classic"                        # back to Classic
# keys inside a window: Down moves through the controls, Center presses
cp.focus = 0; t.on_cmd(42); assert cp.list.sel == 1                    # the applet list takes Up/Down first
t.on_cmd(45); assert cp.focus == 1                                    # Center opens the applet: focus to its controls
t.on_cmd(41); t.on_cmd(41)
# typing a program name on the desktop opens it
g.close(cp); t.line("notepad"); assert g.window == "notepad"
np = g.top
t.line("Owls are"); t.line("very wise")
assert np.lines[:2] == ["Owls are", "very wise"], np.lines
np.path = os.path.join(a.dir, "Documents", "owls.txt"); np.save()
assert open(np.path).read() == "Owls are\nvery wise\n"
g.close(np)
# My Files shows the note and opens it in Notepad
t.line("files"); fl = g.top; assert any(n == "OWLS.TXT" for n, k, p in fl.items), fl.items
fl.list.sel = [n for n, k, p in fl.items].index("OWLS.TXT"); fl.open()
assert g.window == "notepad" and g.top.lines[:2] == ["Owls are", "very wise"]
g.close(g.top); g.close(fl)

# BASIC from the desktop runs full screen and BYE comes back to the desktop
tap(2, 24); assert t.mode == "basic", t.mode
t._run("PRINT 6*7"); assert " 42" in "".join(t.visible())
t._run("BYE"); assert t.mode == "gui"
# a BASIC program from the library window, and back
t.line("programs"); assert g.window == "library"
lib = g.top; lib.list.sel = 2; lib.do("R")
assert wait(lambda: t.mode == "library"), t.mode
assert wait(lambda: t.waiting_input)                                   # ROCK PAPER TALON asks for R, P or T
t.line("Q"); assert wait(lambda: t.lib_state == "after")
t.line(""); assert t.mode == "gui" and g.window == "library"
g.close(lib)

# TALONOS from BASIC, the library, the local terminal, however it's typed
t.leave_gui("menu"); t.line("2"); assert t.mode == "basic"
t.line("talon os"); assert t.mode == "gui", t.mode
t.leave_gui("menu"); assert t.mode == "menu" and not t.return_gui
t.line("Win"); assert t.mode == "gui"
t.leave_gui("menu"); t.line("2"); t.line("LIBRARY"); assert wait(lambda: t.mode == "library"), t.mode
t.line("TALONOS"); assert t.mode == "gui", t.mode
t.leave_gui("menu"); t.line("3"); assert t.mode == "local"; t.line("desktop"); assert t.mode == "gui"
assert not Terminal.wants_gui("PRINT 1") and not Terminal.wants_gui("10 WIN=1") and Terminal.wants_gui("TalonOS Enhanced")
t.leave_gui("menu"); t.line("2"); t._run('10 INPUT A$'); t._run('20 PRINT "GOT ";A$')
t.line("RUN"); assert wait(lambda: t.waiting_input); t.line("WIN")
assert wait(lambda: "GOT WIN" in "".join(t.visible())) and t.mode == "basic", t.mode

# the PDA powering on brings the desktop back (Start-up: TalonOS), or the menu if you chose that
t.line("TALONOS"); assert t.mode == "gui"
t.attach(); assert wait(lambda: t.mode == "gui" and g.splash_until > time.time() - 0.1, 2), t.mode
time.sleep(0.8); assert t.mode == "gui", t.mode
g.set("resume", False); t.attach(); time.sleep(0.9); assert t.mode == "menu", t.mode
g.set("resume", True)
t.leave_gui("menu"); t.attach(); time.sleep(0.9); assert t.mode == "menu", t.mode

# settings are kept in talonos.json
saved = __import__("json").load(open(os.path.join(a.dir, "talonos.json")))["settings"]
assert saved["theme"] == "classic" and saved["resume"] is True, saved

# shut down by keys
t.line("1"); assert wait(lambda: t.mode == "gui")
t.on_cmd(44)
for _ in range(6): t.on_cmd(42)
t.on_cmd(45); assert g.window == "shutdown", g.window
t.on_cmd(45); assert g.window == "safe" and "safe" in text(3)
assert wait(lambda: t.mode == "menu", 5)
# taps don't do anything outside the desktop, and nothing breaks when the CPU is switched off
a.settings["exp_terminal"] = False; tap(1, 1); t.stop()
print("ENHANCED OK")
