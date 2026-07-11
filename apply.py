#!/usr/bin/env python3
"""apply.py - one-command build + install of the English patch onto YOUR game.

This is a FROM-SOURCE patcher: it extracts your own game files, rebuilds them with
the English text in this repo, and writes the patched files back into a play-copy
of your game. No game data ships in this repo - you supply your own legally dumped
BLJS10133.

    python apply.py "<PATH TO YOUR GAME'S USRDIR>"
        [--gd  "<PATH TO dev_hdd0/game/BLJS10133>"]   # RPCS3 install to wipe (recommended)
        [--eboot-elf "<PATH TO YOUR DECRYPTED EBOOT.elf>"]  # optional: letter-spacing patch

  * USRDIR is the folder that contains  PSARC/Logic.psarc.sdat ...  and  EBOOT.BIN.
    Point it at a COPY of your game you boot in RPCS3 (patched in place).
  * --gd wipes the game-data install so RPCS3 reinstalls the patched files. If you
    omit it, delete dev_hdd0/game/BLJS10133 yourself once before booting.
  * --eboot-elf: RPCS3 > Utilities > Decrypt PS3 Binaries on your EBOOT.BIN, pass
    the resulting EBOOT.elf. Omit to skip the (optional) spacing patch.

Requires Python 3.10+ with:  pip install cryptography capstone
"""
import os, sys, json, shutil, subprocess, argparse

REPO = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
CONTAINERS = ["Logic", "Common", "Battle"]   # worksheet-driven; General2d + EBOOT handled specially


def run(*cmd):
    print("   $", " ".join(os.path.basename(c) if str(c).endswith(".py") else str(c) for c in cmd))
    r = subprocess.run([PY, *[str(c) for c in cmd]], cwd=REPO)
    if r.returncode != 0:
        sys.exit(f"!! step failed: {cmd}")


def ensure_extract(name, usrdir):
    """Decrypt + extract a container's pristine files into work/ (once)."""
    sdat = os.path.join(usrdir, "PSARC", f"{name}.psarc.sdat")
    if not os.path.isfile(sdat):
        sys.exit(f"!! not found: {sdat}  (is this the right USRDIR?)")
    work_sdat = os.path.join(REPO, "work", f"{name}.psarc.sdat")
    work_psarc = os.path.join(REPO, "work", f"{name}.psarc")
    work_dir = os.path.join(REPO, "work", name)
    os.makedirs(os.path.join(REPO, "work"), exist_ok=True)
    if not os.path.isfile(work_sdat):
        shutil.copy2(sdat, work_sdat)                       # keep the pristine SDAT (re-encrypt template)
    if not os.path.isfile(work_psarc):
        run("tools/decrypt_sdat.py", work_sdat, work_psarc)
    if not os.path.isdir(work_dir) or not os.listdir(work_dir):
        run("tools/extract_psarc.py", work_psarc, work_dir)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("usrdir", help="path to your game's PS3_GAME/USRDIR")
    ap.add_argument("--gd", help="path to dev_hdd0/game/BLJS10133 to wipe")
    ap.add_argument("--eboot-elf", help="path to your decrypted EBOOT.elf")
    a = ap.parse_args()

    usrdir = os.path.abspath(a.usrdir)
    psarc_dir = os.path.join(usrdir, "PSARC")
    if not os.path.isdir(psarc_dir):
        sys.exit(f"!! no PSARC folder under {usrdir} - point --usrdir at PS3_GAME/USRDIR")

    # write config.json so deploy.py targets YOUR game
    cfg_path = os.path.join(REPO, "build", "config.json")
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    cfg["folder_psarc_dir"] = psarc_dir
    cfg["gd_root"] = os.path.abspath(a.gd) if a.gd else os.path.join(REPO, "work", "_nogd")
    json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), indent=2)
    print(f"target: {psarc_dir}")

    # 1. worksheet-driven containers
    for name in CONTAINERS:
        print(f"\n=== {name} ===")
        ensure_extract(name, usrdir)
        run("tools/deploy.py", "build", name)          # apply -> pack -> deploy (+ GD wipe)

    # 2. General2d (menu chrome - offset-preserving override repack)
    print("\n=== General2d ===")
    ensure_extract("General2d", usrdir)
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import wtd_tool, repack_override, encrypt_sdat
    wtd_rel = "Dat/Window/WindowToolData/windowdataMain.wtd"
    src = open(os.path.join(REPO, "work", "General2d", wtd_rel), "rb").read()
    ws = json.load(open(os.path.join(REPO, "build", "worksheets", "General2d", wtd_rel + ".json"), encoding="utf-8"))
    new, refused, applied = wtd_tool.apply(src, ws)
    newp = repack_override.repack_override(os.path.join(REPO, "work", "General2d.psarc"), {"/" + wtd_rel: bytes(new)})
    outp = os.path.join(REPO, "build", "out", "General2d.psarc")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    shutil.copy2(newp, outp) if isinstance(newp, str) else open(outp, "wb").write(newp)
    encrypt_sdat.wrap(os.path.join(REPO, "work", "General2d.psarc.sdat"), outp, outp + ".sdat")
    shutil.copy2(outp + ".sdat", os.path.join(psarc_dir, "General2d.psarc.sdat"))
    print(f"   General2d deployed ({applied} labels, {len(refused)} refused)")

    # 3. EBOOT (optional letter-spacing + system-string patch)
    print("\n=== EBOOT ===")
    if a.eboot_elf and os.path.isfile(a.eboot_elf):
        os.makedirs(os.path.join(REPO, "_rollback"), exist_ok=True)
        shutil.copy2(a.eboot_elf, os.path.join(REPO, "_rollback", "EBOOT.elf.orig"))
        run("tools/build_eboot.py")
        shutil.copy2(os.path.join(REPO, "build", "EBOOT.patched.BIN"), os.path.join(usrdir, "EBOOT.BIN"))
        print("   EBOOT.BIN patched")
    else:
        print("   skipped (no --eboot-elf). To get proper letter spacing later: RPCS3 >")
        print("   Utilities > Decrypt PS3 Binaries on your EBOOT.BIN, then re-run with")
        print("   --eboot-elf <that EBOOT.elf>.")

    # 4. game-data install
    print("\n=== done ===")
    if a.gd and os.path.isdir(cfg["gd_root"]):
        shutil.rmtree(cfg["gd_root"]); print("   wiped game-data install; RPCS3 reinstalls the patch on next boot.")
    else:
        print("   Before booting: delete your dev_hdd0/game/BLJS10133 install once so RPCS3")
        print("   reinstalls the patched files. Then boot the game in RPCS3.")


if __name__ == "__main__":
    main()
