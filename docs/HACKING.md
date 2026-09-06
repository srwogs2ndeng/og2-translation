# How the patch was made

Target: *Dai-2-Ji Super Robot Taisen OG* (PS3, BLJS10133). Developed and tested on RPCS3.
Tooling is about 50 Python scripts, no dependencies beyond `capstone` for disassembly.

## Containers

The game ships five PSARC archives (Logic, Battle, Common, General2d, General3d), each
wrapped in SDAT encryption. Two things had to work before any text could be changed:

- **SDAT unwrap and rewrap**, including the per-block HMAC that RPCS3 treats as fatal. A
  rebuilt archive that decrypts correctly but fails one block check will not boot.
- **Override repacking.** General2d is 638 MB and only one file inside it ever changes, so
  the packer appends the new file, repoints its TOC entry, and copies everything else
  verbatim instead of rebuilding the archive.

## Text formats

Six formats carry text. Each had a trap in it.

**FIXH** (`Logic/Dat/FixedData/*.dat`) is a tagged container: header, DATA records, SOFS
offset table, STRI string block. SOFS is a flat array of **32-bit big-endian** offsets
relative to a string-block base of `STRI + 0x12`, exact across all 26 files. Reading them
as 16-bit appears to work, because each entry's high half is usually zero, but it cannot
address a block larger than 64 KB, which is why several files stayed Japanese until this
was corrected.

Growing a string is append-and-repoint. That is safe only for strings something points
at. Several FIXH files are **position-addressed** instead:

- HelpData, SpiritData, PartsData and ACEBonusData locate line 2 and beyond by a fixed
  byte stride from the entry start, or by a length byte that is also the string's header.
  Resizing anything shifts those, and later lines start mid-word. These files are rebuilt
  offset-preserving: every segment keeps its exact Japanese byte length.
- SkillData descriptions are sometimes not strings at all. Six of them are records:
  `[u16 line-2 character count][u16 line-1 bytes + 1][line 1][NUL][line 2][NUL]`,
  recognisable because the pointer target begins with a NUL byte. An extractor that walks
  NUL-terminated strings sees only line 2.

**Script files** (`Logic/Dat/logic/talk/ls*.bin`) hold the story text and support growth.
**BMD** files hold battle quotes. **WTD** (`General2d`, `windowdataMain.wtd`) is the menu
chrome: every text record carries its own font size as two big-endian floats immediately
before the string, behind a marker byte pattern, so a single overrunning English label can
be condensed on its own without touching anything else. **MTI** holds map terrain names as
1024 fixed 84-byte records. **CSB** holds the Q&A screens.

### Data traps worth knowing

- `;` is a **line-break control byte** in the library parser, not punctuation. Any
  semicolon in an English description produced a phantom line break mid-sentence.
- Bracketed `[...]-` strings in the scripts are **byte-matched engine keys**. Translating
  them silently skipped every interlude and killed stage BGM.
- Library description slots begin with a 1 to 3 byte control header before the text.
  Writing English from byte zero ate the first letters of entries across the whole
  library.
- The renderer **measures trailing spaces**. Padding a slot to its capacity made the font
  size track the slot rather than the text, which looked like a rendering bug and was not.
- A slot left completely empty lets a run of NULs collapse, and the next entry's text
  bleeds into it.

## Engine patching

English in an engine built for fixed-width Japanese needs code changes, not just data.
Thirty patch regions are applied to the EBOOT and rebuilt into a working fSELF. All new
code lives in an unused run of zeroes at `0xc45928..0xc45d2b`.

- **Glyph advance.** Latin glyphs were spaced on Japanese metrics. The advance is scaled
  by a constant K (0.57) in a cave.
- **Font size floor.** `SetFontSize` at `0x5cb970` writes the x and y size. The engine
  steps the size down by ×0.9 repeatedly until a line fits, so long English lines decayed
  to unreadable. A cave clamps the result.
- **The auto-fit bug.** Both text engines decide whether a line fits by measuring it as
  flat monospace, `glyphs × fontsize`, at K=1.0, while drawing it at K=0.57. A 33
  character line therefore "overflowed" a 672 pixel box on paper at 712.8, when it
  actually draws to 406. Overflowing lines are handed to the Japanese equal-distribution
  justify path, which ignores K and spreads the glyphs to the margin. That is why some
  lines looked letter-spaced and others compact. Both comparison sites are redirected to
  caves that compare `measured × K` against the box width. The comparison only: the
  justify path's own ratio has to stay computed from the unscaled measure, or genuinely
  overlong lines overfill the box by about double.

## Finding all that

The renderer was located with a purpose-built instrumented RPCS3. RPCS3 already contains
memory breakpoints behind the `HAS_MEMORY_BREAKPOINTS` build flag, compiled out by
default; enabling them and adding a small log-and-continue layer gives:

- file-driven read and write breakpoints that dump every general and floating-point
  register plus a call stack, and
- an execution watch on chosen addresses, running at full speed on block entry, with an
  opt-in precise mode for mid-block addresses.

This mattered because the library reaches the text engine through a **deferred render
pass**. Breakpoints on the source string only ever caught the parser, which is why an
earlier attempt concluded, wrongly, that the library never touched the text engine at all.

## Pipeline

Translation lives in JSON worksheets keyed by Japanese file offset, one per game file.
Every build resets each file from a pristine Japanese extract before applying its
worksheet, so offsets are always valid and a build is reproducible from source. Each
deploy keeps a rollback copy of the archive it replaces.

No game data is in the repository. The distribution rebuilds everything from the user's
own dump.
