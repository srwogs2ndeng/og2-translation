#!/usr/bin/env python3
"""patch_eboot_test_dlgterm.py - TEST EBOOT: fix DIALOGUE <term>-link slippage.

Run on top of the current deployed build, brackets ON so the terms link:

    python tools/build_eboot.py                       # deployed EBOOT
    python tools/patch_eboot_test_dlgterm.py           # -> build/EBOOT.test.BIN
    # back up the game's EBOOT.BIN, copy build/EBOOT.test.BIN over it
    # open a story scene with a linked term (ls021: "...the <Inspector Incident>...")

PROBLEM (screenshot 2026-07-10): inline glossary links in story dialogue
(<Inspector Incident>, <L5 Campaign>, <Shura Rebellion>, ...) render full-width
and reserve an oversized field, so the following text is shoved right and slips
off the box edge.

ROOT CAUSE (found by trace): the dialogue renderer advances its pen by the
term-FIELD width, not the term-TEXT width. Two sites compute that field width and
feed it straight into the pen accumulator f30:
    FUN_00a123f0:  fmuls f28,f13,f28  @0xA13BE4  ->  fadds f30,f30,f28  @0xA13BF0
    FUN_00a149e8:  fmuls f27,f13,f27  @0xA16108  ->  fadds f30,f30,f27  @0xA16114
  (f13 = cell_width * char_count, f28/f27 = [term+0x2c]). The already-deployed
  term patches (0xA13A84/0xA16EFC) scale the underline DRAW (stores to r17), NOT
  this pen advance - which is why the underline improved but the text still slips.
This patch scales the pen-advance term width by K (the deployed dialogue advance
constant @0xC45950 = 0.6), so a linked term advances the pen like plain text.

SAFETY: both hosts are FRAMED (they use positive r1 offsets: stfs f7,0xb4(r1);
lwz r6,0x138(r1)), so the red-zone spill cave is safe here (unlike the leaf
window-family width engines that crashed the Library). Caves live in the current
free run at 0xC45CB4 (the stale exp2 script's 0xC45C80 caves now collide with the
deployed fontsize cave).

DIAGNOSTIC (ls021 or any scene with a bracketed term, brackets ON):
  - terms sit tight, following text no longer slips off the edge -> FOUND IT;
    fold 0xA13BE4/0xA16108 into eboot_code_patch.json and set
    OG2_PLAINTEXT_TERMS=0 permanently = links restored, no slippage.
  - terms tighter but underline now too short/long -> the underline DRAW
    (0xA13A84/0xA16EFC) and this advance now disagree; retune (unlikely at 0.6).
  - no change -> pen advance not on this path for the scene shown; re-trace.
  - crash -> host wasn't framed after all; switch caves to dead-register form.
"""
import os, struct, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from patch_eboot_menu_advance import b_word, d_form, ds_form

SEG0 = 0x10000
K_ADDR = 0xC45950                 # deployed dialogue advance K (0.6)
# (site_va, original word, scale word 'fmuls fX,fX,f12', cave_va)
SITES = [
    (0xA13BE4, 0xEF8D0732, 0xEF9C0332, 0xC45CB4),   # f28 *= K  (FUN_00a123f0)
    (0xA16108, 0xEF6D06F2, 0xEF7B0332, 0xC45CE0),   # f27 *= K  (FUN_00a149e8)
]


def foff(va):
    return va - SEG0


def k_load(r=12):
    hi, lo = (K_ADDR >> 16) & 0xFFFF, K_ADDR & 0xFFFF
    assert lo < 0x8000
    return [d_form(15, r, 0, hi), d_form(24, r, r, lo), d_form(48, 12, r, 0)]


def cave(cave_va, redo, scale, return_va):
    # framed host -> red-zone spill (r1-8/r1-16) is safe scratch
    return ([redo,
             ds_form(62, 12, 1, (-8) & 0xFFFF),      # std  r12,-8(r1)
             d_form(54, 12, 1, (-16) & 0xFFFF)]      # stfd f12,-16(r1)
            + k_load(12)                              # f12 = K
            + [scale,                                 # fmuls fX,fX,f12
               d_form(50, 12, 1, (-16) & 0xFFFF),     # lfd  f12,-16(r1)
               ds_form(58, 12, 1, (-8) & 0xFFFF),     # ld   r12,-8(r1)
               b_word(cave_va + 9 * 4, return_va)])


def main():
    src = os.path.join(REPO, "build", "EBOOT.patched.elf")
    if not os.path.exists(src):
        raise SystemExit("run tools/build_eboot.py first")
    d = bytearray(open(src, "rb").read())
    K = struct.unpack_from(">f", d, foff(K_ADDR))[0]
    if not (0.4 <= K <= 0.9):
        raise SystemExit(f"K @{K_ADDR:#x} = {K}; wrong base?")

    for va, orig, scale, cv in SITES:
        got = struct.unpack_from(">I", d, foff(va))[0]
        if got != orig:
            raise SystemExit(f"site {va:#x}={got:08X}, expected {orig:08X}")
        seq = cave(cv, orig, scale, va + 4)
        if any(d[foff(cv):foff(cv) + len(seq) * 4]):
            raise SystemExit(f"cave {cv:#x} not zero - space taken?")
        for j, w in enumerate(seq):
            struct.pack_into(">I", d, foff(cv + j * 4), w)
        struct.pack_into(">I", d, foff(va), b_word(va, cv))
    print(f"dialogue term-advance *= {K:.2f} at {len(SITES)} sites (slippage fix)")

    out_elf = os.path.join(REPO, "build", "EBOOT.test.elf")
    out_bin = os.path.join(REPO, "build", "EBOOT.test.BIN")
    open(out_elf, "wb").write(bytes(d))
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_fself.py"), out_elf, out_bin], cwd=REPO)
    if r.returncode != 0:
        raise SystemExit("make_fself failed")
    print(f"done -> {out_bin}")
    print("deploy brackets-ON: OG2_PLAINTEXT_TERMS=0 deploy.py build Logic, then copy EBOOT.test.BIN over EBOOT.BIN")


if __name__ == "__main__":
    main()
