"""TalonOS Enhanced games (TalonSync 1.13): the Program Library's BASIC games rebuilt as windowed apps you can tap.
Same rules as the BASIC versions (library.py), so the BASIC listings still teach how each one works.

Inside a full window: rows 1-6, columns 1-28 (r0..r1, c0..c1)."""
from __future__ import annotations

import random
from typing import List

from .enhanced import App, S, UI, wrap


class Game(App):
    single = True
    score_key = ""

    def best(self, default=None):
        return self.os.scores.get(self.score_key, default)

    def record(self, value, better=lambda new, old: new > old):
        old = self.os.scores.get(self.score_key)
        if old is None or better(value, old):
            self.os.scores[self.score_key] = value
            self.os.save()
            return True
        return False

    def bump(self, key: str, by: int = 1):
        self.os.scores[key] = int(self.os.scores.get(key, 0)) + by
        self.os.save()

    @staticmethod
    def spinner(ui: UI, r, c0, value, setter, steps=(10, 1), width=6, lo=None, hi=None):
        """[-10][-1][ value ][+1][+10] in one row; typing a number into the box works too."""
        x = c0
        for s in steps:
            lab = f"-{s}"
            ui.button(r, x, x + len(lab) - 1, lab, lambda s=s: setter(value - s))
            x += len(lab) + 1
        def typed(t):
            try:
                setter(int(float(t.strip())))
            except ValueError:
                pass
        ui.field(r, x, x + width - 1, str(value), typed)
        x += width + 1
        for s in reversed(steps):
            lab = f"+{s}"
            ui.button(r, x, x + len(lab) - 1, lab, lambda s=s: setter(value + s))
            x += len(lab) + 1
        return x


# ---------------------------------------------------------------------------------------------------------- Guess
class Guess(Game):
    title = "Guess My Number"
    icon = "M"
    short = "Guess"
    score_key = "guess_best"

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.n, self.g, self.tries, self.msg, self.done = random.randint(1, 100), 50, 0, "Make a guess!", False

    def setg(self, v):
        self.g = max(1, min(100, int(v)))

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, "I'm thinking of a number")
        ui.label(r0 + 1, c0, "from 1 to 100.")
        self.spinner(ui, r0 + 2, c0 + 1, self.g, self.setg)
        ui.label(r0 + 3, c0, self.msg[:c1 - c0 + 1], S.FACE_BLUE)
        b = self.best()
        ui.label(r0 + 4, c0, f"Guesses {self.tries}" + (f"   Best {b}" if b else ""))
        if self.done:
            ui.button(r1, c0, c0 + 9, "New game", self.new)
        else:
            ui.button(r1, c0, c0 + 6, "Guess", self.guess)
            ui.button(r1, c0 + 8, c0 + 17, "New game", self.new)
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def guess(self):
        if self.done:
            return
        self.tries += 1
        if self.g < self.n:
            self.msg = f"{self.g}? Higher..."
        elif self.g > self.n:
            self.msg = f"{self.g}? Lower..."
        else:
            self.done = True
            best = self.record(self.tries, better=lambda a, b: a < b)
            self.msg = f"Yes, {self.n}! " + ("New best!" if best else ("Clever bird!" if self.tries < 8 else "Got it!"))
            self.beep()

    def typed(self, text):
        try:
            self.setg(int(text.strip()))
            self.guess()
        except ValueError:
            pass
        return True


# ---------------------------------------------------------------------------------------------------------- Rock Paper Talon
class RockPaperTalon(Game):
    title = "Rock Paper Talon"
    icon = "M"
    short = "RPT"
    score_key = "rpt_wins"
    NAMES = ["Rock", "Paper", "Talon"]

    def __init__(self, os_):
        super().__init__(os_)
        self.w = self.l = 0
        self.msg = "Pick one!"
        self.mine = -1
        self.yours = -1

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, "Rock blunts talon, talon")
        ui.label(r0 + 1, c0, "tears paper, paper wraps rock")
        for k, n in enumerate(self.NAMES):
            ui.button(r0 + 3, c0 + 1 + k * 9, c0 + 7 + k * 9, n, lambda k=k: self.play(k), pressed=k == self.yours)
        ui.label(r0 + 2, c0, f"You {self.w}   Me {self.l}", S.FACE_BLUE)
        ui.label(r0 + 4, c0, self.msg[:c1 - c0 + 1])
        ui.button(r1, c0, c0 + 7, "Reset", self.reset)
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def reset(self):
        self.w = self.l = 0
        self.msg, self.yours = "Pick one!", -1

    def play(self, h: int):
        c = random.randrange(3)
        self.yours, self.mine = h, c
        # in RPT order: rock(0) blunts talon(2), talon(2) tears paper(1), paper(1) wraps rock(0)
        wins = {(0, 2), (2, 1), (1, 0)}
        if h == c:
            self.msg = f"I pick {self.NAMES[c]}. A tie!"
        elif (h, c) in wins:
            self.w += 1
            self.bump(self.score_key)
            self.msg = f"I pick {self.NAMES[c]}. You win!"
            self.beep()
        else:
            self.l += 1
            self.msg = f"I pick {self.NAMES[c]}. I win!"

    def typed(self, text):
        t = text.strip().upper()[:1]
        if t and t in "RPT":
            self.play("RPT".index(t))
        return True


