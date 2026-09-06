#!/bin/bash
# One-click launcher for the OG2 English Patch GUI installer, on Linux and macOS.
# The Windows counterpart is "Install (GUI).bat". Run:  ./install-gui.sh
#
# It only opens installer/install_gui.pyw with your Python; the GUI does the work.
# Its one real job beyond that is to check tkinter FIRST, because a Python without it
# fails with a bare ModuleNotFoundError that does not tell you which package to install.
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        PY=$c; break
    fi
done
if [ -z "$PY" ]; then
    echo "Python 3.10+ was not found."
    echo "  Debian/Ubuntu : sudo apt install python3 python3-tk python3-venv"
    echo "  Arch/SteamOS  : sudo pacman -S python tk       (SteamOS: needs a disabled readonly fs)"
    echo "  Fedora        : sudo dnf install python3 python3-tkinter"
    exit 1
fi

if ! "$PY" -c 'import tkinter' 2>/dev/null; then
    echo "$PY has no tkinter, so the GUI cannot open. Install it:"
    echo "  Debian/Ubuntu : sudo apt install python3-tk"
    echo "  Arch/SteamOS  : sudo pacman -S tk"
    echo "  Fedora        : sudo dnf install python3-tkinter"
    echo
    echo "Or skip the GUI entirely - it is only a front end over apply.py:"
    echo "  $PY apply.py \"/path/to/PS3_GAME/USRDIR\" --gd \"/path/to/dev_hdd0/game/BLJS10133\""
    exit 1
fi

exec "$PY" installer/install_gui.pyw "$@"
