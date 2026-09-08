#!/usr/bin/env python3
"""patch_eboot_test_unitlist_kwbox.py - TEST EBOOT v2 for the two open renderer
issues (Library letter-spacing + keyword-box term fields).

Run on top of the current deployed build (NOT the pristine ELF):

    python tools/build_eboot.py                       # reproduce deployed build
    python tools/patch_eboot_test_unitlist_kwbox.py   # -> build/EBOOT.test.BIN
    # back up the game's EBOOT.BIN, copy build/EBOOT.test.BIN over it

v3 fix after the round-2 CRASH (Library open): the two width engines are LEAF
functions that keep live data in the red zone - 0xA11F28 saves r31 at -8(r1)
for its whole body (no stack frame), so v2's standard cave spill
`std r12,-8(r1)` corrupted the saved r31 and crashed the caller on return.
*** LESSON: red-zone spills are only safe when the host has a real stack
frame; in leaf functions scan for negative-r1 offsets first. ***
The v3 exp3 caves touch NO memory: r6 and f0 are dead at both sites (every
loop path rewrites them before any read; both volatile at the call boundary),
so K is loaded via r6/f0 directly.

v2 changes after the 2026-07-08 screenshot round:
  - v1 exp1 (edge-fade neutralization in FUN_006205e4) produced NO visible
    change in the Robot Library list -> that widget is not these screens.
    DROPPED (v1's 4 in-place words are no longer applied).
  - The screenshots showed the REAL defect: ALL Library/window text renders
    with full-width advance ("A l t a i r l i o n", gappy keyword text) -
    the WTD window family was never K-patched at all. The selected unit-list
    row is full-width; unselected rows are that same overwide string
    uniformly squeezed into the column -> overlap mush.

EXPERIMENT 3 (new, the main event) - window-family advance/measure K-scale.
  The whole WTD window subsystem (Library, keyword box, robot/pilot library
  lists) gets its text advance from two string-width engines:
      FUN_00a11f28 (length-bounded run)  - fmadds f1,f12,f3,f1 @ 0xA120F4
      FUN_00a12190 (NUL-terminated)      - fmadds f1,f12,f3,f1 @ 0xA1234C
  where f12 = fontsize/cell (loop-invariant), f3 = glyph width byte, and f1
  accumulates the string width in pixels. Their ONLY callers are the two
  window-family wrappers at 0x5CDED0/0x5CDEF8 (verified: no dialogue overlap).
  The walker advances its pen by the returned width, so scaling here fixes
  measure AND draw coherently for the entire family.
  Each fmadds is redirected to a cave computing f1 += f12*f3*K instead
  (K read from 0xC45950, currently 0.6). Caves @0xC45CD0 and @0xC45D40.
  f3 is dead after the site (recomputed per char); K is loaded through r6/f0,
  both dead at the sites - the caves make NO stack/memory writes (see the
  leaf-function red-zone lesson above).
  Expected: Robot Library names + KEY WORD body text tighten to dialogue-like
  spacing; unselected-row squeeze relaxes (measured width also drops by K).
  Check for side effects anywhere in Library/menus that right-aligns or
  centers text (measure users).

EXPERIMENT 2 (kept from v1, still awaiting a dialogue-term check) - the two
  unpatched term-field width multiplies in the DIALOGUE renderers:
      0xA13BE4  fmuls f28,f13,f28  (FUN_00a123f0) -> cave @0xC45C80
      0xA16108  fmuls f27,f13,f27  (FUN_00a149e8) -> cave @0xC45CA8
  width = [term+0x34](char count) * f26 * base; rescaled by K to match the
  two already-deployed sibling sites (0xA13A84/0xA16EFC). Check story
  dialogue with an underlined <term>: underline must hug the text, no
  regression vs the current build.

Flags: --no-window (skip exp3), --no-kwbox (skip exp2).
"""
import os, struct, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from patch_eboot_menu_advance import b_word, d_form, ds_form   # cave helpers

SEG0 = 0x10000
K_ADDR = 0xC45950               # deployed K constant (currently 0.6)

# exp2: (site_va, expected_original=redo instr, scale instr, cave_va)
KWBOX_SITES = [
    (0xA13BE4, 0xEF8D0732, 0xEF9C0332, 0xC45C80),  # fmuls f28,f13,f28 ; f28*=K
    (0xA16108, 0xEF6D06F2, 0xEF7B0332, 0xC45CA8),  # fmuls f27,f13,f27 ; f27*=K
]

