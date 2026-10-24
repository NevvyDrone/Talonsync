"""Talon Enhanced BASIC - a small line-numbered BASIC for the Talon Pilot terminal.

Runs on the PC inside TalonSync; the PDA is its screen and keyboard. Classic home-computer style:

  10 PRINT "HELLO"          numbered lines are stored, others run at once
  RUN  LIST  NEW  CONT      SAVE "NAME"  LOAD "NAME"  FILES  KILL "NAME"  RENUM  DELETE 10-50
  PRINT (or ?)  LET  INPUT  IF..THEN..ELSE  FOR..TO..STEP / NEXT  GOTO  GOSUB / RETURN  ON..GOTO/GOSUB
  DIM  DATA / READ / RESTORE  REM (or ')  END  STOP  CLS  BEEP  SLEEP  RANDOMIZE
  ABS INT FIX SGN SQR SIN COS TAN ATN LOG EXP RND PI LEN VAL ASC INSTR
  LEFT$ RIGHT$ MID$ STR$ CHR$ UCASE$ LCASE$ TIME$ DATE$ TIMER TAB() SPC()
  Operators: + - * / ^ (or **) MOD, = <> < > <= >=, AND OR NOT. True is -1, false 0.
  "Enhanced": RND(n) with n > 1 gives a whole number 1..n; lines may be split over several 15-letter sends.

Like the old ones, keywords are recognised even without spaces (FORI=1TO10), so variable names must not
contain keywords. Errors use the classic "?SYNTAX ERROR IN 20" form.
"""
from __future__ import annotations

import math
import os
import random
import re
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

VERSION = "1.0"
MEMORY = 32000                     # bytes of program space, as shown in the banner and by FREE

STATEMENTS = ["PRINT", "LET", "INPUT", "IF", "THEN", "ELSE", "FOR", "TO", "STEP", "NEXT", "GOTO", "GOSUB", "RETURN", "END",
              "STOP", "REM", "DIM", "DATA", "READ", "RESTORE", "CLS", "BEEP", "ON", "SLEEP", "RANDOMIZE",
              "RUN", "LIST", "NEW", "SAVE", "LOAD", "FILES", "DIR", "KILL", "RENUM", "DELETE", "CONT", "HELP", "VER", "FREE", "BYE", "SYSTEM",
              "LOCATE", "BOX", "LINE"]
OPERATORS = ["AND", "OR", "NOT", "MOD"]
FUNCTIONS = ["ABS", "INT", "FIX", "SGN", "SQR", "SIN", "COS", "TAN", "ATN", "LOG", "EXP", "RND", "PI", "LEN", "VAL", "ASC",
             "INSTR", "LEFT$", "RIGHT$", "MID$", "STR$", "CHR$", "UCASE$", "LCASE$", "TIME$", "DATE$", "TIMER", "TAB", "SPC"]
KEYWORDS = sorted(set(STATEMENTS + OPERATORS + FUNCTIONS), key=len, reverse=True)


class BasicError(Exception):
    pass


class Break(Exception):
    pass


class ExitBasic(Exception):
    """BYE or SYSTEM: leave BASIC for the terminal's own commands."""


# ---------------------------------------------------------------- tokenizer
Token = Tuple[str, object]          # (kind, value): num, str, kw, id, op, end


