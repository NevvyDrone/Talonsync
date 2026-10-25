# TalonOS Enhanced SDK (TalonSync 1.14, API version 1)

TalonOS Enhanced is the small windowed OS that runs inside TalonSync and shows on the Talon Pilot PDA's Terminal.
You can write apps for it in **Talon Enhanced BASIC** (safe to share) or in **Python** (plugins, off by default).

The screen is 30 columns by 8 rows. Row 7 is the taskbar; a full window's inside is rows 1-6, columns 1-28.

## How it fits together

```
 Apps:   built-in apps (tos_apps.py, tos_games.py)   BASIC apps (.BAS)   Python plugins (.PY)
           |                                            |                    |
 API:    self.api  ---------------------------------------------------------- (tos_kernel.API)
           fs (TalonFS)  settings  ui (dialogs)  events  clipboard  notify  launch  open
 Kernel: processes (PID, CPU time, faults)  event bus  registry  notifications  file types
 Window manager: windows, focus, taskbar, Start menu, taps and keys (enhanced.py)
 CPU:    TalonSync on your PC  ->  OSC  ->  the PDA's screen shader draws the cells
```

If an app crashes, the kernel closes that app only, writes the error to `C:\Temp\errors.log`, and the rest of
TalonOS keeps going. Task Manager (Start > Programs) shows every process and can end one.

## TalonFS: the file system

| Path | What's there |
|---|---|
| `C:\Documents` | your notes and documents |
| `C:\Programs` | BASIC programs (`SAVE` and `LOAD` use this folder) |
| `C:\Apps` | installed apps: `.BAS` apps and `.PY` plugins (they appear in Start > Programs) |
| `C:\Recycled` | the Recycle Bin (it remembers where each file came from) |
| `C:\Temp` | scratch space, emptied when TalonSync starts |
| `A:\` | the built-in BASIC programs, read only |

Paths ignore upper and lower case. A path without a drive is relative to the app's current folder (normally
`C:\Documents`). Names can use letters, numbers, spaces, `- _ ( )` and dots, up to 32 characters. Files are up to
1 MB; the C: drive holds up to 64 MB. Nothing can reach outside TalonSync's data folder: `..` stops at `C:\`, and
links are ignored.

File types: `.TXT`, `.LOG` and `.INI` open in Notepad; `.BAS` runs as a windowed app if it uses `WINDOW`, otherwise
in the BASIC terminal; `.PY` is a plugin.

## BASIC apps

A BASIC program that uses `WINDOW` runs as a TalonOS app in its own window. `PRINT` and `INPUT` work in the window
too. Rows 0-5 and columns 0-27 are the inside of the window.

| Statement | What it does |
|---|---|
| `WINDOW "TITLE"` | names the window (and makes the program a windowed app) |
| `TEXT r, c, S$` | writes text at row r, column c |
| `BUTTON id, r, c, width, "LABEL"` | a button; pressing it sends `id` |
| `FIELD id, r, c, width [, TEXT$]` | a text box; pressing Done in it sends `id`; `FIELD$(id)` reads it |
| `CHECK id, r, c, "LABEL" [, ON]` | a check box; ticking it sends `id`; `CHECKED(id)` is true when ticked |
| `BAR r, c, width, FRACTION` | a progress bar, 0 to 1 |
| `WAIT E [, SECONDS]` | waits for a button, field or check box and puts its id in `E` (0 if the time runs out) |
| `NOTIFY S$` | a notification balloon above the clock |
| `MSGBOX S$` | a message with OK; waits until it's pressed |
| `CLS` | clears the window |

Ids are shared by all controls in a window, so give each one its own number.

Files (in the terminal and in apps):

| Statement | What it does |
|---|---|
| `OPEN #n, PATH$, MODE$` | n is 1-4; mode `"I"` input, `"O"` output (replaces the file), `"A"` append |
| `PRINT #n, ...` | writes like `PRINT` |
| `INPUT #n, A$ [, B$...]` | reads the next line (commas split it when you give several variables) |
| `CLOSE #n` / `CLOSE` | closes one file, or all; files also close when the program ends |
| `EOF(n)` | true at the end of an input file |
| `EXISTS(PATH$)` | true when the file is there |

Errors you may see: `?FILE NOT FOUND`, `?BAD FILE NAME`, `?BAD FILE NUMBER`, `?FILE ALREADY OPEN`, `?DISK FULL`,
`?INPUT PAST END`, `?TALONOS ONLY` (a window statement in the BASIC terminal).

Example: a counter that keeps its count in a file.

```basic
10 WINDOW "OWL COUNTER"
20 C=0:IF EXISTS("COUNT.TXT") THEN OPEN #1,"COUNT.TXT","I":INPUT #1,C:CLOSE #1
30 TEXT 0,0,"OWLS:"+STR$(C)+"   ":BUTTON 1,2,0,6,"+1":BUTTON 2,2,8,8,"SAVE"
40 WAIT E
50 IF E=1 THEN C=C+1:GOTO 30
60 IF E=2 THEN OPEN #1,"COUNT.TXT","O":PRINT #1,C:CLOSE #1:NOTIFY "SAVED"
70 GOTO 40
```