# ---------------------------------------------------------------------------------------------------------- Feather Pile
class FeatherPile(Game):
    title = "Feather Pile"
    icon = "M"
    short = "Pile"
    score_key = "pile_wins"

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.f, self.msg, self.over = 21, "Take 1 to 3. Last one loses!", False

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, f"Feathers left: {self.f}", S.FACE_BLUE)
        ui.sc.fill(r0 + 1, c0, r0 + 1, c1, S.FIELD)
        ui.label(r0 + 1, c0 + 1, "•" * self.f, S.FIELD)
        for k in (1, 2, 3):
            ui.button(r0 + 3, c0 + 1 + (k - 1) * 9, c0 + 7 + (k - 1) * 9, f"Take {k}", lambda k=k: self.take(k),
                      enabled=not self.over and k <= self.f)
        for k, line in enumerate(wrap(self.msg, c1 - c0 + 1)[:2]):
            ui.label(r0 + 4 + k, c0, line)
        ui.button(r1, c0, c0 + 9, "New game", self.new)
        ui.label(r1, c0 + 12, f"Wins {self.os.scores.get(self.score_key, 0)}")
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def take(self, x: int):
        if self.over or x < 1 or x > 3 or x > self.f:
            return
        self.f -= x
        if self.f == 0:
            self.msg, self.over = "You took the last one. I win!", True
            return
        c = (self.f - 1) % 4
        if c == 0 or random.random() < 0.3:
            c = random.randint(1, 3)
        c = min(c, self.f)
        self.f -= c
        if self.f == 0:
            self.msg, self.over = f"I take {c} - the last one. You win! So clever!", True
            self.bump(self.score_key)
            self.beep()
        else:
            self.msg = f"You took {x}. I take {c}."

    def typed(self, text):
        try:
            self.take(int(text.strip()))
        except ValueError:
            pass
        return True


# ---------------------------------------------------------------------------------------------------------- Moon Lander
class MoonLander(Game):
    title = "Moon Lander"
    icon = "M"
    short = "Land"
    score_key = "lander_best"

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.h, self.v, self.fuel, self.burn, self.over = 500.0, 50.0, 150, 10, False
        self.msg = "Land under 5 m/s. Burn 0-30."

    def setb(self, v):
        self.burn = max(0, min(30, int(v), self.fuel))

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, "Height")
        ui.progress(r0, c0 + 7, c1 - 5, self.h / 500.0)
        ui.label(r0, c1 - 3, f"{max(0, int(self.h)):>4}"[-4:])
        ui.label(r0 + 1, c0, "Fuel")
        ui.progress(r0 + 1, c0 + 7, c1 - 5, self.fuel / 150.0)
        ui.label(r0 + 1, c1 - 3, f"{self.fuel:>4}")
        ui.label(r0 + 2, c0, f"Falling at {self.v:.0f} m/s", S.FACE_BLUE)
        ui.label(r0 + 3, c0, "Burn")
        self.spinner(ui, r0 + 3, c0 + 5, self.burn, self.setb, steps=(5, 1), width=4)
        ui.label(r0 + 4, c0, self.msg[:c1 - c0 + 1])
        if self.over:
            ui.button(r1, c0, c0 + 9, "New game", self.new)
        else:
            ui.button(r1, c0, c0 + 6, "Burn", self.step)
            ui.button(r1, c0 + 8, c0 + 17, "New game", self.new)
        b = self.best()
        if b is not None:
            ui.label(r1, c0 + 19, f"Best {b}"[:c1 - c0 - 18])

    def step(self):
        if self.over:
            return
        b = max(0, min(30, self.burn, self.fuel))
        self.fuel -= b
        self.v = self.v + 5 - b / 2
        self.h -= self.v
        self.setb(self.burn)
        if self.h > 0:
            self.msg = f"Burned {b}."
            return
        self.over = True
        v = round(self.v, 1)
        if v < 5:
            self.msg = f"Perfect landing at {v} m/s!"
            self.record(v, better=lambda a, b2: a < b2)
            self.beep()
        elif v < 15:
            self.msg = f"Bumpy, {v} m/s. You made it."
        else:
            self.msg = f"Crash at {v}! A {int(v * 3)} m crater."

    def typed(self, text):
        try:
            self.setb(int(text.strip()))
            self.step()
        except ValueError:
            pass
        return True


