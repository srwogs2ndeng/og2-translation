#!/usr/bin/env python3
"""fix_skilldesc.py - translate the SkillData description BODY segments that the
worksheet extraction skipped.

Six skill-description bodies in SkillData.dat carry a 1-byte formatting prefix
(0xa0/0x94/0x8e/0x8b/0x97...) and are NOT referenced by the SOFS offset table
(they're inline continuation segments, with their verb-ending tail in a separate,
offset-referenced string). fixh_grow correctly refuses non-referenced offsets, so
these never enter the worksheet and render as raw Japanese in-game.

Because they aren't repointable, we edit them OFFSET-PRESERVING: overwrite each
segment in place with [prefix][english][NUL pad] to the exact original byte length
(English is ~1/3 the byte size of the JP, so it fits with room). The apply step
compacts/relocates the string block, so we find each body by CONTENT (its
prefix+JP bytes, which survive unchanged) rather than by a fixed offset.

Inputs:  build/skilldesc_inline_en.json  [{prefix(hex), jp, en}, ...]
Target:  build/en/Logic/Dat/FixedData/SkillData.dat   (post-apply built file)

Run AFTER the SkillData worksheet apply (deploy.py calls it, like fix_dictionaries).
The verb-ending tails (0x000879 etc.) are handled normally via the worksheet.
"""
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    cfg = json.load(open(os.path.join(REPO, "build", "skilldesc_inline_en.json"), encoding="utf-8"))
    p = os.path.join(REPO, "build", "en", "Logic", "Dat", "FixedData", "SkillData.dat")
    data = bytearray(open(p, "rb").read())
    n = 0
    problems = []
    for e in cfg:
        pre = bytes.fromhex(e["prefix"])
        seg = pre + e["jp"].encode("utf-8")        # the exact bytes present in the file
        enb = e["en"].encode("utf-8")
        i = data.find(seg)
        if i < 0:
            problems.append(("not-found", e["en"][:40])); continue
        if data.count(seg) != 1:
            problems.append(("ambiguous", e["en"][:40])); continue
        room = len(seg) - len(pre)                 # bytes available for English
        if len(enb) > room:
            problems.append(("too-long %d>%d" % (len(enb), room), e["en"][:40])); continue
        # overwrite in place: prefix + english + NUL pad, exact same segment length
        new = pre + enb + b"\x00" * (len(seg) - len(pre) - len(enb))
        assert len(new) == len(seg)
        data[i:i + len(seg)] = new
        n += 1
    if len(data) != os.path.getsize(p):
        pass  # size unchanged (offset-preserving); assert below is the real gate
    assert len(data) == len(open(p, "rb").read())
    open(p, "wb").write(bytes(data))
    print("fix_skilldesc: patched %d/%d inline skill-description bodies (offset-preserving)" % (n, len(cfg)))
    for why, s in problems:
        print("  !!", why, repr(s))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
