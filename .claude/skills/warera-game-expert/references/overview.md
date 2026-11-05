# WarEra — overview

WarEra (warera.io) is a geopolitical browser game, in active development (sources cover up to **v0.26.1**, September 2026).
Players belong to a country (citizenship), live in a region on the world map, and split their time between an
**economy** (companies producing items) and **combat** (fighting in battles over regions). Countries are run by elected
governments and congresses; players group into **Military Units (MUs)**.

## Core loop `[STRAT-RO]` (the guide's central principle)

> The economy finances the fight; Discord turns individual power into coordinated national impact.

1. **Economy phase** (typically levels 1–15+): skill points into economic skills, build companies toward 6 companies with
   Automated Engine level 5, keep liquidity.
2. **Respec to Fight** when the country needs damage: plan with the build optimizer, buy 7–14 days of consumables, keep
   ~500 money in reserve.
3. **Fight phase**: one Pill cycle per day, hit only on coordinated orders, target ~0.15–0.20 money per 1,000 damage.
4. **Recycle**: sell/reuse scrap, cases (incl. wooden cases), loot and company output to extend the fight; donate to country/MU.
5. Respec back to economy (7-day respec cooldown) or Prestige at level 50.

## The three layers this skill keeps separate

| Layer | Where | Example |
|---|---|---|
| Game mechanics | `data/mechanics.yaml`, domain references | Pill: +60% attack 8 h, then −60% for 15.5 h |
| Romanian strategy & policy | `[STRAT-RO]`/`[POLICY-RO]` sections, `strategy-guidelines.md`, `romanian-community-ops.md` | "Activate the Pill only when a valid order exists" |
| Live state | supplied snapshots ([data-model.md](data-model.md)) | "Region X has a +37% iron deposit right now" |

## Bars and resources at a glance `[RULE]`

| Bar | Spent on | Regen |
|---|---|---|
| Energy | working as an employee; from v0.27 self-work, hiring and training (100 + 10/level) | 10% of max every hour on the hour `[LIVE]` |
| Entrepreneurship | self-work in own companies (removed in v0.27) | same |
| Health | hitting in battle (~10 × (1 − armor%) per hit `[INFER]`) | regen + food (uses Hunger) + MU help |
| Hunger | eating food (1 per item) | regen |
| Stamina | travel (10 per region); not needed to fight since v0.28; removed ~2026-11-10 | +10 per hour, max 100 |

Money is the currency; Gems are a premium currency (e.g. day-7 login reward). Concrete, steel, oil and paper are the
key strategic materials (construction, upgrades, upkeep, orders/laws).

## Where WarEra changes often

Battle bonuses, alliance scaling, deposits, missions, map/travel and political thresholds have changed recently. Always
check [unresolved-mechanics.md](unresolved-mechanics.md) before stating a precise number in these areas.

**v0.27** (live since 2026-10-26) is the largest rework so far: hired employees replace the job market,
government types replace party ethics, deposits and specialization go, strategic resources become income, and the map grows to
742 regions. See [deprecated-mechanics.md](deprecated-mechanics.md) for the full old → new list.
