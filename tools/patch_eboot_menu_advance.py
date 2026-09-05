#!/usr/bin/env python3
"""patch_eboot_menu_advance.py - tighten letter-spacing in the MENU/STATUS/SPIRIT
text renderers (not the dialogue box, which is already fixed).

The dialogue fix redirected ONE `fmuls f0,f28,f0` advance-multiply site
(0xA150D8) to a code cave that scales the per-glyph advance by K=0.66. The
status/menu/spirit/story renderers each compute their advance with the SAME
`fmuls f0,f28,f0` instruction but were never scaled, so English (Latin) text
overruns the fixed Japanese-sized slots and overlaps.

We redirect each of those sites to its own cave that redoes the fmuls, scales
f0 by K (reusing the existing K constant at 0xC45950), and branches back.

SAFETY (the earlier crash came from an unsafe stack spill): each cave saves AND
restores BOTH scratch regs it touches (r12, f12) to the PPC64 red zone (negative
offsets below r1). The cave makes no calls, so the red zone is free - PROVIDED
the host function has a real stack frame (stdu). *** LEAF-FUNCTION TRAP
(2026-07-08 Library crash): leaf hosts may keep LIVE data in the red zone -
0xA11F28 stores its saved r31 at -8(r1) for its whole body. Before reusing this
template, scan the host for negative-r1 offsets; if it's a leaf, use provably
dead registers instead of spilling (see patch_eboot_test_unitlist_kwbox.py). ***

Usage: patch_eboot_menu_advance.py in.elf out.elf [K_addr=0xC45950] [site,site,...]
"""
import sys, struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_64

SEG0 = 0x10000
FMULS_ADV = 0xEC1C0032           # fmuls f0,f28,f0 (the advance = width*scale site)
CAVE_BASE = 0xC45B68             # free zero-run (0xC45960 is occupied by the dialogue caves)
CAVE_STRIDE = 0x28               # 10 instrs reserved per cave (9 used)
K_ADDR = 0xC45950                # existing K=0.66 float constant

# candidate menu/status/spirit/story renderers (fmuls advance sites), excluding the
# two dialogue renderers (0xa123f4 / 0xa149e8) which are already correct.
DEFAULT_SITES = [0x957418, 0xC04358, 0xC04B90, 0xC056C4, 0xC05F0C]


def foff(va): return va - SEG0
def b_word(frm, to): return 0x48000000 | ((to - frm) & 0x03FFFFFC)
def d_form(op, a, b, imm): return (op << 26) | (a << 21) | (b << 16) | (imm & 0xFFFF)
def ds_form(op, a, b, off): return (op << 26) | (a << 21) | (b << 16) | (off & 0xFFFC)


def build_cave(cave_va, k_addr, return_va):
    hi = (k_addr >> 16) & 0xFFFF
    lo = k_addr & 0xFFFF
    assert lo < 0x8000
    R = 12
    seq = [
        FMULS_ADV,                          # fmuls f0,f28,f0  (redo original advance)
        ds_form(62, R, 1, (-8) & 0xFFFF),   # std   r12,-8(r1)   (red-zone spill)
        d_form(54, 12, 1, (-16) & 0xFFFF),  # stfd  f12,-16(r1)  (save f12)
        d_form(15, R, 0, hi),               # lis   r12,hi
        d_form(24, R, R, lo),               # ori   r12,r12,lo
        d_form(48, 12, R, 0),               # lfs   f12,0(r12)   (f12 = K)
        0xEC000332,                         # fmuls f0,f0,f12    (advance *= K)
        d_form(50, 12, 1, (-16) & 0xFFFF),  # lfd   f12,-16(r1)  (restore f12)
        ds_form(58, R, 1, (-8) & 0xFFFF),   # ld    r12,-8(r1)   (restore r12)
        b_word(cave_va + 9 * 4, return_va), # b return
    ]
    return seq


def main():
    inf, outf = sys.argv[1], sys.argv[2]
    sites = DEFAULT_SITES
    data = bytearray(open(inf, "rb").read())

    # sanity: every target site must currently be `fmuls f0,f28,f0`
    for va in sites:
        got = struct.unpack_from(">I", data, foff(va))[0]
        if got != FMULS_ADV:
            raise SystemExit("site %#x is %08x, expected fmuls f0,f28,f0" % (va, got))
    # verify K constant present
    K = struct.unpack_from(">f", data, foff(K_ADDR))[0]
    # cave region must be zero
    need = len(sites) * CAVE_STRIDE
    for off in range(0, need):
        if data[foff(CAVE_BASE + off)] != 0:
            raise SystemExit("cave region not zero at %#x" % (CAVE_BASE + off))

    caves = []
    for i, site in enumerate(sites):
        cave_va = CAVE_BASE + i * CAVE_STRIDE
        for j, wd in enumerate(build_cave(cave_va, K_ADDR, site + 4)):
            struct.pack_into(">I", data, foff(cave_va + j * 4), wd)
        struct.pack_into(">I", data, foff(site), b_word(site, cave_va))
        caves.append((site, cave_va))

    open(outf, "wb").write(data)

    md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_64)
    print("K=%.4f @ %#x   %d sites" % (K, K_ADDR, len(sites)))
    for site, cave_va in caves:
        ins = next(md.disasm(bytes(data[foff(site):foff(site) + 4]), site))
        print("\nsite %#x -> %s %s" % (site, ins.mnemonic, ins.op_str))
        for x in md.disasm(bytes(data[foff(cave_va):foff(cave_va) + 10 * 4]), cave_va):
            print("    %#010x: %-8s %s" % (x.address, x.mnemonic, x.op_str))
    print("\nwrote %s" % outf)


if __name__ == "__main__":
    main()
