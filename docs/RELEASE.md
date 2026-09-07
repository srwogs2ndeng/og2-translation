# Dai-2-Ji Super Robot Taisen OG - English patch

An English translation patch for *Dai-2-Ji Super Robot Taisen OG* (PS3, BLJS10133),
built for RPCS3. About 87,000 strings are translated: the full main story script, battle
quotes, menus, the unit and pilot library, help text, skills, parts, and map names.

| Part | Strings |
|---|---|
| Story dialogue (102 script files) | 41,473 |
| Battle quotes | 34,604 |
| Menus and UI | 3,248 |
| Executable strings | 1,697 |
| Options and Q&A | 509 |
| Map terrain names | 300 |

The patch also changes the game's executable so English renders correctly: Latin glyph
spacing, a floor on the automatic font shrinking, and a fix for an auto-fit bug that made
some lines letter-spread while others stayed compact.

## Read this before downloading: the translation is machine generated

The English was produced by a large language model, not by a human translator. That is
the single most important thing to know about this patch, and no amount of tooling around
it changes that.

What that means in practice, stated plainly:

- The script was translated **from the game's own Japanese**, in chunks of roughly 180
  lines in story order, so the model had scene context rather than working line by line.
  It is not a line-by-line pass through a conventional MTL engine, and it is not a
  human translation either.
- Character, unit and weapon names come from the game's own data and from official
  English materials where they exist, then are applied consistently by script rather than
  left to the model.
- Punctuation, name consistency and line fitting are handled by deterministic passes, not
  by the model.
- **No human proofread the dialogue line by line.** Menus, the library and UI text were
  checked on screen and corrected; the roughly 41,500 dialogue lines were spot-checked,
  not reviewed in full.

Expect the consequences of that. Dialogue is often stiff. Japanese omits subjects and
pronouns, so expect a wrong "he" or "she" sometimes, and expect jokes and wordplay to
land flat or disappear. Terminology is consistent, but tone and characterisation are
weaker than a human translation would give you.

If you would rather wait for a human translation, wait. This is offered as a way to play
the game now, not as a replacement for one.

## Requirements

- RPCS3 and your own dump of the game. **No game data is distributed here.** The
  installer rebuilds the archives from the files you already own.
- Python 3.10+ with `cryptography`. `capstone` as well, but **only** if you want the
  optional letter-spacing patch — nothing else uses it.
- On Linux, some distributions split parts of Python into separate packages: Debian and
  Ubuntu need `python3-tk` for the GUI and `python3-venv` for a virtualenv
  (`pacman -S tk` on Arch and SteamOS). The command-line installer needs neither.

## Installing

Unpack, then point the installer at your game directory and its game-data directory. The
readme in the archive has the exact command. It rebuilds every container and the
executable in place, and keeps a rollback copy of everything it replaces.

There is a GUI if you want one — `Install (GUI).bat` on Windows, `./install-gui.sh` on
Linux and macOS — but it is only a front end over the same command.

## Platform support

**Windows** is where the patch is developed: built, deployed and played, end to end.

**Linux and the Steam Deck work.** The build is verified — run against a pristine dump on
a case-sensitive filesystem, all five patched archives come out with the same sha256 as
the Windows build, so the data is identical either way — and several people have reported
the result booting on a Steam Deck with the English rendering correctly. Those boots are
user reports, not something reproduced here. Two pieces have still not been exercised
outside Windows: the GUI window, and the optional letter-spacing step.

**macOS is untested.** It is all pure Python and there is no reason to expect trouble, but
"no reason to expect trouble" is not the same as tested.

## Known limitations

- Developed and tested on Windows; Linux and the Steam Deck are confirmed working by
  users. macOS is untested. See *Platform support* above.
- Tested on RPCS3 only. It has not been tried on hardware.
- A handful of long names and descriptions are shortened to fit fixed-width fields.
- About 10,300 bracketed strings in the script files are left in Japanese **on purpose**.
  They are keys the engine compares byte for byte, not displayed text. Translating them
  skips every interlude and silences stage music. No spoken line is left untranslated.

## Source

Full source, tooling and technical notes are included. The patch is reproducible from
source against your own dump.
