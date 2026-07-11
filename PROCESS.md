# Dai-2-Ji Super Robot Taisen OG (PS3, BLJS10133) — English Translation: End-to-End Process

A complete, reproducible record of every reverse-engineering and pipeline step used to
translate *2nd Super Robot Wars Original Generation* into English and run it on RPCS3.
Everything is **pure Python, no compiler**. Tools live in `tools/`, translation source of
truth in `build/worksheets/`, pristine extracts in `work/`, built artifacts in `build/out/`.

> **This is a living document** — updated as new findings land. See the Changelog at the
> bottom for the running log of discoveries, dead ends, and status changes.

---

## 0. High-level architecture

```
game .psarc.sdat ──decrypt──▶ .psarc ──unpack──▶ loose files (work/<Archive>/)
                                                        │
                                                   scan for CJK strings
                                                        │
                                              build/worksheets/<Archive>/**.json   ← translation source of truth
                                                        │  (multi-agent workflows fill "en")
                                                        ▼
   work/ (pristine) ──apply worksheet──▶ build/en/<Archive>/  ──repack──▶ build/out/<Archive>.psarc
                                                                                 │ encrypt (SDAT wrap)
                                                                                 ▼
                            deploy: copy .sdat → games/BLJS10133_EN/.../PSARC/ ; wipe GD to force reinstall
```

The EBOOT (executable) is a separate lane: decrypt → patch ELF (strings + code caves) →
re-wrap as fake-signed SELF (fSELF) → copy to `USRDIR/EBOOT.BIN`.

**Golden rule discovered early:** every reinsertion path must **self-verify** (re-scan the
output, confirm each edited offset reads back the exact bytes; a no-op rebuild must be
byte-identical). Trusting the eye caused a combat crash once; the verify gate caught the rest.

---

## 1. Crypto & container layer (the "extraction pipeline")

### 1.1 SDAT decryption — `tools/decrypt_sdat.py`
PS3 archives ship as `<name>.psarc.sdat` — an **NPD/SDAT** wrapper: a header + the payload
split into blocks, each with an HMAC-SHA1. Ported the SDAT path of `make_npdata` to pure
Python (`cryptography` lib for AES/HMAC).
- `decrypt_sdat(in.sdat, out.psarc)` → plaintext PSARC.
- Header gives version, flags, block size, total file size (verified against output length).

### 1.2 SDAT re-encryption — `tools/encrypt_sdat.py`
The inverse, needed to deploy. `wrap(orig_sdat_template, new_psarc, out_sdat)` re-encrypts a
(possibly different-size) PSARC using the **NPD key material from the original .sdat** as a
template. Re-computes every block HMAC. This is what makes a modified archive bootable.

### 1.3 PSARC pack/unpack — `tools/extract_psarc.py`, `tools/pack_psarc.py`
PSARC v1.4, zlib compression, 64 KB blocks. Structure:
- Header (`PSAR`, version, comp=`zlib`, toc_length, entry_size=30, num_files, block_size, flags).
- TOC: `num_files` entries of `[md5(16)][block_index(u32)][uncompressed_size(u40)][offset(u40)]`.
- Block-size table (each entry `bnum` bytes; 0 = full uncompressed block).
- Data region: zlib blocks.
- **File 0 is the manifest** — a newline-separated list of the names for files 1..N-1.

`pack_psarc.pack(orig_psarc, src_dir, file_bytes={name:bytes})` rebuilds the archive,
overriding only the named files (rest read from `src_dir` or reused). Dedups identical files.

### 1.4 Fast override repack — `tools/repack_override.py` (built for General2d)
`pack()` recompresses every block and needs the whole archive on disk — wasteful for the
**638 MB General2d** where we change **one** file. `repack_override(orig_psarc, {name:bytes})`:
keeps every original compressed block verbatim, appends only the changed file's new blocks,
and shifts every TOC entry offset by the TOC-growth delta (adding block-table rows grows
`toc_length`, moving the data region). **~1.4 s vs minutes**; verified byte-identical across
123 sampled files. This made iterating on the menu chrome practical.

---

## 2. Text-format reverse engineering (per container)

All game text is **UTF-8, NUL-terminated** (no Shift-JIS wall). The work was finding, per
container, *how strings are addressed* so they can be replaced or grown without breaking
offsets. `tools/reinsert_utf8.py` provides `scan(data, cjk_only)` (every NUL-terminated valid
UTF-8 run) and `reinsert_grow(data, {off:text})` (in-place if it fits, else refuse).

### 2.1 LDBI — dialogue talk files (`Logic/Dat/logic/talk/ls*.bin`)
Conversation dialogue. Lines break only at literal `@` markers (no auto-wrap), so English
sized for Japanese overruns the box. `worksheet.rewrap(text, width)` re-flows each `@`
segment to a column budget, inserting extra `@` breaks. Grows via append+repoint.

### 2.2 LOGO — scenario scripts (`Logic/Dat/logic/scr*.bin`, 102 files)
Stage scripts: **mission objectives, victory/defeat conditions, stage titles, `[ＤＭ]-name`
speaker tags, event captions**. 32-bit pointer tables addressing a string pool. In practice
English is byte-shorter than CJK (3 B/char), so **99% fit in-place** (offset-preserving);
`tools/logo.py` grows the rest (append + repoint). 11,468 strings **dedupe to 770 unique**
(the same ~162 characters repeated across all 102 stages) — one workflow covers them all.

### 2.3 FIXH — gameplay database (`Logic/Dat/FixedData/*.dat`) — `tools/fixh_grow.py`
Weapon/Spirit/Unit/Pilot data, Ability/Skill/Parts, the **encyclopedia** (Unit/Pilot
Dictionary), HelpData, KeyGuideData, KeyWordData. This was the hardest data format.

