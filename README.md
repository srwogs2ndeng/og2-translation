# 2nd Super Robot Taisen OG — English translation

A work-in-progress English translation of **Dai-2-Ji Super Robot Taisen OG**
(PS3, BLJS10133) for RPCS3. The game's own Japanese was translated directly; no
third-party fan translation was used.

> Contains **no game files** — only tools, translated text, and docs. You supply
> your own legally dumped copy. Work in progress; not yet human-translator-reviewed.

## Install

There is **no pre-patched game download** — that would redistribute Bamco's data,
and the game re-encrypts every file on repack so small binary patches aren't
possible anyway. Instead you rebuild the patch from **your own dump**.

**You need:** RPCS3 + PS3 firmware · your **BLJS10133** dump · Python 3.10+
(`pip install cryptography capstone`).

```sh
git clone https://github.com/srwogs2ndeng/og2-translation
cd og2-translation
```

### Option A — click the GUI (easiest)

Double-click **`Install (GUI).bat`**. A small window opens: pick your game's
**USRDIR** (the folder holding `PSARC\` and `EBOOT.BIN`), optionally your RPCS3
game-data folder and a decrypted `EBOOT.elf`, then click **Patch** and watch it
build. It's a thin front-end over `apply.py` — same result, no command line.
(Details: [installer/README.md](installer/README.md).)

### Option B — one command

```sh
# point it at a play-copy of your game (the USRDIR that holds PSARC/ and EBOOT.BIN):
python apply.py "/path/to/BLJS10133/PS3_GAME/USRDIR" --gd "/path/to/dev_hdd0/game/BLJS10133"
```

Either way, it extracts your own files, rebuilds them with the English text, and
writes the patched containers back into that USRDIR. Then boot it in RPCS3.

**Optional — proper letter spacing (recommended).** RPCS3 → *Utilities → Decrypt
PS3 Binaries* on your `EBOOT.BIN`, then add `--eboot-elf "/path/to/EBOOT.elf"` (or
pick it in the GUI). Without it the game still plays; Latin text is just wider.

Full manual steps and rollback are in **[docs/INSTALL.md](docs/INSTALL.md)**.

## What's translated

Main-story dialogue, battle quotes, all menus / library / Q&A / help, the unit +
pilot + keyword dictionaries, scenario interludes, and the EBOOT system strings —
plus an EBOOT patch so half-width Latin text renders with proper spacing, and a
wiki-validated name canon enforced across the whole script.

**Known rough edges** (see `docs/HANDOFF.md`): a few things the game's
monospace-Japanese engine resists — inline keyword-link underlines run wide, some
fixed-width name plates compress, one stat-screen column is tight, and on the
animated stage-title cut-in the `第N話` ("Chapter N") marker is still Japanese
(the engine draws those glyphs itself; the stage subtitle below it is translated).
None block play.

## Notes

- `tools/decrypt_sdat.py` derives from make_npdata (Hykem, GPLv3).
- Don't commit game-derived files; the `.gitignore` enforces this.
