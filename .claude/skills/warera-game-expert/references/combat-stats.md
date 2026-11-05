# Combat stats

| Stat | Practical effect `[RULE]` | Sources |
|---|---|---|
| Attack | base damage of a hit | skill, weapon, ammo, Pill, military rank |
| Precision | chance of a non-missed hit. A **miss** deals **exactly half** of Attack (since v0.16.5), can't crit, gives **no loot**, still uses ammo and equipment durability | skill, gloves |
| Critical Chance | chance of a critical hit; if a hit is both crit and miss, **the miss wins** | skill, weapon |
| Critical Damage | crit hit = Attack × (1 + Critical Damage %) `[WIKI-ONLY]` | skill, helmet |
| Armor | reduces Health spent per hit → more hits per bar | skill, chest, pants |
| Dodge | chance to hit **without losing Health and without wear on non-weapon gear**; ammo and weapon are still consumed | skill, boots |
| Health | bar consumed by each attack | skill, regen, MU help, food |
| Hunger | allows eating food to restore Health | skill, regen |
| Loot Chance | case / elite-case chance per **valid** hit | skill |

Skill values per level: [skills-and-respec.md](skills-and-respec.md).

## Armor and Dodge (F-MITIGATION) `[RULE][LIVE]`

```
effective % = total / (total + 40)      rounded to 2 significant figures
```
- ~40 points double the number of hits, 80 triple it (comparable conditions). No simple armor cap (config `softCap` 40 is
  the constant above).
- Armor total = Armor skill (6 points/level) + chest + pants. Dodge total = Dodge skill (4 points/level) + boots.
- Rounding creates **breakpoints**: several totals give the same %. Verified by community tests for armor; assumed for dodge.
- Health per hit `[RULE][LIVE]` (base 10): `10 × (1 − armor%)` = `10 × 40 / (armor + 40)` (user-confirmed, A-2). v0.24.0
  (2026-03-21) removed the armor hard cap; the wiki's minimum loss of 1 per hit is `[WIKI-ONLY]` (it would bind only above 360
  armor). Since v0.22.0 (2026-01-09) you **can hit below 10 Health**, depending on armor (exact threshold `[GAP]`). Expected with
  dodge: `10 × (1 − armor%) × (1 − dodge%)`.

### Breakpoint table (points → %)

| Points | % | Points | % | Points | % |
|---|---|---|---|---|---|
| 24–25 | 38 | 50–51 | 56 | 101–105 | 72 |
| 26 | 39 | 52–54 | 57 | 106–110 | 73 |
| 27 | 40 | 55–56 | 58 | 111–116 | 74 |
| 28 | 41 | 57–58 | 59 | 117–123 | 75 |
| 29 | 42 | 59–61 | 60 | 124–130 | 76 |
| 30 | 43 | 62–63 | 61 | 131–137 | 77 |
| 31–32 | 44 | 64–66 | 62 | 138–146 | 78 |
| 33 | 45 | 67–69 | 63 | 147–155 | 79 |
| 34 | 46 | 70–72 | 64 | 156–165 | 80 |
| 35–36 | 47 | 73–75 | 65 | 166–176 | 81 |
| 37 | 48 | 76–79 | 66 | 177–188 | 82 |
| 38–39 | 49 | 80–83 | 67 | 189–200+ | 83 |
| 40 | 50 | 84–86 | 68 | | |
| 41–42 | 51 | 87–91 | 69 | | |
| 43–44 | 52 | 92–95 | 70 | | |
| 45–46 | 53 | 96–100 | 71 | | |
| 47 | 54 | | | | |
| 48–49 | 55 | | | | |

Below 24 points every point changes the %. The formula reproduces this whole table (checked by script).
`python scripts/combat_calculator.py mitigation --skill-level 6 --item 29 --item 27` → 92 → 70% → bracket 92–95.

Guide examples: 36 + vest 29 + pants 27 = 92 → 70% (3 HP/hit); pants 30 → 95 → still 70% (≈6 money wasted at the time).
48 + mythic 70 + 70 = 188 → 82% (1.8 HP); 48 + 64 + 65 = 177 → also 82% (~150 money saved per pair at the time). Dodge L6 =
24 + boots 24 → 48 → 55%; boots 25 → still 55%. Dodge L8 = 32 + boots 55–59 → all 69% (~40 money price spread).

`[STRAT-RO]` Before buying a vest/pants/boots, compute the post-purchase total and check whether you cross into the next
bracket; buy the cheapest combination reaching the target or move saved skill points elsewhere. Matters little for cheap
gear, a lot for yellow/red gear. Relative value rises: 60→61% dodge = +2.5% relative, 70→71% = +3.33%.

## Overflow (F-OVERFLOW) `[RULE][LIVE]`

- Precision above 100% → **+4 Attack** per overflow point.
- Critical Chance above 100% → **+4 Critical Damage** per overflow point.
- Confirmed again in the live v0.27 client (`skillOverflow`, `skillOverflowValue` 4), 2026-10-26 `[LIVE-CLIENT]`.

