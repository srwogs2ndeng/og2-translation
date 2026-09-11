# Changelog

Versions follow the public releases at
https://github.com/srwogs2ndeng/og2-translation/releases . Each release ships
`og2-english-patch.zip`, which contains the patch, the tooling and the RPCS3 settings
for this title, but no game data.

## v1.0.21 - 2026-09-11

### Fixed (interim)
- **The opening crawl lost the start of its longer lines off the left of the screen.**
  Its English is re-wrapped to at most 40 characters a line, so every line now stays on
  screen. Not a word changes, and both text blocks are byte-for-byte the same length as
  before: the crawl lives in a CSB container that cannot grow, and swapping a space for a
  line break costs nothing.

  This is a stopgap, and it looks like one. The crawl centres each line using a width
  about 1.7 times wider than the width it actually draws, so a line sits further left
  the longer it is. The re-wrap keeps every line on screen, but the block now reads as
  ragged and roughly right-aligned. The likely cause is the letter-spacing EBOOT patch,
  which narrows Latin letters to 0.57 of their advance after the crawl has measured them:
  the ratio measured from a screenshot, about 1.68, is close to 1/0.57. A fix that makes
  the measurement agree with the drawing will follow, and centre the lines properly.

  The route-introduction cards (the Telop screens) show the same overflow pattern on
  paper and are unchanged for now; nobody has reported them cropping.

## v1.0.20 - 2026-09-10

### Changed
- **A failing worksheet now says which one it was.** A Linux user reported "errors with
  a single file", could not tell which, and worked it out by deleting worksheets until
  the run finished - on `155.bmd.json`, which turns out to be fine. One bad worksheet
  aborted the whole container with a traceback that named no file, so that was the only
  way to find out. It now prints the file, the worksheet path and the underlying error,
  and says plainly that deleting a worksheet lets the run finish but silently leaves
  those lines in Japanese.
- A worksheet whose extracted file is missing is reported as such, pointing at path case
  - which matters on Linux and macOS and not on Windows - instead of failing later.

### Note
`155.bmd.json` was investigated and is not at fault: it applies 5/5 cleanly, and the five
record keys in the shipped worksheet match the five entries the Japanese vault holds for
it. Its lines are the game's own bracketed punctuation ("......" and the like). The
command line was most likely what fixed that run, not the deletion.

## v1.0.19 - 2026-09-09

### Fixed
- **Twelve defeat conditions read as orders to the player rather than as things that
  happen to you** - "1. Shoot down Hugo." where it should say "1. Hugo is shot down."
  The Japanese is the same either way: 「ヒューゴの撃墜」 is a noun phrase, "Hugo's
  shooting-down", which reads as an objective in a victory list and as a loss in a defeat
  list. Affects chapters 3, 30, 38, 39, 55, 63, 64, 66, 71, 83 and 91.

  Identified structurally rather than by eye: each stage numbers its victory conditions
  1, 2, 3 and then restarts at 1 for the defeat conditions, so the second run is the
  defeat block. Every candidate was then checked individually against whether the named
  unit is ours, because the same sentence is correct in a victory list - "Shoot down Air
  Christmas" in chapter 79 is an objective and was deliberately left alone.

  The elliptical form already used in about twenty places, "Ally battleship shot down.",
  is left as it is: terse, but not wrong.

## v1.0.18 - 2026-09-08

### Changed
- **天上天下一撃必殺砲 is now "Tenjo Tenge Hissatsuho"**, romanized like the rest of its
  set, rather than v1.0.17's invented "Tenjo Tenge Deathblow Gun". Long vowels are
  dropped to match the "Tenjo Tenge" the unit's other three weapons already use, and for
  the same reason macrons are not used anywhere: the font renders them from the CJK range,
  full-width and misaligned.

