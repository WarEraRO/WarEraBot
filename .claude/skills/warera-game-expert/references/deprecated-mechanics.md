# Deprecated and replaced mechanics

Systems the sources describe as replaced/removed. Don't present these as current. Dates are unknown unless stated.

| Old behaviour | Replaced by | Source | Notes |
|---|---|---|---|
| Hit any battle anywhere with one click (no position) | Player position on the map; Move button; Stamina/oil travel; fight from launch/attacked/disputed region | GUIDE 24, 24.5 | Community view: the old system favoured 1–2 giant alliances. **Reversed by v0.28** (2026-11-03): hit from anywhere again (see below) |
| Travel missions measured in kilometres | Missions count regions crossed; new "Move somewhere" and "Collect a wooden case" missions | GUIDE 10.2 | |
| Fixed deposit production bonus (likely 30%) | Random 20–40% per deposit, fixed until depletion | GUIDE 17.1; LIVECFG key 30 | Old value inferred from config key |
| Lower patriotic bonus (value unknown) | +20% | GUIDE 33.2 | |
| Earlier alliance bonus model (unknown) | World-development curve +20 … −20 | GUIDE 33.4 | Live config conflict |
| Battles in the Orders list sorted by age | Ranked orders #1…#99, drag-to-reorder, auto-renumbering | GUIDE 34 | |
| Joining country chat only after the welcome window | Added to country chat from account creation; country picked on sign-up screen | GUIDE 3.10 | |
| intel.warera.wiki/builder as reference build tool | SpyWarEra Build Optimizer | GUIDE 25.1 | Tooling, not a game mechanic |
| Vote at level 15 | Vote at level 20 + 7 days since citizenship change | GUIDE 50.2 vs LIVECFG | change date unknown |
| Tournament MU emptied after registering could win by walkover | Emptied MU is eliminated | GUIDE 41.3 | |
| Tournaments starting with <2 entries | Cancelled with notification | GUIDE 41.3 | |
| Shorter beginner mission lists (14, then 20 per screenshots) | 25 missions, auto-added to old accounts | GUIDE 10.1 | |
| Possibly: contract auction 0.05 step/min, 30 s extension | Live: 0.01 step/min, 60/60 extension | GUIDE 38.1 vs LIVECFG | unresolved — could be a guide error |

When a user relies on any left-column behaviour, correct it and cite the replacement.

## Removed or replaced by v0.27 (live since 2026-10-26; article `6ade08f7899288ce9f0bfe36`)

The deploy is confirmed: the live client served v0.27 on 2026-10-26 (`LIVECLIENT_V027`; no Entrepreneurship, employee config
present). Treat the "Old" column as history. Server-side rows (deposits, specialization, ethics, strategic-resource income) rest on
the article alone until live data shows them, except deposits (`region.depositsEnabled` false), strategic-resource production
bonuses (`region.resourcesBonus` removed) and loyalty (`worker.fidelity*` removed), which the live config of 2026-10-26 confirms.