Save it with Notepad or the BASIC editor in TalonSync's Experimental page, put it in `C:\Apps`, and it appears in
Start > Programs. HELLO, TODO and COUNTER in `C:\Apps` are samples to learn from.

Keywords are found even without spaces (classic BASIC), so variable names can't contain a keyword: `TEXT1`,
`BARN` or `WAITING` won't work as names.

## Python plugins

Python plugins can do anything Python can do on your PC, so they are **off** until you switch on
Control Panel > Plugins > Allow Python plugins. Each plugin asks once before it first runs, and asks again whenever
its file changes. Only run plugins from people you trust.

A plugin is one `.py` file in `C:\Apps` with a class `Main` built on `App` from `talonsync.tos_sdk`:

```python
from talonsync.tos_sdk import App, S

NAME = "Hello Plugin"       # the title in the Start menu and Task Manager
ICON = "K"                  # one of the PDA's icon letters (optional)


class Main(App):
    title = "Hello Plugin"
    short = "Hello"          # taskbar label, 5 letters
    # rect = (0, 0, 6, 29)  # the window: row0, col0, row1, col1 (rows 0-6)

    def __init__(self, os_):
        super().__init__(os_)
        self.count = self.api.settings.get("count", 0)

    def draw(self, ui, r0, c0, r1, c1):      # called every frame; r0..r1, c0..c1 is the inside of the window
        ui.label(r0, c0, "Hello from Python!", S.FACE_BLUE)
        ui.button(r1, c0, c0 + 8, "Press", self.press)

    def press(self):
        self.count += 1
        self.api.settings.set("count", self.count)

    # optional: key(k) -> bool, typed(text) -> bool, tick() -> bool (about once a second), back(), closing()
```

### The toolkit (`ui` in `draw`)

Controls are focusable in the order you draw them: Up/Down move between them, Center presses, Left calls `back()`
(close), typed text goes to the focused field or to `typed()`.

| Call | |
|---|---|
| `ui.label(r, c, text, style=S.FACE)` | text (clipped to the window) |
| `ui.center(r, c0, c1, text)` | centred text |
| `ui.button(r, c0, c1, label, action, enabled=True, pressed=False)` | a button |
| `ui.field(r, c0, c1, text, on_text, placeholder="")` | a text box; `on_text(text)` gets what's typed |
| `ui.check(r, c, label, value, on_toggle)` | a check box; `on_toggle(new_value)` |
| `ui.radio(r, c, label, on, choose)` | a radio button |
| `ui.listbox(r0, r1, c0, c1, items, state, on_open, on_select=None)` | a list; keep a `ListState()` in your app |
| `ui.progress(r, c0, c1, fraction)` | a progress bar |
| `ui.icon(r, c, letter, style=S.ICON)` | a PDA icon (`A`-`P`), `S.OWL` for the owl |

Styles: `S.FACE` (window), `S.FACE_BLUE` (blue text), `S.FIELD` (white box), `S.SEL` (selected), `S.BLUE`,
`S.CONSOLE` (black), `S.TIP` (yellow note), `S.DISABLED`. They follow the Classic or Skyglass look by themselves.

### The API (`self.api`)

| | |
|---|---|
| `api.fs` | TalonFS with your app's own current folder: `listdir`, `read_text`, `write_text`, `append_text`, `mkdir`, `rename`, `copy`, `move`, `delete` (to the bin), `exists`, `isdir`, `stat`, `normalize`, `cd` |
| `api.settings.get(key, default)` / `.set(key, value)` | your app's own saved settings |
| `api.system(key)` | read a system setting: `theme`, `clock24`, `seconds`, `sounds` |
| `api.ui.message(text, title, buttons, done)` | a dialog; `done(button)` |
| `api.ui.prompt(prompt, done, title, value, free)` | ask for a line of text |
| `api.ui.open_file(done, types, folder)` / `api.ui.save_file(done, name, types, folder)` | the Open and Save As dialogs |
| `api.events.on(topic, fn)` | `fs.changed`, `settings.changed`, `clipboard.changed`, `process.started`, `process.ended`, and `app.*` |
| `api.events.emit("app.something", data)` | tell other apps something (only `app.*` topics) |
| `api.clipboard_get()` / `api.clipboard_set(text)` | the shared clipboard |
| `api.notify(text)` | a notification balloon |
| `api.launch(app_id, **args)` / `api.open(path)` | start an app, or open a file with its app |
| `api.beep()`, `api.clock()`, `api.processes()`, `api.pid`, `api.log(text)` | |

Import only from `talonsync.tos_sdk`; the rest of TalonSync can change between versions, the SDK keeps working.
