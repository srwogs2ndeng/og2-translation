#!/usr/bin/env python3
"""git_account.py - per-repo GitHub identity: which account pushes where, and with what.

THE PROBLEM THIS SOLVES. One machine, several GitHub identities. `gh` is git's
credential helper for github.com, so whichever account is ACTIVE in gh authenticates
EVERY push, whatever remote it targets. Push to the wrong remote with the wrong account
active and you get either a 403 or, worse, a silent success that links two identities
you deliberately kept apart.

TWO WAYS TO AUTHENTICATE, and this picks the better one automatically:

  * A PAT bound to that account (preferred). The token is injected for ONE git
    invocation and the credential helper is switched off for it, so gh's active account
    is never consulted and nothing global changes. This is what makes a separated
    identity safe: no switching, no ambient state, no chance of the wrong token going
    out. Modelled on the icraft launcher's server-box log-push.
  * Otherwise gh: switch active account, run, switch back. If the switch back fails, or
    the account state could not be read in the first place, the command FAILS LOUDLY
    rather than leaving an unexpected identity armed for the next plain `git push`.

TOKEN RESOLUTION, in order, per account:
  1. env  GIT_PAT_<ACCOUNT>          (upper-cased, non-alphanumerics -> _)
  2. file <config>/git-account/<account>.token   (0600; `save-token` writes it)
  3. gh, if it knows the account
`status` reports WHICH source answered and never the token itself.

Built as git-account.exe and placed on PATH, git exposes it as its own subcommand: git
runs any git-<name> found on PATH as `git <name>`. Both forms work, exe form shown:

    git account status                        # who may push where, and with what
    git account map <url-substring> <account>
    git account unmap <url-substring>
    git account save-token <account>          # reads the token from stdin, never argv
    git account forget-token <account>
    git account use <remote-or-url>           # gh account switch only
    git account push <remote> [args...]
    git account install-hook

THE PUSH URL DECIDES, NOT THE FETCH URL. `git remote -v` prints the fetch line first,
and a remote can carry a separate remote.<name>.pushurl. Choosing the identity from the
fetch URL would send one account's token to whatever repo the push URL names -- so
rules are matched against the PUSH url, which is where git actually connects.

THE TOKEN ONLY EVER GOES TO GITHUB OVER HTTPS. Rules are plain substrings, so one could
match a remote on any host; before a PAT is used the URL is parsed and must be https on
github.com. The header is also scoped with `http.<url>.extraHeader`, so git will not
carry it to a different host even across a redirect.

WHY BASIC AND NOT BEARER. GitHub's REST API takes `Authorization: Bearer <pat>`, but
the git smart-HTTP endpoint canonicalises on Basic with the PAT as the password; Bearer
gets rejected and git falls through to prompting. So: Basic, user `x-access-token`.
(Learned the hard way in the icraft launcher, 2026-05-08.)

WHY ENV AND NOT `-c`. The header carries the token, and `git -c http.extraHeader=...`
puts it in argv, which peer processes can read (`ps aux`, WMI). GIT_CONFIG_COUNT /
GIT_CONFIG_KEY_n / GIT_CONFIG_VALUE_n (git 2.31+) does the same job through the
environment, which is owner-only on Linux and not casually readable on Windows. Neither
form ever touches .git/config, shell history or the reflog.

WHY THE HOOK IS ONLY A BACKSTOP. git asks the remote what it already has before it can
tell pre-push what would be pushed, so on a PRIVATE https remote it has authenticated
once by the time the hook runs. The hook stops the WRITE; it does not stop that first
request. For identity separation use `push`, which authenticates correctly from the
start. Install the hook for the day you forget.
"""
import base64, json, os, stat, subprocess, sys
try:
    from urllib.parse import urlsplit
except ImportError:                                        # pragma: no cover
    from urlparse import urlsplit                          # type: ignore

HOST = "github.com"
CONFIG = os.environ.get("GIT_ACCOUNT_CONFIG") or os.path.join(
    os.path.expanduser("~"), ".git-account.json")
TOKEN_PREFIXES = ("ghp_", "github_pat_", "gho_", "ghu_", "ghs_")

