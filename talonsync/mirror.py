"""Live backup of the PDA (TalonSync 1.15).

VRChat reports every avatar parameter change over OSC. The Talon Pilot keeps everything it remembers (typed lines,
task ticks, settings, the Hoot Pet, best scores) in saved avatar parameters, so TalonSync can keep a copy of them the
moment they change: no sync button, nothing to remember. VRChat gives no warning before you leave a world, and none is
needed: the copy is always current.

When your avatar loads (a new world, or switching back to it) TalonSync compares the PDA with the copy. If the PDA
comes up wiped (its typed lines gone while the copy has them), TalonSync offers to put everything back, or does it
by itself if you allow that in Settings. Restoring writes the saved parameters straight back over OSC, the same way
VRChat would have loaded them. Snapshots (the last few versions per avatar) live next to the database.

Nothing leaves your PC.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

# the saved PDA memory (see TalonPilotWizard.cs: the expression parameters saved with "saved = true")
EXACT = {"TP/Hour", "TP/Min", "TP/Theme", "TP/Bright", "TP/Sound", "TP/Foil", "TP/Sky/Lat", "TP/SB/Best",
         "TP/Scope/Mode"} | {f"TP/T{i}" for i in range(8)}
PREFIXES = ("TP/S/", "TP/Tx/", "TP/XL/", "TP/3D/", "TP/Hyp/")
PET = {"TP/Pet/Food", "TP/Pet/Joy", "TP/Pet/Energy", "TP/Pet/Age", "TP/Pet/Sleep"}
KEEP_SNAPSHOTS = 12
SNAPSHOT_EVERY = 10 * 60          # seconds between snapshots while things keep changing
RESTORE_RATE = 250                # OSC messages per second when writing a copy back


def is_saved(name: str) -> bool:
    return name in EXACT or name in PET or name.startswith(PREFIXES)


def text_cells(values: Dict[str, float]) -> int:
    """How many typed characters the PDA holds (the measure of 'is this PDA wiped?')."""
    return sum(1 for k, v in values.items() if k.startswith("TP/Tx/") and _num(v) > 0.5)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", s or "unknown")[:80]


class PdaMirror:
    def __init__(self, folder: str, settings, log: Callable[[str], None], link_fn: Callable[[], object],
                 busy_fn: Callable[[], bool], query_fn: Callable[[], Dict[str, object]]):
        self.folder = os.path.join(folder, "pda_backup")
        self.settings, self.log, self.link_fn, self.busy_fn, self.query_fn = settings, log, link_fn, busy_fn, query_fn
        self.lock = threading.Lock()
        self.avatar: Optional[str] = None
        self.values: Dict[str, float] = {}
        self.changed_at = 0.0
        self.saved_at = 0.0
        self.last_snapshot = 0.0
        self.offer: Optional[Dict] = None        # a wiped PDA was found: {"avatar", "cells_now", "cells_saved", "from"}
        self.restoring = False
        os.makedirs(self.folder, exist_ok=True)

    # ------------------------------------------------------------ files
    def _path(self, avatar: str) -> str:
        return os.path.join(self.folder, _safe(avatar) + ".json")

    def _snap_dir(self, avatar: str) -> str:
        return os.path.join(self.folder, _safe(avatar) + "_snapshots")

    def _load(self, avatar: str) -> Dict:
        try:
            with open(self._path(avatar), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _write_json(self, path: str, data: Dict):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=0)
        os.replace(tmp, path)

    def _save(self):
        if not self.avatar or not self.values:
            return
        data = {"avatar": self.avatar, "saved": datetime.now().isoformat(timespec="seconds"), "values": dict(self.values)}
        self._write_json(self._path(self.avatar), data)
        self.saved_at = time.time()

    def snapshot(self, why: str = "") -> Optional[str]:
        with self.lock:
            if not self.avatar or not self.values:
                return None
            d = self._snap_dir(self.avatar)
            os.makedirs(d, exist_ok=True)
            name = datetime.now().strftime("%Y-%m-%d %H%M%S") + (f" {re.sub(r'[^A-Za-z0-9 ]', '', why)[:30]}" if why else "") + ".json"
            self._write_json(os.path.join(d, name), {"avatar": self.avatar, "saved": datetime.now().isoformat(timespec="seconds"),
                                                     "why": why, "values": dict(self.values)})
            self.last_snapshot = time.time()
            snaps = sorted(f for f in os.listdir(d) if f.endswith(".json"))
            for old in snaps[:-KEEP_SNAPSHOTS]:
                try:
                    os.remove(os.path.join(d, old))
                except OSError:
                    pass
            return name

    def snapshots(self) -> List[Dict]:
        if not self.avatar:
            return []
        d = self._snap_dir(self.avatar)
        out = []
        for f in sorted(os.listdir(d), reverse=True) if os.path.isdir(d) else []:
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    v = json.load(fh).get("values", {})
                out.append({"name": f, "cells": text_cells(v), "count": len(v)})
            except (OSError, ValueError):
                pass
        return out

    # ------------------------------------------------------------ live: called for every OSC message
    def on_osc(self, addr: str, args):
        if not self.settings.get("live_backup", True) or self.restoring:
            return
        if addr == "/avatar/change":
            threading.Thread(target=self._avatar_loaded, args=(str(args[0]) if args else "",), daemon=True).start()
            return
        if not addr.startswith("/avatar/parameters/TP/") or not args:
            return
        name = addr[len("/avatar/parameters/"):]
        if not is_saved(name) or self.avatar is None:
            return
        v = args[0]                                       # kept as VRChat sent it (int, float or bool), so a restore matches
        if not isinstance(v, (bool, int, float)):
            return
        with self.lock:
            if self.values.get(name) != v:
                self.values[name] = v
                self.changed_at = time.time()

    def tick(self):
        """From TalonSync's housekeeping (every 2 s): write the copy a moment after things stop changing."""
        with self.lock:
            due = self.changed_at > self.saved_at and time.time() - self.changed_at > 1.5
        if due:
            with self.lock:
                self._save()
            if time.time() - self.last_snapshot > SNAPSHOT_EVERY:
                self.snapshot("auto")

    # ------------------------------------------------------------ avatar loaded: wiped?
    def _avatar_loaded(self, avatar: str):
        time.sleep(4.0)                                   # let VRChat load the avatar and its saved values
        fresh = {k: v for k, v in (self.query_fn() or {}).items() if is_saved(k) and isinstance(v, (bool, int, float))}
        saved = self._load(avatar).get("values", {})
        with self.lock:
            if self.avatar and self.values and self.avatar != avatar:
                self._save()                              # the avatar we were wearing keeps its copy
            self.avatar = avatar
            self.values = dict(saved)
            self.values.update(fresh)                     # what the PDA has now wins, except a wipe (below)
            self.changed_at = time.time() if fresh else 0.0
        if not saved or not fresh:
            if not saved and fresh:
                self.log("Live backup: started for this avatar.")
            return
        now_cells, saved_cells = text_cells(fresh), text_cells(saved)
        if now_cells == 0 and saved_cells >= 6:
            with self.lock:
                self.values = dict(saved)                 # don't let the wiped PDA overwrite the good copy
                self.changed_at = 0.0
            self.offer = {"avatar": avatar, "cells_now": now_cells, "cells_saved": saved_cells, "from": "live"}
            self.log(f"Live backup: the PDA came up wiped ({saved_cells} typed characters missing).")
            if self.settings.get("auto_restore", False):
                self.restore()
            else:
                self.log("Live backup: press Restore on the Backups page to put everything back.")

    # ------------------------------------------------------------ restore
    def restore(self, snapshot: str = "") -> str:
        if self.busy_fn():
            return "A TalonSync is running: try again when it finishes."
        link = self.link_fn()
        if link is None:
            return "Not connected to VRChat."
        with self.lock:
            if not self.avatar:
                return "No avatar yet: put on your Talon Pilot avatar first."
            if snapshot:
                try:
                    with open(os.path.join(self._snap_dir(self.avatar), os.path.basename(snapshot)), encoding="utf-8") as f:
                        values = json.load(f).get("values", {})
                except (OSError, ValueError) as e:
                    return f"Couldn't read that snapshot: {e}"
            else:
                values = dict(self.values) if self.values else self._load(self.avatar).get("values", {})
        if not values:
            return "There's no copy of this PDA yet."
        self.snapshot("before restore")
        self.restoring = True
        try:
            n = 0
            for name, v in sorted(values.items()):
                if not is_saved(name):
                    continue
                link.set(name, v)                         # the same type VRChat reported it as (int, float or bool)
                n += 1
                if n % RESTORE_RATE == 0:
                    time.sleep(1.0)
            with self.lock:
                self.values = dict(values)
                self._save()
            self.offer = None
            self.log(f"Live backup: restored {n} saved values to the PDA. Switch the PDA off and on once to refresh its screen.")
            return f"Restored {n} values. Switch the PDA off and on once so its screen catches up."
        finally:
            self.restoring = False

    def dismiss(self):
        self.offer = None

    def state(self) -> Dict:
        with self.lock:
            return {"enabled": bool(self.settings.get("live_backup", True)), "auto_restore": bool(self.settings.get("auto_restore", False)),
                    "avatar": self.avatar, "values": len(self.values), "cells": text_cells(self.values),
                    "saved": datetime.fromtimestamp(self.saved_at).isoformat(timespec="seconds") if self.saved_at else "",
                    "offer": self.offer}
