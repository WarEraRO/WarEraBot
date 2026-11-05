# Data model for script / API game state

This is the **state layer**. References and `data/*.yaml` are the **mechanics layer**. Scripts that gather WarEra data should
emit snapshots in this normalized shape so Claude and `scripts/validate_game_snapshot.py` can reason over them.
Machine-readable schema: [../data/snapshot-schema.yaml](../data/snapshot-schema.yaml). Fetching code: sibling skill `warera-api`
(the WarEra tRPC API at api2.warera.io; IDs are 24-hex Mongo ObjectIds).

## Conventions

- **snake_case**, dotted paths in prose: `player.skills.attack`, `battle.terrain_attacker`.
- Every snapshot has `as_of` (ISO-8601 UTC) and ideally `game_version` and `source` (script name, endpoint).
- **Percentages are percentage points** (`deposit_bonus_percent: 37` = +37%). Fractions are flagged by the validator.
- Money in game money; PP as numbers; times as ISO datetimes; durations in hours unless the field name says otherwise.
- `null` = unknown. Never fill unknowns with defaults from references; reasoning must state the gap.
- Flags in the schema: **required**, **volatile** (timestamp it; stale after minutes/hours), **derived** (recompute — never trust
  a supplied value), **never_assume** (if missing, ask/state; don't default).

## Snapshot envelope

```json
{
  "as_of": "2026-10-05T12:00:00Z",
  "game_version": "0.26.1",
  "source": "my_script.py / user.getUserLite",
  "player": {...},  "companies": [...],  "regions": [...],  "market_orders": [...],
  "battles": [...], "battle_orders": [...], "military_units": [...], "alliances": [...], "transactions": [...]
}
```

## Entities

| Entity | Key fields | Relationships | Volatile | Derived | Never assume |
|---|---|---|---|---|---|
| **Player** | id, level (1–50), current_xp, lifetime_xp, prestige_level, skills{code: level}, energy, entrepreneurship, health, hunger, stamina (≤100), money, pill_consumed_at, military_rank | citizenship_country_id → Country; residence_region_id, current_region_id → Region; military_unit_id → MU | bars, money, current_region_id, pill timestamp | pill_phase, is_inactive, skill values (base+step×lvl), spent points | citizenship, current region |
| **Country** | id, development, active_population, citizens, treasury_money/paper/oil, tax_percent (≤45), specialization_item, ruling_ethics[], main_enemy_country_id, main_enemy_days, capital_occupied, unrest_percent, strategic_resources[] | alliance_id → Alliance; capital_region_id → Region; government | treasury, population, unrest | congress seats (F-SEATS), order cost scale | ethics, alliance share |
| **Region** | id, owner_country_id, core_country_id, development, linked_to_capital, deposit_item, deposit_bonus_percent, deposit_expires_at, bunker/base/pacification levels + *_active, resistance, resistance_max | owner/core → Country | owner, linked, deposit, buildings active, resistance | malus applicability | deposit bonus (live value wins) |
| **Company** | id, product (item code), region_id, active, engine_level (1–7), storage_level (1–7), break_room_level (none 2026-01-09 → v0.27; 1–5 before), stored_pp, production_bonus_percent, wage_per_pp, wage_balance | owner_player_id → Player; region_id → Region; workers → Job | stored_pp, bonus, balance | storage_capacity_pp (200×L), engine PP/day, hours to full, profit | production_bonus_percent |
| **Job** | company_id, worker_player_id, wage_per_pp, loyalty_percent (0–10), started_at | → Company, Player | loyalty | loyalty from days | — |
| **MarketOrder** | item, side (buy/sell), price, quantity, observed_at | — | all | mid/realistic price, liquidity | realistic sell price ≠ top listing |
| **InventoryItem / Equipment** | item, quantity, rarity, durability_percent, stats{}, equipped | → Player/MU/Country | durability | real cost (F-ITEM-COST), armor/dodge totals | — |
| **Battle** | id, attacker_country_id, defender_country_id, region_id, launch_region_id, type, round, rounds_won_*, terrain_* (0–300), damage_pool_* (current tick), round_damage_total, battle_damage_total, ended_at | → Country, Region | everything | pool items (F-LOOT), ticks to win | launch region (where attackers had to stand until v0.27.4; since v0.28 only the attack's origin) |
| **BattleSide / BattleRound** | can be embedded: per side damage, terrain, rankings; per round winner, damage | → Battle | | | |
| **BattleOrder** | battle_id, issuer_type (country/mu), issuer_id, side_country_id, priority (low/medium/high), rank (1–99), description | → Battle, Country/MU | rank, priority | bonus value (from priority, not rank) | — |
| **MilitaryUnit** | id, owner_player_id, commander_ids, member_ids, country_id, hq_level (0–4), hq_active, dormitories_level, oil, paper, money, reputation, active_contract_id | → Player, Country, MercenaryContract | stock, hq_active, reputation | HQ oil/day, days of autonomy | hq_active |
| **Government** | country_id, president_id, vice_president_id, minister_*_id, congress_member_ids | → Country, Player | membership | permissions (government.md) | activity of members |

**v0.27 shape changes** (live since 2026-10-26; field names are this skill's, not the API's — check the API):
Player loses `entrepreneurship`; Country gains `government_type`, `government_type_changed_at`, `manager_tax_percent` and loses
`specialization_item` and `ruling_ethics[]`; Region loses the `deposit_*` fields and gains a daily income estimate; Company
`break_room_level` becomes 1–3 and gains `employee_ids`, `manager_id`, `manager_pay_per_management_point`; **Job** is replaced
by **Employee** (production, luck, responsibility, traits[], training_potential, age, expectation_percent, happiness, tool
{type, rarity, worked_hours}, same_good_days, hired_at) and **ManagerContract** (company_id, manager_player_id, pay, started_at).
Never assume an employee's hidden stats before hire, its happiness, or the 7-day PP value.
API names (`employee.getCompanyRoster`, 2026-11-02): **`base.production` is base + trained**; the rolled base is
`breakdown.production.base`, and `breakdown.production.contributions[]` lists trait/coworker Production (no `percent` flag) and
percent effects. v0.27.4 added `lastAgedDay` (UTC date of the last ageing) and `companyDisabled`; the roster's
`hourly.engineMultiplier` is the engine multiplier (2 with a lone Talks to Machines employee). `wage` is per hour.
| **Alliance** | id, member_country_ids, world_development_share_percent | → Country | share | alliance bonus (F-ALLIANCE) | **share** |
| **Treaty** | type (defensive_pact, nap, main_enemy, economic_agreement, non_aggression_window), country_a_id, country_b_id, started_at, expires_at, in_game | → Country | | pact/enemy days → bonus | NAPs are community data, not API |
| **Mission** | period, description, progress, target, completed, claimed, reroll_index | → Player | all | next reroll cost | — |
| **Milestone** | ladder, tier_claimed, progress, next_target | → Player | progress | claimable tiers | XP per tier beyond known points |
| **Tournament** | id, edition (country/mu), registration_closes_at, skill_bonus, max_rarity, registered_ids | → Country/MU | registrants | registration open? | — |
| **Transaction** | from_id, to_id, type, item, quantity, price, reference_price, at | → Player/Country/MU | | price ratio (boosting signal) | reference_price |
| **Bounty** | battle_id, side_country_id, rate_per_1k, budget_remaining, posted_at | → Battle | budget | active_from = posted_at + ~3 min | — |
| **MercenaryContract** | battle_id, side_country_id, budget, min_damage, rate_per_1k, mu_id, status, progress_damage | → Battle, MU | progress | fee (10%), payout per member | — |
| **PatchVersion** | version, released_at, changes[] | → mechanics.yaml entries | | | release date (never guess) |

## Fields a calculation needs (examples)

**Company profitability**: company.product, base PP/day (engine_level, owner's Entrepreneurship & Production, employees'
Energy & Production, active days), company.production_bonus_percent (or region deposit + country specialization + strategic
resources), market prices of the product and each input (realistic, timestamped), wage_per_pp, loyalty per job, storage level and
stored_pp (is production stopped?), employee tax (if net wages matter), move/switch cost and deposit_expires_at for decisions.
From v0.27: owner's Energy and Production (self-work), each employee's Production, expectation, traits, happiness and tool, the
PP value, owner and manager Management, same-good days, core-region flag, the income tax rate, and manager pay.

**Most efficient battle for a player**: active battle_orders (issuer, priority, rank, description) for the player's country and MU;
battle side, type, launch/attacked region; (until v0.27.4 only: player's current_region_id, stamina, oil for travel); diplomacy (patriotic? ally?
alliance WD share, pact days, Main Enemy days, NAP list); buildings active in the relevant region; resistance fill if revolt;
territorial maluses (linked to capital? fighting for occupier?); battle state (round, terrain, damage pools, time to tick); bounty
and contract status (active? eligibility — gov member, contract holder); player's Pill phase, Health/Hunger, consumables and gear
durability. Without the damage formula, rank battles by bonus total, order rank and objective (travel cost until v0.27.4) — not by absolute damage.

## API field traps (from the UNIKHORNE codex, `[CODEX]` 2026-09) — map them before computing

Each cost the codex a wrong answer first. Code that fetches these belongs to the `warera-api` skill; this is what they mean.

| Field | Meaning | Trap |
|---|---|---|
| user `location` / `region` | `location` = region the player **stands** in; `region` = **home** region | treating `region` as the position misprices every trip (checked on two players, 2026-09-16) |
| `skills.stamina.currentBarValue`, `.hourlyBarRegen` | Stamina bar | — |
| `buffs.buffCodes` / `buffs.debuffCodes` containing `cocain` | Pill active / Pill debuff | the item is `cocain`; the mysterious plant is `coca`. Lookups by display name ("pill") find nothing |
| `skills.attack.overflow`, `attack.tournament`, `attack.militaryRankPercent` | Precision overflow as flat Attack; tournament skill bonus as flat Attack (+25 per bonus level); rank % | none of the profile totals contain **battle** bonuses |
| battle side `damages` | damage of **completed rounds only** | add `currentRound`, or a 500k-per-item battle divisor looks like ~387k |
| `battleRanking.getRanking` (POST) for a **round** | needs `roundId` | passing `battleId` (or both) returns `itemCount 0` without an error |
| ranking row `lootItem` | the pool item that rank gets (code) | rows below the item count have none ([battle-loot.md](battle-loot.md)) |

## Reasoning rules for state

1. Validate first (`validate_game_snapshot.py`); mention ERRORs before analysing.
2. State overrides reference values **for this calculation only** (e.g. a region's +38% deposit), and say so.
3. Note the snapshot time; volatile fields older than the decision window (e.g. damage pools > a few minutes) must be called stale.
4. A single observation never rewrites `data/mechanics.yaml`; repeated, consistent observations go through [update-process.md](update-process.md).
5. If state contradicts a mechanic (e.g. round 4 when guide says max 3), report the discrepancy — it may be evidence for a
   disputed mechanic (here U-CMB-1).
