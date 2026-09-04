# Library (dictionary) width-fitting spec — answers for the remote

Three findings reshaped this workstream. Here are the verified answers, the corrected
scope, and the work files.

---

## Answer 0 (correction): the library is NOT 0% translated — it's 100% translated

The 2,574 all-`en=""` segments you saw are the **intentionally-blank SEGMENT worksheets**
(`build/worksheets/Logic/Dat/FixedData/{Unit,Pilot}DictionaryData.dat.json`,
`KeyWordData.dat.json`). Those are **not** the translation source and never were.

The real English lives at the **entry level** and is complete:
- `build/dict_desc_en.json` — **363/363** unit + pilot descriptions (100%)
- `build/keyword_desc_en.json` — **64/64** keyword descriptions (100%)

At deploy, `tools/fix_dictionaries.py` (unit/pilot) and `tools/fix_keyworddata.py`
(keywords) wrap that entry-level English into the fixed segment rows — they are the
*only* writers of those `.dat` files; the blank worksheets are correct and must stay blank.

**So this is not "translate from scratch." It is "width-fit the existing translation."**
That changes the size of the job by an order of magnitude (see Answer 3).

---

## Answer 1 (point 2): the crush is display-WIDTH, and width ≠ byte slot

Confirmed, with numbers:
- **Box width** ≈ 27 full-width JP chars ≈ **~54 half-width cells** (1 ASCII char = 1 cell).
- **Per-segment byte cap** ≈ **82–84 bytes median, up to 92** (measured across all segments).
- The byte slot is therefore **~30 bytes looser** than the display budget. A byte-only check
  says "83 bytes, fits!" while a 70-char ASCII line overflows the box and the engine
  **condenses (crushes) it**.
- The engine condense triggers when a rendered line's width **meets or exceeds** the box.
  `fix_dictionaries.py` currently wraps at `WRAP = 54` **cells** → lines up to 54 → sitting
  *at* the box width → condense fires. This is exactly why byte-slot discipline never
  protected the library.

**Rule for all library text:** wrap each English line to **~50 ASCII chars** (margin below
the ~54-cell box), NOT to the byte cap. The byte cap is only a secondary ceiling — never
fill it with ASCII. Target **50**; hard ceiling **52**; 48 is the safe floor.

---

## Answer 2 (point 3): line count per entry is fixed and not growable

Confirmed. Each entry has a fixed number of segment rows:
- Unit: 1–25 segments/entry; Pilot: 1–12; KeyWord: varies.
Dict segments are **position-addressed** (the library UI reads description lines *by
position*) and are **not** SOFS-referenced, so they are **not growable/repointable** the way
dialogue is (`fixh_grow` only repoints SOFS-referenced strings; see `docs/RE-INSTRUMENT-PLAN.md`
and `tools/fixh_grow.py`). English must satisfy **both** constraints at once:
per-line width (~50) **and** the entry's fixed line count. When a width-wrapped translation
would spill an extra line, the prose must be **tightened**, not allowed to overflow.

---

## The actual workstream (much smaller than "from scratch")

Re-wrapping the *existing* English at width 50 and checking it against each entry's fixed
line count:

| target width | entries that already fit fixed lines | need a 1-line tightening | worst overflow |
|---|---|---|---|
| 48 | 353 / 363 | 10 | +1 line |
| **50** | **360 / 363** | **3** | +1 line |
| 52 | 362 / 363 | 1 | +1 line |

So at width 50 the job is:
1. **Mechanical (one line of code):** set `WRAP = 50` in `tools/fix_dictionaries.py` (and mirror
   the same target in `tools/fix_keyworddata.py`). This re-wraps ~99% of entries clean, no
   translation work.
2. **Prose tightening (small):** the **3 unit/pilot entries** (+ any keyword spillers) that
   still need one line trimmed. Tighten wording so the *same meaning* fits `lines × ~50`.
   These are flagged in the work file below.
3. Optionally, a **quality pass** on the existing English while you're in each entry (the
   `jp` source is included) — but the width-fit is the required part; quality is a bonus.

Do **not** re-translate the whole library. The English is done; it just needs to fit.

---

## Work files (in the repo)

`build/workflows/library/library_worklist.json` — **427 entries**, one object each:

```json
"U_0x00291E": {
  "type": "unit",                 // unit | pilot | keyword
  "jp": "…full Japanese source…", // for reference / quality check
  "lines": 15,                    // FIXED segment count — must NOT be exceeded
  "width_chars": 50,              // per-line target (ASCII)
  "total_char_budget": 750,       // lines * width_chars (rough ceiling)
  "per_line_bytes": [84, 84, …],  // secondary byte ceiling per line (do not target)
  "current_en": "A thorough rebuild of Alt Eisen…",  // existing translation — tighten this
  "width_fitted_en": ""           // <- fill ONLY for entries that spill at width 50
}
```

Keyword entries additionally carry `term_jp` / `term_en` (the headword).

**How to fill it:** for each entry whose `current_en`, wrapped at 50 chars/line, exceeds
`lines`, write a tightened version into `width_fitted_en` that fits `lines × ~50`. Leave
`width_fitted_en` empty when `current_en` already fits (the WRAP change handles those).

---

## Deploy path (how the fitted text lands)

- The entry-level English is `build/dict_desc_en.json` / `build/keyword_desc_en.json`.
  For a tightened entry, put the new text there (that is what the fixers read).
- Change `WRAP` to 50 in `fix_dictionaries.py` (+ the keyword fixer target).
- `python tools/deploy.py build Logic` re-wraps and rebuilds the `.dat` files
  offset-preserving; GD is wiped so RPCS3 reinstalls. Verify in-game that long lines no
  longer condense and nothing truncates.

**Guardrails:** offset-preserving only — never grow/repoint dict segments (crashes the
library, see `docs`/memory on library control bytes). Preserve each entry's leading
control-byte prefix. Keep half-width ASCII punctuation. Don't touch the blank segment
worksheets.
