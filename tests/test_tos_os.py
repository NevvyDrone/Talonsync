"""TalonOS Enhanced 1.14, the OS layer: TalonFS (paths, sandbox safety, quotas, the bin), the kernel (processes, fault
isolation, events, registry, clipboard, notifications), BASIC file I/O and BASIC windowed apps, Python plugins
(off by default, consent, re-consent when changed, crash isolation), Task Manager and Run."""
import json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.terminal import Terminal
from talonsync.tos_fs import FSError, TalonFS
from talonsync.enhanced import App as BaseApp

class Link:
    def __init__(s): s.v = {}
    def set(s, n, v): s.v[n] = v
    def get(s, n, d=0): return s.v.get(n, d)
class A: pass
a = A(); a.link = Link(); a.dir = tempfile.mkdtemp(); a.settings = {"exp_terminal": True}
t = Terminal(a); t.mode = "gui"; t.return_gui = True
g = t.gui; g.splash_until = 0; k = g.kernel; fs = k.fs
def wait(cond, s=4.0):
    end = time.time() + s
    while time.time() < end and not cond(): time.sleep(0.02)
    return cond()
def raises(fn, *x):
    try:
        fn(*x)
    except FSError:
        return True
    return False

# ---------------------------------------------------------------- TalonFS
assert fs.normalize("c:/documents/Owls.txt") == "C:\\Documents\\Owls.txt"
assert fs.normalize("notes.txt") == "C:\\Documents\\notes.txt"                     # relative to C:\Documents
assert fs.normalize("..\\Apps\\x.bas") == "C:\\Apps\\x.bas"
assert fs.normalize("C:\\..\\..\\..\\etc\\passwd") == "C:\\etc\\passwd"            # can't climb out of C:\
assert fs.real("C:\\..\\..\\etc\\passwd").startswith(os.path.join(a.dir, "TalonOS"))
for bad in ["C:\\Documents\\a*b.txt", "C:\\Documents\\con:x", "D:\\x.txt", "C:\\" + "x" * 40]:
    assert raises(fs.normalize, bad), bad
fs.write_text("C:\\Documents\\Owls.txt", "hoo\n")
assert fs.read_text("c:\\DOCUMENTS\\owls.TXT") == "hoo\n"                           # names ignore case
assert {"Documents", "Programs", "Apps", "Recycled", "Temp"} <= {e.name for e in fs.listdir("C:\\") if e.is_dir}
assert "GUESS.BAS" in [e.name for e in fs.listdir("A:\\")] and "PRINT" in fs.read_text("A:\\guess.bas")
assert raises(fs.write_text, "A:\\NEW.BAS", "x")                                     # A: is read only
assert raises(fs.write_text, "C:\\Documents\\big.txt", "x" * (1024 * 1024 + 1))     # 1 MB per file
# a link that points outside the sandbox is invisible and can't be used
os.symlink("/etc", os.path.join(a.dir, "Documents", "escape"))
assert "escape" not in [e.name for e in fs.listdir("C:\\Documents")]
assert raises(fs.read_text, "C:\\Documents\\escape\\passwd")
fs.mkdir("C:\\Documents\\Owl Notes")
assert raises(fs.mkdir, "C:\\Documents\\owl notes")                                  # already there (any case)
fs.copy("C:\\Documents\\Owls.txt", "C:\\Documents\\Owl Notes")
fs.copy("C:\\Documents\\Owls.txt", "C:\\Documents\\Owl Notes")
assert [e.name for e in fs.listdir("C:\\Documents\\Owl Notes")] == ["Owls (2).txt", "Owls.txt"]
fs.rename("C:\\Documents\\Owl Notes\\Owls (2).txt", "Copy.txt")
fs.copy("A:\\GUESS.BAS", "C:\\Programs")                                             # copy off the ROM disk
assert fs.exists("C:\\Programs\\GUESS.BAS")
assert raises(fs.delete, "C:\\Documents") and raises(fs.rename, "C:\\Apps", "X")     # system folders stay
binned = fs.delete("C:\\Documents\\Owl Notes\\Copy.txt")
assert ("Copy.txt", "C:\\Documents\\Owl Notes\\Copy.txt") in fs.bin_items()
fs.delete("C:\\Documents\\Owl Notes")                                                # the folder goes too
assert fs.restore("Copy.txt") == "C:\\Documents\\Copy.txt"                           # its folder is gone: Documents
fs.restore("Owl Notes"); assert fs.isdir("C:\\Documents\\Owl Notes")
assert fs.empty_bin() == 0 and not fs.bin_items()
print("fs ok")

