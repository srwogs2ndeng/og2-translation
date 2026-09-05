# Over-cap rewrite proposals (trim tier, <= +4B)

Every FixedData/EBOOT string whose English exceeds its byte cap. These rely on
the all-or-nothing `fixh_grow` (a single over-cap row can revert a whole file to
JP), so fitting them within `slot` lets the file deploy in-place, bulletproof.

**Rule:** proposed English must be `<= slot` bytes. `WIDEN` = proper noun / canon
term / too-tight slot that can't be trimmed without butchering -> goes to the
field-widening list, full form preserved. `REVIEW` = a fit I'm least sure of.
Edit the **Proposed** column freely; I apply exactly what's here after your pass.

**Owner decisions:** BGM titles AND stage titles stay FULL (routed to keep-full/
widen, never trimmed). Sanger's theme 悪を断つ剣 = **The Sword That Cleaves Evil**.

## StageData  (24 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x000BCB | 召喚 | Summoning (9) | 6 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000CD6 | 王都への路 | Road to the Capital (19) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000D21 | 野心の代償 | Price of Ambition (17) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000D66 | 違えた道 | The Wrong Path (14) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000D9E | 地底世界 | The Underworld (14) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000E2C | 胞子の谷 | Valley of Spores (16) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000ECB | 遭遇 | Encounter (9) | 6 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000F7D | 手負いの狼 | The Wounded Wolf (16) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x000FC2 | 黒き迅雷 | Black Lightning (15) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x00106E | 揺れる矛先 | Wavering Spearhead (18) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x0010A7 | 影の軍団 | Shadow Legion (13) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x0010EF | 流星と彗星 | Meteor and Comet (16) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x001105 | 漆黒の虎、氷の白刃 | Black Tiger, White Blade of Ice (31) | 27 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x001127 | 運命の風 | Wind of Destiny (15) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x00117C | 呼応する偽核 | Resonating False Cores (22) | 18 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x0011D0 | 追逃逆転 | Pursuit Reversal (16) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x0011E3 | 不可視の扉 | The Invisible Door (18) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x0012DF | 凶鳥は三度死ぬ | The Ill Bird Dies Thrice (24) | 21 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x001374 | 去来交差点 | Crossroads of Fate (18) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x00138A | 風の呼び声 | Call of the Wind (16) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x0013BF | 封印の予兆 | Omen of the Seal (16) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x0013D5 | 天蓋の下で | Under the Firmament (19) | 15 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x001442 | 神の牢獄 | Prison of God (13) | 12 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |
| 0x001595 | 母なる星の護り神 | Guardian of the Mother Star (27) | 24 | -> widen: keep full stage title (owner: stage titles stay) | WIDEN |

## BGMData  (22 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x001030 | 休みも大事 | Rest Matters Too (16) | 15 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x00149A | 鋼の魂 | Soul of Steel (13) | 9 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x001748 | 我ニ敵ナシ | None Can Best Me (16) | 15 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x00175E | 剣・魂・一・擲 | Sword, Soul, One Throw (22) | 21 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x0018B2 | 黙示録 | Apocalypse (10) | 9 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x0018C2 | 静寂と動乱 | Silence and Turmoil (19) | 15 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x001A79 | 戦火の狭間で | Amid the Flames of War (22) | 18 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x001AD0 | 雪解けの詩 | Song of the Thaw (16) | 15 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x001B49 | 天翔る龍 | Soaring Dragon (14) | 12 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002004 | 戦士達の記録 | Record of the Warriors (22) | 18 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x0020F2 | 勝利者への機構 | Machinery for the Victor (24) | 21 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002146 | 猛き巨神の交響曲 | Symphony of the Fierce Titan (28) | 24 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002165 | 我が望むは勝利の福音 | I Wish for the Gospel of Victory (32) | 30 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x0023F3 | 炎の中華体育教師 | Fiery Chinese Gym Teacher (25) | 24 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002491 | 巨大な闇 | Immense Darkness (16) | 12 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002649 | 月夜の晩に | On a Moonlit Night (18) | 15 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002767 | １００光年の勇気 | 100 Light-Years of Courage (26) | 24 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002870 | 君がいるから | Because You're Here (19) | 18 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002AB2 | 正義は我にあり | Justice Is On Our Side (22) | 21 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002AF9 | 軍神が災いを呼ぶ | The War God Brings Calamity (27) | 24 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002C12 | 闘志、果てなく | Endless Fighting Spirit (23) | 21 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |
| 0x002DA1 | 迷宮のプリズナー | Prisoner of the Labyrinth (25) | 24 | -> widen: keep full BGM title (owner: BGMs stay) | WIDEN |

