"""OSCQuery: lets VRChat find TalonSync even when other OSC apps (face tracking, chatbox tools...) run too.

We serve a tiny OSCQuery HTTP endpoint and advertise it (and our OSC UDP port) over mDNS, so
VRChat sends avatar parameters to *our* port instead of everyone fighting over 9001. We also look
for VRChat's own OSCQuery service to learn its input port and read current parameter values.
mDNS needs the `zeroconf` package (bundled in the exe); without it TalonSync uses plain 9000/9001.
"""
from __future__ import annotations

import json
import socket
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional

try:
    from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
    HAVE_ZEROCONF = True
except Exception:  # pragma: no cover
    HAVE_ZEROCONF = False


def free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class _Handler(BaseHTTPRequestHandler):
    service: "OscQueryService" = None

    def log_message(self, *a):
        pass

    def do_GET(self):
        svc = self.service
        if "HOST_INFO" in self.path:
            body = {"NAME": svc.name, "OSC_IP": "127.0.0.1", "OSC_PORT": svc.osc_port, "OSC_TRANSPORT": "UDP",
                    "EXTENSIONS": {"ACCESS": True, "VALUE": True, "DESCRIPTION": True}}
        else:
            node = lambda path, access=2, typ=None, desc="": dict(FULL_PATH=path, ACCESS=access, DESCRIPTION=desc, **({"TYPE": typ} if typ else {}))
            body = {"DESCRIPTION": svc.name, "FULL_PATH": "/", "ACCESS": 0, "CONTENTS": {
                "avatar": {"FULL_PATH": "/avatar", "ACCESS": 0, "CONTENTS": {
                    "change": node("/avatar/change", 2, "s", "avatar changed"),
                    "parameters": {"FULL_PATH": "/avatar/parameters", "ACCESS": 0, "CONTENTS": {}},
                }}}}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class OscQueryService:
    def __init__(self, osc_port: int, name: str = "TalonSync", log: Callable[[str], None] = None):
        self.name = name
        self.osc_port = osc_port
        self.log = log or (lambda m: None)
        self.http: Optional[ThreadingHTTPServer] = None
        self.zc = None
        self.vrchat: Dict[str, object] = {}       # discovered VRChat client: host, http_port, osc_port
        self._infos = []

    @property
    def active(self) -> bool:
        return self.zc is not None

    def start(self) -> bool:
        if not HAVE_ZEROCONF:
            self.log("OSCQuery: zeroconf not installed - using plain OSC ports")
            return False
        handler = type("H", (_Handler,), {"service": self})
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.http.serve_forever, daemon=True, name="oscquery-http").start()
        http_port = self.http.server_address[1]
        try:
            self.zc = Zeroconf()
            addr = socket.inet_aton("127.0.0.1")
            short = f"{self.name}-{self.osc_port}"
            self._infos = [
                ServiceInfo("_oscjson._tcp.local.", f"{short}._oscjson._tcp.local.", addresses=[addr], port=http_port,
                            server=f"{short}.oscjson.tcp.local."),
                ServiceInfo("_osc._udp.local.", f"{short}._osc._udp.local.", addresses=[addr], port=self.osc_port,
                            server=f"{short}.osc.udp.local."),
            ]
            for i in self._infos:
                self.zc.register_service(i)
            ServiceBrowser(self.zc, "_oscjson._tcp.local.", _VrcListener(self))
            self.log(f"OSCQuery: advertising OSC on UDP {self.osc_port}, HTTP {http_port}")
            return True
        except Exception as e:
            self.log(f"OSCQuery failed ({e}) - using plain OSC ports")
            self.stop()
            return False

    def stop(self):
        try:
            if self.zc:
                for i in self._infos:
                    self.zc.unregister_service(i)
                self.zc.close()
        except Exception:
            pass
        self.zc = None
        if self.http:
            self.http.shutdown()
            self.http = None

    def vrchat_values(self) -> Dict[str, object]:
        """Current avatar parameter values from VRChat's OSCQuery (if found)."""
        v = self.vrchat
        if not v.get("http_port"):
            return {}
        try:
            url = f"http://{v['host']}:{v['http_port']}/avatar/parameters"
            with urllib.request.urlopen(url, timeout=1.5) as r:
                tree = json.loads(r.read().decode())
        except Exception:
            return {}
        out = {}

        def walk(node):
            for child in (node.get("CONTENTS") or {}).values():
                if "VALUE" in child and child.get("FULL_PATH", "").startswith("/avatar/parameters/"):
                    vals = child["VALUE"]
                    if vals:
                        out[child["FULL_PATH"][19:]] = vals[0]
                walk(child)
        walk(tree)
        return out


if HAVE_ZEROCONF:
    class _VrcListener(ServiceListener):
        def __init__(self, svc: OscQueryService):
            self.svc = svc

        def add_service(self, zc, type_, name):
            if not name.lower().startswith("vrchat-client"):
                return
            info = zc.get_service_info(type_, name, 1500)
            if not info:
                return
            host = socket.inet_ntoa(info.addresses[0]) if info.addresses else "127.0.0.1"
            self.svc.vrchat = {"name": name, "host": host, "http_port": info.port}
            try:
                with urllib.request.urlopen(f"http://{host}:{info.port}/?HOST_INFO", timeout=1.5) as r:
                    hi = json.loads(r.read().decode())
                self.svc.vrchat["osc_port"] = hi.get("OSC_PORT")
            except Exception:
                pass
            self.svc.log(f"OSCQuery: found {name}")

        def update_service(self, zc, type_, name):
            self.add_service(zc, type_, name)

        def remove_service(self, zc, type_, name):
            if self.svc.vrchat.get("name") == name:
                self.svc.vrchat = {}
else:  # pragma: no cover
    _VrcListener = None
