#!/usr/bin/env python3
"""git_account_gui.py - desktop front end for git_account.

Same engine as the CLI (it imports git_account and calls its functions), so there is one
implementation of the rules, the token resolution and the push. This module is only
presentation.

    python tools/git_account_gui.py
    git-account-gui.exe                     (built by tools/build_git_account.py --gui)

TOKENS ARE NEVER DISPLAYED. The entry that accepts one is masked, its variable is
cleared as soon as the token is written, and every status line reports the SOURCE a
token came from rather than the token. The log pane cannot show one either: the only
thing that ever touches a token is the engine, which puts it in a child process's
environment.

Git and gh calls run on a worker thread so the window never freezes, and only one runs
at a time (the action buttons disable while one is in flight). The engine's CWD global
is set from the repository picker, so nothing has to chdir the process.
"""
import os, queue, subprocess, sys, threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_account as G

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:                                        # pragma: no cover
    sys.exit("tkinter is not available in this Python build")

PAD = 8


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("git-account - GitHub identity per repository")
        self.geometry("980x680")
        self.minsize(820, 560)
        self._q = queue.Queue()
        self._busy = False
        self._build()
        self.after(80, self._drain)
        start = os.getcwd()
        top = self._git_top(start)
        self.repo.set(top or start)
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=3)
        self.rowconfigure(4, weight=2)

        bar = ttk.Frame(self, padding=(PAD, PAD, PAD, 0))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="Repository").grid(row=0, column=0, padx=(0, PAD))
        self.repo = tk.StringVar()
        ttk.Entry(bar, textvariable=self.repo).grid(row=0, column=1, sticky="ew")
        self.btn_browse = ttk.Button(bar, text="Browse...", command=self.pick_repo)
        self.btn_browse.grid(row=0, column=2, padx=(PAD, 0))
        self.btn_refresh = ttk.Button(bar, text="Refresh", command=self.refresh)
        self.btn_refresh.grid(row=0, column=3, padx=(PAD, 0))

        self.summary = ttk.Label(self, padding=(PAD, 4), foreground="#444")
        self.summary.grid(row=1, column=0, sticky="ew")

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.grid(row=2, column=0, sticky="nsew", padx=PAD, pady=(0, PAD))

        # --- remotes
        left = ttk.Labelframe(panes, text="Remotes in this repository", padding=PAD)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.rtree = ttk.Treeview(left, columns=("remote", "url", "account", "how"),
                                  show="headings", selectmode="browse")
        for c, w, txt in (("remote", 90, "Remote"), ("url", 300, "URL"),
                          ("account", 150, "Must push as"), ("how", 220, "Credential")):
            self.rtree.heading(c, text=txt)
            self.rtree.column(c, width=w, anchor="w")
        self.rtree.grid(row=0, column=0, sticky="nsew")
        rsb = ttk.Scrollbar(left, orient="vertical", command=self.rtree.yview)
        rsb.grid(row=0, column=1, sticky="ns")
        self.rtree.configure(yscrollcommand=rsb.set)
        rb = ttk.Frame(left)
        rb.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(PAD, 0))
        self.btn_push = ttk.Button(rb, text="Push selected remote", command=self.do_push)
        self.btn_push.pack(side="left")
        self.btn_hook = ttk.Button(rb, text="Install pre-push guard", command=self.do_hook)
        self.btn_hook.pack(side="left", padx=(PAD, 0))
        panes.add(left, weight=3)

        # --- accounts
        right = ttk.Labelframe(panes, text="Accounts", padding=PAD)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.atree = ttk.Treeview(right, columns=("cred",), show="tree headings", selectmode="browse")
        self.atree.heading("#0", text="Account")
        self.atree.heading("cred", text="Credential source")
        self.atree.column("#0", width=170)
        self.atree.column("cred", width=230)
        self.atree.grid(row=0, column=0, sticky="nsew")
        ab = ttk.Frame(right)
        ab.grid(row=1, column=0, sticky="ew", pady=(PAD, 0))
        self.btn_tok = ttk.Button(ab, text="Set token...", command=self.set_token)
        self.btn_tok.pack(side="left")
        self.btn_forget = ttk.Button(ab, text="Forget token", command=self.forget_token)
        self.btn_forget.pack(side="left", padx=(PAD, 0))
        panes.add(right, weight=2)

        # --- rules
        rules = ttk.Labelframe(self, text="Rules  (a remote URL containing the text pushes as that account)",
                               padding=PAD)
        rules.grid(row=3, column=0, sticky="ew", padx=PAD)
        rules.columnconfigure(0, weight=1)
        self.ltree = ttk.Treeview(rules, columns=("match", "account"), show="headings", height=4,
                                  selectmode="browse")
        self.ltree.heading("match", text="URL contains")
        self.ltree.heading("account", text="Push as")
        self.ltree.column("match", width=460)
        self.ltree.column("account", width=200)
        self.ltree.grid(row=0, column=0, sticky="ew")
        form = ttk.Frame(rules)
        form.grid(row=1, column=0, sticky="ew", pady=(PAD, 0))
        ttk.Label(form, text="URL contains").pack(side="left")
        self.f_match = tk.StringVar()
        ttk.Entry(form, textvariable=self.f_match, width=42).pack(side="left", padx=(4, PAD))
        ttk.Label(form, text="push as").pack(side="left")
        self.f_acct = tk.StringVar()
        ttk.Entry(form, textvariable=self.f_acct, width=22).pack(side="left", padx=(4, PAD))
        ttk.Button(form, text="Add / update", command=self.add_rule).pack(side="left")
        ttk.Button(form, text="Remove selected", command=self.del_rule).pack(side="left", padx=(PAD, 0))

        log = ttk.Labelframe(self, text="Output", padding=PAD)
        log.grid(row=4, column=0, sticky="nsew", padx=PAD, pady=PAD)
        log.columnconfigure(0, weight=1)
        log.rowconfigure(0, weight=1)
        self.log = tk.Text(log, height=8, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(log, orient="vertical", command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)

    # ------------------------------------------------------------------ helpers
    def say(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _git_top(self, path):
        try:
            r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                               capture_output=True, text=True)
            return r.stdout.strip() or None
        except OSError:
            return None

    def _set_busy(self, busy):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_push, self.btn_hook, self.btn_tok, self.btn_forget,
                  self.btn_browse, self.btn_refresh):
            b.configure(state=state)
        self.configure(cursor="watch" if busy else "")

    def _work(self, fn, done=None):
        """Run fn() off the UI thread; post its result back through the queue."""
        if self._busy:
            return
        self._set_busy(True)

        def runner():
            try:
                out = fn()
                self._q.put(("ok", out, done))
            except Exception as e:                      # surfaced, never swallowed
                self._q.put(("err", "%s: %s" % (type(e).__name__, e), done))
        threading.Thread(target=runner, daemon=True).start()

    def _drain(self):
        try:
            while True:
                kind, payload, done = self._q.get_nowait()
                self._set_busy(False)
                if kind == "err":
                    self.say("ERROR " + payload)
                elif payload:
                    self.say(payload)
                if done:
                    try:
                        done()
                    except Exception as e:
                        self.say("ERROR while updating the view: %s: %s" % (type(e).__name__, e))
        except queue.Empty:
            pass
        self.after(80, self._drain)

    def _sync_engine(self):
        """Point the engine at the chosen repo. Returns None when the path is not a git
        repository -- it must never silently fall back to this process's own directory,
        which would act on whatever folder the GUI happened to be started in."""
        path = self.repo.get().strip()
        if not path or not os.path.isdir(path) or not self._git_top(path):
            G.CWD = None
            return None
        G.CWD = path
        return path

    # ------------------------------------------------------------------ actions
    def pick_repo(self):
        d = filedialog.askdirectory(title="Choose a git repository",
                                    initialdir=self.repo.get() or os.getcwd())
        if d:
            self.repo.set(self._git_top(d) or d)
            self.refresh()

    def refresh(self):
        cwd = self._sync_engine()
        if not cwd:
            self.summary.configure(text="Not a git repository - pick another folder.")
            for tree in (self.rtree, self.atree, self.ltree):
                tree.delete(*tree.get_children())
            return

        def gather():
            cfg = G.load()
            accts = G.accounts()          # None means gh could not be read at all
            gh_ok = accts is not None
            accts = accts or []
            act = G.active()
            rem = G.remotes()
            rows = []
            # remotes() yields (fetch_url, push_url); the PUSH url is what decides the
            # identity, and it is the one worth showing.
            for name, (furl, purl) in sorted(rem.items()):
                exp = G.expected(purl, cfg)
                if exp is None:
                    how = "unmapped - any account could push"
                else:
                    src = G.token_source(exp)
                    if src and not src.startswith("gh"):
                        how = ("PAT via %s" % src) if G.is_github_https(purl) \
                              else "PAT REFUSED - not an https %s URL" % G.HOST
                    elif src:
                        how = "gh switch" + ("" if exp == act else " (active: %s)" % (act or "none"))
                    else:
                        how = "NO CREDENTIAL"
                shown = purl if furl == purl else "%s   (fetches %s)" % (purl, furl)
                rows.append((name, shown, exp or "-", how))
            names = sorted({r["account"] for r in cfg["rules"] if r.get("account")}
                           | {a for a, _ in accts})
            acct_rows = [(a, G.token_source(a) or "none") for a in names]
            rules = [(r.get("match", ""), r.get("account", "")) for r in cfg["rules"]]
            return {"rows": rows, "accts": acct_rows, "rules": rules, "active": act,
                    "gh_ok": gh_ok}

        def runner():
            # An unhandled exception here used to kill the thread with _busy still True,
            # disabling every button for the rest of the session.
            try:
                data = gather()
                self._q.put(("ok", "", lambda d=data: self._paint(d)))
            except Exception as e:
                self._q.put(("err", "%s: %s" % (type(e).__name__, e), None))

        if self._busy:
            return
        self._set_busy(True)
        threading.Thread(target=runner, daemon=True).start()

    def _paint(self, d):
        self.summary.configure(text="Active gh account: %s     rules file: %s"
                                    % (d["active"] or ("none" if d.get("gh_ok", True)
                                                       else "UNAVAILABLE (gh failed)"),
                                       G.CONFIG))
        self.rtree.delete(*self.rtree.get_children())
        for name, url, exp, how in d["rows"]:
            self.rtree.insert("", "end", iid=name, values=(name, url, exp, how))
        self.atree.delete(*self.atree.get_children())
        for a, src in d["accts"]:
            self.atree.insert("", "end", iid=a, text=a, values=(src,))
        self.ltree.delete(*self.ltree.get_children())
        for i, (m, a) in enumerate(d["rules"]):
            self.ltree.insert("", "end", iid=str(i), values=(m, a))

    def _selected_remote(self):
        sel = self.rtree.selection()
        return sel[0] if sel else None

    def _selected_account(self):
        sel = self.atree.selection()
        return sel[0] if sel else None

    def do_push(self):
        if self._busy:
            return
        remote = self._selected_remote()
        if not remote:
            messagebox.showinfo("git-account", "Select a remote first.")
            return
        repo = self._sync_engine()
        if not repo:
            messagebox.showerror("git-account", "That folder is not a git repository.")
            return
        url, exp = G.resolve(remote)
        if not exp:
            messagebox.showwarning("git-account",
                                   "No rule matches\n%s\n\nAdd one below." % url)
            return
        pat, src = G.pat_for(exp)
        if pat and not G.is_github_https(url):
            messagebox.showerror("git-account",
                                 "Refusing to send %s's token to\n%s\n\nA PAT is only ever "
                                 "attached to an https %s URL." % (exp, url, G.HOST))
            return
        if not pat:
            known = G.accounts()
            if known is None:
                messagebox.showerror("git-account",
                                     "Cannot read gh's account state, so switching accounts "
                                     "is not safe.\nGive %s its own token instead." % exp)
                return
            if exp not in [a for a, _ in known]:
                messagebox.showerror("git-account",
                                     "No credential for %s.\nUse \"Set token...\" or sign it "
                                     "into gh." % exp)
                return
        how = ("PAT via %s" % src) if pat else "gh account switch"
        if not messagebox.askokcancel("Push", "Push %s\n  %s\nas %s\n  (%s)"
                                              % (remote, url, exp, how)):
            return
        self.say("--- pushing %s as %s [%s] ---" % (remote, exp, how))

        # Bind the repository NOW. G.CWD is a module global that Browse could otherwise
        # change between this click and the subprocess actually starting.
        cwd = repo

        def job():
            if pat:
                r = subprocess.run(["git", "push", remote], cwd=cwd,
                                   env=G.authed_env(pat, url, exp),
                                   capture_output=True, text=True)
            else:
                known = G.accounts() or []
                before = next((a for a, b in known if b), None)
                if not G.switch(exp):
                    return "could not switch gh to %s" % exp
                restored = True
                try:
                    r = subprocess.run(["git", "push", remote], cwd=cwd,
                                       capture_output=True, text=True)
                finally:
                    if before and before != exp:
                        restored = G.switch(before)
                if not restored:
                    return ("PUSH DONE, BUT THE ACTIVE ACCOUNT WAS NOT RESTORED.\n"
                            "gh is STILL %s - every plain `git push` from this machine will "
                            "go out as that account.\nPut it back with:  gh auth switch "
                            "--user %s" % (exp, before))
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode and "could not read Username" in out:
                out += ("\nThat means GitHub REJECTED the token: expired, wrong account, or "
                        "not scoped to this repository with Contents: read and write.")
            return out.strip() or ("push finished, exit %d" % r.returncode)
        self._work(job, done=self.refresh)

    def do_hook(self):
        self._sync_engine()

        def job():
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    G.cmd_install_hook()
                except SystemExit as e:
                    return str(e)
            return buf.getvalue()
        self._work(job)

    def set_token(self):
        acct = self._selected_account() or self.f_acct.get().strip()
        if not acct:
            messagebox.showinfo("git-account", "Select an account, or type one in the rule box.")
            return
        TokenDialog(self, acct, on_saved=self.refresh)

    def forget_token(self):
        acct = self._selected_account()
        if not acct:
            messagebox.showinfo("git-account", "Select an account first.")
            return
        p = G.token_path(acct)
        if not os.path.exists(p):
            messagebox.showinfo("git-account", "No stored token for %s.\n(%s)" % (acct, p))
            return
        if messagebox.askokcancel("Forget token", "Delete the stored token for %s?\n\n%s" % (acct, p)):
            os.remove(p)
            self.say("deleted %s" % p)
            if os.environ.get(G.env_var_for(acct)):
                self.say("NOTE: %s is still set in the environment and takes precedence."
                         % G.env_var_for(acct))
            self.refresh()

    def add_rule(self):
        m, a = self.f_match.get().strip(), self.f_acct.get().strip()
        if not m or not a:
            messagebox.showinfo("git-account", "Both fields are needed.")
            return
        cfg = G.load()
        for r in cfg["rules"]:
            if r.get("match") == m:
                r["account"] = a
                break
        else:
            cfg["rules"].append({"match": m, "account": a})
        G.save(cfg)
        self.say("mapped %r -> %s" % (m, a))
        self.f_match.set("")
        self.refresh()

    def del_rule(self):
        sel = self.ltree.selection()
        if not sel:
            messagebox.showinfo("git-account", "Select a rule first.")
            return
        m, a = self.ltree.item(sel[0], "values")
        cfg = G.load()
        cfg["rules"] = [r for r in cfg["rules"] if r.get("match") != m]
        G.save(cfg)
        self.say("removed rule %r" % m)
        self.refresh()


