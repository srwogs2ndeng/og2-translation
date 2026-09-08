#!/usr/bin/env python3
"""OG2 English Patch — GUI installer.

A thin Tkinter front-end over ../apply.py. Pick your game's USRDIR (and,
optionally, the RPCS3 game-data install to wipe + a decrypted EBOOT.elf),
click Patch, and watch the build run. Nothing is downloaded; your dump stays
local and is patched in place.

Runs on stock Python 3.10+ (Tkinter ships with Python on Windows). No extra
GUI dependencies. apply.py itself still needs:  pip install cryptography capstone

Double-click this file, or run:  pythonw install_gui.pyw
"""
import os
import sys
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog

HERE = os.path.dirname(os.path.abspath(__file__))
# apply.py lives one level up (repo root); fall back to HERE if bundled together.
REPO = os.path.dirname(HERE)
if not os.path.isfile(os.path.join(REPO, "apply.py")) and os.path.isfile(os.path.join(HERE, "apply.py")):
    REPO = HERE
APPLY = os.path.join(REPO, "apply.py")

BG, FG, SUB = "#0f172a", "#e2e8f0", "#94a3b8"
PANEL, BORDER, ACCENT = "#020617", "#334155", "#22d3ee"


def python_exe():
    """Prefer pythonw-less interpreter so the child console pipes cleanly."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.isfile(cand):
            return cand
    return exe


class Installer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OG2 English Patch Installer")
        self.configure(bg=BG)
        self.geometry("640x640")
        self.minsize(520, 560)
        self.val = {"usrdir": tk.StringVar(), "gd": tk.StringVar(), "eboot": tk.StringVar()}
        self.q = queue.Queue()
        self.proc = None
        self._reason = None
        self._task = None          # 'patch' or 'pip'
        self.absent = []           # packages the target interpreter cannot import
        self._build()
        self.after(80, self._drain)
        self.after(120, self._check_packages)

    # ---- layout -------------------------------------------------------------
    def _build(self):
        pad = dict(padx=18)
        tk.Label(self, text="2nd Super Robot Taisen OG — English Patch",
                 bg=BG, fg=FG, font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(16, 2), **pad)
        tk.Label(self, text="Point this at a play-copy of your own legally-dumped game. It rebuilds the\n"
                            "translation from source and writes it back in place. Nothing is downloaded.",
                 bg=BG, fg=SUB, justify="left", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 12), **pad)

        self._picker("Game USRDIR  (contains PSARC\\ and EBOOT.BIN)  — required",
                     "usrdir", directory=True, clearable=False)
        self._picker("RPCS3 game-data install  (dev_hdd0\\game\\BLJS10133)  — wiped so the patch reinstalls  · recommended",
                     "gd", directory=True, clearable=True)
        self._picker("Decrypted EBOOT.elf  — optional, enables proper letter spacing",
                     "eboot", directory=False, clearable=True)

        self.go = tk.Button(self, text="Patch", command=self._start, state="disabled",
                            bg=ACCENT, fg="#08131f", relief="flat", font=("Segoe UI", 11, "bold"),
                            activebackground="#38dcf0", cursor="hand2")
        self.go.pack(fill="x", pady=(10, 10), **pad)

        self.fix = tk.Button(self, text="", command=self._install_packages,
                             bg="#f59e0b", fg="#08131f", relief="flat",
                             font=("Segoe UI", 10, "bold"),
                             activebackground="#fbbf24", cursor="hand2")
        # packed only when a package is missing; see _check_packages

        self.log = tk.Text(self, height=14, bg=PANEL, fg="#cbd5e1", relief="flat",
                           insertbackground=FG, font=("Cascadia Code", 9), wrap="word",
                           highlightthickness=1, highlightbackground=BORDER)
        self.log.pack(fill="both", expand=True, **pad)
        self.log.configure(state="disabled")

        self.status = tk.Label(self, text="", bg=BG, fg=SUB, anchor="w", font=("Segoe UI", 10, "bold"))
        self.status.pack(fill="x", pady=(8, 14), **pad)

        for v in self.val.values():
            v.trace_add("write", lambda *_: self._refresh())

    def _picker(self, label, key, directory, clearable):
        tk.Label(self, text=label, bg=BG, fg="#cbd5e1", anchor="w",
                 font=("Segoe UI", 9)).pack(fill="x", padx=18, pady=(6, 2))
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=18)
        ent = tk.Entry(row, textvariable=self.val[key], bg="#1e293b", fg=FG, relief="flat",
                       insertbackground=FG, font=("Segoe UI", 9))
        ent.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        tk.Button(row, text="Browse…", command=lambda: self._pick(key, directory),
                  bg=BORDER, fg=FG, relief="flat", cursor="hand2").pack(side="left")
        if clearable:
            tk.Button(row, text="✕", command=lambda: self.val[key].set(""),
                      bg=BORDER, fg=FG, relief="flat", cursor="hand2", width=2).pack(side="left", padx=(6, 0))

    # ---- packages -----------------------------------------------------------
    def _check_packages(self):
        """Which required packages the interpreter that will run apply.py cannot import.

        Asking THIS process is not good enough: python_exe() may be a different
        interpreter, and "installed, but into the wrong python" is the most common way
        this goes wrong."""
        absent = []
        for mod in ("cryptography", "capstone"):
            try:
                r = subprocess.run([python_exe(), "-c", "import " + mod],
                                   capture_output=True,
                                   creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
                if r.returncode != 0:
                    absent.append(mod)
            except Exception:                      # no usable interpreter; let Patch report it
                return []
        self.absent = absent
        if absent:
            self.fix.configure(text="Install missing package%s: %s"
                                    % ("" if len(absent) == 1 else "s", ", ".join(absent)))
            self.fix.pack(fill="x", pady=(0, 10), padx=18, before=self.log)
        else:
            self.fix.pack_forget()
        self._refresh()
        return absent

    def _blocking(self):
        """The absent packages that this run actually needs. capstone is only used for the
        EBOOT spacing patch, so it must not block a run that does not ask for one - which
        is the same rule apply.py's preflight applies."""
        need = ["cryptography"] + (["capstone"] if self.val["eboot"].get().strip() else [])
        return [m for m in self.absent if m in need]

    def _install_packages(self):
        if not self.absent:
            return
        self._reason = None
        self._task = "pip"
        self.go.configure(state="disabled")
        self.fix.configure(state="disabled")
        self._set_status("Installing " + ", ".join(self.absent) + "…", SUB)
        # --user keeps this out of a system directory that would need admin, but pip
        # REFUSES it inside a virtualenv, where the env itself is already writable.
        venv = False
        try:
            r = subprocess.run([python_exe(), "-c",
                                "import sys;print(int(sys.prefix!=sys.base_prefix))"],
                               capture_output=True, text=True,
                               creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            venv = r.stdout.strip() == "1"
        except Exception:
            pass
        cmd = [python_exe(), "-m", "pip", "install"] + ([] if venv else ["--user"]) + list(self.absent)
        self._append("$ " + " ".join(cmd[1:]))
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    # ---- actions ------------------------------------------------------------
    def _pick(self, key, directory):
        if directory:
            sel = filedialog.askdirectory(title="Select folder")
        else:
            sel = filedialog.askopenfilename(title="Select EBOOT.elf",
                                             filetypes=[("Decrypted EBOOT", "*.elf"), ("All files", "*.*")])
        if sel:
            self.val[key].set(os.path.normpath(sel))

    def _refresh(self):
        running = self.proc is not None and self.proc.poll() is None
        ok = bool(self.val["usrdir"].get().strip()) and not running and not self._blocking()
        self.go.configure(state="normal" if ok else "disabled")

    def _append(self, line, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_status(self, text, color):
        self.status.configure(text=text, fg=color)

    def _start(self):
        if not os.path.isfile(APPLY):
            self._set_status("✕ Can't find apply.py — run this from inside the patch folder.", "#f87171")
            return
        self.go.configure(state="disabled")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._reason = None
        self._task = "patch"
        self._set_status("Working…", SUB)

        cmd = [python_exe(), "apply.py", self.val["usrdir"].get().strip()]
        gd = self.val["gd"].get().strip()
        eb = self.val["eboot"].get().strip()
        if gd:
            cmd += ["--gd", gd]
        if eb:
            cmd += ["--eboot-elf", eb]
        self._append("$ python " + " ".join(cmd[1:]))
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _run(self, cmd):
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1,
                                         encoding="utf-8", errors="replace", creationflags=flags)
        except Exception as e:  # noqa: BLE001 - surface any launch failure to the UI
            self.q.put(("log", f"ERROR: could not launch Python: {e}"))
            self.q.put(("done", False))
            return
        for line in self.proc.stdout:
            self.q.put(("log", line.rstrip("\n")))
        rc = self.proc.wait()
        self.q.put(("done", rc == 0))

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._append(payload)
                    # remember the first real complaint so the status line can name it
                    if self._reason is None and (payload.startswith("!!")
                                                 or payload.startswith("ERROR")):
                        self._reason = payload.lstrip("! ").strip()
                elif kind == "done":
                    if self._task == "pip":
                        self.fix.configure(state="normal")
                        still = self._check_packages()
                        if not still:
                            self._set_status("✓ Packages installed — you can Patch now.", "#4ade80")
                        elif not self._blocking():
                            self._set_status("✓ Installed — %s still missing, only needed for the "
                                             "EBOOT patch." % ", ".join(still), "#4ade80")
                        else:
                            # --user can still fail on a managed or read-only install
                            self._set_status("✕ Could not install: " + ", ".join(self._blocking())
                                             + " — see the log.", "#f87171")
                    elif payload:
                        self._set_status("✓ Done — delete the game-data install if you skipped it, then boot in RPCS3.", "#4ade80")
                    else:
                        msg = self._reason or "see the log above"
                        if len(msg) > 96:
                            msg = msg[:93] + "..."
                        self._set_status("✕ Failed — " + msg, "#f87171")
                    self._task = None
                    self._refresh()
        except queue.Empty:
            pass
        try:
            self.after(80, self._drain)
        except tk.TclError:            # window closed with this poll still pending
            pass


if __name__ == "__main__":
    Installer().mainloop()
