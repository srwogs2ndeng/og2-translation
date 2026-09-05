#!/usr/bin/env python3
"""fix_canon_names.py - apply owner-flagged canonical-name corrections directly
to the worksheets + library flat stores.

These are NOT fidelity-review proposals; they are hard canon fixes the owner
caught in-game. Each replacement is word-boundary anchored and validated
against the row's byte slot (dialogue in logic/ and the growable FixedData /
library stores have no byte cap). Anything that would overflow its slot is
skipped and logged rather than silently truncated at deploy.

    python tools/fix_canon_names.py            # apply + write log
    python tools/fix_canon_names.py --dry-run  # preview only

Log -> build/audit/fix_canon_names_log.json
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from audit import is_growable  # noqa: E402

WS_ROOT = os.path.join(REPO, "build", "worksheets")
FLAT_STORES = [
    os.path.join(REPO, "build", "dict_desc_en.json"),
    os.path.join(REPO, "build", "keyword_desc_en.json"),
]

# (compiled pattern, replacement, human label)
RULES = [
    (re.compile(r"\b(?:Shtedonias|Shtedonia|Shtedonius|Shutedonia|Schutedenia)\b"),
     "Shutedonias", "shutedonias"),
    (re.compile(r"\bGundro\b"), "GanDuro", "gundro->ganduro"),
]


def apply_rules(text):
    """-> (new_text, [labels changed]) or (text, [])."""
    labels = []
    out = text
    for pat, repl, label in RULES:
        new = pat.sub(repl, out)
        if new != out:
            labels.append(label)
            out = new
    return out, labels


def byte_capped(relpath):
    """logic/ dialogue reflows (no byte cap); FixedData grows; everything else
    is slot-bound to its original byte length."""
    return not is_growable(relpath)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    applied, skipped = [], []

    # worksheets
    for root, _dirs, files in os.walk(WS_ROOT):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, WS_ROOT)
            ws = json.load(open(path))
            changed = False
            for key, ent in ws.items():
                if not isinstance(ent, dict):
                    continue
                en = ent.get("en")
                if not en:
                    continue
                new, labels = apply_rules(en)
                if not labels:
                    continue
                slot = ent.get("slot")
                if byte_capped(rel) and slot is not None \
                        and len(new.encode("utf-8")) > slot:
                    skipped.append({"file": rel, "key": key, "labels": labels,
                                    "old": en, "new": new,
                                    "why": f"over slot ({len(new.encode('utf-8'))}>{slot}B)"})
                    continue
                applied.append({"file": rel, "key": key, "labels": labels,
                                "old": en, "new": new})
                if not args.dry_run:
                    ent["en"] = new
                    changed = True
            if changed and not args.dry_run:
                json.dump(ws, open(path, "w"), ensure_ascii=False, indent=1)

    # library flat stores (key -> en string; wrap-truncated at build, no cap)
    for path in FLAT_STORES:
        if not os.path.exists(path):
            continue
        rel = os.path.relpath(path, REPO)
        sm = json.load(open(path))
        changed = False
        for key, en in list(sm.items()):
            if not isinstance(en, str) or not en:
                continue
            new, labels = apply_rules(en)
            if not labels:
                continue
            applied.append({"file": rel, "key": key, "labels": labels,
                            "old": en, "new": new})
            if not args.dry_run:
                sm[key] = new
                changed = True
        if changed and not args.dry_run:
            json.dump(sm, open(path, "w"), ensure_ascii=False, indent=1)

    label_hist = Counter(l for a in applied for l in a["labels"])
    print(f"{'[DRY RUN] ' if args.dry_run else ''}"
          f"{len(applied)} rows changed, {len(skipped)} skipped, "
          f"{len({a['file'] for a in applied})} files touched")
    for label, n in label_hist.most_common():
        print(f"  {label:20s} {n}")
    for s in skipped:
        print(f"  SKIP {s['file']} {s['key']}: {s['why']}")

    if not args.dry_run:
        lp = os.path.join(REPO, "build", "audit", "fix_canon_names_log.json")
        json.dump({"applied": applied, "skipped": skipped},
                  open(lp, "w"), ensure_ascii=False, indent=1)
        print(f"log -> {lp}")


if __name__ == "__main__":
    main()
