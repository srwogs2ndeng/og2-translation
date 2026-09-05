#!/usr/bin/env python3
"""make_release.py - build the release zip.

Produces ../og2-english-patch.zip: the patch, the tooling, the RPCS3 settings for this
title, and instructions. Everything a person needs to go from "I have RPCS3 and my own
dump" to playing in English.

WHAT IS DELIBERATELY NOT IN IT, and cannot be:
  * the game. Any part of BLJS10133 is Bandai Namco's. The whole design of this project
    is that you rebuild the patch against a copy you already own.
  * PS3 firmware. That is Sony's and is not redistributable. Get it from
    playstation.com/en-us/support/hardware/ps3/system-software/ .
  * RPCS3 itself. It is free and open source, but shipping a frozen copy means shipping
    a build that rots and a licence obligation to match. Get it from rpcs3.net .

So the zip configures RPCS3; it does not contain it. That is the honest version of
"ready to play" and the only version that is legal to hand someone.

    python tools/make_release.py                 # build from the tree as it stands
    python tools/make_release.py --require-vault # refuse unless the Japanese is locked

Run it on a LOCKED snapshot (tools/make_anon_snapshot.py) if the zip is going public,
so the game's script is not inside it either.
"""
import os, re, subprocess, sys, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(REPO), "og2-english-patch.zip")
TOP = "og2-english-patch"
CJK = re.compile(r"[぀-ヿ一-鿿]")

INSTRUCTIONS = """\
2nd Super Robot Taisen OG - English patch
=========================================

THE TRANSLATION IS MACHINE GENERATED. The English came from a large language model, not
a human translator, and the dialogue was not proofread line by line. Read README.md
before you install: it explains exactly what that means and what to expect.

WHAT YOU NEED, none of which is in this zip:
  1. RPCS3                 https://rpcs3.net
  2. PS3 firmware          https://www.playstation.com/en-us/support/hardware/ps3/system-software/
                           install it in RPCS3 via File > Install Firmware
  3. Your own dump of BLJS10133 (Dai-2-Ji Super Robot Taisen OG)
  4. Python 3.10 or newer, then:  pip install cryptography capstone

INSTALL
  1. Configure RPCS3 for this game:
         python tools/setup_rpcs3.py "<your RPCS3 folder>"

  2. Patch your copy of the game. Either double-click

         Install (GUI).bat

     or run:

         python apply.py "<...>/BLJS10133/PS3_GAME/USRDIR" --gd "<...>/dev_hdd0/game/BLJS10133"

     Point it at a COPY of your game, not your only one. It rebuilds the containers in
     place and keeps a rollback of everything it replaces.

  3. Optional but recommended, for correct letter spacing:
     in RPCS3, Utilities > Decrypt PS3 Binaries on your EBOOT.BIN, then re-run step 2
     adding  --eboot-elf "<the EBOOT.elf that produced>".

  4. Boot the game in RPCS3.

The English text lives in this zip; the game's original Japanese does not. A few build
steps need it, so it is stored encrypted in build/jp_vault.enc under a key derived from
your own disc files, and the installer unlocks it as it runs. If you own the game you
will never notice. If you do not, this zip gives you nothing.

Settings used: Vulkan, 1280x720, LLVM recompilers, SPU block size Safe, colour buffers
off. tools/setup_rpcs3.py writes them as a per-game config, leaving your global RPCS3
settings alone.
"""


def tracked():
    r = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True)
    return [p for p in r.stdout.splitlines() if p.strip()]


def main():
    files = tracked()
    if not files:
        sys.exit("no tracked files; run this inside the repository")
    vault = os.path.join(REPO, "build", "jp_vault.enc")
    locked = os.path.exists(vault)
    if "--require-vault" in sys.argv and not locked:
        sys.exit("refusing: build/jp_vault.enc is absent, so the worksheets still carry\n"
                 "the game's Japanese. Run tools/make_anon_snapshot.py first.")

    n_jp = 0
    written = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in files:
            p = os.path.join(REPO, rel)
            if not os.path.isfile(p):
                continue                       # tracked but deleted by the snapshot step
            written += 1
            data = open(p, "rb").read()
            if rel.endswith((".json", ".md", ".py", ".txt", ".yml")):
                try:
                    n_jp += len(CJK.findall(data.decode("utf-8")))
                except UnicodeDecodeError:
                    pass
            z.writestr(TOP + "/" + rel, data)
        if locked and "build/jp_vault.enc" not in files:
            z.write(vault, TOP + "/build/jp_vault.enc")     # present but untracked
        z.writestr(TOP + "/INSTALL.txt", INSTRUCTIONS)

    size = os.path.getsize(OUT)
    print("wrote %s (%.1f MB, %d files)" % (OUT, size / 1e6, written + 1))
    print("japanese vault: %s" % ("locked in" if locked else "ABSENT - worksheets carry the script"))
    print("japanese characters inside the zip's text files: %d" % n_jp)
    if n_jp > 20000:
        print("\nWARNING: that is a lot. If this zip is going public, build it from a\n"
              "locked snapshot instead (tools/make_anon_snapshot.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