## WeaponData  (39 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x0142F8 | 実弾 | Solid Shot (10) | 6 | Rounds (6) | APPLIED |
| 0x0143AF | 実体剣 | Solid Sword (11) | 9 | Hard Edge (9) | REVIEW |
| 0x014570 | 非実体剣 | Phantom Sword (13) | 12 | Phantom Edge (12) | APPLIED |
| 0x0149D2 | 補給装置 | Resupply Unit (13) | 12 | Supply Unit (11) | APPLIED |
| 0x014A64 | 天上天下念動連撃拳 | Tenjo Tenge Psycho Combo Fist (29) | 27 | -> widen: canon attack name (Tenjo Tenge) | WIDEN |
| 0x014D02 | 天上天下念動爆砕剣 | Tenjo Tenge Psycho Blast Sword (30) | 27 | -> widen: canon attack name (Tenjo Tenge) | WIDEN |
| 0x01547C | 零式斬艦刀・疾風迅雷 | Zero Warship Slayer: Hayate Jinrai (34) | 30 | -> widen: canon Zankantou art | WIDEN |
| 0x0154A1 | 零式斬艦刀・疾風怒濤 | Zero Warship Slayer: Shippu Dotoh (33) | 30 | -> widen: canon Zankantou art | WIDEN |
| 0x015563 | 計都羅¶剣・暗剣殺 | Keito Rago Sword: Anken Satsu (29) | 26 | -> widen: canon attack name (Keito Rago) | WIDEN |
| 0x015584 | 計都羅¶剣・五黄殺 | Keito Rago Sword: Goo Satsu (27) | 26 | -> widen: canon attack name (Keito Rago) | WIDEN |
| 0x015746 | 参式獅子王刀・歳破 | Type-3 Shishioh Blade: Saiha (28) | 27 | -> widen: canon (Type-3 Shishioh Blade - owner-set) | WIDEN |
| 0x015784 | 龍王爆雷符 | Ryuoh Bakurai Fu (16) | 15 | -> widen: canon (Ryuoh) | WIDEN |
| 0x0157C6 | 龍王破山剣・逆鱗断 | Ryuoh Hazan Sword: Gekirin Dan (30) | 27 | -> widen: canon (Ryuoh Hazan Sword) | WIDEN |
| 0x0157E8 | 龍王破山剣・天魔降伏斬 | Ryuoh Hazan Sword: Tenma Gofuku Zan (35) | 33 | -> widen: canon (Ryuoh Hazan Sword) | WIDEN |
| 0x0158C9 | 参式爆連打 | Sanshiki Bakurenda (18) | 15 | -> widen: canon attack name | WIDEN |
| 0x01597E | 爆雷符 | Bakurai Fu (10) | 9 | -> widen: canon attack name | WIDEN |
| 0x015E33 | 肥袋撃 | Hitai Geki (10) | 9 | -> widen: romanized attack name | WIDEN |
| 0x015E59 | 万針撃 | Manshin Geki (12) | 9 | -> widen: romanized attack name | WIDEN |
| 0x015EE9 | 魚胎覧 | Gyotai Ran (10) | 9 | -> widen: romanized attack name | WIDEN |
| 0x016399 | 実体弾 | Solid Shot (10) | 9 | Live Shot (9) | APPLIED |
| 0x016BCF | 準必殺技 | Semi-Finisher (13) | 12 | Sub-Finisher (12) | APPLIED |
| 0x016DD7 | 主砲 | Main Gun (8) | 6 | Cannon (6) | APPLIED |
| 0x016ED0 | 連装副砲 | Linked Sub Gun (14) | 12 | Sub Cannons (11) | APPLIED |
| 0x016F46 | 艦首超重力衝撃砲 | Bow Gravity Impact Cannon (25) | 24 | Bow Gravity Cannon (18) | APPLIED |
| 0x016FF6 | 対空機銃 | AA Machine Gun (14) | 12 | AA Gun (6) | APPLIED |
| 0x01701C | 斬艦刀・大車輪 | Zankantou: Grand Wheel (22) | 21 | -> widen: canon Zankantou art | WIDEN |
| 0x017038 | 斬艦刀・雷光斬り | Zankantou: Lightning Slash (26) | 24 | -> widen: canon Zankantou art | WIDEN |
| 0x0170C6 | 竜巻斬艦刀 | Tornado Zankantou (17) | 15 | -> widen: canon Zankantou variant | WIDEN |
| 0x017712 | 通常用 | Normal use (10) | 9 | Normal (6) | APPLIED |
| 0x017756 | 影用 | Shadow use (10) | 6 | Shadow (6) | APPLIED |
| 0x017C5C | 烈火刃 | Blazing Blade (13) | 9 | Fire Edge (9) | REVIEW |
| 0x017CDE | 玄武金剛弾 | Black Tortoise Shot (19) | 15 | Tortoise Shot (13) | REVIEW |
| 0x018113 | 円月殺法 | Full Moon Slash (15) | 12 | Moon Slash (10) | APPLIED |
| 0x018348 | 五郎入道正宗 | Goro Nyudo Masamune (19) | 18 | -> widen: proper sword name (Masamune) | WIDEN |
| 0x018632 | 超振動クロー | Ultra Vibration Claw (20) | 18 | Ultra Vibro-Claw (16) | APPLIED |
| 0x01886D | 浄化の焔 | Purifying Flame (15) | 12 | Purge Flame (11) | APPLIED |
| 0x0197EF | 実体剣系 | Solid Sword type (16) | 12 | Solid Sword (11) | APPLIED |
| 0x01987B | 精神１系 | Spirit 1 type (13) | 12 | Spirit 1 (8) | APPLIED |
| 0x01988E | 精神２系 | Spirit 2 type (13) | 12 | Spirit 2 (8) | APPLIED |

