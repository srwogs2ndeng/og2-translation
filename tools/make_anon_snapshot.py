#!/usr/bin/env python3
"""make_anon_snapshot.py - build the public, identity-scrubbed, Japanese-free snapshot.

Run from a clean checkout on an orphan branch. It does, in order:

  1. scrub absolute Windows paths out of every tracked file (make_dist.scrub)
  2. swap docs/README.anon.md in as README.md
  3. DELETE the build intermediates that carry the game's Japanese and are not needed to
     rebuild the patch: agent batches, QA reports, scratch files. About 3.6 million
     characters of the script live only in these, and encrypting them would be silly
     when nothing needs them.
  4. LOCK the Japanese that IS needed into build/jp_vault.enc, keyed to the user's own
     disc files (tools/jpvault.py)
  5. report what Japanese, if any, is left in the open

What survives in the clear: the English translation, the byte offsets it applies at, the
slot sizes, and all the tooling. That is the patch, and it is ours to publish. What does
not: the game's script.

    python tools/make_anon_snapshot.py <path to your USRDIR/PSARC>
"""
import glob, os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

# Build intermediates that carry Japanese and are NOT inputs to the build.
DROP = [
    "build/workflows",          # per-agent translation batches (the script, chunked)
    "build/audit",              # QA and fidelity reports (jp/en pairs)
    "build/eboot_batches",
    "build/scr_batches",
    "build/wtd_batches",
]
DROP_GLOBS = [
    "build/_*.json",            # scratch dumps from one-off passes
    "build/*_todo.json",
    "build/*_missed.json",
    "build/*_overflow*.json",
    "build/*_remaining.json",
    "build/*_wf_args.json",
    "build/*_in.json",
]
CJK = re.compile(r"[぀-ヿ一-鿿]")


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True, text=True)


def tracked():
    return [p for p in git("ls-files").stdout.splitlines() if p.strip()]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    psarc_dir = sys.argv[1]
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch in ("main", "master"):
        sys.exit("refusing to run on %s: this rewrites files in place.\n"
                 "  git checkout --orphan anon-tmp   first." % branch)

    import make_dist as M
    import jpvault as V

    # 1 + 2
    n = 0
    for rel in tracked():
        p = os.path.join(REPO, rel)
        if not os.path.isfile(p):
            continue
        d = open(p, "rb").read()
        new, changed = M.scrub(d)
        if changed:
            open(p, "wb").write(new)
            n += 1
    print("scrubbed absolute paths from %d file(s)" % n)
    anon = os.path.join(REPO, "docs", "README.anon.md")
    if os.path.isfile(anon):
        shutil.copyfile(anon, os.path.join(REPO, "README.md"))
        print("README.md <- docs/README.anon.md")

    # 3
    dropped = 0
    for rel in DROP:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if os.path.isdir(p):
            dropped += sum(len(f) for _, _, f in os.walk(p))
            shutil.rmtree(p, ignore_errors=True)
            print("dropped %s/" % rel)
    for pat in DROP_GLOBS:
        for p in glob.glob(os.path.join(REPO, pat.replace("/", os.sep))):
            if os.path.isfile(p):
                os.remove(p)
                dropped += 1
    print("dropped %d intermediate file(s)" % dropped)

    # 4
    V.cmd_lock(psarc_dir)

    # 5. SWEEP. An explicit drop list will always miss something - the first run of this
    # left 593,649 characters of script sitting in files nobody thought of (a phase-2
    # scene index, objective passes, name maps). So instead of trusting the list, look at
    # what is actually left and drop anything under build/ that still carries Japanese
    # and is not an input the build reads. Files outside build/ are reported, never
    # deleted: docs may quote Japanese on purpose.
    keep = {os.path.relpath(p, REPO).replace("\\", "/") for p in V.targets()}
    swept = 0
    for rel in tracked():
        if rel in keep or not rel.startswith("build/"):
            continue
        p = os.path.join(REPO, rel)
        if not os.path.isfile(p):
            continue
        try:
            text = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        if len(CJK.findall(text)) > 20:      # >20 excludes fullwidth punctuation in EN
            os.remove(p)
            swept += 1
    print("swept %d further build file(s) that still carried Japanese" % swept)

    # 6 - tell the truth about what is left
    left, worst, outside = 0, [], []
    for rel in tracked():
        p = os.path.join(REPO, rel)
        if not os.path.isfile(p):
            continue
        try:
            text = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        c = len(CJK.findall(text))
        if c:
            left += c
            worst.append((c, rel))
            if not rel.startswith("build/"):
                outside.append((c, rel))
    worst.sort(reverse=True)
    print("\nJapanese characters still in the clear: %d" % left)
    for c, rel in worst[:8]:
        print("   %6d  %s" % (c, rel))
    if outside:
        print("\nOutside build/ (review these by hand, nothing was deleted):")
        for c, rel in sorted(outside, reverse=True)[:10]:
            print("   %6d  %s" % (c, rel))
    print("\n(a small residue is expected: fullwidth brackets and punctuation inside OUR\n"
          " English strings, which the game's font requires.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