**Tagged-section container:** `[FIXH hdr][DATA records][SOFS section][STRI section]`.
- `SOFS` = `['SOFS' | u32 size | offset table]`. **The table is 32-bit big-endian offsets**
  (first assumed 16-bit — that only *appeared* to work because each 4-byte entry's zero high
  half resolved to block-offset 0, and it physically could not address the two 100 KB+ files
  whose offsets exceed 0xFFFF; that was the stuck ~246 strings).
- `STRI` = `['STRI' | u32 size | u32 count | u32 flags | 2-byte pad | string block]`.
  **Block base = STRI + 0x12** (exact: a string's stored offset + base == its file position).

**Two growth mechanisms, both self-gated:**
- `grow()` — append+repoint (for SOFS-referenced strings).
- `splice_grow()` — the winner. Many long **dictionary descriptions are adjacency-read** (no
  offset field points at them; the game reads a name via SOFS then walks to the next string).
  Splice rewrites each edited string in place inside the block and fixes up **every** SOFS
  offset by the cumulative insertion delta. Safe because SOFS is the *only* thing referencing
  block offsets (verified: no other 32-bit block/file pointer targets these strings; inline
  bytes are position-relative control codes, not pointers). Hard-gated: fails closed to the
  original bytes unless a no-op is byte-identical, every SOFS resolves post-splice, every
  non-edited name is byte-identical, every edited string reads back correct, and the NUL-unit
  count is unchanged. **Result: FixedData 100%** (6839/6839).
- **Crash lesson:** an early heuristic base (0x142D9 for WeaponData; correct is 0x1429A) put
  the offset table into garbage → corrupted weapon data → combat crash at the text renderer.
  Fixed by the deterministic SOFS/STRI parse + the hard gate.

### 2.4 CSB — Common menu/Q&A (`Common/Dat/Option/QA/`, `Common/Dat/Archive/Csb/`)
Menu text, the strategy Q&A, Archive story blurbs. **Offset-preserving only** — the game
rejects a Common CSB whose block size changed. So English must fit the original byte slot;
overruns are shortened by hand (e.g. `編成編`→"Formation" fit 9 B exactly; long Archive
blurbs trimmed a few bytes to fit).

### 2.5 BMD — battle lines/cut-ins (`Battle/Dat/Battle/Message/*.bmd`)
34,450 battle quotes. Same offsets recur across many BMD files, so worksheets use **compound
keys `relpath|offset`** (`wf_prep.splitdir`/`collectdir`) to avoid cross-file collisions.
96.5% fit in-place.

### 2.6 WTD (`_DTW`) — menu chrome (`General2d/Dat/Window/WindowToolData/windowdataMain.wtd`)
**All UI labels** (Library, main menus, stat screen, pilot training, parts, etc.) — 3,290
records. This was un-extracted for most of the project (it's in the 638 MB General2d, not
Battle/Common/Logic). Format: `_DTW` UI-layout binary. Menu text records are:
`[1-byte length][UTF-8 content][NUL]` where **length = 1 + content bytes** (= offset from the
length byte to the terminating NUL). Records are embedded among layout binary (position
floats, texture refs), and **~214 absolute offset references** point at string starts.
`tools/wtd_tool.py` edits **offset-preserving in place**: rewrite content, keep the record's
byte span, NUL-pad the freed tail. 3290 records dedupe to 979 unique.

Two crashes cracked the format (both now documented in code):
- **CRASH #1 — ASCII `<>` are control tags.** The renderer parses `<C=..>`, `<I=61>`, `<W=..>`
  as tags (564 wtd strings use them). Converting the menus' fullwidth `＜＞` display brackets
  to ASCII `<>` made `<Robot Library>` look like a malformed tag → **crash on opening the
  Library**. Fix: **keep fullwidth `＜＞【】`** in English; never emit bare ASCII `<`/`>`.
- **CRASH #2 — length-driven traversal.** Records are variable-length and the game walks to
  the next field using each record's length byte (proven: the same label sits at *varying*
  strides 0x40/0x44/0x70). Updating the length byte to the shorter English length while the
  next field stayed at its physical position made the game read the next field from inside the
  NUL padding → crash. Fix: **do not change the length byte** — write English + NUL + NUL
  slack inside the original span. The record stream then parses byte-identically; only the
  visible content differs.

### 2.7 EBOOT hardcoded strings
2,500 CJK strings baked in the executable: system messages, confirmations, install/error
dialogs, weapon & attack category labels, spirit-command prompts, the Archive cut-ins.
Patched **in-place** (English is byte-shorter than CJK; the code references string start
addresses, so offset-preserving is safe). Strict gate: **preserve every `%d`/`%s`/`%3.3f`
format specifier and `@`/`\n` marker**, no control chars, byte-length ≤ original. A strict
"real Japanese" filter (hiragana/katakana/common kanji, no control bytes) excludes ~360
binary false-positives (executable bytes that decode as obscure CJK) and internal identifiers
(font resource names, `dd%04d.dat` file patterns) that must never be touched. **1,561 offsets
patched.**

---

## 3. Translation layer

### 3.1 Worksheets — `tools/worksheet.py`
`dump <container> <work.json>` produces `{hexoff:{jp, en:"", slot}}` for every CJK string.
`apply` writes the normalized `en` back (in-place if it fits, format-specific growth
otherwise) and **self-verifies** the round-trip. The worksheet is the git-tracked source of
truth; regenerating `build/en` from `work` + worksheets is deterministic.

