# OG2 Translation — Text Inventory & Work-List

## CORRECTED string counts (2026-07-04) — actual translatable STRINGS, not CJK runs
(earlier "runs" numbers over-counted ~8x; these are `reinsert_utf8.scan` strings)
| Phase | Container | STRINGS | JP size | Source | Status |
|---|---|---|---|---|---|
| 1 | Common CSB (Archive OG1/OG2/OGg + Q&A) | **510** | 160 KB | akurasu + translate | OG2 done (38/40), OG1 in progress |
| 2 | Logic talk ls*.bin | **51,774** | 2.7 MB | 2ndsrwoge (align) | not started |
| 2 | Logic scr*.bin | **11,468** | 226 KB | 2ndsrwoge (align) | not started |
| 3 | Battle BMD | **34,450** | 1.7 MB | translate | not started |
Total ~98k strings (+ Battle name CSVs + General2d menus TBD).
Efficient workflow ≈ 170 tokens/string (30-string batches, small per-agent input).
NOTE: **CSB is in-place-only** (growth refused) — CSB English MUST fit the JP byte slot.

---


All dynamic text is UTF-8 in pointer-table containers (reinsertable/growable with
tools/reinsert_utf8 + logo). Menu *labels* are often baked into DDS textures (image
edit via dds_tool — a separate workstream). Counts are JP text runs / JP characters
(rough; a "run" ≈ one string or line).

## Phase 1 — Menus / Library / Informational  (source: mostly akurasu + translate)
Archive = Common.psarc. Dynamic text lives in 6 CSB (magic "CSB "):
| File | JP runs | Notes |
|---|---|---|
| Dat/Archive/Csb/Archive_OG1.csb | 277 | in-game library/lore (OG1 era) |
| Dat/Archive/Csb/Archive_OG2.csb | 365 | library/lore (OG2) |
| Dat/Archive/Csb/Archive_OGg.csb | 268 | library/lore (OG gaiden) |
| Dat/Option/QA/2og_Q&A.csb | 3342 | tutorial / help / Q&A (134 KB) |
| Dat/Option/ScenarioChart/ScenarioChart.csb | ~1 | scenario chart labels |
| Dat/Archive/Csb/Archive_Ending.csb | 0 | structural |
**CSB dynamic total ≈ 4,250 runs.**
BAKED (image edit, DDS): Dat/SceneTitle/*, Dat/LessonTitle/*, Dat/Option/Img/* (menu
labels, tutorial screens, option titles). Separate DDS workstream.
TODO: extract General2d.psarc (654 MB, not yet extracted) — likely holds the
intermission/gameplay menu dynamic text (unit/weapon select, spirit commands).

## Phase 2 — Main Script  (source: EXISTS — the English script PDFs; align + insert)
Archive = Logic.psarc.
| Group | files | JP runs | JP chars |
|---|---|---|---|
| Dat/logic/talk/ls*.bin (LDBI dialogue) | 102 | ~103,000 | ~694,000 |
| scr*.bin (scene/scenario) | 102 | ~9,600 | ~39,000 |
Biggest by volume, but LOWEST effort — English already written; this phase is
alignment (match EN script lines to JP slots) + insertion, not translation.

## Phase 3 — Battle lines / cutins / names  (source: translate from scratch + akurasu)
Archive = Battle.psarc.
| Group | files | JP runs | JP chars | Source |
|---|---|---|---|---|
| Dat/Battle/Message/*.bmd (quotes/cutins) | 171/307 | ~61,000 | ~406,000 | translate |
| Dat/Battle/**/ *U8.csv (unit/pilot/weapon names) | 252 | ~21,900 | ~120,000 | akurasu DB |
Largest from-scratch translation; consistency-critical (names must match Phase 1/2).

## Grand total (dynamic text): ~200k runs / ~1.26M JP chars
- Phase 2 (~733k chars) = existing EN → mechanical.
- Phase 1 CSB (~4.25k runs) + Phase 3 (~525k chars) = real translation work.
- Plus baked-DDS menu labels = image workstream (scope TBD).

## Pipeline per format (all pure-Python, proven):
decrypt_sdat → extract_psarc → edit (reinsert_utf8/logo, +ASCII-punct normalize) →
pack_psarc → encrypt_sdat → deploy to FOLDER **and** GD + clean GD reinstall.
Container magics: LDBI (talk/scr), CSB ("CSB "), BMD, FIXH, CSV(plain).
