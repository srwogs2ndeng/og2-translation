#!/usr/bin/env python3
"""patch_eboot_fit_kaware.py - make the text auto-fit DECISION K-aware.

THE BUG (found live 2026-07-27 with the og2 tracer, library descriptions):
  Both text engines (FUN_00a123f0 primary, FUN_00a149e4 twin) decide "does this line fit
  its box?" by comparing a MEASURED width against maxWidth (obj+0x34). The measure is
  FLAT MONOSPACE at K=1.0: measured = nglyphs * fontsize (live: 1080 = 50*21.6, 712.8 =
  33*21.6, every value an exact multiple). But the DRAW uses our advance patch K=0.57
  (patch_eboot_advance.py), so real drawn width is ~0.57x the measure. Result: a 33-char
  line "overflows" a 672px box on paper (712.8 > 672) and is thrown into FIT-MODE, when it
  actually draws to 449px and fits with room.
  FIT-MODE is the JP equal-distribution justify: it sets a flag (stw 1,0x114(r1)), scales
  glyphs by ratio = maxW/measured, and DISTRIBUTES them evenly across the box on a path
  that ignores K -> those lines come out letter-SPREAD to the margin, while lines that
  "fit" draw compact at K. That is the per-line letter-spacing mismatch on screen.

THE FIX: scale the measured width by K FOR THE COMPARISON ONLY, in both engines:
    primary 0xa126d0  fcmpu cr6, f1(measured), f12(maxW)   -> cmp (f1*K) vs f12
    twin    0xa14ca4  fcmpu cr1, f12(maxW), f1(measured)   -> cmp f12 vs (f1*K)
  Fit-mode then triggers only when the DRAWN width would overflow (n > ~54 glyphs at
  fontsize 21.6). Lines up to that draw on the normal path = uniform K spacing.
  We do NOT scale f1 itself: fit-mode's ratio (fdivs f27,f12,f1 at 0xa13a30/0xa16eac)
  must stay computed from the UNSCALED measure, because fit-mode distributes at K=1.0 --
  scaling f1 would make genuinely-overlong lines overfill the box ~2x. Comparison-only
  keeps fit-mode self-consistent for the lines that still need it.
  K is read from the SAME constant the advance caves use (0xc45950), so the fit test
  and the draw can never drift apart if K is retuned.

SAFETY: cave spills r12 -> -8(r1) and f13 -> -0x10(r1) (red zone; the exact pattern the
  14 deployed advance caves use, no calls in between), sets ONLY the CR field the original
  fcmpu set, and returns to the instruction after the displaced fcmpu. Caves live in the
  proven zero run 0xc45928..0xc45d2b at 0xc45cc0 / 0xc45cf0 (48 bytes each), clear of
  every other deployed cave (#21 ..954, #22 ..c80, #24 ..ca4, #25 cb0..cb4).

    python tools/patch_eboot_fit_kaware.py        # edits build/eboot_code_patch.json
    python tools/build_eboot.py                   # then deploy EBOOT
"""
import json, struct, sys, binascii, shutil, os

JSON   = "build/eboot_code_patch.json"
K_VA   = 0xc45950          # advance K constant (shared with patch_eboot_advance caves)
SITES = [
    # (fcmpu va, its original word, cave va, crf, A, B, return va, label)
    (0xa126d0, 0xFF016000, 0xc45cc0, 6, "measK", "f12", 0xa126d4, "primary FUN_00a123f0"),
    (0xa14ca4, 0xFC8C0800, 0xc45cf0, 1, "f12", "measK", 0xa14ca8, "twin FUN_00a149e4"),
]

def std_(S, A, d):    return (62 << 26) | (S << 21) | (A << 16) | (d & 0xFFFC)
def ld_(D, A, d):     return (58 << 26) | (D << 21) | (A << 16) | (d & 0xFFFC)
def stfd(S, A, d):    return (54 << 26) | (S << 21) | (A << 16) | (d & 0xFFFF)
def lfd(D, A, d):     return (50 << 26) | (D << 21) | (A << 16) | (d & 0xFFFF)
def lfs(D, A, d):     return (48 << 26) | (D << 21) | (A << 16) | (d & 0xFFFF)
def addis(D, A, im):  return (15 << 26) | (D << 21) | (A << 16) | (im & 0xFFFF)
def ori(A, S, im):    return (24 << 26) | (S << 21) | (A << 16) | (im & 0xFFFF)
def fmuls(D, A, C):   return (59 << 26) | (D << 21) | (A << 16) | (C << 6) | (25 << 1)
def fcmpu(crf, A, B): return (63 << 26) | (crf << 23) | (A << 16) | (B << 11)
def b(cur, tgt):      return (18 << 26) | ((((tgt - cur) >> 2) & 0xFFFFFF) << 2)

