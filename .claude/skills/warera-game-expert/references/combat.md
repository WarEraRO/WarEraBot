# Combat — build philosophy and analysis

## What can and cannot be computed

| Computable (sourced) | Not computable / uncertain `[GAP]` |
|---|---|
| Battle bonus total by source (`combat_bonus_calculator.py`) | Exact stacking order of Pill/ammo/rank vs battle bonuses (inferred) |
| **Expected damage per attempt and per Health bar** (`combat_calculator.py damage`) — estimate | RNG spread of individual hits |
| Armor/Dodge %, breakpoints, HP per hit (min 1) (`mitigation`, `hp`) | Elite-case drop table |
| Military rank bonus from total damage (`rank`) | |
| Precision/crit overflow, Pill phase (date-aware) | |
| Cost per 1k damage and sustainability (from supplied totals) | |
| Regular case odds (30% weapon / 70% gear; 62/30/7.1/0.85/0.04/0.01) | |

For build optimization (which skills/gear maximize damage per money), use the community tool the guide recommends: **SpyWarEra Build Optimizer**
(spywarera.com/tools/buildoptimizer). `intel.warera.wiki/builder` is no longer the reference `[DEPRECATED]`.

## Build philosophy `[STRAT-RO]`

A good build maximizes impact over the whole fighting period, not one click or one bomb. Real cost includes ammo, food,
Pills, gear durability and the economic opportunity lost by moving points out of economy (travel stopped costing fighters
anything with v0.28, 2026-11-03).

- Efficiency target: **~0.15–0.20 money per 1,000 damage** (incl. cases and loot value, excl. bounty income); 0.20–0.25 can
  be acceptable by level, goal and budget (`ro.target_cost_per_1k_damage`).
- Indicative net daily cost: level 25+ → 200–400 money/day; level 35+ → 400–800 money/day.
- Don't sacrifice a week of activity for one explosion. A build that empties you in 3 days produces less total damage over
  7–14 days than a sustainable one.

## Using the optimizer `[STRAT-RO]`

1. Import profile (or enter level and military-rank bonus).
2. Enter the companies you'll keep active (≤ ~6 in fight mode).
3. Set a **realistic battle bonus** — results depend heavily on it (patriotic +20%; alliance may be negative). Run a
   conservative scenario using current order/tooltip values.
4. Select Pill and the conditions you will actually use.
5. Compare builds by net daily cost, cost/1k and market availability of the items.
6. Choose what you can sustain ≥7 days, ideally 14 if mobilization is likely.

Durability % under an item = total durability consumed over the analysed cycle: 200% ≈ two copies, 140% = one full item +
40% of a second — round up when buying.

## Analysing a player for a battle (checklist)

Inputs: level, skills, equipment + durability, ammo/food/Pills, Pill timestamp, citizenship, MU, rank, current region,
battle state (round, terrain, damage pools, tick), orders (rank + priority + description), diplomacy (alliance share, pact,
Main Enemy, NAPs), buildings (active?), resistance fill, territorial penalties, remaining budget.

Questions and where to answer them:
- *Which battle?* → order rank #1 first, then bonus total, location/travel cost, NAPs ([battle-orders.md](battle-orders.md)).
- *Use expensive gear here?* → total bonus vs the ~50% efficiency heuristic, Pill phase, priority ([battle-bonuses.md](battle-bonuses.md)).
- *Wait for bunker/base?* → if the order says "hold until base/bunker" or the obj. allows waiting, yes (activation ~12 h).
- *Bonus breakdown* → `combat_bonus_calculator.py` with tooltip overrides.
- *Buff or debuff?* → `combat_calculator.py pill --consumed-at ...`.
- *7-day sustainability* → `combat_calculator.py cost1k --budget B --daily-cost C`, plus [ammunition-food-pills.md](ammunition-food-pills.md).

## Concrete preparation for 7–14 days `[STRAT-RO]`

| Category | Prepare | Buffer |
|---|---|---|
| Money | respec, purchases, volatility, emergencies | ≥ ~500 liquid after main purchases |
| Pills | 1 per planned cycle | 7–14 + reserve |
| Food | mix from Health/Hunger and optimizer | +10–20% |
| Ammo | build's type | +10–20%; no heavy ammo without justification |
| Weapons/gear | copies per durability % | round up + spares |
| Travel oil | none for fighting since v0.28 (2026-11-03) | before: 2 × regions over Stamina, plus the way back |
| Companies | 4–6 active, liquid | free storage, sellable goods, wages covered |
| Coordination | MU, fighter role, notifications, schedule | confirm before respec |

*History (v0.26–v0.27.4):* fronts 12 regions from home; full bar covers 10 → 100 Stamina + 4 oil each way. Switching fronts twice a day
adds up quickly; for a 7-day campaign on distant fronts, a reserve of a few dozen oil is prudent.

## Self-financing fighter `[STRAT-RO]`

Sell scrap from broken gear; sell cases/elite cases when opening EV is unfavourable; collect wooden cases (until the v0.28 switch-off, ~2026-11-10); sell
company output; sell or reuse loot; take bounties/contracts compatible with national orders (don't switch fronts just for
money); sell premium loot and buy a sufficient cheaper piece (or one reaching the same breakpoint).
*Cycle: economy funds the fight; the fight yields scrap, cases, loot and bounties; these fund the next cycle.*