## TrophyData  (9 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x000959 | 撃墜王 | Ace of Aces (11) | 9 | Top Ace (7) | APPLIED |
| 0x000B37 | 奇跡の生還 | Miracle Survival (16) | 15 | Miracle Return (14) | APPLIED |
| 0x000C07 | 戦闘で、敵のＨＰを１桁台にする。 | Reduce an enemy's HP to a single digit in battle. (49) | 48 | Reduce a foe's HP to single digits in battle. (45) | APPLIED |
| 0x000DAC | 艦長の風格 | A Captain's Bearing (19) | 15 | Captain's Poise (15) | APPLIED |
| 0x0013E4 | 撃墜され王 | King of the Downed (18) | 15 | Downed King (11) | APPLIED |
| 0x0014E4 | 一騎当千 | One vs Thousand (15) | 12 | One-Man Army (12) | APPLIED |
| 0x001599 | 狙撃王 | Sniper King (11) | 9 | Sharpshot (9) | APPLIED |
| 0x001734 | その漢、鉄壁 | That Man, Iron Wall (19) | 18 | Iron Wall Man (13) | APPLIED |
| 0x00185F | 愛の戦士 | Warrior of Love (15) | 12 | Love Warrior (12) | APPLIED |

## UnitData  (14 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x00C5BA | 敵版 | Enemy ver. (10) | 6 | Enemy (5) | APPLIED |
| 0x00C72C | 苦辛公主 | Kushin Koushu (13) | 12 | Kushin Koshu (12) | REVIEW |
| 0x00CDAA | 合体形態 | Combined form (13) | 12 | Combo Form (10) | APPLIED |
| 0x00DD35 | 水系高位（水） | Water high-rank (water) (23) | 21 | Water high (water) (18) | APPLIED |
| 0x00DE2F | 敵用 | Enemy use (9) | 6 | Enemy (5) | APPLIED |
| 0x00DEB9 | 炎系低位（雷） | Fire low-rank (thunder) (23) | 21 | Fire low (thunder) (18) | APPLIED |
| 0x00DF17 | 風系低位（陽炎） | Wind low-rank (heat haze) (25) | 24 | Wind low (heat haze) (20) | APPLIED |
| 0x00DFBD | 緑と青の２種類 | Green and blue, 2 types (23) | 21 | Green & blue, 2 types (21) | APPLIED |
| 0x00E2C8 | 敵用。緑 | Enemy use. Green (16) | 12 | Enemy. Green (12) | APPLIED |
| 0x00E316 | 紫 | Purple (6) | 3 | -> widen: color label - 'Purple' can't fit 3B | WIDEN |
| 0x00E49D | 青 | Blue (4) | 3 | -> widen: color label - 'Blue' can't fit 3B | WIDEN |
| 0x00E4F5 | 緑 | Green (5) | 3 | -> widen: color label - 'Green' can't fit 3B | WIDEN |
| 0x00E912 | 戦艦 | Warship (7) | 6 | Ship (4) | APPLIED |
| 0x00F37D | 暴走時 | Berserk mode (12) | 9 | Berserk (7) | APPLIED |