### 3.2 Punctuation normalizer (memory: ascii-punctuation-rule)
English must use **half-width ASCII** punctuation (`'` `"` `-` `...`), never typographic
Unicode — the font renders CJK-range punctuation full-width/misaligned. `normalize()` maps
`’‘→'  “”→"  —–―→-  …→...  ！？（）：；，．→ASCII`. WTD keeps fullwidth `＜＞【】` (see 2.6).

### 3.3 Glossary — `glossary/glossary.json`
162 canonical character/unit/faction names (JP→EN) scraped from 2ndsrwoge.com and the
character PDFs (`tools/build_glossary.py`). Fed to every translation agent for consistency.

### 3.4 Multi-agent translation workflows (`build/workflows/`, and inline scripts)
Large string sets are translated by fan-out workflows: dedupe to unique strings → split into
~40-string batch files → N agents each Read a batch + the glossary and return
`{t:[{id/k, en}]}` under a JSON schema (forces structured output, retries on mismatch).
Prompts encode the per-format rules (byte budgets, preserve tags/specifiers/brackets, glossary
names). Over-budget translations **fall back to Japanese** rather than risk anything. Runs:
Phase-1 menus/Q&A (~502), Phase-3 battle (34,442), FixedData, menu chrome (959 unique), EBOOT
system (2,021 unique), scenario objectives (770 unique).

---

## 4. Deployment — `tools/deploy.py` + the GD gotcha
`apply → pack → deploy` per archive, with rollbacks at every step.
- Each translated file is **reset from the pristine JP base** before its worksheet is applied,
  so offsets are always valid.
- `deploy` backs up the live `.sdat` to `build/rollbacks/<Archive>/<ts>.sdat`, copies the new
  one into the game folder, then **wipes the GameData (GD) directory**
  (`dev_hdd0/game/BLJS10133`) so the next boot force-reinstalls from the folder.
- **Corruption-guard gotcha:** the game's `cellGameDataCheck` shows 「ゲームデータが壊れています」
  if the folder and GD disagree. Deploying to both + wiping GD for a clean reinstall avoids it.
- General2d has its own build path (uses `repack_override` + manual encrypt/deploy, not the
  standard recompress).

---

## 5. The EBOOT lane (executable reverse engineering)

### 5.1 Scoping the EBOOT
`EBOOT.BIN` is an SCE/fake-SELF. The plaintext ELF header is at file offset 0x90; **seg0 =
PT_LOAD, vaddr 0x10000, plaintext PPC64** (so `file_off = vaddr − 0x10000`), seg1 encrypted.
Binary is stripped (no symbols/sections). Decrypt via RPCS3 → Utilities → Decrypt PS3 Binaries
→ `EBOOT.elf`. Static analysis with **capstone** (linear disasm) and a Ghidra project
(`_re/`, EbootAgg) for the call graph.

### 5.2 fSELF re-wrapping — `tools/make_fself.py`
Wraps a plaintext PPC64 ELF into a **fake-signed SELF** (flags 0x8000) that RPCS3 boots
directly. Header offsets match retail exactly (appinfo 0x70, elf 0x90, phdr 0xD0, secinfo
0x290); appended ELF is byte-identical. Deploy = copy to `USRDIR/EBOOT.BIN`; RPCS3
recompiles PPU on the new hash automatically (no cache clear needed).

### 5.3 Dialogue letter-spacing — `tools/patch_eboot_advance.py`
The font is a **fixed-cell bitmap atlas** (FTTF, 32×32×8bpp glyphs), so Latin renders in
full-width cells → gappy, overrunning text. The advance is **renderer-controlled**, not a
font field (confirmed: editing font.bin widths changed nothing on screen). Per-glyph advance
in the layout routine = `f28 (scale) × width_byte`, then `fadds f30,f30,f0` accumulates x.
The fix redirects the advance-multiply to a **code cave** in the RX seg0 zero-run (@0xC45930)
that scales it by K (K=0.66 float @0xC45950): `fmuls f0,f28,f0` → scale → branch back.
Deployed at site **0xA150D8** (FUN_00a149e8) — fixes the **main dialogue box**.
- **Cave stack-spill crash lesson:** the cave spills a scratch GPR/FPR; slots that a host
  function already uses cause a combat crash. `tools/patch_eboot_menu_advance.py` uses the
  **red zone** (r1−8/r1−16) and saves+restores *both* r12 and f12, so it's safe for any host
  function (the cave makes no calls, so the red zone is guaranteed free).

### 5.4 The still-open rendering problem (status at time of writing)
Only the **main message box** is spacing-fixed. Other screens (stat/unit, Spirit Command,
Back Log, in-battle event overlay, intermission menus) render Latin full-width and
overlap/clip. Findings:
- The font-file route is a **confirmed dead end** (runtime widths not from font.bin).
- The **only** route is per-renderer EBOOT advance-scaling; the blocker is *identifying which
  renderer draws each screen*. Mapped all text-advance sites; ruled out several by boot test.
  The tutorial renderer was found (one of 0x4a5e84/0x61f89c) and tightened successfully.
- **Stat/Spirit/tab screens are fixed-position layout** (label at x1, value at x2) — no
  per-glyph advance to scale, so no code patch helps; instead their labels were
  **abbreviated** to fit (Melee→Mel, Unit Ability→Unit, Target→Tgt, etc.). This worked.
- **Back Log clipping** fixed by tightening the dialogue **rewrap width** (37→28).

**Renderers patched / ruled out for the stat/Spirit letter-spacing (all boot-tested):**

