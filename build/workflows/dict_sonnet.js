export const meta = {
  name: 'translate-dictionaries-sonnet',
  description: 'Finish + fit remaining Unit/Pilot library dictionary entries on Sonnet 5',
  phases: [{ title: 'Finish', detail: 'Sonnet agents: translate untranslated + re-trim overflowing' }]
}
const DIR = 'build/workflows/batches/dict'
const plan = { remaining: ["P02","P04","P05","P06","P07","P08","P09","P10","P11","P12","P13","P14","P15","P16","P17","P18","P19","P20","P21","P22","P23","P24","P25","P26","P27","P28","P29","U14","U21"], retrim: ["R00","R01","R02"] }

const translatePrompt = (nm) => `You are localizing the in-game LIBRARY encyclopedia of the PS3 game "2nd Super Robot Wars OG" (JP->EN fan patch). ${nm.startsWith('U') ? 'These are MECHA/ROBOT entries.' : 'These are PILOT/CHARACTER entries.'}

Read: 1. ${DIR}/${nm}.json -- { "<key>": {"jp": "...", "max_chars": N}, ... }  2. ${DIR}/namemap.json (keywords for <tags>, names).

Translate every "jp" to natural encyclopedic English (third person).
RULES: at most max_chars chars per entry (aim ~92%); <...> tags -> EXACT English from the keywords map, brackets kept; names from the names map; ASCII punctuation only (' " - ...), no macrons/non-Latin; do NOT put raw newlines in a JSON string - write backslash-n for a paragraph break (max 2); translate EVERY key.
WRITE with the Write tool to EXACTLY ${DIR}/out/${nm}.json as { "<key>": "<english>", ... }, then reply with ONLY the integer count.`

const trimPrompt = (nm) => `You are TIGHTENING English encyclopedia entries for a PS3 SRW OG fan-translation so they fit the display box.

Read ${DIR}/${nm}.json -- { "<key>": {"en": "<current English>", "max_chars": N}, ... }
For EVERY entry, shorten "en" to AT MOST max_chars characters (aim ~92%). Cut redundancy, keep all key facts and names. Keep every <...> tag EXACTLY (brackets and inner text). ASCII punctuation only; no raw newlines in JSON strings (use backslash-n, max 2). No commentary.
WRITE with the Write tool to EXACTLY ${DIR}/out/${nm}.json as { "<key>": "<shortened english>", ... }, then reply with ONLY the integer count.`

phase('Finish')
const jobs = [
  ...plan.remaining.map(nm => ({ nm, p: translatePrompt(nm) })),
  ...plan.retrim.map(nm => ({ nm, p: trimPrompt(nm) })),
]
const results = await parallel(jobs.map(({ nm, p }) => () =>
  agent(p, { label: `dict-${nm}`, phase: 'Finish', effort: 'medium', model: 'sonnet' })
    .then(r => ({ nm, ok: !!r })).catch(() => ({ nm, ok: false }))
))
const fail = results.filter(r => !r || !r.ok).map(r => r && r.nm)
log(`dict-sonnet: ${jobs.length - fail.length}/${jobs.length} ok`)
return { ok: jobs.length - fail.length, failed: fail }
