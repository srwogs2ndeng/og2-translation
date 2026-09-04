#!/usr/bin/env python3
"""build_git_account.py - build git-account into standalone executables.

Two binaries from one engine:
  * git-account       console. The name matters: git runs any `git-<name>` found on PATH
                      as the subcommand `git <name>`, so this becomes `git account status`,
                      `git account push origin`, with no alias or wrapper.
  * git-account-gui   windowed. Same engine (it imports git_account), so the rules, the
                      token resolution and the push have exactly one implementation.

    python tools/build_git_account.py             # build both -> build/bin/
    python tools/build_git_account.py --install   # also copy to the per-user programs dir
    python tools/build_git_account.py --cli-only  # skip the GUI

--install copies to %LOCALAPPDATA%\\Programs\\git-account (or ~/.local/bin) and prints the
one command needed to put that directory on PATH. It does NOT edit PATH itself: that is
the user's environment, and a tool that silently rewrites it is one you cannot reason
about later.

Needs pyinstaller (pip install pyinstaller).
"""
import os, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(REPO, "build", "bin")
WORK = os.path.join(REPO, "build", "_pyinstaller")
SUFFIX = ".exe" if os.name == "nt" else ""

ENGINE = os.path.join(REPO, "tools", "git_account.py")
GUI = os.path.join(REPO, "tools", "git_account_gui.py")

TARGETS = [
    # (binary name, entry point, windowed, every source it is built from)
    # The GUI imports the engine, so a binary built before an ENGINE edit is stale even
    # though its own entry point has not changed. Freshness is judged against ALL of
    # these, not just the entry point.
    ("git-account", ENGINE, False, [ENGINE]),
    ("git-account-gui", GUI, True, [GUI, ENGINE]),
]


def install_dir():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Programs", "git-account")
    return os.path.join(os.path.expanduser("~"), ".local", "bin")


def build_one(name, src, windowed, deps):
    exe = name + SUFFIX
    built = os.path.join(OUTDIR, exe)
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile",
           "--windowed" if windowed else "--console",
           "--name", name, "--distpath", OUTDIR, "--workpath", WORK,
           "--specpath", WORK, "--noconfirm", src]
    # JUDGE THE BUILD BY THE ARTIFACT, NOT THE EXIT CODE, in both directions.
    #  * rc can be non-zero on a GOOD build: pyinstaller here dies with 0xC0000005
    #    (rc 3221225477) in its own shutdown, sometimes AFTER writing a working exe.
    #  * rc can be zero without writing anything: when nothing changed it reuses the
    #    previous build, so "was it rewritten just now" is the wrong question too.
    # What matters is that the binary is at least as new as its source, then that it runs.
    #
    # That crash is also intermittent: the identical command can crash before writing on
    # one run and after writing on the next, so a single failure is not evidence of a
    # broken build. Retry once before believing it.
    def current():
        if not os.path.exists(built):
            return False
        newest = max(os.path.getmtime(d) for d in deps)
        return os.path.getmtime(built) >= newest

    attempts = 2
    for attempt in range(1, attempts + 1):
        print("building %s ...%s" % (exe, "" if attempt == 1 else "  (retry %d)" % attempt))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if current():
            break
        if attempt < attempts:
            print("  pyinstaller rc %d and no fresh binary; retrying once" % r.returncode)
    else:
        sys.stdout.write(r.stdout[-4000:])
        sys.stderr.write(r.stderr[-4000:])
        sys.exit("no %s newer than its sources (%s) after %d attempts (last pyinstaller rc %d)"
                 % (exe, ", ".join(os.path.basename(d) for d in deps), attempts, r.returncode))
    if r.returncode != 0:
        print("  note: pyinstaller exited %d (it crashes on shutdown here); the exe is "
              "current" % r.returncode)
    print("  built %s (%.1f MB)" % (built, os.path.getsize(built) / 1e6))
    return built


def smoke_cli(path):
    t = subprocess.run([path, "status"], capture_output=True, text=True, timeout=120)
    if t.returncode not in (0, 1):          # 1 = "a remote has no credential", still valid
        sys.stdout.write(t.stdout)
        sys.stderr.write(t.stderr)
        sys.exit("built CLI failed to run")
    print("  smoke test OK (exit %d)" % t.returncode)


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("pyinstaller is not installed:  python -m pip install pyinstaller")
    os.makedirs(OUTDIR, exist_ok=True)
    targets = TARGETS[:1] if "--cli-only" in sys.argv else TARGETS
    built = []
    for name, src, windowed, deps in targets:
        for d in deps:
            if not os.path.exists(d):
                sys.exit("missing %s" % d)
        p = build_one(name, src, windowed, deps)
        if not windowed:
            smoke_cli(p)        # a GUI binary cannot be smoke-tested without a desktop
        built.append(p)

    if "--install" in sys.argv:
        d = install_dir()
        os.makedirs(d, exist_ok=True)
        for p in built:
            dst = os.path.join(d, os.path.basename(p))
            shutil.copy2(p, dst)
            print("installed -> %s" % dst)
        # Check the PERSISTED PATH, not just this process's copy. A shell started before
        # the directory was added carries a stale environment, and testing os.environ
        # alone would tell someone to add an entry they already have.
        candidates = os.environ.get("PATH", "")
        if os.name == "nt":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                    candidates += os.pathsep + winreg.QueryValueEx(k, "Path")[0]
            except OSError:
                pass
        on_path = any(os.path.normcase(os.path.abspath(x)) == os.path.normcase(d)
                      for x in candidates.split(os.pathsep) if x)
        if on_path:
            print("that directory is on PATH: `git account status` works in a new shell")
        elif os.name == "nt":
            # NOT `setx PATH "%PATH%;..."`. That expands to machine PATH + user PATH and
            # writes the union back into the USER variable, permanently duplicating every
            # system entry, and setx silently truncates past 1024 characters. Edit only
            # the User scope, read from the registry rather than from %PATH%.
            print("\nadd it to PATH (once, then open a new terminal). In PowerShell:\n"
                  "  $u=[Environment]::GetEnvironmentVariable('Path','User'); "
                  "[Environment]::SetEnvironmentVariable('Path', $u+';{0}', 'User')".format(d))
        else:
            print("\nadd it to PATH (once):\n  export PATH=\"$PATH:%s\"   # in ~/.profile" % d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