| Old | New | Notes |
|---|---|---|
| Job market: players work in other players' companies for an owner-set wage | Hired employees (game characters) with automatic hourly wages; players can only work for others as **managers** | [employees-and-wages.md](employees-and-wages.md) |
| Entrepreneurship bar (30 + 5/level) for self-work | Removed (points refunded); self-work uses **Energy** (100 + 10/level) | `skills.economy_values` |
| Production skill 10 + 3/level PP per action | Self-work gives 30 + 3/level | |
| Management = max workers (4 + 2/level) | +2% employee production per point | `skills.management_effect` |
| No Break Room (removed in v0.22.0); Management caps the workers | Break Room L1–L3: 1–3 employees | `company.break_room_levels` |
| Worker loyalty +1%/day, max 10% | Gone; employee same-good streak +1%/day, max 20% | |
| Wage band ±30% of the 24 h average; 24 h job leave lock | Employee-set wages; manager pay 80–120% of average; 24 h manager contract lock | |
| Party ethics (3 points; Fanatic versions; Unethical) | Country **government types**, 30-day cooldown | [government-types.md](government-types.md) |
| Parties could start/fund a resistance | Can't; pending motions fail at no cost | |
| Deposits (random +20–40%, 12 h spawns) | Turned off | |
| Country specialization (law, 10-day cooldown) | Removed | |
| Strategic resources boost production (+5/+0.5/+0.25%) | Daily income = development of their original country (×2, core development, since v0.27.2) | `country.strategic_resource_income` |
| Unlinked regions earn −50% development income | Full income (the −25% defense malus is untouched) | `region.unlinked_development_malus` |
| Self-work tax (undocumented before; v0.27 says it "is gone") | None; income tax on employee wages + new manager tax | `country.taxes`, U-V27-2 |
| Candidacy at level 15 | Level 20 | `election.candidate_min_level` |
| Market at level 7, chat at level 8 | Market (and MUs) at 5; chat from level 1 with slow mode until 15 | `progression.unlock_levels` |
| Starting bag: 5 money, 50 concrete, 20 oil; random raw first company | 25 money (100 since v0.27.2), 100 concrete, 150 oil; first company Iron | `progression.starting_bag` |
| Wooden cases: every case 20–80 PP; odds 65/20/13/2 | Budgets by rarity 20–40 / 40–70 / 80–130 / 160–260; odds 60/25/12/3 | `map.wooden_case` |
| Daily login day 7: 35 money | 50 money | |
| "Move a company" mission; "Find a job" = a worker job | Mission removed; "Find a job" = a manager job | |
| Premium: open 10 cases at once | 50 | |
| Changing a company's product needed an empty storage | Not needed | |
| Elections with no candidates (behaviour undocumented) | The current president stays | |

