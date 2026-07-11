export const meta = {
  name: 'translate-batches',
  description: 'Translate pre-split JP->EN batch files with glossary consistency (efficient: small per-agent input)',
  phases: [{ title: 'Translate', detail: 'one agent per batch file' }]
}

// args = { glossary, guidance, label,
//   batches: [path,...]                         // explicit list, OR
//   dir, start, count                           // generate <dir>/b####.json for start..start+count-1
// }
const A = (typeof args === 'string') ? JSON.parse(args) : args
const { glossary, guidance, label } = A
const pad = (n) => String(n).padStart(4, '0')
const batches = A.batches
  ? A.batches
  : Array.from({ length: A.count }, (_, i) => `${A.dir}/b${pad(A.start + i)}.json`)

const SCHEMA = {
  type: 'object',
  properties: {
    t: {
      type: 'array',
      items: {
        type: 'object',
        properties: { k: { type: 'string' }, en: { type: 'string' } },
        required: ['k', 'en'], additionalProperties: false
      }
    }
  },
  required: ['t'], additionalProperties: false
}

const prompt = (bp) => `You are translating in-game text of "2nd Super Robot Wars OG" (PS3) from Japanese to English for a fan-translation patch.

Read these two files with the Read tool:
1. ${bp}  — a JSON object { "<key>": "<Japanese source>", ... }. Keys are OPAQUE identifiers; echo each one back EXACTLY as-is (do not parse, split, or alter them).
2. ${glossary}  — a JSON object mapping Japanese names -> official English names.

Translate every value in the batch file to natural, fluent English.

RULES (critical):
- Names: use the glossary's EXACT English spelling for any character/unit/faction name that appears.
- Punctuation: use ONLY half-width ASCII — ' " - ...  (NEVER curly quotes ' ' " ", em-dash, or the … glyph). The game font renders those wrong.
- Length: the English MUST be about the same length or SHORTER than the Japanese (it is written back into a fixed byte slot; Japanese is 3 bytes/char, ASCII is 1, so this is usually easy — but do not pad).
- Preserve every \\n newline marker from the source in roughly the same place.
- Keep Japanese corner brackets 「 」 exactly where they appear (they are the game's quote brackets).
- ${guidance || ''}
- No notes, no commentary.

Return {"t":[{"k":"<hexkey>","en":"<english>"}, ...]} covering EVERY key in the batch file.`

phase('Translate')
const results = await parallel(batches.map((bp, i) => () =>
  agent(prompt(bp), { label: `${label || 'tr'}-${i}`, phase: 'Translate', schema: SCHEMA, effort: 'low' })
))

const merged = {}
let n = 0, failed = 0
for (const r of results) {
  if (r && r.t) { for (const x of r.t) { merged[x.k] = x.en; n++ } }
  else failed++
}
log(`merged ${n} translations; ${failed}/${batches.length} batches returned nothing`)
return merged