def build(cave_va, crf, opA, opB, ret_va):
    reg = {"measK": 13, "f12": 12}
    w = [
        std_(12, 1, -8),          # spill r12
        stfd(13, 1, -0x10),       # spill f13
        addis(12, 0, K_VA >> 16),
        ori(12, 12, K_VA & 0xFFFF),
        lfs(13, 12, 0),           # f13 = K
        fmuls(13, 13, 1),         # f13 = measured * K
        fcmpu(crf, reg[opA], reg[opB]),   # the ORIGINAL compare, K-scaled measured
        ld_(12, 1, -8),
        lfd(13, 1, -0x10),
        b(cave_va + 9 * 4, ret_va),
    ]
    return b"".join(struct.pack(">I", x) for x in w)

EXPECT = ["std", "stfd", "lis", "ori", "lfs", "fmuls", "fcmpu", "ld", "lfd", "b"]

def verify(blob, cave_va, ret_va, crf):
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_64, CS_MODE_BIG_ENDIAN
    md = Cs(CS_ARCH_PPC, CS_MODE_64 | CS_MODE_BIG_ENDIAN)
    got = list(md.disasm(blob, cave_va)); ok = len(got) == len(EXPECT)
    for ins, want in zip(got, EXPECT):
        bad = ins.mnemonic != want
        ok &= not bad
        print("    0x%06x  %-7s %-26s%s" % (ins.address, ins.mnemonic, ins.op_str,
              "   <<< MISMATCH want %s" % want if bad else ""))
    if ("cr%d" % crf) not in got[6].op_str: print("    !! wrong CR field"); ok = False
    if ("0x%x" % ret_va) not in got[-1].op_str: print("    !! bad return"); ok = False
    return ok

def main():
    d = json.load(open(JSON, encoding="utf-8"))
    have = {p["off"] + 0x10000 for p in d["patch"]}
    orig = open("_rollback/EBOOT.elf.orig", "rb").read()
    new = []
    for site_va, orig_word, cave_va, crf, A, B, ret_va, label in SITES:
        w = struct.unpack_from(">I", orig, site_va - 0x10000)[0]
        if w != orig_word:
            sys.exit("!! %s: original word at 0x%x is %08X, expected %08X" % (label, site_va, w, orig_word))
        if site_va in have or cave_va in have:
            print("  = already patched: %s" % label); continue
        blob = build(cave_va, crf, A, B, ret_va)
        print("cave for %s @0x%06x (%d bytes):" % (label, cave_va, len(blob)))
        if not verify(blob, cave_va, ret_va, crf):
            sys.exit("!! verification FAILED - nothing written")
        assert cave_va + len(blob) <= 0xc45d2b, "cave overruns the zero run"
        new.append({"off": site_va - 0x10000,
                    "bytes": binascii.hexlify(struct.pack(">I", b(site_va, cave_va))).decode(),
                    "note": "fit-test K-aware: fcmpu -> cave (%s)" % label})
        new.append({"off": cave_va - 0x10000, "bytes": binascii.hexlify(blob).decode(),
                    "note": "fit-test cave: cmp (measured*K) vs maxW; K shared @0xc45950 (%s)" % label})
    if not new:
        print("nothing to do"); return 0
    if not os.path.exists(JSON + ".bak2"):
        shutil.copy2(JSON, JSON + ".bak2")
    d["patch"].extend(new)
    d["comment"] += (" [fit-test K-aware 2026-07-27: fcmpu at 0xa126d0/0xa14ca4 compare measured*K"
                     " vs maxW so fit-mode (equal-distribution justify, ignores K) only fires on"
                     " genuinely overlong lines; measure is flat monospace K=1.0]")
    json.dump(d, open(JSON, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s (+%d entries). next: python tools/build_eboot.py" % (JSON, len(new)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