class TokenDialog(tk.Toplevel):
    """Masked, one-shot token entry. The value is written straight to the engine's store
    and cleared from the widget; it is never logged, echoed or kept on the instance."""

    def __init__(self, parent, account, on_saved=None):
        super().__init__(parent)
        self.title("Token for %s" % account)
        self.account = account
        self.on_saved = on_saved
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        f = ttk.Frame(self, padding=PAD * 2)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Fine-grained personal access token for %s" % account,
                  font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(f, justify="left", foreground="#444",
                  text=("Scope it to only the repositories it may touch, with\n"
                        "Repository permissions -> Contents: Read and write.\n"
                        "It is stored readable only by you, and never shown again.")
                  ).pack(anchor="w", pady=(4, PAD))
        self.var = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.var, show="•", width=54)
        e.pack(fill="x")
        e.focus_set()
        self.note = ttk.Label(f, text="", foreground="#a00")
        self.note.pack(anchor="w", pady=(4, 0))
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(PAD, 0))
        ttk.Button(b, text="Save", command=self.save).pack(side="right")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=(0, PAD))
        self.bind("<Return>", lambda _e: self.save())
        self.bind("<Escape>", lambda _e: self.destroy())

    def save(self):
        tok = self.var.get().strip()
        self.var.set("")                      # clear the widget before anything else
        if not tok:
            self.note.configure(text="Nothing entered.")
            return
        if not tok.startswith(G.TOKEN_PREFIXES):
            self.note.configure(text="That does not look like a GitHub token.")
            return
        p = G.token_path(self.account)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(tok + "\n")
        try:
            import stat as _s
            os.chmod(p, _s.S_IRUSR | _s.S_IWUSR)
        except OSError:
            pass
        del tok
        parent = self.master
        self.destroy()
        parent.say("stored a token for %s -> %s" % (self.account, p))
        if self.on_saved:
            self.on_saved()


def main():
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
