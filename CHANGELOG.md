# Changelog

Versions follow the public releases at
https://github.com/srwogs2ndeng/og2-translation/releases . Each release ships
`og2-english-patch.zip`, which contains the patch, the tooling and the RPCS3 settings
for this title, but no game data.

## v1.0.9 - 2026-09-05

Installer only. Nothing changes in game, so there is no need to re-patch if you are
already on v1.0.8.

### Added
- **The GUI installs the missing Python packages itself.** If `cryptography` (or, when you
  supply an `EBOOT.elf`, `capstone`) cannot be imported, an orange button appears offering
  to install it, and Patch stays disabled until it is there. It installs with `--user`,
  except inside a virtualenv, where pip refuses that flag.

### Fixed
- **A missing package failed the run several minutes in, having already decrypted
  archives, with a message that scrolled past.** `apply.py` now checks the packages before
  it touches anything, and prints the full path of the interpreter that needs them - the
  usual cause is not "not installed" but "installed into a different Python", which the
  old message could not distinguish.
- The GUI checks packages against the interpreter that will actually run the patch, not
  its own, for the same reason.
- **The GUI said only "Failed - see the log above".** It now names the first complaint in
  the status line, so the reason is visible without reading the log.
- `apply.py` line-buffers its output, which was interleaving wrongly with stderr when the
  GUI piped it.
- Closing the window while a run was polling raised a Tcl error on teardown.

## v1.0.8 - 2026-09-05

### Fixed
- **The squad-select headers ran into the counter beside them.** 部隊選択 is eight cells,
  a six-character budget, and "Select Squad" is twelve. All 16 headers in that family are
  now "Squad", and the verbose bracketed categories are shortened with them: "Ally
  Forces" to "Allies", "Enemy List" to "Enemy", "Neutral Forces" to "Neutral", "3rd/4th
  Army List" to "3rd/4th Army". Every one now fits.

## v1.0.7 - 2026-09-05

### Fixed
- **Support Atk and Counter had no description at all.** v1.0.0 converted those two from
  plain strings into the two-line record format as a test, to find out whether the game
  recognises a record purely by its leading NUL byte. It does not: a record where the
  original was a plain string renders nothing. Both are back to single strings, shortened
  to the one-line budget. The six descriptions that are genuinely records in the Japanese
  are unaffected and keep their two lines.

## v1.0.6 - 2026-09-05

### Changed
- **The Four Gods are now romanized consistently: Seiryu, Byakko, Suzaku, Genbu.** Every
  one of them had been rendered two or more ways, 青龍 alone appearing as Seiryu, Azure
  Dragon, Seiryuu and Blue Dragon, and the library disagreed with the script. Romanized
  matches the mecha built from the same kanji (RyuOhKi, KoOhKi, JakuBuOh). 44 lines across
  the story script, battle quotes, stage titles, weapon names and the unit library.
  Weapon names change with it: "Azure Dragon Scale" is now "Seiryu Scale", and so on.

## v1.0.5 - 2026-09-05

### Fixed
- **Kanan was mis-gendered.** She tells the Steel Dragons outright that she is a woman
  (ls064: "For the record, I'm no man"), and the scene turns on their having assumed
  otherwise. Sean's later line called her "he". The Japanese has no pronoun there at all,
  so it was invented. Fixed, and every other reference checked.
- **A line named the wrong character entirely.** ls054 rendered 夏喃 as "Ranshao", who is
  someone else; our own canon_names maps it to Kanan. The same line also inverted who was
  looking at whom: Kanan takes an interest in the Seiryu girl, who is the person being
  spoken to.
- Kanan's reveal line said "sort by common gender"; 俗人 is specifically *mortals*, the
  contrast being that she is an immortal, so it now reads "sort me by mortal sexes".

## v1.0.4 - 2026-09-04

### Fixed
- **"Game data is corrupted" after every deploy.** The 2026-09-01 change had it backwards:
  it concluded the retail RPCS3 could not fresh-install and switched deploy from wiping
  the game-data install to mirroring new archives into it. Retail installs fine when the
  directory is genuinely absent, and mirroring is itself the fault - the game validates
  the install it made, so overwriting those archives underneath it makes the next boot
  report corruption. Deploy wipes again; `--mirror` is opt-in and documented as the cause.
- **The "Stats" label overran its cell on the pilot screen.** Its cell holds 能力, two
  fullwidth characters, which is a 3.2-character budget against a 5-character word. Only
  one of the eleven copies had ever been resized, and not enough. Nine are now condensed;
  two sit in a different record layout and are deliberately left alone.