| Site | Function | Instruction | Result |
|------|----------|-------------|--------|
| 0xA150D8 | FUN_00a149e8 | `fmuls f0,f28,f0` | ✅ fixes main dialogue box |
| 0x4A711C / 0x61FA4C | 0x4a5e84 / 0x61f89c | `fadds f30,f30,f0` | ✅ one is the **tutorial** renderer (tightened) |
| 0xA12968.. (5 sites) | FUN_00a123f0 | `fadds f30,f30,f0` | ❌ no on-screen effect (wrong sites) |
| 0x957418, 0xC04358/B90, 0xC056C4/F0C | 0x956be8/c03de4/c05144 | `fmuls f0,f28,f0` | ❌ no on-screen effect |
| **0xA12B0C** | FUN_00a123f0 | `fmuls f0,f27,f0` (real glyph advance) | ❌ **no effect — reverted** |

**Conclusion (2026-07-05):** the only two *width-read-confirmed* glyph-advance sites in the
whole EBOOT are 0xA150D8 (dialogue) and 0xA12B0C (FUN_00a123f0) — and neither draws the
stat/Spirit menus. Therefore **those screens do not use a per-glyph float advance**; they
almost certainly use **fixed integer-grid positioning** (x = base + index×cell_width), which
is not practically findable by static disasm (integer steps are ubiquitous). Static
advance-scaling is **exhausted** for these screens. Remaining levers: (a) the label
**abbreviations** already deployed (the practical ceiling), (b) an **RPCS3-debugger** session
to breakpoint the stat-screen render and read the actual positioning code (high effort,
uncertain payoff). The **text** is fully translated; this is rendering polish only.

---

## 6. Rebuild-from-scratch procedure

```sh
# one-time extraction
python tools/decrypt_sdat.py <game>/PSARC/Logic.psarc.sdat   work/Logic.psarc
python tools/extract_psarc.py work/Logic.psarc               work/Logic        # (repeat: Common, Battle)
python tools/decrypt_sdat.py <game>/PSARC/General2d.psarc.sdat work/General2d.psarc   # menu chrome

# translate (worksheets are already filled + git-tracked); regenerate + deploy an archive:
FIXH_GROW=1 python tools/deploy.py apply  Logic
FIXH_GROW=1 python tools/deploy.py pack   Logic
FIXH_GROW=1 python tools/deploy.py deploy Logic

# General2d (menu chrome) — manual fast path:
#   wtd_tool.apply → repack_override → encrypt_sdat.wrap → copy to folder + wipe GD

# EBOOT:
python tools/patch_eboot_advance.py _rollback/EBOOT.elf.orig build/EBOOT.fx.elf 0.66  # font fix
#   apply eboot worksheet strings in-place (format-specifier gated)
#   optional: patch_eboot_menu_advance.py for extra renderers
python tools/make_fself.py build/EBOOT.final.elf build/EBOOT.BIN
cp build/EBOOT.BIN <game>/USRDIR/EBOOT.BIN
```

Rollbacks: `build/rollbacks/<Archive>/<ts>.sdat`, `build/rollbacks/EBOOT/<ts>.BIN`,
`_rollback/EBOOT.BIN.orig`.

---

## 7. Status summary (text = essentially complete)

| Layer | Container(s) | Status |
|-------|--------------|--------|
| Menus / Library / Q&A | Common CSB | ✅ deployed |
| Gameplay data + encyclopedia | Logic FixedData (FIXH) | ✅ 100% |
| Battle lines / cut-ins | Battle BMD | ✅ ~96.5% in-place |
| Mission objectives / stage titles | Logic scr (LOGO) | ✅ deployed (99% in-place) |
| Menu chrome (all UI labels) | General2d WTD | ✅ 100% translated |
| System UI (dialogs, categories, archive) | EBOOT strings | ✅ 1,561 patched |
| Main dialogue letter-spacing | EBOOT code cave | ✅ fixed |
| Fixed-layout label overlap | WTD/EBOOT labels | ✅ abbreviated |
| Back Log wrap | rewrap width | ✅ fixed |
| Story pilot (main script) | Logic ls talk | ◐ prologue done; bulk is Phase 2 |
| Fixed-layout label overlap (stat/Spirit/tabs) | WTD/EBOOT labels | ✅ abbreviated |
| Stat/Spirit/menu letter-spacing (full-width) | EBOOT renderers | ⛔ static route exhausted (fixed integer-grid) — debugger only |

The **text** is essentially fully translated and deployed. The one unresolved item is the
full-width letter-spacing on a few fixed-position screens (stat/Spirit), which is a rendering
limitation, not missing translation.

---

## Changelog (living log)

- **2026-07-08 (terrain-gap fix via grade-string prefix - no renderer trace)** —
  Continued the terrain-box hunt: the descriptor is fully data-driven (accessed
  via struct base pointers, no direct address loads), so the grade-draw x-offset
  isn't statically pinnable without tracing the generic WTD element renderer.
  Found a cleaner lever instead: the rank-indexed grade-letter table (subdesc
  0xCF1768 -> glyphs at 0xC498F8 '－' / 0xC49900 'Ｄ' / ...Ｃ/Ｂ/Ａ/0xC49920 'Ｓ')
  is single full-width glyphs, each in an 8-byte slot using 4. Prepending a
  space to each (offset-preserving; descriptor pointer unchanged) shifts every
  drawn grade right by one space -> opens the label<->grade gap while keeping
  inter-column spacing (all grades shift equally). VA/file-offset note: these
  file offsets collide with unrelated worksheet keys (0xC49908 Evade / 0xC49920
  Aim) but build_eboot resolves those by JP-byte match to other offsets, so it
  won't clobber the grade table. `patch_eboot_test_terrain_gap.py` (half-width
  default, `full` for full-width) builds the test. If the renderer re-measures/
  re-centers the string the space gets absorbed (fall back to the x-offset
  trace); if it left-draws at the anchor, the gap opens. Awaiting in-game round.

