#!/usr/bin/env python3
"""patch_eboot_test_terrain_gap.py - TEST EBOOT: open the terrain label<->grade gap.

*** DEAD END - DO NOT RE-RUN (verdict 2026-07-09). ***
In-game result was DIAGNOSTIC outcome 3: the space-shifted grade letter overstrikes
the +/- modifier, which is drawn at a FIXED x, not relative to the letter. That
proves letter and modifier are both anchored to the terrain element at fixed
offsets, so no leading-space (and no WTD label move) can open the gap - both ride
the same anchor. The real lever is the renderer's grade-draw x-offset, which is
NOT statically locatable (the descriptor tree 0xCF1768->0xD8D360 is walked with
register-relative pointers; no lis/ori builds it in code). Kept only as the
reproduction of why this route is closed. Next step is RPCS3 runtime - see
docs/HANDOFF.md sec 5 "Renderer-level verdicts" for the exact watchpoint recipe.

Run on top of the current deployed build:

    python tools/build_eboot.py                    # reproduce deployed build
    python tools/patch_eboot_test_terrain_gap.py   # -> build/EBOOT.test.BIN (half-width space)
    python tools/patch_eboot_test_terrain_gap.py full   # full-width space (bigger gap)
    # back up the game's EBOOT.BIN, copy build/EBOOT.test.BIN over it

PROBLEM (stat screen Terrain Adj box): rows render jammed - "SkA+ A- A" - the
2-char WTD label (Sk/Ln/Se/Sp = the kanji 空/陸/海/宇) butts directly against the
EBOOT-drawn grade letter. Owner confirmed the grade is NOT in the WTD; the label
and grade share one cell and the gap is renderer-side.

APPROACH (no renderer trace needed): the grade letters are a rank-indexed table
of single full-width glyphs the renderer draws at the terrain anchor:
    0xC498F8 '－'  0xC49900 'Ｄ'  0xC49908 'Ｃ'  0xC49910 'Ｂ'  0xC49918 'Ａ'
    0xC49920 'Ｓ'
each in an 8-byte slot using only 4 (3-byte glyph + NUL). Prepending a SPACE to
each glyph (offset-preserving - the descriptor pointer is unchanged, the slot has
room) shifts the drawn grade right by one space, opening the label<->grade gap.
Because EVERY grade gets the same leading space, inter-column spacing is
unchanged - only the label<->grade1 gap grows (label is fixed, grade shifts).

These file offsets collide (VA-vs-file) with unrelated worksheet keys
(0xC49908->'Evade', 0xC49920->'Aim'), but build_eboot resolves those by JP-byte
match to OTHER offsets, so it will not overwrite this static grade table. This
tool patches build/EBOOT.patched.elf AFTER build_eboot, so the order is moot.

DIAGNOSTIC.
  - Gap opens, rows read "Sk A+ A- A" cleanly -> done; fold the 6 string edits
    into eboot_code_patch.json (data regions). If half-width is too tight, use
    `full`. If too wide, that's the trade - half is the gentle one.
  - No change / grade still jammed -> the renderer re-measures & re-anchors the
    string (centered/right-aligned), absorbing the leading space; fall back to
    the renderer x-offset trace.
  - Grades shift but the +/- modifier detaches -> the modifier is drawn at a
    fixed x, not relative to the letter; note it and reassess.
"""
import os, struct, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEG0 = 0x10000

# (file_va, original 3-byte glyph) - each in an 8-byte slot
GRADES = [
    (0xC498F8, bytes.fromhex("efbc8d")),  # －
    (0xC49900, bytes.fromhex("efbca4")),  # Ｄ
    (0xC49908, bytes.fromhex("efbca3")),  # Ｃ
    (0xC49910, bytes.fromhex("efbca2")),  # Ｂ
    (0xC49918, bytes.fromhex("efbca1")),  # Ａ
    (0xC49920, bytes.fromhex("efbcb3")),  # Ｓ
]
SLOT = 8


def main():
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    prefix = "　".encode("utf-8") if full else b" "   # full-width U+3000 or ASCII space
    src = os.path.join(REPO, "build", "EBOOT.patched.elf")
    if not os.path.exists(src):
        raise SystemExit("run tools/build_eboot.py first (need build/EBOOT.patched.elf)")
    d = bytearray(open(src, "rb").read())

    for va, glyph in GRADES:
        o = va - SEG0
        if bytes(d[o:o + len(glyph)]) != glyph:
            raise SystemExit(f"grade @{va:#x} = {d[o:o+3].hex()}, expected {glyph.hex()}")
        new = prefix + glyph + b"\x00"
        assert len(new) <= SLOT, "prefix overflows slot"
        d[o:o + SLOT] = new + b"\x00" * (SLOT - len(new))
    print(f"prepended {'full-width' if full else 'half-width'} space to {len(GRADES)} grade glyphs")

    out_elf = os.path.join(REPO, "build", "EBOOT.test.elf")
    out_bin = os.path.join(REPO, "build", "EBOOT.test.BIN")
    open(out_elf, "wb").write(bytes(d))
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_fself.py"), out_elf, out_bin], cwd=REPO)
    if r.returncode != 0:
        raise SystemExit("make_fself failed")
    print(f"done -> {out_bin}")
    print("deploy: back up the game's EBOOT.BIN, then copy EBOOT.test.BIN over it")


if __name__ == "__main__":
    main()