*Derived ceilings without Prestige* (skill caps + best mythic rolls): flat Attack 350 + 300 (jet) + 240 (precision 100 + 60 gloves
→ 60 overflow) = **890**; Critical Damage 300 + 150 (helmet) + 40 (crit 60 + 50 weapon → 10 overflow) = **490%**. Outside battle the
highest Attack is 890 × 1.40 (heavy ammo) × 1.60 (Pill) × 1.375 (Supreme Commander) ≈ **2,741**. The codex quotes ≈ 5,054 by also
multiplying a battle factor of 1.95 and rank 1.30; that rests on its battle-bonus model (U-CDX-1), not on this skill's.

## No ammo in a firearm `[CODEX]` (checked by the codex against ammo-less live profiles' `skills.attack.total`)

A firearm without ammo counts only up to **knife level: at most 40 flat Attack**, and its **crit chance drops out** of the hit too.
So running dry costs far more than the ammo's +10/20/40%: for a 261-Attack firearm with 12% crit, light ammo lifted the codex's
expected hit from 1,029 to 2,031. The knife needs no ammo and loses nothing. Treat "no ammo" as a different (weak) weapon, not a
small discount. (History: v0.16.x briefly blocked guns without ammo entirely; reverted.) Verification of the crit part rests on
the codex alone `[Unverified]`.

## Stat valuation `[OBS]` (one advanced player's measurements, with Pill, green ammo, rank +25%, precision capped)

| Profile | Equivalences (1% Crit as reference) |
|---|---|
| Lvl 40, full epic | 5 Attack = 1.2% Precision = 1% Crit = 5% Crit Damage |
| Lvl 45, full legendary | 6 Attack = 1.5% Precision = 1% Crit = 4.5% Crit Damage |
| Lvl 50, full mythic | 9 Attack = 2.3% Precision = 1% Crit = 4% Crit Damage |

Conclusions `[OBS]`: Crit Chance is generally the most valuable stat; Crit and Crit Damage are synergistic (Crit Damage has
diminishing returns at high values); Precision below 100% is worth only ~50–70% of these figures, above 100% it becomes very
useful — aim to pass the cap. Don't max one stat blindly; ask "which item gives the most damage per money?".

## Damage per hit (F-DAMAGE) — estimate: miss rule `[GUIDE]`, crit rule `[WIKI-ONLY]`, stacking `[INFER]`

| Outcome | Probability | Damage |
|---|---|---|
| Miss | 1 − P | Attack / 2 |
| Critical | P × C | Attack × (1 + CD) |
| Normal | P × (1 − C) | Attack |

`E[damage per attempt] = A × [ (1 − P) × 0.5 + P × (1 + C × CD) ] × multipliers`, A = Attack (skill + weapon, plus +4 per precision
point above 100%), ammo and Pill as % of Attack (+10/20/40; Pill +60 / −60), then military rank and the battle-bonus total as
multipliers (guide: "Pill, ammo and rank multiply"). Wiki example: Attack 276, P 69%, C 24%, CD 59% → crit 439, expected ≈ 260.
`python scripts/combat_calculator.py damage ...`. Averages only (actions have RNG); calibrate against real hits.

Verification: miss = half damage / no crit / no loot is confirmed by the guide. The crit formula is `[WIKI-ONLY]` and the wiki
example predates the current scale (live Critical Damage skill = 100% at level 0 → 300% at level 10). The guide's equivalences
(level 40: 1% Crit ≈ 5% Crit Damage) fit this formula when Crit Damage ≈ 5 × Crit Chance, which is some support. A second
community source agrees: PrinceRealMarijn's *Fight Skills Mechanics Guide* (2026-05-30, via `[CODEX]`) gives crit = Attack ×
(1 + Crit Damage), "100% crit damage doubles the hit", miss resolved first. Still not an official statement.

Same expectation in the codex's shape: `E = A × (0.5 + 0.5·P + P·C·CD)` with P and C capped at 100%. It is algebraically identical
to the formula above.

**Per-hit spread** `[CODEX]` (unconfirmed): a 2025 formula shared on the game's Discord rolled each hit at **90–110%** and rounded up
twice. Whether it still applies is unknown. If it does, it is mean-neutral, so expected-damage figures don't change.

## Military rank `[RULE]`, table `[WIKI-ONLY]` (page from 2026-01-09; unverified)

Damage bonus by **total lifetime damage** — 120 ranks in three tiers (full table: `data/military-ranks.yaml`):

| Damage | Rank | Bonus |
|---|---|---|
| 0 | Initiate | 0% |
| 10K | Recruit | 2.5% |
| 100K–125K | 3★ Specialist / Corporal | 8.25–8.75% |
| 1M | Chief (silver tier) | 15% |
| 5M | Captain | 20% |
| 26M | Brigadier | 25% (the guide's "+25% at high ranks") |
| 100M | Rear Admiral (gold tier) | 28.75% |
| 1B | General | 34.25% |
| 10B | Supreme Commander | 37.5% |

`python scripts/combat_calculator.py rank --damage D`. Shown as a circular badge next to the avatar with progress on hover.