- **2026-07-08 (fontsize folded permanent; terrain-box descriptor mapped)** —
  (A) The window-family fontsize fix (Kf=0.8) is folded into
  eboot_code_patch.json (26 regions); build_eboot reproduces it byte-exactly.
  Confirmed in-game: menus centered, button guides fixed, KEY WORD box tight.
  `patch_eboot_test_fontsize.py Kf` is idempotent - on the folded build it just
  retunes the Kf float @0xC45CB0 (one word) for size comparisons.
  (B) Terrain-box overlap ("SkA+" jam on the stat screen): the WTD-nudge route
  is DEAD (owner verified from work/General2d: the grade letter is NOT in the
  WTD - only the kanji label is; 172 label records are non-uniform, no single
  delta). The gap is renderer-controlled. Mapped the EBOOT terrain descriptor:
    - element name strings @0xC49398+: `chikei_tekiou`, `sora`/`riku`/`mizu`/
      `chi` (air/land/sea/space).
    - descriptor array @0xD55150+: chikei_tekiou slot (0xD55158) -> sub-desc
      0xCF1768; two terrain-column child lists @0xCF191C and 0xCF192C (each =
      sora/riku/mizu/chi) = the two grade columns.
    - GRADE-LETTER table @0xCF176C: fullwidth Ｄ/Ｃ/Ｂ/Ａ/Ｓ (0xC49900/08/10/18/
      20), rank-indexed; drawn at each terrain element's anchor.
  NEXT (unfinished): find the WTD element renderer that walks this registry and
  draws the grade at element_anchor + x_offset; nudge that x_offset to open the
  label<->grade gap. The descriptor base isn't a direct address load (accessed
  via a struct base pointer / name-match walk), so the renderer trace is the
  remaining work - or an RPCS3-debugger breakpoint on the grade draw (the tool
  HANDOFF flags for exactly this "which code positions this" question).