# ---------------------------------------------------------------- kernel: processes, faults, events, registry
calc = g.launch("calc"); note = g.launch("notepad")
procs = {p["name"]: p for p in k.list()}
assert "Calculator" in procs and "Notepad" in procs and procs["Notepad"]["kind"] == "system"
class Broken(BaseApp):
    title = "Broken"
    def draw(self, ui, r0, c0, r1, c1):
        raise ZeroDivisionError("oops")
seen = []
b = g.start(Broken, "broken", "Broken")
b.api.events.on("fs.changed", lambda vp: seen.append(vp))
g.render()                                                                          # its draw fails ...
assert b not in g.apps and calc in g.apps and note in g.apps                       # ... only it closes
assert g.window == "msg" and "Broken has a problem" in " ".join(g.top.lines), g.top.lines
assert "ZeroDivisionError" in fs.read_text("C:\\Temp\\errors.log")
g.close(g.top)
seen.clear(); fs.write_text("C:\\Documents\\after.txt", "x"); assert seen == []                   # its subscriptions ended with it
got = []
calc.api.events.on("fs.changed", got.append); fs.write_text("C:\\Documents\\after.txt", "y")
assert got == ["C:\\Documents\\after.txt"]
calc.api.settings.set("memory", 42); note.api.settings.set("memory", 7)
assert calc.api.settings.get("memory") == 42 and note.api.settings.get("memory") == 7   # each app has its own
reg = json.load(open(os.path.join(a.dir, "talonos.json")))["registry"]
assert reg["apps.calc.memory"] == 42
note.api.clipboard_set("feathers"); assert calc.api.clipboard_get() == "feathers"
calc.api.notify("Hello owls"); assert "Hello owls" in g.render().text_rows()[6]
k.notes = []
try:
    calc.api.events.emit("fs.changed", "x"); assert False
except ValueError:
    pass                                                                            # apps can't fake system events
assert k.kill(calc.pid) and calc not in g.apps and calc.pid not in k.procs
tm = g.launch("taskmgr"); g.render()
names = [p["name"] for p in tm.rows]; tm.list.sel = names.index("Notepad"); tm.end()
assert note not in g.apps
g.boot(); g.splash_until = 0
print("kernel ok")

# ---------------------------------------------------------------- BASIC files (in the terminal)
t.mode = "basic"
out = []
bas = t.basic
bas.out = out.append
for line in ['10 OPEN #1,"C:\\DOCUMENTS\\OWLS.DAT","O"', '20 FOR I=1 TO 3:PRINT #1,"OWL";I:NEXT I', '30 CLOSE #1',
             '40 OPEN #1,"OWLS.DAT","A":PRINT #1,"LAST":CLOSE #1', '50 OPEN #2,"OWLS.DAT","I"',
             '60 IF EOF(2) THEN CLOSE #2:END', '70 INPUT #2,A$:PRINT "GOT ";A$:GOTO 60']:
    bas.enter(line)
bas.run()
assert fs.read_text("C:\\Documents\\OWLS.DAT") == "OWL 1 \nOWL 2 \nOWL 3 \nLAST\n", repr(fs.read_text("C:\\Documents\\OWLS.DAT"))
assert "".join(out).count("GOT ") == 4
def basic_error(src):
    bas.program.clear(); out.clear()
    for l in src: bas.enter(l)
    try:
        bas.run()
    except Exception as e:
        return str(e)
    return ""
assert basic_error(['10 OPEN #1,"NOPE.TXT","I"']) == "FILE NOT FOUND"
assert basic_error(['10 PRINT #3,"X"']) == "BAD FILE NUMBER"
assert basic_error(['10 OPEN #1,"A:\\GUESS.BAS","O"']) == "FILE ERROR"
assert basic_error(['10 OPEN #1,"A:\\GUESS.BAS","I":INPUT #1,A$:PRINT A$']) == "" and "CLS" in "".join(out)
assert basic_error(['10 WINDOW "X"']) == "TALONOS ONLY"
assert basic_error(['10 PRINT EXISTS("C:\\DOCUMENTS\\OWLS.DAT");EXISTS("NOPE")']) == "" and "-1  0" in "".join(out)
t.mode = "gui"
print("basic files ok")

