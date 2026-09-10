# Session handoff — full project state

Read this top-to-bottom before touching anything. It encodes every landmine we
hit. `PROCESS.md` has the deep technical background for each item.

## 1. Architecture in one paragraph

The translation lives in `build/worksheets/**` (JSON: `{offset: {jp, en}}` per
game file), applied by `tools/deploy.py build <Archive>` which resets each file
from the pristine JP extract (`work/`), applies the worksheet, repacks the
PSARC, re-encrypts the SDAT, deploys to the game folder, and wipes the GD
install. Three files are **NOT** worksheet-driven (see §3). The executable is
built separately by `tools/build_eboot.py` (byte-exact from a code-patch file +
the EBOOT worksheet).

## 2. Text rules (violating these = crashes or broken scenes)

1. **Engine keys**: any `[...]-` bracketed string in `ls*.bin` (talk) or
   `scr*.bin` — scene labels like `[２]-000` (fullwidth digits!) and roster
   tags like `[ＤＭ]-アイビス` — is an internal identifier matched **byte-for-byte**
   between scr and talk. Translating/normalizing them silently skips every
   story interlude and kills stage BGM (it took a full day to find this).
   They are locked to `en:""` with a note in the worksheets. NEVER touch them.
2. **ASCII punctuation only** in dialogue/battle text: `' " - ...` — never
   curly quotes, em-dash, ellipsis glyph, macrons, or non-Latin letters
   (the font renders them wrong or full-width).
3. **WTD menu text** (`windowdataMain.wtd`): keep fullwidth `＜＞【】` — ASCII
   `<` `>` are parsed as control tags and **crash the Library**. Keep `<I=61>`
   style tags verbatim. Offset-preserving edits only (the tool enforces it).
4. **In-place containers** (Battle, Common, General2d, EBOOT): English must fit
   the original JP byte slot or the line silently stays Japanese in-game.
   Growable: Logic talk (LDBI regrow) and FixedData (splice_grow).
5. **`#0` `#1` tokens** are number substitutions; `@` is a dialogue line break
   (re-flowed at apply time); `/` is the battle-quote line break; `§` is a
   special glyph. Preserve all of them.
6. **Names**: `build/canon_names.json` (686 entries, wiki-validated) is law.
   Same JP name = same EN spelling everywhere, and mecha names must match the
   in-game unit list (UnitData.dat).

## 3. The three fixer-owned files (position-addressed UIs)

`KeyWordData.dat`, `UnitDictionaryData.dat`, `PilotDictionaryData.dat` render
description **lines by position** — any byte-shift scrambles their boxes. Their
worksheets are intentionally blank; the ONLY writers are:

- `tools/fix_keyworddata.py` — sources: `build/keyword_entries.json` (layout) +
  `build/keyword_desc_en.json` (text). Keyword box ≈ 46 half-width cells; 12
  over-slot names are abbreviated in place (append+repoint broke the title
  renderer).
- `tools/fix_dictionaries.py` — sources: `build/dict_entries.json` +
  `build/dict_desc_en.json`. Box ≈ 56 cells (WRAP=54). Fit fallbacks: wrap →
  drop trailing sentences → truncate (only NO TRANSLATION is a build error).

