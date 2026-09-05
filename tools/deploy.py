#!/usr/bin/env python3
"""deploy.py - build + deploy the translation with rollback at every step.

Model (sustainable):
  * build/worksheets/<Archive>/<relpath>.json  = translation source of truth (git-tracked)
  * work/<Archive>                             = pristine JP extract (never mutated)
  * build/en/<Archive>                         = English working tree (regenerated)
  * build/out/<Archive>.psarc[.sdat]           = repacked archive
  * build/rollbacks/<Archive>/<ts>.sdat        = pre-deploy backups of the live SDAT

Each translated file is RESET from the JP base before its worksheet is applied, so
offsets are always valid (worksheets are keyed by JP-file offset).

Commands:
  apply   <Archive>          reset+apply every worksheet -> build/en/<Archive>
  pack    <Archive>          pack_psarc + encrypt_sdat  -> build/out/<Archive>.psarc.sdat
  deploy  <Archive>          backup live SDAT, copy new -> game folder, WIPE every GD tree
                             so the next boot reinstalls (--mirror overwrites the GD in place
                             instead, which corrupts an install the game has already accepted)
  rollback<Archive>          restore latest backup -> game folder, mirror into GD
  build   <Archive>          apply + pack + deploy
  status  <Archive>          show worksheet count / build / deploy state
"""
import sys, os, json, shutil, subprocess, glob, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(REPO, "build", "config.json"), encoding="utf-8"))
sys.path.insert(0, os.path.join(REPO, "tools"))
import worksheet as WS
import pack_psarc as PK


def rp(p):  # resolve a config-relative path against the repo root
    return os.path.normpath(os.path.join(REPO, p))

def arch(name):
    a = CFG["archives"][name]
    return {k: rp(v) for k, v in a.items()}

def run(*cmd):
    print("  $", " ".join(os.path.basename(c) if c.endswith(".py") else c for c in cmd))
    r = subprocess.run([sys.executable] + list(cmd), cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout); print(r.stderr); raise SystemExit(f"step failed: {cmd}")
    return r.stdout


def cmd_apply(name):
    a = arch(name)
    ws_dir = os.path.join(REPO, "build", "worksheets", name)
    en_root = os.path.join(REPO, "build", "en", name)
    sheets = glob.glob(os.path.join(ws_dir, "**", "*.json"), recursive=True)
    if not sheets:
        print(f"no worksheets for {name} (nothing to translate yet)"); return 0
    n = 0
    for sh in sheets:
        rel = os.path.relpath(sh, ws_dir)[:-5]           # strip .json -> container relpath
        jp_file = os.path.join(a["jp_extract"], rel)
        en_file = os.path.join(en_root, rel)
        os.makedirs(os.path.dirname(en_file), exist_ok=True)
        shutil.copy2(jp_file, en_file)                    # reset to JP (valid offsets)
        WS.cmd_apply(en_file, sh, en_file)                # apply English in place
        n += 1
    print(f"applied {n} worksheet(s) -> {en_root}")
    if name == "Logic":
        # KeyWordData is offset-preserving (keyword UI addresses lines by position);
        # its worksheet is blank and this fixer is the file's only writer.
        run(os.path.join(REPO, "tools", "fix_keyworddata.py"))
        run(os.path.join(REPO, "tools", "fix_dictionaries.py"))
        # SkillData has 6 inline description bodies the extractor skipped (control-byte
        # prefixed, not SOFS-referenced); this writer patches them offset-preserving.
        run(os.path.join(REPO, "tools", "fix_skilldesc.py"))
        # SkillData's 6 two-part description RECORDS ([u16 tail chars][u16 body+1][body][NUL]
        # [tail][NUL]) must be rebuilt as a unit: the per-JP-line pour put ~110 English chars
        # on line 1 and 5 on line 2, and the renderer shrank line 1 to ~1/3 size (2026-09-03).
        run(os.path.join(REPO, "tools", "fix_skilldata.py"))
        # HelpData / SpiritData / PartsData / ACEBonusData: MULTI-LINE descriptions whose line
        # 2+ starts are fixed byte strides from the entry start (or a length byte). Rebuilt
        # fully OFFSET-PRESERVING from JP (supersedes fix_helpdesc.py, 2026-07-27).
        run(os.path.join(REPO, "tools", "fix_fixh_text.py"))
    return n