- **2026-07-08 (font-size v1 dead end; v2 = window-family fontsize lever)** —
  v1 (scale billboard unit-quad 0x00C41980) tested in-game: ZERO visible change.
  Those +/-1 floats are a corner OFFSET added to the vertex, not a size scale.
  Re-traced via the window-family quad emitter FUN_005d0618 (draws the Robot
  Library list, KEY WORD/dict boxes - the actual screens): glyph quad extent
  f31 = glyph_metric * (fontsize/32) @0x5D0840/5C, and the advance = fontsize/
  cellsize (FUN_00a11f28). BOTH derive from context fontsize @+0x2c, written
  once per string in setup FUN_005cb970 (`stfs f1,0x2c(r3)` @0x5CB984). So for
  the window family, one knob (fontsize) scales SIZE + spacing together =
  genuinely smaller, correctly-spaced text. (The old "font_size does nothing"
  finding was about the DIALOGUE renderer 0xA149E8, whose quad comes from a
  runtime buffer - different renderer; doesn't apply here.) v2 probe
  `patch_eboot_test_fontsize.py Kf` redirects the fontsize store to a LEAF-SAFE
  cave (no stack writes: r12+f0, both dead in the setup - FUN_005cb970 itself
  uses the red zone, so a spill would crash it) that scales fontsize by Kf
  before storing. Also note for the record: exp3 (window-family advance K) was
  NEVER folded into eboot_code_patch.json, so the base deployed build renders
  the Library list full-width; the fontsize lever supersedes exp3 (fontsize
  scales advance too), so fold whichever verifies.

- **2026-07-08 (GLYPH-SIZE lever found: the billboard unit-quad @0x00C41980)** —
  Chased the on-screen glyph SIZE (not advance) through the dialogue renderer's
  vertex assembly (0xA14FF0-0xA15200): the glyph billboard corners come from a
  static unit-quad table at 0x00C41980 = {(1,1),(1,-1),(-1,1),(-1,-1)} (the +/-1
  half-extents), combined with pen position + runtime per-glyph buffers. Key
  result: this table is read at EXACTLY 8 sites, ALL in the two text renderers
  FUN_00a123f0 (4x) + FUN_00a149e4 (4x), NOWHERE else, and has no direct-address
  refs - so it is a TEXT-ONLY size lever. `tools/patch_eboot_test_fontsize.py Kf`
  scales the 8 floats by Kf (default 0.85) = smaller glyphs in text renderers
  only. PURE DATA PATCH (no code cave, can't crash). This is the probe for the
  "spacing can only go so far" wall; if it shrinks glyphs cleanly it's the first
  working glyph-size lever (all prior font_size/atlas routes were dead ends).
  Pairs with the deployed advance K=0.6. Diagnostic outcomes in the tool
  docstring (clean shrink vs baseline drift vs UV distortion).

- **2026-07-08 (font-size lever fully mapped + plaintext-terms readability fix)** —
  (A) Shipped the immediate readability fix: keyword/dict inline `<term>` links
  render as PLAIN tight text (strip_terms, OG2_PLAINTEXT_TERMS default on) -
  stops the full-width term glyphs from overflowing their positional slot and
  clipping the link+tail. Fixes the malformed paragraphs and "wrong links" at
  the data layer; needs only `deploy.py build Logic`, no EBOOT round. Reversible.
  (B) Mapped the glyph-SIZE lever in the dialogue renderer 0xA149E8 (the pattern
  generalizes): the on-screen glyph quad is built from the glyph's atlas bytes x
  the text-context scale fields r31+0x14/0x18/0x1c/0x20/0x24/0x28 (populated at
  FTTF load, the fdivs cluster @0x5CD2D0 = dim/cellsize UV normalizers) via the
  four `fmadds` @0xA15050/0xA15070/0xA1508C/0xA150AC → quad corners on stack
  (0xb4/0xb8/0xbc/0xc0); screen position = pen accumulator f30. Because the atlas
  is fixed-cell, each glyph draws a full `fontsize`-wide cell (context +0x2c),
  which is exactly why spacing (advance = fontsize/cell x width, @0xA150D8) can
  tighten gaps but never shrink the letters. **The true smaller-font lever =
  reduce fontsize (context +0x2c): it scales the quad AND the advance together
  = genuinely smaller readable text.** 0x2c is read at 0xA14BAC (→ fdivs f28
  advance scale) and 0xA14F2C. NEXT: a bounded probe that scales 0x2c down at
  the read sites for the text-heavy renderers (careful, multi-site; must not
  crash - build like the leaf-safe caves). Compact-font swap still blocked at
  the undecodable atlas; fontsize reduction is the viable route.

- **2026-07-08 (round 3 result: exp3 works; three distinct problems isolated)** —
  v3 test EBOOT booted; KEY WORD box body text now renders TIGHT (window-family
  width-engine K-scale confirmed working — the main spacing win). Screenshots
  isolated the remaining issues into THREE separate mechanisms, do not conflate:
  1. **Inline `<term>` links clip their line** (keyword/dict boxes) — this is
     BOTH the "wrong glossary links" and most of the "malformed paragraphs."
     Proof: EOTI seg6 authored "became the parent body of the <DC>, whose"
     renders as "became the parent body of the" — the link AND everything after
     it on that line vanish. Plain link-free lines (43 chars) render fine; a
     41-char line WITH a `<DC>` overflows. So the inline TERM TEXT still draws
     full-width (the window-family term/underline path was never K-scaled;
     exp3 fixed only plain-run advance via a11f28/a12190). JP uses the same
     ASCII `<>` (U+003C/E) so brackets aren't the bug — the term glyphs are
     just wide, overflow the positional line slot, and clip. FIX = find the
     window-family term advance path (walker `<` handler → tagR/tagU
     0x5CB9FC/0x5CC068) and K-scale it; then re-tune fixer TAG_COST/WRAP.
  2. **Positional segment structure forces orphan lines** — these boxes draw
     one JP-authored line per byte-slot segment; Project TD has a 6-byte
     segment that can only hold "builds", so it's alone on a line no matter
     how we wrap. Inherent to the position-addressed format; only cosmetic.
  3. **Robot-info detail box renders MIXED glyph SIZES** — a genuinely
     different renderer (the condense-to-fit widget, FUN_006205e4 family, the
     one whose edge-fade ramp v1 probed): some runs draw full-size, some
     condensed small, interleaved. Untouched by exp3. Separate work item.
  Font-size (strategic): confirmed the only real lever. Glyph SCREEN size =
  text.fontsize (context +0x2c) → `fdivs f28,fontsize,cellsize` (@0xA14BCC in
  the dialogue renderer) → fed into quad-corner vertex math; the advance patch
  (@0xA150D8) scales only spacing, NOT the quad. So spacing genuinely can't
  shrink glyphs. Untried lever: reduce the 0x2c fontsize feeding the text-heavy
  renderers — shrinks advance AND quad together = real smaller text; needs an
  in-game probe to confirm 0x2c drives the quad. Compact-font swap stays blocked
  at the atlas (fixed 32x32, won't decode — prior finding stands).

- **2026-07-08 (round 3: leaf-function red-zone crash, cave rules updated)** —
  Test v2 CRASHED on Library open. Cause: the standard cave template spills
  r12/f12 to r1−8/r1−16, which is only safe when the host has a stack frame.
  The two width engines are **leaf functions that keep live state in the red
  zone**: FUN_00a11f28 stores its saved r31 at −8(r1) for its entire body (and
  uses −0x20 as int→float scratch; FUN_00a12190 uses −0x10). The cave's
  `std r12,-8(r1)` overwrote the saved r31 → corrupted register in the caller
  on return → crash. **New cave rule: before spilling to the red zone, scan
  the host for negative-r1 offsets; in leaf hosts use provably-dead registers
  instead.** v3 caves are stack-free: r6 and f0 are dead at both fmadds sites
  (every loop path rewrites them before any read; volatile at the boundary),
  so K loads via r6/f0 and the cave is 7 instructions with no memory writes.
  Register-liveness proofs recorded in the tool docstring. Warning added to
  patch_eboot_menu_advance.py's SAFETY note.

- **2026-07-08 (round 2: Library = WTD window family, width engines found)** —
  Round-1 screenshots (Robot Library list, KEY WORD box) falsified both v1
  hypotheses and revealed the actual defect: **all window-family text renders
  full-width** — selected list rows show raw full-width spacing, unselected
  rows are the same overwide string uniformly squeezed into the column (the
  mush); keyword-box body text is equally gappy. Traced the family's advance:
  the walker's four pen updates (`fadds f10,f30,f1` @0x5CED40/0x5CEEDC/
  0x5CF818/0x5CF9D4) add the return of wrapper 0x5CDEBC → **FUN_00a11f28**
  (run-bounded) / 0x5CDEE8 → **FUN_00a12190** (NUL-terminated): shared
  string-WIDTH engines — f12 = fontsize/cell, then per char
  `fmadds f1,f12,f3,f1` with f3 = glyph width byte (sites 0xA120F4/0xA1234C;
  missing-glyph fallback adds a full cell @0xA12134/0xA12394, left alone).
  Only callers are the two window wrappers (verified by full bl scan), so
  K-scaling these two sites fixes measure+draw for the whole family without
  touching dialogue. Test EBOOT v2: exp3 = caves @0xC45CD0/0xC45D40 computing
  f1 += f12*f3*K; exp2 (dialogue term-field siblings 0xA13BE4/0xA16108)
  carried over; v1's exp1 fade neutralization dropped (no visible effect —
  FUN_006205e4 is not these screens; noted as dead end). Also mapped the six
  specialized `advance16×size/32` fmadds pen sites (0x5CB8C0, 0x5D0500,
  0x5D0F18, 0x5D1348, 0x5D1764, 0x5D1A88 — digit/counter draws via quad fn
  0x5D0618) as follow-up candidates if numbers still render wide.

- **2026-07-08 (open-issue RE round: unit-list + keyword-box, test EBOOT built)** —
  Full static pass over both open renderer issues, from the pristine ELF via
  release asset (§HANDOFF 4b). (1) The handoff's 8 candidate `fmuls` sites at
  0x5CBB7C–0x5CC5E4 are two twin `<R…>`/`<U…>` inline-tag handler functions
  (dispatch on tag byte 'R' 0x52 / 'U' 0x55, then '0'/'1'/'2'/'=') that scale
  coordinates by TOC const 3.125 (r2+0x20c8) — unrelated to glyph advance;
  candidates disproved. (2) Real unit-list mechanism found: list-text widget
  renderer FUN_006205e4 computes per-glyph draw scale f0 = f31 × edge-fade
  ramp; ramp interpolates 1.0→0.0 (TOC 0x2d1c/0x2d4c) over the window in
  widget halfwords +0x96/+0x98 (order picks fade-out vs fade-in); row scale
  f31 from thresholds +0x64/+0x68 (carousel). Tails of long EN names live deep
  in the fade window → scale→0 → "ExcellenceRescue mush". Glyph x-positions
  come from the already-patched 0x61F89C layout (all 3 advance paths K-scaled),
  so the ramp is the remaining suspect. (3) Keyword-box term-field: the two
  rich-text renderers each contain a second, differently-shaped field-width
  multiply (`fmuls f28,f13,f28` @0xA13BE4; `fmuls f27,f13,f27` @0xA16108;
  width = count[term+0x34] × f26 × base) feeding pen advance + underline quad —
  the likely KEYWORD-library path the old fingerprint missed. (4) Bonus: the
  FTTF font **loader** is FUN_005cce98 ('FTTF' magic check; allocates the
  r2+0x2100 font object; fills scale fields +0x14/+0x18/+0x1C/+0x20/+0x28 from
  TOC consts × header cell dims via the fdivs cluster @0x5CD2D0) — the "no
  static init path" claim in the font-width-wall note is wrong; a future
  global-width attack could patch these init ratios. (5) Built
  `tools/patch_eboot_test_unitlist_kwbox.py`: exp1 neutralizes the positional
  ramp in-place (4 words → `fmr f0,f31`, diagnostic); exp2 redirects the two
  field-width sites to K-rescale caves @0xC45C80/0xC45CA8. Verified: 6 word
  diffs + 2 caves only; disasm readback clean; K reads 0.6 (HANDOFF §4's 0.66
  was stale — deployed constant is 0.6 per the 2026-07-05 pullback).

- **2026-07-08 (dictionary fit: 7 SHORTENED entries resolved)** — Reproduced the
  fixer fit logic offline (no `work/` needed: `wrap_into` + the fallback chain
  against `dict_entries.json` caps) and confirmed exactly the 7 HANDOFF entries
  hit the drop-trailing-sentence fallback. Condensed all 7 in
  `build/dict_desc_en.json` so the FULL text now fits (0 SHORTENED / 0
  TRUNCATED). Notable: P_0x00EEB5 (Gaspard, 2 lines = 108 cells, tag costs 23.8)
  and P_0x00EF62 (the Joint Chiefs chairman) genuinely cannot hold every JP
  clause in English — condensed to keep the character-defining facts instead of
  losing whole trailing sentences. The "3 keyword entries end in ..." half of
  the issue did not reproduce from current sources (no ellipses anywhere in
  keyword/dict desc JSONs, zero OVERFLOW) — presumed already cleaned; verify
  in-game at next deploy. NOT yet deployed: needs `deploy.py build Logic` on
  the machine with `work/` + the game.

- **2026-07-05 (PS2 reference + atlas-shrink test)** — Studied the PS2 OGs English fan
  translation (SLPS_257.33 + packed BINs): it's a PS2-engine VWF hack, not portable to the
  PS3's different renderer. Tested the spinoff idea of shrinking the PS3 font.bin glyph
  BITMAPS (vs the width metric that failed before): **font.bin's atlas won't cleanly decode**
  — glyph entries are `[00][width][idx_hi][idx_lo]` (page = *(font+(cp>>8)*4+0x54); ASCII page
  base 0x580; atlas base = hdr+0x14 = 0x18180), but no index→offset mapping rendered a known
  letter recognizably (likely swizzled PS3 texture tiling). With the prior "font edits don't
  take on screen" finding, the atlas-shrink is not a viable lever. **Conclusion: "smaller
  glyphs" is a genuine engine wall** — engine font_size does nothing, the glyph quad is buried
  in vertex construction, and the atlas is undecodable. All reasonable levers explored.
  DIALOGUE IS FIXED regardless (tight spacing + reflow + trimmed the 1 over-long message).
- **2026-07-05 (spacing vs size)** — Dialogue advance patch (K=0.6 on the fadds paths) tightens
  SPACING and works; reflow (drop JP @ breaks, re-wrap continuously) fills the box. But "smaller
  GLYPHS" is separate: the dialogue advance is NOT f28-based (it's `f0=f27` or fixed `0x2c(r31)`
  font_size on a fadds path), so scaling the fdivs f28/f27 font_size did nothing. And the glyph
  on-screen SIZE is pre-computed as vertex quads in the layout fn, then just COPIED by the draw
  (FUN_00a11a58 = memcpy of x0/y0/x1/y1 + texcoords). So shrinking glyphs = scaling the 4 quad-
  corner computations in 0xa149e8 — deep/multi-site/risky. Current best: advance K=0.6 (tight
  spacing) + reflow + wrap 48 (fills dialogue box; the narrower Back Log still clips at the far
  edge — a review-only cosmetic). Genuine smaller-glyph shrink is the open lever.
