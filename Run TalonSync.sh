#!/usr/bin/env bash
# TalonSync for Linux and macOS: sets itself up the first time, then starts TalonSync.
#   ./Run\ TalonSync.sh            start TalonSync
#   ./Run\ TalonSync.sh --setup    (re)install its packages, then start
#   ./Run\ TalonSync.sh --qt       also install the Qt window engine (Linux, ~150 MB) if you'd
#                                  rather have a real app window than a browser-style one
# Anything else is passed to TalonSync (try --help).
set -u
cd "$(dirname "$0")"

say() { printf '  %s\n' "$*"; }
echo
echo "  ==============================================="
echo "    TalonSync for $( [ "$(uname)" = Darwin ] && echo macOS || echo Linux )"
echo "  ==============================================="

# ---- a Python 3.10.1 or newer
PY=""
for c in python3.13 python3.12 python3.14 python3.11 python3 python3.15 python3.10 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info[:3] >= (3,10,1) else 1)' 2>/dev/null; then
        PY="$c"; break
    fi
done
if [ -z "$PY" ]; then
    say "No Python 3.10.1 or newer found."
    if [ "$(uname)" = Darwin ]; then say "Install one from https://www.python.org/downloads/macos/ (or: brew install python), then run this again."
    else say "Install it with your package manager, e.g.  sudo apt install python3 python3-venv  /  sudo dnf install python3"; fi
    exit 1
fi
say "Using $($PY -c 'import sys; print(sys.version.split()[0])') ($PY)"

SETUP=0; QT=0; ARGS=()
for a in "$@"; do
    case "$a" in --setup) SETUP=1 ;; --qt) QT=1; SETUP=1 ;; *) ARGS+=("$a") ;; esac
done

# ---- a private environment (so nothing touches your other Python stuff)
if [ ! -x .venv/bin/python ]; then
    SETUP=1
    say "Making a private environment in .venv ..."
    # system site packages: lets the app window use your desktop's GTK WebKit if it's installed
    if ! "$PY" -m venv --system-site-packages .venv 2>/dev/null; then
        rm -rf .venv
        say "Couldn't make one (on Debian/Ubuntu: sudo apt install python3-venv)."
        say "Starting with plain Python instead: everything works, it just opens in your browser."
        exec "$PY" talonsync_main.py "${ARGS[@]+"${ARGS[@]}"}"
    fi
fi
VPY=.venv/bin/python

if [ "$SETUP" = 1 ]; then
    say "Installing packages (first time takes a minute) ..."
    "$VPY" -m pip install --upgrade pip >/dev/null 2>&1
    opt() {  # package, what it gives, what happens without it
        if "$VPY" -m pip install --upgrade "$1" >/dev/null 2>&1; then say "  [ok] $1 - $2"; else say "  [--] $1 - skipped: $3"; fi
    }
    opt Pillow "tray icon + importing pictures" "a plainer tray icon"
    opt zeroconf "OSCQuery" "plain OSC ports 9000/9001 only"
    opt psutil "PC Link: CPU and memory load" "PC Link shows -- for CPU and RAM"
    opt openvr "PC Link: headset and controller battery" "PC Link shows -- for batteries"
    opt pystray "tray icon" "closing the window quits"
    opt pywebview "app window" "TalonSync opens in a browser window instead - works the same"
    if [ "$QT" = 1 ]; then opt "pywebview[qt]" "Qt app window" "browser window instead"; fi
    if [ "$(uname)" != Darwin ]; then
        if ! "$VPY" -c 'import gi; gi.require_version("Gtk","3.0")' >/dev/null 2>&1 && [ "$QT" = 0 ]; then
            say "  [--] no GTK for the app window: TalonSync will open in a Chrome/Chromium/Edge app window or your browser."
            say "       (For a real window: sudo apt install python3-gi gir1.2-webkit2-4.1  - or run with --qt)"
        fi
        command -v playerctl >/dev/null 2>&1 || command -v gdbus >/dev/null 2>&1 || \
            say "  [--] Now Playing needs playerctl or gdbus (sudo apt install playerctl)"
    fi
    say "Checking it works ..."
    if "$VPY" tests/test_formats.py >/dev/null 2>&1; then say "  [ok] self-test"; else say "  [!!] self-test failed - TalonSync may still run; see tests/test_formats.py"; fi
fi

echo
say "Starting TalonSync ... (close this window or press Ctrl+C to quit it)"
exec "$VPY" talonsync_main.py "${ARGS[@]+"${ARGS[@]}"}"
