"""TalonFS (TalonSync 1.14): the file system of TalonOS Enhanced.

Paths look like C:\\Documents\\OWLS.TXT. Everything lives in a sandbox inside TalonSync's data folder; no path can
reach anything outside it (no "..", no drive letters other than ours, no links). Names are matched without caring
about upper/lower case, like the classic systems.

  C:\\                 TalonOS/C                    the system drive
  C:\\Documents        <data>/Documents             your notes (Notepad)
  C:\\Programs         <data>/Programs              BASIC programs (SAVE / LOAD use the same folder)
  C:\\Apps             TalonOS/C/Apps               installed apps: .BAS windowed apps and .PY plugins
  C:\\Recycled         <data>/Recycled              the Recycle Bin (remembers where each file came from)
  C:\\Temp             TalonOS/C/Temp               scratch space, emptied at start-up
  A:\\                 (read only)                  the built-in BASIC programs, like a ROM disk

Limits: names up to 32 letters, numbers, spaces, dots, dashes and underscores; files up to 1 MB; the C: drive up to
64 MB; up to 1,000 entries in one folder.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from typing import Dict, List, Optional, Tuple

MAX_FILE = 1024 * 1024
MAX_DRIVE = 64 * 1024 * 1024
MAX_ENTRIES = 1000
NAME_RX = re.compile(r"^[A-Za-z0-9 _.()\-]{1,32}$")

# extension -> (description, icon, app that opens it)
FILE_TYPES: Dict[str, Tuple[str, str, str]] = {
    ".TXT": ("Text document", "D", "notepad"),
    ".BAS": ("BASIC program", "I", "basicapp"),
    ".PY": ("Python plugin", "K", "plugin"),
    ".LOG": ("Log file", "D", "notepad"),
    ".INI": ("Settings file", "G", "notepad"),
}


class FSError(Exception):
    """A file system problem, worded for the person using TalonOS."""


class Entry:
    __slots__ = ("name", "is_dir", "size", "mtime", "path")

    def __init__(self, name, is_dir, size, mtime, path):
        self.name, self.is_dir, self.size, self.mtime, self.path = name, is_dir, size, mtime, path

    @property
    def ext(self) -> str:
        return os.path.splitext(self.name)[1].upper() if not self.is_dir else ""

    @property
    def kind(self) -> str:
        if self.is_dir:
            return "Folder"
        return FILE_TYPES.get(self.ext, ("File", "D", ""))[0]

    def __repr__(self):
        return f"Entry({self.path!r})"


def vbasename(vpath: str) -> str:
    """The last part of a TalonFS path (C:\\Documents\\A.TXT -> A.TXT), on any PC (\\ isn't a separator on Linux)."""
    return vpath.replace("/", "\\").rstrip("\\").split("\\")[-1]


def vdirname(vpath: str) -> str:
    """The folder of a TalonFS path (C:\\Documents\\A.TXT -> C:\\Documents)."""
    p = vpath.replace("/", "\\").rstrip("\\")
    head = p.rsplit("\\", 1)[0] if "\\" in p else p
    return head + "\\" if head.endswith(":") else head


def human_size(n: int) -> str:
    if n < 1000:
        return f"{n}B"
    if n < 1000 * 1024:
        return f"{n / 1024:.1f}K" if n < 10 * 1024 else f"{n // 1024}K"
    return f"{n / 1024 / 1024:.1f}M"


class TalonFS:
    def __init__(self, data_dir: str, programs_dir: Optional[str] = None, rom: Optional[Dict[str, str]] = None):
        self.data_dir = os.path.abspath(data_dir)
        base = os.path.join(self.data_dir, "TalonOS", "C")
        self.mounts: Dict[str, str] = {                     # C: folder (upper case) -> real folder
            "": base,
            "DOCUMENTS": os.path.join(self.data_dir, "Documents"),
            "PROGRAMS": os.path.abspath(programs_dir) if programs_dir else os.path.join(self.data_dir, "Programs"),
            "APPS": os.path.join(base, "Apps"),
            "RECYCLED": os.path.join(self.data_dir, "Recycled"),
            "TEMP": os.path.join(base, "Temp"),
        }
        self.mount_names = {"DOCUMENTS": "Documents", "PROGRAMS": "Programs", "APPS": "Apps", "RECYCLED": "Recycled",
                            "TEMP": "Temp"}
        self.rom = rom or {}                                # A: file name -> text
        self.listeners: List = []
        for p in self.mounts.values():
            try:
                os.makedirs(p, exist_ok=True)
            except OSError:
                pass
        try:                                                 # Temp starts empty
            for f in os.listdir(self.mounts["TEMP"]):
                q = os.path.join(self.mounts["TEMP"], f)
                shutil.rmtree(q) if os.path.isdir(q) and not os.path.islink(q) else os.remove(q)
        except OSError:
            pass

    # ------------------------------------------------------------------ paths
    @staticmethod
    def split(vpath: str, cwd: str = "C:\\Documents") -> Tuple[str, List[str]]:
        """'docs\\a.txt' (relative to cwd), 'C:/Documents/A.TXT' or 'A:\\GUESS.BAS' -> ('C', ['Documents', 'A.TXT'])."""
        p = (vpath or "").strip().replace("/", "\\")
        m = re.match(r"^([A-Za-z]):\\?(.*)$", p)
        if m:
            drive, rest = m.group(1).upper(), m.group(2)
        else:
            d, parts = TalonFS.split(cwd, "C:\\")
            drive, rest = d, "\\".join(parts + ([p] if p else []))
        parts: List[str] = []
        for part in rest.split("\\"):
            part = part.strip()
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            if not NAME_RX.match(part) or part.strip(".") == "":
                raise FSError(f"'{part[:20]}' isn't a good name: use letters, numbers, spaces, - _ ( ) and dots")
            parts.append(part)
        if drive not in ("C", "A"):
            raise FSError(f"There's no {drive}: drive. Try C:\\")
        return drive, parts

    @staticmethod
    def join(drive: str, parts: List[str]) -> str:
        return f"{drive}:\\" + "\\".join(parts)

    def normalize(self, vpath: str, cwd: str = "C:\\Documents") -> str:
        drive, parts = self.split(vpath, cwd)
        return self.join(drive, self._display_parts(drive, parts))

    def _display_parts(self, drive: str, parts: List[str]) -> List[str]:
        """Use the stored spelling of names that exist."""
        if drive != "C" or not parts:
            return [p.upper() for p in parts] if drive == "A" else parts
        out = []
        top = parts[0].upper()
        if top in self.mount_names:
            out.append(self.mount_names[top])
            real = self.mounts[top]
        else:
            real = self.mounts[""]
            found = self._match(real, parts[0])
            out.append(found or parts[0])
            real = os.path.join(real, found or parts[0])
        for part in parts[1:]:
            found = self._match(real, part) if os.path.isdir(real) else None
            out.append(found or part)
            real = os.path.join(real, found or part)
        return out

    @staticmethod
    def _match(folder: str, name: str) -> Optional[str]:
        try:
            for f in os.listdir(folder):
                if f.lower() == name.lower():
                    return f
        except OSError:
            pass
        return None

    def real(self, vpath: str, cwd: str = "C:\\Documents", must_exist=False) -> str:
        """The real path for a C: path, after checking it can't leave the sandbox."""
        drive, parts = self.split(vpath, cwd)
        if drive != "C":
            raise FSError("A: is read only")
        if parts and parts[0].upper() in self.mount_names:
            root = self.mounts[parts[0].upper()]
            rest = parts[1:]
        else:
            root, rest = self.mounts[""], parts
        path = root
        for part in rest:
            found = self._match(path, part) if os.path.isdir(path) else None
            path = os.path.join(path, found or part)
            if os.path.islink(path):
                raise FSError("Links aren't allowed in TalonOS")
        root_real = os.path.realpath(root)
        if os.path.commonpath([root_real, os.path.realpath(path)]) != root_real:
            raise FSError("That path leaves TalonOS")
        if must_exist and not os.path.exists(path):
            raise FSError(f"{self.join(drive, parts)} doesn't exist")
        return path

    def is_mount_root(self, vpath: str) -> bool:
        drive, parts = self.split(vpath)
        return drive == "C" and (not parts or (len(parts) == 1 and parts[0].upper() in self.mount_names))

    # ------------------------------------------------------------------ reading
    def exists(self, vpath: str, cwd="C:\\Documents") -> bool:
        try:
            drive, parts = self.split(vpath, cwd)
            if drive == "A":
                return not parts or (len(parts) == 1 and parts[0].upper() in self.rom)
            return os.path.exists(self.real(vpath, cwd))
        except FSError:
            return False

    def isdir(self, vpath: str, cwd="C:\\Documents") -> bool:
        try:
            drive, parts = self.split(vpath, cwd)
            if drive == "A":
                return not parts
            return os.path.isdir(self.real(vpath, cwd))
        except FSError:
            return False

    def listdir(self, vpath: str = "C:\\", cwd="C:\\Documents") -> List[Entry]:
        drive, parts = self.split(vpath, cwd)
        base = self.join(drive, self._display_parts(drive, parts))
        sep = "" if base.endswith("\\") else "\\"
        if drive == "A":
            if parts:
                raise FSError("A: has no folders")
            return [Entry(n, False, len(t.encode()), 0, f"A:\\{n}") for n, t in sorted(self.rom.items())]
        real = self.real(vpath, cwd, must_exist=True)
        if not os.path.isdir(real):
            raise FSError(f"{base} is a file, not a folder")
        out: List[Entry] = []
        seen = set()
        if not parts:                                        # C:\ shows the standard folders first
            for key, name in self.mount_names.items():
                out.append(Entry(name, True, 0, 0, f"C:\\{name}"))
                seen.add(name.upper())
        try:
            names = os.listdir(real)
        except OSError as e:
            raise FSError(str(e))
        for f in sorted(names, key=str.lower):
            if f.upper() in seen or f.startswith(".") or f.startswith("_") or f.endswith(".tmp"):
                continue
            q = os.path.join(real, f)
            if os.path.islink(q) or not NAME_RX.match(f):
                continue
            try:
                st = os.stat(q)
            except OSError:
                continue
            out.append(Entry(f, os.path.isdir(q), 0 if os.path.isdir(q) else st.st_size, st.st_mtime, base + sep + f))
        return sorted(out, key=lambda e: (not e.is_dir, e.name.lower()))

    def read_text(self, vpath: str, cwd="C:\\Documents") -> str:
        drive, parts = self.split(vpath, cwd)
        if drive == "A":
            if len(parts) == 1 and parts[0].upper() in self.rom:
                return self.rom[parts[0].upper()]
            raise FSError(f"{self.join(drive, parts)} doesn't exist")
        path = self.real(vpath, cwd, must_exist=True)
        if os.path.isdir(path):
            raise FSError("That's a folder")
        if os.path.getsize(path) > MAX_FILE:
            raise FSError("That file is too big (over 1 MB)")
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().replace("\r\n", "\n")

    def stat(self, vpath: str, cwd="C:\\Documents") -> Entry:
        drive, parts = self.split(vpath, cwd)
        disp = self.join(drive, self._display_parts(drive, parts))
        if drive == "A":
            if not parts:
                return Entry("A:", True, 0, 0, "A:\\")
            t = self.rom.get(parts[0].upper())
            if t is None:
                raise FSError(f"{disp} doesn't exist")
            return Entry(parts[0].upper(), False, len(t.encode()), 0, disp)
        path = self.real(vpath, cwd, must_exist=True)
        st = os.stat(path)
        return Entry(vbasename(disp) or "C:", os.path.isdir(path), 0 if os.path.isdir(path) else st.st_size,
                     st.st_mtime, disp)

    def used(self) -> int:
        total = 0
        for key, root in self.mounts.items():
            if key == "":
                continue
            for dp, dn, fn in os.walk(root):
                for f in fn:
                    try:
                        total += os.path.getsize(os.path.join(dp, f))
                    except OSError:
                        pass
        for dp, dn, fn in os.walk(self.mounts[""]):
            dn[:] = [d for d in dn if d.upper() not in self.mount_names]
            for f in fn:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
        return total

    # ------------------------------------------------------------------ writing
    def _changed(self, vpath: str):
        for fn in list(self.listeners):
            try:
                fn(vpath)
            except Exception:
                pass

    def _check_write(self, path: str, size: int):
        if size > MAX_FILE:
            raise FSError("Files can be up to 1 MB")
        old = os.path.getsize(path) if os.path.isfile(path) else 0
        if self.used() - old + size > MAX_DRIVE:
            raise FSError("C: is full (64 MB). Empty the Recycle Bin or delete something")
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            raise FSError("That folder doesn't exist")
        if not os.path.exists(path) and len(os.listdir(folder)) >= MAX_ENTRIES:
            raise FSError("That folder is full (1,000 files)")

    def write_text(self, vpath: str, text: str, cwd="C:\\Documents") -> str:
        path = self.real(vpath, cwd)
        if os.path.isdir(path):
            raise FSError("That's a folder")
        data = text.replace("\r\n", "\n")
        self._check_write(path, len(data.encode("utf-8")))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
        vp = self.normalize(vpath, cwd)
        self._changed(vp)
        return vp

    def append_text(self, vpath: str, text: str, cwd="C:\\Documents") -> str:
        old = self.read_text(vpath, cwd) if self.exists(vpath, cwd) else ""
        return self.write_text(vpath, old + text, cwd)

    def mkdir(self, vpath: str, cwd="C:\\Documents") -> str:
        path = self.real(vpath, cwd)
        if os.path.exists(path):
            raise FSError("Something with that name is already there")
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            raise FSError("That folder doesn't exist")
        if len(os.listdir(parent)) >= MAX_ENTRIES:
            raise FSError("That folder is full (1,000 files)")
        os.mkdir(path)
        vp = self.normalize(vpath, cwd)
        self._changed(vp)
        return vp

    def rename(self, vpath: str, new_name: str, cwd="C:\\Documents") -> str:
        if not NAME_RX.match(new_name or "") or new_name.strip(".") == "":
            raise FSError("Use letters, numbers, spaces, - _ and dots (up to 32)")
        if self.is_mount_root(vpath):
            raise FSError("System folders can't be renamed")
        path = self.real(vpath, cwd, must_exist=True)
        dest = os.path.join(os.path.dirname(path), new_name)
        if os.path.exists(dest) and dest.lower() != path.lower():
            raise FSError("Something with that name is already there")
        os.replace(path, dest)
        drive, parts = self.split(vpath, cwd)
        vp = self.join(drive, self._display_parts(drive, parts[:-1]) + [new_name])
        self._changed(vp)
        return vp

    def copy(self, src: str, dest_folder: str, cwd="C:\\Documents") -> str:
        """Copy a file (from C: or A:) into a C: folder; a name already there gets ' (2)'."""
        e = self.stat(src, cwd)
        if e.is_dir:
            raise FSError("Folders can't be copied (yet); copy the files inside")
        text = self.read_text(src, cwd)
        base, ext = os.path.splitext(e.name)
        name, n = e.name, 2
        folder = self.normalize(dest_folder, cwd)
        while self.exists(folder + "\\" + name):
            name = f"{base} ({n}){ext}"
            n += 1
        return self.write_text(folder + "\\" + name, text)

    def move(self, src: str, dest_folder: str, cwd="C:\\Documents") -> str:
        if self.is_mount_root(src):
            raise FSError("System folders can't be moved")
        path = self.real(src, cwd, must_exist=True)
        folder = self.real(dest_folder, cwd, must_exist=True)
        dest = os.path.join(folder, os.path.basename(path))
        if os.path.exists(dest):
            raise FSError("Something with that name is already there")
        shutil.move(path, dest)
        vp = self.normalize(dest_folder, cwd) + "\\" + os.path.basename(path)
        self._changed(vp)
        return vp

    # ------------------------------------------------------------------ the Recycle Bin
    def _bin_index_path(self):
        return os.path.join(self.mounts["RECYCLED"], "_index.json")

    def _bin_index(self) -> Dict[str, str]:
        try:
            with open(self._bin_index_path(), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _bin_save(self, idx: Dict[str, str]):
        try:
            with open(self._bin_index_path(), "w", encoding="utf-8") as f:
                json.dump(idx, f, indent=1)
        except OSError:
            pass

    def delete(self, vpath: str, cwd="C:\\Documents", permanent=False) -> str:
        """Move a file or folder to the Recycle Bin (or delete it for good). Returns its name in the bin."""
        if self.is_mount_root(vpath):
            raise FSError("System folders can't be deleted")
        path = self.real(vpath, cwd, must_exist=True)
        orig = self.normalize(vpath, cwd)
        if permanent or orig.upper().startswith("C:\\RECYCLED\\"):
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            idx = self._bin_index()
            idx.pop(os.path.basename(path), None)
            self._bin_save(idx)
            self._changed(orig)
            return ""
        bin_dir = self.mounts["RECYCLED"]
        name = os.path.basename(path)
        base, ext = os.path.splitext(name)
        n = 2
        while os.path.exists(os.path.join(bin_dir, name)):
            name = f"{base} ({n}){ext}"
            n += 1
        shutil.move(path, os.path.join(bin_dir, name))
        idx = self._bin_index()
        idx[name] = orig
        self._bin_save(idx)
        self._changed(orig)
        return name

    def bin_items(self) -> List[Tuple[str, str]]:
        """(name in the bin, where it came from)."""
        idx = self._bin_index()
        out = []
        try:
            for f in sorted(os.listdir(self.mounts["RECYCLED"]), key=str.lower):
                if f.startswith("_") or f.startswith("."):
                    continue
                guess = idx.get(f)
                if not guess:
                    folder = "Programs" if f.lower().endswith(".bas") else "Documents"
                    guess = f"C:\\{folder}\\{f}"
                out.append((f, guess))
        except OSError:
            pass
        return out

    def restore(self, name: str) -> str:
        items = dict(self.bin_items())
        if name not in items:
            raise FSError("That isn't in the bin")
        orig = items[name]
        drive, parts = self.split(orig)
        folder = self.join(drive, parts[:-1])
        if not self.isdir(folder):
            folder = "C:\\Documents"
        dest_name = parts[-1]
        base, ext = os.path.splitext(dest_name)
        n = 2
        while self.exists(folder + "\\" + dest_name):
            dest_name = f"{base} ({n}){ext}"
            n += 1
        shutil.move(os.path.join(self.mounts["RECYCLED"], name), os.path.join(self.real(folder), dest_name))
        idx = self._bin_index()
        idx.pop(name, None)
        self._bin_save(idx)
        vp = self.normalize(folder + "\\" + dest_name)
        self._changed(vp)
        return vp

    def empty_bin(self) -> int:
        n = 0
        for name, orig in self.bin_items():
            p = os.path.join(self.mounts["RECYCLED"], name)
            try:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                n += 1
            except OSError:
                pass
        self._bin_save({})
        self._changed("C:\\Recycled")
        return n

    # ------------------------------------------------------------------ types
    @staticmethod
    def type_of(vpath: str) -> Tuple[str, str, str]:
        ext = os.path.splitext(vpath)[1].upper()
        return FILE_TYPES.get(ext, ("File", "D", ""))