# ---------------------------------------------------------------------------------------------------------- Tic-Tac-Talon
LINES3 = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


class TicTacTalon(Game):
    title = "Tic-Tac-Talon"
    icon = "M"
    short = "TTT"
    score_key = "ttt"

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.b = [0] * 9
        self.msg, self.over = "You are X. Tap a square.", False

    @staticmethod
    def wins(b, k):
        return any(b[x] == k and b[y] == k and b[z] == k for x, y, z in LINES3)

    def draw(self, ui: UI, r0, c0, r1, c1):
        for j in range(3):
            for i in range(3):
                q = self.b[j * 3 + i]
                ui.button(r0 + j, c0 + 1 + i * 4, c0 + 3 + i * 4, " XO"[q], lambda p=j * 3 + i: self.move(p),
                          pressed=q != 0)
        rec = self.os.scores.get(self.score_key, [0, 0, 0])
        ui.label(r0, c0 + 14, "You X  Me O", S.FACE_BLUE)
        ui.label(r0 + 1, c0 + 14, f"Won {rec[0]} Lost {rec[1]}")
        ui.label(r0 + 2, c0 + 14, f"Drawn {rec[2]}")
        for k, line in enumerate(wrap(self.msg, c1 - c0 + 1)[:2]):
            ui.label(r0 + 3 + k, c0, line)
        ui.button(r1, c0, c0 + 9, "New game", self.new)
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def _rec(self, i):
        rec = list(self.os.scores.get(self.score_key, [0, 0, 0]))
        rec[i] += 1
        self.os.scores[self.score_key] = rec
        self.os.save()

    def move(self, p: int):
        if self.over or self.b[p]:
            return
        self.b[p] = 1
        if self.wins(self.b, 1):
            self.msg, self.over = "You win! Clever bird!", True
            self._rec(0)
            self.beep()
            return
        if all(self.b):
            self.msg, self.over = "A draw.", True
            self._rec(2)
            return
        c = None
        for k in (2, 1):                       # win if I can, else block you (the BASIC version's order)
            for z in range(9):
                if c is None and self.b[z] == 0:
                    self.b[z] = k
                    if self.wins(self.b, k):
                        c = z
                    self.b[z] = 0
        if c is None and self.b[4] == 0:
            c = 4
        if c is None:
            c = random.choice([z for z in range(9) if self.b[z] == 0])
        self.b[c] = 2
        if self.wins(self.b, 2):
            self.msg, self.over = "I win this one!", True
            self._rec(1)
        elif all(self.b):
            self.msg, self.over = "A draw.", True
            self._rec(2)
        else:
            self.msg = "Your move."

    def typed(self, text):
        t = text.strip()
        if t.isdigit() and 1 <= int(t) <= 9:
            self.move(int(t) - 1)
        return True


# ---------------------------------------------------------------------------------------------------------- Featherword
WORDS = ["OWL", "GRYPHON", "FEATHER", "TALON", "NEST", "MOONLIGHT", "PINECONE", "WHISKER", "MEADOW", "LANTERN",
         "COMPUTER", "KEYBOARD", "PIXEL", "SPARROW", "THUNDER", "ORCHARD", "SNOWFALL", "PLANET", "MARBLE", "HARBOR"]


