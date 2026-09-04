#!/bin/sh
# One-command EBOOT rollback to the last known-good build (dialogue reflow + K=0.6, no risky patches)
cp "build/EBOOT.GOOD.BIN" "../games/BLJS10133_EN/PS3_GAME/USRDIR/EBOOT.BIN" && echo "ROLLED BACK to EBOOT.GOOD.BIN"
