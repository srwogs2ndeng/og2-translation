#!/usr/bin/env python3
"""patch_eboot_test_uline.py - TEST EBOOT: tighten the <U=> underline field width.

The make-or-break probe for restoring library term links (2026-07-10).

Run on top of the current deployed build, WITH brackets on so links exist:

    OG2_PLAINTEXT_TERMS=0 python tools/deploy.py build Logic   # brackets ON
    python tools/build_eboot.py                                # deployed EBOOT
    python tools/patch_eboot_test_uline.py                     # -> build/EBOOT.test.BIN
    # back up the game's EBOOT.BIN, copy build/EBOOT.test.BIN over it
    # (deploy the Logic archive too - it carries the brackets-on .dat files)

BACKGROUND. The library/keyword term links are drawn by a SEPARATE renderer
from plain glyphs (owner confirmed in-game: term text ignores the Kf=0.9
spacing patch and reserves an underline field ~1.67x the text width -> the
line goes wide+gappy). The window-family markup command set is a 19-entry tag
jump table (dispatch @0x5D25xx). Handler 0x5CC068 is the `<U...>` case (checks
byte1==0x55 'U'); its `<U=>` body (0x5CC120) computes the underline QUAD from
the widget's own field:
    lfs f27,0x80(r31); lfs f28,0x84(r31); lfs f31,0x20c8(r2)   (0x20c8(r2)=unit const)
    fmuls f8,f27,f31    @0x5CC1E0   -> stfs f8,0x80(r1)   (extent from +0x80)
    fmuls f29,f28,f31   @0x5CC1E8   -> stfs f29,0x84(r1)  (extent from +0x84)
    ... bl 0x6ba45c   (draw the underline quad)
So the field width = [widget+0x80] * const. 1.67 ~= 1/0.6, and 0.6 is exactly
the deployed Latin-advance K - i.e. the underline is measured full-width while
the text now advances half-width. This patch scales the +0x80 multiply by K
(the deployed 0.6 @0xC45950) so the underline field shrinks to match the text.

Host 0x5CC068 has a REAL stack frame (stdu r1,-0x150), so the red-zone spill
template is safe here (unlike the leaf width-engines that crashed round 2).

DIAGNOSTIC (open KEY WORD box on an entry with an inline link, e.g. the DC /
EOT keyword bodies):
  - underline shrinks to hug the term text, line no longer gappy
      -> FOUND IT. This handler renders the keyword-box links. Fold @0x5CC1E0
         into eboot_code_patch.json and flip OG2_PLAINTEXT_TERMS=0 permanently
         = full fix (tight text + working links). If the line tightens but the
         underline is now a hair SHORT, +0x80 is the horizontal extent and 0.6
         slightly overshoots - retune K up (this script's --k).
  - underline unchanged, still ~1.67x -> the keyword `<Name>` link does NOT
      route through the `<U=>` handler; it uses a different/default tag case.
      Re-probe the other jump-table handlers (0x5CABD8/0x5CC8FC/0x5D1908/...).
  - the UNDERLINE got thinner (vertically) instead of shorter -> +0x80 is the
      thickness, not the width; switch the site to 0x5CC1E8 (+0x84).
  - crash -> unexpected (host is framed); revert and report.
"""
import os, struct, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from patch_eboot_menu_advance import b_word, d_form, ds_form   # cave helpers

SEG0 = 0x10000
K_ADDR = 0xC45950            # deployed K constant (0.6)
SITE_VA = 0x5CC1E0           # fmuls f8,f27,f31  (underline extent from widget+0x80)
SITE_ORIG = 0xED1B07F2
SCALE = 0xED080332          # fmuls f8,f8,f12   (f8 *= K; frD=frA=8, frC=12)
CAVE_VA = 0xC45D40          # free zero-run in the deployed build


def foff(va):
    return va - SEG0


def k_load(into_f, scratch_r=12):
    hi, lo = (K_ADDR >> 16) & 0xFFFF, K_ADDR & 0xFFFF
    assert lo < 0x8000
    return [d_form(15, scratch_r, 0, hi),           # lis  r12,hi
            d_form(24, scratch_r, scratch_r, lo),   # ori  r12,r12,lo
            d_form(48, into_f, scratch_r, 0)]       # lfs  fX,0(r12)


def build_cave(return_va):
    # red-zone spill is safe: host 0x5CC068 has a real frame (stdu -0x150)
    return ([SITE_ORIG,                              # redo fmuls f8,f27,f31
             ds_form(62, 12, 1, (-8) & 0xFFFF),      # std  r12,-8(r1)
             d_form(54, 12, 1, (-16) & 0xFFFF)]      # stfd f12,-16(r1)
            + k_load(12)
            + [SCALE,                                # fmuls f8,f8,f12
               d_form(50, 12, 1, (-16) & 0xFFFF),    # lfd  f12,-16(r1)
               ds_form(58, 12, 1, (-8) & 0xFFFF),    # ld   r12,-8(r1)
               b_word(CAVE_VA + 9 * 4, return_va)])


def main():
    src = os.path.join(REPO, "build", "EBOOT.patched.elf")
    if not os.path.exists(src):
        raise SystemExit("run tools/build_eboot.py first (need build/EBOOT.patched.elf)")
    d = bytearray(open(src, "rb").read())

    K = struct.unpack_from(">f", d, foff(K_ADDR))[0]
    if not (0.4 <= K <= 0.9):
        raise SystemExit(f"K @{K_ADDR:#x} reads {K} - wrong base?")
    got = struct.unpack_from(">I", d, foff(SITE_VA))[0]
    if got != SITE_ORIG:
        raise SystemExit(f"site {SITE_VA:#x} = {got:08X}, expected {SITE_ORIG:08X}")

    seq = build_cave(SITE_VA + 4)
    if any(d[foff(CAVE_VA):foff(CAVE_VA) + len(seq) * 4]):
        raise SystemExit(f"cave {CAVE_VA:#x} not zero - space taken?")
    for j, w in enumerate(seq):
        struct.pack_into(">I", d, foff(CAVE_VA + j * 4), w)
    struct.pack_into(">I", d, foff(SITE_VA), b_word(SITE_VA, CAVE_VA))
    print(f"<U=> underline field width *= {K:.2f}  (site {SITE_VA:#x}, cave {CAVE_VA:#x})")

    out_elf = os.path.join(REPO, "build", "EBOOT.test.elf")
    out_bin = os.path.join(REPO, "build", "EBOOT.test.BIN")
    open(out_elf, "wb").write(bytes(d))
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_fself.py"), out_elf, out_bin], cwd=REPO)
    if r.returncode != 0:
        raise SystemExit("make_fself failed")
    print(f"done -> {out_bin}")
    print("deploy: back up the game's EBOOT.BIN, copy EBOOT.test.BIN over it;")
    print("        also deploy the brackets-on Logic build so links exist to test.")


if __name__ == "__main__":
    main()
