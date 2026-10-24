# PyInstaller recipe for TalonSync.exe (used by "Build TalonSync.bat")
import sys
if sys.version_info[:3] == (3, 10, 0):
    raise SystemExit("\n  This build environment uses Python 3.10.0, which has a bug that crashes PyInstaller.\n"
                     "  Install Python 3.12 from python.org, DELETE the .venv folder, and run Build TalonSync.bat again.\n")
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = ["talonsync", "talonsync.pclink", "talonsync.deskclick", "talonsync.support", "psutil", "openvr", "pystray._win32", "PIL._tkinter_finder", "zeroconf._utils.ipaddress", "zeroconf._handlers.answers"]
for pkg in ("winsdk.windows.media.control", "winsdk.windows.foundation", "winrt.windows.media.control", "winrt.windows.foundation", "webview", "zeroconf"):
    try:
        hidden += collect_submodules(pkg)
    except Exception:
        pass

datas = [("talonsync/web", "talonsync/web"), ("assets/talonsync.ico", "assets")]
try:
    datas += collect_data_files("webview")
except Exception:
    pass

a = Analysis(["talonsync_main.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="TalonSync", icon="assets/talonsync.ico",
          console=False, upx=False, disable_windowed_traceback=False,
          version=None)