class Featherword(Game):
    title = "Featherword"
    icon = "M"
    short = "Word"
    score_key = "word_wins"

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.word, self.tried, self.miss, self.over = random.choice(WORDS), "", 0, False
        self.msg = "Pick a letter"

    def draw(self, ui: UI, r0, c0, r1, c1):
        shown = " ".join(ch if ch in self.tried or self.over else "_" for ch in self.word)
        ui.sc.fill(r0, c0, r0, c1, S.FIELD)
        ui.center(r0, c0, c1, shown, S.FIELD)
        ui.label(r0 + 1, c0, "Feathers ")
        ui.label(r0 + 1, c0 + 9, "•" * (6 - self.miss) + "  " + self.msg[:c1 - c0 - 16])
        for k, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            r = r0 + 2 + k // 13
            x = c0 + 1 + (k % 13) * 2
            ui.button(r, x, x, ch, lambda ch=ch: self.guess(ch), enabled=not self.over and ch not in self.tried)
        ui.label(r0 + 4, c0, f"Words found {self.os.scores.get(self.score_key, 0)}")
        ui.button(r1, c0, c0 + 9, "New word", self.new)
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def guess(self, ch: str):
        if self.over or ch in self.tried or not ("A" <= ch <= "Z"):
            return
        self.tried += ch
        if ch not in self.word:
            self.miss += 1
            self.msg = f"No {ch}!"
            if self.miss >= 6:
                self.msg, self.over = f"It was {self.word}", True
            return
        if all(c in self.tried for c in self.word):
            self.msg, self.over = "You got it!", True
            self.bump(self.score_key)
            self.beep()
        else:
            self.msg = f"Yes, {ch}!"

    def typed(self, text):
        for ch in text.strip().upper():
            self.guess(ch)
        return True