# Set by authed_env() so the pre-push hook can tell "this tool authenticated the push"
# from "some unrelated git config happened to be injected". Carries the account name so
# the hook can also confirm it is the account the rules asked for.
AUTHED_MARKER = "GIT_ACCOUNT_AUTHED"

# Runs either as a script or as the PyInstaller-built git-account.exe. When that exe is
# on PATH, git itself exposes it as the subcommand `git account ...` (git runs any
# git-<name> on PATH as `git <name>`), which is the intended way to use it.
FROZEN = bool(getattr(sys, "frozen", False))
SELF = os.path.abspath(sys.executable if FROZEN else __file__)

# Which repository the git calls apply to. None = the process's own directory, which is
# what the CLI wants. The GUI points this at whatever repo the user picked, so nothing
# has to chdir the whole process (which would race between background actions).
CWD = None


def self_cmd():
    """Argv prefix that re-invokes this program, however it was built."""
    return [SELF] if FROZEN else [sys.executable, SELF]


def how_to_call():
    """What to tell the user to type."""
    return "git account" if FROZEN else "python tools/git_account.py"


def _warn(msg):
    """Write a warning without assuming stderr exists. A --windowed PyInstaller build
    has sys.stderr set to None, and an unguarded write there raises AttributeError --
    which previously aborted the gh restore and left the wrong account active."""
    try:
        if sys.stderr is not None:
            sys.stderr.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _run(cmd, **kw):
    kw.setdefault("cwd", CWD)
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------- rules (no secrets)

