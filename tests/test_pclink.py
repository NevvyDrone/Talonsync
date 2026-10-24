"""PC Link against the demo PDA: protocol 3, values, messages, the focus timer and PDA commands."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.core import TalonSyncApp
from talonsync import protocol as pr

app = TalonSyncApp(tempfile.mkdtemp())
app.settings.data["demo_pda"] = True
app.settings.data["oscquery"] = False
app.start()
try:
    for _ in range(40):
        if app.pc.protocol >= 3 and app.demo.pc[pr.PC_UNREAD] == 0:
            break
        time.sleep(0.5)
    assert app.pc.protocol == 3, app.pc.protocol
    app.pc.message("Discord", "Wren: on my way")
    time.sleep(3)
    assert app.demo.pc_message == ["Discord", "Wren: on my way"], app.demo.pc_message
    assert app.demo.alerts == 1 and app.demo.pc[pr.PC_UNREAD] == 1
    app.pc._timer_phase(1)
    time.sleep(4)
    assert app.demo.pc[pr.PC_TIMER_STATE] == 1 and app.demo.pc[pr.PC_TIMER_MIN] == 25, app.demo.pc
    app.demo._setp(pr.PC_CMD, pr.CMD_CLEAR)            # the PDA's "clear messages"
    time.sleep(3)
    assert app.demo.pc_message == ["", ""] and app.demo.pc[pr.PC_UNREAD] == 0
    assert app.demo.params.get(pr.PC_CMD) == 0          # TalonSync re-armed the command line
    app.demo._setp(pr.PC_CMD, pr.CMD_TIMER)              # stop the timer from the PDA
    time.sleep(4)
    assert app.demo.pc[pr.PC_TIMER_STATE] == 0, app.demo.pc
    print("PCLINK OK")
finally:
    app.stop()
