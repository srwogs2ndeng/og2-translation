# GUI installer

A small Tkinter front-end over [`apply.py`](../apply.py). It gives friends a
window with three folder-pickers and a **Patch** button instead of a command
line — but it runs the exact same from-source build.

## For your friends (no build needed)

1. Install **Python 3.10+** (on Windows, tick *Add Python to PATH*).
2. `pip install cryptography` — and `capstone` **only** if you will use `--eboot-elf`.
3. Launch it: Windows, double-click **`Install (GUI).bat`**; Linux/macOS, run
   **`./install-gui.sh`**. Both live in the repo root.
4. Pick the game **USRDIR** (required), optionally the RPCS3 game-data folder
   and a decrypted `EBOOT.elf`, then click **Patch**.

If a required package is missing the window says so and offers to install it,
checking the interpreter that will actually run `apply.py` rather than its own.

No compiler, no MSI, no admin rights.

### Tkinter is not always present

On Windows and macOS the python.org installers bundle Tkinter, so there is nothing
extra to do. **Several Linux distributions ship it separately** — a stock Ubuntu
`python3` has no `tkinter` at all, and the GUI then dies with a bare
`ModuleNotFoundError` before it can display anything, including an explanation:

```sh
sudo apt install python3-tk        # Debian/Ubuntu   (also python3-venv for venvs)
sudo pacman -S tk                  # Arch/SteamOS
sudo dnf install python3-tkinter   # Fedora
```

`install-gui.sh` checks for it first and prints the right line for your distro. The GUI
is only a front end, so `apply.py` on the command line remains a complete alternative.

**Tested on Windows.** On Linux only the launcher's dependency check has been exercised
here; the window itself has not been opened on that side. The patch it drives is
confirmed working on Linux and the Steam Deck — if the GUI gives you trouble there,
`apply.py` does the same job and is the better thing to fall back to.

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
