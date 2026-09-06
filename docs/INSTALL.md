# Installation guide — from a fresh clone to a playable English build

Everything is pure Python; no compiler needed. Steps 1–4 are one-time setup;
step 5 is the actual build+deploy (also what you re-run after any text change).

## 0. Prerequisites

- **RPCS3** (the project was built against 0.0.36) with the PS3 firmware installed.
- **Your own dump** of `Dai-2-Ji Super Robot Taisen OG (Japan)` (BLJS10133) as an ISO
  or extracted `PS3_GAME` folder. Nothing game-derived ships in this repo.
- **Python 3.10+** with: `pip install cryptography capstone`
- 7-Zip (only for reading the ISO's UDF directly, if starting from an ISO).

## 1. Lay out the game folder

Create the play-copy the emulator boots (a *folder* install, not the ISO):

```
<rpcs3>/games/BLJS10133_EN/PS3_GAME/...   (copy of the game's PS3_GAME tree)
```

RPCS3 boots this via *Add Games*. The deploy scripts overwrite the `.psarc.sdat`
containers and `EBOOT.BIN` inside it.

## 2. Extract the pristine sources into `work/`

From the repo root (paths in `build/config.json` — adjust if your layout differs):

```sh
python tools/decrypt_sdat.py <game>/PS3_GAME/USRDIR/PSARC/Logic.psarc.sdat  work/Logic.psarc
python tools/extract_psarc.py work/Logic.psarc  work/Logic
# repeat for Common, Battle, General2d (General2d is 638 MB - needed for menu text)
```

Keep the decrypted `.psarc` files AND the original `.psarc.sdat` files in `work/` —
the build re-encrypts using the originals as templates (`encrypt_sdat.wrap`).

## 3. Decrypt the EBOOT (one-time, needs RPCS3 GUI)

RPCS3 → **Utilities → Decrypt PS3 Binaries** → select the game's original
`EBOOT.BIN` → save the decrypted ELF as:

```
_rollback/EBOOT.elf.orig
```

Also keep a copy of the original `EBOOT.BIN` as `_rollback/EBOOT.BIN.orig` (rollback).

## 4. Sanity check

```sh
python tools/deploy.py status Logic
```

should list ~231 worksheets and a valid JP extract.

## 5. Build + deploy everything

```sh
# the three worksheet-driven containers (each: reset-from-JP -> apply -> pack -> deploy)
python tools/deploy.py build Logic      # story, dictionaries, objectives, help
python tools/deploy.py build Battle     # battle quotes (1.6 GB, takes a few minutes)
python tools/deploy.py build Common     # Q&A, archive/library text

# menu chrome (General2d) - fast override repack:
python - <<'PY'
import sys, json, shutil, os, datetime; sys.path.insert(0, "tools")
import wtd_tool, repack_override, encrypt_sdat
src = open("work/General2d/Dat/Window/WindowToolData/windowdataMain.wtd", "rb").read()
ws = json.load(open("build/worksheets/General2d/Dat/Window/WindowToolData/windowdataMain.wtd.json", encoding="utf-8"))
new, refused, applied = wtd_tool.apply(src, ws)
p = repack_override.repack_override("work/General2d.psarc", {"/Dat/Window/WindowToolData/windowdataMain.wtd": bytes(new)})
shutil.copy2(p, "build/out/General2d.psarc")
encrypt_sdat.wrap("work/General2d.psarc.sdat", "build/out/General2d.psarc", "build/out/General2d.psarc.sdat")
# then copy build/out/General2d.psarc.sdat over the game folder's copy
PY

# the executable (letter-spacing patches + system strings, byte-exact):
python tools/build_eboot.py
# copy build/EBOOT.patched.BIN over <game>/PS3_GAME/USRDIR/EBOOT.BIN
```

`deploy.py` automatically backs up the live file to `build/rollbacks/<Archive>/`
and **wipes the game-data install** (`dev_hdd0/game/BLJS10133`) so the next boot
reinstalls cleanly.

## 6. Boot

Launch `games/BLJS10133_EN` in RPCS3. First boot reinstalls game data (GD).

### The corruption-guard gotcha

The game runs `cellGameDataCheck`: if the game folder and the installed GD
disagree, you get 「ゲームデータが壊れています」. **Always deploy to the folder AND
wipe the GD** (deploy.py does both). Never hand-edit one without the other.

### Rollbacks

- containers: `python tools/deploy.py rollback <Archive>` (restores latest backup)
- EBOOT: copy the timestamped backup from `build/rollbacks/EBOOT/` back over
  `EBOOT.BIN`.

### Savestates

RPCS3 savestates need `Save Disc Game Data: true` (Config → Advanced →
Savestates). Savestates snapshot loaded game files — a state made before a
re-deploy may not load after it; prefer in-game saves around deploys.