- `wtd_sizes` refused any record whose marker bytes differed from the common layout, which
  is why five of those Stats labels silently stayed full size. It can now identify a
  record by its length byte instead, which does not assume a layout.

## v1.0.3 - 2026-09-04

### Added
- `docs/TRANSLATION-STYLE.md`: the rules the English follows (accuracy, idioms, names
  from the game data and akurasu, natural phrasing) and how a translation pass is
  actually run, including why the script is translated in ~180-line scene chunks rather
  than line by line.

## v1.0.2 - 2026-09-04

### Changed
- **限仙境 is now "the Boundary Realm" everywhere.** It had been rendered five different
  ways across the script: "Gensenkyou", "Genxian", "Boundary Realm", "Hidden Paradise",
  and once dropped entirely. "Gensenkyou" also reads as a Touhou reference, which this
  game is not making. 10 lines.
- **蚩尤 is now "Chi You"**, the Chinese war deity the mound is named for, rather than
  the invented reading "Chiyuu" or the run-together "Chiyou". 12 lines plus 5 map
  terrain names.
- Kanan's line about the Chi You Mound was reworded: 境界僅差転移 is a coined technical
  term, a boundary-margin transfer, not a description of how delicately it was done.

### Fixed
- **96 of the 300 map terrain names were still in Japanese.** The generic reinserter
  sizes a slot as "bytes up to the next NUL", which for landinfo.mti is the Japanese
  name's length rather than the 64-byte field reserved for it, so every English name
  that was longer got refused. `tools/fix_landinfo.py` writes the whole field,
  offset-preserving; all 300 now apply.

### Added
- `tools/build_general3d.py`, a one-command build for the map-name archive. It had been
  done by hand, which is fine once and a trap the second time.

## v1.0.1 - 2026-09-04

Tooling only. Nothing changes in game, so there is no need to re-patch if you are
already on v1.0.0.

### Fixed
- The deploy watcher never fired. `grep -c` prints `0` and exits non-zero when nothing
  matches, so the fallback appended a second zero and every comparison failed with
  "integer expression expected". It sat armed through a real stop while reporting
  nothing.

## v1.0.0 - 2026-09-04

First public release. About 87,000 strings translated.

| Part | Strings |
|---|---|
| Story dialogue (102 script files) | 41,473 |
| Battle quotes | 34,604 |
| Menus and UI | 3,248 |
| Executable strings | 1,697 |
| Options and Q&A | 509 |
| Map terrain names | 300 |

### Added
- The full main story script, battle quotes, menus, the unit and pilot library, help
  text, skills, parts and map terrain names.
- Executable patches so English renders correctly: Latin glyph spacing, a floor under
  the automatic font shrinking, and a fix for the auto-fit bug that letter-spread some
  lines while leaving others compact.
- `tools/setup_rpcs3.py` writes a per-game RPCS3 config for BLJS10133 (Vulkan, 1280x720,
  LLVM recompilers, SPU block size Safe, colour buffers off), leaving global settings
  alone.
- `docs/HACKING.md`, the technical writeup of the formats and engine patches.
- `docs/RELEASE.md`, the short description.

### Changed
- **The machine-translation disclosure is on the front page**, above the install
  instructions, not in a footnote. The English came from a language model and the
  dialogue was not proofread line by line.
- **The game's original Japanese is no longer published.** The worksheets keep the
  English, the byte offsets and the slot sizes; the Japanese moved into
  `build/jp_vault.enc`, encrypted under a key derived from files in your own dump, and
  `apply.py` unlocks it while it builds. If you own the game you will not notice. If you
  do not, the repository does not hand you the script.

### Fixed
- Ability tooltips were clipped or crushed. All 21 were 32-77 characters in a box that
  clips around 37; they are now 11-35.
- Terrain row labels collided with their values, and are condensed to fit.
- `Fixed Weapon` ran into the RANK column, and is now `Weapon`.
- `Transform` collided with the next button legend, and is now `Morph`.
- Skill descriptions: six are two-line records rather than plain strings, and the English
  had been poured onto line 1, crushing it. They are rebuilt as records.
- The library, help, spirit, parts and ACE bonus text: sizing, wrapping, eaten first
  letters, and phantom line breaks from semicolons.
- Result screen labels overlapping their values.

## v0.9.1 - 2026-07-11 (prerelease)

### Added
- GUI installer: `Install (GUI).bat` opens a small window to pick your USRDIR, the RPCS3
  game-data folder and a decrypted `EBOOT.elf`.

## v0.9.0 - 2026-07-10 (prerelease)

First playable snapshot, before human review. Build-from-your-own-dump from the start:
no pre-patched game, because that would redistribute copyrighted data, and because the
game re-encrypts every file on repack so a binary patch would be full size anyway.
