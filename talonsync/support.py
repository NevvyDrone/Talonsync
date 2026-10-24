"""'Copy support info': one block of plain text a buyer can paste into a help request.

What's in it: versions, platform, connection doctor results, PC Link / desktop click status, the settings
that matter for troubleshooting, and the last log lines. What's NOT in it: your records, your location,
your Twitch channel, custom texts, and your Windows user name (home folder paths become ~).
"""
from __future__ import annotations

import os
import platform
import sys
import time
from typing import List

from . import __version__

# settings never included (personal, or not useful for troubleshooting)
PRIVATE = {"ts_place", "ts_extra_cities", "twitch_channel", "twitch_name", "ts_crawl_text", "ts_pda_ticker_text",
           "auto_export_folder", "watch_import_folder", "window", "accent", "first_run"}


def _redact(text: str) -> str:
    home = os.path.expanduser("~")
    if home and len(home) > 3:
        text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    return text


def build_report(app, log_lines: int = 30, ping: bool = True) -> str:
    L: List[str] = []
    L.append("=== TalonSync support info ===")
    L.append(f"TalonSync {__version__} | {platform.system()} {platform.release()} | Python {platform.python_version()}"
             + (" | built app" if getattr(sys, "frozen", False) else " | from source"))
    L.append(f"Made {time.strftime('%Y-%m-%d %H:%M')} | running {int(time.time() - app.started)} s")
    L.append("")
    L.append("-- Connection doctor")
    try:
        checks = app.doctor() if ping else []
        for c in checks:
            L.append(f"[{'OK ' if c.get('ok') else 'BAD'}] {c.get('name')}: {c.get('detail')}")
    except Exception as e:
        L.append(f"(doctor failed: {e})")
    L.append("")
    L.append("-- PDA")
    try:
        st = app.pc.state()
        L.append(f"Link protocol {st.get('protocol')} | PDA app {st.get('pda_app')} | PC Link open {st.get('pclink_open')}")
        src = st.get("sources", {})
        L.append("Sources: " + ", ".join(f"{k}={v}" for k, v in src.items() if k not in ("twitch_channel", "twitch_error")))
    except Exception as e:
        L.append(f"(PC Link state failed: {e})")
    try:
        d = app.desk.status()
        L.append(f"Desktop click: available={d['available']} on={d['on']} button={d['button']} here={d['here']} "
                 f"vrchat_in_front={d['vrchat_front']} taps={d['taps']}" + (f" ({d['why']})" if d.get("why") else ""))
    except Exception as e:
        L.append(f"(desktop click state failed: {e})")
    L.append("")
    L.append("-- Settings (personal ones left out)")
    try:
        with app.settings.lock:
            data = dict(app.settings.data)
        for k in sorted(data):
            if k in PRIVATE:
                continue
            L.append(f"{k} = {data[k]}")
    except Exception as e:
        L.append(f"(settings failed: {e})")
    L.append("")
    L.append(f"-- Last {log_lines} log lines")
    L.extend(list(app.log_lines)[-log_lines:])
    L.append("=== end ===")
    return _redact("\n".join(str(x) for x in L))
