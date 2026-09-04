#!/usr/bin/env python3
"""patch_eboot_fitclamp.py - stop the engine from over-condensing overflowing text.

RE finding (2026-07-05, r2/TOC=0xD5CAA8): MULTIPLE text renderers compute a
HORIZONTAL condense-to-fit scale = box_width / text_width and multiply it into the
glyph x-positions, so a line wider than its box gets squished. English is wider than
the Japanese the boxes were sized for, so narrow boxes (Spirit "Eff" strip, Q&A list
items, objective lines) squish. Sites found:
  * 0xA15868 (FUN_00a149e8) : fdivs f26,f2,f1    -> f26 = 1.0/f1        (dialogue box)
  * 0xA1329C (FUN_00a123f0) : fdivs f26,f2,f1    -> f26 = 1.0/f1        (dialogue box)
  * 0x5CD2D4 (menu subsys)  : fdivs f0,f1,f5     -> f0  = box_w/text_w  (menu lists,
                              status "Eff" strip, etc.)
For fitting text the scale is >=1.0; only overflow drives it below 1.

FIX = clamp the scale to a FLOOR (default 0.8) right after each fdivs, via a
red-zone-safe cave that does scale = max(scale, FLOOR) with fsel. Because fitting
text is already >= FLOOR, the clamp is a NO-OP for normal text and ONLY relaxes the
over-condensed lines (they overflow their box slightly instead of turning to mush).

Usage: patch_eboot_fitclamp.py in.elf out.elf [FLOOR=0.8]
"""
import sys, struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_64

SEG0 = 0x10000
# (site_va, expected_word, target_freg) - the fdivs whose result is the fit scale
SITES = [
    (0xA15868, 0xEF420824, 26),   # fdivs f26,f2,f1  (dialogue a149e8)
    (0xA1329C, 0xEF420824, 26),   # fdivs f26,f2,f1  (dialogue a123f0)
    (0x5CD2D4, 0xEC012824, 0),    # fdivs f0,f1,f5   (menu subsystem)
]
CAVE_BASE = 0xC45D40              # free zero-run (264 bytes)
FLOOR_SLOT = CAVE_BASE
CODE_BASE = CAVE_BASE + 0x10
CAVE_STRIDE = 0x38                # 14 instrs reserved per cave (13 used)


def foff(va): return va - SEG0
def b_word(frm, to): return 0x48000000 | ((to - frm) & 0x03FFFFFC)
def d_form(op, a, b, imm): return (op << 26) | (a << 21) | (b << 16) | (imm & 0xFFFF)
def ds_form(op, a, b, off): return (op << 26) | (a << 21) | (b << 16) | (off & 0xFFFC)
def a_form(op, d, a, b, xo): return (op << 26) | (d << 21) | (a << 16) | (b << 11) | (xo << 1)
def fsel(d, a, c, b): return (63 << 26) | (d << 21) | (a << 16) | (b << 11) | (c << 6) | (23 << 1)


def build_cave(cave_va, floor_addr, redo_word, target, return_va):
    """redo the fdivs, then target = max(target, FLOOR) via fsel; scratch = f12/f13/r12
    (spilled to the red zone). target is never f12/f13 for our sites."""
    assert target not in (12, 13)
    hi = (floor_addr >> 16) & 0xFFFF
    lo = floor_addr & 0xFFFF
    assert lo < 0x8000
    return [
        redo_word,                          # redo original fdivs -> target = scale
        ds_form(62, 12, 1, -8),             # std   r12,-8(r1)
        d_form(54, 12, 1, -16),             # stfd  f12,-16(r1)
        d_form(54, 13, 1, -24),             # stfd  f13,-24(r1)
        d_form(15, 12, 0, hi),              # lis   r12,hi
        d_form(24, 12, 12, lo),             # ori   r12,r12,lo
        d_form(48, 12, 12, 0),              # lfs   f12,0(r12)   (f12 = FLOOR)
        a_form(59, 13, target, 12, 20),     # fsubs f13,target,f12  (f13 = target-FLOOR)
        fsel(target, 13, target, 12),       # fsel  target,f13,target,f12  (max)
        d_form(50, 13, 1, -24),             # lfd   f13,-24(r1)
        d_form(50, 12, 1, -16),             # lfd   f12,-16(r1)
        ds_form(58, 12, 1, -8),             # ld    r12,-8(r1)
        b_word(cave_va + 12 * 4, return_va) # b return
    ]


def main():
    inf, outf = sys.argv[1], sys.argv[2]
    FLOOR = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
    data = bytearray(open(inf, "rb").read())

    for va, expect, _ in SITES:
        got = struct.unpack_from(">I", data, foff(va))[0]
        if got != expect:
            raise SystemExit("site %#x is %08x, expected %08x" % (va, got, expect))

    struct.pack_into(">f", data, foff(FLOOR_SLOT), FLOOR)
    need = 0x10 + len(SITES) * CAVE_STRIDE
    for off in range(4, need):
        if data[foff(CAVE_BASE + off)] != 0:
            raise SystemExit("cave region not zero at %#x" % (CAVE_BASE + off))

    md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_64)
    print("FLOOR=%.3f @ %#x   %d site(s)" % (FLOOR, FLOOR_SLOT, len(SITES)))
    for i, (site, redo, target) in enumerate(SITES):
        cave_va = CODE_BASE + i * CAVE_STRIDE
        for j, wd in enumerate(build_cave(cave_va, FLOOR_SLOT, redo, target, site + 4)):
            struct.pack_into(">I", data, foff(cave_va + j * 4), wd)
        struct.pack_into(">I", data, foff(site), b_word(site, cave_va))
        print("\nsite %#x (f%d) -> b %#x" % (site, target, cave_va))
        for x in md.disasm(bytes(data[foff(cave_va):foff(cave_va) + 13 * 4]), cave_va):
            print("    %#010x: %-8s %s" % (x.address, x.mnemonic, x.op_str))

    open(outf, "wb").write(data)
    print("\nwrote %s" % outf)


if __name__ == "__main__":
    main()
