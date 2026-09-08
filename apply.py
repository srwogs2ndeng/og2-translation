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
import os, sys, json, glob, shutil, subprocess, argparse

try:                       # piped to the GUI, stdout would otherwise block-buffer and
    sys.stdout.reconfigure(line_buffering=True)   # interleave wrongly with stderr
except Exception:
    pass

REPO = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
CONTAINERS = ["Logic", "Common", "Battle"]   # worksheet-driven; General2d + EBOOT handled specially


def run(*cmd):
    print("   $", " ".join(os.path.basename(c) if str(c).endswith(".py") else str(c) for c in cmd))
    r = subprocess.run([PY, *[str(c) for c in cmd]], cwd=REPO)
    if r.returncode != 0:
        sys.exit(f"!! step failed: {cmd}")


def preflight(need_capstone):
    """Check the Python packages BEFORE touching anything.

    Without this the run gets several minutes in, starts decrypting, and only then dies
    somewhere deep with a message that scrolls past. Worse, the usual cause is not "not
    installed" but "installed into a DIFFERENT Python", so the fix has to name the exact
    interpreter that is actually running."""
    missing = []
    try:
        import cryptography  # noqa: F401
    except ImportError:
        missing.append("cryptography")
    if need_capstone:
        try:
            import capstone  # noqa: F401
        except ImportError:
            missing.append("capstone")
    if not missing:
        return
    exe = sys.executable
    print("!! missing Python package(s): " + ", ".join(missing))
    print("!! install them into THIS interpreter, which is the one running the patch:")
    print('!!     "%s" -m pip install %s' % (exe, " ".join(missing)))
    print("!! (if you already ran pip and still see this, pip went to a different Python)")
    sys.exit(1)


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


def verify_pristine(name):
    """Confirm the archive we just extracted is the game's ORIGINAL Japanese.

    Every worksheet offset is a byte position in the Japanese file. Point this at a USRDIR
    that has already been patched and the English archives extract fine, but every offset
    is wrong, and the first thing the user sees is

        ValueError: no NUL terminator after 0x91

    from four frames deep in the reinserter, which says nothing about the actual cause.
    That is a normal upgrade path - unzip the new release, run it on the game you patched
    last time - so it needs to say what happened.

    The test: a worksheet's `jp` string must be at the offset it is recorded at. That is
    exactly the assumption the whole pipeline rests on, so checking a sample of it costs
    nothing and fails where the user can still act on it."""
    ws_dir = os.path.join(REPO, "build", "worksheets", name)
    ex_dir = os.path.join(REPO, "work", name)
    checked = hit = 0
    for sh in sorted(glob.glob(os.path.join(ws_dir, "**", "*.json"), recursive=True))[:12]:
        p = os.path.join(ex_dir, os.path.relpath(sh, ws_dir)[:-5])
        if not os.path.isfile(p):
            continue
        try:
            d = open(p, "rb").read()
            entries = json.load(open(sh, encoding="utf-8"))
        except Exception:
            continue
        n = 0
        for k, v in entries.items():
            jp = v.get("jp") if isinstance(v, dict) else None
            if not jp:
                continue
            b = jp.encode("utf-8")
            off = int(k, 16)
            checked += 1
            n += 1
            if d[off:off + len(b)] == b:
                hit += 1
            if n >= 20:
                break
    if checked < 20 or hit >= checked * 0.5:
        return                                    # pristine, or too little evidence to judge
    sys.exit(
        "!! %s does not look like the game's original Japanese (%d of %d sampled strings\n"
        "!! were not where the worksheet says they are).\n"
        "!! The usual cause is pointing this at a USRDIR you have ALREADY patched. The\n"
        "!! patch rebuilds from the Japanese, so it needs the original archives.\n"
        "!! Restore PSARC/*.psarc.sdat from your own dump (or copy your dump again to a\n"
        "!! clean folder) and re-run. Nothing has been written." % (name, checked - hit, checked))


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("usrdir", help="path to your game's PS3_GAME/USRDIR")
    ap.add_argument("--gd", help="path to dev_hdd0/game/BLJS10133 to wipe")
    ap.add_argument("--eboot-elf", help="path to your decrypted EBOOT.elf")
    a = ap.parse_args()

    preflight(need_capstone=bool(a.eboot_elf))

    # Directories that hold only generated files. git tracks files, not directories, so
    # none of these survive into a clone or the release zip, and every one of them is a
    # FileNotFoundError waiting for the first person to run this on a clean tree. Each
    # write site creates its own too; this is the backstop for the one that forgets.
    for d in ("work", os.path.join("build", "out"), os.path.join("build", "en")):
        os.makedirs(os.path.join(REPO, d), exist_ok=True)

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

    # The published worksheets carry the English but not the game's original Japanese;
    # a few of the fixers need the Japanese to locate control headers and segments. It
    # lives in build/jp_vault.enc, encrypted under a key derived from files in YOUR dump,
    # so the repository alone cannot open it. Restore it before anything is built.
    if os.path.exists(os.path.join(REPO, "build", "jp_vault.enc")):
        print("\n=== unlocking the Japanese reference text from your dump ===")
        run("tools/jpvault.py", "unlock", psarc_dir)

    # 1. worksheet-driven containers
    for name in CONTAINERS:
        print(f"\n=== {name} ===")
        ensure_extract(name, usrdir)
        verify_pristine(name)
        run("tools/deploy.py", "build", name)          # apply -> pack -> deploy (+ GD wipe)

    # 2. General2d (menu chrome) and General3d (map terrain names), each a single changed
    #    file appended into a huge archive rather than a full repack.
    #
    #    These call the SAME one-command builders that produce the releases. General2d used
    #    to be reimplemented inline here, and the copy drifted from the builder it was copied
    #    from: it never ran wtd_sizes, so not one of the 92 per-element font-size fixes ever
    #    reached anybody, and General3d had no step at all, so all 300 map terrain names
    #    stayed Japanese. Both were invisible from here because the releases are built with
    #    the builders. One build path now, so it cannot drift again.
    for name, builder in (("General2d", "tools/build_general2d.py"),
                          ("General3d", "tools/build_general3d.py")):
        print(f"\n=== {name} ===")
        ensure_extract(name, usrdir)
        run(builder, "--deploy")

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