## SpiritData  (12 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x0005ED | 直感 | Intuition (9) | 6 | -> widen: canon spirit command (Intuition) | WIDEN |
| 0x000960 | 魂 | Soul (4) | 3 | -> widen: canon spirit 'Soul' - can't fit 3B | WIDEN |
| 0x000C1F | 強襲 | Assault (7) | 6 | -> widen: canon spirit command (Assault) | WIDEN |
| 0x000C79 | できます。 | Direct Hit at once. (19) | 15 | Direct Hit now. (15) | REVIEW |
| 0x000C8F | 愛 | Love (4) | 3 | -> widen: canon spirit 'Love' - can't fit 3B | WIDEN |
| 0x000D32 | 直撃 | Direct Hit (10) | 6 | -> widen: canon spirit (Direct Hit) | WIDEN |
| 0x000D9F | 鉄壁 | Iron Wall (9) | 6 | -> widen: canon spirit (Iron Wall) | WIDEN |
| 0x001022 | 信頼 | Support (7) | 6 | Trust (5) | REVIEW |
| 0x001072 | 友情 | Friendship (10) | 6 | -> widen: canon spirit (Friendship) | WIDEN |
| 0x0010B9 | 絆 | Bond (4) | 3 | -> widen: canon spirit 'Bond' - can't fit 3B | WIDEN |
| 0x00137A | 大激励 | Great Rouse (11) | 9 | Rouse All (9) | REVIEW |
| 0x00146D | 補給 | Resupply (8) | 6 | Supply (6) | APPLIED |

## KeyGuideData  (6 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x003B22 | 改造 | Upgrade (7) | 6 | Modify (6) | APPLIED |
| 0x003C11 | 変形 | Transform (9) | 6 | Morph (5) | REVIEW |
| 0x003C70 | 頁切換 | Switch Page (11) | 9 | Flip Page (9) | APPLIED |
| 0x00453A | 養成 | Training (8) | 6 | Train (5) | APPLIED |
| 0x00462C | 行送り | Line Forward (12) | 9 | Next Line (9) | APPLIED |
| 0x004A33 | 登録 | Register (8) | 6 | Enroll (6) | REVIEW |

## PartsData  (4 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x000E14 | 高性能スラスター | High-Performance Thruster (25) | 24 | High-Power Thruster (19) | APPLIED |
| 0x000F3E | 1機体の移動力を１、運動性を５だけ | 1Raises the unit's Movement by 1 and Mobility by 5 (50) | 49 | 1Raises unit Movement by 1 and Mobility by 5 (44) | APPLIED |
| 0x001C70 | 勇者の印 | Hero's Emblem (13) | 12 | Hero's Crest (12) | APPLIED |
| 0x001CFB | 鋼の魂 | Soul of Steel (13) | 9 | Iron Soul (9) | APPLIED |