def load():
    if not os.path.exists(CONFIG):
        return {"rules": []}
    with open(CONFIG, encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("rules", [])
    return d


def save(d):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
        f.write("\n")


def expected(url, cfg=None):
    """The account a URL must be pushed as: longest matching rule wins."""
    cfg = cfg or load()
    best = None
    for rule in cfg["rules"]:
        m = rule.get("match", "")
        if m and m.lower() in (url or "").lower():
            if best is None or len(m) > len(best["match"]):
                best = rule
    return best["account"] if best else None


def is_github_https(url):
    """True only for https://github.com/... (or a github.com subdomain).

    Rules are substrings, so a rule meant for a github repo can match a remote on any
    host -- and the injected Authorization header would then be sent there. The PAT path
    is gated on this."""
    if not url:
        return False
    try:
        u = urlsplit(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and (host == HOST or host.endswith("." + HOST))


def remotes():
    """name -> (fetch_url, push_url).

    `git remote -v` prints two lines per remote, `(fetch)` then `(push)`, and they
    differ whenever remote.<name>.pushurl is set. Keeping only the first line -- as this
    did originally -- picks the identity from a URL git may never contact."""
    seen = {}
    for line in _run(["git", "remote", "-v"]).stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name, url, kind = parts[0], parts[1], parts[2]
        f, p = seen.get(name, (None, None))
        if kind == "(push)":
            p = url
        elif kind == "(fetch)":
            f = url
        seen[name] = (f, p)
    return {n: (f or p, p or f) for n, (f, p) in seen.items()}


def push_url(target):
    """The URL git will actually push to, for a remote name or a bare URL."""
    r = remotes().get(target)
    if r:
        return r[1]
    g = _run(["git", "remote", "get-url", "--push", target])
    if g.returncode == 0 and g.stdout.strip():
        return g.stdout.strip()
    return target


def resolve(target):
    """(push_url, required_account) -- always decided by the PUSH url."""
    url = push_url(target)
    return url, expected(url)


# ---------------------------------------------------------------- gh accounts

def accounts():
    """[(login, is_active)] known to gh, or None if gh could not be consulted.

    None and [] must stay distinguishable: treating a failed `gh auth status` as "no
    accounts" is how the restore step silently decided there was nothing to restore."""
    r = _run(["gh", "auth", "status", "--json", "hosts"])
    if r.returncode != 0:
        return None
    try:
        hosts = json.loads(r.stdout).get("hosts", {})
    except (json.JSONDecodeError, AttributeError):
        return None
    return [(a.get("login"), bool(a.get("active"))) for a in hosts.get(HOST, [])]


def account_names():
    a = accounts()
    return [x for x, _ in a] if a else []


def active():
    """The active login, or None if there is none OR gh could not be read. Callers that
    must tell those apart should call accounts() themselves."""
    a = accounts()
    if not a:
        return None
    for login, is_active in a:
        if is_active:
            return login
    return None


def switch(login):
    if login == active():
        return True
    r = _run(["gh", "auth", "switch", "--hostname", HOST, "--user", login])
    if r.returncode != 0:
        _warn((r.stderr or r.stdout).strip())
        return False
    return True


# ---------------------------------------------------------------- tokens

def env_var_for(account):
    safe = "".join(c if c.isalnum() else "_" for c in account).upper()
    return "GIT_PAT_" + safe


def token_path(account):
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    if not base:
        base = os.path.expanduser("~")
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in account)
    return os.path.join(base, "git-account", safe + ".token")


def _read_token_file(p):
    try:
        with open(p, encoding="utf-8") as f:
            first = (f.readline() or "").strip()
    except OSError:
        return None
    return first or None


def pat_for(account):
    """(token, source_description) or (None, None). The token is NEVER logged."""
    v = os.environ.get(env_var_for(account), "").strip()
    if v:
        return v, "env %s" % env_var_for(account)
    p = token_path(account)
    t = _read_token_file(p)
    if t:
        return t, "file %s" % p
    return None, None


def token_source(account):
    """Where a token would come from, without returning it."""
    tok, src = pat_for(account)
    if tok:
        return src
    if account in account_names():
        return "gh (keyring)"
    return None


def authed_env(pat, url=None, account=None):
    """Environment that injects Basic auth for one git run, without using argv.

    The header is bound to `url` via http.<url>.extraHeader so git will not present it
    to a different host, even if the request is redirected. Falls back to the github.com
    prefix rather than a bare global header."""
    env = dict(os.environ)
    basic = base64.b64encode(("x-access-token:%s" % pat).encode()).decode()
    scope = url if is_github_https(url) else "https://%s/" % HOST
    entries = [
        ("http.%s.extraHeader" % scope, "Authorization: Basic %s" % basic),
        # switch the helper off for this run: a bad or under-scoped PAT then fails with
        # a real 401/403 instead of silently falling back to gh's ACTIVE account --
        # which is the identity leak this tool exists to prevent.
        ("credential.helper", ""),
    ]
    env["GIT_CONFIG_COUNT"] = str(len(entries))
    for i, (k, v) in enumerate(entries):
        env["GIT_CONFIG_KEY_%d" % i] = k
        env["GIT_CONFIG_VALUE_%d" % i] = v
    env["GIT_TERMINAL_PROMPT"] = "0"
    if account:
        env[AUTHED_MARKER] = account
    return env


# ---------------------------------------------------------------- commands

def cmd_status():
    known = accounts()
    act = active()
    print("rules:  %s%s" % (CONFIG, "" if os.path.exists(CONFIG) else "   (none yet)"))
    if known is None:
        print("gh:     UNAVAILABLE (gh auth status failed)")
    else:
        print("gh:     %s" % (", ".join(("%s <- active" % a) if b else a for a, b in known) or "(none)"))
    cfg = load()
    accts = sorted({r["account"] for r in cfg["rules"] if r.get("account")})
    if accts:
        print("tokens:")
        for a in accts:
            print("  %-24s %s" % (a, token_source(a) or "NONE - cannot push as this account"))
    rem = remotes()
    if not rem:
        print("no git remotes here")
        return 0
    print("remotes:")
    bad = 0
    for name, (furl, purl) in sorted(rem.items()):
        print("  %s  %s" % (name, purl))
        if furl != purl:
            print("      (fetches from %s)" % furl)
        exp = expected(purl, cfg)
        if exp is None:
            print("      unmapped - any account could push this")
            continue
        src = token_source(exp)
        if src and not src.startswith("gh"):
            how = ("PAT via %s" % src) if is_github_https(purl) else \
                  "PAT REFUSED - not an https github.com URL"
            if not is_github_https(purl):
                bad += 1
        elif src:
            how = "gh switch to %s%s" % (exp, "" if exp == act else "  (active is %s)" % (act or "none"))
        else:
            how = "NO CREDENTIAL for %s - `%s save-token %s`, or gh auth login" % (
                exp, how_to_call(), exp)
            bad += 1
        print("      must push as %-22s %s" % (exp, how))
    if bad:
        print("\n%d remote(s) cannot be pushed as their required account." % bad)
    return 1 if bad else 0


def cmd_map(match, account):
    cfg = load()
    for rule in cfg["rules"]:
        if rule.get("match") == match:
            rule["account"] = account
            break
    else:
        cfg["rules"].append({"match": match, "account": account})
    save(cfg)
    print("mapped %r -> %s   (%s)" % (match, account, CONFIG))
    if not token_source(account):
        print("NOTE: no credential for %s yet. Either:\n"
              "  %s save-token %s      (paste a fine-grained PAT)\n"
              "  gh auth login                                  (sign that account into gh)"
              % (account, how_to_call(), account))
    return 0


def cmd_unmap(match):
    cfg = load()
    n = len(cfg["rules"])
    cfg["rules"] = [r for r in cfg["rules"] if r.get("match") != match]
    save(cfg)
    print("removed %d rule(s) for %r" % (n - len(cfg["rules"]), match))
    return 0


def cmd_save_token(account):
    """Read a PAT from STDIN and store it 0600. Never taken as an argument: argv is
    visible to peer processes and lands in shell history."""
    p = token_path(account)
    if sys.stdin.isatty():
        print("Paste the fine-grained PAT for %s, then press Enter." % account)
        print("(scope it to just the repos it may touch, Contents: read and write)")
    tok = (sys.stdin.readline() or "").strip()
    if not tok:
        sys.exit("no token on stdin; nothing written")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(tok + "\n")
    try:
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    print("saved %d-char token for %s -> %s" % (len(tok), account, p))
    if not tok.startswith(TOKEN_PREFIXES):
        print("WARNING: that does not look like a GitHub token (expected one of %s)"
              % ", ".join(TOKEN_PREFIXES))
    return 0


def cmd_forget_token(account):
    p = token_path(account)
    if os.path.exists(p):
        os.remove(p)
        print("deleted %s" % p)
    else:
        print("no stored token at %s" % p)
    if os.environ.get(env_var_for(account)):
        print("NOTE: %s is still set in this environment and takes precedence."
              % env_var_for(account))
    return 0


def cmd_use(target):
    url, exp = resolve(target)
    if not exp:
        sys.exit("no rule matches %s\n  map it:  %s map "
                 "<url-substring> <account>" % (url, how_to_call()))
    if not switch(exp):
        return 1
    print("active account is now %s (for %s)" % (exp, url))
    return 0


def cmd_push(remote, args):
    url, exp = resolve(remote)
    if not exp:
        sys.exit("no rule matches %s\n  map it:  %s map "
                 "<url-substring> <account>" % (url, how_to_call()))
    pat, src = pat_for(exp)

    if pat:
        if not is_github_https(url):
            sys.exit("refusing to send %s's token to %s\n"
                     "  a PAT is only ever attached to an https %s URL; this rule matched "
                     "a remote on another host." % (exp, url, HOST))
        # Nothing global changes and gh is never consulted: the safest path.
        print("pushing to %s as %s  [PAT from %s]" % (url, exp, src))
        rc = subprocess.run(["git", "push", remote] + list(args), cwd=CWD,
                            env=authed_env(pat, url, exp)).returncode
        if rc:
            # With the helper off and prompts disabled, a REJECTED token surfaces as
            # git's generic "could not read Username" rather than a 401. Say what it
            # actually means so nobody goes hunting for a username problem.
            _warn("\nthe push failed. If the error mentions 'could not read Username',\n"
                  "GitHub rejected the token itself - expired, wrong account, or not\n"
                  "scoped to this repo with Contents: read and write.\n"
                  "  token came from: %s\n"
                  "  replace it:      %s save-token %s" % (src, how_to_call(), exp))
        return rc

    # ---- gh fallback: global state changes, so be strict about restoring it ----
    known = accounts()
    if known is None:
        sys.exit("cannot read gh's account state, so switching accounts is not safe.\n"
                 "  fix gh (`gh auth status`), or give %s its own token:\n"
                 "  %s save-token %s" % (exp, how_to_call(), exp))
    if exp not in [a for a, _ in known]:
        sys.exit("no credential for %s.\n"
                 "  %s save-token %s   (paste a PAT)\n"
                 "  gh auth login                                (sign it into gh)"
                 % (exp, how_to_call(), exp))
    before = next((a for a, b in known if b), None)
    if not switch(exp):
        return 1
    print("pushing to %s as %s  [gh account switch]" % (url, exp))
    try:
        rc = subprocess.run(["git", "push", remote] + list(args), cwd=CWD).returncode
    finally:
        restored = True
        if before and before != exp:
            restored = switch(before)
            if restored:
                print("restored active account: %s" % before)
    if before and before != exp and not restored:
        # Never report success while the machine is left authenticated as someone else:
        # every later plain `git push` would go out as this account.
        _warn("\nCOULD NOT RESTORE the active gh account. gh is STILL %s.\n"
              "  put it back with:  gh auth switch --user %s" % (exp, before))
        return rc or 1
    return rc


def hook_text():
    """A /bin/sh pre-push hook that calls back into whichever build installed it, by
    ABSOLUTE path (forward-slashed, which Git Bash and MSYS both accept) so it works
    from any repository and any working directory."""
    if FROZEN:
        target = '"%s"' % SELF.replace("\\", "/")
    else:
        target = '"%s" "%s"' % (sys.executable.replace("\\", "/"), SELF.replace("\\", "/"))
    return ("#!/bin/sh\n"
            "# installed by git-account - refuse a push made as the wrong GitHub account\n"
            "exec %s check-push \"$1\" \"$2\"\n" % target)


def cmd_install_hook():
    top = _run(["git", "rev-parse", "--show-toplevel"]).stdout.strip()
    if not top:
        sys.exit("not inside a git repository")
    d = _run(["git", "rev-parse", "--git-path", "hooks"]).stdout.strip()
    # `--git-path` answers relative to the repository root, not to this process's
    # directory, so it must be joined to `top` or the hook lands next to wherever the
    # GUI happened to be started.
    d = os.path.join(top, d) if d and not os.path.isabs(d) else (d or os.path.join(top, ".git", "hooks"))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "pre-push")
    if os.path.exists(p):
        cur = open(p, encoding="utf-8", errors="replace").read()
        if "git-account" not in cur and "git_account.py" not in cur:
            sys.exit("a different pre-push hook already exists: %s (not overwriting)" % p)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(hook_text())
    os.chmod(p, 0o755)
    print("installed %s" % p)
    return 0


