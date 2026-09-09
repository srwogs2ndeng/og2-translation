#!/usr/bin/env python3
"""fix_helpdesc.py - translate the HelpData help-text bodies the extractor skipped.

142 HelpData help segments carry a 1-byte formatting prefix and are NOT
SOFS-referenced (inline continuation segments), so extraction skipped them and
they render as raw Japanese in-game (weapon attribute/ammo help, EN/PP/SP/SR
Points/weapon-gauge tooltips, etc.). Same mechanism + fix as tools/fix_skilldesc.py:
overwrite each segment offset-preserving with [prefix][english][NUL pad] to the
exact original byte length, finding it by CONTENT (prefix+JP bytes survive the
apply's block compaction unchanged).

Inputs:  build/helpdesc_inline_en.json   [{prefix(hex), jp, en}, ...]
Target:  build/en/Logic/Dat/FixedData/HelpData.dat   (post-apply built file)

Run AFTER the HelpData worksheet apply (deploy.py calls it, like fix_dictionaries).
"""
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    cfg_path = os.path.join(REPO, "build", "helpdesc_inline_en.json")
    if not os.path.isfile(cfg_path):
        print("fix_helpdesc: no build/helpdesc_inline_en.json (nothing to patch)")
        return 0
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    p = os.path.join(REPO, "build", "en", "Logic", "Dat", "FixedData", "HelpData.dat")
    orig_len = os.path.getsize(p)
    data = bytearray(open(p, "rb").read())
    n = 0
    problems = []
    for e in cfg:
        en = (e.get("en") or "").strip()
        if not en:
            continue
        pre = bytes.fromhex(e["prefix"])
        seg = pre + e["jp"].encode("utf-8")
        enb = en.encode("utf-8")
        room = len(seg) - len(pre)
        if len(enb) > room:
            problems.append(("too-long %d>%d" % (len(enb), room), en[:40])); continue
        repl = pre + enb + b"\x00" * (len(seg) - len(pre) - len(enb))
        # replace EVERY occurrence that is a COMPLETE segment (immediately NUL-terminated);
        # skip any occurrence that is a substring of a longer string (never NUL-terminated there).
        hits = 0
        i = 0
        while True:
            i = data.find(seg, i)
            if i < 0:
                break
            if i + len(seg) < len(data) and data[i + len(seg)] == 0:
                data[i:i + len(seg)] = repl
                hits += 1
            i += len(seg)
        if hits:
            n += 1
        else:
            problems.append(("not-found-as-segment", en[:40]))
    assert len(data) == orig_len, "offset-preserving invariant broken"
    open(p, "wb").write(bytes(data))
    print("fix_helpdesc: patched %d/%d inline help bodies (offset-preserving)" % (n, len(cfg)))
    if problems:
        print("  (%d not applied - left as-is, non-fatal:)" % len(problems))
        for why, s in problems[:20]:
            print("    -", why, repr(s))
    # partial success is fine (skipped ones just keep their current bytes); only a
    # hard error (missing input / broken invariant) raises above. Never abort the deploy.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