- **2026-07-05 (dialogue renderer FOUND)** — At K=0.5 the story dialogue box finally
  tightened ⇒ it DOES route through the two candidate functions; the fix was patching ALL
  advance paths (9 sites) in both FUN_00a149e8 + FUN_00a123f0, not just one. Follow-ups:
  (a) K=0.5 over-tightens the **Spirit box** (smaller font → advance < glyph width → chars
  overlap) — it shares the K constant, so pulled K back to **0.6**; (b) dialogue clipping is
  now a **wrap-width** issue (lines still exceed the box), so rewrap width **28→20**. K and
  wrap are coupled (tighter font fits more chars). If the Spirit box still collapses at a K
  the dialogue needs, the next step is **separate K constants** per function (dialogue vs the
  Spirit/description renderer).
- **2026-07-05 (tutorial subsystem lead)** — Answering "why is the tutorial different": it
  uses a **float-advance** text renderer (reads each glyph's advance from a glyph-info struct
  `+0x30`, accumulates with `fadds f30`), like the dialogue box — so it's scalable. Found this
  is a **shared subsystem** (0x61Exxx: 9 functions, 132 calls to the glyph-measure fn 0xA201D0).
  The DRAW fn is **0x61F89C with THREE advance paths** (0x61F97C/0x61F9D4/0x61FA4C) — only ONE
  (0x61FA4C) had been patched, so glyphs taking the other two paths stayed full-width. Patched
  all 3. If the stat/Spirit/menu text routes through this subsystem via the other paths, it
  should now tighten. Awaiting in-game result.
