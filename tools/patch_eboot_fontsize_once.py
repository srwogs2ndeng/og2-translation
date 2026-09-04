#!/usr/bin/env python3
"""patch_eboot_fontsize_once.py - make the window-family fontsize cave IDEMPOTENT.

THE BUG (found live 2026-07-27 with the og2 tracer):
  The original cave (eboot_code_patch.json #24) hooks `stfs f1,0x2c(r3)` inside
  SetFontSize (FUN_005cb970) and unconditionally does `f1 *= Kf`. Its design note
  assumed "fontsize is written ONCE per string" -- but the engine repeatedly
  RE-APPLIES an element's existing size (captured live at 0x82edc0 AND 0x82f088,
  plus the render pass at 0x5cec**/0x5d2***). Each re-apply multiplied by Kf AGAIN,
  so the size decayed geometrically:
        24 -> 21.6 -> 19.44 -> 17.496 -> 15.7464      (Kf = 0.9, x4)
  Those are the exact values measured off a live library description. Elements that
  got re-set 4x rendered at 66% width = the "unreadable tiny text".

THE FIX:
  A re-apply passes back the value ALREADY stored in obj[0x2c]. So compare the
  incoming f1 against obj[0x2c] and skip the scale when they match => Kf is applied
  exactly ONCE, at the source, and re-applies become the no-ops they were meant to be.

    lfs   f0, 0x2c(r3)     ; current stored size
    fcmpu cr7, f1, f0
    beq   cr7, store       ; re-apply -> store unchanged (NO scale)
    lis   r12, 0xc4
    ori   r12, r12, 0x5cb0
    lfs   f0, 0(r12)       ; Kf
    fmuls f1, f1, f0
  store:
    stfs  f1, 0x2c(r3)
    b     0x5cb988

SAFETY (verified against the unpatched EBOOT):
  * f0  is DEAD until 0x5cb9b8 (first written by `fmuls f0,f1,f3`) -> free to use.
  * NO CR field is read anywhere in FUN_005cb970 -> cr7 free to clobber.
  * r12 is dead in the setup (as the original cave already relied on).
  * NO stack writes -- FUN_005cb970 is a leaf using the red zone at -0x10(r1);
    the standard spill template would corrupt it (the round-2 Library crash).
  * NaN/garbage in obj[0x2c] -> fcmpu sets FU, beq NOT taken -> scales. Safe default.

Cave grows 24 -> 36 bytes at va 0xc45c80; Kf constant lives at 0xc45cb0, so the
36 bytes fit with 12 to spare. Idempotent: re-running detects the new cave.

    python tools/patch_eboot_fontsize_once.py [--kf 0.9]
"""
import json, struct, sys, binascii, shutil, os

JSON = "build/eboot_code_patch.json"
CAVE_VA = 0xc45c80
KF_VA   = 0xc45cb0
RET_VA  = 0x5cb988

def lfs(D, A, d):    return (48 << 26) | (D << 21) | (A << 16) | (d & 0xFFFF)
def stfs(S, A, d):   return (52 << 26) | (S << 21) | (A << 16) | (d & 0xFFFF)
def fcmpu(crf, A, B):return (63 << 26) | (crf << 23) | (A << 16) | (B << 11)
def bc(BO, BI, bd):  return (16 << 26) | (BO << 21) | (BI << 16) | (bd & 0xFFFC)
def addis(D, A, im): return (15 << 26) | (D << 21) | (A << 16) | (im & 0xFFFF)
def ori(A, S, im):   return (24 << 26) | (S << 21) | (A << 16) | (im & 0xFFFF)
def fmuls(D, A, C):  return (59 << 26) | (D << 21) | (A << 16) | (C << 6) | (25 << 1)
def b(cur, tgt):     return (18 << 26) | (((tgt - cur) >> 2) & 0xFFFFFF) << 2

def fsubs(D, A, B):  return (59 << 26) | (D << 21) | (A << 16) | (B << 11) | (20 << 1)
def fsel(D, A, C, B):return (63 << 26) | (D << 21) | (A << 16) | (B << 11) | (C << 6) | (23 << 1)

