"""Talon Enhanced BASIC: the interpreter on its own (no PDA needed)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from talonsync.basic import Basic, BasicError

out, inputs = [], ["7"]
b = Basic(out.append, lambda p: (out.append(p), inputs.pop(0))[1] if inputs else None, folder=tempfile.mkdtemp())
def run(*lines):
    for l in lines:
        try: b.enter(l)
        except BasicError as e: out.append(f"?{e} ERROR\n")
run("10 FORI=1TO3", "20 ?I*I;", "30 NEXT:?", "40 INPUT N", "50 IF N>5 THEN ?\"BIG\" ELSE ?\"SMALL\"", "60 GOSUB 100:?A$", "70 END",
    "100 A$=LEFT$(\"OWLISH\",3)+STR$(N)", "110 RETURN", "RUN")
run("?2**10;SQR(144);LEN(\"OWL\")", "DIM A(3):A(2)=9:?A(2)", "?1/0", "SAVE \"T\"", "NEW", "LOAD \"T\"", "LIST 10")
text = "".join(out)
for want in [" 1  4  9", "BIG", "OWL7", " 1024  12  3", " 9", "?DIVISION BY ZERO ERROR", "SAVED T", "LOADED T", "10 FORI=1TO3"]:
    assert want in text, (want, text)
print("BASIC OK")
