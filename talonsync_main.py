"""TalonSync - entry point. Runs the service and opens the window (or your browser)."""
import argparse
import os
import sys
import threading
import time


def main():
    ap = argparse.ArgumentParser(prog="TalonSync")
    ap.add_argument("--minimized", action="store_true", help="start in the tray")
    ap.add_argument("--browser", action="store_true", help="open in your web browser instead of a window")
    ap.add_argument("--port", type=int, default=0, help="UI port (default: any free port)")
    ap.add_argument("--data", default=None, help="data folder")
    ap.add_argument("--demo", action="store_true", help="use the built-in demo PDA")
    ap.add_argument("--headless", action="store_true", help="no window (print the URL)")
    args = ap.parse_args()

    from talonsync.core import TalonSyncApp
    from talonsync.server import Server
    from talonsync import ui

    if not ui.single_instance():
        return
    app = TalonSyncApp(args.data)
    if args.demo:
        app.settings.update({"demo_pda": True})
    app.start()
    srv = Server(app, args.port).start()
    try:
        if args.headless:
            print(srv.url, flush=True)
            while True:
                time.sleep(3600)
        ui.run(app, srv, minimized=args.minimized or app.settings.get("start_minimized"), browser=args.browser)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        srv.stop()


if __name__ == "__main__":
    main()