### Note on the weapon column
v1.0.17 put the column at about 26 English characters, derived from the longest Japanese
name in the table. That was too generous - the entry it came from evidently renders in a
wider list elsewhere. Observed on screen: 16 characters fits with room, 25 overlaps the
Type column, 35 garbles once the auto-shrink gives up. The true limit is somewhere below
25, so a few names shortened in v1.0.17 may still be too long. They will be measured
against a screen rather than estimated again.

## v1.0.17 - 2026-09-07

### Fixed
- **Long weapon names ran into the Type column, and the longest rendered as overlapping
  glyphs.** The list auto-shrinks text that will not fit, and past a certain length it
  hits the floor this patch puts under that shrinking, so the letters pile up instead.
  Nine names were over the column's width. The Japanese sets it: the longest name the
  game itself ships is 34 half-cells, which is about 26 English characters.

  | Japanese | was | now |
  |---|---|---|
  | 龍王破山剣・逆鱗断 | Ryuoh Hazan Sword: Gekirin Dan | Gekirin Dan |
  | 龍王破山剣・天魔降伏斬 | Ryuoh Hazan Sword: Tenma Gofuku Zan | Tenma Gofuku Dan |
  | 計都羅睺剣・暗剣殺 | Keito Rago Sword: Anken Satsu | Anken Satsu |
  | 計都羅睺剣・五黄殺 | Keito Rago Sword: Goo Satsu | Goou Satsu |
  | 天上天下念動破砕剣 | Tenjo Tenge Psycho Splitter Sword | Tenjo Tenge Splitter Sword |
  | 天上天下念動爆砕剣 | Tenjo Tenge Psycho Blast Sword | Tenjo Tenge Blast Sword |
  | 天上天下念動連撃拳 | Tenjo Tenge Psycho Combo Fist | Tenjo Tenge Combo Fist |
  | 天上天下一撃必殺砲 | Tenjo Tenge Ultimate Cannon | Tenjo Tenge Deathblow Gun |
  | 集束荷電粒子砲 | Focused Charged Particle Gun | Focused Particle Cannon |

  The four paired finishers drop their shared family prefix and keep their distinguishing
  sub-names in full, which is what tells them apart; the unit's other weapons still carry
  it. Five battle quotes that spoke these names were updated to match, so the menu and the
  dialogue agree. 五黄 is *goou* - the *g* is from 五, and 黄 contributes *ou*, not its
  other reading *kou*.

- **Stage victory, defeat and SR Point conditions ran off the right of the screen.**
  17 lines across 15 chapters, Chapter 40's SR condition among them. The objective box is
  a fixed width - it does not shrink to each line - and the longest Japanese condition the
  game ships is 94 half-cells, so the limit is about 74 English characters. Every number,
  turn count, HP threshold and unit name is unchanged; only the wording is tighter.

- **The System Settings / Library tabs sat too far left**, the same fault as the Pilot
  Training tabs in v1.0.16 and fixed the same way, +40 on the X in `wtd_positions`.
  "System Settings" is now "System", which is what fits.

## v1.0.16 - 2026-09-07

### Fixed
- **The Pilot Training tabs sat too far left in their frames**, "Learn Skill" crowding
  its frame's left edge with dead space to the right. Both are moved 40px right and
  confirmed correct in game.

### Added
- **`tools/wtd_positions.py`: per-element X nudges for menu labels.** These six records
  store coordinates in the slots where a size-bearing record stores sizeX/sizeY, so
  `wtd_sizes` refuses them - correctly, there is no font size in them - and until now the
  only apparent remedy was shortening English that was not too long in the first place.
  The labels were mispositioned, not oversized. Every menu label whose record carries no
  font size is now fixable without touching the translation.

  The field is located **by value**, not at a fixed offset: four of the six hold X at
  `off-15` and two at `off-11`, the same record shape shifted along one slot, so a fixed
  offset would have written four correctly and corrupted an unrelated float in the other
  two. Each entry declares the value it expects to find and any record that does not
  match is refused untouched.

