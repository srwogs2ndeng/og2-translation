#!/usr/bin/env python3
"""Flag translated LDBI dialogue messages that reflow to >3 lines (the box truncates them)."""
import sys,glob,json,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import worksheet as W
MAX=int(sys.argv[1]) if len(sys.argv)>1 else 3
n=0
for wp in glob.glob("build/worksheets/Logic/Dat/logic/talk/*.json"):
    ws=json.load(open(wp,encoding="utf-8"))
    for k,v in ws.items():
        en=(v.get("en") or "").strip()
        if not en: continue
        L=len(W.rewrap(W.normalize(en),48).split("@"))
        if L>MAX:
            print(f"{os.path.basename(wp)} {k}: {L} lines - {en[:60]}"); n+=1
print(f"\n{n} messages exceed {MAX} lines (would truncate in the box)")
