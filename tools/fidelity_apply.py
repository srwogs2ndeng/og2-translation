#!/usr/bin/env python3
"""fidelity_apply.py - apply approved fidelity-review findings to the worksheets.

Consumes build/audit/fidelity_findings.json (the merged re-read report) one
severity WAVE at a time (owner-approved order: error -> awkward -> polish):

    python tools/fidelity_apply.py error            # apply + write log
    python tools/audit.py --gate                    # then gate before committing
    python tools/fidelity_apply.py error --dry-run  # preview only

Design: VALIDATING applier, not a blind patcher. A finding is applied only if
ALL of the following hold; otherwise it is skipped with a logged reason:

  match   the worksheet entry still carries exactly the jp+en the reviewer saw
          (rows edited since the review are STALE and never clobbered)
  tokens  § count, #N substitutions, and control tags {W,H,C,S,Y,T,I,X,LINK}
          in the proposal match the original en; leading 「 / trailing 」 kept;
          wtd fullwidth chrome ＜＞【】 multiset kept
  clean   normalized proposal contains no CJK/kana and no exotic confusables
  length  dialogue (logic/talk): rewrap@48 of the proposal fits <=3 lines;
          FixedData: growable, no byte cap;
          everything else (Battle/Common/General2d/EBOOT/logic-bin/Roll/...):
          UTF-8 bytes <= the entry's slot
  dedupe  one finding per row: best severity wins (error > awkward > polish),
          the rest are logged as superseded

Proposals are stored normalized through the same PUNCT map the audit and
reinsert use (R0 keeps those in lockstep), so the gate sees exactly what
will be emitted.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from audit import (PUNCT, normalize, rewrap, tags_of, is_dialogue, is_growable,
                   CONFUSABLE, COMBINING, LATIN_EXT, EXOTIC_LITERAL, CJK, SUBST)

FID = os.path.join(REPO, "build", "audit", "fidelity")
WS_ROOT = os.path.join(REPO, "build", "worksheets")
SEV_RANK = {"error": 0, "awkward": 1, "polish": 2}
SECT = re.compile(r"§")
FW_CHROME = set("＜＞【】")


def worksheet_index():
    """basename-stem -> relpath for every worksheet file (e.g. '113.bmd',
    'scr00064.bin', 'scr00064', 'windowdataMain.wtd', 'eboot')."""
    idx = {}
    for root, _dirs, files in os.walk(WS_ROOT):
        for f in files:
            if not f.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(root, f), WS_ROOT)
            stem = f[:-5]                       # strip .json
            idx.setdefault(stem, rel)
            if "." in stem:                     # scr00064.bin -> scr00064
                idx.setdefault(stem.split(".")[0], rel)
    return idx


# library units write to FLAT string maps (not worksheets): key -> en string.
# fix_dictionaries/fix_keyworddata wrap-truncate at build time, so no slot rule.
FLAT_STORES = {
    "library_dict": os.path.join("build", "dict_desc_en.json"),
    "library_keywords": os.path.join("build", "keyword_desc_en.json"),
}


def flat_store_for(unit_name):
    if unit_name.startswith("library_dict"):
        return FLAT_STORES["library_dict"]
    if unit_name == "library_keywords":
        return FLAT_STORES["library_keywords"]
    return None


def unit_file_hint(unit_name):
    """Default worksheet stem for units whose row keys are bare offsets."""
    m = re.match(r"story_(ls\d+)_p\d+$", unit_name)
    if m:
        return m.group(1) + ".bin"
    if unit_name.startswith("eboot_"):
        return "eboot"
    return None


def resolve(unit_name, key, idx):
    """-> (worksheet relpath, offset) or (None, reason)."""
    if ":" in key:
        fpart, off = key.split(":", 1)
        rel = idx.get(fpart) or idx.get(fpart.split(".")[0])
        if not rel:
            return None, f"no worksheet for '{fpart}'"
        return rel, off
    hint = unit_file_hint(unit_name)
    if hint:
        rel = idx.get(hint)
        if rel:
            return rel, key
    return None, f"bare key {key} in unit {unit_name} with no file hint"


def token_sig(text):
    return (len(SECT.findall(text or "")),
            tuple(sorted(SUBST.findall(text or ""))),
            tuple(sorted(tags_of(text or ""))))


def validate(orig_en, proposed, relpath, slot):
    """-> (normalized proposal, None) or (None, reason)."""
    if not proposed or not proposed.strip():
        return None, "empty proposal"
    p = normalize(proposed).strip()
    if p == normalize(orig_en).strip():
        return None, "proposal identical to current text"
    if token_sig(p) != token_sig(orig_en):
        return None, "control tokens differ (§ / #N / control tags)"
    o = normalize(orig_en).strip()   # emit strips, so compare stripped forms
    if o.startswith("「") != p.startswith("「") or o.endswith("」") != p.endswith("」"):
        return None, "corner-bracket wrapper changed"
    if "WindowToolData" in relpath:
        if Counter(c for c in orig_en if c in FW_CHROME) != Counter(c for c in p if c in FW_CHROME):
            return None, "wtd fullwidth chrome changed"
    if CJK.search(p):
        return None, "CJK/kana in proposal"
    if CONFUSABLE.search(p) or COMBINING.search(p) or LATIN_EXT.search(p) \
            or any(c in EXOTIC_LITERAL for c in p):
        return None, "exotic characters in proposal"
    if is_dialogue(relpath):
        if rewrap(p).count("@") > 2:
            return None, "reflows past 3 lines"
    elif not is_growable(relpath):
        if slot is not None and len(p.encode("utf-8")) > slot:
            return None, f"over slot ({len(p.encode('utf-8'))}>{slot}B)"
    return p, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wave", choices=["error", "awkward", "polish"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    flat = json.load(open(os.path.join(REPO, "build", "audit", "fidelity_findings.json")))
    finds = flat["findings"] if isinstance(flat, dict) else flat
    idx = worksheet_index()

    # dedupe: best severity per (unit, key); stable within severity
    best = {}
    for f in finds:
        k = (f["source"], f["key"])
        if k not in best or SEV_RANK[f["severity"]] < SEV_RANK[best[k]["severity"]]:
            best[k] = f
    superseded = len(finds) - len(best)
    wave = [f for f in best.values() if f["severity"] == args.wave]

    units, applied, skipped = {}, [], []
    touched = {}
    for f in sorted(wave, key=lambda x: (x["source"], x["key"])):
        uname, key = f["source"], f["key"]
        if uname not in units:
            units[uname] = json.load(open(os.path.join(FID, "in", f"{uname}.json")))
        row = units[uname]["rows"].get(key)
        if row is None:
            skipped.append({**f, "why": "key not in unit input"})
            continue
        # library units: flat string-map stores, no worksheet/slot machinery
        store = flat_store_for(uname)
        if store:
            spath = os.path.join(REPO, store)
            sm = touched.get(store) or json.load(open(spath))
            touched[store] = sm
            cur = sm.get(key)
            if cur is None:
                skipped.append({**f, "why": f"key missing from {store}"})
                continue
            if cur != row["en"]:
                skipped.append({**f, "why": "STALE: store changed since review"})
                continue
            newen, why = validate(cur, f.get("proposed"), store, None)
            if newen is None:
                skipped.append({**f, "why": why})
                continue
            if not args.dry_run:
                sm[key] = newen
            applied.append({"file": store, "key": key, "check": f["check"],
                            "old": cur, "new": newen})
            continue
        rel, off = resolve(uname, key, idx)
        if rel is None:
            skipped.append({**f, "why": off})
            continue
        wpath = os.path.join(WS_ROOT, rel)
        ws = touched.get(rel) or json.load(open(wpath))
        touched[rel] = ws
        ent = ws.get(off)
        if ent is None:
            skipped.append({**f, "why": f"offset {off} not in {rel}"})
            continue
        if ent.get("jp") != row["jp"] or ent.get("en") != row["en"]:
            skipped.append({**f, "why": "STALE: worksheet changed since review"})
            continue
        newen, why = validate(ent.get("en") or "", f.get("proposed"), rel, row.get("slot"))
        if newen is None:
            skipped.append({**f, "why": why})
            continue
        if not args.dry_run:
            ent["en"] = newen
        applied.append({"file": rel, "key": off, "check": f["check"],
                        "old": row["en"], "new": newen})

    if not args.dry_run:
        flat_paths = set(FLAT_STORES.values())
        for rel, ws in touched.items():
            # only rewrite files that actually changed
            if any(a["file"] == rel for a in applied):
                path = os.path.join(REPO, rel) if rel in flat_paths \
                    else os.path.join(WS_ROOT, rel)
                json.dump(ws, open(path, "w"), ensure_ascii=False, indent=1)
        log = {"wave": args.wave, "applied": applied, "skipped": skipped,
               "superseded_total": superseded}
        lp = os.path.join(REPO, "build", "audit", f"apply_log_{args.wave}.json")
        json.dump(log, open(lp, "w"), ensure_ascii=False, indent=1)
        print(f"log -> {lp}")

    why_hist = Counter(s["why"].split(" (")[0] for s in skipped)
    print(f"wave={args.wave}{' [DRY RUN]' if args.dry_run else ''}: "
          f"{len(applied)} applied, {len(skipped)} skipped, "
          f"{len({a['file'] for a in applied})} files touched")
    for why, n in why_hist.most_common():
        print(f"  skip {n:4d}  {why}")


if __name__ == "__main__":
    main()
