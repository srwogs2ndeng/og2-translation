#!/usr/bin/env python3
"""make_dist.py - build the shareable, identity-scrubbed source zip.

Produces ../og2-translation-src.zip from the repo's TRACKED files only (so no
game data, work/, or build products can ever leak in), with the same two
anonymization steps as the anon mirror:
  * any absolute Windows path pointing into the game folder is rewritten to its
    repo-relative form, keeping only the tail from the game directory onward.
    Matched by PATTERN, never by a hardcoded user name, so this file carries no
    identity of its own to leak.
  * README.md: swapped for the friend-facing install README (docs/README.anon.md
    if present, else left as-is)

Friends unzip and run `Install (GUI).bat` or `python apply.py` per the README.
Re-run after every update and re-upload to the same cloud-storage file to keep
the share link static.
"""
import os, re, subprocess, zipfile, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(REPO), "og2-translation-src.zip")

# A drive-letter Users path that runs into the game directory: group(1) keeps the
# tail from the game directory onward. Backslashes or forward slashes, quoted or
# not; stops at a quote or line end. Worded so this comment cannot self-match.
ABS_WIN_PATH = re.compile(rb'[A-Za-z]:[\\/]+Users[\\/]+[^\r\n"\']*?[\\/]+(games[\\/][^\r\n"\']*)')


def scrub(data):
    """Rewrite absolute Windows paths to repo-relative ones. Returns (data, changed)."""
    new = ABS_WIN_PATH.sub(lambda m: m.group(1).replace(b"\\", b"/"), data)
    return new, new != data


def main():
    files = subprocess.check_output(["git", "ls-files"], cwd=REPO, text=True).splitlines()
    scrubbed = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            p = os.path.join(REPO, rel)
            if not os.path.isfile(p):
                continue
            data = open(p, "rb").read()
            data, changed = scrub(data)
            if changed:
                scrubbed += 1
            if rel == "README.md":
                anon = os.path.join(REPO, "docs", "README.anon.md")
                if os.path.isfile(anon):
                    data = open(anon, "rb").read()
                    scrubbed += 1
            z.writestr("og2-translation/" + rel, data)
    blob = open(OUT, "rb").read()
    # a leak is this machine's user name anywhere, or ANY absolute C:\Users\ path left over
    who = (os.environ.get("USERNAME") or os.environ.get("USER") or "").strip().encode()
    hits = []
    if who and who.lower() in blob.lower():
        hits.append("current user name")
    if re.search(rb'[A-Za-z]:[\\/]+Users[\\/]+', blob):
        hits.append("absolute C:\\Users path")
    print(f"wrote {OUT} ({len(blob)//1024//1024} MB, {len(files)} files, {scrubbed} scrubbed)")
    print("identity leak check:", "LEAK!! " + ", ".join(hits) if hits else "clean")
    if hits:
        os.remove(OUT)
        sys.exit("aborted - leak found")


if __name__ == "__main__":
    main()
