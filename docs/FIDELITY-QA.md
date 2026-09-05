# Fidelity / QA re-read — remote pickup guide

A full JP-vs-EN fidelity re-read of the entire translation is **in progress**.
This doc is the handoff for a remote agent session to continue it. Everything
needed is in the repo; no game files are required (this pass is text-only).

## State (as of 2026-07-11)

- **225 / 518 units done** (~26k of ~111k rows) — all story-tier so far, through ~`ls072`.
- **1,142 findings** on disk. **REPORT-ONLY: do not edit worksheets, do not "fix" anything.**
  The owner reviews the merged report and approves an apply batch separately.
- Local runs keep hitting the local session token cap; the remote's larger window
  is why this is being handed off.

## Layout

```
build/audit/fidelity/_items.json   manifest: [{name, kind, in, out, n}] (repo-relative)
build/audit/fidelity/in/<name>.json    unit input:  {"kind","note","must":{key:reason},"rows":{key:{jp,en,slot}}}
build/audit/fidelity/out/<name>.json   unit result: {"source","reviewed","findings":[...]}  <- EXISTS = unit done
tools/fidelity_merge.py                merges out/* -> build/audit/FIDELITY-REPORT.md + fidelity_findings.json
build/canon_names.json                 name canon (check E5 against this)
```

**A unit is DONE iff its `out/<name>.json` exists.** To find remaining work:
every `name` in `_items.json` without a file in `out/`. Process units in
manifest order (story units are in scene order). Any number of units can run
in parallel; they are fully independent.

## Per-unit reviewer protocol

For each remaining unit, review every row and write `out/<name>.json`.
Model guidance: Sonnet at high effort (or equivalent); one unit per agent/context.

SKIP a row when: `en` is empty/whitespace (unless its key is in `must`), OR
`jp` starts with `[` and contains `]-` (engine key — must stay Japanese).

Flag ONLY these classes (anything else is out of scope):

- **E1 residual-japanese** — `en` contains hiragana/katakana/kanji (the 「 」
  wrappers, and fullwidth ＜＞【】 in `wtd` units, do NOT count).
- **E2 romaji-leak** — a Japanese common noun left romanized instead of
  translated (project exemplar: "musha Guarlion" → "samurai Guarlion").
  Canon proper names (Masaki, Cybuster, Masou Kishin...) are NOT leaks.
- **E3 meaning-error** — `en` states something `jp` does not: wrong
  subject/object, dropped/inverted negation, wrong number, wrong
  question-vs-statement, invented content, key point missing.
- **E4 broken-text** — typo, native-catchable grammar error, doubled word,
  truncated sentence, unbalanced 「」/quotes/parens, mangled control tokens.
- **E5 canon-violation** — name spelled differently than `build/canon_names.json`.
- **A1 translationese** — JP structure carried into English ("As for X...",
  literal idioms like "it can't be helped", "that person" for 彼, untranslated
  interjections like "Kuh!"/"Muu...", stiff textbook phrasing from casual speakers).
- **A2 register-mismatch** — line contradicts speaker voice / unit register.
- **P1 polish** — clearly better wording for a correct line. HARD CAP 5/unit.

Budget per unit: every E* found; at most the 15 worst A1/A2; at most 5 P1.
DO NOT flag: natural lines, meaning-preserving liberties, slot-fitting
abbreviations, control tokens themselves.

**must-list:** every key in the unit's `must` REQUIRES a finding whose
`proposed` satisfies the stated reason (fits byte budget / reflows to <=3
lines / supplies a translation). Severity `error`.

**Proposed rewrites** must: use ASCII punctuation only (`' " - ...`, never
typographic); keep leading 「 / trailing 」 if present; preserve control tokens
(`<C=..></C>`, `<W=..>`, `@` line breaks, `；@` option separators, `#0/#1`,
`§`) unless the finding is about them; for `story` units keep plain text
(@ removed) <= 144 chars (reflows to <=3 lines), for all other kinds keep
UTF-8 bytes <= the row's `slot`.

**Output** (`out/<name>.json`, UTF-8, no BOM):

```json
{"source":"<name>","reviewed":N,
 "findings":[{"key","check":"E1|E2|E3|E4|E5|A1|A2|P1",
              "severity":"error|awkward|polish","jp","en","issue","proposed"}]}
```

`severity`: E\*=error, A\*=awkward, P1=polish. Copy jp/en verbatim (truncate jp
at 120 chars). Empty `findings` is a valid result.

Unit-kind registers: `story` = natural anime-localization dialogue (scene
order — check continuity); `battle` = short punchy barks; `scr` = concise
mission/UI; `fixed`/`eboot`/`common` = concise UI; `wtd` = menu chrome (never
touch fullwidth brackets); `roll` = literary narration; `library` = encyclopedia
prose, English-quality-only (jp field only names the topic — run E4/E5/A1).

## After each batch

```
python tools/fidelity_merge.py
```

regenerates `build/audit/FIDELITY-REPORT.md` + `fidelity_findings.json` from
whatever is done. Commit `build/audit/fidelity/out/` + the two merged files +
push. Do NOT commit changes to `build/worksheets/` from this pass (report-only).

## When all 518 are done

Ping the owner. The apply phase (separate, owner-approved) consumes
`fidelity_findings.json`: errors first, then awkward, polish last — with the
audit gate (`python tools/audit.py --gate`) run after application.
