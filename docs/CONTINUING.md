# Continuing the work — recipes

Prereq: read `docs/HANDOFF.md` (the invariants) and skim `PROCESS.md`.

## Fix a single line of text

1. Find it: `grep -rl "the exact english" build/worksheets/` (or search the JP).
2. Edit that worksheet entry's `"en"`. Constraints by container:
   - `Battle/`, `Common/`, `General2d/`, `EBOOT/`: UTF-8 bytes must be ≤ the JP
     bytes (`len(en.encode()) <= len(jp.encode())`) or the line stays Japanese.
   - `Logic/` talk + FixedData: can grow freely.
   - Dialogue `@` breaks are re-flowed automatically at 48 cols; don't hand-wrap.
3. Redeploy that container (`python tools/deploy.py build <Archive>`;
   General2d and EBOOT have their own paths — see docs/INSTALL.md §5).

## Fix keyword / robot-guide / character-guide text

Edit `build/keyword_desc_en.json` or `build/dict_desc_en.json` (key = entry's
first-segment offset), then `python tools/deploy.py build Logic`. The fixers
wrap and write offset-preserving; watch their output for OVERFLOW/TRUNCATED.

## Rename something everywhere

1. Update `build/canon_names.json` (and the glossary if it's a character).
2. Sweep: for every worksheet entry whose `jp` contains the JP name, word-bound
   replace old EN → new EN, **slot-checking in-place containers** (pattern used
   throughout: see PROCESS.md §name-audit). Also check `keyword_desc_en.json`,
   `dict_desc_en.json`, and `<tags>` (link keys must match keyword entry names).
3. Redeploy affected containers.

## Run the QA audit after bulk changes

The audit checks, in order of value:
1. slot overflow on in-place containers (lines that would silently stay JP),
2. typographic punctuation / exotic characters (curly quotes, macrons,
   Cyrillic lookalikes — agents produce these),
3. `<..>` tag count mismatches jp vs en, lost `@`/`§`/`#0` tokens,
4. engine-key regressions (`^\[[^\]]{1,8}\]-` entries must have `en:""`),
5. JP-name → canonical-EN mismatches (fuzzy variant extraction, JP-gated).

## Translate new/remaining text with agents (the proven pattern)

1. Split the source into JSON batches: `{key: {jp, max_chars}}` (~6-8 entries).
2. One agent per batch; prompt includes: glossary/namemap file to Read, ASCII
   punctuation rule, hard `max_chars` (agents overshoot ~20% of the time),
   "no raw newlines inside JSON strings", write results to `out/<batch>.json`,
   reply only a count.
3. **Verify loop**: after merge, re-check every entry against the REAL
   constraint (byte slot or box-wrap), re-batch failures with tighter budgets,
   repeat (typically converges in 2-3 rounds: 102→32→9).
4. Salvage malformed agent JSON with `json.loads(text, strict=False)`.
5. Normalize typographic punctuation on merge — always.

Sonnet-class models are fine for trims/condensing; use a stronger model for
fresh contextual translation of story dialogue.

## Attack the open EBOOT issues

Workflow that has worked five times: find the advance/width multiply
(`fmuls` against the scale register — scan patterns are in PROCESS.md and
`tools/patch_eboot_menu_advance.py`), redirect it to a red-zone-safe cave that
rescales by K (template in `tools/build_eboot.py::patch_term_fields` of the
git history, or the menu tool), deploy as a TEST EBOOT with a timestamped
rollback, have a human eyeball the screen it affects. When verified, fold the
byte-diff into `build/eboot_code_patch.json`:

```sh
# after building a verified new elf (build/EBOOT.new.elf):
python - <<'PY'
# regenerate the code patch = diff(orig, new) minus worksheet string slots
# (script in PROCESS.md §eboot-code-patch; ~20 lines)
PY
python tools/build_eboot.py   # must reproduce your verified elf byte-exactly
```

NEVER clamp the menu renderer's f0 normalizer (garbles all UI text — tested).
NEVER scale glyph-size f31 (text vanishes — tested). Advance and field-width
scaling are the safe levers.

## Deploy + test etiquette

- Always let deploy.py make its rollback; note the timestamp in your notes.
- The human tester drives RPCS3; you cannot. Batch changes to minimize boots.
- After EBOOT changes, RPCS3 recompiles PPU on the new hash automatically.
