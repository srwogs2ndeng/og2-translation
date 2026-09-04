#!/usr/bin/env python3
"""build_general3d.py - one-command General3d (map terrain names) build [+ deploy].

General3d is a 1 GB archive in which exactly one file carries text: the map terrain
names in /Dat/Map/MapLandInfo/landinfo.mti (1024 records of 84 bytes, the name being the
first 64). So it is never repacked wholesale: apply the worksheet offset-preserving, then
repack_override appends the one new file and repoints its TOC entry, copying the rest
verbatim.

Same shape as build_general2d.py. It exists because this was previously done by hand,
which is fine once and a trap the second time.

    python tools/build_general3d.py            # build only -> build/out/General3d.psarc.sdat
    python tools/build_general3d.py --deploy   # build + deploy (game must not be running)
"""
import datetime, json, os, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda *p: os.path.join(REPO, "tools", *p)
REL = os.path.join("Dat", "Map", "MapLandInfo", "landinfo.mti")
MANIFEST_NAME = "/Dat/Map/MapLandInfo/landinfo.mti"
JP = os.path.join(REPO, "work", "General3d", REL)
WS = os.path.join(REPO, "build", "worksheets", "General3d", REL + ".json")
EN = os.path.join(REPO, "build", "en", "General3d", REL)
PSARC_JP = os.path.join(REPO, "work", "General3d.psarc")
SDAT_JP = os.path.join(REPO, "work", "General3d.psarc.sdat")
PSARC_OUT = os.path.join(REPO, "build", "out", "General3d.psarc")
SDAT_OUT = PSARC_OUT + ".sdat"


def run(*cmd):
    print("  $", " ".join(os.path.basename(str(c)) if str(c).endswith(".py") else str(c) for c in cmd))
    r = subprocess.run([sys.executable] + [str(c) for c in cmd], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("step failed: %s" % (cmd,))
    for line in [l for l in r.stdout.splitlines() if l.strip()][-2:]:
        print("   ", line)
    return r.stdout


def main():
    for p in (JP, WS, PSARC_JP, SDAT_JP):
        if not os.path.exists(p):
            raise SystemExit("missing %s\n  extract General3d first (tools/run_extract_all.py --all)" % p)
    # NOT the generic worksheet apply: it sizes each slot as "bytes up to the next NUL",
    # which is the Japanese name's length rather than the 64-byte field reserved for it,
    # and refuses 96 of the 300 English names for being longer. fix_landinfo writes the
    # whole field, offset-preserving, and gets all 300 in.
    run(T("fix_landinfo.py"))
    if os.path.getsize(EN) != os.path.getsize(JP):
        raise SystemExit("landinfo.mti changed size; these are fixed 84-byte records and "
                         "must stay offset-preserving")

    sys.path.insert(0, os.path.join(REPO, "tools"))
    import repack_override as RO
    os.makedirs(os.path.dirname(PSARC_OUT), exist_ok=True)
    open(PSARC_OUT, "wb").write(
        RO.repack_override(PSARC_JP, {MANIFEST_NAME: open(EN, "rb").read()}))
    print("  repacked ->", PSARC_OUT)
    run(T("encrypt_sdat.py"), "wrap", SDAT_JP, PSARC_OUT, SDAT_OUT)
    out = run(T("encrypt_sdat.py"), "verify", SDAT_OUT)
    if "PASS" not in out:
        raise SystemExit("sdat verify did not PASS")

    if "--deploy" in sys.argv:
        cfg = json.load(open(os.path.join(REPO, "build", "config.json"), encoding="utf-8"))
        dst = os.path.normpath(os.path.join(REPO, cfg["folder_psarc_dir"], "General3d.psarc.sdat"))
        bdir = os.path.join(REPO, "build", "rollbacks", "General3d")
        os.makedirs(bdir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        if os.path.exists(dst):
            shutil.copy2(dst, os.path.join(bdir, ts + ".sdat"))
            print("  backup live -> build/rollbacks/General3d/%s.sdat" % ts)
        shutil.copy2(SDAT_OUT, dst)
        print("  deployed ->", dst)
        import deploy as D
        D._sync_gd("General3d", SDAT_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