def tokenize(src: str) -> List[Token]:
    toks: List[Token] = []
    i, n, up = 0, len(src), src.upper()
    while i < n:
        ch = src[i]
        if ch in " \t":
            i += 1
            continue
        if ch == '"':
            j = src.find('"', i + 1)
            if j < 0:
                j = n                                      # an unclosed string runs to the end of the line
            toks.append(("str", src[i + 1:j]))
            i = j + 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and src[i + 1].isdigit()):
            m = re.match(r"\d*\.?\d*(E[+-]?\d+)?", up[i:])
            toks.append(("num", float(m.group(0))))
            i += len(m.group(0))
            continue
        if ch == "?":
            toks.append(("kw", "PRINT"))
            i += 1
            continue
        if ch == "'":
            toks.append(("kw", "REM"))
            toks.append(("str", src[i + 1:]))
            break
        if ch.isalpha():
            kw = next((k for k in KEYWORDS if up.startswith(k, i)), None)
            if kw:
                toks.append(("kw", kw))
                i += len(kw)
                if kw == "REM":
                    toks.append(("str", src[i:].strip()))
                    break
                if kw == "DATA":
                    toks.append(("str", src[i:]))
                    break
                continue
            j = i + 1
            while j < n and (src[j].isalnum()) and not any(up.startswith(k, j) for k in KEYWORDS):
                j += 1
            if j < n and src[j] == "$":
                j += 1
            toks.append(("id", up[i:j]))
            i = j
            continue
        two = src[i:i + 2]
        if two in ("<>", "<=", ">=", "**", "><", "=<", "=>"):
            toks.append(("op", {"><": "<>", "=<": "<=", "=>": ">=", "**": "^"}.get(two, two)))
            i += 2
            continue
        if ch in "+-*/^=<>(),;:":
            toks.append(("op", ch))
            i += 1
            continue
        raise BasicError("SYNTAX")
    toks.append(("end", None))
    return toks


def fmt_num(v: float) -> str:
    if v == int(v) and abs(v) < 1e15:
        s = str(int(v))
    else:
        s = f"{v:.9g}".replace("e+", "E+").replace("e-", "E-")
        if s.startswith("0."):
            s = s[1:]
        elif s.startswith("-0."):
            s = "-" + s[2:]
    return (" " + s if v >= 0 else s) + " "