## v1.0.15 - 2026-09-06

### Fixed
- **Pre-deploy backups were never pruned, and the folder grew without limit.** Every
  deploy copies the whole live archive into `build/rollbacks/<Archive>/` before replacing
  it, and Battle is 1.6 GB a time. Here that had reached **61 GB across 182 files** - 90
  of them Logic, 22 Battle - which nobody would notice until a disk filled. The newest 3
  per container are now kept and older ones pruned as each backup is made, by `deploy.py`
  and by both General2d/General3d builders.

  Pruning orders by the timestamp **in the filename**, never by mtime: the backup is made
  with `shutil.copy2`, which preserves the source file's mtime, so these files carry the
  game archives' dates - some read 2012 - and an mtime sort would delete exactly the wrong
  ones. Files whose names carry no timestamp are left alone.

  Nothing is lost: `work/*.psarc.sdat` holds the pristine Japanese and any English build
  is reproducible from the worksheets.

## v1.0.14 - 2026-09-06

Documentation only. Nothing in the patch changes.

### Changed
- **Linux and the Steam Deck are confirmed working.** Several people have now reported
  the patch booting on a Deck with the English rendering correctly, which settles the
  one thing v1.0.13's disclaimer could not: the build was verified here, but nobody on
  this end owns the hardware to boot the result. The wording is updated everywhere it
  appears rather than left pessimistic, since "untested" was discouraging people from a
  configuration that demonstrably works.

  Still Windows-only tested, and still said so: the GUI window on Linux, and the optional
  letter-spacing step. macOS remains untested entirely.

## v1.0.13 - 2026-09-06

Documentation only. Nothing in the patch changes.

### Added
- **A plain statement of what is actually tested, on the front page, in the release
  description and in the zip's own `INSTALL.txt`.** Windows is the only platform tested
  end to end - built, deployed and played. On Linux the *build* is verified, and that is
  a real result rather than a guess: the shipped zip run against a pristine dump on a
  case-sensitive filesystem produces all five archives with the same sha256 as the
  Windows build. What is not tested there is the optional `--eboot-elf` step, the GUI
  window itself, and booting the result. macOS is untested. Saying "should work" and
  saying "tested" are different claims and the docs now keep them apart.

### Changed
- Install instructions cover Linux everywhere they appear, not just in the README:
  `python3`, the GUI launcher per platform, and the `python3-tk` / `python3-venv`
  packages that Debian and Ubuntu split out of the stock interpreter.
- `capstone` is described as needed only for the letter-spacing step in all four places
  that list requirements. It was a blanket requirement, which is how people ended up
  trying to install a package they did not need.
- `installer/README.md` said Tkinter always ships with Python. It does not on several
  Linux distributions, which is exactly where the GUI fails with no message at all.

### Fixed
- **`docs/INSTALL.md` documented the General2d build as a copy-paste snippet**, which is
  the same duplication that produced the v1.0.10 bugs - the inline copy in `apply.py`
  had drifted from the builder and silently dropped every font-size fix. It now tells
  you to run `tools/build_general2d.py` and `tools/build_general3d.py`, and says why.
  The manual extraction step also never mentioned General3d, so anyone following it by
  hand would have been missing the 300 map terrain names.

## v1.0.12 - 2026-09-06

### Fixed
- **The v1.0.11 permission fix did not work, and this is the one that does.** Setting a
  unix mode on a zip entry only means anything if the entry also says it came from a unix
  system. Built on Windows, Python stamps every entry `create_system = 0` (FAT), so
  `unzip` reads the mode field as DOS attribute bits and discards it: `install-gui.sh`
  still landed non-executable. Verified this time by unzipping the built artifact on
  Linux and running it, rather than by reading the field back in Python - which is what
  hid the mistake, since the mode was stored correctly and simply ignored.

  If you have the v1.0.11 zip: `chmod +x install-gui.sh`, or just use `bash install-gui.sh`.