def build():
    # HARD FLOOR relative to the Y size: x = max(x*Kf, y*Kf).
    # An equality test against obj[0x2c] proved too fragile -- other paths pass values that
    # aren't bit-identical to what's stored, so they still scaled and the decay reached 0.9^9
    # (measured live). A y-relative floor cannot be evaded by ANY path:
    #   square input (x == y, the normal font case) -> max(y*Kf*Kf, y*Kf) = y*Kf
    #   re-apply of y*Kf                            -> max(y*Kf*Kf, y*Kf) = y*Kf   (STABLE)
    # so Kf lands exactly ONCE no matter how many times SetFontSize is called.
    # Non-square callers (0x058468 passes 1280x1 etc -- this setter is also used for
    # non-font objects) keep x*Kf, i.e. unchanged from the original cave's behaviour.
    w = [
        addis(12, 0, 0xc4),       # lis  r12, 0xc4
        ori(12, 12, 0x5cb0),      # ori  r12, r12, 0x5cb0   -> &Kf
        lfs(0, 12, 0),            # f0  = Kf
        fmuls(1, 1, 0),           # f1  = x * Kf
        fmuls(0, 2, 0),           # f0  = y * Kf            (floor; f0 reused)
        fsubs(13, 1, 0),          # f13 = f1 - floor        (f13 dead until 0x5cb9a4)
        fsel(1, 13, 1, 0),        # f1  = (f13>=0) ? f1 : floor   == max(x*Kf, y*Kf)
        stfs(1, 3, 0x2c),         # obj[0x2c] = f1
        b(CAVE_VA + 8 * 4, RET_VA),
    ]
    return b"".join(struct.pack(">I", x) for x in w)

EXPECT = ["lis", "ori", "lfs", "fmuls", "fmuls", "fsubs", "fsel", "stfs", "b"]

def verify(blob):
    try:
        from capstone import Cs, CS_ARCH_PPC, CS_MODE_64, CS_MODE_BIG_ENDIAN
    except ImportError:
        print("  !! capstone missing - CANNOT verify; refusing to write"); return False
    md = Cs(CS_ARCH_PPC, CS_MODE_64 | CS_MODE_BIG_ENDIAN)
    got = list(md.disasm(blob, CAVE_VA))
    if len(got) != len(EXPECT):
        print("  !! decoded %d instrs, expected %d" % (len(got), len(EXPECT))); return False
    ok = True
    for ins, want in zip(got, EXPECT):
        flag = "" if ins.mnemonic == want else "   <<< MISMATCH (want %s)" % want
        if flag: ok = False
        print("    0x%06x  %-8s %-28s%s" % (ins.address, ins.mnemonic, ins.op_str, flag))
    # the branch must land exactly on the stfs, and the tail must return to RET_VA
    tgt = CAVE_VA + 0x8 + 0x14
    if tgt != CAVE_VA + 7 * 4:
        print("  !! beq target 0x%x is not the stfs at 0x%x" % (tgt, CAVE_VA + 7 * 4)); ok = False
    if ("0x%x" % RET_VA) not in got[-1].op_str:
        print("  !! tail branch does not return to 0x%x" % RET_VA); ok = False
    return ok

def main():
    kf = 0.9
    if "--kf" in sys.argv: kf = float(sys.argv[sys.argv.index("--kf") + 1])
    d = json.load(open(JSON, encoding="utf-8"))
    cave_i = kf_i = None
    for i, p in enumerate(d["patch"]):
        if p["off"] + 0x10000 == CAVE_VA: cave_i = i
        if p["off"] + 0x10000 == KF_VA:   kf_i = i
    if cave_i is None or kf_i is None:
        sys.exit("!! could not locate the fontsize cave / Kf entries in %s" % JSON)

    blob = build()
    print("New idempotent cave (%d bytes at va 0x%06x):" % (len(blob), CAVE_VA))
    if not verify(blob):
        sys.exit("!! verification FAILED - nothing written")
    if CAVE_VA + len(blob) > KF_VA:
        sys.exit("!! cave would overrun the Kf constant at 0x%x" % KF_VA)

    if not os.path.exists(JSON + ".bak"):
        shutil.copy2(JSON, JSON + ".bak"); print("\nbacked up -> %s.bak" % JSON)
    d["patch"][cave_i]["bytes"] = binascii.hexlify(blob).decode()
    d["patch"][cave_i]["note"] = ("fontsize leaf-safe cave, IDEMPOTENT: skip scale when incoming"
                                  " == obj[0x2c] (re-apply); else f1*=Kf; stfs; branch back")
    d["patch"][kf_i]["bytes"] = binascii.hexlify(struct.pack(">f", kf)).decode()
    d["patch"][kf_i]["note"] = "fontsize Kf constant (%g)" % kf
    d["comment"] = d["comment"].replace(
        "[dialogue advance nudged 0.60->0.57 for overflow margin 2026-07-22]",
        "[dialogue advance nudged 0.60->0.57 2026-07-22]"
        " [fontsize cave made IDEMPOTENT 2026-07-27: was compounding Kf on every"
        " re-apply -> 24/21.6/19.44/17.496/15.7464 decay = unreadable library text]")
    json.dump(d, open(JSON, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s  (cave #%d, Kf #%d = %g)" % (JSON, cave_i, kf_i, kf))
    print("next:  python tools/build_eboot.py    then deploy")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
