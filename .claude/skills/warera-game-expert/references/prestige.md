# Prestige

## Conditions and effects `[RULE][LIVE]`

Available at **level 50**. Prestiging:
- subtracts a fixed **65,000 XP** from your total (not a reset to zero);
- grants a permanent **XP bonus**, **1 Prestige Point**, a **free full respec**, and a **Prestige badge** (preserved across
  game resets per config).

| Total XP before | XP after | Level after (wiki XP table) |
|---|---|---|
| 86,600 (exactly at cap) | 21,600 | **25** (exactly the level-25 threshold) |
| 150,000 | 85,000 | **49** |

`python scripts/progression_calculator.py prestige --total-xp X` computes the landing level and skill points. Lifetime XP is
tracked separately and kept. Players who were already at level 50 when Prestige launched kept the XP banked above the cap `[WIKI-ONLY]`.

## XP bonus (`prestige.xp_bonus`)

| Prestige level | XP bonus |
|---|---|
| 1 | +50% |
| 2 | +60% |
| 3 | +70% |
| each further | +10 percentage points |

The bonus is **disabled while you are at level 50** (the cap only accumulates XP), and returns right after the next Prestige.

## Prestige Points (`prestige.point_stacking_cost`)

- A Prestige level adds one level to a skill **on top of whatever base level it has**, and lets it pass the normal
  maximum (10). `[LIVE]` (API, 2026-10-26): `skills.<s>.value` = table value at `level + prestige`, e.g. Energy 0+1 = 110,
  Attack 6+1 = 275. The Prestige Point budget is `leveling.prestigeLevel`.
- Repeated points on the **same** skill cost 1, 2, 4, 8 … — the cost **doubles** for each further bonus level (k-th level = 2^(k−1);
  confirmed by the wiki). +4 levels = 15 points, +5 = 31.
- A skill reset refunds all allocated Prestige Points.
- `python scripts/progression_calculator.py prestige-points --levels 4`.

`[STRAT-RO]` The first point on a skill gives the most per cost; before stacking, compare with the first bonus level on
another useful skill (run the build optimizer).

**What a bonus level is worth.** The live client extends a skill's value above its table in a straight line with the same step
`[LIVE-CLIENT]` (e.g. Attack 11 = 375, Companies 11 = 13). `[CODEX]` [OBS] for economy skills: all 19 profiles in the codex's
corpus with a skill above the cap sat exactly on that line (15 at Companies 13, 4 at Production 43 under the pre-v0.27 ladder).
No profile in that corpus (2026-08/09) had spent a Prestige Point on a **combat** skill. `[LIVE]` By 2026-10-26 they had: the API
showed Attack 6+1 = 275, Health 6+1 = 170, Precision 4+1 = 75 and Loot Chance 6+1 = 19, all on the same straight line.

## Prestige timing `[STRAT-RO]`

A level-50 player planning an Eco → Fight switch can Prestige just before mobilization: the free respec saves the reset cost
(0.5/point) and the build is rebuilt for war. Downside: the level drops, so check in the optimizer that the build at the new
level still hits the cost/1k target. `python scripts/progression_calculator.py prestige --total-xp X --level 50`.

### Bank at 50 or Prestige at once? *Derived*, from the XP clock in [progression.md](progression.md)

Every Prestige Point costs 65,000 XP either way. Banking at level 50 earns it at 1× (the bonus is off at the cap); prestiging at
once earns it at 1.5× (then 1.6×, 1.7× …). At full repeatable claims (~418.6 XP/day since v0.25.5), assuming the bonus applies to
mission and calendar XP:

| Path | Days per Prestige Point |
|---|---|
| Bank at 50 | 65,000 / 418.6 ≈ **155** |
| Prestige now, 1st cycle (+50%) | 65,000 / 628 ≈ **104** |
| 2nd cycle (+60%) / 3rd (+70%) | ≈ 97 / ≈ 91 |

`[CODEX]` cites a community XP census (2026-08-18, 15,920 accounts) with ~228 vs ~152 days. Those figures match the **pre-v0.25.5**
rates (daily 200 + weekly 600/7 ≈ 286 XP/day, no monthly set, no calendar XP), so they are history, not today's numbers. The
census's point still stands: the cost of prestiging is the damage lost while levelling back from 25 (it estimated a level-25 war
build at roughly **2.5× less damage per day** than a level-50 one `[CODEX]`, an estimate), so it is a commitment decision, not a
free win.