# ---------------------------------------------------------------------------------------------------------- Aerie Keeper
class AerieKeeper(Game):
    title = "Aerie Keeper"
    icon = "M"
    short = "Aerie"
    score_key = "aerie_best"

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.y, self.n, self.m, self.a, self.t = 1, 10, 300, 100, 0
        self.price = random.randint(16, 25)
        self.buy, self.feed = 0, 200
        self.report: List[str] = ["Keep your owls fed for 10", "years. Each owl eats 20 mice", "and hunts 15 acres."]
        self.over = False

    def setbuy(self, v):
        v = int(v)
        hi = self.m // self.price
        self.buy = max(-self.a, min(hi, v))
        self.feed = min(self.feed, self.m - self.buy * self.price)

    def setfeed(self, v):
        self.feed = max(0, min(int(v), self.m - self.buy * self.price))

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, f"Year {self.y}  Owls {self.n}  Mice {self.m}"[:c1 - c0 + 1], S.FACE_BLUE)
        if self.over:
            for k, line in enumerate(self.report[:4]):
                ui.label(r0 + 1 + k, c0, line[:c1 - c0 + 1])
            ui.button(r1, c0, c0 + 9, "New rule", self.new)
            b = self.best()
            if b is not None:
                ui.label(r1, c0 + 12, f"Best {b} owls")
            return
        ui.label(r0 + 1, c0, f"Meadow {self.a}, {self.price} mice/acre"[:c1 - c0 + 1])
        ui.label(r0 + 2, c0, "Buy")
        self.spinner(ui, r0 + 2, c0 + 5, self.buy, self.setbuy, steps=(10, 1), width=4)
        ui.label(r0 + 3, c0, "Feed")
        self.spinner(ui, r0 + 3, c0 + 5, self.feed, self.setfeed, steps=(100, 20), width=4)
        ui.label(r0 + 4, c0, (self.report[0] if self.report else "")[:c1 - c0 + 1])
        ui.button(r1, c0, c0 + 9, "End year", self.end_year)
        ui.button(r1, c0 + 11, c0 + 16, "Info", self.info)
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def info(self):
        self.os.launch("msg", title="Last year", text=" ".join(self.report) or "Nothing yet.")

    def end_year(self):
        self.setbuy(self.buy)
        self.setfeed(self.feed)
        self.m -= self.buy * self.price
        self.a += self.buy
        self.m -= self.feed
        fed = min(self.feed // 20, self.n)
        hungry = self.n - fed
        h = random.randint(2, 6)
        caught = min(self.a, self.n * 15) * h
        stolen = int(self.m * random.randint(2, 5) / 10) if random.randint(1, 6) == 1 else 0
        self.m = self.m - stolen + caught
        hatched = int(self.n * random.randint(1, 3) / 10) if hungry == 0 else 0
        rep = [f"Year {self.y}: caught {caught} mice."]
        if stolen:
            rep.append(f"Weasels stole {stolen} mice!")
        if hungry:
            rep.append(f"{hungry} owls flew off hungry.")
        if hatched:
            rep.append(f"{hatched} owlets hatched!")
        self.n = self.n - hungry + hatched
        self.t += hungry
        self.y += 1
        self.buy, self.price = 0, random.randint(16, 25)
        self.feed = min(self.n * 20, self.m)
        if self.n < 1 or self.y > 10:
            self.over = True
            end = "Your aerie is empty..." if self.n < 1 else (
                "A legendary keeper!" if self.n >= 15 and self.t < 3 else
                "A wise and steady rule." if self.n >= 10 else "The owls expected more.")
            rep = rep[:1] + [f"Owls {self.n}  Meadow {self.a}", f"Lost to hunger: {self.t}", end]
            if self.n >= 1:
                self.record(self.n)
            if self.n >= 15 and self.t < 3:
                self.beep()
            self.y = min(self.y, 10)
        self.report = rep


# ---------------------------------------------------------------------------------------------------------- Talon Dice
class TalonDice(Game):
    title = "Talon Dice"
    icon = "M"
    short = "Dice"
    score_key = "dice_wins"

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.you, self.me, self.turn, self.last, self.over = 0, 0, 0, 0, False
        self.msg = "First to 50. A 1 loses the turn!"

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, f"You {self.you}   Me {self.me}", S.FACE_BLUE)
        ui.label(r0 + 1, c0, "Rolled")
        ui.sc.fill(r0 + 1, c0 + 7, r0 + 1, c0 + 9, S.FIELD)
        ui.label(r0 + 1, c0 + 8, str(self.last) if self.last else "-", S.FIELD)
        ui.label(r0 + 1, c0 + 12, f"This turn {self.turn}")
        for k, line in enumerate(wrap(self.msg, c1 - c0 + 1)[:3]):
            ui.label(r0 + 2 + k, c0, line)
        if self.over:
            ui.button(r1, c0, c0 + 9, "New game", self.new)
        else:
            ui.button(r1, c0, c0 + 5, "Roll", self.roll)
            ui.button(r1, c0 + 7, c0 + 12, "Hold", self.hold)
        ui.label(r1, c0 + 15, f"Wins {self.os.scores.get(self.score_key, 0)}")

    def roll(self):
        if self.over:
            return
        r = random.randint(1, 6)
        self.last = r
        if r == 1:
            self.turn = 0
            self.msg = "Rolled a 1 - turn lost! " + self.my_turn()
            return
        self.turn += r
        if self.you + self.turn >= 50:
            self.hold()
            return
        self.msg = f"Rolled {r}. Roll again or hold?"

    def hold(self):
        if self.over:
            return
        self.you += self.turn
        self.turn = 0
        if self.you >= 50:
            self.over = True
            self.msg = "You win! Clever bird!"
            self.bump(self.score_key)
            self.beep()
            return
        self.msg = self.my_turn()

    def my_turn(self) -> str:
        t, rolls = 0, []
        while True:
            r = random.randint(1, 6)
            rolls.append(str(r))
            if r == 1:
                return f"I roll {', '.join(rolls)} and lose my turn."
            t += r
            if not (t < 15 and self.me + t < 50):
                break
        self.me += t
        if self.me >= 50:
            self.over = True
            return f"I roll {', '.join(rolls)}: {self.me}. I win!"
        return f"I roll {', '.join(rolls)} and hold at {t}."

    def typed(self, text):
        t = text.strip().upper()[:1]
        if t == "R":
            self.roll()
        elif t == "H":
            self.hold()
        return True