- **2026-07-05 (font-width wall)** — Established that **all 7 text-renderer sites read the same
  shared font object** (global at `r2+0x2100`; loads at 0x5CD348, 0x5CDBE8, 0x5CFCC8, 0x5D0624,
  0xA11A64, 0xA123FC, 0xA149F0). Per-glyph widths come from that object (`lbz …,1(r30)`), so
  editing the object's widths *would* be the true global fix (would tighten integer-grid
  screens too). BUT: (1) editing the **font.bin** width table is a **confirmed dead end** (prior
  attempt: ASCII width 0x16→0x08, folder+GD, zero on-screen change → the load does not source
  widths from the editable file, or they're computed at load); (2) the object global is
  populated via init/relocation — **no direct `stw …,0x2100(r2)` store exists** to patch
  statically. So the global font-width fix is **blocked to static analysis**. Verified the
  deployed EBOOT still carries the dialogue fix (0xA150D8 branch, K=0.66) — it's active; the
  reason "spacing seems unchanged" is that only the dialogue box + tutorial renderers are
  patched while every other screen reads the (still-full-width) shared font object.
  **Remaining route = RPCS3 runtime debugger:** inspect the font object in memory during a
  render to find where its width bytes live (heap vs a table), then patch that source or the
  load code. High effort, requires live memory inspection.
- **2026-07-05** — Stat/Spirit letter-spacing: patched 0xA12B0C (the *real* glyph advance of
  FUN_00a123f0) → **no effect, reverted**. Both width-read-confirmed advance sites now ruled
  out for these screens ⇒ conclusion: they use **fixed integer-grid** layout, not float
  advance; static advance-scaling **exhausted** (see §5.4). Deployed instead:
  **label abbreviations** (Mel/Rng/Skl/Def/Eva/Hit, Unit/Pilot/Robot/Weapon tabs, Tgt/Eff) —
  confirmed in-game; and **Back Log rewrap 37→28** — confirmed better. Tutorial renderer
  (0x4a5e84/0x61f89c) tightened successfully.
- **2026-07-05** — EBOOT system UI: all 2,021 unique strings translated in-place (1,561
  offsets patched) with strict format-specifier + binary-false-positive gating. Archive
  cut-ins done. Boot-safe.
- **2026-07-05** — Scenario objectives: 770 unique scr (LOGO) strings translated, 8,794
  entries applied across 102 stages, 99% in-place.
- **2026-07-04/05** — Menu chrome (WTD): full 3,290-record translation after cracking two
  crashes (ASCII `<>` tags; length-driven traversal). `repack_override` built for fast 638 MB
  General2d rebuilds.
- **2026-07-04** — FixedData (FIXH): reached 100% via the 32-bit SOFS discovery + `splice_grow`.
- **2026-07-04** — Main dialogue letter-spacing fixed via EBOOT code cave (K=0.66).
- **(earlier)** — Extraction pipeline, worksheet/reinsert tooling, glossary, Phase-1 (Common)
  and Phase-3 (Battle) translations, deploy automation.

*Append new findings here as they land.*