**Inline `<term>` links (2026-07-08): rendered as PLAIN text by default.**
Inline term glyphs draw full-width in these boxes, so a line with a link
overflows its fixed slot and the link + trailing text CLIP (the "malformed
paragraphs" / "wrong glossary links" reports). Both fixers now strip `< >`
before wrapping (`strip_terms`, gated by `OG2_PLAINTEXT_TERMS`, DEFAULT ON)
so paragraphs render complete. Set `OG2_PLAINTEXT_TERMS=0` to restore
brackets — only once the window-family term-advance EBOOT patch is verified.
Source JSONs keep their brackets; this is an emit-time transform only.

Both run automatically inside `deploy.py build Logic`. **To edit dictionary or
keyword text, edit the `*_desc_en.json` files, not the .dat worksheets.**
`<term>` spans in these texts are underline/link tags and cost ~1.7× their
length in display cells (see §4) — the wrappers account for this.

## 4. EBOOT state (current deployed build)

Reproduce byte-exactly with `python tools/build_eboot.py`. It applies
`build/eboot_code_patch.json` (920 bytes, 23 regions) over the pristine ELF:

- **Dialogue advance ×14 sites**, K @0xC45950 (currently **0.6** — §4 of older
  notes says 0.66; 0.6 is what's deployed), caves @0xC45960+ —
  half-width Latin letter spacing in dialogue.
- **Menu/status advance ×5 sites**, caves @0xC45B68+ — same for menu renderers.
- **Term-field width ×2 sites** (0xA13A84, 0xA16EFC), caves @0xC45C30/58 — the
  `<term>` underline field is sized `char_count × cell width` separately from
  glyph advance; unpatched it renders ~1.67× wider than the text.
- Plus 1,564 translated system strings (worksheet, JP-validated offsets — the
  keys are ambiguous VA/file offsets, so every write verifies the JP bytes first).

Free cave space continues at ~0xC45C80 (zero-run to ~0xC45D2B, more at
0xC45D40). K constant for new caves: `lfs` from 0xC45950.
**Cave safety rule (learned via Library crash 2026-07-08): the r1−8/r1−16
red-zone spill template is ONLY safe in hosts with a real stack frame. Leaf
functions may keep live data below r1 (0xA11F28 keeps saved r31 at −8(r1)).
Scan the host for negative-r1 offsets first; in leaf hosts use provably-dead
registers instead of spilling.**

## 4b. Working on the EBOOT without the game (remote agents)

The pristine decrypted ELF is available as a private release asset (NOT in the
git tree - keep it that way):

```sh
gh release download eboot-ref -p "EBOOT.elf.orig" -D _rollback/
# md5 must be 2a08c6ca204e229bfd67ee2bd10224fb
python tools/build_eboot.py   # reproduces the deployed EBOOT byte-exactly
```

`pip install capstone` for disassembly. You can analyze, patch, and rebuild the
executable entirely from this - but you CANNOT test it: every candidate patch
must go back through the local machine (push an updated
`build/eboot_code_patch.json` or a standalone patch script + notes on exactly
which screen to check) for an in-game verification round.

## 5. Open issues

### Renderer-level verdicts (2026-07-09) — read these first

The two remaining renderer items (terrain grade gap, library term-link
underlines) were traced as far as static analysis can go. Verdicts:

- **TERRAIN grade gap — DEBUGGER-TERRITORY, static trace exhausted.** The grade
  letters live in a rank-indexed table (0xC498F8 '－' .. 0xC49920 'Ｓ') reached
  only through the descriptor tree: subdesc 0xCF1768 → registry entry 0xD8D360
  (pointed from 0xD54C4C/0xD59D48/… all in the 0xD5xxxx **data** region). I
  confirmed NONE of 0xD8D360 / 0xD5515C / 0xCF176C / 0xCF191C is built by a
  `lis`/`ori` (or `lis`/`addi`) pair anywhere in the code segment — the whole
  tree is walked with runtime-register-relative pointers, so the grade-draw
  x-offset constant is not statically locatable. The leading-space trick is dead
  (outcome 3: the shifted letter overstrikes the fixed-x +/- modifier, proving
  letter and modifier are *both* anchored to the element at fixed offsets, so
  moving the WTD label moves both and does not open the gap either).
  **RPCS3-runtime route is BLOCKED (verified in-emulator 2026-07-09).** Drove
  RPCS3 0.0.41's debugger directly: main_thread selected, live disasm/regs. Its
  "Add a breakpoint" dialog has a type dropdown with a SINGLE option —
  **"Execution"** — and the disassembly right-click has no memory-breakpoint
  entry. RPCS3 has NO data read/write watchpoint, so the "read-watchpoint on
  0xCF178C" plan cannot be run here. Cheat Engine (installed) can watch host
  memory but RPCS3 JITs PPC→x86, so it catches the recompiled x86, not the guest
  PPC instruction we'd patch — no clean mapping. Execution BPs need the render
  function's address, which is the unknown we're chasing (circular).
  **Verdict: terrain grade-gap is PARKED** — cosmetic (one stat sub-column),
  static route exhausted, runtime route unavailable in this toolchain. Reopen
  only if a decapping/emulator-with-data-watchpoints becomes available, or via a
  full static trace of the descriptor-tree walker from its known callers.

- **LIBRARY term-link renderer — SEPARATE routine; needs runtime ground truth.**
  In-game (2026-07-09) the owner confirmed the model: linked terms go through a
  DIFFERENT renderer than plain glyphs. It ignores the Kf=0.9 fontsize/spacing
  patch (draws term text full-width) AND reserves an underline field ~1.67× the
  text width, so any line with a link goes wide+gappy and shoves the layout
  (the Altairlion big/small alternation). These are ONE bug — an over-wide term
  field — not two. Ruled OUT this round:
    * Brackets-on at Kf=0.9 alone: the link path never sees that patch (owner
      confirmed) → does NOT fix it. The earlier "cheap gate" is void.
    * Data-side fix: term markup is bare `<Full Name>` (engine name-matches the
      keyword table, auto-measures the underline). No width argument exists → no
      data lever.
    * exp2 (`patch_eboot_test_unitlist_kwbox.py`, sites 0xA13BE4/0xA16108): those
      are the DIALOGUE term-field renderers (FUN_00a123f0/a149e8), not the window
      family — wrong target, and its `cave_mul_scale` still uses the red-zone
      spill that crashed the Library. DO NOT fire it for this.
    * exp3 (0xA120F4/0xA1234C): window-family PLAIN-text advance, already handled
      by fontsize → folding double-scales plain text. Not the term lever.
  Where the term field IS sized: the tag sub-renderer in FUN_005cb970 — dispatcher
  0x5CB3B4 + body parser 0x5CB2E8 (parse `<INK=>`/`<I=>`/`<=NNN>`, store to widget
  +0x8/+0x28), then the R/U-tag box-size switch does
  `lfs [widget+0x80/0x84]; fmuls ×const@0x20c8(r2); stfs -> frame` at blocks
  0x5CBB74 / 0x5CBCF0 / 0x5CBDFC / 0x5CBF78 / 0x5CC1E0 / 0x5CC35C / 0x5CC468 /
  0x5CC5E4. The clean fix is a per-block K-cave on the ONE block that sizes the
  term underline (leaving the shared const alone).
  **UPDATE 2026-07-10 — the `<U=>` handler is pinned; a screenshot-test is ready.**
  The 19-entry tag jump table (dispatch @0x5D25xx) was fully enumerated; handler
  0x5CC068 is the `<U...>` case (checks byte1==0x55 'U'). Its `<U=>` body @0x5CC120
  builds the underline QUAD: `lfs f27,0x80(r31); lfs f31,0x20c8(r2);
  fmuls f8,f27,f31 @0x5CC1E0 -> stfs f8,0x80(r1); ... bl 0x6ba45c(draw)`. So the
  underline field = [widget+0x80]*const, and 1.67≈1/0.6 = the field is measured
  full-width while the text now advances half-width. Host 0x5CC068 HAS a real
  frame (stdu -0x150) → the red-zone cave is safe here (not a leaf).
  `tools/patch_eboot_test_uline.py` scales that one multiply by K(0.6). **Test it
  (owner, screenshot workflow — NO debugger needed):**
  ```sh
  OG2_PLAINTEXT_TERMS=0 python tools/deploy.py build Logic   # brackets ON (links exist)
  python tools/build_eboot.py && python tools/patch_eboot_test_uline.py
  # deploy the Logic archive + copy build/EBOOT.test.BIN over the game's EBOOT.BIN
  # open KEY WORD box on a linked entry (DC / EOT keyword bodies)
  ```
  Outcomes (full list in the script's DIAGNOSTIC block): underline hugs text →
  FOUND IT, fold @0x5CC1E0 permanent + flip OG2_PLAINTEXT_TERMS=0 = full fix;
  unchanged → the bare `<Name>` link uses a different jump-table case (re-probe
  0x5CABD8 / 0x5CC8FC / 0x5D1908 / …); underline thinner not shorter → +0x80 is
  thickness, switch site to 0x5CC1E8 (+0x84). Until confirmed, plaintext
  (default ON) ships — paragraphs read complete, no links, odd full-line selector
  bar (cosmetic; the □:Term cursor has no anchors when links are stripped).
  **RESULT 2026-07-10 = OUTCOME 2 (unchanged).** In-game brackets-on + uline-test
  (KEY WORD Tesla Leicht / DC War / EOT Special Council): underlines still overrun
  ~1.6× (text ends, underline runs on ~another term-width); scaling 0x5CC1E0 had
  no visible effect → keyword `<Name>` links do NOT route through the `<U=>`
  handler. Cave was safe (framed host, no crash). Next: re-probe 0x5CABD8 /
  0x5CC8FC / 0x5D1908 / the remaining jump-table handlers for the one that draws
  THIS underline. **NB the continuous-flow wrap fix means brackets-on now renders
  the KEYWORD box as clean paragraphs + working links — only the long underline
  is left there.** (Robot-Library/dict entries' full-width term-TEXT big-font is
  still unverified in brackets-on; get a dict screenshot before shipping
  brackets-on.) Deployed state after the test was reverted to plaintext default.

- **DIALOGUE `<term>`-link slippage — ROOT-CAUSED, test patch ready (2026-07-10).**
  Story dialogue links (`<Inspector Incident>`, `<L5 Campaign>`, ...) render
  full-width and shove following text off the box edge (owner screenshot). This is
  a SEPARATE renderer from the library (FUN_00a123f0 / FUN_00a149e8, the 0xA1xxxx
  dialogue family). Trace: the pen advances by the term-FIELD width, not the
  term-TEXT width — `fmuls f28,f13,f28 @0xA13BE4 -> fadds f30,f30,f28 @0xA13BF0`
  and `fmuls f27,f13,f27 @0xA16108 -> fadds f30,f30,f27 @0xA16114` (f30 = pen X,
  f13 = cell*charcount). The already-deployed term patches (0xA13A84/0xA16EFC)
  scale the underline DRAW (stores to r17), NOT this advance — hence slippage
  persisted. `tools/patch_eboot_test_dlgterm.py` scales both advance sites by the
  dialogue K (0.6) via red-zone caves (hosts are framed: positive r1 offsets).
  Test brackets-ON (`OG2_PLAINTEXT_TERMS=0`) on ls021. If tight -> fold
  0xA13BE4/0xA16108 permanent + flag 0 = links restored, no slippage. 293 dialogue
  lines (R6) are the affected set. The library `<U=>` fix
  (patch_eboot_test_uline.py) is the separate window-family half.
  **RESULT 2026-07-10 = FAILED (terms still slip).** In-game brackets-on +
  dlgterm test (Elis "The `<Elemental Lord>` Granveil...", Yang Long "a
  `<Elemental>` like that"): terms STILL draw with big out-of-flow gaps —
  scaling the two advance sites by 0.6 did NOT tighten them. So the
  advance-scale hypothesis is DISPROVEN: 0xA13BE4/0xA16108 are not the (whole)
  slippage mechanism. No crash (framed hosts confirmed). Reverted to
  `OG2_PLAINTEXT_TERMS_DLG=1` (clean dialogue) + permanent EBOOT.
  **Post-revert observation (Kyosuke "La Gias...?" screenshot): dialogue
  AUTO-LINKS keyword names even in plaintext** (same engine behavior found in
  the library 2026-07-09). Plaintext dialogue renders READABLE: one oversized
  underline field + gap per term, text flows on correctly (vs brackets =
  shattered layout). So plaintext is a good interim, links still work, and the
  eventual term-field width fix benefits dialogue with no flag flip. Next: the pen
  must jump somewhere else too (a tab-stop / fixed-x placement, or a second
  advance contribution before the `fadds f30`). Re-trace the term-emit path in
  FUN_00a123f0 from the `<...>` tag branch to the next glyph draw.
- **STAGE-START title cut-in shows JP (2026-07-10) — not a reachable text bug.**
  StageData titles are 100% translated + deployed (0 residual CJK; menus/scenario
  select show English). But the animated stage-start title card still renders JP.
  Checked every text source: scr carries NO title string, ScenarioChart.csb has
  no text, and NO per-stage title texture exists in any psarc manifest (Battle/
  Common/General2d/3d/Logic scanned). So the cut-in is a BAKED TEXTURE (image
  lane — extract/re-render/repack, defer to human-review release) or reads a
  source not yet decoded (possibly embedded in a General3d Map file). Need a
  screenshot of the cut-in to disambiguate: clean UI font = hidden text source
  to grep; brush/stylized calligraphy = texture.

### Older issue log

1+2. **Library letter-spacing (unit-list mush + keyword box)** — TEST EBOOT v2
   ready (2026-07-08 round 2), awaiting in-game check. Round-1 screenshots
   showed the real defect: ALL WTD-window text (Robot Library list, KEY WORD
   box) renders FULL-WIDTH — the window family was never K-patched. The
   selected list row is plain full-width; unselected rows are that overwide
   string uniformly squeezed into the column = the "ExcellenceRescue" mush.
   Fix in v2 (`tools/patch_eboot_test_unitlist_kwbox.py` exp3): the family's
   two string-width engines FUN_00a11f28 / FUN_00a12190 (only callers: the
   window wrappers 0x5CDED0/0x5CDEF8) accumulate width via
   `fmadds f1,f12,f3,f1` @0xA120F4/0xA1234C; both redirected to caves
   (@0xC45CD0/0xC45D40) computing f1 += f12*f3*K. Covers measure AND draw
   coherently. If underlines in the keyword box still run ~1.67× after this,
   the remaining site is the window-family underline-field width (likely fed
   by the `<R=>`/`<U=>` tag handlers' [widget+0x80/0x84] values).
   Dead ends so far (do NOT revisit): the 8 fmuls at 0x5CBB7C–0x5CC5E4 are
   R/U tag handlers (coord×3.125, not advance); the FUN_006205e4 edge-fade
   ramp neutralization (v1 exp1) produced no visible change on these screens.
   Also in v2 (exp2, unchanged from v1): dialogue term-field sibling sites
   0xA13BE4/0xA16108 → K caves @0xC45C80/0xC45CA8 — verify story-dialogue
   term underlines show no regression.
3. ~~7 dictionary entries clean-drop a trailing clause~~ **Fixed in source
   2026-07-08**: the 7 entries (U_0x0171A6 + 6 pilots) were condensed in
   `build/dict_desc_en.json` to fully fit their line budgets (verified against
   the real `wrap_into` offline). **Needs `deploy.py build Logic` + in-game
   spot check on the box that has `work/`.** The "3 tiny keyword entries end
   in '...'" half did NOT reproduce from current sources (no ellipses in
   either desc JSON, zero keyword OVERFLOW) — either already cleaned before
   the snapshot or an in-game observation; re-check the KEYWORD library after
   the next deploy.
4. **Human review** of the whole translation before any release (owner's
   explicit decision: no release until a human translator has verified it).

## 6. QA / verification tooling

- Mechanical audit (punct, tag balance, slot overflow, engine keys, residual
  JP, exotic chars): the scan logic is in `build/audit_tier1.json`'s generator —
  see PROCESS.md §QA; re-run after any bulk edit.
- Name audit: scan all worksheets for JP-name→EN mismatches vs
  `build/canon_names.json` (JP-gated variant replacement; see docs/CONTINUING.md).
- Every fixer has hard gates (offset preservation, NUL positions, readback).

## 7. Rollbacks & recovery

- `build/rollbacks/<Archive>/<timestamp>.sdat` — every deploy backs up first.
- `python tools/deploy.py rollback <Archive>` restores the latest.
- EBOOT backups in `build/rollbacks/EBOOT/`; pristine in `_rollback/`.
- The GD install (`dev_hdd0/game/BLJS10133`) is disposable — wipe it any time;
  the folder deploy is the source of truth.

## 8. Provenance & rights

- Translation: produced directly from the game's Japanese by LLM agents
  (Claude Opus/Fable/Sonnet), name canon validated against the akurasu wiki and
  the official character list. The 2ndsrwoge.com fan translation was
  deliberately NOT used (copyright; derivative-work concerns).
- `decrypt_sdat.py` derives from make_npdata (Hykem, GPLv3).
- No game assets in this repo. Do not add any (ISO, psarc, EBOOT, extracted
  files) — the .gitignore enforces this; keep it that way.
