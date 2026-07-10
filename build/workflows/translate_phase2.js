export const meta = {
  name: 'translate-phase2',
  description: 'Translate Phase 2 main-story dialogue batches; each agent writes its own result file (no huge return)',
  phases: [{ title: 'Translate', detail: 'one agent per batch file, writes result to disk' }]
}

// args = { glossary, dir, outdir, count, start }
const A = (typeof args === 'string') ? JSON.parse(args) : args
const { glossary, dir, outdir } = A
const start = A.start || 0
const count = A.count
const pad = (n) => String(n).padStart(4, '0')

const prompt = (i) => `You are translating MAIN-STORY DIALOGUE of the PS3 game "2nd Super Robot Wars OG" (Dai-2-Ji Super Robot Taisen OG) from Japanese to English for a fan-translation patch.

Read these with the Read tool:
1. ${dir}/b${pad(i)}.json  -- a JSON object { "<key>": "<Japanese source>", ... }. Keys are OPAQUE identifiers; echo each one back EXACTLY (do not parse/alter them).
2. ${glossary}  -- a JSON object mapping Japanese names -> official English names.

Translate every value to natural, fluent SPOKEN English that fits the character's voice (this is story dialogue, not a manual).

RULES (critical):
- Names: use the glossary's EXACT English spelling for any character / mecha / faction name that appears. If a name is not in the glossary, romanize it consistently and sensibly.
- Punctuation: use ONLY half-width ASCII -- ' " - ...  (NEVER curly quotes, em-dash, or the single-glyph ellipsis). The game font renders those wrong.
- Length: the English should be about the same length or SHORTER than the Japanese (it is written into a byte slot; JP is 3 bytes/char, ASCII is 1, so this is usually easy). Do not pad.
- Preserve every @ and \\n line-break marker in roughly its original place.
- Keep the Japanese corner brackets 「 」 exactly where they appear (the game's quote brackets).
- Echo any non-Japanese control tags verbatim (e.g. <...>, [ ... ], § ).
- No notes, no commentary, no romaji gloss.

Then WRITE the result to this EXACT path using the Write tool:
  ${outdir}/b${pad(i)}.json
The file content must be a single JSON object { "<key>": "<english>", ... } covering EVERY key in the batch file, ASCII/UTF-8. After writing, reply with ONLY the integer count of entries you wrote.`

phase('Translate')
const results = await parallel(
  Array.from({ length: count }, (_, j) => start + j).map((i) => () =>
    agent(prompt(i), { label: `p2-${pad(i)}`, phase: 'Translate', effort: 'low' })
      .then(r => ({ i, ok: !!r }))
      .catch(() => ({ i, ok: false }))
  )
)
let ok = 0, fail = 0, failed = []
for (const r of results) { if (r && r.ok) ok++; else { fail++; if (r) failed.push(r.i) } }
log(`Phase2 batches ${start}..${start + count - 1}: ${ok} ok, ${fail} failed`)
return { ok, fail, failedBatches: failed.slice(0, 60) }
