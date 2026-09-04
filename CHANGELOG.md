# Changelog

Versions follow the public releases at
https://github.com/srwogs2ndeng/og2-translation/releases . Each release ships
`og2-english-patch.zip`, which contains the patch, the tooling and the RPCS3 settings
for this title, but no game data.

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