# ---------------------------------------------------------------------------------------------------------- Find the Mouse
class FindTheMouse(Game):
    title = "Find the Mouse"
    icon = "M"
    short = "Mouse"
    score_key = "mouse_best"
    W, H, SWOOPS = 9, 5, 5

    def __init__(self, os_):
        super().__init__(os_)
        self.new()

    def new(self):
        self.x, self.y = random.randrange(self.W), random.randrange(self.H)
        self.hints = {}
        self.left, self.over = self.SWOOPS, False
        self.msg = f"Tap a square! {self.SWOOPS} left"

    def draw(self, ui: UI, r0, c0, r1, c1):
        for j in range(self.H):
            for i in range(self.W):
                h = self.hints.get((i, j))
                found = self.over and (i, j) == (self.x, self.y)
                ui.button(r0 + j, c0 + i * 3, c0 + i * 3 + 1, "@" if found else (h or ""),
                          lambda i=i, j=j: self.swoop(i, j), pressed=bool(h) or found)
        ui.label(r1, c0, self.msg[:20])
        ui.button(r1, c1 - 5, c1, "New", self.new)

    def swoop(self, i, j):
        if self.over or (i, j) in self.hints:
            return
        if (i, j) == (self.x, self.y):
            n = self.SWOOPS - self.left + 1
            self.over = True
            self.msg = f"Got it on swoop {n}!"
            self.record(n, better=lambda a, b: a < b)
            self.beep()
            return
        d = ("N" if self.y < j else "S" if self.y > j else "") + ("W" if self.x < i else "E" if self.x > i else "")
        self.hints[(i, j)] = d
        self.left -= 1
        if self.left == 0:
            self.over = True
            self.msg = "It escaped!"
        else:
            self.msg = f"To the {d}. {self.left} left"


# ---------------------------------------------------------------------------------------------------------- Ponder
PONDER_KEYS = [("SAD", "Why do you feel sad?"), ("HAPPY", "Hoo! What made you happy?"), ("TIRED", "Even owls need a nap."),
               ("VRCHAT", "Which world are you in?"), ("WORLD", "Building worlds is an art."),
               ("MOM", "Tell me about your family."), ("FRIEND", "Good friends are treasure."),
               ("LOVE", "Love is a fine thing."), ("HATE", "That is a strong feeling."),
               ("BORED", "Write a program in BASIC!"), ("COMPUTER", "Do computers worry you?"),
               ("OWL", "Owls are very wise. Hoo."), ("GRYPHON", "A gryphon! How noble."),
               ("HELLO", "Hello there! How are you?"), ("HI", "Hello there! How are you?"), ("WHY", "Why do you ask?"),
               ("BECAUSE", "Is that the real reason?"), ("YES", "You seem quite sure."), ("NO", "Why not?"),
               ("DREAM", "What do you dream of?")]
PONDER_ANY = ["Tell me more.", "Hoo... go on.", "How does that feel?", "Very interesting.", "And what do you think?",
              "I see. Ponder ponders."]


class Ponder(Game):
    title = "Ponder the Owl"
    icon = "P"
    short = "Owl"

    def __init__(self, os_):
        super().__init__(os_)
        self.log = ["Ponder: Hoo. I am Ponder. Tell me what's on your mind."]
        self.text = ""

    @staticmethod
    def reply(said: str) -> str:
        a = " " + said.upper() + " "
        for k, r in PONDER_KEYS:
            if " " + k in a:
                return r
        return random.choice(PONDER_ANY)

    def draw(self, ui: UI, r0, c0, r1, c1):
        w = c1 - c0 + 1
        lines: List[str] = []
        for entry in self.log:
            lines += wrap(entry, w)
        ui.icon(r0, c1 - 1, "o", S.MINI_OWL)
        for k, line in enumerate(lines[-(r1 - r0):]):
            ui.label(r0 + k, c0, line[:w - (3 if k == 0 else 0)])
        ui.field(r1, c0, c1 - 6, self.text, self.say, placeholder="type and press Done")
        ui.button(r1, c1 - 4, c1, "Bye", self.back)

    def say(self, text: str):
        text = text.strip()
        if not text:
            return
        if "BYE" in text.upper():
            self.log.append("Ponder: Hoo hoo. Fly safe!")
            self.os.close(self)
            return
        self.log.append("You: " + text)
        self.log.append("Ponder: " + self.reply(text))
        self.log = self.log[-12:]

    def typed(self, text):
        self.say(text)
        return True