UI labels that went with these systems (Job offers, Fidelity Bonus, Wage per production, Ethics, Specialty, Premium …) and what
replaced them: [ui-guide.md](ui-guide.md#old--new-labels-v026--v027), from the game's English catalog before and after the deploy.

## Changed one day later by v0.27.1 (2026-10-27, article `6ae0defd260ab3cd58036d7a`)

These v0.27 rules lasted about a day. Answer questions about 2026-10-26 with the "v0.27" column.

| v0.27 (2026-10-26 → 27) | v0.27.1 (from 2026-10-27) | Registry |
|---|---|---|
| Firing a hire younger than 24 h counted as a reroll (current reroll Energy price) | Firing is free (client `fire.rerollWithinHours` removed) | `employees.hiring` |
| Events only for employees hired ≥ 48 h ago | Right after hiring (client `minHiredHours` 0) | `employees.events` |
| 1% risk of death per battle in the employee's region | No deaths in battles "for now" (client constant still 0.01, G-ART-4) | `employees.retention` |
| Homesick penalised anywhere outside the home country | Not in the home country's occupied regions (server-side, G-ART-5) | prose only |
| Manager wages at launch levels; no pay in a company without employees | Wages divided by 10; paid every hour even with no employees; can leave a paused company | `employees.managers` |
| Alliance leave cooldown suspended to 2026-10-30 (config only) | Also reset; off until 30 October (announced) | `alliance.cooldowns` |

### Job market and player workers (until v0.27)

Kept for history and for reading older guides. Do not apply after the v0.27 deploy.

- Workers spent **Energy**; each work action produced their **Production** PP for the employer, who paid a **wage per PP**
  (gross). The job market was sorted by **after-tax** wage. If the employer's balance couldn't cover the wage, the session failed.
- Limits: total workers = **Management** (2 + 1/level from v0.22.0, doubled to 4 + 2/level on 2026-01-26; the Break Room
  L1–L5 = 2–10 workers and daily hires existed until v0.22.0, 2026-01-09). Wage band **±30% of
  the 24 h average** (v0.17.0; since v0.22.0 an out-of-band wage was adjusted instead of firing the worker; wages could be lowered
  only 24 h after joining, v0.23.0, and the worker could accept or decline, v0.22.2). A new worker couldn't leave for **24 h**
  (v0.17.7). Family Group members couldn't work for each other.
- Tax flow: the company country's **income tax** was withheld; an occupied core region diverted **1% of the tax per resistance
  point** to the core country (v0.16.12); a worker employed abroad sent **30%** of their tax home, out of the host's share (U-ECO-8).
- **Loyalty** (`employees.loyalty`): +~1% per working day at the same company, max 10%, applied after work and not paid as wage;
  lost on leaving or firing, kept on transfers between the same employer's companies.
- **Maximum profitable wage** (F-MAXWAGE): `Max wage/PP = (1 + bonus + loyalty) × (price − input cost per unit) / recipe PP`.
  Example: steel 1.80, iron 0.12, +34% bonus, 5% loyalty → 1.39 × 0.06 = **0.0834**/PP
  (`economy_calculator.py wage`, which models only this old system).
- Moderation: reciprocal minimum-wage employment and wages outside **0.8×–1.2× the normal wage** were boosting indicators
  ([account-rules-and-security.md](account-rules-and-security.md)).
- `[STRAT-RO]` of the time: compare net, not gross; retention (loyalty) can make a marginal worker profitable; never overpay;
  beginners shouldn't hire early.
- Wage levels `[OBS]` (`[CODEX]`, for reading old data): the job market showed an **allowed wage range** the game moved over time:
  **0.106–0.159** per PP in August 2026 and **0.117–0.176** on 2026-10-05. Measured wages between players rose from ~0.073 (August
  2025) to ~0.132 (October 2026). The income tax came **off the worker's pay**, not on top for the employer; the job card said so
  ("2.5% income tax is deducted from the earnings when working in this company", seen 2026-09-09). Engine output and self-work
  were never income-taxed. (For v0.27 the same question is open again: U-V27-4.)

## Changed by v0.27.3 (2026-10-29, article `6ae39f39b9d173140341a461`)

Answer questions about 2026-10-26 → 28 with the left column.

| v0.27 → v0.27.2 | v0.27.3 (from 2026-10-29) | Registry |
|---|---|---|
| **Leadership** skill (0 + 1/level): training-card odds, event odds | Merged into **Management**; points refunded, one more free reset; 13 skills, 715 points to max | `skills.economy_values`, `employees.training`, `employees.events` |
| Responsibility cancelled 10% of each happiness loss per point | +3 happiness per point | `employees.stats`, `employees.happiness` |
| Candidate card: one hint; 50% of hires had a trait | All stats and the wage shown; every hire has exactly one trait | `employees.hiring`, `employees.stats` |
| Firing: coworkers −5 for 24 h; employee transfer −5 for 7 days and a 24 h fire lock | Both free; a new hire can't be fired for 12 h | `employees.hiring`, `employees.happiness` |
| **Sprinter** trait: +50% for 24 h after arrival | **Early bloomer**: +6 Production until 40, −2 per 10 years, gone at 60 | `employees.stats` |
| Luck in events: `(Luck − 3) × 4` / `× 2` | `Luck × 4` / `× 2` | `employees.events` |
| Rehab: mixed (Uncommon) or bad (Rare) trait | Bad traits only, always Rare | `employees.training` |
| Specialist: a random good | The company's good (hire and training) | `employees.stats` |
| In-game profit estimate: average PP value of all goods | The produced good's PP value | prose only |
## Changed silently (no article): toolbox cap 2026-10-29, Trainer and Lucky charm 2026-10-31

Found by live checks (`LIVECLIENT_20261101`, `LIVEAPI_20261101`); the Trainer/Lucky charm change was first reported in the
community article `6ae682c7470184738824c070`.

| Before | After | Registry |
|---|---|---|
| Toolbox chance capped at 2%/h (Scavenger: ×2 chance and ×2 cap, 4%/h) | No cap: 0.1% per Luck point per worked hour (Scavenger ×2) — from 2026-10-29 | `employees.tools` |
| **Trainer**: every coworker trains twice a day | 2 extra sessions a day per Trainer, shared by its coworkers, refill 00:00 UTC — from 2026-10-31 | `employees.training` |
| **Lucky charm**: +3 Luck to whoever is beside it right now | +3 Luck to whoever was beside it at 00:00 UTC, kept until the next reset even after a transfer — from 2026-10-31 | `employees.stats` |

## Changed by v0.27.4 (2026-11-02, article `6ae8bb12bcc26a2f5712ec9d`)

Answer questions about 2026-10-26 → 11-01 with the left column.

| Before | v0.27.4 (from 2026-11-02) | Registry |
|---|---|---|
| Age +1 year per calendar day | +1 year per day worked or trained; frozen in a disabled company | `employees.stats` |
| Disabled company: employees idle but still ageing and trainable | Employees on hold: no work, ageing or training | `employees.stats`, `employees.training` |
| Bully: mixed trait | Bad trait (Rehab / Clean slate can remove it) | `employees.stats` |
| Wild card: Uncommon, +1 stat | Rare, +2 stat | `employees.training` |
| New habit offered a mixed trait as a Rare card | Mixed traits can't be taught; New habit is Epic (good traits) only | `employees.training` |
| — | Reroll card (Uncommon): a new hand, free | `employees.training` |
| A tool stayed, unused, with an employee moved to a company it doesn't fit | It returns to your inventory | `employees.tools` |
| Event costs (e.g. Eureka 2, convince to stay 5, Night Classes course 3 wage-days; Mentor 10 Energy; per Elereo's dev-server guide, U-V274-4); Van Race ×2; Gambling Debts ×1 | The 23 cut costs 0.1–1.9 wage-days (most under 0.75), Energy 1–5; Van Race ×3; Gambling Debts ×2 (full list: [employee-events.md](employee-events.md#v0274-rebalance-versioned)) | `employees.events` |
| Crafting at level 10 | Level 7 | `progression.unlock_levels` |
| Vote: 7 days after any citizenship change | No wait during a new country's first 14 days | `election.vote_citizenship_lock` |

## Changed by v0.28 (2026-11-03, article `6aea1496b615c31fa0eb4152`; second step scheduled ~2026-11-10)

Answer questions about 2026-09-16 → 11-02 with the left column. Rows marked ~11-10 are `[SCHEDULED]` ("in 7 days"); confirm with
the live config's `mapTravel` flags before calling them done.

| Before | v0.28 | Registry |
|---|---|---|
| Fight only from the launch / attacked / disputed region; Move button with a travel cost | Fight in any battle from anywhere (2026-11-03; config `battle.locationGateEnabled` false) | `war.attack_origin` |
| Travel between regions with Stamina (10 per region) and oil (2 per region beyond Stamina) | No movement, no Stamina (~11-10) | `map.stamina`, `map.oil_per_region` |
| Free trip home every 12 h | Gone with movement (~11-10); Move home's fate not stated | `map.move_home` |
| Wooden cases spawn on the map (25%/h + Loot chance, max 5, 48 h) | No map spawns; held cases still open; market listings returned, buy orders refunded (~11-10) | `map.wooden_case` |
| Milestones "Cross regions on the map", "Collect wooden cases" | Disabled, levels saved for a possible return (~11-10) | `milestones.map_ladders` |
| Travel / wooden-case missions | Replaced by other missions (~11-10) | — |
| Nationalist +2 Responsibility and +5 happiness (+11); Statist +2 Responsibility (+6); Foreman +3 Responsibility per coworker (+9) | Direct happiness on their own line: Nationalist +10, Statist +6, Foreman +9 | `employees.happiness` |
| 71 old links open for 10 days of grace (v0.27) | Closed; longest shortest path 20 regions (was 19 stated, 18 measured on the old map) | `map.max_region_distance` |

## Dated changes from the official patch log (`data/patch-history.yaml`, v0.0.2 → v0.17.7)

| Old | New | Version / date |
|---|---|---|
| Pill 24 h buff / 24 h debuff | 8 h / 16 h (then 15.5 h debuff, v0.25.1) | v0.17.7, 2025-10-04 |
| No ranking loot pool | 3% per 1k damage to the top 30% (2.5% from v0.21.0; removed in v0.24.1) | v0.17.7, 2025-10-04 |
| MU help: 10 health, helpers +1 | 5 helpers × 2 HP | v0.17.5 (2025-08-31) → v0.17.6 (2025-09-04) |
| Crafting/merge cost in money; company move/change in money | steel; concrete | v0.17.6, 2025-09-04 |
| Deposit depletion −50/h; deposits every 24 h | −0.5% of initial quantity/h; every 12 h (then 1–5 days, v0.22.0) | v0.17.2, 2025-08-24 |
| No citizenship cooldown | 5 days (30 from v0.23.0) | v0.17.1, 2025-08-21 |
| No occupier malus | −30% (−50% from v0.23.0) | v0.17.1, 2025-08-21 |
| Loot: chance at end of battle | per-hit loot, stacks above 100% | v0.17.0, 2025-08-15 |
| Deposit bonus +20% | +30% (random 20–40% from v0.25.5) | v0.16.12, 2025-08-04 |
| Tax hijack 0.5% per resistance point | 1% (removed in v0.25.1) | v0.16.12, 2025-08-04 |
| Miss deals 0 damage | half damage | v0.16.5, 2025-07-21 |
| Contracts max 10 per 1k | 1 → 2 → now ×6 of average wage | 2025-07-14, 2025-08-15 |
| Oil = 10 PP + 10 petroleum | 1 PP + 1 petroleum | v0.16.1, 2025-07-14 |
| Skill reset 1 money/point, 14-day cooldown | 0.5 money/point, 7 days | v0.16.0, 2025-07-13 |
| Construction and Management skills | removed (Management re-added later as max workers; from v0.27 +2% employee production per point) | v0.16.0 |
| Production skill +2/level | +3/level | v0.16.0 |
| Region upkeep in money, construction in money | oil, steel | v0.16.0 |
| Strategic resources 3+ copies +1% | +0.5% (now +0.25%) | v0.16.0 |
| Max wage tax 99% | 45% | v0.15.15, 2025-06-26 |
| Congress 10 seats | 2 + active/10 → 2 + active/20 → clamp(…, 5, 50) | 2025-06-15 / 2025-06-18 |
| Presidential election on the 4th | 1st; congress on the 5th | v0.15.13, 2025-06-15 |
| Dodge consumed nothing | dodge still uses ammo and weapon durability | v0.15.12, 2025-06-03 |
| Vote at any level | level 5 → 15 → 10 → 15 → 20 | v0.15.8 (2025-05-28), v0.21.1/2 (2025-12-26/28); later changes undated |
| Unlinked-region malus −10% | −15% → −25% | 2025-01-27 → 2025-05-25 |
| MU help: the helper gives 2 HP at no cost and gets nothing back | the helper also gets +1 health | v0.27, 2026-10-26 (`mu.helperHealthPerHelp` 1, live config) |
| Inactive after 7 days | 3 days | v0.15.1, 2025-05-04 |
| Takeover cooldown 3 days | 5 days (2025-05-01) → 1 day now; min level 3 → 25 | v0.15.0 / v0.15.4 |
| Pill 100 PP + 100 plants | 200 + 200 | v0.15.0, 2025-05-01 |
| Companies cost money | concrete | v0.15.5, 2025-05-16 |
| Weekly missions 30 XP each / 300 set | 50 / 500 | v0.25.5, 2026-08-29 |
| Alliance flat +10% → +10% up to 15% WD | +20% up to 10% WD, −4/pt, floor −20 | v0.25.0 (2026-06-10) → 2026-09-01 (v0.25.5) |
| Hit from anywhere | stand in the launch region (attack) or target region (defense); target still adjacent (U-CMB-12) | v0.26.0, 2026-09-16 |
| +15% defending own core region (v0.15.15) | removed, replaced by patriotic +10% | v0.23.0, 2026-02-13 |

## Dated changes from the official articles v0.17.8 → v0.26.1 (`data/patch-history.yaml`, ingested 2026-10-25)

A newer patch overrides an older one where they overlap, so a row's "New" can itself be replaced by a later row.

| Old | New | Version / date |
|---|---|---|
| Merging items | dismantle into scrap, craft from scrap (exact item ×2 steel); no item offers below 100% state | v0.18.0, 2025-10-22 |
| Helmet and skill crit damage | ×2 | v0.18.0, 2025-10-22 |
| — | losing the region you attack from: −25% | v0.19.0, 2025-10-29 |
| 8 development per region | `((active × avg level) / 20)` then 0.95 (power or factor, U-DEV-1a), split over core regions | v0.20.0, 2025-12-14 |
| Order costs | ×2 (money) | v0.20.1, 2025-12-15 |
| Daily rewards + daily XP | missions (daily, weekly, beginner); weekly XP 1050 → 1700 | v0.21.0, 2025-12-26 |
| Attack % modifiers added | multiplied (pill × ammo × rank); military ranks added | v0.21.0, 2025-12-26 |
| Pill +80% | +60% | v0.21.0, 2025-12-26 |
| Country production bonus on everything | only on the specialization item (law, 10-day cooldown) | v0.21.0, 2025-12-26 |
| Vote level 5, candidacy 0, takeover 3 | 15 / 15 / 15, then vote and candidacy 10 (2025-12-28) | v0.21.1 / v0.21.2 |
| Strategic resources 3 / 1 / 0.5% | 5 / 0.5 / 0.25% | v0.21.4, 2025-12-31 |
| Deposits: depleting quantity, every 12 h | 1–5 days; hourly roll, 10% chance | v0.22.0 / v0.22.1, 2026-01-09 |
| Break Room L1–L5 (2–10 workers) | removed; Management skill = max workers (2 → 12) | v0.22.0, 2026-01-09 |
| Out-of-band wage: worker fired | wage adjusted; worker loyalty +1%/day (max 10%) | v0.22.0, 2026-01-09 |
| Can't hit below 10 Health | can, depending on armor | v0.22.0, 2026-01-09 |
| Management 2 → 12 workers | 4 → 24 ("temporary ×2", still live) | 2026-01-26 |
| Self-defense +15% | patriotic +10% | v0.23.0, 2026-02-13 |
| Occupier malus −30% | −50% | v0.23.0, 2026-02-13 |
| Citizenship cooldown 5 days | 30 days | v0.23.0, 2026-02-13 |
| High order ×3 Low | ×4 Low | v0.23.0, 2026-02-13 |
| Resistance per point (max 40) | bar = region development × 100; reset to 0 after a liberation battle | v0.23.0, 2026-02-13 |
| — | parties, ethics, unrest/civil war, Pacification Center | v0.23.0, 2026-02-13 |
| — | 1 h before a region can be attacked again | v0.23.2, 2026-02-26 |
| Active citizen = level 3+ | level 10+ | v0.23.4, 2026-03-04 |
| Unrest daily decay | removed (energy/health action instead) | v0.23.4, 2026-03-04 |
| Pacification −2..−10%/day; bunker/base for everyone, 6 h activation | −0.05..−0.25%/h; citizens + allies, 12 h; upgrades 8 h between levels | v0.23.4, 2026-03-04 |
| Armor/Dodge exponential, armor cap | `total / (total + 40)`, no cap; armor 4 → 6 per level | v0.24.0, 2026-03-21 |
| Base health 50, attack 20/level, food flat 10/20/30 HP | 100, 25/level, 10/15/20% of max | v0.24.0, 2026-03-21 |
| Unrest multiplier 100 | 50 | v0.24.0, 2026-03-21 |
| Loot chance accumulated, rolled at the end; ranking pool | per-hit case + elite case; item pools per 200k / 500k | v0.24.1, 2026-03-30 |
| — | government wages (President 3%, others 1%) | v0.24.1, 2026-03-30 |
| Weekly cases for country rankings | removed; user/MU tiers 1/3/6/10/20/30 | v0.24.1, 2026-03-30 |
| Bounty delay 1 min | 3 min; national bounties and contracts disabled | v0.24.3, 2026-04-03 |
| Proposal-based contracts | reverse auctions (launch: step 0.05, last 30 s +30 s; config now 0.01, 60/60) | v0.24.4, 2026-04-25 |
| — | non-aggression windows 24 h / 72 h / 72 h; 5-day liberation cooldown | v0.24.7, 2026-05-19 |
| Bilateral allies list, ally bonus +10% | alliance entities, WD-scaled bonus, paper upkeep; pacts; sworn enemy rework | v0.25.0, 2026-06-10 |
| Politics paid in money | paper (laws, orders, party motions, treaty upkeep) | v0.25.0, 2026-06-10 |
| Bunker/base full for allies | half for allies | v0.25.0, 2026-06-10 |
| Missions claimed by hand | auto-claim (back to by hand in v0.25.5) | v0.25.1, 2026-06-14 |
| Resistance tax/development hijack (max 40%) | removed; 30% of a foreign worker's tax goes home; region transfer tax | v0.25.1, 2026-06-14 |
| Pill debuff 16 h | 15.5 h | v0.25.1, 2026-06-14 |
| Flat daily reward | 7-day calendar + come-back rewards; Prestige | v0.25.2, 2026-08-19 |
| Tournaments scheduled by hand | registration, every two weeks | v0.25.4, 2026-08-19 |
| Patriotic +10% | +20% | v0.25.5, 2026-08-29 |
| Deposit bonus +30% | random 20–40% | v0.25.5, 2026-08-29 |
| No total floor | total battle bonus floored at −100% | v0.25.5, 2026-08-29 |
| Hit from anywhere | position, Stamina, oil travel, wooden cases | v0.26.0, 2026-09-16 |
| Stamina or oil, never both | Stamina first, oil for the rest | v0.26.1, 2026-09-17 |
