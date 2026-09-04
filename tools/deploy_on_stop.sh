#!/bin/bash
# deploy_on_stop.sh - wait until the game is STOPPED (or RPCS3 exits), then deploy the three
# freshly built archives. A "Stopping emulator..." that is immediately followed by
# "Emulator::BootGame" is a context-menu REBOOT, not a stop -> keep waiting.
# paths are derived from this script's own location (repo/tools/), never hardcoded
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${OG2_RPCS3_LOG:-$REPO/../log/RPCS3.log}"

running() { tasklist //FI "IMAGENAME eq rpcs3.exe" 2>/dev/null | grep -q -i "rpcs3.exe"; }
stops()   { grep -a -c "Stopping emulator" "$LOG" 2>/dev/null || echo 0; }

base=$(stops)
echo "armed: stop-count=$base, rpcs3 running=$(running && echo yes || echo no)"
while true; do
  if ! running; then echo "RPCS3 process exited -> deploying"; break; fi
  n=$(stops)
  if [ "$n" -gt "$base" ]; then
    sleep 6
    last=$(grep -a -n "Stopping emulator" "$LOG" | tail -n 1 | cut -d: -f1)
    if tail -n +"$last" "$LOG" | grep -a -q "Emulator::BootGame"; then
      base=$(stops); echo "stop was a reboot -> still waiting"; continue
    fi
    echo "game stopped -> deploying (do NOT relaunch until DEPLOY DONE)"; break
  fi
  sleep 5
done

cd "$REPO" || { echo "DEPLOY FAILED: cd"; exit 1; }
ok=1
for a in ${ARCHIVES:-Logic Battle}; do
  out=$(python tools/deploy.py deploy "$a" 2>&1)
  if [ $? -ne 0 ]; then ok=0; echo "DEPLOY FAILED: $a"; echo "$out" | tail -n 5; fi
  echo "$out" | grep -E "deployed ->|GD mirrored|GD in sync" | sed "s/^/  [$a] /" | cut -c1-120
done
if [ "${WITH_GENERAL2D:-1}" = "1" ]; then
  out=$(python tools/build_general2d.py --deploy-only 2>&1)
  if [ $? -ne 0 ]; then ok=0; echo "DEPLOY FAILED: General2d"; echo "$out" | tail -n 5; fi
  echo "$out" | grep -E "deployed ->|GD mirrored|GD in sync" | sed "s/^/  [General2d] /" | cut -c1-120
fi
[ $ok -eq 1 ] && echo "DEPLOY DONE - safe to launch the game" || echo "DEPLOY FINISHED WITH ERRORS"
