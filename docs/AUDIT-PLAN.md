# Audit plan — codify every lesson as a permanent gate

The honest headline from this project's history: **almost every bug found
in-game was a class we could have linted for, once we knew the rule.** So the
audit is not a one-off sweep — it is `tools/audit.py`, a permanent, re-runnable
QA suite that encodes every lesson as a rule, runs in zero model tokens, and
doubles as the repo's regression gate (local, deploy, and remote-agent).

## Tier 0 — `tools/audit.py` (deterministic, zero tokens)

Self-contained (no `reinsert_utf8` import — that needs py3.12; audit runs on
3.11 too). It re-derives `emit_en` exactly as `worksheet.apply` does
(`normalize().strip()`, plus `rewrap()` for LDBI dialogue) and measures UTF-8
bytes against each entry's stored `slot`. Rule → lesson:

| ID | Rule | Sev | Lesson it comes from |
|----|------|-----|----------------------|
| R0  | Normalizer non-drift: audit's `normalize` map == `worksheet.PUNCT` | ERROR | silent audit/apply divergence |
| R1  | Engine keys (`[...]-` in ls/scr) must have `en:""` | ERROR | BGM/interlude kill |
| R2  | Slot fit on in-place containers (Battle/Common/General2d/EBOOT; LDBI-talk & FixedData grow): emit bytes ≤ slot | WARN¹ | 1,229 invisible-JP battle lines |
| R3  | Exotic chars in emit_en outside the normalizer's coverage (Cyrillic/Greek lookalikes, macrons, `¶`, stray `…`, fullwidth ASCII) | ERROR | "Solgади", "Keito Ra¶ken" |
| R4  | Token preservation: `§` count, `#0/#1/..` presence, `「」` balance | ERROR | crash / dropped-substitution classes |
| R5  | Control tags `{W,H,C,S,Y,T,I,X,LINK}` (+ `/` closers) multiset matches JP↔EN | ERROR | dialogue 2-column split, layout |
| R6  | `<...>` term-link (readable name, not a key=value control tag) in emit_en → renders full-width in the oversized field → line slips off the box edge | WARN | library scramble, 2-column split, dialogue term-link slippage |
| R7  | Fullwidth ASCII (Ａ-Ｚ ａ-ｚ ０-９) in emit_en outside the WTD file | WARN | fw_ascii leaks from JP source |
| R8  | Doubled words `\b(\w+) \1\b` (whitelisted) | WARN | "Hiryu Kai Kai" (user found, audit didn't) |
| R9  | Visible-empty: empty-`en` entry whose offset-neighbours in the same file are mostly translated + short label JP | WARN | 待機/Float/Fuse EBOOT strays |
| R10 | Name canon (JP-gated vs `pdf_charnames.json`): JP name present ⇒ EN spelling present | WARN | Cybaster/Exelance/etc. |
| R11 | Cross-container term consistency: same JP UI term → one EN spelling | INFO | "Support Atk" vs "Support Attack" |
| R12 | Dialogue reflow ≤3 lines (LDBI, `rewrap` @48) | WARN | box truncation / squish |

¹ R2 is WARN, not ERROR, because `reinsert_grow` repoints an over-slot entry
whenever it finds a pointer to it (`_detect_tables`) and only leaves it as JP
when it can't — a per-offset fact slot size can't predict. The **authoritative**
silent-JP signal is the deploy's own `REFUSED (left original, safe): N offsets`
line; R2 is the static heads-up that tells you which entries to watch there.

Severity: ERROR = crash / corruption / silently-invisible in game (gate-blocking);
WARN = likely-visible defect (triage + fix); INFO = report-only (human judgement).
`python tools/audit.py --gate` exits nonzero if any ERROR survives — wire into
`deploy.py` and CI. `--json build/audit_report.json` for the full dump.

## Tier 1 — run + fix (deterministic; small token cost only for rewordings)

Run the suite; fix mechanically what's mechanical (normalize slips, token
restores, tag restores, trims that fit). Anything needing a reworded line goes
to Sonnet with the proven verify-loop.

## Tier 2 — coverage audit (zero tokens)

The Telop/Roll lesson (files dumped but never translated) + the remaining
empty-`en` EBOOT entries. Classify every empty entry: visible-table neighbour
(translate), debug/format string (skip, documented), unknown (list for
playtest). Same for any worksheet at 0% coverage. `audit.py --coverage`.

## Tier 3 — language-quality (real token spend; depth = owner's call)

- **3a** Chunk-boundary continuity (~340 Phase-2 seams): Sonnet reads the 20
  lines spanning each seam for tone/pronoun/terminology discontinuity.
- **3b** Grammar/slip sweep (~200 files): per-file low-effort Sonnet pass,
  report-only (doubled/dropped words, broken sentences, homophones); we fix
  confirmed.
- **3c** Full JP-vs-EN fidelity re-read (all ~88k entries): the "human
  translator" tier — deferred to human review per the release decision. Not now.

## Decision (2026-07-10)

Tier 0+1+2 now (near-free, kills the "user keeps finding strays" class). Tier
3a/3b to Sonnet when token budget is comfortable. Tier 3c stays deferred to the
human review. The suite is the standing regression gate thereafter — every
future edit is checked against every lesson automatically.
