#!/usr/bin/env python3
"""wf_prep.py - split a worksheet's UNTRANSLATED entries into small per-agent batch
files for the translation workflow, and (re)build a compact glossary.

Each batch file is {hexkey: jp} for ~batch_size strings; an agent reads ONE batch
file + the compact glossary (small), so per-agent input stays ~8KB instead of
re-reading the whole worksheet+glossary (the pilot's cost blow-up).

  wf_prep.py split <worksheet.json> <batch_dir> [batch_size=30]   -> prints [paths]
  wf_prep.py glossary                                             -> glossary/glossary_compact.json
  wf_prep.py merge <worksheet.json> <results.json>                -> write en fields
"""
import sys, os, json, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def cmd_glossary():
    g = json.load(open(os.path.join(REPO, "glossary", "glossary.json"), encoding="utf-8"))
    flat = g.get("flat") or g.get("characters", {})
    outp = os.path.join(REPO, "glossary", "glossary_compact.json")
    json.dump(flat, open(outp, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"compact glossary: {len(flat)} pairs -> {outp} ({os.path.getsize(outp)} B)")

def cmd_split(ws_path, batch_dir, bs=30):
    ws = json.load(open(ws_path, encoding="utf-8"))
    todo = [(k, v["jp"]) for k, v in ws.items() if not (v.get("en") or "").strip()]
    os.makedirs(batch_dir, exist_ok=True)
    for f in glob.glob(os.path.join(batch_dir, "b*.json")):
        os.remove(f)
    paths = []
    for i in range(0, len(todo), bs):
        batch = dict(todo[i:i+bs])
        p = os.path.join(batch_dir, f"b{i//bs:04d}.json")
        json.dump(batch, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        paths.append(p.replace("\\", "/"))
    print(json.dumps(paths))
    sys.stderr.write(f"{len(todo)} untranslated -> {len(paths)} batch files (size {bs})\n")

def cmd_merge(ws_path, results_path):
    ws = json.load(open(ws_path, encoding="utf-8"))
    res = json.load(open(results_path, encoding="utf-8"))
    if isinstance(res, str):
        res = json.loads(res)
    got = 0
    for k, en in res.items():
        if k in ws and str(en).strip():
            ws[k]["en"] = en; got += 1
    json.dump(ws, open(ws_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    over = sum(1 for k in ws if ws[k]["en"] and len(ws[k]["en"].encode()) > ws[k]["slot"])
    print(f"merged {got} translations into {os.path.basename(ws_path)}; {over} exceed slot")

WSROOT = os.path.join(REPO, "build", "worksheets")

def cmd_splitdir(ws_glob, batch_dir, bs=120):
    """Split MANY worksheets into batches with compound keys 'wsrel|hexoffset' so
    results merge back to the correct file. wsrel = worksheet path relative to
    build/worksheets, without .json (e.g. Battle/Dat/Battle/Message/002.bmd)."""
    wss = sorted(glob.glob(os.path.join(REPO, ws_glob), recursive=True))
    os.makedirs(batch_dir, exist_ok=True)
    for f in glob.glob(os.path.join(batch_dir, "b*.json")):
        os.remove(f)
    items = []
    for ws in wss:
        wsrel = os.path.relpath(ws, WSROOT).replace("\\", "/")[:-5]   # strip .json
        d = json.load(open(ws, encoding="utf-8"))
        for k, v in d.items():
            if not (v.get("en") or "").strip():
                items.append((f"{wsrel}|{k}", v["jp"]))
    n = 0
    for i in range(0, len(items), bs):
        batch = dict(items[i:i+bs])
        json.dump(batch, open(os.path.join(batch_dir, f"b{n:04d}.json"), "w", encoding="utf-8"), ensure_ascii=False)
        n += 1
    print(f"{len(wss)} worksheets, {len(items)} strings -> {n} batches (size {bs}) in {batch_dir}")
    return n

def cmd_collectdir(output_file):
    """Merge a Workflow result of {'wsrel|offset': en} back into each worksheet."""
    d = json.load(open(output_file, encoding="utf-8"))
    res = d.get("result", d)
    if isinstance(res, str):
        res = json.loads(res)
    by_ws = {}
    for ck, en in res.items():
        if "|" not in ck:
            continue
        wsrel, off = ck.rsplit("|", 1)
        by_ws.setdefault(wsrel, {})[off] = en
    total = 0
    for wsrel, edits in by_ws.items():
        ws_path = os.path.join(WSROOT, wsrel + ".json")
        if not os.path.exists(ws_path):
            sys.stderr.write(f"  ?? missing worksheet {wsrel}\n"); continue
        ws = json.load(open(ws_path, encoding="utf-8"))
        got = 0
        for off, en in edits.items():
            if off in ws and str(en).strip():
                ws[off]["en"] = en; got += 1; total += 1
        json.dump(ws, open(ws_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"collected {total} translations into {len(by_ws)} worksheets")

def cmd_collect(output_file, ws_path):
    """Extract ['result'] from a Workflow .output file and merge into the worksheet."""
    d = json.load(open(output_file, encoding="utf-8"))
    res = d.get("result", d)
    if isinstance(res, str):
        res = json.loads(res)
    tmp = output_file + ".result.json"
    json.dump(res, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    cmd_merge(ws_path, tmp)

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if   c == "glossary": cmd_glossary()
    elif c == "split":    cmd_split(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 30)
    elif c == "merge":    cmd_merge(sys.argv[2], sys.argv[3])
    elif c == "collect":  cmd_collect(sys.argv[2], sys.argv[3])
    elif c == "splitdir": cmd_splitdir(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 120)
    elif c == "collectdir": cmd_collectdir(sys.argv[2])
    else: print(__doc__); sys.exit(1)
