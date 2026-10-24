"""TalonStar weather + jazz against the REAL animator (bridge.ps1 on 19200/19201)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.osc import OscLink
from talonsync.bus import PdaBus, Timing
from talonsync import weather as W, protocol as pr
link = OscLink(send_port=19200, listen_port=19201); assert link.start()
bus = PdaBus(link, Timing(ack_timeout=1.0))
for i in range(30):
    try: print("ping", bus.ping()); break
    except Exception: time.sleep(0.5)
w = W.sample()
w["current"]["temp"] = -12
bus.weather(w); print("weather sent")
bus.open_app(27); bus.jazz_mode(2); print("app 27, jazz everyone")
time.sleep(1.0)
print("JazzAll seen over OSC:", link.get("TP/JazzAll"))
bus.jazz_mode(1); time.sleep(0.5); print("after 'just me':", link.get("TP/JazzAll"))
bus.jazz_mode(2); time.sleep(0.5)
print("done")
bus.ticker("Hoot hoot! Stay warm and clever, friend!")
print("ticker sent")
