export const meta = {
  name: 'translate-phase2-contextual',
  description: 'Contextual JP->EN of Phase 2 story dialogue: scene-sized chunks in story order, medium effort, agents write result files',
  phases: [{ title: 'Translate', detail: 'one agent per scene chunk, in order, writes result to out/' }]
}

// args = { glossary, dir, outdir, chunks: [name,...] }   (names from _manifest.json)
const A = (typeof args === 'string') ? JSON.parse(args) : args
const { glossary, dir, outdir, chunks } = A

const prompt = (name) => `You are localizing the MAIN STORY of the PS3 game "2nd Super Robot Wars OG" (Dai-2-Ji Super Robot Taisen OG) from Japanese into English for a fan-translation patch. This is a dramatic mecha strategy-RPG with a large cast; the register ranges from military briefings to emotional character moments and banter.

Read these with the Read tool:
1. ${dir}/${name}  -- a JSON object { "<key>": "<Japanese line>", ... }. The entries are ONE CONTINUOUS SCENE SEQUENCE in story order (keys are opaque offset ids; echo each EXACTLY). Use the surrounding lines as context: track who is speaking, the emotional beat, and what was just said, so each line reads naturally in flow.
2. ${glossary}  -- Japanese name -> official English name.

Produce a proper, IDIOMATIC English localization -- not a literal gloss. Each line should read like natural spoken English in the character's voice, consistent with the lines around it.

RULES (critical):
- Names: use the glossary's EXACT English spelling for any character / mecha / faction / place name. For names not in the glossary, romanize consistently (and keep the SAME choice everywhere in this chunk).
- Voice & flow: match tone to the moment (terse in combat, warmer in quiet scenes); keep each character's voice consistent across the chunk; render idioms and banter as an English speaker actually would.
- Punctuation: half-width ASCII ONLY -- ' " - ...  (NEVER curly quotes, em-dash, or the single-glyph ellipsis; the game font renders those wrong).
- Length: aim for about the same length or SHORTER than the Japanese (it goes into a byte slot; JP is 3 bytes/char, ASCII 1). Don't pad; trim wordiness.
- Preserve every @ and \\n line-break marker in roughly its place; keep the corner brackets 「 」 where they appear; echo any non-Japanese control tags verbatim (<...>, [ ... ], §).
- Translate EVERY entry. No notes, no romaji, no commentary.

Then WRITE the result to this EXACT path with the Write tool:
  ${outdir}/${name}
Content = one JSON object { "<key>": "<english>", ... } covering EVERY key, UTF-8. After writing, reply with ONLY the integer count of entries written.`

phase('Translate')
const results = await parallel(chunks.map((name) => () =>
  agent(prompt(name), { label: name.replace('.json', ''), phase: 'Translate', effort: 'medium' })
    .then(r => ({ name, ok: !!r }))
    .catch(() => ({ name, ok: false }))
))
let ok = 0, fail = 0, failed = []
for (const r of results) { if (r && r.ok) ok++; else { fail++; if (r) failed.push(r.name) } }
log(`Phase2 contextual: ${ok} ok, ${fail} failed of ${chunks.length}`)
return { ok, fail, failed: failed.slice(0, 80) }
