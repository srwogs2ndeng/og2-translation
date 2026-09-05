#!/usr/bin/env python3
"""publish_release.py - publish a version: snapshot, zip, mirror push, tag, release.

The whole public-release step in one command, so the repository, the zip and the release
notes cannot drift apart:

  1. read the notes for this version out of CHANGELOG.md (refuses if the section is
     missing, which is what keeps the changelog from being forgotten)
  2. build the identity-scrubbed, Japanese-free snapshot on a throwaway orphan branch
  3. build og2-english-patch.zip from that snapshot
  4. force-push the snapshot to the public mirror
  5. create the tag and the GitHub release, and upload the zip to it

    python tools/publish_release.py v1.0.1
    python tools/publish_release.py v1.0.1 --dry-run     # steps 1-3 only, nothing public
    python tools/publish_release.py v1.0.1 --prerelease

It refuses to run on a dirty tree or off main, and it always returns you to main, even
when a step fails. The token comes from git_account (the mirror's own account), so the
named account never authenticates against the public repo.
"""
import json, os, re, subprocess, sys, urllib.error, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
CHANGELOG = os.path.join(REPO, "CHANGELOG.md")
ZIP = os.path.join(os.path.dirname(REPO), "og2-english-patch.zip")
OWNER, NAME = "srwogs2ndeng", "og2-translation"
ACCOUNT = OWNER
BRANCH = "anon-tmp"


def git(*args, check=True):
    r = subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit("git %s failed:\n%s%s" % (" ".join(args), r.stdout, r.stderr))
    return r.stdout.strip()


def notes_for(version):
    """The CHANGELOG section for this version, without its heading."""
    if not os.path.isfile(CHANGELOG):
        sys.exit("no CHANGELOG.md")
    text = open(CHANGELOG, encoding="utf-8").read()
    m = re.search(r"^## +%s\b[^\n]*\n(.*?)(?=^## |\Z)" % re.escape(version),
                  text, re.S | re.M)
    if not m:
        sys.exit("CHANGELOG.md has no '## %s' section.\n"
                 "Add one before publishing: the release notes come from it." % version)
    body = m.group(1).strip()
    if not body:
        sys.exit("the '## %s' section in CHANGELOG.md is empty" % version)
    return body


def api(tok, method, path, payload=None, host="api.github.com"):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request("https://%s%s" % (host, path), data=data, method=method)
    r.add_header("Authorization", "Bearer " + tok)
    r.add_header("Accept", "application/vnd.github+json")
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def upload_asset(tok, upload_url, path):
    url = upload_url.split("{")[0] + "?name=" + os.path.basename(path)
    data = open(path, "rb").read()
    r = urllib.request.Request(url, data=data, method="POST")
    r.add_header("Authorization", "Bearer " + tok)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("Content-Type", "application/zip")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 1
    version = args[0]
    dry = "--dry-run" in sys.argv
    pre = "--prerelease" in sys.argv

    body = notes_for(version)
    print("release notes for %s: %d characters from CHANGELOG.md" % (version, len(body)))

    if git("status", "--porcelain"):
        sys.exit("working tree is dirty; commit or stash first")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        sys.exit("run this from main")

    import git_account as G
    tok, src = G.pat_for(ACCOUNT)
    if not tok and not dry:
        sys.exit("no credential for %s (git account save-token %s)" % (ACCOUNT, ACCOUNT))

    cfg = json.load(open(os.path.join(REPO, "build", "config.json"), encoding="utf-8"))
    psarc = os.path.normpath(os.path.join(REPO, cfg["folder_psarc_dir"]))
    if not os.path.isdir(psarc):
        sys.exit("cannot find your PSARC folder (%s); the vault key comes from it" % psarc)

    try:
        git("branch", "-D", BRANCH, check=False)
        git("checkout", "-q", "--orphan", BRANCH)
        subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_anon_snapshot.py"),
                        psarc], cwd=REPO, check=True)
        # Stage FIRST. `git checkout --orphan` carries main's index over, so until this
        # runs `git ls-files` still lists every file the snapshot just deleted, and
        # make_release would be reading a stale file list.
        git("add", "-A")
        subprocess.run([sys.executable, os.path.join(REPO, "tools", "make_release.py"),
                        "--require-vault"], cwd=REPO, check=True)
        env = dict(os.environ, GIT_AUTHOR_NAME=OWNER, GIT_COMMITTER_NAME=OWNER,
                   GIT_AUTHOR_EMAIL="%s@users.noreply.github.com" % OWNER,
                   GIT_COMMITTER_EMAIL="%s@users.noreply.github.com" % OWNER)
        msg = ("OG2 English translation %s\n\n"
               "The English is MACHINE GENERATED and was not proofread line by line; see\n"
               "README.md. The game's own Japanese is not published here.\n\n"
               "Build against your own dump. No game data included.\n" % version)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=REPO, env=env, check=True)
        head_msg = git("log", "-1", "--format=%h %an")
        print("snapshot committed: %s" % head_msg)
        if dry:
            print("\n--dry-run: nothing pushed, no release created")
            return 0
        url = "https://github.com/%s/%s.git" % (OWNER, NAME)
        git("remote", "remove", "anon", check=False)
        git("remote", "add", "anon", url)
        rc = subprocess.run([sys.executable, os.path.join(REPO, "tools", "git_account.py"),
                             "push", "anon", "+%s:main" % BRANCH], cwd=REPO).returncode
        git("remote", "remove", "anon", check=False)
        if rc:
            sys.exit("mirror push failed; no release created")
    finally:
        git("checkout", "-q", "-f", "main", check=False)
        git("checkout", "-f", "--", ".", check=False)

    st, rel = api(tok, "GET", "/repos/%s/%s/releases/tags/%s" % (OWNER, NAME, version))
    if st == 200:
        print("release %s already exists; updating its notes" % version)
        st, rel = api(tok, "PATCH", "/repos/%s/%s/releases/%d" % (OWNER, NAME, rel["id"]),
                      {"body": body, "prerelease": pre})
    else:
        st, rel = api(tok, "POST", "/repos/%s/%s/releases" % (OWNER, NAME),
                      {"tag_name": version, "name": version, "body": body,
                       "prerelease": pre, "draft": False})
    if st not in (200, 201):
        sys.exit("could not create the release (%s): %s" % (st, rel.get("message")))
    print("release %s -> %s" % (version, rel.get("html_url")))

    for a in rel.get("assets", []):
        if a["name"] == os.path.basename(ZIP):
            api(tok, "DELETE", "/repos/%s/%s/releases/assets/%d" % (OWNER, NAME, a["id"]))
            print("  replaced the existing zip asset")
    if os.path.isfile(ZIP):
        st, _ = upload_asset(tok, rel["upload_url"], ZIP)
        print("  uploaded %s (%.1f MB) -> %s"
              % (os.path.basename(ZIP), os.path.getsize(ZIP) / 1e6, st))
    else:
        print("  WARNING: %s missing, release has no zip" % ZIP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