## MapWeaponData  (2 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x000252 | ◆自機中心型 | ?Self-Centered Type (19) | 18 | ?Self-Center Type (17) | APPLIED |
| 0x0009DF | ◆着弾指定型 | ?Target-Impact Type (19) | 18 | ?Impact-Point Type (18) | APPLIED |

## HelpData  (3 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x0089B9 | せん。 | not occur. (10) | 9 | not occur (9) | APPLIED |
| 0x00B3B5 | 声優名を表します。 | Shows the voice actor's name. (29) | 27 | Shows the VA's name. (20) | APPLIED |
| 0x015DAB | 攻撃対象のバリア系特殊能力を発生させません。 | Prevents the target's barrier-type special abilities from ac (69) | 66 | Stops the target's barrier-type abilities from activating. ( | APPLIED |

## PilotData  (71 rows)

| key | jp | current (B) | slot | Proposed (B) | flag |
|-----|----|-------------|------|--------------|------|
| 0x01732D | 無人 | Unmanned (8) | 6 | Empty (5) | REVIEW |
| 0x0173EB | 井上和彦 | Kazuhiko Inoue (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017554 | 石塚運昇 | Unshou Ishizuka (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017668 | 皆口裕子 | Yuko Minaguchi (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01772D | 子安武人 | Takehito Koyasu (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01788A | 小林沙苗 | Sanae Kobayashi (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0179D6 | 速水奨 | Sho Hayami (10) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017B59 | 菅原正志 | Masashi Sugawara (16) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017BAB | 秋元羊介 | Yosuke Akimoto (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017D7B | 宮坂俊蔵 | Shunzo Miyasaka (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017E27 | 木村雅史 | Masashi Kimura (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017F3C | 水谷優子 | Yuko Mizutani (13) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017F9A | 杉田智和 | Tomokazu Sugita (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x017FCD | 高橋美佳子 | Mikako Takahashi (16) | 15 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0180A7 | 折笠愛 | Ai Orikasa (10) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0180E0 | 田中敦子 | Atsuko Tanaka (13) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01812F | 堀内賢雄 | Kenyu Horiuchi (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018165 | 小林由美子 | Yumiko Kobayashi (16) | 15 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0181D1 | 堀川仁 | Jin Horikawa (12) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018201 | 田中大文 | Hirofumi Tanaka (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018231 | 相沢舞 | Mai Aizawa (10) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018267 | 山口勝平 | Kappei Yamaguchi (16) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0182A6 | 榊原ゆい | Yui Sakakibara (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01831E | 青木崇 | Takashi Aoki (12) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01839C | 田中完 | Kan Tanaka (10) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018402 | 西前忠久 | Tadahisa Saizen (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018438 | 清水香里 | Kaori Shimizu (13) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01846E | 鶏内一也 | Kazuya Torinai (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018528 | 渡辺明乃 | Akeno Watanabe (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01859A | 長沢美樹 | Miki Nagasawa (13) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018624 | 稲田徹 | Tetsu Inada (11) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01865A | 真殿光昭 | Mitsuaki Madono (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0186AC | 松本梨香 | Rica Matsumoto (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0186E8 | 田中秀幸 | Hideyuki Tanaka (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018721 | 佐藤正治 | Masaharu Sato (13) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0187E9 | 井上剛 | Takeshi Inoue (13) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018884 | 寺島拓篤 | Takuma Terashima (16) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018912 | 園部好德 | Yoshinori Sonobe (16) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01894B | 神奈延年 | Nobutoshi Kanna (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018A50 | 武政秀一 | Shuichi Takemasa (16) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018AEB | 池添朋文 | Tomofumi Ikezoe (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018C10 | 石田彰 | Akira Ishida (12) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018C74 | 広瀬正志 | Masashi Hirose (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018CAD | 高橋広樹 | Hiroki Takahashi (16) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018CE6 | 白鳥由里 | Yuri Shiratori (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018D1C | 宝亀克寿 | Katsuhisa Hoki (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018D4F | 小林優子 | Yuko Kobayashi (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018E6F | 中村悠一 | Yuichi Nakamura (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018F76 | 桑島法子 | Houko Kuwashima (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x018FD1 | 高塚正也 | Masaya Takatsuka (16) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x019010 | 竹内良太 | Ryota Takeuchi (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x019167 | 島田敏 | Bin Shimada (11) | 9 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x019234 | 加瀬康之 | Yasuyuki Kase (13) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0192FD | 鳥海浩輔 | Kosuke Toriumi (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01932A | 岡本寛志 | Hiroshi Okamoto (15) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x0193D1 | 池澤春菜 | Haruna Ikezawa (14) | 12 | -> widen: voice-actor name (cannot trim a real name) | WIDEN |
| 0x01A3DE | 基地司令 | Base Commander (14) | 12 | Base Cmdr (9) | APPLIED |
| 0x01A3F1 | 議員 | Councilor (9) | 6 | Member (6) | REVIEW |
| 0x01A3FE | 議員Ａ | Councilor A (11) | 9 | Member A (8) | APPLIED |
| 0x01A41E | 市民 | Citizen (7) | 6 | Local (5) | REVIEW |
| 0x01A42B | 秘書 | Secretary (9) | 6 | Aide (4) | APPLIED |
| 0x01A47E | 地上の人 | Surface Dweller (15) | 12 | Surfacer (8) | APPLIED |
| 0x01A586 | 永吉ユカ | Yuka Nagayoshi (14) | 12 | -> widen: character name (Yuka Nagayoshi) | WIDEN |
| 0x01A6FD | 泰北 | Taihoku (7) | 6 | -> widen: character name (Taihoku) | WIDEN |
| 0x01A73A | 蓬 | Yomogi (6) | 3 | -> widen: character name (Yomogi) - can't fit 3B | WIDEN |
| 0x01A75E | 敵 | Enemy (5) | 3 | Foe (3) | APPLIED |
| 0x01A778 | 敵用 | For Enemy (9) | 6 | Enemy (5) | APPLIED |
| 0x01A7AC | 暴走 | Berserk (7) | 6 | Frenzy (6) | APPLIED |
| 0x01A888 | 能力値は適当 | Stats are placeholder (21) | 18 | Stats: placeholder (18) | APPLIED |
| 0x01A934 | バラル兵 | Baral Soldier (13) | 12 | Baral Grunt (11) | APPLIED |
| 0x01A988 | 不利時 | When losing (11) | 9 | If losing (9) | APPLIED |

---

## Widen-tier catalog (77 rows, > +4B) - field-widening only
These overflow too far to trim without butchering; they wait on field-widening.

### BGMData (22)
- `0x000F6D` slot 15 +8  jp=記憶の底へ  en=`To the Depths of Memory`
- `0x001001` slot 9 +7  jp=蠢く影  en=`Stirring Shadows`
- `0x0014FA` slot 15 +12  jp=悪を断つ剣  en=`The Sword That Cleaves Evil`
- `0x0019D5` slot 18 +7  jp=凶星の監察官  en=`Inspector of the Ill Star`
- `0x001A1C` slot 15 +6  jp=始まりの地  en=`The Land of Beginning`
- `0x001A5D` slot 21 +5  jp=激闘への間奏曲  en=`Interlude to Fierce Battle`
- `0x001A92` slot 21 +10  jp=再起を心に誓え  en=`Vow in Your Heart to Rise Again`
- `0x001C74` slot 15 +5  jp=絆を信じて  en=`Believe in the Bonds`
- `0x0020BD` slot 21 +6  jp=生と死の分岐点  en=`Line Between Life and Death`
- `0x00210E` slot 18 +6  jp=試される戦略  en=`Strategy Put to the Test`
- `0x0023A9` slot 12 +16  jp=雀武周天  en=`Mahjong Warrior Round Heaven`
- `0x002412` slot 21 +11  jp=水と沼の国から  en=`From the Land of Water and Marsh`
- `0x002459` slot 21 +6  jp=春風のプレシア  en=`Presia of the Spring Breeze`
- `0x0024A4` slot 15 +6  jp=迫り来る敵  en=`The Approaching Enemy`
- `0x0026C2` slot 6 +5  jp=予感  en=`Premonition`
- `0x0026FA` slot 15 +8  jp=精霊の加護  en=`Blessing of the Spirits`
- `0x002757` slot 9 +6  jp=力と技  en=`Power and Skill`
- `0x002901` slot 18 +5  jp=暴虐の超機人  en=`The Tyrannical Chokijin`
- `0x00291A` slot 12 +12  jp=四龍の長  en=`Lord of the Four Dragons`
- `0x00295F` slot 12 +7  jp=奔る黒影  en=`Racing Black Shadow`
- `0x0029B3` slot 12 +11  jp=古の忌憶  en=`Ancient Memory of Dread`
- `0x002CC4` slot 15 +6  jp=黒焔の狩人  en=`Hunter of Black Flame`

### WeaponData (18)
- `0x014A20` slot 27 +6  jp=天上天下念動破砕剣  en=`Tenjo Tenge Psycho Splitter Sword`
- `0x015E82` slot 12 +5  jp=回針轢殺  en=`Kaishin Rekisatsu`
- `0x015F7D` slot 12 +5  jp=一輪轢殺  en=`Ichirin Rekisatsu`
- `0x015FA0` slot 9 +11  jp=死反玉  en=`Makarugaeshi no Tama`
- `0x015FC0` slot 9 +10  jp=八握剣  en=`Yasakani no Tsurugi`
- `0x016DCA` slot 6 +5  jp=機銃  en=`Machine Gun`
- `0x016EE3` slot 15 +5  jp=連装衝撃砲  en=`Linked Impact Cannon`
- `0x017C95` slot 9 +7  jp=風刃閃  en=`Wind Blade Flash`
- `0x017CA5` slot 18 +7  jp=奥義・光刃閃  en=`Secret: Light Blade Flash`
- `0x017CBE` slot 9 +9  jp=青龍鱗  en=`Azure Dragon Scale`
- `0x017CCE` slot 9 +7  jp=白虎咬  en=`White Tiger Bite`
- `0x017CF4` slot 9 +13  jp=舞朱雀  en=`Dancing Vermilion Bird`
- `0x017ECD` slot 21 +7  jp=集束荷電粒子砲  en=`Focused Charged Particle Gun`
- `0x018225` slot 14 +5  jp=α外伝武器  en=`Alpha Gaiden weapon`
- `0x01829A` slot 15 +11  jp=火風青雲剣  en=`Fire Wind Blue Cloud Sword`
- `0x018316` slot 12 +8  jp=超振動拳  en=`Ultra Vibration Fist`
- `0x01846B` slot 12 +5  jp=黒き霹靂  en=`Black Thunderclap`
- `0x0184D1` slot 39 +5  jp=罪と罰の上位武器。魔装のみ  en=`Upgrade of Crime and Punishment. Mazoku only`

### TrophyData (1)
- `0x001203` slot 6 +5  jp=実戦  en=`Real Battle`

### UnitData (2)
- `0x00C69B` slot 6 +5  jp=後半  en=`Latter half`
- `0x00E442` slot 9 +10  jp=機装兵  en=`Mechanical Soldiers`

### MapWeaponData (1)
- `0x000B6E` slot 18 +7  jp=◆方向指定型  en=`?Direction-Specified Type`

### StageData (21)
- `0x000D37` slot 15 +9  jp=邪神の胎動  en=`Stirring of the Dark God`
- `0x000DC8` slot 18 +8  jp=孤狼との再会  en=`Reunion with the Lone Wolf`
- `0x000EB8` slot 12 +11  jp=異界の剣  en=`Sword of the Otherworld`
- `0x000F26` slot 12 +8  jp=敗軍の将  en=`The Defeated General`
- `0x000F93` slot 18 +10  jp=空を望む騎士  en=`Knight Who Longs for the Sky`
- `0x000FAC` slot 15 +6  jp=黒焔の狩人  en=`Hunter of Black Flame`
- `0x000FD5` slot 12 +15  jp=厭客再来  en=`The Loathsome Guest Returns`
- `0x000FE8` slot 18 +5  jp=地球を護る剣  en=`Sword That Guards Earth`
- `0x001001` slot 12 +15  jp=甦る青龍  en=`Revival of the Azure Dragon`
- `0x00103C` slot 12 +6  jp=南極の門  en=`The Antarctic Gate`
- `0x001084` slot 15 +7  jp=常夜の世界  en=`World of Endless Night`
- `0x00113A` slot 18 +6  jp=蒼光なき宇宙  en=`Space Without Blue Light`
- `0x001195` slot 12 +6  jp=繋がる縁  en=`Bonds That Connect`
- `0x00121E` slot 12 +6  jp=四神邂逅  en=`The Four Gods Meet`
- `0x001231` slot 12 +5  jp=狼と犬達  en=`Wolf and the Dogs`
- `0x001244` slot 15 +8  jp=蒼炎の逆鱗  en=`Wrath of the Blue Flame`
- `0x0012C9` slot 15 +5  jp=特異点崩壊  en=`Singularity Collapse`
- `0x0013EB` slot 12 +6  jp=雷迅昇星  en=`Rising Thunderbolt`
- `0x001502` slot 12 +12  jp=四龍の長  en=`Lord of the Four Dragons`
- `0x001563` slot 12 +10  jp=機人大戦  en=`War of the Machine Men`
- `0x0015B4` slot 12 +9  jp=古の忌憶  en=`Ancient Cursed Memory`

### PilotData (9)
- `0x01735D` slot 9 +8  jp=緑川光  en=`Hikaru Midorikawa`
- `0x0177EC` slot 12 +5  jp=増谷康紀  en=`Yasunori Masutani`
- `0x01795D` slot 12 +5  jp=阪口大助  en=`Daisuke Sakaguchi`
- `0x017B0D` slot 12 +5  jp=池水通洋  en=`Michihiro Ikemizu`
- `0x017EFA` slot 12 +6  jp=森川智之  en=`Toshiyuki Morikawa`
- `0x018835` slot 9 +6  jp=石川恵  en=`Megumi Ishikawa`
- `0x018A89` slot 12 +5  jp=松山鷹志  en=`Takashi Matsuyama`
- `0x0191F7` slot 9 +5  jp=関俊彦  en=`Toshihiko Seki`
- `0x01A538` slot 12 +5  jp=白熊寛嗣  en=`Hiroshi Shirokuma`

### HelpData (1)
- `0x00E119` slot 42 +6  jp=常などの特殊効果を与えます。  en=`applies special effects such as status ailments.`

### SpiritData (1)
- `0x000D86` slot 18 +9  jp=させません。  en=`defense & special defenses.`

### KeyGuideData (1)
- `0x003EF1` slot 6 +6  jp=先攻  en=`First Strike`

## EBOOT over-cap (8) - build_eboot is the authority on real slot
- `0xC395F8` slot~12 +1  jp=射撃武器  en=`Ranged Weapon`
- `0xC39650` slot~12 +1  jp=通常攻撃  en=`Normal Attack`
- `0xC513A8` slot~3 +2  jp=敵  en=`Enemy`
- `0xC514A8` slot~12 +1  jp=通常攻撃  en=`Normal Attack`
- `0xC64760` slot~3 +1  jp=陸  en=`Land`
- `0xC67AD8` slot~6 +1  jp=回収  en=`Recover`
- `0xC6E8C0` slot~6 +1  jp=反撃  en=`Counter`
- `0xC747C0` slot~6 +1  jp=回収  en=`Recover`
