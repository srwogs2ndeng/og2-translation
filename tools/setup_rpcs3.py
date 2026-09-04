#!/usr/bin/env python3
"""setup_rpcs3.py - install the per-game RPCS3 settings for this title.

Writes installer/config_BLJS10133.yml into your RPCS3's custom-config folder, so the
game boots with the settings the patch was developed and played on. Everything not
listed in that file keeps whatever your global RPCS3 configuration says.

    python tools/setup_rpcs3.py "C:/path/to/rpcs3"        # folder containing rpcs3.exe
    python tools/setup_rpcs3.py "C:/path/to/rpcs3" --show # print what it would write

It backs up any custom config you already have for this title before replacing it.
It does not touch your global config, your firmware, or your save data.
"""
import os, shutil, sys, datetime

TITLE = "BLJS10133"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "installer", "config_%s.yml" % TITLE)


def find_config_dir(rpcs3_dir):
    """RPCS3 keeps custom configs next to the executable on Windows portable installs,
    and under the user config directory otherwise. Prefer whichever already exists."""
    candidates = [os.path.join(rpcs3_dir, "config", "custom_configs")]
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(os.path.join(appdata, "rpcs3", "config", "custom_configs"))
    else:
        candidates.append(os.path.join(os.path.expanduser("~"), ".config", "rpcs3",
                                       "custom_configs"))
    for c in candidates:
        if os.path.isdir(os.path.dirname(c)):
            return c
    return candidates[0]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if not os.path.isfile(SRC):
        sys.exit("missing %s" % SRC)
    if "--show" in sys.argv:
        sys.stdout.write(open(SRC, encoding="utf-8").read())
        return 0

    rpcs3_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(rpcs3_dir):
        sys.exit("not a folder: %s" % rpcs3_dir)
    exe = any(os.path.isfile(os.path.join(rpcs3_dir, n))
              for n in ("rpcs3.exe", "rpcs3", "rpcs3.AppImage"))
    if not exe:
        print("warning: no rpcs3 executable in %s - is this the right folder?" % rpcs3_dir)

    dest_dir = find_config_dir(rpcs3_dir)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "config_%s.yml" % TITLE)
    if os.path.exists(dest):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = dest + "." + stamp + ".bak"
        shutil.copy2(dest, backup)
        print("backed up your existing config -> %s" % backup)
    shutil.copy2(SRC, dest)
    print("installed %s" % dest)
    print("\nRPCS3 will use these settings for %s. Right-click the game in RPCS3 and\n"
          "choose 'Change Custom Configuration' to review or adjust them." % TITLE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
