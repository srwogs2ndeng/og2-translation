@echo off
REM One-click launcher for the OG2 English Patch GUI installer.
REM Double-click this file. It just opens installer\install_gui.pyw with your
REM installed Python (the GUI then does the work). Requires Python 3.10+.
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (
  start "" py -3 "installer\install_gui.pyw"
  goto :eof
)
where python >nul 2>nul && (
  start "" python "installer\install_gui.pyw"
  goto :eof
)

echo Python 3 was not found.
echo Install Python 3.10+ from https://www.python.org/downloads/ (tick "Add
echo Python to PATH" during setup), then run:  pip install cryptography capstone
echo and double-click this file again.
pause