def cmd_pack(name):
    a = arch(name)
    en_root = os.path.join(REPO, "build", "en", name)
    if not os.path.isdir(en_root):
        raise SystemExit(f"no build/en/{name}; run apply first")
    # manifest names from the JP archive -> lookup by normalized relpath
    d = open(a["jp_psarc"], "rb").read()
    h, entries, btab, bnum = PK.parse(d)
    names = PK.manifest_names(d, entries, btab, h["block_size"])
    lut = {nm.lstrip("/").replace("\\", "/").lower(): nm for nm in names}
    # overrides = only the translated files sitting in build/en/<name>
    overrides = {}
    for f in glob.glob(os.path.join(en_root, "**", "*"), recursive=True):
        if not os.path.isfile(f):
            continue
        rel = os.path.relpath(f, en_root).replace("\\", "/").lower()
        nm = lut.get(rel)
        if nm is None:
            raise SystemExit(f"translated file not in manifest: {rel}")
        overrides[nm] = open(f, "rb").read()
    print(f"  overriding {len(overrides)} translated file(s); rest from pristine JP tree")
    out_psarc = os.path.join(REPO, "build", "out", f"{name}.psarc")
    out_sdat = out_psarc + ".sdat"
    out_bytes = PK.pack(a["jp_psarc"], a["jp_extract"], file_bytes=overrides)
    open(out_psarc, "wb").write(out_bytes)
    run(rp("tools/encrypt_sdat.py"), "wrap", a["jp_sdat"], out_psarc, out_sdat)
    print(f"packed -> {out_sdat} ({os.path.getsize(out_sdat)} bytes)")


def _live_paths(name):
    folder = os.path.join(rp(CFG["folder_psarc_dir"]), f"{name}.psarc.sdat")
    gd = os.path.join(rp(CFG["gd_root"]), "USRDIR", "PSARC", f"{name}.psarc.sdat")
    return folder, gd

def cmd_deploy(name):
    out_sdat = os.path.join(REPO, "build", "out", f"{name}.psarc.sdat")
    if not os.path.exists(out_sdat):
        raise SystemExit(f"no {out_sdat}; run pack first")
    folder, gd = _live_paths(name)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(REPO, "build", "rollbacks", name)
    os.makedirs(bdir, exist_ok=True)
    if os.path.exists(folder):
        shutil.copy2(folder, os.path.join(bdir, f"{ts}.sdat"))
        print(f"  backup live -> build/rollbacks/{name}/{ts}.sdat")
    shutil.copy2(out_sdat, folder)
    print(f"  deployed -> {folder}")
    if "--mirror" in sys.argv:
        _sync_gd(name, out_sdat)
    else:
        _wipe_gd()
        print("  GD wiped -> the next boot reinstalls it from the disc folder")

def cmd_rollback(name):
    bdir = os.path.join(REPO, "build", "rollbacks", name)
    backs = sorted(glob.glob(os.path.join(bdir, "*.sdat")))
    if not backs:
        raise SystemExit(f"no backups for {name}")
    latest = backs[-1]
    folder, gd = _live_paths(name)
    shutil.copy2(latest, folder)
    print(f"restored {os.path.basename(latest)} -> {folder}")
    _sync_gd(name, latest)

def _gd_roots():
    """Every RPCS3 install's game-data dir for this title. There is more than one emulator
    tree here (retail + rpcs3-instrumented, each with its OWN dev_hdd0), and a deploy that
    wipes only one leaves the other holding a STALE archive. The corruption guard
    (cellGameDataCheck) then content-validates it against the install manifest and the game
    dies with "game data corrupted" -- which is exactly what happened 2026-07-27 after a
    Logic deploy while running the instrumented build. Wipe them all."""
    roots = [CFG["gd_root"]] + list(CFG.get("gd_roots") or [])
    seen, out = set(), []
    for r in roots:
        p = rp(r)
        if p not in seen:
            seen.add(p); out.append(p)
    return out


