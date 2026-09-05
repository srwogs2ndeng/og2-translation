#!/usr/bin/env python3
"""name_canon_fix.py - apply the audited character/mech-name spelling corrections
to the worksheets AND the canon reference files (pdf_charnames.json,
canon_names.json). Word-boundary anchored; corpus rows that are byte-slot-bound
and would overflow are skipped+logged (never silently truncated).

  python tools/name_canon_fix.py [--dry-run]
"""
import argparse, json, os, re, sys, glob
from collections import Counter
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(REPO,"tools"))
from audit import is_growable

# safe misspelled TOKENS -> replace globally (word-boundary); these strings have
# no other meaning in the script.
TOKENS=[
 ("Gheist","Geist"),("Soulgady","Solgady"),("Gadyful","Gadifall"),
 ("Feinschmeker","Feinschmecker"),("Toumine","Tomine"),("Vysaga","Vaisaga"),
 ("Rishuu","Rishu"),("Gojyou","Gojo"),("Irmgult","Irmgard"),
 ("Lestgrunch","Lestgranche"),("Araseli","Araceli"),("Almara","Amara"),
 ("Rahda","Radha"),("Oreg","Oleg"),("Rathgrith","Razangriff"),
 ("Ashsaber","Ash Saviour"),("Hevy","Heavy"),("Forete","Forte"),
 ("Angeleg","Angelg"),("Granvell","Granveil"),("Jaohmn","Jaohm"),
 ("Webly","Webley"),("Bidner","Bittner"),("Takakuwa","Takakura"),
 ("Hamil","Hamill"),("OhRyuuKoh","OhRyuKoh"),("Galgaurd","Galguard"),
]
# PHRASES -> replace as whole phrase (component is a real word / ambiguous alone)
PHRASES=[
 ("Axel Almar","Axel Almer"),("Yuuki Jaggar","Yuuki Jegnan"),
 ("Graf Drone","Graf Droso"),("Norse Ray","Norse Rei"),
 ("Hugo Medius","Hugo Medio"),("Skull Plume","Scalprum"),
 ("Ares Geist","Alles Geist"),("Gigascudo Duo","Giganscudo Duro"),
 ("Lige- Geios","Liege Geios"),("Gilliam Yager","Gilliam Yeager"),
 ("Wild Rauptier Schnabel","Wildraubtier Schnabel"),
 ("Alt Eisen Risse","Alt Eisen Riese"),("Rein Weiss Ritter","Rein Weissritter"),
]
RULES=[(re.compile(r'(?<![A-Za-z])'+re.escape(w)+r'(?![A-Za-z])'),r) for w,r in TOKENS]
RULES+=[(re.compile(re.escape(w)),r) for w,r in PHRASES]

def fix(text):
    labels=[]; out=text
    for pat,repl in RULES:
        new=pat.sub(repl,out)
        if new!=out: labels.append(repl); out=new
    return out,labels

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dry-run",action="store_true")
    a=ap.parse_args()
    applied=[]; skipped=[]
    # corpus
    for f in glob.glob(os.path.join(REPO,"build","worksheets","**","*.json"),recursive=True):
        rel=os.path.relpath(f,os.path.join(REPO,"build","worksheets"))
        d=json.load(open(f)); ch=False
        for k,v in d.items():
            if not isinstance(v,dict): continue
            en=v.get("en")
            if not en: continue
            new,labels=fix(en)
            if not labels: continue
            slot=v.get("slot")
            if not is_growable(rel) and slot is not None and len(new.encode())>slot:
                skipped.append({"file":rel,"key":k,"old":en,"new":new,"why":f"over slot {len(new.encode())}>{slot}"}); continue
            applied.append({"file":rel,"key":k,"labels":labels,"old":en,"new":new})
            if not a.dry_run: v["en"]=new; ch=True
        if ch and not a.dry_run: json.dump(d,open(f,"w"),ensure_ascii=False,indent=1)
    # canon files (values)
    for cf in ["build/pdf_charnames.json","build/canon_names.json"]:
        p=os.path.join(REPO,cf); d=json.load(open(p)); ch=False
        for k,v in list(d.items()):
            if not isinstance(v,str): continue
            new,labels=fix(v)
            if labels:
                applied.append({"file":cf,"key":k,"labels":labels,"old":v,"new":new})
                if not a.dry_run: d[k]=new; ch=True
        if ch and not a.dry_run: json.dump(d,open(p,"w"),ensure_ascii=False,indent=1)
    hist=Counter(l for x in applied for l in x["labels"])
    corpus=[x for x in applied if x["file"].endswith('.json') and 'worksheets' not in x['file'] and not x['file'].startswith('build/')]
    ncorpus=sum(1 for x in applied if x['file'] not in ('build/pdf_charnames.json','build/canon_names.json'))
    print(f"{'[DRY] ' if a.dry_run else ''}{ncorpus} corpus rows + "
          f"{len(applied)-ncorpus} canon-file entries changed; {len(skipped)} skipped")
    for name,n in hist.most_common(): print(f"  {n:3d}  ->{name}")
    for s in skipped: print(f"  SKIP {s['file']} {s['key']}: {s['why']}")
    if not a.dry_run:
        json.dump({"applied":applied,"skipped":skipped},
                  open(os.path.join(REPO,"build","audit","name_canon_fix_log.json"),"w"),
                  ensure_ascii=False,indent=1)
if __name__=="__main__": main()
