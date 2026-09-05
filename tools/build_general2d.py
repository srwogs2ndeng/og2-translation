#!/usr/bin/env python3
"""build_general2d.py - one-command General2d (menu chrome) build [+ deploy].

General2d only ever changes ONE file (windowdataMain.wtd), so we never repack the 638 MB
archive: wtd_tool apply (offset-preserving text) -> wtd_sizes (per-element font sizes)
-> repack_override (append the new file, repoint its TOC entry, everything else verbatim)
-> encrypt_sdat wrap + verify (RPCS3 HMAC) -> optional deploy (backup live sdat, copy,
mirror into every game-data tree via deploy._sync_gd; no install screen).

    python tools/build_general2d.py               # build only  -> build/out/General2d.psarc.sdat
    python tools/build_general2d.py --deploy      # build + deploy (game must not be running)
    python tools/build_general2d.py --deploy-only # deploy the existing build/out sdat (no rebuild)
"""
import os, sys, shutil, datetime, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda *p: os.path.join(REPO, "tools", *p)
WTD_JP  = os.path.join(REPO, "work", "General2d", "Dat", "Window", "WindowToolData", "windowdataMain.wtd")
WTD_WS  = os.path.join(REPO, "build", "worksheets", "General2d", "Dat", "Window", "WindowToolData", "windowdataMain.wtd.json")
WTD_EN  = os.path.join(REPO, "build", "en", "General2d_windowdataMain.wtd")
PSARC_JP = os.path.join(REPO, "work", "General2d.psarc")
SDAT_JP  = os.path.join(REPO, "work", "General2d.psarc.sdat")
PSARC_OUT = os.path.join(REPO, "build", "out", "General2d.psarc")
SDAT_OUT  = PSARC_OUT + ".sdat"
MANIFEST_NAME = "/Dat/Window/WindowToolData/windowdataMain.wtd"


def run(*cmd):
    print("  $", " ".join(os.path.basename(c) if str(c).endswith(".py") else str(c) for c in cmd))
    r = subprocess.run([sys.executable] + list(cmd), cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout); print(r.stderr); raise SystemExit(f"step failed: {cmd}")
    tail = [l for l in r.stdout.splitlines() if l.strip()][-2:]
    for l in tail: print("   ", l)
    return r.stdout


def build():
    os.makedirs(os.path.dirname(WTD_EN), exist_ok=True)
    run(T("wtd_tool.py"), "apply", WTD_JP, WTD_WS, WTD_EN)
    run(T("wtd_sizes.py"), WTD_EN, WTD_EN)
    # repack_override takes the manifest name as an argument; call the module directly to
    # avoid shell path mangling of the leading '/'
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import repack_override as RO
    open(PSARC_OUT, "wb").write(RO.repack_override(PSARC_JP, {MANIFEST_NAME: open(WTD_EN, "rb").read()}))
    print("  repacked ->", PSARC_OUT)
    run(T("encrypt_sdat.py"), "wrap", SDAT_JP, PSARC_OUT, SDAT_OUT)
    out = run(T("encrypt_sdat.py"), "verify", SDAT_OUT)
    if "PASS" not in out:
        raise SystemExit("sdat verify did not PASS")


def main():
    if "--deploy-only" in sys.argv:
        if not os.path.exists(SDAT_OUT):
            raise SystemExit(f"no {SDAT_OUT}; build first")
    else:
        build()
    if "--deploy" in sys.argv or "--deploy-only" in sys.argv:
        import json
        cfg = json.load(open(os.path.join(REPO, "build", "config.json"), encoding="utf-8"))
        dst = os.path.normpath(os.path.join(REPO, cfg["folder_psarc_dir"], "General2d.psarc.sdat"))
        bdir = os.path.join(REPO, "build", "rollbacks", "General2d"); os.makedirs(bdir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        if os.path.exists(dst):
            shutil.copy2(dst, os.path.join(bdir, ts + ".sdat")); print(f"  backup live -> build/rollbacks/General2d/{ts}.sdat")
        shutil.copy2(SDAT_OUT, dst); print("  deployed ->", dst)
        import deploy as D
        # wipe, do not mirror: overwriting an install the game already accepted is what
        # makes it report "Game data is corrupted" on the next boot (see deploy._sync_gd)
        D._wipe_gd()
        print("  GD wiped -> the next boot reinstalls it from the disc folder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