# ---------------------------------------------------------------------------------------------------------- Math Drill
class MathDrill(Game):
    title = "Math Drill"
    icon = "E"
    short = "Math"
    score_key = "math_best"

    def __init__(self, os_):
        super().__init__(os_)
        self.level = 1
        self.new()

    def new(self):
        self.q, self.right, self.answer, self.over = 0, 0, "", False
        self.msg = "Ten quick sums. Go!"
        self.next_q()

    def next_q(self):
        L = self.level
        a, b, k = random.randint(1, 10 * L * L), random.randint(1, 10 * L * L), random.randint(1, 3)
        if k == 3:
            a, b = random.randint(1, 5 * L + 4), random.randint(1, 9)
        self.a, self.b, self.op = a, b, "+-x"[k - 1]
        self.c = a + b if k == 1 else a - b if k == 2 else a * b
        self.q += 1
        self.answer = ""

    def setlevel(self, L):
        self.level = L
        self.new()

    def draw(self, ui: UI, r0, c0, r1, c1):
        ui.label(r0, c0, "Level")
        for L in (1, 2, 3):
            ui.radio(r0, c0 + 6 + (L - 1) * 6, str(L), self.level == L, lambda L=L: self.setlevel(L))
        if self.over:
            ui.label(r0 + 1, c0, f"You got {self.right} out of 10.", S.FACE_BLUE)
            ui.label(r0 + 2, c0, self.msg[:c1 - c0 + 1])
        else:
            ui.label(r0 + 1, c0, f"Q{self.q}: {self.a} {self.op} {self.b} =", S.FACE_BLUE)
            ui.field(r0 + 1, c0 + 18, c1, self.answer, self.set_answer)
            ui.label(r0 + 2, c0, self.msg[:c1 - c0 + 1])
            for k, key in enumerate("1234567890-<"):
                ui.button(r0 + 3 + k // 6, c0 + (k % 6) * 3, c0 + (k % 6) * 3 + 1, key, lambda key=key: self.key_in(key))
            ui.label(r0 + 3, c0 + 19, f"Right {self.right}")
        b = self.best()
        ui.label(r0 + 4, c0 + 19, f"Best {b}" if b is not None else "")
        if self.over:
            ui.button(r1, c0, c0 + 9, "Again", self.new)
        else:
            ui.button(r1, c0, c0 + 5, "OK", self.check)
        ui.button(r1, c1 - 6, c1, "Close", self.back)

    def key_in(self, key):
        if key == "<":
            self.answer = self.answer[:-1]
        elif key == "-":
            self.answer = "" if self.answer.startswith("-") else "-" + self.answer
        elif len(self.answer) < 6:
            self.answer += key

    def set_answer(self, text):
        t = text.strip()
        if t:
            self.answer = t[:6]
            self.check()

    def check(self):
        if self.over or not self.answer:
            return
        try:
            ok = int(self.answer) == self.c
        except ValueError:
            ok = False
        if ok:
            self.right += 1
            self.msg = "Right!"
        else:
            self.msg = f"No, it's {self.c}."
        if self.q >= 10:
            self.over = True
            self.record(self.right)
            self.msg = "Perfect! So smart!" if self.right == 10 else "Well done!" if self.right >= 7 else "Keep practising!"
            if self.right == 10:
                self.beep()
            return
        self.next_q()

    def typed(self, text):
        self.set_answer(text)
        return True


GAMES = {
    "guess": {"cls": Guess, "name": "Guess My Number", "words": ["GUESS"], "blurb": "Find my number, 1 to 100."},
    "rpt": {"cls": RockPaperTalon, "name": "Rock Paper Talon", "words": ["RPT", "ROCK"], "blurb": "Rock, paper or talon?"},
    "pile": {"cls": FeatherPile, "name": "Feather Pile", "words": ["PILE", "FEATHERS"], "blurb": "Don't take the last feather!"},
    "lander": {"cls": MoonLander, "name": "Moon Lander", "words": ["LANDER", "MOON"], "blurb": "Touch down under 5 m/s."},
    "tictac": {"cls": TicTacTalon, "name": "Tic-Tac-Talon", "words": ["TICTAC", "TTT"], "blurb": "Three in a row beats me."},
    "word": {"cls": Featherword, "name": "Featherword", "words": ["WORD", "HANGMAN"], "blurb": "Find the word, 6 misses."},
    "aerie": {"cls": AerieKeeper, "name": "Aerie Keeper", "words": ["AERIE"], "blurb": "Rule the owls for 10 years."},
    "dice": {"cls": TalonDice, "name": "Talon Dice", "words": ["DICE"], "blurb": "Race me to 50. Beware the 1!"},
    "mouse": {"cls": FindTheMouse, "name": "Find the Mouse", "words": ["MOUSE"], "blurb": "Swoop on the mouse in 5."},
    "ponder": {"cls": Ponder, "name": "Ponder the Owl", "words": ["PONDER", "OWL"], "blurb": "A wise owl who listens."},
    "math": {"cls": MathDrill, "name": "Math Drill", "words": ["MATH"], "blurb": "Ten sums, three levels."},
}