## v1.0.11 - 2026-09-06

Linux and Steam Deck. Nothing changes in game: the patched archives are **byte-identical**
on Linux and Windows, so there is no need to re-patch if v1.0.10 already worked for you.

Prompted by two Steam Deck reports, one of which asked whether the patcher is
case-aware. It is, and that is now checked rather than assumed: all 545 worksheet paths
match their archive manifest entry exactly, case included, and there are no case-only
filename collisions among the 20,794 files in the five archives. The whole install was
then run on a case-sensitive filesystem and every output archive came out with the same
sha256 as the Windows build. What actually trips Linux users is distro packaging.

### Added
- **`install-gui.sh`**, the Linux/macOS counterpart to `Install (GUI).bat`. It checks for
  `tkinter` before launching and names the package for your distro, because a Python
  without it fails with a bare `ModuleNotFoundError` that does not say what to install.

### Fixed
- **Everything in the zip was stored mode `0600`, with no execute bit**, so `./install-gui.sh`
  would have come out non-executable. The zip now carries git's own file modes.
- **`tools/setup_rpcs3.py` could not find a Flatpak RPCS3**, which is how the Steam Deck
  installs it - the sandbox redirects the config directory one level deeper.

### Changed
- Install instructions cover Linux: `python3`, the `python3-tk` and `python3-venv`
  packages Debian/Ubuntu splits out of the stock interpreter, and the Arch/SteamOS
  equivalents.
- `capstone` is now correctly described as needed **only** for `--eboot-elf`. It was
  listed as a hard requirement, which sent people installing a package they did not need
  and, on Python builds without a matching wheel, could not get.

## v1.0.10 - 2026-09-05

**Every fresh install was broken from v0.9.0 to v1.0.9, and installs that did work were
missing two sets of fixes.** Re-download and run it again.

All three of these come from the same cause: `apply.py`, which is what you run, had
drifted from the build path used to produce the releases, so none of it was visible from
here. The install path is now built and tested the same way the releases are.

### Fixed
- **The patch died packing the first archive: `FileNotFoundError: build\out\Logic.psarc`.**
  `build/out` holds only generated archives, so git has nothing to track in it and
  neither a clone nor the release zip ever contained it - and the pack step was the one
  write site of four in that file that did not create its own directory. It was invisible
  here because this machine has had a `build/out` since the first build in July. Nobody
  starting from a clean copy ever got past it.
- **None of the menu font-size fixes had ever shipped.** `apply.py` reimplemented the
  General2d build inline instead of calling the builder, and the copy left out the
  `wtd_sizes` step, so all 92 per-element overrides were silently skipped - the condensed
  "Stats" label from v1.0.4, the terrain row labels and the spirit badges among them. They
  were in every release note and in none of the releases.
- **All 300 map terrain names were still Japanese.** `apply.py` had no General3d step at
  all, so the archive holding them was never rebuilt. v1.0.2 said they were fixed; they
  were fixed in the data and never applied to anyone's game.

### Added
- **A check that the archives really are the game's original Japanese, before anything is
  built.** Every worksheet offset is a byte position in the Japanese file, so pointing the
  patch at a USRDIR you have already patched used to fail with
  `ValueError: no NUL terminator after 0x91` from deep inside the reinserter, which does
  not hint at the cause. That is a normal upgrade path - unzip the new release, run it on
  the game you patched last time - so it now checks a sample of strings against their
  recorded offsets and says plainly what is wrong and what to restore.

### Changed
- `apply.py` calls `tools/build_general2d.py` and `tools/build_general3d.py` rather than
  reimplementing them, and creates the generated directories up front. Two of the three
  bugs above were a second copy of a build path drifting from the first; there is now one
  copy. Verified by running the release zip against a pristine dump and comparing every
  output archive against the ones this project ships from.

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
