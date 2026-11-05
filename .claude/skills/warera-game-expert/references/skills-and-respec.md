# Skills and skill reset (respec)

## Points and costs `[RULE][LIVE]`

- 4 skill points per player level (total = 4 × level). `[VERSIONED]` Maxing all **13** point-buyable skills costs **715** points
  (13 × 55) since v0.27.3 removed Leadership; 770 (14 × 55) before, with Leadership (v0.27 → v0.27.2) or Entrepreneurship (until v0.27).
- Buying level *n* of any skill costs *n* points; level 0→n costs **n(n+1)/2** (0, 1, 3, 6, 10, 15, 21, 28, 36, 45, **55**).
- Normal max level 10; Prestige Points add bonus levels above 10 ([prestige.md](prestige.md)).
- `python scripts/progression_calculator.py skill-cost --from A --to B`.

## Skill table `[LIVE]` (value = base + step × level; config of 2026-10-04, pre-v0.27 for the eco rows)

| Skill | Group | Unlock (player lvl) | Lvl 0 | +/lvl | Lvl 10 | Notes |
|---|---|---|---|---|---|---|
| Energy | eco bar | 1 | 30 | 10 | 130 | employee work (until v0.27; see below) |
| Entrepreneurship | eco bar | 1 | 30 | 5 | 80 | self-work (removed in v0.27) |
| Production | eco | 1 | 10 | 3 | 40 | PP per work action (until v0.27) |
| Companies | eco | 5 | 2 | 1 | 12 | max active companies (unlocks at 1 from v0.27) |
| Management | eco | 10 | 4 | 2 | 24 | probably max number of workers you can employ `[WIKI-ONLY]` (removed v0.16.0, re-added later; reworked in v0.27) |
| Attack | combat | 1 | 100 | 25 | 350 | |
| Precision | combat | 1 | 50 | 5 | 100 | overflow >100% → +4 Attack per % |
| Critical Chance | combat | 5 | 10 | 5 | 60 | overflow >100% → +4 Crit Damage per % |
| Critical Damage | combat | 10 | 100 | 20 | 300 | |
| Armor | combat | 5 | 0 | 6 | 60 | total/(total+40) |
| Dodge | combat | 10 | 0 | 4 | 40 | total/(total+40) |
| Health | combat bar | 5 | 100 | 10 | 200 | |
| Hunger | combat bar | 10 | 4 | 1 | 14 | |
| Loot Chance | combat | 1 | 5 | 2 | 25 | % case chance per valid hit |
| Stamina | map bar | 1 | 100 | — | — | only level 0 |

The guide's "Eco" build = Energy, Entrepreneurship, Production, Companies, Management.

### v0.27 economy skills `[RULE]` (2026-10-26 ~14:00 UTC; `skills.economy_values`)

