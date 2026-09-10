#!/usr/bin/env python3
"""patch_eboot_glyphsize.py - shrink the on-screen GLYPH SIZE (not spacing).

Spacing/advance is handled separately (patch_eboot_advance / K-scale on the fmuls
advance sites). This patch attacks the glyph QUAD dimension instead.

RE finding (2026-07-05, r2/TOC resolved = 0xD5CAA8): the dialogue renderer
FUN_00a149e8 builds each glyph's quad from `f31`, the per-glyph render dimension
`f31 = frsp(fcfid(glyph_metric))` computed ONCE at 0xA14D10. Its 97 uses are all
`fsubs fX, f31, fY` - the quad-corner coordinates. The advance uses a SEPARATE path
(f0/f28 -> f30), so scaling f31 changes glyph SIZE without touching letter-spacing.
(The other two f31 writes are: 0xA14FE4 = epilogue restore of the callee-saved reg
 - NOT touched; 0xA16EF4 = a second path, optionally scaled with --also-a16.)

Mechanism = the same proven red-zone-safe code cave as patch_eboot_menu_advance:
redirect 0xA14D10 to a cave that redoes `frsp f31,f13`, multiplies f31 by KS (a
planted float), then branches back. The cave spills BOTH scratch regs it uses
(r12, f12) to the PPC64 red zone (r1-8 / r1-16) and makes no calls, so it is safe
regardless of the host frame.

This is an EXPERIMENT: whether scaling f31 shrinks glyphs *cleanly* (vs. distorting
them) depends on whether the fsubs offsets are f31-proportional - which only an
in-game look confirms. Rollback stays armed (build/EBOOT.GOOD.BIN).

Usage: patch_eboot_glyphsize.py in.elf out.elf [KS=0.85] [--also-a16]
"""
import sys, struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_64

SEG0 = 0x10000
SITE_MAIN = 0xA14D10          # frsp f31, f13   (primary glyph-dimension def)
SITE_A16  = 0xA16EF4          # fcfid f31, f0   (second path; optional)
FRSP_F31_F13 = 0xFFE06818     # frsp f31, f13
FCFID_F31_F0 = 0xFFE0069C     # fcfid f31, f0
CAVE_BASE = 0xC45D40          # free 264-byte zero-run (separate from advance caves)
CAVE_STRIDE = 0x30            # 12 instrs reserved per cave
KS_SLOT = CAVE_BASE           # planted KS float lives at the very start, code after


def foff(va): return va - SEG0
def b_word(frm, to): return 0x48000000 | ((to - frm) & 0x03FFFFFC)
def d_form(op, a, b, imm): return (op << 26) | (a << 21) | (b << 16) | (imm & 0xFFFF)
def ds_form(op, a, b, off): return (op << 26) | (a << 21) | (b << 16) | (off & 0xFFFC)

def fmuls(frt, fra, frc):     # fmuls frt,fra,frc  (op 59, xo 25)
    return (59 << 26) | (frt << 21) | (fra << 16) | (frc << 6) | (25 << 1)


def build_cave(cave_va, ks_addr, redo_word, return_va):
    """redo the original def, then f31 *= KS, restore, branch back."""
    hi = (ks_addr >> 16) & 0xFFFF
    lo = ks_addr & 0xFFFF
    assert lo < 0x8000, "KS addr low half must be < 0x8000 for addi"
    R = 12
    return [
        redo_word,                          # redo original (frsp/fcfid f31,...)
        ds_form(62, R, 1, (-8) & 0xFFFF),   # std   r12,-8(r1)    (red-zone spill)
        d_form(54, 12, 1, (-16) & 0xFFFF),  # stfd  f12,-16(r1)   (save f12)
        d_form(15, R, 0, hi),               # lis   r12,hi
        d_form(24, R, R, lo),               # ori   r12,r12,lo
        d_form(48, 12, R, 0),               # lfs   f12,0(r12)    (f12 = KS)
        fmuls(31, 31, 12),                  # fmuls f31,f31,f12   (glyph dim *= KS)
        d_form(50, 12, 1, (-16) & 0xFFFF),  # lfd   f12,-16(r1)   (restore f12)
        ds_form(58, R, 1, (-8) & 0xFFFF),   # ld    r12,-8(r1)    (restore r12)
        b_word(cave_va + 9 * 4, return_va), # b return
    ]


def main():
    inf, outf = sys.argv[1], sys.argv[2]
    KS = 0.85
    also_a16 = False
    for a in sys.argv[3:]:
        if a == "--also-a16": also_a16 = True
        else: KS = float(a)

    data = bytearray(open(inf, "rb").read())

    sites = [(SITE_MAIN, FRSP_F31_F13)]
    if also_a16: sites.append((SITE_A16, FCFID_F31_F0))

    # sanity: each site holds its expected instruction
    for va, expect in sites:
        got = struct.unpack_from(">I", data, foff(va))[0]
        if got != expect:
            raise SystemExit("site %#x is %08x, expected %08x" % (va, got, expect))

    # plant KS float at KS_SLOT, then caves start after a 0x10 pad (keeps float isolated)
    struct.pack_into(">f", data, foff(KS_SLOT), KS)
    code_base = CAVE_BASE + 0x10

    # cave region (float + code) must be zero
    need = 0x10 + len(sites) * CAVE_STRIDE
    for off in range(4, need):    # skip the 4 KS bytes we just wrote
        if data[foff(CAVE_BASE + off)] != 0:
            raise SystemExit("cave region not zero at %#x" % (CAVE_BASE + off))

    caves = []
    for i, (site, redo) in enumerate(sites):
        cave_va = code_base + i * CAVE_STRIDE
        for j, wd in enumerate(build_cave(cave_va, KS_SLOT, redo, site + 4)):
            struct.pack_into(">I", data, foff(cave_va + j * 4), wd)
        struct.pack_into(">I", data, foff(site), b_word(site, cave_va))
        caves.append((site, cave_va))

    open(outf, "wb").write(data)

    md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_64)
    print("KS=%.4f @ %#x   %d site(s)" % (KS, KS_SLOT, len(sites)))
    for site, cave_va in caves:
        ins = next(md.disasm(bytes(data[foff(site):foff(site) + 4]), site))
        print("\nsite %#x -> %s %s" % (site, ins.mnemonic, ins.op_str))
        for x in md.disasm(bytes(data[foff(cave_va):foff(cave_va) + 10 * 4]), cave_va):
            print("    %#010x: %-8s %s" % (x.address, x.mnemonic, x.op_str))
    print("\nwrote %s" % outf)


if __name__ == "__main__":
    main()