# ---------------------------------------------------------------- BASIC windowed apps
assert {"HELLO.BAS", "TODO.BAS", "COUNTER.BAS", "hello_plugin.py"} <= {e.name for e in fs.listdir("C:\\Apps")}
h = k.open("C:\\Apps\\HELLO.BAS")
assert wait(lambda: h.windowed and h.title == "HELLO")
assert h in g.apps and k.proc_of(h).kind == "basic"
g.render(); h.focus = 0; g.typed("Robin")                                          # the name field
assert wait(lambda: "HI Robin! HOO!" in "".join(g.render().text_rows())), g.render().text_rows()
g.close(h); assert wait(lambda: not h.thread.is_alive())                            # closing stops the program
td = k.open("C:\\Apps\\TODO.BAS"); assert wait(lambda: td.windowed and 1 in td.controls and 2 in td.controls)
td._field_done(1, "Feed the owl")
assert wait(lambda: fs.exists("C:\\Documents\\TODO.TXT") and "Feed the owl" in fs.read_text("C:\\Documents\\TODO.TXT")), (td.error, td.console, td.controls)
g.close(td)
td2 = k.open("C:\\Apps\\TODO.BAS")                                                  # it remembers
assert wait(lambda: "1. Feed the owl" in "".join(g.render().text_rows()))
g.close(td2)
# a program with a mistake: a clear message, then Edit opens it in BASIC
fs.write_text("C:\\Apps\\OOPS.BAS", '10 WINDOW "OOPS"\n20 PRINT @\n')
k.open("C:\\Apps\\OOPS.BAS"); assert g.window == "msg" and "mistake" in " ".join(g.top.lines), g.top.lines
fs.write_text("C:\\Apps\\OOPS.BAS", '10 WINDOW "OOPS"\n20 X=1/0\n')
oops = k.open("C:\\Apps\\OOPS.BAS")
assert wait(lambda: "DIVISION BY ZERO" in oops.error), oops.error
assert oops in g.apps and "DIVISION BY ZERO" in "".join(g.render().text_rows())   # the error stays on screen
g.close(oops)
# a plain program (no WINDOW) opens in the BASIC terminal
fs.write_text("C:\\Programs\\PLAIN.BAS", '10 PRINT "HI"\n')
k.open("C:\\Programs\\PLAIN.BAS"); assert t.mode == "basic" and 10 in t.basic.program
t.mode = "gui"
print("basic apps ok")

# ---------------------------------------------------------------- Python plugins
g.boot(); g.splash_until = 0
assert not g.cfg["plugins"]
k.open("C:\\Apps\\hello_plugin.py"); assert g.window == "msg" and "off" in " ".join(g.top.lines)
g.top.answer("Settings"); assert g.window == "control"                               # Settings opens the Plugins page
g.boot(); g.splash_until = 0
g.set("plugins", True)
k.open("C:\\Apps\\hello_plugin.py"); assert g.window == "msg" and "trust" in " ".join(g.top.lines)
g.top.answer("Cancel"); assert not any(getattr(x, "app_id", "").startswith("plugin:") for x in g.apps)
k.open("C:\\Apps\\hello_plugin.py"); g.top.answer("Run")
p = g.top; assert p.app_id == "plugin:hello_plugin.py" and k.proc_of(p).kind == "plugin"
p.press(); p.press(); assert p.api.settings.get("count") == 2
g.close(p)
k.open("C:\\Apps\\hello_plugin.py"); assert g.top.app_id == "plugin:hello_plugin.py"   # trusted: no question
g.close(g.top)
fs.append_text("C:\\Apps\\hello_plugin.py", "\n# changed\n")
k.open("C:\\Apps\\hello_plugin.py"); assert g.window == "msg"                       # changed: asks again
g.top.answer("Cancel")
fs.write_text("C:\\Apps\\crashy.py", "from talonsync.tos_sdk import App\nclass Main(App):\n    title='Crashy'\n"
              "    def draw(self, ui, r0, c0, r1, c1):\n        raise RuntimeError('plugin bug')\n")
k.open("C:\\Apps\\crashy.py"); g.top.answer("Run"); g.render()
assert g.window == "msg" and "Crashy has a problem" in " ".join(g.top.lines)        # only the plugin closes
g.close(g.top)
fs.write_text("C:\\Apps\\nomain.py", "X = 1\n")
k.open("C:\\Apps\\nomain.py"); g.top.answer("Run")
assert g.window == "msg" and "couldn't start" in " ".join(g.top.lines)
g.close(g.top)
print("plugins ok")

# ---------------------------------------------------------------- Run and the Start menu
g.boot(); g.splash_until = 0
r = g.launch("run"); g.typed("calc"); assert g.window == "calc"
g.boot(); g.splash_until = 0
r = g.launch("run"); g.typed("C:\\Documents\\after.txt"); assert g.window == "notepad"
g.boot(); g.splash_until = 0
r = g.launch("run"); g.typed("C:\\Nowhere\\x.txt"); assert g.window == "msg"
from talonsync.tos_apps import start_menu
menu = start_menu(g)
progs = [x if isinstance(x, str) else x[0] for x in menu[0][2]]
assert "Hello" in progs and "Todo" in progs and "Hello Plugin" in progs, progs
docs = [x[0] for x in menu[3][2]]
assert "after.txt" in docs and docs[-1] == "My Documents", docs
t.stop()
print("TOS OS OK")
