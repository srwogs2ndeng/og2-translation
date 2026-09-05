#!/usr/bin/env python3
"""canon_sweep.py - JP-gated canonical-name normalization across all worksheets.

The autonomous fidelity-apply fixed only the specific rows a reviewer flagged,
leaving the same character/faction name spelled inconsistently elsewhere. This
completes the sweep deterministically and SAFELY:

  * JP-GATED: a row's `en` is only touched when its `jp` contains the katakana
    source name. This eliminates English-word collisions (wheel "rim" vs the
    character Lim, "a Brit" vs the pilot Bullet) - those rows have no katakana
    match so they are never touched.
  * FIT-GUARDED: the replacement is emit-simulated (normalize) and its UTF-8
    length compared to the row `slot`. LDBI talk files grow-and-repoint at
    deploy so growth is allowed there; every other container must fit or the row
    is SKIPPED and reported (never silently over-slot -> stays-Japanese).
  * Word-boundary matching so "Rim" doesn't hit "Rimfire" etc.

Usage:  python tools/canon_sweep.py            # dry-run: report only
        python tools/canon_sweep.py --apply    # write the worksheets
"""
import json, glob, os, re, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from worksheet import normalize

# (jp_source, wrong_variants, canon_en)  -- canon verified against build/canon_names.json
RULES = [
    ("リム",             ["Rim"],              "Lim"),      # heroine, canon "Lim"
    ("ガイアセイバーズ", ["Savers", "Saviours"], "Sabers"),   # only the 2nd word; faction "Gaia Sabers"
    ("ブリット",         ["Britt", "Brit"],    "Bullet"),   # Brooklyn "Bullet" Luckfield
    ("ゼゼーナン",       ["Zezenan"],          "Zezernan"), # Teniquette Zezernan
    ("セニア",           ["Senia"],            "Xenia"),
    ("リュウセイ",       ["Ryusei"],           "Ryuusei"),
]

def load_rows():
    files = {}
    for wp in glob.glob(os.path.join(REPO, "build/worksheets/**/*.json"), recursive=True):
        try:
            files[wp] = json.load(open(wp, encoding="utf-8"))
        except Exception:
            pass
    return files

def emit_bytes(en):
    return len(normalize(en).strip().encode("utf-8"))

def main(apply):
    files = load_rows()
    total_hits = total_applied = total_skipped = 0
    per_rule = {}
    changed_files = {}
    samples = []
    skipped = []
    for wp, d in files.items():
        if not isinstance(d, dict):
            continue
        is_talk = "logic/talk/" in wp.replace("\\", "/")
        touched = False
        for k, v in d.items():
            if not isinstance(v, dict):
                continue
            jp, en = v.get("jp", ""), v.get("en", "")
            if not en:
                continue
            for jpname, wrongs, canon in RULES:
                if jpname not in jp:
                    continue
                new = en
                for w in wrongs:
                    if w == canon:
                        continue
                    new = re.sub(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", canon, new)
                if new == en:
                    continue
                total_hits += 1
                per_rule[jpname] = per_rule.get(jpname, 0) + 1
                slot = v.get("slot", 0)
                fits = (not slot) or is_talk or emit_bytes(new) <= slot
                if not fits:
                    total_skipped += 1
                    skipped.append((os.path.relpath(wp, REPO), k, en[:50], new[:50], emit_bytes(new), slot))
                    break
                if len(samples) < 12:
                    samples.append((os.path.basename(wp), k, en[:46], new[:46]))
                v["en"] = new
                en = new
                total_applied += 1
                touched = True
                break
        if touched:
            changed_files[wp] = d
    print(f"JP-gated canon sweep: {total_hits} straggler rows, {total_applied} fixable, {total_skipped} skipped (over-slot)")
    print("per source name:", per_rule)
    print("--- samples ---")
    for s in samples:
        print(f"  {s[0]} {s[1]}: {s[2]!r} -> {s[3]!r}")
    if skipped:
        print(f"--- SKIPPED (would overflow slot; need manual shortening) ---")
        for s in skipped[:15]:
            print(f"  {s[0]} {s[1]}: {s[4]}B>{s[5]} {s[3]!r}")
    if apply:
        for wp, d in changed_files.items():
            txt = open(wp, encoding="utf-8").read()
            nl = txt.find("\n")
            ind = len(txt[nl+1:]) - len(txt[nl+1:].lstrip(" ")) if nl >= 0 else 0
            open(wp, "w", encoding="utf-8", newline="\n").write(json.dumps(d, ensure_ascii=False, indent=ind))
        print(f"APPLIED to {len(changed_files)} worksheets")
    else:
        print("(dry-run; pass --apply to write)")

if __name__ == "__main__":
    main("--apply" in sys.argv)
