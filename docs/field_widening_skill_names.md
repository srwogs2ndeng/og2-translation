# Field-widening targets: skill-name renames

Four owner-approved skill renames (2026-07) are blocked on byte-capped name
fields: each field is capped at its JP byte length and the target English exceeds
it. Growing them as FIXH growth risks reverting the whole skill list to JP, so
they wait on the EBOOT/FIXH **field-widening** pass. Once a field's capacity is
widened to `>= target_bytes`, apply `target_en` to every listed offset.

Owner decisions: 底力->Potential, 強運->Fortune, 再攻撃->Double Attack,
念動力->Telekinesis. Not renamed: 予知 stays **Sense**; 連続攻撃 is **Chain Atk**
(already fit and applied).

## Name fields (widen these)

| JP | cur | target | bytes | file | offset | slot | over by |
|----|-----|--------|-------|------|--------|------|---------|
| 底力 | Guts | **Potential** | 9 | SkillData.dat.json | 0x0008A1 | 6 | +3 |
| 強運 | Chance | **Fortune** | 7 | SkillData.dat.json | 0x0011D7 | 6 | +1 |
| 再攻撃 | Re-Attack | **Double Attack** | 13 | SkillData.dat.json | 0x001A42 | 9 | +4 |
| 再攻撃 | Re-Attack | **Double Attack** | 13 | EBOOT/eboot.json | 0xC69BC0 | 9 | +4 |
| 再攻撃 | Re-Attack | **Double Attack** | 13 | EBOOT/eboot.json | 0xC6E9C0 | 9 | +4 |
| 念動力 | Psychic | **Telekinesis** | 11 | SkillData.dat.json | 0x00074B | 9 | +2 |

**Interim within-slot names already deployed (2026-07):** 強運 field = `Chance`
(6B, was `Luck`); 念動力 field = `Psychic` (7B, was `Psydriver`). These fit the
byte cap and ship now; swap to Fortune / Telekinesis once the field is widened.
底力 stays `Guts` and 再攻撃 stays `Re-Attack` in the interim (both coherent, fit).

## Phrase references (update for consistency when the rename lands)

| file | offset | slot | cur_en | target_en | bytes | over by |
|------|--------|------|--------|-----------|-------|---------|
| EBOOT/eboot.json | 0xC5D498 | 24 | Attack method: Re-Attack | Attack method: Double Attack | 28 | +4 |
| EBOOT/eboot.json | 0xC5D920 | 27 | ?Attack: Re-Attack | ?Attack: Double Attack | 22 | 0 |
| EBOOT/eboot.json | 0xC60308 | 39 | : Re-Attack (like Support) | : Double Attack (like Support) | 30 | 0 |

## Roomy reference fields — ALIGNED DOWN to interim (2026-07); flip UP at widening

STATUS: these description/tutorial blocks have byte room and previously used the
ideal names. To give the player ONE name per skill on every screen in the interim,
they were aligned DOWN to the current field names (Psychodriver->Psychic,
Fortune->Chance, Potential->Guts, Foresight->Sense). **When the byte-capped fields
are widened, flip BOTH the fields AND these references UP to the eventual names
(Telekinesis / Fortune / Potential) together.** (予知 = Sense is final, no flip.)
The pre-widening → post-widening mapping and exact offsets:

| skill | field shows (interim) | reference shows | reference locations (jp = 特殊スキル「…」) |
|-------|----------------------|-----------------|--------------------------------------------|
| 念動力 | Psychic | **Psychodriver** | HelpData 0x00E361 / 0x012949 / 0x012A50 / 0x01A8ED; AbilityData 0x000B47 / 0x000C6D; Q&A 0x00D43A / 0x00D4CB / 0x00DB5A / 0x00DBF7; Q&A 0x00B175 ("Psychic Field" barrier line refs "Psychodriver") |
| 強運 | Chance | **Fortune** | Q&A 0x00E7E6 / 0x00E81D / 0x015835 / 0x0158BA (already the eventual name) |
| 底力 | Guts | **Potential** | Q&A 0x00D43A / 0x00D4CB / 0x00DB5A / 0x00DBF7 (already the eventual name) |
| 予知 | Sense | **Foresight** | Q&A 0x00DB5A / 0x00DBF7 — separate Sense-vs-Foresight inconsistency; pick one and unify (owner kept skill = "Sense") |

When widening lets the fields hold Fortune / Telekinesis / Potential, flip both
the fields AND these references together so every screen agrees.

## Manual review (collisions / mixed references)

- **強運 vs 幸運 collision**: 幸運 is the **"Luck" spirit command** and must STAY
  "Luck". Do NOT globally replace `Luck -> Fortune`; only the 強運 *skill* becomes
  Fortune (interim: Chance).
- **CORRECTION — 念動力 IS "Psychodriver" in the descriptions.** Earlier note said
  the "Psychodriver" in HelpData was a separate ability; the data disproves this —
  every HelpData/AbilityData/Q&A "Psychodriver" whose jp is 特殊スキル「念動力」 is
  this same skill. So renaming 念動力 -> Telekinesis (interim Psychic) must also
  update those references. (Prose `念動力者` = a person with the power; render as
  telekinetic/psychic/esper in dialogue as fits — that's separate from the skill
  name and not part of this pass.)
- 2og_Q&A.csb.json `0x00E81D`, `0x015835`, `0x0158BA` each reference both the
  強運 skill (-> Fortune) and the 幸運 command (-> keep Luck) in one answer;
  disambiguate each "Luck" against the JP by hand when the rename lands.