# exp3: (site_va, expected_original fmadds f1,f12,f3,f1, cave_va)
WINDOW_SITES = [
    (0xA120F4, 0xEC2C08FA, 0xC45CD0),
    (0xA1234C, 0xEC2C08FA, 0xC45D40),
]

FMULS_F3_F12_F3 = 0xEC6C00F2    # fmuls f3,f12,f3
FMULS_F3_F3_F0 = 0xEC630032     # fmuls f3,f3,f0
FADDS_F1_F1_F3 = 0xEC21182A     # fadds f1,f1,f3
R_SCRATCH = 6                   # dead at both exp3 sites (rewritten each loop)


def foff(va):
    return va - SEG0


def k_load(into_f, scratch_r=12):
    hi, lo = (K_ADDR >> 16) & 0xFFFF, K_ADDR & 0xFFFF
    assert lo < 0x8000
    return [
        d_form(15, scratch_r, 0, hi),               # lis  r12,hi
        d_form(24, scratch_r, scratch_r, lo),       # ori  r12,r12,lo
        d_form(48, into_f, scratch_r, 0),           # lfs  fX,0(r12)
    ]


def cave_mul_scale(cave_va, redo, scale, return_va):
    """v1 template: redo original fmuls, result *= K (f12/r12 red-zone)."""
    return ([redo,
             ds_form(62, 12, 1, (-8) & 0xFFFF),     # std  r12,-8(r1)
             d_form(54, 12, 1, (-16) & 0xFFFF)]     # stfd f12,-16(r1)
            + k_load(12)
            + [scale,
               d_form(50, 12, 1, (-16) & 0xFFFF),   # lfd  f12,-16(r1)
               ds_form(58, 12, 1, (-8) & 0xFFFF),   # ld   r12,-8(r1)
               b_word(cave_va + 9 * 4, return_va)])


def cave_madds_scale(cave_va, return_va):
    """exp3: replace fmadds f1,f12,f3,f1 with f1 += f12*f3*K.
    NO stack use: the hosts are leaf functions with live red-zone slots
    (0xA11F28 keeps saved r31 at -8(r1) - v2 clobbered it and crashed).
    f3 dead after site; r6/f0 dead at the sites (rewritten before any read)."""
    return ([FMULS_F3_F12_F3]                       # f3 = f12*f3
            + k_load(0, R_SCRATCH)                  # f0 = K (via r6)
            + [FMULS_F3_F3_F0,                      # f3 *= K
               FADDS_F1_F1_F3,                      # f1 += f3
               b_word(cave_va + 6 * 4, return_va)])


def main():
    do_window = "--no-window" not in sys.argv
    do_kw = "--no-kwbox" not in sys.argv
    src = os.path.join(REPO, "build", "EBOOT.patched.elf")
    if not os.path.exists(src):
        raise SystemExit("run tools/build_eboot.py first (need build/EBOOT.patched.elf)")
    d = bytearray(open(src, "rb").read())

    K = struct.unpack_from(">f", d, foff(K_ADDR))[0]
    if not (0.4 <= K <= 0.9):
        raise SystemExit(f"K @{K_ADDR:#x} reads {K} - wrong base?")

    def apply_cave(va, exp, cave, seq):
        got = struct.unpack_from(">I", d, foff(va))[0]
        if got != exp:
            raise SystemExit(f"site {va:#x}: {got:08X}, expected {exp:08X}")
        if any(d[foff(cave):foff(cave) + len(seq) * 4]):
            raise SystemExit(f"cave {cave:#x} not zero - space taken?")
        for j, w in enumerate(seq):
            struct.pack_into(">I", d, foff(cave + j * 4), w)
        struct.pack_into(">I", d, foff(va), b_word(va, cave))

    if do_kw:
        for va, exp, scale, cave in KWBOX_SITES:
            apply_cave(va, exp, cave, cave_mul_scale(cave, exp, scale, va + 4))
        print(f"exp2 dialogue term-field siblings: {len(KWBOX_SITES)} sites, K={K:.2f}")

    if do_window:
        for va, exp, cave in WINDOW_SITES:
            apply_cave(va, exp, cave, cave_madds_scale(cave, va + 4))
        print(f"exp3 window-family measure/advance: {len(WINDOW_SITES)} sites, K={K:.2f}")

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
