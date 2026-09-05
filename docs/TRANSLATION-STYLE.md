# Translation style and method

How the English in this project is produced, and the rules any further pass has to
follow. This applies to new text, to fixes, and to any future title built on this
toolchain.

## The four rules

**1. Accurate before anything else.** Every mechanic, number, condition, scope and
qualifier survives intact. A description that says damage rises by 5% says 5%. A skill
that works only during the enemy phase says so. Nothing is invented to fill space and
nothing is dropped to save it. If the meaning genuinely will not fit the slot, shorten
the *wording*, never the *content*, and if content still has to go, say so in the commit
rather than letting it disappear quietly.

**2. Translate idioms, not words.** Japanese set phrases become the English phrase that
does the same job, not a literal gloss of their parts. 「さもありなん」 is "So it would
seem", not "it may well be so". 根を上げる is "throw in the towel", not "raise the
root". A coined technical term stays a term: 境界僅差転移 is *a boundary-margin
transfer*, a named process, not a description of how carefully something was done.
The test is whether a reader meets the same idea with the same register, not whether the
words line up.

**3. Names follow the game and akurasu, not invention.** In priority order:

| Source | Use it for |
|---|---|
| The game's own data (`UnitData.dat`, `PilotData.dat`, `WeaponData.dat`) | Units, pilots, weapons. This is the game's own romanization and it wins. |
| [akurasu.net](https://akurasu.net/wiki/Super_Robot_Wars/OG2nd) | Everything the game data does not spell out: terms, places, organisations, series conventions. |
| Official English materials, where they exist | Character names the series has already localised. |
| `glossary/glossary.json`, `build/canon_names.json` | The applied mapping, 162 characters and 691 names. Add to these rather than deciding again per line. |

Never invent a reading. 蚩尤 is **Chi You**, the Chinese war deity, not the invented
"Chiyuu" a pass once produced and not the run-together "Chiyou". When a name has a real
referent outside the game, use the referent's established English form.

Names are applied **by script, from the mapping**, not left to per-line judgement. That
is what keeps 200 scattered lines from drifting into four spellings of the same word,
which is exactly what happened to 限仙境 before it was unified as "the Boundary Realm".

**4. It has to sound like English.** Read the line as a person speaking. If nobody would
say it that way, rewrite it. Specifically:

- Prefer the natural English construction over mirroring Japanese order.
- Cut "This unit's ..." padding where the UI context already says whose it is: a tooltip
  reads "Ranged weapon damage +5%.", not "This unit's ranged weapon damage rises by 5%."
- Keep each character's register. A blunt pilot stays blunt; a formal one stays formal.
- **Half-width ASCII punctuation only.** No curly quotes, em dashes or ellipsis
  characters: the font renders those from the CJK range, full-width and misaligned. Keep
  the game's own 「」 brackets and the full-width brackets the menus require.
- Never emit `;` in library or dictionary text. The parser treats it as a line break.

## How a pass is run

The full-script pass that produced the story dialogue worked like this, and is the
pattern to repeat:

1. **Split into scene chunks in story order**, roughly 180 lines each. Chunk size is the
   point: it is large enough that the translator sees who is in the scene and what just
   happened, and small enough to stay coherent. Per-line translation produces exactly the
   stilted output people expect from machine translation.
2. **One translator per chunk**, each writing its own result file. Chunks are independent,
   so they run in parallel, and no single result is large enough to be truncated.
3. **Merge back into the worksheets by key.** The worksheet is the source of truth, keyed
   by the string's offset in the Japanese file.
4. **Apply names deterministically** from the glossary and canon-name maps, over the whole
   corpus at once. Never per chunk.
5. **Normalise mechanically**: punctuation to ASCII, ellipsis glyphs collapsed, spacing.
6. **Fit-check against the real slot budgets** before deploying. Each screen has its own:
   the wide help box takes 84 characters, the skill box 54, an ability tooltip about 37, a
   menu label its Japanese cell width divided by 1.26. `docs/HACKING.md` has the formats.
7. **Read it in game.** Every rendering bug this project has found was found on screen,
   not in the data.

## Translate the game's Japanese. Only that.

The English is produced **from the game's own script**. Do not align to, lift from, or
derive from any other party's translation, official or fan-made, even for comparison,
and even when one exists for the same game on another platform. That is someone else's
copyrighted work; the whole value of this project is that it is not a copy of one.

## What does not get translated

- **Bracketed `[...]-` strings in the scripts.** They are keys the engine matches byte
  for byte. Translating them skips every interlude and silences stage music.
- **Control bytes below 0x20**, and the 1 to 3 byte headers at the start of library
  description slots. Overwriting those ate the first letters of entries library-wide.
- **Full-width `＜＞【】` in menu chrome.** ASCII `<>` are parsed as control tags there and
  crash the menu.

## Honesty about what this is

The English came from a language model, and the dialogue was not proofread line by line.
Every public release says so on its front page. These rules exist to make that output as
good as it can be, not to obscure where it came from. See `docs/RELEASE.md`.
