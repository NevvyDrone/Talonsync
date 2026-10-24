"""Twitch chat reader against a tiny local IRC server (no internet needed)."""
import os, socket, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.pclink import TwitchChat, twitch_channel_name

assert twitch_channel_name("https://www.twitch.tv/Some_Owl") == "some_owl"
assert twitch_channel_name("#Some_Owl ") == "some_owl" and twitch_channel_name("@Owl") == "owl"
srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
port = srv.getsockname()[1]
got = []
def serve():
    c, _ = srv.accept()
    data = b""
    while b"JOIN" not in data:
        data += c.recv(1024)
    assert b"NICK justinfan" in data and b"JOIN #some_owl" in data, data
    c.sendall(b":tmi.twitch.tv 001 justinfan1 :Welcome\r\n:justinfan1!justinfan1@justinfan1.tmi.twitch.tv JOIN #some_owl\r\n"
              b":tmi.twitch.tv 366 justinfan1 #some_owl :End of /NAMES list\r\nPING :tmi.twitch.tv\r\n"
              b"@badge-info=;color=#FF0000 :wren!wren@wren.tmi.twitch.tv PRIVMSG #some_owl :hoot @some_owl!\r\n")
    time.sleep(1); c.close()
threading.Thread(target=serve, daemon=True).start()
t = TwitchChat("twitch.tv/Some_Owl", lambda u, m: got.append((u, m)), log=lambda m: None, host="127.0.0.1", ports=((port, False),))
t.start()
for _ in range(30):
    if got: break
    time.sleep(0.1)
t.stop()
assert got == [("wren", "hoot @some_owl!")], got
assert t.count == 1
print("TWITCH OK")
