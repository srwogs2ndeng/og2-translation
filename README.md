# 2nd Super Robot Taisen OG - English translation

An English translation of **Dai-2-Ji Super Robot Taisen OG** (PS3, BLJS10133) for RPCS3.
About 87,000 strings: the full main story script, battle quotes, menus, the unit and
pilot library, help text, skills, parts and map names. The game's own Japanese was
translated directly; no third-party fan translation was used.

> Contains **no game files**. Only tools, translated text and docs. You supply your own
> legally dumped copy.

## The translation is machine generated. Read this first.

The English was produced by a large language model, not by a human translator. If that is
a dealbreaker, stop here, and that is a reasonable position.

What it actually is, stated plainly:

- The script was translated **from the game's own Japanese**, in chunks of roughly 180
  lines in story order, so the model had scene context. It is not a line-by-line pass
  through a conventional MTL engine, and it is not a human translation either.
- Character, unit and weapon names come from the game's own data and from official
  English materials where they exist, then are applied consistently by script rather than
  left to the model.
- Punctuation, name consistency and line fitting are handled by deterministic passes.
- **No human proofread the dialogue line by line.** Menus, the library and UI text were
  checked on screen and corrected. The 41,473 dialogue lines were spot-checked, not
  reviewed in full.

Expect the consequences. Dialogue is often stiff. Japanese omits subjects and pronouns,
so expect a wrong "he" or "she" sometimes, and expect jokes and wordplay to land flat.
Terminology is consistent; tone and characterisation are weaker than a human translation.

This exists so the game can be played in English now. It is not a replacement for a human
translation, and if one appears, use that instead.

## Install

There is **no pre-patched game download**. That would redistribute Bandai Namco's data,
and the game re-encrypts every file on repack, so small binary patches are not possible
anyway. You rebuild the patch from **your own dump**.

**You need:** RPCS3 and PS3 firmware, your **BLJS10133** dump, and Python 3.10+
(`pip install cryptography capstone`).

Unzip anywhere, then:

### Option A: the GUI

Double-click **`Install (GUI).bat`**. Pick your game's **USRDIR** (the folder holding
`PSARC\` and `EBOOT.BIN`), optionally your RPCS3 game-data folder and a decrypted
`EBOOT.elf`, then click **Patch**. It is a front-end over `apply.py`.
(Details: [installer/README.md](installer/README.md).)

### Option B: one command

```sh
python apply.py "/path/to/BLJS10133/PS3_GAME/USRDIR" --gd "/path/to/dev_hdd0/game/BLJS10133"
```

Either way it extracts your own files, rebuilds them with the English text, and writes
the patched containers back. Then boot it in RPCS3.

**Optional but recommended: proper letter spacing.** RPCS3 → *Utilities → Decrypt PS3
Binaries* on your `EBOOT.BIN`, then add `--eboot-elf "/path/to/EBOOT.elf"` (or pick it in
the GUI). Without it the game still plays, but Latin text is spaced on Japanese metrics
and looks wide.

Manual steps and rollback: **[docs/INSTALL.md](docs/INSTALL.md)**.

## Known limitations

- Tested on RPCS3 only. Not tried on hardware.
- Some long names and descriptions are shortened to fit fixed-width fields.
- About 10,300 bracketed strings in the script files are left in Japanese **on purpose**.
  They are keys the engine compares byte for byte, not displayed text. Translating them
  skips every interlude and silences stage music. No spoken line is left untranslated.

## How it was built

**[docs/HACKING.md](docs/HACKING.md)** covers the container and text formats, the
executable patches that make English render correctly, and how the renderer was found
using an RPCS3 build with its memory breakpoints enabled. **[docs/RELEASE.md](docs/RELEASE.md)**
is the short description.

## Notes

- `tools/decrypt_sdat.py` derives from make_npdata (Hykem, GPLv3).
- No game-derived files are committed; `.gitignore` enforces it.
