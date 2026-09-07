# Installation guide — from a fresh clone to a playable English build

Everything is pure Python; no compiler needed. Steps 1–4 are one-time setup;
step 5 is the actual build+deploy (also what you re-run after any text change).

> **Most people do not need this page.** `python3 apply.py "<USRDIR>" --gd "<game-data
> folder>"` does all of it, and the GUI wraps that. This is the manual route, for working
> on the patch rather than installing it.

> **Platform:** developed and tested on **Windows**. Linux and the Steam Deck are
> confirmed working by users, and the build is verified here to produce byte-identical
> archives; the GUI and the EBOOT step are still Windows-only tested. macOS is untested.
> Use `python3` throughout on Linux and macOS.

## 0. Prerequisites

- **RPCS3** (the project was built against 0.0.36) with the PS3 firmware installed.
- **Your own dump** of `Dai-2-Ji Super Robot Taisen OG (Japan)` (BLJS10133) as an ISO
  or extracted `PS3_GAME` folder. Nothing game-derived ships in this repo.
- **Python 3.10+** with `pip install cryptography`. Add `capstone` **only** for the
  optional EBOOT step (3 and the end of 5) — nothing else imports it.
  On Debian/Ubuntu also `sudo apt install python3-venv` for a venv, and `python3-tk`
  for the GUI; on Arch/SteamOS `pacman -S tk`.
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
# repeat for Common, Battle, General2d (menu text, 638 MB) and General3d (map
# terrain names, 1 GB). All five carry text; General3d is easy to forget.
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

# menu chrome and map terrain names - single-file override repacks, not full rebuilds:
python tools/build_general2d.py --deploy    # windowdataMain.wtd: text AND font sizes
python tools/build_general3d.py --deploy    # landinfo.mti: 300 terrain names

# the executable (letter-spacing patches + system strings, byte-exact):
python tools/build_eboot.py
# copy build/EBOOT.patched.BIN over <game>/PS3_GAME/USRDIR/EBOOT.BIN
```

**Use the builders; do not inline what they do.** This page used to spell out the
General2d repack as a snippet, and the copy in `apply.py` drifted from the real builder:
it dropped the `wtd_sizes` step, so for eleven releases no font-size fix reached anybody,
and General3d had no step at all, so 300 translated terrain names never shipped
(fixed in v1.0.10). `build_general2d.py` also verifies the SDAT's per-block HMACs, which
a hand-rolled snippet does not.

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

  Each deploy copies the whole live archive into `build/rollbacks/<Archive>/` first, and
  **the newest 3 per container are kept**; older ones are pruned automatically. They are
  full copies — Battle is 1.6 GB apiece — so unbounded they add up fast. Nothing is lost
  by pruning: `work/*.psarc.sdat` holds the pristine Japanese, and any English build is
  reproducible from the worksheets.
- EBOOT: copy the timestamped backup from `build/rollbacks/EBOOT/` back over
  `EBOOT.BIN`.

### Savestates

RPCS3 savestates need `Save Disc Game Data: true` (Config → Advanced →
Savestates). Savestates snapshot loaded game files — a state made before a
re-deploy may not load after it; prefer in-game saves around deploys.
