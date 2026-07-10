export const meta = {
  name: 'translate-hybrid',
  description: 'Hybrid script translation: match story dialogue to the chapter English script, translate the rest',
  phases: [{ title: 'Translate', detail: 'per-batch, script-referenced' }]
}

// args = { batches:[path], glossary:path, ref:path, guidance, label }
const A = (typeof args === 'string') ? JSON.parse(args) : args
const { glossary, ref, guidance, label } = A
const pad = (n) => String(n).padStart(4, '0')
const batches = A.batches
  ? A.batches
  : Array.from({ length: A.count }, (_, i) => `${A.dir}/b${pad(A.start + i)}.json`)

const SCHEMA = {
  type: 'object',
  properties: {
    t: { type: 'array', items: {
      type: 'object',
      properties: { k: { type: 'string' }, en: { type: 'string' } },
      required: ['k', 'en'], additionalProperties: false
    } }
  },
  required: ['t'], additionalProperties: false
}

const prompt = (bp) => `You are localizing the STORY DIALOGUE of "2nd Super Robot Wars OG" (PS3) into English for a fan patch.

Read with the Read tool:
1. ${bp}          - JSON { "<key>": "<Japanese source>", ... }. Keys are OPAQUE; echo each back EXACTLY.
2. ${glossary}    - JSON of Japanese name -> official English name.
3. ${ref}         - the OFFICIAL English fan-translation of THIS chapter, as "Speaker: line".

For each Japanese value, produce English:
- If the Japanese is a DIALOGUE LINE that appears in the reference script (same speaker/scene/meaning), REUSE the reference's English wording as closely as possible (this keeps the patch consistent with the fan translation). Adapt lightly only if the game line is split/joined differently.
- If it is a bark/reaction/system line NOT in the reference (e.g. defeat cries, generic combat lines), translate it naturally and concisely.
- SPEAKER / NAME entries: some strings are speaker labels or bare names (e.g. "アイビス", or a tag like "[ＤＭ]-？イング"). Keep any bracketed control code (like "[ＤＭ]-", "[２]-003") EXACTLY as-is and only translate the Japanese NAME using the glossary. A leading "？" on a name means the speaker is unknown -> render the name part as "???".

Rules for ALL outputs:
- Preserve EVERY control/format marker exactly where it is: the markers @ , / , \\n , the corner brackets 「 」, and any nonprintable/control bytes at the start of a string.
- Use ONLY half-width ASCII punctuation: ' " - ...  (never curly quotes / em-dash / ellipsis glyph / fullwidth space).
- Use glossary spellings for every character/unit/faction name.
- ${guidance || ''}

Return {"t":[{"k","en"}, ...]} for EVERY key in the batch.`

phase('Translate')
const results = await parallel(batches.map((bp, i) => () =>
  agent(prompt(bp), { label: `${label || 'hy'}-${i}`, phase: 'Translate', schema: SCHEMA, effort: 'low' })
))

const merged = {}
let n = 0, failed = 0
for (const r of results) {
  if (r && r.t) { for (const x of r.t) { merged[x.k] = x.en; n++ } }
  else failed++
}
log(`merged ${n} translations; ${failed}/${batches.length} batches empty`)
return merged