# ---------------------------------------------------------------- interpreter
class Basic:
    """The interpreter. `out(text)` prints (\\n for new lines); `inp(prompt)` blocks until the user sends a line;
    `beep()`, `cls()` drive the PDA. RUN executes on the caller's thread: run it on a worker thread."""

    def __init__(self, out: Callable[[str], None], inp: Callable[[str], Optional[str]],
                 beep: Callable[[], None] = lambda: None, cls: Callable[[], None] = lambda: None,
                 folder: Optional[str] = None, locate: Optional[Callable[[int, int], None]] = None,
                 plot: Optional[Callable[[int, int, str], None]] = None):
        self.out, self.inp, self.beep_fn, self.cls_fn = out, inp, beep, cls
        self.locate_fn, self.plot_fn = locate or (lambda r, c: None), plot or (lambda r, c, ch: None)
        self.folder = folder
        self.program: Dict[int, str] = {}
        self.col = 0                                      # print column, for TAB and commas
        self.stop_flag = threading.Event()
        self.running = False
        self.cont: Optional[Tuple[int, int]] = None
        self.clear()

    # -- state
    def clear(self):
        self.vars: Dict[str, object] = {}
        self.arrays: Dict[str, Tuple[List[int], Dict[Tuple[int, ...], object]]] = {}
        self.for_stack: List[Tuple[str, float, float, int, int]] = []
        self.gosub_stack: List[Tuple[int, int]] = []
        self.data: List[object] = []
        self.data_ptr = 0

    def used(self) -> int:
        return sum(len(str(k)) + len(v) + 2 for k, v in self.program.items())

    def write(self, text: str):
        for ch in text:
            if ch == "\n":
                self.col = 0
            else:
                self.col = (self.col + 1) % 30
        self.out(text)

    # -- entry point for one line typed at the prompt
    def enter(self, line: str):
        line = line.rstrip()
        if not line.strip():
            return
        m = re.match(r"\s*(\d+)\s?(.*)$", line)
        if m:
            num, body = int(m.group(1)), m.group(2)
            if body.strip():
                tokenize(body)                            # reject a syntax error now, not when it runs
                if self.used() + len(body) > MEMORY:
                    raise BasicError("OUT OF MEMORY")
                self.program[num] = body.strip()
            else:
                self.program.pop(num, None)
            self.cont = None
            return
        self.exec_line(tokenize(line), direct=True)

    # -- running
    def lines(self) -> List[int]:
        return sorted(self.program)

    def run(self, start: Optional[int] = None, resume: Optional[Tuple[int, int]] = None):
        order = self.lines()
        if resume is None:
            self.clear()
            self.data = []
            for n in order:
                t = tokenize(self.program[n])
                for k, tok in enumerate(t):
                    if tok == ("kw", "DATA"):
                        self.data += self._split_data(t[k + 1][1] if t[k + 1][0] == "str" else "")
            idx = 0 if start is None else self._index_of(start, order)
            pos = 0
        else:
            idx, pos = resume
        self.running = True
        self.stop_flag.clear()
        self.order = order
        count = 0
        try:
            while 0 <= idx < len(order):
                self.cur_line = order[idx]
                toks = tokenize(self.program[self.cur_line])
                res = self._exec_from(toks, pos, idx)
                if res is None:                           # END / STOP
                    return
                idx, pos = res
                count += 1
                if count % 200 == 0:
                    if self.stop_flag.is_set():
                        self.cont = (idx, pos)
                        raise Break()
                    time.sleep(0.0005)                    # keep TalonSync responsive during tight loops
        finally:
            self.running = False

    def _index_of(self, num: int, order=None) -> int:
        order = order if order is not None else self.order
        try:
            return order.index(num)
        except ValueError:
            raise BasicError("UNDEF'D STATEMENT")

    def _split_data(self, s: str) -> List[object]:
        items, cur, q = [], "", False
        for ch in s + ",":
            if ch == '"':
                q = not q
            elif ch == "," and not q:
                v = cur.strip()
                try:
                    items.append(float(v))
                except ValueError:
                    items.append(v.strip('"'))
                cur = ""
            else:
                cur += ch
        return items

    # -- statements
    def exec_line(self, toks: List[Token], direct=False):
        self.order = self.lines()
        self.cur_line = None
        self._exec_from(toks, 0, -1, direct=True)

    def _exec_from(self, toks: List[Token], pos: int, idx: int, direct=False):
        """Execute statements of one line from token pos. Returns (next idx, next pos), or None to stop."""
        self.t, self.p = toks, pos
        while True:
            if self.stop_flag.is_set() and not direct:
                self.cont = (idx, self.p)
                raise Break()
            kind, val = self.t[self.p]
            if kind == "end":
                return (idx + 1, 0)
            if (kind, val) == ("op", ":"):
                self.p += 1
                continue
            if kind == "kw" and val == "ELSE":            # reached ELSE after a true IF: skip the rest
                return (idx + 1, 0)
            jump = self.statement(idx, direct)
            if jump == "stop":
                return None
            if jump == "then":                            # IF: the next statement follows THEN / ELSE directly
                continue
            if isinstance(jump, tuple):
                if jump[0] == -1:                         # a jump from immediate mode: start running there
                    if direct:
                        self.run(resume=(jump[1], jump[2]))
                        return None
                    return (jump[1], jump[2])
                return jump
            kind, val = self.t[self.p]
            if kind == "end":
                return (idx + 1, 0)
            if (kind, val) == ("op", ":"):
                self.p += 1
            elif (kind, val) == ("kw", "ELSE"):
                return (idx + 1, 0)
            else:
                raise BasicError("SYNTAX")

    def peek(self) -> Token:
        return self.t[self.p]

    def take(self) -> Token:
        tok = self.t[self.p]
        self.p += 1
        return tok

    def expect(self, kind, val=None):
        k, v = self.take()
        if k != kind or (val is not None and v != val):
            raise BasicError("SYNTAX")
        return v

    def at(self, kind, val=None) -> bool:
        k, v = self.t[self.p]
        return k == kind and (val is None or v == val)

    def _goto(self, num: int, direct: bool):
        i = self._index_of(num, self.lines())
        return (-1, i, 0) if direct else (i, 0)

    def statement(self, idx: int, direct: bool):
        kind, val = self.peek()
        if kind == "id":
            self.assign()
            return None
        if kind != "kw":
            raise BasicError("SYNTAX")
        self.p += 1
        kw = val
        if kw == "PRINT":
            self.do_print()
        elif kw == "LET":
            self.assign()
        elif kw == "REM":
            self.p = len(self.t) - 1
        elif kw == "DATA":
            self.p = len(self.t) - 1
        elif kw == "IF":
            cond = self.expr()
            if self.at("kw", "THEN"):
                self.take()
            elif not self.at("kw", "GOTO"):
                raise BasicError("SYNTAX")
            if cond:
                if self.at("num"):
                    return self._goto(int(self.take()[1]), direct)
                if self.at("kw", "GOTO"):
                    self.take()
                    return self._goto(int(self.expr()), direct)
                return "then"                             # carry on with the statements after THEN
            # false: find a matching ELSE on this line
            depth = 0
            while not self.at("end"):
                k, v = self.take()
                if (k, v) == ("kw", "IF"):
                    depth += 1
                elif (k, v) == ("kw", "ELSE"):
                    if depth == 0:
                        if self.at("num"):
                            return self._goto(int(self.take()[1]), direct)
                        return "then"
                    depth -= 1
            return None
        elif kw == "GOTO":
            return self._goto(int(self.expr()), direct)
        elif kw == "GOSUB":
            if direct:
                raise BasicError("ILLEGAL DIRECT")
            target = int(self.expr())
            self.gosub_stack.append((idx, self.p))
            return self._goto(target, direct)
        elif kw == "RETURN":
            if not self.gosub_stack:
                raise BasicError("RETURN WITHOUT GOSUB")
            ri, rp = self.gosub_stack.pop()
            return (ri, rp)
        elif kw == "ON":
            n = int(self.expr())
            how = self.expect("kw")
            if how not in ("GOTO", "GOSUB"):
                raise BasicError("SYNTAX")
            targets = [int(self.expr())]
            while self.at("op", ","):
                self.take()
                targets.append(int(self.expr()))
            if 1 <= n <= len(targets):
                if how == "GOSUB":
                    self.gosub_stack.append((idx, self.p))
                return self._goto(targets[n - 1], direct)
        elif kw == "FOR":
            name = self.expect("id")
            self.expect("op", "=")
            self.vars[name] = self.num(self.expr())
            self.expect("kw", "TO")
            end = self.num(self.expr())
            step = 1.0
            if self.at("kw", "STEP"):
                self.take()
                step = self.num(self.expr())
            self.for_stack = [f for f in self.for_stack if f[0] != name]
            self.for_stack.append((name, end, step, idx, self.p))
        elif kw == "NEXT":
            names = [self.take()[1]] if self.at("id") else [None]
            while self.at("op", ","):                      # NEXT J, I
                self.take()
                names.append(self.expect("id"))
            for name in names:
                while True:
                    if not self.for_stack:
                        raise BasicError("NEXT WITHOUT FOR")
                    fname, end, step, fi, fp = self.for_stack[-1]
                    if name is None or fname == name:
                        break
                    self.for_stack.pop()
                v = self.vars[fname] + step
                self.vars[fname] = v
                if (step >= 0 and v <= end) or (step < 0 and v >= end):
                    if fi < 0:                             # a loop typed on one line at the prompt
                        self.p = fp
                        return None
                    return (fi, fp)
                self.for_stack.pop()
        elif kw == "END":
            return "stop"
        elif kw == "STOP":
            self.cont = (idx, self.p)
            self.write("BREAK" + (f" IN {self.cur_line}" if self.cur_line is not None else "") + "\n")
            return "stop"
        elif kw == "DIM":
            while True:
                name = self.expect("id")
                self.expect("op", "(")
                dims = [int(self.expr())]
                while self.at("op", ","):
                    self.take()
                    dims.append(int(self.expr()))
                self.expect("op", ")")
                if any(d < 0 or d > 1000 for d in dims):
                    raise BasicError("ILLEGAL QUANTITY")
                self.arrays[name] = (dims, {})
                if not self.at("op", ","):
                    break
                self.take()
        elif kw == "READ":
            while True:
                target = self.lvalue()
                if self.data_ptr >= len(self.data):
                    raise BasicError("OUT OF DATA")
                v = self.data[self.data_ptr]
                self.data_ptr += 1
                self.store(target, v)
                if not self.at("op", ","):
                    break
                self.take()
        elif kw == "RESTORE":
            self.data_ptr = 0
        elif kw == "INPUT":
            prompt = "? "
            if self.at("str"):
                prompt = self.take()[1]
                if self.at("op", ";"):
                    self.take()
                    prompt += "? "
                elif self.at("op", ","):
                    self.take()
            targets = [self.lvalue()]
            while self.at("op", ","):
                self.take()
                targets.append(self.lvalue())
            while True:
                reply = self.inp(prompt)
                if reply is None:
                    raise Break()
                parts = [x.strip() for x in reply.split(",")] if len(targets) > 1 else [reply]
                try:
                    if len(parts) < len(targets):
                        raise ValueError
                    for tgt, part in zip(targets, parts):
                        self.store(tgt, part if tgt[0].endswith("$") else float(part or 0))
                    break
                except ValueError:
                    self.write("?REDO FROM START\n")
        elif kw == "CLS":
            self.cls_fn()
            self.col = 0
        elif kw == "BEEP":
            self.beep_fn()
        elif kw == "SLEEP":
            secs = self.num(self.expr())
            end = time.time() + max(0.0, min(secs, 600.0))
            while time.time() < end:
                if self.stop_flag.is_set():
                    raise Break()
                time.sleep(0.05)
        elif kw == "RANDOMIZE":
            if not self.at("end") and not self.at("op", ":"):
                random.seed(self.expr())
            else:
                random.seed()
        elif kw == "LOCATE":                               # LOCATE row, column (0-7, 0-29)
            r, c = self.nums(2)
            self.locate_fn(int(r), int(c))
            self.col = int(c)
        elif kw == "BOX":                                  # BOX row, column, height, width: a box in lines
            r, c, h, w = (int(v) for v in self.nums(4))
            if h < 2 or w < 2:
                raise BasicError("ILLEGAL QUANTITY")
            for i in range(w):
                side = (4 if i else 0) + (8 if i < w - 1 else 0)
                corner = i == 0 or i == w - 1
                self.plot_fn(r, c + i, chr(16 + side + (2 if corner else 0)))
                self.plot_fn(r + h - 1, c + i, chr(16 + side + (1 if corner else 0)))
            for j in range(1, h - 1):
                self.plot_fn(r + j, c, chr(19))
                self.plot_fn(r + j, c + w - 1, chr(19))
        elif kw == "LINE":                                 # LINE row1, col1, row2, col2: straight or 45 degrees
            r1, c1, r2, c2 = (int(v) for v in self.nums(4))
            dr, dc = (r2 > r1) - (r2 < r1), (c2 > c1) - (c2 < c1)
            n = max(abs(r2 - r1), abs(c2 - c1))
            if dr and dc and abs(r2 - r1) != abs(c2 - c1):
                raise BasicError("ILLEGAL QUANTITY")
            for i in range(n + 1):
                if dr and dc:
                    ch = chr(15 if dr == dc else 14)
                elif dr:
                    ch = chr(16 + (0 if i == 0 else (1 if dr > 0 else 2)) + (0 if i == n else (2 if dr > 0 else 1)))
                else:
                    ch = chr(16 + (0 if i == 0 else (4 if dc > 0 else 8)) + (0 if i == n else (8 if dc > 0 else 4)))
                if n == 0:
                    ch = chr(31)
                self.plot_fn(r1 + i * dr, c1 + i * dc, ch)
        elif kw in ("BYE", "SYSTEM"):
            raise ExitBasic()
        elif kw in ("RUN", "LIST", "NEW", "SAVE", "LOAD", "FILES", "DIR", "KILL", "RENUM", "DELETE", "CONT", "HELP", "VER", "FREE"):
            return self.command(kw, direct)
        else:
            raise BasicError("SYNTAX")
        return None

    # -- immediate-mode commands
    def command(self, kw: str, direct: bool):
        if kw == "RUN":
            start = int(self.expr()) if self.at("num") else None
            if not self.program:
                return None
            self.run(start)
            self.p = len(self.t) - 1
            return "stop"
        if kw == "CONT":
            if not self.cont:
                raise BasicError("CAN'T CONTINUE")
            c, self.cont = self.cont, None
            self.order = self.lines()
            self.run(resume=c)
            return "stop"
        if kw == "LIST":
            lo, hi = 0, 10 ** 9
            if self.at("num"):
                lo = hi = int(self.take()[1])
            if self.at("op", "-"):
                self.take()
                hi = int(self.take()[1]) if self.at("num") else 10 ** 9
            for n in self.lines():
                if lo <= n <= hi:
                    self.write(f"{n} {self.program[n]}\n")
            return None
        if kw == "NEW":
            self.program.clear()
            self.clear()
            self.cont = None
            return None
        if kw == "FREE":
            self.write(f"{MEMORY - self.used()} BYTES FREE\n")
            return None
        if kw == "VER":
            self.write(f"TALON ENHANCED BASIC {VERSION}\n")
            return None
        if kw == "HELP":
            for line in HELP_TEXT:
                self.write(line + "\n")
            return None
        if kw == "DELETE":
            lo = int(self.take()[1]) if self.at("num") else 0
            hi = lo
            if self.at("op", "-"):
                self.take()
                hi = int(self.take()[1]) if self.at("num") else 10 ** 9
            for n in [n for n in self.program if lo <= n <= hi]:
                del self.program[n]
            return None
        if kw == "RENUM":
            self.renum()
            return None
        if kw in ("FILES", "DIR"):
            names = self.files()
            if not names:
                self.write("NO FILES\n")
            for n in names:
                self.write(n + "\n")
            return None
        name = self._filename()
        path = os.path.join(self.folder or ".", name + ".bas")
        if kw == "SAVE":
            os.makedirs(self.folder, exist_ok=True)
            with open(path, "w", encoding="utf-8", errors="replace") as f:
                for n in self.lines():
                    f.write(f"{n} {self.program[n]}\n")
            self.write(f"SAVED {name}\n")
        elif kw == "LOAD":
            if not os.path.exists(path):
                raise BasicError("FILE NOT FOUND")
            prog: Dict[int, str] = {}
            for raw in open(path, encoding="utf-8", errors="replace"):
                m = re.match(r"\s*(\d+)\s?(.*)$", raw.rstrip("\n"))
                if m and m.group(2).strip():
                    prog[int(m.group(1))] = m.group(2).strip()
            self.program = prog
            self.clear()
            self.write(f"LOADED {name}\n")
        elif kw == "KILL":
            if not os.path.exists(path):
                raise BasicError("FILE NOT FOUND")
            os.remove(path)
            self.write(f"DELETED {name}\n")
        return None

    def nums(self, n: int) -> List[float]:
        vals = [self.num(self.expr())]
        for _ in range(n - 1):
            self.expect("op", ",")
            vals.append(self.num(self.expr()))
        return vals

    def _filename(self) -> str:
        if not self.at("str") or not self.folder:
            raise BasicError("SYNTAX")
        name = re.sub(r"[^A-Z0-9_]", "", str(self.take()[1]).upper())[:8]
        if not name:
            raise BasicError("BAD FILE NAME")
        return name

    def files(self) -> List[str]:
        if not self.folder or not os.path.isdir(self.folder):
            return []
        return sorted(f[:-4] for f in os.listdir(self.folder) if f.endswith(".bas") and not f.startswith("_"))

    def renum(self, start=10, step=10):
        old = self.lines()
        mapping = {n: start + i * step for i, n in enumerate(old)}
        def fix(body: str) -> str:
            def rep(m):
                n = int(m.group(2))
                return m.group(1) + str(mapping.get(n, n))
            return re.sub(r"((?:GOTO|GOSUB|THEN|ELSE)\s*)(\d+)", rep, body, flags=re.I)
        self.program = {mapping[n]: fix(self.program[n]) for n in old}

    # -- PRINT
    def do_print(self):
        newline = True
        while not self.at("end") and not self.at("op", ":") and not self.at("kw", "ELSE"):
            if self.at("op", ";"):
                self.take()
                newline = False
                continue
            if self.at("op", ","):
                self.take()
                self.write(" " * (10 - self.col % 10))
                newline = False
                continue
            if self.at("kw", "TAB") or self.at("kw", "SPC"):
                f = self.take()[1]
                self.expect("op", "(")
                n = int(self.num(self.expr()))
                self.expect("op", ")")
                self.write(" " * (max(0, n - self.col) if f == "TAB" else max(0, n)))
                newline = True
                continue
            v = self.expr()
            self.write(fmt_num(v) if isinstance(v, float) else str(v))
            newline = True
        if newline:
            self.write("\n")

    # -- variables
    def lvalue(self):
        name = self.expect("id")
        if self.at("op", "("):
            self.take()
            idx = [int(self.num(self.expr()))]
            while self.at("op", ","):
                self.take()
                idx.append(int(self.num(self.expr())))
            self.expect("op", ")")
            return (name, tuple(idx))
        return (name, None)

    def store(self, target, value):
        name, idx = target
        if name.endswith("$"):
            value = value if isinstance(value, str) else fmt_num(value).strip()
        elif isinstance(value, str):
            raise BasicError("TYPE MISMATCH")
        if idx is None:
            self.vars[name] = value
            return
        dims, cells = self.arrays.setdefault(name, ([10] * len(idx), {}))
        if len(idx) != len(dims) or any(i < 0 or i > d for i, d in zip(idx, dims)):
            raise BasicError("SUBSCRIPT OUT OF RANGE")
        cells[idx] = value

    def assign(self):
        target = self.lvalue()
        self.expect("op", "=")
        self.store(target, self.expr())

    @staticmethod
    def num(v) -> float:
        if isinstance(v, str):
            raise BasicError("TYPE MISMATCH")
        return v

    # -- expressions
    def expr(self):
        v = self.and_expr()
        while self.at("kw", "OR"):
            self.take()
            v = float(int(self.num(v)) | int(self.num(self.and_expr())))
        return v

    def and_expr(self):
        v = self.not_expr()
        while self.at("kw", "AND"):
            self.take()
            v = float(int(self.num(v)) & int(self.num(self.not_expr())))
        return v

    def not_expr(self):
        if self.at("kw", "NOT"):
            self.take()
            return float(~int(self.num(self.not_expr())))
        return self.comparison()

    def comparison(self):
        v = self.additive()
        while self.at("op") and self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.take()[1]
            w = self.additive()
            if isinstance(v, str) != isinstance(w, str):
                raise BasicError("TYPE MISMATCH")
            r = {"=": v == w, "<>": v != w, "<": v < w, ">": v > w, "<=": v <= w, ">=": v >= w}[op]
            v = -1.0 if r else 0.0
        return v

    def additive(self):
        v = self.term()
        while self.at("op") and self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            w = self.term()
            if op == "+":
                if isinstance(v, str) and isinstance(w, str):
                    v = v + w
                else:
                    v = self.num(v) + self.num(w)
            else:
                v = self.num(v) - self.num(w)
        return v

    def term(self):
        v = self.unary()
        while (self.at("op") and self.peek()[1] in ("*", "/")) or self.at("kw", "MOD"):
            op = self.take()[1]
            w = self.num(self.unary())
            if op == "*":
                v = self.num(v) * w
            else:
                if w == 0:
                    raise BasicError("DIVISION BY ZERO")
                v = self.num(v) / w if op == "/" else float(math.fmod(self.num(v), w))
        return v

    def unary(self):
        if self.at("op", "-"):
            self.take()
            return -self.num(self.unary())
        if self.at("op", "+"):
            self.take()
            return self.num(self.unary())
        return self.power()

    def power(self):
        v = self.primary()
        if self.at("op", "^"):
            self.take()
            e = self.num(self.unary())
            try:
                v = float(self.num(v) ** e)
            except (OverflowError, ZeroDivisionError):
                raise BasicError("OVERFLOW")
            if isinstance(v, complex):
                raise BasicError("ILLEGAL QUANTITY")
        return v

    def primary(self):
        kind, val = self.take()
        if kind == "num":
            return val
        if kind == "str":
            return val
        if (kind, val) == ("op", "("):
            v = self.expr()
            self.expect("op", ")")
            return v
        if kind == "id":
            if self.at("op", "("):
                self.p -= 1
                name, idx = self.lvalue()
                dims, cells = self.arrays.setdefault(name, ([10] * len(idx), {}))
                if len(idx) != len(dims) or any(i < 0 or i > d for i, d in zip(idx, dims)):
                    raise BasicError("SUBSCRIPT OUT OF RANGE")
                return cells.get(idx, "" if name.endswith("$") else 0.0)
            return self.vars.get(val, "" if val.endswith("$") else 0.0)
        if kind == "kw" and val in FUNCTIONS:
            return self.function(val)
        raise BasicError("SYNTAX")

    def args(self, n_min: int, n_max: int):
        self.expect("op", "(")
        a = [self.expr()]
        while self.at("op", ","):
            self.take()
            a.append(self.expr())
        self.expect("op", ")")
        if not n_min <= len(a) <= n_max:
            raise BasicError("SYNTAX")
        return a

    def function(self, f: str):
        now = datetime.now()
        if f == "PI":
            return math.pi
        if f == "TIME$":
            return now.strftime("%H:%M:%S")
        if f == "DATE$":
            return now.strftime("%m-%d-%Y")
        if f == "TIMER":
            return float(now.hour * 3600 + now.minute * 60 + now.second) + now.microsecond / 1e6
        if f == "RND":
            x = self.num(self.args(1, 1)[0]) if self.at("op", "(") else 1.0
            return float(random.randint(1, int(x))) if x > 1 else random.random()
        a = self.args(1, 3)
        N = lambda i: self.num(a[i])
        def S(i):
            if not isinstance(a[i], str):
                raise BasicError("TYPE MISMATCH")
            return a[i]
        try:
            if f == "ABS": return abs(N(0))
            if f == "INT": return float(math.floor(N(0)))
            if f == "FIX": return float(math.trunc(N(0)))
            if f == "SGN": return float((N(0) > 0) - (N(0) < 0))
            if f == "SQR": return math.sqrt(N(0))
            if f == "SIN": return math.sin(N(0))
            if f == "COS": return math.cos(N(0))
            if f == "TAN": return math.tan(N(0))
            if f == "ATN": return math.atan(N(0))
            if f == "LOG": return math.log(N(0))
            if f == "EXP": return math.exp(N(0))
            if f == "LEN": return float(len(S(0)))
            if f == "VAL":
                m = re.match(r"\s*[-+]?\d*\.?\d*(E[-+]?\d+)?", S(0).upper())
                try:
                    return float(m.group(0))
                except ValueError:
                    return 0.0
            if f == "ASC": return float(ord(S(0)[0])) if S(0) else 0.0
            if f == "CHR$": return chr(int(N(0)) & 127)
            if f == "STR$": return fmt_num(N(0)).strip()
            if f == "LEFT$": return S(0)[:max(0, int(N(1)))]
            if f == "RIGHT$": return S(0)[-int(N(1)):] if int(N(1)) > 0 else ""
            if f == "MID$":
                st = max(1, int(N(1))) - 1
                return S(0)[st:st + int(N(2))] if len(a) > 2 else S(0)[st:]
            if f == "INSTR": return float(S(0).find(S(1)) + 1)
            if f == "UCASE$": return S(0).upper()
            if f == "LCASE$": return S(0).lower()
        except (ValueError, OverflowError):
            raise BasicError("ILLEGAL QUANTITY")
        except IndexError:
            raise BasicError("SYNTAX")
        raise BasicError("SYNTAX")


HELP_TEXT = [
    "TALON ENHANCED BASIC",
    "10 PRINT \"HI\"  stores a line",
    "RUN LIST NEW CONT FREE",
    "SAVE\"X\" LOAD\"X\" FILES KILL\"X\"",
    "RENUM  DELETE 10-50",
    "PRINT(?) LET INPUT IF THEN",
    "ELSE FOR TO STEP NEXT GOTO",
    "GOSUB RETURN ON DIM DATA",
    "READ RESTORE END STOP CLS",
    "BEEP SLEEP RANDOMIZE REM(')",
    "ABS INT SQR SIN COS RND LEN",
    "LEFT$ RIGHT$ MID$ STR$ VAL",
    "CHR$ ASC TIME$ DATE$ TAB SPC",
    "A full 15-letter line keeps",
    "going: type the rest next.",
    "LOCATE R,C  BOX R,C,H,W",
    "LINE R1,C1,R2,C2 (ROW 0-7,",
    "COLUMN 0-29). CHR$(5-31) ARE",
    "LINE GRAPHICS, SEE MANUAL.",
    "BYE leaves BASIC.",
    "\x02 break  \x03 repeat  Up/Dn scroll",
]