| Skill | Until v0.27 | From v0.27 (`[LIVE-CLIENT]` = read from the live client, 2026-10-26) |
|---|---|---|
| Energy | 30 + 10/level; employee work | **100 + 10/level** (lvl 10 = 200); pays self-work, hiring, candidate rerolls and training, and resistance/unrest contributions (in-game text) `[LIVE-CLIENT]` |
| Entrepreneurship | 30 + 5/level; self-work | **removed**, points refunded (absent from the live client) |
| Production | 10 + 3/level PP per action | self-work gives **30 + 3/level** (lvl 10 = 60); now flagged a **bar** in the client (`isABar`) |
| Management | 4 + 2/level max workers | value **1 + 1/level** (11 at level 10) `[LIVE-CLIENT]`; **+2% employee production per point**, so 22% at level 10; no longer caps hires. `[VERSIONED]` Since v0.27.3 (2026-10-29) it also does Leadership's job: each **level** moves training-card odds off Common and adds **+2 to event checks** `[LIVE-CLIENT]` |
| Leadership | — | **v0.27 → v0.27.2 only**: value **0 + 1/level** (10 at level 10) `[LIVE-CLIENT]`; each level "moved card odds off Common": Common −2, uncommon +1, rare +0.6, epic +0.3, legendary +0.1 ([employees-and-wages.md](employees-and-wages.md#training-rule-employeestraining)), and helped event checks; unlocked at 1 (U-CDX-4). **Merged into Management by v0.27.3**: points refunded, gone from the live config and client (2026-10-30) `[VERSIONED]` |
| Companies | 2 + 1/level, unlocks at 5 | unchanged value; unlocks at **level 1** `[LIVE-CLIENT]` |

The combat skills are unchanged in the live v0.27 client (same base, step and unlock levels as the table above). The client
also has a separate **feature gate** `fightSkills: 10` (`featureUnlockLevels`), the "military skills at 10" of the article, next
to the per-skill `unlockAtLevel` 1/5/10. How the two interact in the menu isn't visible from the config `[GAP]` (U-V27-13).

- Everyone gets **1 free skill reset with no cooldown** to rebuild (one-off, from the 2026-10-26 deploy). v0.27.3 (2026-10-29)
  gave everyone **another one**, with no cooldown, for the refunded Leadership points.
- **Skill presets**: save 3 builds (10 with premium) and load one when you want it. Loading a preset presumably still costs a
  normal reset `[GAP]`.
- `[VERSIONED]` From v0.27 to v0.27.2 the client had **14** point-buyable skills (9 combat + Energy, Production, Companies,
  Management, Leadership), so 770 points (14 × 55) maxed everything. Since v0.27.3 the live config and client list **13** (no
  Leadership), all 10 levels on the same cost table: **715** (13 × 55), which a guide's "715" now matches.
- `[LIVE-CLIENT]` Above the table's last level the client extends a skill's value in a straight line (same step), which is how
  Prestige bonus levels are valued ([prestige.md](prestige.md)).
- *Derived:* the "Eco" build becomes Energy, Production, Companies and Management (plus Leadership from v0.27 to v0.27.2). The BuhDeuce order and the
  ECOBUILD model below are built on Entrepreneurship and the job market, so they are **outdated from v0.27**: keep them only as
  history until a new guide appears.

### v0.27 builds `[STRAT-EXT]`

*Derived:* self-work gives `0.24 × Energy × Production` PP a day (Energy refills 10% an hour, 10 Energy per action), i.e.
`7.2 × (10 + Energy level) × (10 + Production level)`: 720 PP/day at 0/0, 2,880 at 10/10. For a fixed number of levels the
product is largest with **Energy level = Production level**, which is Wodkabouter's "1:1, no more lookup tables". Energy spent on
hiring and training (10 per action) comes out of that self-work.

Launch-day advice from the v0.27 community guides (source `V027_GUIDES`), not tested over time:

| Guide | Economy players | War players |
|---|---|---|
| Wodkabouter | Some Leadership first; after the first round of training, Management : Energy/Production about 1 : 2; long-run upkeep build 10 Production, 10 Energy, 10 Companies, 5 Management, 5 Leadership | under ~6 companies: skip Management and Leadership |
| babeuce | 12 companies, max Leadership; a first week of all-out Energy (to train 12 × 3 employees daily), then Management : Energy 1 : 1; **no points in Production**, since you'll rarely self-work | no extra eco points beyond Companies and "luck" (no eco skill has that name; probably Loot Chance); a war player farming eco between wars: Energy and Leadership |
| fish, Piraterer | start with Leadership and Energy to hire and train; move points to Management once the employees are developed (fish: reshuffle after a few days); scale Leadership with the number of employees | don't build up employees if you'll cut companies for a war build within ~2 weeks |

All three predate v0.27.3. Read their "Leadership" as Management, which now holds both jobs, so their Management : Energy
ratios understate Management for players who train many employees *[Derived]*.

The guides disagree on Production. babeuce spends the Energy on training rather than self-work; Wodkabouter values a Production
or Energy level at ~12 money a day against ~5 for a Management level (36 employees at Production 12, PP value 0.1; see
[employees-and-wages.md](employees-and-wages.md#derived-economics-derived--check-against-live-data)).

## Economy skill plan to level 15 `[STRAT-RO]`

The first 60 points (levels 1–15) go predominantly into economy (the guide's infographic with the exact split is not
available as text `[GAP]`). Rationale: a fight build without an economy forces you to sell assets, fight without Pills, or
depend on bounties; a solid economy buys the freedom to fight efficiently later.

`[STRAT-EXT]` BuhDeuce's order (source BUHDEUCE) is an **order, not a table by level**:
- Production 1 → Energy 1 → P2 → E2 → P3 → E3 → P4 → P5 → E4 → Entrepreneurship 1 → En2 → P6 → E5 → P7 → E6, which ends "by level ~20", then war.
- The Companies skill is bought **whenever you're at the company cap** (2/2, 3/3, …), not at fixed levels.
- War Era Coach's table by level 1–15 is that coach's own conversion of this order.

`[STRAT-EXT]` The economic build calculator (source ECOBUILD) values a build in coins/day:
- **Formula:** job = Energy/10 × 2.4 × Production × wage × (1 − tax), plus self-work = Entrepreneurship/10 × 2.4 × (1 + company bonus) × Production × value of one production point. Here 2.4 = 24 h ÷ 10 per action, and the skill values are 30+5/level, 30+10/level and 10+3/level.
- **Site inputs:** the first public offer (wage capped at 0.15), that company's bonus, the iron price, and 9% tax.
- **Its best build per budget doesn't stack** (2026-10-25 run): at 85 of 165 budgets, the next best build lowers a skill, which means a paid reset with a 7-day cooldown.
- **An add-only order works almost as well:** take the step with the best coins/day per skill point, saving points for it when needed. It stayed on average within ~2% of the per-budget best across four wage/price scenarios. Taking whatever is affordable instead lost 5–7%.
- **Not in the model:** Management, Automated Engine output, and gear that raises skill totals.

The bot's `/economy` and `/progression` (`SKILL_ORDER`) use this model (warerabot-dev skill). Both depend on the job market and
Entrepreneurship, which v0.27 removed; they need rework now that v0.27 is live.

## Skill reset `[RULE][LIVE]` (`respec.*`)

| Property | Value |
|---|---|
| Cost | 0.5 money per allocated skill point (~2 money per level) — was 1.0 until v0.16.0 (2025-07-13) |
| Cooldown | 7 days — was 14 until v0.16.0 |
| Prestige Points | refunded on reset (can be re-allocated) |
| Free resets | Prestige grants one; occasional free resets after big updates — never plan on them (v0.27 and v0.27.3 each gave everyone one, no cooldown) |
| Companies over the new limit | deactivated at random, **not** deleted; reactivate automatically when the limit returns; you can toggle manually |

`python scripts/progression_calculator.py respec --level 40` → 160 points → 80 money.

## Before a Fight respec — checklist `[STRAT-RO]`

Optimizer run with real profile/rank and a conservative bonus; build chosen by cost/1k and sustainable days; armor/dodge
breakpoints checked; 4–6 companies left active and manageable; ≥500 money liquid after purchases; 7–14 days of Pills, food,
ammo (+10–20%); gear count from durability %; reserve oil for travel (until v0.27.4; fighting needs none since v0.28); fighter role, MU and notifications active; respec date
agreed with national needs (or synced with Prestige at level 50). Don't put points into Loot Chance before the damage core is
complete. When returning to economy: remember the 7-day cooldown and keep company storage empty so nothing is lost.

> Common mistake: the "bomb" build that empties everything in one fight and stays inefficient for six more days is usually
> worse for the country and more expensive for the player than a sustainable build.
