#!/usr/bin/env python3
"""patch_eboot_test_fontsize.py - TEST EBOOT: shrink WINDOW-FAMILY text size.

Run on top of the current deployed build:

    python tools/build_eboot.py                   # reproduce deployed build
    python tools/patch_eboot_test_fontsize.py 0.8 # -> build/EBOOT.test.BIN (Kf=0.8)
    # back up the game's EBOOT.BIN, copy build/EBOOT.test.BIN over it

SCOPE: the WTD window family - Robot Library list, KEY WORD / dictionary boxes,
menus. (The dialogue box is a different renderer - see the dead-end note below.)

BACKGROUND - the real size lever (v1's 0x00C41980 quad was a dead end).
  v1 scaled the billboard unit-quad 0x00C41980 -> ZERO visible change: those
  +/-1 values are a corner OFFSET added to the vertex, not a size multiplier.
  Tracing the window-family quad emitter FUN_005d0618 instead:
      glyph quad extent  f31 = glyph_metric * (fontsize/32)   [@0x5D0840/5C]
      glyph advance      via FUN_00a11f28: fontsize / cellsize
  BOTH read the same context field fontsize @+0x2c. So one knob - fontsize -
  scales glyph SIZE and letter-spacing together = genuinely smaller text that
  stays correctly spaced. fontsize is written once per string in the setup
  FUN_005cb970 (`stfs f1,0x2c(r3)` @0x5CB984). This patch redirects that store
  to a cave that multiplies the incoming fontsize by Kf first.

  NOTE the prior "engine font_size does nothing" finding was about the DIALOGUE
  renderer (0xA149E8), whose quad comes from a runtime buffer, not fontsize.
  For the window family, fontsize genuinely drives the quad - different renderer.

SAFETY - FUN_005cb970 is a LEAF that already uses the red zone (-0x10(r1)), so
  the standard spill template would corrupt it (the round-2 Library crash lesson).
  This cave makes NO stack writes: it uses r12 (dead in the setup) for the Kf
  address and f0 (dead until 0x5CB9B8) to hold Kf. Pure register work.

DIAGNOSTIC.
  - Robot Library / KEY WORD text visibly smaller AND still correctly spaced
    -> lever confirmed; pick a Kf, fold cave into eboot_code_patch.json. This is
    the answer to "spacing can only go so far" for the window family; the
    dialogue box would then need its own (harder) size work.
  - Text smaller but letters now overlap -> advance under-scaled somewhere; tune.
  - No change -> setup isn't on this path; re-trace.
  Start gentle (0.8). Kf=1.0 is a no-op.
"""
import os, struct, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from patch_eboot_menu_advance import b_word, d_form   # encoders

SEG0 = 0x10000
STORE_VA = 0x5CB984          # stfs f1,0x2c(r3)  (fontsize write in FUN_005cb970)
STORE_WORD = 0xD023002C
CAVE_VA = 0xC45C80           # free zero-run in the deployed build
KF_VA = 0xC45CB0             # Kf float constant (in the same free run)
STFS_F1_2C_R3 = 0xD023002C   # the original store, replayed inside the cave
FMULS_F1_F1_F0 = 0xEC210032  # fmuls f1,f1,f0


def foff(va):
    return va - SEG0


def build_cave(return_va):
    hi, lo = (KF_VA >> 16) & 0xFFFF, KF_VA & 0xFFFF
    assert lo < 0x8000
    seq = [
        d_form(15, 12, 0, hi),     # lis  r12,hi        (r12 dead in setup)
        d_form(24, 12, 12, lo),    # ori  r12,r12,lo
        d_form(48, 0, 12, 0),      # lfs  f0,0(r12)      f0 = Kf (f0 dead here)
        FMULS_F1_F1_F0,            # fmuls f1,f1,f0      fontsize *= Kf
        STFS_F1_2C_R3,             # stfs f1,0x2c(r3)    original store, scaled
    ]
    seq.append(b_word(CAVE_VA + len(seq) * 4, return_va))
    return seq


def main():
    Kf = float(sys.argv[1]) if len(sys.argv) > 1 else 0.8
    if not (0.5 <= Kf <= 1.0):
        raise SystemExit("Kf must be in [0.5, 1.0] (1.0 = no change); pass e.g. 0.8")
    src = os.path.join(REPO, "build", "EBOOT.patched.elf")
    if not os.path.exists(src):
        raise SystemExit("run tools/build_eboot.py first (need build/EBOOT.patched.elf)")
    d = bytearray(open(src, "rb").read())

    got = struct.unpack_from(">I", d, foff(STORE_VA))[0]
    if got == b_word(STORE_VA, CAVE_VA):
        # already folded into the deployed build - just retune the Kf constant
        struct.pack_into(">f", d, foff(KF_VA), Kf)
        print(f"fontsize cave already present (folded); retuned Kf -> {Kf} @{KF_VA:#x}")
    elif got == STORE_WORD:
        seq = build_cave(STORE_VA + 4)
        span = len(seq) * 4
        if any(d[foff(CAVE_VA):foff(CAVE_VA) + span]) or d[foff(KF_VA):foff(KF_VA) + 4] != b"\0\0\0\0":
            raise SystemExit("cave/constant region not zero - space taken?")
        for j, w in enumerate(seq):
            struct.pack_into(">I", d, foff(CAVE_VA + j * 4), w)
        struct.pack_into(">f", d, foff(KF_VA), Kf)
        struct.pack_into(">I", d, foff(STORE_VA), b_word(STORE_VA, CAVE_VA))
        print(f"window-family fontsize *= {Kf} (glyph size + spacing together); "
              f"cave @{CAVE_VA:#x}, Kf @{KF_VA:#x}")
    else:
        raise SystemExit(f"store site {STORE_VA:#x} = {got:08X}, expected stfs {STORE_WORD:08X} "
                         f"or an existing cave branch")

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
