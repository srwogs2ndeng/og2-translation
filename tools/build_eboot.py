#!/usr/bin/env python3
"""build_eboot.py - rebuild the complete patched EBOOT, byte-exact, from:

  _rollback/EBOOT.elf.orig          pristine decrypted ELF (produce with RPCS3:
                                    Utilities > Decrypt PS3 Binaries; see docs/INSTALL.md)
  build/eboot_code_patch.json       all CODE changes as data (920 bytes across 23 regions):
                                    dialogue advance K=0.66 (14 sites + caves), menu/status
                                    advance caves, term-field width caves. Generated from the
                                    verified in-game build; see PROCESS.md for what each does.
  build/worksheets/EBOOT/eboot.json translated system strings (applied JP-validated, in place)

Output:  build/EBOOT.patched.elf + build/EBOOT.patched.BIN (fSELF, boots in RPCS3)
Deploy:  copy build/EBOOT.patched.BIN over <game>/PS3_GAME/USRDIR/EBOOT.BIN
"""
import json, os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEG0 = 0x10000


def main():
    orig_p = os.path.join(REPO, "_rollback", "EBOOT.elf.orig")
    if not os.path.exists(orig_p):
        raise SystemExit("missing _rollback/EBOOT.elf.orig - decrypt the retail EBOOT "
                         "with RPCS3 (Utilities > Decrypt PS3 Binaries) first")
    orig = open(orig_p, "rb").read()
    d = bytearray(orig)

    # 1. code/cave patch
    cp = json.load(open(os.path.join(REPO, "build", "eboot_code_patch.json"), encoding="utf-8"))
    assert cp["base_len"] == len(orig), "EBOOT.elf.orig does not match the patch base"
    for e in cp["patch"]:
        b = bytes.fromhex(e["bytes"])
        d[e["off"]:e["off"] + len(b)] = b
    print(f"code patch: {len(cp['patch'])} regions applied")

    # 2. worksheet strings, JP-validated in place (keys are ambiguous VA/file offsets)
    ws = json.load(open(os.path.join(REPO, "build", "worksheets", "EBOOT", "eboot.json"), encoding="utf-8"))
    n = bad = toolong = 0
    for k, v in ws.items():
        en, jp = (v.get("en") or ""), (v.get("jp") or "")
        if not en.strip() or not jp:
            continue
        key, jb = int(k, 16), jp.encode("utf-8")
        fo = next((c for c in (key, key - SEG0, key + SEG0)
                   if 0 <= c < len(orig) and orig[c:c + len(jb)] == jb), None)
        if fo is None:
            bad += 1; continue
        e = fo
        while e < len(orig) and orig[e] != 0:
            e += 1
        # slot may extend into trailing NUL padding (tables are 8/16-byte aligned);
        # keep one NUL as terminator, cap the extension conservatively at 8 bytes
        pad = 0
        while pad < 8 and e + pad < len(orig) and orig[e + pad] == 0:
            pad += 1
        slot, nb = e - fo + max(0, pad - 1), en.encode("utf-8")
        if len(nb) > slot:
            toolong += 1; continue
        d[fo:fo + slot] = nb + b"\x00" * (slot - len(nb))
        n += 1
    print(f"strings applied: {n} (jp-not-found {bad}, too-long {toolong})")
    if toolong:
        print("  WARNING: too-long strings stay Japanese in-game - trim them in the worksheet")

    out_elf = os.path.join(REPO, "build", "EBOOT.patched.elf")
    out_bin = os.path.join(REPO, "build", "EBOOT.patched.BIN")
    open(out_elf, "wb").write(bytes(d))

    # 3. fSELF wrap
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_fself.py"), out_elf, out_bin], cwd=REPO)
    if r.returncode != 0:
        raise SystemExit("make_fself failed")
    print(f"done -> {out_bin}")


if __name__ == "__main__":
    main()
