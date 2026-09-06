#!/usr/bin/env python3
"""patch_eboot_advance.py - tighten dialogue letter-spacing in the OG2 EBOOT.

The dialogue layout routine FUN_00a149e4 accumulates a running x (f30) with a
per-glyph horizontal advance held in f0.  There are THREE advance-add sites,
one per glyph sub-path:

    0xA14F30  fadds f30,f30,f0   ; absent-glyph path (f0 = fixed 0x2c(r31) metric)
    0xA150E4  fadds f30,f30,f0   ; present-glyph main path (f0 = f28*width)
    0xA15F10  fadds f30,f30,f0   ; present-glyph alt path

At runtime every glyph advances by a uniform (too-wide) amount, so Latin text
renders on a gappy fixed grid.  In the English build the dialogue is all Latin,
so uniformly down-scaling the advance is the fix.

We redirect EACH `fadds f30,f30,f0` site to its own code cave (planted in the
RX seg0 zero-run at vaddr 0xC45930).  Each cave spills r12/f12, loads the scale
constant K, does `f0 *= K`, redoes `fadds f30,f30,f0`, restores, and branches
back.  Spilling both scratch regs makes each cave self-contained and safe
regardless of per-site liveness; nothing touches CR.

Usage:
    patch_eboot_advance.py in.elf out.elf [K=0.66]
"""
import sys, struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_64

SEG0_VBASE = 0x10000              # seg0.p_offset == 0, so file_off = vaddr - this
# Every `fadds f30,f30,f0` advance site across BOTH text-layout routines
# (FUN_00a123f0 and FUN_00a149e4); the message box is one of these two.
ADV_SITES  = [0xA12968, 0xA12B18, 0xA133C0, 0xA13950, 0xA13E58,   # FUN_00a123f0
              0xA14F30, 0xA150E4, 0xA15980, 0xA15F10, 0xA1637C]   # FUN_00a149e4
FADDS_F30  = 0xEFDE002A           # fadds f30,f30,f0
FMULS_K    = 0xEC000332           # fmuls f0,f0,f12
CAVE_BASE  = 0xC45930            # 16-aligned inside the 0xC45928 zero run (1027 bytes)
GPR_SPILL  = 0x48                 # 8-byte stack slots off r1 unused by BOTH layout
FPR_SPILL  = 0x50                 # functions (FUN_00a123f0 uses 0x158/0x160 - crash!)
CAVE_STRIDE = 0x30                # bytes reserved per cave (10 instrs = 0x28, padded)


def foff(va):
    return va - SEG0_VBASE


def b_word(from_va, to_va):
    return 0x48000000 | ((to_va - from_va) & 0x03FFFFFC)


def d_form(op, r1, r2, imm):
    return (op << 26) | (r1 << 21) | (r2 << 16) | (imm & 0xFFFF)

def ds_form(op, r1, r2, off):
    return (op << 26) | (r1 << 21) | (r2 << 16) | (off & 0xFFFC)


def build_cave(cave_va, kconst_va, return_va):
    hi = (kconst_va >> 16) & 0xFFFF
    lo = kconst_va & 0xFFFF
    assert lo < 0x8000
    R = 12
    seq = [
        ds_form(62, R, 1, GPR_SPILL),   # std   r12,0x160(r1)
        d_form(54, 12, 1, FPR_SPILL),   # stfd  f12,0x158(r1)
        d_form(15, R, 0, hi),           # lis   r12,hi
        d_form(24, R, R, lo),           # ori   r12,r12,lo
        d_form(48, 12, R, 0),           # lfs   f12,0(r12)
        FMULS_K,                        # fmuls f0,f0,f12
        FADDS_F30,                      # fadds f30,f30,f0
        d_form(50, 12, 1, FPR_SPILL),   # lfd   f12,0x158(r1)
        ds_form(58, R, 1, GPR_SPILL),   # ld    r12,0x160(r1)
        b_word(cave_va + 9 * 4, return_va),  # b return
    ]
    return seq


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    inf, outf = sys.argv[1], sys.argv[2]
    K = float(sys.argv[3]) if len(sys.argv) > 3 else 0.66
    data = bytearray(open(inf, "rb").read())

    # sanity: each site must currently be `fadds f30,f30,f0`
    for va in ADV_SITES:
        got = struct.unpack_from(">I", data, foff(va))[0]
        if got != FADDS_F30:
            raise SystemExit("site %#x is %08x, expected fadds f30,f30,f0" % (va, got))

    n = len(ADV_SITES)
    kconst_va = CAVE_BASE + n * CAVE_STRIDE          # K float after all caves
    # verify cave region + kconst are within the known zero run and all-zero
    for off in range(0, n * CAVE_STRIDE + 4):
        if data[foff(CAVE_BASE + off)] != 0:
            raise SystemExit("cave region not zero at %#x" % (CAVE_BASE + off))

    struct.pack_into(">f", data, foff(kconst_va), K)
    caves = []
    for i, site in enumerate(ADV_SITES):
        cave_va = CAVE_BASE + i * CAVE_STRIDE
        seq = build_cave(cave_va, kconst_va, site + 4)
        for j, w in enumerate(seq):
            struct.pack_into(">I", data, foff(cave_va + j * 4), w)
        struct.pack_into(">I", data, foff(site), b_word(site, cave_va))   # redirect
        caves.append((site, cave_va))

    open(outf, "wb").write(data)

    # --- verify by disassembling every redirect + cave ---
    md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_64)
    print("K=%s (%s)  kconst@%#x  %d sites" % (K, struct.pack(">f", K).hex(), kconst_va, n))
    for site, cave_va in caves:
        print("\nsite %#x -> cave %#x" % (site, cave_va))
        for ins in md.disasm(bytes(data[foff(site):foff(site) + 4]), site):
            print("  redirect 0x%08X: %s %s" % (ins.address, ins.mnemonic, ins.op_str))
        for ins in md.disasm(bytes(data[foff(cave_va):foff(cave_va) + 10 * 4]), cave_va):
            print("    0x%08X: %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
    print("\nKconst @ %#x = %s" % (kconst_va, struct.unpack(">f", data[foff(kconst_va):foff(kconst_va)+4])[0]))
    print("wrote %s (%d bytes)" % (outf, len(data)))


if __name__ == "__main__":
    main()
