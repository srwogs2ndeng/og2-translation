# GUI installer

A small Tkinter front-end over [`apply.py`](../apply.py). It gives friends a
window with three folder-pickers and a **Patch** button instead of a command
line — but it runs the exact same from-source build.

## For your friends (no build needed)

They already need Python for `apply.py`, and Tkinter ships with it, so there is
nothing extra to install for the GUI itself:

1. Install **Python 3.10+** (tick *Add Python to PATH*).
2. `pip install cryptography capstone`
3. Double-click **`Install (GUI).bat`** in the repo root.
4. Pick the game **USRDIR** (required), optionally the RPCS3 game-data folder
   and a decrypted `EBOOT.elf`, then click **Patch**.

That's the whole thing — no compiler, no MSI, no admin rights.

## Why not Tauri / a real MSI?

`apply.py` rebuilds the patch against each person's *own* game dump every time,
so there is nothing to "install" to Program Files — it's a run-once build tool,
and it already depends on Python. A Tkinter GUI adds **zero** new dependencies
and no toolchain. A WebView/Tauri app or a WiX MSI would drag in a Rust/Node or
installer toolchain to accomplish the same `subprocess` call.

## Optional: freeze it into a single `.exe`

If you'd rather hand friends one clickable `installer.exe` (they still need
Python on their machine, because `apply.py` and its `cryptography`/`capstone`
deps run under it):

```
pip install pyinstaller
cd installer
pyinstaller --onefile --noconsole --name "OG2-Installer" install_gui.pyw
```

The exe lands in `installer/dist/OG2-Installer.exe`. Keep it next to the repo
(it looks for `apply.py` one folder up, then in its own folder). `app-icon.png`
here is the source icon — pass `--icon app-icon.ico` if you convert it first.