def _sync_gd(name, sdat_path):
    """Mirror the deployed archive into every game-data tree. OPT-IN ONLY (--mirror).

    DO NOT make this the default. Overwriting the archives inside an install the game has
    already accepted is what makes it report "Game data is corrupted" on the next boot:
    the game validates the install it made, and the files are no longer the ones it wrote.
    That is the bug that kept recurring through early September, once per deploy.

    The 2026-09-01 reasoning for mirroring was WRONG. It claimed the retail build could
    never fresh-install because its cellGameDataCheck creates the directory during the
    check. The log disproves that on 2026-09-04: with the directory genuinely ABSENT,
    retail logged "directory '/dev_hdd0/game/BLJS10335' not found" and then installed
    cleanly via cellGameCreateGameData. Wiping works; mirroring is what breaks."""
    tmpl = os.path.join(REPO, "build", "gd_template")
    disc = rp(CFG["folder_psarc_dir"])
    for gd_root in _gd_roots():
        psarc_dir = os.path.join(gd_root, "USRDIR", "PSARC")
        os.makedirs(psarc_dir, exist_ok=True)
        for fn in ("PARAM.SFO", "ICON0.PNG"):
            dst = os.path.join(gd_root, fn)
            if not os.path.exists(dst) and os.path.exists(os.path.join(tmpl, fn)):
                shutil.copy2(os.path.join(tmpl, fn), dst)
        # every archive must be present and identical to the disc folder (the guard's
        # cellGameDataCheck size validation rejects the install otherwise). Size alone is NOT
        # a valid "unchanged" test: most of our edits are offset-preserving and leave the
        # archive the same size (2026-09-03: a same-size Logic deploy was skipped as "in
        # sync"). copy2 preserves mtime, so a mirrored copy matches its source on BOTH size
        # and mtime, while a fresh build never does.
        def same(a, b):
            sa, sb = os.stat(a), os.stat(b)
            return sa.st_size == sb.st_size and abs(sa.st_mtime - sb.st_mtime) < 2
        for f in glob.glob(os.path.join(disc, "*.psarc.sdat")):
            dst = os.path.join(psarc_dir, os.path.basename(f))
            if not os.path.exists(dst) or not same(f, dst):
                shutil.copy2(f, dst)
                print(f"  GD mirrored: {os.path.relpath(dst, REPO)}")
        print(f"  GD in sync: {gd_root}")


def _wipe_gd():
    hit = False
    for gd_root in _gd_roots():
        if os.path.isdir(gd_root):
            shutil.rmtree(gd_root, ignore_errors=True)
            print(f"  wiped GD: {gd_root}")
            hit = True
    if not hit:
        print("  (no GD present to wipe)")

def cmd_status(name):
    a = arch(name)
    ws_dir = os.path.join(REPO, "build", "worksheets", name)
    sheets = glob.glob(os.path.join(ws_dir, "**", "*.json"), recursive=True)
    out_sdat = os.path.join(REPO, "build", "out", f"{name}.psarc.sdat")
    folder, gd = _live_paths(name)
    print(f"{name}: worksheets={len(sheets)}  built={os.path.exists(out_sdat)}  "
          f"deployed={os.path.exists(folder)}  gd_present={os.path.isdir(rp(CFG['gd_root']))}")


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    cmd, name = sys.argv[1], sys.argv[2]
    if   cmd == "apply":    cmd_apply(name)
    elif cmd == "pack":     cmd_pack(name)
    elif cmd == "deploy":   cmd_deploy(name)
    elif cmd == "rollback": cmd_rollback(name)
    elif cmd == "status":   cmd_status(name)
    elif cmd == "build":    cmd_apply(name); cmd_pack(name); cmd_deploy(name)
    else: print(__doc__); sys.exit(1)