def cmd_check_push(remote, url):
    # git hands the hook the real push URL as $2, so this sees the right one even when
    # a remote.<name>.pushurl is set.
    exp = expected(url or remote)
    if exp is None:
        return 0                                  # unmapped remote: not our business
    marker = os.environ.get(AUTHED_MARKER)
    if marker:
        # Our own `push` already authenticated this run. Only OUR marker counts, and
        # only when it names the account the rules require -- an unrelated
        # GIT_CONFIG_COUNT in the environment must not wave a push through.
        if marker == exp:
            return 0
        _warn("\nREFUSED: this push was authenticated as %s but %s requires %s.\n"
              % (marker, url or remote, exp))
        return 1
    act = active()
    if act == exp:
        return 0
    _warn("\nREFUSED: %s must be pushed as %s, but the active GitHub account is %s.\n"
          "  push correctly:  %s push %s\n"
          "  (bypass with --no-verify if you really mean it)\n"
          % (url or remote, exp, act or "none", how_to_call(), remote))
    return 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, rest = argv[1], argv[2:]
    table = {
        ("status", 0): cmd_status,
        ("map", 2): cmd_map,
        ("unmap", 1): cmd_unmap,
        ("save-token", 1): cmd_save_token,
        ("forget-token", 1): cmd_forget_token,
        ("use", 1): cmd_use,
        ("install-hook", 0): cmd_install_hook,
        ("check-push", 2): cmd_check_push,
    }
    fn = table.get((cmd, len(rest)))
    if fn:
        return fn(*rest)
    if cmd == "push" and rest:
        return cmd_push(rest[0], rest[1:])
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
